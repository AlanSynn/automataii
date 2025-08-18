#!/usr/bin/env python3
"""
macOS build utilities for Automataii

Provides a MacOSBuilder class consumed by scripts/build.py and
retains a CLI entrypoint for direct use.
"""

import os
import shutil
import subprocess
import sys
import logging
from pathlib import Path

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class MacOSBuilder:
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.dist_dir = self.project_root / 'dist'
        self.build_dir = self.project_root / 'build'
        self.spec_file = self.project_root / 'automataii.spec'
        # Match app name in automataii.spec
        self.app_name = 'AutomataII'
        self.app_bundle = self.dist_dir / f'{self.app_name}.app'

    def check_dependencies(self) -> bool:
        """Check for required tools."""
        logger.info("Checking dependencies...")
        # PyInstaller
        try:
            subprocess.run([sys.executable, '-c', 'import PyInstaller'], check=True, capture_output=True)
            logger.info("✓ PyInstaller is available")
        except subprocess.CalledProcessError:
            logger.error("✗ PyInstaller not found. Install with: uv add pyinstaller")
            return False
        return True

    def clean(self):
        """Remove previous build artifacts."""
        logger.info("Cleaning previous build artifacts...")
        if self.dist_dir.exists():
            shutil.rmtree(self.dist_dir)
        if self.build_dir.exists():
            shutil.rmtree(self.build_dir)
        logger.info("Clean complete")

    def build_executable(self):
        """Run PyInstaller with the project spec file."""
        if not self.spec_file.exists():
            raise FileNotFoundError(f"Spec file not found: {self.spec_file}")

        cmd = [sys.executable, '-m', 'PyInstaller', '--clean', '--noconfirm', str(self.spec_file)]
        logger.info(f"Running: {' '.join(cmd)}")
        subprocess.run(cmd, cwd=self.project_root, check=True)

        if not self.app_bundle.exists():
            # Allow for case mismatch fallback
            alt_app = self.dist_dir / 'Automataii.app'
            if alt_app.exists():
                self.app_bundle = alt_app
            else:
                raise FileNotFoundError(f"Built app bundle not found at {self.app_bundle}")

        logger.info(f"✓ PyInstaller build successful: {self.app_bundle}")

    def sign_app(self, sign_identity: str | None):
        """Codesign the app bundle if identity provided."""
        if not sign_identity:
            logger.info("Skipping code signing (no identity provided)")
            return
        logger.info(f"Signing app with identity: {sign_identity}")
        cmd = [
            'codesign', '--deep', '--force', '--options', 'runtime',
            '--sign', sign_identity, str(self.app_bundle)
        ]
        # Timestamp if available (non-fatal if not)
        try:
            subprocess.run(cmd + ['--timestamp'], check=True)
        except subprocess.CalledProcessError:
            subprocess.run(cmd, check=True)
        logger.info("✓ Codesign complete")

    def create_dmg(self, arch_label: str | None = None):
        """Create a DMG for the built app using hdiutil (fallback if create-dmg not installed).

        If arch_label is provided, name output as 'Automataii-macos-<arch>.dmg'.
        """
        if arch_label:
            dmg_filename = f'Automataii-macos-{arch_label}.dmg'
        else:
            dmg_filename = f'{self.app_name}.dmg'
        dmg_path = self.dist_dir / dmg_filename
        # Remove existing DMG
        if dmg_path.exists():
            dmg_path.unlink()

        # Prefer hdiutil (standard on macOS)
        if shutil.which('hdiutil') is not None:
            cmd = [
                'hdiutil', 'create', '-volname', self.app_name,
                '-srcfolder', str(self.app_bundle),
                '-ov', '-format', 'UDZO', str(dmg_path)
            ]
            logger.info(f"Creating DMG: {' '.join(cmd)}")
            subprocess.run(cmd, check=True)
            logger.info(f"✓ DMG created at {dmg_path}")
            return

        # Optional: use create-dmg if present
        if shutil.which('create-dmg') is not None:
            cmd = [
                'create-dmg', '--overwrite', '--volname', self.app_name,
                str(dmg_path), str(self.app_bundle)
            ]
            logger.info(f"Creating DMG with create-dmg: {' '.join(cmd)}")
            subprocess.run(cmd, check=True)
            logger.info(f"✓ DMG created at {dmg_path}")
            return

        logger.warning("DMG creation tools not found (hdiutil/create-dmg). Skipping DMG.")

    def notarize(self, target_path: Path) -> bool:
        """Notarize the given file (DMG recommended) and staple the ticket.

        Credentials are taken from environment variables:
        - APPLE_ID, APPLE_TEAM_ID, APPLE_APP_SPECIFIC_PASSWORD

        Returns True on success, False otherwise.
        """
        apple_id = os.environ.get('APPLE_ID')
        team_id = os.environ.get('APPLE_TEAM_ID')
        app_password = os.environ.get('APPLE_APP_SPECIFIC_PASSWORD')

        if not (apple_id and team_id and app_password):
            logger.warning("Notarization skipped: APPLE_ID / APPLE_TEAM_ID / APPLE_APP_SPECIFIC_PASSWORD not set")
            return False

        submit_cmd = [
            'xcrun', 'notarytool', 'submit', str(target_path),
            '--apple-id', apple_id,
            '--password', app_password,
            '--team-id', team_id,
            '--wait'
        ]
        logger.info(f"Submitting for notarization: {' '.join(submit_cmd[:-1])} --wait")
        try:
            subprocess.run(submit_cmd, check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Notarization submission failed: {e}")
            return False

        # Staple to both DMG and .app bundle
        try:
            subprocess.run(['xcrun', 'stapler', 'staple', str(target_path)], check=True)
            if self.app_bundle.exists():
                subprocess.run(['xcrun', 'stapler', 'staple', str(self.app_bundle)], check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Stapling failed: {e}")
            return False

        logger.info("✓ Notarization and stapling completed")
        return True

    def build(self, sign_identity: str | None = None, create_dmg: bool = True, experiment_mode: bool = False, editing_mode: bool = False, arch: str = 'auto', notarize: bool = False) -> bool:
        """Execute the macOS build pipeline."""
        logger.info("=== Starting macOS build ===")
        import platform
        machine = platform.machine()
        # Normalize arch from host
        host_arch = 'arm64' if machine == 'arm64' else 'x86_64'
        if arch == 'auto':
            arch = host_arch
        elif arch != host_arch:
            logger.error(f"Requested arch '{arch}' does not match host arch '{host_arch}'. macOS cross-compilation is not supported. Build on a native host or use Rosetta for x86_64 builds.")
            return False
        if not self.check_dependencies():
            return False
        try:
            self.clean()
            self.build_executable()
            self.sign_app(sign_identity)
            dmg_path = None
            if create_dmg:
                self.create_dmg(arch_label=arch)
                dmg_filename = f'Automataii-macos-{arch}.dmg' if arch else f'{self.app_name}.dmg'
                dmg_path = self.dist_dir / dmg_filename
                if notarize and dmg_path.exists():
                    self.notarize(dmg_path)
            logger.info("=== macOS build complete ===")
            return True
        except Exception as e:
            logger.error(f"Build error: {e}")
            return False


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Build Automataii for macOS')
    parser.add_argument('--sign', type=str, help='Code signing identity (Developer ID)')
    parser.add_argument('--no-dmg', action='store_true', help='Skip DMG creation')
    parser.add_argument('--experiment', action='store_true', help='Build in experiment mode (no-op for macOS)')
    parser.add_argument('--editing', action='store_true', help='Build in edit mode (no-op for macOS)')
    parser.add_argument('--notarize', action='store_true', help='Notarize the DMG (requires APPLE_ID/APPLE_TEAM_ID/APPLE_APP_SPECIFIC_PASSWORD env vars)')
    parser.add_argument('--arch', choices=['auto', 'arm64', 'x86_64'], default='auto', help='Target architecture (native only)')
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent
    builder = MacOSBuilder(project_root)
    success = builder.build(sign_identity=args.sign, create_dmg=not args.no_dmg, experiment_mode=args.experiment,
    editing_mode=args.editing, arch=args.arch, notarize=args.notarize)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
