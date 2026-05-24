import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.models import Base
from backend.services.proxy_service import ProxyNotFound, ProxyService


@pytest.fixture
def sf(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'p.db'}", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)


def test_create_proxy(sf):
    svc = ProxyService(session_factory=sf)
    p = svc.create(label="DE-1", type="http", host="1.2.3.4", port=8080)
    assert p.id
    assert p.label == "DE-1"
    assert p.last_check_ok is False


def test_list_proxies(sf):
    svc = ProxyService(session_factory=sf)
    svc.create(label="a", type="http", host="1.1.1.1", port=80)
    svc.create(label="b", type="socks5", host="2.2.2.2", port=1080)
    rows = svc.list_proxies()
    assert {r.label for r in rows} == {"a", "b"}


def test_get_proxy(sf):
    svc = ProxyService(session_factory=sf)
    p = svc.create(label="x", type="http", host="1.1.1.1", port=80)
    assert svc.get(p.id).label == "x"


def test_get_missing_raises(sf):
    svc = ProxyService(session_factory=sf)
    with pytest.raises(ProxyNotFound):
        svc.get("nope")


def test_update_label(sf):
    svc = ProxyService(session_factory=sf)
    p = svc.create(label="old", type="http", host="1.1.1.1", port=80)
    svc.update(p.id, label="new")
    assert svc.get(p.id).label == "new"


def test_delete_proxy(sf):
    svc = ProxyService(session_factory=sf)
    p = svc.create(label="x", type="http", host="1.1.1.1", port=80)
    svc.delete(p.id)
    with pytest.raises(ProxyNotFound):
        svc.get(p.id)


def test_batch_import(sf):
    svc = ProxyService(session_factory=sf)
    text = "1.2.3.4:8080\n5.6.7.8:1080:user:pass\nsocks5://9.9.9.9:9050"
    added = svc.batch_import(text=text, type_default="http")
    assert len(added) == 3
    assert added[1].username == "user"
    assert added[2].type == "socks5"


def test_record_health_check(sf):
    svc = ProxyService(session_factory=sf)
    p = svc.create(label="x", type="http", host="1.1.1.1", port=80)
    svc.record_check(
        p.id,
        ok=True,
        ip="2.3.4.5",
        country="DE",
        city="Berlin",
        timezone="Europe/Berlin",
        latency_ms=150,
    )
    fresh = svc.get(p.id)
    assert fresh.last_check_ok is True
    assert fresh.last_ip == "2.3.4.5"
    assert fresh.last_country == "DE"
    assert fresh.last_latency_ms == 150
