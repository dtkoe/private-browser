"""Alembic env.py for private-browser — uses sqlcipher3 module for encrypted DB."""
from __future__ import annotations

import os
from logging.config import fileConfig
from pathlib import Path

import sqlcipher3
from alembic import context
from sqlalchemy import create_engine, event, pool

from backend.models import Base
from backend.models.app_settings import AppSettings  # noqa: F401 — force import for metadata
from backend.models.audit_log import AuditLog  # noqa: F401 — force import for metadata


config = context.config

# Setup logging from alembic.ini if [loggers] sections exist
if config.config_file_name is not None:
    try:
        fileConfig(config.config_file_name)
    except Exception:
        pass

target_metadata = Base.metadata


def _build_engine_for_alembic():
    """Build sync engine with sqlcipher3 module + PRAGMA key on connect."""
    db_path = Path(os.environ["PB_ALEMBIC_DB_PATH"])
    key_hex = os.environ["PB_ALEMBIC_KEY_HEX"]

    url = f"sqlite:///{db_path}"
    engine = create_engine(url, module=sqlcipher3, poolclass=pool.NullPool, future=True)

    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute(f'PRAGMA key = "x\'{key_hex}\'";')
        cur.execute("PRAGMA cipher_compatibility = 4;")
        cur.close()

    return engine


def run_migrations_offline() -> None:
    """Offline mode is not meaningful for encrypted DB; emit metadata against generic sqlite."""
    context.configure(
        url="sqlite://",
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = _build_engine_for_alembic()
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
