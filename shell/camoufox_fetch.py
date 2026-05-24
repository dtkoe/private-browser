"""Run `camoufox fetch` (or check if already present) with logging."""
from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path


def camoufox_binary_path() -> Path:
    explicit = os.environ.get("PB_CAMOUFOX_DIR")
    if explicit:
        return Path(explicit) / "camoufox.exe"
    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "camoufox"
    return base / "camoufox.exe"


def is_camoufox_installed() -> bool:
    try:
        from camoufox.pkgman import installed_verstr
        return bool(installed_verstr())
    except Exception:
        return camoufox_binary_path().is_file()


def fetch_camoufox(log: Callable[[str], None]) -> None:
    log("[camoufox] downloading Camoufox bundle…")
    cmd = [sys.executable, "-m", "camoufox", "fetch"]
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        log(f"[camoufox] {line.rstrip()}")
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"camoufox fetch failed with rc={proc.returncode}")
    log("[camoufox] done.")
