"""Resultados: anúncios que casaram com os alertas do usuário."""

from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_active
from app.errors import ApiError
from app.models import Alert, Item, Match, User
from app.presenters import start_of_today
from app.services.currency import from_eur, to_eur
from app.schemas import ItemOut, ItemPageOut

router = APIRouter(tags=["items"])

PAGE_SIZE = 20


def _eur(item: Item) -> float:
    return to_eur(float(item.price), item.currency)


def _is_perfect(item: Item, alert: Alert) -> bool:
    price = _eur(item)
    lo, hi = alert.perfect_min, alert.perfect_max
    if lo is None and hi is None:
        return False
    return (lo is None or price >= float(lo)) and (hi is None or price <= float(hi))


@router.get("/items", response_model=ItemPageOut)
def list_items(
    alert_ids: list[str] = Query(default=[], alias="alertIds"),
    min_price: float | None = Query(default=None, alias="minPrice", ge=0),
    max_price: float | None = Query(default=None, alias="maxPrice", ge=0),
    only_perfect: bool = Query(default=False, alias="onlyPerfect"),
    period: Literal["1h", "today", "7d"] | None = None,
    sort: Literal["newest", "price_asc"] = "newest",
    cursor: str | None = None,
    user: User = Depends(require_active),
    db: Session = Depends(get_db),
) -> ItemPageOut:
    try:
        offset = max(0, int(cursor)) if cursor else 0
    except ValueError as exc:
        raise ApiError(422, "VALIDATION_ERROR", "invalid cursor") from exc

    # Um anúncio pode casar com dois alertas: mostra uma vez só (o primeiro que casou).
    first_match = (
        select(Match.item_id, func.min(Match.created_at).label("first_at"))
        .where(Match.user_id == user.id)
        .group_by(Match.item_id)
        .subquery()
    )
    query = (
        select(Item, Alert)
        .join(Match, Match.item_id == Item.id)
        .join(first_match, (first_match.c.item_id == Match.item_id) & (first_match.c.first_at == Match.created_at))
        .join(Alert, Alert.id == Match.alert_id)
        .where(Match.user_id == user.id)
    )
    if alert_ids:
        query = query.where(Match.alert_id.in_(alert_ids))
    if period:
        now = datetime.now(timezone.utc)
        cutoff = {"1h": now - timedelta(hours=1), "today": start_of_today(), "7d": now - timedelta(days=7)}[period]
        query = query.where(Item.first_seen_at >= cutoff)

    if sort == "newest":
        # A Vinted não informa a data de postagem na busca, mas numera os anúncios em ordem crescente:
        # id maior = postado depois. Quando a data existir, ela manda.
        query = query.order_by(Item.posted_at.desc().nulls_last(), Item.vinted_id.desc())

    rows = [(i, a) for i, a in db.execute(query).all()]
    # Cada país mostra a moeda local (PLN, DKK...): preço mínimo/máximo e ordenação valem em EUR.
    if min_price is not None:
        rows = [(i, a) for i, a in rows if _eur(i) >= min_price]
    if max_price is not None:
        rows = [(i, a) for i, a in rows if _eur(i) <= max_price]
    if sort == "price_asc":
        rows.sort(key=lambda row: (_eur(row[0]), row[0].id))
    if only_perfect:
        rows = [(i, a) for i, a in rows if _is_perfect(i, a)]

    total = len(rows)
    page = rows[offset : offset + PAGE_SIZE]
    items = [
        ItemOut(
            id=i.id,
            title=i.title,
            title_pt=i.title_pt if user.language == "pt" else None,
            price=float(i.price),
            price_eur=round(_eur(i), 2),
            price_user=round(from_eur(_eur(i), user.currency), 2),
            user_currency=user.currency,
            currency=i.currency,
            condition=i.condition,  # type: ignore[arg-type]
            seller_login=i.seller_login,
            url=i.url,
            photo_url=i.photo_url,
            posted_at=i.posted_at,
            first_seen_at=i.first_seen_at,
            alert_id=a.id,
            alert_name=a.name,
            is_perfect=_is_perfect(i, a),
        )
        for i, a in page
    ]
    next_cursor = str(offset + PAGE_SIZE) if offset + PAGE_SIZE < total else None
    return ItemPageOut(items=items, next_cursor=next_cursor, total=total)
