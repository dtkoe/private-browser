"""Build private-browser desktop bundle. Run from repo root."""
from __future__ import annotations

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
BUILD = ROOT / "build"


def run(cmd: list[str], cwd: Path) -> None:
    print(f"[build] $ {' '.join(cmd)}")
    # On Windows, npm/npx are .cmd shims that need shell resolution
    use_shell = sys.platform == "win32" and cmd[0] in {"npm", "npx", "yarn", "pnpm"}
    subprocess.check_call(cmd, cwd=str(cwd), shell=use_shell)


def main() -> None:
    print("[build] clean previous outputs")
    for p in (DIST / "private-browser", DIST / "private-browser-portable.zip"):
        if p.exists():
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()

    print("[build] frontend build")
    fe = ROOT / "frontend"
    if not (fe / "node_modules").exists():
        run(["npm", "install", "--no-audit", "--no-fund"], cwd=fe)
    run(["npm", "run", "build"], cwd=fe)

    print("[build] pyinstaller")
    run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            str(BUILD / "private_browser.spec"),
        ],
        cwd=ROOT,
    )

    print("[build] zip portable")
    folder = DIST / "private-browser"
    zip_path = DIST / "private-browser-portable.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in folder.rglob("*"):
            if f.is_file():
                zf.write(f, f.relative_to(DIST))
    print(f"[build] done. {zip_path}")


if __name__ == "__main__":
    main()
