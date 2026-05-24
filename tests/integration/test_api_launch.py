import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.launch import build_launch_router
from backend.api.profiles import build_profiles_router
from backend.core.app_state import AppState
from backend.core.config import Settings
from backend.services.launch_manager import LaunchManager
from backend.services.profile_service import ProfileService
from backend.services.proxy_service import ProxyService
from backend.services.security_service import SecurityService
from tests.unit.test_launch_manager import FakeLauncher


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    settings = Settings()
    settings.ensure_dirs()
    sec = SecurityService(settings)
    sec.initialize_with_password("TestPass!1234")
    engine = sec.unlock("TestPass!1234")
    state = AppState()
    state.set_unlocked(engine)

    def svc_factory(s: AppState) -> ProfileService:
        return ProfileService(session_factory=s.session_factory, settings=settings)

    def proxy_factory(s: AppState) -> ProxyService:
        return ProxyService(session_factory=s.session_factory)

    mgr = LaunchManager(FakeLauncher())

    app = FastAPI()
    app.state.app_state = state
    app.include_router(build_profiles_router(svc_factory))
    app.include_router(build_launch_router(svc_factory, proxy_factory, mgr))
    return TestClient(app)


def test_launch_profile(client):
    created = client.post("/api/profiles", json={"name": "x"}).json()
    r = client.post(f"/api/profiles/{created['id']}/launch")
    assert r.status_code == 200
    assert r.json()["status"] == "running"


def test_launch_unknown_returns_404(client):
    r = client.post("/api/profiles/missing/launch")
    assert r.status_code == 404


def test_double_launch_returns_409(client):
    created = client.post("/api/profiles", json={"name": "x"}).json()
    client.post(f"/api/profiles/{created['id']}/launch")
    r = client.post(f"/api/profiles/{created['id']}/launch")
    assert r.status_code == 409


def test_stop_profile(client):
    created = client.post("/api/profiles", json={"name": "x"}).json()
    client.post(f"/api/profiles/{created['id']}/launch")
    r = client.post(f"/api/profiles/{created['id']}/stop")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"


def test_stop_not_running_is_idempotent(client):
    created = client.post("/api/profiles", json={"name": "x"}).json()
    r = client.post(f"/api/profiles/{created['id']}/stop")
    assert r.status_code == 200
