from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.services.security_service import (
    SecurityService,
    AlreadyInitialized,
    InvalidPassword,
    NotInitialized,
)


@pytest.fixture
def settings(tmp_path: Path, monkeypatch) -> Settings:
    monkeypatch.setenv("APPDATA", str(tmp_path))
    s = Settings()
    s.ensure_dirs()
    return s


def test_initialize_creates_encrypted_db(settings: Settings):
    svc = SecurityService(settings)
    svc.initialize_with_password("MasterPass!1234")
    assert settings.db_path.is_file()


def test_double_initialize_raises(settings: Settings):
    svc = SecurityService(settings)
    svc.initialize_with_password("first-pass-XYZ")
    with pytest.raises(AlreadyInitialized):
        svc.initialize_with_password("second-pass")


def test_unlock_with_correct_password(settings: Settings):
    svc = SecurityService(settings)
    svc.initialize_with_password("CorrectHorse!")
    engine = svc.unlock("CorrectHorse!")
    assert engine is not None
    engine.dispose()


def test_unlock_with_wrong_password_raises(settings: Settings):
    svc = SecurityService(settings)
    svc.initialize_with_password("CorrectHorse!")
    with pytest.raises(InvalidPassword):
        svc.unlock("nope")


def test_unlock_before_init_raises(settings: Settings):
    svc = SecurityService(settings)
    with pytest.raises(NotInitialized):
        svc.unlock("any")
