import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import models  # noqa: F401  (registra as tabelas no metadata)
from app.config import get_settings
from app.db import Base, engine
from app.errors import install_error_handlers
from app.routers import alerts, auth, billing, destinations, items, me, monitor, public, search, webhooks
from app.services.channels import get_channel, register_channel
from app.services.monitor import engine as monitor_engine
from app.services.telegram import TelegramChannel


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    # Em desenvolvimento com SQLite as tabelas são criadas sozinhas; no Postgres use `alembic upgrade head`.
    if settings.is_sqlite and settings.environment != "production":
        Base.metadata.create_all(engine)
    _logs = logging.getLogger("garimpo")  # avisos e envios aparecem no terminal do servidor
    if not _logs.handlers:
        _handler = logging.StreamHandler()
        _handler.setFormatter(logging.Formatter("%(levelname)s [%(name)s] %(message)s"))
        _logs.addHandler(_handler)
        _logs.setLevel(logging.INFO)
        _logs.propagate = False
    register_channel(TelegramChannel())
    if settings.monitor_autostart and settings.environment != "test":
        monitor_engine.start()
    yield
    monitor_engine.stop()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Garimpo API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None if settings.environment == "production" else "/docs",
        redoc_url=None,
        openapi_url=None if settings.environment == "production" else "/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["content-type"],
    )
    install_error_handlers(app)
    for router in (public.router, auth.router, me.router, alerts.router, destinations.router, monitor.router, items.router, search.router, billing.router, webhooks.router):
        app.include_router(router)
    return app


app = create_app()
