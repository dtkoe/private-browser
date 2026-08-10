"""ensure_google_search: repairs Camoufox's sabotaged search files, idempotently."""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

import backend.services.camoufox_search as cs

STUB_SRC = (
    "class SearchEngineSelector {\n"
    "  async _getConfiguration(firstTime = true) {\n"
    "    if (true) {\n"
    "      return [{}];\n"
    "    }\n"
    "    return this._remoteConfig.get();\n"
    "  }\n"
    "}\n"
)

CAMOUFOX_POLICIES = {
    "__COMMENT__": "x",
    "policies": {
        "DisableAppUpdate": True,
        "Extensions": {
            "Uninstall": [
                "google@search.mozilla.org",
                "bing@search.mozilla.org",
                "amazondotcom@search.mozilla.org",
                "ebay@search.mozilla.org",
                "twitter@search.mozilla.org",
                "webcompat@mozilla.org",
                "screenshots@mozilla.org",
            ]
        },
        "SearchEngines": {
            "PreventInstalls": True,
            "Remove": ["Google", "DuckDuckGo"],
            "Default": "None",
            "Add": [{"Name": "None", "URLTemplate": "http://127.0.0.1"}],
        },
    },
}


@pytest.fixture()
def fake_install(tmp_path, monkeypatch) -> Path:
    monkeypatch.setenv("PB_CAMOUFOX_DIR", str(tmp_path))
    with zipfile.ZipFile(tmp_path / "omni.ja", "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(cs._SELECTOR_MEMBER, STUB_SRC)
        z.writestr("modules/Other.sys.mjs", "// untouched\n")
    dist = tmp_path / "distribution"
    dist.mkdir()
    (dist / "policies.json").write_text(json.dumps(CAMOUFOX_POLICIES), "utf-8")
    return tmp_path


def test_repairs_selector_policies_and_keeps_backup(fake_install):
    cs.ensure_google_search()

    with zipfile.ZipFile(fake_install / "omni.ja") as z:
        sel = z.read(cs._SELECTOR_MEMBER).decode()
        assert "if (false) {" in sel
        assert "if (true) {" not in sel
        assert z.read("modules/Other.sys.mjs").decode() == "// untouched\n"
    assert (fake_install / "omni.ja.orig").is_file(), "rollback copy must exist"
    with zipfile.ZipFile(fake_install / "omni.ja.orig") as z:
        assert "if (true) {" in z.read(cs._SELECTOR_MEMBER).decode()

    pol = json.loads((fake_install / "distribution" / "policies.json").read_text("utf-8"))
    assert pol["policies"]["SearchEngines"] == {"Default": "Google"}
    assert pol["policies"]["Extensions"]["Uninstall"] == [
        "webcompat@mozilla.org",
        "screenshots@mozilla.org",
    ]
    # Unrelated policies survive.
    assert pol["policies"]["DisableAppUpdate"] is True


def test_second_run_is_a_noop(fake_install):
    cs.ensure_google_search()
    omni = fake_install / "omni.ja"
    pol = fake_install / "distribution" / "policies.json"
    omni_sig = (omni.stat().st_mtime_ns, omni.stat().st_size)
    pol_sig = (pol.stat().st_mtime_ns, pol.stat().st_size)

    cs.ensure_google_search()

    assert (omni.stat().st_mtime_ns, omni.stat().st_size) == omni_sig
    assert (pol.stat().st_mtime_ns, pol.stat().st_size) == pol_sig


def test_missing_install_never_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("PB_CAMOUFOX_DIR", str(tmp_path / "nope"))
    cs.ensure_google_search()  # nothing to patch, no exception


def test_omni_without_selector_member_is_skipped(tmp_path, monkeypatch):
    monkeypatch.setenv("PB_CAMOUFOX_DIR", str(tmp_path))
    with zipfile.ZipFile(tmp_path / "omni.ja", "w") as z:
        z.writestr("modules/Other.sys.mjs", "x")
    before = (tmp_path / "omni.ja").stat().st_mtime_ns
    cs.ensure_google_search()
    assert (tmp_path / "omni.ja").stat().st_mtime_ns == before
    assert not (tmp_path / "omni.ja.orig").exists()
