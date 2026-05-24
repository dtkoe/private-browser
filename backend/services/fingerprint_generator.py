"""High-level fingerprint generator. Wraps Camoufox's browserforge generator."""
from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from typing import Any, Literal, TypedDict

from camoufox.fingerprints import from_browserforge, generate_fingerprint

GENERATOR_VERSION = "0.1.0"
SCHEMA_VERSION = 1

OSName = Literal["windows", "macos", "linux"]


class GeoInfo(TypedDict, total=False):
    country: str
    city: str
    timezone: str
    latitude: float
    longitude: float


@dataclass(frozen=True)
class GeneratorOptions:
    target_os: OSName | None = None
    target_geo: GeoInfo | None = None
    pinned_window: tuple[int, int] | None = None


class FingerprintGenerator:
    """Produces a consistent Camoufox config dict per call."""

    def generate(self, options: GeneratorOptions | None = None) -> dict[str, Any]:
        opts = options or GeneratorOptions()

        os_choice = opts.target_os
        if os_choice is None:
            from backend.core.datasets import OS_DISTRIBUTION, weighted_choice

            os_choice = weighted_choice(OS_DISTRIBUTION)

        fp = generate_fingerprint(os=(os_choice,), window=opts.pinned_window)
        config = from_browserforge(fp)

        config["_meta"] = {
            "schema_version": SCHEMA_VERSION,
            "generator_version": GENERATOR_VERSION,
            "generated_at": int(time.time() * 1000),
        }
        config["_os"] = os_choice
        config["_geo"] = dict(opts.target_geo) if opts.target_geo else None
        config["_seeds"] = {
            "canvas": secrets.randbits(64),
            "audio": secrets.randbits(64),
            "webgl_noise": secrets.randbits(64),
        }
        return config
