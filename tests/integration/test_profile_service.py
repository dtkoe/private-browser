from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

from backend.core.config import Settings
from backend.services.profile_service import ProfileNotFound, ProfileService
from backend.services.security_service import SecurityService


@pytest.fixture
def svc(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    settings = Settings()
    settings.ensure_dirs()
    security = SecurityService(settings)
    security.initialize_with_password("TestPassword!12")
    engine = security.unlock("TestPassword!12")
    sf = sessionmaker(engine, expire_on_commit=False)
    return ProfileService(session_factory=sf, settings=settings)


def test_create_profile_generates_fingerprint(svc):
    p = svc.create(name="acc-1")
    assert p.id
    assert p.name == "acc-1"
    assert p.fingerprint["_os"] in ("windows", "macos", "linux")
    assert p.fingerprint["_seeds"]["canvas"] > 0
    assert p.status == "new"
    assert Path(p.user_data_dir).is_dir()


def test_create_profile_with_target_os(svc):
    p = svc.create(name="mac-1", target_os="macos")
    assert p.fingerprint["_os"] == "macos"


def test_list_profiles(svc):
    svc.create(name="a")
    svc.create(name="b")
    rows = svc.list_profiles()
    assert {r.name for r in rows} == {"a", "b"}


def test_get_profile(svc):
    created = svc.create(name="x")
    fetched = svc.get(created.id)
    assert fetched.id == created.id


def test_get_missing_raises(svc):
    with pytest.raises(ProfileNotFound):
        svc.get("does-not-exist")


def test_update_name_and_notes(svc):
    p = svc.create(name="old")
    updated = svc.update(p.id, name="new", notes="hello")
    assert updated.name == "new"
    assert updated.notes == "hello"


def test_regenerate_fingerprint(svc):
    p = svc.create(name="x", target_os="windows")
    old_seeds = dict(p.fingerprint["_seeds"])
    p2 = svc.regenerate_fingerprint(p.id, target_os="windows")
    assert p2.fingerprint["_seeds"] != old_seeds
    assert p2.fingerprint["_os"] == "windows"


def test_update_status(svc):
    p = svc.create(name="x")
    p2 = svc.update_status(p.id, status_value="running", last_opened_at=12345)
    assert p2.status == "running"
    assert p2.last_opened_at == 12345
    assert p2.open_count == 1


def test_delete_profile_removes_db_row_and_dir(svc):
    p = svc.create(name="dropme")
    pdir = Path(p.user_data_dir)
    assert pdir.is_dir()
    svc.delete(p.id)
    with pytest.raises(ProfileNotFound):
        svc.get(p.id)
    assert not pdir.exists()


def test_ten_profiles_have_distinct_seeds(svc):
    profiles = [svc.create(name=f"p{i}") for i in range(10)]
    seed_tuples = {tuple(p.fingerprint["_seeds"].values()) for p in profiles}
    assert len(seed_tuples) == 10
