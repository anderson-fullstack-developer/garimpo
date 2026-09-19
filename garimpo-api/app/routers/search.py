"""Busca manual ("Buscar agora") e prévia de um alerta."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_access, require_active
from app.errors import ApiError
from app.models import User
from app.ratelimit import RateLimiter
from app.schemas import AlertIn, ApiErrorOut, ItemOut, PreviewOut, PreviewRowOut, SearchRunIn, SearchStatusOut
from app.services.currency import from_eur
from app.services.filters import price_eur_of, price_of
from app.services import manual_search
from app.services.monitor import preview_alert
from app.services.vinted import RawItem, VintedError

router = APIRouter(tags=["search"])

_manual_limiter = RateLimiter(6, 60, "Too many searches in a row. Wait a moment.")
_preview_limiter = RateLimiter(40, 60, "Too many previews in a row. Wait a moment.")


@router.post("/search/run", response_model=SearchStatusOut, status_code=202)
def search_run(
    body: SearchRunIn | None = None,
    user: User = Depends(require_access),
    db: Session = Depends(get_db),
) -> SearchStatusOut:
    """Dá a partida na busca contínua e responde na hora; ela segue no servidor até `POST /search/stop`."""
    if manual_search.status(user.id).state not in ("running", "stopping"):
        _manual_limiter.check(user.id)
    job, started = manual_search.start(user, db.get_bind())
    if started:
        _manual_limiter.record(user.id)
    return _out(job)


@router.post("/search/stop", response_model=SearchStatusOut)
def search_stop(user: User = Depends(require_active)) -> SearchStatusOut:
    return _out(manual_search.stop(user.id))


@router.get("/search/status", response_model=SearchStatusOut)
def search_status(user: User = Depends(require_active)) -> SearchStatusOut:
    return _out(manual_search.status(user.id))


def _out(job: manual_search.SearchJob) -> SearchStatusOut:
    error = ApiErrorOut(code=job.error_code, message=job.error_message or "") if job.error_code else None
    return SearchStatusOut(
        state=job.state,  # type: ignore[arg-type]
        analyzed=job.analyzed,
        new_items=job.new_items,
        cycles=job.cycles,
        error=error,
        started_at=job.started_at,
        finished_at=job.finished_at,
        last_cycle_at=job.last_cycle_at,
    )


def _row(raw: RawItem, alert_name: str, draft: AlertIn, reasons: list[str], currency: str) -> PreviewRowOut:
    price = price_of(raw)
    perfect = (draft.perfect_min is not None or draft.perfect_max is not None) and (
        (draft.perfect_min is None or price >= draft.perfect_min)
        and (draft.perfect_max is None or price <= draft.perfect_max)
    )
    return PreviewRowOut(
        item=ItemOut(
            id=str(raw.vinted_id),
            title=raw.title,
            title_pt=None,
            price=price,
            price_eur=round(price_eur_of(raw), 2),
            price_user=round(from_eur(price_eur_of(raw), currency), 2),
            user_currency=currency,
            currency=raw.currency,
            condition=raw.condition,  # type: ignore[arg-type]
            seller_login=raw.seller_login,
            url=raw.url,
            photo_url=raw.photo_url,
            posted_at=raw.posted_at,
            first_seen_at=datetime.now(timezone.utc),
            alert_id="preview",
            alert_name=alert_name,
            is_perfect=bool(perfect),
        ),
        matched=not reasons,
        reasons=reasons,
    )


@router.post("/alerts/preview", response_model=PreviewOut)
def alert_preview(body: AlertIn, user: User = Depends(require_access)) -> PreviewOut:
    """Mostra o que este alerta encontraria agora e por que cada anúncio foi descartado (não grava nada)."""
    _preview_limiter.check(user.id)
    _preview_limiter.record(user.id)
    try:
        rows, analyzed = preview_alert(body)
    except VintedError as exc:
        raise ApiError(502, "UPSTREAM_ERROR", f"Could not search Vinted right now: {exc}") from exc
    name = body.name.strip() or body.query
    built = [_row(raw, name, body, reasons, user.currency) for raw, reasons in rows]
    return PreviewOut(
        matched=[r for r in built if r.matched],
        discarded=[r for r in built if not r.matched],
        analyzed=analyzed,
    )
