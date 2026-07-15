# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for macOS Drive Local Open.app"""

from pathlib import Path

ROOT = Path(SPECPATH).resolve().parents[1]
SRC = ROOT / "src"

a = Analysis(
    [str(SRC / "drive_local_open" / "__main__.py")],
    pathex=[str(SRC)],
    binaries=[],
    datas=[],
    hiddenimports=["drive_local_open"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Drive Local Open",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Drive Local Open",
)

app = BUNDLE(
    coll,
    name="Drive Local Open.app",
    icon=None,
    bundle_identifier="com.is3.DriveLocalOpen",
    info_plist={
        "CFBundleName": "Drive Local Open",
        "CFBundleDisplayName": "Drive Local Open",
        "CFBundleShortVersionString": "0.2.0",
        "CFBundleVersion": "0.2.0",
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "12.0",
        "NSAppleEventsUsageDescription": (
            "Google Chrome の現在のタブ URL を読み取り、同期済みローカルフォルダを開くために使用します。"
        ),
        "CFBundleURLTypes": [
            {
                "CFBundleURLName": "Drive Local Open",
                "CFBundleTypeRole": "Viewer",
                "CFBundleURLSchemes": ["drive-local-open"],
            }
        ],
    },
)
