#!/usr/bin/env python3
"""
Build script for MotionSmith experiment mode
Creates a build with --experiment flag automatically enabled
"""

import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

try:
    from .macos_arch import (
        MACOS_ARCH_CHOICES,
        PYINSTALLER_TARGET_ARCH_ENV,
        THIN_MACOS_ARCHES,
        host_arch,
    )
    from .macos_notary import (
        APPLE_NOTARY_PROFILE_ENV,
        notarization_credentials_help,
        notarytool_submit_plan,
    )
    from .verify_macos_release import ReleaseVerification, verify_release
except ImportError:  # pragma: no cover - used when executed as scripts/build_experiment.py
    from macos_arch import (
        MACOS_ARCH_CHOICES,
        PYINSTALLER_TARGET_ARCH_ENV,
        THIN_MACOS_ARCHES,
        host_arch,
    )
    from macos_notary import (
        APPLE_NOTARY_PROFILE_ENV,
        notarization_credentials_help,
        notarytool_submit_plan,
    )
    from verify_macos_release import ReleaseVerification, verify_release


SIGN_IDENTITY_ENV = "MACOS_SIGN_IDENTITY"
APP_NAME = "MotionSmith"
EXPERIMENT_APP_NAME = f"{APP_NAME}-Experiment"

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def _pyinstaller_command(spec_file: Path, *, fast: bool) -> list[str]:
    """Build the PyInstaller command for the experiment spec file."""
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", str(spec_file)]
    if not fast:
        cmd.append("--clean")
    return cmd


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

    staging_dir_handle = tempfile.TemporaryDirectory(prefix="motionsmith-experiment-dmg-")
    staging_dir = Path(staging_dir_handle.name)
    try:
        staged_app = staging_dir / app_bundle.name
        shutil.copytree(app_bundle, staged_app, symlinks=True)
        (staging_dir / "Applications").symlink_to("/Applications")

        return _create_dmg_from_staging(staging_dir, dmg_path, volname)
    finally:
        staging_dir_handle.cleanup()


def _create_dmg_from_staging(staging_dir: Path, dmg_path: Path, volname: str) -> Path:
    if shutil.which("hdiutil") is not None:
        cmd = [
            "hdiutil",
            "create",
            "-volname",
            volname,
            "-srcfolder",
            str(staging_dir),
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
        cmd = ["create-dmg", "--overwrite", "--volname", volname, str(dmg_path), str(staging_dir)]
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

    with tempfile.TemporaryDirectory(prefix="motionsmith-experiment-app-notary-") as temp_dir:
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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_distribution_artifact(
    dmg_path: Path, expected_arch: str
) -> ReleaseVerification | None:
    verification = verify_release(
        dmg_path,
        expected_arch=expected_arch,
        require_notarization=True,
        require_gatekeeper=True,
    )
    for check in verification.checks:
        status = "PASS" if check.passed else "FAIL"
        logger.info("[%s] %s: %s", status, check.name, check.message)
    logger.info("Distribution ready for other Macs: %s", verification.distribution_ready)
    if not verification.distribution_ready:
        logger.error("Experiment DMG failed strict distribution verification.")
        return None
    return verification


def _write_distribution_manifest(
    dmg_path: Path,
    dist_dir: Path,
    arch_label: str,
    sign_identity: str,
    verification: ReleaseVerification,
) -> Path:
    manifest_path = dist_dir / f"{EXPERIMENT_APP_NAME}-macos-{arch_label}-release-manifest.json"
    manifest = {
        "created_at": datetime.now(UTC).isoformat(),
        "artifact": str(dmg_path),
        "sha256": _sha256_file(dmg_path),
        "size_bytes": dmg_path.stat().st_size,
        "arch": arch_label,
        "sign_identity": sign_identity,
        "notary_profile": os.environ.get(APPLE_NOTARY_PROFILE_ENV),
        "strict_distribution": True,
        "verification": asdict(verification),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    logger.info("✓ Experiment release manifest written: %s", manifest_path)
    return manifest_path


def main() -> bool:
    """Build experiment version of MotionSmith."""
    import argparse

    parser = argparse.ArgumentParser(description="Build MotionSmith (experiment mode)")
    parser.add_argument("--fast", action="store_true", help="Faster build: skip --clean")
    parser.add_argument(
        "--skip-clean", action="store_true", help="Do not remove dist/ before build"
    )
    parser.add_argument(
        "--arch",
        choices=MACOS_ARCH_CHOICES,
        default="auto",
        help="Target architecture. universal2 builds for Intel and Apple Silicon when dependencies support both slices.",
    )
    parser.add_argument(
        "--sign",
        type=str,
        help=f"Code signing identity (Developer ID). Defaults to {SIGN_IDENTITY_ENV}.",
    )
    parser.add_argument("--no-dmg", action="store_true", help="Skip DMG creation (non-macOS only)")
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent
    os.chdir(project_root)

    sign_identity = (args.sign or os.environ.get(SIGN_IDENTITY_ENV) or "").strip() or None

    target_arch = None
    if sys.platform == "darwin":
        if args.no_dmg:
            logger.error("macOS experiment builds are distribution builds; DMG creation is required.")
            return False
        if not sign_identity:
            logger.error(
                "macOS experiment builds require Developer ID signing. "
                "Pass --sign or set %s.",
                SIGN_IDENTITY_ENV,
            )
            return False
        if not os.environ.get(APPLE_NOTARY_PROFILE_ENV):
            logger.error(
                "macOS experiment builds require notarization. %s",
                notarization_credentials_help(),
            )
            return False

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
        logger.info(f"Building MotionSmith in experiment mode for arch: {target_arch}...")
    else:
        if args.arch != "auto":
            logger.warning("--arch is only applied to macOS experiment builds; ignoring.")
        logger.info("Building MotionSmith in experiment mode for current platform...")

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

    entry_script_path = project_root / "motionsmith_experiment_entry.py"
    with open(entry_script_path, "w") as f:
        f.write(entry_script_content)

    try:
        # Build using the experiment spec file
        spec_file = project_root / "packaging" / "pyinstaller" / "automataii-experiment.spec"
        cmd = _pyinstaller_command(spec_file, fast=args.fast)
        env = os.environ.copy()
        env.pop(PYINSTALLER_TARGET_ARCH_ENV, None)
        if target_arch:
            env[PYINSTALLER_TARGET_ARCH_ENV] = target_arch

        logger.info(f"Running: {' '.join(cmd)}")
        # Stream PyInstaller output directly for better progress visibility and less overhead
        result = subprocess.run(cmd, check=True, env=env, cwd=project_root)

        if result.returncode == 0:
            logger.info("✓ Build completed successfully!")
            logger.info(f"Output directory: {dist_dir}")

            # List built files
            if dist_dir.exists():
                for item in dist_dir.iterdir():
                    logger.info(f"  - {item.name}")

            # macOS extras: sign, DMG, notarize
            if sys.platform == "darwin":
                app_bundle = dist_dir / f"{EXPERIMENT_APP_NAME}.app"
                _sign_app(app_bundle, sign_identity)
                if not _notarize_app_bundle(app_bundle):
                    return False
                dmg_path = None
                dmg_path = _create_dmg(
                    app_bundle, dist_dir, EXPERIMENT_APP_NAME, target_arch
                )
                _sign_dmg(dmg_path, sign_identity)
                if dmg_path is None or not dmg_path.exists():
                    logger.error("Notarization requested but DMG was not created.")
                    return False
                if not _notarize_target(dmg_path):
                    return False
                verification = _verify_distribution_artifact(dmg_path, target_arch)
                if verification is None:
                    return False
                _write_distribution_manifest(
                    dmg_path,
                    dist_dir,
                    target_arch,
                    sign_identity,
                    verification,
                )

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
