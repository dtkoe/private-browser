import json

import pytest

from backend.services.fingerprint_generator import (
    FingerprintGenerator,
    GeneratorOptions,
)


@pytest.fixture
def gen() -> FingerprintGenerator:
    return FingerprintGenerator()


def test_generate_returns_dict_with_meta(gen):
    fp = gen.generate()
    assert fp["_meta"]["schema_version"] >= 2  # bumped in v0.2.0 for locale+timezone in _geo
    assert fp["_meta"]["generated_at"] > 0
    assert "generator_version" in fp["_meta"]


def test_generate_returns_seeds(gen):
    fp = gen.generate()
    seeds = fp["_seeds"]
    assert set(seeds.keys()) >= {"canvas", "audio", "webgl_noise"}
    for v in seeds.values():
        assert isinstance(v, int)
        assert v != 0


def test_generate_seeds_are_unique_across_calls(gen):
    seeds_1 = gen.generate()["_seeds"]
    seeds_2 = gen.generate()["_seeds"]
    assert seeds_1 != seeds_2


def test_generate_with_target_os_windows(gen):
    fp = gen.generate(GeneratorOptions(target_os="windows"))
    assert fp["_os"] == "windows"
    assert "Windows" in fp["navigator.userAgent"]
    assert fp["navigator.platform"] == "Win32"


def test_generate_with_target_os_macos(gen):
    fp = gen.generate(GeneratorOptions(target_os="macos"))
    assert fp["_os"] == "macos"
    assert "Mac" in fp["navigator.userAgent"] or "Macintosh" in fp["navigator.userAgent"]
    assert fp["navigator.platform"] in {"MacIntel", "Mac68K"}


def test_generate_with_target_os_linux(gen):
    fp = gen.generate(GeneratorOptions(target_os="linux"))
    assert fp["_os"] == "linux"
    assert "Linux" in fp["navigator.userAgent"]
    assert "Linux" in fp["navigator.platform"]


def test_generate_screen_dimensions_present(gen):
    fp = gen.generate()
    for key in ("screen.width", "screen.height", "screen.availWidth", "screen.availHeight"):
        assert isinstance(fp[key], int)
        assert fp[key] > 0


def test_generate_navigator_ua_matches_oscpu(gen):
    fp = gen.generate(GeneratorOptions(target_os="windows"))
    assert "Windows NT" in fp["navigator.oscpu"]


def test_generate_includes_color_depth(gen):
    fp = gen.generate()
    assert fp["screen.colorDepth"] in {24, 30, 32}
    assert fp["screen.pixelDepth"] in {24, 30, 32}


def test_ten_generations_produce_distinct_seeds(gen):
    fps = [gen.generate() for _ in range(10)]
    seed_set = {tuple(f["_seeds"].values()) for f in fps}
    assert len(seed_set) == 10


def test_generate_with_geo_sets_geo_fields(gen):
    geo = {
        "country": "DE",
        "city": "Berlin",
        "timezone": "Europe/Berlin",
        "latitude": 52.52,
        "longitude": 13.405,
    }
    fp = gen.generate(GeneratorOptions(target_os="windows", target_geo=geo))
    # All caller-supplied geo keys should be preserved verbatim.
    for k, v in geo.items():
        assert fp["_geo"][k] == v, f"{k} not preserved"
    # And the generator may add a default locale alongside the user's geo.
    assert "locale" in fp["_geo"]


def test_generate_without_geo_fills_default_locale_and_timezone(gen):
    """v0.2.0: _geo is always populated with locale+timezone defaults so the
    Camoufox launcher can plug Intl.timeZone (was leaking the host TZ before)."""
    fp = gen.generate()
    assert fp["_geo"]["locale"] == "en-US"
    assert fp["_geo"]["timezone"] == "America/New_York"
    # And the timezone must propagate into Camoufox config so it actually applies.
    assert fp["timezone"] == "America/New_York"


def test_generate_with_locale_picks_matching_timezone(gen):
    fp = gen.generate(GeneratorOptions(locale="ru-RU"))
    assert fp["_geo"]["locale"] == "ru-RU"
    assert fp["_geo"]["timezone"] == "Europe/Moscow"
    assert fp["timezone"] == "Europe/Moscow"


def test_generate_explicit_timezone_overrides_locale_default(gen):
    fp = gen.generate(GeneratorOptions(locale="en-US", target_geo={"timezone": "Asia/Tokyo"}))
    assert fp["_geo"]["timezone"] == "Asia/Tokyo"
    assert fp["timezone"] == "Asia/Tokyo"


def test_generated_config_serializable_as_json(gen):
    fp = gen.generate()
    s = json.dumps(fp)
    fp_2 = json.loads(s)
    assert fp_2 == fp


def test_seeds_are_uint64_range(gen):
    fp = gen.generate()
    for v in fp["_seeds"].values():
        assert 0 <= v < 2**64
