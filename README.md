# Private Browser

Open-source anti-detect browser manager for Windows, built on [Camoufox](https://github.com/daijro/camoufox) (Firefox-based anti-detect engine).

Multiple isolated browser profiles, each with its own fingerprint, proxy, cookies, and extensions. Encrypted local storage. No telemetry.

## Features

- **Fingerprint isolation per profile** — UA, screen, WebGL, fonts, timezone, canvas/audio noise, hardware concurrency
- **Proxy pool** — HTTP / HTTPS / SOCKS5 with health checks and per-profile binding
- **WebRTC leak prevention** — proxy mode when a proxy is bound; full block when not
- **Encrypted at rest** — SQLCipher (Argon2id KDF) + master password
- **Extensions** — per-profile Firefox addon install/remove
- **`.pbprof` export/import** — encrypted (AES-256-GCM + HMAC) profile bundles
- **Profile cloning + bulk operations**
- **Native desktop shell** — pywebview window over a local Next.js UI

## Quick start (end-user)

1. Download `private-browser-setup.exe` (or `private-browser-portable.zip`) from [Releases](https://github.com/dtkoe/private-browser/releases)
2. Run it (no admin needed)
3. Launch from Start Menu — set a master password on first run
4. Click **+ New** to create a profile, then **▶ Launch**

On first launch Camoufox (~150 MB Firefox-based browser) downloads automatically.

## Build from source

```bash
git clone https://github.com/dtkoe/private-browser
cd private-browser
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
python -m playwright install firefox
python -m camoufox fetch

cd frontend && npm install && npm run build && cd ..
python shell/run_app.py
```

To build the standalone `.exe`:
```bash
python build/build_app.py
# outputs dist/private-browser/ + dist/private-browser-portable.zip
```

To build the NSIS installer (requires NSIS 3.x on PATH):
```bash
cd installer && makensis private-browser.nsi
```

## Documentation

- [User Guide](docs/USER_GUIDE.md) — UI walkthrough
- [Troubleshooting](docs/TROUBLESHOOTING.md) — known issues
- [Contributing](CONTRIBUTING.md) — dev setup, branching, commits
- [Architecture spec](docs/superpowers/specs/2026-05-24-private-browser/) — design docs
- [Dev machine setup](docs/dev-machine-setup.md)
- [Changelog](CHANGELOG.md)

## License

MIT — see [LICENSE](LICENSE).

## Acknowledgements

- [@daijro](https://github.com/daijro) and the [Camoufox](https://github.com/daijro/camoufox) community for the anti-detect engine
- The [CloverLabsAI](https://github.com/CloverLabsAI/camoufox) community fork
- [polyackiy/camoufox-profile-manager](https://github.com/polyackiy/camoufox-profile-manager) — referenced during initial design
