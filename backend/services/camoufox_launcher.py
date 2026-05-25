"""Real launcher: spawns Camoufox in a background thread using its sync API."""
from __future__ import annotations

import threading
from typing import Any

from camoufox.sync_api import Camoufox

from backend.services.launch_manager import Launcher, LaunchError, LaunchHandle


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

        # Firefox prefs that make the browser behave like a normal user of `locale`,
        # with Google as the search engine and homepage.
        firefox_user_prefs = {
            "browser.search.defaultenginename": "Google",
            "browser.search.defaultenginename.US": "Google",
            "browser.urlbar.placeholderName": "Google",
            "browser.urlbar.placeholderName.private": "Google",
            "browser.startup.homepage": "https://www.google.com/",
            "browser.startup.page": 1,  # open homepage on launch
            "browser.newtabpage.enabled": True,
            "browser.newtabpage.activity-stream.default.sites": "https://www.google.com/",
            "intl.accept_languages": accept_languages,
            "general.useragent.locale": locale,
            # Keep window manageable; user can maximise themselves
            "browser.tabs.warnOnClose": False,
        }

        def runner() -> None:
            try:
                with Camoufox(
                    config=cf_config,
                    proxy=proxy,
                    block_webrtc=(proxy is None),
                    user_data_dir=user_data_dir,
                    persistent_context=True,
                    headless=False,
                    window=(1280, 800),
                    locale=locale,
                    firefox_user_prefs=firefox_user_prefs,
                    # We deliberately persist+replay a flat Camoufox config so the
                    # same profile gets the same UA/screen/etc on every launch.
                    # Camoufox warns about this; we acknowledge.
                    i_know_what_im_doing=True,
                ) as browser:
                    pid_ref.append(_extract_pid(browser))
                    # Land on Google: reuse the initial tab if Camoufox already
                    # opened one (persistent context); otherwise create a new tab.
                    # Avoids duplicate Google tabs on relaunch.
                    try:
                        pages = list(getattr(browser, "pages", []) or [])
                        page = pages[0] if pages else browser.new_page()
                        page.goto("https://www.google.com/", timeout=15000)
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
