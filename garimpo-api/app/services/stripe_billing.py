"""Assinatura Garimpo Pro na Stripe (Checkout hospedado). O app nunca toca no cartão."""

import hashlib
import hmac
import logging
import time
from datetime import datetime, timezone

import httpx

from app.config import get_settings
from app.models import User

log = logging.getLogger("garimpo.stripe")
API = "https://api.stripe.com/v1"


class StripeNotConfigured(Exception):
    pass


class StripeError(Exception):
    pass


def _post(path: str, data: dict) -> dict:
    key = get_settings().stripe_secret_key
    if not key:
        raise StripeNotConfigured("Stripe is not configured")
    try:
        response = httpx.post(f"{API}{path}", data=data, auth=(key, ""), timeout=15)
    except httpx.HTTPError as exc:
        raise StripeError(f"Stripe unreachable: {type(exc).__name__}") from exc
    body = response.json() if response.content else {}
    if response.status_code >= 400:
        raise StripeError((body.get("error") or {}).get("message") or f"Stripe answered {response.status_code}")
    return body


def create_checkout_url(user: User) -> str:
    settings = get_settings()
    if not settings.stripe_price_id:
        raise StripeNotConfigured("Stripe price is not configured")
    data = {
        "mode": "subscription",
        "line_items[0][price]": settings.stripe_price_id,
        "line_items[0][quantity]": "1",
        "client_reference_id": user.id,
        "subscription_data[metadata][user_id]": user.id,
        "success_url": f"{settings.web_url}/app/results?subscribed=1",
        "cancel_url": f"{settings.web_url}/app/results?canceled=1",
        "allow_promotion_codes": "true",
    }
    if user.stripe_customer_id:
        data["customer"] = user.stripe_customer_id
    else:
        data["customer_email"] = user.email
    return _post("/checkout/sessions", data)["url"]


def create_portal_url(user: User) -> str:
    if not user.stripe_customer_id:
        raise StripeError("No subscription to manage yet")
    return _post(
        "/billing_portal/sessions",
        {"customer": user.stripe_customer_id, "return_url": f"{get_settings().web_url}/app/settings?tab=account"},
    )["url"]


# ------------------------------------------------------------------ webhook
def verify_signature(payload: bytes, header: str, secret: str, tolerance: int = 300, now: float | None = None) -> bool:
    """Confere o cabeçalho `Stripe-Signature` (t=...,v1=...): HMAC-SHA256 de "t.corpo" com o segredo do webhook."""
    pairs = [p.split("=", 1) for p in header.split(",") if "=" in p]
    stamps = [v for k, v in pairs if k == "t"]
    signatures = [v for k, v in pairs if k == "v1"]
    if not stamps or not signatures or not stamps[0].isdigit():
        return False
    stamp = int(stamps[0])
    if abs((now if now is not None else time.time()) - stamp) > tolerance:
        return False
    expected = hmac.new(secret.encode(), f"{stamp}.".encode() + payload, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, s) for s in signatures)


def _period_end(subscription: dict) -> datetime | None:
    end = subscription.get("current_period_end")
    if end is None:  # versões novas da API trazem o fim do período nos itens
        items = (subscription.get("items") or {}).get("data") or []
        end = items[0].get("current_period_end") if items else None
    return datetime.fromtimestamp(end, tz=timezone.utc) if end else None


def _find_user(db, *, user_id: str | None, customer: str | None, subscription: str | None) -> User | None:
    from sqlalchemy import select

    if user_id and (user := db.get(User, user_id)):
        return user
    if subscription and (user := db.scalar(select(User).where(User.stripe_subscription_id == subscription))):
        return user
    if customer:
        return db.scalar(select(User).where(User.stripe_customer_id == customer))
    return None


def handle_event(db, event: dict) -> str:
    """Aplica um evento da Stripe à conta. Devolve uma etiqueta do que foi feito (útil em logs e testes)."""
    kind = event.get("type", "")
    obj = (event.get("data") or {}).get("object") or {}
    if kind == "checkout.session.completed":
        user = _find_user(db, user_id=obj.get("client_reference_id"), customer=obj.get("customer"), subscription=obj.get("subscription"))
        if user is None:
            return "unknown_user"
        user.stripe_customer_id = obj.get("customer") or user.stripe_customer_id
        user.stripe_subscription_id = obj.get("subscription") or user.stripe_subscription_id
        if obj.get("payment_status") in ("paid", "no_payment_required"):
            user.subscription_status = "active"
        db.commit()
        return "checkout_completed"
    if kind in ("customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted"):
        user_id = (obj.get("metadata") or {}).get("user_id")
        user = _find_user(db, user_id=user_id, customer=obj.get("customer"), subscription=obj.get("id"))
        if user is None:
            return "unknown_user"
        user.stripe_customer_id = obj.get("customer") or user.stripe_customer_id
        user.stripe_subscription_id = obj.get("id") or user.stripe_subscription_id
        user.subscription_status = "canceled" if kind.endswith("deleted") else obj.get("status")
        user.subscription_ends_at = _period_end(obj) or user.subscription_ends_at
        db.commit()
        return "subscription_updated"
    return "ignored"
