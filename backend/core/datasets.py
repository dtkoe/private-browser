"""Statistical distributions for fingerprint generation."""
from __future__ import annotations

import random
from typing import Mapping, TypeVar

_T = TypeVar("_T")


OS_DISTRIBUTION: Mapping[str, float] = {
    "windows": 0.72,
    "macos": 0.18,
    "linux": 0.10,
}

HW_CONCURRENCY_DISTRIBUTION: Mapping[int, float] = {
    4: 0.25,
    6: 0.15,
    8: 0.35,
    12: 0.15,
    16: 0.10,
}

DEVICE_MEMORY_BY_CONCURRENCY: Mapping[int, int] = {
    4: 8,
    6: 8,
    8: 16,
    12: 16,
    16: 32,
}


def weighted_choice(weights: Mapping[_T, float], *, rng: random.Random | None = None) -> _T:
    total = sum(weights.values())
    if abs(total - 1.0) > 1e-6:
        raise ValueError(f"weights must sum to 1.0, got {total}")
    r = (rng or random).random()
    acc = 0.0
    last_key = None
    for key, w in weights.items():
        last_key = key
        acc += w
        if r <= acc:
            return key
    return last_key  # type: ignore[return-value]
