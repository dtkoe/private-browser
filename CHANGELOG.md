# Changelog

All notable changes to this project will be documented in this file.

## [v0.1.0-m1] — 2026-05-24

### Added

**Foundation (M0 + M1):**
- Project scaffold: `backend/`, `frontend/`, `tests/`, `alembic/`, `.github/workflows/`
- Python 3.11+ project metadata via `pyproject.toml`
- Camoufox SDK integration (smoke test verifies `navigator.userAgent` spoofing engaged)
- SQLCipher 4 encrypted SQLite via `sqlcipher3-wheels` (no compilation on Windows)
- Argon2id KDF for master password (OWASP-recommended parameters: 64 MiB memory, 3 iterations, parallelism 4)
- HMAC-SHA256 verifier for double-checking unlock
- Salt sidecar pattern (`app.salt` next to `app.db`) — salt is not secret, avoids chicken-and-egg
- Random per-startup API token with `X-PB-Token` header middleware
- `/api/auth/initialize` and `/api/auth/unlock` endpoints
- FastAPI lifespan prints `PB_API_TOKEN=...` to stdout for launcher capture
- Alembic-managed schema with `app_settings` and `audit_log` tables
- SecurityService glues KDF + DB + migrations together
- AuditService records actions to `audit_log` table
- Structured logging via `structlog` — JSON to rotating file (`logs/app.log`), pretty on console
- GitHub Actions CI on `windows-latest` — ruff lint + pytest (29 tests)
- Acceptance test simulates "fresh install → init → restart → unlock" end-to-end

### Verified

- 29 tests pass locally and in CI
- `app.db` on disk is genuinely encrypted (header bytes are random, not "SQLite format 3")
- Restart of the app generates a NEW API token; old tokens are rejected
- Wrong password is rejected with 401; correct password returns 200
- Master password is never written to disk — only Argon2id-derived key briefly held in memory

### Architectural notes

- Backend uses SYNC SQLAlchemy (FastAPI handles sync endpoints via threadpool). `sqlcipher3-wheels` has no async dialect; sync engine is the right call.
- Camoufox SDK is a runtime dependency, downloaded via `python -m camoufox fetch` (~530 MB binary, NOT shipped in the repo).
- Frontend package.json is currently a stub; UI work is M4.

### Known limitations

- No UI yet (planned M4)
- No profile management endpoints yet (planned M2)
- No proxy management yet (planned M3)
- Recovery code / BIP39 not implemented yet (planned M5)
