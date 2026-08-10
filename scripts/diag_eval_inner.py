"""Launch Camoufox via our launcher, then ask JS what it thinks the dimensions are.
Tells us whether the spoofed outerWidth matches the real OS window.
"""
from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

from camoufox.sync_api import Camoufox

from backend.services.camoufox_launcher import _primary_screen_metrics


def main() -> None:
    locale = sys.argv[1] if len(sys.argv) > 1 else "en-US"
    sw, sh, ww, wh = _primary_screen_metrics()
    print(f"[metrics] full={sw}x{sh} work={ww}x{wh}")

    udd = Path(tempfile.mkdtemp(prefix="eval-"))
    with Camoufox(
        headless=False,
        user_data_dir=str(udd),
        persistent_context=True,
        config={
            "screen.width": sw,
            "screen.height": sh,
            "screen.availWidth": ww,
            "screen.availHeight": wh,
            # mirror CamoufoxLauncher: pin JS window position to the origin
            "window.screenX": 0,
            "window.screenY": 0,
        },
        window=(ww, wh),
        locale=locale,
        i_know_what_im_doing=True,
    ) as browser:
        page = browser.new_page()
        page.goto("https://example.com", timeout=15000)
        time.sleep(2)
        # Maximize
        import ctypes
        from ctypes import wintypes
        u = ctypes.windll.user32
        EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        hwnds = []
        def cb(hwnd, _):
            if u.IsWindowVisible(hwnd) and u.GetParent(hwnd) == 0:
                cls = ctypes.create_unicode_buffer(64)
                u.GetClassNameW(hwnd, cls, 64)
                if cls.value == "MozillaWindowClass":
                    hwnds.append(hwnd)
            return True
        u.EnumWindows(EnumWindowsProc(cb), 0)
        for hw in hwnds:
            u.ShowWindow(hw, 3)
        time.sleep(1)
        # JS values
        res = page.evaluate("""() => ({
            outerWidth: window.outerWidth,
            outerHeight: window.outerHeight,
            innerWidth: window.innerWidth,
            innerHeight: window.innerHeight,
            screenX: window.screenX,
            screenY: window.screenY,
            screen_w: screen.width,
            screen_h: screen.height,
            screen_availW: screen.availWidth,
            screen_availH: screen.availHeight,
            dpr: window.devicePixelRatio,
        })""")
        for k, v in res.items():
            print(f"  JS {k} = {v}")
        # OS window size after maximize
        for hw in hwnds:
            r = wintypes.RECT()
            u.GetWindowRect(hw, ctypes.byref(r))
            print(f"  OS hwnd={hw:#x} rect=({r.left},{r.top},{r.right},{r.bottom}) W={r.right-r.left} H={r.bottom-r.top}")
        print("press enter to exit")
        try:
            input()
        except EOFError:
            time.sleep(5)


if __name__ == "__main__":
    main()
