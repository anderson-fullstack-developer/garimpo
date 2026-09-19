from datetime import timedelta

from app.models import RefreshToken, User
from sqlalchemy import select

from tests.conftest import PASSWORD


def test_register_verify_login_me_logout(client, signup):
    user = signup(client)
    assert user["email"] == "ana@example.com"
    assert user["status"] == "ACTIVE"
    assert user["verified"] is True
    assert "passwordHash" not in user and "password" not in user

    # Cookies de sessão são httpOnly (o JavaScript do site nunca vê o token).
    cookies = client.cookies
    assert cookies.get("garimpo_access") and cookies.get("garimpo_refresh")

    assert client.get("/me").json()["email"] == "ana@example.com"

    assert client.post("/auth/logout").status_code == 204
    assert client.get("/me").status_code == 401


def test_set_cookie_flags(client, signup):
    signup(client, login=False)
    r = client.post("/auth/login", json={"email": "ana@example.com", "password": PASSWORD})
    headers = r.headers.get_list("set-cookie")
    assert headers and all("HttpOnly" in h and "SameSite=lax" in h for h in headers)


def test_unverified_user_can_login_but_only_use_data_after_linking_telegram(client, session_factory):
    from app.services.telegram_webhook import handle_update
    from tests.test_telegram import FakeTG, new_code, private

    client.post("/auth/register", json={"email": "ana@example.com", "password": PASSWORD, "captchaToken": "x"})
    r = client.post("/auth/login", json={"email": "ana@example.com", "password": PASSWORD})
    assert r.status_code == 200 and r.json()["verified"] is False
    blocked = client.get("/alerts")
    assert blocked.status_code == 403 and blocked.json()["code"] == "TELEGRAM_NOT_VERIFIED"
    assert client.get("/me").status_code == 200  # o front precisa dele para mostrar o passo do Telegram

    # só o chat PRIVADO verifica: grupo/canal não abrem a conta
    assert client.post("/destinations/link-code", json={"kind": "GROUP"}).status_code == 403
    code = new_code(client, "PRIVATE")
    with session_factory() as db:
        assert handle_update(db, private(4242, code), FakeTG()) == "linked"
    assert client.get("/me").json()["verified"] is True
    assert client.get("/alerts").status_code == 200


def test_one_telegram_chat_cannot_verify_two_accounts(client, make_client, session_factory):
    from app.services.telegram_webhook import handle_update
    from tests.test_telegram import FakeTG, new_code, private

    for email in ("ana@example.com", "bia@example.com"):
        client.post("/auth/register", json={"email": email, "password": PASSWORD, "captchaToken": "x"})
    client.post("/auth/login", json={"email": "ana@example.com", "password": PASSWORD})
    with session_factory() as db:
        assert handle_update(db, private(777, new_code(client, "PRIVATE")), FakeTG()) == "linked"
    other = make_client()
    other.post("/auth/login", json={"email": "bia@example.com", "password": PASSWORD})
    with session_factory() as db:
        assert handle_update(db, private(777, new_code(other, "PRIVATE")), FakeTG()) == "taken"  # mesmo chat, outra conta
    assert other.get("/me").json()["verified"] is False


def test_wrong_password_is_generic_and_locks_after_five(client, signup):
    signup(client, login=False)
    for _ in range(5):
        r = client.post("/auth/login", json={"email": "ana@example.com", "password": "errada-errada"})
        assert r.status_code == 401
        assert r.json() == {"code": "INVALID_CREDENTIALS", "message": "Invalid email or password"}
    r = client.post("/auth/login", json={"email": "ana@example.com", "password": PASSWORD})
    assert r.status_code == 429 and r.json()["code"] == "RATE_LIMITED"


def test_unknown_email_gets_same_error_as_wrong_password(client):
    r = client.post("/auth/login", json={"email": "ninguem@example.com", "password": "qualquer-coisa"})
    assert r.status_code == 401 and r.json()["code"] == "INVALID_CREDENTIALS"


def test_register_existing_email_does_not_reveal_it(client, signup):
    signup(client, login=False)
    r = client.post("/auth/register", json={"email": "ana@example.com", "password": PASSWORD, "captchaToken": "x"})
    assert r.status_code == 204


def test_weak_and_short_passwords_rejected(client):
    r = client.post("/auth/register", json={"email": "a@example.com", "password": "curta", "captchaToken": "x"})
    assert r.status_code == 422 and r.json()["code"] == "VALIDATION_ERROR"
    r = client.post("/auth/register", json={"email": "a@example.com", "password": "1234567890", "captchaToken": "x"})
    assert r.status_code == 422


def test_forgot_is_silent_for_unknown_email_and_reset_kills_sessions(client, signup, session_factory, fake_channel):
    signup(client)
    _link_private(client, session_factory, "ana@example.com")
    assert client.post("/auth/forgot", json={"email": "ninguem@example.com"}).status_code == 204
    assert fake_channel.texts == []

    client.post("/auth/forgot", json={"email": "ana@example.com"})
    token = fake_channel.buttons[0][1].split("/reset?token=")[1]
    assert client.post("/auth/reset", json={"token": token, "password": "outra-senha-forte-1"}).status_code == 204

    # O link é de uso único e a senha antiga deixa de valer.
    assert client.post("/auth/reset", json={"token": token, "password": "mais-uma-senha-forte"}).status_code == 400
    assert client.post("/auth/login", json={"email": "ana@example.com", "password": PASSWORD}).status_code == 401
    assert client.post("/auth/login", json={"email": "ana@example.com", "password": "outra-senha-forte-1"}).status_code == 200


def test_reset_revokes_existing_refresh_tokens(client, signup, session_factory, fake_channel):
    signup(client)
    _link_private(client, session_factory, "ana@example.com")
    client.post("/auth/forgot", json={"email": "ana@example.com"})
    token = fake_channel.buttons[0][1].split("/reset?token=")[1]
    client.post("/auth/reset", json={"token": token, "password": "outra-senha-forte-1"})
    with session_factory() as db:
        assert all(t.revoked_at for t in db.scalars(select(RefreshToken)))


def test_refresh_rotates_token(client, signup):
    signup(client)
    old = client.cookies.get("garimpo_refresh")
    assert client.post("/auth/refresh").status_code == 204
    assert client.cookies.get("garimpo_refresh") != old
    assert client.get("/me").status_code == 200


def test_reused_refresh_token_revokes_whole_family(client, signup, monkeypatch):
    monkeypatch.setattr("app.routers.auth.REFRESH_REUSE_GRACE", timedelta(0))
    signup(client)
    stolen = client.cookies.get("garimpo_refresh")
    assert client.post("/auth/refresh").status_code == 204  # uso legítimo: gira o token
    newest = client.cookies.get("garimpo_refresh")

    client.cookies.set("garimpo_refresh", stolen)  # o token antigo reaparece (roubado)
    assert client.post("/auth/refresh").status_code == 401

    client.cookies.set("garimpo_refresh", newest)  # e o token novo também foi derrubado
    assert client.post("/auth/refresh").status_code == 401


def test_refresh_without_cookie_is_401(client):
    assert client.post("/auth/refresh").status_code == 401


def test_approval_mode_pending_user_can_login_but_not_use_data(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "registration_mode", "APPROVAL")
    monkeypatch.setattr(settings, "require_verification", False)
    client.post("/auth/register", json={"email": "bia@example.com", "password": PASSWORD, "captchaToken": "x"})
    r = client.post("/auth/login", json={"email": "bia@example.com", "password": PASSWORD})
    assert r.status_code == 200 and r.json()["status"] == "PENDING"
    assert client.get("/me").status_code == 200
    r = client.get("/alerts")
    assert r.status_code == 403 and r.json()["code"] == "ACCOUNT_PENDING"


def test_suspended_user_cannot_login(client, signup, session_factory):
    signup(client, login=False)
    with session_factory() as db:
        user = db.scalar(select(User))
        user.status = "SUSPENDED"
        db.commit()
    r = client.post("/auth/login", json={"email": "ana@example.com", "password": PASSWORD})
    assert r.status_code == 403 and r.json()["code"] == "ACCOUNT_SUSPENDED"


def test_invite_mode_requires_valid_code(client, settings, monkeypatch, session_factory):
    from app.models import Invite, utcnow
    from app.security import hash_token

    monkeypatch.setattr(settings, "registration_mode", "INVITE")
    body = {"email": "cris@example.com", "password": PASSWORD, "captchaToken": "x"}
    assert client.post("/auth/register", json=body).status_code == 403
    assert client.post("/auth/register", json={**body, "inviteCode": "codigo-errado"}).status_code == 403

    with session_factory() as db:
        db.add(Invite(code_hash=hash_token("convite-valido"), expires_at=utcnow() + timedelta(days=1)))
        db.commit()
    assert client.post("/auth/register", json={**body, "inviteCode": "convite-valido"}).status_code == 204
    # Convite de uso único.
    other = {**body, "email": "dani@example.com", "inviteCode": "convite-valido"}
    assert client.post("/auth/register", json=other).status_code == 403


def test_change_password_and_delete_account(client, signup):
    signup(client)
    r = client.post("/me/password", json={"current": "senha-errada-123", "next": "nova-senha-forte-1"})
    assert r.status_code == 400 and r.json()["code"] == "INVALID_CREDENTIALS"
    r = client.post("/me/password", json={"current": PASSWORD, "next": "nova-senha-forte-1"})
    assert r.status_code == 204
    assert client.get("/me").status_code == 200  # esta sessão continua válida

    assert client.delete("/me").status_code == 204
    assert client.get("/me").status_code == 401
    r = client.post("/auth/login", json={"email": "ana@example.com", "password": "nova-senha-forte-1"})
    assert r.status_code == 401


def test_validation_errors_use_front_format(client):
    r = client.post("/auth/login", json={"email": "nao-e-email", "password": "x"})
    assert r.status_code == 422
    assert set(r.json()) == {"code", "message"} and r.json()["code"] == "VALIDATION_ERROR"


def test_public_config_and_health(client):
    assert client.get("/health").json() == {"status": "ok"}
    cfg = client.get("/public/config").json()
    assert cfg["registrationMode"] == "OPEN" and cfg["botUsername"]


# ------------------------------------------------------------------ país, idioma e moeda
def test_country_at_signup_sets_language_and_currency(client):
    def create(email, country):
        client.post("/auth/register", json={"email": email, "password": PASSWORD, "captchaToken": "x", "country": country})
        return client.post("/auth/login", json={"email": email, "password": PASSWORD}).json()

    pl = create("ola@example.com", "pl")
    assert (pl["country"], pl["language"], pl["currency"]) == ("pl", "en", "PLN")
    client.post("/auth/logout")
    pt = create("ana2@example.com", "PT")
    assert (pt["country"], pt["language"], pt["currency"]) == ("pt", "pt", "EUR")


def test_invalid_country_is_rejected_and_preferences_are_independent(client, signup):
    body = {"email": "x@example.com", "password": "Senha-Forte-12345", "captchaToken": "x", "country": "zz"}
    assert client.post("/auth/register", json=body).status_code == 422
    signup(client)
    me = client.get("/me").json()
    assert me["language"] == "pt" and me["currency"] == "EUR" and me["country"] is None
    r = client.patch("/me/preferences", json={"country": "de", "language": "pt", "currency": "sek"})
    assert r.status_code == 200
    assert (r.json()["country"], r.json()["language"], r.json()["currency"]) == ("de", "pt", "SEK")
    assert client.patch("/me/preferences", json={"language": "xx"}).status_code == 422
    assert client.patch("/me/preferences", json={"currency": "XXX"}).status_code == 422
    assert client.get("/me").json()["currency"] == "SEK"


# ------------------------------------------------------------------ redefinir a senha pelo Telegram
def _link_private(client, session_factory, email, chat_id="777", kind="PRIVATE", disconnected=False):
    from sqlalchemy import select

    from app.models import Destination, User, utcnow

    with session_factory() as db:
        user = db.scalar(select(User).where(User.email == email))
        db.add(Destination(user_id=user.id, kind=kind, external_id=chat_id, title="Ana", linked_at=utcnow(),
                           disconnected_at=utcnow() if disconnected else None, is_default=True))
        db.commit()


def test_password_reset_link_arrives_in_the_private_telegram_chat(client, signup, session_factory, fake_channel):
    signup(client)
    _link_private(client, session_factory, "ana@example.com")
    client.post("/auth/logout")
    r = client.post("/auth/forgot", json={"email": "ana@example.com", "via": "telegram"})
    assert r.status_code == 204
    assert len(fake_channel.texts) == 1 and fake_channel.texts[0][0].external_id == "777"
    text = fake_channel.texts[0][1]
    assert "Reset your Garimpo password" in text and "valid for 15 minutes" in text  # inglês para todos
    assert fake_channel.buttons[0][0] == "🔑 Reset password" and "/reset?token=" in fake_channel.buttons[0][1]
    token = fake_channel.buttons[0][1].split("/reset?token=")[1]
    assert client.post("/auth/reset", json={"token": token, "password": "Nova-Senha-Forte-99"}).status_code == 204
    assert client.post("/auth/login", json={"email": "ana@example.com", "password": "Nova-Senha-Forte-99"}).status_code == 200
    assert client.post("/auth/reset", json={"token": token, "password": "Outra-Senha-Forte-11"}).status_code == 400  # uso único


def test_telegram_reset_never_goes_to_groups_disconnected_chats_or_unknown_accounts(client, signup, session_factory, fake_channel):
    signup(client)
    client.post("/auth/logout")
    for setup in (None, ("-100", "GROUP", False), ("888", "PRIVATE", True)):
        if setup:
            _link_private(client, session_factory, "ana@example.com", setup[0], setup[1], setup[2])
        r = client.post("/auth/forgot", json={"email": "ana@example.com", "via": "telegram"})
        assert r.status_code == 204  # a resposta é a mesma: ninguém descobre quem tem Telegram
    assert client.post("/auth/forgot", json={"email": "ninguem@example.com", "via": "telegram"}).status_code == 204
    assert fake_channel.texts == []  # sem chat privado ativo, nada é enviado


def test_reset_message_is_english_for_everyone_even_with_a_portuguese_account(client, signup, session_factory, fake_channel):
    signup(client)  # conta em português
    _link_private(client, session_factory, "ana@example.com")
    client.post("/auth/logout")
    client.post("/auth/forgot", json={"email": "ana@example.com", "via": "telegram"})
    text = fake_channel.texts[0][1]
    assert "<b>Reset your Garimpo password</b>" in text and "Redefinir" not in text
    assert "<a href=" in text and "Didn't ask for this?" in text
    token = fake_channel.buttons[0][1].split("/reset?token=")[1]
    assert f"<code>{token}</code>" in text  # código copiável: vale colado na página quando o link não abre


def test_reset_falls_back_when_telegram_rejects_the_button_or_html():
    from app.models import Destination
    from app.services.channels import PermanentChannelError
    from app.services.messages import reset_message_html, reset_message_plain
    from app.services.telegram import TelegramChannel

    calls = []

    class Client:
        def __init__(self, fail_first):
            self.fail = fail_first

        def send_message(self, chat_id, text, thread=None, parse_mode=None, buttons=None):
            calls.append((parse_mode, bool(buttons)))
            if self.fail > 0:
                self.fail -= 1
                raise PermanentChannelError("Bad Request: wrong HTTP URL")

    dest = Destination(user_id="u", external_id="9", linked_at=None)
    link = "http://localhost:3300/reset?token=abc"
    args = (dest, reset_message_html(link, 15), reset_message_plain(link, 15), [("🔑 Reset password", link)])
    TelegramChannel(Client(0)).send_rich(*args)
    assert calls == [("HTML", True)]
    calls.clear()
    TelegramChannel(Client(2)).send_rich(*args)  # botão recusado (localhost) -> sem botão -> texto simples
    assert calls == [("HTML", True), ("HTML", False), (None, False)]
    assert "localhost:3300/reset?token=abc" in reset_message_plain(link, 15)
