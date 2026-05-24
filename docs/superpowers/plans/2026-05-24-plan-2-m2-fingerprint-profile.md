# Plan 2 — M2: FingerprintGenerator + Profile API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate consistent per-profile Camoufox fingerprints, persist full profile model in SQLCipher, expose profile CRUD + regenerate + launch via REST API.

**Architecture:** Thin wrapper around Camoufox's `browserforge`-based `generate_fingerprint()` — adds per-profile seeds, OS/geo overrides, persistence (config dict + seeds as the profile's `fingerprint` blob). Launch via `subprocess.Popen(camoufox.exe)` driven by `launch_options(config=…, proxy=…)` serialized to JSON+stdin (Camoufox's own protocol).

**Tech Stack:** Same as Plan 1 (FastAPI, SQLAlchemy 2 sync, SQLCipher, Alembic, structlog, pytest). New deps: none — `camoufox[geoip]>=0.4` already includes `browserforge` and `GeoLite2-City.mmdb`.

**Source spec:** [../specs/2026-05-24-private-browser/03-fingerprint-vectors.md](../specs/2026-05-24-private-browser/03-fingerprint-vectors.md), [05-profile-model.md](../specs/2026-05-24-private-browser/05-profile-model.md), [09-phasing-and-milestones.md M2](../specs/2026-05-24-private-browser/09-phasing-and-milestones.md).

## Strategy notes

- **Do NOT reinvent fingerprint datasets** — Camoufox already ships `browserforge.yml` (OS distributions), `fonts.json` (per-OS font lists), `webgl/` (vendor/renderer pairs), and `GeoLite2-City.mmdb`. Our `FingerprintGenerator` is a thin orchestrator: it picks high-level params (target_os, target_geo) and calls `camoufox.fingerprints.generate_fingerprint()`, then enriches with per-profile seeds.
- **Persistence shape:** store the dict produced by `camoufox.fingerprints.from_browserforge(fp)` augmented with `_seeds`, `_meta` (schema_version, generator_version, generated_at), and our `_os`/`_geo` choices. That dict is what we feed back to `Camoufox(config=…)` at launch.
- **Sync code throughout** (matches Plan 1's choice). FastAPI handles sync handlers via threadpool.
- **No live CreepJS check in CI** — that requires a real human. Acceptance is: unit tests for consistency rules + integration test that 10 profiles via API produce 10 distinct fingerprints. Manual checkpoint at end of plan.

---

## File map

| Путь | Цель | Действие |
|---|---|---|
| `backend/core/datasets.py` | Statistical distributions (OS weights, hardware concurrency) | Create |
| `backend/services/fingerprint_generator.py` | High-level generator wrapping browserforge | Create |
| `backend/services/fingerprint_validator.py` | Consistency checks on existing config | Create |
| `backend/models/profile.py` | `profile` table model | Create |
| `backend/models/session.py` | `session` table model | Create |
| `backend/models/proxy.py` | `proxy` table model (stub for M3) | Create |
| `alembic/versions/0002_profile_proxy_session.py` | Schema for new tables | Create |
| `backend/services/profile_service.py` | CRUD + regenerate logic | Create |
| `backend/core/app_state.py` | Holds unlocked engine + services after auth | Create |
| `backend/api/deps.py` | FastAPI dependencies (get_app_state, require_unlocked) | Create |
| `backend/api/profiles.py` | `/api/profiles/*` endpoints | Create |
| `backend/services/launch_manager.py` | Registry + subprocess control | Create |
| `backend/api/launch.py` | `/api/profiles/{id}/launch`, `/stop` | Create |
| `backend/main.py` | Wire profiles + launch routers, app_state | Modify |
| `tests/unit/test_fingerprint_generator.py` | 20+ unit tests | Create |
| `tests/unit/test_fingerprint_validator.py` | Validator tests | Create |
| `tests/unit/test_profile_model.py` | Schema tests | Create |
| `tests/integration/test_profile_service.py` | Service CRUD tests | Create |
| `tests/integration/test_api_profiles.py` | API endpoint tests | Create |
| `tests/integration/test_m2_acceptance.py` | 10-profile uniqueness | Create |

---

## Task 1: Statistical datasets module

**Files:**
- Create: `backend/core/datasets.py`
- Create: `tests/unit/test_datasets.py`

- [ ] **Step 1.1: Write failing test**

Create `tests/unit/test_datasets.py`:
```python
import collections

import pytest

from backend.core.datasets import (
    OS_DISTRIBUTION,
    HW_CONCURRENCY_DISTRIBUTION,
    DEVICE_MEMORY_BY_CONCURRENCY,
    weighted_choice,
)


def test_os_distribution_sums_to_one():
    assert abs(sum(OS_DISTRIBUTION.values()) - 1.0) < 1e-9
    assert set(OS_DISTRIBUTION) == {"windows", "macos", "linux"}


def test_hw_concurrency_distribution_sums_to_one():
    assert abs(sum(HW_CONCURRENCY_DISTRIBUTION.values()) - 1.0) < 1e-9
    assert set(HW_CONCURRENCY_DISTRIBUTION).issubset({2, 4, 6, 8, 12, 16})


def test_device_memory_by_concurrency_covers_all_keys():
    for c in HW_CONCURRENCY_DISTRIBUTION:
        assert c in DEVICE_MEMORY_BY_CONCURRENCY
        assert DEVICE_MEMORY_BY_CONCURRENCY[c] in {2, 4, 8, 16, 32}


def test_weighted_choice_distribution(monkeypatch):
    import random
    rng = random.Random(42)
    counts = collections.Counter(
        weighted_choice({"a": 0.7, "b": 0.3}, rng=rng) for _ in range(10_000)
    )
    # 70/30 within tolerance
    assert 6500 < counts["a"] < 7500
    assert 2500 < counts["b"] < 3500


def test_weighted_choice_rejects_non_normalized():
    with pytest.raises(ValueError):
        weighted_choice({"a": 0.5, "b": 0.6})
```

- [ ] **Step 1.2: Run, expect ImportError**

```bash
.venv/Scripts/python.exe -m pytest tests/unit/test_datasets.py -v
```

- [ ] **Step 1.3: Implement `backend/core/datasets.py`**

```python
"""Statistical distributions for fingerprint generation."""
from __future__ import annotations

import random
from typing import Mapping, TypeVar

_T = TypeVar("_T")


OS_DISTRIBUTION: Mapping[str, float] = {
    "windows": 0.72,
    "macos": 0.18,
    "linux": 0.10,
}

HW_CONCURRENCY_DISTRIBUTION: Mapping[int, float] = {
    4: 0.25,
    6: 0.15,
    8: 0.35,
    12: 0.15,
    16: 0.10,
}

DEVICE_MEMORY_BY_CONCURRENCY: Mapping[int, int] = {
    4: 8,
    6: 8,
    8: 16,
    12: 16,
    16: 32,
}


def weighted_choice(weights: Mapping[_T, float], *, rng: random.Random | None = None) -> _T:
    total = sum(weights.values())
    if abs(total - 1.0) > 1e-6:
        raise ValueError(f"weights must sum to 1.0, got {total}")
    r = (rng or random).random()
    acc = 0.0
    for key, w in weights.items():
        acc += w
        if r <= acc:
            return key
    return key  # safety for FP drift
```

- [ ] **Step 1.4: Run tests green**

```bash
.venv/Scripts/python.exe -m pytest tests/unit/test_datasets.py -v
```
Expected: 5 passed.

- [ ] **Step 1.5: Commit**

```bash
git add backend/core/datasets.py tests/unit/test_datasets.py
git commit -m "feat(core): statistical datasets for fingerprint generation"
```

---

## Task 2: FingerprintGenerator core (TDD)

**Files:**
- Create: `backend/services/fingerprint_generator.py`
- Create: `tests/unit/test_fingerprint_generator.py`

The generator wraps `camoufox.fingerprints.generate_fingerprint()` (Browserforge) and `from_browserforge()` (config dict). Output schema:

```python
{
    "_meta": {"schema_version": 1, "generator_version": "0.1.0", "generated_at": <unix_ms>},
    "_os": "windows" | "macos" | "linux",
    "_geo": None | {"country": "...", "city": "...", "timezone": "...", "latitude": ..., "longitude": ...},
    "_seeds": {"canvas": <int>, "audio": <int>, "webgl_noise": <int>},
    # ...flat camoufox config keys from from_browserforge:
    "navigator.userAgent": "...",
    "navigator.platform": "...",
    "screen.width": ...,
    # etc.
}
```

- [ ] **Step 2.1: Write failing tests**

Create `tests/unit/test_fingerprint_generator.py`:
```python
import secrets

import pytest

from backend.services.fingerprint_generator import (
    FingerprintGenerator,
    GeneratorOptions,
)


@pytest.fixture
def gen() -> FingerprintGenerator:
    return FingerprintGenerator()


def test_generate_returns_dict_with_meta(gen):
    fp = gen.generate()
    assert fp["_meta"]["schema_version"] == 1
    assert fp["_meta"]["generated_at"] > 0
    assert "generator_version" in fp["_meta"]


def test_generate_returns_seeds(gen):
    fp = gen.generate()
    seeds = fp["_seeds"]
    assert set(seeds.keys()) >= {"canvas", "audio", "webgl_noise"}
    for v in seeds.values():
        assert isinstance(v, int)
        assert v != 0


def test_generate_seeds_are_unique_across_calls(gen):
    seeds_1 = gen.generate()["_seeds"]
    seeds_2 = gen.generate()["_seeds"]
    assert seeds_1 != seeds_2


def test_generate_with_target_os_windows(gen):
    fp = gen.generate(GeneratorOptions(target_os="windows"))
    assert fp["_os"] == "windows"
    assert "Windows" in fp["navigator.userAgent"]
    assert fp["navigator.platform"] == "Win32"


def test_generate_with_target_os_macos(gen):
    fp = gen.generate(GeneratorOptions(target_os="macos"))
    assert fp["_os"] == "macos"
    assert "Mac" in fp["navigator.userAgent"] or "Macintosh" in fp["navigator.userAgent"]
    assert fp["navigator.platform"] in {"MacIntel", "Mac68K"}


def test_generate_with_target_os_linux(gen):
    fp = gen.generate(GeneratorOptions(target_os="linux"))
    assert fp["_os"] == "linux"
    assert "Linux" in fp["navigator.userAgent"]
    assert "Linux" in fp["navigator.platform"]


def test_generate_screen_dimensions_present(gen):
    fp = gen.generate()
    for key in ("screen.width", "screen.height", "screen.availWidth", "screen.availHeight"):
        assert isinstance(fp[key], int)
        assert fp[key] > 0


def test_generate_navigator_ua_matches_oscpu(gen):
    fp = gen.generate(GeneratorOptions(target_os="windows"))
    assert "Windows NT" in fp["navigator.oscpu"]


def test_generate_includes_color_depth(gen):
    fp = gen.generate()
    assert fp["screen.colorDepth"] == 24
    assert fp["screen.pixelDepth"] == 24


def test_ten_generations_produce_distinct_ua_or_seeds(gen):
    fps = [gen.generate() for _ in range(10)]
    ua_set = {f["navigator.userAgent"] for f in fps}
    seed_set = {tuple(f["_seeds"].values()) for f in fps}
    # UAs may collide (limited variety), but seeds must all differ
    assert len(seed_set) == 10


def test_generate_with_geo_sets_geo_fields(gen):
    geo = {
        "country": "DE",
        "city": "Berlin",
        "timezone": "Europe/Berlin",
        "latitude": 52.52,
        "longitude": 13.405,
    }
    fp = gen.generate(GeneratorOptions(target_os="windows", target_geo=geo))
    assert fp["_geo"] == geo


def test_generate_without_geo_has_null_geo(gen):
    fp = gen.generate()
    assert fp["_geo"] is None


def test_generated_config_serializable_as_json(gen):
    import json
    fp = gen.generate()
    s = json.dumps(fp)
    fp_2 = json.loads(s)
    assert fp_2 == fp


def test_seeds_are_uint64_range(gen):
    fp = gen.generate()
    for v in fp["_seeds"].values():
        assert 0 <= v < 2**64
```

- [ ] **Step 2.2: Run, expect fail**

```bash
.venv/Scripts/python.exe -m pytest tests/unit/test_fingerprint_generator.py -v
```

- [ ] **Step 2.3: Implement**

Create `backend/services/fingerprint_generator.py`:
```python
"""High-level fingerprint generator. Wraps Camoufox's browserforge generator."""
from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Literal, TypedDict

from camoufox.fingerprints import from_browserforge, generate_fingerprint

GENERATOR_VERSION = "0.1.0"
SCHEMA_VERSION = 1

OSName = Literal["windows", "macos", "linux"]


class GeoInfo(TypedDict, total=False):
    country: str
    city: str
    timezone: str
    latitude: float
    longitude: float


@dataclass(frozen=True)
class GeneratorOptions:
    target_os: OSName | None = None
    target_geo: GeoInfo | None = None
    # Allow caller to pin specific values (rarely used)
    pinned_window: tuple[int, int] | None = None


class FingerprintGenerator:
    """Produces a consistent Camoufox config dict per call."""

    def generate(self, options: GeneratorOptions | None = None) -> dict[str, Any]:
        opts = options or GeneratorOptions()

        os_choice = opts.target_os
        if os_choice is None:
            from backend.core.datasets import OS_DISTRIBUTION, weighted_choice
            os_choice = weighted_choice(OS_DISTRIBUTION)

        fp = generate_fingerprint(os=(os_choice,), window=opts.pinned_window)
        config = from_browserforge(fp)

        config["_meta"] = {
            "schema_version": SCHEMA_VERSION,
            "generator_version": GENERATOR_VERSION,
            "generated_at": int(time.time() * 1000),
        }
        config["_os"] = os_choice
        config["_geo"] = dict(opts.target_geo) if opts.target_geo else None
        config["_seeds"] = {
            "canvas": secrets.randbits(64),
            "audio": secrets.randbits(64),
            "webgl_noise": secrets.randbits(64),
        }
        return config
```

- [ ] **Step 2.4: Run tests, all green**

```bash
.venv/Scripts/python.exe -m pytest tests/unit/test_fingerprint_generator.py -v
```
Expected: 14 passed.

- [ ] **Step 2.5: Commit**

```bash
git add backend/services/fingerprint_generator.py tests/unit/test_fingerprint_generator.py
git commit -m "feat(fingerprint): FingerprintGenerator wrapping browserforge with seeds + meta"
```

---

## Task 3: FingerprintValidator (TDD)

**Files:**
- Create: `backend/services/fingerprint_validator.py`
- Create: `tests/unit/test_fingerprint_validator.py`

The validator enforces consistency between OS / UA / platform / oscpu. Used both for sanity-checking generated configs and validating user-edited configs (PATCH endpoint, M2).

- [ ] **Step 3.1: Write failing tests**

Create `tests/unit/test_fingerprint_validator.py`:
```python
import pytest

from backend.services.fingerprint_generator import FingerprintGenerator, GeneratorOptions
from backend.services.fingerprint_validator import (
    FingerprintValidator,
    ValidationError,
)


@pytest.fixture
def validator() -> FingerprintValidator:
    return FingerprintValidator()


@pytest.fixture
def gen() -> FingerprintGenerator:
    return FingerprintGenerator()


def test_validate_freshly_generated_passes(validator, gen):
    for os_name in ("windows", "macos", "linux"):
        fp = gen.generate(GeneratorOptions(target_os=os_name))
        validator.validate(fp)  # no exception


def test_validate_missing_meta_fails(validator, gen):
    fp = gen.generate()
    del fp["_meta"]
    with pytest.raises(ValidationError, match="_meta"):
        validator.validate(fp)


def test_validate_missing_seeds_fails(validator, gen):
    fp = gen.generate()
    del fp["_seeds"]
    with pytest.raises(ValidationError, match="_seeds"):
        validator.validate(fp)


def test_validate_os_ua_mismatch_fails(validator, gen):
    fp = gen.generate(GeneratorOptions(target_os="windows"))
    fp["navigator.userAgent"] = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.5; rv:142.0) Gecko/20100101 Firefox/142.0"
    with pytest.raises(ValidationError, match="userAgent.*windows"):
        validator.validate(fp)


def test_validate_os_platform_mismatch_fails(validator, gen):
    fp = gen.generate(GeneratorOptions(target_os="windows"))
    fp["navigator.platform"] = "MacIntel"
    with pytest.raises(ValidationError, match="platform.*windows"):
        validator.validate(fp)


def test_validate_screen_negative_fails(validator, gen):
    fp = gen.generate()
    fp["screen.width"] = -1
    with pytest.raises(ValidationError, match="screen"):
        validator.validate(fp)


def test_validate_unknown_os_fails(validator, gen):
    fp = gen.generate()
    fp["_os"] = "amiga"
    with pytest.raises(ValidationError, match="_os"):
        validator.validate(fp)
```

- [ ] **Step 3.2: Run, expect fail**

```bash
.venv/Scripts/python.exe -m pytest tests/unit/test_fingerprint_validator.py -v
```

- [ ] **Step 3.3: Implement**

Create `backend/services/fingerprint_validator.py`:
```python
"""Consistency checks for fingerprint configs."""
from __future__ import annotations

from typing import Any


class ValidationError(ValueError):
    pass


_OS_TO_UA_TOKEN = {
    "windows": "Windows",
    "macos": "Mac",  # matches "Macintosh" or "Mac OS"
    "linux": "Linux",
}

_OS_TO_PLATFORM = {
    "windows": {"Win32", "Win64"},
    "macos": {"MacIntel", "Mac68K"},
    "linux": {"Linux x86_64", "Linux i686", "Linux armv81"},
}


class FingerprintValidator:
    def validate(self, fp: dict[str, Any]) -> None:
        for required in ("_meta", "_os", "_seeds"):
            if required not in fp:
                raise ValidationError(f"missing required field: {required}")

        os_name = fp["_os"]
        if os_name not in _OS_TO_UA_TOKEN:
            raise ValidationError(f"_os must be one of {list(_OS_TO_UA_TOKEN)}, got {os_name!r}")

        ua = fp.get("navigator.userAgent", "")
        if _OS_TO_UA_TOKEN[os_name] not in ua:
            raise ValidationError(
                f"navigator.userAgent inconsistent with _os={os_name!r}: {ua!r}"
            )

        platform = fp.get("navigator.platform", "")
        if platform not in _OS_TO_PLATFORM[os_name]:
            raise ValidationError(
                f"navigator.platform={platform!r} inconsistent with _os={os_name!r}"
            )

        for key in ("screen.width", "screen.height", "screen.availWidth", "screen.availHeight"):
            v = fp.get(key)
            if not isinstance(v, int) or v <= 0:
                raise ValidationError(f"screen field {key!r} must be positive int, got {v!r}")

        seeds = fp["_seeds"]
        for s in ("canvas", "audio", "webgl_noise"):
            if s not in seeds or not isinstance(seeds[s], int):
                raise ValidationError(f"_seeds.{s} missing or not int")
```

- [ ] **Step 3.4: Tests green**

```bash
.venv/Scripts/python.exe -m pytest tests/unit/test_fingerprint_validator.py -v
```
Expected: 7 passed.

- [ ] **Step 3.5: Commit**

```bash
git add backend/services/fingerprint_validator.py tests/unit/test_fingerprint_validator.py
git commit -m "feat(fingerprint): FingerprintValidator with OS/UA/platform consistency checks"
```

---

## Task 4: Profile, Proxy, Session models + Alembic migration

**Files:**
- Create: `backend/models/profile.py`
- Create: `backend/models/proxy.py`
- Create: `backend/models/session.py`
- Modify: `alembic/env.py` (import new models for autogen)
- Create: `alembic/versions/0002_profile_proxy_session.py`
- Create: `tests/unit/test_profile_model.py`

- [ ] **Step 4.1: Write model test**

Create `tests/unit/test_profile_model.py`:
```python
import time

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.models import Base
from backend.models.profile import Profile
from backend.models.proxy import Proxy
from backend.models.session import Session as SessionRow


def test_profile_defaults(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'p.db'}", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(engine, expire_on_commit=False)
    now = int(time.time() * 1000)
    with SessionLocal() as s:
        p = Profile(
            id="p-1",
            name="acc1",
            user_data_dir=str(tmp_path / "profiles" / "p-1"),
            fingerprint={"_os": "windows", "_seeds": {}, "_meta": {}},
            created_at=now,
            updated_at=now,
            status="new",
        )
        s.add(p)
        s.commit()
        loaded = s.query(Profile).filter_by(id="p-1").one()
        assert loaded.open_count == 0
        assert loaded.tags == []
        assert loaded.fingerprint["_os"] == "windows"


def test_proxy_basic(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'p.db'}", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(engine, expire_on_commit=False)
    now = int(time.time() * 1000)
    with SessionLocal() as s:
        s.add(Proxy(
            id="x-1", label="DE-1", type="http", host="1.2.3.4", port=8080,
            created_at=now, updated_at=now,
        ))
        s.commit()
        loaded = s.query(Proxy).filter_by(id="x-1").one()
        assert loaded.last_check_ok is False


def test_session_relation(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'p.db'}", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(engine, expire_on_commit=False)
    now = int(time.time() * 1000)
    with SessionLocal() as s:
        s.add(Profile(
            id="p-1", name="x", user_data_dir="/tmp/p-1",
            fingerprint={}, created_at=now, updated_at=now, status="new",
        ))
        s.add(SessionRow(id="s-1", profile_id="p-1", started_at=now))
        s.commit()
        loaded = s.query(SessionRow).filter_by(id="s-1").one()
        assert loaded.profile_id == "p-1"
```

- [ ] **Step 4.2: Run, expect fail**

```bash
.venv/Scripts/python.exe -m pytest tests/unit/test_profile_model.py -v
```

- [ ] **Step 4.3: Create Profile model**

Create `backend/models/profile.py`:
```python
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import BigInteger, Integer, String, Text, TypeDecorator
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class _JsonBlob(TypeDecorator):
    """Serializes/deserializes a dict to TEXT as JSON. Portable across SQLite/SQLCipher."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        return json.dumps(value, separators=(",", ":"))

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        return json.loads(value)


class _JsonList(_JsonBlob):
    """JSON-encoded list with [] default."""


class Profile(Base):
    __tablename__ = "profile"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str]] = mapped_column(_JsonList, nullable=False, default=list)
    color: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    last_opened_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    open_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="new")

    fingerprint: Mapped[dict] = mapped_column(_JsonBlob, nullable=False)
    proxy_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_data_dir: Mapped[str] = mapped_column(String, nullable=False)

    total_sessions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_duration_sec: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
```

- [ ] **Step 4.4: Create Proxy model (stub)**

Create `backend/models/proxy.py`:
```python
from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base
from backend.models.profile import _JsonList


class Proxy(Base):
    __tablename__ = "proxy"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    label: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String(16), nullable=False)  # http|https|socks5
    host: Mapped[str] = mapped_column(String, nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    username: Mapped[str | None] = mapped_column(String, nullable=True)
    password: Mapped[str | None] = mapped_column(String, nullable=True)

    last_checked_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_check_ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_ip: Mapped[str | None] = mapped_column(String, nullable=True)
    last_country: Mapped[str | None] = mapped_column(String(8), nullable=True)
    last_city: Mapped[str | None] = mapped_column(String, nullable=True)
    last_timezone: Mapped[str | None] = mapped_column(String, nullable=True)
    last_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    tags: Mapped[list[str]] = mapped_column(_JsonList, nullable=False, default=list)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
```

- [ ] **Step 4.5: Create Session model**

Create `backend/models/session.py`:
```python
from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class Session(Base):
    __tablename__ = "session"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    profile_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("profile.id", ondelete="CASCADE"), nullable=False
    )
    started_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    ended_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    duration_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    proxy_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("proxy.id", ondelete="SET NULL"), nullable=True
    )
    exit_ip: Mapped[str | None] = mapped_column(String, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
```

- [ ] **Step 4.6: Update `alembic/env.py` imports**

In `alembic/env.py`, after the existing `from backend.models.audit_log import AuditLog  # noqa: F401` add:
```python
from backend.models.profile import Profile  # noqa: F401
from backend.models.proxy import Proxy  # noqa: F401
from backend.models.session import Session as SessionRow  # noqa: F401
```

- [ ] **Step 4.7: Write migration**

Create `alembic/versions/0002_profile_proxy_session.py`:
```python
"""profile + proxy + session

Revision ID: 0002_profile_proxy_session
Revises: 0001_initial
Create Date: 2026-05-24
"""
from alembic import op
import sqlalchemy as sa


revision = "0002_profile_proxy_session"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "proxy",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("host", sa.String(), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(), nullable=True),
        sa.Column("password", sa.String(), nullable=True),
        sa.Column("last_checked_at", sa.BigInteger(), nullable=True),
        sa.Column("last_check_ok", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_ip", sa.String(), nullable=True),
        sa.Column("last_country", sa.String(8), nullable=True),
        sa.Column("last_city", sa.String(), nullable=True),
        sa.Column("last_timezone", sa.String(), nullable=True),
        sa.Column("last_latency_ms", sa.Integer(), nullable=True),
        sa.Column("tags", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=False),
    )
    op.create_index("idx_proxy_last_check", "proxy", ["last_checked_at"])

    op.create_table(
        "profile",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("tags", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("color", sa.String(16), nullable=True),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=False),
        sa.Column("last_opened_at", sa.BigInteger(), nullable=True),
        sa.Column("open_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False, server_default="new"),
        sa.Column("fingerprint", sa.Text(), nullable=False),
        sa.Column("proxy_id", sa.String(64), nullable=True),
        sa.Column("user_data_dir", sa.String(), nullable=False),
        sa.Column("total_sessions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_duration_sec", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("idx_profile_status", "profile", ["status"])
    op.create_index("idx_profile_last_opened", "profile", ["last_opened_at"])

    op.create_table(
        "session",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("profile_id", sa.String(64), nullable=False),
        sa.Column("started_at", sa.BigInteger(), nullable=False),
        sa.Column("ended_at", sa.BigInteger(), nullable=True),
        sa.Column("duration_sec", sa.Integer(), nullable=True),
        sa.Column("pid", sa.Integer(), nullable=True),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column("proxy_id", sa.String(64), nullable=True),
        sa.Column("exit_ip", sa.String(), nullable=True),
        sa.Column("user_agent", sa.String(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["profile_id"], ["profile.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["proxy_id"], ["proxy.id"], ondelete="SET NULL"),
    )
    op.create_index("idx_session_profile", "session", ["profile_id", "started_at"])


def downgrade() -> None:
    op.drop_index("idx_session_profile", table_name="session")
    op.drop_table("session")
    op.drop_index("idx_profile_last_opened", table_name="profile")
    op.drop_index("idx_profile_status", table_name="profile")
    op.drop_table("profile")
    op.drop_index("idx_proxy_last_check", table_name="proxy")
    op.drop_table("proxy")
```

- [ ] **Step 4.8: Run model tests green**

```bash
.venv/Scripts/python.exe -m pytest tests/unit/test_profile_model.py -v
```
Expected: 3 passed.

Also re-run M1 acceptance — must still pass (Alembic now applies 2 migrations on `initialize_with_password`):
```bash
.venv/Scripts/python.exe -m pytest tests/integration/test_m1_acceptance.py -v
```
Expected: 2 passed.

- [ ] **Step 4.9: Commit**

```bash
git add backend/models/profile.py backend/models/proxy.py backend/models/session.py alembic/env.py alembic/versions/0002_profile_proxy_session.py tests/unit/test_profile_model.py
git commit -m "feat(db): profile/proxy/session models + migration 0002"
```

---

## Task 5: App state container (unlocked engine + services)

**Files:**
- Create: `backend/core/app_state.py`
- Create: `backend/api/deps.py`
- Create: `tests/unit/test_app_state.py`

After `unlock`, the app holds: unlocked engine, session factory, services. Routes pull this via FastAPI's `Depends`. Before unlock, only `/healthz` and `/api/auth/*` work.

- [ ] **Step 5.1: Write failing test**

Create `tests/unit/test_app_state.py`:
```python
import pytest

from backend.core.app_state import AppState, NotUnlocked


def test_app_state_starts_locked():
    s = AppState()
    assert not s.is_unlocked()
    with pytest.raises(NotUnlocked):
        _ = s.engine


def test_set_unlocked_engine(tmp_path):
    from sqlalchemy import create_engine
    eng = create_engine("sqlite:///:memory:", future=True)
    s = AppState()
    s.set_unlocked(eng)
    assert s.is_unlocked()
    assert s.engine is eng
    assert s.session_factory is not None
    s.lock()
    assert not s.is_unlocked()
```

- [ ] **Step 5.2: Run, expect fail**

```bash
.venv/Scripts/python.exe -m pytest tests/unit/test_app_state.py -v
```

- [ ] **Step 5.3: Implement**

Create `backend/core/app_state.py`:
```python
"""Mutable app state — holds the unlocked DB engine and derived session factory."""
from __future__ import annotations

import threading

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker


class NotUnlocked(RuntimeError):
    pass


class AppState:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._engine: Engine | None = None
        self._session_factory: sessionmaker[Session] | None = None

    def is_unlocked(self) -> bool:
        with self._lock:
            return self._engine is not None

    @property
    def engine(self) -> Engine:
        with self._lock:
            if self._engine is None:
                raise NotUnlocked("app is locked — call /api/auth/unlock first")
            return self._engine

    @property
    def session_factory(self) -> sessionmaker[Session]:
        with self._lock:
            if self._session_factory is None:
                raise NotUnlocked("app is locked")
            return self._session_factory

    def set_unlocked(self, engine: Engine) -> None:
        with self._lock:
            self._engine = engine
            self._session_factory = sessionmaker(engine, expire_on_commit=False)

    def lock(self) -> None:
        with self._lock:
            if self._engine is not None:
                self._engine.dispose()
            self._engine = None
            self._session_factory = None
```

- [ ] **Step 5.4: Create deps module**

Create `backend/api/deps.py`:
```python
"""FastAPI dependency providers."""
from __future__ import annotations

from typing import Iterator

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.core.app_state import AppState, NotUnlocked


def get_app_state(request: Request) -> AppState:
    state: AppState | None = getattr(request.app.state, "app_state", None)
    if state is None:
        raise RuntimeError("AppState not attached to app.state")
    return state


def require_unlocked(state: AppState = Depends(get_app_state)) -> AppState:
    if not state.is_unlocked():
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="application is locked — POST /api/auth/unlock first",
        )
    return state


def get_db_session(state: AppState = Depends(require_unlocked)) -> Iterator[Session]:
    try:
        with state.session_factory() as session:
            yield session
    except NotUnlocked as exc:
        raise HTTPException(status_code=423, detail=str(exc)) from exc
```

- [ ] **Step 5.5: Tests green**

```bash
.venv/Scripts/python.exe -m pytest tests/unit/test_app_state.py -v
```
Expected: 2 passed.

- [ ] **Step 5.6: Commit**

```bash
git add backend/core/app_state.py backend/api/deps.py tests/unit/test_app_state.py
git commit -m "feat(core): AppState container + FastAPI deps (require_unlocked, get_db_session)"
```

---

## Task 6: ProfileService (CRUD + regenerate, TDD)

**Files:**
- Create: `backend/services/profile_service.py`
- Create: `tests/integration/test_profile_service.py`

- [ ] **Step 6.1: Write failing tests**

Create `tests/integration/test_profile_service.py`:
```python
import pytest

from backend.core.config import Settings
from backend.services.profile_service import (
    ProfileNotFound,
    ProfileService,
)
from backend.services.security_service import SecurityService


@pytest.fixture
def svc(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    settings = Settings()
    settings.ensure_dirs()
    security = SecurityService(settings)
    security.initialize_with_password("TestPassword!12")
    engine = security.unlock("TestPassword!12")
    from sqlalchemy.orm import sessionmaker
    sf = sessionmaker(engine, expire_on_commit=False)
    return ProfileService(session_factory=sf, settings=settings)


def test_create_profile_generates_fingerprint(svc):
    p = svc.create(name="acc-1")
    assert p.id
    assert p.name == "acc-1"
    assert p.fingerprint["_os"] in ("windows", "macos", "linux")
    assert p.fingerprint["_seeds"]["canvas"] > 0
    assert p.status == "new"
    # user_data_dir created
    from pathlib import Path
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


def test_delete_profile_removes_db_row_and_dir(svc, tmp_path):
    p = svc.create(name="dropme")
    from pathlib import Path
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
```

- [ ] **Step 6.2: Run, expect ImportError**

```bash
.venv/Scripts/python.exe -m pytest tests/integration/test_profile_service.py -v
```

- [ ] **Step 6.3: Implement**

Create `backend/services/profile_service.py`:
```python
"""Profile CRUD + regenerate."""
from __future__ import annotations

import shutil
import time
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from backend.core.config import Settings
from backend.models.profile import Profile
from backend.services.fingerprint_generator import (
    FingerprintGenerator,
    GeneratorOptions,
    OSName,
)


class ProfileNotFound(LookupError):
    pass


class ProfileService:
    def __init__(
        self,
        session_factory: sessionmaker,
        settings: Settings,
        generator: FingerprintGenerator | None = None,
    ) -> None:
        self._sf = session_factory
        self._settings = settings
        self._gen = generator or FingerprintGenerator()

    def create(
        self,
        *,
        name: str,
        notes: str | None = None,
        tags: list[str] | None = None,
        color: str | None = None,
        target_os: OSName | None = None,
    ) -> Profile:
        pid = str(uuid.uuid4())
        now = _now_ms()
        fp = self._gen.generate(GeneratorOptions(target_os=target_os))
        user_data_dir = self._settings.profiles_dir / pid
        user_data_dir.mkdir(parents=True, exist_ok=False)

        row = Profile(
            id=pid,
            name=name,
            notes=notes,
            tags=tags or [],
            color=color,
            created_at=now,
            updated_at=now,
            status="new",
            fingerprint=fp,
            user_data_dir=str(user_data_dir),
        )
        with self._sf() as s:
            s.add(row)
            s.commit()
            s.refresh(row)
            s.expunge(row)
        return row

    def list_profiles(self) -> list[Profile]:
        with self._sf() as s:
            rows = list(s.execute(select(Profile).order_by(Profile.created_at.desc())).scalars())
            for r in rows:
                s.expunge(r)
        return rows

    def get(self, profile_id: str) -> Profile:
        with self._sf() as s:
            row = s.execute(select(Profile).where(Profile.id == profile_id)).scalar_one_or_none()
            if row is None:
                raise ProfileNotFound(profile_id)
            s.expunge(row)
        return row

    def update(
        self,
        profile_id: str,
        *,
        name: str | None = None,
        notes: str | None = None,
        tags: list[str] | None = None,
        color: str | None = None,
    ) -> Profile:
        with self._sf() as s:
            row = s.execute(select(Profile).where(Profile.id == profile_id)).scalar_one_or_none()
            if row is None:
                raise ProfileNotFound(profile_id)
            if name is not None:
                row.name = name
            if notes is not None:
                row.notes = notes
            if tags is not None:
                row.tags = tags
            if color is not None:
                row.color = color
            row.updated_at = _now_ms()
            s.commit()
            s.refresh(row)
            s.expunge(row)
        return row

    def regenerate_fingerprint(
        self,
        profile_id: str,
        *,
        target_os: OSName | None = None,
    ) -> Profile:
        with self._sf() as s:
            row = s.execute(select(Profile).where(Profile.id == profile_id)).scalar_one_or_none()
            if row is None:
                raise ProfileNotFound(profile_id)
            row.fingerprint = self._gen.generate(GeneratorOptions(target_os=target_os))
            row.updated_at = _now_ms()
            s.commit()
            s.refresh(row)
            s.expunge(row)
        return row

    def delete(self, profile_id: str) -> None:
        with self._sf() as s:
            row = s.execute(select(Profile).where(Profile.id == profile_id)).scalar_one_or_none()
            if row is None:
                raise ProfileNotFound(profile_id)
            udd = Path(row.user_data_dir)
            s.delete(row)
            s.commit()
        if udd.exists():
            shutil.rmtree(udd, ignore_errors=True)


def _now_ms() -> int:
    return int(time.time() * 1000)
```

- [ ] **Step 6.4: Tests green**

```bash
.venv/Scripts/python.exe -m pytest tests/integration/test_profile_service.py -v
```
Expected: 9 passed.

- [ ] **Step 6.5: Commit**

```bash
git add backend/services/profile_service.py tests/integration/test_profile_service.py
git commit -m "feat(profiles): ProfileService with CRUD + regenerate_fingerprint"
```

---

## Task 7: Profile REST API endpoints

**Files:**
- Create: `backend/api/profiles.py`
- Create: `tests/integration/test_api_profiles.py`

- [ ] **Step 7.1: Write failing tests**

Create `tests/integration/test_api_profiles.py`:
```python
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.profiles import build_profiles_router
from backend.core.app_state import AppState
from backend.core.config import Settings
from backend.services.profile_service import ProfileService
from backend.services.security_service import SecurityService


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    settings = Settings()
    settings.ensure_dirs()
    security = SecurityService(settings)
    security.initialize_with_password("TestPass!1234")
    engine = security.unlock("TestPass!1234")

    state = AppState()
    state.set_unlocked(engine)
    svc = ProfileService(session_factory=state.session_factory, settings=settings)

    app = FastAPI()
    app.state.app_state = state
    app.include_router(build_profiles_router(svc))
    return TestClient(app)


def test_create_profile_returns_201(client):
    r = client.post("/api/profiles", json={"name": "acc-1"})
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "acc-1"
    assert "id" in body
    assert body["fingerprint"]["_os"] in ("windows", "macos", "linux")


def test_create_with_target_os(client):
    r = client.post("/api/profiles", json={"name": "win-only", "target_os": "windows"})
    assert r.status_code == 201
    assert r.json()["fingerprint"]["_os"] == "windows"


def test_list_profiles(client):
    client.post("/api/profiles", json={"name": "a"})
    client.post("/api/profiles", json={"name": "b"})
    r = client.get("/api/profiles")
    assert r.status_code == 200
    names = {p["name"] for p in r.json()}
    assert names == {"a", "b"}


def test_get_profile(client):
    created = client.post("/api/profiles", json={"name": "x"}).json()
    r = client.get(f"/api/profiles/{created['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]


def test_get_missing_returns_404(client):
    r = client.get("/api/profiles/missing")
    assert r.status_code == 404


def test_patch_profile(client):
    created = client.post("/api/profiles", json={"name": "old"}).json()
    r = client.patch(f"/api/profiles/{created['id']}", json={"name": "new", "notes": "hi"})
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "new"
    assert body["notes"] == "hi"


def test_regenerate_endpoint(client):
    created = client.post("/api/profiles", json={"name": "x", "target_os": "windows"}).json()
    old_seeds = created["fingerprint"]["_seeds"]
    r = client.post(f"/api/profiles/{created['id']}/regenerate", json={"target_os": "windows"})
    assert r.status_code == 200
    assert r.json()["fingerprint"]["_seeds"] != old_seeds


def test_delete_profile(client):
    created = client.post("/api/profiles", json={"name": "del"}).json()
    r = client.delete(f"/api/profiles/{created['id']}")
    assert r.status_code == 204
    r2 = client.get(f"/api/profiles/{created['id']}")
    assert r2.status_code == 404


def test_validate_endpoint_ok(client):
    created = client.post("/api/profiles", json={"name": "vx"}).json()
    r = client.post("/api/fingerprint/validate", json={"config": created["fingerprint"]})
    assert r.status_code == 200
    assert r.json() == {"valid": True}


def test_validate_endpoint_fail(client):
    created = client.post("/api/profiles", json={"name": "vy", "target_os": "windows"}).json()
    bad = dict(created["fingerprint"])
    bad["navigator.platform"] = "MacIntel"
    r = client.post("/api/fingerprint/validate", json={"config": bad})
    assert r.status_code == 422
    assert "platform" in r.json()["detail"]
```

- [ ] **Step 7.2: Run, expect fail**

```bash
.venv/Scripts/python.exe -m pytest tests/integration/test_api_profiles.py -v
```

- [ ] **Step 7.3: Implement**

Create `backend/api/profiles.py`:
```python
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from backend.services.fingerprint_validator import FingerprintValidator, ValidationError
from backend.services.profile_service import ProfileNotFound, ProfileService

OSLiteral = Literal["windows", "macos", "linux"]


class CreateProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    notes: str | None = None
    tags: list[str] | None = None
    color: str | None = None
    target_os: OSLiteral | None = None


class UpdateProfileIn(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    notes: str | None = None
    tags: list[str] | None = None
    color: str | None = None


class RegenerateIn(BaseModel):
    target_os: OSLiteral | None = None


class ValidateIn(BaseModel):
    config: dict[str, Any]


def _profile_to_dict(p) -> dict[str, Any]:
    return {
        "id": p.id,
        "name": p.name,
        "notes": p.notes,
        "tags": p.tags,
        "color": p.color,
        "created_at": p.created_at,
        "updated_at": p.updated_at,
        "last_opened_at": p.last_opened_at,
        "open_count": p.open_count,
        "status": p.status,
        "fingerprint": p.fingerprint,
        "proxy_id": p.proxy_id,
        "user_data_dir": p.user_data_dir,
        "total_sessions": p.total_sessions,
        "total_duration_sec": p.total_duration_sec,
    }


def build_profiles_router(svc: ProfileService) -> APIRouter:
    router = APIRouter(tags=["profiles"])
    validator = FingerprintValidator()

    @router.post("/api/profiles", status_code=status.HTTP_201_CREATED)
    def create(body: CreateProfileIn) -> dict[str, Any]:
        p = svc.create(
            name=body.name,
            notes=body.notes,
            tags=body.tags,
            color=body.color,
            target_os=body.target_os,
        )
        return _profile_to_dict(p)

    @router.get("/api/profiles")
    def list_all() -> list[dict[str, Any]]:
        return [_profile_to_dict(p) for p in svc.list_profiles()]

    @router.get("/api/profiles/{pid}")
    def get_one(pid: str) -> dict[str, Any]:
        try:
            return _profile_to_dict(svc.get(pid))
        except ProfileNotFound as exc:
            raise HTTPException(status_code=404, detail="profile not found") from exc

    @router.patch("/api/profiles/{pid}")
    def patch(pid: str, body: UpdateProfileIn) -> dict[str, Any]:
        try:
            return _profile_to_dict(svc.update(
                pid,
                name=body.name,
                notes=body.notes,
                tags=body.tags,
                color=body.color,
            ))
        except ProfileNotFound as exc:
            raise HTTPException(status_code=404, detail="profile not found") from exc

    @router.post("/api/profiles/{pid}/regenerate")
    def regenerate(pid: str, body: RegenerateIn) -> dict[str, Any]:
        try:
            return _profile_to_dict(svc.regenerate_fingerprint(pid, target_os=body.target_os))
        except ProfileNotFound as exc:
            raise HTTPException(status_code=404, detail="profile not found") from exc

    @router.delete("/api/profiles/{pid}", status_code=status.HTTP_204_NO_CONTENT)
    def delete(pid: str) -> None:
        try:
            svc.delete(pid)
        except ProfileNotFound as exc:
            raise HTTPException(status_code=404, detail="profile not found") from exc

    @router.post("/api/fingerprint/validate")
    def validate(body: ValidateIn) -> dict[str, Any]:
        try:
            validator.validate(body.config)
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"valid": True}

    return router
```

- [ ] **Step 7.4: Tests green**

```bash
.venv/Scripts/python.exe -m pytest tests/integration/test_api_profiles.py -v
```
Expected: 10 passed.

- [ ] **Step 7.5: Commit**

```bash
git add backend/api/profiles.py tests/integration/test_api_profiles.py
git commit -m "feat(api): /api/profiles CRUD + /regenerate + /fingerprint/validate"
```

---

## Task 8: LaunchManager (subprocess control)

**Files:**
- Create: `backend/services/launch_manager.py`
- Create: `tests/unit/test_launch_manager.py`

Camoufox's Python SDK uses Playwright/Marionette under the hood — convenient for control but heavy. For our LaunchManager we use the simpler path: build `launch_options(config=…, proxy=…, executable_path=…, user_data_dir=…)`, then start a `Camoufox` instance in a background thread (since the user must close the window via UI, not programmatically).

Actually simpler still: use `subprocess.Popen` to spawn `camoufox.exe` directly with the JSON config. Camoufox reads its config from stdin or env vars. For v1 we use the **Camoufox Python SDK path** — wrap `Camoufox(**launch_options).start()` in a thread, store the resulting Browser handle in a registry, expose `.stop()` to close it.

To keep tests deterministic and not depend on a real Camoufox binary, we abstract launching behind a `Launcher` protocol with a real impl and a fake impl for tests.

- [ ] **Step 8.1: Write failing tests with fake launcher**

Create `tests/unit/test_launch_manager.py`:
```python
import time

import pytest

from backend.services.launch_manager import (
    LaunchManager,
    LaunchHandle,
    LaunchError,
    Launcher,
)


class FakeHandle(LaunchHandle):
    def __init__(self, pid: int):
        self._pid = pid
        self._alive = True

    @property
    def pid(self) -> int:
        return self._pid

    def is_alive(self) -> bool:
        return self._alive

    def stop(self) -> None:
        self._alive = False


class FakeLauncher(Launcher):
    def __init__(self):
        self._next_pid = 1000

    def launch(self, *, profile_id, user_data_dir, fingerprint, proxy):
        self._next_pid += 1
        return FakeHandle(self._next_pid)


def test_launch_registers_handle():
    mgr = LaunchManager(FakeLauncher())
    h = mgr.launch(profile_id="p1", user_data_dir="/tmp/p1", fingerprint={}, proxy=None)
    assert h.pid > 0
    assert mgr.is_running("p1")
    assert mgr.get_handle("p1") is h


def test_double_launch_same_profile_raises():
    mgr = LaunchManager(FakeLauncher())
    mgr.launch(profile_id="p1", user_data_dir="/tmp/p1", fingerprint={}, proxy=None)
    with pytest.raises(LaunchError, match="already running"):
        mgr.launch(profile_id="p1", user_data_dir="/tmp/p1", fingerprint={}, proxy=None)


def test_stop_removes_from_registry():
    mgr = LaunchManager(FakeLauncher())
    mgr.launch(profile_id="p1", user_data_dir="/tmp/p1", fingerprint={}, proxy=None)
    mgr.stop("p1")
    assert not mgr.is_running("p1")


def test_stop_unknown_is_noop():
    mgr = LaunchManager(FakeLauncher())
    mgr.stop("missing")  # no exception


def test_running_profiles_list():
    mgr = LaunchManager(FakeLauncher())
    mgr.launch(profile_id="a", user_data_dir="/tmp/a", fingerprint={}, proxy=None)
    mgr.launch(profile_id="b", user_data_dir="/tmp/b", fingerprint={}, proxy=None)
    assert set(mgr.running_profiles()) == {"a", "b"}
```

- [ ] **Step 8.2: Run, expect fail**

```bash
.venv/Scripts/python.exe -m pytest tests/unit/test_launch_manager.py -v
```

- [ ] **Step 8.3: Implement**

Create `backend/services/launch_manager.py`:
```python
"""Manages launch lifecycle for Camoufox subprocesses."""
from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from typing import Any


class LaunchError(RuntimeError):
    pass


class LaunchHandle(ABC):
    @property
    @abstractmethod
    def pid(self) -> int: ...

    @abstractmethod
    def is_alive(self) -> bool: ...

    @abstractmethod
    def stop(self) -> None: ...


class Launcher(ABC):
    @abstractmethod
    def launch(
        self,
        *,
        profile_id: str,
        user_data_dir: str,
        fingerprint: dict[str, Any],
        proxy: dict[str, Any] | None,
    ) -> LaunchHandle: ...


class LaunchManager:
    def __init__(self, launcher: Launcher) -> None:
        self._launcher = launcher
        self._lock = threading.RLock()
        self._handles: dict[str, LaunchHandle] = {}

    def launch(
        self,
        *,
        profile_id: str,
        user_data_dir: str,
        fingerprint: dict[str, Any],
        proxy: dict[str, Any] | None = None,
    ) -> LaunchHandle:
        with self._lock:
            existing = self._handles.get(profile_id)
            if existing is not None and existing.is_alive():
                raise LaunchError(f"profile {profile_id} already running")
            handle = self._launcher.launch(
                profile_id=profile_id,
                user_data_dir=user_data_dir,
                fingerprint=fingerprint,
                proxy=proxy,
            )
            self._handles[profile_id] = handle
            return handle

    def stop(self, profile_id: str) -> None:
        with self._lock:
            h = self._handles.pop(profile_id, None)
            if h is not None:
                try:
                    h.stop()
                except Exception:
                    pass

    def is_running(self, profile_id: str) -> bool:
        with self._lock:
            h = self._handles.get(profile_id)
            return h is not None and h.is_alive()

    def get_handle(self, profile_id: str) -> LaunchHandle | None:
        with self._lock:
            return self._handles.get(profile_id)

    def running_profiles(self) -> list[str]:
        with self._lock:
            return [pid for pid, h in self._handles.items() if h.is_alive()]
```

- [ ] **Step 8.4: Tests green**

```bash
.venv/Scripts/python.exe -m pytest tests/unit/test_launch_manager.py -v
```
Expected: 5 passed.

- [ ] **Step 8.5: Commit**

```bash
git add backend/services/launch_manager.py tests/unit/test_launch_manager.py
git commit -m "feat(launch): LaunchManager + Launcher abstraction with thread-safe registry"
```

---

## Task 9: CamoufoxLauncher (real launcher)

**Files:**
- Create: `backend/services/camoufox_launcher.py`
- Create: `tests/integration/test_camoufox_launcher_smoke.py` (marked `slow`)

- [ ] **Step 9.1: Implement real launcher**

Create `backend/services/camoufox_launcher.py`:
```python
"""Real launcher: spawns Camoufox in a background thread using its sync API."""
from __future__ import annotations

import threading
from typing import Any

from camoufox.sync_api import Camoufox

from backend.services.launch_manager import LaunchError, LaunchHandle, Launcher


class CamoufoxHandle(LaunchHandle):
    def __init__(self, browser_ctx_mgr_thread: threading.Thread, stopper: threading.Event, pid_ref: list[int]):
        self._thread = browser_ctx_mgr_thread
        self._stop = stopper
        self._pid_ref = pid_ref

    @property
    def pid(self) -> int:
        return self._pid_ref[0] if self._pid_ref else -1

    def is_alive(self) -> bool:
        return self._thread.is_alive()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=15)


class CamoufoxLauncher(Launcher):
    """Spawns Camoufox in a background thread.

    Each launch runs `with Camoufox(...) as browser:` and blocks on a stop event
    until `.stop()` is called. The thread cleans up on exit.
    """

    def launch(
        self,
        *,
        profile_id: str,
        user_data_dir: str,
        fingerprint: dict[str, Any],
        proxy: dict[str, Any] | None,
    ) -> LaunchHandle:
        stopper = threading.Event()
        pid_ref: list[int] = []
        ready = threading.Event()
        err_ref: list[BaseException] = []

        def runner() -> None:
            try:
                with Camoufox(
                    config=fingerprint,
                    proxy=proxy,
                    user_data_dir=user_data_dir,
                    persistent_context=True,
                    headless=False,
                ) as browser:
                    pid_ref.append(_extract_pid(browser))
                    ready.set()
                    # block until user closes window OR caller asks us to stop
                    while not stopper.is_set():
                        if not _browser_alive(browser):
                            break
                        stopper.wait(0.5)
            except BaseException as exc:  # noqa: BLE001
                err_ref.append(exc)
                ready.set()

        t = threading.Thread(target=runner, name=f"camoufox-{profile_id}", daemon=True)
        t.start()
        if not ready.wait(timeout=60):
            stopper.set()
            t.join(timeout=5)
            raise LaunchError("Camoufox failed to start within 60s")
        if err_ref:
            raise LaunchError(f"Camoufox launch failed: {err_ref[0]!r}") from err_ref[0]
        return CamoufoxHandle(t, stopper, pid_ref)


def _extract_pid(browser: Any) -> int:
    """Best-effort PID extraction from a Playwright Browser/BrowserContext."""
    try:
        # BrowserContext has .browser; Browser has internal channel with pid
        ctx = browser
        b = getattr(ctx, "browser", None) or ctx
        process = getattr(b, "_impl_obj", None) and getattr(b._impl_obj, "_browser_process", None)
        if process is not None and hasattr(process, "pid"):
            return process.pid
    except Exception:
        pass
    return -1


def _browser_alive(browser: Any) -> bool:
    try:
        return browser.is_connected() if hasattr(browser, "is_connected") else True
    except Exception:
        return False
```

NOTE: We use `persistent_context=True` so Camoufox uses `user_data_dir` properly. `config=fingerprint` accepts our augmented dict (Camoufox passes unknown keys with `_` prefix through unchanged — they're stored as part of profile metadata but ignored by Camoufox C++).

- [ ] **Step 9.2: Smoke test (slow, opt-in)**

Create `tests/integration/test_camoufox_launcher_smoke.py`:
```python
"""Real Camoufox launcher — slow, opens a real browser window. Marked 'slow'."""
import os
import time

import pytest

from backend.services.camoufox_launcher import CamoufoxLauncher
from backend.services.fingerprint_generator import FingerprintGenerator
from backend.services.launch_manager import LaunchManager


@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("PB_SKIP_CAMOUFOX_SMOKE") == "1",
    reason="Camoufox smoke test skipped via PB_SKIP_CAMOUFOX_SMOKE=1",
)
def test_real_camoufox_launches_and_stops(tmp_path):
    udd = tmp_path / "udd"
    udd.mkdir()
    fp = FingerprintGenerator().generate()
    mgr = LaunchManager(CamoufoxLauncher())
    h = mgr.launch(
        profile_id="smoke-1",
        user_data_dir=str(udd),
        fingerprint=fp,
        proxy=None,
    )
    assert h.is_alive()
    # quickly stop
    time.sleep(2)
    mgr.stop("smoke-1")
    # thread should join within a few seconds
    t0 = time.monotonic()
    while h.is_alive() and time.monotonic() - t0 < 20:
        time.sleep(0.2)
    assert not h.is_alive()
```

Add to `pyproject.toml` under `[tool.pytest.ini_options]`:
```toml
markers = ["slow: opt-in slow tests (real Camoufox launches)"]
```

- [ ] **Step 9.3: Run smoke (opt-in, manual)**

```bash
.venv/Scripts/python.exe -m pytest tests/integration/test_camoufox_launcher_smoke.py -v -m slow
```
Expected: real Camoufox window opens, then closes within ~5s. PASSED.
If fails (sandbox, missing executable_path) — debug separately.

For default CI runs, skip slow:
```bash
.venv/Scripts/python.exe -m pytest -q -m "not slow"
```

- [ ] **Step 9.4: Commit**

```bash
git add backend/services/camoufox_launcher.py tests/integration/test_camoufox_launcher_smoke.py pyproject.toml
git commit -m "feat(launch): CamoufoxLauncher (real subprocess launcher) + opt-in smoke test"
```

---

## Task 10: /api/profiles/{id}/launch + /stop endpoints

**Files:**
- Create: `backend/api/launch.py`
- Create: `tests/integration/test_api_launch.py`

- [ ] **Step 10.1: Failing test using FakeLauncher injection**

Create `tests/integration/test_api_launch.py`:
```python
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.launch import build_launch_router
from backend.api.profiles import build_profiles_router
from backend.core.app_state import AppState
from backend.core.config import Settings
from backend.services.launch_manager import LaunchManager
from backend.services.profile_service import ProfileService
from backend.services.security_service import SecurityService
from tests.unit.test_launch_manager import FakeLauncher  # reuse fake


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    settings = Settings()
    settings.ensure_dirs()
    sec = SecurityService(settings)
    sec.initialize_with_password("TestPass!1234")
    engine = sec.unlock("TestPass!1234")
    state = AppState()
    state.set_unlocked(engine)

    svc = ProfileService(session_factory=state.session_factory, settings=settings)
    mgr = LaunchManager(FakeLauncher())

    app = FastAPI()
    app.state.app_state = state
    app.include_router(build_profiles_router(svc))
    app.include_router(build_launch_router(svc, mgr))
    return TestClient(app)


def test_launch_profile(client):
    created = client.post("/api/profiles", json={"name": "x"}).json()
    r = client.post(f"/api/profiles/{created['id']}/launch")
    assert r.status_code == 200
    assert r.json()["status"] == "running"


def test_launch_unknown_returns_404(client):
    r = client.post("/api/profiles/missing/launch")
    assert r.status_code == 404


def test_double_launch_returns_409(client):
    created = client.post("/api/profiles", json={"name": "x"}).json()
    client.post(f"/api/profiles/{created['id']}/launch")
    r = client.post(f"/api/profiles/{created['id']}/launch")
    assert r.status_code == 409


def test_stop_profile(client):
    created = client.post("/api/profiles", json={"name": "x"}).json()
    client.post(f"/api/profiles/{created['id']}/launch")
    r = client.post(f"/api/profiles/{created['id']}/stop")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"


def test_stop_not_running_is_idempotent(client):
    created = client.post("/api/profiles", json={"name": "x"}).json()
    r = client.post(f"/api/profiles/{created['id']}/stop")
    assert r.status_code == 200
```

- [ ] **Step 10.2: Implement**

Create `backend/api/launch.py`:
```python
from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException

from backend.services.launch_manager import LaunchError, LaunchManager
from backend.services.profile_service import ProfileNotFound, ProfileService


def build_launch_router(svc: ProfileService, mgr: LaunchManager) -> APIRouter:
    router = APIRouter(tags=["launch"])

    @router.post("/api/profiles/{pid}/launch")
    def launch(pid: str) -> dict:
        try:
            p = svc.get(pid)
        except ProfileNotFound as exc:
            raise HTTPException(status_code=404, detail="profile not found") from exc
        try:
            handle = mgr.launch(
                profile_id=pid,
                user_data_dir=p.user_data_dir,
                fingerprint=p.fingerprint,
                proxy=None,  # M3 will wire proxy lookup
            )
        except LaunchError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        svc.update_status(pid, status_value="running", last_opened_at=int(time.time() * 1000))
        return {"status": "running", "pid": handle.pid}

    @router.post("/api/profiles/{pid}/stop")
    def stop(pid: str) -> dict:
        try:
            svc.get(pid)
        except ProfileNotFound as exc:
            raise HTTPException(status_code=404, detail="profile not found") from exc
        mgr.stop(pid)
        svc.update_status(pid, status_value="ready")
        return {"status": "ready"}

    return router
```

- [ ] **Step 10.3: Add `update_status` to ProfileService**

Append to `backend/services/profile_service.py` inside the class:
```python
    def update_status(
        self,
        profile_id: str,
        *,
        status_value: str,
        last_opened_at: int | None = None,
    ) -> Profile:
        with self._sf() as s:
            row = s.execute(select(Profile).where(Profile.id == profile_id)).scalar_one_or_none()
            if row is None:
                raise ProfileNotFound(profile_id)
            row.status = status_value
            if last_opened_at is not None:
                row.last_opened_at = last_opened_at
                row.open_count = (row.open_count or 0) + 1
            row.updated_at = _now_ms()
            s.commit()
            s.refresh(row)
            s.expunge(row)
        return row
```

- [ ] **Step 10.4: Tests green**

```bash
.venv/Scripts/python.exe -m pytest tests/integration/test_api_launch.py tests/integration/test_profile_service.py -v
```
Expected: 5 + 9 = 14 passed.

- [ ] **Step 10.5: Commit**

```bash
git add backend/api/launch.py backend/services/profile_service.py tests/integration/test_api_launch.py
git commit -m "feat(api): /api/profiles/{id}/launch and /stop with ProfileService.update_status"
```

---

## Task 11: Wire profiles + launch into app, gate by unlock

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 11.1: Modify main.py**

Replace `backend/main.py` with:
```python
"""FastAPI application entry point."""
from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog
from fastapi import FastAPI

from backend.api.auth import build_auth_router
from backend.api.launch import build_launch_router
from backend.api.middleware.auth_token import APITokenMiddleware
from backend.api.profiles import build_profiles_router
from backend.core.app_state import AppState
from backend.core.config import Settings
from backend.core.logging import configure_logging
from backend.core.security import generate_api_token
from backend.services.camoufox_launcher import CamoufoxLauncher
from backend.services.launch_manager import LaunchManager
from backend.services.profile_service import ProfileService
from backend.services.security_service import SecurityService


def create_app() -> FastAPI:
    settings = Settings()
    settings.ensure_dirs()
    configure_logging(settings.logs_dir)
    log = structlog.get_logger("private-browser.startup")

    token = generate_api_token()
    settings.api_token = token

    state = AppState()
    security = SecurityService(settings)
    launch_mgr = LaunchManager(CamoufoxLauncher())

    @asynccontextmanager
    async def lifespan(app_: FastAPI) -> AsyncIterator[None]:
        log.info("app.start", port=settings.api_port, host=settings.api_host)
        print(f"PB_API_TOKEN={token}", flush=True, file=sys.stdout)
        try:
            yield
        finally:
            for pid in list(launch_mgr.running_profiles()):
                launch_mgr.stop(pid)
            state.lock()
            log.info("app.stop")

    app = FastAPI(title="private-browser", version="0.2.0", lifespan=lifespan)
    app.state.app_state = state
    app.state.settings = settings
    app.add_middleware(
        APITokenMiddleware,
        token=token,
        exempt_paths=("/healthz", "/docs", "/openapi.json", "/redoc"),
    )

    @app.get("/healthz")
    async def healthz() -> dict:
        return {"ok": True, "unlocked": state.is_unlocked()}

    # Auth router needs SecurityService + the AppState (so it can set engine on unlock)
    app.include_router(_build_auth_router_with_state(security, state))

    # Profiles + Launch require unlocked state. We build the routers lazily on
    # the first unlocked request to avoid binding to a non-existent session_factory.
    # Simpler: use deps to fetch state per-request inside the route bodies.
    # For this milestone we attach service builders to app.state and the route
    # functions resolve them via the unlocked state.
    app.include_router(_lazy_profiles_router(state, settings))
    app.include_router(_lazy_launch_router(state, settings, launch_mgr))
    return app


def _build_auth_router_with_state(security: SecurityService, state: AppState):
    from fastapi import APIRouter, HTTPException, status
    from pydantic import BaseModel, Field

    from backend.services.security_service import (
        AlreadyInitialized,
        InvalidPassword,
        NotInitialized,
    )

    class _PasswordIn(BaseModel):
        password: str = Field(min_length=12, max_length=512)

    router = APIRouter(prefix="/api/auth", tags=["auth"])

    @router.post("/initialize", status_code=status.HTTP_201_CREATED)
    def initialize(body: _PasswordIn) -> dict:
        try:
            security.initialize_with_password(body.password)
        except AlreadyInitialized as exc:
            raise HTTPException(status_code=409, detail="already initialized") from exc
        return {"ok": True}

    @router.post("/unlock", status_code=status.HTTP_200_OK)
    def unlock(body: _PasswordIn) -> dict:
        try:
            engine = security.unlock(body.password)
        except NotInitialized as exc:
            raise HTTPException(status_code=412, detail="not initialized") from exc
        except InvalidPassword as exc:
            raise HTTPException(status_code=401, detail="invalid password") from exc
        state.set_unlocked(engine)
        return {"ok": True, "unlocked": True}

    @router.post("/lock", status_code=status.HTTP_200_OK)
    def lock() -> dict:
        state.lock()
        return {"ok": True, "unlocked": False}

    return router


def _lazy_profiles_router(state: AppState, settings: Settings):
    from fastapi import APIRouter, HTTPException

    from backend.api.profiles import build_profiles_router
    from backend.services.profile_service import ProfileService

    outer = APIRouter()

    def make_svc() -> ProfileService:
        if not state.is_unlocked():
            raise HTTPException(status_code=423, detail="app locked")
        return ProfileService(session_factory=state.session_factory, settings=settings)

    @outer.api_route("/api/profiles{rest:path}", methods=["GET", "POST", "PATCH", "DELETE"])
    @outer.api_route("/api/fingerprint{rest:path}", methods=["POST"])
    def _dispatch(rest: str):  # placeholder to ensure import
        raise HTTPException(status_code=500, detail="should not be reached")

    # Replace placeholder with real router that resolves svc per-request:
    # Simpler approach — inject a per-request svc by overriding include_router with a sub-app
    # using FastAPI's dependency_overrides is complex; for v1 we accept that profiles
    # endpoints only work after unlock, and we re-build the router once.
    inner = APIRouter()

    async def gate_unlocked():
        if not state.is_unlocked():
            raise HTTPException(status_code=423, detail="app locked — POST /api/auth/unlock")

    # Build a fresh ProfileService per request via a closure
    def _resolve_svc() -> ProfileService:
        return ProfileService(session_factory=state.session_factory, settings=settings)

    # Use the existing build_profiles_router but with a per-request resolver
    from backend.api import profiles as _profiles_mod
    # Build router that resolves svc lazily — wrap the existing factory
    from backend.api.profiles import (
        CreateProfileIn,
        RegenerateIn,
        UpdateProfileIn,
        ValidateIn,
        _profile_to_dict,
    )
    from backend.services.fingerprint_validator import FingerprintValidator, ValidationError
    from backend.services.profile_service import ProfileNotFound
    from fastapi import status as _status

    validator = FingerprintValidator()

    @inner.post("/api/profiles", status_code=_status.HTTP_201_CREATED, dependencies=[Depends(gate_unlocked)])
    def create(body: CreateProfileIn):
        svc = _resolve_svc()
        p = svc.create(name=body.name, notes=body.notes, tags=body.tags, color=body.color, target_os=body.target_os)
        return _profile_to_dict(p)

    @inner.get("/api/profiles", dependencies=[Depends(gate_unlocked)])
    def list_all():
        return [_profile_to_dict(p) for p in _resolve_svc().list_profiles()]

    @inner.get("/api/profiles/{pid}", dependencies=[Depends(gate_unlocked)])
    def get_one(pid: str):
        try:
            return _profile_to_dict(_resolve_svc().get(pid))
        except ProfileNotFound:
            raise HTTPException(status_code=404, detail="profile not found")

    @inner.patch("/api/profiles/{pid}", dependencies=[Depends(gate_unlocked)])
    def patch(pid: str, body: UpdateProfileIn):
        try:
            return _profile_to_dict(_resolve_svc().update(pid, name=body.name, notes=body.notes, tags=body.tags, color=body.color))
        except ProfileNotFound:
            raise HTTPException(status_code=404, detail="profile not found")

    @inner.post("/api/profiles/{pid}/regenerate", dependencies=[Depends(gate_unlocked)])
    def regenerate(pid: str, body: RegenerateIn):
        try:
            return _profile_to_dict(_resolve_svc().regenerate_fingerprint(pid, target_os=body.target_os))
        except ProfileNotFound:
            raise HTTPException(status_code=404, detail="profile not found")

    @inner.delete("/api/profiles/{pid}", status_code=_status.HTTP_204_NO_CONTENT, dependencies=[Depends(gate_unlocked)])
    def delete(pid: str):
        try:
            _resolve_svc().delete(pid)
        except ProfileNotFound:
            raise HTTPException(status_code=404, detail="profile not found")

    @inner.post("/api/fingerprint/validate", dependencies=[Depends(gate_unlocked)])
    def validate(body: ValidateIn):
        try:
            validator.validate(body.config)
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        return {"valid": True}

    return inner


def _lazy_launch_router(state: AppState, settings: Settings, mgr: LaunchManager):
    from fastapi import APIRouter, Depends, HTTPException
    import time as _time

    async def gate_unlocked():
        if not state.is_unlocked():
            raise HTTPException(status_code=423, detail="app locked")

    def _resolve_svc():
        return ProfileService(session_factory=state.session_factory, settings=settings)

    inner = APIRouter()

    @inner.post("/api/profiles/{pid}/launch", dependencies=[Depends(gate_unlocked)])
    def launch(pid: str):
        svc = _resolve_svc()
        from backend.services.profile_service import ProfileNotFound
        from backend.services.launch_manager import LaunchError
        try:
            p = svc.get(pid)
        except ProfileNotFound:
            raise HTTPException(status_code=404, detail="profile not found")
        try:
            handle = mgr.launch(
                profile_id=pid,
                user_data_dir=p.user_data_dir,
                fingerprint=p.fingerprint,
                proxy=None,
            )
        except LaunchError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        svc.update_status(pid, status_value="running", last_opened_at=int(_time.time() * 1000))
        return {"status": "running", "pid": handle.pid}

    @inner.post("/api/profiles/{pid}/stop", dependencies=[Depends(gate_unlocked)])
    def stop(pid: str):
        svc = _resolve_svc()
        from backend.services.profile_service import ProfileNotFound
        try:
            svc.get(pid)
        except ProfileNotFound:
            raise HTTPException(status_code=404, detail="profile not found")
        mgr.stop(pid)
        svc.update_status(pid, status_value="ready")
        return {"status": "ready"}

    return inner


app = create_app()
```

NOTE: The lazy router pattern above is intentional and pragmatic — we avoid `Depends` parameters that pass services through, instead resolving them from `state` per-request via closure. The `_lazy_profiles_router` duplicates routes from `build_profiles_router` because the latter requires services up-front. This is acceptable for v1; we can refactor to proper `Depends`-based wiring later when M4 adds WebSocket support.

Also add at the top of `_lazy_profiles_router` the missing `from fastapi import Depends`:
```python
from fastapi import APIRouter, Depends, HTTPException
```

- [ ] **Step 11.2: Quick smoke — start app, hit healthz**

```bash
cd "/c/Users/kirill/Desktop/code/private-browser"
.venv/Scripts/python.exe -c "from backend.main import app; print('ok')"
```
Expected: prints `ok`. If imports fail, fix typos in main.py.

- [ ] **Step 11.3: Run ALL tests to ensure nothing regressed**

```bash
.venv/Scripts/python.exe -m pytest -q -m "not slow"
```
Expected: all green.

- [ ] **Step 11.4: Commit**

```bash
git add backend/main.py
git commit -m "feat(app): wire profiles + launch routers behind unlock gate"
```

---

## Task 12: M2 acceptance test

**Files:**
- Create: `tests/integration/test_m2_acceptance.py`

- [ ] **Step 12.1: Write end-to-end acceptance**

```python
"""M2 acceptance: 10 profiles via API, each with unique consistent fingerprint."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.core.config import Settings


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    from backend.main import create_app
    app = create_app()
    # Pluck the token from app state — it was generated in create_app
    settings: Settings = app.state.settings
    token = settings.api_token

    c = TestClient(app)
    c.headers["X-PB-Token"] = token
    return c


def test_create_unlock_and_ten_profiles(client):
    # Initialize + unlock
    r = client.post("/api/auth/initialize", json={"password": "M2Acceptance!12"})
    assert r.status_code == 201
    r = client.post("/api/auth/unlock", json={"password": "M2Acceptance!12"})
    assert r.status_code == 200

    # Before unlock would have been 423, after unlock it's allowed
    created = []
    for i in range(10):
        r = client.post("/api/profiles", json={"name": f"p-{i}"})
        assert r.status_code == 201
        created.append(r.json())

    # All seeds distinct
    seed_tuples = {tuple(p["fingerprint"]["_seeds"].values()) for p in created}
    assert len(seed_tuples) == 10

    # Each fingerprint passes our validator endpoint
    for p in created:
        r = client.post("/api/fingerprint/validate", json={"config": p["fingerprint"]})
        assert r.status_code == 200, r.text

    # GET /api/profiles returns all 10
    r = client.get("/api/profiles")
    assert r.status_code == 200
    assert len(r.json()) == 10


def test_profiles_locked_before_unlock(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    from backend.main import create_app
    app = create_app()
    c = TestClient(app)
    c.headers["X-PB-Token"] = app.state.settings.api_token

    client_unlocked = c
    r = client_unlocked.get("/api/profiles")
    assert r.status_code == 423
```

- [ ] **Step 12.2: Run**

```bash
.venv/Scripts/python.exe -m pytest tests/integration/test_m2_acceptance.py -v
```
Expected: 2 passed.

- [ ] **Step 12.3: Run full suite (no slow)**

```bash
.venv/Scripts/python.exe -m pytest -q -m "not slow"
```
Expected: 0 failures.

- [ ] **Step 12.4: Commit**

```bash
git add tests/integration/test_m2_acceptance.py
git commit -m "test: M2 acceptance — 10 profiles via API with unique fingerprints"
```

---

## Task 13: M2 review checkpoint

- [ ] **Step 13.1: Lint check**

```bash
.venv/Scripts/python.exe -m ruff check .
```
Fix any issues, recommit.

- [ ] **Step 13.2: Manual real-Camoufox smoke (best-effort, opt-in)**

```bash
.venv/Scripts/python.exe -m pytest tests/integration/test_camoufox_launcher_smoke.py -v -m slow
```
Expected: real Camoufox window opens, closes after 2s. PASSED.

If failures (Defender blocked, missing binary, etc.) — fix per Plan 1 Task 2 dev setup or document in `docs/dev-machine-setup.md` known-issues section, then proceed.

- [ ] **Step 13.3: Update CHANGELOG**

Prepend to `CHANGELOG.md`:
```markdown
## [v0.2.0-m2] — 2026-XX-XX

### Added
- `FingerprintGenerator` wrapping Camoufox/Browserforge with per-profile canvas/audio/webgl seeds
- `FingerprintValidator` enforcing OS↔UA↔platform consistency
- Profile / Proxy / Session SQLAlchemy models
- Alembic migration 0002 (profile + proxy + session tables)
- `ProfileService` (CRUD, regenerate fingerprint)
- `LaunchManager` + `Launcher` protocol; `CamoufoxLauncher` real implementation
- REST endpoints: `POST/GET/PATCH/DELETE /api/profiles`, `POST /api/profiles/{id}/regenerate`, `POST /api/fingerprint/validate`, `POST /api/profiles/{id}/launch`, `POST /api/profiles/{id}/stop`
- `AppState` container holding unlocked engine; routes gated by `unlocked` check (423 otherwise)
- `POST /api/auth/lock` endpoint
- Opt-in slow smoke test that launches real Camoufox window
```

- [ ] **Step 13.4: Tag**

```bash
git add CHANGELOG.md
git commit -m "docs: changelog v0.2.0-m2"
git tag v0.2.0-m2 -m "M2: FingerprintGenerator + Profile API"
git push origin main --tags
```

---

## Definition of Done (M2)

- ✅ All 13 tasks ticked
- ✅ `pytest -q -m "not slow"` — 0 failures
- ✅ 10 profiles via API → 10 distinct fingerprints (acceptance test)
- ✅ Each generated fingerprint passes validator
- ✅ Profiles endpoints return 423 before unlock, work after
- ✅ Tag `v0.2.0-m2` on origin

## Next plan
**Plan 3 — M3: Proxy + WebRTC**
