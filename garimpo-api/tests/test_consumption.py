"""Trabalho que não precisa ser feito (banco, Vinted, tradução): cada caso aqui é dinheiro no Railway/Neon."""

from datetime import timedelta
from types import SimpleNamespace

from sqlalchemy import select

from app.models import MonitorRun, utcnow
from app.services import pipeline, translate
from app.services.channels import TransientChannelError
from app.services.maintenance import prune
from app.services.monitor import TickResult
from tests.conftest import ALERT, T, make_raw
from tests.test_monitor import IPHONE, setup_user


# ------------------------------------------------------------------ monitor dorme até a próxima busca devida
def test_monitor_sleeps_until_the_next_user_is_due(client, signup, link_destination, fake_source, fake_channel, engine_, settings, monkeypatch):
    monkeypatch.setattr(settings, "monitor_tick_seconds", 5)
    setup_user(client, signup, link_destination)  # PRO: 15 s
    result = engine_.tick(T(0))
    assert result.users == 1 and result.next_due_at == T(0) + timedelta(seconds=15)
    # antes: conferia o banco de 5 em 5 s sem nada para fazer; agora dorme o que falta para a próxima busca
    assert engine_.next_wait(result, now=T(0) + timedelta(seconds=2)) == 13
    assert engine_.next_wait(result, now=T(0) + timedelta(seconds=30)) == 1  # atrasado: volta logo

    early = engine_.tick(T(0) + timedelta(seconds=4))  # ninguém na hora: o banco é lido, mas não busca
    assert early.users == 0 and early.next_due_at == T(0) + timedelta(seconds=15)


def test_monitor_wait_has_limits(engine_, settings, monkeypatch):
    monkeypatch.setattr(settings, "monitor_idle_seconds", 240)
    monkeypatch.setattr(settings, "monitor_tick_seconds", 5)
    far = TickResult(enabled=1, next_due_at=T(0) + timedelta(hours=2))  # intervalo longo escolhido pelo usuário
    assert engine_.next_wait(far, now=T(0)) == 240  # ainda confere de vez em quando (ex.: mudou de plano)
    backoff = TickResult(enabled=1, skipped="backoff", next_due_at=T(0) + timedelta(hours=2))
    assert engine_.next_wait(backoff, now=T(0)) == 5


def test_changing_the_interval_wakes_the_monitor(client, signup, monkeypatch):
    signup(client)
    woke = []
    monkeypatch.setattr("app.routers.monitor.monitor_engine", SimpleNamespace(wake=lambda: woke.append(1)))
    assert client.patch("/settings", json={"intervalMinutes": 2}).status_code == 200
    assert woke == [1]  # recalcula quando dormir com o novo intervalo


# ------------------------------------------------------------------ pendências só quando pode haver alguma
def test_pending_notifications_are_only_checked_when_something_may_be_pending(client, signup, link_destination, fake_source, fake_channel, engine_, monkeypatch):
    setup_user(client, signup, link_destination)
    fake_source.put("iphone 12", [make_raw(1, "iPhone 12", 80)])
    checks = []
    original = pipeline._pending_items
    monkeypatch.setattr(pipeline, "_pending_items", lambda db, alert: checks.append(1) or original(db, alert))

    engine_.tick(T(0))  # 1ª vez do alerta desde que o servidor ligou: confere
    assert len(checks) == 1
    engine_.tick(T(6))  # nada novo: não gasta consulta
    assert len(checks) == 1

    fake_source.put("iphone 12", [make_raw(2, "iPhone 12 novo", 70), make_raw(1, "iPhone 12", 80)])
    fake_channel.error = TransientChannelError("Telegram pediu para esperar")
    engine_.tick(T(12))  # novo anúncio, mas o envio falhou por motivo passageiro
    assert len(checks) == 2 and fake_channel.sent == []
    fake_channel.error = None
    engine_.tick(T(18))  # sem anúncio novo, mas há o envio que falhou: confere e entrega
    assert len(checks) == 3 and [[i.title for i in m.items] for _, m in fake_channel.sent] == [["iPhone 12 novo"]]
    engine_.tick(T(24))
    assert len(checks) == 3


# ------------------------------------------------------------------ status do monitor: só o que é do usuário
def test_monitor_status_shows_only_the_users_own_searches(client, signup, link_destination, fake_source, fake_channel, engine_, make_client):
    setup_user(client, signup, link_destination)
    other = make_client()
    setup_user(other, signup, link_destination, email="bia@example.com", alert={**IPHONE, "query": "ps5"}, chat="-1002")
    fake_source.put("iphone 12", [make_raw(1, "iPhone 12", 80)])
    fake_source.put("ps5", [make_raw(2, "PS5", 300)])
    engine_.tick(T(0))
    mine = client.get("/monitor/status").json()["runs"]
    theirs = other.get("/monitor/status").json()["runs"]
    assert len(mine) == 1 and len(theirs) == 1  # antes cada um via as buscas (e os termos) de todo mundo
    assert mine[0]["analyzed"] == 1 and theirs[0]["analyzed"] == 1


def test_monitor_status_without_alerts_has_no_runs(client, signup):
    signup(client)
    assert client.get("/monitor/status").json()["runs"] == []


# ------------------------------------------------------------------ histórico de execuções mais curto
def test_monitor_history_is_kept_for_two_days(session_factory):
    with session_factory() as db:
        db.add_all([
            MonitorRun(search_key="3 dias", started_at=utcnow() - timedelta(days=3)),
            MonitorRun(search_key="ontem", started_at=utcnow() - timedelta(days=1)),
        ])  # fmt: skip
        db.commit()
    with session_factory() as db:
        assert prune(db)["monitor_runs"] == 1
        assert [r.search_key for r in db.scalars(select(MonitorRun))] == ["ontem"]  # o painel usa as últimas 24 h


# ------------------------------------------------------------------ tradução
class FakeHttp:
    def __init__(self, reply=lambda text: f"PT {text}"):
        self.calls, self.reply = [], reply

    def get(self, url, params=None, timeout=None):
        self.calls.append(params["q"])
        text = self.reply(params["q"])
        return SimpleNamespace(json=lambda: {"responseStatus": 200, "responseData": {"translatedText": text}})


def _translation_on(settings, monkeypatch, http):
    monkeypatch.setattr(settings, "translate_enabled", True)
    monkeypatch.setattr(translate, "httpx", SimpleNamespace(get=http.get, HTTPError=Exception))
    monkeypatch.setattr(translate, "_cache", {})
    monkeypatch.setattr(translate, "_paused_until", 0.0)


def test_translation_stops_asking_for_an_hour_when_the_daily_quota_ends(settings, monkeypatch):
    http = FakeHttp(lambda text: "MYMEMORY WARNING: YOU USED ALL AVAILABLE FREE TRANSLATIONS FOR TODAY")
    _translation_on(settings, monkeypatch, http)
    assert translate.translate_titles(["Kurtka", "Buty"], "pt") == ["Kurtka", "Buty"]  # o aviso nunca vira título
    asked = len(http.calls)
    assert translate.translate_titles(["Spodnie", "Czapka"], "pt") == ["Spodnie", "Czapka"]
    assert len(http.calls) == asked  # pausada: nem tenta
    assert translate._cache == {}  # e não guarda o original: quando a cota voltar, ainda dá para traduzir


def test_translation_threads_are_reused(settings, monkeypatch):
    _translation_on(settings, monkeypatch, FakeHttp())
    assert translate.translate_titles(["Kurtka"], "pt") == ["PT Kurtka"]
    pool = translate._executor()
    translate.translate_titles(["Buty"], "pt")
    assert translate._executor() is pool  # antes: 6 threads novas a cada aviso

