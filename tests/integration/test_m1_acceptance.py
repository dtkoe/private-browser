"""M1 acceptance: fresh install → initialize → restart → unlock works."""
from __future__ import annotations

from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.services.security_service import (
    InvalidPassword,
    NotInitialized,
    SecurityService,
)


def test_m1_full_happy_path(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))

    # 1. Fresh app, no DB
    settings_1 = Settings()
    settings_1.ensure_dirs()
    sec_1 = SecurityService(settings_1)
    with pytest.raises(NotInitialized):
        sec_1.unlock("anythingLong12")

    # 2. Initialize
    sec_1.initialize_with_password("MyMaster!2026")
    assert settings_1.db_path.is_file()
    assert (settings_1.data_dir / "app.salt").is_file()

    # 3. Re-instantiate everything as if restart
    settings_2 = Settings()
    sec_2 = SecurityService(settings_2)

    # 4. Wrong password → InvalidPassword
    with pytest.raises(InvalidPassword):
        sec_2.unlock("wrong-password!")

    # 5. Correct password → engine
    engine = sec_2.unlock("MyMaster!2026")
    assert engine is not None
    engine.dispose()


def test_m1_db_is_not_plaintext_sqlite(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    settings = Settings()
    settings.ensure_dirs()
    sec = SecurityService(settings)
    sec.initialize_with_password("Plaintext!Check12")

    header = settings.db_path.read_bytes()[:16]
    # Plaintext SQLite header starts with literal magic string.
    assert not header.startswith(b"SQLite format 3\x00"), (
        "DB header looks like plaintext SQLite — encryption is NOT engaged."
    )
