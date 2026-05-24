"""Ground-truth: launch real Camoufox and verify navigator.* / screen.* match what we generated."""
from __future__ import annotations

import os

import pytest

from backend.services.fingerprint_generator import FingerprintGenerator, GeneratorOptions


@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("PB_SKIP_CAMOUFOX_SMOKE") == "1",
    reason="Camoufox smoke test skipped via PB_SKIP_CAMOUFOX_SMOKE=1",
)
@pytest.mark.parametrize("target_os", ["windows", "macos", "linux"])
def test_generated_fingerprint_is_actually_applied(target_os, tmp_path):
    """Generate fingerprint, launch Camoufox with it, read navigator.* from the page,
    confirm the values match what we sent."""
    from camoufox.sync_api import Camoufox

    fp = FingerprintGenerator().generate(GeneratorOptions(target_os=target_os))
    cf_config = {k: v for k, v in fp.items() if not k.startswith("_")}

    udd = tmp_path / "udd"
    udd.mkdir()

    with Camoufox(
        config=cf_config,
        user_data_dir=str(udd),
        persistent_context=True,
        headless=True,
        i_know_what_im_doing=True,
    ) as browser:
        page = browser.new_page()
        page.goto("about:blank")
        observed = {
            "userAgent": page.evaluate("() => navigator.userAgent"),
            "platform": page.evaluate("() => navigator.platform"),
            "oscpu": page.evaluate("() => navigator.oscpu"),
            "screen_width": page.evaluate("() => screen.width"),
            "screen_height": page.evaluate("() => screen.height"),
            "hardwareConcurrency": page.evaluate("() => navigator.hardwareConcurrency"),
        }

    assert observed["userAgent"] == fp["navigator.userAgent"], (
        f"UA mismatch: got {observed['userAgent']!r}, sent {fp['navigator.userAgent']!r}"
    )
    assert observed["platform"] == fp["navigator.platform"], (
        f"platform mismatch: got {observed['platform']!r}, sent {fp['navigator.platform']!r}"
    )
    assert observed["oscpu"] == fp["navigator.oscpu"], (
        f"oscpu mismatch: got {observed['oscpu']!r}, sent {fp['navigator.oscpu']!r}"
    )
    assert observed["screen_width"] == fp["screen.width"]
    assert observed["screen_height"] == fp["screen.height"]
    assert observed["hardwareConcurrency"] == fp["navigator.hardwareConcurrency"]
