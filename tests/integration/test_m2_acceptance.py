"""M2 acceptance: 10 profiles via API, each with unique consistent fingerprint."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    from backend.main import create_app
    app = create_app()
    c = TestClient(app)
    c.headers["X-PB-Token"] = app.state.settings.api_token
    return c


def test_create_unlock_and_ten_profiles(client):
    r = client.post("/api/auth/initialize", json={"password": "M2Acceptance!12"})
    assert r.status_code == 201
    r = client.post("/api/auth/unlock", json={"password": "M2Acceptance!12"})
    assert r.status_code == 200

    created = []
    for i in range(10):
        r = client.post("/api/profiles", json={"name": f"p-{i}"})
        assert r.status_code == 201, r.text
        created.append(r.json())

    seed_tuples = {tuple(p["fingerprint"]["_seeds"].values()) for p in created}
    assert len(seed_tuples) == 10

    for p in created:
        r = client.post("/api/fingerprint/validate", json={"config": p["fingerprint"]})
        assert r.status_code == 200, r.text

    r = client.get("/api/profiles")
    assert r.status_code == 200
    assert len(r.json()) == 10


def test_profiles_locked_before_unlock(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    from backend.main import create_app
    app = create_app()
    c = TestClient(app)
    c.headers["X-PB-Token"] = app.state.settings.api_token

    r = c.get("/api/profiles")
    assert r.status_code == 423
