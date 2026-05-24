from __future__ import annotations

import json
from typing import Any

from sqlalchemy import BigInteger, Integer, String, Text, TypeDecorator
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class _JsonBlob(TypeDecorator):
    """Serializes/deserializes a dict to TEXT as JSON."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        return json.dumps(value, separators=(",", ":"))

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        return json.loads(value)


class _JsonList(_JsonBlob):
    """JSON-encoded list."""


class Profile(Base):
    __tablename__ = "profile"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str]] = mapped_column(_JsonList, nullable=False, default=list)
    color: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    last_opened_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    open_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="new")

    fingerprint: Mapped[dict] = mapped_column(_JsonBlob, nullable=False)
    proxy_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_data_dir: Mapped[str] = mapped_column(String, nullable=False)

    total_sessions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_duration_sec: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
