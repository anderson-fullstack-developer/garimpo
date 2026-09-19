"""Processa as atualizações que o Telegram envia ao webhook: vínculo de destinos e comandos do bot."""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access import start_trial
from app.models import Alert, Destination, User, UserSettings, utcnow
from app.security import hash_token
from app.services.channels import ChannelError
from app.services.messages import tr
from app.services.telegram import CODE_RE, PLAIN_CODE_RE, TelegramClient

log = logging.getLogger("garimpo.telegram")

_KIND_BY_CHAT = {"private": "PRIVATE", "group": "GROUP", "supergroup": "GROUP", "channel": "CHANNEL"}
_ADMIN_STATUS = {"creator", "administrator"}


def _reply(client: TelegramClient, chat_id: int | str, text: str) -> None:
    try:
        client.send_message(chat_id, text)
    except ChannelError as exc:  # responder é um extra: nunca derruba o webhook
        log.info("Não consegui responder no chat %s: %s", chat_id, exc)


def _user_language(db: Session, user_id: str) -> str:
    user = db.get(User, user_id)
    return user.language if user else "pt"


def _dest_language(db: Session, dest: Destination) -> str:
    return dest.language or _user_language(db, dest.user_id)


def _sender_language(sender: dict | None) -> str:
    """Sem conta vinculada, o idioma do próprio Telegram de quem escreveu (pt*, senão inglês)."""
    return (sender or {}).get("language_code") or "pt"


def _chat_title(chat: dict) -> str | None:
    return chat.get("title") or chat.get("first_name") or chat.get("username")


def _link(db: Session, client: TelegramClient, chat: dict, sender: dict | None, code: str) -> str:
    kind = _KIND_BY_CHAT.get(chat.get("type", ""))
    chat_id = str(chat["id"])
    if kind is None:
        return "ignored"

    pending = db.scalar(
        select(Destination).where(
            Destination.code_hash == hash_token(code),
            Destination.linked_at.is_(None),
            Destination.code_expires_at > utcnow(),
        )
    )
    if pending is None:
        _reply(client, chat_id, tr(_sender_language(sender), "invalid_code"))
        return "invalid_code"
    if pending.kind != kind:
        lang = (pending.language or _user_language(db, pending.user_id))
        kind_name = tr(lang, f"kind_{pending.kind}") if pending.kind in _KIND_BY_CHAT.values() else tr(lang, "kind_other")
        _reply(client, chat_id, tr(lang, "kind_mismatch", kind=kind_name))
        return "kind_mismatch"

    # Em grupo, só quem administra pode vincular (senão qualquer membro sequestraria o grupo).
    if kind == "GROUP":
        try:
            status = client.get_chat_member_status(chat["id"], (sender or {}).get("id", 0))
        except ChannelError:
            status = ""
        if status not in _ADMIN_STATUS:
            _reply(client, chat_id, tr((pending.language or _user_language(db, pending.user_id)), "not_admin"))
            return "not_admin"

    taken = db.scalar(
        select(Destination).where(
            Destination.channel == "TELEGRAM",
            Destination.external_id == chat_id,
            Destination.linked_at.is_not(None),
            Destination.id != pending.id,
        )
    )
    if taken is not None:
        if taken.user_id == pending.user_id:
            db.delete(pending)
            db.commit()
            _reply(client, chat_id, tr((pending.language or _user_language(db, pending.user_id)), "already_yours"))
            return "already_linked"
        _reply(client, chat_id, tr((pending.language or _user_language(db, pending.user_id)), "already_other"))
        return "taken"

    has_default = db.scalar(
        select(Destination.id).where(Destination.user_id == pending.user_id, Destination.is_default.is_(True))
    )
    pending.external_id = chat_id
    pending.title = (_chat_title(chat) or "Telegram")[:120]
    pending.linked_at = utcnow()
    pending.disconnected_at = None
    pending.code_hash = None
    pending.code_expires_at = None
    pending.is_default = has_default is None
    owner = db.get(User, pending.user_id)
    if owner is not None and owner.email_verified_at is None and kind == "PRIVATE":
        owner.email_verified_at = utcnow()  # dono do chat privado = conta verificada (sem e-mail)
        start_trial(owner)  # os 7 dias grátis começam agora
    db.commit()
    _reply(client, chat_id, tr((pending.language or _user_language(db, pending.user_id)), "linked"))
    return "linked"


def _on_member_change(db: Session, update: dict) -> str:
    change = update["my_chat_member"]
    chat_id = str(change["chat"]["id"])
    status = (change.get("new_chat_member") or {}).get("status", "")
    destinations = db.scalars(
        select(Destination).where(Destination.channel == "TELEGRAM", Destination.external_id == chat_id)
    ).all()
    if not destinations:
        return "ignored"
    if status in {"left", "kicked"}:
        for dest in destinations:
            dest.disconnected_at = utcnow()  # o usuário verá "Desconectado" e poderá reconectar
        db.commit()
        return "disconnected"
    if status in {"member", "administrator", "creator"}:
        for dest in destinations:
            dest.disconnected_at = None
        db.commit()
        return "reconnected"
    return "ignored"


def _command(db: Session, client: TelegramClient, chat: dict, command: str, sender: dict | None = None) -> str:
    chat_id = str(chat["id"])
    dest = db.scalar(
        select(Destination).where(
            Destination.channel == "TELEGRAM", Destination.external_id == chat_id, Destination.linked_at.is_not(None)
        )
    )
    if command == "/start":
        _reply(client, chat_id, tr(_sender_language(sender), "help"))
        return "help"
    if dest is None:
        _reply(client, chat_id, tr(_sender_language(sender), "unlinked"))
        return "unlinked"

    settings = db.get(UserSettings, dest.user_id)
    lang = _dest_language(db, dest)
    if command == "/stop":
        if settings:
            settings.monitor_enabled = False
            db.commit()
        _reply(client, chat_id, tr(lang, "stopped"))
        return "stopped"

    alerts = db.scalars(select(Alert).where(Alert.user_id == dest.user_id, Alert.active.is_(True))).all()
    state = tr(lang, "on" if settings and settings.monitor_enabled else "off")
    _reply(client, chat_id, tr(lang, "status", state=state, n=len(alerts)))
    return "status"


def handle_update(db: Session, update: dict, client: TelegramClient) -> str:
    """Devolve uma etiqueta do que foi feito (útil em logs e testes)."""
    if "my_chat_member" in update:
        return _on_member_change(db, update)

    message = update.get("message") or update.get("channel_post")
    if not message or "chat" not in message:
        return "ignored"
    text = (message.get("text") or "").strip()
    if not text.startswith("/"):
        if message["chat"].get("type") == "private" and PLAIN_CODE_RE.match(text):
            return _link(db, client, message["chat"], message.get("from"), text)
        return "ignored"

    match = CODE_RE.match(text)
    if match:
        command, code = match.group(1), match.group(2)
        # /start só vale no chat privado (é o link "Abrir no Telegram"); /link vale em qualquer lugar.
        if command == "start" and message["chat"].get("type") != "private":
            return "ignored"
        return _link(db, client, message["chat"], message.get("from"), code)

    command = text.split()[0].split("@")[0].lower()
    if command in {"/start", "/stop", "/status"}:
        return _command(db, client, message["chat"], command, message.get("from"))
    return "ignored"
