import pytest

from backend.services.proxy_validator import (
    ProxyFormatError,
    ProxyValidator,
    parse_batch_line,
)


@pytest.fixture
def v():
    return ProxyValidator()


def test_valid_http(v):
    v.validate(type="http", host="1.2.3.4", port=8080)


def test_valid_socks5(v):
    v.validate(type="socks5", host="proxy.example.com", port=1080)


def test_invalid_type(v):
    with pytest.raises(ProxyFormatError, match="type"):
        v.validate(type="ftp", host="1.2.3.4", port=8080)


def test_port_out_of_range(v):
    with pytest.raises(ProxyFormatError, match="port"):
        v.validate(type="http", host="1.2.3.4", port=70000)
    with pytest.raises(ProxyFormatError, match="port"):
        v.validate(type="http", host="1.2.3.4", port=0)


def test_empty_host(v):
    with pytest.raises(ProxyFormatError, match="host"):
        v.validate(type="http", host="", port=8080)


def test_parse_batch_line_minimal():
    out = parse_batch_line("1.2.3.4:8080", type_default="http")
    assert out == {"type": "http", "host": "1.2.3.4", "port": 8080, "username": None, "password": None}


def test_parse_batch_line_with_auth():
    out = parse_batch_line("proxy.example:1080:user:pass", type_default="socks5")
    assert out == {"type": "socks5", "host": "proxy.example", "port": 1080, "username": "user", "password": "pass"}


def test_parse_batch_line_with_scheme():
    out = parse_batch_line("socks5://1.2.3.4:9050", type_default="http")
    assert out["type"] == "socks5"
    assert out["host"] == "1.2.3.4"
    assert out["port"] == 9050


def test_parse_batch_blank_returns_none():
    assert parse_batch_line("", type_default="http") is None
    assert parse_batch_line("   ", type_default="http") is None
