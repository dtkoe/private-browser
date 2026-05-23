# Dev Machine Setup

Verified on Windows 11, 2026-05-24.

## Prerequisites

- Python 3.11+ (3.12 verified)
- Node 20+ (Node 24 verified)
- Git 2.40+
- gh CLI 2.80+ (for releases/CI later)

## First-time setup

```bash
git clone https://github.com/dtkoe/private-browser
cd private-browser
python -m venv .venv
source .venv/Scripts/activate   # PowerShell: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m playwright install firefox
python -m camoufox fetch
```

## Smoke test

```bash
python scripts/smoke_camoufox.py
```

Should open a Camoufox window and print spoofed navigator values.

## Backend dev

```bash
uvicorn backend.main:app --reload --port 8769
```

## Frontend dev

```bash
cd frontend
npm install
npm run dev
```

## Known issues

- Windows Defender may quarantine Camoufox binary on first download → add %LOCALAPPDATA%\camoufox to exclusions
- If `pysqlcipher3` install fails on Windows, try a prebuilt wheel: `pip install pysqlcipher3-binary` (Task 4 will revisit if needed)
