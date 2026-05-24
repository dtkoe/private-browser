from __future__ import annotations

import io
import json
import re
import zipfile
from pathlib import Path
from typing import Any

_ID_SAFE = re.compile(r"^[A-Za-z0-9@._\-+{}]+$")


class ExtensionNotFound(LookupError):
    pass


class ExtensionService:
    def _ext_dir(self, profile_dir: Path) -> Path:
        d = profile_dir / "extensions"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def list_extensions(self, profile_dir: Path) -> list[dict[str, Any]]:
        d = self._ext_dir(profile_dir)
        out: list[dict[str, Any]] = []
        for f in sorted(d.iterdir()):
            if not f.is_file() or f.suffix != ".xpi":
                continue
            try:
                info = self._read_manifest(f.read_bytes())
            except Exception:
                continue
            info["filename"] = f.name
            out.append(info)
        return out

    def install(self, profile_dir: Path, *, xpi_bytes: bytes, filename: str) -> dict[str, Any]:
        info = self._read_manifest(xpi_bytes)
        addon_id = info["id"]
        if not _ID_SAFE.match(addon_id):
            raise ValueError(f"unsafe addon id: {addon_id!r}")
        d = self._ext_dir(profile_dir)
        target = d / f"{addon_id}.xpi"
        target.write_bytes(xpi_bytes)
        info["filename"] = target.name
        return info

    def remove(self, profile_dir: Path, *, addon_id: str) -> None:
        d = self._ext_dir(profile_dir)
        target = d / f"{addon_id}.xpi"
        if not target.is_file():
            for f in d.glob("*.xpi"):
                try:
                    info = self._read_manifest(f.read_bytes())
                except Exception:
                    continue
                if info["id"] == addon_id:
                    f.unlink()
                    return
            raise ExtensionNotFound(addon_id)
        target.unlink()

    def _read_manifest(self, xpi_bytes: bytes) -> dict[str, Any]:
        try:
            with zipfile.ZipFile(io.BytesIO(xpi_bytes), "r") as z:
                mraw = z.read("manifest.json")
        except (zipfile.BadZipFile, KeyError) as exc:
            raise ValueError(f"not a valid .xpi: {exc}") from exc
        m = json.loads(mraw)
        gecko = (m.get("browser_specific_settings") or {}).get("gecko") or {}
        addon_id = gecko.get("id") or m.get("applications", {}).get("gecko", {}).get("id")
        if not addon_id:
            raise ValueError("xpi has no gecko addon id")
        return {
            "id": addon_id,
            "name": m.get("name", addon_id),
            "version": m.get("version", "0.0.0"),
        }
