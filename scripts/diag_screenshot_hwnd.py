"""Capture an EXACT HWND from screen — uses BitBlt from the desktop window (which
includes the actual composited pixels of GPU-rendered windows like Firefox)
restricted to the target HWND's screen rect. Then we know exactly what pixels
Firefox is painting, regardless of z-order."""
from __future__ import annotations

import ctypes
import sys
import tempfile
import time
from ctypes import wintypes
from pathlib import Path

from camoufox.sync_api import Camoufox

from backend.services.camoufox_launcher import (
    _list_top_mozilla_windows,
    _primary_screen_metrics,
)

u = ctypes.windll.user32
g = ctypes.windll.gdi32


def grab_screen_rect(lf: int, t: int, r: int, b: int, out: Path) -> None:
    w, h = r - lf, b - t
    src = u.GetDC(0)
    dst = g.CreateCompatibleDC(src)
    bmp = g.CreateCompatibleBitmap(src, w, h)
    g.SelectObject(dst, bmp)
    SRCCOPY = 0x00CC0020
    g.BitBlt(dst, 0, 0, w, h, src, lf, t, SRCCOPY)

    class BMIH(ctypes.Structure):
        _fields_ = [
            ("biSize", wintypes.DWORD),
            ("biWidth", wintypes.LONG),
            ("biHeight", wintypes.LONG),
            ("biPlanes", wintypes.WORD),
            ("biBitCount", wintypes.WORD),
            ("biCompression", wintypes.DWORD),
            ("biSizeImage", wintypes.DWORD),
            ("biXPelsPerMeter", wintypes.LONG),
            ("biYPelsPerMeter", wintypes.LONG),
            ("biClrUsed", wintypes.DWORD),
            ("biClrImportant", wintypes.DWORD),
        ]

    class BMI(ctypes.Structure):
        _fields_ = [("h", BMIH), ("c", wintypes.DWORD * 3)]

    bi = BMI()
    bi.h.biSize = ctypes.sizeof(BMIH)
    bi.h.biWidth = w
    bi.h.biHeight = -h
    bi.h.biPlanes = 1
    bi.h.biBitCount = 32
    bi.h.biCompression = 0
    buf = (ctypes.c_ubyte * (w * h * 4))()
    g.GetDIBits(dst, bmp, 0, h, buf, ctypes.byref(bi), 0)

    from PIL import Image
    img = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1)
    img.save(out)

    g.DeleteObject(bmp)
    g.DeleteDC(dst)
    u.ReleaseDC(0, src)


def main() -> None:
    out_name = sys.argv[1] if len(sys.argv) > 1 else "camoufox-hwnd.png"

    sw, sh, ww, wh = _primary_screen_metrics()
    print(f"[metrics] full={sw}x{sh} work={ww}x{wh}")

    udd = Path(tempfile.mkdtemp(prefix="hwnd-"))
    before = {h for h, _ in _list_top_mozilla_windows()}
    with Camoufox(
        headless=False,
        user_data_dir=str(udd),
        persistent_context=True,
        window=(ww, wh),
        i_know_what_im_doing=True,
    ) as browser:
        page = browser.new_page()
        page.goto("about:blank", timeout=15000)
        time.sleep(2)
        new = [h for h, _ in _list_top_mozilla_windows() if h not in before]
        if not new:
            print("no new hwnd")
            return
        hwnd = new[0]
        u.ShowWindow(hwnd, 3)
        time.sleep(0.5)
        # Bring to top to make sure we capture clean pixels
        u.SetForegroundWindow(hwnd)
        u.BringWindowToTop(hwnd)
        time.sleep(1)
        r = wintypes.RECT()
        u.GetWindowRect(hwnd, ctypes.byref(r))
        print(f"hwnd={hwnd:#x} rect=({r.left},{r.top},{r.right},{r.bottom})")
        grab_screen_rect(max(r.left, 0), max(r.top, 0), min(r.right, sw), min(r.bottom, sh), Path.cwd() / out_name)
        print(f"saved {out_name}")


if __name__ == "__main__":
    main()
