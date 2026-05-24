"""FastAPI dependency providers."""
from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.core.app_state import AppState


def get_app_state(request: Request) -> AppState:
    state: AppState | None = getattr(request.app.state, "app_state", None)
    if state is None:
        raise RuntimeError("AppState not attached to app.state")
    return state


def require_unlocked(state: AppState = Depends(get_app_state)) -> AppState:
    if not state.is_unlocked():
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="application is locked — POST /api/auth/unlock first",
        )
    return state


def get_db_session(state: AppState = Depends(require_unlocked)) -> Iterator[Session]:
    with state.session_factory() as session:
        yield session
