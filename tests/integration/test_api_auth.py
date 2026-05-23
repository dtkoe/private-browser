from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.middleware.auth_token import APITokenMiddleware


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
