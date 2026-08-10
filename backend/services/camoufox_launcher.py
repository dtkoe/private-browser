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
# Persisted fingerprint may include OS-window-shaped keys (Camoufox/Browserforge
# generates them at fingerprint-time from a random plausible monitor). They MUST
# be stripped before launch — see comment in CamoufoxLauncher.launch.
_WINDOW_OVERRIDE_KEYS = frozenset(
    {
        "window.outerWidth",
        "window.outerHeight",
        "window.innerWidth",
        "window.innerHeight",
        "window.screenX",
        "window.screenY",
    }
)


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
    CSS/LOGICAL pixels (the units Firefox sizes its chrome in).

    CRITICAL: the answer must NOT depend on whether the calling process is
    DPI-aware. In dev mode this Python process is DPI-unaware → GetSystemMetrics
    already gives us CSS pixels. In the frozen/bundled build pywebview's WebView2
    backend flips the process to per-monitor-v2 DPI awareness → GetSystemMetrics
    would suddenly return PHYSICAL pixels. We'd then pass e.g. window=(1920,1032)
    to Camoufox, Camoufox treats that as CSS pixels, Firefox creates a 1.25×
    larger OS window (≈2400×1290 physical on a 125% display) — chrome and
    extensions get drawn off-screen, "twice the size of the monitor" as the
    user reported on 2026-05-27.

    Fix: pin this thread to DPI-UNAWARE while measuring. SetThreadDpiAwarenessContext
    is per-thread and per-call; the process awareness is left alone.
    """
    if sys.platform != "win32":
        return 1366, 768, 1366, 720
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        # DPI_AWARENESS_CONTEXT_UNAWARE = (HANDLE)-1
        DPI_UNAWARE = ctypes.c_void_p(-1)
        prev_ctx = None
        try:
            user32.SetThreadDpiAwarenessContext.restype = ctypes.c_void_p
            user32.SetThreadDpiAwarenessContext.argtypes = [ctypes.c_void_p]
            prev_ctx = user32.SetThreadDpiAwarenessContext(DPI_UNAWARE)
        except (AttributeError, OSError):
            prev_ctx = None  # pre-Win10-1703; assume already-unaware behavior

        try:
            sw = user32.GetSystemMetrics(0)  # SM_CXSCREEN — full primary
            sh = user32.GetSystemMetrics(1)  # SM_CYSCREEN
            SPI_GETWORKAREA = 0x0030
            rect = wintypes.RECT()
            if user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0):
                ww = max(rect.right - rect.left, 1024)
                wh = max(rect.bottom - rect.top, 700)
            else:
                ww, wh = sw, max(sh - 48, 700)
        finally:
            if prev_ctx is not None:
                try:
                    user32.SetThreadDpiAwarenessContext(prev_ctx)
                except OSError:
                    pass

        return max(sw, 1024), max(sh, 768), ww, wh
    except Exception:
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


def _window_watcher(
    before_hwnds: set[int],
    state: dict,
    stop_evt: threading.Event,
    appear_timeout_s: float = 30.0,
    enforce_s: float = 3.0,
) -> None:
    """Maximize the new Camoufox window the moment it appears — independent of
    Playwright. The OS window exists seconds BEFORE Camoufox.__enter__ returns
    (juggler handshake takes 4-16s on aged profiles, sometimes hangs), so any
    maximize that waits for Playwright leaves the user staring at a non-maximized
    window. This watcher runs from launch t0, maximizes at the first frame, and
    re-asserts for a few seconds in case Firefox re-applies its own sizing.
    Also records the window's OS pid so a hung launch can be killed.
    """
    if sys.platform != "win32":
        return
    import ctypes

    user32 = ctypes.windll.user32
    SW_MAXIMIZE = 3
    hwnd = None
    deadline = time.monotonic() + appear_timeout_s
    while not stop_evt.is_set() and time.monotonic() < deadline:
        new = [(h, p) for h, p in _list_top_mozilla_windows() if h not in before_hwnds]
        if new:
            hwnd, state["pid"] = new[0]
            state["hwnd"] = hwnd
            break
        stop_evt.wait(0.05)
    if hwnd is None:
        return
    user32.ShowWindow(hwnd, SW_MAXIMIZE)
    try:
        user32.SetForegroundWindow(hwnd)
    except Exception:
        pass
    end = time.monotonic() + enforce_s
    while not stop_evt.is_set() and time.monotonic() < end:
        if not user32.IsZoomed(hwnd):
            user32.ShowWindow(hwnd, SW_MAXIMIZE)
        stop_evt.wait(0.2)


def _kill_pid_tree(pid: int) -> None:
    if pid <= 0:
        return
    try:
        if sys.platform == "win32":
            import subprocess

            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                timeout=10,
            )
        else:
            import os
            import signal

            os.kill(pid, signal.SIGKILL)
    except Exception:
        pass


class CamoufoxHandle(LaunchHandle):
    def __init__(
        self,
        thread: threading.Thread,
        stopper: threading.Event,
        pid_ref: list[int],
        os_pid_ref: dict,
    ):
        self._thread = thread
        self._stop = stopper
        self._pid_ref = pid_ref
        self._os_pid_ref = os_pid_ref

    @property
    def pid(self) -> int:
        if self._pid_ref and self._pid_ref[0] > 0:
            return self._pid_ref[0]
        return self._os_pid_ref.get("pid") or -1

    def is_alive(self) -> bool:
        return self._thread.is_alive()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=20)
        if self._thread.is_alive():
            # Runner stuck (e.g. wedged Playwright call) — kill the browser so
            # the user is never left with an unmanageable orphan window.
            _kill_pid_tree(self.pid)
            self._thread.join(timeout=5)


# Per-attempt gate on Camoufox.__enter__ (browser process + juggler handshake).
# Empirically: fresh profiles ~2-5s, aged profiles 6-16s; a flaky juggler race
# can hang the handshake FOREVER while the Firefox window sits open. 30s cleanly
# separates "slow" from "wedged"; a wedged attempt is killed and retried once.
_LAUNCH_READY_TIMEOUT_S = 30.0


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
        # CRITICAL (user 2026-05-27): drop `window.outerWidth/Height/screenX/Y`
        # from the persisted fingerprint before passing it to Camoufox. These
        # are GENERATED at fingerprint-time from a random plausible monitor
        # (e.g. 1920×1037 for a "full HD" persona) and would otherwise leak
        # into cf_config. Camoufox's internal merge then keeps the user-set
        # key over the `window=(w,h)` derived value, so Firefox creates the
        # OS window at whatever the persisted fingerprint said — on a
        # 125 %-scaled display, 1920 CSS becomes 2400 PHYSICAL, blowing past
        # the screen edge. We re-derive the right values from the real
        # monitor below.
        cf_config = {
            k: v
            for k, v in fingerprint.items()
            if not k.startswith("_") and k not in _WINDOW_OVERRIDE_KEYS
        }

        # Re-spoof screen.* to the user's REAL monitor so JS fingerprints stay
        # plausible (a 1.25x-scaled 1920×1080 display reports screen.width=1536).
        # window.outer*, window.screen* and friends are intentionally NOT set —
        # Camoufox derives them from `window=(work_w, work_h)` and Firefox keeps
        # them in sync with the real OS window, so chrome reflows on resize.
        screen_w, screen_h, win_w, win_h = _primary_screen_metrics()
        cf_config["screen.width"] = screen_w
        cf_config["screen.height"] = screen_h
        cf_config["screen.availWidth"] = win_w
        cf_config["screen.availHeight"] = win_h

        # Pin the JS-reported window position to the work-area origin. Without
        # this Camoufox centers the window inside a RANDOM generated screen and
        # JS reports e.g. screenX=72 while outerWidth == screen.width — an
        # impossible geometry (72+1536 > 1536) that antibot scripts can flag.
        # We always place+maximize the real window at the origin, so 0,0 is the
        # one pair that matches reality. (Config keys win over Camoufox's merge;
        # the OS window position itself is NOT affected by these — verified.)
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
            # A hung/killed launch (our watchdog, taskkill, crash) must NEVER
            # make the next start show the "restore session?" / safe-mode
            # prompts — those block the juggler handshake invisibly.
            "browser.sessionstore.resume_from_crash": False,
            "browser.sessionstore.max_resumed_crashes": 0,
            "toolkit.startup.max_resumed_crashes": -1,
        }

        last_error: LaunchError | None = None
        for _attempt in (1, 2):
            outcome = self._launch_once(
                profile_id=profile_id,
                user_data_dir=user_data_dir,
                cf_config=cf_config,
                proxy=proxy,
                win_w=win_w,
                win_h=win_h,
                locale=locale,
                firefox_user_prefs=firefox_user_prefs,
                homepage=homepage,
            )
            if isinstance(outcome, CamoufoxHandle):
                return outcome
            last_error = outcome
            # Retry ONLY the flaky juggler hang; exceptions are deterministic
            # (bad proxy, bad config) and would just fail again.
            if not getattr(outcome, "is_hang", False):
                break
        assert last_error is not None
        raise last_error

    def _launch_once(
        self,
        *,
        profile_id: str,
        user_data_dir: str,
        cf_config: dict[str, Any],
        proxy: dict[str, Any] | None,
        win_w: int,
        win_h: int,
        locale: str,
        firefox_user_prefs: dict[str, Any],
        homepage: str,
    ) -> CamoufoxHandle | LaunchError:
        stopper = threading.Event()
        ready = threading.Event()
        pid_ref: list[int] = []
        err_ref: list[BaseException] = []

        # Snapshot existing Mozilla windows BEFORE launch: the watcher picks the
        # first NEW one (works even when Playwright doesn't surface a PID).
        before_hwnds: set[int] = {h for h, _ in _list_top_mozilla_windows()}
        watch_state: dict = {"hwnd": None, "pid": None}
        watch_stop = threading.Event()
        watcher = threading.Thread(
            target=_window_watcher,
            args=(before_hwnds, watch_state, watch_stop),
            name=f"camoufox-watch-{profile_id}",
            daemon=True,
        )
        watcher.start()

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
                    # Launch is "ready" once the browser is up — the window is
                    # already maximized by the watcher. Homepage navigation runs
                    # AFTER so a slow network never delays the launch API.
                    ready.set()
                    # Land on a locale-correct Google: reuse the initial tab if
                    # Camoufox already opened one (persistent context), otherwise
                    # create a new tab. Avoids duplicate Google tabs on relaunch.
                    try:
                        pages = list(getattr(browser, "pages", []) or [])
                        page = pages[0] if pages else browser.new_page()
                        page.goto(homepage, timeout=10000)
                    except Exception:
                        pass
                    while not stopper.is_set():
                        if not _browser_alive(browser):
                            break
                        stopper.wait(0.5)
            except BaseException as exc:  # noqa: BLE001
                err_ref.append(exc)
                ready.set()

        t = threading.Thread(target=runner, name=f"camoufox-{profile_id}", daemon=True)
        t.start()

        if not ready.wait(timeout=_LAUNCH_READY_TIMEOUT_S):
            # Wedged juggler handshake: the Firefox window may be open but
            # Playwright never connected. Kill the browser (unblocks the stuck
            # thread too) — the caller retries once.
            watch_stop.set()
            stopper.set()
            _kill_pid_tree(watch_state.get("pid") or -1)
            t.join(timeout=10)
            err = LaunchError(
                f"Camoufox did not become ready within {_LAUNCH_READY_TIMEOUT_S:.0f}s"
            )
            err.is_hang = True  # type: ignore[attr-defined]
            return err
        if err_ref:
            watch_stop.set()
            stopper.set()
            t.join(timeout=5)
            return LaunchError(f"Camoufox launch failed: {err_ref[0]!r}")
        return CamoufoxHandle(t, stopper, pid_ref, watch_state)


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
