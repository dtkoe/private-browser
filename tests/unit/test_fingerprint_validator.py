import pytest

from backend.services.fingerprint_generator import FingerprintGenerator, GeneratorOptions
from backend.services.fingerprint_validator import (
    FingerprintValidator,
    ValidationError,
)


@pytest.fixture
def validator() -> FingerprintValidator:
    return FingerprintValidator()


@pytest.fixture
def gen() -> FingerprintGenerator:
    return FingerprintGenerator()


def test_validate_freshly_generated_passes(validator, gen):
    for os_name in ("windows", "macos", "linux"):
        fp = gen.generate(GeneratorOptions(target_os=os_name))
        validator.validate(fp)


def test_validate_missing_meta_fails(validator, gen):
    fp = gen.generate()
    del fp["_meta"]
    with pytest.raises(ValidationError, match="_meta"):
        validator.validate(fp)


def test_validate_missing_seeds_fails(validator, gen):
    fp = gen.generate()
    del fp["_seeds"]
    with pytest.raises(ValidationError, match="_seeds"):
        validator.validate(fp)


def test_validate_os_ua_mismatch_fails(validator, gen):
    fp = gen.generate(GeneratorOptions(target_os="windows"))
    fp["navigator.userAgent"] = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.5; rv:142.0) Gecko/20100101 Firefox/142.0"
    with pytest.raises(ValidationError, match="userAgent.*windows"):
        validator.validate(fp)


def test_validate_os_platform_mismatch_fails(validator, gen):
    fp = gen.generate(GeneratorOptions(target_os="windows"))
    fp["navigator.platform"] = "MacIntel"
    with pytest.raises(ValidationError, match="platform.*windows"):
        validator.validate(fp)


def test_validate_screen_negative_fails(validator, gen):
    fp = gen.generate()
    fp["screen.width"] = -1
    with pytest.raises(ValidationError, match="screen"):
        validator.validate(fp)


def test_validate_unknown_os_fails(validator, gen):
    fp = gen.generate()
    fp["_os"] = "amiga"
    with pytest.raises(ValidationError, match="_os"):
        validator.validate(fp)
