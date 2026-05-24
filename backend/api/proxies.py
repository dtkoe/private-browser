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
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return _proxy_to_dict(p)

    @router.get("/api/proxies")
    def list_all(svc: ProxyService = Depends(_svc)):
        return [_proxy_to_dict(p) for p in svc.list_proxies()]

    @router.get("/api/proxies/{pid}")
    def get_one(pid: str, svc: ProxyService = Depends(_svc)):
        try:
            return _proxy_to_dict(svc.get(pid))
        except ProxyNotFound as exc:
            raise HTTPException(status_code=404, detail="proxy not found") from exc

    @router.patch("/api/proxies/{pid}")
    def patch(pid: str, body: UpdateProxyIn, svc: ProxyService = Depends(_svc)):
        try:
            return _proxy_to_dict(svc.update(pid, **body.model_dump(exclude_none=True)))
        except ProxyNotFound as exc:
            raise HTTPException(status_code=404, detail="proxy not found") from exc

    @router.delete("/api/proxies/{pid}", status_code=status.HTTP_204_NO_CONTENT)
    def delete(pid: str, svc: ProxyService = Depends(_svc)):
        try:
            svc.delete(pid)
        except ProxyNotFound as exc:
            raise HTTPException(status_code=404, detail="proxy not found") from exc

    @router.post("/api/proxies/{pid}/check")
    def check(pid: str, svc: ProxyService = Depends(_svc)):
        try:
            p = svc.get(pid)
        except ProxyNotFound as exc:
            raise HTTPException(status_code=404, detail="proxy not found") from exc
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
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"added": len(added), "ids": [p.id for p in added]}

    return router
