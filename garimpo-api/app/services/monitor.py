"""Monitor em segundo plano + busca manual + prévia."""

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access import has_access
from app.config import get_settings
from app.db import SessionLocal
from app.models import Alert, User, UserSettings, utcnow
from app.services.filters import Rules, dedupe, evaluate
from app.services.maintenance import prune
from app.services.pipeline import RunSummary, SearchKey, due_interval, fetch_keys, keys_for, notify_outcomes, run_alerts
from app.services.vinted import ItemSource, RawItem, get_source

log = logging.getLogger("garimpo.monitor")

MAX_BACKOFF_SECONDS = 15 * 60
PRUNE_EVERY = timedelta(hours=6)


@dataclass
class TickResult:
    users: int = 0
    enabled: int = 0  # usuários com o monitor ligado (devidos ou não)
    analyzed: int = 0
    new_matches: int = 0
    sent: int = 0
    errors: list[str] = field(default_factory=list)
    skipped: str | None = None


class MonitorEngine:
    def __init__(self, session_factory: Callable[[], Session] = SessionLocal) -> None:
        self._session_factory = session_factory
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._wake = threading.Event()
        self._last_prune: datetime | None = None
        self.backoff_until: datetime | None = None
        self.backoff_seconds = 0

    # ------------------------------------------------------------ um ciclo
    def _due(self, db: Session, now: datetime) -> tuple[list[tuple[User, UserSettings]], int]:
        rows = db.execute(
            select(User, UserSettings)
            .join(UserSettings, UserSettings.user_id == User.id)
            .where(UserSettings.monitor_enabled.is_(True), User.status == "ACTIVE")
        ).all()
        verify = get_settings().require_verification
        due, enabled = [], 0
        for user, settings in rows:
            if verify and user.email_verified_at is None:
                continue
            if not has_access(user, now):
                continue  # teste acabou e não há assinatura: não busca nem avisa
            enabled += 1
            if settings.last_run_at is None or now >= settings.last_run_at + due_interval(user, settings.interval_minutes):
                due.append((user, settings))
        return due, enabled

    def _register_backoff(self, now: datetime) -> None:
        self.backoff_seconds = min(max(60, self.backoff_seconds * 2), MAX_BACKOFF_SECONDS)
        self.backoff_until = now + timedelta(seconds=self.backoff_seconds)
        log.warning("Vinted limitou o ritmo; pausando buscas por %ss", self.backoff_seconds)

    def tick(self, now: datetime | None = None, source: ItemSource | None = None) -> TickResult:
        now = now or utcnow()
        result = TickResult()
        with self._lock:
            if self.backoff_until and now < self.backoff_until:
                result.skipped = "backoff"
                return result
            with self._session_factory() as db:
                try:
                    due, result.enabled = self._due(db, now)
                    result.users = len(due)
                    if not due:
                        return result
                    alerts = list(
                        db.scalars(
                            select(Alert).where(Alert.user_id.in_([u.id for u, _ in due]), Alert.active.is_(True))
                        )
                    )
                    summary = RunSummary()
                    if alerts:
                        summary = run_alerts(db, source or get_source(), alerts)
                        sent, notify_errors = notify_outcomes(db, summary.outcomes)
                        result.sent = sent
                        result.errors = summary.errors + notify_errors
                    result.analyzed, result.new_matches = summary.analyzed, summary.new_matches

                    if summary.rate_limited:
                        self._register_backoff(now)
                    else:
                        self.backoff_seconds = 0
                        self.backoff_until = None
                        for _, settings in due:
                            settings.last_run_at = now
                            settings.last_error = "; ".join(dict.fromkeys(result.errors))[:500] or None
                    db.commit()
                except Exception:
                    db.rollback()
                    log.exception("Falha no ciclo do monitor")
                    result.errors.append("erro interno no monitor")
        return result

    # ------------------------------------------------------------ thread de fundo
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="garimpo-monitor", daemon=True)
        self._thread.start()
        log.info("Monitor iniciado")

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread:
            self._thread.join(timeout=5)

    def wake(self) -> None:
        """Acorda o servidor agora (ex.: alguém ligou o monitor) em vez de esperar o próximo intervalo."""
        self._wake.set()

    def next_wait(self, result: TickResult) -> float:
        """Quanto esperar até o próximo ciclo. Sem ninguém monitorando, espera bem mais: assim o banco
        (Neon) não fica acordado à toa. Ligar o monitor chama `wake()` e o ciclo roda na hora."""
        settings = get_settings()
        if result.enabled == 0 and result.skipped is None:
            return float(settings.monitor_idle_seconds)
        return float(settings.monitor_tick_seconds)

    def maybe_prune(self, now: datetime | None = None) -> dict[str, int] | None:
        now = now or utcnow()
        if self._last_prune is not None and now - self._last_prune < PRUNE_EVERY:
            return None
        self._last_prune = now
        with self._session_factory() as db:
            try:
                return prune(db, now)
            except Exception:
                db.rollback()
                log.exception("Falha na limpeza do banco")
                return None

    def _loop(self) -> None:
        while not self._stop.is_set():
            wait = float(get_settings().monitor_tick_seconds)
            try:
                wait = self.next_wait(self.tick())
                self.maybe_prune()
            except Exception:
                log.exception("Monitor: erro inesperado")
            if self._wake.wait(timeout=wait):
                self._wake.clear()


engine = MonitorEngine()


# ---------------------------------------------------------------- busca manual ("Buscar agora")
def run_user_search(db: Session, user: User, source: ItemSource | None = None) -> RunSummary:
    """Busca os alertas ativos do usuário agora. O que achar aparece em Resultados; não vai para o
    Telegram (o usuário já está vendo na tela), então é marcado como visto."""
    alerts = list(db.scalars(select(Alert).where(Alert.user_id == user.id, Alert.active.is_(True))))
    if not alerts:
        return RunSummary()
    summary = run_alerts(db, source or get_source(), alerts, silent_reason="manual")
    db.commit()
    return summary


# ---------------------------------------------------------------- prévia (sem gravar nada)
_PREVIEW_TTL = 60.0
_preview_cache: dict[SearchKey, tuple[float, list[RawItem]]] = {}
_preview_lock = threading.Lock()


def clear_preview_cache() -> None:
    _preview_cache.clear()


def preview_alert(draft: object, source: ItemSource | None = None) -> tuple[list[tuple[RawItem, list[str]]], int]:
    """Avalia o alerta (rascunho) contra a 1ª página de resultados. Devolve ([(anúncio, motivos)], analisados).

    Para "Europa" usa só o 1º país, para a prévia ser rápida.
    """
    source = source or get_source()
    key = keys_for(draft)[0]
    key = SearchKey(key.domain, key.query, 1, key.params_json)
    with _preview_lock:
        cached = _preview_cache.get(key)
        if cached and time.monotonic() - cached[0] < _PREVIEW_TTL:
            items = cached[1]
        else:
            results, _ = fetch_keys(source, [key])
            res = results[key]
            if res.status != "ok":
                from app.services.vinted import VintedError

                raise VintedError(res.error or "Falha ao buscar")
            items = res.items
            _preview_cache[key] = (time.monotonic(), items)
    rules = Rules.from_alert(draft)
    now = datetime.now(timezone.utc)
    rows = [(item, evaluate(rules, item, now)) for item in items]
    matched_ids = {id(i) for i in dedupe([i for i, r in rows if not r])}
    rows = [(i, r) for i, r in rows if r or id(i) in matched_ids]  # repetidos nem aparecem
    return rows, len({i.vinted_id for i in items})
