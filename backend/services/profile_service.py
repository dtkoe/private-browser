"""Profile CRUD + regenerate."""
from __future__ import annotations

import shutil
import time
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from backend.core.config import Settings
from backend.models.profile import Profile
from backend.services.fingerprint_generator import (
    FingerprintGenerator,
    GeneratorOptions,
    OSName,
)


class ProfileNotFound(LookupError):
    pass


class ProfileService:
    def __init__(
        self,
        session_factory: sessionmaker,
        settings: Settings,
        generator: FingerprintGenerator | None = None,
    ) -> None:
        self._sf = session_factory
        self._settings = settings
        self._gen = generator or FingerprintGenerator()

    def create(
        self,
        *,
        name: str,
        notes: str | None = None,
        tags: list[str] | None = None,
        color: str | None = None,
        target_os: OSName | None = None,
    ) -> Profile:
        pid = str(uuid.uuid4())
        now = _now_ms()
        fp = self._gen.generate(GeneratorOptions(target_os=target_os))
        user_data_dir = self._settings.profiles_dir / pid
        user_data_dir.mkdir(parents=True, exist_ok=False)

        row = Profile(
            id=pid,
            name=name,
            notes=notes,
            tags=tags or [],
            color=color,
            created_at=now,
            updated_at=now,
            status="new",
            fingerprint=fp,
            user_data_dir=str(user_data_dir),
        )
        with self._sf() as s:
            s.add(row)
            s.commit()
            s.refresh(row)
            s.expunge(row)
        return row

    def list_profiles(self) -> list[Profile]:
        with self._sf() as s:
            rows = list(s.execute(select(Profile).order_by(Profile.created_at.desc())).scalars())
            for r in rows:
                s.expunge(r)
        return rows

    def get(self, profile_id: str) -> Profile:
        with self._sf() as s:
            row = s.execute(select(Profile).where(Profile.id == profile_id)).scalar_one_or_none()
            if row is None:
                raise ProfileNotFound(profile_id)
            s.expunge(row)
        return row

    def update(
        self,
        profile_id: str,
        *,
        name: str | None = None,
        notes: str | None = None,
        tags: list[str] | None = None,
        color: str | None = None,
    ) -> Profile:
        with self._sf() as s:
            row = s.execute(select(Profile).where(Profile.id == profile_id)).scalar_one_or_none()
            if row is None:
                raise ProfileNotFound(profile_id)
            if name is not None:
                row.name = name
            if notes is not None:
                row.notes = notes
            if tags is not None:
                row.tags = tags
            if color is not None:
                row.color = color
            row.updated_at = _now_ms()
            s.commit()
            s.refresh(row)
            s.expunge(row)
        return row

    def regenerate_fingerprint(
        self,
        profile_id: str,
        *,
        target_os: OSName | None = None,
    ) -> Profile:
        with self._sf() as s:
            row = s.execute(select(Profile).where(Profile.id == profile_id)).scalar_one_or_none()
            if row is None:
                raise ProfileNotFound(profile_id)
            row.fingerprint = self._gen.generate(GeneratorOptions(target_os=target_os))
            row.updated_at = _now_ms()
            s.commit()
            s.refresh(row)
            s.expunge(row)
        return row

    def set_proxy(self, profile_id: str, proxy_id: str | None) -> Profile:
        with self._sf() as s:
            row = s.execute(select(Profile).where(Profile.id == profile_id)).scalar_one_or_none()
            if row is None:
                raise ProfileNotFound(profile_id)
            row.proxy_id = proxy_id
            row.updated_at = _now_ms()
            s.commit()
            s.refresh(row)
            s.expunge(row)
        return row

    def update_status(
        self,
        profile_id: str,
        *,
        status_value: str,
        last_opened_at: int | None = None,
    ) -> Profile:
        with self._sf() as s:
            row = s.execute(select(Profile).where(Profile.id == profile_id)).scalar_one_or_none()
            if row is None:
                raise ProfileNotFound(profile_id)
            row.status = status_value
            if last_opened_at is not None:
                row.last_opened_at = last_opened_at
                row.open_count = (row.open_count or 0) + 1
            row.updated_at = _now_ms()
            s.commit()
            s.refresh(row)
            s.expunge(row)
        return row

    def delete(self, profile_id: str) -> None:
        with self._sf() as s:
            row = s.execute(select(Profile).where(Profile.id == profile_id)).scalar_one_or_none()
            if row is None:
                raise ProfileNotFound(profile_id)
            udd = Path(row.user_data_dir)
            s.delete(row)
            s.commit()
        if udd.exists():
            shutil.rmtree(udd, ignore_errors=True)


def _now_ms() -> int:
    return int(time.time() * 1000)
