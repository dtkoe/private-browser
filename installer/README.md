# Building the Windows installer

## Prerequisites
- [NSIS 3.x](https://nsis.sourceforge.io/Download) installed (`makensis` on PATH)
- PyInstaller build already done: `python build/build_app.py`

## Build
```
cd installer
makensis private-browser.nsi
```
Outputs `installer/private-browser-setup.exe`.

## Distribution
- Installer: `installer/private-browser-setup.exe` (no admin required, installs to `%LOCALAPPDATA%`)
- Portable: `dist/private-browser-portable.zip` (unzip anywhere, run `private-browser.exe`)
