from __future__ import annotations

import hmac
from typing import Iterable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class APITokenMiddleware(BaseHTTPMiddleware):
    """Require X-PB-Token header on every request except `exempt_paths`."""

    def __init__(self, app, token: str, exempt_paths: Iterable[str] = ()) -> None:
        super().__init__(app)
        self._token = token
        self._exempt = tuple(exempt_paths)

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if any(path.startswith(p) for p in self._exempt):
            return await call_next(request)

        provided = request.headers.get("X-PB-Token", "")
        if not hmac.compare_digest(provided, self._token):
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)

        return await call_next(request)
