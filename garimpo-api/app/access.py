"""Quem pode usar as buscas: durante o teste grátis ou com assinatura ativa (administradores sempre)."""

from datetime import datetime, timedelta

from app.config import get_settings
from app.models import User, utcnow

# Estados da assinatura (Stripe) que mantêm o acesso. "past_due" = cobrança falhou, a Stripe ainda tenta de novo.
PAID_STATUSES = {"active", "trialing", "past_due"}


def has_subscription(user: User) -> bool:
    return user.subscription_status in PAID_STATUSES


def trial_active(user: User, now: datetime | None = None) -> bool:
    return user.trial_ends_at is not None and (now or utcnow()) < user.trial_ends_at


def has_access(user: User, now: datetime | None = None) -> bool:
    return user.role == "ADMIN" or has_subscription(user) or trial_active(user, now)


def start_trial(user: User, now: datetime | None = None) -> None:
    """O teste começa quando a conta é ativada (Telegram vinculado) e só uma vez."""
    if user.trial_ends_at is None:
        user.trial_ends_at = (now or utcnow()) + timedelta(days=get_settings().trial_days)
