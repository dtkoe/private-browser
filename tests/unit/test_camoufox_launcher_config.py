"""CamoufoxLauncher.launch: config hygiene (window.* strip, screen re-spoof),
watcher-driven maximize, ready-before-goto, and the hang-kill-retry watchdog —
with a fake Camoufox (no real browser)."""
from __future__ import annotations

import time
from typing import Any

import pytest

import backend.services.camoufox_launcher as cl


class _FakePage:
    def __init__(self, log: list[str]):
        self._log = log

    def goto(self, url: str, timeout: int = 0) -> None:
        self._log.append(f"goto:{url}")


class _FakeBrowser:
    def __init__(self, log: list[str]):
        self.pages = [_FakePage(log)]

    def is_connected(self) -> bool:
        return True


class _FakeCamoufox:
    captured: dict[str, Any] = {}

    def __init__(self, **kwargs: Any):
        _FakeCamoufox.captured = kwargs

    def __enter__(self) -> _FakeBrowser:
        return _FakeBrowser(_FakeCamoufox.captured["__log"])

    def __exit__(self, *exc: Any) -> None:
        return None


@pytest.fixture()
def launch_capture(monkeypatch, tmp_path):
    """Run launcher.launch() against fakes; return (kwargs, event_log)."""
    log: list[str] = []

    class Camo(_FakeCamoufox):
        def __init__(self, **kwargs: Any):
            kwargs["__log"] = log
            super().__init__(**kwargs)

    monkeypatch.setattr(cl, "Camoufox", Camo)
    monkeypatch.setattr(
        cl,
        "_window_watcher",
        lambda *a, **k: log.append("watch"),
    )
    monkeypatch.setattr(cl, "_primary_screen_metrics", lambda: (1536, 864, 1536, 816))

    def run(fingerprint: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        launcher = cl.CamoufoxLauncher()
        handle = launcher.launch(
            profile_id="t1",
            user_data_dir=str(tmp_path),
            fingerprint=fingerprint,
            proxy=None,
        )
        handle.stop()
        kwargs = dict(_FakeCamoufox.captured)
        kwargs.pop("__log", None)
        return kwargs, log

    return run


def test_persisted_window_keys_stripped_and_screenxy_pinned(launch_capture):
    fp = {
        "navigator.userAgent": "UA",
        "window.outerWidth": 1920,
        "window.outerHeight": 1037,
        "window.innerWidth": 1903,
        "window.innerHeight": 927,
        "window.screenX": 214,
        "window.screenY": 143,
        "_geo": {"locale": "en-US"},
    }
    kwargs, _ = launch_capture(fp)
    cfg = kwargs["config"]

    # Stale persisted window geometry must never reach Camoufox…
    assert "window.outerWidth" not in cfg
    assert "window.outerHeight" not in cfg
    assert "window.innerWidth" not in cfg
    assert "window.innerHeight" not in cfg
    # …but the position is pinned to the work-area origin (we maximize there),
    # otherwise Camoufox derives it from a random generated screen and JS shows
    # impossible geometry (screenX + outerWidth > screen.width).
    assert cfg["window.screenX"] == 0
    assert cfg["window.screenY"] == 0
    # Private keys (_geo) never leak into cf_config.
    assert not any(k.startswith("_") for k in cfg)


def test_screen_respoofed_to_real_monitor_and_window_param(launch_capture):
    kwargs, _ = launch_capture({"_geo": {"locale": "ru-RU"}})
    cfg = kwargs["config"]
    assert cfg["screen.width"] == 1536
    assert cfg["screen.height"] == 864
    assert cfg["screen.availWidth"] == 1536
    assert cfg["screen.availHeight"] == 816
    assert kwargs["window"] == (1536, 816)
    assert kwargs["no_viewport"] is True
    # Consistency invariant an antibot would check:
    assert cfg["window.screenX"] + kwargs["window"][0] <= cfg["screen.width"]
    assert cfg["window.screenY"] + kwargs["window"][1] <= cfg["screen.availHeight"]


def test_watcher_started_and_homepage_goto_runs(launch_capture):
    _, log = launch_capture({"_geo": {"locale": "de-DE"}})
    # The maximize watcher must run independently of Playwright readiness.
    assert "watch" in log
    goto_events = [e for e in log if e.startswith("goto:")]
    assert goto_events, "homepage navigation must run"
    assert "hl=de" in goto_events[0] and "gl=de" in goto_events[0]


def test_crash_prompt_prefs_always_set(launch_capture):
    kwargs, _ = launch_capture({"_geo": {"locale": "en-US"}})
    prefs = kwargs["firefox_user_prefs"]
    # Watchdog kills / taskkill must never trigger restore-session or safe-mode
    # prompts on the next launch — they'd invisibly block the juggler handshake.
    assert prefs["browser.sessionstore.resume_from_crash"] is False
    assert prefs["browser.sessionstore.max_resumed_crashes"] == 0
    assert prefs["toolkit.startup.max_resumed_crashes"] == -1


def test_hung_enter_is_killed_and_retried_once(monkeypatch, tmp_path):
    log: list[str] = []
    instances: list[str] = []

    class HangThenOkCamoufox:
        def __init__(self, **kwargs: Any):
            self.n = len(instances)
            instances.append("i")

        def __enter__(self) -> _FakeBrowser:
            if self.n == 0:
                time.sleep(1.5)  # longer than the patched ready timeout
            return _FakeBrowser(log)

        def __exit__(self, *exc: Any) -> None:
            return None

    monkeypatch.setattr(cl, "Camoufox", HangThenOkCamoufox)
    monkeypatch.setattr(cl, "_window_watcher", lambda *a, **k: None)
    monkeypatch.setattr(cl, "_primary_screen_metrics", lambda: (1536, 864, 1536, 816))
    monkeypatch.setattr(cl, "_LAUNCH_READY_TIMEOUT_S", 0.3)
    kills: list[int] = []
    monkeypatch.setattr(cl, "_kill_pid_tree", lambda pid: kills.append(pid))

    launcher = cl.CamoufoxLauncher()
    handle = launcher.launch(
        profile_id="t1",
        user_data_dir=str(tmp_path),
        fingerprint={"_geo": {"locale": "en-US"}},
        proxy=None,
    )
    assert len(instances) == 2, "hung first attempt must be retried exactly once"
    assert kills, "the wedged browser must be killed before retrying"
    handle.stop()


def test_exception_fails_fast_without_retry(monkeypatch, tmp_path):
    instances: list[str] = []

    class BoomCamoufox:
        def __init__(self, **kwargs: Any):
            instances.append("i")

        def __enter__(self) -> _FakeBrowser:
            raise ValueError("bad proxy")

        def __exit__(self, *exc: Any) -> None:
            return None

    monkeypatch.setattr(cl, "Camoufox", BoomCamoufox)
    monkeypatch.setattr(cl, "_window_watcher", lambda *a, **k: None)
    monkeypatch.setattr(cl, "_primary_screen_metrics", lambda: (1536, 864, 1536, 816))

    launcher = cl.CamoufoxLauncher()
    with pytest.raises(cl.LaunchError, match="bad proxy"):
        launcher.launch(
            profile_id="t1",
            user_data_dir=str(tmp_path),
            fingerprint={"_geo": {"locale": "en-US"}},
            proxy=None,
        )
    assert len(instances) == 1, "deterministic failures must not be retried"
