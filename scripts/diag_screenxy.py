"""Prove/disprove: Camoufox fork positions the OS window at config window.screenX/Y.

Run A: config {'window.screenX': 300, 'window.screenY': 200}, window=(1000, 700)
Run B: no explicit screenX/Y (Camoufox derives from a RANDOM generated screen)
Print GetWindowRect for the new MozillaWindowClass HWND in both runs.
"""
from __future__ import annotations

import ctypes
import tempfile
import time
from ctypes import wintypes

from camoufox.sync_api import Camoufox

u = ctypes.windll.user32


def list_moz_hwnds() -> list[int]:
    out: list[int] = []
    proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(hwnd, _):
        if u.IsWindowVisible(hwnd) and u.GetParent(hwnd) == 0:
            cls = ctypes.create_unicode_buffer(64)
            u.GetClassNameW(hwnd, cls, 64)
            if cls.value == "MozillaWindowClass":
                out.append(hwnd)
        return True

    u.EnumWindows(proc(cb), 0)
    return out


def run(label: str, config: dict) -> None:
    before = set(list_moz_hwnds())
    with Camoufox(
        headless=False,
        user_data_dir=tempfile.mkdtemp(prefix=f"sxy-{label}-"),
        persistent_context=True,
        window=(1000, 700),
        config=config,
        i_know_what_im_doing=True,
    ) as _browser:
        hwnd = None
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline and hwnd is None:
            new = [h for h in list_moz_hwnds() if h not in before]
            hwnd = new[0] if new else None
            time.sleep(0.2)
        if hwnd is None:
            print(f"[{label}] no HWND found")
            return
        time.sleep(1.0)
        r = wintypes.RECT()
        u.GetWindowRect(hwnd, ctypes.byref(r))
        print(
            f"[{label}] rect L={r.left} T={r.top} R={r.right} B={r.bottom} "
            f"W={r.right - r.left} H={r.bottom - r.top}"
        )


if __name__ == "__main__":
    run("explicit-300-200", {"window.screenX": 300, "window.screenY": 200})
    run("derived-random", {})
    run("explicit-0-0", {"window.screenX": 0, "window.screenY": 0})
