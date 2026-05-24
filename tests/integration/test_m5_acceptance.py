"""M5 acceptance: round-trip + extensions + clone + bulk."""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def _xpi(addon_id: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("manifest.json", json.dumps({
            "manifest_version": 2, "name": addon_id, "version": "1.0",
            "browser_specific_settings": {"gecko": {"id": addon_id}},
        }))
    return buf.getvalue()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    import backend.services.camoufox_launcher as cl
    from tests.unit.test_launch_manager import FakeLauncher
    monkeypatch.setattr(cl, "CamoufoxLauncher", FakeLauncher)
    import backend.main as m
    monkeypatch.setattr(m, "CamoufoxLauncher", FakeLauncher)
    app = m.create_app()
    c = TestClient(app)
    c.headers["X-PB-Token"] = app.state.settings.api_token
    c.post("/api/auth/initialize", json={"password": "M5Acc12345xy"})
    c.post("/api/auth/unlock", json={"password": "M5Acc12345xy"})
    return c


def test_m5_full_flow(client):
    p = client.post("/api/profiles", json={"name": "Source", "target_os": "windows"}).json()
    (Path(p["user_data_dir"]) / "cookies.sqlite").write_bytes(b"COOKIE-BLOB")
    client.post(
        f"/api/profiles/{p['id']}/extensions",
        files={"file": ("u.xpi", _xpi("ublock@m5"), "application/zip")},
    )
    assert len(client.get(f"/api/profiles/{p['id']}/extensions").json()) == 1

    cloned = client.post(f"/api/profiles/{p['id']}/clone", json={"new_name": "Source (c)"}).json()
    assert cloned["id"] != p["id"]
    assert cloned["fingerprint"]["_seeds"] != p["fingerprint"]["_seeds"]

    r = client.post(f"/api/profiles/{p['id']}/export", json={"password": "Export!Pwd12345"})
    assert r.status_code == 200
    blob = r.content
    client.delete(f"/api/profiles/{p['id']}")
    files = {"file": ("p.pbprof", io.BytesIO(blob), "application/octet-stream")}
    r = client.post("/api/import", data={"password": "Export!Pwd12345"}, files=files)
    assert r.status_code == 200
    imported = client.get(f"/api/profiles/{r.json()['id']}").json()
    assert imported["fingerprint"]["_os"] == "windows"
    assert (Path(imported["user_data_dir"]) / "cookies.sqlite").read_bytes() == b"COOKIE-BLOB"

    r = client.post("/api/profiles/bulk/delete", json={"ids": [cloned["id"], imported["id"]]})
    assert set(r.json()["deleted"]) == {cloned["id"], imported["id"]}
    assert client.get("/api/profiles").json() == []
