# ruff: noqa: F821

import os
import sys
from pathlib import Path

# Increase recursion limit for complex projects
sys.setrecursionlimit(5000)

PROJECT_ROOT = Path(SPECPATH).parents[1]


def project_path(*parts):
    return str(PROJECT_ROOT.joinpath(*parts))


def macos_extra_binaries():
    if sys.platform != "darwin":
        return []

    candidates = [
        Path(sys.prefix) / "lib" / "libncurses.6.dylib",
        Path(sys.base_prefix) / "lib" / "libncurses.6.dylib",
    ]
    for candidate in candidates:
        if candidate.exists():
            return [(str(candidate), ".")]
    return []


a = Analysis(
    [project_path("src", "automataii", "__main__.py")],
    pathex=[project_path("src")],
    binaries=macos_extra_binaries(),
    datas=[
        (project_path("models", "onnx"), "models/onnx"),
        (
            project_path("src", "automataii", "presentation", "qt", "fonts"),
            "automataii/presentation/qt/fonts",
        ),
        (project_path("src", "automataii", "modules"), "automataii/modules"),
        # Only include root-level images from examples directory
        (project_path("src", "examples", "*.png"), "examples"),
        (project_path("resources"), "resources"),  # Includes resources/data/*.json
    ],
    hiddenimports=[
        "PyQt6.sip",
        "PyQt6.QtGui",
        "PyQt6.QtCore",
        "PyQt6.QtWidgets",
        "sklearn.utils._cython_blas",
        "scipy.special._cdflib",
        "onnxruntime.capi.onnxruntime_pybind11_state",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AutomataII",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Set to False for GUI applications
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=os.environ.get("PYINSTALLER_TARGET_ARCH") or None,
    codesign_identity=None,
    entitlements_file=None,
    icon=project_path("resources", "icons", "AppIcon.icns"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="AutomataII",
)

app = BUNDLE(
    coll,
    name="AutomataII.app",
    icon=project_path("resources", "icons", "AppIcon.icns"),
    bundle_identifier="dev.automataii.automataii",
    info_plist={
        "NSPrincipalClass": "NSApplication",
        "NSAppleScriptEnabled": False,
        "NSRequiresAquaSystemAppearance": "YES",  # Forces light mode for the app
        "CFBundlePackageType": "APPL",
    },
)
