from datetime import timedelta

from sqlalchemy import select

from app.models import Alert, Destination, Item, Match, User, utcnow
from tests.conftest import ALERT


# ------------------------------------------------------------------ destinos
def test_channels(client, signup):
    signup(client)
    channels = client.get("/channels").json()
    assert channels[0]["id"] == "TELEGRAM" and channels[0]["supportsGroups"] is True
    assert set(channels[0]["instructions"]) == {"PRIVATE", "GROUP", "CHANNEL"}


def test_link_code_creates_pending_destination(client, signup):
    signup(client)
    r = client.post("/destinations/link-code", json={"channel": "TELEGRAM", "kind": "GROUP"})
    assert r.status_code == 200
    body = r.json()
    assert body["command"] == f"/link {body['code']}" and body["deepLink"] is None
    assert body["expiresAt"].endswith("Z")

    destinations = client.get("/destinations").json()
    assert destinations == [
        {
            "id": body["destinationId"],
            "channel": "TELEGRAM",
            "kind": "GROUP",
            "title": None,
            "status": "PENDING",
            "isDefault": False,
            "linkedAt": None,
            "language": "pt",
        }
    ]


def test_private_link_uses_deep_link(client, signup):
    signup(client)
    body = client.post("/destinations/link-code", json={"channel": "TELEGRAM", "kind": "PRIVATE"}).json()
    assert body["deepLink"].startswith("https://t.me/") and body["deepLink"].endswith(f"?start={body['code']}")
    assert body["command"] is None


def test_new_code_replaces_previous_pending_one(client, signup):
    signup(client)
    first = client.post("/destinations/link-code", json={"kind": "GROUP"}).json()
    second = client.post("/destinations/link-code", json={"kind": "PRIVATE"}).json()
    ids = [d["id"] for d in client.get("/destinations").json()]
    assert ids == [second["destinationId"]] and first["destinationId"] not in ids


def _link(session_factory, email: str, **kwargs) -> str:
    with session_factory() as db:
        user = db.scalar(select(User).where(User.email == email))
        dest = Destination(user_id=user.id, kind="GROUP", linked_at=utcnow(), **kwargs)
        db.add(dest)
        db.commit()
        return dest.id


def test_destination_limit_counts_only_linked(client, signup, session_factory):
    signup(client)
    with session_factory() as db:
        db.scalar(select(User)).plan = "FREE"  # FREE: 1 destino
        db.commit()
    assert client.post("/destinations/link-code", json={"kind": "GROUP"}).status_code == 200  # pendente não conta
    _link(session_factory, "ana@example.com", external_id="-1001", title="A")
    r = client.post("/destinations/link-code", json={"kind": "GROUP"})
    assert r.status_code == 402 and r.json()["code"] == "PLAN_LIMIT_REACHED"


def test_default_rename_and_delete_promotes_another(client, signup, session_factory):
    signup(client)
    a = _link(session_factory, "ana@example.com", external_id="-1001", title="A", is_default=True)
    b = _link(session_factory, "ana@example.com", external_id="-1002", title="B")

    r = client.patch(f"/destinations/{b}", json={"title": "Grupo B", "isDefault": True})
    assert r.status_code == 200 and r.json()["title"] == "Grupo B" and r.json()["isDefault"] is True
    defaults = {d["id"]: d["isDefault"] for d in client.get("/destinations").json()}
    assert defaults == {a: False, b: True}

    assert client.delete(f"/destinations/{b}").status_code == 204
    assert {d["id"]: d["isDefault"] for d in client.get("/destinations").json()} == {a: True}


def test_destinations_are_private_to_their_owner(client, signup, make_client, session_factory):
    signup(client, "ana@example.com")
    dest = _link(session_factory, "ana@example.com", external_id="-1001", title="A")
    bruno = make_client()
    signup(bruno, "bruno@example.com")
    assert bruno.get("/destinations").json() == []
    assert bruno.patch(f"/destinations/{dest}", json={"title": "x"}).status_code == 404
    assert bruno.delete(f"/destinations/{dest}").status_code == 404


# ------------------------------------------------------------------ monitor / config
def test_monitor_toggle_and_status(client, signup):
    signup(client)
    assert client.get("/monitor/status").json()["state"] == "PAUSED"
    assert client.post("/monitor/start").status_code == 204
    status = client.get("/monitor/status").json()
    assert status["state"] == "ACTIVE" and status["enabled"] is True and status["runs"] == []
    assert client.post("/monitor/stop").status_code == 204
    assert client.get("/monitor/status").json()["enabled"] is False


def test_interval_respects_plan_floor(client, signup, session_factory):
    signup(client)  # PRO: mínimo 15 s
    assert client.patch("/settings", json={"intervalMinutes": 2}).json() == {"intervalMinutes": 2}
    r = client.patch("/settings", json={"intervalMinutes": 0.1})
    assert r.status_code == 402 and r.json()["code"] == "PLAN_LIMIT_REACHED"


# ------------------------------------------------------------------ resultados
def _add_match(db, user_id, alert_id, *, title, price, posted_minutes_ago, vinted_id):
    item = Item(
        vinted_id=vinted_id,
        title=title,
        price=price,
        seller_login="vendedor",
        url=f"https://exemplo/{vinted_id}",
        posted_at=utcnow() - timedelta(minutes=posted_minutes_ago),
        first_seen_at=utcnow() - timedelta(minutes=posted_minutes_ago),
    )
    db.add(item)
    db.flush()
    db.add(Match(user_id=user_id, alert_id=alert_id, item_id=item.id))
    return item


def test_items_empty_then_newest_first_with_perfect_flag(client, signup, session_factory):
    signup(client)
    assert client.get("/items").json() == {"items": [], "nextCursor": None, "total": 0}

    alert = client.post("/alerts", json={**ALERT, "perfectMin": 60, "perfectMax": 70}).json()
    with session_factory() as db:
        user = db.scalar(select(User))
        _add_match(db, user.id, alert["id"], title="Velho", price=90, posted_minutes_ago=300, vinted_id=1)
        _add_match(db, user.id, alert["id"], title="Novo", price=65, posted_minutes_ago=2, vinted_id=2)
        _add_match(db, user.id, alert["id"], title="Meio", price=80, posted_minutes_ago=60, vinted_id=3)
        db.commit()

    page = client.get("/items").json()
    assert [i["title"] for i in page["items"]] == ["Novo", "Meio", "Velho"]
    assert page["total"] == 3
    novo = page["items"][0]
    assert novo["isPerfect"] is True and novo["alertName"] == "iphone 12" and novo["price"] == 65

    cheap = client.get("/items", params={"sort": "price_asc"}).json()["items"]
    assert [i["title"] for i in cheap] == ["Novo", "Meio", "Velho"]
    assert [i["title"] for i in client.get("/items", params={"onlyPerfect": "true"}).json()["items"]] == ["Novo"]
    assert len(client.get("/items", params={"period": "1h"}).json()["items"]) == 1
    assert client.get("/alerts").json()[0]["newToday"] == 3


def test_items_pagination(client, signup, session_factory):
    signup(client)
    alert = client.post("/alerts", json=ALERT).json()
    with session_factory() as db:
        user = db.scalar(select(User))
        for n in range(25):
            _add_match(db, user.id, alert["id"], title=f"Item {n}", price=10 + n, posted_minutes_ago=n + 1, vinted_id=100 + n)
        db.commit()
    first = client.get("/items").json()
    assert len(first["items"]) == 20 and first["nextCursor"] == "20" and first["total"] == 25
    second = client.get("/items", params={"cursor": first["nextCursor"]}).json()
    assert len(second["items"]) == 5 and second["nextCursor"] is None


def test_items_only_show_own_matches_and_filter_by_alert(client, signup, make_client, session_factory):
    signup(client, "ana@example.com")
    a1 = client.post("/alerts", json=ALERT).json()
    a2 = client.post("/alerts", json={**ALERT, "query": "ps5"}).json()
    bruno = make_client()
    signup(bruno, "bruno@example.com")
    b1 = bruno.post("/alerts", json=ALERT).json()
    with session_factory() as db:
        ana = db.scalar(select(User).where(User.email == "ana@example.com"))
        bru = db.scalar(select(User).where(User.email == "bruno@example.com"))
        _add_match(db, ana.id, a1["id"], title="Do iPhone", price=50, posted_minutes_ago=5, vinted_id=1)
        _add_match(db, ana.id, a2["id"], title="Do PS5", price=300, posted_minutes_ago=6, vinted_id=2)
        _add_match(db, bru.id, b1["id"], title="Do Bruno", price=40, posted_minutes_ago=1, vinted_id=3)
        db.commit()
    assert sorted(i["title"] for i in client.get("/items").json()["items"]) == ["Do PS5", "Do iPhone"]
    only_ps5 = client.get("/items", params={"alertIds": a2["id"]}).json()["items"]
    assert [i["title"] for i in only_ps5] == ["Do PS5"]
    assert [i["title"] for i in bruno.get("/items").json()["items"]] == ["Do Bruno"]


def test_deleting_alert_removes_its_matches(client, signup, session_factory):
    signup(client)
    alert = client.post("/alerts", json=ALERT).json()
    with session_factory() as db:
        user = db.scalar(select(User))
        _add_match(db, user.id, alert["id"], title="X", price=1, posted_minutes_ago=1, vinted_id=1)
        db.commit()
    client.delete(f"/alerts/{alert['id']}")
    assert client.get("/items").json()["total"] == 0
    with session_factory() as db:
        assert db.scalars(select(Match)).all() == [] and db.scalars(select(Alert)).all() == []


def test_newest_first_uses_listing_number_when_post_date_is_unknown(client, signup, session_factory):
    """A Vinted não informa a data de postagem na busca; o número do anúncio cresce com o tempo."""
    signup(client)
    alert = client.post("/alerts", json=ALERT).json()
    with session_factory() as db:
        user = db.scalar(select(User))
        for vid in (500, 900, 100):
            item = Item(vinted_id=vid, title=f"Anúncio {vid}", price=10, seller_login="#1", url=f"https://x/{vid}")
            db.add(item)
            db.flush()
            db.add(Match(user_id=user.id, alert_id=alert["id"], item_id=item.id))
        db.commit()
    assert [i["title"] for i in client.get("/items").json()["items"]] == ["Anúncio 900", "Anúncio 500", "Anúncio 100"]


def test_items_report_euro_price_and_filter_and_sort_in_euros(client, signup, session_factory):
    from decimal import Decimal

    from app.models import Alert, Item, Match, User

    signup(client)
    alert_id = client.post("/alerts", json=ALERT).json()["id"]
    with session_factory() as db:
        uid = db.scalar(select(User.id))
        # 500 zł ≈ 115 €;  150 € ;  1000 kr (DKK) ≈ 134 €
        rows = [(1, "zl", "PLN", 500), (2, "eur", "EUR", 150), (3, "dkk", "DKK", 1000)]
        for vid, title, cur, price in rows:
            item = Item(vinted_id=vid, title=title, price=Decimal(price), currency=cur, seller_login=f"#{vid}", url="u")
            db.add(item)
            db.flush()
            db.add(Match(user_id=uid, alert_id=alert_id, item_id=item.id))
        db.commit()
    data = client.get("/items", params={"sort": "price_asc"}).json()["items"]
    assert [i["title"] for i in data] == ["zl", "dkk", "eur"]  # por euros, não pelo número cru (500 > 150)
    assert 100 < data[0]["priceEur"] < 130 and data[0]["currency"] == "PLN"
    only = client.get("/items", params={"maxPrice": 140, "sort": "price_asc"}).json()["items"]
    assert [i["title"] for i in only] == ["zl", "dkk"]


def test_destination_language_overrides_the_account_language(client, signup, link_destination, fake_channel, fake_source):
    from tests.conftest import make_raw, run_search  # noqa: F401

    signup(client)
    dest_id = link_destination("ana@example.com")
    # sem idioma próprio: herda o da conta (pt)
    listed = client.get("/destinations").json()[0]
    assert listed["language"] == "pt"
    r = client.patch(f"/destinations/{dest_id}", json={"language": "en"})
    assert r.status_code == 200 and r.json()["language"] == "en"
    assert client.patch(f"/destinations/{dest_id}", json={"language": "xx"}).status_code == 422
    client.post(f"/destinations/{dest_id}/test")
    assert "Garimpo test" in fake_channel.texts[-1][1]
    client.patch(f"/destinations/{dest_id}", json={"language": "pt"})
    client.post(f"/destinations/{dest_id}/test")
    assert "Garimpo test" in fake_channel.texts[-1][1]  # o Telegram sai sempre em inglês, qualquer que seja o idioma


def test_link_code_can_carry_the_language_and_alerts_use_it(client, signup, session_factory, fake_source, fake_channel, engine_, link_destination):
    from app.models import Destination
    from tests.conftest import ALERT, T, make_raw

    signup(client)
    code = client.post("/destinations/link-code", json={"kind": "GROUP", "language": "en"})
    assert code.status_code == 200
    with session_factory() as db:
        assert db.get(Destination, code.json()["destinationId"]).language == "en"
    assert client.post("/destinations/link-code", json={"kind": "GROUP", "language": "zz"}).status_code == 422

    dest_id = link_destination("ana@example.com", chat_id="-2002")
    client.patch(f"/destinations/{dest_id}", json={"language": "en"})
    client.post("/alerts", json={**ALERT, "destinationId": dest_id, "excludeWords": ["capa"], "maxPrice": None})
    client.post("/monitor/start")
    fake_source.put("iphone 12", [])
    engine_.tick(T(0))
    fake_source.put("iphone 12", [make_raw(5, "iPhone 12", 80)])
    engine_.tick(T(6))
    assert fake_channel.sent, "deveria ter avisado"
    assert fake_channel.sent[-1][1].language == "en"
