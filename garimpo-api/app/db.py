import time
from collections.abc import Iterator

from sqlalchemy import create_engine, event, exc
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


STALE_AFTER_SECONDS = 30


def normalize_url(url: str) -> str:
    """Aceita as URLs da Neon (`postgres://`/`postgresql://`) e usa o driver psycopg 3."""
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


def direct_url(url: str) -> str:
    """Conexão direta da Neon (sem o pooler). Migrações precisam dela: o PgBouncer em modo transação
    não garante a mesma sessão entre comandos (travas do Alembic, SET, DDL)."""
    return url.replace("-pooler.", ".", 1)


def make_engine(url: str) -> Engine:
    url = normalize_url(url)
    if url.startswith("sqlite"):
        engine = create_engine(url, connect_args={"check_same_thread": False})

        @event.listens_for(engine, "connect")
        def _enable_foreign_keys(dbapi_connection, _record):  # noqa: ANN001
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        return engine
    engine = create_engine(
        url,
        pool_size=5,  # a Neon já tem pooler (PgBouncer); aqui basta um conjunto pequeno
        max_overflow=5,
        pool_recycle=240,  # renova antes de a Neon fechar conexões ociosas
        connect_args={
            "prepare_threshold": None,  # compatível com PgBouncer em modo transação
            "connect_timeout": 15,  # tolera o "acordar" da computação suspensa
        },
    )

    # `pool_pre_ping` testaria a conexão em TODA requisição (uma ida e volta a mais, ~65 ms daqui até a
    # Neon). Só testamos quando a conexão ficou parada tempo suficiente para a Neon ter podido fechá-la.
    @event.listens_for(engine, "checkin")
    def _mark_idle(_dbapi, record) -> None:  # noqa: ANN001
        record.info["idle_since"] = time.monotonic()

    @event.listens_for(engine, "checkout")
    def _ping_if_stale(dbapi, record, _proxy) -> None:  # noqa: ANN001
        idle_since = record.info.get("idle_since")
        if idle_since is not None and time.monotonic() - idle_since > STALE_AFTER_SECONDS:
            try:
                cursor = dbapi.cursor()
                cursor.execute("SELECT 1")
                cursor.close()
            except Exception as error:  # conexão morta: o pool descarta e abre outra
                raise exc.DisconnectionError() from error

    return engine


engine = make_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
