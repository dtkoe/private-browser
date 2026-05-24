"""Mutable app state — holds the unlocked DB engine and derived session factory."""
from __future__ import annotations

import threading

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker


class NotUnlocked(RuntimeError):
    pass


class AppState:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._engine: Engine | None = None
        self._session_factory: sessionmaker[Session] | None = None

    def is_unlocked(self) -> bool:
        with self._lock:
            return self._engine is not None

    @property
    def engine(self) -> Engine:
        with self._lock:
            if self._engine is None:
                raise NotUnlocked("app is locked — call /api/auth/unlock first")
            return self._engine

    @property
    def session_factory(self) -> sessionmaker[Session]:
        with self._lock:
            if self._session_factory is None:
                raise NotUnlocked("app is locked")
            return self._session_factory

    def set_unlocked(self, engine: Engine) -> None:
        with self._lock:
            self._engine = engine
            self._session_factory = sessionmaker(engine, expire_on_commit=False)

    def lock(self) -> None:
        with self._lock:
            if self._engine is not None:
                self._engine.dispose()
            self._engine = None
            self._session_factory = None
