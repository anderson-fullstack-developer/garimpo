"""Busca contínua ("Buscar"): roda em segundo plano até o usuário mandar parar.

O clique só dá a partida; a busca repete ciclos na thread do servidor e continua mesmo que o usuário
troque de página ou feche a aba. O front consulta o estado (`status`) e mostra o resultado quando voltar.
O que ela acha aparece em Resultados (não vai ao Telegram: quem avisa é o monitor automático).
"""

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.orm import sessionmaker

from app.access import has_access
from app.config import get_settings
from app.models import User, utcnow
from app.services.monitor import run_user_search

log = logging.getLogger("garimpo.search")

BACKOFF_START = 60.0  # 429 da Vinted: espera 1 min, dobrando até 15 min
BACKOFF_MAX = 900.0


@dataclass
class SearchJob:
    state: str = "idle"  # idle | running | stopping | done | error
    analyzed: int = 0  # anúncios analisados no último ciclo
    new_items: int = 0  # novos desde que o usuário clicou em buscar (soma dos ciclos)
    cycles: int = 0
    error_code: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    last_cycle_at: datetime | None = None
    exiting: bool = False  # a thread já decidiu sair: não dá mais para retomar
    stop: threading.Event = field(default_factory=threading.Event, repr=False, compare=False)


_lock = threading.Lock()
_jobs: dict[str, SearchJob] = {}


def _snapshot(job: SearchJob) -> SearchJob:
    return SearchJob(**{k: v for k, v in vars(job).items() if k != "stop"}, stop=job.stop)


def status(user_id: str) -> SearchJob:
    with _lock:
        job = _jobs.get(user_id)
        return _snapshot(job) if job else SearchJob()


def reset_all() -> None:
    with _lock:
        for job in _jobs.values():
            job.stop.set()
        _jobs.clear()


def start(user: User, bind) -> tuple[SearchJob, bool]:
    """Inicia a busca do usuário. Devolve (estado, iniciou_agora). Se já há uma rodando, não abre outra."""
    with _lock:
        current = _jobs.get(user.id)
        if current and current.state == "stopping" and not current.exiting:
            current.stop.clear()  # clicou de novo antes de parar de fato: retoma a mesma busca
            current.state = "running"
            return _snapshot(current), True
        if current and current.state in ("running", "stopping") and not current.exiting:
            return _snapshot(current), False
        job = SearchJob(state="running", started_at=utcnow())
        _jobs[user.id] = job
        snapshot = _snapshot(job)
    factory = sessionmaker(bind=bind, autoflush=False, expire_on_commit=False)
    threading.Thread(target=_work, args=(user.id, job, factory), name="garimpo-search", daemon=True).start()
    return snapshot, True


def stop(user_id: str) -> SearchJob:
    """Pede para parar. A busca termina o ciclo em andamento e para (estado "stopping" até lá)."""
    with _lock:
        job = _jobs.get(user_id)
        if job is None:
            return SearchJob()
        if job.state == "running":
            job.state = "stopping"
            job.stop.set()
        return _snapshot(job)


def _finish(job: SearchJob, code: str | None = None, message: str | None = None) -> None:
    with _lock:
        if code:
            job.error_code, job.error_message = code, message
        job.state = "error" if job.error_code else "done"  # erro que ficou do último ciclo continua visível
        job.finished_at = utcnow()


def _work(user_id: str, job: SearchJob, factory: sessionmaker) -> None:
    settings = get_settings()
    deadline = settings.manual_search_max_seconds
    started = utcnow()
    backoff = 0.0
    while True:
        with _lock:
            if job.stop.is_set():
                job.exiting = True
                break
        wait = settings.manual_search_pause_seconds
        try:
            with factory() as db:
                user = db.get(User, user_id)
                if user is None:
                    return _finish(job, "NOT_FOUND", "Account not found")
                if not has_access(user):
                    return _finish(job, "SUBSCRIPTION_REQUIRED", "Your free trial has ended. Subscribe to keep searching")
                summary = run_user_search(db, user)
            with _lock:
                job.cycles += 1
                job.last_cycle_at = utcnow()
                if summary.rate_limited:
                    backoff = min(BACKOFF_MAX, backoff * 2 if backoff else BACKOFF_START)
                    wait = backoff
                    job.error_code = "RATE_LIMITED"
                    job.error_message = "Vinted asked us to slow down. We keep trying on our own."
                elif summary.errors and not summary.outcomes:
                    job.error_code = "UPSTREAM_ERROR"
                    job.error_message = f"Could not search Vinted right now: {summary.errors[0]}"
                else:
                    backoff = 0.0
                    job.error_code = job.error_message = None
                    job.analyzed = summary.analyzed
                    job.new_items += summary.new_matches
        except Exception:  # a thread nunca morre calada: registra e tenta no próximo ciclo
            log.exception("Ciclo da busca contínua falhou")
            with _lock:
                job.error_code = "UPSTREAM_ERROR"
                job.error_message = "Could not complete this search. Trying again."
                job.cycles += 1
            wait = max(wait, 15.0)
        if (utcnow() - started).total_seconds() > deadline:
            with _lock:
                job.exiting = True
            break  # trava de segurança: ninguém fica buscando para sempre sem querer
        job.stop.wait(wait)
    _finish(job)
