"""Consistency checks for fingerprint configs."""
from __future__ import annotations

from typing import Any


class ValidationError(ValueError):
    pass


_OS_TO_UA_TOKEN = {
    "windows": "Windows",
    "macos": "Mac",
    "linux": "Linux",
}

_OS_TO_PLATFORM = {
    "windows": {"Win32", "Win64"},
    "macos": {"MacIntel", "Mac68K"},
    "linux": {"Linux x86_64", "Linux i686", "Linux armv81"},
}


class FingerprintValidator:
    def validate(self, fp: dict[str, Any]) -> None:
        for required in ("_meta", "_os", "_seeds"):
            if required not in fp:
                raise ValidationError(f"missing required field: {required}")

        os_name = fp["_os"]
        if os_name not in _OS_TO_UA_TOKEN:
            raise ValidationError(f"_os must be one of {list(_OS_TO_UA_TOKEN)}, got {os_name!r}")

        ua = fp.get("navigator.userAgent", "")
        if _OS_TO_UA_TOKEN[os_name] not in ua:
            raise ValidationError(
                f"navigator.userAgent inconsistent with _os={os_name!r}: {ua!r}"
            )

        platform = fp.get("navigator.platform", "")
        if platform not in _OS_TO_PLATFORM[os_name]:
            raise ValidationError(
                f"navigator.platform={platform!r} inconsistent with _os={os_name!r}"
            )

        for key in ("screen.width", "screen.height", "screen.availWidth", "screen.availHeight"):
            v = fp.get(key)
            if not isinstance(v, int) or v <= 0:
                raise ValidationError(f"screen field {key!r} must be positive int, got {v!r}")

        seeds = fp["_seeds"]
        for s in ("canvas", "audio", "webgl_noise"):
            if s not in seeds or not isinstance(seeds[s], int):
                raise ValidationError(f"_seeds.{s} missing or not int")
