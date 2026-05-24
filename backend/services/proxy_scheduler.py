from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler


class BackgroundProxyScheduler:
    """Run `check_callback` immediately on start, then every `interval_seconds`."""

    def __init__(self, *, check_callback: Callable[[], None], interval_seconds: float = 1800.0):
        self._cb = check_callback
        self._interval = interval_seconds
        self._sched: BackgroundScheduler | None = None

    def start(self) -> None:
        if self._sched is not None:
            return
        self._sched = BackgroundScheduler(daemon=True)
        self._sched.add_job(
            self._cb,
            "interval",
            seconds=self._interval,
            next_run_time=datetime.now(),
        )
        self._sched.start()

    def stop(self) -> None:
        if self._sched is not None:
            self._sched.shutdown(wait=False)
            self._sched = None
