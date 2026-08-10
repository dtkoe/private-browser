"""Back/Forward must work: Camoufox ships browser.sessionhistory.max_entries=0,
so without enable_cache=True + a real history depth the toolbar Back button is
permanently dead (repro: history.length stuck at 1, go_back() noop)."""
from __future__ import annotations

from typing import Any

import backend.services.camoufox_launcher as cl


class _FakePage:
    def goto(self, url: str, timeout: int = 0) -> None:
        return None


class _FakeBrowser:
    pages = [_FakePage()]

    def is_connected(self) -> bool:
        return True


class _FakeCamoufox:
    captured: dict[str, Any] = {}

    def __init__(self, **kwargs: Any):
        _FakeCamoufox.captured = kwargs

    def __enter__(self) -> _FakeBrowser:
        return _FakeBrowser()

    def __exit__(self, *exc: Any) -> None:
        return None


def test_session_history_enabled_for_back_forward(monkeypatch, tmp_path):
    monkeypatch.setattr(cl, "Camoufox", _FakeCamoufox)
    monkeypatch.setattr(cl, "_window_watcher", lambda *a, **k: None)
    monkeypatch.setattr(cl, "_primary_screen_metrics", lambda: (1536, 864, 1536, 816))
    monkeypatch.setattr(cl, "ensure_google_search", lambda: None)

    handle = cl.CamoufoxLauncher().launch(
        profile_id="t1",
        user_data_dir=str(tmp_path),
        fingerprint={"_geo": {"locale": "en-US"}},
        proxy=None,
    )
    handle.stop()
    kwargs = _FakeCamoufox.captured

    # enable_cache merges Camoufox's CACHE_PREFS (memory cache, max_total_viewers)
    # — without it session history stays empty and Back does nothing.
    assert kwargs["enable_cache"] is True
    # Stock-Firefox history depth; user pref wins over CACHE_PREFS' 10.
    assert kwargs["firefox_user_prefs"]["browser.sessionhistory.max_entries"] == 50
