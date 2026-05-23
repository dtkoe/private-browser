from __future__ import annotations

from sqlalchemy import CheckConstraint, Integer, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class AppSettings(Base):
    __tablename__ = "app_settings"
    __table_args__ = (CheckConstraint("id = 1", name="ck_app_settings_singleton"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    theme: Mapped[str] = mapped_column(String, default="dark", nullable=False)
    language: Mapped[str] = mapped_column(String, default="ru", nullable=False)
    camoufox_version: Mapped[str | None] = mapped_column(String, nullable=True)
    auto_update_check: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    api_port: Mapped[int] = mapped_column(Integer, default=8769, nullable=False)

    # Master password — KDF
    kdf_salt: Mapped[bytes] = mapped_column(LargeBinary(16), nullable=False)
    kdf_verifier: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    kdf_params_json: Mapped[str] = mapped_column(String, nullable=False)
