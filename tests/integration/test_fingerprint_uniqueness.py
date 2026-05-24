"""Ground-truth: two profiles of the same OS render distinct canvas + WebGL fingerprints."""
from __future__ import annotations

import hashlib
import os

import pytest

from backend.services.fingerprint_generator import FingerprintGenerator, GeneratorOptions

CANVAS_FP_JS = """() => {
  const canvas = document.createElement('canvas');
  canvas.width = 220; canvas.height = 30;
  const ctx = canvas.getContext('2d');
  ctx.textBaseline = 'top';
  ctx.font = '14px Arial';
  ctx.fillStyle = '#f60';
  ctx.fillRect(125, 1, 62, 20);
  ctx.fillStyle = '#069';
  ctx.fillText('Private-Browser-fp-test 🎨', 2, 15);
  return canvas.toDataURL();
}"""


WEBGL_FP_JS = """() => {
  const canvas = document.createElement('canvas');
  const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
  if (!gl) return 'no-webgl';
  const ext = gl.getExtension('WEBGL_debug_renderer_info');
  const vendor = ext ? gl.getParameter(ext.UNMASKED_VENDOR_WEBGL) : gl.getParameter(gl.VENDOR);
  const renderer = ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER);
  return vendor + '||' + renderer;
}"""


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:16]


@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("PB_SKIP_CAMOUFOX_SMOKE") == "1",
    reason="Camoufox smoke test skipped via PB_SKIP_CAMOUFOX_SMOKE=1",
)
def test_two_windows_profiles_have_distinct_canvas_fingerprints(tmp_path):
    from camoufox.sync_api import Camoufox

    gen = FingerprintGenerator()
    results = []
    for i in range(2):
        fp = gen.generate(GeneratorOptions(target_os="windows"))
        cf_config = {k: v for k, v in fp.items() if not k.startswith("_")}
        udd = tmp_path / f"udd-{i}"
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
            canvas_data = page.evaluate(CANVAS_FP_JS)
            webgl_data = page.evaluate(WEBGL_FP_JS)
        results.append({
            "ua": fp["navigator.userAgent"],
            "canvas_hash": _hash(canvas_data),
            "webgl": webgl_data,
            "seed_canvas": fp["_seeds"]["canvas"],
        })

    print("\nProfile 1 canvas:", results[0]["canvas_hash"], "WebGL:", results[0]["webgl"])
    print("Profile 2 canvas:", results[1]["canvas_hash"], "WebGL:", results[1]["webgl"])

    # Canvas hashes MUST differ — that's the core anti-detect promise
    assert results[0]["canvas_hash"] != results[1]["canvas_hash"], (
        f"Two Windows profiles produced IDENTICAL canvas fingerprints! "
        f"hash={results[0]['canvas_hash']}. Anti-detect is broken."
    )
