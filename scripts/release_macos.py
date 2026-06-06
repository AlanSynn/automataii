#!/usr/bin/env python3
"""One-command macOS direct-distribution release automation.

This wrapper intentionally keeps the long-lived release command small:

1. load non-secret defaults from `.env`;
2. preflight the notarytool keychain profile;
3. build/sign/notarize/staple a universal2 DMG;
4. run strict release verification;
5. mount the produced DMG, copy the app out, and run a packaged smoke scenario;
6. write checksums and evidence manifests.

Secrets are not read from logs or written to manifests. Notarization submits use
only a notarytool keychain profile.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

try:
    from .macos_arch import MACOS_ARCH_CHOICES, dmg_filename, host_arch
    from .macos_notary import APPLE_NOTARY_PROFILE_ENV
except ImportError:  # pragma: no cover - used when executed as scripts/release_macos.py
    from macos_arch import MACOS_ARCH_CHOICES, dmg_filename, host_arch
    from macos_notary import APPLE_NOTARY_PROFILE_ENV


SIGN_IDENTITY_ENV = "MACOS_SIGN_IDENTITY"
DEFAULT_NOTARY_PROFILE = "MotionSmith"
DEFAULT_UNIVERSAL2_UV_ENV = ".venv-universal2"
APP_NAME = "MotionSmith"


@dataclass(frozen=True)
class ReleaseConfig:
    project_root: Path
    env_file: Path
    arch: str
    sign_identity: str
    notary_profile: str | None
    uv_project_environment: str | None
    sync: bool
    notarize: bool
    strict_distribution: bool
    smoke: bool
    profile_check: bool
    dry_run: bool
    timestamp: str

    @property
    def evidence_dir(self) -> Path:
        return self.project_root / ".omx" / "evidence" / f"macos-release-{self.timestamp}"

    @property
    def log_path(self) -> Path:
        return self.project_root / ".omx" / "cache" / f"macos-release-{self.timestamp}.log"

    @property
    def resolved_arch_label(self) -> str:
        return host_arch() if self.arch == "auto" else self.arch

    @property
    def artifact_path(self) -> Path:
        return self.project_root / "dist" / dmg_filename(APP_NAME, self.resolved_arch_label)

    @property
    def manifest_path(self) -> Path:
        return (
            self.project_root
            / "dist"
            / f"{APP_NAME}-macos-{self.resolved_arch_label}-release-manifest.json"
        )


@dataclass(frozen=True)
class SmokeResult:
    passed: bool
    evidence_dir: Path
    returncode: int
    app_path: str | None
    output_files: tuple[str, ...]


def parse_env_file(path: Path) -> dict[str, str]:
    """Parse a small shell-compatible .env file without expanding variables."""
    if not path.exists():
        return {}

    parsed: dict[str, str] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped.removeprefix("export ").lstrip()
        if "=" not in stripped:
            raise ValueError(f"Invalid .env line {line_number}: expected KEY=value")

        key, raw_value = stripped.split("=", 1)
        key = key.strip()
        if not key or not key.replace("_", "").isalnum() or key[0].isdigit():
            raise ValueError(f"Invalid .env line {line_number}: invalid key {key!r}")

        value_tokens = shlex.split(raw_value, comments=True, posix=True)
        parsed[key] = value_tokens[0] if value_tokens else ""
    return parsed


def merged_release_env(env_file: Path, base_env: Mapping[str, str]) -> dict[str, str]:
    """Merge `.env` defaults under the process environment.

    Real environment variables win, which allows CI and local overrides without
    rewriting the file.
    """
    merged = dict(parse_env_file(env_file))
    merged.update(base_env)
    return merged


def _timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def build_config(args: argparse.Namespace, env: Mapping[str, str]) -> ReleaseConfig:
    project_root = Path(args.project_root).resolve()
    requested_env_file = Path(args.env_file)
    env_file = (
        requested_env_file
        if requested_env_file.is_absolute()
        else (project_root / requested_env_file).resolve()
    )
    merged_env = merged_release_env(env_file, env)

    sign_identity = _optional_text(args.sign) or _optional_text(merged_env.get(SIGN_IDENTITY_ENV))
    if sign_identity is None:
        raise SystemExit(
            f"{SIGN_IDENTITY_ENV} is required. Set it in {env_file} or pass --sign."
        )

    notary_profile = (
        _optional_text(args.notary_profile)
        or _optional_text(merged_env.get(APPLE_NOTARY_PROFILE_ENV))
        or DEFAULT_NOTARY_PROFILE
    )
    if args.notarize and notary_profile is None:
        raise SystemExit(
            f"{APPLE_NOTARY_PROFILE_ENV} is required for notarized releases. "
            "Store a keychain profile first with make store-notary-profile."
        )

    uv_project_environment = _optional_text(args.uv_project_environment)
    if uv_project_environment is None:
        uv_project_environment = _optional_text(merged_env.get("UV_PROJECT_ENVIRONMENT"))
    if uv_project_environment is None and args.arch == "universal2":
        uv_project_environment = DEFAULT_UNIVERSAL2_UV_ENV

    return ReleaseConfig(
        project_root=project_root,
        env_file=env_file,
        arch=args.arch,
        sign_identity=sign_identity,
        notary_profile=notary_profile if args.notarize else None,
        uv_project_environment=uv_project_environment,
        sync=args.sync,
        notarize=args.notarize,
        strict_distribution=args.strict_distribution,
        smoke=args.smoke,
        profile_check=args.profile_check,
        dry_run=args.dry_run,
        timestamp=args.timestamp or _timestamp(),
    )


def release_env(config: ReleaseConfig, base_env: Mapping[str, str]) -> dict[str, str]:
    env = merged_release_env(config.env_file, base_env)
    env[SIGN_IDENTITY_ENV] = config.sign_identity
    if config.notary_profile:
        env[APPLE_NOTARY_PROFILE_ENV] = config.notary_profile
    if config.uv_project_environment:
        env["UV_PROJECT_ENVIRONMENT"] = config.uv_project_environment
    return env


def sync_command() -> list[str]:
    return ["uv", "sync"]


def profile_check_command(config: ReleaseConfig) -> list[str]:
    if not config.notary_profile:
        raise ValueError("notary profile is required for profile checks")
    return [
        "xcrun",
        "notarytool",
        "history",
        "--keychain-profile",
        config.notary_profile,
        "--output-format",
        "json",
    ]


def build_release_command(config: ReleaseConfig) -> list[str]:
    command = [
        "uv",
        "run",
        "python",
        "scripts/build_macos.py",
        "--arch",
        config.arch,
        "--sign",
        config.sign_identity,
        "--verify-release",
    ]
    if config.notarize:
        command.append("--notarize")
    if config.strict_distribution:
        command.append("--strict-distribution")
    return command


def verify_release_command(config: ReleaseConfig) -> list[str]:
    command = [
        "uv",
        "run",
        "python",
        "scripts/verify_macos_release.py",
        str(config.artifact_path),
        "--expected-arch",
        config.resolved_arch_label,
    ]
    if config.notarize:
        command.append("--require-notarization")
    if config.strict_distribution:
        command.append("--strict-distribution")
    return command


def _log_command(command: Sequence[str], log_file) -> None:
    rendered = shlex.join([str(part) for part in command])
    print(f"$ {rendered}")
    print(f"$ {rendered}", file=log_file, flush=True)


def run_streamed(
    command: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
    log_file,
    dry_run: bool,
) -> None:
    _log_command(command, log_file)
    if dry_run:
        return

    process = subprocess.Popen(
        list(command),
        cwd=cwd,
        env=dict(env),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert process.stdout is not None
    for line in process.stdout:
        print(line, end="")
        print(line, end="", file=log_file)
    returncode = process.wait()
    log_file.flush()
    if returncode != 0:
        raise subprocess.CalledProcessError(returncode, list(command))


def _run_capture(
    command: Sequence[str], *, cwd: Path, env: Mapping[str, str]
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        cwd=cwd,
        env=dict(env),
        check=False,
        capture_output=True,
        text=True,
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def smoke_test_dmg(config: ReleaseConfig, env: Mapping[str, str], log_file) -> SmokeResult:
    smoke_dir = config.evidence_dir / "smoke"
    smoke_dir.mkdir(parents=True, exist_ok=True)
    mount_dir = Path(tempfile.mkdtemp(prefix="automataii-release-mount."))
    copy_dir = Path(tempfile.mkdtemp(prefix="automataii-release-copy."))
    app_copy: Path | None = None
    returncode = 1
    attached = False

    try:
        run_streamed(
            [
                "hdiutil",
                "attach",
                "-readonly",
                "-nobrowse",
                "-noverify",
                "-mountpoint",
                str(mount_dir),
                str(config.artifact_path),
            ],
            cwd=config.project_root,
            env=env,
            log_file=log_file,
            dry_run=config.dry_run,
        )
        attached = not config.dry_run
        if config.dry_run:
            return SmokeResult(True, smoke_dir, 0, None, ())

        app_source = next(mount_dir.glob("*.app"), None)
        if app_source is None:
            raise FileNotFoundError(f"No .app bundle found in mounted DMG: {mount_dir}")

        app_copy = copy_dir / app_source.name
        shutil.copytree(app_source, app_copy, symlinks=True)

        run_streamed(
            ["spctl", "--assess", "--type", "execute", "--verbose=4", str(app_copy)],
            cwd=config.project_root,
            env=env,
            log_file=log_file,
            dry_run=False,
        )
        if config.notarize:
            run_streamed(
                ["xcrun", "stapler", "validate", str(app_copy)],
                cwd=config.project_root,
                env=env,
                log_file=log_file,
                dry_run=False,
            )

        executable = app_copy / "Contents" / "MacOS" / APP_NAME
        stdout_path = smoke_dir / "stdout.txt"
        stderr_path = smoke_dir / "stderr.txt"
        scenario_output = smoke_dir / "blueprint"
        command = [
            str(executable),
            "--scenario",
            "blueprint-export",
            "--scenario-output",
            str(scenario_output),
        ]
        _log_command(command, log_file)
        result = _run_capture(command, cwd=config.project_root, env=env)
        stdout_path.write_text(result.stdout, encoding="utf-8")
        stderr_path.write_text(result.stderr, encoding="utf-8")
        returncode = result.returncode
        if result.returncode != 0:
            raise subprocess.CalledProcessError(result.returncode, command)

        output_files = tuple(_relative_file_paths(smoke_dir))
        return SmokeResult(True, smoke_dir, returncode, str(app_copy), output_files)
    finally:
        if attached:
            detach = subprocess.run(
                ["hdiutil", "detach", str(mount_dir)],
                check=False,
                capture_output=True,
                text=True,
            )
            if detach.returncode != 0:
                print(detach.stdout, end="", file=log_file)
                print(detach.stderr, end="", file=log_file)
        shutil.rmtree(mount_dir, ignore_errors=True)
        shutil.rmtree(copy_dir, ignore_errors=True)


def _relative_file_paths(root: Path) -> list[str]:
    return [str(path.relative_to(root)) for path in sorted(root.rglob("*")) if path.is_file()]


def notary_history(config: ReleaseConfig, env: Mapping[str, str]) -> list[dict[str, str]]:
    if not config.notary_profile:
        return []
    result = _run_capture(profile_check_command(config), cwd=config.project_root, env=env)
    if result.returncode != 0:
        return []
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []
    history = payload.get("history", [])
    if not isinstance(history, list):
        return []

    compact_history: list[dict[str, str]] = []
    for item in history[:8]:
        if not isinstance(item, dict):
            continue
        compact_history.append(
            {
                "id": str(item.get("id", "")),
                "name": str(item.get("name", "")),
                "status": str(item.get("status", "")),
                "createdDate": str(item.get("createdDate", "")),
            }
        )
    return compact_history


def write_manifest(
    config: ReleaseConfig,
    env: Mapping[str, str],
    smoke_result: SmokeResult | None,
) -> Path:
    artifact = config.artifact_path
    if not artifact.exists() and not config.dry_run:
        raise FileNotFoundError(f"Release artifact not found: {artifact}")

    sha256 = "dry-run"
    size_bytes = 0
    if artifact.exists():
        sha256 = sha256_file(artifact)
        size_bytes = artifact.stat().st_size

    manifest: dict[str, object] = {
        "created_at": datetime.now(UTC).isoformat(),
        "artifact": str(artifact),
        "sha256": sha256,
        "size_bytes": size_bytes,
        "arch": config.resolved_arch_label,
        "sign_identity": config.sign_identity,
        "notary_profile": config.notary_profile,
        "uv_project_environment": config.uv_project_environment,
        "strict_distribution": config.strict_distribution,
        "log_path": str(config.log_path),
        "evidence_dir": str(config.evidence_dir),
        "notary_history": notary_history(config, env) if not config.dry_run else [],
        "smoke": None,
    }
    if smoke_result is not None:
        manifest["smoke"] = {
            "passed": smoke_result.passed,
            "returncode": smoke_result.returncode,
            "evidence_dir": str(smoke_result.evidence_dir),
            "app_path": smoke_result.app_path,
            "output_files": list(smoke_result.output_files),
        }

    config.manifest_path.parent.mkdir(parents=True, exist_ok=True)
    config.manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    summary_path = config.evidence_dir / "release-summary.md"
    config.evidence_dir.mkdir(parents=True, exist_ok=True)
    smoke_line = "not run"
    if smoke_result is not None:
        smoke_line = f"passed={smoke_result.passed}, returncode={smoke_result.returncode}"
    summary_path.write_text(
        "\n".join(
            [
                "# macOS release evidence",
                "",
                f"- Artifact: `{artifact}`",
                f"- SHA-256: `{sha256}`",
                f"- Architecture: `{config.resolved_arch_label}`",
                f"- Signing identity: `{config.sign_identity}`",
                f"- Notary profile: `{config.notary_profile}`",
                f"- Strict distribution: `{config.strict_distribution}`",
                f"- Smoke: `{smoke_line}`",
                f"- Log: `{config.log_path}`",
                f"- Manifest: `{config.manifest_path}`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return config.manifest_path


def run_release(config: ReleaseConfig, base_env: Mapping[str, str]) -> Path:
    config.log_path.parent.mkdir(parents=True, exist_ok=True)
    config.evidence_dir.mkdir(parents=True, exist_ok=True)
    env = release_env(config, base_env)
    smoke_result: SmokeResult | None = None

    with config.log_path.open("w", encoding="utf-8") as log_file:
        print(f"Release timestamp: {config.timestamp}", file=log_file)
        print(f"Project root: {config.project_root}", file=log_file)
        print(f"Artifact: {config.artifact_path}", file=log_file)
        if config.uv_project_environment:
            print(f"UV_PROJECT_ENVIRONMENT={config.uv_project_environment}", file=log_file)

        if config.profile_check and config.notarize:
            run_streamed(
                profile_check_command(config),
                cwd=config.project_root,
                env=env,
                log_file=log_file,
                dry_run=config.dry_run,
            )
        if config.sync:
            run_streamed(
                sync_command(),
                cwd=config.project_root,
                env=env,
                log_file=log_file,
                dry_run=config.dry_run,
            )
        run_streamed(
            build_release_command(config),
            cwd=config.project_root,
            env=env,
            log_file=log_file,
            dry_run=config.dry_run,
        )
        run_streamed(
            verify_release_command(config),
            cwd=config.project_root,
            env=env,
            log_file=log_file,
            dry_run=config.dry_run,
        )
        if config.smoke:
            smoke_result = smoke_test_dmg(config, env, log_file)

    return write_manifest(config, env, smoke_result)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build, sign, notarize, staple, verify, and smoke-test a macOS release DMG."
    )
    parser.add_argument("--project-root", default=Path(__file__).parent.parent)
    parser.add_argument("--env-file", default=".env", help="Shell-compatible env file to load.")
    parser.add_argument(
        "--arch",
        choices=MACOS_ARCH_CHOICES,
        default="universal2",
        help="Release architecture. Default is universal2 for Intel + Apple Silicon Macs.",
    )
    parser.add_argument(
        "--sign",
        help=f"Developer ID signing identity. Defaults to {SIGN_IDENTITY_ENV}.",
    )
    parser.add_argument(
        "--notary-profile",
        help=f"notarytool keychain profile. Defaults to {APPLE_NOTARY_PROFILE_ENV}.",
    )
    parser.add_argument(
        "--uv-project-environment",
        help=(
            "uv project environment for child build commands. Defaults to "
            f"{DEFAULT_UNIVERSAL2_UV_ENV!r} for universal2 releases unless already set."
        ),
    )
    parser.add_argument("--timestamp", help="UTC timestamp override for reproducible test paths.")
    parser.add_argument("--skip-sync", dest="sync", action="store_false", help="Skip uv sync.")
    parser.add_argument("--dry-run", action="store_true", help="Print commands and write dry-run manifest.")
    parser.set_defaults(sync=True, notarize=True, strict_distribution=True, smoke=True, profile_check=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        config = build_config(args, os.environ)
        manifest_path = run_release(config, os.environ)
    except (OSError, subprocess.CalledProcessError, ValueError, SystemExit) as exc:
        if isinstance(exc, SystemExit):
            raise
        print(f"macOS release failed: {exc}", file=sys.stderr)
        return 1

    print(f"macOS release automation complete. Manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
