"""Diagnostic: launch Camoufox, log every step of the maximize flow so we can
see whether the HWND search finds the window, what its initial geometry is,
and whether MoveWindow+SW_MAXIMIZE actually changes it.
"""
from __future__ import annotations

import ctypes
import sys
import tempfile
import time
from ctypes import wintypes

from backend.services.camoufox_launcher import (
    _list_top_mozilla_windows,
    _primary_screen_size,
)
from backend.services.fingerprint_generator import FingerprintGenerator, GeneratorOptions

user32 = ctypes.windll.user32


def rect(hwnd):
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return (r.left, r.top, r.right, r.bottom, r.right - r.left, r.bottom - r.top)


def main():
    locale = sys.argv[1] if len(sys.argv) > 1 else "ru-RU"
    win_w, win_h = _primary_screen_size()
    print(f"[diag] work area = {win_w}x{win_h}", flush=True)
    print(f"[diag] before launch, Mozilla top-levels: {_list_top_mozilla_windows()}", flush=True)
    before = {h for h, _ in _list_top_mozilla_windows()}

    fp = FingerprintGenerator().generate(GeneratorOptions(target_os="windows", locale=locale))
    print(f"[diag] spoofed screen={fp['screen.width']}x{fp['screen.height']} "
          f"outer={fp['window.outerWidth']}x{fp['window.outerHeight']} "
          f"screenXY=({fp['window.screenX']},{fp['window.screenY']})", flush=True)

    from camoufox.sync_api import Camoufox

    cf = {k: v for k, v in fp.items() if not k.startswith("_")}
    udd = tempfile.mkdtemp()
    with Camoufox(
        config=cf,
        user_data_dir=udd,
        persistent_context=True,
        headless=False,
        window=(win_w, win_h),
        locale=locale,
        firefox_user_prefs={"intl.accept_languages": f"{locale},en"},
        i_know_what_im_doing=True,
    ):
        print("[diag] Camoufox up, polling for new window...", flush=True)
        deadline = time.monotonic() + 10
        hwnd = None
        while time.monotonic() < deadline:
            cur = _list_top_mozilla_windows()
            new = [h for h, _ in cur if h not in before]
            if new:
                hwnd = new[0]
                pid = [p for h, p in cur if h == hwnd][0]
                print(f"[diag] FOUND new HWND={hwnd:#x} PID={pid}", flush=True)
                break
            time.sleep(0.2)
        if not hwnd:
            print(f"[diag] no new MozillaWindowClass HWND in 10s. current={_list_top_mozilla_windows()}", flush=True)
            return
        print(f"[diag] initial rect (L,T,R,B,W,H) = {rect(hwnd)}", flush=True)
        print(f"[diag] IsWindowVisible = {bool(user32.IsWindowVisible(hwnd))}", flush=True)
        print(f"[diag] IsIconic (minimized) = {bool(user32.IsIconic(hwnd))}", flush=True)
        print(f"[diag] IsZoomed (maximized) = {bool(user32.IsZoomed(hwnd))}", flush=True)
        print("[diag] calling MoveWindow(0,0,...)", flush=True)
        ok = user32.MoveWindow(hwnd, 0, 0, win_w, win_h, True)
        print(f"[diag] MoveWindow -> {ok}, rect now = {rect(hwnd)}", flush=True)
        print("[diag] calling ShowWindow(SW_MAXIMIZE)", flush=True)
        ok = user32.ShowWindow(hwnd, 3)
        print(f"[diag] ShowWindow -> {ok}, IsZoomed now = {bool(user32.IsZoomed(hwnd))}, rect = {rect(hwnd)}", flush=True)
        time.sleep(2)
        print(f"[diag] after sleep, rect = {rect(hwnd)}", flush=True)


if __name__ == "__main__":
    main()
