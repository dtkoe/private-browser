from __future__ import annotations

import time
from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import require_unlocked
from backend.core.app_state import AppState
from backend.services.launch_manager import LaunchError, LaunchManager
from backend.services.profile_service import ProfileNotFound, ProfileService


def build_launch_router(
    svc_factory: Callable[[AppState], ProfileService],
    mgr: LaunchManager,
) -> APIRouter:
    router = APIRouter(tags=["launch"])

    def _svc(state: AppState = Depends(require_unlocked)) -> ProfileService:
        return svc_factory(state)

    @router.post("/api/profiles/{pid}/launch")
    def launch(pid: str, svc: ProfileService = Depends(_svc)) -> dict:
        try:
            p = svc.get(pid)
        except ProfileNotFound as exc:
            raise HTTPException(status_code=404, detail="profile not found") from exc
        try:
            handle = mgr.launch(
                profile_id=pid,
                user_data_dir=p.user_data_dir,
                fingerprint=p.fingerprint,
                proxy=None,
            )
        except LaunchError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        svc.update_status(pid, status_value="running", last_opened_at=int(time.time() * 1000))
        return {"status": "running", "pid": handle.pid}

    @router.post("/api/profiles/{pid}/stop")
    def stop(pid: str, svc: ProfileService = Depends(_svc)) -> dict:
        try:
            svc.get(pid)
        except ProfileNotFound as exc:
            raise HTTPException(status_code=404, detail="profile not found") from exc
        mgr.stop(pid)
        svc.update_status(pid, status_value="ready")
        return {"status": "ready"}

    return router
