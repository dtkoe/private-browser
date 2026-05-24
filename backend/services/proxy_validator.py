from __future__ import annotations

import re
from typing import Literal

ProxyType = Literal["http", "https", "socks5"]

_ALLOWED_TYPES = {"http", "https", "socks5"}
_HOST_RE = re.compile(r"^[A-Za-z0-9.\-_:]+$")


class ProxyFormatError(ValueError):
    pass


class ProxyValidator:
    def validate(self, *, type: str, host: str, port: int) -> None:
        if type not in _ALLOWED_TYPES:
            raise ProxyFormatError(f"type must be one of {sorted(_ALLOWED_TYPES)}, got {type!r}")
        if not host or not _HOST_RE.match(host):
            raise ProxyFormatError(f"host invalid: {host!r}")
        if not isinstance(port, int) or port <= 0 or port > 65535:
            raise ProxyFormatError(f"port must be 1..65535, got {port!r}")


def parse_batch_line(line: str, *, type_default: ProxyType) -> dict | None:
    s = line.strip()
    if not s:
        return None

    proxy_type: str = type_default
    rest = s
    if "://" in s:
        proxy_type, rest = s.split("://", 1)

    parts = rest.split(":")
    if len(parts) == 2:
        host, port = parts
        return {"type": proxy_type, "host": host, "port": int(port), "username": None, "password": None}
    if len(parts) == 4:
        host, port, user, pw = parts
        return {"type": proxy_type, "host": host, "port": int(port), "username": user, "password": pw}
    raise ProxyFormatError(f"can't parse: {line!r}")
