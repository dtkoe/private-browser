# Contributing

## Dev setup

```
git clone https://github.com/dtkoe/private-browser
cd private-browser
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
python -m playwright install firefox
python -m camoufox fetch
cd frontend && npm install && npm run build && cd ..
```

Run:
- Backend only: `uvicorn backend.main:app --reload --port 8769`
- Full app (with shell): `python shell/run_app.py`
- Tests: `pytest -q -m "not slow"`
- Lint: `ruff check .`
- Frontend dev: `cd frontend && npm run dev`

## Code style
- Python: PEP-8 enforced by Ruff (line-length 100, `E/F/I/W/B/UP/ASYNC` selected, `B008` ignored).
- TypeScript: Next.js defaults; small focused components.

## Commits
- Conventional commits: `feat(scope):`, `fix(scope):`, `docs:`, `chore:`, `test:`, `refactor:`.
- Reference the milestone for in-scope work: `feat(M3): …`.
- Co-author trailers and AI-generated footers are NOT added.

## Branching
- `main` is the development line.
- Tag releases as `vX.Y.Z-mN` (e.g., `v0.5.0-m5`).

## Tests
- New backend services need TDD: failing unit test first, then implementation.
- API endpoints need integration tests using FastAPI's TestClient.
- Acceptance tests live under `tests/integration/test_mN_acceptance.py` and cover the milestone's user-facing flow end-to-end.
- Real-Camoufox tests are marked `slow` and excluded from the default run.

## Adding a milestone
- Write the plan in `docs/superpowers/plans/YYYY-MM-DD-plan-N-mN-name.md`.
- Execute task-by-task, committing after each.
- Update `CHANGELOG.md` with the milestone entry.
- Tag `vX.Y.Z-mN`.

## Releasing (manual)
1. `python build/build_app.py` — produces `dist/private-browser-portable.zip`
2. `cd installer && makensis private-browser.nsi` — produces `installer/private-browser-setup.exe`
3. `gh release create vX.Y.Z-mN dist/private-browser-portable.zip installer/private-browser-setup.exe --notes-file CHANGELOG.md`
