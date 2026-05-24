"""M3 acceptance: proxy pool CRUD, batch import, bind to profile."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    # Replace real launcher with the fake one in module — monkeypatch CamoufoxLauncher
    import backend.services.camoufox_launcher as cl
    from tests.unit.test_launch_manager import FakeLauncher
    monkeypatch.setattr(cl, "CamoufoxLauncher", FakeLauncher)
    import backend.main as m
    monkeypatch.setattr(m, "CamoufoxLauncher", FakeLauncher)
    app = m.create_app()
    c = TestClient(app)
    c.headers["X-PB-Token"] = app.state.settings.api_token
    return c


def test_proxy_pool_flow(client):
    r = client.post("/api/auth/initialize", json={"password": "M3Acceptance!12"})
    assert r.status_code == 201
    r = client.post("/api/auth/unlock", json={"password": "M3Acceptance!12"})
    assert r.status_code == 200

    proxies = []
    for i in range(5):
        r = client.post(
            "/api/proxies",
            json={"label": f"P{i}", "type": "http", "host": f"1.1.1.{i}", "port": 8080 + i},
        )
        assert r.status_code == 201
        proxies.append(r.json())

    r = client.get("/api/proxies")
    assert r.status_code == 200
    assert len(r.json()) == 5

    r = client.post(
        "/api/proxies/batch",
        json={"text": "9.9.9.1:1080\n9.9.9.2:1081", "type_default": "socks5"},
    )
    assert r.status_code == 200
    assert r.json()["added"] == 2

    profile = client.post("/api/profiles", json={"name": "with-proxy"}).json()
    r = client.patch(f"/api/profiles/{profile['id']}/proxy", json={"proxy_id": proxies[0]["id"]})
    assert r.status_code == 200
    assert r.json()["proxy_id"] == proxies[0]["id"]

    r = client.post(f"/api/profiles/{profile['id']}/launch")
    assert r.status_code == 200, r.text
    assert r.json()["proxy"] == proxies[0]["id"]

    r = client.post(f"/api/profiles/{profile['id']}/stop")
    assert r.status_code == 200
