"""SQLCipher-backed SQLAlchemy engine (sync; called from async via to_thread when needed)."""
from __future__ import annotations

from pathlib import Path

import sqlcipher3
from sqlalchemy import Engine, create_engine, event, text


class DatabaseUnlockError(Exception):
    """Raised when SQLCipher refuses the supplied key (or DB is corrupt)."""


def _hex_key(key: bytes) -> str:
    return key.hex()


def _attach_sqlcipher_key(engine: Engine, key: bytes) -> None:
    """Register a connect-listener that runs PRAGMA key on every new connection."""
    hex_key = _hex_key(key)

    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute(f"PRAGMA key = \"x'{hex_key}'\";")
        cur.execute("PRAGMA cipher_compatibility = 4;")
        cur.execute("PRAGMA journal_mode = WAL;")
        cur.close()


def _build_engine(path: Path, key: bytes) -> Engine:
    """Build a SQLAlchemy Engine that uses sqlcipher3 as the DBAPI module."""
    url = f"sqlite:///{path}"
    engine = create_engine(url, module=sqlcipher3, future=True)
    _attach_sqlcipher_key(engine, key)
    return engine


def create_new_encrypted_db(path: Path, key: bytes) -> None:
    """Create a brand new encrypted DB at `path` keyed with `key`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(path)

    engine = _build_engine(path, key)
    try:
        with engine.begin() as conn:
            # Sanity write so the DB has a real (encrypted) header
            conn.execute(text("CREATE TABLE _init (v INTEGER)"))
            conn.execute(text("DROP TABLE _init"))
    finally:
        engine.dispose()


def open_encrypted_db(path: Path, key: bytes) -> Engine:
    """Open existing encrypted DB. Raises DatabaseUnlockError on bad key."""
    if not path.is_file():
        raise FileNotFoundError(path)

    engine = _build_engine(path, key)
    try:
        with engine.connect() as conn:
            # Trigger a read; wrong key => DatabaseError "file is not a database"
            conn.execute(text("SELECT count(*) FROM sqlite_master"))
    except Exception as exc:
        engine.dispose()
        raise DatabaseUnlockError(str(exc)) from exc
    return engine
