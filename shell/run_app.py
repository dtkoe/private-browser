"""Desktop shell: launches FastAPI backend as subprocess + opens native window pointing to it."""
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

REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_OUT = REPO_ROOT / "frontend" / "out"
TOKEN_RE = re.compile(r"^PB_API_TOKEN=(\S+)\s*$")
DEFAULT_PORT = 8769

# Allow `from shell.camoufox_fetch import …` whether run as a script or as a module
sys.path.insert(0, str(REPO_ROOT))
from shell.camoufox_fetch import fetch_camoufox, is_camoufox_installed  # noqa: E402


def ensure_camoufox(log=print) -> None:
    if is_camoufox_installed():
        log("[camoufox] already present.")
        return
    log("[camoufox] not installed — first-run download (this may take 5-10 min)…")
    fetch_camoufox(log)


def acquire_single_instance_lock() -> None:
    if sys.platform != "win32":
        return
    import ctypes

    ctypes.windll.kernel32.CreateMutexW(None, False, "Global\\private-browser-mutex-v1")
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        print("[shell] Another instance is already running.", file=sys.stderr)
        sys.exit(1)


def start_backend(port: int) -> tuple[subprocess.Popen, str]:
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


def serve_frontend(port: int) -> subprocess.Popen:
    """Static-file server for the out/ build."""
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


def main() -> None:
    acquire_single_instance_lock()
    if not FRONTEND_OUT.is_dir():
        print("[shell] frontend not built. Run: cd frontend && npm install && npm run build")
        sys.exit(1)

    ensure_camoufox()

    backend_port = DEFAULT_PORT
    frontend_port = backend_port + 1

    print("[shell] starting backend…")
    backend, token = start_backend(backend_port)
    print(f"[shell] backend up, token={token[:8]}…")

    print("[shell] starting static frontend server…")
    frontend = serve_frontend(frontend_port)
    time.sleep(0.5)

    def cleanup() -> None:
        for p, label in [(frontend, "frontend"), (backend, "backend")]:
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
            print(f"[shell] stopped {label}")

    atexit.register(cleanup)

    url = f"http://127.0.0.1:{frontend_port}/?t={token}&api={backend_port}"
    js_inject = f"window.PB_API_BASE = 'http://127.0.0.1:{backend_port}';"

    window = webview.create_window("Private Browser", url, width=1280, height=800)

    def on_loaded() -> None:
        try:
            window.evaluate_js(js_inject)
        except Exception:
            pass

    webview.start(on_loaded, debug=False)


if __name__ == "__main__":
    main()
