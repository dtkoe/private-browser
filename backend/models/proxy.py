from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base
from backend.models.profile import _JsonList


class Proxy(Base):
    __tablename__ = "proxy"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    label: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    host: Mapped[str] = mapped_column(String, nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    username: Mapped[str | None] = mapped_column(String, nullable=True)
    password: Mapped[str | None] = mapped_column(String, nullable=True)

    last_checked_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_check_ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_ip: Mapped[str | None] = mapped_column(String, nullable=True)
    last_country: Mapped[str | None] = mapped_column(String(8), nullable=True)
    last_city: Mapped[str | None] = mapped_column(String, nullable=True)
    last_timezone: Mapped[str | None] = mapped_column(String, nullable=True)
    last_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    tags: Mapped[list[str]] = mapped_column(_JsonList, nullable=False, default=list)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
