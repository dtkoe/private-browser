"""Real Camoufox launcher — slow, opens a real browser window. Marked 'slow'."""
import os
import time

import pytest

from backend.services.camoufox_launcher import CamoufoxLauncher
from backend.services.fingerprint_generator import FingerprintGenerator
from backend.services.launch_manager import LaunchManager


@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("PB_SKIP_CAMOUFOX_SMOKE") == "1",
    reason="Camoufox smoke test skipped via PB_SKIP_CAMOUFOX_SMOKE=1",
)
def test_real_camoufox_launches_and_stops(tmp_path):
    udd = tmp_path / "udd"
    udd.mkdir()
    fp = FingerprintGenerator().generate()
    mgr = LaunchManager(CamoufoxLauncher())
    h = mgr.launch(
        profile_id="smoke-1",
        user_data_dir=str(udd),
        fingerprint=fp,
        proxy=None,
    )
    assert h.is_alive()
    time.sleep(2)
    mgr.stop("smoke-1")
    t0 = time.monotonic()
    while h.is_alive() and time.monotonic() - t0 < 20:
        time.sleep(0.2)
    assert not h.is_alive()
