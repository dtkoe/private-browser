from __future__ import annotations

import time
from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import require_unlocked
from backend.core.app_state import AppState
from backend.services.launch_manager import LaunchError, LaunchManager
from backend.services.profile_service import ProfileNotFound, ProfileService
from backend.services.proxy_service import ProxyNotFound, ProxyService


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
        proxy_id_out = None
        if p.proxy_id:
            try:
                px = xsvc.get(p.proxy_id)
            except ProxyNotFound as exc:
                raise HTTPException(
                    status_code=409, detail=f"bound proxy missing: {p.proxy_id}"
                ) from exc
            proxy_dict = _proxy_to_launch_dict(px)
            proxy_id_out = px.id

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
        return {"status": "running", "pid": handle.pid, "proxy": proxy_id_out}

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
    return {
        "server": f"{p.type}://{p.host}:{p.port}",
        "username": p.username or None,
        "password": p.password or None,
    }
