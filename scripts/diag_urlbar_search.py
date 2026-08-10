"""Diag: does typing a query in the Camoufox URL bar search Google?

Launches Camoufox with the SAME config/prefs the prod launcher builds (captured
from CamoufoxLauncher via a wrapper), focuses the window, OS-types a query into
the urlbar (Ctrl+L -> text -> Enter) and reports where the page navigated.

Usage: .venv/Scripts/python.exe scripts/diag_urlbar_search.py [profile_dir]
"""
from __future__ import annotations

import ctypes
import sys
import tempfile
import time
from ctypes import wintypes
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import backend.services.camoufox_launcher as cl  # noqa: E402
from backend.services.fingerprint_generator import (  # noqa: E402
    FingerprintGenerator,
    GeneratorOptions,
)

u = ctypes.windll.user32

# --- OS-level keyboard (SendInput) -------------------------------------------
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
VK_CONTROL, VK_RETURN, VK_MENU, VK_L = 0x11, 0x0D, 0x12, 0x4C

PUL = ctypes.POINTER(ctypes.c_ulong)


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", PUL),
    ]


class INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("pad", ctypes.c_ubyte * 32)]

    _anonymous_ = ("u",)
    _fields_ = [("type", ctypes.c_ulong), ("u", _U)]


def _send(*events: tuple[int, int, int]) -> None:
    arr = (INPUT * len(events))()
    for i, (vk, scan, flags) in enumerate(events):
        arr[i].type = 1  # INPUT_KEYBOARD
        arr[i].ki = KEYBDINPUT(vk, scan, flags, 0, None)
    u.SendInput(len(events), arr, ctypes.sizeof(INPUT))


def press_vk(vk: int) -> None:
    _send((vk, 0, 0), (vk, 0, KEYEVENTF_KEYUP))
    time.sleep(0.05)


def ctrl_l() -> None:
    _send((VK_CONTROL, 0, 0), (VK_L, 0, 0), (VK_L, 0, KEYEVENTF_KEYUP), (VK_CONTROL, 0, KEYEVENTF_KEYUP))
    time.sleep(0.3)


def type_text(text: str) -> None:
    """Type like a real user: virtual-key events (not KEYEVENTF_UNICODE, which
    Firefox routes through IME composition — Enter then commits the composition
    instead of navigating). ASCII lowercase/digits/space only."""
    for ch in text:
        vk = u.VkKeyScanW(ord(ch)) & 0xFF
        _send((vk, 0, 0), (vk, 0, KEYEVENTF_KEYUP))
        time.sleep(0.06)


def focus(hwnd: int) -> None:
    # ALT-tap trick to bypass the foreground lock, then force foreground.
    _send((VK_MENU, 0, 0), (VK_MENU, 0, KEYEVENTF_KEYUP))
    ok = u.SetForegroundWindow(hwnd)
    time.sleep(0.4)
    fg = u.GetForegroundWindow()
    print(f"[diag] SetForegroundWindow ok={ok} foreground_is_camoufox={fg == hwnd} (fg={fg:#x} want={hwnd:#x})")


def capture(hwnd: int, out: str) -> None:
    gdi = ctypes.windll.gdi32
    r = wintypes.RECT()
    u.GetWindowRect(hwnd, ctypes.byref(r))
    w, h = r.right - r.left, r.bottom - r.top
    if w <= 0 or h <= 0:
        return
    hwnd_dc = u.GetWindowDC(hwnd)
    mem_dc = gdi.CreateCompatibleDC(hwnd_dc)
    bmp = gdi.CreateCompatibleBitmap(hwnd_dc, w, h)
    gdi.SelectObject(mem_dc, bmp)
    u.PrintWindow(hwnd, mem_dc, 0x00000002)

    class BMIH(ctypes.Structure):
        _fields_ = [
            ("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
            ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
            ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
            ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
            ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
            ("biClrImportant", wintypes.DWORD),
        ]

    class BMI(ctypes.Structure):
        _fields_ = [("h", BMIH), ("c", wintypes.DWORD * 3)]

    bi = BMI()
    bi.h.biSize = ctypes.sizeof(BMIH)
    bi.h.biWidth, bi.h.biHeight = w, -h
    bi.h.biPlanes, bi.h.biBitCount = 1, 32
    buf = (ctypes.c_ubyte * (w * h * 4))()
    gdi.GetDIBits(mem_dc, bmp, 0, h, buf, ctypes.byref(bi), 0)
    from PIL import Image

    Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).save(out)
    gdi.DeleteObject(bmp)
    gdi.DeleteDC(mem_dc)
    u.ReleaseDC(hwnd, hwnd_dc)
    print(f"[diag] screenshot -> {out}")


def window_title(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(512)
    u.GetWindowTextW(hwnd, buf, 512)
    return buf.value


def moz_hwnds() -> set[int]:
    out: set[int] = set()
    proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(hwnd, _):
        if u.IsWindowVisible(hwnd) and u.GetParent(hwnd) == 0:
            cls = ctypes.create_unicode_buffer(64)
            u.GetClassNameW(hwnd, cls, 64)
            if cls.value == "MozillaWindowClass":
                out.add(hwnd)
        return True

    u.EnumWindows(proc(cb), 0)
    return out


# --- capture the EXACT kwargs the prod launcher passes to Camoufox -----------
class CaptureCamoufox:
    kwargs: dict = {}

    def __init__(self, **kwargs):
        CaptureCamoufox.kwargs = kwargs

    def __enter__(self):
        raise RuntimeError("capture-only")

    def __exit__(self, *a):
        return None


def main() -> None:
    udd = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="udd-search-")
    fp = FingerprintGenerator().generate(GeneratorOptions(target_os="windows", locale="en-US"))

    real_camoufox = cl.Camoufox
    cl.Camoufox = CaptureCamoufox  # type: ignore[misc]
    try:
        try:
            cl.CamoufoxLauncher().launch(
                profile_id="diag", user_data_dir=udd, fingerprint=fp, proxy=None
            )
        except cl.LaunchError:
            pass  # expected: capture-only fake raised
    finally:
        cl.Camoufox = real_camoufox  # type: ignore[misc]

    kw = dict(CaptureCamoufox.kwargs)
    assert kw, "failed to capture launcher kwargs"
    print("[diag] captured prefs:", {k: v for k, v in kw["firefox_user_prefs"].items() if "search" in k or "keyword" in k})

    before = moz_hwnds()
    with real_camoufox(**kw) as browser:
        # wait for window
        hwnd = None
        t0 = time.monotonic()
        while time.monotonic() - t0 < 30:
            new = moz_hwnds() - before
            if new:
                hwnd = new.pop()
                break
            time.sleep(0.1)
        assert hwnd, "no Camoufox window appeared"
        u.ShowWindow(hwnd, 3)  # maximize

        pages = list(getattr(browser, "pages", []) or [])
        page = pages[0] if pages else browser.new_page()
        try:
            page.goto("https://www.google.com/?hl=en&gl=us", timeout=15000)
        except Exception as e:
            print("[diag] homepage goto failed:", e)
        # Let post-load urlbar refreshes finish — they reset the input value
        # and would eat the first typed characters.
        time.sleep(4)

        focus(hwnd)
        ctrl_l()
        time.sleep(0.5)
        query = "gilfoyle diag search 42"
        type_text(query)
        time.sleep(0.5)
        capture(hwnd, "diag-urlbar-typed.png")
        press_vk(VK_RETURN)
        print(f"[diag] typed query: {query!r} (udd={udd})")

        # page.url is BLIND to chrome-initiated navigations in juggler (it kept
        # reporting the homepage while the real window sat on google.com/search)
        # — the OS window title is the source of truth. Google may interpose
        # its "unusual traffic" /sorry/ page; both outcomes carry google+search.
        t0 = time.monotonic()
        last = None
        retried = False
        while time.monotonic() - t0 < 15:
            if not retried and time.monotonic() - t0 > 5:
                retried = True
                press_vk(VK_RETURN)
                print("[diag] second Enter sent (first may have been swallowed)")
            title = window_title(hwnd)
            if title != last:
                print(f"[diag] t={time.monotonic()-t0:4.1f}s title: {title!r}")
                last = title
            tl = title.lower()
            if "google" in tl and ("search" in tl or "q=" in tl) and tl.strip() != "google":
                print("[diag] RESULT: OK — urlbar query searched Google")
                capture(hwnd, "diag-urlbar-after.png")
                return
            time.sleep(0.4)
        capture(hwnd, "diag-urlbar-after.png")
        print("[diag] RESULT: FAIL — no Google search happened; final title:", last)


if __name__ == "__main__":
    main()
