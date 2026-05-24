# User Guide

## First run

1. Launch Private Browser. A "Create a master password" screen appears.
2. Enter a password (≥12 characters). **There is no recovery** — lose it and your data is gone.
3. The app downloads Camoufox (~150 MB, one-time). Watch the console log for progress.

## Creating a profile

- Click **+ New** in the left sidebar.
- Optionally pick an OS to target (Windows / macOS / Linux). Otherwise a weighted-random OS is chosen.
- Click **Create**. The profile appears in the sidebar with a generated fingerprint.

## Launching

- Select a profile in the sidebar.
- Click **▶ Launch**. A real Camoufox window opens with the configured fingerprint.
- Use it like any browser. Cookies/history are saved to the profile's data dir.
- Click **Stop** in the UI (or close the browser window) to end the session.

## Proxies

- Open the **Proxies** tab.
- Add one via the form, or paste many lines (`host:port` or `host:port:user:pass`) into "Batch import".
- Click **Check** to verify a proxy via ipinfo.io — sees the exit IP and geo.
- The background scheduler re-checks every 30 minutes after unlock.

## Binding a proxy

- In a profile's detail panel, pick a proxy from the dropdown. The profile launches with it.
- "No proxy" mode forces WebRTC off entirely (prevents IP leakage).

## Export / Import

- **Export**: profile detail panel → **Export** → set a password (≥12). A `.pbprof` file downloads.
- **Import**: top bar → **Import** → pick `.pbprof` → enter password. A new profile is created with the same fingerprint and (if included) cookies.
- Wrong password → 401. Tampered file → 422.

## Extensions

- In a profile's detail panel, scroll to the Extensions block.
- **+ Install .xpi**: upload a Firefox addon file.
- Extensions are per-profile — installed in A is absent in B.

## Locking

- Top-right **Lock** button forgets the unlocked DB engine in memory. To return you must re-enter the master password.

## Bulk operations (API)

The backend supports `POST /api/profiles/bulk/delete` with `{"ids": [...]}` to delete many profiles at once. UI multi-select is on the post-v1 roadmap.

## Where my data lives

```
%APPDATA%\private-browser\
├── app.db                 # SQLCipher-encrypted catalog
├── app.salt               # KDF salt (not secret)
├── profiles\<uuid>\       # one folder per profile (cookies, history, extensions)
├── camoufox\              # the Camoufox browser bundle (~150 MB)
├── logs\app.log           # structured backend log
└── temp\                  # .pbprof staging area
```
