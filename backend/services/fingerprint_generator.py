"""High-level fingerprint generator. Wraps Camoufox's browserforge generator."""
from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from typing import Any, Literal, TypedDict

from camoufox.fingerprints import from_browserforge, generate_fingerprint

GENERATOR_VERSION = "0.2.0"
SCHEMA_VERSION = 2

OSName = Literal["windows", "macos", "linux"]

# Locale -> sensible default timezone. Used when the user picks a UI language
# but doesn't pin a timezone explicitly. Keeps the JS Intl.timeZone consistent
# with the apparent locale, instead of leaking the host OS timezone.
LOCALE_DEFAULT_TIMEZONE: dict[str, str] = {
    "en-US": "America/New_York",
    "en-GB": "Europe/London",
    "ru-RU": "Europe/Moscow",
    "de-DE": "Europe/Berlin",
    "fr-FR": "Europe/Paris",
    "es-ES": "Europe/Madrid",
    "it-IT": "Europe/Rome",
    "pt-BR": "America/Sao_Paulo",
    "ja-JP": "Asia/Tokyo",
    "zh-CN": "Asia/Shanghai",
    "uk-UA": "Europe/Kyiv",
    "pl-PL": "Europe/Warsaw",
    "tr-TR": "Europe/Istanbul",
}

DEFAULT_LOCALE = "en-US"


class GeoInfo(TypedDict, total=False):
    locale: str        # e.g. "en-US", "ru-RU"
    timezone: str      # e.g. "America/New_York"
    country: str       # ISO-3166 alpha-2
    city: str
    latitude: float
    longitude: float


@dataclass(frozen=True)
class GeneratorOptions:
    target_os: OSName | None = None
    target_geo: GeoInfo | None = None
    pinned_window: tuple[int, int] | None = None
    locale: str | None = None


class FingerprintGenerator:
    """Produces a consistent Camoufox config dict per call."""

    def generate(self, options: GeneratorOptions | None = None) -> dict[str, Any]:
        opts = options or GeneratorOptions()

        os_choice = opts.target_os
        if os_choice is None:
            from backend.core.datasets import OS_DISTRIBUTION, weighted_choice

            os_choice = weighted_choice(OS_DISTRIBUTION)

        # Resolve locale + timezone with sensible fallbacks.
        # Priority: explicit options.locale > target_geo.locale > DEFAULT_LOCALE.
        geo = dict(opts.target_geo) if opts.target_geo else {}
        locale = opts.locale or geo.get("locale") or DEFAULT_LOCALE
        timezone = geo.get("timezone") or LOCALE_DEFAULT_TIMEZONE.get(locale) or LOCALE_DEFAULT_TIMEZONE[DEFAULT_LOCALE]

        fp = generate_fingerprint(os=(os_choice,), window=opts.pinned_window)
        config = from_browserforge(fp)

        # Plug the timezone leak: Camoufox propagates `config['timezone']` to
        # Intl.DateTimeFormat / Date.getTimezoneOffset via its C++ patches.
        # Without this, the host OS timezone leaks (audit 2026-05-25).
        config["timezone"] = timezone

        config["_meta"] = {
            "schema_version": SCHEMA_VERSION,
            "generator_version": GENERATOR_VERSION,
            "generated_at": int(time.time() * 1000),
        }
        config["_os"] = os_choice
        config["_geo"] = {
            "locale": locale,
            "timezone": timezone,
            **{k: v for k, v in geo.items() if k not in ("locale", "timezone")},
        }
        config["_seeds"] = {
            "canvas": secrets.randbits(64),
            "audio": secrets.randbits(64),
            "webgl_noise": secrets.randbits(64),
        }
        return config
