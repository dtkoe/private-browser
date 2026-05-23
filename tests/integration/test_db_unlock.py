import secrets
from pathlib import Path

import pytest

from backend.core.db import (
    DatabaseUnlockError,
    create_new_encrypted_db,
    open_encrypted_db,
)
from backend.core.security import derive_key


def test_create_then_open_with_same_key(tmp_path: Path):
    db = tmp_path / "test.db"
    salt = secrets.token_bytes(16)
    key = derive_key("strong-password", salt)
    create_new_encrypted_db(db, key)
    assert db.is_file()
    # open and verify we can run a trivial query
    engine = open_encrypted_db(db, key)
    from sqlalchemy import text
    with engine.connect() as conn:
        v = conn.execute(text("SELECT 1")).scalar_one()
        assert v == 1
    engine.dispose()


def test_open_with_wrong_key_raises(tmp_path: Path):
    db = tmp_path / "test.db"
    salt = secrets.token_bytes(16)
    right = derive_key("right", salt)
    wrong = derive_key("wrong", salt)
    create_new_encrypted_db(db, right)
    with pytest.raises(DatabaseUnlockError):
        open_encrypted_db(db, wrong)


def test_db_file_is_encrypted_on_disk(tmp_path: Path):
    db = tmp_path / "test.db"
    salt = secrets.token_bytes(16)
    key = derive_key("pw", salt)
    create_new_encrypted_db(db, key)
    # Header MUST NOT be the plaintext SQLite magic.
    data = db.read_bytes()[:16]
    assert not data.startswith(b"SQLite format 3\x00")
