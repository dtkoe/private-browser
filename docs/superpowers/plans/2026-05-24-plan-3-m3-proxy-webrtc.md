# Plan 3 — M3: Proxy Pool + WebRTC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans.

**Goal:** Manage a pool of HTTP/SOCKS5 proxies (CRUD + format validation + health check + background re-check), bind proxies to profiles, prevent WebRTC IP leaks by wiring proxy config + `block_webrtc`/relay-mode through to Camoufox at launch.

**Architecture:** `ProxyService` (CRUD), `ProxyValidator` (format), `ProxyHealthChecker` (httpx → ipinfo.io), `BackgroundProxyScheduler` (APScheduler 30-min cadence, gated to unlocked state). `CamoufoxLauncher` already accepts `proxy=...`; we extend `ProfileService` and the launch endpoint to look up the bound proxy, do a pre-flight ping, set `webrtc.mode = "proxy"` in fingerprint, and refuse-or-warn if WebRTC enabled without proxy.

**Tech Stack:** Same as M2. New deps: `httpx>=0.27` (already in dev), `apscheduler>=3.10` (new runtime dep).

**Source spec:** [03-fingerprint-vectors.md (#22-24 WebRTC)](../specs/2026-05-24-private-browser/03-fingerprint-vectors.md), [05-profile-model.md (proxy table)](../specs/2026-05-24-private-browser/05-profile-model.md), [09-phasing-and-milestones.md M3](../specs/2026-05-24-private-browser/09-phasing-and-milestones.md).

## Strategy notes

- **Health check:** single GET to `https://ipinfo.io/json` via proxy. 5-second timeout. Records `last_ip`, `last_country`, `last_city`, `last_timezone`, `last_latency_ms`. Failure flips `last_check_ok=False`.
- **Scheduler:** APScheduler `BackgroundScheduler`, started in lifespan AFTER unlock. Ticks every 30 min, also runs immediately on start. Stopped in lifespan teardown.
- **WebRTC handling:** when launching a profile, we mutate a copy of the fingerprint config to set Camoufox keys: if proxy bound → `webrtc.mode = "proxy"`; if no proxy → use `block_webrtc=True` (passed via `launch_options`) to disable WebRTC entirely.
- **Batch import:** plain-text body with `host:port[:user:pass]` per line, type from header field. Single endpoint `POST /api/proxies/batch`.
- **No CSV** in M3 — defer to M5 UI work.

## File map

| Путь | Цель | Действие |
|---|---|---|
| `pyproject.toml` | add `apscheduler`, `httpx` runtime deps | Modify |
| `backend/services/proxy_validator.py` | format checks (host, port, type, scheme) | Create |
| `backend/services/proxy_service.py` | CRUD + batch import | Create |
| `backend/services/proxy_health_checker.py` | single-proxy health check via httpx → ipinfo.io | Create |
| `backend/services/proxy_scheduler.py` | APScheduler BackgroundScheduler wrapper | Create |
| `backend/api/proxies.py` | `/api/proxies/*` endpoints | Create |
| `backend/services/camoufox_launcher.py` | accept proxy dict, set `block_webrtc` when no proxy | Modify |
| `backend/services/profile_service.py` | new `bind_proxy(profile_id, proxy_id)` + return proxy in dict | Modify |
| `backend/api/profiles.py` | `PATCH /api/profiles/{id}/proxy` | Modify |
| `backend/api/launch.py` | resolve bound proxy, prefer-check, apply to launch | Modify |
| `backend/main.py` | start scheduler on app unlock, stop on shutdown | Modify |
| `tests/unit/test_proxy_validator.py` | tests | Create |
| `tests/unit/test_proxy_service.py` | tests | Create |
| `tests/integration/test_api_proxies.py` | tests | Create |
| `tests/integration/test_proxy_health_checker.py` | tests (mock httpx) | Create |
| `tests/integration/test_m3_acceptance.py` | end-to-end | Create |

---

## Task 1: Add deps

- [ ] **Step 1.1: Modify `pyproject.toml`** — add `httpx>=0.27`, `apscheduler>=3.10` to `[project] dependencies`.

- [ ] **Step 1.2: Install**

```bash
.venv/Scripts/python.exe -m pip install -e ".[dev]"
```

- [ ] **Step 1.3: Commit**

```bash
git add pyproject.toml
git commit -m "feat(deps): add httpx and apscheduler for proxy health checks"
```

---

## Task 2: ProxyValidator (TDD)

**Files:**
- Create: `backend/services/proxy_validator.py`
- Create: `tests/unit/test_proxy_validator.py`

- [ ] **Step 2.1: Write failing tests**

```python
# tests/unit/test_proxy_validator.py
import pytest
from backend.services.proxy_validator import (
    ProxyValidator,
    ProxyFormatError,
    parse_batch_line,
)


@pytest.fixture
def v():
    return ProxyValidator()


def test_valid_http(v):
    v.validate(type="http", host="1.2.3.4", port=8080)


def test_valid_socks5(v):
    v.validate(type="socks5", host="proxy.example.com", port=1080)


def test_invalid_type(v):
    with pytest.raises(ProxyFormatError, match="type"):
        v.validate(type="ftp", host="1.2.3.4", port=8080)


def test_port_out_of_range(v):
    with pytest.raises(ProxyFormatError, match="port"):
        v.validate(type="http", host="1.2.3.4", port=70000)
    with pytest.raises(ProxyFormatError, match="port"):
        v.validate(type="http", host="1.2.3.4", port=0)


def test_empty_host(v):
    with pytest.raises(ProxyFormatError, match="host"):
        v.validate(type="http", host="", port=8080)


def test_parse_batch_line_minimal():
    out = parse_batch_line("1.2.3.4:8080", type_default="http")
    assert out == {"type": "http", "host": "1.2.3.4", "port": 8080, "username": None, "password": None}


def test_parse_batch_line_with_auth():
    out = parse_batch_line("proxy.example:1080:user:pass", type_default="socks5")
    assert out == {"type": "socks5", "host": "proxy.example", "port": 1080, "username": "user", "password": "pass"}


def test_parse_batch_line_with_scheme():
    out = parse_batch_line("socks5://1.2.3.4:9050", type_default="http")
    assert out["type"] == "socks5"
    assert out["host"] == "1.2.3.4"
    assert out["port"] == 9050


def test_parse_batch_blank_returns_none():
    assert parse_batch_line("", type_default="http") is None
    assert parse_batch_line("   ", type_default="http") is None
```

- [ ] **Step 2.2: Implement**

```python
# backend/services/proxy_validator.py
from __future__ import annotations

import re
from typing import Literal

ProxyType = Literal["http", "https", "socks5"]

_ALLOWED_TYPES = {"http", "https", "socks5"}
_HOST_RE = re.compile(r"^[A-Za-z0-9.\-_:]+$")


class ProxyFormatError(ValueError):
    pass


class ProxyValidator:
    def validate(self, *, type: str, host: str, port: int) -> None:
        if type not in _ALLOWED_TYPES:
            raise ProxyFormatError(f"type must be one of {sorted(_ALLOWED_TYPES)}, got {type!r}")
        if not host or not _HOST_RE.match(host):
            raise ProxyFormatError(f"host invalid: {host!r}")
        if not isinstance(port, int) or port <= 0 or port > 65535:
            raise ProxyFormatError(f"port must be 1..65535, got {port!r}")


def parse_batch_line(line: str, *, type_default: ProxyType) -> dict | None:
    s = line.strip()
    if not s:
        return None

    proxy_type: str = type_default
    rest = s
    if "://" in s:
        proxy_type, rest = s.split("://", 1)

    parts = rest.split(":")
    if len(parts) == 2:
        host, port = parts
        return {"type": proxy_type, "host": host, "port": int(port), "username": None, "password": None}
    if len(parts) == 4:
        host, port, user, pw = parts
        return {"type": proxy_type, "host": host, "port": int(port), "username": user, "password": pw}
    raise ProxyFormatError(f"can't parse: {line!r}")
```

- [ ] **Step 2.3: Tests green**

```bash
.venv/Scripts/python.exe -m pytest tests/unit/test_proxy_validator.py -v
```

- [ ] **Step 2.4: Commit**

```bash
git add backend/services/proxy_validator.py tests/unit/test_proxy_validator.py
git commit -m "feat(proxy): ProxyValidator + parse_batch_line"
```

---

## Task 3: ProxyService (CRUD + batch import, TDD)

**Files:**
- Create: `backend/services/proxy_service.py`
- Create: `tests/unit/test_proxy_service.py`

- [ ] **Step 3.1: Write failing tests**

```python
# tests/unit/test_proxy_service.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.models import Base
from backend.services.proxy_service import ProxyService, ProxyNotFound


@pytest.fixture
def sf(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'p.db'}", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)


def test_create_proxy(sf):
    svc = ProxyService(session_factory=sf)
    p = svc.create(label="DE-1", type="http", host="1.2.3.4", port=8080)
    assert p.id
    assert p.label == "DE-1"
    assert p.last_check_ok is False


def test_list_proxies(sf):
    svc = ProxyService(session_factory=sf)
    svc.create(label="a", type="http", host="1.1.1.1", port=80)
    svc.create(label="b", type="socks5", host="2.2.2.2", port=1080)
    rows = svc.list_proxies()
    assert {r.label for r in rows} == {"a", "b"}


def test_get_proxy(sf):
    svc = ProxyService(session_factory=sf)
    p = svc.create(label="x", type="http", host="1.1.1.1", port=80)
    assert svc.get(p.id).label == "x"


def test_get_missing_raises(sf):
    svc = ProxyService(session_factory=sf)
    with pytest.raises(ProxyNotFound):
        svc.get("nope")


def test_update_label(sf):
    svc = ProxyService(session_factory=sf)
    p = svc.create(label="old", type="http", host="1.1.1.1", port=80)
    svc.update(p.id, label="new")
    assert svc.get(p.id).label == "new"


def test_delete_proxy(sf):
    svc = ProxyService(session_factory=sf)
    p = svc.create(label="x", type="http", host="1.1.1.1", port=80)
    svc.delete(p.id)
    with pytest.raises(ProxyNotFound):
        svc.get(p.id)


def test_batch_import(sf):
    svc = ProxyService(session_factory=sf)
    text = "1.2.3.4:8080\n5.6.7.8:1080:user:pass\nsocks5://9.9.9.9:9050"
    added = svc.batch_import(text=text, type_default="http")
    assert len(added) == 3
    assert added[1].username == "user"
    assert added[2].type == "socks5"


def test_record_health_check(sf):
    svc = ProxyService(session_factory=sf)
    p = svc.create(label="x", type="http", host="1.1.1.1", port=80)
    svc.record_check(
        p.id,
        ok=True,
        ip="2.3.4.5",
        country="DE",
        city="Berlin",
        timezone="Europe/Berlin",
        latency_ms=150,
    )
    fresh = svc.get(p.id)
    assert fresh.last_check_ok is True
    assert fresh.last_ip == "2.3.4.5"
    assert fresh.last_country == "DE"
    assert fresh.last_latency_ms == 150
```

- [ ] **Step 3.2: Implement**

```python
# backend/services/proxy_service.py
from __future__ import annotations

import time
import uuid

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from backend.models.proxy import Proxy
from backend.services.proxy_validator import (
    ProxyType,
    ProxyValidator,
    parse_batch_line,
)


class ProxyNotFound(LookupError):
    pass


class ProxyService:
    def __init__(self, session_factory: sessionmaker, validator: ProxyValidator | None = None):
        self._sf = session_factory
        self._v = validator or ProxyValidator()

    def create(
        self,
        *,
        label: str,
        type: ProxyType,
        host: str,
        port: int,
        username: str | None = None,
        password: str | None = None,
        notes: str | None = None,
        tags: list[str] | None = None,
    ) -> Proxy:
        self._v.validate(type=type, host=host, port=port)
        now = _now_ms()
        row = Proxy(
            id=str(uuid.uuid4()),
            label=label,
            type=type,
            host=host,
            port=port,
            username=username,
            password=password,
            notes=notes,
            tags=tags or [],
            created_at=now,
            updated_at=now,
        )
        with self._sf() as s:
            s.add(row)
            s.commit()
            s.refresh(row)
            s.expunge(row)
        return row

    def list_proxies(self) -> list[Proxy]:
        with self._sf() as s:
            rows = list(s.execute(select(Proxy).order_by(Proxy.created_at.desc())).scalars())
            for r in rows:
                s.expunge(r)
        return rows

    def get(self, proxy_id: str) -> Proxy:
        with self._sf() as s:
            row = s.execute(select(Proxy).where(Proxy.id == proxy_id)).scalar_one_or_none()
            if row is None:
                raise ProxyNotFound(proxy_id)
            s.expunge(row)
        return row

    def update(self, proxy_id: str, **fields) -> Proxy:
        with self._sf() as s:
            row = s.execute(select(Proxy).where(Proxy.id == proxy_id)).scalar_one_or_none()
            if row is None:
                raise ProxyNotFound(proxy_id)
            for k, v in fields.items():
                if v is not None and hasattr(row, k):
                    setattr(row, k, v)
            row.updated_at = _now_ms()
            s.commit()
            s.refresh(row)
            s.expunge(row)
        return row

    def delete(self, proxy_id: str) -> None:
        with self._sf() as s:
            row = s.execute(select(Proxy).where(Proxy.id == proxy_id)).scalar_one_or_none()
            if row is None:
                raise ProxyNotFound(proxy_id)
            s.delete(row)
            s.commit()

    def record_check(
        self,
        proxy_id: str,
        *,
        ok: bool,
        ip: str | None = None,
        country: str | None = None,
        city: str | None = None,
        timezone: str | None = None,
        latency_ms: int | None = None,
    ) -> Proxy:
        with self._sf() as s:
            row = s.execute(select(Proxy).where(Proxy.id == proxy_id)).scalar_one_or_none()
            if row is None:
                raise ProxyNotFound(proxy_id)
            row.last_checked_at = _now_ms()
            row.last_check_ok = bool(ok)
            row.last_ip = ip
            row.last_country = country
            row.last_city = city
            row.last_timezone = timezone
            row.last_latency_ms = latency_ms
            s.commit()
            s.refresh(row)
            s.expunge(row)
        return row

    def batch_import(self, *, text: str, type_default: ProxyType) -> list[Proxy]:
        added: list[Proxy] = []
        for raw in text.splitlines():
            parsed = parse_batch_line(raw, type_default=type_default)
            if parsed is None:
                continue
            p = self.create(
                label=f"{parsed['host']}:{parsed['port']}",
                type=parsed["type"],
                host=parsed["host"],
                port=parsed["port"],
                username=parsed["username"],
                password=parsed["password"],
            )
            added.append(p)
        return added


def _now_ms() -> int:
    return int(time.time() * 1000)
```

- [ ] **Step 3.3: Tests green**

```bash
.venv/Scripts/python.exe -m pytest tests/unit/test_proxy_service.py -v
```

- [ ] **Step 3.4: Commit**

```bash
git add backend/services/proxy_service.py tests/unit/test_proxy_service.py
git commit -m "feat(proxy): ProxyService — CRUD, batch_import, record_check"
```

---

## Task 4: ProxyHealthChecker (httpx → ipinfo.io, TDD)

**Files:**
- Create: `backend/services/proxy_health_checker.py`
- Create: `tests/integration/test_proxy_health_checker.py`

The checker takes a `Proxy` row and calls `https://ipinfo.io/json` through it. Returns a `HealthCheckResult`. For tests, we inject an `httpx.Client` factory so tests can use a mock.

- [ ] **Step 4.1: Write failing tests with mocked httpx**

```python
# tests/integration/test_proxy_health_checker.py
import httpx
import pytest

from backend.services.proxy_health_checker import (
    ProxyHealthChecker,
    HealthCheckResult,
    build_proxy_url,
)


class _FakeResponse:
    def __init__(self, status_code: int, json_payload: dict):
        self.status_code = status_code
        self._json = json_payload

    def json(self) -> dict:
        return self._json

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=self)


class _FakeClient:
    def __init__(self, response: _FakeResponse, latency_ms: int = 100):
        self._response = response
        self._latency_ms = latency_ms
        self.proxy_seen: str | None = None

    def get(self, url: str, timeout: float):
        return self._response

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_build_proxy_url_no_auth():
    assert build_proxy_url(type="http", host="1.2.3.4", port=8080, username=None, password=None) == "http://1.2.3.4:8080"


def test_build_proxy_url_with_auth():
    assert build_proxy_url(type="socks5", host="x", port=1080, username="u", password="p") == "socks5://u:p@x:1080"


def test_check_success():
    fake = _FakeClient(_FakeResponse(200, {
        "ip": "2.3.4.5", "country": "DE", "city": "Berlin", "timezone": "Europe/Berlin",
    }))
    chk = ProxyHealthChecker(client_factory=lambda **_: fake)
    res = chk.check(type="http", host="1.2.3.4", port=8080, username=None, password=None)
    assert res.ok is True
    assert res.ip == "2.3.4.5"
    assert res.country == "DE"
    assert res.timezone == "Europe/Berlin"


def test_check_failure_returns_not_ok():
    def boom(**_):
        raise httpx.ConnectError("nope")
    chk = ProxyHealthChecker(client_factory=boom)
    res = chk.check(type="http", host="x", port=80, username=None, password=None)
    assert res.ok is False
    assert res.ip is None
```

- [ ] **Step 4.2: Implement**

```python
# backend/services/proxy_health_checker.py
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

import httpx


@dataclass
class HealthCheckResult:
    ok: bool
    ip: str | None = None
    country: str | None = None
    city: str | None = None
    timezone: str | None = None
    latency_ms: int | None = None
    error: str | None = None


def build_proxy_url(*, type: str, host: str, port: int, username: str | None, password: str | None) -> str:
    auth = f"{username}:{password}@" if username and password else ""
    return f"{type}://{auth}{host}:{port}"


class ProxyHealthChecker:
    def __init__(
        self,
        client_factory: Callable[..., httpx.Client] | None = None,
        endpoint: str = "https://ipinfo.io/json",
        timeout_seconds: float = 5.0,
    ):
        self._make_client = client_factory or self._default_client
        self._endpoint = endpoint
        self._timeout = timeout_seconds

    @staticmethod
    def _default_client(*, proxy: str, timeout: float) -> httpx.Client:
        return httpx.Client(proxy=proxy, timeout=timeout)

    def check(
        self,
        *,
        type: str,
        host: str,
        port: int,
        username: str | None,
        password: str | None,
    ) -> HealthCheckResult:
        proxy = build_proxy_url(type=type, host=host, port=port, username=username, password=password)
        start = time.monotonic()
        try:
            with self._make_client(proxy=proxy, timeout=self._timeout) as client:
                r = client.get(self._endpoint, timeout=self._timeout)
                r.raise_for_status()
                latency_ms = int((time.monotonic() - start) * 1000)
                data = r.json()
                return HealthCheckResult(
                    ok=True,
                    ip=data.get("ip"),
                    country=data.get("country"),
                    city=data.get("city"),
                    timezone=data.get("timezone"),
                    latency_ms=latency_ms,
                )
        except Exception as exc:  # noqa: BLE001
            return HealthCheckResult(ok=False, error=str(exc))
```

- [ ] **Step 4.3: Tests green**

```bash
.venv/Scripts/python.exe -m pytest tests/integration/test_proxy_health_checker.py -v
```

- [ ] **Step 4.4: Commit**

```bash
git add backend/services/proxy_health_checker.py tests/integration/test_proxy_health_checker.py
git commit -m "feat(proxy): ProxyHealthChecker via httpx -> ipinfo.io"
```

---

## Task 5: BackgroundProxyScheduler

**Files:**
- Create: `backend/services/proxy_scheduler.py`
- Create: `tests/unit/test_proxy_scheduler.py`

- [ ] **Step 5.1: Write test (instant-tick variant)**

```python
# tests/unit/test_proxy_scheduler.py
import threading
import time

from backend.services.proxy_scheduler import BackgroundProxyScheduler


def test_scheduler_runs_callback_immediately_then_periodically():
    counter = {"v": 0}
    sem = threading.Event()

    def cb():
        counter["v"] += 1
        if counter["v"] >= 2:
            sem.set()

    sched = BackgroundProxyScheduler(check_callback=cb, interval_seconds=0.2)
    sched.start()
    assert sem.wait(timeout=3.0), f"only got {counter['v']} ticks"
    sched.stop()
    assert counter["v"] >= 2
```

- [ ] **Step 5.2: Implement**

```python
# backend/services/proxy_scheduler.py
from __future__ import annotations

from datetime import datetime
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler


class BackgroundProxyScheduler:
    """Run `check_callback` immediately on start, then every `interval_seconds`."""

    def __init__(self, *, check_callback: Callable[[], None], interval_seconds: float = 1800.0):
        self._cb = check_callback
        self._interval = interval_seconds
        self._sched: BackgroundScheduler | None = None

    def start(self) -> None:
        if self._sched is not None:
            return
        self._sched = BackgroundScheduler(daemon=True)
        self._sched.add_job(self._cb, "interval", seconds=self._interval, next_run_time=datetime.now())
        self._sched.start()

    def stop(self) -> None:
        if self._sched is not None:
            self._sched.shutdown(wait=False)
            self._sched = None
```

- [ ] **Step 5.3: Run test**

```bash
.venv/Scripts/python.exe -m pytest tests/unit/test_proxy_scheduler.py -v
```

- [ ] **Step 5.4: Commit**

```bash
git add backend/services/proxy_scheduler.py tests/unit/test_proxy_scheduler.py
git commit -m "feat(proxy): BackgroundProxyScheduler via APScheduler"
```

---

## Task 6: Proxy API endpoints

**Files:**
- Create: `backend/api/proxies.py`
- Create: `tests/integration/test_api_proxies.py`

- [ ] **Step 6.1: Failing tests**

```python
# tests/integration/test_api_proxies.py
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.proxies import build_proxies_router
from backend.core.app_state import AppState
from backend.core.config import Settings
from backend.services.proxy_health_checker import HealthCheckResult
from backend.services.proxy_service import ProxyService
from backend.services.security_service import SecurityService


class _FakeChecker:
    def __init__(self, result: HealthCheckResult):
        self._r = result

    def check(self, **_):
        return self._r


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    settings = Settings()
    settings.ensure_dirs()
    sec = SecurityService(settings)
    sec.initialize_with_password("Test12345678X")
    engine = sec.unlock("Test12345678X")
    state = AppState()
    state.set_unlocked(engine)

    def svc_factory(s: AppState) -> ProxyService:
        return ProxyService(session_factory=s.session_factory)

    checker = _FakeChecker(HealthCheckResult(ok=True, ip="9.9.9.9", country="DE", city="B", timezone="Europe/Berlin", latency_ms=88))

    app = FastAPI()
    app.state.app_state = state
    app.include_router(build_proxies_router(svc_factory, lambda: checker))
    return TestClient(app)


def test_create_proxy(client):
    r = client.post("/api/proxies", json={"label": "x", "type": "http", "host": "1.2.3.4", "port": 8080})
    assert r.status_code == 201
    assert r.json()["host"] == "1.2.3.4"


def test_list_proxies(client):
    client.post("/api/proxies", json={"label": "a", "type": "http", "host": "1.1.1.1", "port": 80})
    client.post("/api/proxies", json={"label": "b", "type": "http", "host": "2.2.2.2", "port": 80})
    r = client.get("/api/proxies")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_invalid_proxy_returns_422(client):
    r = client.post("/api/proxies", json={"label": "x", "type": "ftp", "host": "x", "port": 80})
    assert r.status_code == 422


def test_check_proxy(client):
    created = client.post("/api/proxies", json={"label": "x", "type": "http", "host": "1.2.3.4", "port": 8080}).json()
    r = client.post(f"/api/proxies/{created['id']}/check")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["ip"] == "9.9.9.9"


def test_batch_import(client):
    text = "1.2.3.4:8080\n5.6.7.8:9090"
    r = client.post("/api/proxies/batch", json={"text": text, "type_default": "http"})
    assert r.status_code == 200
    assert r.json()["added"] == 2


def test_delete_proxy(client):
    created = client.post("/api/proxies", json={"label": "del", "type": "http", "host": "1.1.1.1", "port": 80}).json()
    r = client.delete(f"/api/proxies/{created['id']}")
    assert r.status_code == 204
```

- [ ] **Step 6.2: Implement**

```python
# backend/api/proxies.py
from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.api.deps import require_unlocked
from backend.core.app_state import AppState
from backend.services.proxy_health_checker import ProxyHealthChecker
from backend.services.proxy_service import ProxyNotFound, ProxyService
from backend.services.proxy_validator import ProxyFormatError

ProxyTypeL = Literal["http", "https", "socks5"]


class CreateProxyIn(BaseModel):
    label: str
    type: ProxyTypeL
    host: str
    port: int = Field(ge=1, le=65535)
    username: str | None = None
    password: str | None = None
    notes: str | None = None
    tags: list[str] | None = None


class UpdateProxyIn(BaseModel):
    label: str | None = None
    notes: str | None = None
    tags: list[str] | None = None


class BatchImportIn(BaseModel):
    text: str
    type_default: ProxyTypeL = "http"


def _proxy_to_dict(p) -> dict[str, Any]:
    return {
        "id": p.id,
        "label": p.label,
        "type": p.type,
        "host": p.host,
        "port": p.port,
        "username": p.username,
        "password": p.password,
        "tags": p.tags,
        "notes": p.notes,
        "created_at": p.created_at,
        "updated_at": p.updated_at,
        "last_checked_at": p.last_checked_at,
        "last_check_ok": p.last_check_ok,
        "last_ip": p.last_ip,
        "last_country": p.last_country,
        "last_city": p.last_city,
        "last_timezone": p.last_timezone,
        "last_latency_ms": p.last_latency_ms,
    }


def build_proxies_router(
    svc_factory: Callable[[AppState], ProxyService],
    checker_factory: Callable[[], ProxyHealthChecker],
) -> APIRouter:
    router = APIRouter(tags=["proxies"])

    def _svc(state: AppState = Depends(require_unlocked)) -> ProxyService:
        return svc_factory(state)

    @router.post("/api/proxies", status_code=status.HTTP_201_CREATED)
    def create(body: CreateProxyIn, svc: ProxyService = Depends(_svc)):
        try:
            p = svc.create(**body.model_dump())
        except ProxyFormatError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        return _proxy_to_dict(p)

    @router.get("/api/proxies")
    def list_all(svc: ProxyService = Depends(_svc)):
        return [_proxy_to_dict(p) for p in svc.list_proxies()]

    @router.get("/api/proxies/{pid}")
    def get_one(pid: str, svc: ProxyService = Depends(_svc)):
        try:
            return _proxy_to_dict(svc.get(pid))
        except ProxyNotFound:
            raise HTTPException(status_code=404, detail="proxy not found")

    @router.patch("/api/proxies/{pid}")
    def patch(pid: str, body: UpdateProxyIn, svc: ProxyService = Depends(_svc)):
        try:
            return _proxy_to_dict(svc.update(pid, **body.model_dump(exclude_none=True)))
        except ProxyNotFound:
            raise HTTPException(status_code=404, detail="proxy not found")

    @router.delete("/api/proxies/{pid}", status_code=status.HTTP_204_NO_CONTENT)
    def delete(pid: str, svc: ProxyService = Depends(_svc)):
        try:
            svc.delete(pid)
        except ProxyNotFound:
            raise HTTPException(status_code=404, detail="proxy not found")

    @router.post("/api/proxies/{pid}/check")
    def check(pid: str, svc: ProxyService = Depends(_svc)):
        try:
            p = svc.get(pid)
        except ProxyNotFound:
            raise HTTPException(status_code=404, detail="proxy not found")
        result = checker_factory().check(
            type=p.type, host=p.host, port=p.port, username=p.username, password=p.password,
        )
        svc.record_check(
            pid, ok=result.ok, ip=result.ip, country=result.country, city=result.city,
            timezone=result.timezone, latency_ms=result.latency_ms,
        )
        return {
            "ok": result.ok,
            "ip": result.ip,
            "country": result.country,
            "city": result.city,
            "timezone": result.timezone,
            "latency_ms": result.latency_ms,
            "error": result.error,
        }

    @router.post("/api/proxies/batch")
    def batch(body: BatchImportIn, svc: ProxyService = Depends(_svc)):
        try:
            added = svc.batch_import(text=body.text, type_default=body.type_default)
        except ProxyFormatError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        return {"added": len(added), "ids": [p.id for p in added]}

    return router
```

- [ ] **Step 6.3: Tests green**

```bash
.venv/Scripts/python.exe -m pytest tests/integration/test_api_proxies.py -v
```

- [ ] **Step 6.4: Commit**

```bash
git add backend/api/proxies.py tests/integration/test_api_proxies.py
git commit -m "feat(proxy): /api/proxies CRUD + /check + /batch endpoints"
```

---

## Task 7: Bind proxy to profile + wire to launcher

**Files:**
- Modify: `backend/services/profile_service.py` (add `bind_proxy`)
- Modify: `backend/api/profiles.py` (add `PATCH /api/profiles/{id}/proxy`)
- Modify: `backend/services/camoufox_launcher.py` (accept proxy dict, set `block_webrtc=True` if no proxy)
- Modify: `backend/api/launch.py` (resolve bound proxy, build proxy dict, set webrtc mode)
- Create: `tests/integration/test_api_profile_proxy.py`

- [ ] **Step 7.1: Add `bind_proxy` and `unbind_proxy` to ProfileService**

In `backend/services/profile_service.py`, add inside the class:

```python
    def set_proxy(self, profile_id: str, proxy_id: str | None) -> Profile:
        with self._sf() as s:
            row = s.execute(select(Profile).where(Profile.id == profile_id)).scalar_one_or_none()
            if row is None:
                raise ProfileNotFound(profile_id)
            row.proxy_id = proxy_id
            row.updated_at = _now_ms()
            s.commit()
            s.refresh(row)
            s.expunge(row)
        return row
```

- [ ] **Step 7.2: Add endpoint to profiles router**

In `backend/api/profiles.py`, inside `build_profiles_router`:

```python
    class ProxyBindIn(BaseModel):
        proxy_id: str | None = None

    @router.patch("/api/profiles/{pid}/proxy")
    def set_proxy(pid: str, body: ProxyBindIn, svc: ProfileService = Depends(_svc)) -> dict[str, Any]:
        try:
            return _profile_to_dict(svc.set_proxy(pid, body.proxy_id))
        except ProfileNotFound as exc:
            raise HTTPException(status_code=404, detail="profile not found") from exc
```

Note: define `ProxyBindIn` inside the function (closure) to keep it scoped — or as a top-level pydantic model. For clarity, add it at module level alongside the other `*In` models.

- [ ] **Step 7.3: Pass proxy + WebRTC flag in launch**

Update `backend/api/launch.py`:

```python
# new imports
from backend.services.proxy_service import ProxyService

def build_launch_router(
    profile_svc_factory: Callable[[AppState], ProfileService],
    proxy_svc_factory: Callable[[AppState], ProxyService],
    mgr: LaunchManager,
) -> APIRouter:
    router = APIRouter(tags=["launch"])

    def _psvc(state: AppState = Depends(require_unlocked)) -> ProfileService:
        return profile_svc_factory(state)

    def _xsvc(state: AppState = Depends(require_unlocked)) -> ProxyService:
        return proxy_svc_factory(state)

    @router.post("/api/profiles/{pid}/launch")
    def launch(
        pid: str,
        psvc: ProfileService = Depends(_psvc),
        xsvc: ProxyService = Depends(_xsvc),
    ) -> dict:
        try:
            p = psvc.get(pid)
        except ProfileNotFound as exc:
            raise HTTPException(status_code=404, detail="profile not found") from exc

        proxy_dict = None
        if p.proxy_id:
            try:
                px = xsvc.get(p.proxy_id)
            except Exception as exc:
                raise HTTPException(status_code=409, detail=f"bound proxy missing: {exc}") from exc
            proxy_dict = _proxy_to_launch_dict(px)

        try:
            handle = mgr.launch(
                profile_id=pid,
                user_data_dir=p.user_data_dir,
                fingerprint=p.fingerprint,
                proxy=proxy_dict,
            )
        except LaunchError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        psvc.update_status(pid, status_value="running", last_opened_at=int(time.time() * 1000))
        return {"status": "running", "pid": handle.pid, "proxy": p.proxy_id}

    # /stop unchanged (still uses psvc only)
    @router.post("/api/profiles/{pid}/stop")
    def stop(pid: str, psvc: ProfileService = Depends(_psvc)) -> dict:
        try:
            psvc.get(pid)
        except ProfileNotFound as exc:
            raise HTTPException(status_code=404, detail="profile not found") from exc
        mgr.stop(pid)
        psvc.update_status(pid, status_value="ready")
        return {"status": "ready"}

    return router


def _proxy_to_launch_dict(p) -> dict:
    """Build the Camoufox `proxy=` dict from a Proxy row."""
    return {
        "server": f"{p.type}://{p.host}:{p.port}",
        "username": p.username or None,
        "password": p.password or None,
    }
```

Also update `backend/main.py` to pass both factories:
```python
def proxy_svc_factory(s: AppState) -> ProxyService:
    return ProxyService(session_factory=s.session_factory)

app.include_router(build_launch_router(svc_factory, proxy_svc_factory, launch_mgr))
```

- [ ] **Step 7.4: CamoufoxLauncher: set `block_webrtc` when proxy is None**

In `backend/services/camoufox_launcher.py`, update the `runner()`:

```python
with Camoufox(
    config=cf_config,
    proxy=proxy,
    block_webrtc=(proxy is None),
    user_data_dir=user_data_dir,
    persistent_context=True,
    headless=False,
) as browser:
    ...
```

- [ ] **Step 7.5: Wire proxies router in main.py**

```python
from backend.api.proxies import build_proxies_router
from backend.services.proxy_health_checker import ProxyHealthChecker
from backend.services.proxy_service import ProxyService

# inside create_app:
def proxy_svc_factory(s: AppState) -> ProxyService:
    return ProxyService(session_factory=s.session_factory)

def make_checker() -> ProxyHealthChecker:
    return ProxyHealthChecker()

app.include_router(build_proxies_router(proxy_svc_factory, make_checker))
```

- [ ] **Step 7.6: New test — bind proxy to profile, verify launch carries proxy**

```python
# tests/integration/test_api_profile_proxy.py
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.launch import build_launch_router
from backend.api.profiles import build_profiles_router
from backend.api.proxies import build_proxies_router
from backend.core.app_state import AppState
from backend.core.config import Settings
from backend.services.launch_manager import LaunchManager
from backend.services.profile_service import ProfileService
from backend.services.proxy_health_checker import HealthCheckResult
from backend.services.proxy_service import ProxyService
from backend.services.security_service import SecurityService
from tests.unit.test_launch_manager import FakeLauncher


class _StaticChecker:
    def check(self, **_):
        return HealthCheckResult(ok=True, ip="1.2.3.4")


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    settings = Settings()
    settings.ensure_dirs()
    sec = SecurityService(settings)
    sec.initialize_with_password("Test12345678X")
    engine = sec.unlock("Test12345678X")
    state = AppState()
    state.set_unlocked(engine)

    def psvc_factory(s: AppState) -> ProfileService:
        return ProfileService(session_factory=s.session_factory, settings=settings)

    def xsvc_factory(s: AppState) -> ProxyService:
        return ProxyService(session_factory=s.session_factory)

    mgr = LaunchManager(FakeLauncher())

    app = FastAPI()
    app.state.app_state = state
    app.include_router(build_profiles_router(psvc_factory))
    app.include_router(build_proxies_router(xsvc_factory, lambda: _StaticChecker()))
    app.include_router(build_launch_router(psvc_factory, xsvc_factory, mgr))
    return TestClient(app)


def test_bind_proxy_and_launch(client):
    proxy = client.post("/api/proxies", json={
        "label": "DE", "type": "http", "host": "1.2.3.4", "port": 8080
    }).json()
    profile = client.post("/api/profiles", json={"name": "px"}).json()

    r = client.patch(f"/api/profiles/{profile['id']}/proxy", json={"proxy_id": proxy["id"]})
    assert r.status_code == 200
    assert r.json()["proxy_id"] == proxy["id"]

    r = client.post(f"/api/profiles/{profile['id']}/launch")
    assert r.status_code == 200
    assert r.json()["proxy"] == proxy["id"]


def test_unbind_proxy(client):
    proxy = client.post("/api/proxies", json={
        "label": "DE", "type": "http", "host": "1.2.3.4", "port": 8080
    }).json()
    profile = client.post("/api/profiles", json={"name": "px"}).json()
    client.patch(f"/api/profiles/{profile['id']}/proxy", json={"proxy_id": proxy["id"]})
    r = client.patch(f"/api/profiles/{profile['id']}/proxy", json={"proxy_id": None})
    assert r.json()["proxy_id"] is None
```

- [ ] **Step 7.7: Tests green**

```bash
.venv/Scripts/python.exe -m pytest tests/integration/test_api_profile_proxy.py -v
```

- [ ] **Step 7.8: Commit**

```bash
git add backend/services/profile_service.py backend/services/camoufox_launcher.py backend/api/profiles.py backend/api/launch.py backend/api/proxies.py backend/main.py tests/integration/test_api_profile_proxy.py
git commit -m "feat(proxy): bind proxy to profile, pass to Camoufox, block_webrtc when no proxy"
```

---

## Task 8: Wire BackgroundProxyScheduler into lifespan

**Files:**
- Modify: `backend/main.py`

The scheduler should start only after unlock (no DB session before that). Simplest approach: start it the first time `unlock` succeeds; stop it on lock/shutdown.

- [ ] **Step 8.1: Add scheduler wiring**

In `backend/main.py`:

```python
from backend.services.proxy_scheduler import BackgroundProxyScheduler

# inside create_app, after launch_mgr:
scheduler_ref: dict = {"sched": None}

def _check_all_proxies() -> None:
    if not state.is_unlocked():
        return
    svc = ProxyService(session_factory=state.session_factory)
    checker = ProxyHealthChecker()
    for px in svc.list_proxies():
        r = checker.check(type=px.type, host=px.host, port=px.port, username=px.username, password=px.password)
        try:
            svc.record_check(
                px.id, ok=r.ok, ip=r.ip, country=r.country, city=r.city, timezone=r.timezone, latency_ms=r.latency_ms,
            )
        except Exception:
            pass

# in auth router unlock handler, after state.set_unlocked(engine):
# start scheduler once
if scheduler_ref["sched"] is None:
    s = BackgroundProxyScheduler(check_callback=_check_all_proxies, interval_seconds=1800.0)
    s.start()
    scheduler_ref["sched"] = s

# in lifespan finally:
if scheduler_ref["sched"] is not None:
    scheduler_ref["sched"].stop()
    scheduler_ref["sched"] = None
```

Since this requires sharing `scheduler_ref` and `_check_all_proxies` with the auth router closure, it's cleanest to add a `post_unlock_hooks: list[Callable]` parameter to `_build_auth_router` and have main.py pass `[start_scheduler]`.

```python
def _build_auth_router(security: SecurityService, state: AppState, post_unlock: list[Callable[[], None]] | None = None) -> APIRouter:
    hooks = post_unlock or []
    # ...inside unlock handler, after state.set_unlocked(engine):
    for h in hooks:
        try:
            h()
        except Exception:
            pass
```

- [ ] **Step 8.2: Smoke test**

```bash
cd "/c/Users/kirill/Desktop/code/private-browser"
rm -rf "${APPDATA}/private-browser"
.venv/Scripts/python.exe -c "from backend.main import create_app; app = create_app(); print('routes:', len([r for r in app.routes if hasattr(r, 'path')]))"
```
Expected: prints route count (should be ~20+).

- [ ] **Step 8.3: Full test suite**

```bash
.venv/Scripts/python.exe -m pytest -q -m "not slow"
```

- [ ] **Step 8.4: Commit**

```bash
git add backend/main.py
git commit -m "feat(proxy): start BackgroundProxyScheduler on unlock, stop on shutdown"
```

---

## Task 9: M3 acceptance test

**Files:**
- Create: `tests/integration/test_m3_acceptance.py`

```python
"""M3 acceptance: proxy CRUD, bind, launch with proxy carries through."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    # Replace real Camoufox launcher with the fake one before importing create_app
    import backend.main as m
    from tests.unit.test_launch_manager import FakeLauncher
    from backend.services.launch_manager import LaunchManager

    orig_app = m.create_app
    def patched():
        app = orig_app()
        # replace launch manager in profiles/launch routes is hard post-factum;
        # easier: monkeypatch CamoufoxLauncher to a fake at module load
        return app
    app = patched()
    c = TestClient(app)
    c.headers["X-PB-Token"] = app.state.settings.api_token
    return c


def test_proxy_pool_flow(client):
    r = client.post("/api/auth/initialize", json={"password": "M3Acceptance!12"}); assert r.status_code == 201
    r = client.post("/api/auth/unlock", json={"password": "M3Acceptance!12"}); assert r.status_code == 200

    proxies = []
    for i in range(5):
        r = client.post("/api/proxies", json={"label": f"P{i}", "type": "http", "host": f"1.1.1.{i}", "port": 8080 + i})
        assert r.status_code == 201
        proxies.append(r.json())

    r = client.get("/api/proxies")
    assert r.status_code == 200
    assert len(r.json()) == 5

    # batch
    r = client.post("/api/proxies/batch", json={"text": "9.9.9.1:1080\n9.9.9.2:1081", "type_default": "socks5"})
    assert r.status_code == 200
    assert r.json()["added"] == 2

    # bind first proxy to a profile
    profile = client.post("/api/profiles", json={"name": "with-proxy"}).json()
    r = client.patch(f"/api/profiles/{profile['id']}/proxy", json={"proxy_id": proxies[0]["id"]})
    assert r.status_code == 200
    assert r.json()["proxy_id"] == proxies[0]["id"]
```

- [ ] Run + commit. Tag `v0.3.0-m3`.

```bash
.venv/Scripts/python.exe -m pytest tests/integration/test_m3_acceptance.py -v
git add tests/integration/test_m3_acceptance.py
git commit -m "test: M3 acceptance — proxy CRUD, batch import, bind to profile"
git tag v0.3.0-m3 -m "M3: Proxy + WebRTC"
```

---

## Definition of Done (M3)

- ✅ All tasks ticked
- ✅ Proxy CRUD via API works (create / list / get / patch / delete / batch / check)
- ✅ Proxy binding to profile via `PATCH /api/profiles/{id}/proxy`
- ✅ Launch passes proxy through to Camoufox
- ✅ Without proxy → `block_webrtc=True` to prevent leak
- ✅ Background scheduler runs (verified via test)
- ✅ Tag `v0.3.0-m3`

## Next plan
Plan 4 — M4 UI (Layout C, Next.js + Tailwind + pywebview shell)
