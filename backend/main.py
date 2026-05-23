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
    settings.api_token = token

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
    def healthz() -> dict:
        return {"ok": True}

    app.include_router(build_auth_router(security))
    return app


app = create_app()
