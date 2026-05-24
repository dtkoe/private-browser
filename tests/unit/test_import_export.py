import io
import json
import zipfile

import pytest

from backend.services.import_export_service import (
    ImportExportService,
    PbprofIntegrityError,
    PbprofPasswordError,
)


@pytest.fixture
def svc():
    return ImportExportService()


def test_round_trip_text_payload(svc, tmp_path):
    payload = {"profile": {"id": "x", "name": "Acc"}, "proxy": None, "browser_data": None}
    out = tmp_path / "export.pbprof"
    svc.export_to_file(out, payload=payload, password="Round!Trip12345")

    assert out.is_file()
    assert out.stat().st_size > 200

    imported = svc.import_from_file(out, password="Round!Trip12345")
    assert imported == payload


def test_import_with_wrong_password_raises(svc, tmp_path):
    out = tmp_path / "e.pbprof"
    svc.export_to_file(out, payload={"k": "v"}, password="CorrectPassword!12")
    with pytest.raises(PbprofPasswordError):
        svc.import_from_file(out, password="WrongPassword!12")


def test_import_tampered_payload_raises(svc, tmp_path):
    out = tmp_path / "e.pbprof"
    svc.export_to_file(out, payload={"k": "v"}, password="GoodPassword!12")

    raw = out.read_bytes()
    with zipfile.ZipFile(io.BytesIO(raw), "r") as zin:
        manifest = zin.read("manifest.json")
        encrypted = bytearray(zin.read("payload.enc"))
        sig = zin.read("signature.bin")
    encrypted[0] ^= 0xFF
    new_buf = io.BytesIO()
    with zipfile.ZipFile(new_buf, "w") as zout:
        zout.writestr("manifest.json", manifest)
        zout.writestr("payload.enc", bytes(encrypted))
        zout.writestr("signature.bin", sig)
    out.write_bytes(new_buf.getvalue())

    with pytest.raises(PbprofIntegrityError):
        svc.import_from_file(out, password="GoodPassword!12")


def test_manifest_is_readable_plaintext(svc, tmp_path):
    out = tmp_path / "e.pbprof"
    svc.export_to_file(
        out,
        payload={"k": "v"},
        password="GoodPassword!12",
        profile_name="Acc01",
        profile_id="pid-1",
    )
    with zipfile.ZipFile(out, "r") as z:
        m = json.loads(z.read("manifest.json"))
    assert m["format"] == "pbprof"
    assert m["format_version"] == 1
    assert m["profile_id"] == "pid-1"
    assert m["profile_name"] == "Acc01"
    assert m["encryption"]["cipher"] == "aes-256-gcm"
    assert m["encryption"]["kdf"] == "argon2id"
