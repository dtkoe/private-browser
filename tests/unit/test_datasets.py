import collections

import pytest

from backend.core.datasets import (
    DEVICE_MEMORY_BY_CONCURRENCY,
    HW_CONCURRENCY_DISTRIBUTION,
    OS_DISTRIBUTION,
    weighted_choice,
)


def test_os_distribution_sums_to_one():
    assert abs(sum(OS_DISTRIBUTION.values()) - 1.0) < 1e-9
    assert set(OS_DISTRIBUTION) == {"windows", "macos", "linux"}


def test_hw_concurrency_distribution_sums_to_one():
    assert abs(sum(HW_CONCURRENCY_DISTRIBUTION.values()) - 1.0) < 1e-9
    assert set(HW_CONCURRENCY_DISTRIBUTION).issubset({2, 4, 6, 8, 12, 16})


def test_device_memory_by_concurrency_covers_all_keys():
    for c in HW_CONCURRENCY_DISTRIBUTION:
        assert c in DEVICE_MEMORY_BY_CONCURRENCY
        assert DEVICE_MEMORY_BY_CONCURRENCY[c] in {2, 4, 8, 16, 32}


def test_weighted_choice_distribution():
    import random
    rng = random.Random(42)
    counts = collections.Counter(
        weighted_choice({"a": 0.7, "b": 0.3}, rng=rng) for _ in range(10_000)
    )
    assert 6500 < counts["a"] < 7500
    assert 2500 < counts["b"] < 3500


def test_weighted_choice_rejects_non_normalized():
    with pytest.raises(ValueError):
        weighted_choice({"a": 0.5, "b": 0.6})
