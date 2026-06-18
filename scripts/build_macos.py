#!/usr/bin/env python3
"""
macOS build utilities for MotionSmith

Provides a MacOSBuilder class consumed by scripts/build.py and
retains a CLI entrypoint for direct use.
"""

import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from automataii.utils.update_config import (  # noqa: E402
    configured_appcast_url,
    normalize_release_version,
    ota_enabled,
    signed_appcast_path,
    sparkle_public_ed_key,
    validate_signed_appcast,
)

try:
    from .macos_arch import (
        MACOS_ARCH_CHOICES,
        PYINSTALLER_TARGET_ARCH_ENV,
        THIN_MACOS_ARCHES,
        dmg_filename,
        host_arch,
        is_universal2_capable,
        pyinstaller_target_arch,
    )
    from .macos_notary import notarization_credentials_help, notarytool_submit_plan
    from .verify_macos_release import verify_release
except ImportError:  # pragma: no cover - used when executed as scripts/build_macos.py
    from macos_arch import (
        MACOS_ARCH_CHOICES,
        PYINSTALLER_TARGET_ARCH_ENV,
        THIN_MACOS_ARCHES,
        dmg_filename,
        host_arch,
        is_universal2_capable,
        pyinstaller_target_arch,
    )
    from macos_notary import notarization_credentials_help, notarytool_submit_plan
    from verify_macos_release import verify_release

# Logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

SPARKLE_FRAMEWORK_PATH_ENV = "SPARKLE_FRAMEWORK_PATH"


class MacOSBuilder:
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.dist_dir = self.project_root / "dist"
        self.build_dir = self.project_root / "build"
        self.spec_file = self.project_root / "packaging" / "pyinstaller" / "automataii.spec"
        self.entitlements_file = self.project_root / "packaging" / "macos" / "entitlements.plist"
        self.dmg_settings_file = self.project_root / "packaging" / "macos" / "dmg_settings.py"
        self.app_icon_file = self.project_root / "resources" / "icons" / "AppIcon.png"
        self.volume_icon_file = self.project_root / "resources" / "icons" / "AppIcon.icns"
        # Match app name in automataii.spec
        self.app_name = "MotionSmith"
        self.app_bundle = self.dist_dir / f"{self.app_name}.app"

    def ota_enabled(self) -> bool:
        """Return whether strict OTA readiness is required for this build."""
        return ota_enabled(os.environ)

    def sparkle_framework_source(self) -> Path | None:
        """Return the configured Sparkle.framework source, if available."""
        env_path = os.environ.get(SPARKLE_FRAMEWORK_PATH_ENV, "").strip()
        candidates = []
        if env_path:
            candidates.append(Path(env_path))
        candidates.append(self.project_root / "packaging" / "vendor" / "Sparkle.framework")

        for candidate in candidates:
            if candidate.exists() and candidate.name == "Sparkle.framework":
                return candidate
        return None

    def check_ota_build_inputs(
        self,
        require_ota: bool,
        sign_identity: str | None,
        notarize: bool,
        create_dmg: bool,
        expected_artifact_name: str,
        expected_version: str,
    ) -> bool:
        """Validate hard production OTA prerequisites before building."""
        if not require_ota:
            return True

        logger.info("Strict OTA gate enabled; validating Sparkle/update release inputs.")
        missing: list[str] = []
        if not sign_identity:
            missing.append("MACOS_SIGN_IDENTITY / --sign Developer ID identity")
        if not notarize:
            missing.append("--notarize / APPLE_NOTARY_PROFILE notarization path")
        if not create_dmg:
            missing.append("DMG creation")
        if self.sparkle_framework_source() is None:
            missing.append(
                f"Sparkle.framework via {SPARKLE_FRAMEWORK_PATH_ENV} or packaging/vendor"
            )
        if not sparkle_public_ed_key(os.environ):
            missing.append("SPARKLE_PUBLIC_ED_KEY (or SPARKLE_PUBLIC_KEY)")

        appcast_path_value = signed_appcast_path(os.environ)
        if appcast_path_value is not None:
            appcast_path = Path(appcast_path_value)
            if not appcast_path.exists():
                missing.append(f"signed appcast evidence exists at {appcast_path}")
            else:
                appcast_validation = validate_signed_appcast(
                    appcast_path,
                    expected_artifact_name=expected_artifact_name,
                    expected_version=expected_version,
                )
                if not appcast_validation.passed:
                    missing.extend(
                        f"signed appcast validation: {error}" for error in appcast_validation.errors
                    )

        if missing:
            logger.error(
                "Strict OTA gate failed for appcast %s. Missing: %s",
                configured_appcast_url(os.environ),
                "; ".join(missing),
            )
            return False
        return True

    def project_version(self) -> str:
        """Return the project version from pyproject.toml."""
        pyproject = self.project_root / "pyproject.toml"
        try:
            import tomllib

            with pyproject.open("rb") as handle:
                version = tomllib.load(handle).get("project", {}).get("version")
            if isinstance(version, str) and version:
                return normalize_release_version(version) or "0.1.1"
        except Exception:
            pass
        return "0.1.1"

    def release_version(self) -> str:
        """Return the expected appcast/bundle version for this build."""
        return (
            normalize_release_version(os.environ.get("MOTIONSMITH_VERSION"))
            or self.project_version()
        )

    def embed_sparkle_framework(self, require_ota: bool) -> bool:
        """Copy Sparkle.framework into the app bundle when configured."""
        source = self.sparkle_framework_source()
        if source is None:
            if require_ota:
                logger.error(
                    "Strict OTA gate requires Sparkle.framework. Set %s or vendor it under "
                    "packaging/vendor/Sparkle.framework.",
                    SPARKLE_FRAMEWORK_PATH_ENV,
                )
                return False
            logger.info("Sparkle.framework not configured; macOS OTA runtime remains disabled.")
            return True

        destination = self.app_bundle / "Contents" / "Frameworks" / "Sparkle.framework"
        if source.resolve() == destination.resolve():
            logger.info("Sparkle.framework already embedded at %s", destination)
            return True

        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            shutil.rmtree(destination)

        if shutil.which("ditto") is not None:
            subprocess.run(["ditto", str(source), str(destination)], check=True)
        else:
            shutil.copytree(source, destination, symlinks=True)
        logger.info("Embedded Sparkle.framework: %s -> %s", source, destination)
        return True

    def check_dependencies(self) -> bool:
        """Check for required tools."""
        logger.info("Checking dependencies...")
        # PyInstaller
        try:
            subprocess.run(
                [sys.executable, "-c", "import PyInstaller"], check=True, capture_output=True
            )
            logger.info("✓ PyInstaller is available")
        except subprocess.CalledProcessError:
            logger.error("✗ PyInstaller not found. Install with: uv add pyinstaller")
            return False
        return True

    def check_architecture_requirements(self, arch: str) -> bool:
        """Validate architecture-specific prerequisites before destructive cleanup."""
        if arch != "universal2" or sys.platform != "darwin":
            return True

        if sys.version_info[:2] != (3, 12):
            logger.error(
                "Universal2 release builds require Python 3.12; active Python is %s.%s.",
                sys.version_info[0],
                sys.version_info[1],
            )
            return False

        capable = is_universal2_capable()
        if capable is True:
            return True

        logger.error(
            "Universal2 build requires a Python executable with both arm64 and x86_64 slices. "
            "Install/use a universal2 Python environment, rerun uv sync there, then retry."
        )
        return False

    def clean(self, arch_label: str | None = None):
        """Remove previous app build artifacts without deleting unrelated dist files."""
        logger.info("Cleaning previous build artifacts...")
        if self.build_dir.exists():
            shutil.rmtree(self.build_dir)
        for app_name in (f"{self.app_name}.app", "AutomataII.app", "Automataii.app"):
            app_path = self.dist_dir / app_name
            if app_path.exists():
                shutil.rmtree(app_path)
        for collect_name in (self.app_name, "AutomataII", "Automataii"):
            collect_path = self.dist_dir / collect_name
            if collect_path.is_dir():
                shutil.rmtree(collect_path)
            elif collect_path.exists():
                collect_path.unlink()
        if arch_label is None:
            dmg_paths = []
        else:
            dmg_paths = [self.dist_dir / dmg_filename(self.app_name, arch_label)]
        for dmg_path in dmg_paths:
            if dmg_path.exists():
                dmg_path.unlink()
        logger.info("Clean complete")

    def clean_all_release_dmgs(self) -> None:
        """Explicitly remove all MotionSmith/legacy Automataii macOS DMGs.

        The normal build path intentionally deletes only the requested target
        DMG to avoid surprising local artifact loss.
        """
        for pattern in ("MotionSmith*.dmg", "Automataii*.dmg", "AutomataII*.dmg"):
            for dmg_path in self.dist_dir.glob(pattern):
                dmg_path.unlink()

    def build_executable(self, target_arch: str | None = None):
        """Run PyInstaller with the project spec file."""
        if not self.spec_file.exists():
            raise FileNotFoundError(f"Spec file not found: {self.spec_file}")

        cmd = [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm"]
        env = os.environ.copy()
        env.pop(PYINSTALLER_TARGET_ARCH_ENV, None)
        if target_arch:
            env[PYINSTALLER_TARGET_ARCH_ENV] = target_arch
        cmd.append(str(self.spec_file))
        logger.info(f"Running: {' '.join(cmd)}")
        subprocess.run(cmd, cwd=self.project_root, check=True, env=env)

        if not self.app_bundle.exists():
            # Allow for case mismatch fallback
            alt_app = self.dist_dir / "AutomataII.app"
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
        nested_code = self._nested_macho_files()
        if nested_code:
            logger.info("Signing nested Mach-O files: %s", len(nested_code))
            for code_path in nested_code:
                self._codesign_path(code_path, sign_identity)
        nested_bundles = self._nested_code_bundle_targets()
        if nested_bundles:
            logger.info("Signing nested code bundles/frameworks: %s", len(nested_bundles))
            for code_path in nested_bundles:
                self._codesign_path(code_path, sign_identity)
        logger.info(f"Signing app with identity: {sign_identity}")
        cmd = [
            "codesign",
            "--deep",
            "--force",
            "--options",
            "runtime",
            "--sign",
            sign_identity,
        ]
        if self.entitlements_file.exists():
            cmd.extend(["--entitlements", str(self.entitlements_file)])
        cmd.append(str(self.app_bundle))
        # Timestamp if available (non-fatal if not)
        try:
            subprocess.run(cmd + ["--timestamp"], check=True)
        except subprocess.CalledProcessError:
            subprocess.run(cmd, check=True)
        logger.info("✓ Codesign complete")

    @staticmethod
    def _codesign_path(code_path: Path, sign_identity: str) -> None:
        cmd = [
            "codesign",
            "--force",
            "--options",
            "runtime",
            "--sign",
            sign_identity,
            str(code_path),
        ]
        try:
            subprocess.run(cmd + ["--timestamp"], check=True)
        except subprocess.CalledProcessError:
            subprocess.run(cmd, check=True)

    def _nested_code_bundle_targets(self) -> list[Path]:
        """Return nested code bundles that need their own signatures."""
        if not self.app_bundle.exists():
            return []

        suffixes = (".framework", ".xpc", ".appex", ".app", ".bundle")
        targets: list[Path] = []
        for path in self.app_bundle.rglob("*"):
            if path == self.app_bundle:
                continue
            if not path.is_dir() or path.is_symlink():
                continue
            if path.name.endswith(suffixes):
                targets.append(path)
        return sorted(targets, key=lambda item: len(item.parts), reverse=True)

    def _nested_macho_files(self) -> list[Path]:
        """Return Mach-O files inside the app that need explicit signing.

        PyInstaller onedir bundles contain extension modules and dylibs that
        are loaded directly by the hardened runtime. A final `codesign --deep`
        on the .app is not sufficient on all macOS versions; unsigned nested
        .so/.dylib files can still fail library validation at launch.
        """
        if not self.app_bundle.exists():
            return []

        files: list[Path] = []
        for path in self.app_bundle.rglob("*"):
            if not path.is_file() or path.is_symlink():
                continue
            if self._is_macho_file(path):
                files.append(path)
        # Sign deeper paths first so the final bundle signature seals the
        # already-signed nested code.
        return sorted(files, key=lambda item: len(item.parts), reverse=True)

    @staticmethod
    def _is_macho_file(path: Path) -> bool:
        result = subprocess.run(
            ["lipo", "-archs", str(path)],
            check=False,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0 and bool(result.stdout.strip())

    def create_dmg(
        self,
        arch_label: str | None = None,
        *,
        strict_distribution: bool = False,
    ) -> Path:
        """Create a DMG for the built app using hdiutil (fallback if create-dmg not installed).

        If arch_label is provided, name output as 'MotionSmith-macos-<arch>.dmg'.
        """
        dmg_path = self.dist_dir / dmg_filename(self.app_name, arch_label)
        # Remove existing DMG
        if dmg_path.exists():
            dmg_path.unlink()

        if self._can_use_dmgbuild():
            branded_dmg = self._create_branded_dmg(dmg_path)
            if not strict_distribution:
                return branded_dmg
            if self._dmg_embedded_app_passes_strict_codesign(branded_dmg):
                return branded_dmg

            logger.warning(
                "Branded DMG leaves Finder metadata on the embedded app, which breaks "
                "strict codesign verification after copy. Falling back to hdiutil DMG."
            )
            branded_dmg.unlink(missing_ok=True)
            return self._create_hdiutil_dmg(dmg_path)

        # Prefer hdiutil (standard on macOS)
        if shutil.which("hdiutil") is not None:
            return self._create_hdiutil_dmg(dmg_path)

        # Optional: use create-dmg if present
        if shutil.which("create-dmg") is not None:
            cmd = [
                "create-dmg",
                "--overwrite",
                "--volname",
                self.app_name,
                str(dmg_path),
                str(self.app_bundle),
            ]
            logger.info(f"Creating DMG with create-dmg: {' '.join(cmd)}")
            subprocess.run(cmd, check=True)
            if not dmg_path.exists():
                raise FileNotFoundError(f"Requested DMG was not created: {dmg_path}")
            logger.info(f"✓ DMG created at {dmg_path}")
            return dmg_path

        raise RuntimeError("DMG creation tools not found (hdiutil/create-dmg).")

    def _create_hdiutil_dmg(self, dmg_path: Path) -> Path:
        """Create a distribution DMG without Finder metadata on the signed app bundle."""
        if shutil.which("hdiutil") is None:
            raise RuntimeError("hdiutil is required to create a distribution DMG.")
        if shutil.which("ditto") is None:
            raise RuntimeError("ditto is required to stage the app without extended attributes.")

        with tempfile.TemporaryDirectory(prefix="motionsmith-dmg-root-") as temp_dir:
            staging_root = Path(temp_dir) / "root"
            staging_root.mkdir()
            staged_app = staging_root / self.app_bundle.name
            # Drop extended attributes/resource forks when staging the app. These
            # are not part of the code signature and can make `codesign --strict`
            # reject an app copied from the DMG even when Gatekeeper accepts it.
            subprocess.run(
                [
                    "ditto",
                    "--noextattr",
                    "--norsrc",
                    str(self.app_bundle),
                    str(staged_app),
                ],
                check=True,
            )
            if shutil.which("xattr") is not None:
                subprocess.run(["xattr", "-cr", str(staged_app)], check=False)
            (staging_root / "Applications").symlink_to("/Applications")
            output_path = dmg_path.with_name(
                f".{dmg_path.stem}-hdiutil-{os.getpid()}{dmg_path.suffix}"
            )
            output_path.unlink(missing_ok=True)
            cmd = [
                "hdiutil",
                "create",
                "-volname",
                self.app_name,
                "-srcfolder",
                str(staging_root),
                "-ov",
                "-format",
                "UDZO",
                str(output_path),
            ]
            logger.info("Creating DMG: %s", " ".join(cmd))
            for attempt in range(1, 4):
                result = subprocess.run(cmd, check=False, capture_output=True, text=True)
                if result.returncode == 0:
                    stdout = (result.stdout or "").strip()
                    stderr = (result.stderr or "").strip()
                    if stdout:
                        logger.info(stdout)
                    if stderr:
                        logger.info(stderr)
                    break

                output = "\n".join(
                    part.strip() for part in (result.stdout, result.stderr) if part and part.strip()
                )
                if "Resource busy" in output and attempt < 3:
                    logger.warning(
                        "hdiutil create reported Resource busy; retrying DMG creation "
                        "(attempt %s/3).",
                        attempt + 1,
                    )
                    output_path.unlink(missing_ok=True)
                    time.sleep(2)
                    continue

                raise subprocess.CalledProcessError(
                    result.returncode,
                    cmd,
                    output=result.stdout,
                    stderr=result.stderr,
                )
            output_path.replace(dmg_path)
        if not dmg_path.exists():
            raise FileNotFoundError(f"Requested DMG was not created: {dmg_path}")
        logger.info("✓ DMG created at %s", dmg_path)
        return dmg_path

    def _can_use_dmgbuild(self) -> bool:
        """Return whether the branded DMG path can run in the current environment."""
        if sys.platform != "darwin":
            return False
        if not self.dmg_settings_file.exists():
            return False
        if shutil.which("hdiutil") is None:
            return False
        result = subprocess.run(
            [sys.executable, "-c", "import dmgbuild"],
            check=False,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0

    def _create_branded_dmg(self, dmg_path: Path) -> Path:
        """Create a release DMG with branding, background, and Applications link."""
        background_path = self._create_dmg_background_assets()
        volume_icon = self.volume_icon_file if self.volume_icon_file.exists() else ""
        cmd = [
            sys.executable,
            "-m",
            "dmgbuild",
            "-s",
            str(self.dmg_settings_file),
            "-D",
            f"app_bundle={self.app_bundle}",
            "-D",
            f"background_image={background_path}",
            "-D",
            f"volume_icon={volume_icon}",
            "-D",
            f"app_name={self.app_name}",
            self.app_name,
            str(dmg_path),
        ]
        logger.info("Creating branded DMG: %s", " ".join(cmd))
        subprocess.run(cmd, check=True, cwd=self.project_root)
        if not dmg_path.exists():
            raise FileNotFoundError(f"Requested DMG was not created: {dmg_path}")
        logger.info("✓ Branded DMG created at %s", dmg_path)
        return dmg_path

    def _dmg_embedded_app_passes_strict_codesign(self, dmg_path: Path) -> bool:
        """Return whether the app as stored inside the DMG passes strict codesign checks."""
        if shutil.which("hdiutil") is None or shutil.which("codesign") is None:
            return False

        with tempfile.TemporaryDirectory(prefix="motionsmith-dmg-verify-") as mount_dir:
            mount_path = Path(mount_dir)
            attach = subprocess.run(
                [
                    "hdiutil",
                    "attach",
                    "-readonly",
                    "-nobrowse",
                    "-noverify",
                    "-mountpoint",
                    str(mount_path),
                    str(dmg_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            if attach.returncode != 0:
                logger.warning(
                    "Could not mount DMG for strict embedded-app check: %s",
                    attach.stderr.strip(),
                )
                return False
            detach_target = str(mount_path)
            for line in attach.stdout.splitlines():
                if line.startswith("/dev/"):
                    detach_target = line.split()[0]
                    break

            try:
                app_path = next(mount_path.glob("*.app"), None)
                if app_path is None:
                    logger.warning("Could not find app inside DMG for strict embedded-app check.")
                    return False
                verify = subprocess.run(
                    ["codesign", "--verify", "--strict", "--verbose=2", str(app_path)],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if verify.returncode == 0:
                    return True
                output = "\n".join(
                    part.strip() for part in (verify.stdout, verify.stderr) if part.strip()
                )
                logger.warning("Embedded app strict codesign check failed: %s", output)
                return False
            finally:
                for attempt in range(1, 4):
                    detach = subprocess.run(
                        ["hdiutil", "detach", detach_target],
                        check=False,
                        capture_output=True,
                        text=True,
                    )
                    if detach.returncode == 0:
                        break
                    if attempt == 3:
                        subprocess.run(
                            ["hdiutil", "detach", "-force", detach_target],
                            check=False,
                            capture_output=True,
                            text=True,
                        )
                    else:
                        time.sleep(1)

    def _create_dmg_background_assets(self) -> Path:
        """Generate deterministic 1x/2x DMG background artwork from the app logo."""
        from PIL import Image, ImageDraw, ImageFont

        assets_dir = self.build_dir / "dmg-assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        background_1x = assets_dir / "dmg-background.png"
        background_2x = assets_dir / "dmg-background@2x.png"
        self._draw_dmg_background(
            background_1x, scale=1, image_module=Image, draw_module=ImageDraw, font_module=ImageFont
        )
        self._draw_dmg_background(
            background_2x, scale=2, image_module=Image, draw_module=ImageDraw, font_module=ImageFont
        )
        return background_1x

    def _draw_dmg_background(
        self,
        output_path: Path,
        *,
        scale: int,
        image_module,
        draw_module,
        font_module,
    ) -> None:
        width, height = 520 * scale, 340 * scale
        image = image_module.new("RGB", (width, height), "#f7f4ee")
        draw = draw_module.Draw(image)

        def xy(value: int) -> int:
            return value * scale

        # Warm branded panel with enough open area for Finder's real icons.
        draw.rounded_rectangle(
            (xy(24), xy(22), xy(496), xy(318)),
            radius=xy(24),
            fill="#fffaf2",
            outline="#e9ddce",
            width=max(1, xy(1)),
        )
        draw.rounded_rectangle(
            (xy(42), xy(38), xy(478), xy(302)),
            radius=xy(18),
            outline="#f1e8dc",
            width=max(1, xy(1)),
        )

        title_font = self._load_font(font_module, 30 * scale, bold=True)
        body_font = self._load_font(font_module, 15 * scale)
        caption_font = self._load_font(font_module, 13 * scale)

        icon_size = xy(58)
        if self.app_icon_file.exists():
            logo = image_module.open(self.app_icon_file).convert("RGBA")
            logo.thumbnail((icon_size, icon_size))
            image.paste(logo, (xy(68), xy(54)), logo)

        draw.text((xy(140), xy(55)), self.app_name, fill="#2b2520", font=title_font)
        draw.text(
            (xy(142), xy(92)),
            "Drag the app into Applications to install.",
            fill="#6a5b4d",
            font=body_font,
        )

        # Arrow between the app icon and the Applications link.
        arrow_color = "#b76e32"
        y = xy(220)
        draw.line((xy(205), y, xy(315), y), fill=arrow_color, width=xy(5))
        draw.polygon(
            [(xy(315), y - xy(15)), (xy(315), y + xy(15)), (xy(344), y)],
            fill=arrow_color,
        )
        draw.text((xy(220), xy(235)), "copy to install", fill="#8d5a32", font=caption_font)

        draw.text((xy(96), xy(286)), self.app_name, fill="#4a4038", font=caption_font)
        draw.text((xy(332), xy(286)), "Applications", fill="#4a4038", font=caption_font)

        image.save(output_path, "PNG", dpi=(72 * scale, 72 * scale))

    @staticmethod
    def _load_font(font_module, size: int, *, bold: bool = False):
        names = (
            [
                "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                "/System/Library/Fonts/Supplemental/Arial.ttf",
            ]
            if bold
            else [
                "/System/Library/Fonts/Supplemental/Arial.ttf",
                "/System/Library/Fonts/Helvetica.ttc",
            ]
        )
        for name in names:
            try:
                return font_module.truetype(name, size)
            except OSError:
                continue
        return font_module.load_default()

    def sign_dmg(self, sign_identity: str | None, dmg_path: Path) -> None:
        """Sign the DMG container when a Developer ID identity is available."""
        if not sign_identity or not dmg_path.exists():
            return

        cmd = [
            "codesign",
            "--force",
            "--sign",
            sign_identity,
            "--timestamp",
            str(dmg_path),
        ]
        logger.info("Signing DMG with identity: %s", sign_identity)
        subprocess.run(cmd, check=True)
        subprocess.run(["codesign", "--verify", "--verbose=2", str(dmg_path)], check=True)
        logger.info("✓ DMG signature verified")

    def _submit_for_notarization(self, target_path: Path) -> bool:
        """Submit the given file to Apple notarization.

        Credentials are taken from environment variables:
        - APPLE_NOTARY_PROFILE, required notarytool keychain profile

        Returns True on success, False otherwise.
        """
        submit_plan = notarytool_submit_plan(target_path)
        if submit_plan is None:
            logger.error(
                "Notarization requested but credentials are missing. %s",
                notarization_credentials_help(),
            )
            return False

        logger.info(
            "Submitting %s for notarization with %s",
            target_path,
            submit_plan.auth_description,
        )
        try:
            subprocess.run(submit_plan.command, check=True)
        except subprocess.CalledProcessError:
            logger.error("Notarization submission failed.")
            return False
        return True

    def notarize(self, target_path: Path) -> bool:
        """Notarize a DMG/zip and staple the same target."""
        if not self._submit_for_notarization(target_path):
            return False

        try:
            subprocess.run(["xcrun", "stapler", "staple", str(target_path)], check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Stapling failed: {e}")
            return False

        logger.info("✓ Notarization and stapling completed")
        return True

    def notarize_app_bundle(self) -> bool:
        """Notarize and staple the app bundle before packaging it in a DMG."""
        if not self.app_bundle.exists():
            logger.error("App bundle not found for notarization: %s", self.app_bundle)
            return False

        with tempfile.TemporaryDirectory(prefix="automataii-app-notary-") as temp_dir:
            zip_path = Path(temp_dir) / f"{self.app_bundle.name}.zip"
            subprocess.run(
                ["ditto", "-c", "-k", "--keepParent", str(self.app_bundle), str(zip_path)],
                check=True,
            )
            if not self._submit_for_notarization(zip_path):
                return False

        try:
            subprocess.run(["xcrun", "stapler", "staple", str(self.app_bundle)], check=True)
        except subprocess.CalledProcessError as e:
            logger.error("App stapling failed: %s", e)
            return False

        logger.info("✓ App notarization and stapling completed")
        return True

    def verify_release_artifact(
        self,
        target_path: Path,
        expected_arch: str,
        require_notarization: bool,
        require_gatekeeper: bool,
        strict_distribution: bool,
        require_ota: bool = False,
    ) -> bool:
        """Run release checks for the built artifact."""
        verification = verify_release(
            target_path,
            expected_arch=expected_arch,
            require_notarization=require_notarization or strict_distribution,
            require_gatekeeper=require_gatekeeper or strict_distribution,
            require_ota=require_ota,
            expected_appcast_url=configured_appcast_url(os.environ),
        )
        for check in verification.checks:
            status = "PASS" if check.passed else "FAIL"
            logger.info("[%s] %s: %s", status, check.name, check.message)
        logger.info("Distribution ready for other Macs: %s", verification.distribution_ready)
        if strict_distribution:
            return verification.distribution_ready
        return verification.passed

    def build(
        self,
        sign_identity: str | None = None,
        create_dmg: bool = True,
        experiment_mode: bool = False,
        editing_mode: bool = False,
        arch: str = "auto",
        notarize: bool = False,
        verify_release_checks: bool = False,
        require_gatekeeper: bool = True,
        strict_distribution: bool = False,
    ) -> bool:
        """Execute the macOS build pipeline."""
        logger.info("=== Starting macOS build ===")
        require_ota = self.ota_enabled()
        if require_ota:
            logger.info("MOTIONSMITH_OTA_ENABLED is enabled; enforcing strict OTA readiness.")
            verify_release_checks = True
            strict_distribution = True
        if strict_distribution and not verify_release_checks:
            logger.info("Strict distribution requested; enabling final release verification.")
            verify_release_checks = True
        current_arch = host_arch()
        if arch == "auto":
            arch = current_arch
        elif arch in THIN_MACOS_ARCHES and arch != current_arch:
            logger.error(
                f"Requested arch '{arch}' does not match host arch '{current_arch}'. macOS cross-compilation is not supported. Build on a native host or use Rosetta for x86_64 builds."
            )
            return False
        if arch == "universal2":
            logger.info(
                "Universal2 build requested; Python and binary dependencies must provide both arm64 and x86_64 slices."
            )
        if notarize and not create_dmg:
            logger.error("Notarization requires a DMG. Remove --no-dmg or disable --notarize.")
            return False
        if not self.check_ota_build_inputs(
            require_ota,
            sign_identity,
            notarize,
            create_dmg,
            expected_artifact_name=dmg_filename(self.app_name, arch),
            expected_version=self.release_version(),
        ):
            return False
        if not self.check_architecture_requirements(arch):
            return False
        if not self.check_dependencies():
            return False
        try:
            self.clean(arch_label=arch)
            self.build_executable(target_arch=pyinstaller_target_arch(arch))
            if not self.embed_sparkle_framework(require_ota):
                return False
            self.sign_app(sign_identity)
            if notarize and not self.notarize_app_bundle():
                return False
            release_target = self.app_bundle
            if create_dmg:
                dmg_path = self.create_dmg(
                    arch_label=arch,
                    strict_distribution=strict_distribution,
                )
                self.sign_dmg(sign_identity, dmg_path)
                release_target = dmg_path
                if notarize:
                    if not self.notarize(dmg_path):
                        return False
            if verify_release_checks and not self.verify_release_artifact(
                release_target,
                expected_arch=arch,
                require_notarization=notarize or strict_distribution,
                require_gatekeeper=require_gatekeeper,
                strict_distribution=strict_distribution,
                require_ota=require_ota,
            ):
                return False
            logger.info("=== macOS build complete ===")
            return True
        except Exception as e:
            logger.error(f"Build error: {e}")
            return False


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Build MotionSmith for macOS")
    parser.add_argument("--sign", type=str, help="Code signing identity (Developer ID)")
    parser.add_argument("--no-dmg", action="store_true", help="Skip DMG creation")
    parser.add_argument(
        "--experiment", action="store_true", help="Build in experiment mode (no-op for macOS)"
    )
    parser.add_argument(
        "--editing", action="store_true", help="Build in edit mode (no-op for macOS)"
    )
    parser.add_argument(
        "--notarize",
        action="store_true",
        help="Notarize the app and DMG (requires APPLE_NOTARY_PROFILE keychain profile)",
    )
    parser.add_argument(
        "--verify-release",
        action="store_true",
        help="Run macOS release checks after building.",
    )
    parser.add_argument(
        "--no-gatekeeper",
        action="store_true",
        help="Do not require spctl Gatekeeper assessment during --verify-release.",
    )
    parser.add_argument(
        "--strict-distribution",
        action="store_true",
        help="Require full distribution readiness, including stapled notarization. Implies --verify-release.",
    )
    parser.add_argument(
        "--arch",
        choices=MACOS_ARCH_CHOICES,
        default="auto",
        help="Target architecture. universal2 builds for Intel and Apple Silicon when dependencies support both slices.",
    )
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent
    builder = MacOSBuilder(project_root)
    success = builder.build(
        sign_identity=args.sign,
        create_dmg=not args.no_dmg,
        experiment_mode=args.experiment,
        editing_mode=args.editing,
        arch=args.arch,
        notarize=args.notarize,
        verify_release_checks=args.verify_release,
        require_gatekeeper=not args.no_gatekeeper,
        strict_distribution=args.strict_distribution,
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
