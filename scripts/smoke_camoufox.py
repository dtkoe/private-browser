"""Smoke test: launch Camoufox, open a page, confirm fingerprint spoofing engaged."""
from __future__ import annotations

from camoufox.sync_api import Camoufox


def main() -> None:
    print("Launching Camoufox (this may take a few seconds)...")
    with Camoufox(headless=False, os=("windows",), humanize=False) as browser:
        page = browser.new_page()
        page.goto("https://browserleaks.com/javascript", wait_until="domcontentloaded")
        ua = page.evaluate("navigator.userAgent")
        platform = page.evaluate("navigator.platform")
        languages = page.evaluate("navigator.languages")
        webgl_vendor = page.evaluate(
            "(() => { try { const c=document.createElement('canvas').getContext('webgl'); "
            "const i=c.getExtension('WEBGL_debug_renderer_info'); "
            "return c.getParameter(i.UNMASKED_VENDOR_WEBGL); } catch(e) { return 'n/a'; } })()"
        )
        print(f"navigator.userAgent  = {ua}")
        print(f"navigator.platform   = {platform}")
        print(f"navigator.languages  = {languages}")
        print(f"WebGL vendor         = {webgl_vendor}")
        input("Press ENTER to close browser...")


if __name__ == "__main__":
    main()
