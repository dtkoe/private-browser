import secrets

import pytest

from backend.core.security import (
    derive_key,
    make_verifier,
    check_verifier,
    KDFParams,
    generate_api_token,
)


@pytest.fixture
def salt() -> bytes:
    return secrets.token_bytes(16)


def test_derive_key_is_deterministic(salt: bytes):
    key1 = derive_key("correct horse battery staple", salt)
    key2 = derive_key("correct horse battery staple", salt)
    assert key1 == key2
    assert len(key1) == 32


def test_derive_key_different_password_gives_different_key(salt: bytes):
    k1 = derive_key("password1", salt)
    k2 = derive_key("password2", salt)
    assert k1 != k2


def test_derive_key_different_salt_gives_different_key():
    k1 = derive_key("pw", b"\x00" * 16)
    k2 = derive_key("pw", b"\x01" * 16)
    assert k1 != k2


def test_verifier_round_trip(salt: bytes):
    key = derive_key("pw", salt)
    verifier = make_verifier(key)
    assert check_verifier(key, verifier) is True


def test_verifier_rejects_wrong_key(salt: bytes):
    key_a = derive_key("right", salt)
    key_b = derive_key("wrong", salt)
    verifier = make_verifier(key_a)
    assert check_verifier(key_b, verifier) is False


def test_kdf_params_serializable():
    p = KDFParams.default()
    assert p.memory_kb >= 65536
    assert p.iterations >= 3
    assert p.parallelism >= 1
    d = p.to_dict()
    p2 = KDFParams.from_dict(d)
    assert p2 == p


def test_generate_api_token_unique():
    t1 = generate_api_token()
    t2 = generate_api_token()
    assert len(t1) >= 32
    assert t1 != t2
