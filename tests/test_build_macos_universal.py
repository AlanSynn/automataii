from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from scripts import build_experiment, build_macos, macos_arch
from scripts.pyinstaller_datas import existing_datas, source_exists


def test_build_executable_passes_universal2_to_pyinstaller(monkeypatch, tmp_path):
    spec_file = tmp_path / "packaging" / "pyinstaller" / "automataii.spec"
    spec_file.parent.mkdir(parents=True)
    spec_file.write_text("# test spec\n")

    builder = build_macos.MacOSBuilder(tmp_path)
    commands: list[list[str]] = []
    envs: list[dict[str, str]] = []

    def fake_run(cmd, cwd=None, check=False, capture_output=False, env=None):
        commands.append(list(cmd))
        envs.append(dict(env or {}))
        builder.app_bundle.mkdir(parents=True)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(build_macos.subprocess, "run", fake_run)

    builder.build_executable(target_arch="universal2")

    assert commands == [
        [
            build_macos.sys.executable,
            "-m",
            "PyInstaller",
            "--clean",
            "--noconfirm",
            str(spec_file),
        ]
    ]
    assert envs[0][macos_arch.PYINSTALLER_TARGET_ARCH_ENV] == "universal2"


def test_build_executable_omits_target_arch_for_auto(monkeypatch, tmp_path):
    spec_file = tmp_path / "packaging" / "pyinstaller" / "automataii.spec"
    spec_file.parent.mkdir(parents=True)
    spec_file.write_text("# test spec\n")

    builder = build_macos.MacOSBuilder(tmp_path)
    commands: list[list[str]] = []
    envs: list[dict[str, str]] = []

    def fake_run(cmd, cwd=None, check=False, capture_output=False, env=None):
        commands.append(list(cmd))
        envs.append(dict(env or {}))
        builder.app_bundle.mkdir(parents=True)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setenv(macos_arch.PYINSTALLER_TARGET_ARCH_ENV, "stale")
    monkeypatch.setattr(build_macos.subprocess, "run", fake_run)

    builder.build_executable(target_arch=None)

    assert "--target-arch" not in commands[0]
    assert macos_arch.PYINSTALLER_TARGET_ARCH_ENV not in envs[0]


def test_universal2_dmg_filename_is_arch_labeled():
    assert macos_arch.dmg_filename("MotionSmith", "universal2") == (
        "MotionSmith-macos-universal2.dmg"
    )


def test_build_scripts_share_macos_arch_choices():
    assert build_macos.MACOS_ARCH_CHOICES is macos_arch.MACOS_ARCH_CHOICES
    assert "universal2" in build_macos.MACOS_ARCH_CHOICES


def test_universal2_python_preflight_rejects_thin_python(monkeypatch, tmp_path):
    builder = build_macos.MacOSBuilder(tmp_path)
    monkeypatch.setattr(build_macos.sys, "platform", "darwin")
    monkeypatch.setattr(build_macos, "is_universal2_capable", lambda: False)

    assert builder.check_architecture_requirements("universal2") is False


def test_universal2_python_preflight_allows_unknown_arch(monkeypatch, tmp_path):
    builder = build_macos.MacOSBuilder(tmp_path)
    monkeypatch.setattr(build_macos.sys, "platform", "darwin")
    monkeypatch.setattr(build_macos, "is_universal2_capable", lambda: None)
    monkeypatch.setattr(build_macos.sys, "version_info", (3, 12, 11, "final", 0))

    assert builder.check_architecture_requirements("universal2") is False


def test_universal2_python_preflight_rejects_non_312_python(monkeypatch, tmp_path):
    builder = build_macos.MacOSBuilder(tmp_path)
    monkeypatch.setattr(build_macos.sys, "platform", "darwin")
    monkeypatch.setattr(build_macos.sys, "version_info", (3, 11, 9, "final", 0))
    monkeypatch.setattr(
        build_macos,
        "is_universal2_capable",
        lambda: (_ for _ in ()).throw(AssertionError("arch check should not run")),
    )

    assert builder.check_architecture_requirements("universal2") is False


def test_universal2_python_preflight_accepts_312_universal(monkeypatch, tmp_path):
    builder = build_macos.MacOSBuilder(tmp_path)
    monkeypatch.setattr(build_macos.sys, "platform", "darwin")
    monkeypatch.setattr(build_macos.sys, "version_info", (3, 12, 11, "final", 0))
    monkeypatch.setattr(build_macos, "is_universal2_capable", lambda: True)

    assert builder.check_architecture_requirements("universal2") is True


def test_clean_preserves_unrelated_dist_artifacts(tmp_path):
    dist_dir = tmp_path / "dist"
    build_dir = tmp_path / "build"
    dist_dir.mkdir()
    build_dir.mkdir()
    wheel = dist_dir / "automataii-0.1.0-py3-none-any.whl"
    wheel.write_text("wheel")
    app = dist_dir / "MotionSmith.app"
    app.mkdir()
    collect_dir = dist_dir / "MotionSmith"
    collect_dir.mkdir()
    exact_dmg = dist_dir / "MotionSmith-macos-x86_64.dmg"
    exact_dmg.write_text("dmg")
    unrelated_dmg = dist_dir / "MotionSmith-macos-universal2.dmg"
    unrelated_dmg.write_text("dmg")

    build_macos.MacOSBuilder(tmp_path).clean(arch_label="x86_64")

    assert wheel.exists()
    assert not app.exists()
    assert not collect_dir.exists()
    assert not exact_dmg.exists()
    assert unrelated_dmg.exists()
    assert not build_dir.exists()


def test_sign_dmg_uses_developer_id_identity(monkeypatch, tmp_path):
    builder = build_macos.MacOSBuilder(tmp_path)
    dmg = tmp_path / "dist" / "MotionSmith-macos-universal2.dmg"
    dmg.parent.mkdir(parents=True)
    dmg.write_text("dmg", encoding="utf-8")
    commands: list[list[str]] = []

    def fake_run(cmd, check=False, **kwargs):
        commands.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(build_macos.subprocess, "run", fake_run)

    builder.sign_dmg("Developer ID Application: Example (TEAMID)", dmg)

    assert commands == [
        [
            "codesign",
            "--force",
            "--sign",
            "Developer ID Application: Example (TEAMID)",
            "--timestamp",
            str(dmg),
        ],
        ["codesign", "--verify", "--verbose=2", str(dmg)],
    ]


def test_build_fails_when_requested_notarization_fails(monkeypatch, tmp_path):
    builder = build_macos.MacOSBuilder(tmp_path)

    monkeypatch.setattr(builder, "check_architecture_requirements", lambda arch: True)
    monkeypatch.setattr(builder, "check_dependencies", lambda: True)
    monkeypatch.setattr(builder, "clean", lambda arch_label=None: None)
    monkeypatch.setattr(builder, "build_executable", lambda target_arch=None: None)
    monkeypatch.setattr(builder, "sign_app", lambda sign_identity: None)

    def fake_create_dmg(arch_label=None, *, strict_distribution=False):
        builder.dist_dir.mkdir(parents=True, exist_ok=True)
        dmg = builder.dist_dir / macos_arch.dmg_filename(builder.app_name, "x86_64")
        dmg.write_text("dmg")
        return dmg

    monkeypatch.setattr(builder, "create_dmg", fake_create_dmg)
    monkeypatch.setattr(builder, "notarize_app_bundle", lambda: True)
    monkeypatch.setattr(builder, "notarize", lambda target_path: False)
    monkeypatch.setattr(build_macos, "host_arch", lambda: "x86_64")

    assert builder.build(arch="x86_64", notarize=True) is False


def test_strict_distribution_implies_release_verification(monkeypatch, tmp_path):
    builder = build_macos.MacOSBuilder(tmp_path)
    verified_targets: list[Path] = []

    monkeypatch.setattr(build_macos, "host_arch", lambda: "x86_64")
    monkeypatch.setattr(builder, "check_architecture_requirements", lambda arch: True)
    monkeypatch.setattr(builder, "check_dependencies", lambda: True)
    monkeypatch.setattr(builder, "clean", lambda arch_label=None: None)
    monkeypatch.setattr(builder, "build_executable", lambda target_arch=None: None)
    monkeypatch.setattr(builder, "sign_app", lambda sign_identity: None)
    monkeypatch.setattr(builder, "sign_dmg", lambda sign_identity, dmg_path: None)

    def fake_create_dmg(arch_label=None, *, strict_distribution=False):
        assert strict_distribution is True
        builder.dist_dir.mkdir(parents=True, exist_ok=True)
        dmg = builder.dist_dir / macos_arch.dmg_filename(builder.app_name, arch_label)
        dmg.write_text("dmg", encoding="utf-8")
        return dmg

    def fake_verify_release_artifact(
        target_path,
        *,
        expected_arch,
        require_notarization,
        require_gatekeeper,
        strict_distribution,
        require_ota=False,
    ):
        verified_targets.append(Path(target_path))
        assert expected_arch == "x86_64"
        assert require_notarization is True
        assert require_gatekeeper is True
        assert strict_distribution is True
        assert require_ota is False
        return True

    monkeypatch.setattr(builder, "create_dmg", fake_create_dmg)
    monkeypatch.setattr(builder, "verify_release_artifact", fake_verify_release_artifact)

    assert builder.build(arch="x86_64", strict_distribution=True) is True
    assert verified_targets == [builder.dist_dir / "MotionSmith-macos-x86_64.dmg"]


def test_create_dmg_fails_when_no_tool_is_available(monkeypatch, tmp_path):
    builder = build_macos.MacOSBuilder(tmp_path)
    builder.app_bundle.mkdir(parents=True)
    monkeypatch.setattr(build_macos.shutil, "which", lambda name: None)

    try:
        builder.create_dmg("universal2")
    except RuntimeError as exc:
        assert "DMG creation tools" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_create_dmg_prefers_branded_dmgbuild_path(monkeypatch, tmp_path):
    builder = build_macos.MacOSBuilder(tmp_path)
    builder.app_bundle.mkdir(parents=True)
    builder.dmg_settings_file.parent.mkdir(parents=True)
    builder.dmg_settings_file.write_text("# settings\n", encoding="utf-8")
    builder.volume_icon_file.parent.mkdir(parents=True)
    builder.volume_icon_file.write_text("icon", encoding="utf-8")
    background = tmp_path / "build" / "dmg-assets" / "dmg-background.png"
    background.parent.mkdir(parents=True)
    background.write_text("background", encoding="utf-8")
    commands: list[list[str]] = []

    monkeypatch.setattr(builder, "_can_use_dmgbuild", lambda: True)
    monkeypatch.setattr(builder, "_create_dmg_background_assets", lambda: background)

    def fake_run(cmd, check=False, cwd=None, **kwargs):
        commands.append(list(cmd))
        dmg_path = Path(cmd[-1])
        dmg_path.parent.mkdir(parents=True, exist_ok=True)
        dmg_path.write_text("dmg", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(build_macos.subprocess, "run", fake_run)

    dmg = builder.create_dmg("universal2")

    assert dmg == tmp_path / "dist" / "MotionSmith-macos-universal2.dmg"
    assert commands == [
        [
            build_macos.sys.executable,
            "-m",
            "dmgbuild",
            "-s",
            str(builder.dmg_settings_file),
            "-D",
            f"app_bundle={builder.app_bundle}",
            "-D",
            f"background_image={background}",
            "-D",
            f"volume_icon={builder.volume_icon_file}",
            "-D",
            f"app_name={builder.app_name}",
            builder.app_name,
            str(dmg),
        ]
    ]


def test_strict_create_dmg_falls_back_when_branded_dmg_has_app_detritus(monkeypatch, tmp_path):
    builder = build_macos.MacOSBuilder(tmp_path)
    builder.app_bundle.mkdir(parents=True)
    builder.dmg_settings_file.parent.mkdir(parents=True)
    builder.dmg_settings_file.write_text("# settings\n", encoding="utf-8")
    background = tmp_path / "build" / "dmg-assets" / "dmg-background.png"
    background.parent.mkdir(parents=True)
    background.write_text("background", encoding="utf-8")
    hdiutil_calls: list[Path] = []

    monkeypatch.setattr(builder, "_can_use_dmgbuild", lambda: True)
    monkeypatch.setattr(builder, "_create_dmg_background_assets", lambda: background)
    monkeypatch.setattr(builder, "_dmg_embedded_app_passes_strict_codesign", lambda dmg: False)

    def fake_run(cmd, check=False, cwd=None, **kwargs):
        dmg_path = Path(cmd[-1])
        dmg_path.parent.mkdir(parents=True, exist_ok=True)
        dmg_path.write_text("branded dmg", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0)

    def fake_hdiutil_dmg(dmg_path: Path) -> Path:
        hdiutil_calls.append(dmg_path)
        dmg_path.write_text("fallback dmg", encoding="utf-8")
        return dmg_path

    monkeypatch.setattr(build_macos.subprocess, "run", fake_run)
    monkeypatch.setattr(builder, "_create_hdiutil_dmg", fake_hdiutil_dmg)

    dmg = builder.create_dmg("arm64", strict_distribution=True)

    assert dmg == tmp_path / "dist" / "MotionSmith-macos-arm64.dmg"
    assert hdiutil_calls == [dmg]
    assert dmg.read_text(encoding="utf-8") == "fallback dmg"


def test_hdiutil_dmg_stages_app_without_extended_attributes(monkeypatch, tmp_path):
    builder = build_macos.MacOSBuilder(tmp_path)
    builder.app_bundle.mkdir(parents=True)
    dmg = tmp_path / "dist" / "MotionSmith-macos-arm64.dmg"
    commands: list[list[str]] = []

    def fake_run(cmd, check=False, **kwargs):
        commands.append(list(cmd))
        if cmd[0] == "ditto":
            staged_app = Path(cmd[-1])
            staged_app.mkdir(parents=True)
        elif cmd[0] == "hdiutil" and cmd[1] == "create":
            Path(cmd[-1]).parent.mkdir(parents=True, exist_ok=True)
            Path(cmd[-1]).write_text("dmg", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(build_macos.subprocess, "run", fake_run)

    assert builder._create_hdiutil_dmg(dmg) == dmg
    assert commands[0][:3] == ["ditto", "--noextattr", "--norsrc"]
    hdiutil_command = next(command for command in commands if command[0:2] == ["hdiutil", "create"])
    assert hdiutil_command[hdiutil_command.index("-srcfolder") + 1].endswith("/root")


def test_hdiutil_dmg_requires_ditto(monkeypatch, tmp_path):
    builder = build_macos.MacOSBuilder(tmp_path)
    builder.app_bundle.mkdir(parents=True)

    monkeypatch.setattr(
        build_macos.shutil,
        "which",
        lambda name: "/usr/bin/hdiutil" if name == "hdiutil" else None,
    )

    with pytest.raises(RuntimeError, match="ditto is required"):
        builder._create_hdiutil_dmg(tmp_path / "dist" / "MotionSmith-macos-arm64.dmg")


def test_dmg_background_assets_include_logo_and_retina_variant(tmp_path):
    from PIL import Image

    builder = build_macos.MacOSBuilder(tmp_path)
    builder.app_icon_file.parent.mkdir(parents=True)
    icon = Image.new("RGBA", (128, 128), (180, 80, 40, 255))
    icon.save(builder.app_icon_file)

    background = builder._create_dmg_background_assets()
    retina = background.with_name("dmg-background@2x.png")

    assert background.exists()
    assert retina.exists()
    assert Image.open(background).size == (520, 340)
    assert Image.open(retina).size == (1040, 680)


def test_existing_datas_skips_missing_sources(tmp_path):
    present_dir = tmp_path / "present"
    present_dir.mkdir()
    missing_dir = tmp_path / "missing"

    assert existing_datas(
        [
            (str(present_dir), "present"),
            (str(missing_dir), "missing"),
        ]
    ) == [(str(present_dir), "present")]


def test_source_exists_supports_globs(tmp_path):
    image = tmp_path / "example.png"
    image.write_text("png", encoding="utf-8")

    assert source_exists(str(tmp_path / "*.png")) is True
    assert source_exists(str(tmp_path / "*.jpg")) is False


def test_pyinstaller_specs_add_project_root_before_helper_import():
    for spec_name in ("automataii.spec", "automataii-experiment.spec"):
        spec_text = (Path("packaging") / "pyinstaller" / spec_name).read_text(encoding="utf-8")

        assert spec_text.index("sys.path.insert(0, str(PROJECT_ROOT))") < spec_text.index(
            "from scripts.pyinstaller_datas import existing_datas"
        )


def test_experiment_fast_pyinstaller_command_omits_spec_invalid_noupx(tmp_path):
    spec_file = tmp_path / "automataii-experiment.spec"
    spec_file.write_text("# spec", encoding="utf-8")

    command = build_experiment._pyinstaller_command(spec_file, fast=True)

    assert str(spec_file) in command
    assert "--clean" not in command
    assert "--noupx" not in command


def test_experiment_full_pyinstaller_command_keeps_clean(tmp_path):
    spec_file = tmp_path / "automataii-experiment.spec"
    spec_file.write_text("# spec", encoding="utf-8")

    command = build_experiment._pyinstaller_command(spec_file, fast=False)

    assert command[-1] == "--clean"
