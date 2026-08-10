"""Diagnostic: same launch path as the UI Start button.
Launches via CamoufoxLauncher (which the API uses) and prints the resulting
OS window rect so we can see whether the launcher's spoof overrides actually
fit on screen."""
from __future__ import annotations

import ctypes
import sys
import tempfile
import time
from ctypes import wintypes
from pathlib import Path

from backend.services.camoufox_launcher import (
    CamoufoxLauncher,
    _list_top_mozilla_windows,
    _primary_screen_metrics,
)
from backend.services.fingerprint_generator import FingerprintGenerator, GeneratorOptions
from backend.services.launch_manager import LaunchManager

user32 = ctypes.windll.user32


def rect_of(hwnd: int) -> tuple[int, int, int, int, int, int]:
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom, r.right - r.left, r.bottom - r.top


def main() -> None:
    locale = sys.argv[1] if len(sys.argv) > 1 else "en-US"

    # Mirror what the UI launches: a user-data-dir that already exists, with a
    # persisted fingerprint. Use a temp dir for the UDD but a fresh fingerprint
    # so we exercise the exact same launch path the API uses.
    fp = FingerprintGenerator().generate(GeneratorOptions(target_os="windows", locale=locale))
    print(
        f"[fp] spoofed screen={fp.get('screen.width')}x{fp.get('screen.height')}"
        f" outer={fp.get('window.outerWidth')}x{fp.get('window.outerHeight')}"
        f" screenXY=({fp.get('window.screenX')},{fp.get('window.screenY')})"
    )
    screen_w, screen_h, ww, wh = _primary_screen_metrics()
    print(f"[metrics] full={screen_w}x{screen_h} work={ww}x{wh}")
    print(f"[dpi-aware] thread_dpi_ctx={user32.GetThreadDpiAwarenessContext()}")
    # The flag bit that distinguishes per-monitor / system / unaware. We just
    # print everything we can to compare against the UI launch.
    SetProcessDPIAware = ctypes.windll.user32.SetProcessDPIAware
    print(f"[dpi-aware] SetProcessDPIAware addr={SetProcessDPIAware!r}")

    before = {h for h, _ in _list_top_mozilla_windows()}
    udd = Path(tempfile.mkdtemp(prefix="diag-launcher-"))
    mgr = LaunchManager(CamoufoxLauncher())
    print(f"[launch] using UDD={udd}")
    h = mgr.launch(profile_id=f"diag-{locale}", user_data_dir=str(udd), fingerprint=fp, proxy=None)
    print(f"[launch] handle pid={h.pid} alive={h.is_alive()}")

    # Find the new HWND
    deadline = time.monotonic() + 5
    hwnd = None
    while time.monotonic() < deadline:
        new = [hw for hw, _ in _list_top_mozilla_windows() if hw not in before]
        if new:
            hwnd = new[0]
            break
        time.sleep(0.2)
    if not hwnd:
        print("[launch] no new MozillaWindowClass HWND found")
    else:
        print(f"[launch] hwnd={hwnd:#x}")
        print(f"[launch] window rect (L,T,R,B,W,H) = {rect_of(hwnd)}")
        print(f"[launch] IsZoomed = {bool(user32.IsZoomed(hwnd))}")

    time.sleep(2)
    if hwnd:
        print(f"[launch] after 2s rect = {rect_of(hwnd)}")
    mgr.stop(f"diag-{locale}")


if __name__ == "__main__":
    main()
