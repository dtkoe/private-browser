"""CamoufoxLauncher.launch config-building: window.* hygiene, screen re-spoof,
and maximize-before-goto ordering — with a fake Camoufox (no real browser)."""
from __future__ import annotations

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
        "_maximize_camoufox_window",
        lambda *a, **k: log.append("maximize") or True,
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


def test_maximize_happens_before_homepage_goto(launch_capture):
    _, log = launch_capture({"_geo": {"locale": "de-DE"}})
    assert "maximize" in log, "maximize must run"
    goto_events = [e for e in log if e.startswith("goto:")]
    assert goto_events, "homepage navigation must run"
    assert log.index("maximize") < log.index(goto_events[0])
    assert "hl=de" in goto_events[0] and "gl=de" in goto_events[0]
