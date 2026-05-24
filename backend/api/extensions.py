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
        except ProfileNotFound as exc:
            raise HTTPException(status_code=404, detail="profile not found") from exc
        return ext.list_extensions(Path(p.user_data_dir))

    @router.post("/api/profiles/{pid}/extensions")
    async def install(pid: str, file: UploadFile = File(...), svc: ProfileService = Depends(_svc)):
        try:
            p = svc.get(pid)
        except ProfileNotFound as exc:
            raise HTTPException(status_code=404, detail="profile not found") from exc
        data = await file.read()
        try:
            return ext.install(Path(p.user_data_dir), xpi_bytes=data, filename=file.filename or "x.xpi")
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.delete("/api/profiles/{pid}/extensions/{addon_id:path}", status_code=204)
    def delete_ext(pid: str, addon_id: str, svc: ProfileService = Depends(_svc)):
        try:
            p = svc.get(pid)
        except ProfileNotFound as exc:
            raise HTTPException(status_code=404, detail="profile not found") from exc
        try:
            ext.remove(Path(p.user_data_dir), addon_id=addon_id)
        except ExtensionNotFound as exc:
            raise HTTPException(status_code=404, detail="extension not found") from exc

    return router
