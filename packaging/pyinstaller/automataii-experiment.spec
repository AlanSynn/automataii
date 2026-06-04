# ruff: noqa: F821,E402

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(SPECPATH).parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.pyinstaller_datas import existing_datas

# Increase recursion limit for complex projects
sys.setrecursionlimit(5000)


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


# Create entry script for experiment mode
entry_script = """
import sys
sys.argv.append('--experiment')
from automataii.__main__ import main
if __name__ == "__main__":
    main()
"""

with open("automataii_experiment_entry.py", "w") as f:
    f.write(entry_script)

a = Analysis(
    [project_path("automataii_experiment_entry.py")],
    pathex=[project_path("src")],
    binaries=macos_extra_binaries(),
    datas=[
        (project_path("models", "onnx"), "models/onnx"),
        (
            project_path("src", "automataii", "presentation", "qt", "fonts"),
            "automataii/presentation/qt/fonts",
        ),
        (project_path("resources"), "resources/"),  # Includes resources/data/*.json
        *existing_datas(
            [
                (project_path("config"), "config"),
                (project_path("src", "automataii", "modules"), "automataii/modules"),
                # Only include root-level images from examples directory
                (project_path("src", "examples", "*.png"), "examples/"),
            ]
        ),
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
    name="AutomataII-Experiment",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=os.environ.get("PYINSTALLER_TARGET_ARCH") or None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="AutomataII-Experiment",
)

# macOS app bundle configuration
app = BUNDLE(
    coll,
    name="AutomataII-Experiment.app",
    icon=project_path("resources", "icons", "AppIcon.icns"),
    bundle_identifier="dev.automataii.automataii.experiment",
    info_plist={
        "NSPrincipalClass": "NSApplication",
        "NSAppleScriptEnabled": False,
        "CFBundleDocumentTypes": [],
        "NSHighResolutionCapable": "True",
        "LSMinimumSystemVersion": "10.13.0",
        "NSHumanReadableCopyright": "Copyright © 2024 Automataii Contributors. All rights reserved.",
        "CFBundleShortVersionString": "1.0.0",
        "CFBundleVersion": "1.0.0",
        "CFBundleDisplayName": "AutomataII Experiment",
        "LSApplicationCategoryType": "public.app-category.graphics-design",
        # Experiment-specific identifier
        "CFBundleIdentifier": "dev.automataii.automataii.experiment",
    },
)
