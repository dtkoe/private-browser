"""Process-wide event bus. Sync producers (REST handlers, LaunchManager)
push events; async consumers (WebSocket handler) await them via their own queue."""
from __future__ import annotations

import asyncio
import threading
from typing import Any


class EventBus:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: list[asyncio.Queue] = []
        self._loop: asyncio.AbstractEventLoop | None = None

    def attach_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Called once from app startup so that .publish() from sync code can dispatch
        into async-side queues."""
        with self._lock:
            self._loop = loop

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=64)
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        with self._lock:
            try:
                self._subscribers.remove(q)
            except ValueError:
                pass

    def publish(self, event: dict[str, Any]) -> None:
        """Thread-safe; can be called from sync code. Dropped if no loop attached."""
        with self._lock:
            loop = self._loop
            subs = list(self._subscribers)
        if loop is None or not subs:
            return
        for q in subs:
            loop.call_soon_threadsafe(_offer_no_wait, q, event)


def _offer_no_wait(q: asyncio.Queue, event: dict[str, Any]) -> None:
    try:
        q.put_nowait(event)
    except asyncio.QueueFull:
        # Drop oldest, push new — keep stream live
        try:
            q.get_nowait()
        except asyncio.QueueEmpty:
            pass
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass


# Singleton instance — wired in main.py
bus = EventBus()
