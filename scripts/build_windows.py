#!/usr/bin/env python3
"""
Windows build script with WinSparkle auto-update support and Authenticode signing.
"""

from __future__ import annotations

import glob
import hashlib
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from collections.abc import Iterable
from pathlib import Path
from typing import cast


def _download_file(url: str, destination: Path) -> Path:
    if __package__:
        from .download_utils import download_file as package_download_file

        return package_download_file(url, destination)
    from download_utils import download_file as script_download_file

    return cast(Path, script_download_file(url, destination))


DEFAULT_TIMESTAMP_URL = "http://timestamp.digicert.com"
DEFAULT_CERT_PASSWORD_ENV = "WINDOWS_CERT_PASSWORD"
WINSPARKLE_ZIP_SHA256 = "ffada2df3180de5376bfcde076a13ef406c87a83173ca62ae02b583cd7103c58"

# Logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class WindowsBuilder:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.build_dir = project_root / "scripts" / "build"
        self.dist_dir = project_root / "dist"
        self.winsparkle_version = "0.8.0"
        self.winsparkle_url = f"https://github.com/vslavik/winsparkle/releases/download/v{self.winsparkle_version}/WinSparkle-{self.winsparkle_version}.zip"

    def check_dependencies(self) -> bool:
        """Check if required tools are installed"""
        required_tools = ["pyinstaller"]
        missing_tools = []

        for tool in required_tools:
            if shutil.which(tool) is None:
                missing_tools.append(tool)

        if missing_tools:
            logger.error(f"Missing required tools: {', '.join(missing_tools)}")
            if "pyinstaller" in missing_tools:
                logger.info("Make sure pyinstaller is installed via uv sync --group build")
            return False

        return True

    def download_winsparkle(self) -> Path:
        """Download WinSparkle library"""
        winsparkle_dir = self.build_dir / "WinSparkle"

        if winsparkle_dir.exists():
            logger.info("WinSparkle already downloaded.")
            return winsparkle_dir

        logger.info(f"Downloading WinSparkle {self.winsparkle_version}...")

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            zip_path = temp_path / "winsparkle.zip"

            _download_file(self.winsparkle_url, zip_path)
            self.verify_file_sha256(zip_path, WINSPARKLE_ZIP_SHA256)

            # Extract ZIP
            logger.info("Extracting WinSparkle...")
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(temp_path)

            # Find extracted directory
            extracted_dirs = [
                d for d in temp_path.iterdir() if d.is_dir() and d.name.startswith("WinSparkle")
            ]
            if not extracted_dirs:
                raise FileNotFoundError("WinSparkle directory not found in extracted files.")

            # Copy to build directory
            self.build_dir.mkdir(parents=True, exist_ok=True)
            shutil.copytree(extracted_dirs[0], winsparkle_dir)
            logger.info(f"WinSparkle installed at: {winsparkle_dir}")

        return winsparkle_dir

    def verify_file_sha256(self, path: Path, expected_sha256: str) -> None:
        actual_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual_sha256.lower() != expected_sha256.lower():
            raise RuntimeError(f"SHA256 mismatch for {path}: {actual_sha256}")

    def build_executable(self) -> Path:
        """Build executable with PyInstaller"""
        logger.info("Building executable with PyInstaller...")

        spec_file = self.project_root / "packaging" / "pyinstaller" / "automataii.spec"
        if not spec_file.exists():
            raise FileNotFoundError(f"Spec file not found: {spec_file}")

        # Clean existing dist folder
        if self.dist_dir.exists():
            shutil.rmtree(self.dist_dir)

        # Run PyInstaller
        cmd = [sys.executable, "-m", "PyInstaller", "--clean", str(spec_file)]
        subprocess.run(cmd, cwd=self.project_root, check=True)

        exe_path = self.find_built_executable()
        logger.info(f"Executable built successfully: {exe_path}")
        return exe_path

    def find_built_executable(self) -> Path:
        """Return the PyInstaller-built Windows one-folder executable."""
        exe_path = self.dist_dir / "MotionSmith" / "MotionSmith.exe"
        if exe_path.exists():
            return exe_path
        raise FileNotFoundError("Built one-folder executable not found.")

    def find_signtool(self, signtool: str | Path | None = None) -> Path:
        """Find Microsoft SignTool."""
        requested = signtool or os.environ.get("WINDOWS_SIGNTOOL_PATH")
        if requested:
            path = Path(requested)
            if path.exists():
                return path
            raise FileNotFoundError(f"SignTool not found: {path}")

        for name in ("signtool", "signtool.exe"):
            if found := shutil.which(name):
                return Path(found)

        roots = [os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles")]
        patterns = []
        for root in filter(None, roots):
            patterns.extend(
                [
                    str(Path(root) / "Windows Kits" / "10" / "bin" / "*" / "x64" / "signtool.exe"),
                    str(Path(root) / "Windows Kits" / "10" / "bin" / "x64" / "signtool.exe"),
                ]
            )
        for candidate in sorted(
            {p for pattern in patterns for p in glob.glob(pattern)}, reverse=True
        ):
            return Path(candidate)

        raise FileNotFoundError(
            "Microsoft SignTool was not found. Install the Windows SDK or set WINDOWS_SIGNTOOL_PATH."
        )

    def sign_executable(
        self,
        exe_path: Path,
        certificate: Path,
        cert_password_env: str = DEFAULT_CERT_PASSWORD_ENV,
        signtool: str | Path | None = None,
        timestamp_url: str = DEFAULT_TIMESTAMP_URL,
    ) -> None:
        """Sign the executable with Authenticode."""
        if not certificate.exists():
            raise FileNotFoundError(f"Windows signing certificate not found: {certificate}")
        password = os.environ.get(cert_password_env)
        if not password:
            raise RuntimeError(f"{cert_password_env} is required for Windows signing")

        signtool_path = self.find_signtool(signtool)
        cmd = [
            str(signtool_path),
            "sign",
            "/v",
            "/fd",
            "SHA256",
            "/tr",
            timestamp_url,
            "/td",
            "SHA256",
            "/f",
            str(certificate),
            "/p",
            password,
            "/d",
            "MotionSmith",
            str(exe_path),
        ]
        logger.info("Signing Windows executable with SignTool...")
        try:
            subprocess.run(cmd, cwd=self.project_root, check=True)
        except subprocess.CalledProcessError as exc:
            raise RuntimeError("SignTool signing failed") from exc

    def verify_signature(self, exe_path: Path, signtool: str | Path | None = None) -> None:
        """Verify the Authenticode signature."""
        signtool_path = self.find_signtool(signtool)
        cmd = [str(signtool_path), "verify", "/pa", "/v", str(exe_path)]
        logger.info("Verifying Windows executable signature...")
        try:
            subprocess.run(cmd, cwd=self.project_root, check=True)
        except subprocess.CalledProcessError as exc:
            raise RuntimeError("SignTool verification failed") from exc

    def stage_winsparkle(self, winsparkle_dir: Path, exe_path: Path) -> Path:
        """Copy WinSparkle.dll beside MotionSmith.exe so auto-update works from the zip."""
        matches = sorted(winsparkle_dir.rglob("WinSparkle.dll"))
        if not matches:
            raise FileNotFoundError(f"WinSparkle.dll not found under {winsparkle_dir}")
        destination = exe_path.parent / "WinSparkle.dll"
        shutil.copy2(matches[0], destination)
        logger.info(f"WinSparkle staged at: {destination}")
        return destination

    def signable_payload_files(self, exe_path: Path) -> list[Path]:
        """Return PE files that should be Authenticode-signed before zipping."""
        suffixes = {".exe", ".dll", ".pyd"}
        return sorted(
            path
            for path in exe_path.parent.rglob("*")
            if path.is_file() and path.suffix.lower() in suffixes
        )

    def sign_payload_files(
        self,
        files: Iterable[Path],
        certificate: Path,
        cert_password_env: str = DEFAULT_CERT_PASSWORD_ENV,
        signtool: str | Path | None = None,
        timestamp_url: str = DEFAULT_TIMESTAMP_URL,
    ) -> None:
        for file in files:
            self.sign_executable(
                file,
                certificate=certificate,
                cert_password_env=cert_password_env,
                signtool=signtool,
                timestamp_url=timestamp_url,
            )

    def verify_payload_signatures(
        self, files: Iterable[Path], signtool: str | Path | None = None
    ) -> None:
        for file in files:
            self.verify_signature(file, signtool=signtool)

    def create_distribution_zip(self, exe_path: Path) -> Path:
        """Package the PyInstaller one-folder app and user install scripts into a zip."""
        archive_base = self.dist_dir / "MotionSmith-windows"
        archive_path = archive_base.with_suffix(".zip")
        if archive_path.exists():
            archive_path.unlink()

        installer_files = {
            "install.ps1": self.project_root / "packaging" / "windows" / "install.ps1",
            "uninstall.ps1": self.project_root / "packaging" / "windows" / "uninstall.ps1",
            "README-Windows.txt": self.project_root
            / "packaging"
            / "windows"
            / "README-Windows.txt",
        }
        missing = [str(path) for path in installer_files.values() if not path.exists()]
        if missing:
            raise FileNotFoundError(f"Windows installer payload missing: {', '.join(missing)}")

        app_dir = exe_path.parent
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(app_dir.rglob("*")):
                if not path.is_file():
                    continue
                relative = path.relative_to(app_dir)
                archive.write(path, "/".join(("MotionSmith", *relative.parts)))
            for archive_name, source in installer_files.items():
                archive.write(source, archive_name)

        logger.info(f"Windows distribution archive created: {archive_path}")
        return archive_path

    def build(
        self,
        sign: bool = False,
        certificate: Path | None = None,
        cert_password_env: str = DEFAULT_CERT_PASSWORD_ENV,
        signtool: str | Path | None = None,
        verify_signature: bool = False,
        timestamp_url: str = DEFAULT_TIMESTAMP_URL,
    ) -> bool:
        """Execute complete build process"""
        logger.info("=== Starting Windows build ===")

        # Check dependencies
        if not self.check_dependencies():
            return False

        try:
            if sign and certificate is None:
                raise RuntimeError("--certificate is required when --sign is set")

            # 2. Download WinSparkle
            winsparkle_dir = self.download_winsparkle()

            # 3. Build executable
            exe_path = self.build_executable()
            self.stage_winsparkle(winsparkle_dir, exe_path)

            payload_files = self.signable_payload_files(exe_path)

            if sign:
                signing_certificate = certificate
                assert signing_certificate is not None
                self.sign_payload_files(
                    payload_files,
                    certificate=signing_certificate,
                    cert_password_env=cert_password_env,
                    signtool=signtool,
                    timestamp_url=timestamp_url,
                )

            if verify_signature:
                self.verify_payload_signatures(payload_files, signtool=signtool)

            archive_path = self.create_distribution_zip(exe_path)

            logger.info(f"Final distribution file: {archive_path}")
            logger.info("=== Windows build complete ===")
            return True

        except Exception as e:
            logger.error(f"Build error: {e}")
            return False


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Build MotionSmith for Windows")
    parser.add_argument("--sign", action="store_true", help="Sign MotionSmith.exe with SignTool")
    parser.add_argument("--certificate", type=Path, help="PFX certificate used for Windows signing")
    parser.add_argument(
        "--cert-password-env",
        default=DEFAULT_CERT_PASSWORD_ENV,
        help="Environment variable containing the PFX password",
    )
    parser.add_argument(
        "--signtool",
        help="Path to signtool.exe; defaults to WINDOWS_SIGNTOOL_PATH/PATH/Windows SDK",
    )
    parser.add_argument(
        "--timestamp-url",
        default=DEFAULT_TIMESTAMP_URL,
        help="RFC3161 timestamp server URL",
    )
    parser.add_argument(
        "--verify-signature",
        action="store_true",
        help="Verify Authenticode signature after build/sign",
    )

    args = parser.parse_args()

    project_root = Path(__file__).parent.parent
    builder = WindowsBuilder(project_root)

    success = builder.build(
        sign=args.sign,
        certificate=args.certificate,
        cert_password_env=args.cert_password_env,
        signtool=args.signtool,
        verify_signature=args.verify_signature,
        timestamp_url=args.timestamp_url,
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
