"""O banco não pode crescer para sempre nem ficar acordado à toa."""

import threading
import time
from datetime import timedelta

from sqlalchemy import select

from app.models import (
    Alert,
    Destination,
    EmailToken,
    Invite,
    Item,
    Match,
    MonitorRun,
    Notification,
    PriceSnapshot,
    RefreshToken,
    User,
    utcnow,
)
from app.services.maintenance import prune
from app.services.monitor import MonitorEngine, TickResult
from app.services.pipeline import store_items
from tests.conftest import ALERT, T, make_raw


def days(n: float):
    return utcnow() - timedelta(days=n)


def test_prune_removes_only_what_is_old(client, signup, session_factory):
    signup(client)
    alert_id = client.post("/alerts", json=ALERT).json()["id"]
    with session_factory() as db:
        user = db.scalar(select(User))
        uid = user.id

        db.add_all([MonitorRun(search_key="antiga", started_at=days(8)), MonitorRun(search_key="recente", started_at=days(1))])
        db.add_all([
            EmailToken(user_id=uid, kind="RESET_PASSWORD", token_hash="a" * 64, expires_at=days(8)),
            EmailToken(user_id=uid, kind="RESET_PASSWORD", token_hash="b" * 64, expires_at=utcnow() + timedelta(hours=1)),
        ])  # fmt: skip
        db.add_all([
            RefreshToken(user_id=uid, family_id="f1", token_hash="c" * 64, expires_at=days(8)),  # venceu há 8 dias
            RefreshToken(user_id=uid, family_id="f2", token_hash="d" * 64, expires_at=utcnow() + timedelta(days=20), revoked_at=days(31)),
            RefreshToken(user_id=uid, family_id="f3", token_hash="e" * 64, expires_at=utcnow() + timedelta(days=20), revoked_at=days(2)),
        ])  # fmt: skip
        db.add_all([
            Destination(user_id=uid, kind="GROUP", code_hash="x1", code_expires_at=utcnow() - timedelta(hours=2)),  # vínculo esquecido
            Destination(user_id=uid, kind="GROUP", code_hash="x2", code_expires_at=utcnow() + timedelta(minutes=5)),  # ainda válido
            Destination(user_id=uid, kind="GROUP", external_id="-1", linked_at=days(90)),  # vinculado: nunca sai
        ])  # fmt: skip
        db.add_all([Invite(code_hash="i" * 64, expires_at=days(40)), Invite(code_hash="j" * 64, expires_at=days(1))])

        old = Item(vinted_id=1, title="velho", price=10, seller_login="#1", url="u", last_seen_at=days(31))
        fresh = Item(vinted_id=2, title="novo", price=10, seller_login="#2", url="u", last_seen_at=days(1))
        db.add_all([old, fresh])
        db.flush()
        for item in (old, fresh):
            db.add_all([Match(user_id=uid, alert_id=alert_id, item_id=item.id), Notification(user_id=uid, item_id=item.id), PriceSnapshot(item_id=item.id, price=10)])
        db.commit()

    with session_factory() as db:
        counts = prune(db)
    assert counts == {
        "monitor_runs": 1, "email_tokens": 1, "refresh_tokens": 2, "destinations_pending": 1, "invites": 1, "items": 1,
    }  # fmt: skip

    with session_factory() as db:
        assert [r.search_key for r in db.scalars(select(MonitorRun))] == ["recente"]
        hashes = {e.token_hash for e in db.scalars(select(EmailToken))}  # (o cadastro também criou um token)
        assert "b" * 64 in hashes and "a" * 64 not in hashes
        assert {t.family_id for t in db.scalars(select(RefreshToken)) if t.family_id in ("f1", "f2", "f3")} == {"f3"}
        assert {d.code_hash for d in db.scalars(select(Destination)) if d.code_hash} == {"x2"}
        assert len(db.scalars(select(Destination)).all()) == 2  # o vinculado e o pendente válido
        assert [i.code_hash for i in db.scalars(select(Invite))] == ["j" * 64]
        # o anúncio antigo levou junto casamento, aviso e histórico de preço (cascata); o novo ficou inteiro
        assert [i.title for i in db.scalars(select(Item))] == ["novo"]
        assert len(db.scalars(select(Match)).all()) == 1 and len(db.scalars(select(Notification)).all()) == 1
        assert len(db.scalars(select(PriceSnapshot)).all()) == 1


def test_prune_is_a_noop_on_a_clean_database(session_factory):
    with session_factory() as db:
        assert set(prune(db).values()) == {0}


def test_retention_days_is_configurable(client, signup, session_factory, settings, monkeypatch):
    monkeypatch.setattr(settings, "retention_days", 3)
    signup(client)
    with session_factory() as db:
        db.add_all([Item(vinted_id=1, title="a", price=1, seller_login="#1", url="u", last_seen_at=days(4)),
                    Item(vinted_id=2, title="b", price=1, seller_login="#2", url="u", last_seen_at=days(2))])  # fmt: skip
        db.commit()
        assert prune(db)["items"] == 1


# ------------------------------------------------------------------ menos escrita
def test_last_seen_is_refreshed_at_most_hourly(session_factory):
    with session_factory() as db:
        store_items(db, [make_raw(1, "iPhone 12", 80)])
        db.commit()
        item = db.scalar(select(Item))
        recent = utcnow() - timedelta(minutes=10)
        item.last_seen_at = recent
        db.commit()

        store_items(db, [make_raw(1, "iPhone 12", 80)])  # visto de novo 10 min depois: nada a gravar
        db.commit()
        assert db.scalar(select(Item)).last_seen_at == recent

        item.last_seen_at = utcnow() - timedelta(hours=2)
        db.commit()
        store_items(db, [make_raw(1, "iPhone 12", 80)])  # passou de 1 h: renova
        db.commit()
        assert utcnow() - db.scalar(select(Item)).last_seen_at < timedelta(minutes=1)


def test_price_history_is_recorded_only_when_price_changes(session_factory):
    with session_factory() as db:
        store_items(db, [make_raw(1, "iPhone 12", 80)])
        store_items(db, [make_raw(1, "iPhone 12", 80)])
        store_items(db, [make_raw(1, "iPhone 12", 70)])
        db.commit()
        assert sorted(float(s.price) for s in db.scalars(select(PriceSnapshot))) == [70.0, 80.0]


# ------------------------------------------------------------------ deixar a Neon dormir
def test_enabled_users_are_counted_even_when_not_due(client, signup, fake_source, engine_):
    signup(client)
    client.patch("/settings", json={"intervalMinutes": 5})
    client.post("/alerts", json=ALERT)
    assert engine_.tick(T(0)).enabled == 0  # ninguém monitorando
    client.post("/monitor/start")
    assert engine_.tick(T(0)).enabled == 1
    result = engine_.tick(T(1))  # ainda não venceu o intervalo, mas o usuário continua "ligado"
    assert result.users == 0 and result.enabled == 1


def test_idle_server_waits_longer_and_busy_one_does_not(engine_, settings, monkeypatch):
    monkeypatch.setattr(settings, "monitor_idle_seconds", 240)
    monkeypatch.setattr(settings, "monitor_tick_seconds", 20)
    assert engine_.next_wait(TickResult(enabled=0)) == 240
    assert engine_.next_wait(TickResult(enabled=3)) == 20
    assert engine_.next_wait(TickResult(enabled=0, skipped="backoff")) == 20  # em pausa por 429: volta a checar


def test_prune_runs_at_most_every_six_hours(engine_):
    now = utcnow()
    assert engine_.maybe_prune(now) is not None
    assert engine_.maybe_prune(now + timedelta(hours=5)) is None
    assert engine_.maybe_prune(now + timedelta(hours=6, minutes=1)) is not None


def test_turning_the_monitor_on_wakes_the_sleeping_loop(client, signup, session_factory, settings, monkeypatch):
    """Sem isso, com o servidor "dormindo" (espera longa), ligar o monitor demoraria minutos."""
    monkeypatch.setattr(settings, "monitor_idle_seconds", 30)
    monkeypatch.setattr(settings, "monitor_tick_seconds", 30)
    from app.services import monitor as monitor_module

    engine = MonitorEngine(session_factory=session_factory)
    monkeypatch.setattr(monitor_module, "engine", engine)
    monkeypatch.setattr("app.routers.monitor.monitor_engine", engine)
    ticks = []
    original = engine.tick
    engine.tick = lambda *a, **k: (ticks.append(time.monotonic()), original(*a, **k))[1]

    engine.start()
    try:
        deadline = time.time() + 5
        while not ticks and time.time() < deadline:
            time.sleep(0.02)
        assert len(ticks) == 1  # 1º ciclo ao iniciar; agora dorme ~30 s
        time.sleep(0.3)
        assert len(ticks) == 1

        signup(client)
        client.post("/monitor/start")  # acorda
        deadline = time.time() + 5
        while len(ticks) < 2 and time.time() < deadline:
            time.sleep(0.02)
        assert len(ticks) == 2, "ligar o monitor deveria acordar o ciclo na hora"
    finally:
        started = time.monotonic()
        engine.stop()
        assert time.monotonic() - started < 3  # parar não espera o sono acabar
    assert not any(t.name == "garimpo-monitor" and t.is_alive() for t in threading.enumerate())
