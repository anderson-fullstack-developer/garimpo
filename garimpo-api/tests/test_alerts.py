from sqlalchemy import select

from app.models import Destination, User, utcnow
from tests.conftest import ALERT


def test_requires_login(client):
    assert client.get("/alerts").status_code == 401
    assert client.post("/alerts", json=ALERT).status_code == 401


def test_create_list_get_alert_uses_camel_case(client, signup):
    signup(client)
    r = client.post("/alerts", json=ALERT)
    assert r.status_code == 201, r.text
    alert = r.json()
    assert alert["name"] == "iphone 12"  # nome vazio -> vira o termo de busca
    assert alert["maxPrice"] == 90 and alert["excludeWords"] == ["capa"]
    assert alert["country"] == "pt" and alert["notifyOnFirstRun"] is False
    assert alert["newToday"] == 0 and alert["createdAt"].endswith("Z")
    assert "max_price" not in alert and "user_id" not in alert and "userId" not in alert

    assert [a["id"] for a in client.get("/alerts").json()] == [alert["id"]]
    assert client.get(f"/alerts/{alert['id']}").json()["query"] == "iphone 12"


def test_validation(client, signup):
    signup(client)
    bad = [
        {**ALERT, "query": "a"},
        {**ALERT, "minPrice": 100, "maxPrice": 50},
        {**ALERT, "country": "xx"},
        {**ALERT, "pages": 9},
        {**ALERT, "excludeWords": ["x" * 41]},
        {**ALERT, "statusFilter": ["quebrado"]},
        {**ALERT, "perfectMin": 80, "perfectMax": 60},
    ]
    for body in bad:
        r = client.post("/alerts", json=body)
        assert r.status_code == 422, body
        assert r.json()["code"] == "VALIDATION_ERROR"


def test_europe_country_is_accepted(client, signup):
    signup(client)
    assert client.post("/alerts", json={**ALERT, "country": "eu"}).json()["country"] == "eu"


def test_patch_changes_only_sent_fields_and_can_clear(client, signup):
    signup(client)
    alert = client.post("/alerts", json=ALERT).json()
    r = client.patch(f"/alerts/{alert['id']}", json={"active": False, "maxPrice": None, "country": "eu"})
    assert r.status_code == 200
    out = r.json()
    assert out["active"] is False and out["maxPrice"] is None and out["country"] == "eu"
    assert out["query"] == "iphone 12" and out["excludeWords"] == ["capa"]  # intacto

    r = client.patch(f"/alerts/{alert['id']}", json={"minPrice": 500, "maxPrice": 10})
    assert r.status_code == 422 and r.json()["code"] == "VALIDATION_ERROR"


def test_delete_and_duplicate(client, signup):
    signup(client)
    alert = client.post("/alerts", json=ALERT).json()
    copy = client.post(f"/alerts/{alert['id']}/duplicate")
    assert copy.status_code == 201 and copy.json()["name"] == "iphone 12 (copy)"
    assert copy.json()["id"] != alert["id"]
    assert client.delete(f"/alerts/{alert['id']}").status_code == 204
    assert client.get(f"/alerts/{alert['id']}").status_code == 404
    assert len(client.get("/alerts").json()) == 1


def test_plan_limit_returns_402(client, signup, session_factory):
    signup(client)
    with session_factory() as db:
        db.scalar(select(User)).plan = "FREE"  # FREE: 1 alerta
        db.commit()
    assert client.post("/alerts", json=ALERT).status_code == 201
    r = client.post("/alerts", json=ALERT)
    assert r.status_code == 402 and r.json()["code"] == "PLAN_LIMIT_REACHED"
    # FREE também só varre 1 página.
    client.delete(f"/alerts/{client.get('/alerts').json()[0]['id']}")
    assert client.post("/alerts", json={**ALERT, "pages": 3}).status_code == 402


def test_users_cannot_touch_each_others_alerts(client, signup, make_client):
    signup(client, "ana@example.com")
    alert = client.post("/alerts", json=ALERT).json()

    bruno = make_client()
    signup(bruno, "bruno@example.com")
    assert bruno.get("/alerts").json() == []
    for call in (
        lambda: bruno.get(f"/alerts/{alert['id']}"),
        lambda: bruno.patch(f"/alerts/{alert['id']}", json={"active": False}),
        lambda: bruno.delete(f"/alerts/{alert['id']}"),
        lambda: bruno.post(f"/alerts/{alert['id']}/duplicate"),
    ):
        r = call()
        assert r.status_code == 404 and r.json()["code"] == "NOT_FOUND"
    # e o alerta da Ana segue intacto
    assert client.get(f"/alerts/{alert['id']}").json()["active"] is True


def test_cannot_point_alert_to_someone_elses_destination(client, signup, make_client, session_factory):
    signup(client, "ana@example.com")
    bruno = make_client()
    signup(bruno, "bruno@example.com")
    with session_factory() as db:
        ana = db.scalar(select(User).where(User.email == "ana@example.com"))
        dest = Destination(user_id=ana.id, kind="GROUP", external_id="-100123", title="Grupo da Ana", linked_at=utcnow())
        db.add(dest)
        db.commit()
        dest_id = dest.id
    r = bruno.post("/alerts", json={**ALERT, "destinationId": dest_id})
    assert r.status_code == 422 and r.json()["code"] == "VALIDATION_ERROR"
    assert client.post("/alerts", json={**ALERT, "destinationId": dest_id}).status_code == 201


def test_presets(client, signup):
    signup(client)
    presets = client.get("/alerts/presets").json()
    assert [p["id"] for p in presets] == ["PHONES", "CONSOLES_GAMES", "AUDIO_VIDEO"]
    phones = next(p for p in presets if p["id"] == "PHONES")["words"]
    assert "capa" in phones and "pelicula" in phones
