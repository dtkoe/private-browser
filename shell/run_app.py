"""Desktop shell:

- Dev mode (run from source): spawn uvicorn + http.server as subprocesses, open pywebview
- Frozen mode (PyInstaller bundle): run uvicorn in a thread inside this process, serve
  frontend via StaticFiles mounted on the same FastAPI app, open pywebview.
"""
from __future__ import annotations

import atexit
import os
import re
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import webview

IS_FROZEN = getattr(sys, "frozen", False)
BUNDLE_ROOT = Path(sys._MEIPASS) if IS_FROZEN else None  # type: ignore[attr-defined]
REPO_ROOT = BUNDLE_ROOT if IS_FROZEN else Path(__file__).resolve().parents[1]
FRONTEND_OUT = REPO_ROOT / "frontend" / "out"
TOKEN_RE = re.compile(r"^PB_API_TOKEN=(\S+)\s*$")
DEFAULT_PORT = 8769

# `shell.camoufox_fetch` works from source; in frozen bundle imports resolve via sys.path[0]
if not IS_FROZEN:
    sys.path.insert(0, str(REPO_ROOT))

from shell.camoufox_fetch import fetch_camoufox, is_camoufox_installed  # noqa: E402
from shell.shortcut import ensure_desktop_shortcut  # noqa: E402


def ensure_camoufox(log=print) -> None:
    if os.environ.get("PB_SKIP_CAMOUFOX_CHECK") == "1":
        log("[camoufox] skip check (PB_SKIP_CAMOUFOX_CHECK=1)")
        return
    if is_camoufox_installed():
        log("[camoufox] already present.")
        return
    log("[camoufox] not installed — first-run download (this may take 5-10 min)…")
    fetch_camoufox(log)


_MUTEX_HANDLE: int | None = None


def acquire_single_instance_lock() -> None:
    """Acquire a single-instance lock that doesn't permanently lock us out if the
    previous run crashed without cleaning up. We TRY to hold a named mutex AND we
    keep the handle in a module global so it survives the function return; if a
    prior run is genuinely still alive the OS will report ERROR_ALREADY_EXISTS,
    but in that case we still continue — port-binding (below) is the real check.
    """
    global _MUTEX_HANDLE
    if sys.platform != "win32":
        return
    import ctypes

    handle = ctypes.windll.kernel32.CreateMutexW(None, False, "Global\\private-browser-mutex-v1")
    _MUTEX_HANDLE = handle  # keep the handle alive for the lifetime of the process
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        # Don't sys.exit() here — a prior crashed instance can leak this name and
        # then nothing the user does brings the app back. The port bind below is
        # the authoritative check, and pick_free_port() will jump to a free one
        # if 8769 is genuinely occupied.
        print("[shell] note: another instance may already be running.", file=sys.stderr)


def pick_free_port(preferred: int, max_tries: int = 10) -> int:
    """Return `preferred` if free, otherwise probe the next ports for one we can bind."""
    import socket

    for offset in range(max_tries):
        port = preferred + offset
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(("127.0.0.1", port))
            s.close()
            return port
        except OSError:
            continue
        finally:
            try:
                s.close()
            except Exception:
                pass
    raise RuntimeError(f"no free port near {preferred} (tried {max_tries})")


# ------------------------- DEV MODE (subprocess) ----------------------------


def start_backend_subprocess(port: int) -> tuple[subprocess.Popen, str]:
    env = os.environ.copy()
    env["PB_API_PORT"] = str(port)
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "backend.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]
    proc = subprocess.Popen(
        cmd,
        cwd=str(REPO_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    token_holder: dict[str, str | None] = {"v": None}
    found = threading.Event()

    def pump() -> None:
        assert proc.stdout is not None
        for raw in proc.stdout:
            line = raw.rstrip()
            sys.stdout.write(f"[backend] {line}\n")
            sys.stdout.flush()
            m = TOKEN_RE.match(line)
            if m:
                token_holder["v"] = m.group(1)
                found.set()

    t = threading.Thread(target=pump, daemon=True)
    t.start()
    if not found.wait(timeout=30):
        proc.terminate()
        raise RuntimeError("Backend did not print PB_API_TOKEN within 30s")
    assert token_holder["v"] is not None
    return proc, token_holder["v"]


def serve_frontend_subprocess(port: int) -> subprocess.Popen:
    cmd = [
        sys.executable,
        "-m",
        "http.server",
        str(port),
        "--bind",
        "127.0.0.1",
        "--directory",
        str(FRONTEND_OUT),
    ]
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)


# ------------------------- FROZEN MODE (in-process) -------------------------


def start_backend_in_process(port: int) -> tuple[threading.Thread, str]:
    """Start uvicorn in a thread and mount frontend StaticFiles on the same FastAPI app."""
    import uvicorn
    from fastapi.staticfiles import StaticFiles

    from backend.main import create_app  # noqa: WPS433

    app = create_app()
    if FRONTEND_OUT.is_dir():
        app.mount("/", StaticFiles(directory=str(FRONTEND_OUT), html=True), name="frontend")

    token = app.state.settings.api_token  # type: ignore[attr-defined]

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="info")
    server = uvicorn.Server(config)

    def run() -> None:
        try:
            server.run()
        except SystemExit:
            pass

    t = threading.Thread(target=run, name="uvicorn", daemon=True)
    t.start()

    # wait for /healthz to respond
    import urllib.request
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=1).read()
            print(f"[backend] PB_API_TOKEN={token}", flush=True)
            return t, token
        except Exception:
            time.sleep(0.2)
    raise RuntimeError("backend did not become healthy in 30s")


# ------------------------------ MAIN ---------------------------------------


def main() -> None:
    acquire_single_instance_lock()
    if not FRONTEND_OUT.is_dir():
        print(f"[shell] frontend not built at {FRONTEND_OUT}")
        sys.exit(1)

    # Default: skip master password (PB_DEV_NO_AUTH=1). User can opt back in
    # to auth by setting PB_REQUIRE_AUTH=1 before launching.
    if os.environ.get("PB_REQUIRE_AUTH") != "1":
        os.environ["PB_DEV_NO_AUTH"] = "1"

    ensure_camoufox()

    # First-launch Desktop shortcut (frozen bundle only — in dev mode `sys.executable`
    # is the venv's python.exe, which would create a useless shortcut to a python).
    if IS_FROZEN:
        try:
            ensure_desktop_shortcut(target_exe=Path(sys.executable))
        except Exception as exc:  # noqa: BLE001
            print(f"[shell] shortcut creation failed: {exc!r}")

    backend_port = pick_free_port(DEFAULT_PORT)
    if backend_port != DEFAULT_PORT:
        print(f"[shell] port {DEFAULT_PORT} busy, using {backend_port}")

    if IS_FROZEN:
        print("[shell] starting backend (in-process, frozen mode)…")
        _bt, token = start_backend_in_process(backend_port)
        print(f"[shell] backend up, token={token[:8]}…")
        # Same origin for everything — no separate frontend port, no CORS dance
        url = f"http://127.0.0.1:{backend_port}/?t={token}&api={backend_port}"
        cleanup_subprocesses: list[subprocess.Popen] = []
    else:
        print("[shell] starting backend (subprocess, dev mode)…")
        backend, token = start_backend_subprocess(backend_port)
        print(f"[shell] backend up, token={token[:8]}…")
        frontend_port = backend_port + 1
        print("[shell] starting static frontend server…")
        frontend = serve_frontend_subprocess(frontend_port)
        time.sleep(0.5)
        url = f"http://127.0.0.1:{frontend_port}/?t={token}&api={backend_port}"
        cleanup_subprocesses = [frontend, backend]

    def cleanup() -> None:
        for p in cleanup_subprocesses:
            try:
                if p.poll() is None:
                    if sys.platform == "win32":
                        try:
                            p.send_signal(signal.CTRL_BREAK_EVENT)
                        except (ValueError, OSError):
                            p.terminate()
                    else:
                        p.terminate()
                    p.wait(timeout=5)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass

    atexit.register(cleanup)

    js_inject = f"window.PB_API_BASE = 'http://127.0.0.1:{backend_port}';"
    window = webview.create_window(
        "Genesis Browser",
        url,
        width=1280,
        height=800,
        maximized=True,
        min_size=(900, 600),
    )

    def on_loaded() -> None:
        try:
            window.evaluate_js(js_inject)
        except Exception:
            pass

    webview.start(on_loaded, debug=False)


if __name__ == "__main__":
    main()
