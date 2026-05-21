# -*- mode: python ; coding: utf-8 -*-

import platform
from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.hooks import collect_submodules

# -------------------------------------------------
# PLATFORM DETECTION
# -------------------------------------------------

IS_WINDOWS = platform.system() == "Windows"
IS_MAC = platform.system() == "Darwin"

# -------------------------------------------------
# ICON HANDLING
# -------------------------------------------------

if IS_WINDOWS:
    app_icon = "assets/hireflow_icon.ico"
else:
    app_icon = "assets/hireflow_icon.icns"

# -------------------------------------------------
# DATA FILES
# -------------------------------------------------

datas = [
    ("templates", "templates"),
    ("assets", "assets"),
    ("samples", "samples"),
]

datas += collect_data_files("certifi")

# -------------------------------------------------
# HIDDEN IMPORTS
# -------------------------------------------------

hiddenimports = []
hiddenimports += collect_submodules("keyring")

# -------------------------------------------------
# ANALYSIS
# -------------------------------------------------

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

# -------------------------------------------------
# PYZ
# -------------------------------------------------

pyz = PYZ(a.pure)

# -------------------------------------------------
# WINDOWS / MAIN EXECUTABLE
# -------------------------------------------------

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="HireFlow",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=app_icon,
)

# -------------------------------------------------
# COLLECT
# -------------------------------------------------

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="HireFlow",
)

# -------------------------------------------------
# macOS APP BUNDLE
# -------------------------------------------------

if IS_MAC:
    app = BUNDLE(
        coll,
        name="HireFlow.app",
        icon=app_icon,
        bundle_identifier="com.hireflow.app",
    )