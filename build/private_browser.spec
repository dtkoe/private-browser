# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for private-browser desktop bundle."""
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None
ROOT = Path(SPECPATH).parent

hidden = [
    "sqlcipher3",
    "sqlcipher3.dbapi2",
    "sqlalchemy.dialects.sqlite",
    "uvicorn.logging",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.http.httptools_impl",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.lifespan.on",
    "structlog",
    "alembic",
    "alembic.runtime.migration",
    "argon2.low_level",
    "cryptography.hazmat.primitives.ciphers.aead",
    "apscheduler",
    "apscheduler.schedulers.background",
    "apscheduler.executors.pool",
    "apscheduler.triggers.interval",
    "webview",
    "webview.platforms.winforms",
    "python_multipart",
]

datas = [
    (str(ROOT / "frontend" / "out"), "frontend/out"),
    (str(ROOT / "alembic"), "alembic"),
    (str(ROOT / "alembic.ini"), "."),
]
# Third-party data files PyInstaller misses by default
datas += collect_data_files("apify_fingerprint_datapoints")
datas += collect_data_files("browserforge")
datas += collect_data_files("camoufox")
datas += collect_data_files("language_tags")
hidden += collect_submodules("browserforge")
hidden += collect_submodules("camoufox")

a = Analysis(
    [str(ROOT / "shell" / "run_app.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "pytest"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="private-browser",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="private-browser",
)
