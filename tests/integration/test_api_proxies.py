import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.proxies import build_proxies_router
from backend.core.app_state import AppState
from backend.core.config import Settings
from backend.services.proxy_health_checker import HealthCheckResult
from backend.services.proxy_service import ProxyService
from backend.services.security_service import SecurityService


class _FakeChecker:
    def __init__(self, result: HealthCheckResult):
        self._r = result

    def check(self, **_):
        return self._r


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

    def svc_factory(s: AppState) -> ProxyService:
        return ProxyService(session_factory=s.session_factory)

    checker = _FakeChecker(HealthCheckResult(
        ok=True, ip="9.9.9.9", country="DE", city="B", timezone="Europe/Berlin", latency_ms=88
    ))

    app = FastAPI()
    app.state.app_state = state
    app.include_router(build_proxies_router(svc_factory, lambda: checker))
    return TestClient(app)


def test_create_proxy(client):
    r = client.post("/api/proxies", json={"label": "x", "type": "http", "host": "1.2.3.4", "port": 8080})
    assert r.status_code == 201
    assert r.json()["host"] == "1.2.3.4"


def test_list_proxies(client):
    client.post("/api/proxies", json={"label": "a", "type": "http", "host": "1.1.1.1", "port": 80})
    client.post("/api/proxies", json={"label": "b", "type": "http", "host": "2.2.2.2", "port": 80})
    r = client.get("/api/proxies")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_invalid_proxy_returns_422(client):
    r = client.post("/api/proxies", json={"label": "x", "type": "ftp", "host": "x", "port": 80})
    assert r.status_code == 422


def test_check_proxy(client):
    created = client.post("/api/proxies", json={"label": "x", "type": "http", "host": "1.2.3.4", "port": 8080}).json()
    r = client.post(f"/api/proxies/{created['id']}/check")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["ip"] == "9.9.9.9"


def test_batch_import(client):
    text = "1.2.3.4:8080\n5.6.7.8:9090"
    r = client.post("/api/proxies/batch", json={"text": text, "type_default": "http"})
    assert r.status_code == 200
    assert r.json()["added"] == 2


def test_delete_proxy(client):
    created = client.post("/api/proxies", json={"label": "del", "type": "http", "host": "1.1.1.1", "port": 80}).json()
    r = client.delete(f"/api/proxies/{created['id']}")
    assert r.status_code == 204
