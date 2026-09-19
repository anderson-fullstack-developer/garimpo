"""Teste grátis de 7 dias, bloqueio depois dele e assinatura pela Stripe."""

import hashlib
import hmac
import json
import time
from datetime import timedelta

import httpx
from sqlalchemy import select

from app.access import has_access
from app.models import User, utcnow
from app.services import stripe_billing
from tests.conftest import ALERT, T, make_raw, run_search
from tests.test_telegram import FakeTG, new_code, private


def _user(session_factory, email="ana@example.com"):
    with session_factory() as db:
        return db.scalar(select(User).where(User.email == email))


def _set(session_factory, **fields):
    with session_factory() as db:
        user = db.scalar(select(User))
        for key, value in fields.items():
            setattr(user, key, value)
        db.commit()


def test_trial_starts_when_telegram_is_linked_and_lasts_seven_days(client, session_factory):
    from app.services.telegram_webhook import handle_update
    from tests.conftest import PASSWORD

    client.post("/auth/register", json={"email": "ana@example.com", "password": PASSWORD, "captchaToken": "x"})
    me = client.post("/auth/login", json={"email": "ana@example.com", "password": PASSWORD}).json()
    assert me["trialEndsAt"] is None and me["hasAccess"] is False  # o relógio ainda não começou
    with session_factory() as db:
        assert handle_update(db, private(11, new_code(client, "PRIVATE")), FakeTG()) == "linked"
    me = client.get("/me").json()
    assert me["hasAccess"] is True
    remaining = _user(session_factory).trial_ends_at - utcnow()
    assert timedelta(days=6, hours=23) < remaining <= timedelta(days=7)


def test_after_the_trial_search_is_blocked_but_the_rest_of_the_app_still_opens(client, signup, session_factory, fake_source):
    signup(client)
    client.post("/alerts", json=ALERT)
    _set(session_factory, trial_ends_at=utcnow() - timedelta(minutes=1))

    assert client.get("/me").json()["hasAccess"] is False
    blocked = client.post("/search/run", json={})
    assert blocked.status_code == 402 and blocked.json()["code"] == "SUBSCRIPTION_REQUIRED"
    assert client.post("/monitor/start").status_code == 402
    assert client.post("/alerts/preview", json=ALERT).status_code == 402
    assert client.get("/alerts").status_code == 200  # ver e editar continua livre
    assert client.get("/items").status_code == 200
    assert client.get("/destinations").status_code == 200


def test_expired_users_are_skipped_by_the_monitor_and_get_no_alerts(client, signup, link_destination, fake_source, fake_channel, engine_, session_factory):
    signup(client)
    link_destination("ana@example.com")
    client.post("/alerts", json={**ALERT, "notifyOnFirstRun": True})
    client.post("/monitor/start")
    fake_source.put("iphone 12", [make_raw(1, "iPhone 12", 80)])
    _set(session_factory, trial_ends_at=T(0) - timedelta(days=1))  # o motor usa o relógio do ciclo (T)
    result = engine_.tick(T(0))
    assert result.users == 0 and fake_channel.sent == [] and fake_source.calls == []


def test_a_running_search_stops_by_itself_when_the_trial_ends(client, signup, session_factory, fake_source, settings, monkeypatch):
    import time as _time

    monkeypatch.setattr(settings, "manual_search_pause_seconds", 0.05)
    signup(client)
    client.post("/alerts", json=ALERT)
    assert client.post("/search/run", json={}).status_code == 202
    deadline = _time.time() + 10
    while client.get("/search/status").json()["cycles"] < 1 and _time.time() < deadline:
        _time.sleep(0.02)
    _set(session_factory, trial_ends_at=utcnow() - timedelta(seconds=1))
    while client.get("/search/status").json()["state"] == "running" and _time.time() < deadline:
        _time.sleep(0.02)
    final = client.get("/search/status").json()
    assert final["state"] == "error" and final["error"]["code"] == "SUBSCRIPTION_REQUIRED"


def test_an_active_subscription_unblocks_and_canceled_blocks_again(client, signup, session_factory, fake_source):
    signup(client)
    _set(session_factory, trial_ends_at=utcnow() - timedelta(days=1))
    assert client.post("/search/run", json={}).status_code == 402
    _set(session_factory, subscription_status="active")
    assert client.get("/me").json()["hasAccess"] is True
    assert run_search(client)["state"] in ("done", "error")  # a busca roda
    _set(session_factory, subscription_status="canceled")
    assert client.post("/search/run", json={}).status_code == 402


def test_admins_never_lose_access(client, signup, session_factory):
    signup(client)
    _set(session_factory, trial_ends_at=utcnow() - timedelta(days=30), role="ADMIN")
    with session_factory() as db:
        assert has_access(db.scalar(select(User))) is True


# ------------------------------------------------------------------ Stripe
def _sign(payload: bytes, secret: str, stamp: int | None = None) -> str:
    stamp = stamp or int(time.time())
    digest = hmac.new(secret.encode(), f"{stamp}.".encode() + payload, hashlib.sha256).hexdigest()
    return f"t={stamp},v1={digest}"


def test_signature_check_accepts_only_fresh_correctly_signed_payloads():
    body = b'{"type":"x"}'
    assert stripe_billing.verify_signature(body, _sign(body, "whsec_a"), "whsec_a")
    assert not stripe_billing.verify_signature(body, _sign(body, "whsec_a"), "whsec_b")  # segredo errado
    assert not stripe_billing.verify_signature(b'{"type":"y"}', _sign(body, "whsec_a"), "whsec_a")  # corpo alterado
    assert not stripe_billing.verify_signature(body, _sign(body, "whsec_a", stamp=int(time.time()) - 3600), "whsec_a")  # velho
    assert not stripe_billing.verify_signature(body, "lixo", "whsec_a")


def test_checkout_needs_configuration_then_returns_the_stripe_url(client, signup, settings, monkeypatch):
    signup(client)
    assert client.post("/billing/checkout").status_code == 503  # sem chaves: pagamento indisponível

    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_x")
    monkeypatch.setattr(settings, "stripe_price_id", "price_test_1")
    sent = {}

    def fake_post(url, data=None, auth=None, timeout=None):
        sent.update(url=url, data=data, auth=auth)
        return httpx.Response(200, json={"url": "https://checkout.stripe.com/pay/abc"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    r = client.post("/billing/checkout", json={"plan": "PRO", "interval": "month"})
    assert r.status_code == 200 and r.json() == {"url": "https://checkout.stripe.com/pay/abc"}
    assert sent["url"].endswith("/checkout/sessions") and sent["auth"] == ("sk_test_x", "")
    assert sent["data"]["mode"] == "subscription" and sent["data"]["line_items[0][price]"] == "price_test_1"
    assert sent["data"]["client_reference_id"] and sent["data"]["customer_email"] == "ana@example.com"
    assert "trial_period_days" not in json.dumps(sent["data"])  # o teste grátis é do app, não da Stripe


def test_webhook_activates_and_cancels_the_subscription(client, signup, session_factory, settings, monkeypatch):
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_test")
    signup(client)
    uid = _user(session_factory).id
    _set(session_factory, trial_ends_at=utcnow() - timedelta(days=1))

    def send(event, secret="whsec_test"):
        body = json.dumps(event).encode()
        return client.post("/webhooks/stripe", content=body, headers={"Stripe-Signature": _sign(body, secret), "content-type": "application/json"})

    assert send({"type": "checkout.session.completed", "data": {"object": {}}}, secret="errado").status_code == 403  # forjado
    assert client.post("/webhooks/stripe", json={}).status_code == 403  # sem assinatura

    done = {"type": "checkout.session.completed", "data": {"object": {"client_reference_id": uid, "customer": "cus_1", "subscription": "sub_1", "payment_status": "paid"}}}
    assert send(done).status_code == 200
    me = client.get("/me").json()
    assert me["subscriptionStatus"] == "active" and me["hasAccess"] is True

    period_end = int(time.time()) + 30 * 86400
    updated = {"type": "customer.subscription.updated", "data": {"object": {"id": "sub_1", "customer": "cus_1", "status": "past_due", "current_period_end": period_end}}}
    send(updated)
    me = client.get("/me").json()
    assert me["subscriptionStatus"] == "past_due" and me["hasAccess"] is True and me["subscriptionEndsAt"]  # a Stripe ainda tenta cobrar

    deleted = {"type": "customer.subscription.deleted", "data": {"object": {"id": "sub_1", "customer": "cus_1", "status": "canceled"}}}
    send(deleted)
    me = client.get("/me").json()
    assert me["subscriptionStatus"] == "canceled" and me["hasAccess"] is False
    assert client.post("/search/run", json={}).status_code == 402


def test_webhook_is_off_without_a_secret(client):
    assert client.post("/webhooks/stripe", json={}).status_code == 503


def test_portal_needs_a_customer_first(client, signup, settings, monkeypatch, session_factory):
    signup(client)
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_x")
    assert client.post("/billing/portal").status_code == 400  # ainda não assinou
    _set(session_factory, stripe_customer_id="cus_9")
    monkeypatch.setattr(httpx, "post", lambda url, data=None, auth=None, timeout=None: httpx.Response(200, json={"url": "https://billing.stripe.com/p/x"}, request=httpx.Request("POST", url)))
    r = client.post("/billing/portal")
    assert r.status_code == 200 and r.json()["url"].startswith("https://billing.stripe.com/")
