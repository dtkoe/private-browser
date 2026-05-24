import httpx

from backend.services.proxy_health_checker import (
    ProxyHealthChecker,
    build_proxy_url,
)


class _FakeResponse:
    def __init__(self, status_code: int, json_payload: dict):
        self.status_code = status_code
        self._json = json_payload

    def json(self) -> dict:
        return self._json

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=self)


class _FakeClient:
    def __init__(self, response: _FakeResponse):
        self._response = response

    def get(self, url: str, timeout: float):
        return self._response

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_build_proxy_url_no_auth():
    assert build_proxy_url(type="http", host="1.2.3.4", port=8080, username=None, password=None) == "http://1.2.3.4:8080"


def test_build_proxy_url_with_auth():
    assert build_proxy_url(type="socks5", host="x", port=1080, username="u", password="p") == "socks5://u:p@x:1080"


def test_check_success():
    fake = _FakeClient(_FakeResponse(200, {
        "ip": "2.3.4.5", "country": "DE", "city": "Berlin", "timezone": "Europe/Berlin",
    }))
    chk = ProxyHealthChecker(client_factory=lambda **_: fake)
    res = chk.check(type="http", host="1.2.3.4", port=8080, username=None, password=None)
    assert res.ok is True
    assert res.ip == "2.3.4.5"
    assert res.country == "DE"
    assert res.timezone == "Europe/Berlin"


def test_check_failure_returns_not_ok():
    def boom(**_):
        raise httpx.ConnectError("nope")
    chk = ProxyHealthChecker(client_factory=boom)
    res = chk.check(type="http", host="x", port=80, username=None, password=None)
    assert res.ok is False
    assert res.ip is None
