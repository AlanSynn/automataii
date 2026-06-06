from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

from scripts import build_experiment, build_macos, macos_notary
from scripts.verify_macos_release import CheckResult, ReleaseVerification


def test_notarytool_submit_plan_prefers_keychain_profile(tmp_path):
    target = tmp_path / "MotionSmith.dmg"
    env = {
        macos_notary.APPLE_NOTARY_PROFILE_ENV: "MotionSmith",
        macos_notary.APPLE_ID_ENV: "developer@example.com",
        macos_notary.APPLE_TEAM_ID_ENV: "TEAMID",
        macos_notary.APPLE_APP_SPECIFIC_PASSWORD_ENV: "secret-password",
    }

    plan = macos_notary.notarytool_submit_plan(target, env=env)

    assert plan is not None
    assert plan.command == [
        "xcrun",
        "notarytool",
        "submit",
        str(target),
        "--keychain-profile",
        "MotionSmith",
        "--wait",
    ]
    assert "--password" not in plan.command
    assert "secret-password" not in plan.auth_description


def test_notarytool_submit_plan_rejects_password_credentials_without_profile(tmp_path):
    target = tmp_path / "MotionSmith.dmg"
    env = {
        macos_notary.APPLE_ID_ENV: "developer@example.com",
        macos_notary.APPLE_TEAM_ID_ENV: "TEAMID",
        macos_notary.APPLE_APP_SPECIFIC_PASSWORD_ENV: "secret-password",
    }

    plan = macos_notary.notarytool_submit_plan(target, env=env)

    assert plan is None
    assert "secret-password" not in macos_notary.notarization_credentials_help()


def test_notarytool_submit_plan_requires_complete_credentials(tmp_path):
    env = {
        macos_notary.APPLE_ID_ENV: "developer@example.com",
        macos_notary.APPLE_TEAM_ID_ENV: "TEAMID",
    }

    assert macos_notary.notarytool_submit_plan(tmp_path / "MotionSmith.dmg", env=env) is None
    help_text = macos_notary.notarization_credentials_help()
    assert macos_notary.APPLE_NOTARY_PROFILE_ENV in help_text
    assert "make store-notary-profile" in help_text
    assert "notarytool history --keychain-profile" in help_text


def test_builder_notarize_fails_without_running_subprocess(monkeypatch, tmp_path):
    builder = build_macos.MacOSBuilder(tmp_path)
    calls: list[list[str]] = []

    def fake_run(cmd, check=False, **kwargs):
        calls.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(build_macos.subprocess, "run", fake_run)
    for env_name in (
        macos_notary.APPLE_NOTARY_PROFILE_ENV,
        macos_notary.APPLE_ID_ENV,
        macos_notary.APPLE_TEAM_ID_ENV,
        macos_notary.APPLE_APP_SPECIFIC_PASSWORD_ENV,
    ):
        monkeypatch.delenv(env_name, raising=False)

    assert builder.notarize(tmp_path / "MotionSmith.dmg") is False
    assert calls == []


def test_builder_notarize_submits_and_staples_with_profile(monkeypatch, tmp_path):
    builder = build_macos.MacOSBuilder(tmp_path)
    dmg_path = tmp_path / "MotionSmith.dmg"
    commands: list[list[str]] = []

    def fake_run(cmd, check=False, **kwargs):
        commands.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setenv(macos_notary.APPLE_NOTARY_PROFILE_ENV, "MotionSmith")
    monkeypatch.setattr(build_macos.subprocess, "run", fake_run)

    assert builder.notarize(dmg_path) is True
    assert commands == [
        [
            "xcrun",
            "notarytool",
            "submit",
            str(dmg_path),
            "--keychain-profile",
            "MotionSmith",
            "--wait",
        ],
        ["xcrun", "stapler", "staple", str(dmg_path)],
    ]


def test_builder_notarize_app_bundle_zips_submits_and_staples(monkeypatch, tmp_path):
    builder = build_macos.MacOSBuilder(tmp_path)
    builder.app_bundle.mkdir(parents=True)
    commands: list[list[str]] = []

    def fake_run(cmd, check=False, **kwargs):
        commands.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setenv(macos_notary.APPLE_NOTARY_PROFILE_ENV, "MotionSmith")
    monkeypatch.setattr(build_macos.subprocess, "run", fake_run)

    assert builder.notarize_app_bundle() is True
    assert commands[0][:4] == ["ditto", "-c", "-k", "--keepParent"]
    assert commands[1][:4] == ["xcrun", "notarytool", "submit", commands[0][-1]]
    assert commands[1][-3:] == ["--keychain-profile", "MotionSmith", "--wait"]
    assert commands[2] == ["xcrun", "stapler", "staple", str(builder.app_bundle)]


def test_experiment_notarize_fails_without_credentials(monkeypatch, tmp_path):
    commands: list[list[str]] = []

    def fake_run(cmd, check=False, **kwargs):
        commands.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(build_experiment.subprocess, "run", fake_run)
    for env_name in (
        macos_notary.APPLE_NOTARY_PROFILE_ENV,
        macos_notary.APPLE_ID_ENV,
        macos_notary.APPLE_TEAM_ID_ENV,
        macos_notary.APPLE_APP_SPECIFIC_PASSWORD_ENV,
    ):
        monkeypatch.delenv(env_name, raising=False)

    assert build_experiment._notarize_target(tmp_path / "MotionSmith.dmg") is False
    assert commands == []


def test_experiment_notarize_failure_does_not_log_password(monkeypatch, tmp_path, caplog):
    secret = "secret-password"
    env = {
        macos_notary.APPLE_ID_ENV: "developer@example.com",
        macos_notary.APPLE_TEAM_ID_ENV: "TEAMID",
        macos_notary.APPLE_APP_SPECIFIC_PASSWORD_ENV: secret,
    }
    for env_name, value in env.items():
        monkeypatch.setenv(env_name, value)
    monkeypatch.delenv(macos_notary.APPLE_NOTARY_PROFILE_ENV, raising=False)

    def fake_run(cmd, check=False, **kwargs):
        raise subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr(build_experiment.subprocess, "run", fake_run)
    caplog.set_level(logging.ERROR, logger=build_experiment.logger.name)

    assert build_experiment._notarize_target(tmp_path / "MotionSmith.dmg") is False
    assert secret not in caplog.text


def test_experiment_notarize_app_bundle_zips_submits_and_staples(monkeypatch, tmp_path):
    app_bundle = tmp_path / "App.app"
    app_bundle.mkdir()
    commands: list[list[str]] = []

    def fake_run(cmd, check=False, **kwargs):
        commands.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setenv(macos_notary.APPLE_NOTARY_PROFILE_ENV, "MotionSmith")
    monkeypatch.setattr(build_experiment.subprocess, "run", fake_run)

    assert build_experiment._notarize_app_bundle(app_bundle) is True
    assert commands[0][:4] == ["ditto", "-c", "-k", "--keepParent"]
    assert commands[1][:4] == ["xcrun", "notarytool", "submit", commands[0][-1]]
    assert commands[1][-3:] == ["--keychain-profile", "MotionSmith", "--wait"]
    assert commands[2] == ["xcrun", "stapler", "staple", str(app_bundle)]


def test_experiment_create_dmg_stages_app_bundle(monkeypatch, tmp_path):
    app_bundle = tmp_path / "MotionSmith-Experiment.app"
    (app_bundle / "Contents").mkdir(parents=True)
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    commands: list[list[str]] = []

    def fake_which(name: str) -> str | None:
        return "/usr/bin/hdiutil" if name == "hdiutil" else None

    def fake_run(cmd, check=False, **kwargs):
        commands.append(list(cmd))
        source = Path(cmd[cmd.index("-srcfolder") + 1])
        assert source != app_bundle
        assert (source / app_bundle.name).is_dir()
        assert (source / "Applications").is_symlink()
        Path(cmd[-1]).write_bytes(b"dmg")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(build_experiment.shutil, "which", fake_which)
    monkeypatch.setattr(build_experiment.subprocess, "run", fake_run)

    dmg_path = build_experiment._create_dmg(app_bundle, dist_dir, "MotionSmith-Experiment", "arm64")

    assert dmg_path == dist_dir / "MotionSmith-Experiment-macos-arm64.dmg"
    assert commands[0][0] == "hdiutil"


def test_experiment_macos_build_requires_sign_identity(monkeypatch):
    monkeypatch.setattr(build_experiment.sys, "platform", "darwin")
    monkeypatch.setattr(build_experiment.sys, "argv", ["build_experiment.py", "--arch", "arm64"])
    monkeypatch.delenv(build_experiment.SIGN_IDENTITY_ENV, raising=False)
    monkeypatch.setenv(macos_notary.APPLE_NOTARY_PROFILE_ENV, "MotionSmith")

    assert build_experiment.main() is False


def test_experiment_macos_build_requires_notary_profile(monkeypatch):
    monkeypatch.setattr(build_experiment.sys, "platform", "darwin")
    monkeypatch.setattr(build_experiment.sys, "argv", ["build_experiment.py", "--arch", "arm64"])
    monkeypatch.setenv(
        build_experiment.SIGN_IDENTITY_ENV,
        "Developer ID Application: Example (TEAMID)",
    )
    monkeypatch.delenv(macos_notary.APPLE_NOTARY_PROFILE_ENV, raising=False)

    assert build_experiment.main() is False


def test_experiment_macos_build_rejects_no_dmg(monkeypatch):
    monkeypatch.setattr(build_experiment.sys, "platform", "darwin")
    monkeypatch.setattr(build_experiment.sys, "argv", ["build_experiment.py", "--no-dmg"])
    monkeypatch.setenv(
        build_experiment.SIGN_IDENTITY_ENV,
        "Developer ID Application: Example (TEAMID)",
    )
    monkeypatch.setenv(macos_notary.APPLE_NOTARY_PROFILE_ENV, "MotionSmith")

    assert build_experiment.main() is False


def test_experiment_distribution_verification_requires_ready_artifact(monkeypatch, tmp_path):
    dmg_path = tmp_path / "MotionSmith-Experiment-macos-arm64.dmg"
    failing_verification = ReleaseVerification(
        artifact=str(dmg_path),
        app_path=None,
        checks=[CheckResult("codesign_verify", False, True, "Signature failed.")],
        distribution_ready=False,
    )
    monkeypatch.setattr(
        build_experiment,
        "verify_release",
        lambda *args, **kwargs: failing_verification,
    )

    assert build_experiment._verify_distribution_artifact(dmg_path, "arm64") is None


def test_experiment_distribution_manifest_records_strict_release_gate(monkeypatch, tmp_path):
    dmg_path = tmp_path / "MotionSmith-Experiment-macos-arm64.dmg"
    dmg_path.write_bytes(b"release artifact")
    verification = ReleaseVerification(
        artifact=str(dmg_path),
        app_path="MotionSmith-Experiment.app",
        checks=[CheckResult("notarization_staple", True, True, "Stapled.")],
        distribution_ready=True,
    )
    monkeypatch.setenv(macos_notary.APPLE_NOTARY_PROFILE_ENV, "MotionSmith")

    manifest_path = build_experiment._write_distribution_manifest(
        dmg_path,
        tmp_path,
        "arm64",
        "Developer ID Application: Example (TEAMID)",
        verification,
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["artifact"] == str(dmg_path)
    assert manifest["arch"] == "arm64"
    assert manifest["notary_profile"] == "MotionSmith"
    assert manifest["strict_distribution"] is True
    assert manifest["verification"]["distribution_ready"] is True


def test_build_rejects_notarize_without_dmg_before_dependency_checks(monkeypatch, tmp_path):
    builder = build_macos.MacOSBuilder(tmp_path)
    monkeypatch.setattr(build_macos, "host_arch", lambda: "x86_64")
    monkeypatch.setattr(
        builder,
        "check_dependencies",
        lambda: (_ for _ in ()).throw(AssertionError("dependency check should not run")),
    )

    assert builder.build(arch="x86_64", create_dmg=False, notarize=True) is False


def test_build_fails_when_notarization_requested_but_dmg_was_not_created(monkeypatch, tmp_path):
    builder = build_macos.MacOSBuilder(tmp_path)

    monkeypatch.setattr(build_macos, "host_arch", lambda: "x86_64")
    monkeypatch.setattr(builder, "check_architecture_requirements", lambda arch: True)
    monkeypatch.setattr(builder, "check_dependencies", lambda: True)
    monkeypatch.setattr(builder, "clean", lambda arch_label=None: None)
    monkeypatch.setattr(builder, "build_executable", lambda target_arch=None: None)
    monkeypatch.setattr(builder, "sign_app", lambda sign_identity: None)
    monkeypatch.setattr(builder, "notarize_app_bundle", lambda: True)
    monkeypatch.setattr(
        builder,
        "create_dmg",
        lambda arch_label=None, *, strict_distribution=False: (_ for _ in ()).throw(
            FileNotFoundError("missing dmg")
        ),
    )
    monkeypatch.setattr(
        builder,
        "notarize",
        lambda target_path: (_ for _ in ()).throw(AssertionError("notarize should not run")),
    )

    assert builder.build(arch="x86_64", create_dmg=True, notarize=True) is False


def test_release_workflows_accept_notary_profile_or_password_credentials():
    for workflow in (
        ".github/workflows/build-and-release.yml",
        ".github/workflows/release.yml",
        ".github/workflows/macos-arch-build.yml",
    ):
        text = Path(workflow).read_text()
        assert "APPLE_NOTARY_PROFILE" in text
        assert "xcrun notarytool store-credentials" in text


def test_manual_notarize_script_supports_notary_profile():
    text = Path("scripts/sign_notarize_dmg.sh").read_text()

    assert "APPLE_NOTARY_PROFILE" in text
    assert "--keychain-profile" in text
    assert "APPLE_NOTARY_PROFILE is required" in text


def test_macos_distribution_docs_include_profile_storage_and_verification():
    text = Path("docs/macos-distribution.md").read_text()

    assert "make store-notary-profile" in text
    assert "xcrun notarytool history --keychain-profile" in text
    assert "No Keychain password item found for profile" in text
