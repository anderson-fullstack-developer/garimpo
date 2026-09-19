import os
import re

# Precisa vir antes de importar o app: define um ambiente de teste isolado.
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET"] = "segredo-de-teste-com-mais-de-trinta-e-dois-caracteres"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import ratelimit  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import Base, get_db  # noqa: E402
from app.services import manual_search  # noqa: E402
from app.main import app  # noqa: E402

PASSWORD = "senha-segura-123"


@pytest.fixture
def settings(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "translate_enabled", False)  # nunca chamar a internet nos testes
    monkeypatch.setattr(s, "live_exchange_rates", False)
    monkeypatch.setattr(s, "registration_mode", "OPEN")
    monkeypatch.setattr(s, "require_verification", True)
    monkeypatch.setattr(s, "stripe_secret_key", None)
    monkeypatch.setattr(s, "stripe_price_id", None)
    monkeypatch.setattr(s, "stripe_webhook_secret", None)
    monkeypatch.setattr(s, "default_plan", "PRO")
    monkeypatch.setattr(s, "turnstile_secret", None)
    monkeypatch.setattr(s, "telegram_webhook_secret", None)  # os testes não dependem do .env de verdade
    monkeypatch.setattr(s, "telegram_bot_token", None)
    return s


# ---------------------------------------------------------------- banco dos testes
# Padrão: SQLite em memória (rápido, sem nada para instalar). Opcional e explícito: `TEST_DATABASE_URL`
# roda a MESMA suíte num Postgres de verdade (ex.: a Neon). Só usa o schema isolado `garimpo_test`
# (nunca o `public`), e por isso tabelas e dados de verdade ficam intocados.
PG_TEST_SCHEMA = "garimpo_test"
_pg_engine = None


def _postgres_test_engine():
    global _pg_engine
    if _pg_engine is None:
        from sqlalchemy import text

        from app.db import direct_url, normalize_url

        url = direct_url(normalize_url(os.environ["TEST_DATABASE_URL"]))  # direto: aceita `search_path`
        assert url.startswith("postgresql"), "TEST_DATABASE_URL precisa ser Postgres"
        engine = create_engine(
            url, connect_args={"options": f"-csearch_path={PG_TEST_SCHEMA}", "prepare_threshold": None}
        )
        with engine.begin() as conn:
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {PG_TEST_SCHEMA}"))
            # Trava de segurança: se o search_path não estiver isolado, aborta em vez de mexer no `public`.
            assert conn.execute(text("select current_schema()")).scalar() == PG_TEST_SCHEMA
        Base.metadata.create_all(engine)
        _pg_engine = engine
    return _pg_engine


@pytest.fixture
def session_factory(tmp_path):
    if os.environ.get("TEST_DATABASE_URL"):
        from sqlalchemy import text

        engine = _postgres_test_engine()
        names = ", ".join(t.name for t in Base.metadata.sorted_tables)
        with engine.begin() as conn:
            conn.execute(text(f"TRUNCATE TABLE {names} RESTART IDENTITY CASCADE"))  # só o schema de teste
        return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    # Arquivo (não memória): cada thread tem sua conexão, como no Postgres. A busca manual roda em outra thread.
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False, "timeout": 15})

    @event.listens_for(engine, "connect")
    def _fk(conn, _):  # noqa: ANN001
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA synchronous=OFF")  # só testes: sem esperar o disco

    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture
def client(settings, session_factory):
    def override():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    ratelimit.reset_all()
    manual_search.reset_all()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def signup(session_factory):
    """Cria (e opcionalmente loga) uma conta já verificada (é o que o vínculo do Telegram faz)."""

    def _signup(client: TestClient, email: str = "ana@example.com", login: bool = True) -> dict | None:
        r = client.post(
            "/auth/register", json={"email": email, "password": PASSWORD, "captchaToken": "x"}
        )
        assert r.status_code == 204, r.text
        with session_factory() as db:
            user = db.scalar(select(User).where(User.email == email))
            user.email_verified_at = utcnow()
            user.trial_ends_at = utcnow() + timedelta(days=7)  # como no vínculo do Telegram
            db.commit()
        if not login:
            return None
        r = client.post("/auth/login", json={"email": email, "password": PASSWORD})
        assert r.status_code == 200, r.text
        return r.json()

    return _signup


@pytest.fixture
def make_client(client):
    """Um segundo navegador (cookies próprios) falando com a mesma API."""

    def _make() -> TestClient:
        other = TestClient(app)
        return other

    return _make


ALERT = {
    "name": "",
    "query": "iphone 12",
    "matchType": "PHRASE",
    "requiredWords": [],
    "excludeWords": ["capa"],
    "excludePresets": [],
    "minPrice": 0,
    "maxPrice": 90,
    "statusFilter": [],
    "maxAgeMinutes": None,
    "pages": 1,
    "country": "pt",
    "notifyOnFirstRun": False,
    "vintedParams": None,
    "sourceUrl": None,
    "perfectMin": None,
    "perfectMax": None,
    "destinationId": None,
    "active": True,
}


# ---------------------------------------------------------------- Vinted e canal de mentira
from datetime import datetime, timedelta  # noqa: E402
from decimal import Decimal  # noqa: E402

from app.models import Destination, User, UserSettings, utcnow  # noqa: E402
from app.services import channels as channels_module  # noqa: E402
from app.services import monitor as monitor_module  # noqa: E402
from app.services import vinted as vinted_module  # noqa: E402
from app.services.channels import PermanentChannelError, TransientChannelError  # noqa: E402
from app.services.monitor import MonitorEngine  # noqa: E402
from app.services.vinted import RawItem  # noqa: E402
from sqlalchemy import select  # noqa: E402


def make_raw(vid: int, title: str, price: float, domain: str = "pt", condition: str | None = "good") -> RawItem:
    return RawItem(
        vinted_id=vid, domain=domain, title=title, price=Decimal(str(price)), total_price=None, currency="EUR",
        condition=condition, condition_text=None, seller_login=f"#{vid}", url=f"https://www.vinted.{domain}/items/{vid}",
        photo_url=None, posted_at=None,
    )  # fmt: skip


class FakeSource:
    """Controla o que a "Vinted" devolve e conta as chamadas."""

    def __init__(self):
        self.items: dict[tuple[str, str], list[RawItem]] = {}
        self.calls: list[tuple[str, str, int]] = []
        self.errors: dict[str, Exception] = {}  # por domínio; "*" vale para todos

    def put(self, query: str, items: list[RawItem], domain: str = "pt") -> None:
        self.items[(domain, query.lower())] = items

    def fetch(self, domain, query, page=1, params=None):
        self.calls.append((domain, query, page))
        error = self.errors.get(domain) or self.errors.get("*")
        if error:
            raise error
        return list(self.items.get((domain, query.lower()), [])) if page == 1 else []


class FakeChannel:
    name = "TELEGRAM"

    def __init__(self):
        self.sent: list[tuple[Destination, object]] = []
        self.texts: list[tuple[Destination, str]] = []
        self.error: Exception | None = None

    def send(self, destination, message):
        if self.error:
            raise self.error
        self.sent.append((destination, message))

    def send_text(self, destination, text):
        if self.error:
            raise self.error
        self.texts.append((destination, text))

    def send_rich(self, destination, html_text, plain_text, buttons):
        if self.error:
            raise self.error
        self.texts.append((destination, html_text))
        self.buttons = buttons


@pytest.fixture
def fake_source():
    source = FakeSource()
    vinted_module.set_source(source)
    monitor_module.clear_preview_cache()
    yield source
    vinted_module.set_source(None)


@pytest.fixture
def fake_channel():
    channel = FakeChannel()
    channels_module.register_channel(channel)
    yield channel
    channels_module.register_channel(__import__("app.services.telegram", fromlist=["TelegramChannel"]).TelegramChannel())


@pytest.fixture
def engine_(session_factory):
    return MonitorEngine(session_factory=session_factory)


@pytest.fixture
def link_destination(session_factory):
    def _link(email: str, chat_id: str = "-1001", title: str = "Grupo", default: bool = True, kind: str = "GROUP") -> str:
        with session_factory() as db:
            user = db.scalar(select(User).where(User.email == email))
            dest = Destination(
                user_id=user.id, kind=kind, external_id=chat_id, title=title, linked_at=utcnow(), is_default=default
            )
            db.add(dest)
            db.commit()
            return dest.id

    return _link


@pytest.fixture
def start_monitor(client):
    def _start(c=None):
        assert (c or client).post("/monitor/start").status_code == 204

    return _start


def T(minutes: int = 0) -> datetime:
    """Relógio de teste: cada ciclo avança 6 min (o intervalo padrão é 5)."""
    return datetime(2026, 1, 1, 12, 0, tzinfo=__import__("datetime").timezone.utc) + __import__("datetime").timedelta(minutes=minutes)


def run_search(client, timeout: float = 10.0) -> dict:
    """"Buscar" é contínuo: roda 1 ciclo, manda parar e devolve o estado final."""
    import time

    first = client.post("/search/run", json={})
    if first.status_code != 202:
        return {"http": first.status_code, **first.json()}
    deadline = time.time() + timeout
    while time.time() < deadline:
        state = client.get("/search/status").json()
        if state["cycles"] >= 1:
            break
        time.sleep(0.02)
    else:
        raise AssertionError("a busca não fez nenhum ciclo")
    client.post("/search/stop")
    while time.time() < deadline:
        state = client.get("/search/status").json()
        if state["state"] not in ("running", "stopping"):
            return state
        time.sleep(0.02)
    raise AssertionError("a busca não parou")
