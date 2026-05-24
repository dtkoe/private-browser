from __future__ import annotations

import base64
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend.api.deps import require_unlocked
from backend.core.app_state import AppState
from backend.core.config import Settings
from backend.services.import_export_service import (
    ImportExportService,
    PbprofFormatError,
    PbprofIntegrityError,
    PbprofPasswordError,
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
                "id": p.id,
                "name": p.name,
                "notes": p.notes,
                "tags": p.tags,
                "color": p.color,
                "fingerprint": p.fingerprint,
                "status": "new",
                "created_at": p.created_at,
                "updated_at": p.updated_at,
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
                    "cookies_sqlite_b64": base64.b64encode(cookies.read_bytes()).decode("ascii"),
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
        tmp = settings.temp_dir / f"import-{file.filename or 'pbprof'}"
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
            try:
                tmp.unlink()
            except Exception:
                pass

        prof = data["profile"]
        new_profile = svc.create(
            name=f"{prof['name']} (imported)",
            notes=prof.get("notes"),
            tags=prof.get("tags") or [],
            color=prof.get("color"),
        )
        # Replace generator fingerprint with the imported one
        from backend.models.profile import Profile as P
        with svc._sf() as s:
            row = s.get(P, new_profile.id)
            row.fingerprint = prof["fingerprint"]
            s.commit()

        if data.get("browser_data") and data["browser_data"].get("cookies_sqlite_b64"):
            cookies_bytes = base64.b64decode(data["browser_data"]["cookies_sqlite_b64"])
            (Path(new_profile.user_data_dir) / "cookies.sqlite").write_bytes(cookies_bytes)

        return {"id": new_profile.id, "name": new_profile.name}

    return router


def _safe_name(s: str) -> str:
    import re
    return re.sub(r"[^A-Za-z0-9._\-]", "_", s) or "profile"
