# private-browser — agent working rules

Apply on every change, no exceptions:

1. **Test every function you touch.** Unit test for the logic; integration test for any endpoint; manual/visual check for UI. Never claim "done" without green tests.
2. **Spot missing functionality as you go.** While editing X, ask "what's missing for X to actually be useful end-to-end?" Note gaps in `memory/` (use the auto-memory system) and start implementing them in the same loop.
3. **Verify visually for UI.** Use Playwright to drive the running app, take screenshots, and confirm the change works in the browser/pywebview window. Type-checks and unit tests are not enough.
4. **Stream results.** Show the user a screenshot or short diff at meaningful checkpoints — but never block on approval; keep building.
5. **Keep momentum.** After each commit/checkpoint, immediately pick up the next task (next test, next missing feature, next polish item). No idle pauses.

Stack reminders:
- Backend: Python 3.11+, FastAPI sync, SQLAlchemy 2 sync, SQLCipher via `sqlcipher3-wheels`, Alembic, structlog. Run tests: `.venv/Scripts/python.exe -m pytest -q -m "not slow"`. Lint: `ruff check .`.
- Frontend: Next.js 14 static export under `frontend/`. Build: `npm run build`. Source files in `frontend/{app,components,lib}`.
- Shell: `python shell/run_app.py` — pywebview window over backend (8769) + static frontend (8770).
- Tests live under `tests/{unit,integration}` and `tests/integration/test_mN_acceptance.py` per milestone.

Commit style: conventional (`feat(scope):`, `fix(scope):`, `docs:`, `test:`). No `Co-Authored-By` / AI footers. Reference milestone (`feat(M3): …`) for in-scope work.
