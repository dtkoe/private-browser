import pytest
from sqlalchemy import create_engine

from backend.core.app_state import AppState, NotUnlocked


def test_app_state_starts_locked():
    s = AppState()
    assert not s.is_unlocked()
    with pytest.raises(NotUnlocked):
        _ = s.engine


def test_set_unlocked_engine():
    eng = create_engine("sqlite:///:memory:", future=True)
    s = AppState()
    s.set_unlocked(eng)
    assert s.is_unlocked()
    assert s.engine is eng
    assert s.session_factory is not None
    s.lock()
    assert not s.is_unlocked()
