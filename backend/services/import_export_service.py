"""Encrypted .pbprof export/import. zip(manifest.json + payload.enc + signature.bin)."""
from __future__ import annotations

import base64
import hmac
import io
import json
import secrets
import time
import zipfile
from hashlib import sha256
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from backend.core.security import KDFParams, check_verifier, derive_key, make_verifier

FORMAT = "pbprof"
FORMAT_VERSION = 1
CREATOR_VERSION = "0.5.0"


class PbprofPasswordError(Exception):
    pass


class PbprofIntegrityError(Exception):
    pass


class PbprofFormatError(Exception):
    pass


class ImportExportService:
    def export_to_file(
        self,
        path: Path,
        *,
        payload: dict[str, Any],
        password: str,
        profile_id: str = "",
        profile_name: str = "",
        include_browser_data: bool = True,
        include_extensions: bool = False,
    ) -> None:
        params = KDFParams.default()
        salt = secrets.token_bytes(16)
        key = derive_key(password, salt, params)

        plaintext = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        nonce = secrets.token_bytes(12)
        ciphertext = AESGCM(key).encrypt(nonce, plaintext, None)
        signature = hmac.new(key, ciphertext, sha256).digest()

        manifest = {
            "format": FORMAT,
            "format_version": FORMAT_VERSION,
            "created_at": int(time.time() * 1000),
            "creator_version": CREATOR_VERSION,
            "profile_id": profile_id,
            "profile_name": profile_name,
            "encryption": {
                "kdf": "argon2id",
                "kdf_salt": base64.b64encode(salt).decode("ascii"),
                "kdf_params": params.to_dict(),
                "cipher": "aes-256-gcm",
                "nonce": base64.b64encode(nonce).decode("ascii"),
                "verifier": base64.b64encode(make_verifier(key)).decode("ascii"),
            },
            "include_browser_data": include_browser_data,
            "include_extensions": include_extensions,
            "size_bytes_encrypted": len(ciphertext),
        }

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("manifest.json", json.dumps(manifest, indent=2))
            z.writestr("payload.enc", ciphertext)
            z.writestr("signature.bin", signature)
        path.write_bytes(buf.getvalue())

    def import_from_file(self, path: Path, *, password: str) -> dict[str, Any]:
        if not path.is_file():
            raise PbprofFormatError(f"file not found: {path}")
        raw = path.read_bytes()
        try:
            with zipfile.ZipFile(io.BytesIO(raw), "r") as z:
                manifest = json.loads(z.read("manifest.json"))
                ciphertext = z.read("payload.enc")
                signature = z.read("signature.bin")
        except (zipfile.BadZipFile, KeyError, json.JSONDecodeError) as exc:
            raise PbprofFormatError(str(exc)) from exc

        if manifest.get("format") != FORMAT:
            raise PbprofFormatError(f"unknown format: {manifest.get('format')!r}")

        enc = manifest["encryption"]
        salt = base64.b64decode(enc["kdf_salt"])
        nonce = base64.b64decode(enc["nonce"])
        params = KDFParams.from_dict(enc["kdf_params"])
        key = derive_key(password, salt, params)

        # Step 1: verifier separates "wrong password" from "tampered file"
        verifier = enc.get("verifier")
        if verifier:
            expected = base64.b64decode(verifier)
            if not check_verifier(key, expected):
                raise PbprofPasswordError("wrong password")

        # Step 2: HMAC signature catches manifest/signature tampering
        candidate_sig = hmac.new(key, ciphertext, sha256).digest()
        if not hmac.compare_digest(candidate_sig, signature):
            raise PbprofIntegrityError("signature mismatch (tampering detected)")

        # Step 3: AESGCM decryption — should always succeed once verifier+sig pass
        try:
            plaintext = AESGCM(key).decrypt(nonce, ciphertext, None)
        except Exception as exc:
            raise PbprofIntegrityError(f"AES-GCM auth failed: {exc}") from exc

        return json.loads(plaintext.decode("utf-8"))
