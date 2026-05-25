"""Audit: drive a real Camoufox to CreepJS-style probes and observe what leaks.

This is *not* a pass/fail test — it's a diagnostic that prints the fingerprint
surfaces Camoufox sends, so we can manually compare against what was configured
in the profile.
"""
from __future__ import annotations

import json
import os

import pytest

from backend.services.fingerprint_generator import FingerprintGenerator, GeneratorOptions


PROBE_JS = r"""
() => {
  const out = {};
  // Navigator surfaces
  for (const k of [
    'userAgent','appVersion','appName','appCodeName','platform','product',
    'oscpu','hardwareConcurrency','deviceMemory','language','languages',
    'doNotTrack','vendor','cookieEnabled','onLine','pdfViewerEnabled',
    'maxTouchPoints'
  ]) out['navigator.'+k] = navigator[k];

  // Screen
  for (const k of ['width','height','availWidth','availHeight','colorDepth','pixelDepth'])
    out['screen.'+k] = screen[k];

  // Window dimensions
  for (const k of ['outerWidth','outerHeight','screenX','screenY','devicePixelRatio'])
    out['window.'+k] = window[k];

  // Timezone + Locale
  try {
    out['intl.timeZone'] = Intl.DateTimeFormat().resolvedOptions().timeZone;
    out['intl.locale'] = Intl.DateTimeFormat().resolvedOptions().locale;
  } catch(e) { out['intl.error'] = String(e); }
  out['Date.tzOffsetMinutes'] = new Date().getTimezoneOffset();

  // WebGL renderer / vendor
  try {
    const cv = document.createElement('canvas');
    const gl = cv.getContext('webgl');
    const ext = gl && gl.getExtension('WEBGL_debug_renderer_info');
    if (gl && ext) {
      out['webgl.vendor'] = gl.getParameter(ext.UNMASKED_VENDOR_WEBGL);
      out['webgl.renderer'] = gl.getParameter(ext.UNMASKED_RENDERER_WEBGL);
    } else if (gl) {
      out['webgl.vendor'] = gl.getParameter(gl.VENDOR);
      out['webgl.renderer'] = gl.getParameter(gl.RENDERER);
    } else out['webgl'] = 'unavailable';
  } catch(e) { out['webgl.error'] = String(e); }

  // Plugins / mimeTypes count
  try { out['plugins.length'] = navigator.plugins.length; } catch(e) {}
  try { out['mimeTypes.length'] = navigator.mimeTypes.length; } catch(e) {}

  // Battery + connection (often gated in FF)
  out['battery.exposed'] = typeof navigator.getBattery === 'function';
  out['connection.exposed'] = !!navigator.connection;

  // Permissions and storage
  out['storage.estimate'] = typeof (navigator.storage && navigator.storage.estimate) === 'function';

  // Speech synthesis voices count
  try {
    const vs = window.speechSynthesis && speechSynthesis.getVoices();
    out['speech.voices.length'] = vs ? vs.length : null;
  } catch(e) {}

  return out;
}
"""


@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("PB_SKIP_CAMOUFOX_SMOKE") == "1",
    reason="Camoufox smoke test skipped via PB_SKIP_CAMOUFOX_SMOKE=1",
)
def test_audit_what_camoufox_actually_exposes(tmp_path, capsys):
    from camoufox.sync_api import Camoufox

    # Use the generator's default locale (en-US) -> timezone=America/New_York
    # so the audit verifies the fix for the 2026-05-25 timezone leak.
    fp = FingerprintGenerator().generate(GeneratorOptions(target_os="windows"))
    cf_config = {k: v for k, v in fp.items() if not k.startswith("_")}
    udd = tmp_path / "udd"
    udd.mkdir()

    locale = fp["_geo"]["locale"]
    firefox_user_prefs = {
        "intl.accept_languages": f"{locale},{locale.split('-')[0]},en",
    }

    with Camoufox(
        config=cf_config,
        user_data_dir=str(udd),
        persistent_context=True,
        headless=True,
        locale=locale,
        firefox_user_prefs=firefox_user_prefs,
        i_know_what_im_doing=True,
    ) as browser:
        page = browser.new_page()
        page.goto("about:blank")
        observed = page.evaluate(PROBE_JS)

    print("\n=== Configured (FingerprintGenerator) ===")
    for k in sorted(cf_config.keys()):
        print(f"  {k} = {cf_config[k]!r}")

    print("\n=== Observed (in Camoufox at runtime) ===")
    for k in sorted(observed.keys()):
        print(f"  {k} = {observed[k]!r}")

    # Critical assertions: things we explicitly set should match
    assert observed["navigator.userAgent"] == cf_config["navigator.userAgent"]
    assert observed["screen.width"] == cf_config["screen.width"]
    assert observed["screen.height"] == cf_config["screen.height"]
    assert observed["navigator.hardwareConcurrency"] == cf_config["navigator.hardwareConcurrency"]
    assert observed["navigator.platform"] == cf_config["navigator.platform"]

    # Language assertion (driven by locale + firefox_user_prefs)
    assert observed["navigator.language"].startswith("en"), (
        f"language leaked, got {observed['navigator.language']!r}"
    )

    # Configured timezone (set by FingerprintGenerator) must match what Intl reports.
    expected_tz = cf_config["timezone"]
    assert observed["intl.timeZone"] == expected_tz, (
        f"TIMEZONE LEAK: configured {expected_tz!r}, browser reports {observed['intl.timeZone']!r}"
    )

    # Print a clear PASS/FAIL summary for human review
    print("\n=== Audit summary ===")
    gaps = []
    # deviceMemory: Firefox doesn't expose this Chrome-only API.
    # If it WERE exposed, it would need to be set; getting None is the FF default and OK.
    if observed.get("navigator.deviceMemory") is not None and observed.get("navigator.deviceMemory") not in (2, 4, 8, 16):
        gaps.append(f"deviceMemory exposed but suspicious (got {observed.get('navigator.deviceMemory')!r})")
    if "ANGLE" not in str(observed.get("webgl.renderer", "")).upper():
        gaps.append(f"WebGL renderer suspicious (got {observed.get('webgl.renderer')!r})")
    if gaps:
        print("GAPS:")
        for g in gaps:
            print(f"  - {g}")
    else:
        print(f"No critical gaps. Timezone correctly = {observed['intl.timeZone']}.")
