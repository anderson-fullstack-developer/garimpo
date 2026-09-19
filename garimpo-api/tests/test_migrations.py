"""Garante que as migrações do Alembic e os modelos (app/models.py) estão sempre em sincronia."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.config import get_settings
from app.db import Base

ROOT = Path(__file__).resolve().parent.parent


def _config() -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    return cfg


def test_migrations_create_every_model_table_and_match_models(tmp_path, monkeypatch):
    db_file = tmp_path / "migracao.db"
    monkeypatch.setattr(get_settings(), "database_url", f"sqlite:///{db_file}")

    command.upgrade(_config(), "head")
    tables = set(inspect(create_engine(f"sqlite:///{db_file}")).get_table_names())
    assert set(Base.metadata.tables) <= tables

    # Se falhar aqui: mudou um modelo sem criar migração (`alembic revision --autogenerate -m "..."`).
    command.check(_config())


def test_migrations_can_be_reverted(tmp_path, monkeypatch):
    db_file = tmp_path / "volta.db"
    monkeypatch.setattr(get_settings(), "database_url", f"sqlite:///{db_file}")
    command.upgrade(_config(), "head")
    command.downgrade(_config(), "base")
    tables = set(inspect(create_engine(f"sqlite:///{db_file}")).get_table_names())
    assert tables <= {"alembic_version"}
