from __future__ import annotations

import subprocess
from pathlib import Path

from scripts import build_macos, verify_macos_release

from automataii.utils import update_config
from automataii.utils.auto_updater import AutoUpdater


def test_update_config_uses_motionsmith_defaults_and_env_overrides():
    assert update_config.DEFAULT_APPCAST_URL == "https://alansynn.github.io/motionsmith/appcast.xml"
    assert (
        update_config.DEFAULT_RELEASES_URL
        == "https://github.com/AlanSynn/motionsmith/releases/latest"
    )
    assert update_config.configured_appcast_url({}) == update_config.DEFAULT_APPCAST_URL
    assert update_config.configured_update_url({}) == update_config.DEFAULT_RELEASES_URL
    assert (
        update_config.configured_appcast_url({"MOTIONSMITH_APPCAST_URL": " https://e/appcast.xml "})
        == "https://e/appcast.xml"
    )
    assert update_config.ota_enabled({"MOTIONSMITH_OTA_ENABLED": "yes"}) is True


class _FakeSparkleUpdater:
    def __init__(self, automatic: bool) -> None:
        self.automatic = automatic
        self.background_checks = 0
        self.manual_checks = 0

    def automaticallyChecksForUpdates(self) -> bool:
        return self.automatic

    def checkForUpdatesInBackground(self) -> None:
        self.background_checks += 1

    def checkForUpdates_(self, sender: object) -> None:
        self.manual_checks += 1


def test_macos_background_check_respects_sparkle_automatic_state():
    updater = AutoUpdater(None)
    updater.platform = "darwin"
    fake = _FakeSparkleUpdater(automatic=False)
    updater.updater = fake

    assert updater.can_check_for_updates_in_background() is False
    assert updater.check_for_updates(show_ui=False) is False
    assert fake.background_checks == 0

    fake.automatic = True
    assert updater.can_check_for_updates_in_background() is True
    assert updater.check_for_updates(show_ui=False) is True
    assert fake.background_checks == 1


def test_manual_macos_check_uses_controller_when_available():
    updater = AutoUpdater(None)
    updater.platform = "darwin"
    updater.updater = _FakeSparkleUpdater(automatic=True)
    controller = _FakeSparkleUpdater(automatic=True)
    updater._sparkle_controller = controller

    assert updater.check_for_updates(show_ui=True) is True
    assert controller.manual_checks == 1


def test_schedule_startup_update_check_schedules_only_when_allowed():
    from automataii.__main__ import schedule_startup_update_check

    callbacks: list[tuple[int, object]] = []

    class FakeTimer:
        @staticmethod
        def singleShot(delay_ms: int, callback: object) -> None:
            callbacks.append((delay_ms, callback))

    class FakeUpdater:
        def __init__(self, allowed: bool) -> None:
            self.allowed = allowed
            self.checked = False

        def can_check_for_updates_in_background(self) -> bool:
            return self.allowed

        def check_for_updates(self, *, show_ui: bool) -> bool:
            self.checked = not show_ui
            return True

    blocked = FakeUpdater(False)
    assert schedule_startup_update_check(blocked, qtimer_cls=FakeTimer) is False
    assert callbacks == []

    allowed = FakeUpdater(True)
    assert schedule_startup_update_check(allowed, delay_ms=123, qtimer_cls=FakeTimer) is True
    assert callbacks[0][0] == 123
    callbacks[0][1]()
    assert allowed.checked is True


def _write_app_info(app_path: Path, info: str) -> None:
    contents = app_path / "Contents"
    contents.mkdir(parents=True)
    (contents / "Info.plist").write_text(info, encoding="utf-8")


def test_ota_metadata_checks_require_motionsmith_appcast_and_public_key(tmp_path):
    app = tmp_path / "MotionSmith.app"
    _write_app_info(
        app,
        """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>SUFeedURL</key><string>https://alansynn.github.io/motionsmith/appcast.xml</string>
<key>CFBundleShortVersionString</key><string>1.2.3</string>
<key>CFBundleVersion</key><string>123</string>
<key>SUPublicEDKey</key><string>public-key</string>
</dict></plist>
""",
    )

    checks = verify_macos_release._check_update_metadata(
        app,
        require_ota=True,
        expected_appcast_url=update_config.DEFAULT_APPCAST_URL,
    )

    assert all(check.passed and check.required for check in checks)


def test_ota_metadata_checks_fail_when_required_values_are_missing(tmp_path):
    app = tmp_path / "MotionSmith.app"
    _write_app_info(
        app,
        """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>SUFeedURL</key><string>https://example.invalid/appcast.xml</string>
<key>CFBundleShortVersionString</key><string>0.0.0</string>
</dict></plist>
""",
    )

    checks = verify_macos_release._check_update_metadata(
        app,
        require_ota=True,
        expected_appcast_url=update_config.DEFAULT_APPCAST_URL,
    )

    failed_names = {check.name for check in checks if not check.passed and check.required}
    assert failed_names == {
        "appcast_feed_url",
        "bundle_short_version",
        "bundle_version",
        "sparkle_public_key",
    }


def _signed_appcast_xml(
    *,
    artifact: str = "MotionSmith-macos-universal2.dmg",
    version: str = "1.2.3",
    signature: str = "sig",
    length: int = 123,
) -> str:
    return f"""<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0" xmlns:sparkle="{update_config.SPARKLE_NAMESPACE}">
  <channel>
    <item>
      <enclosure
        url="https://github.com/AlanSynn/motionsmith/releases/download/v{version}/{artifact}"
        length="{length}"
        type="application/octet-stream"
        sparkle:version="{version}"
        sparkle:shortVersionString="{version}"
        sparkle:edSignature="{signature}" />
    </item>
  </channel>
</rss>
"""


def test_signed_appcast_validation_requires_expected_artifact_and_version(tmp_path):
    appcast = tmp_path / "appcast.xml"
    appcast.write_text(_signed_appcast_xml(), encoding="utf-8")

    validation = update_config.validate_signed_appcast(
        appcast,
        expected_artifact_name="MotionSmith-macos-universal2.dmg",
        expected_version="v1.2.3",
    )

    assert validation.passed is True
    assert validation.matched_enclosure_count == 1


def test_signed_appcast_validation_rejects_empty_signature(tmp_path):
    appcast = tmp_path / "appcast.xml"
    appcast.write_text(_signed_appcast_xml(signature=""), encoding="utf-8")

    validation = update_config.validate_signed_appcast(
        appcast,
        expected_artifact_name="MotionSmith-macos-universal2.dmg",
        expected_version="1.2.3",
    )

    assert validation.passed is False
    assert any("edSignature" in error for error in validation.errors)


def test_signed_appcast_validation_rejects_mismatched_artifact(tmp_path):
    appcast = tmp_path / "appcast.xml"
    appcast.write_text(_signed_appcast_xml(artifact="OtherApp.dmg"), encoding="utf-8")

    validation = update_config.validate_signed_appcast(
        appcast,
        expected_artifact_name="MotionSmith-macos-universal2.dmg",
        expected_version="1.2.3",
    )

    assert validation.passed is False
    assert validation.matched_enclosure_count == 0
    assert any("expected artifact" in error for error in validation.errors)


def test_signed_appcast_validation_rejects_mismatched_version(tmp_path):
    appcast = tmp_path / "appcast.xml"
    appcast.write_text(_signed_appcast_xml(version="9.9.9"), encoding="utf-8")

    validation = update_config.validate_signed_appcast(
        appcast,
        expected_artifact_name="MotionSmith-macos-universal2.dmg",
        expected_version="1.2.3",
    )

    assert validation.passed is False
    assert any("does not match" in error for error in validation.errors)


def test_signed_appcast_validation_rejects_http_enclosure_url(tmp_path):
    appcast = tmp_path / "appcast.xml"
    appcast.write_text(
        _signed_appcast_xml().replace(
            "https://github.com/AlanSynn/motionsmith/releases/download/",
            "http://github.com/AlanSynn/motionsmith/releases/download/",
        ),
        encoding="utf-8",
    )

    validation = update_config.validate_signed_appcast(
        appcast,
        expected_artifact_name="MotionSmith-macos-universal2.dmg",
        expected_version="1.2.3",
    )

    assert validation.passed is False
    assert any("HTTPS" in error for error in validation.errors)


def test_strict_ota_build_inputs_require_sparkle_key_framework_and_signed_appcast(
    monkeypatch, tmp_path
):
    builder = build_macos.MacOSBuilder(tmp_path)
    appcast = tmp_path / "appcast.xml"
    appcast.write_text(_signed_appcast_xml(), encoding="utf-8")
    framework = tmp_path / "Sparkle.framework"
    framework.mkdir()

    monkeypatch.setenv("SPARKLE_FRAMEWORK_PATH", str(framework))
    monkeypatch.setenv("SPARKLE_PUBLIC_ED_KEY", "public")
    monkeypatch.setenv("MOTIONSMITH_SIGNED_APPCAST_PATH", str(appcast))

    assert (
        builder.check_ota_build_inputs(
            True,
            "Developer ID Application: Example (TEAMID)",
            notarize=True,
            create_dmg=True,
            expected_artifact_name="MotionSmith-macos-universal2.dmg",
            expected_version="1.2.3",
        )
        is True
    )


def test_strict_ota_build_inputs_reject_unsigned_appcast(monkeypatch, tmp_path):
    builder = build_macos.MacOSBuilder(tmp_path)
    appcast = tmp_path / "appcast.xml"
    appcast.write_text("<rss />", encoding="utf-8")
    framework = tmp_path / "Sparkle.framework"
    framework.mkdir()

    monkeypatch.setenv("SPARKLE_FRAMEWORK_PATH", str(framework))
    monkeypatch.setenv("SPARKLE_PUBLIC_ED_KEY", "public")
    monkeypatch.setenv("MOTIONSMITH_SIGNED_APPCAST_PATH", str(appcast))

    assert (
        builder.check_ota_build_inputs(
            True,
            "Developer ID Application: Example (TEAMID)",
            notarize=True,
            create_dmg=True,
            expected_artifact_name="MotionSmith-macos-universal2.dmg",
            expected_version="1.2.3",
        )
        is False
    )


def test_build_script_embeds_sparkle_framework_with_ditto(monkeypatch, tmp_path):
    builder = build_macos.MacOSBuilder(tmp_path)
    source = tmp_path / "vendor" / "Sparkle.framework"
    source.mkdir(parents=True)
    builder.app_bundle = tmp_path / "dist" / "MotionSmith.app"
    builder.app_bundle.mkdir(parents=True)
    commands: list[list[str]] = []

    monkeypatch.setenv("SPARKLE_FRAMEWORK_PATH", str(source))
    monkeypatch.setattr(
        build_macos.shutil, "which", lambda name: "/usr/bin/ditto" if name == "ditto" else None
    )

    def fake_run(cmd, check=False, **kwargs):
        commands.append(list(cmd))
        destination = Path(cmd[-1])
        destination.mkdir(parents=True)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(build_macos.subprocess, "run", fake_run)

    assert builder.embed_sparkle_framework(require_ota=True) is True
    assert commands == [
        [
            "ditto",
            str(source),
            str(builder.app_bundle / "Contents" / "Frameworks" / "Sparkle.framework"),
        ]
    ]


def test_pipeline_files_are_not_using_stale_appcast_targets_or_dsa_signatures():
    files = [
        Path("scripts/generate_appcast.py"),
        Path(".github/workflows/release.yml"),
        Path(".github/workflows/build-and-release.yml"),
        Path(".github/workflows/macos-arch-build.yml"),
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in files)

    assert "automataii/automataii" not in text
    assert "sparkle:dsaSignature" not in text
    assert "dist/Automataii-macos" not in text
    assert "https://alansynn.github.io/motionsmith/" in text

    release_workflow = Path(".github/workflows/release.yml").read_text(encoding="utf-8")
    build_release_workflow = Path(".github/workflows/build-and-release.yml").read_text(
        encoding="utf-8"
    )
    assert "signed_appcast_url" in release_workflow
    assert "signed-appcast/appcast.xml" in release_workflow
    assert "diagnostic-appcast" in release_workflow
    assert "appcast/*" not in release_workflow
    assert "path: appcast\n" not in release_workflow
    assert "validate_appcast.py" in release_workflow
    assert "inputs.publish_external == 'true'" not in release_workflow
    assert "curl --proto '=https' --proto-redir '=https'" in release_workflow
    assert "ota_smoke_passed" in release_workflow
    assert "MOTIONSMITH_OTA_ENABLED" in release_workflow
    assert "MOTIONSMITH_SIGNED_APPCAST_PATH" in release_workflow
    assert "SPARKLE_PUBLIC_ED_KEY" in release_workflow

    assert "signed_appcast_url" in build_release_workflow
    assert "signed-appcast/appcast.xml" in build_release_workflow
    assert "inputs.create_release == 'true'" not in build_release_workflow
    assert "SPARKLE_ED_SIGNATURE" not in build_release_workflow
    assert "ED_SIGNATURE" not in build_release_workflow
    assert "curl --proto '=https' --proto-redir '=https'" in build_release_workflow
    assert "ota_smoke_passed" in build_release_workflow
    assert "MOTIONSMITH_OTA_ENABLED" in build_release_workflow
    assert "MOTIONSMITH_SIGNED_APPCAST_PATH" in build_release_workflow
    assert "SPARKLE_PUBLIC_ED_KEY" in build_release_workflow
    assert "This version includes automatic update checking" not in build_release_workflow
    assert "production OTA notification is gated" in build_release_workflow
    assert "validate_appcast.py" in build_release_workflow


def test_pyinstaller_spec_declares_sparkle_metadata_without_hardcoded_public_key():
    spec_text = Path("packaging/pyinstaller/automataii.spec").read_text(encoding="utf-8")

    assert "SUFeedURL" in spec_text
    assert "CFBundleVersion" in spec_text
    assert "sparkle_public_ed_key(os.environ)" in spec_text
    assert 'SUPublicEDKey": "' not in spec_text
