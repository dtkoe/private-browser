import time

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.models import Base
from backend.models.profile import Profile
from backend.models.proxy import Proxy
from backend.models.session import Session as SessionRow


def test_profile_defaults(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'p.db'}", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(engine, expire_on_commit=False)
    now = int(time.time() * 1000)
    with SessionLocal() as s:
        p = Profile(
            id="p-1",
            name="acc1",
            user_data_dir=str(tmp_path / "profiles" / "p-1"),
            fingerprint={"_os": "windows", "_seeds": {}, "_meta": {}},
            tags=[],
            created_at=now,
            updated_at=now,
            status="new",
        )
        s.add(p)
        s.commit()
        loaded = s.query(Profile).filter_by(id="p-1").one()
        assert loaded.open_count == 0
        assert loaded.tags == []
        assert loaded.fingerprint["_os"] == "windows"


def test_proxy_basic(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'p.db'}", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(engine, expire_on_commit=False)
    now = int(time.time() * 1000)
    with SessionLocal() as s:
        s.add(Proxy(
            id="x-1", label="DE-1", type="http", host="1.2.3.4", port=8080,
            tags=[], created_at=now, updated_at=now,
        ))
        s.commit()
        loaded = s.query(Proxy).filter_by(id="x-1").one()
        assert loaded.last_check_ok is False


def test_session_relation(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'p.db'}", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(engine, expire_on_commit=False)
    now = int(time.time() * 1000)
    with SessionLocal() as s:
        s.add(Profile(
            id="p-1", name="x", user_data_dir="/tmp/p-1",
            fingerprint={}, tags=[], created_at=now, updated_at=now, status="new",
        ))
        s.add(SessionRow(id="s-1", profile_id="p-1", started_at=now))
        s.commit()
        loaded = s.query(SessionRow).filter_by(id="s-1").one()
        assert loaded.profile_id == "p-1"
