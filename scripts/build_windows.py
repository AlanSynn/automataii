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
DEFAULT_WINSPARKLE_TARGET_ARCH = "x64"
PE_MACHINE_BY_ARCH = {
    "x86": 0x014C,
    "x64": 0x8664,
    "arm64": 0xAA64,
}
WINSPARKLE_ARCH_ALIASES = {
    "x86": ("x86", "win32"),
    "x64": ("x64", "amd64", "win64"),
    "arm64": ("arm64", "aarch64"),
}

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

    @staticmethod
    def pe_machine_type(path: Path) -> int | None:
        """Return a Windows PE machine type, or None when the file is not parseable PE."""
        data = path.read_bytes()
        if len(data) < 0x40 or data[:2] != b"MZ":
            return None
        pe_offset = int.from_bytes(data[0x3C:0x40], "little")
        if pe_offset < 0 or len(data) < pe_offset + 6:
            return None
        if data[pe_offset : pe_offset + 4] != b"PE\0\0":
            return None
        return int.from_bytes(data[pe_offset + 4 : pe_offset + 6], "little")

    @staticmethod
    def _winsparkle_candidate_matches_arch(path: Path, target_arch: str) -> bool:
        aliases = WINSPARKLE_ARCH_ALIASES.get(target_arch, (target_arch,))
        return any(part.lower() in aliases for part in path.parts)

    @staticmethod
    def _winsparkle_candidate_rank(path: Path) -> tuple[int, int, str]:
        parts = {part.lower() for part in path.parts}
        release_rank = 0 if "release" in parts else 1
        return (release_rank, len(path.parts), str(path).lower())

    def select_winsparkle_dll(
        self,
        winsparkle_dir: Path,
        target_arch: str = DEFAULT_WINSPARKLE_TARGET_ARCH,
    ) -> Path:
        """Select the WinSparkle DLL matching the Windows build architecture."""
        matches = sorted(winsparkle_dir.rglob("WinSparkle.dll"))
        if not matches:
            raise FileNotFoundError(f"WinSparkle.dll not found under {winsparkle_dir}")

        arch_matches = [
            path for path in matches if self._winsparkle_candidate_matches_arch(path, target_arch)
        ]
        if arch_matches:
            selected = min(arch_matches, key=self._winsparkle_candidate_rank)
        elif len(matches) == 1:
            selected = matches[0]
        else:
            candidates = "\n".join(f"  - {path}" for path in matches)
            raise FileNotFoundError(
                f"Could not find a WinSparkle.dll for target architecture {target_arch!r}. "
                f"Candidates:\n{candidates}"
            )

        self.verify_winsparkle_machine_type(selected, target_arch)
        return selected

    def verify_winsparkle_machine_type(self, path: Path, target_arch: str) -> None:
        """Fail closed when a parseable WinSparkle DLL has the wrong PE architecture."""
        expected = PE_MACHINE_BY_ARCH.get(target_arch)
        if expected is None:
            raise ValueError(f"Unsupported WinSparkle target architecture: {target_arch}")

        actual = self.pe_machine_type(path)
        if actual is None:
            logger.warning("Could not parse PE machine type for %s; selected by path only.", path)
            return
        if actual != expected:
            raise RuntimeError(
                f"WinSparkle DLL architecture mismatch for {path}: "
                f"expected 0x{expected:04x} ({target_arch}), got 0x{actual:04x}"
            )

    def stage_winsparkle(
        self,
        winsparkle_dir: Path,
        exe_path: Path,
        target_arch: str = DEFAULT_WINSPARKLE_TARGET_ARCH,
    ) -> Path:
        """Copy WinSparkle.dll beside MotionSmith.exe so auto-update works from the zip."""
        winsparkle_dll = self.select_winsparkle_dll(winsparkle_dir, target_arch=target_arch)
        destination = exe_path.parent / "WinSparkle.dll"
        shutil.copy2(winsparkle_dll, destination)
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
        """Package the PyInstaller one-folder app so MotionSmith.exe is at zip root."""
        archive_base = self.dist_dir / "MotionSmith-windows"
        archive_path = archive_base.with_suffix(".zip")
        if archive_path.exists():
            archive_path.unlink()

        readme = self.project_root / "packaging" / "windows" / "README-Windows.txt"
        if not readme.exists():
            raise FileNotFoundError(f"Windows README missing: {readme}")

        app_dir = exe_path.parent
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(app_dir.rglob("*")):
                if not path.is_file():
                    continue
                relative = path.relative_to(app_dir)
                archive.write(path, "/".join(relative.parts))
            archive.write(readme, "README-Windows.txt")

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
