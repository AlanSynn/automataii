from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from scripts import build_experiment, build_macos, macos_notary


def test_notarytool_submit_plan_prefers_keychain_profile(tmp_path):
    target = tmp_path / "Automataii.dmg"
    env = {
        macos_notary.APPLE_NOTARY_PROFILE_ENV: "AutomataiiNotary",
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
        "AutomataiiNotary",
        "--wait",
    ]
    assert "--password" not in plan.command
    assert "secret-password" not in plan.auth_description


def test_notarytool_submit_plan_rejects_password_credentials_without_profile(tmp_path):
    target = tmp_path / "Automataii.dmg"
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

    assert macos_notary.notarytool_submit_plan(tmp_path / "Automataii.dmg", env=env) is None
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

    assert builder.notarize(tmp_path / "Automataii.dmg") is False
    assert calls == []


def test_builder_notarize_submits_and_staples_with_profile(monkeypatch, tmp_path):
    builder = build_macos.MacOSBuilder(tmp_path)
    dmg_path = tmp_path / "Automataii.dmg"
    commands: list[list[str]] = []

    def fake_run(cmd, check=False, **kwargs):
        commands.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setenv(macos_notary.APPLE_NOTARY_PROFILE_ENV, "AutomataiiNotary")
    monkeypatch.setattr(build_macos.subprocess, "run", fake_run)

    assert builder.notarize(dmg_path) is True
    assert commands == [
        [
            "xcrun",
            "notarytool",
            "submit",
            str(dmg_path),
            "--keychain-profile",
            "AutomataiiNotary",
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

    monkeypatch.setenv(macos_notary.APPLE_NOTARY_PROFILE_ENV, "AutomataiiNotary")
    monkeypatch.setattr(build_macos.subprocess, "run", fake_run)

    assert builder.notarize_app_bundle() is True
    assert commands[0][:4] == ["ditto", "-c", "-k", "--keepParent"]
    assert commands[1][:4] == ["xcrun", "notarytool", "submit", commands[0][-1]]
    assert commands[1][-3:] == ["--keychain-profile", "AutomataiiNotary", "--wait"]
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

    assert build_experiment._notarize_target(tmp_path / "Automataii.dmg") is False
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

    assert build_experiment._notarize_target(tmp_path / "Automataii.dmg") is False
    assert secret not in caplog.text


def test_experiment_notarize_app_bundle_zips_submits_and_staples(monkeypatch, tmp_path):
    app_bundle = tmp_path / "App.app"
    app_bundle.mkdir()
    commands: list[list[str]] = []

    def fake_run(cmd, check=False, **kwargs):
        commands.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setenv(macos_notary.APPLE_NOTARY_PROFILE_ENV, "AutomataiiNotary")
    monkeypatch.setattr(build_experiment.subprocess, "run", fake_run)

    assert build_experiment._notarize_app_bundle(app_bundle) is True
    assert commands[0][:4] == ["ditto", "-c", "-k", "--keepParent"]
    assert commands[1][:4] == ["xcrun", "notarytool", "submit", commands[0][-1]]
    assert commands[1][-3:] == ["--keychain-profile", "AutomataiiNotary", "--wait"]
    assert commands[2] == ["xcrun", "stapler", "staple", str(app_bundle)]


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
        lambda arch_label=None: (_ for _ in ()).throw(FileNotFoundError("missing dmg")),
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
