import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.profiles import build_profiles_router
from backend.core.app_state import AppState
from backend.core.config import Settings
from backend.services.profile_service import ProfileService
from backend.services.security_service import SecurityService


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    settings = Settings()
    settings.ensure_dirs()
    security = SecurityService(settings)
    security.initialize_with_password("TestPass!1234")
    engine = security.unlock("TestPass!1234")

    state = AppState()
    state.set_unlocked(engine)

    def svc_factory(s: AppState) -> ProfileService:
        return ProfileService(session_factory=s.session_factory, settings=settings)

    app = FastAPI()
    app.state.app_state = state
    app.include_router(build_profiles_router(svc_factory))
    return TestClient(app)


def test_create_profile_returns_201(client):
    r = client.post("/api/profiles", json={"name": "acc-1"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "acc-1"
    assert "id" in body
    assert body["fingerprint"]["_os"] in ("windows", "macos", "linux")


def test_create_with_target_os(client):
    r = client.post("/api/profiles", json={"name": "win-only", "target_os": "windows"})
    assert r.status_code == 201
    assert r.json()["fingerprint"]["_os"] == "windows"


def test_list_profiles(client):
    client.post("/api/profiles", json={"name": "a"})
    client.post("/api/profiles", json={"name": "b"})
    r = client.get("/api/profiles")
    assert r.status_code == 200
    names = {p["name"] for p in r.json()}
    assert names == {"a", "b"}


def test_get_profile(client):
    created = client.post("/api/profiles", json={"name": "x"}).json()
    r = client.get(f"/api/profiles/{created['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]


def test_get_missing_returns_404(client):
    r = client.get("/api/profiles/missing")
    assert r.status_code == 404


def test_patch_profile(client):
    created = client.post("/api/profiles", json={"name": "old"}).json()
    r = client.patch(f"/api/profiles/{created['id']}", json={"name": "new", "notes": "hi"})
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "new"
    assert body["notes"] == "hi"


def test_regenerate_endpoint(client):
    created = client.post("/api/profiles", json={"name": "x", "target_os": "windows"}).json()
    old_seeds = created["fingerprint"]["_seeds"]
    r = client.post(f"/api/profiles/{created['id']}/regenerate", json={"target_os": "windows"})
    assert r.status_code == 200
    assert r.json()["fingerprint"]["_seeds"] != old_seeds


def test_delete_profile(client):
    created = client.post("/api/profiles", json={"name": "del"}).json()
    r = client.delete(f"/api/profiles/{created['id']}")
    assert r.status_code == 204
    r2 = client.get(f"/api/profiles/{created['id']}")
    assert r2.status_code == 404


def test_validate_endpoint_ok(client):
    created = client.post("/api/profiles", json={"name": "vx"}).json()
    r = client.post("/api/fingerprint/validate", json={"config": created["fingerprint"]})
    assert r.status_code == 200
    assert r.json() == {"valid": True}


def test_validate_endpoint_fail(client):
    created = client.post("/api/profiles", json={"name": "vy", "target_os": "windows"}).json()
    bad = dict(created["fingerprint"])
    bad["navigator.platform"] = "MacIntel"
    r = client.post("/api/fingerprint/validate", json={"config": bad})
    assert r.status_code == 422
    assert "platform" in r.json()["detail"]
