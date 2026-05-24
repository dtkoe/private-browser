# Plan 6 — M6: Distribution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans.

**Goal:** Ship a runnable Windows desktop app: PyInstaller `.exe` bundling backend + shell + frontend; NSIS installer with shortcuts + `.pbprof` file association + uninstaller; portable ZIP layout; first-run Camoufox auto-download; user docs.

**Architecture:**
- PyInstaller spec produces `dist/private-browser/private-browser.exe` (onedir mode — Windows Defender is less suspicious of onedir than onefile)
- Bundle includes: backend modules, shell/run_app.py as entry, frontend/out/, sqlcipher3 native DLLs, camoufox python package (NOT the Camoufox binary — too large; downloaded on first run)
- NSIS script wraps the dist/private-browser folder + sets up shortcuts + registers `.pbprof` extension association
- Portable: zip of `dist/private-browser/`
- First-run Camoufox download: shell checks for `%APPDATA%/private-browser/camoufox/camoufox.exe`; if missing, runs `python -m camoufox fetch` (or equivalent) with progress logging
- Release: `gh release create vX.Y.Z dist/*.exe dist/*.zip` (manual, requires user)

**Tech Stack:** PyInstaller 6.x, NSIS 3.x (or stub script, since NSIS may not be installed). Compile is a manual step; we ship the configuration.

**Source spec:** [09 M6](../specs/2026-05-24-private-browser/09-phasing-and-milestones.md).

## Scope reduction vs spec (deliberate)

- ✅ PyInstaller `.spec` + build script
- ✅ NSIS installer script (`installer/private-browser.nsi`)
- ✅ Portable ZIP build script (just zips PyInstaller output)
- ✅ Camoufox first-run download integration in shell
- ✅ User guide / Troubleshooting / Contributing docs
- ✅ README polish
- ✅ Auto-update notification stub (checks GitHub releases, shows in UI)
- ⏭ Actual binary release (requires user to run scripts + push to GH — we ship the recipe)
- ⏭ Single-instance lock (Windows mutex) — added as a small fix
- ⏭ Signed binaries (requires user's code-signing cert)

## File map

| Путь | Цель | Действие |
|---|---|---|
| `pyproject.toml` | pin pyinstaller as dev dep | Modify |
| `build/private_browser.spec` | PyInstaller spec | Create |
| `build/build_app.py` | build orchestrator (clean → pyinstaller → zip) | Create |
| `installer/private-browser.nsi` | NSIS installer script | Create |
| `installer/README.md` | how to install NSIS + build the installer | Create |
| `shell/run_app.py` | add: Camoufox check + download, single-instance mutex | Modify |
| `shell/camoufox_fetch.py` | wrapper around `camoufox fetch` with status log | Create |
| `backend/services/update_checker.py` | poll GH Releases for latest tag | Create |
| `backend/api/system.py` | `/api/system/info` + `/api/system/check-updates` | Create |
| `backend/main.py` | wire system router | Modify |
| `frontend/components/SettingsPanel.tsx` | show version + update check button | Modify |
| `frontend/lib/api.ts` | add system endpoints | Modify |
| `README.md` | full README — install / use / build | Replace |
| `docs/USER_GUIDE.md` | user-facing tutorial | Create |
| `docs/TROUBLESHOOTING.md` | known issues + workarounds | Create |
| `CONTRIBUTING.md` | dev setup, branching, commits | Create |
| `tests/unit/test_update_checker.py` | mocked-httpx update check | Create |
| `tests/integration/test_api_system.py` | endpoint tests | Create |

---

## Task 1: PyInstaller spec + build orchestrator

- [ ] **Step 1.1: Pin pyinstaller**

`pyproject.toml` — append to `[project.optional-dependencies] dev`:
```toml
    "pyinstaller>=6.10",
```

`.venv/Scripts/python.exe -m pip install -e ".[dev]"`.

- [ ] **Step 1.2: `build/private_browser.spec`**

```python
# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for private-browser desktop bundle."""
import os
from pathlib import Path

block_cipher = None
ROOT = Path(SPECPATH).parent  # build/ → repo root

# Hidden imports: sqlalchemy dialects + sqlcipher3 + structlog
hidden = [
    "sqlcipher3",
    "sqlcipher3.dbapi2",
    "sqlalchemy.dialects.sqlite",
    "uvicorn.logging",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.http.httptools_impl",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.lifespan.on",
    "structlog",
    "alembic",
    "alembic.runtime.migration",
    "argon2.low_level",
    "cryptography.hazmat.primitives.ciphers.aead",
    "apscheduler",
    "apscheduler.schedulers.background",
    "apscheduler.executors.pool",
    "apscheduler.triggers.interval",
    "webview",
    "webview.platforms.winforms",
]

datas = [
    (str(ROOT / "frontend" / "out"), "frontend/out"),
    (str(ROOT / "alembic"), "alembic"),
    (str(ROOT / "alembic.ini"), "."),
]

a = Analysis(
    [str(ROOT / "shell" / "run_app.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "pytest"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="private-browser",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="private-browser",
)
```

- [ ] **Step 1.3: Build orchestrator script**

`build/build_app.py`:
```python
"""Build private-browser desktop bundle. Run from repo root."""
from __future__ import annotations

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
BUILD = ROOT / "build"


def run(cmd: list[str], cwd: Path) -> None:
    print(f"[build] $ {' '.join(cmd)}")
    subprocess.check_call(cmd, cwd=str(cwd))


def main() -> None:
    print("[build] clean previous outputs")
    for p in (DIST / "private-browser", DIST / "private-browser.zip"):
        if p.exists():
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()

    print("[build] frontend build")
    fe = ROOT / "frontend"
    if not (fe / "node_modules").exists():
        run(["npm", "install", "--no-audit", "--no-fund"], cwd=fe)
    run(["npm", "run", "build"], cwd=fe)

    print("[build] pyinstaller")
    run([sys.executable, "-m", "PyInstaller", "--noconfirm",
         "--clean", str(BUILD / "private_browser.spec")],
        cwd=ROOT)

    print("[build] zip portable")
    folder = DIST / "private-browser"
    zip_path = DIST / "private-browser-portable.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in folder.rglob("*"):
            if f.is_file():
                zf.write(f, f.relative_to(DIST))
    print(f"[build] done. {zip_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 1.4: Commit**

```bash
git add pyproject.toml build/
git commit -m "feat(dist): PyInstaller spec + build orchestrator"
```

---

## Task 2: Camoufox first-run download integration

- [ ] **Step 2.1: `shell/camoufox_fetch.py`**

```python
"""Run `camoufox fetch` (or check if already present) with logging."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def camoufox_binary_path() -> Path:
    # Camoufox stores itself under %LOCALAPPDATA% or its own per-package data dir
    # We allow override via PB_CAMOUFOX_DIR
    explicit = os.environ.get("PB_CAMOUFOX_DIR")
    if explicit:
        return Path(explicit) / "camoufox.exe"
    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "camoufox"
    return base / "camoufox.exe"


def is_camoufox_installed() -> bool:
    """Best-effort detection — Camoufox SDK can locate its own binary."""
    try:
        from camoufox.pkgman import installed_version
        return installed_version() is not None
    except Exception:
        return camoufox_binary_path().is_file()


def fetch_camoufox(log) -> None:
    """Invoke `python -m camoufox fetch`. log is a callable accepting str."""
    log("[camoufox] downloading Camoufox bundle…")
    cmd = [sys.executable, "-m", "camoufox", "fetch"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, bufsize=1)
    assert proc.stdout is not None
    for line in proc.stdout:
        log(f"[camoufox] {line.rstrip()}")
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"camoufox fetch failed with rc={proc.returncode}")
    log("[camoufox] done.")
```

- [ ] **Step 2.2: Wire into `shell/run_app.py`**

In `shell/run_app.py`, before `start_backend`:
```python
from shell.camoufox_fetch import fetch_camoufox, is_camoufox_installed

def ensure_camoufox(log=print) -> None:
    if is_camoufox_installed():
        log("[camoufox] already present.")
        return
    log("[camoufox] not installed — first-run download (this may take 5-10 min)…")
    fetch_camoufox(log)

# in main(), before start_backend:
ensure_camoufox()
```

- [ ] **Step 2.3: Single-instance mutex (Windows)**

In `shell/run_app.py`, at start of `main()`:
```python
if sys.platform == "win32":
    import ctypes
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "Global\\private-browser-mutex-v1")
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        print("[shell] Another instance is already running.", file=sys.stderr)
        sys.exit(1)
```

- [ ] **Step 2.4: Commit**

```bash
git add shell/
git commit -m "feat(shell): single-instance mutex + Camoufox first-run download"
```

---

## Task 3: Update checker (poll GH Releases)

- [ ] **Step 3.1: Implement**

`backend/services/update_checker.py`:
```python
from __future__ import annotations

from dataclasses import dataclass

import httpx


@dataclass
class UpdateInfo:
    current_version: str
    latest_version: str | None
    has_update: bool
    release_url: str | None


def _version_tuple(v: str) -> tuple:
    parts = v.lstrip("v").split("-")[0].split(".")
    return tuple(int(p) if p.isdigit() else 0 for p in parts)


class UpdateChecker:
    def __init__(self, repo: str = "dtkoe/private-browser", current_version: str = "0.6.0"):
        self._repo = repo
        self._current = current_version

    def check(self, *, client: httpx.Client | None = None) -> UpdateInfo:
        url = f"https://api.github.com/repos/{self._repo}/releases/latest"
        try:
            c = client or httpx.Client(timeout=5.0)
            r = c.get(url, headers={"Accept": "application/vnd.github+json"})
            r.raise_for_status()
            data = r.json()
        except Exception:
            return UpdateInfo(self._current, None, False, None)

        latest = (data.get("tag_name") or "").lstrip("v")
        if not latest:
            return UpdateInfo(self._current, None, False, None)
        return UpdateInfo(
            current_version=self._current,
            latest_version=latest,
            has_update=_version_tuple(latest) > _version_tuple(self._current),
            release_url=data.get("html_url"),
        )
```

- [ ] **Step 3.2: Tests**

`tests/unit/test_update_checker.py`:
```python
from backend.services.update_checker import UpdateChecker


class _FakeResponse:
    def __init__(self, j, status=200):
        self._j = j; self.status_code = status
    def json(self): return self._j
    def raise_for_status(self):
        if self.status_code >= 400: raise RuntimeError("err")


class _FakeClient:
    def __init__(self, r): self._r = r
    def get(self, url, headers=None): return self._r


def test_no_update():
    c = UpdateChecker(current_version="9.9.9")
    res = c.check(client=_FakeClient(_FakeResponse({"tag_name": "v0.1.0", "html_url": "x"})))
    assert res.has_update is False


def test_update_available():
    c = UpdateChecker(current_version="0.1.0")
    res = c.check(client=_FakeClient(_FakeResponse({"tag_name": "v0.5.0", "html_url": "x"})))
    assert res.has_update is True
    assert res.latest_version == "0.5.0"


def test_request_fails():
    class _Boom:
        def get(self, *a, **k): raise RuntimeError("net")
    c = UpdateChecker(current_version="0.1.0")
    res = c.check(client=_Boom())
    assert res.has_update is False
```

- [ ] **Step 3.3: System API endpoints**

`backend/api/system.py`:
```python
from __future__ import annotations

from fastapi import APIRouter

from backend.services.update_checker import UpdateChecker

VERSION = "0.6.0"


def build_system_router() -> APIRouter:
    router = APIRouter(tags=["system"])

    @router.get("/api/system/info")
    def info():
        return {"version": VERSION, "name": "private-browser"}

    @router.get("/api/system/check-updates")
    def check():
        u = UpdateChecker(current_version=VERSION).check()
        return {
            "current_version": u.current_version,
            "latest_version": u.latest_version,
            "has_update": u.has_update,
            "release_url": u.release_url,
        }

    return router
```

Wire in `backend/main.py`:
```python
from backend.api.system import build_system_router
# ...
app.include_router(build_system_router())
```

Tests:
```python
# tests/integration/test_api_system.py
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    import backend.services.camoufox_launcher as cl
    from tests.unit.test_launch_manager import FakeLauncher
    monkeypatch.setattr(cl, "CamoufoxLauncher", FakeLauncher)
    import backend.main as m
    monkeypatch.setattr(m, "CamoufoxLauncher", FakeLauncher)
    app = m.create_app()
    c = TestClient(app)
    c.headers["X-PB-Token"] = app.state.settings.api_token
    return c


def test_system_info(client):
    r = client.get("/api/system/info")
    assert r.status_code == 200
    assert "version" in r.json()
```

- [ ] **Step 3.4: Commit**

```bash
git add backend/services/update_checker.py backend/api/system.py backend/main.py tests/unit/test_update_checker.py tests/integration/test_api_system.py
git commit -m "feat(updates): GH Releases polling + /api/system/info|check-updates"
```

---

## Task 4: NSIS installer script

- [ ] **Step 4.1: `installer/private-browser.nsi`**

```nsis
; Private Browser NSIS installer
!define APPNAME "Private Browser"
!define COMPANYNAME "private-browser"
!define DESCRIPTION "Anti-detect browser manager"
!define VERSIONMAJOR 0
!define VERSIONMINOR 6
!define VERSIONBUILD 0
!define HELPURL "https://github.com/dtkoe/private-browser"

RequestExecutionLevel user
InstallDir "$LOCALAPPDATA\${COMPANYNAME}"
Name "${APPNAME}"
OutFile "private-browser-setup.exe"

Page directory
Page instfiles
UninstPage uninstConfirm
UninstPage instfiles

Section "install"
    SetOutPath $INSTDIR
    File /r "..\dist\private-browser\*.*"

    ; Start menu shortcut
    CreateDirectory "$SMPROGRAMS\${APPNAME}"
    CreateShortcut "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk" "$INSTDIR\private-browser.exe"
    CreateShortcut "$DESKTOP\${APPNAME}.lnk" "$INSTDIR\private-browser.exe"

    ; .pbprof association
    WriteRegStr HKCU "Software\Classes\.pbprof" "" "PrivateBrowser.Profile"
    WriteRegStr HKCU "Software\Classes\PrivateBrowser.Profile" "" "Private Browser Profile"
    WriteRegStr HKCU "Software\Classes\PrivateBrowser.Profile\DefaultIcon" "" "$INSTDIR\private-browser.exe,0"
    WriteRegStr HKCU "Software\Classes\PrivateBrowser.Profile\shell\open\command" "" '"$INSTDIR\private-browser.exe" "%1"'

    ; Add/Remove Programs
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "DisplayName" "${APPNAME}"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "UninstallString" "$\"$INSTDIR\uninstall.exe$\""
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "DisplayVersion" "${VERSIONMAJOR}.${VERSIONMINOR}.${VERSIONBUILD}"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "Publisher" "${COMPANYNAME}"

    WriteUninstaller "$INSTDIR\uninstall.exe"
SectionEnd

Section "uninstall"
    Delete "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk"
    RMDir "$SMPROGRAMS\${APPNAME}"
    Delete "$DESKTOP\${APPNAME}.lnk"
    DeleteRegKey HKCU "Software\Classes\.pbprof"
    DeleteRegKey HKCU "Software\Classes\PrivateBrowser.Profile"
    DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}"

    ; Note: %APPDATA%\private-browser\ (user data) is preserved by default.
    ; Uncomment next line to also remove user data:
    ; RMDir /r "$APPDATA\private-browser"

    RMDir /r "$INSTDIR"
SectionEnd
```

- [ ] **Step 4.2: `installer/README.md`**

```markdown
# Building the Windows installer

## Prerequisites
- [NSIS 3.x](https://nsis.sourceforge.io/Download) installed (`makensis` on PATH)
- PyInstaller build already done: `python build/build_app.py`

## Build
```
cd installer
makensis private-browser.nsi
```
Outputs `installer/private-browser-setup.exe`.

## Distribution
- Installer: `installer/private-browser-setup.exe` (no admin required, installs to %LOCALAPPDATA%)
- Portable: `dist/private-browser-portable.zip` (unzip anywhere, run private-browser.exe)
```

- [ ] **Step 4.3: Commit**

```bash
git add installer/
git commit -m "feat(dist): NSIS installer script with .pbprof association"
```

---

## Task 5: Documentation

- [ ] **Step 5.1: README replacement**

`README.md`:
```markdown
# Private Browser

Open-source anti-detect browser manager for Windows, built on [Camoufox](https://github.com/daijro/camoufox) (Firefox-based anti-detect engine).

Multiple isolated browser profiles, each with its own fingerprint, proxy, cookies, and extensions. Encrypted local storage. No telemetry.

## Features

- **Fingerprint isolation per profile** — UA, screen, WebGL, fonts, timezone, canvas/audio noise, hardware concurrency, etc.
- **Proxy pool** — HTTP / HTTPS / SOCKS5 with health checks and per-profile binding
- **WebRTC leak prevention** — proxy mode when a proxy is bound; full block when not
- **Encrypted at rest** — SQLCipher (Argon2id KDF) + master password
- **Extensions** — per-profile Firefox addon install/remove
- **`.pbprof` export/import** — encrypted (AES-256-GCM + HMAC) profile bundles
- **Profile cloning + bulk operations**

## Quick start (end-user)

1. Download `private-browser-setup.exe` from [Releases](https://github.com/dtkoe/private-browser/releases)
2. Run it (no admin needed)
3. Launch from Start Menu — set a master password on first run
4. Click **+ New** to create a profile, then **▶ Launch**

On first launch Camoufox (~150 MB Firefox-based browser) downloads automatically.

## Build from source

```bash
git clone https://github.com/dtkoe/private-browser
cd private-browser
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
python -m playwright install firefox
python -m camoufox fetch

cd frontend && npm install && npm run build && cd ..
python shell/run_app.py
```

To build the standalone .exe:
```bash
python build/build_app.py
# outputs dist/private-browser/ + dist/private-browser-portable.zip
```

## Documentation

- [User Guide](docs/USER_GUIDE.md) — UI walkthrough
- [Troubleshooting](docs/TROUBLESHOOTING.md) — known issues
- [Contributing](CONTRIBUTING.md) — dev setup, branching, commits
- [Architecture spec](docs/superpowers/specs/2026-05-24-private-browser/) — design docs
- [Changelog](CHANGELOG.md)

## License

MIT — see [LICENSE](LICENSE).

## Acknowledgements

- [@daijro](https://github.com/daijro) for [Camoufox](https://github.com/daijro/camoufox)
- The [CloverLabsAI](https://github.com/CloverLabsAI/camoufox) community fork
```

- [ ] **Step 5.2: `docs/USER_GUIDE.md`**

```markdown
# User Guide

## First run

1. Launch Private Browser. A "Create a master password" screen appears.
2. Enter a password (≥12 characters). **There is no recovery** — lose it and your data is gone.
3. The app downloads Camoufox (~150 MB, one-time). Watch the console log for progress.

## Creating a profile

- Click **+ New** in the left sidebar.
- Optionally pick an OS to target (Windows / macOS / Linux). Otherwise a weighted-random OS is chosen.
- Click **Create**. The profile appears in the sidebar with a generated fingerprint.

## Launching

- Select a profile in the sidebar.
- Click **▶ Launch**. A real Camoufox window opens with the configured fingerprint.
- Use it like any browser. Cookies/history are saved to the profile's data dir.
- Click **Stop** in the UI (or close the browser window) to end the session.

## Proxies

- Open the **Proxies** tab.
- Add one via the form, or paste many lines (`host:port` or `host:port:user:pass`) into "Batch import".
- Click **Check** to verify a proxy via ipinfo.io — sees the exit IP and geo.
- Background scheduler re-checks every 30 minutes.

## Binding a proxy

- In a profile's detail panel, pick a proxy from the dropdown. The profile launches with it.
- "No proxy" mode forces WebRTC off entirely (prevents IP leakage).

## Export / Import

- **Export**: profile detail panel → **Export** → set a password (≥12). A `.pbprof` file downloads.
- **Import**: top bar → **Import** → pick `.pbprof` → enter password. A new profile is created with the same fingerprint and (if included) cookies.
- Wrong password → "401". Tampered file → "422".

## Extensions

- In a profile's detail panel, scroll to the Extensions block.
- **+ Install .xpi**: upload a Firefox addon file.
- Extensions are per-profile — installed in A is absent in B.

## Locking

- Top-right **Lock** button forgets the unlocked DB engine in memory. To return you must re-enter the master password.
```

- [ ] **Step 5.3: `docs/TROUBLESHOOTING.md`**

```markdown
# Troubleshooting

## "Camoufox fetch failed"
- Windows Defender may quarantine the binary on first download. Add `%LOCALAPPDATA%\camoufox` to exclusions and retry.
- Behind a corporate proxy? Set `HTTPS_PROXY=http://...` before running `python -m camoufox fetch`.

## App doesn't start — port 8769 already in use
- Another instance is running. The single-instance mutex should prevent this, but if it leaks: kill `private-browser.exe` in Task Manager.

## "invalid password" but I know it's right
- The salt sidecar (`app.salt` next to `app.db` in `%APPDATA%\private-browser\`) is required. If you copied `app.db` but not `app.salt`, unlock will always fail.

## Lost master password
- There is no recovery. Delete `%APPDATA%\private-browser\` to start fresh (all profiles lost).
- Plan ahead: export important profiles as `.pbprof` files — those can be re-encrypted with a different password.

## Profile won't launch with proxy
- The bound proxy might have been deleted — launch returns 409. Either rebind or remove the proxy from the profile.
- The proxy itself might be dead — open Proxies tab, click **Check** to see the latest status.

## Extension installed but Firefox doesn't load it
- Camoufox / Firefox needs to be restarted for a new extension to take effect.
- Make sure the .xpi is signed (unsigned XPIs are blocked by default Firefox unless dev mode).

## Logs
- `%APPDATA%\private-browser\logs\app.log` — structured backend log
- Console where the app was launched — shell + backend stdout

## "DB header looks like plaintext SQLite — encryption is NOT engaged"
- This means SQLCipher failed to initialize. Reinstall: `pip install --force-reinstall sqlcipher3-wheels`.
```

- [ ] **Step 5.4: `CONTRIBUTING.md`**

```markdown
# Contributing

## Dev setup

```
git clone https://github.com/dtkoe/private-browser
cd private-browser
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
python -m playwright install firefox
python -m camoufox fetch
cd frontend && npm install && npm run build && cd ..
```

Run:
- Backend only: `uvicorn backend.main:app --reload --port 8769`
- Full app (with shell): `python shell/run_app.py`
- Tests: `pytest -q -m "not slow"`
- Lint: `ruff check .`
- Frontend dev: `cd frontend && npm run dev`

## Code style
- Python: PEP-8 enforced by ruff (line-length 100, E/F/I/W/B/UP/ASYNC selected, B008 ignored).
- TypeScript: Next.js defaults; pin component logic to small focused files.

## Commits
- Conventional commits: `feat(scope):`, `fix(scope):`, `docs:`, `chore:`, `test:`, `refactor:`.
- Reference the milestone for in-scope work: `feat(M3): …`.
- Co-author trailers and AI-generated footers are NOT added.

## Branching
- Main branch is the development line.
- Tag releases as `vX.Y.Z-mN` (e.g., `v0.5.0-m5`).

## Tests
- New backend services need TDD: failing unit test first, then implementation.
- API endpoints need integration tests using FastAPI's TestClient.
- Acceptance tests live under `tests/integration/test_mN_acceptance.py` and cover the milestone's user-facing flow end-to-end.
- Real-Camoufox tests are marked `slow` and excluded from the default run.

## Adding a milestone
- Write the plan in `docs/superpowers/plans/YYYY-MM-DD-plan-N-mN-name.md`.
- Execute task-by-task, committing after each.
- Update `CHANGELOG.md` with the milestone entry.
- Tag `vX.Y.Z-mN`.
```

- [ ] **Step 5.5: Commit**

```bash
git add README.md docs/USER_GUIDE.md docs/TROUBLESHOOTING.md CONTRIBUTING.md
git commit -m "docs: README + USER_GUIDE + TROUBLESHOOTING + CONTRIBUTING"
```

---

## Task 6: M6 acceptance + tag

- [ ] **Step 6.1: Run full suite**

```bash
.venv/Scripts/python.exe -m pytest -q -m "not slow"
```
Expected: all green.

- [ ] **Step 6.2: Lint**

```bash
.venv/Scripts/python.exe -m ruff check .
```

- [ ] **Step 6.3: Smoke build (optional, may take 1-2 minutes)**

```bash
python build/build_app.py
ls dist/private-browser/
```
Expected: `private-browser.exe` exists, ~80-200 MB total.

- [ ] **Step 6.4: Update CHANGELOG**

```markdown
## [v0.6.0-m6] — 2026-XX-XX
### Added
- PyInstaller bundling configuration (build/private_browser.spec, build/build_app.py)
- NSIS installer script with .pbprof association + Start Menu/Desktop shortcuts (installer/private-browser.nsi)
- Portable ZIP build via build_app.py
- Camoufox first-run auto-download (shell/camoufox_fetch.py)
- Single-instance Windows mutex
- Update checker (GH Releases polling) + /api/system/info|check-updates endpoints
- README + USER_GUIDE + TROUBLESHOOTING + CONTRIBUTING docs
```

- [ ] **Step 6.5: Tag**

```bash
git add CHANGELOG.md
git commit -m "docs: CHANGELOG v0.6.0-m6"
git tag v0.6.0-m6 -m "M6: Distribution + docs"
```

---

## Definition of Done (M6)

- ✅ PyInstaller spec, build script
- ✅ NSIS installer script
- ✅ First-run Camoufox download wired
- ✅ Single-instance lock
- ✅ Update checker + /api/system endpoints
- ✅ README, USER_GUIDE, TROUBLESHOOTING, CONTRIBUTING
- ✅ All tests still pass (~145+)
- ✅ Tag `v0.6.0-m6`

## What's left after M6 (manual user steps)
- Install NSIS, run `makensis installer/private-browser.nsi` → ship `.exe`
- Run `python build/build_app.py` → ship `.zip`
- `gh release create v0.6.0-m6 ...` — push artifacts to GitHub
