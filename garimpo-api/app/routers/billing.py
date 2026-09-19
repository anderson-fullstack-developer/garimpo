"""Assinatura: abre o pagamento (Stripe Checkout) e o portal do cliente."""

import logging

from fastapi import APIRouter, Body, Depends

from app.deps import require_account
from app.errors import ApiError
from app.models import User
from app.services import stripe_billing

router = APIRouter(prefix="/billing", tags=["billing"])
log = logging.getLogger("garimpo.billing")


@router.post("/checkout")
def checkout(_body: dict | None = Body(default=None), user: User = Depends(require_account)) -> dict[str, str]:
    try:
        return {"url": stripe_billing.create_checkout_url(user)}
    except stripe_billing.StripeNotConfigured as exc:
        raise ApiError(503, "NOT_CONFIGURED", "Payments are not available yet") from exc
    except stripe_billing.StripeError as exc:
        log.warning("Stripe checkout failed: %s", exc)
        raise ApiError(502, "UPSTREAM_ERROR", "Could not open the payment page. Try again") from exc


@router.post("/portal")
def portal(user: User = Depends(require_account)) -> dict[str, str]:
    try:
        return {"url": stripe_billing.create_portal_url(user)}
    except stripe_billing.StripeNotConfigured as exc:
        raise ApiError(503, "NOT_CONFIGURED", "Payments are not available yet") from exc
    except stripe_billing.StripeError as exc:
        raise ApiError(400, "VALIDATION_ERROR", str(exc)) from exc
