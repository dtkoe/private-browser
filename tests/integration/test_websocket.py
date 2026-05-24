"""Verify /ws works end-to-end: publish from backend code -> WS client receives."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app_and_token(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    import backend.services.camoufox_launcher as cl
    from tests.unit.test_launch_manager import FakeLauncher
    monkeypatch.setattr(cl, "CamoufoxLauncher", FakeLauncher)
    import backend.main as m
    monkeypatch.setattr(m, "CamoufoxLauncher", FakeLauncher)
    app = m.create_app()
    return app, app.state.settings.api_token


def test_ws_bad_token_rejected(app_and_token):
    from starlette.websockets import WebSocketDisconnect

    app, _token = app_and_token
    with TestClient(app) as client, pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws?t=wrong-token") as ws:
            ws.receive_json()


def test_ws_receives_profile_status_changed(app_and_token):
    app, token = app_and_token
    # `with TestClient(app)` runs lifespan -> bus.attach_loop fires
    with TestClient(app) as client:
        client.headers["X-PB-Token"] = token

        r = client.post("/api/auth/initialize", json={"password": "WSTest!12345"})
        assert r.status_code == 201
        r = client.post("/api/auth/unlock", json={"password": "WSTest!12345"})
        assert r.status_code == 200

        profile = client.post("/api/profiles", json={"name": "wsprof"}).json()

        with client.websocket_connect(f"/ws?t={token}") as ws:
            r = client.post(f"/api/profiles/{profile['id']}/launch")
            assert r.status_code == 200
            event = ws.receive_json()
            assert event["event"] == "profile_status_changed"
            assert event["profile_id"] == profile["id"]
            assert event["status"] == "running"

            client.post(f"/api/profiles/{profile['id']}/stop")
            event = ws.receive_json()
            assert event["event"] == "profile_status_changed"
            assert event["status"] == "ready"
