import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.launch import build_launch_router
from backend.api.profiles import build_profiles_router
from backend.api.proxies import build_proxies_router
from backend.core.app_state import AppState
from backend.core.config import Settings
from backend.services.launch_manager import LaunchManager
from backend.services.profile_service import ProfileService
from backend.services.proxy_health_checker import HealthCheckResult
from backend.services.proxy_service import ProxyService
from backend.services.security_service import SecurityService
from tests.unit.test_launch_manager import FakeLauncher


class _StaticChecker:
    def check(self, **_):
        return HealthCheckResult(ok=True, ip="1.2.3.4")


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    settings = Settings()
    settings.ensure_dirs()
    sec = SecurityService(settings)
    sec.initialize_with_password("Test12345678X")
    engine = sec.unlock("Test12345678X")
    state = AppState()
    state.set_unlocked(engine)

    def psvc_factory(s: AppState) -> ProfileService:
        return ProfileService(session_factory=s.session_factory, settings=settings)

    def xsvc_factory(s: AppState) -> ProxyService:
        return ProxyService(session_factory=s.session_factory)

    mgr = LaunchManager(FakeLauncher())

    app = FastAPI()
    app.state.app_state = state
    app.include_router(build_profiles_router(psvc_factory))
    app.include_router(build_proxies_router(xsvc_factory, lambda: _StaticChecker()))
    app.include_router(build_launch_router(psvc_factory, xsvc_factory, mgr))
    return TestClient(app)


def test_bind_proxy_and_launch(client):
    proxy = client.post("/api/proxies", json={
        "label": "DE", "type": "http", "host": "1.2.3.4", "port": 8080
    }).json()
    profile = client.post("/api/profiles", json={"name": "px"}).json()

    r = client.patch(f"/api/profiles/{profile['id']}/proxy", json={"proxy_id": proxy["id"]})
    assert r.status_code == 200
    assert r.json()["proxy_id"] == proxy["id"]

    r = client.post(f"/api/profiles/{profile['id']}/launch")
    assert r.status_code == 200, r.text
    assert r.json()["proxy"] == proxy["id"]


def test_unbind_proxy(client):
    proxy = client.post("/api/proxies", json={
        "label": "DE", "type": "http", "host": "1.2.3.4", "port": 8080
    }).json()
    profile = client.post("/api/profiles", json={"name": "px"}).json()
    client.patch(f"/api/profiles/{profile['id']}/proxy", json={"proxy_id": proxy["id"]})
    r = client.patch(f"/api/profiles/{profile['id']}/proxy", json={"proxy_id": None})
    assert r.json()["proxy_id"] is None


def test_launch_without_proxy(client):
    profile = client.post("/api/profiles", json={"name": "no-proxy"}).json()
    r = client.post(f"/api/profiles/{profile['id']}/launch")
    assert r.status_code == 200
    assert r.json()["proxy"] is None


def test_launch_with_dead_bound_proxy_returns_409(client):
    proxy = client.post("/api/proxies", json={
        "label": "DE", "type": "http", "host": "1.2.3.4", "port": 8080
    }).json()
    profile = client.post("/api/profiles", json={"name": "x"}).json()
    client.patch(f"/api/profiles/{profile['id']}/proxy", json={"proxy_id": proxy["id"]})
    client.delete(f"/api/proxies/{proxy['id']}")
    r = client.post(f"/api/profiles/{profile['id']}/launch")
    assert r.status_code == 409
