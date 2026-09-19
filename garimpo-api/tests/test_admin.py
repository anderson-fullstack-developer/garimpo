"""Painel do administrador: só ADMIN entra e as ações mexem no acesso das contas."""

from datetime import timedelta

from sqlalchemy import select

from app.models import Alert, User, utcnow
from tests.conftest import ALERT, PASSWORD


def _make_admin(session_factory, email="ana@example.com"):
    with session_factory() as db:
        db.scalar(select(User).where(User.email == email)).role = "ADMIN"
        db.commit()


def _user(session_factory, email):
    with session_factory() as db:
        return db.scalar(select(User).where(User.email == email))


def test_only_admins_can_use_the_panel_and_others_get_404(client, signup, make_client):
    assert client.get("/admin/users").status_code == 401  # sem login
    signup(client)
    for path in ("/admin/overview", "/admin/users", "/admin/runs"):
        assert client.get(path).status_code == 404  # usuário comum nem descobre que existe


def test_admin_sees_overview_and_users_with_their_access(client, signup, session_factory, make_client):
    signup(client)
    client.post("/alerts", json=ALERT)
    other = make_client()
    signup(other, "bia@example.com")
    with session_factory() as db:
        bia = db.scalar(select(User).where(User.email == "bia@example.com"))
        bia.trial_ends_at = utcnow() - timedelta(days=1)  # teste da Bia acabou
        db.commit()
    _make_admin(session_factory)

    ov = client.get("/admin/overview").json()
    assert ov["users"] == 2 and ov["verified"] == 2 and ov["alerts"] == 1 and ov["expired"] == 1

    users = {u["email"]: u for u in client.get("/admin/users").json()}
    assert users["ana@example.com"]["access"] == "admin" and users["ana@example.com"]["alerts"] == 1
    assert users["bia@example.com"]["access"] == "expired" and users["bia@example.com"]["hasAccess"] is False
    assert [u["email"] for u in client.get("/admin/users", params={"q": "bia"}).json()] == ["bia@example.com"]
    assert [u["email"] for u in client.get("/admin/users", params={"access": "expired"}).json()] == ["bia@example.com"]
    assert client.get("/admin/users", params={"access": "qualquer"}).status_code == 422


def test_admin_grants_extends_and_cuts_access(client, signup, session_factory, make_client):
    signup(client)
    other = make_client()
    signup(other, "bia@example.com")
    _make_admin(session_factory)
    bia_id = _user(session_factory, "bia@example.com").id

    def act(action, **extra):
        return client.patch(f"/admin/users/{bia_id}", json={"action": action, **extra})

    assert act("end_trial").json()["access"] == "expired"
    assert other.post("/search/run", json={}).status_code == 402  # a Bia está bloqueada
    assert act("grant_access").json()["access"] == "paid"
    assert other.get("/me").json()["hasAccess"] is True
    assert act("revoke_access").json()["access"] == "expired"
    ext = act("extend_trial", days=10).json()
    assert ext["access"] == "trial"
    assert timedelta(days=9, hours=23) < _user(session_factory, "bia@example.com").trial_ends_at - utcnow() <= timedelta(days=10)
    assert act("suspend").json()["status"] == "SUSPENDED"
    assert other.post("/auth/login", json={"email": "bia@example.com", "password": PASSWORD}).status_code == 403
    assert act("reactivate").json()["status"] == "ACTIVE"


def test_admin_cannot_lock_itself_out_or_delete_a_stripe_payer(client, signup, session_factory, make_client):
    signup(client)
    other = make_client()
    signup(other, "bia@example.com")
    _make_admin(session_factory)
    me = _user(session_factory, "ana@example.com").id
    for action in ("suspend", "remove_admin", "revoke_access", "end_trial"):
        assert client.patch(f"/admin/users/{me}", json={"action": action}).status_code == 409
    assert client.delete(f"/admin/users/{me}").status_code == 409

    with session_factory() as db:
        bia = db.scalar(select(User).where(User.email == "bia@example.com"))
        bia.stripe_subscription_id, bia.subscription_status = "sub_1", "active"
        db.commit()
        bia_id = bia.id
    assert client.patch(f"/admin/users/{bia_id}", json={"action": "revoke_access"}).status_code == 409
    assert client.delete(f"/admin/users/{bia_id}").status_code == 409  # cancele na Stripe antes
    with session_factory() as db:
        db.scalar(select(User).where(User.email == "bia@example.com")).subscription_status = "canceled"
        db.commit()
    assert client.delete(f"/admin/users/{bia_id}").status_code == 204
    assert _user(session_factory, "bia@example.com") is None


def test_admin_lists_monitor_runs(client, signup, session_factory):
    from app.models import MonitorRun

    signup(client)
    _make_admin(session_factory)
    with session_factory() as db:
        db.add_all([MonitorRun(search_key="pt|iphone|1", status="ok", raw_count=96, match_count=2, ended_at=utcnow()),
                    MonitorRun(search_key="fr|ps5|1", status="error", error="blocked")])
        db.commit()
    assert len(client.get("/admin/runs").json()) == 2
    errors = client.get("/admin/runs", params={"status": "error"}).json()
    assert len(errors) == 1 and errors[0]["error"] == "blocked"
    assert client.get("/admin/overview").json()["runErrorsLastDay"] == 1
