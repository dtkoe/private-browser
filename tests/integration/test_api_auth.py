from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.middleware.auth_token import APITokenMiddleware
from backend.api.auth import build_auth_router
from backend.core.config import Settings
from backend.services.security_service import SecurityService


def make_app(token: str) -> FastAPI:
    app = FastAPI()
    app.add_middleware(APITokenMiddleware, token=token, exempt_paths=("/healthz",))

    @app.get("/healthz")
    def health():
        return {"ok": True}

    @app.get("/secret")
    def secret():
        return {"secret": 42}

    return app


def test_healthz_allowed_without_token():
    app = make_app("the-secret-token")
    client = TestClient(app)
    r = client.get("/healthz")
    assert r.status_code == 200


def test_secret_requires_token():
    app = make_app("the-secret-token")
    client = TestClient(app)
    r = client.get("/secret")
    assert r.status_code == 401


def test_secret_accepts_correct_token():
    app = make_app("the-secret-token")
    client = TestClient(app)
    r = client.get("/secret", headers={"X-PB-Token": "the-secret-token"})
    assert r.status_code == 200
    assert r.json() == {"secret": 42}


def test_secret_rejects_wrong_token():
    app = make_app("the-secret-token")
    client = TestClient(app)
    r = client.get("/secret", headers={"X-PB-Token": "wrong"})
    assert r.status_code == 401


def test_initialize_then_unlock(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    settings = Settings()
    settings.ensure_dirs()
    security = SecurityService(settings)

    app = FastAPI()
    app.include_router(build_auth_router(security))
    client = TestClient(app)

    # Initialize
    r = client.post("/api/auth/initialize", json={"password": "InitPass!1234"})
    assert r.status_code == 201

    # Re-initialize should fail
    r = client.post("/api/auth/initialize", json={"password": "anythingLong12"})
    assert r.status_code == 409

    # Unlock with wrong password
    r = client.post("/api/auth/unlock", json={"password": "wrongpassword12"})
    assert r.status_code == 401

    # Unlock with correct password
    r = client.post("/api/auth/unlock", json={"password": "InitPass!1234"})
    assert r.status_code == 200


def test_unlock_before_initialize(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    settings = Settings()
    settings.ensure_dirs()
    security = SecurityService(settings)

    app = FastAPI()
    app.include_router(build_auth_router(security))
    client = TestClient(app)

    r = client.post("/api/auth/unlock", json={"password": "anylongpassword12"})
    assert r.status_code == 412   # precondition failed: not initialized
