"""Canais e destinos de entrega. O vínculo real com o Telegram (webhook) entra na próxima etapa."""

from datetime import timedelta

from fastapi import APIRouter, Depends, Response
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import require_account, require_active
from app.entitlements import entitlements_for
from app.errors import ApiError, not_found
from app.models import Alert, Destination, Item, Match, User, utcnow
from app.countries import LANGUAGES
from app.presenters import destination_out
from app.services.messages import tr
from app.services.channels import ChannelError, ChannelNotConfigured, PermanentChannelError, get_channel
from app.services.pipeline import build_message
from app.schemas import (
    ChannelOut,
    DestinationOut,
    DestinationPatch,
    LinkCodeIn,
    LinkCodeOut,
    SendItemsIn,
)
from app.security import hash_token, new_token

router = APIRouter(tags=["destinations"])

LINK_CODE_TTL = timedelta(minutes=10)

CHANNELS = [
    {
        "id": "TELEGRAM",
        "name": "Telegram",
        "supports_groups": True,
        "supports_images": True,
        "instructions": {
            "PRIVATE": [
                "Toque em “Abrir no Telegram”.",
                "Toque em Iniciar na conversa com o bot.",
                "Pronto: o vínculo é automático.",
            ],
            "GROUP": [
                "Adicione o bot @{bot} ao seu grupo.",
                "Envie no grupo: /link {code}",
                "Você precisa ser administrador do grupo.",
            ],
            "CHANNEL": [
                "Adicione o bot @{bot} como administrador do canal.",
                "Publique no canal: /link {code}",
            ],
        },
    }
]


def _valid_language(value: str | None) -> str | None:
    if value is None:
        return None
    code = value.lower()
    if code not in LANGUAGES:
        raise ApiError(422, "VALIDATION_ERROR", "Language not available")
    return code


def _owned(db: Session, user: User, destination_id: str) -> Destination:
    destination = db.get(Destination, destination_id)
    if destination is None or destination.user_id != user.id:
        raise not_found("Destination")
    return destination


@router.get("/channels", response_model=list[ChannelOut])
def list_channels(_: User = Depends(require_active)) -> list[dict]:
    return CHANNELS


@router.get("/destinations", response_model=list[DestinationOut])
def list_destinations(user: User = Depends(require_active), db: Session = Depends(get_db)) -> list[DestinationOut]:
    rows = db.scalars(select(Destination).where(Destination.user_id == user.id)).all()
    rows = [d for d in rows if not (d.status == "PENDING" and d.code_expires_at and d.code_expires_at < utcnow())]
    rows.sort(key=lambda d: (not d.is_default, d.linked_at is None, d.linked_at or utcnow()))
    return [destination_out(d, user.language) for d in rows]


@router.post("/destinations/link-code", response_model=LinkCodeOut)
def create_link_code(
    body: LinkCodeIn, user: User = Depends(require_account), db: Session = Depends(get_db)
) -> LinkCodeOut:
    if user.email_verified_at is None and body.kind != "PRIVATE":
        raise ApiError(403, "TELEGRAM_NOT_VERIFIED", "Connect your private chat first")
    linked = db.scalar(
        select(func.count()).select_from(Destination).where(
            Destination.user_id == user.id, Destination.linked_at.is_not(None)
        )
    ) or 0
    if linked >= entitlements_for(user.plan).max_destinations:
        raise ApiError(402, "PLAN_LIMIT_REACHED", "Your plan's destination limit has been reached")

    # Só existe um vínculo pendente por vez: o anterior (nunca concluído) é descartado.
    db.execute(delete(Destination).where(Destination.user_id == user.id, Destination.linked_at.is_(None)))

    code = new_token(9)
    expires_at = utcnow() + LINK_CODE_TTL
    destination = Destination(
        user_id=user.id,
        channel=body.channel,
        kind=body.kind,
        language=_valid_language(body.language),
        code_hash=hash_token(code),
        code_expires_at=expires_at,
    )
    db.add(destination)
    db.commit()

    bot = get_settings().telegram_bot_username
    return LinkCodeOut(
        destination_id=destination.id,
        code=code,
        expires_at=expires_at,
        deep_link=f"https://t.me/{bot}?start={code}" if body.kind == "PRIVATE" else None,
        command=None if body.kind == "PRIVATE" else f"/link {code}",
    )


@router.patch("/destinations/{destination_id}", response_model=DestinationOut)
def update_destination(
    destination_id: str,
    body: DestinationPatch,
    user: User = Depends(require_active),
    db: Session = Depends(get_db),
) -> DestinationOut:
    destination = _owned(db, user, destination_id)
    if body.title is not None:
        destination.title = body.title.strip() or None
    if body.language is not None:
        destination.language = _valid_language(body.language)
    if body.is_default:
        for other in db.scalars(select(Destination).where(Destination.user_id == user.id)):
            other.is_default = other.id == destination.id
    db.commit()
    return destination_out(destination, user.language)


@router.delete("/destinations/{destination_id}", status_code=204, response_class=Response)
def delete_destination(
    destination_id: str, user: User = Depends(require_active), db: Session = Depends(get_db)
) -> Response:
    destination = _owned(db, user, destination_id)
    was_default = destination.is_default
    db.delete(destination)
    db.flush()
    if was_default:  # o padrão sumiu: promove outro destino já vinculado, se houver
        heir = db.scalar(
            select(Destination)
            .where(Destination.user_id == user.id, Destination.linked_at.is_not(None))
            .order_by(Destination.linked_at)
        )
        if heir:
            heir.is_default = True
    db.commit()
    return Response(status_code=204)


def _deliver(db: Session, destination: Destination, action) -> None:
    """Executa um envio e traduz as falhas do canal em erros claros para o usuário."""
    if destination.status != "LINKED":
        raise ApiError(409, "VALIDATION_ERROR", "This destination is not linked yet")
    try:
        action(get_channel(destination.channel))
    except ChannelNotConfigured as exc:
        raise ApiError(503, "NOT_CONFIGURED", "Telegram is not configured on this server") from exc
    except PermanentChannelError as exc:
        destination.disconnected_at = utcnow()
        db.commit()
        raise ApiError(502, "UPSTREAM_ERROR", f"Could not send: {exc}. Reconnect the destination.") from exc
    except ChannelError as exc:
        raise ApiError(502, "UPSTREAM_ERROR", f"Could not send right now: {exc}") from exc


@router.post("/destinations/{destination_id}/test", status_code=204, response_class=Response)
def test_destination(destination_id: str, user: User = Depends(require_active), db: Session = Depends(get_db)) -> Response:
    destination = _owned(db, user, destination_id)
    _deliver(db, destination, lambda ch: ch.send_text(destination, tr(destination.language or user.language, "test")))
    return Response(status_code=204)


@router.post("/destinations/{destination_id}/send", status_code=204, response_class=Response)
def send_to_destination(
    destination_id: str,
    body: SendItemsIn,
    user: User = Depends(require_active),
    db: Session = Depends(get_db),
) -> Response:
    """Envia anúncios escolhidos (que o usuário já tem em Resultados) para um destino."""
    destination = _owned(db, user, destination_id)
    rows = db.execute(
        select(Item, Alert)
        .join(Match, Match.item_id == Item.id)
        .join(Alert, Alert.id == Match.alert_id)
        .where(Match.user_id == user.id, Item.id.in_(body.item_ids))
    ).all()
    if not rows:
        raise not_found("Listing")
    first_alert = rows[0][1]
    language = destination.language or user.language
    message = build_message(db, first_alert, list({item.id: item for item, _ in rows}.values()), user, language)
    message.alert_name = tr(language, "selected")
    _deliver(db, destination, lambda ch: ch.send(destination, message))
    db.commit()  # guarda as traduções de título
    return Response(status_code=204)
