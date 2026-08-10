"""Launch Camoufox via our launcher, then poll the HWND rect to see the real OS-level
size vs the screen work area. Helps decide whether the window is correctly sized."""
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

u = ctypes.windll.user32


def rect_of(hwnd: int) -> tuple[int, int, int, int]:
    r = wintypes.RECT()
    u.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


def main() -> None:
    locale = sys.argv[1] if len(sys.argv) > 1 else "en-US"
    sw, sh, ww, wh = _primary_screen_metrics()
    print(f"[metrics] full={sw}x{sh} work={ww}x{wh} dpi_ctx={u.GetThreadDpiAwarenessContext()}")

    before = {h for h, _ in _list_top_mozilla_windows()}
    fp = FingerprintGenerator().generate(GeneratorOptions(target_os="windows", locale=locale))
    udd = Path(tempfile.mkdtemp(prefix="rect-"))
    mgr = LaunchManager(CamoufoxLauncher())
    print(f"launching, udd={udd}")
    h = mgr.launch(profile_id=f"rect-{locale}", user_data_dir=str(udd), fingerprint=fp, proxy=None)
    print(f"launched pid={h.pid}")

    deadline = time.monotonic() + 8
    hwnd = None
    while time.monotonic() < deadline:
        new = [hw for hw, _ in _list_top_mozilla_windows() if hw not in before]
        if new:
            hwnd = new[0]
            break
        time.sleep(0.2)

    if hwnd:
        for label, t in [("t+0", 0), ("t+2", 2), ("t+5", 5)]:
            time.sleep(t if label == "t+0" else (t - 2 if label == "t+5" else 2))
            lf, t_, r, b = rect_of(hwnd)
            print(f"[rect {label}] L={lf} T={t_} R={r} B={b}  W={r-lf} H={b-t_}  zoomed={bool(u.IsZoomed(hwnd))}")
    else:
        print("no new HWND found")

    mgr.stop(f"rect-{locale}")
    t0 = time.monotonic()
    while h.is_alive() and time.monotonic() - t0 < 10:
        time.sleep(0.2)


if __name__ == "__main__":
    main()
