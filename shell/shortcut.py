"""Create a 'Genesis Browser' shortcut on the user's Desktop, once.

We track whether it's been created via a marker file in %APPDATA%\\genesis-browser\\
so subsequent launches don't re-create it (the user may have moved or deleted it
on purpose). The user can force re-create by deleting the marker.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _desktop_dir() -> Path:
    # USERPROFILE\Desktop covers default Windows layout; falls back gracefully
    # if OneDrive has redirected it (we read the SHGetKnownFolderPath via PowerShell).
    try:
        out = subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "[Environment]::GetFolderPath('Desktop')",
            ],
            text=True,
            timeout=5,
        ).strip()
        if out:
            return Path(out)
    except Exception:
        pass
    return Path.home() / "Desktop"


def _marker_path() -> Path:
    base = Path(os.environ.get("APPDATA", str(Path.home()))) / "genesis-browser"
    base.mkdir(parents=True, exist_ok=True)
    return base / "shortcut.created"


def ensure_desktop_shortcut(*, target_exe: Path, log=print) -> Path | None:
    """Create the Desktop shortcut once. Returns its path, or None if skipped/failed."""
    if sys.platform != "win32":
        return None

    marker = _marker_path()
    if marker.exists():
        log(f"[shortcut] already created (marker at {marker}); skipping")
        return None

    desktop = _desktop_dir()
    lnk = desktop / "Genesis Browser.lnk"
    if lnk.exists():
        # User already has it (manually placed it, or marker was lost). Touch the marker.
        marker.write_text(str(lnk), encoding="utf-8")
        log(f"[shortcut] already present at {lnk}; recorded marker")
        return lnk

    ps_script = (
        f"$ws = New-Object -ComObject WScript.Shell; "
        f"$lnk = $ws.CreateShortcut('{lnk}'); "
        f"$lnk.TargetPath = '{target_exe}'; "
        f"$lnk.WorkingDirectory = '{target_exe.parent}'; "
        f"$lnk.IconLocation = '{target_exe},0'; "
        f"$lnk.Description = 'Genesis Browser - antidetect browser manager'; "
        f"$lnk.Save()"
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            check=True,
            timeout=10,
            capture_output=True,
        )
    except Exception as exc:  # noqa: BLE001
        log(f"[shortcut] failed to create: {exc!r}")
        return None
    marker.write_text(str(lnk), encoding="utf-8")
    log(f"[shortcut] created {lnk}")
    return lnk
