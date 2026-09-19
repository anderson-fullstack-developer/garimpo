"""Converte objetos do banco para o JSON que o front espera."""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.access import has_access
from app.models import Alert, Destination, Match, User
from app.schemas import AlertOut, DestinationOut, UserOut


def user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        role=user.role,  # type: ignore[arg-type]
        plan=user.plan,  # type: ignore[arg-type]
        status=user.status,  # type: ignore[arg-type]
        verified=user.email_verified_at is not None,
        created_at=user.created_at,
        trial_ends_at=user.trial_ends_at,
        subscription_status=user.subscription_status,
        subscription_ends_at=user.subscription_ends_at,
        has_access=has_access(user),
        country=user.country,
        language=user.language,
        currency=user.currency,
    )


def start_of_today() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def new_today_counts(db: Session, user_id: str) -> dict[str, int]:
    rows = db.execute(
        select(Match.alert_id, func.count())
        .where(Match.user_id == user_id, Match.created_at >= start_of_today())
        .group_by(Match.alert_id)
    ).all()
    return {alert_id: count for alert_id, count in rows}


def alert_out(alert: Alert, new_today: int = 0) -> AlertOut:
    out = AlertOut.model_validate(alert)
    out.new_today = new_today
    return out


def destination_out(destination: Destination, owner_language: str = "pt") -> DestinationOut:
    return DestinationOut(
        id=destination.id,
        channel=destination.channel,  # type: ignore[arg-type]
        kind=destination.kind,  # type: ignore[arg-type]
        title=destination.title,
        status=destination.status,  # type: ignore[arg-type]
        is_default=destination.is_default,
        linked_at=destination.linked_at,
        language=destination.language or owner_language,
    )
