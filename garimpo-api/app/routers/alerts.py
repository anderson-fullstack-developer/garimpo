from fastapi import APIRouter, Depends, Response
from pydantic import ValidationError
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_active
from app.entitlements import entitlements_for
from app.errors import ApiError, not_found
from app.models import Alert, Destination, Match, User
from app.presenters import alert_out, new_today_counts
from app.schemas import AlertIn, AlertOut, AlertPatch, PresetOut
from app.services.presets import PRESETS

router = APIRouter(prefix="/alerts", tags=["alerts"])

# Campos do AlertIn que existem como colunas em Alert (mesmo nome).
_FIELDS = tuple(AlertIn.model_fields)


def _owned(db: Session, user: User, alert_id: str) -> Alert:
    alert = db.get(Alert, alert_id)
    if alert is None or alert.user_id != user.id:
        raise not_found("Alert")  # 404 também para alerta de outra pessoa: não revela que existe
    return alert


def _validate_relations(db: Session, user: User, data: AlertIn) -> None:
    ent = entitlements_for(user.plan)
    if data.pages > ent.max_pages:
        raise ApiError(402, "PLAN_LIMIT_REACHED", f"Your plan allows scanning up to {ent.max_pages} page(s)")
    if data.destination_id is not None:
        destination = db.get(Destination, data.destination_id)
        if destination is None or destination.user_id != user.id:
            raise ApiError(422, "VALIDATION_ERROR", "destinationId: invalid destination")


def _assert_room(db: Session, user: User) -> None:
    used = db.scalar(select(func.count()).select_from(Alert).where(Alert.user_id == user.id)) or 0
    if used >= entitlements_for(user.plan).max_alerts:
        raise ApiError(402, "PLAN_LIMIT_REACHED", "Your plan's alert limit has been reached")


# Campos que mudam QUAIS anúncios casam. Mexer neles invalida os resultados antigos do alerta.
_CRITERIA = (
    "query", "match_type", "required_words", "exclude_words", "exclude_presets", "min_price",
    "max_price", "status_filter", "max_age_minutes", "pages", "country", "vinted_params",
)  # fmt: skip


def _criteria(alert: Alert) -> list:
    return [float(v) if v.__class__.__name__ == "Decimal" else v for v in (getattr(alert, f) for f in _CRITERIA)]


def _apply(alert: Alert, data: AlertIn) -> None:
    for field in _FIELDS:
        setattr(alert, field, getattr(data, field))
    alert.name = data.name.strip() or data.query


@router.get("", response_model=list[AlertOut])
def list_alerts(user: User = Depends(require_active), db: Session = Depends(get_db)) -> list[AlertOut]:
    counts = new_today_counts(db, user.id)
    alerts = db.scalars(select(Alert).where(Alert.user_id == user.id).order_by(Alert.created_at)).all()
    return [alert_out(a, counts.get(a.id, 0)) for a in alerts]


@router.get("/presets", response_model=list[PresetOut])
def presets(_: User = Depends(require_active)) -> list[dict]:
    return PRESETS


@router.get("/{alert_id}", response_model=AlertOut)
def get_alert(alert_id: str, user: User = Depends(require_active), db: Session = Depends(get_db)) -> AlertOut:
    alert = _owned(db, user, alert_id)
    return alert_out(alert, new_today_counts(db, user.id).get(alert.id, 0))


@router.post("", response_model=AlertOut, status_code=201)
def create_alert(body: AlertIn, user: User = Depends(require_active), db: Session = Depends(get_db)) -> AlertOut:
    _assert_room(db, user)
    _validate_relations(db, user, body)
    alert = Alert(user_id=user.id)
    _apply(alert, body)
    db.add(alert)
    db.commit()
    return alert_out(alert)


@router.patch("/{alert_id}", response_model=AlertOut)
def update_alert(
    alert_id: str,
    body: AlertPatch,
    user: User = Depends(require_active),
    db: Session = Depends(get_db),
) -> AlertOut:
    alert = _owned(db, user, alert_id)
    merged = AlertIn.model_validate(alert).model_dump()
    merged.update(body.model_dump(exclude_unset=True))
    try:
        data = AlertIn.model_validate(merged)
    except ValidationError as exc:
        first = exc.errors()[0]
        raise ApiError(422, "VALIDATION_ERROR", f"{'.'.join(map(str, first['loc']))}: {first['msg']}".lstrip(": ")) from exc
    _validate_relations(db, user, data)
    before, was_active = _criteria(alert), alert.active
    _apply(alert, data)
    if _criteria(alert) != before:
        # Outra busca = outro conjunto de anúncios: apaga os casamentos antigos e refaz o "baseline".
        db.execute(delete(Match).where(Match.alert_id == alert.id))
        alert.baselined_at = None
        alert.min_item_id = None
    elif data.active and not was_active:
        alert.baselined_at = None
        alert.min_item_id = None  # voltou depois de pausado: não despeja o que apareceu enquanto isso
    db.commit()
    return alert_out(alert, new_today_counts(db, user.id).get(alert.id, 0))


@router.delete("/{alert_id}", status_code=204, response_class=Response)
def delete_alert(alert_id: str, user: User = Depends(require_active), db: Session = Depends(get_db)) -> Response:
    db.delete(_owned(db, user, alert_id))
    db.commit()
    return Response(status_code=204)


@router.post("/{alert_id}/duplicate", response_model=AlertOut, status_code=201)
def duplicate_alert(alert_id: str, user: User = Depends(require_active), db: Session = Depends(get_db)) -> AlertOut:
    source = _owned(db, user, alert_id)
    _assert_room(db, user)
    data = AlertIn.model_validate(source).model_copy(update={"name": f"{source.name} (copy)"[:80]})
    alert = Alert(user_id=user.id)
    _apply(alert, data)
    db.add(alert)
    db.commit()
    return alert_out(alert)
