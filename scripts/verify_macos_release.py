#!/usr/bin/env python3
"""Verify macOS app/DMG release readiness for distribution outside the App Store."""

from __future__ import annotations

import argparse
import json
import plistlib
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

try:
    from .macos_arch import MACOS_ARCH_CHOICES, executable_arches
except ImportError:  # pragma: no cover - used when executed as scripts/verify_macos_release.py
    from macos_arch import MACOS_ARCH_CHOICES, executable_arches


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    required: bool
    message: str


@dataclass(frozen=True)
class ReleaseVerification:
    artifact: str
    app_path: str | None
    checks: list[CheckResult]
    distribution_ready: bool

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks if check.required)


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=False, capture_output=True, text=True)


def _combined_output(result: subprocess.CompletedProcess[str]) -> str:
    return "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())


def _tool_exists(name: str) -> bool:
    return shutil.which(name) is not None


def _app_executable(app_path: Path) -> Path | None:
    info_plist = app_path / "Contents" / "Info.plist"
    if not info_plist.exists():
        return None

    with info_plist.open("rb") as handle:
        info = plistlib.load(handle)
    executable_name = info.get("CFBundleExecutable")
    if not isinstance(executable_name, str) or not executable_name:
        return None
    return app_path / "Contents" / "MacOS" / executable_name


def _find_app_in_dmg(
    dmg_path: Path,
) -> tuple[Path | None, str | None, list[CheckResult], tempfile.TemporaryDirectory[str] | None]:
    if not _tool_exists("hdiutil"):
        return (
            None,
            None,
            [CheckResult("dmg_mount", False, True, "hdiutil is required to inspect a DMG.")],
            None,
        )

    checks: list[CheckResult] = []
    with tempfile.TemporaryDirectory(prefix="automataii-dmg-") as mount_dir:
        mount_path = Path(mount_dir)
        attach = _run(
            [
                "hdiutil",
                "attach",
                "-readonly",
                "-nobrowse",
                "-noverify",
                "-mountpoint",
                str(mount_path),
                str(dmg_path),
            ]
        )
        if attach.returncode != 0:
            checks.append(
                CheckResult(
                    "dmg_mount",
                    False,
                    True,
                    f"Failed to mount DMG: {_combined_output(attach)}",
                )
            )
            return None, None, checks, None

        try:
            app_path = next(mount_path.glob("*.app"), None)
            if app_path is None:
                checks.append(CheckResult("dmg_contains_app", False, True, "No .app found in DMG."))
                return None, None, checks, None
            checks.append(CheckResult("dmg_contains_app", True, True, f"Found {app_path.name}."))
            app_copy_dir = tempfile.TemporaryDirectory(prefix="automataii-dmg-app-")
            copied_app = Path(app_copy_dir.name) / app_path.name
            try:
                shutil.copytree(app_path, copied_app, symlinks=True)
            except OSError as exc:
                app_copy_dir.cleanup()
                checks.append(
                    CheckResult(
                        "dmg_extract_app",
                        False,
                        True,
                        f"Failed to copy app out of mounted DMG: {exc}",
                    )
                )
                return None, None, checks, None
            checks.append(
                CheckResult(
                    "dmg_extract_app",
                    True,
                    True,
                    f"Copied {app_path.name} for verification.",
                )
            )
            return copied_app, f"{dmg_path.name}/{app_path.name}", checks, app_copy_dir
        finally:
            detach = _run(["hdiutil", "detach", str(mount_path)])
            if detach.returncode != 0:
                checks.append(
                    CheckResult(
                        "dmg_detach",
                        False,
                        False,
                        f"Failed to detach mounted DMG: {_combined_output(detach)}",
                    )
                )


def _check_codesign(app_path: Path) -> list[CheckResult]:
    if not _tool_exists("codesign"):
        return [CheckResult("codesign_verify", False, True, "codesign is not available.")]

    verify = _run(["codesign", "--verify", "--deep", "--strict", "--verbose=2", str(app_path)])
    checks = [
        CheckResult(
            "codesign_verify",
            verify.returncode == 0,
            True,
            "Signature verification passed."
            if verify.returncode == 0
            else _combined_output(verify),
        )
    ]

    details = _run(["codesign", "-dv", "--verbose=4", str(app_path)])
    details_output = _combined_output(details)
    checks.append(
        CheckResult(
            "codesign_details",
            details.returncode == 0,
            True,
            details_output or "No codesign details returned.",
        )
    )
    checks.append(
        CheckResult(
            "hardened_runtime",
            "runtime" in details_output,
            True,
            "Hardened runtime is enabled."
            if "runtime" in details_output
            else "Hardened runtime flag not found in codesign details.",
        )
    )
    checks.append(
        CheckResult(
            "developer_id_signature",
            "Authority=Developer ID Application:" in details_output,
            True,
            "Developer ID Application signature found."
            if "Authority=Developer ID Application:" in details_output
            else "Developer ID Application authority not found.",
        )
    )
    return checks


def _check_dmg_codesign(dmg_path: Path) -> CheckResult:
    if not _tool_exists("codesign"):
        return CheckResult("dmg_codesign_verify", False, True, "codesign is not available.")

    verify = _run(["codesign", "--verify", "--verbose=2", str(dmg_path)])
    return CheckResult(
        "dmg_codesign_verify",
        verify.returncode == 0,
        True,
        "DMG signature verification passed."
        if verify.returncode == 0
        else _combined_output(verify),
    )


def _check_spctl(app_path: Path, required: bool) -> CheckResult:
    if not _tool_exists("spctl"):
        return CheckResult("gatekeeper_assess", False, required, "spctl is not available.")

    result = _run(["spctl", "--assess", "--type", "execute", "--verbose=4", str(app_path)])
    return CheckResult(
        "gatekeeper_assess",
        result.returncode == 0,
        required,
        _combined_output(result) or "Gatekeeper assessment passed.",
    )


def _check_stapler(path: Path, required: bool) -> CheckResult:
    if not _tool_exists("xcrun"):
        return CheckResult("notarization_staple", False, required, "xcrun is not available.")

    result = _run(["xcrun", "stapler", "validate", str(path)])
    return CheckResult(
        "notarization_staple",
        result.returncode == 0,
        required,
        _combined_output(result) or "Stapled notarization ticket validated.",
    )


def _expected_arch_set(expected_arch: str | None) -> set[str] | None:
    if expected_arch in (None, "auto"):
        return None
    if expected_arch == "universal2":
        return {"arm64", "x86_64"}
    assert expected_arch is not None
    return {expected_arch}


def _check_architecture(app_path: Path, expected_arch: str | None) -> CheckResult:
    executable = _app_executable(app_path)
    if executable is None:
        return CheckResult("architecture", False, True, "Could not locate app executable.")
    if not executable.exists():
        return CheckResult("architecture", False, True, f"Executable not found: {executable}")

    arches = executable_arches(executable)
    if not arches:
        return CheckResult("architecture", False, True, "Could not determine executable arches.")

    expected = _expected_arch_set(expected_arch)
    if expected is None:
        return CheckResult(
            "architecture", True, True, f"Executable arches: {', '.join(sorted(arches))}"
        )

    return CheckResult(
        "architecture",
        expected.issubset(arches),
        True,
        f"Executable arches: {', '.join(sorted(arches))}; expected: {', '.join(sorted(expected))}",
    )


def _check_nested_architectures(app_path: Path, expected_arch: str | None) -> CheckResult | None:
    expected = _expected_arch_set(expected_arch)
    if expected is None:
        return None

    missing: list[str] = []
    checked = 0
    for path in app_path.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        arches = executable_arches(path)
        if not arches:
            continue
        checked += 1
        if not expected.issubset(arches):
            missing.append(
                f"{path.relative_to(app_path)} has {', '.join(sorted(arches))}; "
                f"expected {', '.join(sorted(expected))}"
            )

    if missing:
        preview = "; ".join(missing[:20])
        if len(missing) > 20:
            preview += f"; ... {len(missing) - 20} more"
        return CheckResult(
            "nested_architecture",
            False,
            True,
            f"{len(missing)} of {checked} Mach-O files are missing required slices: {preview}",
        )

    return CheckResult(
        "nested_architecture",
        True,
        True,
        f"All {checked} Mach-O files include expected slices: {', '.join(sorted(expected))}",
    )


def _mach_o_files(app_path: Path) -> list[Path]:
    mach_o_paths: list[Path] = []
    for path in app_path.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        if executable_arches(path):
            mach_o_paths.append(path)
    return mach_o_paths


def _otool_list(path: Path) -> list[str]:
    result = _run(["otool", "-L", str(path)])
    if result.returncode != 0:
        return []

    dependencies: list[str] = []
    for line in result.stdout.splitlines()[1:]:
        stripped = line.strip()
        if not stripped:
            continue
        dependencies.append(stripped.split(" (", 1)[0])
    return dependencies


def _otool_install_name(path: Path) -> str | None:
    result = _run(["otool", "-D", str(path)])
    if result.returncode != 0:
        return None
    lines = [line.strip() for line in result.stdout.splitlines()[1:] if line.strip()]
    return lines[0] if lines else None


def _otool_rpaths(path: Path, executable_dir: Path) -> list[Path]:
    result = _run(["otool", "-l", str(path)])
    if result.returncode != 0:
        return []

    loader_dir = path.parent
    rpaths: list[Path] = []
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if not stripped.startswith("path "):
            continue
        raw = stripped.removeprefix("path ").split(" (offset", 1)[0]
        if raw.startswith("@loader_path"):
            rpaths.append(loader_dir / raw.removeprefix("@loader_path").lstrip("/"))
        elif raw.startswith("@executable_path"):
            rpaths.append(executable_dir / raw.removeprefix("@executable_path").lstrip("/"))
        else:
            rpaths.append(Path(raw))
    return rpaths


def _is_system_dependency(dependency: str) -> bool:
    return dependency.startswith(("/usr/lib/", "/System/Library/", "/Library/Apple/System/"))


def _resolve_dependency(
    dependency: str,
    loader_path: Path,
    executable_dir: Path,
    rpaths: list[Path],
) -> bool:
    if _is_system_dependency(dependency):
        return True

    if dependency.startswith("@loader_path"):
        return (loader_path.parent / dependency.removeprefix("@loader_path").lstrip("/")).exists()
    if dependency.startswith("@executable_path"):
        return (
            executable_dir / dependency.removeprefix("@executable_path").lstrip("/")
        ).exists()
    if dependency.startswith("@rpath"):
        suffix = dependency.removeprefix("@rpath").lstrip("/")
        return any((rpath / suffix).exists() for rpath in rpaths)
    if dependency.startswith("/"):
        return Path(dependency).exists()
    return (loader_path.parent / dependency).exists()


def _check_dependency_closure(app_path: Path) -> CheckResult:
    if not _tool_exists("otool"):
        return CheckResult("dependency_closure", False, True, "otool is not available.")

    executable = _app_executable(app_path)
    if executable is None or not executable.exists():
        return CheckResult("dependency_closure", False, True, "Could not locate app executable.")

    executable_dir = executable.parent
    executable_rpaths = _otool_rpaths(executable, executable_dir)
    missing: list[str] = []
    checked = 0

    for path in _mach_o_files(app_path):
        install_name = _otool_install_name(path)
        rpaths = [*executable_rpaths, *_otool_rpaths(path, executable_dir)]
        for dependency in _otool_list(path):
            if dependency == install_name:
                continue
            checked += 1
            if not _resolve_dependency(dependency, path, executable_dir, rpaths):
                missing.append(f"{path.relative_to(app_path)} -> {dependency}")

    if missing:
        preview = "; ".join(missing[:20])
        if len(missing) > 20:
            preview += f"; ... {len(missing) - 20} more"
        return CheckResult(
            "dependency_closure",
            False,
            True,
            f"{len(missing)} of {checked} dependencies could not be resolved: {preview}",
        )

    return CheckResult(
        "dependency_closure",
        True,
        True,
        f"All {checked} Mach-O dependencies resolve inside the app bundle or system paths.",
    )


def verify_release(
    artifact: Path,
    expected_arch: str | None = None,
    require_notarization: bool = False,
    require_gatekeeper: bool = True,
) -> ReleaseVerification:
    artifact = artifact.resolve()
    checks: list[CheckResult] = []
    app_copy_dir: tempfile.TemporaryDirectory[str] | None = None

    if not artifact.exists():
        checks.append(
            CheckResult("artifact_exists", False, True, f"Artifact not found: {artifact}")
        )
        return ReleaseVerification(str(artifact), None, checks, False)

    app_path: Path | None
    app_display_path: str | None
    stapler_target = artifact
    try:
        if artifact.suffix == ".app" or artifact.name.endswith(".app"):
            app_path = artifact
            app_display_path = str(app_path)
            checks.append(CheckResult("artifact_type", True, True, "Artifact is an app bundle."))
        elif artifact.suffix == ".dmg":
            app_path, app_display_path, dmg_checks, app_copy_dir = _find_app_in_dmg(artifact)
            checks.extend(dmg_checks)
            checks.append(_check_dmg_codesign(artifact))
        else:
            checks.append(
                CheckResult("artifact_type", False, True, "Artifact must be a .app bundle or .dmg.")
            )
            return ReleaseVerification(str(artifact), None, checks, False)

        if app_path is None:
            return ReleaseVerification(str(artifact), None, checks, False)

        checks.extend(_check_codesign(app_path))
        checks.append(_check_architecture(app_path, expected_arch))
        nested_architecture = _check_nested_architectures(app_path, expected_arch)
        if nested_architecture is not None:
            checks.append(nested_architecture)
        checks.append(_check_dependency_closure(app_path))
        checks.append(_check_spctl(app_path, require_gatekeeper))
        checks.append(_check_stapler(stapler_target, require_notarization))
        if artifact.suffix == ".dmg":
            app_stapler = _check_stapler(app_path, require_notarization)
            checks.append(
                CheckResult(
                    "app_notarization_staple",
                    app_stapler.passed,
                    app_stapler.required,
                    app_stapler.message,
                )
            )

        signed = _check_passed(checks, "codesign_verify")
        developer_id = _check_passed(checks, "developer_id_signature")
        hardened = _check_passed(checks, "hardened_runtime")
        gatekeeper = _check_passed(checks, "gatekeeper_assess")
        stapled = _check_passed(checks, "notarization_staple")
        app_stapled = (
            _check_passed(checks, "app_notarization_staple") if artifact.suffix == ".dmg" else True
        )
        dmg_signed = _check_passed(checks, "dmg_codesign_verify") if artifact.suffix == ".dmg" else True
        nested_arches = (
            _check_passed(checks, "nested_architecture")
            if expected_arch not in (None, "auto")
            else True
        )
        dependencies = _check_passed(checks, "dependency_closure")
        distribution_ready = (
            signed
            and developer_id
            and hardened
            and gatekeeper
            and stapled
            and app_stapled
            and dmg_signed
            and nested_arches
            and dependencies
        )
        return ReleaseVerification(str(artifact), app_display_path, checks, distribution_ready)
    finally:
        if app_copy_dir is not None:
            app_copy_dir.cleanup()


def _check_passed(checks: list[CheckResult], name: str) -> bool:
    return any(check.name == name and check.passed for check in checks)


def _print_human(verification: ReleaseVerification) -> None:
    print(f"Artifact: {verification.artifact}")
    if verification.app_path:
        print(f"App: {verification.app_path}")
    for check in verification.checks:
        status = "PASS" if check.passed else "FAIL"
        required = "required" if check.required else "optional"
        print(f"[{status}] {check.name} ({required}): {check.message}")
    ready = "yes" if verification.distribution_ready else "no"
    print(f"Distribution ready for other Macs: {ready}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify macOS app/DMG release readiness.")
    parser.add_argument("artifact", type=Path, help="Path to .app bundle or .dmg")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of text")
    parser.add_argument(
        "--expected-arch",
        choices=MACOS_ARCH_CHOICES,
        default=None,
        help="Expected executable architecture.",
    )
    parser.add_argument(
        "--require-notarization",
        action="store_true",
        help="Fail if stapled notarization validation does not pass.",
    )
    parser.add_argument(
        "--no-gatekeeper",
        action="store_true",
        help="Do not require spctl Gatekeeper assessment to pass.",
    )
    parser.add_argument(
        "--strict-distribution",
        action="store_true",
        help="Return non-zero unless the artifact is fully distribution-ready.",
    )
    args = parser.parse_args()

    verification = verify_release(
        artifact=args.artifact,
        expected_arch=args.expected_arch,
        require_notarization=args.require_notarization or args.strict_distribution,
        require_gatekeeper=args.strict_distribution or not args.no_gatekeeper,
    )
    if args.json:
        print(json.dumps(asdict(verification), indent=2))
    else:
        _print_human(verification)

    if args.strict_distribution and not verification.distribution_ready:
        return 1
    return 0 if verification.passed else 1


if __name__ == "__main__":
    sys.exit(main())
