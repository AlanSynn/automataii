#!/usr/bin/env python3
"""
Build script for Automataii experiment mode
Creates a build with --experiment flag automatically enabled
"""

import sys
import os
import shutil
import subprocess
import logging
import platform
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def _host_arch() -> str:
    mach = platform.machine()
    return 'arm64' if mach == 'arm64' else 'x86_64'


def _sign_app(app_bundle: Path, identity: str) -> None:
    logger.info(f"Signing app with identity: {identity}")
    cmd = [
        'codesign', '--deep', '--force', '--options', 'runtime',
        '--sign', identity, str(app_bundle)
    ]
    try:
        subprocess.run(cmd + ['--timestamp'], check=True)
    except subprocess.CalledProcessError:
        subprocess.run(cmd, check=True)
    logger.info("✓ Codesign complete")


def _create_dmg(app_bundle: Path, dist_dir: Path, volname: str, arch_label: str | None) -> Path:
    if arch_label:
        dmg_filename = f'{volname}-macos-{arch_label}.dmg'
    else:
        dmg_filename = f'{volname}.dmg'
    dmg_path = dist_dir / dmg_filename
    if dmg_path.exists():
        dmg_path.unlink()

    if shutil.which('hdiutil') is not None:
        cmd = [
            'hdiutil', 'create', '-volname', volname,
            '-srcfolder', str(app_bundle),
            '-ov', '-format', 'UDZO', str(dmg_path)
        ]
        logger.info(f"Creating DMG: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)
        logger.info(f"✓ DMG created at {dmg_path}")
        return dmg_path

    if shutil.which('create-dmg') is not None:
        cmd = [
            'create-dmg', '--overwrite', '--volname', volname,
            str(dmg_path), str(app_bundle)
        ]
        logger.info(f"Creating DMG with create-dmg: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)
        logger.info(f"✓ DMG created at {dmg_path}")
        return dmg_path

    logger.warning("DMG creation tools not found (hdiutil/create-dmg). Skipping DMG.")
    return dmg_path


def _notarize(dmg_path: Path, app_bundle: Path) -> bool:
    apple_id = os.environ.get('APPLE_ID')
    team_id = os.environ.get('APPLE_TEAM_ID')
    app_password = os.environ.get('APPLE_APP_SPECIFIC_PASSWORD')
    if not (apple_id and team_id and app_password):
        logger.warning("Notarization skipped: APPLE_ID / APPLE_TEAM_ID / APPLE_APP_SPECIFIC_PASSWORD not set")
        return False

    submit_cmd = [
        'xcrun', 'notarytool', 'submit', str(dmg_path),
        '--apple-id', apple_id,
        '--password', app_password,
        '--team-id', team_id,
        '--wait'
    ]
    logger.info("Submitting DMG for notarization (notarytool --wait)...")
    subprocess.run(submit_cmd, check=True)

    # Staple tickets
    subprocess.run(['xcrun', 'stapler', 'staple', str(dmg_path)], check=True)
    if app_bundle.exists():
        subprocess.run(['xcrun', 'stapler', 'staple', str(app_bundle)], check=True)
    logger.info("✓ Notarization and stapling completed")
    return True


def main():
    """Build experiment version of Automataii"""
    import argparse

    parser = argparse.ArgumentParser(description='Build Automataii (experiment mode)')
    parser.add_argument('--fast', action='store_true', help='Faster build: skip --clean and disable UPX')
    parser.add_argument('--skip-clean', action='store_true', help='Do not remove dist/ before build')
    parser.add_argument('--arch', choices=['auto', 'arm64', 'x86_64'], default='auto', help='Target architecture (native only)')
    parser.add_argument('--sign', type=str, help='Code signing identity (Developer ID)')
    parser.add_argument('--no-dmg', action='store_true', help='Skip DMG creation')
    parser.add_argument('--notarize', action='store_true', help='Notarize the DMG (requires APPLE_ID/APPLE_TEAM_ID/APPLE_APP_SPECIFIC_PASSWORD)')
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent
    os.chdir(project_root)

    # Determine target arch
    host = _host_arch()
    target_arch = host if args.arch == 'auto' else args.arch
    if target_arch != host and sys.platform == 'darwin':
        logger.error(f"Requested arch '{target_arch}' does not match host arch '{host}'. macOS cross-compilation is not supported. Use a native host.")
        return False

    logger.info(f"Building Automataii in experiment mode for arch: {target_arch}...")

    # Clean previous builds unless fast/skip-clean
    dist_dir = project_root / "dist"
    if not args.fast and not args.skip_clean:
        if dist_dir.exists():
            logger.info("Cleaning previous builds (dist/)...")
            shutil.rmtree(dist_dir)

    # Create entry script that automatically enables experiment mode
    entry_script_content = '''#!/usr/bin/env python3
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
'''

    entry_script_path = project_root / "automataii_experiment_entry.py"
    with open(entry_script_path, 'w') as f:
        f.write(entry_script_content)

    try:
        # Build using the experiment spec file
        spec_file = project_root / "packaging" / "pyinstaller" / "automataii-experiment.spec"
        cmd = [sys.executable, "-m", "PyInstaller", str(spec_file), "--noconfirm"]
        if args.fast:
            # Faster: keep caches and skip binary compression
            cmd.append("--noupx")
        else:
            # Thorough rebuild each time
            cmd.append("--clean")

        logger.info(f"Running: {' '.join(cmd)}")
        # Stream PyInstaller output directly for better progress visibility and less overhead
        result = subprocess.run(cmd, check=True)

        if result.returncode == 0:
            logger.info("✓ Build completed successfully!")
            logger.info(f"Output directory: {dist_dir}")

            # List built files
            if dist_dir.exists():
                for item in dist_dir.iterdir():
                    logger.info(f"  - {item.name}")

            # macOS extras: sign, DMG, notarize
            if sys.platform == 'darwin':
                app_bundle = dist_dir / 'AutomataII-Experiment.app'
                if args.sign:
                    _sign_app(app_bundle, args.sign)
                dmg_path = None
                if not args.no_dmg:
                    dmg_path = _create_dmg(app_bundle, dist_dir, 'Automataii-Experiment', target_arch)
                if args.notarize and dmg_path and dmg_path.exists():
                    _notarize(dmg_path, app_bundle)

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
