"""Configurações do usuário e liga/desliga do monitor. O motor que roda as buscas entra na próxima etapa."""

from datetime import timedelta

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_access, require_active
from app.entitlements import entitlements_for
from app.errors import ApiError
from app.models import MonitorRun, User, UserSettings
from app.services.monitor import engine as monitor_engine
from app.schemas import MonitorRunOut, MonitorStatusOut, SettingsOut, SettingsPatch

router = APIRouter(tags=["monitor"])


def _settings(db: Session, user: User) -> UserSettings:
    settings = db.get(UserSettings, user.id)
    if settings is None:  # contas antigas/criadas por CLI
        settings = UserSettings(user_id=user.id)
        db.add(settings)
        db.flush()
    return settings


@router.get("/settings", response_model=SettingsOut)
def get_settings_route(user: User = Depends(require_active), db: Session = Depends(get_db)) -> SettingsOut:
    return SettingsOut(interval_minutes=_settings(db, user).interval_minutes)


@router.patch("/settings", response_model=SettingsOut)
def patch_settings(
    body: SettingsPatch, user: User = Depends(require_active), db: Session = Depends(get_db)
) -> SettingsOut:
    settings = _settings(db, user)
    if body.interval_minutes is not None:
        floor = entitlements_for(user.plan).min_interval_minutes
        if body.interval_minutes < floor:
            raise ApiError(402, "PLAN_LIMIT_REACHED", f"Your plan checks at most every {floor:g} min")
        settings.interval_minutes = body.interval_minutes
    db.commit()
    return SettingsOut(interval_minutes=settings.interval_minutes)


@router.get("/monitor/status", response_model=MonitorStatusOut)
def monitor_status(user: User = Depends(require_active), db: Session = Depends(get_db)) -> MonitorStatusOut:
    settings = _settings(db, user)
    runs = db.scalars(select(MonitorRun).order_by(MonitorRun.started_at.desc()).limit(24)).all()
    next_run = (
        settings.last_run_at + timedelta(minutes=settings.interval_minutes)
        if settings.monitor_enabled and settings.last_run_at
        else None
    )
    return MonitorStatusOut(
        state="ACTIVE" if settings.monitor_enabled else "PAUSED",
        enabled=settings.monitor_enabled,
        interval_minutes=settings.interval_minutes,
        last_run_at=settings.last_run_at,
        next_run_at=next_run,
        last_error=settings.last_error,
        runs=[
            MonitorRunOut(
                id=r.id,
                started_at=r.started_at,
                duration_ms=int((r.ended_at - r.started_at).total_seconds() * 1000) if r.ended_at else 0,
                analyzed=r.raw_count,
                matches=r.match_count,
                sent=0,
                status="ok" if r.status == "running" else r.status,  # type: ignore[arg-type]
                error=r.error,
            )
            for r in runs
        ],
        median_detection_seconds=None,
    )


def _set_enabled(db: Session, user: User, enabled: bool) -> Response:
    settings = _settings(db, user)
    settings.monitor_enabled = enabled
    db.commit()
    if enabled:
        monitor_engine.wake()  # o 1º ciclo roda agora, sem esperar o próximo intervalo
    return Response(status_code=204)


@router.post("/monitor/start", status_code=204, response_class=Response)
def monitor_start(user: User = Depends(require_access), db: Session = Depends(get_db)) -> Response:
    return _set_enabled(db, user, True)


@router.post("/monitor/stop", status_code=204, response_class=Response)
def monitor_stop(user: User = Depends(require_active), db: Session = Depends(get_db)) -> Response:
    return _set_enabled(db, user, False)
