import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


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
    c.post("/api/auth/initialize", json={"password": "Test12345678X"})
    c.post("/api/auth/unlock", json={"password": "Test12345678X"})
    return c


def test_export_import_round_trip(client):
    created = client.post("/api/profiles", json={"name": "OrigAcc", "target_os": "windows"}).json()
    (Path(created["user_data_dir"]) / "cookies.sqlite").write_bytes(b"FAKE-COOKIES-DB")

    r = client.post(
        f"/api/profiles/{created['id']}/export",
        json={"password": "Export!Pwd12345", "include_browser_data": True},
    )
    assert r.status_code == 200, r.text
    pbprof_bytes = r.content
    assert len(pbprof_bytes) > 500

    client.delete(f"/api/profiles/{created['id']}")
    assert client.get(f"/api/profiles/{created['id']}").status_code == 404

    files = {"file": ("p.pbprof", io.BytesIO(pbprof_bytes), "application/octet-stream")}
    r = client.post("/api/import", data={"password": "Export!Pwd12345"}, files=files)
    assert r.status_code == 200, r.text
    new = r.json()
    assert "imported" in new["name"]

    fresh = client.get(f"/api/profiles/{new['id']}").json()
    assert fresh["fingerprint"]["_os"] == "windows"
    assert (Path(fresh["user_data_dir"]) / "cookies.sqlite").read_bytes() == b"FAKE-COOKIES-DB"


def test_import_wrong_password(client):
    created = client.post("/api/profiles", json={"name": "x"}).json()
    r = client.post(f"/api/profiles/{created['id']}/export", json={"password": "Correct12345X"})
    pbprof = r.content
    files = {"file": ("p.pbprof", io.BytesIO(pbprof), "application/octet-stream")}
    r = client.post("/api/import", data={"password": "Wrong12345XYZ"}, files=files)
    assert r.status_code == 401
