"""Diag: capture SearchService init logs from the Camoufox browser console.

DEBUG=pw:browser pipes the Firefox process stdout/stderr through playwright's
debug logger; browser.search.log=true makes SearchService chatty.
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ["DEBUG"] = "pw:browser"

from camoufox.sync_api import Camoufox  # noqa: E402


def main() -> None:
    udd = tempfile.mkdtemp(prefix="udd-slog-")
    print("[diag] udd:", udd)
    with Camoufox(
        user_data_dir=udd,
        persistent_context=True,
        headless=False,
        window=(1200, 800),
        firefox_user_prefs={
            "browser.search.log": True,
            "browser.policies.loglevel": "debug",
        },
        i_know_what_im_doing=True,
    ) as browser:
        pages = list(getattr(browser, "pages", []) or [])
        page = pages[0] if pages else browser.new_page()
        # about:preferences#search forces SearchService.init()
        try:
            page.goto("about:preferences#search", timeout=15000)
        except Exception as e:
            print("[diag] goto failed:", e)
        time.sleep(6)
        try:
            print("[diag] page url:", page.url)
        except Exception:
            pass


if __name__ == "__main__":
    main()
