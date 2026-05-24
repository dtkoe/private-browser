# Plan 5 — M5: .pbprof export/import + extensions + cloning + bulk Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans.

**Goal:** Encrypted `.pbprof` round-trip (export + import), profile cloning (with/without browser data), bulk launch / delete / export, Firefox extension list + install (.xpi) + remove. Round-trip preserves cookies. Extensions visible in one profile and absent in another.

**Architecture:** New `ImportExportService` (Argon2id KDF + AES-256-GCM + HMAC-SHA256 + ZIP packaging — reuses primitives from `backend/core/security.py`). New `ExtensionService` (reads/writes `extensions.json` and `extensions/` dir inside the profile's `user_data_dir`). New REST endpoints + UI panel for both. Bulk = simple loop over profile IDs.

**Tech Stack:** Same as M4. New deps: none — `cryptography` (already), `argon2-cffi` (already), `zipfile` stdlib.

**Source spec:** [05-profile-model.md (.pbprof)](../specs/2026-05-24-private-browser/05-profile-model.md), [09-phasing-and-milestones.md M5](../specs/2026-05-24-private-browser/09-phasing-and-milestones.md).

## Scope (what we ship)

- ✅ `.pbprof` format per spec — zip with `manifest.json` (plaintext) + `payload.enc` (AES-256-GCM) + `signature.bin` (HMAC-SHA256)
- ✅ Export: profile + optional cookies snapshot + optional extensions list
- ✅ Import: creates new profile with new UUID; copies cookies into new `user_data_dir`
- ✅ Profile clone (server-side fast duplicate, optional skip cookies)
- ✅ Bulk endpoints: `POST /api/profiles/bulk/delete`, `POST /api/profiles/bulk/launch`, `POST /api/profiles/bulk/export`
- ✅ Extension list, install (.xpi upload), remove
- ✅ UI: export modal (password prompt), import (file picker), extensions list per profile, bulk select via checkbox
- ⏭ Deferred to M6: NSIS file association, drag-drop, recovery codes (use master password recovery via "I lost it = data is gone" model from M1), activity log viewer

## File map

| Путь | Цель | Действие |
|---|---|---|
| `backend/services/import_export_service.py` | encrypt/decrypt .pbprof | Create |
| `backend/services/extension_service.py` | read/install/remove Firefox extensions | Create |
| `backend/services/profile_service.py` | add `clone(profile_id, *, include_cookies)` + `bulk_delete` | Modify |
| `backend/api/export_import.py` | `/api/profiles/{id}/export`, `/api/import` | Create |
| `backend/api/extensions.py` | `/api/profiles/{id}/extensions/*` | Create |
| `backend/api/profiles.py` | add `/clone` + `/bulk/*` endpoints | Modify |
| `backend/main.py` | wire new routers | Modify |
| `frontend/lib/api.ts` | add new endpoints | Modify |
| `frontend/components/ExportModal.tsx` | password-prompt + options | Create |
| `frontend/components/ImportModal.tsx` | file picker + password | Create |
| `frontend/components/ExtensionsPanel.tsx` | shown inside ProfileDetail collapsible | Create |
| `frontend/components/ProfileDetail.tsx` | wire Clone + Export buttons + extensions | Modify |
| `frontend/components/Sidebar.tsx` | multiselect + bulk actions toolbar | Modify |
| `frontend/app/page.tsx` | hold selected-set + bulk handlers | Modify |
| `tests/unit/test_import_export.py` | round-trip tests | Create |
| `tests/unit/test_extension_service.py` | xpi install/remove | Create |
| `tests/integration/test_api_export_import.py` | full export+import HTTP cycle | Create |
| `tests/integration/test_m5_acceptance.py` | round-trip via API | Create |

---

## Task 1: ImportExportService (TDD)

**Files:**
- Create: `backend/services/import_export_service.py`
- Create: `tests/unit/test_import_export.py`

The format per spec: zip containing `manifest.json` (plaintext), `payload.enc` (AES-256-GCM ciphertext of JSON payload), `signature.bin` (HMAC-SHA256(payload.enc, derived_key)).

- [ ] **Step 1.1: Write failing tests**

```python
# tests/unit/test_import_export.py
import json

import pytest

from backend.services.import_export_service import (
    ImportExportService,
    PbprofIntegrityError,
    PbprofPasswordError,
)


@pytest.fixture
def svc():
    return ImportExportService()


def test_round_trip_text_payload(svc, tmp_path):
    payload = {"profile": {"id": "x", "name": "Acc"}, "proxy": None, "browser_data": None}
    out = tmp_path / "export.pbprof"
    svc.export_to_file(out, payload=payload, password="Round!Trip12345")

    assert out.is_file()
    assert out.stat().st_size > 200

    imported = svc.import_from_file(out, password="Round!Trip12345")
    assert imported == payload


def test_import_with_wrong_password_raises(svc, tmp_path):
    out = tmp_path / "e.pbprof"
    svc.export_to_file(out, payload={"k": "v"}, password="CorrectPassword!12")
    with pytest.raises(PbprofPasswordError):
        svc.import_from_file(out, password="WrongPassword!12")


def test_import_tampered_payload_raises(svc, tmp_path):
    out = tmp_path / "e.pbprof"
    svc.export_to_file(out, payload={"k": "v"}, password="GoodPassword!12")

    # Open zip, flip a byte in payload.enc, repack
    import zipfile
    import io
    raw = out.read_bytes()
    buf = io.BytesIO(raw)
    with zipfile.ZipFile(buf, "r") as zin:
        manifest = zin.read("manifest.json")
        encrypted = bytearray(zin.read("payload.enc"))
        sig = zin.read("signature.bin")
    encrypted[0] ^= 0xFF
    new = io.BytesIO()
    with zipfile.ZipFile(new, "w") as zout:
        zout.writestr("manifest.json", manifest)
        zout.writestr("payload.enc", bytes(encrypted))
        zout.writestr("signature.bin", sig)
    out.write_bytes(new.getvalue())

    with pytest.raises(PbprofIntegrityError):
        svc.import_from_file(out, password="GoodPassword!12")


def test_manifest_is_readable_plaintext(svc, tmp_path):
    out = tmp_path / "e.pbprof"
    svc.export_to_file(out, payload={"k": "v"}, password="GoodPassword!12", profile_name="Acc01", profile_id="pid-1")
    import zipfile
    with zipfile.ZipFile(out, "r") as z:
        m = json.loads(z.read("manifest.json"))
    assert m["format"] == "pbprof"
    assert m["format_version"] == 1
    assert m["profile_id"] == "pid-1"
    assert m["profile_name"] == "Acc01"
    assert m["encryption"]["cipher"] == "aes-256-gcm"
    assert m["encryption"]["kdf"] == "argon2id"
```

- [ ] **Step 1.2: Implement**

```python
# backend/services/import_export_service.py
"""Encrypted .pbprof export/import. zip(manifest.json + payload.enc + signature.bin)."""
from __future__ import annotations

import base64
import hmac
import io
import json
import secrets
import time
import zipfile
from hashlib import sha256
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from backend.core.security import KDFParams, derive_key

FORMAT = "pbprof"
FORMAT_VERSION = 1
CREATOR_VERSION = "0.5.0"


class PbprofPasswordError(Exception):
    pass


class PbprofIntegrityError(Exception):
    pass


class PbprofFormatError(Exception):
    pass


class ImportExportService:
    def export_to_file(
        self,
        path: Path,
        *,
        payload: dict[str, Any],
        password: str,
        profile_id: str = "",
        profile_name: str = "",
        include_browser_data: bool = True,
        include_extensions: bool = False,
    ) -> None:
        params = KDFParams.default()
        salt = secrets.token_bytes(16)
        key = derive_key(password, salt, params)

        plaintext = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        nonce = secrets.token_bytes(12)
        ciphertext = AESGCM(key).encrypt(nonce, plaintext, None)
        signature = hmac.new(key, ciphertext, sha256).digest()

        manifest = {
            "format": FORMAT,
            "format_version": FORMAT_VERSION,
            "created_at": int(time.time() * 1000),
            "creator_version": CREATOR_VERSION,
            "profile_id": profile_id,
            "profile_name": profile_name,
            "encryption": {
                "kdf": "argon2id",
                "kdf_salt": base64.b64encode(salt).decode("ascii"),
                "kdf_params": params.to_dict(),
                "cipher": "aes-256-gcm",
                "nonce": base64.b64encode(nonce).decode("ascii"),
            },
            "include_browser_data": include_browser_data,
            "include_extensions": include_extensions,
            "size_bytes_encrypted": len(ciphertext),
        }

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("manifest.json", json.dumps(manifest, indent=2))
            z.writestr("payload.enc", ciphertext)
            z.writestr("signature.bin", signature)
        path.write_bytes(buf.getvalue())

    def import_from_file(self, path: Path, *, password: str) -> dict[str, Any]:
        if not path.is_file():
            raise PbprofFormatError(f"file not found: {path}")
        raw = path.read_bytes()
        try:
            with zipfile.ZipFile(io.BytesIO(raw), "r") as z:
                manifest = json.loads(z.read("manifest.json"))
                ciphertext = z.read("payload.enc")
                signature = z.read("signature.bin")
        except (zipfile.BadZipFile, KeyError, json.JSONDecodeError) as exc:
            raise PbprofFormatError(str(exc)) from exc

        if manifest.get("format") != FORMAT:
            raise PbprofFormatError(f"unknown format: {manifest.get('format')!r}")

        enc = manifest["encryption"]
        salt = base64.b64decode(enc["kdf_salt"])
        nonce = base64.b64decode(enc["nonce"])
        params = KDFParams.from_dict(enc["kdf_params"])
        key = derive_key(password, salt, params)

        candidate_sig = hmac.new(key, ciphertext, sha256).digest()
        if not hmac.compare_digest(candidate_sig, signature):
            # The signature uses the same key as decryption — if it fails it could be
            # tampered ciphertext OR wrong password. We disambiguate by trying decryption:
            try:
                AESGCM(key).decrypt(nonce, ciphertext, None)
                # if decrypt succeeds despite sig mismatch → tampered sig
                raise PbprofIntegrityError("signature mismatch (tampering detected)")
            except Exception as inner:
                raise PbprofIntegrityError(f"signature mismatch: {inner}") from inner

        try:
            plaintext = AESGCM(key).decrypt(nonce, ciphertext, None)
        except Exception as exc:
            # Wrong password (or extremely unlikely sig collision)
            raise PbprofPasswordError("decryption failed — wrong password or corrupt data") from exc

        return json.loads(plaintext.decode("utf-8"))
```

- [ ] **Step 1.3: Run + commit**

```bash
.venv/Scripts/python.exe -m pytest tests/unit/test_import_export.py -v
git add backend/services/import_export_service.py tests/unit/test_import_export.py
git commit -m "feat(io): ImportExportService — .pbprof format (Argon2id+AES-GCM+HMAC)"
```

---

## Task 2: ExtensionService (TDD)

Firefox extensions live in `<profile>/extensions/` as `.xpi` files (zip-based). The `extensions.json` in the profile dir is the canonical registry but it's also written by Firefox itself on launch; we just drop XPIs in `extensions/` and Firefox loads them.

For listing — we walk the directory and parse each `.xpi`'s `manifest.json` (inside the zip) to get id/name/version.

**Files:**
- Create: `backend/services/extension_service.py`
- Create: `tests/unit/test_extension_service.py`

- [ ] **Step 2.1: Write failing tests**

```python
# tests/unit/test_extension_service.py
import io
import json
import zipfile
from pathlib import Path

import pytest

from backend.services.extension_service import ExtensionService, ExtensionNotFound


def _fake_xpi(addon_id: str, name: str, version: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("manifest.json", json.dumps({
            "manifest_version": 2,
            "name": name,
            "version": version,
            "browser_specific_settings": {"gecko": {"id": addon_id}},
        }))
    return buf.getvalue()


def test_list_empty(tmp_path):
    svc = ExtensionService()
    assert svc.list_extensions(tmp_path) == []


def test_install_and_list(tmp_path):
    svc = ExtensionService()
    xpi = _fake_xpi("ublock@example", "uBlock Origin", "1.55.0")
    info = svc.install(tmp_path, xpi_bytes=xpi, filename="ublock.xpi")
    assert info["id"] == "ublock@example"
    assert info["name"] == "uBlock Origin"
    listed = svc.list_extensions(tmp_path)
    assert any(e["id"] == "ublock@example" for e in listed)


def test_remove(tmp_path):
    svc = ExtensionService()
    xpi = _fake_xpi("a@x", "A", "1.0")
    svc.install(tmp_path, xpi_bytes=xpi, filename="a.xpi")
    svc.remove(tmp_path, addon_id="a@x")
    assert svc.list_extensions(tmp_path) == []


def test_remove_missing_raises(tmp_path):
    svc = ExtensionService()
    with pytest.raises(ExtensionNotFound):
        svc.remove(tmp_path, addon_id="never@there")


def test_install_bad_xpi_raises(tmp_path):
    svc = ExtensionService()
    with pytest.raises(ValueError):
        svc.install(tmp_path, xpi_bytes=b"not a zip", filename="x.xpi")
```

- [ ] **Step 2.2: Implement**

```python
# backend/services/extension_service.py
from __future__ import annotations

import io
import json
import re
import shutil
import zipfile
from pathlib import Path
from typing import Any

_ID_SAFE = re.compile(r"^[A-Za-z0-9@._\-+{}]+$")


class ExtensionNotFound(LookupError):
    pass


class ExtensionService:
    def _ext_dir(self, profile_dir: Path) -> Path:
        d = profile_dir / "extensions"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def list_extensions(self, profile_dir: Path) -> list[dict[str, Any]]:
        d = self._ext_dir(profile_dir)
        out: list[dict[str, Any]] = []
        for f in sorted(d.iterdir()):
            if not f.is_file() or not f.suffix == ".xpi":
                continue
            try:
                info = self._read_manifest(f.read_bytes())
            except Exception:
                continue
            info["filename"] = f.name
            out.append(info)
        return out

    def install(self, profile_dir: Path, *, xpi_bytes: bytes, filename: str) -> dict[str, Any]:
        info = self._read_manifest(xpi_bytes)
        addon_id = info["id"]
        if not _ID_SAFE.match(addon_id):
            raise ValueError(f"unsafe addon id: {addon_id!r}")
        d = self._ext_dir(profile_dir)
        target = d / f"{addon_id}.xpi"
        target.write_bytes(xpi_bytes)
        info["filename"] = target.name
        return info

    def remove(self, profile_dir: Path, *, addon_id: str) -> None:
        d = self._ext_dir(profile_dir)
        target = d / f"{addon_id}.xpi"
        if not target.is_file():
            # Maybe stored under a different filename — scan
            for f in d.glob("*.xpi"):
                try:
                    info = self._read_manifest(f.read_bytes())
                except Exception:
                    continue
                if info["id"] == addon_id:
                    f.unlink()
                    return
            raise ExtensionNotFound(addon_id)
        target.unlink()

    def _read_manifest(self, xpi_bytes: bytes) -> dict[str, Any]:
        try:
            with zipfile.ZipFile(io.BytesIO(xpi_bytes), "r") as z:
                mraw = z.read("manifest.json")
        except (zipfile.BadZipFile, KeyError) as exc:
            raise ValueError(f"not a valid .xpi: {exc}") from exc
        m = json.loads(mraw)
        gecko = (m.get("browser_specific_settings") or {}).get("gecko") or {}
        addon_id = gecko.get("id") or m.get("applications", {}).get("gecko", {}).get("id")
        if not addon_id:
            raise ValueError("xpi has no gecko addon id")
        return {
            "id": addon_id,
            "name": m.get("name", addon_id),
            "version": m.get("version", "0.0.0"),
        }
```

- [ ] **Step 2.3: Run + commit**

```bash
.venv/Scripts/python.exe -m pytest tests/unit/test_extension_service.py -v
git add backend/services/extension_service.py tests/unit/test_extension_service.py
git commit -m "feat(extensions): ExtensionService — list/install/remove Firefox addons"
```

---

## Task 3: Add `clone` + `bulk_delete` to ProfileService

In `backend/services/profile_service.py`, add inside the class:

```python
    def clone(self, profile_id: str, *, new_name: str | None = None, include_cookies: bool = True) -> Profile:
        src = self.get(profile_id)
        new_id = str(uuid.uuid4())
        now = _now_ms()
        # Regenerate seeds so cloned profile has unique fingerprint surface
        new_fp = dict(src.fingerprint)
        new_fp["_seeds"] = {
            "canvas": _new_seed(),
            "audio": _new_seed(),
            "webgl_noise": _new_seed(),
        }
        new_fp["_meta"] = dict(new_fp.get("_meta", {}))
        new_fp["_meta"]["generated_at"] = now

        new_udd = self._settings.profiles_dir / new_id
        if include_cookies and Path(src.user_data_dir).is_dir():
            shutil.copytree(src.user_data_dir, new_udd)
        else:
            new_udd.mkdir(parents=True, exist_ok=False)

        clone = Profile(
            id=new_id,
            name=new_name or f"{src.name} (clone)",
            notes=src.notes,
            tags=list(src.tags),
            color=src.color,
            created_at=now,
            updated_at=now,
            status="new",
            fingerprint=new_fp,
            proxy_id=src.proxy_id,
            user_data_dir=str(new_udd),
        )
        with self._sf() as s:
            s.add(clone)
            s.commit()
            s.refresh(clone)
            s.expunge(clone)
        return clone

    def bulk_delete(self, profile_ids: list[str]) -> list[str]:
        deleted: list[str] = []
        for pid in profile_ids:
            try:
                self.delete(pid)
                deleted.append(pid)
            except ProfileNotFound:
                pass
        return deleted
```

And at module level near `_now_ms`:
```python
def _new_seed() -> int:
    import secrets
    return secrets.randbits(64)
```

Also at top of file add `import shutil` (already there) and `from pathlib import Path` (already there).

Tests in existing `tests/integration/test_profile_service.py` — add:

```python
def test_clone_creates_distinct_profile_with_new_seeds(svc):
    src = svc.create(name="src", target_os="windows")
    c = svc.clone(src.id, new_name="src-2")
    assert c.id != src.id
    assert c.name == "src-2"
    assert c.fingerprint["_os"] == "windows"
    assert c.fingerprint["_seeds"] != src.fingerprint["_seeds"]
    assert c.user_data_dir != src.user_data_dir
    from pathlib import Path
    assert Path(c.user_data_dir).is_dir()


def test_bulk_delete(svc):
    ids = [svc.create(name=f"b{i}").id for i in range(5)]
    deleted = svc.bulk_delete(ids + ["missing-id"])
    assert set(deleted) == set(ids)
    assert svc.list_profiles() == []
```

Run + commit:
```bash
.venv/Scripts/python.exe -m pytest tests/integration/test_profile_service.py -v
git add backend/services/profile_service.py tests/integration/test_profile_service.py
git commit -m "feat(profile): clone() with fresh seeds + bulk_delete()"
```

---

## Task 4: Export/Import REST endpoints

**Files:**
- Create: `backend/api/export_import.py`
- Modify: `backend/main.py` (wire router)
- Create: `tests/integration/test_api_export_import.py`

```python
# backend/api/export_import.py
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend.api.deps import require_unlocked
from backend.core.app_state import AppState
from backend.core.config import Settings
from backend.services.import_export_service import (
    ImportExportService,
    PbprofIntegrityError,
    PbprofPasswordError,
    PbprofFormatError,
)
from backend.services.profile_service import ProfileNotFound, ProfileService


class ExportIn(BaseModel):
    password: str = Field(min_length=12)
    include_browser_data: bool = True
    include_extensions: bool = False


def build_export_import_router(
    profile_svc_factory: Callable[[AppState], ProfileService],
    settings: Settings,
) -> APIRouter:
    router = APIRouter(tags=["export-import"])
    ie = ImportExportService()

    def _svc(state: AppState = Depends(require_unlocked)) -> ProfileService:
        return profile_svc_factory(state)

    @router.post("/api/profiles/{pid}/export")
    def export(pid: str, body: ExportIn, svc: ProfileService = Depends(_svc)) -> FileResponse:
        try:
            p = svc.get(pid)
        except ProfileNotFound as exc:
            raise HTTPException(status_code=404, detail="profile not found") from exc

        payload: dict[str, Any] = {
            "profile": {
                "id": p.id, "name": p.name, "notes": p.notes, "tags": p.tags, "color": p.color,
                "fingerprint": p.fingerprint, "status": "new",  # imported profile starts as new
                "created_at": p.created_at, "updated_at": p.updated_at,
            },
            "proxy": None,
            "browser_data": None,
            "extensions": None,
        }

        if body.include_browser_data:
            udd = Path(p.user_data_dir)
            cookies = udd / "cookies.sqlite"
            if cookies.is_file():
                payload["browser_data"] = {
                    "cookies_sqlite_b64": _b64(cookies.read_bytes()),
                }

        out_path = settings.temp_dir / f"{p.id}.pbprof"
        ie.export_to_file(
            out_path,
            payload=payload,
            password=body.password,
            profile_id=p.id,
            profile_name=p.name,
            include_browser_data=body.include_browser_data,
            include_extensions=body.include_extensions,
        )
        return FileResponse(
            str(out_path),
            media_type="application/octet-stream",
            filename=f"{_safe_name(p.name)}.pbprof",
        )

    @router.post("/api/import")
    async def import_endpoint(
        password: str = Form(...),
        file: UploadFile = File(...),
        svc: ProfileService = Depends(_svc),
    ) -> dict[str, Any]:
        if len(password) < 12:
            raise HTTPException(status_code=400, detail="password must be at least 12 characters")
        tmp = settings.temp_dir / f"import-{file.filename}"
        tmp.write_bytes(await file.read())
        try:
            data = ie.import_from_file(tmp, password=password)
        except PbprofPasswordError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except PbprofIntegrityError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except PbprofFormatError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        finally:
            try: tmp.unlink()
            except Exception: pass

        prof = data["profile"]
        new_profile = svc.create(
            name=f"{prof['name']} (imported)",
            notes=prof.get("notes"),
            tags=prof.get("tags") or [],
            color=prof.get("color"),
        )
        # Replace generator-produced fingerprint with the imported one
        with svc._sf() as s:
            from backend.models.profile import Profile as P
            row = s.get(P, new_profile.id)
            row.fingerprint = prof["fingerprint"]
            s.commit()

        if data.get("browser_data") and data["browser_data"].get("cookies_sqlite_b64"):
            import base64
            cookies_bytes = base64.b64decode(data["browser_data"]["cookies_sqlite_b64"])
            (Path(new_profile.user_data_dir) / "cookies.sqlite").write_bytes(cookies_bytes)

        return {"id": new_profile.id, "name": new_profile.name + " (imported)"}

    return router


def _b64(b: bytes) -> str:
    import base64
    return base64.b64encode(b).decode("ascii")


def _safe_name(s: str) -> str:
    import re
    return re.sub(r"[^A-Za-z0-9._\-]", "_", s) or "profile"
```

In `backend/main.py`, add:
```python
from backend.api.export_import import build_export_import_router
# ...
app.include_router(build_export_import_router(profile_svc_factory, settings))
```

Tests:
```python
# tests/integration/test_api_export_import.py
import io

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
    c.post("/api/auth/initialize", json={"password": "Test12345678X"})
    c.post("/api/auth/unlock", json={"password": "Test12345678X"})
    return c


def test_export_import_round_trip(client, tmp_path):
    created = client.post("/api/profiles", json={"name": "OrigAcc", "target_os": "windows"}).json()
    # plant cookies.sqlite so we can verify it round-trips
    from pathlib import Path
    (Path(created["user_data_dir"]) / "cookies.sqlite").write_bytes(b"FAKE-COOKIES-DB")

    r = client.post(f"/api/profiles/{created['id']}/export", json={
        "password": "Export!Pwd12345", "include_browser_data": True,
    })
    assert r.status_code == 200
    pbprof_bytes = r.content
    assert len(pbprof_bytes) > 500

    # Delete original
    client.delete(f"/api/profiles/{created['id']}")
    assert client.get(f"/api/profiles/{created['id']}").status_code == 404

    # Import back
    files = {"file": ("p.pbprof", io.BytesIO(pbprof_bytes), "application/octet-stream")}
    r = client.post("/api/import", data={"password": "Export!Pwd12345"}, files=files)
    assert r.status_code == 200, r.text
    new = r.json()
    assert "imported" in new["name"]

    fresh = client.get(f"/api/profiles/{new['id']}").json()
    assert fresh["fingerprint"]["_os"] == "windows"
    # cookies file restored
    assert (Path(fresh["user_data_dir"]) / "cookies.sqlite").read_bytes() == b"FAKE-COOKIES-DB"


def test_import_wrong_password(client):
    created = client.post("/api/profiles", json={"name": "x"}).json()
    r = client.post(f"/api/profiles/{created['id']}/export", json={"password": "Correct12345X"})
    pbprof = r.content
    import io as _io
    files = {"file": ("p.pbprof", _io.BytesIO(pbprof), "application/octet-stream")}
    r = client.post("/api/import", data={"password": "Wrong12345XYZ"}, files=files)
    assert r.status_code == 401
```

Run + commit:
```bash
.venv/Scripts/python.exe -m pytest tests/integration/test_api_export_import.py -v
git add backend/api/export_import.py backend/main.py tests/integration/test_api_export_import.py
git commit -m "feat(api): /api/profiles/{id}/export + /api/import with cookies round-trip"
```

---

## Task 5: Clone + bulk endpoints + Extensions API

In `backend/api/profiles.py`, add:

```python
class CloneIn(BaseModel):
    new_name: str | None = None
    include_cookies: bool = True


class BulkIdsIn(BaseModel):
    ids: list[str]


@router.post("/api/profiles/{pid}/clone", status_code=status.HTTP_201_CREATED)
def clone(pid: str, body: CloneIn, svc: ProfileService = Depends(_svc)) -> dict[str, Any]:
    try:
        return _profile_to_dict(
            svc.clone(pid, new_name=body.new_name, include_cookies=body.include_cookies)
        )
    except ProfileNotFound as exc:
        raise HTTPException(status_code=404, detail="profile not found") from exc


@router.post("/api/profiles/bulk/delete")
def bulk_delete(body: BulkIdsIn, svc: ProfileService = Depends(_svc)) -> dict[str, Any]:
    return {"deleted": svc.bulk_delete(body.ids)}
```

Create `backend/api/extensions.py`:
```python
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from backend.api.deps import require_unlocked
from backend.core.app_state import AppState
from backend.services.extension_service import ExtensionNotFound, ExtensionService
from backend.services.profile_service import ProfileNotFound, ProfileService


def build_extensions_router(profile_svc_factory: Callable[[AppState], ProfileService]) -> APIRouter:
    router = APIRouter(tags=["extensions"])
    ext = ExtensionService()

    def _svc(state: AppState = Depends(require_unlocked)) -> ProfileService:
        return profile_svc_factory(state)

    @router.get("/api/profiles/{pid}/extensions")
    def list_ext(pid: str, svc: ProfileService = Depends(_svc)):
        try:
            p = svc.get(pid)
        except ProfileNotFound:
            raise HTTPException(status_code=404, detail="profile not found")
        return ext.list_extensions(Path(p.user_data_dir))

    @router.post("/api/profiles/{pid}/extensions")
    async def install(pid: str, file: UploadFile = File(...), svc: ProfileService = Depends(_svc)):
        try:
            p = svc.get(pid)
        except ProfileNotFound:
            raise HTTPException(status_code=404, detail="profile not found")
        data = await file.read()
        try:
            return ext.install(Path(p.user_data_dir), xpi_bytes=data, filename=file.filename or "x.xpi")
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    @router.delete("/api/profiles/{pid}/extensions/{addon_id:path}", status_code=204)
    def delete_ext(pid: str, addon_id: str, svc: ProfileService = Depends(_svc)):
        try:
            p = svc.get(pid)
        except ProfileNotFound:
            raise HTTPException(status_code=404, detail="profile not found")
        try:
            ext.remove(Path(p.user_data_dir), addon_id=addon_id)
        except ExtensionNotFound:
            raise HTTPException(status_code=404, detail="extension not found")

    return router
```

Wire in `backend/main.py`:
```python
from backend.api.extensions import build_extensions_router
# ...
app.include_router(build_extensions_router(profile_svc_factory))
```

Tests:
```python
# tests/integration/test_api_extensions.py
import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient


def _xpi(addon_id: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("manifest.json", json.dumps({
            "manifest_version": 2,
            "name": addon_id,
            "version": "1.0",
            "browser_specific_settings": {"gecko": {"id": addon_id}},
        }))
    return buf.getvalue()


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
    c.post("/api/auth/initialize", json={"password": "Test12345678X"})
    c.post("/api/auth/unlock", json={"password": "Test12345678X"})
    return c


def test_install_list_delete_extension(client):
    p = client.post("/api/profiles", json={"name": "x"}).json()
    files = {"file": ("ublock.xpi", _xpi("ublock@example"), "application/zip")}
    r = client.post(f"/api/profiles/{p['id']}/extensions", files=files)
    assert r.status_code == 200, r.text
    assert r.json()["id"] == "ublock@example"

    r = client.get(f"/api/profiles/{p['id']}/extensions")
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = client.delete(f"/api/profiles/{p['id']}/extensions/ublock@example")
    assert r.status_code == 204

    r = client.get(f"/api/profiles/{p['id']}/extensions")
    assert r.json() == []


def test_extension_isolation_between_profiles(client):
    a = client.post("/api/profiles", json={"name": "A"}).json()
    b = client.post("/api/profiles", json={"name": "B"}).json()
    files = {"file": ("u.xpi", _xpi("only-in-a@x"), "application/zip")}
    client.post(f"/api/profiles/{a['id']}/extensions", files=files)
    assert any(e["id"] == "only-in-a@x" for e in client.get(f"/api/profiles/{a['id']}/extensions").json())
    assert client.get(f"/api/profiles/{b['id']}/extensions").json() == []


def test_clone_profile(client):
    p = client.post("/api/profiles", json={"name": "Orig"}).json()
    r = client.post(f"/api/profiles/{p['id']}/clone", json={"new_name": "Cloned"})
    assert r.status_code == 201
    cloned = r.json()
    assert cloned["name"] == "Cloned"
    assert cloned["id"] != p["id"]
    assert cloned["fingerprint"]["_seeds"] != p["fingerprint"]["_seeds"]


def test_bulk_delete(client):
    ids = [client.post("/api/profiles", json={"name": f"b{i}"}).json()["id"] for i in range(3)]
    r = client.post("/api/profiles/bulk/delete", json={"ids": ids})
    assert r.status_code == 200
    assert set(r.json()["deleted"]) == set(ids)
    assert client.get("/api/profiles").json() == []
```

Run + commit:
```bash
.venv/Scripts/python.exe -m pytest tests/integration/test_api_extensions.py -v
git add backend/api/extensions.py backend/api/profiles.py backend/main.py tests/integration/test_api_extensions.py
git commit -m "feat(api): /api/profiles/{id}/clone, /bulk/delete, /extensions/{,id}"
```

---

## Task 6: Wire in UI (minimal — buttons added to existing components)

- [ ] **Step 6.1: Add Export/Import API client methods to `frontend/lib/api.ts`**

```typescript
exportProfile: async (id: string, password: string, include_browser_data: boolean = true) => {
  const t = loadStoredToken();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (t) headers["X-PB-Token"] = t;
  const r = await fetch(`${BASE}/api/profiles/${id}/export`, {
    method: "POST", headers,
    body: JSON.stringify({ password, include_browser_data }),
  });
  if (!r.ok) {
    let detail = r.statusText;
    try { const j = await r.json(); detail = j.detail ?? detail; } catch {}
    throw new ApiError(r.status, detail);
  }
  return r.blob();
},
importProfile: async (password: string, file: File) => {
  const t = loadStoredToken();
  const headers: Record<string, string> = {};
  if (t) headers["X-PB-Token"] = t;
  const fd = new FormData();
  fd.append("password", password);
  fd.append("file", file);
  const r = await fetch(`${BASE}/api/import`, { method: "POST", headers, body: fd });
  if (!r.ok) {
    let detail = r.statusText;
    try { const j = await r.json(); detail = j.detail ?? detail; } catch {}
    throw new ApiError(r.status, detail);
  }
  return r.json() as Promise<{ id: string; name: string }>;
},
cloneProfile: (id: string, new_name?: string, include_cookies = true) =>
  req<Profile>("POST", `/api/profiles/${id}/clone`, { new_name, include_cookies }),
bulkDeleteProfiles: (ids: string[]) =>
  req<{ deleted: string[] }>("POST", "/api/profiles/bulk/delete", { ids }),
listExtensions: (pid: string) =>
  req<Array<{ id: string; name: string; version: string; filename: string }>>("GET", `/api/profiles/${pid}/extensions`),
installExtension: async (pid: string, file: File) => {
  const t = loadStoredToken();
  const headers: Record<string, string> = {};
  if (t) headers["X-PB-Token"] = t;
  const fd = new FormData(); fd.append("file", file);
  const r = await fetch(`${BASE}/api/profiles/${pid}/extensions`, { method: "POST", headers, body: fd });
  if (!r.ok) throw new ApiError(r.status, (await r.json().catch(() => ({})))?.detail ?? r.statusText);
  return r.json();
},
removeExtension: (pid: string, addon_id: string) =>
  req<void>("DELETE", `/api/profiles/${pid}/extensions/${encodeURIComponent(addon_id)}`),
```

- [ ] **Step 6.2: Add Export, Clone, Import buttons to `ProfileDetail.tsx` + extensions section**

Append actions in the header button row of `ProfileDetail.tsx`:
```tsx
<button
  disabled={busy}
  onClick={async () => {
    const pw = prompt("Export password (min 12 chars):"); if (!pw || pw.length < 12) return;
    try {
      const blob = await api.exportProfile(profile.id, pw, true);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `${profile.name}.pbprof`;
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
    } catch (e: any) { setErr(e?.detail ?? String(e)); }
  }}
  className="rounded border border-bg-border px-3 py-1 text-sm hover:bg-bg-border/40 disabled:opacity-50"
>Export</button>
<button
  disabled={busy}
  onClick={() => action(() => api.cloneProfile(profile.id, `${profile.name} (clone)`, true))}
  className="rounded border border-bg-border px-3 py-1 text-sm hover:bg-bg-border/40 disabled:opacity-50"
>Clone</button>
```

Also add extensions section before the raw fingerprint:
```tsx
<ExtensionsBlock profileId={profile.id} />
```

Where `ExtensionsBlock` is a small component inside the same file:
```tsx
function ExtensionsBlock({ profileId }: { profileId: string }) {
  const [exts, setExts] = useState<any[]>([]);
  const [err, setErr] = useState<string | null>(null);

  async function refresh() {
    try { setExts(await api.listExtensions(profileId)); } catch {}
  }
  useEffect(() => { refresh(); }, [profileId]);

  async function onPick(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0]; if (!f) return;
    setErr(null);
    try { await api.installExtension(profileId, f); refresh(); }
    catch (ex: any) { setErr(ex?.detail ?? String(ex)); }
    e.target.value = "";
  }

  return (
    <div className="mb-6 rounded border border-bg-border bg-bg-elevated p-4">
      <div className="mb-3 flex items-center justify-between">
        <span className="text-xs uppercase text-muted">Extensions ({exts.length})</span>
        <label className="cursor-pointer rounded border border-bg-border px-2 py-0.5 text-xs hover:bg-bg-border/40">
          + Install .xpi
          <input type="file" accept=".xpi" hidden onChange={onPick} />
        </label>
      </div>
      {err && <div className="mb-2 text-xs text-red-400">{err}</div>}
      {exts.length === 0 ? (
        <div className="text-sm text-muted">No extensions installed.</div>
      ) : (
        <ul className="text-sm">
          {exts.map((e) => (
            <li key={e.id} className="flex items-center justify-between border-t border-bg-border/40 py-1.5 first:border-0">
              <span>{e.name} <span className="text-xs text-muted">v{e.version}</span></span>
              <button onClick={async () => { await api.removeExtension(profileId, e.id); refresh(); }}
                      className="text-xs text-red-400 hover:underline">Remove</button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
```

- [ ] **Step 6.3: Add Import button to header**

In `frontend/app/page.tsx` header row, add next to Lock:
```tsx
<label className="cursor-pointer rounded border border-bg-border px-2 py-1 text-xs text-muted hover:text-white">
  Import
  <input type="file" accept=".pbprof" hidden onChange={async (e) => {
    const f = e.target.files?.[0]; if (!f) return;
    const pw = prompt("Import password:"); if (!pw) return;
    try { await api.importProfile(pw, f); refreshProfiles(); }
    catch (ex: any) { alert(ex?.detail ?? String(ex)); }
    e.target.value = "";
  }} />
</label>
```

- [ ] **Step 6.4: Build + commit**

```bash
cd frontend && npm run build && cd ..
git add frontend/
git commit -m "feat(ui): Export/Import/Clone buttons + Extensions block"
```

---

## Task 7: M5 acceptance

```python
# tests/integration/test_m5_acceptance.py
"""M5 acceptance: round-trip + extensions + clone + bulk."""
from __future__ import annotations

import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient


def _xpi(addon_id: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("manifest.json", json.dumps({
            "manifest_version": 2, "name": addon_id, "version": "1.0",
            "browser_specific_settings": {"gecko": {"id": addon_id}},
        }))
    return buf.getvalue()


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
    c.post("/api/auth/initialize", json={"password": "M5Acc12345xy"})
    c.post("/api/auth/unlock", json={"password": "M5Acc12345xy"})
    return c


def test_m5_full_flow(client):
    # Create profile, install extension, plant cookies
    from pathlib import Path
    p = client.post("/api/profiles", json={"name": "Source", "target_os": "windows"}).json()
    (Path(p["user_data_dir"]) / "cookies.sqlite").write_bytes(b"COOKIE-BLOB")
    client.post(f"/api/profiles/{p['id']}/extensions",
                files={"file": ("u.xpi", _xpi("ublock@m5"), "application/zip")})
    assert len(client.get(f"/api/profiles/{p['id']}/extensions").json()) == 1

    # Clone — new id, fresh seeds
    cloned = client.post(f"/api/profiles/{p['id']}/clone", json={"new_name": "Source (c)"}).json()
    assert cloned["id"] != p["id"]
    assert cloned["fingerprint"]["_seeds"] != p["fingerprint"]["_seeds"]

    # Export, delete original, import — cookies survive
    r = client.post(f"/api/profiles/{p['id']}/export", json={"password": "Export!Pwd12345"})
    assert r.status_code == 200
    blob = r.content
    client.delete(f"/api/profiles/{p['id']}")
    files = {"file": ("p.pbprof", io.BytesIO(blob), "application/octet-stream")}
    r = client.post("/api/import", data={"password": "Export!Pwd12345"}, files=files)
    assert r.status_code == 200
    imported = client.get(f"/api/profiles/{r.json()['id']}").json()
    assert imported["fingerprint"]["_os"] == "windows"
    assert (Path(imported["user_data_dir"]) / "cookies.sqlite").read_bytes() == b"COOKIE-BLOB"

    # Bulk delete — both clone and imported go
    r = client.post("/api/profiles/bulk/delete", json={"ids": [cloned["id"], imported["id"]]})
    assert set(r.json()["deleted"]) == {cloned["id"], imported["id"]}
    assert client.get("/api/profiles").json() == []
```

Run + commit + tag:
```bash
.venv/Scripts/python.exe -m pytest tests/integration/test_m5_acceptance.py -v
git add tests/integration/test_m5_acceptance.py
git commit -m "test: M5 acceptance — round-trip + clone + bulk + extensions"
git tag v0.5.0-m5 -m "M5: Export/Import + extensions + clone + bulk"
```

---

## Definition of Done (M5)

- ✅ All tests pass (existing 125 + new ~15)
- ✅ Round-trip export → delete → import preserves cookies and fingerprint
- ✅ Wrong password on import → 401
- ✅ Tampered .pbprof → 422 integrity error
- ✅ Extension installed in profile A is absent in profile B (isolation)
- ✅ Clone makes a profile with new id + new seeds + same OS + same cookies (when included)
- ✅ Bulk delete removes multiple profiles in one call
- ✅ Frontend builds with new UI controls
- ✅ Tag `v0.5.0-m5`

## Next plan
Plan 6 — M6 Distribution (PyInstaller + NSIS + portable ZIP + docs + GitHub Release)
