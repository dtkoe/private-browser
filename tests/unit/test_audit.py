from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.models import Base
from backend.models.audit_log import AuditLog
from backend.services.audit_service import AuditService


def test_record_audit_entry(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'a.db'}", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(engine, expire_on_commit=False)
    svc = AuditService(SessionLocal)
    svc.record(actor="user", action="profile.create", target_type="profile", target_id="abc", details={"name": "x"})

    with SessionLocal() as session:
        rows = session.execute(select(AuditLog)).scalars().all()
        assert len(rows) == 1
        assert rows[0].action == "profile.create"
        assert rows[0].actor == "user"
    engine.dispose()
