# Plan 1 — Foundation (M0 + M1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scaffold the project from scratch as `private-browser`, build encrypted foundation (SQLCipher gated by master password, API token auth, audit log, structured logging). Result: application starts behind login screen; DB on disk is encrypted; smoke test confirms Camoufox SDK works.

**Architecture:** Python 3.11+ FastAPI backend + Next.js 14 frontend, SQLite-encrypted-with-SQLCipher via `pysqlcipher3`, Argon2id KDF for master password, random per-startup API token, structured logging via `structlog`.

**Tech Stack:** Python 3.11+ (3.12 OK), FastAPI, SQLAlchemy 2 (async via greenlet wrap of sync DBAPI), SQLCipher (`pysqlcipher3`), Alembic, `cryptography`, `argon2-cffi`, `structlog`, Node 20+, Next.js 14, React 18, TypeScript 5, Tailwind, pytest, pytest-asyncio.

**Source spec:** [../specs/2026-05-24-private-browser/](../specs/2026-05-24-private-browser/) — особенно [02-architecture.md](../specs/2026-05-24-private-browser/02-architecture.md), [07-security-model.md](../specs/2026-05-24-private-browser/07-security-model.md), [09-phasing-and-milestones.md](../specs/2026-05-24-private-browser/09-phasing-and-milestones.md).

## Important note on strategy change

Original spec (04-fork-strategy.md) called for forking `polyackiy/camoufox-profile-manager`. After examining upstream, it turned out to be messy (random scripts at repo root, awkward nested `CamoufoxProfileManager/` package layout, only 11 commits). **Decision: write from scratch**, treating upstream as one of several reference projects, not a base.

Practical implications:
- No `git fork`; we `git init` in the existing directory (which already has `docs/`)
- No upstream attribution beyond a "thanks to" line in README
- We control the package layout from day one (clean `backend/` + `frontend/`)
- Camoufox SDK itself is still our main dependency — pulled from PyPI

---

## File map (что создаём / правим)

| Путь | Цель | Действие |
|---|---|---|
| `private-browser/` (root) | Проект | Init from fork |
| `BASED_ON.md` | Атрибуция upstream | Create |
| `README.md` | Наш README | Replace |
| `LICENSE` | MIT + dual copyright | Modify |
| `.gitignore` | `.superpowers/`, `__pycache__/`, `node_modules/`, `*.db*`, `dist/`, `.env` | Create |
| `pyproject.toml` | rename, deps | Modify |
| `backend/core/config.py` | Settings via pydantic-settings + paths | Create/Modify |
| `backend/core/security.py` | KDF, verifier, token | Create |
| `backend/core/db.py` | SQLCipher engine, unlock, async session | Create |
| `backend/core/logging.py` | structlog config | Create |
| `backend/models/app_settings.py` | KDF salt + verifier storage | Create |
| `backend/models/audit_log.py` | Audit entries | Create |
| `backend/services/security_service.py` | Master password flows | Create |
| `backend/services/audit_service.py` | Audit log writer | Create |
| `backend/api/auth.py` | `/api/auth/*` endpoints | Create |
| `backend/api/middleware/auth_token.py` | API token middleware | Create |
| `backend/main.py` | App startup + lifespan | Create/Modify |
| `alembic/` | Alembic config + migrations | Create |
| `alembic/versions/0001_initial.py` | Initial schema | Create |
| `tests/conftest.py` | Pytest fixtures (temp DB, token) | Create |
| `tests/unit/test_security.py` | KDF, verifier tests | Create |
| `tests/unit/test_audit.py` | Audit service tests | Create |
| `tests/integration/test_db_unlock.py` | SQLCipher unlock flow | Create |
| `tests/integration/test_api_auth.py` | API auth endpoints | Create |
| `.github/workflows/ci.yml` | Lint + test on push | Create |

---

## Task 1: Git init + project scaffold

**Files:** Whole repo (created from scratch)

- [ ] **Step 1.1: Initialize git in the existing directory**

Working dir: `C:\Users\kirill\Desktop\code\private-browser\` (already has `docs/`).

```bash
cd "/c/Users/kirill/Desktop/code/private-browser"
git init -b main
git config --local user.email "<your email>"
git config --local user.name "<your name>"
```
Expected: `.git/` created, default branch is `main`.

- [ ] **Step 1.2: Create base folder structure**

```bash
mkdir -p backend/api backend/api/middleware backend/core backend/models backend/services
mkdir -p tests/unit tests/integration
mkdir -p frontend
mkdir -p alembic/versions
mkdir -p .github/workflows
```

Add empty `__init__.py` to make the Python packages real:
```bash
for d in backend backend/api backend/api/middleware backend/core backend/models backend/services tests tests/unit tests/integration; do
  touch "$d/__init__.py"
done
```

- [ ] **Step 1.3: Create `.gitignore`**

Write `.gitignore`:
```gitignore
# Editor / OS
.vscode/
.idea/
.DS_Store
Thumbs.db
*.swp

# Python
__pycache__/
*.py[cod]
*$py.class
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/
.venv/
venv/
dist/
build/
*.egg-info/

# Node
node_modules/
.next/
out/
.turbo/

# Project data (encrypted DB and profile dirs)
*.db
*.db-shm
*.db-wal
profiles/
camoufox/
logs/
backups/
temp/
logs_test/

# Secrets
.env
.env.*

# Superpowers brainstorm transcripts
.superpowers/

# PyInstaller / NSIS outputs
*.spec
installer/output/
```

- [ ] **Step 1.4: Initial commit**

```bash
git add .gitignore docs/ backend/ tests/ alembic/ .github/
git status
git commit -m "chore: initial project scaffold + design spec"
```
Expected: commit succeeds, working tree clean.

- [ ] **Step 1.5: Create GitHub remote (private-browser repo)**

```bash
gh repo create private-browser --source=. --remote=origin --public \
  --description "Open-source anti-detect browser manager for Windows, built on Camoufox"
git push -u origin main
```
Expected: GitHub creates `dtkoe/private-browser`, push succeeds.

---

## Task 2: Camoufox SDK smoke test

**Goal:** Confirm Camoufox actually works on this machine before we wrap it. If Camoufox itself doesn't launch, the whole project is in trouble — fail fast.

**Files:**
- Create: `scripts/smoke_camoufox.py`
- Create: `docs/dev-machine-setup.md`

- [ ] **Step 2.1: Create Python venv**

```bash
python -m venv .venv
source .venv/Scripts/activate
python --version
pip install --upgrade pip
```
Expected: venv active, Python ≥ 3.11.

- [ ] **Step 2.2: Install Camoufox SDK + Playwright**

```bash
pip install "camoufox[geoip]>=0.4" "playwright>=1.40"
python -m playwright install firefox  # needed by Camoufox under the hood
python -m camoufox fetch              # downloads Camoufox binary to ~/AppData/Local/camoufox/
```
Expected: `camoufox fetch` completes, prints version + install path.

- [ ] **Step 2.3: Write smoke script**

```bash
mkdir -p scripts
```

Create `scripts/smoke_camoufox.py`:
```python
"""Smoke test: launch Camoufox, open a page, confirm fingerprint spoofing engaged."""
from __future__ import annotations

from camoufox.sync_api import Camoufox


def main() -> None:
    print("Launching Camoufox (this may take a few seconds)...")
    with Camoufox(headless=False, os=("windows",), humanize=False) as browser:
        page = browser.new_page()
        page.goto("https://browserleaks.com/javascript", wait_until="domcontentloaded")
        ua = page.evaluate("navigator.userAgent")
        platform = page.evaluate("navigator.platform")
        languages = page.evaluate("navigator.languages")
        webgl_vendor = page.evaluate(
            "(() => { try { const c=document.createElement('canvas').getContext('webgl'); "
            "const i=c.getExtension('WEBGL_debug_renderer_info'); "
            "return c.getParameter(i.UNMASKED_VENDOR_WEBGL); } catch(e) { return 'n/a'; } })()"
        )
        print(f"navigator.userAgent  = {ua}")
        print(f"navigator.platform   = {platform}")
        print(f"navigator.languages  = {languages}")
        print(f"WebGL vendor         = {webgl_vendor}")
        input("Press ENTER to close browser...")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2.4: Run smoke test**

```bash
python scripts/smoke_camoufox.py
```
Expected:
- A Firefox-styled browser window opens (window title may say "Camoufox" or "Firefox")
- Page browserleaks/javascript loads
- Terminal prints UA matching "Mozilla/5.0 (Windows ...) Gecko/... Firefox/..."
- Platform is "Win32" or similar
- WebGL vendor is a realistic string (not "Mozilla" placeholder)
- Pressing ENTER closes the window cleanly

If Camoufox fails to launch on Windows: report blocking error. Common Windows pitfalls: Defender quarantining the binary, antivirus blocking, missing Visual C++ Redistributable.

- [ ] **Step 2.5: Document the working setup**

Write `docs/dev-machine-setup.md`:
```markdown
# Dev Machine Setup

Verified on Windows 11, 2026-05-24.

## Prerequisites

- Python 3.11+ (3.12 verified)
- Node 20+ (Node 24 verified)
- Git 2.40+
- gh CLI 2.80+ (for releases/CI later)

## First-time setup

```bash
git clone https://github.com/dtkoe/private-browser
cd private-browser
python -m venv .venv
source .venv/Scripts/activate   # PowerShell: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m playwright install firefox
python -m camoufox fetch
```

## Smoke test

```bash
python scripts/smoke_camoufox.py
```

Should open a Camoufox window and print spoofed navigator values.

## Backend dev

```bash
uvicorn backend.main:app --reload --port 8769
```

## Frontend dev

```bash
cd frontend
npm install
npm run dev
```

## Known issues

- Windows Defender may quarantine Camoufox binary on first download → add %LOCALAPPDATA%\camoufox to exclusions
- If `pysqlcipher3` install fails on Windows, see <link to issue> for prebuilt wheel
```

- [ ] **Step 2.6: Commit**

```bash
git add scripts/ docs/dev-machine-setup.md
git commit -m "feat: Camoufox smoke test + dev setup docs"
```

---

## Task 3: Project metadata (pyproject.toml, package.json, README, LICENSE)

**Files:**
- Create: `pyproject.toml`
- Create: `frontend/package.json`
- Create: `README.md`
- Create: `LICENSE`

- [ ] **Step 3.1: Create `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "private-browser"
version = "0.1.0"
description = "Open-source anti-detect browser manager for Windows, built on Camoufox"
authors = [{name = "<your name>"}]
license = {text = "MIT"}
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "pydantic>=2.7",
    "sqlalchemy>=2.0",
    "alembic>=1.13",
    "camoufox[geoip]>=0.4",
    "playwright>=1.40",
]

[tool.setuptools]
packages = ["backend", "backend.api", "backend.api.middleware", "backend.core", "backend.models", "backend.services"]
```

- [ ] **Step 3.2: Create frontend `package.json`**

```bash
mkdir -p frontend
```

Create `frontend/package.json`:
```json
{
  "name": "private-browser-ui",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint"
  }
}
```
NOTE: We'll fill in Next.js dependencies properly during M4 UI work. This is a stub so the directory exists.

- [ ] **Step 3.3: Create `README.md`**

```markdown
# Private Browser

Open-source anti-detect browser manager for Windows. Built on [Camoufox](https://github.com/daijro/camoufox) (Firefox-based anti-detect engine).

## Status

🚧 Pre-release — under active development. Not for production use.

## Documentation

- Design spec: [docs/superpowers/specs/2026-05-24-private-browser/](docs/superpowers/specs/2026-05-24-private-browser/)
- Dev setup: [docs/dev-machine-setup.md](docs/dev-machine-setup.md)

## Acknowledgements

- [@daijro](https://github.com/daijro) and the [Camoufox](https://github.com/daijro/camoufox) community for the anti-detect engine
- The [CloverLabsAI](https://github.com/CloverLabsAI/camoufox) community fork for keeping Camoufox alive
- [polyackiy/camoufox-profile-manager](https://github.com/polyackiy/camoufox-profile-manager) — referenced for inspiration during initial design

## License

MIT. See [LICENSE](./LICENSE).
```

- [ ] **Step 3.4: Create `LICENSE`**

```
MIT License

Copyright (c) 2026 <your name>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 3.5: Install our package locally**

```bash
pip install -e .
python -c "import backend; print(backend.__name__)"
```
Expected: prints `backend`.

- [ ] **Step 3.6: Commit**

```bash
git add pyproject.toml frontend/ README.md LICENSE
git commit -m "feat: project metadata (pyproject.toml, package.json, README, LICENSE)"
```

---

## Task 4: Add SQLCipher dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 4.1: Add deps**

Open `pyproject.toml`, add to `[project] dependencies`:
```toml
dependencies = [
    # ... existing
    "pysqlcipher3>=1.2.0",   # SQLCipher Python binding
    "argon2-cffi>=23.1.0",   # Argon2id KDF
    "cryptography>=42.0.0",  # AES-256-GCM, HMAC
    "structlog>=24.1.0",     # Structured logging
    "pydantic-settings>=2.2",
]
```

Add to dev deps:
```toml
[project.optional-dependencies]
dev = [
    # ... existing
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "httpx>=0.27",        # for FastAPI TestClient async
    "ruff>=0.4",
]
```

- [ ] **Step 4.2: Install and verify**

```bash
pip install -e ".[dev]"
python -c "import pysqlcipher3.dbapi2 as sqlite; print(sqlite.sqlite_version)"
python -c "from argon2 import PasswordHasher; print(PasswordHasher().hash('test'))"
```
Expected: both lines print without errors. SQLCipher version shown, Argon2 hash starts with `$argon2id$`.

- [ ] **Step 4.3: Commit**

```bash
git add pyproject.toml
git commit -m "feat: add SQLCipher, Argon2id, structlog dependencies"
```

---

## Task 5: KDF + verifier — security primitives (TDD)

**Files:**
- Create: `backend/core/security.py`
- Create: `tests/unit/test_security.py`

- [ ] **Step 5.1: Write the failing tests**

Create `tests/unit/test_security.py`:
```python
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
```

- [ ] **Step 5.2: Run to confirm fail**

```bash
pytest tests/unit/test_security.py -v
```
Expected: ImportError / ModuleNotFoundError — `backend.core.security` doesn't exist yet.

- [ ] **Step 5.3: Implement `backend/core/security.py`**

Create `backend/core/security.py`:
```python
"""Security primitives: KDF, verifier, API token."""
from __future__ import annotations

import hmac
import secrets
from dataclasses import dataclass, asdict
from hashlib import sha256
from typing import Any

from argon2.low_level import hash_secret_raw, Type as Argon2Type


@dataclass(frozen=True)
class KDFParams:
    memory_kb: int = 65536
    iterations: int = 3
    parallelism: int = 4
    output_length: int = 32
    type: str = "argon2id"

    @classmethod
    def default(cls) -> "KDFParams":
        return cls()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "KDFParams":
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
```

- [ ] **Step 5.4: Run tests, all green**

```bash
pytest tests/unit/test_security.py -v
```
Expected: 8 passed.

- [ ] **Step 5.5: Commit**

```bash
git add backend/core/security.py tests/unit/test_security.py
git commit -m "feat(security): add Argon2id KDF, verifier, API token primitives"
```

---

## Task 6: Project settings + paths (config module)

**Files:**
- Create: `backend/core/config.py`
- Create: `tests/unit/test_config.py`

- [ ] **Step 6.1: Write failing test**

Create `tests/unit/test_config.py`:
```python
from pathlib import Path
from backend.core.config import Settings


def test_settings_default_paths_under_appdata(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    s = Settings()
    assert s.data_dir == tmp_path / "private-browser"
    assert s.db_path == s.data_dir / "app.db"
    assert s.profiles_dir == s.data_dir / "profiles"
    assert s.logs_dir == s.data_dir / "logs"


def test_settings_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("PB_DATA_DIR", str(tmp_path / "custom"))
    s = Settings()
    assert s.data_dir == tmp_path / "custom"


def test_settings_creates_data_dirs(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    s = Settings()
    s.ensure_dirs()
    for p in [s.data_dir, s.profiles_dir, s.logs_dir, s.backups_dir, s.temp_dir]:
        assert p.is_dir()
```

- [ ] **Step 6.2: Run, expect fail**

```bash
pytest tests/unit/test_config.py -v
```
Expected: ImportError.

- [ ] **Step 6.3: Implement `backend/core/config.py`**

Create `backend/core/config.py`:
```python
"""Application settings and path resolution."""
from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PB_", env_file=".env", extra="ignore")

    app_name: str = "private-browser"
    api_host: str = "127.0.0.1"
    api_port: int = 8769
    api_token: str | None = None  # populated at runtime
    data_dir: Path | None = None

    def model_post_init(self, __ctx) -> None:
        if self.data_dir is None:
            base = Path(os.environ.get("APPDATA", str(Path.home())))
            object.__setattr__(self, "data_dir", base / self.app_name)

    @property
    def db_path(self) -> Path:
        return self.data_dir / "app.db"

    @property
    def profiles_dir(self) -> Path:
        return self.data_dir / "profiles"

    @property
    def camoufox_dir(self) -> Path:
        return self.data_dir / "camoufox"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def backups_dir(self) -> Path:
        return self.data_dir / "backups"

    @property
    def temp_dir(self) -> Path:
        return self.data_dir / "temp"

    def ensure_dirs(self) -> None:
        for p in [
            self.data_dir,
            self.profiles_dir,
            self.camoufox_dir,
            self.logs_dir,
            self.backups_dir,
            self.temp_dir,
        ]:
            p.mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 6.4: Run all tests**

```bash
pytest tests/unit/test_config.py -v
```
Expected: 3 passed.

- [ ] **Step 6.5: Commit**

```bash
git add backend/core/config.py tests/unit/test_config.py
git commit -m "feat(core): add Settings module with APPDATA-based paths"
```

---

## Task 7: SQLCipher async engine + unlock (TDD)

**Files:**
- Create: `backend/core/db.py`
- Create: `tests/integration/test_db_unlock.py`

- [ ] **Step 7.1: Write failing test**

Create `tests/integration/test_db_unlock.py`:
```python
import secrets
from pathlib import Path

import pytest

from backend.core.db import (
    create_new_encrypted_db,
    open_encrypted_db,
    DatabaseUnlockError,
)
from backend.core.security import derive_key


@pytest.mark.asyncio
async def test_create_then_open_with_same_key(tmp_path: Path):
    db = tmp_path / "test.db"
    salt = secrets.token_bytes(16)
    key = derive_key("strong-password", salt)
    await create_new_encrypted_db(db, key)
    assert db.is_file()
    # open and verify we can run a trivial query
    engine = await open_encrypted_db(db, key)
    async with engine.begin() as conn:
        from sqlalchemy import text
        v = (await conn.execute(text("SELECT 1"))).scalar_one()
        assert v == 1
    await engine.dispose()


@pytest.mark.asyncio
async def test_open_with_wrong_key_raises(tmp_path: Path):
    db = tmp_path / "test.db"
    salt = secrets.token_bytes(16)
    right = derive_key("right", salt)
    wrong = derive_key("wrong", salt)
    await create_new_encrypted_db(db, right)
    with pytest.raises(DatabaseUnlockError):
        await open_encrypted_db(db, wrong)


@pytest.mark.asyncio
async def test_db_file_is_encrypted_on_disk(tmp_path: Path):
    db = tmp_path / "test.db"
    salt = secrets.token_bytes(16)
    key = derive_key("pw", salt)
    await create_new_encrypted_db(db, key)
    # Header MUST NOT be the plaintext SQLite magic.
    data = db.read_bytes()[:16]
    assert not data.startswith(b"SQLite format 3\x00")
```

- [ ] **Step 7.2: Run, expect fail**

```bash
pytest tests/integration/test_db_unlock.py -v
```
Expected: ImportError.

- [ ] **Step 7.3: Implement `backend/core/db.py`**

We use `sqlcipher3-wheels` (already installed in Task 4) — it's the `sqlcipher3` Python package with prebuilt Windows wheels. It does NOT ship a SQLAlchemy dialect of its own, so we pass it as the `module` parameter to override the default `sqlite3` DBAPI in SQLAlchemy's standard `sqlite` dialect.

Note: SQLAlchemy 2.x `create_async_engine` can wrap sync DBAPIs via greenlet — but the safer/more standard approach is sync engine + `asyncio.to_thread` for async callsites. We'll use **sync** SQLAlchemy here. FastAPI handles sync endpoints fine via its threadpool, and SecurityService can call sync engine helpers.

Create `backend/core/db.py`:
```python
"""SQLCipher-backed SQLAlchemy engine (sync; called from async via to_thread)."""
from __future__ import annotations

from pathlib import Path

import sqlcipher3
from sqlalchemy import Engine, create_engine, event, text


class DatabaseUnlockError(Exception):
    """Raised when SQLCipher refuses the supplied key (or DB is corrupt)."""


def _hex_key(key: bytes) -> str:
    return key.hex()


def _attach_sqlcipher_key(engine: Engine, key: bytes) -> None:
    """Register a connect-listener that runs PRAGMA key on every new connection."""
    hex_key = _hex_key(key)

    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute(f"PRAGMA key = \"x'{hex_key}'\";")
        cur.execute("PRAGMA cipher_compatibility = 4;")
        cur.execute("PRAGMA journal_mode = WAL;")
        cur.close()


def _build_engine(path: Path, key: bytes) -> Engine:
    """Build a SQLAlchemy Engine that uses sqlcipher3 as the DBAPI module."""
    url = f"sqlite:///{path}"
    engine = create_engine(url, module=sqlcipher3, future=True)
    _attach_sqlcipher_key(engine, key)
    return engine


def create_new_encrypted_db(path: Path, key: bytes) -> None:
    """Create a brand new encrypted DB at `path` keyed with `key`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(path)

    engine = _build_engine(path, key)
    try:
        with engine.begin() as conn:
            # Sanity write so the DB has a real (encrypted) header
            conn.execute(text("CREATE TABLE _init (v INTEGER)"))
            conn.execute(text("DROP TABLE _init"))
    finally:
        engine.dispose()


def open_encrypted_db(path: Path, key: bytes) -> Engine:
    """Open existing encrypted DB. Raises DatabaseUnlockError on bad key."""
    if not path.is_file():
        raise FileNotFoundError(path)

    engine = _build_engine(path, key)
    try:
        with engine.connect() as conn:
            # Trigger a read; wrong key => DatabaseError "file is not a database"
            conn.execute(text("SELECT count(*) FROM sqlite_master"))
    except Exception as exc:
        engine.dispose()
        raise DatabaseUnlockError(str(exc)) from exc
    return engine
```

NOTE on TESTS: Task 7's tests (`test_db_unlock.py`) and downstream tasks (security_service, audit_service) were originally written assuming async SQLAlchemy. Update them to use sync. Specifically:
- Drop `@pytest.mark.asyncio` decorators where the test body only calls sync code
- Replace `async def test_…` with `def test_…`
- Replace `await engine.dispose()` with `engine.dispose()`
- Replace `from sqlalchemy.ext.asyncio import AsyncEngine` with `from sqlalchemy import Engine`
- `with engine.connect() as conn:` instead of `async with`

- [ ] **Step 7.4: Run tests**

```bash
pytest tests/integration/test_db_unlock.py -v
```
Expected: 3 passed. If the dialect string fails, the test will error on engine creation — adjust dialect string per pysqlcipher3 docs.

- [ ] **Step 7.5: Commit**

```bash
git add backend/core/db.py tests/integration/test_db_unlock.py
git commit -m "feat(db): SQLCipher async engine with key-on-connect and unlock errors"
```

---

## Task 8: app_settings model + initial Alembic migration

**Files:**
- Create: `backend/models/__init__.py`
- Create: `backend/models/base.py`
- Create: `backend/models/app_settings.py`
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/versions/0001_initial.py`

- [ ] **Step 8.1: Define SQLAlchemy Base**

Create `backend/models/__init__.py`:
```python
from backend.models.base import Base  # noqa: F401
```

Create `backend/models/base.py`:
```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

- [ ] **Step 8.2: Define `AppSettings` model**

Create `backend/models/app_settings.py`:
```python
from __future__ import annotations

from sqlalchemy import CheckConstraint, Integer, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class AppSettings(Base):
    __tablename__ = "app_settings"
    __table_args__ = (CheckConstraint("id = 1", name="ck_app_settings_singleton"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    theme: Mapped[str] = mapped_column(String, default="dark", nullable=False)
    language: Mapped[str] = mapped_column(String, default="ru", nullable=False)
    camoufox_version: Mapped[str | None] = mapped_column(String, nullable=True)
    auto_update_check: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    api_port: Mapped[int] = mapped_column(Integer, default=8769, nullable=False)

    # Master password — KDF
    kdf_salt: Mapped[bytes] = mapped_column(LargeBinary(16), nullable=False)
    kdf_verifier: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    kdf_params_json: Mapped[str] = mapped_column(String, nullable=False)  # JSON KDFParams
```

- [ ] **Step 8.3: Init Alembic (sync template)**

Alembic is already installed (Task 4). We use the SYNC template (not async), since our SQLCipher engine is sync (Task 7 used `create_engine`, not `create_async_engine`).

If the `alembic/` directory was created during Task 1 scaffold as an empty dir, this will fail because it's already there. In that case, run from inside it OR remove the empty dir first. Try this approach:

```bash
cd "/c/Users/kirill/Desktop/code/private-browser"
source .venv/Scripts/activate
# Remove our scaffolded empty alembic/ so alembic init can populate it fresh
rm -rf alembic
alembic init alembic   # uses sync template by default
```

This creates `alembic.ini`, `alembic/env.py`, `alembic/script.py.mako`, `alembic/versions/` (empty), `alembic/README`.

Then edit `alembic.ini`:
- Find the line `sqlalchemy.url = driver://user:pass@localhost/dbname` and replace with `sqlalchemy.url = ` (empty — we set it programmatically via env.py).
- Set `script_location = alembic` (likely already correct).

Edit `alembic/env.py`. The Alembic-generated template has placeholders. Replace the WHOLE FILE with:

```python
"""Alembic env.py for private-browser — uses sqlcipher3 module for encrypted DB."""
from __future__ import annotations

import os
from logging.config import fileConfig
from pathlib import Path

import sqlcipher3
from alembic import context
from sqlalchemy import create_engine, event, pool

from backend.models import Base
from backend.models.app_settings import AppSettings  # noqa: F401 — force import for metadata


config = context.config

# Setup logging from alembic.ini if [loggers] sections exist
if config.config_file_name is not None:
    try:
        fileConfig(config.config_file_name)
    except Exception:
        pass  # logging config is optional

target_metadata = Base.metadata


def _build_engine_for_alembic():
    """Build sync engine with sqlcipher3 module + PRAGMA key on connect."""
    db_path = Path(os.environ["PB_ALEMBIC_DB_PATH"])
    key_hex = os.environ["PB_ALEMBIC_KEY_HEX"]

    url = f"sqlite:///{db_path}"
    engine = create_engine(url, module=sqlcipher3, poolclass=pool.NullPool, future=True)

    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute(f'PRAGMA key = "x\'{key_hex}\'";')
        cur.execute("PRAGMA cipher_compatibility = 4;")
        cur.close()

    return engine


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no DB connection — emit SQL only).

    For our encrypted DB, offline mode isn't meaningful, so we just emit
    against the metadata using a SQLite literal binding."""
    context.configure(
        url="sqlite://",
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode — connect to the encrypted DB."""
    connectable = _build_engine_for_alembic()
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

Required env vars for alembic to work:
- `PB_ALEMBIC_DB_PATH` — absolute path to the `.db` file
- `PB_ALEMBIC_KEY_HEX` — derived key as hex string

These get set programmatically by `SecurityService` when it calls `command.upgrade` (Task 9).

- [ ] **Step 8.4: Generate initial migration**

We need a DB to autogenerate against. Use a plaintext SQLite for the autogen step (no key) — Alembic only inspects schema metadata, not on-disk DB:

Actually simpler: write the migration by hand because we control schema.

Create `alembic/versions/0001_initial.py`:
```python
"""initial schema with app_settings

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-24
"""
from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("theme", sa.String(), nullable=False, server_default="dark"),
        sa.Column("language", sa.String(), nullable=False, server_default="ru"),
        sa.Column("camoufox_version", sa.String(), nullable=True),
        sa.Column("auto_update_check", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("api_port", sa.Integer(), nullable=False, server_default="8769"),
        sa.Column("kdf_salt", sa.LargeBinary(length=16), nullable=False),
        sa.Column("kdf_verifier", sa.LargeBinary(length=32), nullable=False),
        sa.Column("kdf_params_json", sa.String(), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_app_settings_singleton"),
    )


def downgrade() -> None:
    op.drop_table("app_settings")
```

- [ ] **Step 8.5: Run unit test on schema**

Add `tests/unit/test_models.py`:
```python
from backend.models.app_settings import AppSettings
def test_app_settings_table_name():
    assert AppSettings.__tablename__ == "app_settings"
```
```bash
pytest tests/unit/test_models.py -v
```
Expected: 1 passed.

- [ ] **Step 8.6: Commit**

```bash
git add backend/models/ alembic.ini alembic/ tests/unit/test_models.py
git commit -m "feat(db): add AppSettings model + initial Alembic migration"
```

---

## Task 9: SecurityService — master password flows (TDD)

**Files:**
- Create: `backend/services/security_service.py`
- Create: `tests/integration/test_security_service.py`

- [ ] **Step 9.1: Write failing tests (SYNC)**

Create `tests/integration/test_security_service.py`:
```python
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
```

- [ ] **Step 9.2: Run, expect fail**

```bash
pytest tests/integration/test_security_service.py -v
```
Expected: ImportError.

- [ ] **Step 9.3: Implement service**

Create `backend/services/__init__.py` (empty file).

Create `backend/services/security_service.py`:
```python
"""High-level master-password lifecycle: init, unlock, change. SYNC."""
from __future__ import annotations

import json
import secrets
from pathlib import Path

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

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

        # Read salt from sidecar file (salt is not secret; stored next to encrypted DB).
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
    """Run Alembic upgrade head against the encrypted DB. Sync — call via to_thread if needed."""
    import os
    from alembic.config import Config
    from alembic import command

    os.environ["PB_ALEMBIC_DB_PATH"] = str(db_path)
    os.environ["PB_ALEMBIC_KEY_HEX"] = key.hex()
    cfg = Config("alembic.ini")
    cfg.set_main_option("script_location", "alembic")
    command.upgrade(cfg, "head")
```

NOTE: salt sidecar (`app.salt`) is standard practice — salt is not secret and avoids the chicken-and-egg of "need to read DB to get salt to derive key to read DB". The code above writes it after `_run_migrations`.

- [ ] **Step 9.4: Run tests, all green**

```bash
pytest tests/integration/test_security_service.py -v
```
Expected: 5 passed.

- [ ] **Step 9.5: Commit**

```bash
git add backend/services/__init__.py backend/services/security_service.py tests/integration/test_security_service.py
git commit -m "feat(security): SecurityService for init/unlock with Alembic migrations"
```

---

## Task 10: Audit log model + service (TDD)

**Files:**
- Create: `backend/models/audit_log.py`
- Create: `backend/services/audit_service.py`
- Create: `tests/unit/test_audit.py`
- Modify: `alembic/versions/0001_initial.py`

- [ ] **Step 10.1: Write failing test (SYNC)**

Create `tests/unit/test_audit.py`:
```python
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.models import Base
from backend.models.audit_log import AuditLog
from backend.services.audit_service import AuditService


def test_record_audit_entry(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'a.db'}", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(engine, expire_on_commit=False)
    svc = AuditService(SessionLocal)
    svc.record(actor="user", action="profile.create", target_type="profile", target_id="abc", details={"name": "x"})

    with SessionLocal() as session:
        rows = session.execute(select(AuditLog)).scalars().all()
        assert len(rows) == 1
        assert rows[0].action == "profile.create"
        assert rows[0].actor == "user"
    engine.dispose()
```

- [ ] **Step 10.2: Run, expect fail**

```bash
pytest tests/unit/test_audit.py -v
```
Expected: ImportError.

- [ ] **Step 10.3: Create model**

Create `backend/models/audit_log.py`:
```python
from __future__ import annotations

import time

from sqlalchemy import BigInteger, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[int] = mapped_column(BigInteger, nullable=False, default=lambda: int(time.time() * 1000))
    actor: Mapped[str] = mapped_column(String, nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    target_type: Mapped[str | None] = mapped_column(String, nullable=True)
    target_id: Mapped[str | None] = mapped_column(String, nullable=True)
    details: Mapped[str | None] = mapped_column(String, nullable=True)
```

- [ ] **Step 10.4: Add to migration `0001_initial.py`**

Append to `upgrade()`:
```python
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ts", sa.BigInteger(), nullable=False),
        sa.Column("actor", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("target_type", sa.String(), nullable=True),
        sa.Column("target_id", sa.String(), nullable=True),
        sa.Column("details", sa.String(), nullable=True),
    )
    op.create_index("idx_audit_ts", "audit_log", ["ts"])
```

Append to `downgrade()` (at the top, before drop_table app_settings):
```python
    op.drop_index("idx_audit_ts", table_name="audit_log")
    op.drop_table("audit_log")
```

Also import audit_log in `alembic/env.py`:
```python
from backend.models.audit_log import AuditLog  # noqa: F401
```

- [ ] **Step 10.5: Implement AuditService**

Create `backend/services/audit_service.py`:
```python
from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import sessionmaker

from backend.models.audit_log import AuditLog


class AuditService:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._sf = session_factory

    def record(
        self,
        *,
        actor: str,
        action: str,
        target_type: str | None = None,
        target_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        with self._sf() as session:
            session.add(
                AuditLog(
                    actor=actor,
                    action=action,
                    target_type=target_type,
                    target_id=target_id,
                    details=json.dumps(details) if details else None,
                )
            )
            session.commit()
```

- [ ] **Step 10.6: Run tests**

```bash
pytest tests/unit/test_audit.py -v
```
Expected: 1 passed.

- [ ] **Step 10.7: Commit**

```bash
git add backend/models/audit_log.py backend/services/audit_service.py alembic/versions/0001_initial.py alembic/env.py tests/unit/test_audit.py
git commit -m "feat(audit): add audit_log table and AuditService"
```

---

## Task 11: Structured logging (structlog)

**Files:**
- Create: `backend/core/logging.py`

- [ ] **Step 11.1: Implement logging config**

Create `backend/core/logging.py`:
```python
"""structlog configuration. JSON output to file, pretty console output."""
from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

import structlog


def configure_logging(logs_dir: Path, level: str = "INFO") -> None:
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "app.log"

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        timestamper,
    ]

    structlog.configure(
        processors=shared_processors + [
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer() if sys.stderr.isatty() else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level)),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Also dump JSON-encoded to rotating file
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter("%(message)s"))
    logging.getLogger().addHandler(file_handler)
    logging.getLogger().setLevel(getattr(logging, level))
```

- [ ] **Step 11.2: Smoke test manually**

```bash
python -c "from pathlib import Path; from backend.core.logging import configure_logging; configure_logging(Path('./logs_test')); import structlog; log = structlog.get_logger(); log.info('hello', x=42)"
ls logs_test/
cat logs_test/app.log
```
Expected: line in `app.log`, `hello x=42` printed.

```bash
rm -rf logs_test
```

- [ ] **Step 11.3: Commit**

```bash
git add backend/core/logging.py
git commit -m "feat(logging): structured logging with file + console output"
```

---

## Task 12: API token middleware (TDD)

**Files:**
- Create: `backend/api/__init__.py`
- Create: `backend/api/middleware/__init__.py`
- Create: `backend/api/middleware/auth_token.py`
- Create: `tests/integration/test_api_auth.py`

- [ ] **Step 12.1: Write failing test**

Create `tests/integration/test_api_auth.py`:
```python
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.middleware.auth_token import APITokenMiddleware


def make_app(token: str) -> FastAPI:
    app = FastAPI()
    app.add_middleware(APITokenMiddleware, token=token, exempt_paths=("/healthz",))

    @app.get("/healthz")
    def health():
        return {"ok": True}

    @app.get("/secret")
    def secret():
        return {"secret": 42}

    return app


def test_healthz_allowed_without_token():
    app = make_app("the-secret-token")
    client = TestClient(app)
    r = client.get("/healthz")
    assert r.status_code == 200


def test_secret_requires_token():
    app = make_app("the-secret-token")
    client = TestClient(app)
    r = client.get("/secret")
    assert r.status_code == 401


def test_secret_accepts_correct_token():
    app = make_app("the-secret-token")
    client = TestClient(app)
    r = client.get("/secret", headers={"X-PB-Token": "the-secret-token"})
    assert r.status_code == 200
    assert r.json() == {"secret": 42}


def test_secret_rejects_wrong_token():
    app = make_app("the-secret-token")
    client = TestClient(app)
    r = client.get("/secret", headers={"X-PB-Token": "wrong"})
    assert r.status_code == 401
```

- [ ] **Step 12.2: Run, expect fail**

```bash
pytest tests/integration/test_api_auth.py -v
```
Expected: ImportError.

- [ ] **Step 12.3: Implement middleware**

Create `backend/api/__init__.py` (empty).
Create `backend/api/middleware/__init__.py` (empty).

Create `backend/api/middleware/auth_token.py`:
```python
from __future__ import annotations

import hmac
from typing import Iterable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class APITokenMiddleware(BaseHTTPMiddleware):
    """Require X-PB-Token header on every request except `exempt_paths`."""

    def __init__(self, app, token: str, exempt_paths: Iterable[str] = ()) -> None:
        super().__init__(app)
        self._token = token
        self._exempt = tuple(exempt_paths)

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if any(path.startswith(p) for p in self._exempt):
            return await call_next(request)

        provided = request.headers.get("X-PB-Token", "")
        if not hmac.compare_digest(provided, self._token):
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)

        return await call_next(request)
```

- [ ] **Step 12.4: Run tests**

```bash
pytest tests/integration/test_api_auth.py -v
```
Expected: 4 passed.

- [ ] **Step 12.5: Commit**

```bash
git add backend/api/ tests/integration/test_api_auth.py
git commit -m "feat(api): X-PB-Token middleware with exempt-path support"
```

---

## Task 13: Auth endpoints (`/api/auth/initialize`, `/api/auth/unlock`)

**Files:**
- Create: `backend/api/auth.py`
- Modify: `tests/integration/test_api_auth.py` (extend)

- [ ] **Step 13.1: Write failing test (extend existing file, SYNC TestClient)**

Append to `tests/integration/test_api_auth.py`:
```python
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.core.config import Settings
from backend.api.auth import build_auth_router
from backend.services.security_service import SecurityService


def test_initialize_then_unlock(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    settings = Settings()
    settings.ensure_dirs()
    security = SecurityService(settings)

    app = FastAPI()
    app.include_router(build_auth_router(security))
    client = TestClient(app)

    # Initialize
    r = client.post("/api/auth/initialize", json={"password": "InitPass!1234"})
    assert r.status_code == 201

    # Re-initialize should fail
    r = client.post("/api/auth/initialize", json={"password": "anythingLong12"})
    assert r.status_code == 409

    # Unlock with wrong password
    r = client.post("/api/auth/unlock", json={"password": "wrongpassword12"})
    assert r.status_code == 401

    # Unlock with correct password
    r = client.post("/api/auth/unlock", json={"password": "InitPass!1234"})
    assert r.status_code == 200


def test_unlock_before_initialize(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    settings = Settings()
    settings.ensure_dirs()
    security = SecurityService(settings)

    app = FastAPI()
    app.include_router(build_auth_router(security))
    client = TestClient(app)

    r = client.post("/api/auth/unlock", json={"password": "anylongpassword12"})
    assert r.status_code == 412   # precondition failed: not initialized
```

- [ ] **Step 13.2: Run, expect fail**

```bash
pytest tests/integration/test_api_auth.py -v
```
Expected: ImportError on `build_auth_router`.

- [ ] **Step 13.3: Implement endpoints**

Create `backend/api/auth.py`:
```python
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from backend.services.security_service import (
    AlreadyInitialized,
    InvalidPassword,
    NotInitialized,
    SecurityService,
)


class _PasswordIn(BaseModel):
    password: str = Field(min_length=12, max_length=512)


def build_auth_router(security: SecurityService) -> APIRouter:
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
        engine.dispose()  # caller of SecurityService normally keeps engine; here just verify
        return {"ok": True}

    return router
```

NOTE: in the real app startup we'll keep the engine alive in a global state. Here the endpoint signals success and disposes. Task 14 wires up the lifespan.

- [ ] **Step 13.4: Run tests**

```bash
pytest tests/integration/test_api_auth.py -v
```
Expected: all (4 original + 2 new) = 6 passed.

- [ ] **Step 13.5: Commit**

```bash
git add backend/api/auth.py tests/integration/test_api_auth.py
git commit -m "feat(api): /api/auth/initialize and /api/auth/unlock endpoints"
```

---

## Task 14: App startup wiring (lifespan, token generation, mount middleware)

**Files:**
- Create/Modify: `backend/main.py`

- [ ] **Step 14.1: Write the file**

Replace or create `backend/main.py`:
```python
"""FastAPI application entry point."""
from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog
from fastapi import FastAPI

from backend.api.auth import build_auth_router
from backend.api.middleware.auth_token import APITokenMiddleware
from backend.core.config import Settings
from backend.core.logging import configure_logging
from backend.core.security import generate_api_token
from backend.services.security_service import SecurityService


def create_app() -> FastAPI:
    settings = Settings()
    settings.ensure_dirs()
    configure_logging(settings.logs_dir)
    log = structlog.get_logger("private-browser.startup")

    token = generate_api_token()
    settings.api_token = token   # share to UI via stdout one-time print

    security = SecurityService(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        log.info("app.start", port=settings.api_port, host=settings.api_host)
        # Print token to stdout so launcher / pywebview can capture it
        print(f"PB_API_TOKEN={token}", flush=True, file=sys.stdout)
        try:
            yield
        finally:
            log.info("app.stop")

    app = FastAPI(title="private-browser", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        APITokenMiddleware,
        token=token,
        exempt_paths=("/healthz", "/docs", "/openapi.json", "/redoc"),
    )

    @app.get("/healthz")
    async def healthz() -> dict:
        return {"ok": True}

    app.include_router(build_auth_router(security))
    return app


app = create_app()
```

- [ ] **Step 14.2: Manual run + curl smoke**

```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8769 &
sleep 1
curl -i http://127.0.0.1:8769/healthz
# expect 200
curl -i http://127.0.0.1:8769/api/auth/initialize -H 'Content-Type: application/json' -d '{"password":"TestPass!1234"}'
# expect 401 (no token!)
# now grab token from uvicorn output and:
TOKEN=<from-stdout>
curl -i -X POST http://127.0.0.1:8769/api/auth/initialize -H "X-PB-Token: $TOKEN" -H 'Content-Type: application/json' -d '{"password":"TestPass!1234"}'
# expect 201
curl -i -X POST http://127.0.0.1:8769/api/auth/unlock -H "X-PB-Token: $TOKEN" -H 'Content-Type: application/json' -d '{"password":"TestPass!1234"}'
# expect 200
kill %1
```
Expected: each curl returns the expected status. Then check `%APPDATA%/private-browser/`:
- `app.db` exists, large (encrypted)
- `app.salt` exists, 16 bytes
- `logs/app.log` has startup entries

- [ ] **Step 14.3: Cleanup test DB**

```bash
rm -rf "${APPDATA:-$HOME}/private-browser"
```

- [ ] **Step 14.4: Commit**

```bash
git add backend/main.py
git commit -m "feat(app): wire SecurityService + token middleware + lifespan logging"
```

---

## Task 15: CI workflow (GitHub Actions)

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 15.1: Write workflow**

Create `.github/workflows/ci.yml`:
```yaml
name: CI
on:
  push:
  pull_request:

jobs:
  test:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install deps
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"
      - name: Lint
        run: |
          ruff check .
      - name: Test
        run: |
          pytest -q
```

- [ ] **Step 15.2: Add `ruff` config**

Append to `pyproject.toml`:
```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "W", "B", "UP", "ASYNC"]
ignore = ["E501"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 15.3: Local lint**

```bash
ruff check .
```
Expected: 0 errors (or only minor that we fix).

- [ ] **Step 15.4: Commit + push**

```bash
git add .github/ pyproject.toml
git commit -m "ci: add GitHub Actions workflow for lint + tests"
git push origin main
```

Verify in GitHub UI: workflow run is green.

---

## Task 16: M1 acceptance test (full happy path)

**Files:**
- Create: `tests/integration/test_m1_acceptance.py`

- [ ] **Step 16.1: Write end-to-end acceptance test**

```python
"""M1 acceptance: fresh install → initialize → restart → unlock works."""
from __future__ import annotations

from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.services.security_service import (
    SecurityService,
    InvalidPassword,
    NotInitialized,
)


def test_m1_full_happy_path(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))

    # 1. Fresh app, no DB
    settings_1 = Settings()
    settings_1.ensure_dirs()
    sec_1 = SecurityService(settings_1)
    with pytest.raises(NotInitialized):
        sec_1.unlock("anything")

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
```

- [ ] **Step 16.2: Run**

```bash
pytest tests/integration/test_m1_acceptance.py -v
```
Expected: 2 passed.

- [ ] **Step 16.3: Commit**

```bash
git add tests/integration/test_m1_acceptance.py
git commit -m "test: M1 acceptance — fresh install → init → restart → unlock"
```

---

## Task 17: Final M1 review checkpoint

- [ ] **Step 17.1: Manual run on clean env**

```bash
# Remove ALL existing data
rm -rf "${APPDATA:-$HOME}/private-browser"

# Start uvicorn
uvicorn backend.main:app --port 8769

# In another shell:
TOKEN=<from-stdout-line "PB_API_TOKEN=...">
curl -X POST http://127.0.0.1:8769/api/auth/initialize \
  -H "X-PB-Token: $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"password":"MyMaster!2026"}'
# 201

# Kill uvicorn (Ctrl+C). Restart it. NEW token now.
NEW_TOKEN=<from-stdout>
# OLD token should not work:
curl -i -X POST http://127.0.0.1:8769/api/auth/unlock \
  -H "X-PB-Token: $TOKEN" \
  -d '{"password":"MyMaster!2026"}'
# 401 (old token rejected)

# New token works:
curl -X POST http://127.0.0.1:8769/api/auth/unlock \
  -H "X-PB-Token: $NEW_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"password":"MyMaster!2026"}'
# 200
```

All three must behave as commented.

- [ ] **Step 17.2: Verify on-disk encryption**

```bash
# Hex first 64 bytes of app.db:
xxd "${APPDATA:-$HOME}/private-browser/app.db" | head -5
```
Expected: no plaintext "SQLite format 3" / no readable strings.

- [ ] **Step 17.3: Verify CI green on `main`**

Open GitHub → Actions tab → latest run on main is green.

- [ ] **Step 17.4: Tag milestone**

```bash
git tag v0.1.0-m1 -m "M1 foundation complete: fork, rebrand, SQLCipher, master password, API token, audit log"
git push origin v0.1.0-m1
```

- [ ] **Step 17.5: Update CHANGELOG**

Create `CHANGELOG.md`:
```markdown
# Changelog

## [v0.1.0-m1] — 2026-XX-XX
### Added
- Forked from polyackiy/camoufox-profile-manager (MIT)
- Rebranded as `private-browser`
- SQLCipher-encrypted database (Argon2id KDF, HMAC verifier)
- Master password initialize/unlock REST API
- Random per-startup API token middleware
- Audit log table + AuditService
- Structured logging (structlog) with file rotation
- Alembic-managed schema with initial migration
- GitHub Actions CI (Windows-latest, ruff + pytest)
```

```bash
git add CHANGELOG.md
git commit -m "docs: changelog v0.1.0-m1"
git push
```

---

## Definition of Done (M1)

Plan 1 is **complete** when ALL of the following are true:

- ✅ All 17 tasks ticked
- ✅ All tests pass locally: `pytest -q` shows 0 failures
- ✅ CI green on `main`
- ✅ Manual acceptance test (Task 17.1) passes step-by-step
- ✅ `app.db` on disk is encrypted (Task 17.2)
- ✅ Tag `v0.1.0-m1` exists on `origin`
- ✅ `CHANGELOG.md` reflects the milestone

## Next plan

After M1 is signed off, write **Plan 2: M2 — FingerprintGenerator + Profile API** (see [09-phasing-and-milestones.md](../specs/2026-05-24-private-browser/09-phasing-and-milestones.md) M2 section).
