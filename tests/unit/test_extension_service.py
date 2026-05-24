import io
import json
import zipfile

import pytest

from backend.services.extension_service import ExtensionNotFound, ExtensionService


def _fake_xpi(addon_id: str, name: str, version: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("manifest.json", json.dumps({
            "manifest_version": 2,
            "name": name,
            "version": version,
            "browser_specific_settings": {"gecko": {"id": addon_id}},
        }))
    return buf.getvalue()


def test_list_empty(tmp_path):
    svc = ExtensionService()
    assert svc.list_extensions(tmp_path) == []


def test_install_and_list(tmp_path):
    svc = ExtensionService()
    xpi = _fake_xpi("ublock@example", "uBlock Origin", "1.55.0")
    info = svc.install(tmp_path, xpi_bytes=xpi, filename="ublock.xpi")
    assert info["id"] == "ublock@example"
    assert info["name"] == "uBlock Origin"
    listed = svc.list_extensions(tmp_path)
    assert any(e["id"] == "ublock@example" for e in listed)


def test_remove(tmp_path):
    svc = ExtensionService()
    xpi = _fake_xpi("a@x", "A", "1.0")
    svc.install(tmp_path, xpi_bytes=xpi, filename="a.xpi")
    svc.remove(tmp_path, addon_id="a@x")
    assert svc.list_extensions(tmp_path) == []


def test_remove_missing_raises(tmp_path):
    svc = ExtensionService()
    with pytest.raises(ExtensionNotFound):
        svc.remove(tmp_path, addon_id="never@there")


def test_install_bad_xpi_raises(tmp_path):
    svc = ExtensionService()
    with pytest.raises(ValueError):
        svc.install(tmp_path, xpi_bytes=b"not a zip", filename="x.xpi")
