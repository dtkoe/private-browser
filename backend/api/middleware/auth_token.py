from __future__ import annotations

import hmac
from collections.abc import Iterable

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
        # CORS preflight: let it through so browsers can negotiate
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path

        # Only protect /api/* and /ws. Static/frontend assets and exempt paths pass through.
        is_protected = path.startswith("/api/") or path == "/ws" or path.startswith("/ws?")
        if not is_protected:
            return await call_next(request)

        if any(path.startswith(p) for p in self._exempt):
            return await call_next(request)

        provided = request.headers.get("X-PB-Token", "")
        if not hmac.compare_digest(provided, self._token):
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)

        return await call_next(request)
