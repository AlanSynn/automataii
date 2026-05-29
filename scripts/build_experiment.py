#!/usr/bin/env python3
"""
Build script for Automataii experiment mode
Creates a build with --experiment flag automatically enabled
"""

import logging
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from .macos_arch import (
        MACOS_ARCH_CHOICES,
        PYINSTALLER_TARGET_ARCH_ENV,
        THIN_MACOS_ARCHES,
        host_arch,
    )
    from .macos_notary import notarization_credentials_help, notarytool_submit_plan
except ImportError:  # pragma: no cover - used when executed as scripts/build_experiment.py
    from macos_arch import (
        MACOS_ARCH_CHOICES,
        PYINSTALLER_TARGET_ARCH_ENV,
        THIN_MACOS_ARCHES,
        host_arch,
    )
    from macos_notary import notarization_credentials_help, notarytool_submit_plan

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def _sign_app(app_bundle: Path, identity: str) -> None:
    logger.info(f"Signing app with identity: {identity}")
    entitlements_file = Path(__file__).parent.parent / "packaging" / "macos" / "entitlements.plist"
    cmd = [
        "codesign",
        "--deep",
        "--force",
        "--options",
        "runtime",
        "--sign",
        identity,
    ]
    if entitlements_file.exists():
        cmd.extend(["--entitlements", str(entitlements_file)])
    cmd.append(str(app_bundle))
    try:
        subprocess.run(cmd + ["--timestamp"], check=True)
    except subprocess.CalledProcessError:
        subprocess.run(cmd, check=True)
    logger.info("✓ Codesign complete")


def _create_dmg(app_bundle: Path, dist_dir: Path, volname: str, arch_label: str | None) -> Path:
    if arch_label:
        dmg_filename = f"{volname}-macos-{arch_label}.dmg"
    else:
        dmg_filename = f"{volname}.dmg"
    dmg_path = dist_dir / dmg_filename
    if dmg_path.exists():
        dmg_path.unlink()

    if shutil.which("hdiutil") is not None:
        cmd = [
            "hdiutil",
            "create",
            "-volname",
            volname,
            "-srcfolder",
            str(app_bundle),
            "-ov",
            "-format",
            "UDZO",
            str(dmg_path),
        ]
        logger.info(f"Creating DMG: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)
        if not dmg_path.exists():
            raise FileNotFoundError(f"Requested DMG was not created: {dmg_path}")
        logger.info(f"✓ DMG created at {dmg_path}")
        return dmg_path

    if shutil.which("create-dmg") is not None:
        cmd = ["create-dmg", "--overwrite", "--volname", volname, str(dmg_path), str(app_bundle)]
        logger.info(f"Creating DMG with create-dmg: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)
        if not dmg_path.exists():
            raise FileNotFoundError(f"Requested DMG was not created: {dmg_path}")
        logger.info(f"✓ DMG created at {dmg_path}")
        return dmg_path

    raise RuntimeError("DMG creation tools not found (hdiutil/create-dmg).")


def _sign_dmg(dmg_path: Path, identity: str | None) -> None:
    if not identity:
        return

    cmd = ["codesign", "--force", "--sign", identity, "--timestamp", str(dmg_path)]
    logger.info("Signing DMG with identity: %s", identity)
    subprocess.run(cmd, check=True)
    subprocess.run(["codesign", "--verify", "--verbose=2", str(dmg_path)], check=True)
    logger.info("✓ DMG signature verified")


def _submit_for_notarization(target_path: Path) -> bool:
    submit_plan = notarytool_submit_plan(target_path)
    if submit_plan is None:
        logger.error(
            "Notarization requested but APPLE_NOTARY_PROFILE is missing. %s",
            notarization_credentials_help(),
        )
        return False

    logger.info("Submitting %s for notarization with %s", target_path, submit_plan.auth_description)
    try:
        subprocess.run(submit_plan.command, check=True)
    except subprocess.CalledProcessError:
        logger.error("Notarization submission failed.")
        return False
    return True


def _notarize_target(target_path: Path) -> bool:
    if not _submit_for_notarization(target_path):
        return False
    try:
        subprocess.run(["xcrun", "stapler", "staple", str(target_path)], check=True)
    except subprocess.CalledProcessError:
        logger.error("Stapling failed.")
        return False
    logger.info("✓ Notarization and stapling completed")
    return True


def _notarize_app_bundle(app_bundle: Path) -> bool:
    if not app_bundle.exists():
        logger.error("App bundle not found for notarization: %s", app_bundle)
        return False

    with tempfile.TemporaryDirectory(prefix="automataii-experiment-app-notary-") as temp_dir:
        zip_path = Path(temp_dir) / f"{app_bundle.name}.zip"
        subprocess.run(["ditto", "-c", "-k", "--keepParent", str(app_bundle), str(zip_path)], check=True)
        if not _submit_for_notarization(zip_path):
            return False

    try:
        subprocess.run(["xcrun", "stapler", "staple", str(app_bundle)], check=True)
    except subprocess.CalledProcessError:
        logger.error("App stapling failed.")
        return False
    logger.info("✓ App notarization and stapling completed")
    return True


def main() -> bool:
    """Build experiment version of Automataii"""
    import argparse

    parser = argparse.ArgumentParser(description="Build Automataii (experiment mode)")
    parser.add_argument(
        "--fast", action="store_true", help="Faster build: skip --clean and disable UPX"
    )
    parser.add_argument(
        "--skip-clean", action="store_true", help="Do not remove dist/ before build"
    )
    parser.add_argument(
        "--arch",
        choices=MACOS_ARCH_CHOICES,
        default="auto",
        help="Target architecture. universal2 builds for Intel and Apple Silicon when dependencies support both slices.",
    )
    parser.add_argument("--sign", type=str, help="Code signing identity (Developer ID)")
    parser.add_argument("--no-dmg", action="store_true", help="Skip DMG creation")
    parser.add_argument(
        "--notarize",
        action="store_true",
        help="Notarize the DMG (requires APPLE_NOTARY_PROFILE keychain profile)",
    )
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent
    os.chdir(project_root)

    if args.notarize and args.no_dmg:
        logger.error("Notarization requires a DMG. Remove --no-dmg or disable --notarize.")
        return False

    target_arch = None
    if sys.platform == "darwin":
        host = host_arch()
        target_arch = host if args.arch == "auto" else args.arch
        if target_arch in THIN_MACOS_ARCHES and target_arch != host:
            logger.error(
                f"Requested arch '{target_arch}' does not match host arch '{host}'. macOS cross-compilation is not supported. Use a native host."
            )
            return False
        if target_arch == "universal2":
            logger.info(
                "Universal2 build requested; Python and binary dependencies must provide both arm64 and x86_64 slices."
            )
        logger.info(f"Building Automataii in experiment mode for arch: {target_arch}...")
    else:
        if args.arch != "auto":
            logger.warning("--arch is only applied to macOS experiment builds; ignoring.")
        logger.info("Building Automataii in experiment mode for current platform...")

    # Clean previous builds unless fast/skip-clean
    dist_dir = project_root / "dist"
    if not args.fast and not args.skip_clean:
        if dist_dir.exists():
            logger.info("Cleaning previous builds (dist/)...")
            shutil.rmtree(dist_dir)

    # Create entry script that automatically enables experiment mode
    entry_script_content = """#!/usr/bin/env python3
import sys
import os

# Add project src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Force experiment mode
sys.argv.append('--experiment')

# Import and run main
from automataii.__main__ import main

if __name__ == "__main__":
    main()
"""

    entry_script_path = project_root / "automataii_experiment_entry.py"
    with open(entry_script_path, "w") as f:
        f.write(entry_script_content)

    try:
        # Build using the experiment spec file
        spec_file = project_root / "packaging" / "pyinstaller" / "automataii-experiment.spec"
        cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm"]
        env = os.environ.copy()
        env.pop(PYINSTALLER_TARGET_ARCH_ENV, None)
        if target_arch:
            env[PYINSTALLER_TARGET_ARCH_ENV] = target_arch
        cmd.append(str(spec_file))
        if args.fast:
            # Faster: keep caches and skip binary compression
            cmd.append("--noupx")
        else:
            # Thorough rebuild each time
            cmd.append("--clean")

        logger.info(f"Running: {' '.join(cmd)}")
        # Stream PyInstaller output directly for better progress visibility and less overhead
        result = subprocess.run(cmd, check=True, env=env)

        if result.returncode == 0:
            logger.info("✓ Build completed successfully!")
            logger.info(f"Output directory: {dist_dir}")

            # List built files
            if dist_dir.exists():
                for item in dist_dir.iterdir():
                    logger.info(f"  - {item.name}")

            # macOS extras: sign, DMG, notarize
            if sys.platform == "darwin":
                app_bundle = dist_dir / "AutomataII-Experiment.app"
                if args.sign:
                    _sign_app(app_bundle, args.sign)
                if args.notarize and not _notarize_app_bundle(app_bundle):
                    return False
                dmg_path = None
                if not args.no_dmg:
                    dmg_path = _create_dmg(
                        app_bundle, dist_dir, "Automataii-Experiment", target_arch
                    )
                    _sign_dmg(dmg_path, args.sign)
                if args.notarize:
                    if dmg_path is None or not dmg_path.exists():
                        logger.error("Notarization requested but DMG was not created.")
                        return False
                    if not _notarize_target(dmg_path):
                        return False

            return True
        else:
            logger.error(f"Build failed with return code: {result.returncode}")
            return False

    except subprocess.CalledProcessError as e:
        logger.error(f"Build failed: {e}")
        return False

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False

    finally:
        # Clean up entry script
        if entry_script_path.exists():
            entry_script_path.unlink()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
