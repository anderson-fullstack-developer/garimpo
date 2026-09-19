"""Entrada de eventos dos canais. Hoje: Telegram."""

import hmac

import json

from fastapi import APIRouter, Body, Depends, Header, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.errors import ApiError
from app.services import stripe_billing
from app.services.telegram import TelegramClient
from app.services.telegram_webhook import handle_update

router = APIRouter(tags=["webhooks"])


@router.post("/webhooks/telegram")
def telegram_webhook(
    update: dict = Body(...),
    secret: str | None = Header(default=None, alias="X-Telegram-Bot-Api-Secret-Token"),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    settings = get_settings()
    if not settings.telegram_bot_token or not settings.telegram_webhook_secret:
        raise ApiError(503, "NOT_CONFIGURED", "Telegram is not configured on this server")
    # Só o Telegram conhece o segredo (definido no setWebhook): sem ele, qualquer um forjaria eventos.
    if not secret or not hmac.compare_digest(secret, settings.telegram_webhook_secret):
        raise ApiError(403, "FORBIDDEN", "Invalid webhook secret")
    handle_update(db, update, TelegramClient())
    return {"ok": True}


@router.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    signature: str | None = Header(default=None, alias="Stripe-Signature"),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    secret = get_settings().stripe_webhook_secret
    if not secret:
        raise ApiError(503, "NOT_CONFIGURED", "Stripe webhook is not configured on this server")
    payload = await request.body()
    # Só a Stripe conhece o segredo: sem a assinatura válida, qualquer um forjaria "pagamento feito".
    if not signature or not stripe_billing.verify_signature(payload, signature, secret):
        raise ApiError(403, "FORBIDDEN", "Invalid webhook signature")
    stripe_billing.handle_event(db, json.loads(payload))
    return {"ok": True}
