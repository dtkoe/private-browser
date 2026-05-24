from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

import httpx


@dataclass
class HealthCheckResult:
    ok: bool
    ip: str | None = None
    country: str | None = None
    city: str | None = None
    timezone: str | None = None
    latency_ms: int | None = None
    error: str | None = None


def build_proxy_url(*, type: str, host: str, port: int, username: str | None, password: str | None) -> str:
    auth = f"{username}:{password}@" if username and password else ""
    return f"{type}://{auth}{host}:{port}"


class ProxyHealthChecker:
    def __init__(
        self,
        client_factory: Callable[..., httpx.Client] | None = None,
        endpoint: str = "https://ipinfo.io/json",
        timeout_seconds: float = 5.0,
    ):
        self._make_client = client_factory or self._default_client
        self._endpoint = endpoint
        self._timeout = timeout_seconds

    @staticmethod
    def _default_client(*, proxy: str, timeout: float) -> httpx.Client:
        return httpx.Client(proxy=proxy, timeout=timeout)

    def check(
        self,
        *,
        type: str,
        host: str,
        port: int,
        username: str | None,
        password: str | None,
    ) -> HealthCheckResult:
        proxy = build_proxy_url(type=type, host=host, port=port, username=username, password=password)
        start = time.monotonic()
        try:
            with self._make_client(proxy=proxy, timeout=self._timeout) as client:
                r = client.get(self._endpoint, timeout=self._timeout)
                r.raise_for_status()
                latency_ms = int((time.monotonic() - start) * 1000)
                data = r.json()
                return HealthCheckResult(
                    ok=True,
                    ip=data.get("ip"),
                    country=data.get("country"),
                    city=data.get("city"),
                    timezone=data.get("timezone"),
                    latency_ms=latency_ms,
                )
        except Exception as exc:  # noqa: BLE001
            return HealthCheckResult(ok=False, error=str(exc))
