# ruff: noqa: F821,E402

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(SPECPATH).parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules
from scripts.pyinstaller_datas import existing_datas

from automataii.utils.update_config import (
    AUTOMATIC_CHECKS_ENV,
    configured_appcast_url,
    env_flag_optional,
    sparkle_public_ed_key,
)

# Increase recursion limit for complex projects
sys.setrecursionlimit(5000)


def project_path(*parts):
    return str(PROJECT_ROOT.joinpath(*parts))


def project_version():
    pyproject = PROJECT_ROOT / "pyproject.toml"
    try:
        import tomllib

        with pyproject.open("rb") as handle:
            version = tomllib.load(handle).get("project", {}).get("version")
        if isinstance(version, str) and version:
            return version
    except Exception:
        pass

    try:
        text = pyproject.read_text(encoding="utf-8")
    except OSError:
        return "0.1.0"
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("version"):
            return stripped.split("=", 1)[1].strip().strip('"').strip("'") or "0.1.0"
    return "0.1.0"


def _bundle_version(value):
    return str(value).strip().removeprefix("v") or "0.1.0"


def motionsmith_short_version():
    return _bundle_version(os.environ.get("MOTIONSMITH_VERSION") or project_version())


def motionsmith_bundle_version():
    return _bundle_version(
        os.environ.get("MOTIONSMITH_BUNDLE_VERSION")
        or os.environ.get("MOTIONSMITH_VERSION")
        or project_version()
    )


def motionsmith_info_plist():
    info = {
        "NSPrincipalClass": "NSApplication",
        "NSAppleScriptEnabled": False,
        "NSRequiresAquaSystemAppearance": "YES",  # Forces light mode for the app
        "CFBundlePackageType": "APPL",
        "CFBundleDisplayName": "MotionSmith",
        "CFBundleIdentifier": "app.motionsmith.motionsmith",
        "CFBundleShortVersionString": motionsmith_short_version(),
        "CFBundleVersion": motionsmith_bundle_version(),
        "SUFeedURL": configured_appcast_url(os.environ),
    }
    public_key = sparkle_public_ed_key(os.environ)
    if public_key:
        info["SUPublicEDKey"] = public_key
    automatic_checks = env_flag_optional(AUTOMATIC_CHECKS_ENV, os.environ)
    if automatic_checks is not None:
        info["SUEnableAutomaticChecks"] = automatic_checks
    return info


def pyinstaller_icon():
    if sys.platform == "darwin":
        return project_path("resources", "icons", "AppIcon.icns")
    return None


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


def onnxruntime_extra_binaries():
    # PyInstaller's import graph can see onnxruntime's Python modules while still
    # missing the platform-native runtime/provider DLLs that the C extension loads
    # at runtime.  Collect them explicitly so Windows image processing can run from
    # the packaged app instead of failing at InferenceSession construction.
    return collect_dynamic_libs("onnxruntime")


def onnxruntime_hiddenimports():
    # The top-level package imports capi._pybind_state, validation, and inference
    # collection modules dynamically.  A single hidden import for the .pyd/.so is
    # not enough on Windows: the packaged app can find native files but still fail
    # at `import onnxruntime`.  Keep the scope to capi instead of collecting all
    # optional training/quantization/tooling modules.
    return ["onnxruntime", *collect_submodules("onnxruntime.capi")]


RUNTIME_UPX_EXCLUDES = [
    "onnxruntime*.dll",
    "onnxruntime*.pyd",
    "opencv*.dll",
    "cv2*.pyd",
]


a = Analysis(
    [project_path("src", "automataii", "__main__.py")],
    pathex=[project_path("src")],
    binaries=[*macos_extra_binaries(), *onnxruntime_extra_binaries()],
    datas=[
        (project_path("models", "onnx"), "models/onnx"),
        (
            project_path("src", "automataii", "presentation", "qt", "fonts"),
            "automataii/presentation/qt/fonts",
        ),
        (project_path("fabrication"), "fabrication"),
        (project_path("resources"), "resources"),  # Includes resources/data/*.json
        *existing_datas(
            [
                (project_path("src", "automataii", "modules"), "automataii/modules"),
                # Only include root-level images from examples directory
                (project_path("src", "examples", "*.png"), "examples"),
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
        *onnxruntime_hiddenimports(),
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
    name="MotionSmith",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=RUNTIME_UPX_EXCLUDES,
    runtime_tmpdir=None,
    console=False,  # Set to False for GUI applications
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=os.environ.get("PYINSTALLER_TARGET_ARCH") or None,
    codesign_identity=None,
    entitlements_file=None,
    icon=pyinstaller_icon(),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=RUNTIME_UPX_EXCLUDES,
    name="MotionSmith",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="MotionSmith.app",
        icon=project_path("resources", "icons", "AppIcon.icns"),
        bundle_identifier="app.motionsmith.motionsmith",
        info_plist=motionsmith_info_plist(),
    )
