"""Security primitives: KDF, verifier, API token."""
from __future__ import annotations

import hmac
import secrets
from dataclasses import asdict, dataclass
from hashlib import sha256
from typing import Any

from argon2.low_level import Type as Argon2Type
from argon2.low_level import hash_secret_raw


@dataclass(frozen=True)
class KDFParams:
    memory_kb: int = 65536
    iterations: int = 3
    parallelism: int = 4
    output_length: int = 32
    type: str = "argon2id"

    @classmethod
    def default(cls) -> KDFParams:
        return cls()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> KDFParams:
        return cls(**d)


def derive_key(password: str, salt: bytes, params: KDFParams | None = None) -> bytes:
    p = params or KDFParams.default()
    if p.type != "argon2id":
        raise ValueError(f"Unsupported KDF type: {p.type}")
    return hash_secret_raw(
        secret=password.encode("utf-8"),
        salt=salt,
        time_cost=p.iterations,
        memory_cost=p.memory_kb,
        parallelism=p.parallelism,
        hash_len=p.output_length,
        type=Argon2Type.ID,
    )


_VERIFIER_LABEL = b"private-browser.verifier.v1"


def make_verifier(key: bytes) -> bytes:
    return hmac.new(key, _VERIFIER_LABEL, sha256).digest()


def check_verifier(key: bytes, expected: bytes) -> bool:
    candidate = make_verifier(key)
    return hmac.compare_digest(candidate, expected)


def generate_api_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)
