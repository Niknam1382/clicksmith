# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build spec for Clicksmith.

Build locally on Windows with:
    pyinstaller packaging/pyinstaller/clicksmith.spec --noconfirm

The CI release workflow (.github/workflows/release.yml) runs the exact same command on a
windows-latest runner, so a local build and a release build always produce the same layout.
"""

import sys
from pathlib import Path

block_cipher = None

# This file lives at <repo>/packaging/pyinstaller/clicksmith.spec
ROOT = Path(SPECPATH).resolve().parents[1]
SRC = ROOT / "src"
ASSETS = SRC / "clicksmith" / "assets"

sys.path.insert(0, str(SRC))
from clicksmith import APP_NAME, __version__  # noqa: E402

a = Analysis(
    [str(SRC / "clicksmith" / "__main__.py")],
    pathex=[str(SRC)],
    binaries=[],
    datas=[
        (str(ASSETS / "icon.png"), "clicksmith/assets"),
        (str(ASSETS / "icon.ico"), "clicksmith/assets"),
    ],
    hiddenimports=[
        # pynput picks its backend by platform at import time, which PyInstaller's static
        # analysis cannot see through, so the Windows backend module is listed explicitly.
        "pynput.keyboard._win32",
        "pynput.mouse._win32",
    ],
    hookspath=[],
    excludes=[
        # Qt modules Clicksmith's QtWidgets-only UI never imports; excluding them keeps the
        # bundle a few hundred MB smaller and avoids pulling in an unneeded WebEngine runtime.
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtNetwork",
        "PySide6.QtMultimedia",
        "PySide6.QtPdf",
        "PySide6.Qt3DCore",
        "tkinter",
        "test",
        "unittest",
    ],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Clicksmith",
    version=str(ROOT / "packaging" / "pyinstaller" / "version_info.txt"),
    icon=str(ASSETS / "icon.ico"),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX-packed exes are flagged by some antivirus heuristics; not worth the size win
    console=False,  # windowed app; `clicksmith run ...` re-attaches to the parent console itself
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
