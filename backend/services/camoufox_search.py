"""Repair Camoufox's deliberately-broken search stack so urlbar queries hit Google.

Camoufox 135 ships three layers of search sabotage (verified 2026-08-10 against
135.0.1-beta.24 via browser-console logs):

1. ``modules/SearchEngineSelector.sys.mjs`` inside ``omni.ja`` is patched with a
   hardcoded ``if (true) return [<v1-format stub>]`` — the v2 selector then finds
   no ``defaultEngines`` record and ``SearchService.init()`` throws. Result: ZERO
   engines; typing a query in the urlbar does nothing (multi-word) or tries DNS
   (single word).
2. ``distribution/policies.json`` removes every engine and pins a fake "None"
   engine POSTing to ``http://127.0.0.1`` (only takes effect once 1. is fixed —
   the policy awaits the very init() that 1. breaks).
3. ``camoufox.cfg`` blanks ``services.settings.server`` — Firefox only imports the
   bundled search-config-v2 dump when that pref equals the compiled-in production
   URL (``Utils.LOAD_DUMPS``), so even a healthy selector would get no records.

Layers 1+2 are repaired here by patching the installed Camoufox files
(idempotent; re-applied before every launch because ``camoufox fetch`` restores
the sabotage). Layer 3 is fixed via ``firefox_user_prefs`` in the launcher —
with the production URL set, the dump loads locally from omni.ja and a huge
poll interval keeps remote settings fully offline. Rollback: the original
omni.ja is kept next to the patched one as ``omni.ja.orig``.
"""
from __future__ import annotations

import json
import os
import shutil
import zipfile
from pathlib import Path

import structlog

log = structlog.get_logger("private-browser.camoufox_search")

_SELECTOR_MEMBER = "modules/SearchEngineSelector.sys.mjs"
_STUB = b"async _getConfiguration(firstTime = true) {\n    if (true) {"
_FIXED = b"async _getConfiguration(firstTime = true) {\n    if (false) {"

# Legacy webextension-engine ids Camoufox uninstalls; harmless in FF135 (app
# engines are config-based) but removed so no future model flip re-kills Google.
_SEARCH_EXT_IDS = frozenset(
    {
        "google@search.mozilla.org",
        "bing@search.mozilla.org",
        "amazondotcom@search.mozilla.org",
        "ebay@search.mozilla.org",
        "twitter@search.mozilla.org",
    }
)

_DESIRED_SEARCH_POLICY = {"Default": "Google"}


def camoufox_install_dir() -> Path:
    explicit = os.environ.get("PB_CAMOUFOX_DIR")
    if explicit:
        return Path(explicit)
    from camoufox.pkgman import INSTALL_DIR

    return Path(INSTALL_DIR)


def _patch_omni_selector(omni: Path) -> bool:
    """Flip Camoufox's hardcoded stub so the real dump-loading path runs.
    Returns True when the file was rewritten."""
    with zipfile.ZipFile(omni) as src:
        try:
            member_data = src.read(_SELECTOR_MEMBER)
        except KeyError:
            log.warning("camoufox_search.selector_member_missing", omni=str(omni))
            return False
        if _STUB not in member_data:
            return False  # already patched (or upstream fixed it)
        patched = member_data.replace(_STUB, _FIXED, 1)
        infos = src.infolist()
        tmp = omni.parent / (omni.name + ".tmp")
        with zipfile.ZipFile(tmp, "w") as out:
            for info in infos:
                payload = patched if info.filename == _SELECTOR_MEMBER else src.read(info.filename)
                out.writestr(info, payload)

    backup = omni.parent / (omni.name + ".orig")
    if not backup.exists():
        shutil.copy2(omni, backup)
    try:
        os.replace(tmp, omni)
    except OSError:
        # omni.ja is locked while any Camoufox instance is running; drop the
        # temp copy and retry on a later launch.
        tmp.unlink(missing_ok=True)
        raise
    return True


def _patch_policies(policies_path: Path) -> bool:
    """Replace the engine-stripping SearchEngines policy with 'Google is default'.
    Returns True when the file was rewritten."""
    try:
        data = json.loads(policies_path.read_text("utf-8"))
    except (OSError, ValueError):
        return False
    policies = data.get("policies")
    if not isinstance(policies, dict):
        return False

    changed = False
    if policies.get("SearchEngines") != _DESIRED_SEARCH_POLICY:
        policies["SearchEngines"] = dict(_DESIRED_SEARCH_POLICY)
        changed = True
    uninstall = (policies.get("Extensions") or {}).get("Uninstall")
    if isinstance(uninstall, list):
        kept = [x for x in uninstall if x not in _SEARCH_EXT_IDS]
        if kept != uninstall:
            policies["Extensions"]["Uninstall"] = kept
            changed = True
    if not changed:
        return False

    tmp = policies_path.parent / (policies_path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), "utf-8")
    os.replace(tmp, policies_path)
    return True


def ensure_google_search() -> None:
    """Idempotent, cheap when already repaired. Never raises: a failed patch
    (e.g. omni.ja locked by a running Camoufox) must not block the launch —
    the next launch with no browsers running self-heals."""
    try:
        install = camoufox_install_dir()
        omni = install / "omni.ja"
        if omni.is_file() and _patch_omni_selector(omni):
            log.info("camoufox_search.omni_patched", omni=str(omni))
        policies = install / "distribution" / "policies.json"
        if policies.is_file() and _patch_policies(policies):
            log.info("camoufox_search.policies_patched", path=str(policies))
    except Exception as exc:
        log.warning("camoufox_search.patch_failed", error=repr(exc))
