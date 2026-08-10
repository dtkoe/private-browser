"""Control: launch Camoufox WITHOUT any window.* / screen.* spoofs, just `window=`.
Use PrintWindow on the HWND so we capture the actual browser pixels even if it's
behind another window."""
from __future__ import annotations

import ctypes
import sys
import tempfile
import time
from ctypes import wintypes
from pathlib import Path

from camoufox.sync_api import Camoufox

u = ctypes.windll.user32
gdi = ctypes.windll.gdi32


def list_moz_hwnds() -> list[int]:
    out: list[int] = []
    EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(hwnd, _):
        if u.IsWindowVisible(hwnd) and u.GetParent(hwnd) == 0:
            cls = ctypes.create_unicode_buffer(64)
            u.GetClassNameW(hwnd, cls, 64)
            if cls.value == "MozillaWindowClass":
                out.append(hwnd)
        return True

    u.EnumWindows(EnumWindowsProc(cb), 0)
    return out


def capture_hwnd_png(hwnd: int, out_path: Path) -> None:
    """Use PrintWindow + GDI to dump the window into a PNG, regardless of z-order."""
    r = wintypes.RECT()
    u.GetWindowRect(hwnd, ctypes.byref(r))
    w, h = r.right - r.left, r.bottom - r.top
    hwnd_dc = u.GetWindowDC(hwnd)
    mem_dc = gdi.CreateCompatibleDC(hwnd_dc)
    bmp = gdi.CreateCompatibleBitmap(hwnd_dc, w, h)
    gdi.SelectObject(mem_dc, bmp)
    PW_RENDERFULLCONTENT = 0x00000002
    u.PrintWindow(hwnd, mem_dc, PW_RENDERFULLCONTENT)

    # Pull pixels out via BITMAPINFO + GetDIBits, then save with PIL.
    class BITMAPINFOHEADER(ctypes.Structure):
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

    class BITMAPINFO(ctypes.Structure):
        _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]

    bi = BITMAPINFO()
    bi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bi.bmiHeader.biWidth = w
    bi.bmiHeader.biHeight = -h  # top-down
    bi.bmiHeader.biPlanes = 1
    bi.bmiHeader.biBitCount = 32
    bi.bmiHeader.biCompression = 0  # BI_RGB

    buf = (ctypes.c_ubyte * (w * h * 4))()
    gdi.GetDIBits(mem_dc, bmp, 0, h, buf, ctypes.byref(bi), 0)

    from PIL import Image
    img = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1)
    img.save(out_path)

    gdi.DeleteObject(bmp)
    gdi.DeleteDC(mem_dc)
    u.ReleaseDC(hwnd, hwnd_dc)


def main() -> None:
    out_name = sys.argv[1] if len(sys.argv) > 1 else "camoufox-baseline.png"
    udd = Path(tempfile.mkdtemp(prefix="baseline-"))
    print(f"udd={udd}")

    before = set(list_moz_hwnds())
    with Camoufox(
        headless=False,
        user_data_dir=str(udd),
        persistent_context=True,
        window=(1500, 800),
        i_know_what_im_doing=True,
    ) as browser:
        page = browser.new_page()
        page.goto("https://www.google.com/", timeout=15000)
        time.sleep(2)

        SW_MAXIMIZE = 3
        new = [h for h in list_moz_hwnds() if h not in before]
        if not new:
            print("no new mozilla window")
            return
        hwnd = new[0]
        u.ShowWindow(hwnd, SW_MAXIMIZE)
        time.sleep(0.5)
        r = wintypes.RECT()
        u.GetWindowRect(hwnd, ctypes.byref(r))
        print(
            f"hwnd={hwnd:#x} rect=({r.left},{r.top},{r.right},{r.bottom}) "
            f"W={r.right-r.left} H={r.bottom-r.top} zoomed={bool(u.IsZoomed(hwnd))}"
        )
        capture_hwnd_png(hwnd, Path.cwd() / out_name)
        print(f"saved {out_name}")


if __name__ == "__main__":
    main()
