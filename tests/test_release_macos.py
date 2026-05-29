from __future__ import annotations

import json
import shlex
from pathlib import Path

from scripts import release_macos


def test_parse_env_file_supports_quoted_release_values(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        """
# local release defaults
export APPLE_NOTARY_PROFILE="AutomataiiNotary"
APPLE_TEAM_ID=DE4Q8RKZ4M
MACOS_SIGN_IDENTITY="Developer ID Application: Doang-Joo Synn (DE4Q8RKZ4M)"
""",
        encoding="utf-8",
    )

    parsed = release_macos.parse_env_file(env_file)

    assert parsed["APPLE_NOTARY_PROFILE"] == "AutomataiiNotary"
    assert parsed["APPLE_TEAM_ID"] == "DE4Q8RKZ4M"
    assert parsed["MACOS_SIGN_IDENTITY"] == (
        "Developer ID Application: Doang-Joo Synn (DE4Q8RKZ4M)"
    )


def test_build_config_loads_dotenv_and_defaults_to_universal2_uv_env(tmp_path):
    (tmp_path / ".env").write_text(
        """
APPLE_NOTARY_PROFILE="AutomataiiNotary"
MACOS_SIGN_IDENTITY="Developer ID Application: Example (TEAMID)"
""",
        encoding="utf-8",
    )
    args = release_macos.parse_args(
        [
            "--project-root",
            str(tmp_path),
            "--timestamp",
            "20260528T000000Z",
            "--dry-run",
        ]
    )

    config = release_macos.build_config(args, {})

    assert config.arch == "universal2"
    assert config.sign_identity == "Developer ID Application: Example (TEAMID)"
    assert config.notary_profile == "AutomataiiNotary"
    assert config.uv_project_environment == ".venv-universal2"
    assert config.artifact_path == tmp_path / "dist" / "Automataii-macos-universal2.dmg"


def test_release_env_keeps_process_overrides_over_dotenv(tmp_path):
    (tmp_path / ".env").write_text(
        """
APPLE_NOTARY_PROFILE="DotEnvProfile"
MACOS_SIGN_IDENTITY="Developer ID Application: DotEnv (TEAMID)"
""",
        encoding="utf-8",
    )
    args = release_macos.parse_args(
        ["--project-root", str(tmp_path), "--timestamp", "20260528T000000Z"]
    )
    base_env = {
        "APPLE_NOTARY_PROFILE": "ProcessProfile",
        "MACOS_SIGN_IDENTITY": "Developer ID Application: Process (TEAMID)",
    }
    config = release_macos.build_config(args, base_env)

    env = release_macos.release_env(config, base_env)

    assert config.notary_profile == "ProcessProfile"
    assert config.sign_identity == "Developer ID Application: Process (TEAMID)"
    assert env["APPLE_NOTARY_PROFILE"] == "ProcessProfile"
    assert env["MACOS_SIGN_IDENTITY"] == "Developer ID Application: Process (TEAMID)"


def test_build_and_verify_commands_are_distribution_strict(tmp_path):
    config = release_macos.ReleaseConfig(
        project_root=tmp_path,
        env_file=tmp_path / ".env",
        arch="universal2",
        sign_identity="Developer ID Application: Example (TEAMID)",
        notary_profile="AutomataiiNotary",
        uv_project_environment=".venv-universal2",
        sync=True,
        notarize=True,
        strict_distribution=True,
        smoke=True,
        profile_check=True,
        dry_run=True,
        timestamp="20260528T000000Z",
    )

    build_command = release_macos.build_release_command(config)
    verify_command = release_macos.verify_release_command(config)
    rendered = shlex.join(build_command + verify_command)

    assert build_command == [
        "uv",
        "run",
        "python",
        "scripts/build_macos.py",
        "--arch",
        "universal2",
        "--sign",
        "Developer ID Application: Example (TEAMID)",
        "--verify-release",
        "--notarize",
        "--strict-distribution",
    ]
    assert "--require-notarization" in verify_command
    assert "--strict-distribution" in verify_command
    assert "APPLE_APP_SPECIFIC_PASSWORD" not in rendered
    assert "secret" not in rendered.lower()


def test_dry_run_writes_manifest_without_running_release_tools(tmp_path):
    (tmp_path / ".env").write_text(
        """
APPLE_NOTARY_PROFILE="AutomataiiNotary"
MACOS_SIGN_IDENTITY="Developer ID Application: Example (TEAMID)"
""",
        encoding="utf-8",
    )
    args = release_macos.parse_args(
        [
            "--project-root",
            str(tmp_path),
            "--timestamp",
            "20260528T000000Z",
            "--dry-run",
        ]
    )
    config = release_macos.build_config(args, {})

    manifest_path = release_macos.run_release(config, {})
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    log_text = config.log_path.read_text(encoding="utf-8")

    assert manifest["artifact"] == str(tmp_path / "dist" / "Automataii-macos-universal2.dmg")
    assert manifest["sha256"] == "dry-run"
    assert manifest["smoke"]["passed"] is True
    assert "scripts/build_macos.py --arch universal2" in log_text
    assert "notarytool history --keychain-profile AutomataiiNotary" in log_text


def test_makefile_and_docs_route_releases_through_automation_script():
    makefile = Path("Makefile").read_text(encoding="utf-8")
    docs = Path("docs/macos-distribution.md").read_text(encoding="utf-8")

    assert "scripts/release_macos.py" in makefile
    assert "release-macos" in makefile
    assert "make release-macos" in docs
    assert "MACOS_SIGN_IDENTITY" in docs
    assert "Automataii-macos-universal2-release-manifest.json" in docs
    assert "Applications" in docs
