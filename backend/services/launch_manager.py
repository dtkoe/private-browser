"""Manages launch lifecycle for Camoufox subprocesses."""
from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from typing import Any


class LaunchError(RuntimeError):
    pass


class LaunchHandle(ABC):
    @property
    @abstractmethod
    def pid(self) -> int: ...

    @abstractmethod
    def is_alive(self) -> bool: ...

    @abstractmethod
    def stop(self) -> None: ...


class Launcher(ABC):
    @abstractmethod
    def launch(
        self,
        *,
        profile_id: str,
        user_data_dir: str,
        fingerprint: dict[str, Any],
        proxy: dict[str, Any] | None,
    ) -> LaunchHandle: ...


class LaunchManager:
    def __init__(self, launcher: Launcher) -> None:
        self._launcher = launcher
        self._lock = threading.RLock()
        self._handles: dict[str, LaunchHandle] = {}

    def launch(
        self,
        *,
        profile_id: str,
        user_data_dir: str,
        fingerprint: dict[str, Any],
        proxy: dict[str, Any] | None = None,
    ) -> LaunchHandle:
        with self._lock:
            existing = self._handles.get(profile_id)
            if existing is not None and existing.is_alive():
                raise LaunchError(f"profile {profile_id} already running")
            handle = self._launcher.launch(
                profile_id=profile_id,
                user_data_dir=user_data_dir,
                fingerprint=fingerprint,
                proxy=proxy,
            )
            self._handles[profile_id] = handle
            return handle

    def stop(self, profile_id: str) -> None:
        with self._lock:
            h = self._handles.pop(profile_id, None)
            if h is not None:
                try:
                    h.stop()
                except Exception:
                    pass

    def is_running(self, profile_id: str) -> bool:
        with self._lock:
            h = self._handles.get(profile_id)
            return h is not None and h.is_alive()

    def get_handle(self, profile_id: str) -> LaunchHandle | None:
        with self._lock:
            return self._handles.get(profile_id)

    def running_profiles(self) -> list[str]:
        with self._lock:
            return [pid for pid, h in self._handles.items() if h.is_alive()]
