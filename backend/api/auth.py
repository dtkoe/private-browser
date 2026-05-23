from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from backend.services.security_service import (
    AlreadyInitialized,
    InvalidPassword,
    NotInitialized,
    SecurityService,
)


class _PasswordIn(BaseModel):
    password: str = Field(min_length=12, max_length=512)


def build_auth_router(security: SecurityService) -> APIRouter:
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
        engine.dispose()
        return {"ok": True}

    return router
