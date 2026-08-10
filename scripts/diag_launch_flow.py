"""Trace the REAL launcher flow: rect trajectory of the Camoufox window from the
moment the HWND appears until it settles. Two launches with the SAME user_data_dir
to catch xulstore.json restore effects."""
from __future__ import annotations

import ctypes
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


def trace_new_window(before: set[int], seconds: float) -> None:
    t0 = time.monotonic()
    hwnd = None
    last = None
    while time.monotonic() - t0 < seconds:
        if hwnd is None:
            new = [h for h, _ in _list_top_mozilla_windows() if h not in before]
            if new:
                hwnd = new[0]
                print(f"  t={time.monotonic()-t0:5.2f}s HWND appeared {hwnd:#x}")
            else:
                time.sleep(0.1)
                continue
        r = wintypes.RECT()
        u.GetWindowRect(hwnd, ctypes.byref(r))
        cur = (r.left, r.top, r.right, r.bottom, bool(u.IsZoomed(hwnd)), bool(u.IsIconic(hwnd)))
        if cur != last:
            print(
                f"  t={time.monotonic()-t0:5.2f}s rect=({r.left},{r.top})-({r.right},{r.bottom}) "
                f"W={r.right-r.left} H={r.bottom-r.top} zoomed={cur[4]} iconic={cur[5]}"
            )
            last = cur
        time.sleep(0.1)


def main() -> None:
    sw, sh, ww, wh = _primary_screen_metrics()
    print(f"screen full={sw}x{sh} work={ww}x{wh}")

    fp = FingerprintGenerator().generate(GeneratorOptions(target_os="windows", locale="en-US"))
    udd = Path(tempfile.mkdtemp(prefix="flow-"))
    mgr = LaunchManager(CamoufoxLauncher())

    for attempt in (1, 2):
        print(f"--- launch #{attempt} (udd={udd}) ---")
        before = {h for h, _ in _list_top_mozilla_windows()}
        h = mgr.launch(
            profile_id="flow-test", user_data_dir=str(udd), fingerprint=fp, proxy=None
        )
        print(f"  launch() returned pid={h.pid}")
        trace_new_window(before, 6.0)
        mgr.stop("flow-test")
        t0 = time.monotonic()
        while h.is_alive() and time.monotonic() - t0 < 15:
            time.sleep(0.2)
        print(f"  stopped (alive={h.is_alive()})")
        time.sleep(1.0)


if __name__ == "__main__":
    main()
