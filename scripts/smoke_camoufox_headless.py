"""Headless smoke check: verify Camoufox loads and reports spoofed navigator values."""
from __future__ import annotations

import sys

from camoufox.sync_api import Camoufox


def main() -> int:
    print("Launching Camoufox in headless mode...")
    try:
        with Camoufox(headless=True, os=("windows",), humanize=False) as browser:
            page = browser.new_page()
            page.goto("about:blank", wait_until="domcontentloaded")
            ua = page.evaluate("navigator.userAgent")
            platform = page.evaluate("navigator.platform")
            print(f"navigator.userAgent  = {ua}")
            print(f"navigator.platform   = {platform}")
            if "Firefox" not in ua:
                print("FAIL: UA does not contain Firefox", file=sys.stderr)
                return 1
            if platform != "Win32":
                print(f"FAIL: platform is not Win32 (got {platform!r})", file=sys.stderr)
                return 1
        print("OK")
        return 0
    except Exception as exc:
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
