from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.api.deps import require_unlocked
from backend.core.app_state import AppState
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


class ProxyBindIn(BaseModel):
    proxy_id: str | None = None


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


def build_profiles_router(svc_factory: Callable[[AppState], ProfileService]) -> APIRouter:
    """Build a router that resolves ProfileService per-request via the unlocked AppState."""
    router = APIRouter(tags=["profiles"])
    validator = FingerprintValidator()

    def _svc(state: AppState = Depends(require_unlocked)) -> ProfileService:
        return svc_factory(state)

    @router.post("/api/profiles", status_code=status.HTTP_201_CREATED)
    def create(body: CreateProfileIn, svc: ProfileService = Depends(_svc)) -> dict[str, Any]:
        p = svc.create(
            name=body.name,
            notes=body.notes,
            tags=body.tags,
            color=body.color,
            target_os=body.target_os,
        )
        return _profile_to_dict(p)

    @router.get("/api/profiles")
    def list_all(svc: ProfileService = Depends(_svc)) -> list[dict[str, Any]]:
        return [_profile_to_dict(p) for p in svc.list_profiles()]

    @router.get("/api/profiles/{pid}")
    def get_one(pid: str, svc: ProfileService = Depends(_svc)) -> dict[str, Any]:
        try:
            return _profile_to_dict(svc.get(pid))
        except ProfileNotFound as exc:
            raise HTTPException(status_code=404, detail="profile not found") from exc

    @router.patch("/api/profiles/{pid}")
    def patch(pid: str, body: UpdateProfileIn, svc: ProfileService = Depends(_svc)) -> dict[str, Any]:
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
    def regenerate(pid: str, body: RegenerateIn, svc: ProfileService = Depends(_svc)) -> dict[str, Any]:
        try:
            return _profile_to_dict(svc.regenerate_fingerprint(pid, target_os=body.target_os))
        except ProfileNotFound as exc:
            raise HTTPException(status_code=404, detail="profile not found") from exc

    @router.delete("/api/profiles/{pid}", status_code=status.HTTP_204_NO_CONTENT)
    def delete(pid: str, svc: ProfileService = Depends(_svc)) -> None:
        try:
            svc.delete(pid)
        except ProfileNotFound as exc:
            raise HTTPException(status_code=404, detail="profile not found") from exc

    @router.patch("/api/profiles/{pid}/proxy")
    def set_proxy(pid: str, body: ProxyBindIn, svc: ProfileService = Depends(_svc)) -> dict[str, Any]:
        try:
            return _profile_to_dict(svc.set_proxy(pid, body.proxy_id))
        except ProfileNotFound as exc:
            raise HTTPException(status_code=404, detail="profile not found") from exc

    @router.post("/api/fingerprint/validate", dependencies=[Depends(require_unlocked)])
    def validate(body: ValidateIn) -> dict[str, Any]:
        try:
            validator.validate(body.config)
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"valid": True}

    return router
