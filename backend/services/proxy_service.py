from __future__ import annotations

import time
import uuid

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from backend.models.proxy import Proxy
from backend.services.proxy_validator import (
    ProxyType,
    ProxyValidator,
    parse_batch_line,
)


class ProxyNotFound(LookupError):
    pass


class ProxyService:
    def __init__(self, session_factory: sessionmaker, validator: ProxyValidator | None = None):
        self._sf = session_factory
        self._v = validator or ProxyValidator()

    def create(
        self,
        *,
        label: str,
        type: ProxyType,
        host: str,
        port: int,
        username: str | None = None,
        password: str | None = None,
        notes: str | None = None,
        tags: list[str] | None = None,
    ) -> Proxy:
        self._v.validate(type=type, host=host, port=port)
        now = _now_ms()
        row = Proxy(
            id=str(uuid.uuid4()),
            label=label,
            type=type,
            host=host,
            port=port,
            username=username,
            password=password,
            notes=notes,
            tags=tags or [],
            created_at=now,
            updated_at=now,
        )
        with self._sf() as s:
            s.add(row)
            s.commit()
            s.refresh(row)
            s.expunge(row)
        return row

    def list_proxies(self) -> list[Proxy]:
        with self._sf() as s:
            rows = list(s.execute(select(Proxy).order_by(Proxy.created_at.desc())).scalars())
            for r in rows:
                s.expunge(r)
        return rows

    def get(self, proxy_id: str) -> Proxy:
        with self._sf() as s:
            row = s.execute(select(Proxy).where(Proxy.id == proxy_id)).scalar_one_or_none()
            if row is None:
                raise ProxyNotFound(proxy_id)
            s.expunge(row)
        return row

    def update(self, proxy_id: str, **fields) -> Proxy:
        with self._sf() as s:
            row = s.execute(select(Proxy).where(Proxy.id == proxy_id)).scalar_one_or_none()
            if row is None:
                raise ProxyNotFound(proxy_id)
            for k, v in fields.items():
                if v is not None and hasattr(row, k):
                    setattr(row, k, v)
            row.updated_at = _now_ms()
            s.commit()
            s.refresh(row)
            s.expunge(row)
        return row

    def delete(self, proxy_id: str) -> None:
        with self._sf() as s:
            row = s.execute(select(Proxy).where(Proxy.id == proxy_id)).scalar_one_or_none()
            if row is None:
                raise ProxyNotFound(proxy_id)
            s.delete(row)
            s.commit()

    def record_check(
        self,
        proxy_id: str,
        *,
        ok: bool,
        ip: str | None = None,
        country: str | None = None,
        city: str | None = None,
        timezone: str | None = None,
        latency_ms: int | None = None,
    ) -> Proxy:
        with self._sf() as s:
            row = s.execute(select(Proxy).where(Proxy.id == proxy_id)).scalar_one_or_none()
            if row is None:
                raise ProxyNotFound(proxy_id)
            row.last_checked_at = _now_ms()
            row.last_check_ok = bool(ok)
            row.last_ip = ip
            row.last_country = country
            row.last_city = city
            row.last_timezone = timezone
            row.last_latency_ms = latency_ms
            s.commit()
            s.refresh(row)
            s.expunge(row)
        return row

    def batch_import(self, *, text: str, type_default: ProxyType) -> list[Proxy]:
        added: list[Proxy] = []
        for raw in text.splitlines():
            parsed = parse_batch_line(raw, type_default=type_default)
            if parsed is None:
                continue
            p = self.create(
                label=f"{parsed['host']}:{parsed['port']}",
                type=parsed["type"],
                host=parsed["host"],
                port=parsed["port"],
                username=parsed["username"],
                password=parsed["password"],
            )
            added.append(p)
        return added


def _now_ms() -> int:
    return int(time.time() * 1000)
