#!/usr/bin/env python3
"""
Universal build script for MotionSmith
Supports building for macOS, Linux, and Windows
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Protocol, cast


class WindowsBuilderProtocol(Protocol):
    def build(
        self,
        *,
        sign: bool,
        certificate: Path | None,
        cert_password_env: str,
        signtool: str | None,
        verify_signature: bool,
        timestamp_url: str,
    ) -> bool: ...


class WindowsBuilderFactory(Protocol):
    def __call__(self, project_root: Path) -> WindowsBuilderProtocol: ...


def _import_windows_builder() -> WindowsBuilderFactory:
    if __package__:
        from .build_windows import WindowsBuilder as package_windows_builder

        return package_windows_builder
    from build_windows import WindowsBuilder as script_windows_builder

    return cast(WindowsBuilderFactory, script_windows_builder)


def _macos_arch_choices() -> tuple[str, ...]:
    if __package__:
        from .macos_arch import MACOS_ARCH_CHOICES as package_choices

        return package_choices
    from macos_arch import MACOS_ARCH_CHOICES as script_choices

    return cast(tuple[str, ...], script_choices)


# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build MotionSmith for current platform")
    parser.add_argument(
        "--platform",
        choices=["macos", "linux", "windows", "auto"],
        default="auto",
        help="Target platform (auto-detect by default)",
    )
    parser.add_argument("--sign", type=str, help="Code signing identity (macOS only)")
    parser.add_argument("--no-dmg", action="store_true", help="Skip DMG creation (macOS only)")
    parser.add_argument(
        "--arch",
        choices=_macos_arch_choices(),
        default="auto",
        help="Target architecture for macOS build",
    )
    parser.add_argument(
        "--windows-sign", action="store_true", help="Sign Windows executable with SignTool"
    )
    parser.add_argument(
        "--windows-certificate", type=Path, help="PFX certificate used for Windows signing"
    )
    parser.add_argument(
        "--windows-cert-password-env",
        default="WINDOWS_CERT_PASSWORD",
        help="Environment variable containing the Windows PFX password",
    )
    parser.add_argument(
        "--windows-signtool",
        help="Path to signtool.exe; defaults to WINDOWS_SIGNTOOL_PATH/PATH/Windows SDK",
    )
    parser.add_argument(
        "--windows-timestamp-url",
        default="http://timestamp.digicert.com",
        help="RFC3161 timestamp server URL for Windows signing",
    )
    parser.add_argument(
        "--windows-verify-signature",
        action="store_true",
        help="Verify Windows Authenticode signature after build/sign",
    )
    parser.add_argument(
        "--no-zsync", action="store_true", help="Skip zsync file creation (Linux only)"
    )
    parser.add_argument("--update-url", type=str, help="Update server URL (Linux only)")
    parser.add_argument(
        "--experiment", action="store_true", help="Build in experiment mode (hides Options tab)"
    )

    args = parser.parse_args()

    # Auto-detect platform if not specified
    if args.platform == "auto":
        if sys.platform == "darwin":
            args.platform = "macos"
        elif sys.platform.startswith("linux"):
            args.platform = "linux"
        elif sys.platform == "win32":
            args.platform = "windows"
        else:
            logger.error(f"Unsupported platform: {sys.platform}")
            return 1

    logger.info(f"Building for platform: {args.platform}")

    # Import and run platform-specific builder
    try:
        if args.platform == "macos":
            from build_macos import MacOSBuilder

            builder = MacOSBuilder(Path(__file__).parent.parent)
            success = builder.build(
                sign_identity=args.sign,
                create_dmg=not args.no_dmg,
                experiment_mode=args.experiment,
                arch=args.arch,
            )

        elif args.platform == "linux":
            from build_linux import LinuxBuilder

            builder = LinuxBuilder(Path(__file__).parent.parent)
            success = builder.build(update_url=args.update_url, create_zsync=not args.no_zsync)

        elif args.platform == "windows":
            WindowsBuilder = _import_windows_builder()

            builder = WindowsBuilder(Path(__file__).parent.parent)
            success = builder.build(
                sign=args.windows_sign,
                certificate=args.windows_certificate,
                cert_password_env=args.windows_cert_password_env,
                signtool=args.windows_signtool,
                verify_signature=args.windows_verify_signature,
                timestamp_url=args.windows_timestamp_url,
            )

        else:
            logger.error(f"Unsupported platform: {args.platform}")
            return 1

        return 0 if success else 1

    except ImportError as e:
        logger.error(f"Failed to import platform builder: {e}")
        logger.error("Make sure all required dependencies are installed.")
        return 1
    except Exception as e:
        logger.error(f"Build failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
