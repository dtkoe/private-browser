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
    # Real install path mirrors camoufox.pkgman.INSTALL_DIR
    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "camoufox" / "camoufox" / "Cache"
    return base / "camoufox.exe"


def is_camoufox_installed() -> bool:
    """Returns True if Camoufox is verifiably installed, False otherwise.
    Does NOT mutate state — caller can safely call fetch_camoufox if False."""
    # Primary: ask the SDK for the version (reads Cache/version.json)
    try:
        from camoufox.pkgman import installed_verstr
        if installed_verstr():
            return True
    except Exception:
        pass
    # Fallback: just check the binary file (handles transient version.json glitches)
    return camoufox_binary_path().is_file()


def fetch_camoufox(log: Callable[[str], None]) -> None:
    """In dev mode: subprocess `python -m camoufox fetch`.
    In frozen mode: import CamoufoxFetcher and call install() directly — `sys.executable`
    is the bundled exe (not python), so subprocess would re-launch ourselves."""
    log("[camoufox] downloading Camoufox bundle…")
    if getattr(sys, "frozen", False):
        from camoufox.pkgman import CamoufoxFetcher
        fetcher = CamoufoxFetcher()
        try:
            fetcher.install()
        except Exception as exc:
            raise RuntimeError(f"camoufox install failed: {exc}") from exc
        log("[camoufox] done.")
        return

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
