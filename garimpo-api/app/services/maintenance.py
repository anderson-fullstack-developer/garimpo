"""Limpeza periódica: o banco (e a conta da Neon) não podem crescer para sempre."""

import logging
from datetime import datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Destination, EmailToken, Invite, Item, MonitorRun, RefreshToken, utcnow

log = logging.getLogger("garimpo.maintenance")

RUNS_KEEP = timedelta(days=7)  # histórico de execuções do monitor
TOKENS_KEEP = timedelta(days=7)  # tokens de e-mail vencidos
REVOKED_SESSIONS_KEEP = timedelta(days=30)  # sessões revogadas (a detecção de reuso precisa delas por um tempo)
PENDING_LINK_KEEP = timedelta(hours=1)  # códigos de vínculo do Telegram que ninguém usou


def prune(db: Session, now: datetime | None = None) -> dict[str, int]:
    """Apaga o que já não serve. Devolve quantas linhas saíram de cada tabela."""
    now = now or utcnow()
    retention = timedelta(days=get_settings().retention_days)
    steps = {
        "monitor_runs": delete(MonitorRun).where(MonitorRun.started_at < now - RUNS_KEEP),
        "email_tokens": delete(EmailToken).where(EmailToken.expires_at < now - TOKENS_KEEP),
        "refresh_tokens": delete(RefreshToken).where(
            (RefreshToken.expires_at < now - TOKENS_KEEP) | (RefreshToken.revoked_at < now - REVOKED_SESSIONS_KEEP)
        ),
        "destinations_pending": delete(Destination).where(
            Destination.linked_at.is_(None), Destination.code_expires_at < now - PENDING_LINK_KEEP
        ),
        "invites": delete(Invite).where(Invite.expires_at < now - REVOKED_SESSIONS_KEEP),
        # Anúncios: as tabelas ligadas (casamentos, avisos, histórico de preço) saem junto, em cascata.
        "items": delete(Item).where(Item.last_seen_at < now - retention),
    }
    counts = {name: db.execute(stmt).rowcount or 0 for name, stmt in steps.items()}
    db.commit()
    removed = {k: v for k, v in counts.items() if v}
    if removed:
        log.info("Limpeza do banco: %s", removed)
    return counts
