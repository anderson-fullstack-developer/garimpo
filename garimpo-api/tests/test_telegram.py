from datetime import timedelta

import httpx
import pytest
from sqlalchemy import select

from app.models import Destination, UserSettings, utcnow
from app.services.channels import (
    AlertMessage,
    ChannelNotConfigured,
    MessageItem,
    PermanentChannelError,
    TransientChannelError,
)
from app.services.telegram import TelegramClient, chunk_text, render_message
from app.services.telegram_webhook import handle_update
from tests.conftest import ALERT, T, make_raw, run_search


class FakeTG:
    """Cliente do Telegram de mentira: guarda as respostas e diz quem é administrador."""

    def __init__(self, admins=()):
        self.admins = set(admins)
        self.messages: list[tuple[str, str]] = []

    def send_message(self, chat_id, text, thread_id=None):
        self.messages.append((str(chat_id), text))

    def get_chat_member_status(self, chat_id, user_id):
        return "administrator" if user_id in self.admins else "member"


def new_code(client, kind):
    r = client.post("/destinations/link-code", json={"channel": "TELEGRAM", "kind": kind})
    assert r.status_code == 200, r.text
    return r.json()["code"]


def private(chat_id, code, first="Ana"):
    return {"message": {"chat": {"id": chat_id, "type": "private", "first_name": first}, "from": {"id": chat_id}, "text": f"/start {code}"}}


def group(chat_id, code, sender=7, title="Revenda", kind="supergroup"):
    return {"message": {"chat": {"id": chat_id, "type": kind, "title": title}, "from": {"id": sender}, "text": f"/link {code}"}}


def channel(chat_id, code, title="Canal"):
    return {"channel_post": {"chat": {"id": chat_id, "type": "channel", "title": title}, "text": f"/link {code}"}}


def db_call(session_factory, update, tg):
    with session_factory() as db:
        return handle_update(db, update, tg)


# ------------------------------------------------------------------ vínculo
def test_private_chat_links_with_start_code(client, signup, session_factory):
    signup(client)
    code, tg = new_code(client, "PRIVATE"), FakeTG()
    assert db_call(session_factory, private(555, code), tg) == "linked"
    dest = client.get("/destinations").json()[0]
    assert dest["status"] == "LINKED" and dest["title"] == "Ana" and dest["isDefault"] is True
    assert "Connected" in tg.messages[0][1] and tg.messages[0][0] == "555"
    assert db_call(session_factory, private(555, code), tg) == "invalid_code"  # código de uso único


def test_group_link_requires_an_admin(client, signup, session_factory):
    signup(client)
    code, tg = new_code(client, "GROUP"), FakeTG(admins={7})

    assert db_call(session_factory, group(-1001, code, sender=99), tg) == "not_admin"  # membro comum
    assert client.get("/destinations").json()[0]["status"] == "PENDING"
    assert "group admins" in tg.messages[-1][1]

    assert db_call(session_factory, group(-1001, code, sender=7), tg) == "linked"
    dest = client.get("/destinations").json()[0]
    assert dest["status"] == "LINKED" and dest["kind"] == "GROUP" and dest["title"] == "Revenda"


def test_channel_link_uses_channel_post(client, signup, session_factory):
    signup(client)
    code = new_code(client, "CHANNEL")
    assert db_call(session_factory, channel(-1009, code), FakeTG()) == "linked"
    assert client.get("/destinations").json()[0]["kind"] == "CHANNEL"


def test_invalid_expired_and_wrong_kind_codes(client, signup, session_factory):
    signup(client)
    tg = FakeTG(admins={7})
    assert db_call(session_factory, group(-1, "codigo-inexistente"), tg) == "invalid_code"

    code = new_code(client, "GROUP")
    assert db_call(session_factory, private(5, code), tg) == "kind_mismatch"  # código de grupo usado no privado
    assert db_call(session_factory, {"message": {"chat": {"id": 5, "type": "private"}, "from": {"id": 5}, "text": f"/link {code}"}}, tg) == "kind_mismatch"

    with session_factory() as db:
        dest = db.scalar(select(Destination))
        dest.code_expires_at = utcnow() - timedelta(minutes=1)
        db.commit()
    assert db_call(session_factory, group(-1001, code), tg) == "invalid_code"  # expirou


def test_chat_already_linked_to_another_account_is_refused(client, signup, session_factory, make_client):
    signup(client, "ana@example.com")
    tg = FakeTG(admins={7})
    db_call(session_factory, group(-1001, new_code(client, "GROUP")), tg)

    bruno = make_client()
    signup(bruno, "bruno@example.com")
    code = new_code(bruno, "GROUP")
    assert db_call(session_factory, group(-1001, code), tg) == "taken"
    assert bruno.get("/destinations").json()[0]["status"] == "PENDING"  # o grupo continua sendo da Ana


def test_same_chat_linked_twice_by_same_user_does_not_duplicate(client, signup, session_factory):
    signup(client)
    tg = FakeTG(admins={7})
    db_call(session_factory, group(-1001, new_code(client, "GROUP")), tg)
    assert db_call(session_factory, group(-1001, new_code(client, "GROUP")), tg) == "already_linked"
    assert len(client.get("/destinations").json()) == 1


def test_start_in_a_group_is_ignored_and_bare_start_shows_help(client, signup, session_factory):
    signup(client)
    code, tg = new_code(client, "GROUP"), FakeTG(admins={7})
    update = group(-1001, code)
    update["message"]["text"] = f"/start {code}"
    assert db_call(session_factory, update, tg) == "ignored"
    assert client.get("/destinations").json()[0]["status"] == "PENDING"
    assert db_call(session_factory, {"message": {"chat": {"id": 5, "type": "private"}, "text": "/start"}}, tg) == "help"


def test_bot_removed_disconnects_and_readding_reconnects(client, signup, session_factory):
    signup(client)
    tg = FakeTG(admins={7})
    db_call(session_factory, group(-1001, new_code(client, "GROUP")), tg)

    kicked = {"my_chat_member": {"chat": {"id": -1001, "type": "supergroup"}, "new_chat_member": {"status": "kicked"}}}
    assert db_call(session_factory, kicked, tg) == "disconnected"
    assert client.get("/destinations").json()[0]["status"] == "DISCONNECTED"

    back = {"my_chat_member": {"chat": {"id": -1001, "type": "supergroup"}, "new_chat_member": {"status": "administrator"}}}
    assert db_call(session_factory, back, tg) == "reconnected"
    assert client.get("/destinations").json()[0]["status"] == "LINKED"
    unknown = {"my_chat_member": {"chat": {"id": -555, "type": "group"}, "new_chat_member": {"status": "kicked"}}}
    assert db_call(session_factory, unknown, tg) == "ignored"


def test_stop_and_status_commands(client, signup, session_factory):
    signup(client)
    tg = FakeTG(admins={7})
    db_call(session_factory, group(-1001, new_code(client, "GROUP")), tg)
    client.post("/alerts", json=ALERT)
    client.post("/monitor/start")

    say = lambda text: {"message": {"chat": {"id": -1001, "type": "supergroup"}, "from": {"id": 7}, "text": text}}  # noqa: E731
    assert db_call(session_factory, say("/status"), tg) == "status"
    assert "Monitor on" in tg.messages[-1][1] and "1" in tg.messages[-1][1]
    assert db_call(session_factory, say("/stop@GarimpoAlertasBot"), tg) == "stopped"
    assert client.get("/monitor/status").json()["enabled"] is False
    with session_factory() as db:
        assert db.scalar(select(UserSettings)).monitor_enabled is False

    stranger = {"message": {"chat": {"id": -777, "type": "group"}, "from": {"id": 1}, "text": "/stop"}}
    assert db_call(session_factory, stranger, tg) == "unlinked"
    assert db_call(session_factory, {"message": {"chat": {"id": 1, "type": "private"}, "text": "oi"}}, tg) == "ignored"


# ------------------------------------------------------------------ rota do webhook
@pytest.fixture
def webhook_env(settings, monkeypatch):
    monkeypatch.setattr(settings, "telegram_bot_token", "123:ABC")
    monkeypatch.setattr(settings, "telegram_webhook_secret", "segredo-do-webhook")
    tg = FakeTG(admins={7})
    monkeypatch.setattr("app.routers.webhooks.TelegramClient", lambda: tg)
    return tg


def test_webhook_rejects_missing_or_wrong_secret(client, webhook_env):
    body = {"message": {"chat": {"id": 1, "type": "private"}, "text": "/start"}}
    assert client.post("/webhooks/telegram", json=body).status_code == 403
    r = client.post("/webhooks/telegram", json=body, headers={"X-Telegram-Bot-Api-Secret-Token": "errado"})
    assert r.status_code == 403 and r.json()["code"] == "FORBIDDEN"


def test_webhook_needs_configuration(client, settings):
    r = client.post("/webhooks/telegram", json={}, headers={"X-Telegram-Bot-Api-Secret-Token": "x"})
    assert r.status_code == 503 and r.json()["code"] == "NOT_CONFIGURED"


def test_webhook_links_a_group_end_to_end(client, signup, webhook_env):
    signup(client)
    code = new_code(client, "GROUP")
    r = client.post("/webhooks/telegram", json=group(-1001, code), headers={"X-Telegram-Bot-Api-Secret-Token": "segredo-do-webhook"})
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert client.get("/destinations").json()[0]["status"] == "LINKED"


# ------------------------------------------------------------------ enviar teste / anúncios escolhidos
def link(client, signup, link_destination):
    signup(client)
    return link_destination("ana@example.com")


def test_destination_test_message(client, signup, link_destination, fake_channel):
    dest = link(client, signup, link_destination)
    assert client.post(f"/destinations/{dest}/test").status_code == 204
    assert "Garimpo test" in fake_channel.texts[0][1]


def test_destination_test_errors_are_clear(client, signup, link_destination, fake_channel):
    dest = link(client, signup, link_destination)
    pending = new_code(client, "GROUP") and client.get("/destinations").json()[-1]["id"]
    assert client.post(f"/destinations/{pending}/test").status_code == 409  # ainda não vinculado

    fake_channel.error = ChannelNotConfigured("sem token")
    r = client.post(f"/destinations/{dest}/test")
    assert r.status_code == 503 and r.json()["code"] == "NOT_CONFIGURED"

    fake_channel.error = TransientChannelError("Telegram pediu para esperar 5s")
    assert client.post(f"/destinations/{dest}/test").status_code == 502

    fake_channel.error = PermanentChannelError("bot was kicked")
    r = client.post(f"/destinations/{dest}/test")
    assert r.status_code == 502 and r.json()["code"] == "UPSTREAM_ERROR"
    assert next(d for d in client.get("/destinations").json() if d["id"] == dest)["status"] == "DISCONNECTED"


def test_send_selected_items(client, signup, link_destination, fake_channel, fake_source, engine_, make_client):
    dest = link(client, signup, link_destination)
    client.post("/alerts", json={**ALERT, "maxPrice": None})
    fake_source.put("iphone 12", [make_raw(1, "iPhone 12 A", 80), make_raw(2, "iPhone 12 B", 70)])
    run_search(client)
    ids = [i["id"] for i in client.get("/items").json()["items"]]
    assert len(ids) == 2

    assert client.post(f"/destinations/{dest}/send", json={"itemIds": ids[:1]}).status_code == 204
    message = fake_channel.sent[0][1]
    assert message.alert_name == "Selected listings" and len(message.items) == 1

    assert client.post(f"/destinations/{dest}/send", json={"itemIds": ["nao-existe"]}).status_code == 404
    assert client.post(f"/destinations/{dest}/send", json={"itemIds": []}).status_code == 422

    bruno = make_client()
    signup(bruno, "bruno@example.com")  # não pode enviar anúncios da Ana nem usar o destino dela
    assert bruno.post(f"/destinations/{dest}/send", json={"itemIds": ids}).status_code == 404


# ------------------------------------------------------------------ mensagem
def test_message_rendering():
    message = AlertMessage(
        "iphone 12",
        [
            MessageItem("iPhone 12 64GB", 65.5, "EUR", "https://x/1", "Very good", "#1", highlight="PERFECT"),
            MessageItem("iPhone 12 128GB", 80, "EUR", "https://x/2", None, "#2", highlight="BEST"),
            MessageItem("iPhone 12 mini", 95, "EUR", "https://x/3"),
        ],
        extra_count=4,
    )
    text = render_message(message)
    assert text.startswith("🔔 iphone 12 — 7 new")
    assert "⭐ PERFECT PRICE ⭐\n65.50 EUR | Very good | #1\niPhone 12 64GB\nhttps://x/1" in text
    assert "🔥 BEST DEAL 🔥" in text and "… and 4 more in the app." in text
    assert render_message(AlertMessage("x", [MessageItem("t", 1, "EUR", "u")])).startswith("🔔 x — 1 new\n")


def test_highlights_in_real_notifications(client, signup, link_destination, fake_channel, fake_source, engine_, settings, monkeypatch):
    monkeypatch.setattr(settings, "max_items_per_message", 15)
    link(client, signup, link_destination)
    client.post("/alerts", json={**ALERT, "maxPrice": None, "notifyOnFirstRun": True, "perfectMin": 60, "perfectMax": 65})
    client.post("/monitor/start")
    fake_source.put("iphone 12", [make_raw(i, f"iPhone 12 {i}", p) for i, p in enumerate([61, 40, 50, 55, 70, 90], start=1)])
    engine_.tick(T(0))
    items = fake_channel.sent[0][1].items
    by_price = {i.price: i.highlight for i in items}
    assert by_price[61] == "PERFECT"  # dentro da faixa perfeita
    assert [by_price[p] for p in (40, 50, 55)] == ["BEST", "BEST", "BEST"]  # 3 mais baratos (lote grande)
    assert by_price[70] is None and by_price[90] is None


def test_message_limit_leaves_extras_for_the_app(client, signup, link_destination, fake_channel, fake_source, engine_, settings, monkeypatch):
    monkeypatch.setattr(settings, "max_items_per_message", 3)
    link(client, signup, link_destination)
    client.post("/alerts", json={**ALERT, "maxPrice": None, "notifyOnFirstRun": True})
    client.post("/monitor/start")
    fake_source.put("iphone 12", [make_raw(i, f"iPhone 12 {i}", 50 + i) for i in range(1, 9)])
    engine_.tick(T(0))
    message = fake_channel.sent[0][1]
    assert len(message.items) == 3 and message.extra_count == 5
    assert [i.price for i in message.items] == [51, 52, 53]  # os mais baratos ficam no aviso
    assert engine_.tick(T(6)).sent == 0  # os demais não são reenviados depois


def test_chunk_text_splits_between_listings():
    blocks = [f"anúncio {i} " + "x" * 90 for i in range(50)]
    parts = chunk_text("\n\n".join(blocks), limit=1000)
    assert len(parts) > 1 and all(len(p) <= 1000 for p in parts)
    assert "\n\n".join(parts) == "\n\n".join(blocks)  # nada se perde nem é cortado no meio de um anúncio
    assert chunk_text("curto") == ["curto"]
    assert all(len(p) <= 100 for p in chunk_text("y" * 250, limit=100))


# ------------------------------------------------------------------ cliente HTTP
def fake_post(status, payload):
    def _post(url, json=None, timeout=None):
        return httpx.Response(status, json=payload, request=httpx.Request("POST", url))

    return _post


def test_client_maps_telegram_errors(monkeypatch):
    client = TelegramClient(token="123:ABC")
    monkeypatch.setattr(httpx, "post", fake_post(200, {"ok": True, "result": {"status": "administrator"}}))
    assert client.get_chat_member_status(-1, 7) == "administrator"

    monkeypatch.setattr(httpx, "post", fake_post(429, {"ok": False, "parameters": {"retry_after": 9}}))
    with pytest.raises(TransientChannelError, match="9"):
        client.send_message(1, "oi")
    monkeypatch.setattr(httpx, "post", fake_post(502, {}))
    with pytest.raises(TransientChannelError):
        client.send_message(1, "oi")
    monkeypatch.setattr(httpx, "post", fake_post(403, {"ok": False, "description": "bot was blocked by the user"}))
    with pytest.raises(PermanentChannelError, match="blocked"):
        client.send_message(1, "oi")

    def boom(*a, **k):
        raise httpx.ConnectError("sem rede")

    monkeypatch.setattr(httpx, "post", boom)
    with pytest.raises(TransientChannelError):
        client.send_message(1, "oi")


def test_client_without_token_is_not_configured(settings, monkeypatch):
    monkeypatch.setattr(settings, "telegram_bot_token", None)
    with pytest.raises(ChannelNotConfigured):
        TelegramClient().send_message(1, "oi")


def test_client_sends_long_text_in_parts_with_thread(monkeypatch):
    sent = []

    def _post(url, json=None, timeout=None):
        sent.append(json)
        return httpx.Response(200, json={"ok": True, "result": {}}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", _post)
    TelegramClient(token="t").send_message(-100, "\n\n".join(["a" * 3000, "b" * 3000]), thread_id=42)
    assert len(sent) == 2 and all(p["message_thread_id"] == 42 and p["disable_web_page_preview"] for p in sent)


def test_messages_follow_the_user_language_and_currency():
    from app.services.channels import AlertMessage, MessageItem

    item = MessageItem("Playstation 5", 2500, "DKK", "https://x/1", condition="Good", price_eur=335.1,
                       price_user=1460.5, user_currency="PLN", highlight="PERFECT")
    en = render_message(AlertMessage("ps5", [item], extra_count=2, language="en"))
    assert "🔔 ps5 — 3 new" in en and "PERFECT PRICE" in en and "(≈ 1,460.50 PLN)" in en and "and 2 more in the app" in en
    pt = render_message(AlertMessage("ps5", [item], language="pt"))
    assert "1 new" in pt and "PERFECT PRICE" in pt  # o texto é inglês mesmo pedindo "pt"


def test_bot_replies_use_the_language_of_the_account():
    from app.services.messages import normalize_language, tr

    assert tr("pt-BR", "stopped").startswith("⏸ Monitor paused")  # inglês para todos, inclusive Portugal
    assert tr("en", "stopped").startswith("⏸ Monitor paused")
    assert normalize_language("fr") == "en" and normalize_language(None) == "en"


def test_private_chat_links_when_the_code_is_typed_by_hand(client, signup, session_factory):
    signup(client)
    code, tg = new_code(client, "PRIVATE"), FakeTG()
    typed = {"message": {"chat": {"id": 556, "type": "private", "first_name": "Ana"}, "from": {"id": 556}, "text": code}}
    assert db_call(session_factory, typed, tg) == "linked"  # sem "/start": o usuário só colou o código
    assert client.get("/destinations").json()[0]["status"] == "LINKED"
    # texto comum (mesmo com 12 letras) ou código em grupo não vincula nem responde
    chat = {"message": {"chat": {"id": 556, "type": "private"}, "from": {"id": 556}, "text": "olaolaolaola"}}
    assert db_call(session_factory, chat, tg) == "invalid_code"
    in_group = {"message": {"chat": {"id": -5, "type": "supergroup", "title": "G"}, "from": {"id": 1}, "text": code}}
    assert db_call(session_factory, in_group, tg) == "ignored"


# ------------------------------------------------------------------ cartão bonito (foto, preço, estado, quando saiu)
def test_card_shows_highlight_price_condition_country_and_posting_time():
    from app.services.telegram import render_card

    item = MessageItem("iPhone 12 good condition", 781.94, "PLN", "https://x/1", "Very good", "#1", "PERFECT",
                       "https://img/1.jpg", 179.2, 179.2, "EUR", original_title="iPhone 12 bom estado", domain="pt", age_seconds=95)  # fmt: skip
    card = render_card(item, "iPhone 12 <alerta>", "en")
    assert "<b>⭐ PERFECT PRICE ⭐</b>" in card
    assert "🛍 <b>iPhone 12 good condition</b>" in card and "<i>iPhone 12 bom estado</i>" in card  # original em itálico
    assert "💰 <b>€179.20</b>  (781.94 PLN)" in card
    assert "✨ Very good · 🇵🇹 PT" in card
    assert "⏱ <b>Posted 1 min ago</b>" in card  # o tempo de postagem fica em destaque
    assert "&lt;alerta&gt;" in card and "#1" not in card  # HTML escapado; id de vendedor sem nome não aparece
    pt = render_card(MessageItem("Capa", 1234.5, "EUR", "u", user_currency="EUR", price_user=1234.5, age_seconds=20, domain="fr"), "x", "pt")
    assert "💰 <b>1 234,50 €</b>" in pt and "⏱ <b>Posted just now</b>" in pt and "🇫🇷 FR" in pt


def test_posting_time_units_and_unknown_age():
    from app.services.telegram import posted_text

    assert posted_text(None, "pt") is None
    assert posted_text(200, "en") == "Posted 3 min ago"
    assert posted_text(3 * 3600 + 5, "pt") == "Posted 3 h ago"
    assert posted_text(2 * 86400, "en") == "Posted 2 d ago"


def test_channel_sends_a_photo_card_per_listing_with_a_button_and_falls_back_to_text(monkeypatch):
    from app.models import Destination
    from app.services.channels import PermanentChannelError
    from app.services.telegram import TelegramChannel

    calls = []

    class Client:
        def send_photo(self, chat_id, photo, caption, thread=None, buttons=None):
            calls.append(("photo", photo, buttons))
            if photo.endswith("bad.jpg"):
                raise PermanentChannelError("Bad Request: failed to get HTTP URL content")

        def send_message(self, chat_id, text, thread=None, parse_mode=None, buttons=None):
            calls.append(("text", parse_mode, buttons, text[:12]))

    dest = Destination(user_id="u", external_id="-100", linked_at=None)
    message = AlertMessage("x", [MessageItem("A", 1, "EUR", "https://x/a", photo_url="https://img/ok.jpg"),
                                 MessageItem("B", 2, "EUR", "https://x/b", photo_url="https://img/bad.jpg"),
                                 MessageItem("C", 3, "EUR", "https://x/c")], extra_count=2, language="en")  # fmt: skip
    TelegramChannel(Client()).send(dest, message)
    assert calls[0][0] == "photo" and calls[0][2] == [("🛒 Open on Vinted", "https://x/a")]
    assert calls[1][0] == "photo" and calls[2][:2] == ("text", "HTML")  # foto ruim: cai para texto, sem derrubar o destino
    assert calls[3][:2] == ("text", "HTML") and calls[4][3].startswith("… and 2 more")

    class Blocked(Client):
        def send_photo(self, *a, **k):
            raise PermanentChannelError("Forbidden: bot was blocked by the user")

    import pytest

    with pytest.raises(PermanentChannelError):  # problema do chat (não da foto) continua sendo erro do destino
        TelegramChannel(Blocked()).send(dest, message)
