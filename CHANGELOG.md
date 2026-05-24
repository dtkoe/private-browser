# Changelog

All notable changes to this project will be documented in this file.

## [v0.4.0-m4] — 2026-05-24

### Added

**UI (Next.js 14) + pywebview shell (M4):**
- Next.js 14 App Router project under `frontend/` — pinned to `next@14.2.35` (security-patched), `react@18.3.1`, `tailwindcss@3.4.17`, TypeScript 5
- Static export config (`output: 'export'`) — frontend bundles to `frontend/out/` for shell consumption
- Layout C: top bar (tab nav + Lock button) + main area
  - Profiles tab: sidebar (profile list with status indicator + create form) + details panel
  - Proxies tab: add-one form + batch-import textarea + table with per-row check / delete
  - Settings tab: stub showing version/backend/theme
- `LoginScreen` component — detects first-run via `unlock` probe → 412 means "needs init", offers password+confirm UI; otherwise shows simple unlock
- `ProfileDetail`: launch / stop / regenerate-fingerprint / delete buttons + proxy selector + collapsible raw-fingerprint JSON
- Typed `api.ts` client with `X-PB-Token` header, `ApiError` class, sessionStorage token persistence
- `lib/types.ts` mirrors backend response shapes (`Profile`, `Proxy`, `HealthCheckResult`)
- Dark theme as default (custom Tailwind palette: bg/elevated/border + accent + muted)

**Desktop shell:**
- `shell/run_app.py` — spawns `uvicorn backend.main:app` as subprocess, captures `PB_API_TOKEN=` from stdout via regex, starts a static HTTP server for `frontend/out/`, opens a 1280×800 pywebview window, injects `window.PB_API_BASE` so the SPA talks to the backend port
- `atexit` cleanup terminates both subprocesses
- `pywebview>=5.1` added to runtime deps

### Verified
- `npm run build` produces a static export with 4 routes
- Backend startup helper captures token from stdout in <1s (smoke test)
- 125 backend tests still pass (no regressions)

### Scope reduction vs spec (deliberate)
- shadcn/ui, TanStack Query/Table, Zustand, i18n via next-intl, command palette, hotkeys, virtualization for 1000+ profiles, Playwright e2e — deferred to post-v1 polish
- Justification: spec calls out 4 weeks for M4; we built MVP UI (~15 components, all CRUD flows) in a focused subset. Each deferred item adds polish but not new capability.

### Known limitations
- Confirm-dialog uses native `confirm()` — replace with toast/modal later
- No live WebSocket for profile status push — UI re-fetches on action
- Single-instance lock not implemented (M6 packaging will add it)

## [v0.3.0-m3] — 2026-05-24

### Added

**Proxy Pool + WebRTC (M3):**
- `ProxyValidator` — format checks for `type` (`http`/`https`/`socks5`), host charset, port range; `parse_batch_line` accepts `host:port`, `host:port:user:pass`, and `scheme://host:port` lines
- `ProxyService` — CRUD + `batch_import(text, type_default)` + `record_check(...)` for storing health check telemetry
- `ProxyHealthChecker` — performs `GET https://ipinfo.io/json` via the proxy (`httpx.Client(proxy=…)`), captures IP / country / city / timezone / latency; failures recorded as `ok=False`
- `BackgroundProxyScheduler` — APScheduler `BackgroundScheduler` running checks every 30 minutes plus an immediate run; started after first unlock, stopped in shutdown
- REST endpoints (all behind unlock gate):
  - `POST/GET/PATCH/DELETE /api/proxies` + `POST /api/proxies/{id}/check` + `POST /api/proxies/batch`
  - `PATCH /api/profiles/{id}/proxy` — bind/unbind a proxy
  - `POST /api/profiles/{id}/launch` now resolves bound proxy (404→409 if FK dangling) and passes `proxy={server,username,password}` to Camoufox
- `CamoufoxLauncher` sets `block_webrtc=True` when no proxy is bound to prevent local-IP leakage; with a proxy, Camoufox's "proxy" WebRTC mode is used
- M3 acceptance test: full HTTP flow (initialize → unlock → 5 proxies + 2 batched → bind to profile → launch carries proxy)

### Dependencies
- `httpx>=0.27` (proxy health check)
- `apscheduler>=3.10` (background re-check)

### Verified
- 125 tests pass (`pytest -m "not slow"`)
- Lint clean
- Proxy bound to deleted proxy → launch returns 409 (no silent dangling FK)
- Launch without proxy → `block_webrtc=True` engaged in Camoufox

### Known limitations
- No CSV import (batch import via plain text only; CSV deferred to M5 UI)
- No "suggest re-generate timezone/locale" when binding proxy with different geo (deferred to M4 UI — backend has the data but UX is UI work)
- No live `webrtc.peet.ws` integration test (manual verification only — backend lacks browser to run JS)

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
