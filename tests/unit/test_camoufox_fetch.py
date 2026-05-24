"""Unit tests for shell/camoufox_fetch.py — path resolution + install detection."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from shell.camoufox_fetch import camoufox_binary_path, is_camoufox_installed


def test_explicit_env_var_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("PB_CAMOUFOX_DIR", str(tmp_path / "custom"))
    p = camoufox_binary_path()
    assert p == tmp_path / "custom" / "camoufox.exe"


def test_default_path_under_localappdata_camoufox_camoufox_cache(monkeypatch, tmp_path):
    monkeypatch.delenv("PB_CAMOUFOX_DIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    p = camoufox_binary_path()
    # Real Camoufox install path is %LOCALAPPDATA%\camoufox\camoufox\Cache\camoufox.exe
    assert p == tmp_path / "camoufox" / "camoufox" / "Cache" / "camoufox.exe"


def test_installed_when_binary_present(monkeypatch, tmp_path):
    monkeypatch.delenv("PB_CAMOUFOX_DIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    target = tmp_path / "camoufox" / "camoufox" / "Cache" / "camoufox.exe"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"fake binary")

    # Force pkgman's installed_verstr path to fail so we fall through to the binary check
    import camoufox.pkgman as pm
    monkeypatch.setattr(pm, "installed_verstr", lambda: (_ for _ in ()).throw(RuntimeError("forced")))

    assert is_camoufox_installed() is True


def test_not_installed_when_nothing_present(monkeypatch, tmp_path):
    monkeypatch.delenv("PB_CAMOUFOX_DIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    import camoufox.pkgman as pm
    monkeypatch.setattr(pm, "installed_verstr", lambda: (_ for _ in ()).throw(RuntimeError("forced")))
    assert is_camoufox_installed() is False
