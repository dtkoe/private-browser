"""Visual smoke: launch a Camoufox with given locale, screenshot the desktop after
5s so we can verify the window is full-screen and Google is in the right language."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import time
from pathlib import Path

from backend.services.camoufox_launcher import CamoufoxLauncher
from backend.services.fingerprint_generator import FingerprintGenerator, GeneratorOptions
from backend.services.launch_manager import LaunchManager


def take_desktop_screenshot(out: Path) -> None:
    ps = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "Add-Type -AssemblyName System.Drawing; "
        "$b = [System.Windows.Forms.SystemInformation]::VirtualScreen; "
        "$bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height; "
        "$g = [System.Drawing.Graphics]::FromImage($bmp); "
        "$g.CopyFromScreen($b.X, $b.Y, 0, 0, $bmp.Size); "
        f"$bmp.Save('{out}'); "
        "$g.Dispose(); $bmp.Dispose()"
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True, capture_output=True)


def force_camoufox_topmost() -> None:
    """Bring all MozillaWindowClass windows to the top via SetWindowPos(HWND_TOPMOST)
    so the desktop screenshot captures Camoufox instead of whatever is in the
    foreground. We toggle topmost on then off so the window doesn't get stuck
    above other apps after the screenshot."""
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    HWND_TOPMOST = -1
    HWND_NOTOPMOST = -2
    SWP_NOMOVE = 0x0002
    SWP_NOSIZE = 0x0001
    SWP_SHOWWINDOW = 0x0040
    EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    hwnds: list[int] = []

    def cb(hwnd, _):
        if u.IsWindowVisible(hwnd) and u.GetParent(hwnd) == 0:
            cls = ctypes.create_unicode_buffer(64)
            u.GetClassNameW(hwnd, cls, 64)
            if cls.value == "MozillaWindowClass":
                hwnds.append(hwnd)
        return True

    u.EnumWindows(EnumWindowsProc(cb), 0)
    flags = SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW
    for hw in hwnds:
        u.SetWindowPos(hw, HWND_TOPMOST, 0, 0, 0, 0, flags)
    time.sleep(0.4)
    for hw in hwnds:
        u.SetWindowPos(hw, HWND_NOTOPMOST, 0, 0, 0, 0, flags)


def main() -> None:
    locale = sys.argv[1] if len(sys.argv) > 1 else "en-US"
    out_name = sys.argv[2] if len(sys.argv) > 2 else f"camoufox-{locale}.png"
    out = Path.cwd() / out_name

    fp = FingerprintGenerator().generate(GeneratorOptions(target_os="windows", locale=locale))
    udd = Path(tempfile.mkdtemp(prefix=f"udd-{locale}-"))
    mgr = LaunchManager(CamoufoxLauncher())
    print(f"launching {locale}, udd={udd}")
    h = mgr.launch(profile_id=f"smoke-{locale}", user_data_dir=str(udd), fingerprint=fp, proxy=None)
    print(f"PID={h.pid}, alive={h.is_alive()}")
    time.sleep(6)  # give Google time to load
    force_camoufox_topmost()
    time.sleep(0.5)
    take_desktop_screenshot(out)
    print(f"screenshot -> {out}")
    mgr.stop(f"smoke-{locale}")
    t0 = time.monotonic()
    while h.is_alive() and time.monotonic() - t0 < 15:
        time.sleep(0.2)
    print("stopped, alive=", h.is_alive())


if __name__ == "__main__":
    main()
