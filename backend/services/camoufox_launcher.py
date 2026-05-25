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


def _primary_screen_size() -> tuple[int, int]:
    """Work-area of the primary monitor in LOGICAL pixels (taskbar excluded).

    We deliberately do NOT call SetProcessDPIAware: Firefox/Camoufox sizes its
    window in logical pixels, so on a 1.25x-scaled display we want 1536×864
    (logical), not 1920×1080 (physical) — otherwise the window goes off-screen.
    `SystemParametersInfoW(SPI_GETWORKAREA)` returns the work-area rect
    excluding the taskbar in the process's current DPI awareness mode (default
    DPI-unaware = logical pixels).
    """
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            SPI_GETWORKAREA = 0x0030
            rect = wintypes.RECT()
            if user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0):
                w = rect.right - rect.left
                h = rect.bottom - rect.top
                if w > 0 and h > 0:
                    return max(w, 1024), max(h, 700)
            # Fallback if SPI fails: GetSystemMetrics without DPI-aware → logical
            sw = user32.GetSystemMetrics(0)
            sh = user32.GetSystemMetrics(1)
            return max(sw, 1024), max(sh - 50, 700)
        except Exception:
            pass
    return 1280, 800


def _maximize_window_for_pid(target_pid: int, timeout_s: float = 6.0) -> bool:
    """Find Firefox/Camoufox top-level windows for `target_pid` and SW_MAXIMIZE them.

    The OS-level maximize is the only reliable way to fill the work area
    regardless of DPI scaling, multi-monitor offsets, or the size we initially
    passed to Playwright. Polls for up to `timeout_s` because the Mozilla window
    can take ~1-2s to appear after the process starts.
    """
    if sys.platform != "win32" or target_pid <= 0:
        return False
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    SW_MAXIMIZE = 3
    EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        found: list[int] = []

        def cb(hwnd: int, _: int) -> bool:
            if not user32.IsWindowVisible(hwnd):
                return True
            if user32.GetParent(hwnd) != 0:
                return True  # only top-level windows
            cls = ctypes.create_unicode_buffer(64)
            user32.GetClassNameW(hwnd, cls, 64)
            if cls.value != "MozillaWindowClass":
                return True
            p = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
            if p.value == target_pid:
                found.append(hwnd)
            return True

        user32.EnumWindows(EnumWindowsProc(cb), 0)
        if found:
            for hwnd in found:
                user32.ShowWindow(hwnd, SW_MAXIMIZE)
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

        # Strip our private metadata keys before handing to Camoufox config.
        # `timezone` is already in cf_config (no _ prefix) — it propagates to
        # Intl.DateTimeFormat via Camoufox's C++ patches.
        cf_config = {k: v for k, v in fingerprint.items() if not k.startswith("_")}

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

        # Pick a window size that fills the user's primary monitor minus the
        # Windows taskbar. Playwright doesn't have a real "maximized" flag for
        # Firefox, so we drive maximization by sizing the window to ~full screen.
        win_w, win_h = _primary_screen_size()

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
                    # Force-maximize the OS-level Firefox window. window= alone
                    # doesn't fill the screen reliably across DPI/multi-monitor
                    # setups — ShowWindow(SW_MAXIMIZE) does. Runs in a background
                    # thread so a slow window-appear doesn't block readiness.
                    if fx_pid > 0:
                        threading.Thread(
                            target=_maximize_window_for_pid,
                            args=(fx_pid,),
                            name=f"maximize-{profile_id}",
                            daemon=True,
                        ).start()
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
