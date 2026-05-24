"""FastAPI application entry point."""
from __future__ import annotations

import sys
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

import structlog
from fastapi import APIRouter, FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from backend.api.launch import build_launch_router
from backend.api.middleware.auth_token import APITokenMiddleware
from backend.api.profiles import build_profiles_router
from backend.api.proxies import build_proxies_router
from backend.core.app_state import AppState
from backend.core.config import Settings
from backend.core.logging import configure_logging
from backend.core.security import generate_api_token
from backend.services.camoufox_launcher import CamoufoxLauncher
from backend.services.launch_manager import LaunchManager
from backend.services.profile_service import ProfileService
from backend.services.proxy_health_checker import ProxyHealthChecker
from backend.services.proxy_scheduler import BackgroundProxyScheduler
from backend.services.proxy_service import ProxyService
from backend.services.security_service import (
    AlreadyInitialized,
    InvalidPassword,
    NotInitialized,
    SecurityService,
)


class _PasswordIn(BaseModel):
    password: str = Field(min_length=12, max_length=512)


def _build_auth_router(
    security: SecurityService,
    state: AppState,
    post_unlock_hooks: list[Callable[[], None]] | None = None,
) -> APIRouter:
    hooks = post_unlock_hooks or []
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
        state.set_unlocked(engine)
        for h in hooks:
            try:
                h()
            except Exception:
                pass
        return {"ok": True, "unlocked": True}

    @router.post("/lock", status_code=status.HTTP_200_OK)
    def lock() -> dict:
        state.lock()
        return {"ok": True, "unlocked": False}

    return router


def create_app() -> FastAPI:
    settings = Settings()
    settings.ensure_dirs()
    configure_logging(settings.logs_dir)
    log = structlog.get_logger("private-browser.startup")

    token = generate_api_token()
    settings.api_token = token

    state = AppState()
    security = SecurityService(settings)
    launch_mgr = LaunchManager(CamoufoxLauncher())

    def profile_svc_factory(s: AppState) -> ProfileService:
        return ProfileService(session_factory=s.session_factory, settings=settings)

    def proxy_svc_factory(s: AppState) -> ProxyService:
        return ProxyService(session_factory=s.session_factory)

    def make_checker() -> ProxyHealthChecker:
        return ProxyHealthChecker()

    scheduler_ref: dict = {"sched": None}

    def _check_all_proxies() -> None:
        if not state.is_unlocked():
            return
        svc = ProxyService(session_factory=state.session_factory)
        checker = ProxyHealthChecker()
        for px in svc.list_proxies():
            r = checker.check(
                type=px.type, host=px.host, port=px.port,
                username=px.username, password=px.password,
            )
            try:
                svc.record_check(
                    px.id,
                    ok=r.ok,
                    ip=r.ip,
                    country=r.country,
                    city=r.city,
                    timezone=r.timezone,
                    latency_ms=r.latency_ms,
                )
            except Exception:
                pass

    def _start_scheduler_once() -> None:
        if scheduler_ref["sched"] is not None:
            return
        s = BackgroundProxyScheduler(
            check_callback=_check_all_proxies, interval_seconds=1800.0
        )
        s.start()
        scheduler_ref["sched"] = s

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        log.info("app.start", port=settings.api_port, host=settings.api_host)
        print(f"PB_API_TOKEN={token}", flush=True, file=sys.stdout)
        try:
            yield
        finally:
            for pid in list(launch_mgr.running_profiles()):
                launch_mgr.stop(pid)
            if scheduler_ref["sched"] is not None:
                scheduler_ref["sched"].stop()
                scheduler_ref["sched"] = None
            state.lock()
            log.info("app.stop")

    app = FastAPI(title="private-browser", version="0.3.0", lifespan=lifespan)
    app.state.app_state = state
    app.state.settings = settings
    app.add_middleware(
        APITokenMiddleware,
        token=token,
        exempt_paths=("/healthz", "/docs", "/openapi.json", "/redoc"),
    )

    @app.get("/healthz")
    async def healthz() -> dict:
        return {"ok": True, "unlocked": state.is_unlocked()}

    app.include_router(_build_auth_router(security, state, post_unlock_hooks=[_start_scheduler_once]))
    app.include_router(build_profiles_router(profile_svc_factory))
    app.include_router(build_proxies_router(proxy_svc_factory, make_checker))
    app.include_router(build_launch_router(profile_svc_factory, proxy_svc_factory, launch_mgr))
    return app


app = create_app()
