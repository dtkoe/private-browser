"""High-level master-password lifecycle: init, unlock. SYNC."""
from __future__ import annotations

import json
import os
import secrets
from pathlib import Path

from alembic.config import Config
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from alembic import command
from backend.core.config import Settings
from backend.core.db import (
    DatabaseUnlockError,
    create_new_encrypted_db,
    open_encrypted_db,
)
from backend.core.security import (
    KDFParams,
    check_verifier,
    derive_key,
    make_verifier,
)
from backend.models.app_settings import AppSettings


class AlreadyInitialized(Exception):
    pass


class NotInitialized(Exception):
    pass


class InvalidPassword(Exception):
    pass


class SecurityService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def initialize_with_password(self, password: str) -> None:
        if self._settings.db_path.exists():
            raise AlreadyInitialized(str(self._settings.db_path))

        params = KDFParams.default()
        salt = secrets.token_bytes(16)
        key = derive_key(password, salt, params)
        verifier = make_verifier(key)

        create_new_encrypted_db(self._settings.db_path, key)

        # Apply Alembic migrations on the freshly-created encrypted DB
        _run_migrations(self._settings.db_path, key)

        # Write salt sidecar (salt is not secret; used for KDF on subsequent unlocks)
        salt_path = self._settings.data_dir / "app.salt"
        salt_path.write_bytes(salt)

        # Seed app_settings row
        engine = open_encrypted_db(self._settings.db_path, key)
        try:
            with Session(engine, expire_on_commit=False) as session:
                session.add(
                    AppSettings(
                        id=1,
                        kdf_salt=salt,
                        kdf_verifier=verifier,
                        kdf_params_json=json.dumps(params.to_dict()),
                    )
                )
                session.commit()
        finally:
            engine.dispose()

    def unlock(self, password: str) -> Engine:
        if not self._settings.db_path.exists():
            raise NotInitialized(str(self._settings.db_path))

        salt_path = self._settings.data_dir / "app.salt"
        if not salt_path.exists():
            raise NotInitialized("missing app.salt sidecar")
        salt = salt_path.read_bytes()

        params = KDFParams.default()
        key = derive_key(password, salt, params)
        try:
            engine = open_encrypted_db(self._settings.db_path, key)
        except DatabaseUnlockError as exc:
            raise InvalidPassword() from exc

        # Belt + suspenders: verify HMAC verifier
        try:
            with Session(engine) as session:
                row = session.execute(select(AppSettings).limit(1)).scalar_one()
                if not check_verifier(key, row.kdf_verifier):
                    raise InvalidPassword()
        except InvalidPassword:
            engine.dispose()
            raise

        return engine


def _run_migrations(db_path: Path, key: bytes) -> None:
    """Run Alembic upgrade head against the encrypted DB."""
    os.environ["PB_ALEMBIC_DB_PATH"] = str(db_path)
    os.environ["PB_ALEMBIC_KEY_HEX"] = key.hex()
    # Use absolute path to alembic.ini
    cfg_path = Path("alembic.ini").resolve()
    cfg = Config(str(cfg_path))
    cfg.set_main_option("script_location", "alembic")
    command.upgrade(cfg, "head")
