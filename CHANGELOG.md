# Changelog

All notable changes to this project will be documented in this file.

## [v0.2.0-m2] — 2026-05-24

### Added

**FingerprintGenerator + Profile API (M2):**
- `FingerprintGenerator` — thin wrapper around Camoufox/Browserforge; produces a flat Camoufox-config dict augmented with `_meta` (schema_version, generator_version, generated_at), `_os`, `_geo`, and per-profile `_seeds` (canvas / audio / webgl_noise as 64-bit ints)
- `FingerprintValidator` — enforces OS↔UA, OS↔platform, screen sanity, seeds presence
- Statistical datasets (`backend/core/datasets.py`): OS distribution (Win 72% / Mac 18% / Linux 10%), hardware concurrency distribution, device-memory-by-concurrency mapping, `weighted_choice`
- `Profile`, `Proxy` (stub for M3), `Session` SQLAlchemy models
- Alembic migration `0002_profile_proxy_session` — full schema with indices and FKs (CASCADE / SET NULL)
- `AppState` — thread-safe holder for unlocked engine + sessionmaker; locks/unlocks atomically
- FastAPI deps: `get_app_state`, `require_unlocked` (423 when locked), `get_db_session`
- `ProfileService` — `create`, `list_profiles`, `get`, `update`, `regenerate_fingerprint`, `update_status`, `delete` (also removes `user_data_dir` on delete)
- `LaunchManager` + `Launcher` protocol — thread-safe per-profile registry, prevents double-launch
- `CamoufoxLauncher` — real implementation; spawns Camoufox in a background thread via the SDK's sync API, joins on stop
- REST endpoints (all behind unlock gate):
  - `POST /api/profiles`, `GET /api/profiles`, `GET /api/profiles/{id}`, `PATCH /api/profiles/{id}`, `DELETE /api/profiles/{id}`
  - `POST /api/profiles/{id}/regenerate`
  - `POST /api/profiles/{id}/launch`, `POST /api/profiles/{id}/stop`
  - `POST /api/fingerprint/validate`
  - `POST /api/auth/lock`
- M2 acceptance test: full HTTP flow (initialize → unlock → 10 profiles → validate each → list) — confirms 10 distinct fingerprints
- Opt-in `slow` pytest marker for real-Camoufox smoke test

### Verified

- 92 tests pass (`pytest -m "not slow"`)
- 10 profiles created via API have 10 distinct `_seeds` tuples (acceptance test)
- All generated fingerprints pass `FingerprintValidator` (consistency)
- Profile endpoints return 423 Locked before `POST /api/auth/unlock`, work after
- `ruff check .` — 0 errors
- Lifespan cleanup: on app shutdown, all running Camoufox handles are stopped and AppState is locked

### Architectural notes

- Routers are built with `svc_factory` closures so `ProfileService` is constructed per-request from the unlocked `AppState` — no global mutable singleton, but no `Depends` plumbing through 10 layers either
- `_seeds` are sourced from `secrets.randbits(64)`, not `random` — uniqueness guaranteed cryptographically
- `CamoufoxLauncher` strips `_`-prefixed keys before passing config to Camoufox (those are our metadata, not Camoufox fields)
- B008 (Ruff "no Depends in defaults") is intentionally disabled — it's idiomatic FastAPI

### Known limitations

- Launching profile uses no proxy yet (proxy_id field exists in DB; wiring happens in M3)
- WebSocket for `profile_status_changed` push not implemented yet (M4)
- Bulk operations (multi-select launch, multi-delete) deferred to M5

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
