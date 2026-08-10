"""End-to-end check of the BUNDLED exe: start dist/private-browser/private-browser.exe,
create + launch a profile via the real API, and trace the Camoufox window geometry
(physical pixels) from the first frame. Fails loudly on any off-screen/oversized state.

Usage: .venv/Scripts/python.exe scripts/verify_real_artifact.py
"""
from __future__ import annotations

import ctypes
import json
import re
import subprocess
import sys
import threading
import time
import urllib.request
from ctypes import wintypes
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / "dist" / "private-browser" / "private-browser.exe"
TOKEN_RE = re.compile(r"PB_API_TOKEN=(\S+)")

ctypes.windll.user32.SetProcessDPIAware()
u = ctypes.windll.user32
gdi = ctypes.windll.gdi32


def capture_hwnd_png(hwnd: int, out_path: Path) -> None:
    """PrintWindow + GDI dump of a window into a PNG, regardless of z-order."""
    r = wintypes.RECT()
    u.GetWindowRect(hwnd, ctypes.byref(r))
    w, h = r.right - r.left, r.bottom - r.top
    hwnd_dc = u.GetWindowDC(hwnd)
    mem_dc = gdi.CreateCompatibleDC(hwnd_dc)
    bmp = gdi.CreateCompatibleBitmap(hwnd_dc, w, h)
    gdi.SelectObject(mem_dc, bmp)
    u.PrintWindow(hwnd, mem_dc, 0x00000002)  # PW_RENDERFULLCONTENT

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
    buf = (ctypes.c_ubyte * (w * h * 4))()
    gdi.GetDIBits(mem_dc, bmp, 0, h, buf, ctypes.byref(bi), 0)

    from PIL import Image

    Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).save(out_path)
    gdi.DeleteObject(bmp)
    gdi.DeleteDC(mem_dc)
    u.ReleaseDC(hwnd, hwnd_dc)


def moz_hwnds() -> list[int]:
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


def api(port: int, token: str, method: str, path: str, body: dict | None = None) -> dict | list:
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers={"X-PB-Token": token, "Content-Type": "application/json"},
        method=method,
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read() or b"{}")


def main() -> None:
    if not EXE.exists():
        sys.exit(f"exe not found: {EXE}")

    sw, sh = u.GetSystemMetrics(0), u.GetSystemMetrics(1)
    print(f"[verify] physical screen {sw}x{sh}")

    log_path = ROOT / "verify-exe.log"
    log_f = open(log_path, "w", encoding="utf-8", errors="replace")
    proc = subprocess.Popen(
        [str(EXE)],
        cwd=str(EXE.parent),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
        bufsize=1,
    )
    token: str | None = None
    port = 8769

    def pump() -> None:
        nonlocal token
        assert proc.stdout is not None
        for line in proc.stdout:
            log_f.write(line)
            log_f.flush()
            m = TOKEN_RE.search(line)
            if m:
                token = m.group(1)
    threading.Thread(target=pump, daemon=True).start()

    try:
        deadline = time.monotonic() + 90
        while token is None and time.monotonic() < deadline:
            if proc.poll() is not None:
                sys.exit(f"exe died at startup, see {log_path}")
            time.sleep(0.3)
        if token is None:
            sys.exit("no PB_API_TOKEN in exe output within 90s")
        print(f"[verify] backend token={token[:8]}… port={port}")

        # Shell (pywebview) window: must be on-screen and maximized
        time.sleep(3)  # give pywebview a moment to create + maximize
        shell = u.FindWindowW(None, "Genesis Browser")
        if shell:
            r = wintypes.RECT()
            u.GetWindowRect(shell, ctypes.byref(r))
            zoomed = bool(u.IsZoomed(shell))
            print(
                f"[shell] rect=({r.left},{r.top})-({r.right},{r.bottom})"
                f" W={r.right - r.left} H={r.bottom - r.top} zoomed={zoomed}"
            )
            assert zoomed, "shell window is not maximized"
            assert r.left < sw and r.right > 0 and r.top < sh and r.bottom > 0, (
                "shell window is off-screen"
            )
        else:
            print("[shell] WARNING: 'Genesis Browser' window not found")

        prof = api(port, token, "POST", "/api/profiles", {"name": "window-verify"})
        pid = prof["id"]
        print(f"[verify] profile created {pid}")

        before = set(moz_hwnds())
        t_launch = time.monotonic()

        # Trace geometry in a background thread so we see the window's very
        # first frames WHILE the launch API call is still blocking (Camoufox
        # startup + maximize + goto happen inside it).
        state: dict = {"hwnd": None, "last": None, "t_first": None, "t_zoomed": None}
        bad_frames: list[str] = []
        stop_trace = threading.Event()

        def trace() -> None:
            while not stop_trace.is_set() and time.monotonic() - t_launch < 60:
                hwnd = state["hwnd"]
                if hwnd is None:
                    new = [h for h in moz_hwnds() if h not in before]
                    if new:
                        state["hwnd"] = hwnd = new[0]
                        state["t_first"] = time.monotonic() - t_launch
                        print(f"[trace] t={state['t_first']:.2f}s HWND {hwnd:#x} appeared")
                    else:
                        time.sleep(0.03)
                        continue
                r = wintypes.RECT()
                if not u.GetWindowRect(hwnd, ctypes.byref(r)):
                    time.sleep(0.03)
                    continue
                zoomed = bool(u.IsZoomed(hwnd))
                cur = (r.left, r.top, r.right, r.bottom, zoomed)
                if cur != state["last"]:
                    t = time.monotonic() - t_launch
                    w, h = r.right - r.left, r.bottom - r.top
                    print(
                        f"[trace] t={t:.2f}s rect=({r.left},{r.top})-({r.right},{r.bottom})"
                        f" W={w} H={h} zoomed={zoomed}"
                    )
                    if zoomed and state["t_zoomed"] is None:
                        state["t_zoomed"] = t
                    # off-screen / oversized detection (allow borders margin)
                    if w > sw + 40 or h > sh + 40:
                        bad_frames.append(f"OVERSIZED {w}x{h} at t={t:.2f}s")
                    if r.left >= sw or r.top >= sh or r.right <= 0 or r.bottom <= 0:
                        bad_frames.append(f"FULLY OFF-SCREEN at t={t:.2f}s")
                    # Non-maximized frames must sit at the work-area origin;
                    # a restored stale position (e.g. screenX=-664) is the
                    # "всё съезжает" the user reported on 2026-08-10.
                    if not zoomed and (r.left < -30 or r.top < -30):
                        bad_frames.append(
                            f"MISPLACED non-zoomed ({r.left},{r.top}) at t={t:.2f}s"
                        )
                    state["last"] = cur
                time.sleep(0.03)

        tr = threading.Thread(target=trace, daemon=True)
        tr.start()
        api(port, token, "POST", f"/api/profiles/{pid}/launch", {})
        print(f"[verify] launch API returned after {time.monotonic()-t_launch:.1f}s")
        time.sleep(5)  # observe post-launch settling
        stop_trace.set()
        tr.join(timeout=2)

        assert state["hwnd"] is not None, "Camoufox window never appeared"
        assert state["last"] is not None and state["last"][4], (
            f"final state not maximized: {state['last']}"
        )
        assert not bad_frames, f"bad geometry frames: {bad_frames}"
        assert state["t_zoomed"] is not None, "window never maximized"
        zoom_lag = state["t_zoomed"] - state["t_first"]
        assert zoom_lag <= 1.5, (
            f"maximize lagged {zoom_lag:.2f}s behind the first frame — the "
            "watcher must maximize immediately, not after Playwright connects"
        )
        print(
            f"[verify] OK: window appeared t={state['t_first']:.2f}s,"
            f" maximized t={state['t_zoomed']:.2f}s (lag {zoom_lag:.2f}s)"
        )

        # Screenshot the Camoufox HWND itself (PrintWindow → correct even when
        # another window covers it), plus the whole desktop for context.
        shot = ROOT / "verify-camoufox.png"
        capture_hwnd_png(state["hwnd"], shot)
        print(f"[verify] camoufox window screenshot {shot}")
        from PIL import ImageGrab

        ImageGrab.grab().save(ROOT / "verify-desktop.png")

        api(port, token, "POST", f"/api/profiles/{pid}/stop", {})
        time.sleep(2)
        api(port, token, "POST", "/api/profiles/bulk/delete", {"ids": [pid]})
        print("[verify] profile stopped + deleted")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        log_f.close()
        subprocess.run(
            ["taskkill", "/IM", "private-browser.exe", "/F"],
            capture_output=True,
        )
    print("[verify] done")


if __name__ == "__main__":
    main()
