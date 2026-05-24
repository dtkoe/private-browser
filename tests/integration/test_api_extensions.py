import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient


def _xpi(addon_id: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("manifest.json", json.dumps({
            "manifest_version": 2,
            "name": addon_id,
            "version": "1.0",
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
    c.post("/api/auth/initialize", json={"password": "Test12345678X"})
    c.post("/api/auth/unlock", json={"password": "Test12345678X"})
    return c


def test_install_list_delete_extension(client):
    p = client.post("/api/profiles", json={"name": "x"}).json()
    files = {"file": ("ublock.xpi", _xpi("ublock@example"), "application/zip")}
    r = client.post(f"/api/profiles/{p['id']}/extensions", files=files)
    assert r.status_code == 200, r.text
    assert r.json()["id"] == "ublock@example"

    r = client.get(f"/api/profiles/{p['id']}/extensions")
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = client.delete(f"/api/profiles/{p['id']}/extensions/ublock@example")
    assert r.status_code == 204

    r = client.get(f"/api/profiles/{p['id']}/extensions")
    assert r.json() == []


def test_extension_isolation_between_profiles(client):
    a = client.post("/api/profiles", json={"name": "A"}).json()
    b = client.post("/api/profiles", json={"name": "B"}).json()
    files = {"file": ("u.xpi", _xpi("only-in-a@x"), "application/zip")}
    client.post(f"/api/profiles/{a['id']}/extensions", files=files)
    assert any(e["id"] == "only-in-a@x" for e in client.get(f"/api/profiles/{a['id']}/extensions").json())
    assert client.get(f"/api/profiles/{b['id']}/extensions").json() == []


def test_install_bad_xpi_returns_422(client):
    p = client.post("/api/profiles", json={"name": "y"}).json()
    files = {"file": ("not-xpi.xpi", b"not a zip", "application/zip")}
    r = client.post(f"/api/profiles/{p['id']}/extensions", files=files)
    assert r.status_code == 422


def test_clone_profile(client):
    p = client.post("/api/profiles", json={"name": "Orig"}).json()
    r = client.post(f"/api/profiles/{p['id']}/clone", json={"new_name": "Cloned"})
    assert r.status_code == 201
    cloned = r.json()
    assert cloned["name"] == "Cloned"
    assert cloned["id"] != p["id"]
    assert cloned["fingerprint"]["_seeds"] != p["fingerprint"]["_seeds"]


def test_bulk_delete_endpoint(client):
    ids = [client.post("/api/profiles", json={"name": f"b{i}"}).json()["id"] for i in range(3)]
    r = client.post("/api/profiles/bulk/delete", json={"ids": ids})
    assert r.status_code == 200
    assert set(r.json()["deleted"]) == set(ids)
    assert client.get("/api/profiles").json() == []
