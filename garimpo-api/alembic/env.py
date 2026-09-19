"""Ambiente do Alembic: usa as tabelas de `app.models` e a DATABASE_URL do `.env`."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app import models  # noqa: F401  (registra as tabelas)
from app.config import get_settings
from app.db import Base, direct_url, normalize_url

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# `%` precisa ser escapado porque o configparser interpreta "%(...)s".
config.set_main_option(
    "sqlalchemy.url", direct_url(normalize_url(get_settings().database_url)).replace("%", "%%")
)
target_metadata = Base.metadata

_common = {
    "target_metadata": target_metadata,
    "compare_type": True,
    "user_module_prefix": "app.models.",
    "render_as_batch": True,  # necessário para alterar tabelas no SQLite
}


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        **_common,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, **_common)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
