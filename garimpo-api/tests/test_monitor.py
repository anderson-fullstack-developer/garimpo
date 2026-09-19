"""O ciclo completo: buscar -> filtrar -> baseline -> avisar (sem duplicar)."""

import time
from dataclasses import replace

from sqlalchemy import select

from app.models import Alert, Match, MonitorRun, Notification, UserSettings
from app.services.vinted import BlockedError, RateLimitedError, UpstreamError
from tests.conftest import ALERT, T, make_raw, run_search

IPHONE = {**ALERT, "excludeWords": ["capa"], "maxPrice": None}


def setup_user(client, signup, link_destination, email="ana@example.com", alert=None, chat="-1001"):
    signup(client, email)
    dest = link_destination(email, chat_id=chat)
    created = client.post("/alerts", json=alert or IPHONE).json()
    assert client.post("/monitor/start").status_code == 204
    return created, dest


def sent_titles(channel):
    return [[i.title for i in m.items] for _, m in channel.sent]


def test_first_cycle_is_baseline_then_only_new_items_are_sent(client, signup, link_destination, fake_source, fake_channel, engine_):
    setup_user(client, signup, link_destination)
    fake_source.put("iphone 12", [make_raw(1, "iPhone 12 64GB", 80), make_raw(2, "iPhone 12 128GB", 95)])

    first = engine_.tick(T(0))
    assert (first.users, first.new_matches, first.sent) == (1, 2, 0)  # achou 2, mas não avisa do que já existia
    assert fake_channel.sent == []
    assert client.get("/items").json()["total"] == 2  # e aparecem em Resultados

    fake_source.put("iphone 12", [make_raw(3, "iPhone 12 mini", 70), make_raw(1, "iPhone 12 64GB", 80), make_raw(2, "iPhone 12 128GB", 95)])
    second = engine_.tick(T(6))
    assert (second.new_matches, second.sent) == (1, 1)
    assert sent_titles(fake_channel) == [["iPhone 12 mini"]]
    message = fake_channel.sent[0][1]
    assert message.alert_name == "iphone 12" and message.items[0].price == 70

    third = engine_.tick(T(12))  # nada mudou: não repete
    assert (third.new_matches, third.sent) == (0, 0)
    assert len(fake_channel.sent) == 1


def test_notify_on_first_run_sends_what_already_exists_cheapest_first(client, signup, link_destination, fake_source, fake_channel, engine_):
    setup_user(client, signup, link_destination, alert={**IPHONE, "notifyOnFirstRun": True})
    fake_source.put("iphone 12", [make_raw(1, "iPhone 12 A", 95), make_raw(2, "iPhone 12 B", 60)])
    assert engine_.tick(T(0)).sent == 2
    assert sent_titles(fake_channel) == [["iPhone 12 B", "iPhone 12 A"]]  # uma mensagem, mais barato primeiro


def test_filters_drop_accessories_and_wrong_models(client, signup, link_destination, fake_source, fake_channel, engine_):
    setup_user(client, signup, link_destination, alert={**IPHONE, "excludePresets": ["PHONES"], "notifyOnFirstRun": True})
    fake_source.put(
        "iphone 12",
        [
            make_raw(1, "iPhone 12 64GB", 80),
            make_raw(2, "Capa iPhone 12", 5),
            make_raw(3, "Película de vidro iPhone 12", 4),
            make_raw(4, "iPhone 13", 90),
            make_raw(5, "iPhone 12 Capacidade 128GB", 100),
        ],
    )
    engine_.tick(T(0))
    assert sent_titles(fake_channel) == [["iPhone 12 64GB", "iPhone 12 Capacidade 128GB"]]  # mais barato primeiro
    assert client.get("/items").json()["total"] == 2


def test_price_and_condition_filters(client, signup, link_destination, fake_source, fake_channel, engine_):
    setup_user(
        client, signup, link_destination,
        alert={**IPHONE, "minPrice": 50, "maxPrice": 90, "statusFilter": ["very_good", "good"], "notifyOnFirstRun": True},
    )  # fmt: skip
    fake_source.put(
        "iphone 12",
        [
            make_raw(1, "iPhone 12 ok", 80, condition="good"),
            make_raw(2, "iPhone 12 caro", 200, condition="good"),
            make_raw(3, "iPhone 12 barato demais", 10, condition="good"),
            make_raw(4, "iPhone 12 riscado", 70, condition="satisfactory"),
            make_raw(5, "iPhone 12 idioma estranho", 75, condition=None),  # estado desconhecido não elimina
        ],
    )
    engine_.tick(T(0))
    assert sorted(sent_titles(fake_channel)[0]) == ["iPhone 12 idioma estranho", "iPhone 12 ok"]


def test_two_users_with_the_same_search_cost_one_request(client, signup, link_destination, fake_source, fake_channel, engine_, make_client):
    setup_user(client, signup, link_destination, "ana@example.com", chat="-1001")
    bruno = make_client()
    signup(bruno, "bruno@example.com")
    link_destination("bruno@example.com", chat_id="-2002", title="Grupo do Bruno")
    bruno.post("/alerts", json={**IPHONE, "notifyOnFirstRun": True})
    bruno.post("/monitor/start")
    fake_source.put("iphone 12", [make_raw(1, "iPhone 12 64GB", 80)])

    result = engine_.tick(T(0))
    assert result.users == 2
    assert len(fake_source.calls) == 1  # busca compartilhada (D9)
    # cada um recebe no PRÓPRIO destino; a Ana (baseline) não recebe nada do que já existia
    assert [d.external_id for d, _ in fake_channel.sent] == ["-2002"]
    assert client.get("/items").json()["total"] == 1 and bruno.get("/items").json()["total"] == 1


def test_alert_destination_overrides_default(client, signup, link_destination, fake_source, fake_channel, engine_):
    signup(client)
    default = link_destination("ana@example.com", chat_id="-1", title="Padrão", default=True)
    other = link_destination("ana@example.com", chat_id="-2", title="Outro", default=False)
    client.post("/alerts", json={**IPHONE, "notifyOnFirstRun": True, "destinationId": other})
    client.post("/alerts", json={**IPHONE, "query": "ps5", "notifyOnFirstRun": True})
    client.post("/monitor/start")
    fake_source.put("iphone 12", [make_raw(1, "iPhone 12", 80)])
    fake_source.put("ps5", [make_raw(2, "PS5 Slim", 300)])
    engine_.tick(T(0))
    routed = {m.alert_name: d.external_id for d, m in fake_channel.sent}
    assert routed == {"iphone 12": "-2", "ps5": "-1"} and default != other


def test_without_destination_nothing_is_sent_and_it_is_not_retried(client, signup, fake_source, fake_channel, engine_, session_factory):
    signup(client)
    client.post("/alerts", json={**IPHONE, "notifyOnFirstRun": True})
    client.post("/monitor/start")
    fake_source.put("iphone 12", [make_raw(1, "iPhone 12", 80)])
    engine_.tick(T(0))
    engine_.tick(T(6))
    assert fake_channel.sent == []
    with session_factory() as db:
        notes = db.scalars(select(Notification)).all()
        assert len(notes) == 1 and notes[0].ok is False and "sem destino" in notes[0].error


def test_same_item_in_two_alerts_is_announced_once(client, signup, link_destination, fake_source, fake_channel, engine_):
    signup(client)
    link_destination("ana@example.com")
    client.post("/alerts", json={**IPHONE, "notifyOnFirstRun": True})
    client.post("/alerts", json={**IPHONE, "name": "outro", "notifyOnFirstRun": True})
    client.post("/monitor/start")
    fake_source.put("iphone 12", [make_raw(1, "iPhone 12", 80)])
    engine_.tick(T(0))
    assert sum(len(m.items) for _, m in fake_channel.sent) == 1
    assert len(fake_source.calls) == 1  # os dois alertas compartilham a mesma busca


def test_disabled_not_due_and_suspended_users_are_skipped(client, signup, link_destination, fake_source, fake_channel, engine_, session_factory):
    signup(client)
    client.patch("/settings", json={"intervalMinutes": 5})
    link_destination("ana@example.com")
    client.post("/alerts", json=IPHONE)
    fake_source.put("iphone 12", [make_raw(1, "iPhone 12", 80)])

    assert engine_.tick(T(0)).users == 0  # monitor desligado
    client.post("/monitor/start")
    assert engine_.tick(T(0)).users == 1
    assert engine_.tick(T(2)).users == 0  # intervalo (5 min) ainda não venceu
    assert engine_.tick(T(6)).users == 1

    with session_factory() as db:
        from app.models import User

        db.scalar(select(User)).status = "SUSPENDED"
        db.commit()
    assert engine_.tick(T(30)).users == 0


def test_rate_limit_triggers_backoff_and_recovers(client, signup, link_destination, fake_source, fake_channel, engine_, session_factory):
    setup_user(client, signup, link_destination)
    fake_source.errors["*"] = RateLimitedError("429")
    first = engine_.tick(T(0))
    assert first.errors and engine_.backoff_until is not None
    with session_factory() as db:
        assert db.scalar(select(UserSettings)).last_run_at is None  # não conta como ciclo feito
        assert db.scalar(select(MonitorRun)).status == "rate_limited"

    calls = len(fake_source.calls)
    assert engine_.tick(T(0)).skipped == "backoff" and len(fake_source.calls) == calls  # nem tenta

    fake_source.errors.clear()
    fake_source.put("iphone 12", [make_raw(1, "iPhone 12", 80)])
    recovered = engine_.tick(T(20))
    assert recovered.new_matches == 1 and engine_.backoff_until is None


def test_upstream_errors_are_recorded_without_crashing(client, signup, link_destination, fake_source, fake_channel, engine_, session_factory):
    setup_user(client, signup, link_destination)
    fake_source.errors["*"] = BlockedError("vinted.pt barrou o acesso (403)")
    result = engine_.tick(T(0))
    assert "barrou" in result.errors[0]
    with session_factory() as db:
        assert "barrou" in db.scalar(select(UserSettings)).last_error
    assert client.get("/monitor/status").json()["lastError"].startswith("vinted.pt barrou")


def test_transient_send_failure_is_retried_next_cycle(client, signup, link_destination, fake_source, fake_channel, engine_):
    setup_user(client, signup, link_destination, alert={**IPHONE, "notifyOnFirstRun": True})
    fake_source.put("iphone 12", [make_raw(1, "iPhone 12", 80)])
    from app.services.channels import TransientChannelError

    fake_channel.error = TransientChannelError("429")
    assert engine_.tick(T(0)).sent == 0
    fake_channel.error = None
    assert engine_.tick(T(6)).sent == 1  # o aviso não se perdeu
    assert len(fake_channel.sent) == 1


def test_permanent_send_failure_disconnects_destination(client, signup, link_destination, fake_source, fake_channel, engine_):
    _, dest = setup_user(client, signup, link_destination, alert={**IPHONE, "notifyOnFirstRun": True})
    fake_source.put("iphone 12", [make_raw(1, "iPhone 12", 80)])
    from app.services.channels import PermanentChannelError

    fake_channel.error = PermanentChannelError("bot was kicked from the group chat")
    engine_.tick(T(0))
    listed = client.get("/destinations").json()
    assert [d["status"] for d in listed] == ["DISCONNECTED"]
    assert dest == listed[0]["id"]


def test_europe_alert_waits_for_all_countries_before_baseline(client, signup, link_destination, fake_source, fake_channel, engine_, session_factory):
    setup_user(client, signup, link_destination, alert={**IPHONE, "country": "eu"})
    fake_source.put("iphone 12", [make_raw(1, "iPhone 12", 80)], domain="pt")
    fake_source.errors["fr"] = UpstreamError("fora do ar")

    assert engine_.tick(T(0)).new_matches == 0  # um país falhou: não começa com dados parciais
    with session_factory() as db:
        assert db.scalar(select(Alert)).baselined_at is None and db.scalars(select(Match)).all() == []

    fake_source.errors.clear()
    fake_source.put("iphone 12", [make_raw(2, "iPhone 12 fr", 70, domain="fr")], domain="fr")
    ok = engine_.tick(T(6))
    assert ok.new_matches == 2 and ok.sent == 0  # baseline completo, sem despejar nada
    assert len(fake_source.calls) >= 21  # todos os países consultados


def test_changing_the_filter_resets_results_and_baseline(client, signup, link_destination, fake_source, fake_channel, engine_):
    created, _ = setup_user(client, signup, link_destination)
    fake_source.put("iphone 12", [make_raw(1, "iPhone 12", 80)])
    engine_.tick(T(0))
    assert client.get("/items").json()["total"] == 1

    assert client.patch(f"/alerts/{created['id']}", json={"name": "só o nome"}).status_code == 200
    assert client.get("/items").json()["total"] == 1  # nome não muda o que casa

    client.patch(f"/alerts/{created['id']}", json={"maxPrice": 50})  # muda o critério
    assert client.get("/items").json()["total"] == 0  # resultados antigos saem
    fake_source.put("iphone 12", [make_raw(1, "iPhone 12", 80), make_raw(2, "iPhone 12 barato", 40)])
    result = engine_.tick(T(6))
    assert result.new_matches == 1 and result.sent == 0  # refez o baseline em silêncio


def test_reactivating_a_paused_alert_does_not_flood(client, signup, link_destination, fake_source, fake_channel, engine_):
    created, _ = setup_user(client, signup, link_destination)
    fake_source.put("iphone 12", [make_raw(1, "iPhone 12", 80)])
    engine_.tick(T(0))
    client.patch(f"/alerts/{created['id']}", json={"active": False})
    fake_source.put("iphone 12", [make_raw(1, "iPhone 12", 80), make_raw(2, "iPhone 12 novo", 70)])
    engine_.tick(T(6))
    client.patch(f"/alerts/{created['id']}", json={"active": True})
    engine_.tick(T(12))
    assert fake_channel.sent == []  # o que apareceu durante a pausa não é despejado


def test_monitor_runs_are_recorded(client, signup, link_destination, fake_source, fake_channel, engine_):
    setup_user(client, signup, link_destination)
    fake_source.put("iphone 12", [make_raw(1, "iPhone 12", 80)])
    engine_.tick(T(0))
    runs = client.get("/monitor/status").json()["runs"]
    assert len(runs) == 1 and runs[0]["status"] == "ok" and runs[0]["analyzed"] == 1 and runs[0]["matches"] == 1


# ------------------------------------------------------------------ busca manual e prévia
def test_manual_search_shows_results_but_does_not_message(client, signup, link_destination, fake_source, fake_channel, engine_):
    setup_user(client, signup, link_destination)
    fake_source.put("iphone 12", [make_raw(1, "iPhone 12", 80), make_raw(2, "Capa iPhone 12", 5)])
    r = run_search(client)
    assert r["state"] == "done" and (r["analyzed"], r["newItems"]) == (2, 1)
    assert client.get("/items").json()["total"] == 1
    assert fake_channel.sent == []

    engine_.tick(T(0))  # o monitor não reenvia o que o usuário já viu
    assert fake_channel.sent == []
    fake_source.put("iphone 12", [make_raw(3, "iPhone 12 novo", 60), make_raw(1, "iPhone 12", 80)])
    engine_.tick(T(6))
    assert sent_titles(fake_channel) == [["iPhone 12 novo"]]


def test_manual_search_without_alerts_and_error_mapping(client, signup, fake_source):
    signup(client)
    r = run_search(client)
    assert r["state"] == "done" and (r["analyzed"], r["newItems"]) == (0, 0)
    client.post("/alerts", json=IPHONE)
    fake_source.errors["*"] = RateLimitedError("429")
    r = run_search(client)
    assert r["state"] == "error" and r["error"]["code"] == "RATE_LIMITED"
    fake_source.errors["*"] = BlockedError("barrado")
    r = run_search(client)
    assert r["state"] == "error" and r["error"]["code"] == "UPSTREAM_ERROR"


def test_manual_search_is_rate_limited(client, signup, fake_source):
    signup(client)
    codes = [run_search(client).get("http", 202) for _ in range(8)]
    assert codes[:6] == [202] * 6 and codes[6] == 429


def test_manual_search_keeps_running_without_the_client_and_never_doubles(client, signup, fake_source):
    """Sair da tela não interrompe a busca; clicar de novo enquanto roda não abre uma segunda."""
    import threading

    signup(client)
    client.post("/alerts", json=IPHONE)
    fake_source.put("iphone 12", [make_raw(1, "iPhone 12", 80)])
    gate = threading.Event()
    original = fake_source.fetch

    def slow(*a, **k):
        gate.wait(5)
        return original(*a, **k)

    fake_source.fetch = slow
    assert client.post("/search/run", json={}).status_code == 202
    assert client.get("/search/status").json()["state"] == "running"
    again = client.post("/search/run", json={})  # 2º clique/aba: reaproveita a mesma busca
    assert again.status_code == 202 and again.json()["state"] == "running"
    gate.set()  # (o "cliente" nem precisa estar olhando)
    deadline = time.time() + 10
    while client.get("/search/status").json()["cycles"] < 1 and time.time() < deadline:
        time.sleep(0.02)
    running = client.get("/search/status").json()
    assert running["state"] == "running" and running["newItems"] == 1  # continua rodando: só para se mandarem
    assert client.get("/items").json()["total"] == 1
    assert client.post("/search/stop").status_code == 200
    while client.get("/search/status").json()["state"] in ("running", "stopping") and time.time() < deadline:
        time.sleep(0.02)
    final = client.get("/search/status").json()
    assert final["state"] == "done" and final["finishedAt"]


def test_search_keeps_cycling_until_stopped_and_picks_up_new_listings(client, signup, fake_source, settings, monkeypatch):
    monkeypatch.setattr(settings, "manual_search_pause_seconds", 0.05)
    signup(client)
    client.post("/alerts", json=IPHONE)
    fake_source.put("iphone 12", [make_raw(1, "iPhone 12 velho", 80)])
    assert client.post("/search/run", json={}).status_code == 202
    deadline = time.time() + 10
    while client.get("/search/status").json()["cycles"] < 2 and time.time() < deadline:
        time.sleep(0.02)
    assert client.get("/search/status").json()["state"] == "running"  # nunca "termina" sozinho
    fake_source.put("iphone 12", [make_raw(2, "iPhone 12 chegou agora", 70), make_raw(1, "iPhone 12 velho", 80)])
    while client.get("/search/status").json()["newItems"] < 1 and time.time() < deadline:
        time.sleep(0.02)
    assert client.get("/search/status").json()["newItems"] >= 1  # pegou o novo sem ninguém clicar de novo
    client.post("/search/stop")
    while client.get("/search/status").json()["state"] in ("running", "stopping") and time.time() < deadline:
        time.sleep(0.02)
    assert client.get("/search/status").json()["state"] == "done"


def test_search_status_is_private_to_each_user(client, signup):
    signup(client)
    client.post("/search/run", json={})
    assert client.get("/search/status").json()["state"] in ("running", "done")
    client.post("/auth/logout")
    signup(client, email="outra@exemplo.com")
    assert client.get("/search/status").json()["state"] == "idle"





def test_preview_explains_every_discard_and_saves_nothing(client, signup, fake_source):
    signup(client)
    fake_source.put(
        "iphone 12",
        [
            make_raw(1, "iPhone 12 64GB", 80),
            make_raw(2, "Capa iPhone 12", 5),
            make_raw(3, "iPhone 12 Pro", 300),
            make_raw(4, "Samsung S21", 80),
            replace(make_raw(5, "iPhone 12 64GB", 80), seller_login="#1"),  # repetido (mesmo vendedor/título/preço)
        ],
    )
    r = client.post("/alerts/preview", json={**IPHONE, "excludePresets": ["PHONES"], "maxPrice": 100, "perfectMin": 70, "perfectMax": 85})
    assert r.status_code == 200, r.text
    body = r.json()
    assert [row["item"]["title"] for row in body["matched"]] == ["iPhone 12 64GB"]
    assert body["matched"][0]["item"]["isPerfect"] is True and body["matched"][0]["matched"] is True
    reasons = {row["item"]["title"]: row["reasons"] for row in body["discarded"]}
    assert reasons["Capa iPhone 12"] == ["excluded_by_word:capa"]
    assert reasons["iPhone 12 Pro"] == ["above_max_price"]
    assert reasons["Samsung S21"] == ["query_not_matched"]
    assert body["analyzed"] == 5
    assert client.get("/items").json()["total"] == 0  # nada foi gravado


def test_preview_caches_the_search_and_reports_upstream_errors(client, signup, fake_source):
    signup(client)
    fake_source.put("iphone 12", [make_raw(1, "iPhone 12", 80)])
    client.post("/alerts/preview", json=IPHONE)
    client.post("/alerts/preview", json={**IPHONE, "maxPrice": 50})  # mesma busca, filtro diferente
    assert len(fake_source.calls) == 1
    fake_source.errors["*"] = BlockedError("barrado")
    r = client.post("/alerts/preview", json={**IPHONE, "query": "outra coisa"})
    assert r.status_code == 502 and r.json()["code"] == "UPSTREAM_ERROR"


# ------------------------------------------------------------------ janela da 1ª busca (relógio de ids)
class ClockSource:
    """Fonte com relógio de ids: a busca sem termo devolve o anúncio mais recente do site inteiro."""

    has_id_clock = True

    def __init__(self, inner, newest_id):
        self.inner, self.newest_id = inner, newest_id

    def fetch(self, domain, query, page=1, params=None):
        if query == "":
            return [make_raw(self.newest_id, "qualquer", 1)]
        return self.inner.fetch(domain, query, page, params)


def test_first_search_only_takes_what_was_posted_in_the_last_five_minutes(client, signup, fake_source, monkeypatch):
    from app.services import idclock
    from app.services.monitor import run_user_search

    idclock.clock.reset()
    now_id = 10_050_000_000
    monkeypatch.setattr(
        "app.services.manual_search.run_user_search",
        lambda db, user, source=None: run_user_search(db, user, ClockSource(fake_source, now_id)),
    )
    fresh = now_id - int(idclock.DEFAULT_RATE * 60)  # ~1 min atrás
    stale = now_id - int(idclock.DEFAULT_RATE * 15 * 60)  # ~15 min atrás
    fake_source.put("iphone 12", [make_raw(fresh, "iPhone 12 novo", 80), make_raw(stale, "iPhone 12 velho", 80)])
    signup(client)
    client.post("/alerts", json=IPHONE)
    first = run_search(client)
    assert first["state"] == "done" and first["newItems"] == 1  # só o de ~1 min
    assert [i["title"] for i in client.get("/items").json()["items"]] == ["iPhone 12 novo"]


def test_later_searches_only_add_what_appears_afterwards(client, signup, fake_source, monkeypatch):
    from app.services import idclock
    from app.services.monitor import run_user_search

    idclock.clock.reset()
    now_id = 10_050_000_000
    monkeypatch.setattr(
        "app.services.manual_search.run_user_search",
        lambda db, user, source=None: run_user_search(db, user, ClockSource(fake_source, now_id)),
    )
    stale = now_id - int(idclock.DEFAULT_RATE * 15 * 60)
    fake_source.put("iphone 12", [make_raw(stale, "iPhone 12 velho", 80)])
    signup(client)
    client.post("/alerts", json=IPHONE)
    assert run_search(client)["newItems"] == 0  # nada publicado nos últimos 5 min
    fake_source.put("iphone 12", [make_raw(now_id + 500, "iPhone 12 agora", 70), make_raw(stale, "iPhone 12 velho", 80)])
    again = run_search(client)
    assert again["newItems"] == 1
    assert [i["title"] for i in client.get("/items").json()["items"]] == ["iPhone 12 agora"]


def test_id_clock_estimates_with_anchor_and_refines_rate():
    from app.services.idclock import DEFAULT_RATE, IdClock

    c = IdClock()
    assert c.cutoff_id(300, at=0) is None  # sem âncora, sem relógio
    c.observe(1_000_000, at=0)
    assert c.cutoff_id(300, at=0) == 1_000_000 - int(DEFAULT_RATE * 300)
    c.observe(1_000_000 + 1000, at=10)  # abaixo da estimativa (10*64=640 -> 1000 é maior, vira âncora)
    c.observe(1_000_000 + 500, at=20)  # mais velho que o esperado: ignorado
    assert c._anchors[-1][1] == 1_001_000
    c.observe(1_000_000 + 60_000, at=200)  # 300 s de vão... rate = (61_000-... )/200
    assert 200 < c._rate() < 400


def test_clicking_search_again_while_stopping_resumes_the_same_search(client, signup):
    from app.services import manual_search

    user_id = signup(client)["id"]
    stuck = manual_search.SearchJob(state="stopping", cycles=3, started_at=manual_search.utcnow())
    stuck.stop.set()  # pediu para parar, mas a thread ainda não saiu
    manual_search._jobs[user_id] = stuck
    again = client.post("/search/run", json={})
    assert again.status_code == 202 and again.json()["state"] == "running" and again.json()["cycles"] == 3
    assert not stuck.stop.is_set()  # a mesma busca seguiu, sem abrir outra

    stuck.state, stuck.exiting = "stopping", True  # agora a thread já está saindo: aí abre uma nova
    stuck.stop.set()
    fresh = client.post("/search/run", json={})
    assert fresh.json()["state"] == "running" and fresh.json()["cycles"] == 0
    manual_search.stop(user_id)


def test_new_accounts_start_at_the_fastest_interval_of_their_plan(client, signup):
    signup(client)  # PRO nos testes: 15 s
    assert client.get("/settings").json() == {"intervalMinutes": 0.25}


def test_new_listings_get_an_estimated_posting_time_from_the_id_clock(session_factory):
    from datetime import timedelta

    from sqlalchemy import select

    from app.models import Item, utcnow
    from app.services import idclock
    from app.services.pipeline import store_items

    idclock.clock.reset()
    now_id = 10_050_000_000
    idclock.clock.observe(now_id)  # "agora" no relógio dos anúncios
    five_min_ago = now_id - int(idclock.DEFAULT_RATE * 300)
    ancient = now_id - int(idclock.DEFAULT_RATE * 30 * 86400)
    with session_factory() as db:
        store_items(db, [make_raw(five_min_ago, "iPhone recente", 80), make_raw(ancient, "iPhone velhíssimo", 80)])
        db.commit()
        recent = db.scalar(select(Item).where(Item.vinted_id == five_min_ago))
        old = db.scalar(select(Item).where(Item.vinted_id == ancient))
        assert timedelta(minutes=4) < utcnow() - recent.posted_at < timedelta(minutes=6)  # ~5 min atrás
        assert old.posted_at is None  # velho demais para estimar: melhor não mostrar
    idclock.clock.reset()
