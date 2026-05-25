"""Real launcher: spawns Camoufox in a background thread using its sync API."""
from __future__ import annotations

import sys
import threading
import time
from typing import Any

from camoufox.sync_api import Camoufox

from backend.services.launch_manager import Launcher, LaunchError, LaunchHandle


# Locale -> (Google `hl` UI language, `gl` country code). Google picks its UI
# language by IP country by default, ignoring browser Accept-Language. Forcing
# both query params guarantees the user gets a Google in their profile's locale
# even when the (real or proxy) IP says otherwise.
GOOGLE_HL_GL: dict[str, tuple[str, str]] = {
    "en-US": ("en", "us"),
    "en-GB": ("en", "uk"),
    "ru-RU": ("ru", "ru"),
    "de-DE": ("de", "de"),
    "fr-FR": ("fr", "fr"),
    "es-ES": ("es", "es"),
    "it-IT": ("it", "it"),
    "pt-BR": ("pt-BR", "br"),
    "ja-JP": ("ja", "jp"),
    "zh-CN": ("zh-CN", "cn"),
    "uk-UA": ("uk", "ua"),
    "pl-PL": ("pl", "pl"),
    "tr-TR": ("tr", "tr"),
}


def _primary_screen_metrics() -> tuple[int, int, int, int]:
    """Return (screen_w, screen_h, work_w, work_h) of the primary monitor in
    LOGICAL pixels (the units Firefox sizes its chrome in).

    - `screen_w/h` = full monitor size (matches navigator/screen.width/height a
      real user would have on this machine — including the taskbar strip).
    - `work_w/h`   = work area, taskbar excluded — the size a maximized window
      occupies, matching window.outerWidth/Height and screen.availWidth/Height.

    We deliberately do NOT call SetProcessDPIAware: Firefox uses logical pixels,
    so on a 1.25x-scaled 1920×1080 display we want 1536×864, not 1920×1080.
    """
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            sw = user32.GetSystemMetrics(0)  # SM_CXSCREEN — full primary
            sh = user32.GetSystemMetrics(1)  # SM_CYSCREEN
            SPI_GETWORKAREA = 0x0030
            rect = wintypes.RECT()
            if user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0):
                ww = max(rect.right - rect.left, 1024)
                wh = max(rect.bottom - rect.top, 700)
            else:
                ww, wh = sw, max(sh - 48, 700)
            return max(sw, 1024), max(sh, 768), ww, wh
        except Exception:
            pass
    return 1366, 768, 1366, 720


def _primary_screen_size() -> tuple[int, int]:
    """Back-compat: just the work area, used as the initial window= hint."""
    _, _, ww, wh = _primary_screen_metrics()
    return ww, wh


def _list_top_mozilla_windows() -> list[tuple[int, int]]:
    """Return a list of (hwnd, pid) for every visible top-level Mozilla window."""
    if sys.platform != "win32":
        return []
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    out: list[tuple[int, int]] = []

    def cb(hwnd: int, _: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        if user32.GetParent(hwnd) != 0:
            return True
        cls = ctypes.create_unicode_buffer(64)
        user32.GetClassNameW(hwnd, cls, 64)
        if cls.value != "MozillaWindowClass":
            return True
        p = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
        out.append((hwnd, p.value))
        return True

    user32.EnumWindows(EnumWindowsProc(cb), 0)
    return out


def _maximize_camoufox_window(
    target_pid: int,
    before_hwnds: set[int],
    work_w: int,
    work_h: int,
    timeout_s: float = 5.0,
) -> bool:
    """Find the Firefox/Camoufox top-level window and force it to fill the screen.

    Reposition+resize+maximize, in that order:
      1. MoveWindow(hwnd, 0, 0, work_w, work_h, TRUE) — overrides the spoofed
         `window.screenX/Y` (which could put the window off-screen on a small
         monitor) by pulling it back to the origin of the primary work area.
      2. ShowWindow(hwnd, SW_MAXIMIZE) — fills the work area regardless of DPI.
      3. SetForegroundWindow + SetActiveWindow — bring it on top of pywebview
         (otherwise the shell may stay in front, making the new browser invisible).

    Selection strategy (in order):
      A. If `target_pid` > 0: match Mozilla windows owned by that exact PID.
      B. Otherwise: pick the MozillaWindowClass HWND that wasn't present BEFORE
         launch (set diff). Robust to Playwright not exposing a PID.
    """
    if sys.platform != "win32":
        return False
    import ctypes

    user32 = ctypes.windll.user32
    SW_MAXIMIZE = 3
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        current = _list_top_mozilla_windows()
        if target_pid > 0:
            matches = [h for h, p in current if p == target_pid]
            if not matches:
                # PID filter empty, fall back to set diff so a slow PID
                # association doesn't make us miss the window entirely.
                matches = [h for h, _ in current if h not in before_hwnds]
        else:
            matches = [h for h, _ in current if h not in before_hwnds]
        if matches:
            for hwnd in matches:
                # Pull the window back on-screen (spoofed window.screenX/Y can
                # be > 0 even on single-monitor setups, sending it half off the
                # right edge).
                user32.MoveWindow(hwnd, 0, 0, work_w, work_h, True)
                user32.ShowWindow(hwnd, SW_MAXIMIZE)
                # Bring on top so the user actually sees it appear.
                try:
                    user32.SetForegroundWindow(hwnd)
                except Exception:
                    pass
            return True
        time.sleep(0.2)
    return False


class CamoufoxHandle(LaunchHandle):
    def __init__(self, thread: threading.Thread, stopper: threading.Event, pid_ref: list[int]):
        self._thread = thread
        self._stop = stopper
        self._pid_ref = pid_ref

    @property
    def pid(self) -> int:
        return self._pid_ref[0] if self._pid_ref else -1

    def is_alive(self) -> bool:
        return self._thread.is_alive()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=15)


class CamoufoxLauncher(Launcher):
    """Spawns Camoufox in a background thread; blocks until stop is requested or window closes."""

    def launch(
        self,
        *,
        profile_id: str,
        user_data_dir: str,
        fingerprint: dict[str, Any],
        proxy: dict[str, Any] | None,
    ) -> LaunchHandle:
        stopper = threading.Event()
        pid_ref: list[int] = []
        ready = threading.Event()
        err_ref: list[BaseException] = []

        cf_config = {k: v for k, v in fingerprint.items() if not k.startswith("_")}

        # KEY INSIGHT (user 2026-05-25): Firefox renders its chrome (URL bar,
        # tab strip, buttons) using the SPOOFED window.outerWidth/Height, not
        # the real OS window size. If those values don't match the actual OS
        # window, the chrome lays out wrong — buttons clip / new-tab button
        # goes off-screen.
        #
        # We resolve this by spoofing `screen.*` and `window.outer*` to the
        # USER's REAL screen, then sizing the OS window to match. Every user
        # gets a plausibly-shaped fingerprint (their real monitor dimensions),
        # the chrome renders inside the visible window, and SW_MAXIMIZE just
        # works because the spoofed values agree with the OS reality.
        screen_w, screen_h, win_w, win_h = _primary_screen_metrics()
        cf_config["screen.width"] = screen_w
        cf_config["screen.height"] = screen_h
        cf_config["screen.availWidth"] = win_w
        cf_config["screen.availHeight"] = win_h
        cf_config["window.outerWidth"] = win_w
        cf_config["window.outerHeight"] = win_h
        cf_config["window.screenX"] = 0
        cf_config["window.screenY"] = 0

        # Locale: prefer profile geo, else en-US so the user sees a familiar UI
        geo = fingerprint.get("_geo") or {}
        locale = geo.get("locale") or "en-US"
        # `intl.accept_languages` controls the HTTP Accept-Language header.
        # Build a graceful fallback list: e.g. "ru-RU,ru,en" so sites that
        # don't support the primary locale still get a usable language.
        lang_only = locale.split("-", 1)[0]
        accept_languages = ",".join(dict.fromkeys([locale, lang_only, "en"]))

        # Build the homepage URL with Google's hl/gl params so the user sees a
        # Google in their profile's locale, regardless of IP country. (Google
        # picks UI language by IP by default, ignoring Accept-Language.)
        hl, gl = GOOGLE_HL_GL.get(locale, ("en", "us"))
        homepage = f"https://www.google.com/?hl={hl}&gl={gl}"

        # Firefox prefs that make the browser behave like a normal user of `locale`,
        # with Google as the search engine and homepage.
        firefox_user_prefs = {
            "browser.search.defaultenginename": "Google",
            "browser.search.defaultenginename.US": "Google",
            "browser.urlbar.placeholderName": "Google",
            "browser.urlbar.placeholderName.private": "Google",
            "browser.startup.homepage": homepage,
            "browser.startup.page": 1,  # open homepage on launch
            "browser.newtabpage.enabled": True,
            "browser.newtabpage.activity-stream.default.sites": homepage,
            "intl.accept_languages": accept_languages,
            "general.useragent.locale": locale,
            # Always show the tab bar even with a single tab (otherwise the
            # window looks "stripped" / weird because Playwright's default
            # hides the tab strip when there's only one tab).
            "browser.tabs.tabMinWidth": 76,
            "browser.tabs.warnOnClose": False,
            # Make the URL bar suggest history / bookmarks like a normal user's FF
            "browser.urlbar.suggest.history": True,
            "browser.urlbar.suggest.bookmark": True,
            "browser.urlbar.suggest.openpage": True,
            # Bookmarks toolbar visible on new tabs only — matches modern FF default
            "browser.toolbars.bookmarks.visibility": "newtab",
        }

        # Snapshot existing Mozilla windows BEFORE launch so we can identify
        # the new one when Playwright doesn't surface a PID.
        before_hwnds: set[int] = {h for h, _ in _list_top_mozilla_windows()}

        def runner() -> None:
            try:
                with Camoufox(
                    config=cf_config,
                    proxy=proxy,
                    block_webrtc=(proxy is None),
                    user_data_dir=user_data_dir,
                    persistent_context=True,
                    headless=False,
                    window=(win_w, win_h),
                    locale=locale,
                    firefox_user_prefs=firefox_user_prefs,
                    # CRITICAL: Playwright defaults to a 1280×720 viewport on
                    # launch_persistent_context, which means content renders
                    # at that size INSIDE our 1920×1032 OS window. Result: a
                    # huge empty margin around the page and page buttons
                    # (Google "Accept all", etc.) below the visible area.
                    # no_viewport=True tells Playwright to match viewport to
                    # the actual OS window so the page fills the screen.
                    no_viewport=True,
                    # We deliberately persist+replay a flat Camoufox config so the
                    # same profile gets the same UA/screen/etc on every launch.
                    # Camoufox warns about this; we acknowledge.
                    i_know_what_im_doing=True,
                ) as browser:
                    fx_pid = _extract_pid(browser)
                    pid_ref.append(fx_pid)
                    # Land on a locale-correct Google: reuse the initial tab if
                    # Camoufox already opened one (persistent context), otherwise
                    # create a new tab. Avoids duplicate Google tabs on relaunch.
                    try:
                        pages = list(getattr(browser, "pages", []) or [])
                        page = pages[0] if pages else browser.new_page()
                        page.goto(homepage, timeout=15000)
                    except Exception:
                        pass
                    # Force-position+maximize the OS-level Firefox window
                    # SYNCHRONOUSLY before declaring "ready" so the user never
                    # sees the brief huge-window flash that the spoofed
                    # `window.outerWidth/Height` would otherwise produce.
                    # Don't fail launch if maximize times out — fall through.
                    try:
                        _maximize_camoufox_window(fx_pid, before_hwnds, win_w, win_h)
                    except Exception:
                        pass
                    ready.set()
                    while not stopper.is_set():
                        if not _browser_alive(browser):
                            break
                        stopper.wait(0.5)
            except BaseException as exc:  # noqa: BLE001
                err_ref.append(exc)
                ready.set()

        t = threading.Thread(target=runner, name=f"camoufox-{profile_id}", daemon=True)
        t.start()
        if not ready.wait(timeout=60):
            stopper.set()
            t.join(timeout=5)
            raise LaunchError("Camoufox failed to start within 60s")
        if err_ref:
            raise LaunchError(f"Camoufox launch failed: {err_ref[0]!r}") from err_ref[0]
        return CamoufoxHandle(t, stopper, pid_ref)


def _extract_pid(browser: Any) -> int:
    try:
        b = getattr(browser, "browser", None) or browser
        impl = getattr(b, "_impl_obj", None)
        process = getattr(impl, "_browser_process", None) if impl is not None else None
        if process is not None and hasattr(process, "pid"):
            return process.pid
    except Exception:
        pass
    return -1


def _browser_alive(browser: Any) -> bool:
    try:
        if hasattr(browser, "is_connected"):
            return browser.is_connected()
        return True
    except Exception:
        return False
