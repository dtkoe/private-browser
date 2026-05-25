"""Profile CRUD + regenerate."""
from __future__ import annotations

import secrets
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


def _new_seed() -> int:
    return secrets.randbits(64)


def _emit(event: dict) -> None:
    try:
        from backend.services.event_bus import bus
        bus.publish(event)
    except Exception:
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
        locale: str | None = None,
        timezone: str | None = None,
    ) -> Profile:
        pid = str(uuid.uuid4())
        now = _now_ms()
        geo = _geo_from(locale, timezone)
        fp = self._gen.generate(GeneratorOptions(target_os=target_os, locale=locale, target_geo=geo))
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
        _emit({"event": "profile_created", "profile_id": pid})
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
        _emit({"event": "profile_updated", "profile_id": profile_id})
        return row

    def regenerate_fingerprint(
        self,
        profile_id: str,
        *,
        target_os: OSName | None = None,
        locale: str | None = None,
        timezone: str | None = None,
    ) -> Profile:
        with self._sf() as s:
            row = s.execute(select(Profile).where(Profile.id == profile_id)).scalar_one_or_none()
            if row is None:
                raise ProfileNotFound(profile_id)
            # If caller didn't pass locale/timezone, preserve whatever the
            # existing profile had so regeneration doesn't silently flip locale.
            prev_geo = (row.fingerprint or {}).get("_geo") or {}
            eff_locale = locale or prev_geo.get("locale")
            eff_tz = timezone or prev_geo.get("timezone")
            geo = _geo_from(eff_locale, eff_tz)
            row.fingerprint = self._gen.generate(GeneratorOptions(
                target_os=target_os, locale=eff_locale, target_geo=geo,
            ))
            row.updated_at = _now_ms()
            s.commit()
            s.refresh(row)
            s.expunge(row)
        _emit({"event": "profile_updated", "profile_id": profile_id})
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
        _emit({"event": "profile_updated", "profile_id": profile_id})
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
        _emit({
            "event": "profile_status_changed",
            "profile_id": profile_id,
            "status": status_value,
        })
        return row

    def clone(
        self,
        profile_id: str,
        *,
        new_name: str | None = None,
        include_cookies: bool = True,
    ) -> Profile:
        src = self.get(profile_id)
        new_id = str(uuid.uuid4())
        now = _now_ms()
        new_fp = dict(src.fingerprint)
        new_fp["_seeds"] = {
            "canvas": _new_seed(),
            "audio": _new_seed(),
            "webgl_noise": _new_seed(),
        }
        new_fp["_meta"] = dict(new_fp.get("_meta", {}))
        new_fp["_meta"]["generated_at"] = now

        new_udd = self._settings.profiles_dir / new_id
        if include_cookies and Path(src.user_data_dir).is_dir():
            shutil.copytree(src.user_data_dir, new_udd)
        else:
            new_udd.mkdir(parents=True, exist_ok=False)

        clone = Profile(
            id=new_id,
            name=new_name or f"{src.name} (clone)",
            notes=src.notes,
            tags=list(src.tags),
            color=src.color,
            created_at=now,
            updated_at=now,
            status="new",
            fingerprint=new_fp,
            proxy_id=src.proxy_id,
            user_data_dir=str(new_udd),
        )
        with self._sf() as s:
            s.add(clone)
            s.commit()
            s.refresh(clone)
            s.expunge(clone)
        _emit({"event": "profile_created", "profile_id": new_id})
        return clone

    def bulk_delete(self, profile_ids: list[str]) -> list[str]:
        deleted: list[str] = []
        for pid in profile_ids:
            try:
                self.delete(pid)
                deleted.append(pid)
            except ProfileNotFound:
                pass
        return deleted

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
        _emit({"event": "profile_deleted", "profile_id": profile_id})


def _now_ms() -> int:
    return int(time.time() * 1000)


def _geo_from(locale: str | None, timezone: str | None) -> dict | None:
    """Build a GeoInfo dict for the generator only when at least one field is set."""
    out: dict = {}
    if locale:
        out["locale"] = locale
    if timezone:
        out["timezone"] = timezone
    return out or None
