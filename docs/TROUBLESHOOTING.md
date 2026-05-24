# Troubleshooting

## "Camoufox fetch failed"
- Windows Defender may quarantine the binary on first download. Add `%LOCALAPPDATA%\camoufox` to exclusions and retry.
- Behind a corporate proxy? Set `HTTPS_PROXY=http://...` before running `python -m camoufox fetch`.

## App doesn't start — port 8769 already in use
- Another instance is running. The single-instance mutex should prevent this; if it leaks, kill `private-browser.exe` in Task Manager.

## "invalid password" but I know it's right
- The salt sidecar (`app.salt` next to `app.db` in `%APPDATA%\private-browser\`) is required. If you copied `app.db` but not `app.salt`, unlock will always fail.

## Lost master password
- There is no recovery. Delete `%APPDATA%\private-browser\` to start fresh (all profiles lost).
- Plan ahead: export important profiles as `.pbprof` files — those can be re-encrypted with a different password later.

## Profile won't launch with proxy
- The bound proxy might have been deleted — launch returns 409. Either rebind or remove the proxy from the profile.
- The proxy itself might be dead — open Proxies tab and click **Check**.

## Extension installed but Firefox doesn't load it
- Camoufox / Firefox needs a restart for a new extension to take effect (stop the profile, then re-launch).
- Make sure the `.xpi` is signed — unsigned XPIs are blocked by default Firefox unless dev mode is on.

## Logs
- `%APPDATA%\private-browser\logs\app.log` — structured backend log
- Console where the app was launched — shell + backend stdout

## "DB header looks like plaintext SQLite — encryption is NOT engaged"
- This means SQLCipher failed to initialize. Reinstall:
  ```
  pip install --force-reinstall sqlcipher3-wheels
  ```

## Tampered `.pbprof` import returns 422
- The file's signature doesn't match its ciphertext — either the file is corrupted in transit or someone has modified it. Re-download or re-export from the original source.
