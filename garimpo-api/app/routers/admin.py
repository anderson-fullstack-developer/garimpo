"""Painel do administrador: ver contas, dar ou cortar acesso, apagar contas e acompanhar o monitor.

Tudo aqui exige `role == "ADMIN"`. Para quem não é administrador as rotas respondem 404 (nem revela que existem).
"""

from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.access import has_access, has_subscription, trial_active
from app.db import get_db
from app.deps import get_current_user
from app.errors import ApiError, not_found
from app.models import Alert, Destination, Item, Match, MonitorRun, Notification, User, UserSettings, utcnow
from app.schemas import CamelModel

router = APIRouter(prefix="/admin", tags=["admin"])

STRIPE_LIVE = {"active", "trialing", "past_due"}


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "ADMIN":
        raise not_found("Page")
    return user


class AdminUserOut(CamelModel):
    id: str
    email: str
    role: Literal["USER", "ADMIN"]
    status: Literal["PENDING", "ACTIVE", "SUSPENDED"]
    country: str | None
    language: str
    currency: str
    verified: bool
    created_at: datetime
    last_login_at: datetime | None
    trial_ends_at: datetime | None
    subscription_status: str | None
    stripe_customer: bool
    has_access: bool
    access: Literal["admin", "paid", "trial", "expired", "unverified"]
    alerts: int
    destinations: int
    monitor_enabled: bool
    notified: int  # anúncios que chegaram de fato no Telegram
    notify_failed: int  # anúncios que não chegaram (sem destino, bot bloqueado...)
    last_notified_at: datetime | None


class AdminOverviewOut(CamelModel):
    users: int
    new_this_week: int
    verified: int
    unverified: int
    in_trial: int
    paid: int
    expired: int
    suspended: int
    alerts: int
    destinations: int
    items: int
    monitor_on: int
    runs_last_day: int
    run_errors_last_day: int


class AdminRunOut(CamelModel):
    id: str
    search_key: str
    started_at: datetime
    duration_ms: int
    status: str
    analyzed: int
    matches: int
    error: str | None


class AdminAlertTallyOut(CamelModel):
    id: str
    name: str
    query: str
    country: str
    active: bool
    sent: int
    failed: int


class AdminNotificationOut(CamelModel):
    id: str
    sent_at: datetime
    ok: bool
    error: str | None
    alert_name: str | None
    title: str
    price: float
    currency: str
    url: str
    photo_url: str | None
    domain: str


class AdminUserNotificationsOut(CamelModel):
    sent: int
    failed: int
    alerts: list[AdminAlertTallyOut]
    items: list[AdminNotificationOut]


class AdminUserPatch(CamelModel):
    action: Literal[
        "grant_access", "revoke_access", "extend_trial", "end_trial", "suspend", "reactivate", "make_admin", "remove_admin"
    ]
    days: int = Field(default=7, ge=1, le=365)


def _access_label(user: User, now: datetime) -> str:
    if user.role == "ADMIN":
        return "admin"
    if user.email_verified_at is None:
        return "unverified"
    if has_subscription(user):
        return "paid"
    return "trial" if trial_active(user, now) else "expired"


def _out(db: Session, user: User, counts: dict) -> AdminUserOut:
    now = utcnow()
    settings = db.get(UserSettings, user.id)
    return AdminUserOut(
        id=user.id,
        email=user.email,
        role=user.role,  # type: ignore[arg-type]
        status=user.status,  # type: ignore[arg-type]
        country=user.country,
        language=user.language,
        currency=user.currency,
        verified=user.email_verified_at is not None,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        trial_ends_at=user.trial_ends_at,
        subscription_status=user.subscription_status,
        stripe_customer=bool(user.stripe_customer_id),
        has_access=has_access(user, now),
        access=_access_label(user, now),  # type: ignore[arg-type]
        alerts=counts["alerts"].get(user.id, 0),
        destinations=counts["destinations"].get(user.id, 0),
        monitor_enabled=bool(settings and settings.monitor_enabled),
        notified=counts["notified"].get(user.id, 0),
        notify_failed=counts["notify_failed"].get(user.id, 0),
        last_notified_at=counts["last_notified"].get(user.id),
    )


# Um registro em `Notification` pode ser: aviso que chegou (ok, sem erro), anúncio marcado como visto em
# silêncio na 1ª busca do alerta (ok, error="baseline") ou aviso que falhou (ok=False, com o motivo).
DELIVERED = and_(Notification.ok.is_(True), Notification.error.is_(None))
FAILED = Notification.ok.is_(False)


def _counts(db: Session) -> dict:
    def grouped(model) -> dict:
        return dict(db.execute(select(model.user_id, func.count()).group_by(model.user_id)).all())

    def notifications(value, where) -> dict:
        return dict(db.execute(select(Notification.user_id, value).where(where).group_by(Notification.user_id)).all())

    return {
        "alerts": grouped(Alert),
        "destinations": grouped(Destination),
        "notified": notifications(func.count(), DELIVERED),
        "notify_failed": notifications(func.count(), FAILED),
        "last_notified": notifications(func.max(Notification.sent_at), DELIVERED),
    }


@router.get("/overview", response_model=AdminOverviewOut)
def overview(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> AdminOverviewOut:
    now = utcnow()
    users = list(db.scalars(select(User)))
    day_ago = now - timedelta(hours=24)
    labels = [_access_label(u, now) for u in users]
    runs = db.execute(select(MonitorRun.status, func.count()).where(MonitorRun.started_at >= day_ago).group_by(MonitorRun.status)).all()
    by_status = dict(runs)
    count = lambda model: db.scalar(select(func.count()).select_from(model)) or 0  # noqa: E731
    return AdminOverviewOut(
        users=len(users),
        new_this_week=sum(1 for u in users if u.created_at >= now - timedelta(days=7)),
        verified=sum(1 for u in users if u.email_verified_at is not None),
        unverified=labels.count("unverified"),
        in_trial=labels.count("trial"),
        paid=labels.count("paid"),
        expired=labels.count("expired"),
        suspended=sum(1 for u in users if u.status == "SUSPENDED"),
        alerts=count(Alert),
        destinations=count(Destination),
        items=count(Item),
        monitor_on=db.scalar(select(func.count()).select_from(UserSettings).where(UserSettings.monitor_enabled.is_(True))) or 0,
        runs_last_day=sum(by_status.values()),
        run_errors_last_day=by_status.get("error", 0) + by_status.get("rate_limited", 0),
    )


@router.get("/users", response_model=list[AdminUserOut])
def list_users(
    q: str | None = None,
    access: str | None = Query(default=None, pattern="^(admin|paid|trial|expired|unverified)$"),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[AdminUserOut]:
    query = select(User).order_by(User.created_at.desc()).limit(500)
    if q:
        query = query.where(User.email.ilike(f"%{q.strip()}%"))
    counts = _counts(db)
    rows = [_out(db, u, counts) for u in db.scalars(query)]
    return [r for r in rows if access is None or r.access == access]


@router.get("/users/{user_id}/notifications", response_model=AdminUserNotificationsOut)
def user_notifications(
    user_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminUserNotificationsOut:
    """O que chegou (ou deveria ter chegado) no Telegram desta conta: totais por alerta e os anúncios mais recentes."""
    user = db.get(User, user_id)
    if user is None:
        raise not_found("Account")

    def per_alert(where) -> dict[str, int]:
        query = (
            select(Match.alert_id, func.count())
            .join(Notification, and_(Notification.user_id == Match.user_id, Notification.item_id == Match.item_id))
            .where(Match.user_id == user.id, where)
            .group_by(Match.alert_id)
        )
        return dict(db.execute(query).all())

    sent_by_alert, failed_by_alert = per_alert(DELIVERED), per_alert(FAILED)
    alerts = [
        AdminAlertTallyOut(
            id=a.id,
            name=a.name,
            query=a.query,
            country=a.country,
            active=a.active,
            sent=sent_by_alert.get(a.id, 0),
            failed=failed_by_alert.get(a.id, 0),
        )
        for a in db.scalars(select(Alert).where(Alert.user_id == user.id).order_by(Alert.created_at))
    ]

    rows = db.execute(
        select(Notification, Item)
        .join(Item, Item.id == Notification.item_id)
        .where(Notification.user_id == user.id, or_(DELIVERED, FAILED))
        .order_by(Notification.sent_at.desc())
        .limit(limit)
    ).all()
    # O mesmo anúncio pode casar com mais de um alerta do usuário: mostramos o primeiro.
    alert_name: dict[str, str] = {}
    if rows:
        for item_id, name in db.execute(
            select(Match.item_id, Alert.name)
            .join(Alert, Alert.id == Match.alert_id)
            .where(Match.user_id == user.id, Match.item_id.in_([item.id for _, item in rows]))
            .order_by(Match.created_at)
        ).all():
            alert_name.setdefault(item_id, name)

    count = lambda where: db.scalar(select(func.count()).select_from(Notification).where(Notification.user_id == user.id, where)) or 0  # noqa: E731
    return AdminUserNotificationsOut(
        sent=count(DELIVERED),
        failed=count(FAILED),
        alerts=alerts,
        items=[
            AdminNotificationOut(
                id=n.id,
                sent_at=n.sent_at,
                ok=n.ok,
                error=n.error,
                alert_name=alert_name.get(item.id),
                title=item.title_pt or item.title,
                price=float(item.price),
                currency=item.currency,
                url=item.url,
                photo_url=item.photo_url,
                domain=item.domain,
            )
            for n, item in rows
        ],
    )


@router.patch("/users/{user_id}", response_model=AdminUserOut)
def update_user(
    user_id: str, body: AdminUserPatch, admin: User = Depends(require_admin), db: Session = Depends(get_db)
) -> AdminUserOut:
    user = db.get(User, user_id)
    if user is None:
        raise not_found("Account")
    now = utcnow()
    if user.id == admin.id and body.action in ("suspend", "remove_admin", "revoke_access", "end_trial"):
        raise ApiError(409, "VALIDATION_ERROR", "You cannot do this to your own account")

    if body.action == "grant_access":  # cortesia: acesso pago sem passar pela Stripe
        user.subscription_status = "active"
        user.subscription_ends_at = None
    elif body.action == "revoke_access":
        if user.stripe_subscription_id and user.subscription_status in STRIPE_LIVE:
            raise ApiError(409, "VALIDATION_ERROR", "This account pays through Stripe: cancel it in Stripe first")
        user.subscription_status = None
        user.subscription_ends_at = None
    elif body.action == "extend_trial":
        base = user.trial_ends_at if user.trial_ends_at and user.trial_ends_at > now else now
        user.trial_ends_at = base + timedelta(days=body.days)
    elif body.action == "end_trial":
        user.trial_ends_at = now - timedelta(minutes=1)
    elif body.action == "suspend":
        user.status = "SUSPENDED"
        settings = db.get(UserSettings, user.id)
        if settings:
            settings.monitor_enabled = False
    elif body.action == "reactivate":
        user.status = "ACTIVE"
    elif body.action == "make_admin":
        user.role = "ADMIN"
    elif body.action == "remove_admin":
        user.role = "USER"
    db.commit()
    return _out(db, user, _counts(db))


@router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> None:
    user = db.get(User, user_id)
    if user is None:
        raise not_found("Account")
    if user.id == admin.id:
        raise ApiError(409, "VALIDATION_ERROR", "You cannot delete your own account here")
    if user.stripe_subscription_id and user.subscription_status in STRIPE_LIVE:
        raise ApiError(409, "VALIDATION_ERROR", "This account has an active Stripe subscription: cancel it in Stripe first")
    db.delete(user)
    db.commit()


@router.get("/runs", response_model=list[AdminRunOut])
def list_runs(
    status: str | None = Query(default=None, pattern="^(ok|error|rate_limited|running)$"),
    limit: int = Query(default=50, ge=1, le=200),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[AdminRunOut]:
    query = select(MonitorRun).order_by(MonitorRun.started_at.desc()).limit(limit)
    if status:
        query = query.where(MonitorRun.status == status)
    return [
        AdminRunOut(
            id=r.id,
            search_key=r.search_key,
            started_at=r.started_at,
            duration_ms=int((r.ended_at - r.started_at).total_seconds() * 1000) if r.ended_at else 0,
            status=r.status,
            analyzed=r.raw_count,
            matches=r.match_count,
            error=r.error,
        )
        for r in db.scalars(query)
    ]
