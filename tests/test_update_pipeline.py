from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from scripts import (
    build_macos,
    check_ota_reachability,
    generate_appcast,
    install_sparkle,
    publish_ota_pages,
    verify_macos_release,
)

from automataii.utils import update_config
from automataii.utils.auto_updater import AutoUpdater


def test_update_config_uses_motionsmith_defaults_and_env_overrides():
    assert update_config.DEFAULT_APPCAST_URL == "https://alansynn.com/motionsmith/appcast.xml"
    assert (
        update_config.DEFAULT_RELEASES_URL
        == "https://github.com/AlanSynn/motionsmith/releases/latest"
    )
    assert update_config.MOTIONSMITH_PAGES_REPO == "AlanSynn/motionsmith"
    assert update_config.MOTIONSMITH_PAGES_BRANCH == "master"
    assert update_config.SPARKLE_VERSION == "2.9.3"
    assert (
        update_config.SPARKLE_DISTRIBUTION_URL
        == "https://github.com/sparkle-project/Sparkle/releases/download/2.9.3/Sparkle-2.9.3.tar.xz"
    )
    assert (
        update_config.SPARKLE_DISTRIBUTION_SHA256
        == "74a07da821f92b79310009954c0e15f350173374a3abe39095b4fc5096916be6"
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
<key>SUFeedURL</key><string>https://alansynn.com/motionsmith/appcast.xml</string>
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
    top_level_version: bool = False,
    notes: str | None = None,
) -> str:
    version_attrs = (
        ""
        if top_level_version
        else (f' sparkle:version="{version}" sparkle:shortVersionString="{version}"')
    )
    item_versions = (
        f"<sparkle:version>{version}</sparkle:version>"
        f"<sparkle:shortVersionString>{version}</sparkle:shortVersionString>"
        if top_level_version
        else ""
    )
    notes_xml = (
        f"<sparkle:releaseNotesLink>{notes}</sparkle:releaseNotesLink>" if notes is not None else ""
    )
    return f"""<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0" xmlns:sparkle="{update_config.SPARKLE_NAMESPACE}">
  <channel>
    <item>
      {item_versions}
      {notes_xml}
      <enclosure
        url="https://alansynn.com/motionsmith/{artifact}"
        length="{length}"
        type="application/octet-stream"{version_attrs}
        sparkle:edSignature="{signature}" />
    </item>
  </channel>
</rss>
"""


def test_signed_appcast_validation_requires_expected_artifact_version_and_pages_payload(tmp_path):
    appcast = tmp_path / "appcast.xml"
    artifact = tmp_path / "MotionSmith-macos-universal2.dmg"
    artifact.write_bytes(b"dmg")
    appcast.write_text(_signed_appcast_xml(), encoding="utf-8")

    validation = update_config.validate_signed_appcast(
        appcast,
        expected_artifact_name="MotionSmith-macos-universal2.dmg",
        expected_version="v1.2.3",
        expected_url_prefix=update_config.UPDATE_SITE_BASE_URL,
        payload_dir=tmp_path,
    )

    assert validation.passed is True
    assert validation.matched_enclosure_count == 1
    assert validation.referenced_urls == (
        "https://alansynn.com/motionsmith/MotionSmith-macos-universal2.dmg",
    )


def test_signed_appcast_validation_accepts_sparkle_top_level_version_shape(tmp_path):
    appcast = tmp_path / "appcast.xml"
    artifact = tmp_path / "MotionSmith-macos-universal2.dmg"
    artifact.write_bytes(b"dmg")
    notes = tmp_path / "MotionSmith-macos-universal2.html"
    notes.write_text("notes", encoding="utf-8")
    appcast.write_text(
        _signed_appcast_xml(
            top_level_version=True,
            notes="https://alansynn.com/motionsmith/MotionSmith-macos-universal2.html",
        ),
        encoding="utf-8",
    )

    validation = update_config.validate_signed_appcast(
        appcast,
        expected_artifact_name="MotionSmith-macos-universal2.dmg",
        expected_version="1.2.3",
        expected_url_prefix=update_config.UPDATE_SITE_BASE_URL,
        payload_dir=tmp_path,
    )

    assert validation.passed is True
    assert len(validation.referenced_urls) == 2


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
            "https://alansynn.com/motionsmith/",
            "http://alansynn.com/motionsmith/",
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


def test_signed_appcast_validation_rejects_missing_pages_payload_file(tmp_path):
    appcast = tmp_path / "appcast.xml"
    appcast.write_text(_signed_appcast_xml(), encoding="utf-8")

    validation = update_config.validate_signed_appcast(
        appcast,
        expected_artifact_name="MotionSmith-macos-universal2.dmg",
        expected_version="1.2.3",
        expected_url_prefix=update_config.UPDATE_SITE_BASE_URL,
        payload_dir=tmp_path,
    )

    assert validation.passed is False
    assert any("missing payload file" in error for error in validation.errors)


@pytest.mark.parametrize(
    "artifact",
    [
        "/MotionSmith-macos-universal2.dmg",
        "MotionSmith-macos-universal2.dmg;evil",
        "MotionSmith-macos-universal2.dmg?download=1",
        "MotionSmith-macos-universal2.dmg#fragment",
    ],
)
def test_signed_appcast_validation_rejects_non_canonical_payload_urls(tmp_path, artifact):
    appcast = tmp_path / "appcast.xml"
    payload = tmp_path / "MotionSmith-macos-universal2.dmg"
    payload.write_bytes(b"dmg")
    appcast.write_text(_signed_appcast_xml(artifact=artifact), encoding="utf-8")

    validation = update_config.validate_signed_appcast(
        appcast,
        expected_artifact_name="MotionSmith-macos-universal2.dmg",
        expected_version="1.2.3",
        expected_url_prefix=update_config.UPDATE_SITE_BASE_URL,
        payload_dir=tmp_path,
    )

    assert validation.passed is False
    assert any("unsafe payload path" in error for error in validation.errors)


@pytest.mark.parametrize(
    "encoded_artifact,raw_payload_parts",
    [
        ("%2e%2e/MotionSmith-macos-universal2.dmg", ("%2e%2e", "MotionSmith-macos-universal2.dmg")),
        (
            "%252e%252e/MotionSmith-macos-universal2.dmg",
            ("%252e%252e", "MotionSmith-macos-universal2.dmg"),
        ),
        (
            "%25252525252e%25252525252e/MotionSmith-macos-universal2.dmg",
            ("%25252525252e%25252525252e", "MotionSmith-macos-universal2.dmg"),
        ),
        (
            "foo/..%2fMotionSmith-macos-universal2.dmg",
            ("foo", "..%2fMotionSmith-macos-universal2.dmg"),
        ),
        (
            "foo%25252525252FMotionSmith-macos-universal2.dmg",
            ("foo%25252525252FMotionSmith-macos-universal2.dmg",),
        ),
        ("%2fMotionSmith-macos-universal2.dmg", ("%2fMotionSmith-macos-universal2.dmg",)),
        ("foo%5cMotionSmith-macos-universal2.dmg", ("foo%5cMotionSmith-macos-universal2.dmg",)),
        (
            "foo%25252525255CMotionSmith-macos-universal2.dmg",
            ("foo%25252525255CMotionSmith-macos-universal2.dmg",),
        ),
    ],
)
def test_signed_appcast_validation_rejects_encoded_unsafe_payload_paths(
    tmp_path, encoded_artifact, raw_payload_parts
):
    appcast = tmp_path / "appcast.xml"
    raw_payload = tmp_path.joinpath(*raw_payload_parts)
    raw_payload.parent.mkdir(parents=True, exist_ok=True)
    raw_payload.write_bytes(b"dmg")
    appcast.write_text(_signed_appcast_xml(artifact=encoded_artifact), encoding="utf-8")

    validation = update_config.validate_signed_appcast(
        appcast,
        expected_artifact_name="MotionSmith-macos-universal2.dmg",
        expected_version="1.2.3",
        expected_url_prefix=update_config.UPDATE_SITE_BASE_URL,
        payload_dir=tmp_path,
    )

    assert validation.passed is False
    assert any("unsafe payload path" in error for error in validation.errors)


@pytest.mark.parametrize(
    "notes_url,raw_notes_parts",
    [
        (
            "https://alansynn.com/motionsmith/%2e%2e/notes.html",
            ("%2e%2e", "notes.html"),
        ),
        (
            "https://alansynn.com/motionsmith/notes%25252525252frelease.html",
            ("notes%25252525252frelease.html",),
        ),
    ],
)
def test_signed_appcast_validation_rejects_encoded_unsafe_release_notes_path(
    tmp_path, notes_url, raw_notes_parts
):
    artifact = tmp_path / "MotionSmith-macos-universal2.dmg"
    raw_notes = tmp_path.joinpath(*raw_notes_parts)
    appcast = tmp_path / "appcast.xml"
    artifact.write_bytes(b"dmg")
    raw_notes.parent.mkdir(parents=True, exist_ok=True)
    raw_notes.write_text("<p>notes</p>", encoding="utf-8")
    appcast.write_text(
        _signed_appcast_xml(notes=notes_url),
        encoding="utf-8",
    )

    validation = update_config.validate_signed_appcast(
        appcast,
        expected_artifact_name="MotionSmith-macos-universal2.dmg",
        expected_version="1.2.3",
        expected_url_prefix=update_config.UPDATE_SITE_BASE_URL,
        payload_dir=tmp_path,
    )

    assert validation.passed is False
    assert any("unsafe payload path" in error for error in validation.errors)


@pytest.mark.parametrize(
    "notes_url",
    [
        "https://alansynn.com/motionsmith//notes.html",
        "https://alansynn.com/motionsmith/notes.html;evil",
    ],
)
def test_signed_appcast_validation_rejects_non_canonical_release_notes_url(tmp_path, notes_url):
    artifact = tmp_path / "MotionSmith-macos-universal2.dmg"
    notes = tmp_path / "notes.html"
    appcast = tmp_path / "appcast.xml"
    artifact.write_bytes(b"dmg")
    notes.write_text("<p>notes</p>", encoding="utf-8")
    appcast.write_text(_signed_appcast_xml(notes=notes_url), encoding="utf-8")

    validation = update_config.validate_signed_appcast(
        appcast,
        expected_artifact_name="MotionSmith-macos-universal2.dmg",
        expected_version="1.2.3",
        expected_url_prefix=update_config.UPDATE_SITE_BASE_URL,
        payload_dir=tmp_path,
    )

    assert validation.passed is False
    assert any("unsafe payload path" in error for error in validation.errors)


def test_strict_ota_build_inputs_require_sparkle_key_framework_but_not_prebuilt_appcast(
    monkeypatch, tmp_path
):
    builder = build_macos.MacOSBuilder(tmp_path)
    framework = tmp_path / "Sparkle.framework"
    framework.mkdir()

    monkeypatch.setenv("SPARKLE_FRAMEWORK_PATH", str(framework))
    monkeypatch.setenv("SPARKLE_PUBLIC_ED_KEY", "public")
    monkeypatch.delenv("MOTIONSMITH_SIGNED_APPCAST_PATH", raising=False)

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


def test_strict_ota_build_inputs_reject_optional_unsigned_appcast_evidence(monkeypatch, tmp_path):
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


def test_generate_appcast_resolves_explicit_sparkle_tool(tmp_path):
    tool = tmp_path / "generate_appcast"
    tool.write_text("#!/bin/sh\n", encoding="utf-8")

    assert generate_appcast.resolve_generate_appcast(str(tool)) == tool.resolve()


def test_generate_production_appcast_uses_official_tool_and_stdin_secret(monkeypatch, tmp_path):
    artifact = tmp_path / "MotionSmith-macos-universal2.dmg"
    artifact.write_bytes(b"dmg")
    tool = tmp_path / "generate_appcast"
    tool.write_text("#!/bin/sh\n", encoding="utf-8")
    calls: list[tuple[list[str], str | None]] = []

    def fake_run(cmd, input=None, **kwargs):
        calls.append((list(cmd), input))
        output_dir = Path(cmd[-1])
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "appcast.xml").write_text(_signed_appcast_xml(), encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setenv("SPARKLE_PRIVATE_ED_KEY", "private-key-material")
    monkeypatch.setattr(generate_appcast.subprocess, "run", fake_run)

    args = generate_appcast.build_parser().parse_args(
        [
            "production",
            "--artifact",
            str(artifact),
            "--output-dir",
            str(tmp_path / "payload"),
            "--expected-version",
            "1.2.3",
            "--sparkle-generate-appcast",
            str(tool),
            "--private-key-env",
            "SPARKLE_PRIVATE_ED_KEY",
        ]
    )
    appcast_path = generate_appcast.generate_production_appcast(args)

    assert appcast_path == tmp_path / "payload" / "appcast.xml"
    command, stdin = calls[0]
    assert command[0] == str(tool.resolve())
    assert "--ed-key-file" in command
    assert "-" in command
    assert "private-key-material" not in command
    assert stdin == "private-key-material"


def test_generate_production_appcast_can_use_keychain_account(monkeypatch, tmp_path):
    artifact = tmp_path / "MotionSmith-macos-universal2.dmg"
    artifact.write_bytes(b"dmg")
    tool = tmp_path / "generate_appcast"
    tool.write_text("#!/bin/sh\n", encoding="utf-8")
    calls: list[tuple[list[str], str | None]] = []

    def fake_run(cmd, input=None, **kwargs):
        calls.append((list(cmd), input))
        output_dir = Path(cmd[-1])
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "appcast.xml").write_text(_signed_appcast_xml(), encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(generate_appcast.subprocess, "run", fake_run)

    args = generate_appcast.build_parser().parse_args(
        [
            "production",
            "--artifact",
            str(artifact),
            "--output-dir",
            str(tmp_path / "payload"),
            "--expected-version",
            "1.2.3",
            "--sparkle-generate-appcast",
            str(tool),
            "--keychain-account",
            "ci-ed25519",
        ]
    )
    generate_appcast.generate_production_appcast(args)

    command, stdin = calls[0]
    assert "--account" in command
    assert "ci-ed25519" in command
    assert "--ed-key-file" not in command
    assert stdin is None


def test_install_sparkle_constants_match_pinned_release():
    assert install_sparkle.SPARKLE_VERSION == "2.9.3"
    assert install_sparkle.SPARKLE_DISTRIBUTION_URL.endswith("/2.9.3/Sparkle-2.9.3.tar.xz")
    assert (
        install_sparkle.SPARKLE_DISTRIBUTION_SHA256
        == "74a07da821f92b79310009954c0e15f350173374a3abe39095b4fc5096916be6"
    )


def test_pipeline_files_use_generated_appcast_and_cross_repo_pages_publish():
    files = [
        Path("src/automataii/utils/update_config.py"),
        Path("scripts/generate_appcast.py"),
        Path("scripts/install_sparkle.py"),
        Path("scripts/publish_ota_pages.py"),
        Path(".github/workflows/release.yml"),
        Path(".github/workflows/macos-arch-build.yml"),
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in files)

    assert "automataii/automataii" not in text
    assert "sparkle:dsaSignature" not in text
    assert "dist/Automataii-macos" not in text
    assert "https://alansynn.com/motionsmith/" in text
    assert "https://alansynn.github.io/" + "motionsmith/" not in text
    assert "signed_appcast_url" not in text
    assert "curl --proto '=https' --proto-redir '=https'" not in text
    assert "SPARKLE_ED_SIGNATURE" not in text
    assert "ED_SIGNATURE" not in text
    assert "Sparkle-2.9.3.tar.xz" in text
    assert "74a07da821f92b79310009954c0e15f350173374a3abe39095b4fc5096916be6" in text
    assert not Path(".github/workflows/build-and-release.yml").exists()

    workflow = Path(".github/workflows/release.yml").read_text(encoding="utf-8")
    assert "scripts/generate_appcast.py production" in workflow
    assert "scripts/validate_appcast.py sparkle-appcast-payload/appcast.xml" in workflow
    assert "python3 scripts/publish_ota_pages.py preflight" in workflow
    assert "python3 scripts/publish_ota_pages.py publish" in workflow
    assert "MOTIONSMITH_PAGES_TOKEN" in workflow
    assert "MOTIONSMITH_PAGES_DEPLOY_KEY" in workflow
    assert "Preflight MotionSmith Pages publishing access" in workflow
    assert "configure_pages_remote" not in workflow
    assert "ssh-keyscan" not in workflow
    assert "git config --global" not in workflow
    assert "rsync -av" not in workflow
    assert "https://github.com/AlanSynn/motionsmith.git" not in workflow
    assert "ref: main" not in workflow
    assert "actions/deploy-pages" not in workflow
    assert "actions/upload-pages-artifact" not in workflow
    assert "update-appcast" not in workflow
    assert "MOTIONSMITH_SIGNED_APPCAST_PATH" not in workflow
    assert "ota_smoke_passed" in workflow
    assert "manual attestation" in workflow
    assert "sparkle-appcast-payload/**" in workflow
    assert "sparkle-appcast-payload/*.delta" not in workflow
    assert "sparkle-appcast-payload/*.html" not in workflow
    assert "MotionSmith-macos-universal2.dmg" in workflow
    assert workflow.index("Preflight MotionSmith Pages publishing access") < workflow.index(
        "name: Create Release"
    )
    assert workflow.index("name: Create Release") < workflow.index(
        "name: Publish OTA payload to MotionSmith Pages repository"
    )

    publisher = Path("scripts/publish_ota_pages.py").read_text(encoding="utf-8")
    assert 'permissions.get("push") or permissions.get("admin")' in publisher
    assert "git@github.com:{repo}.git" in publisher
    assert '"push", "--dry-run", "origin", f"HEAD:{args.branch}"' in publisher
    assert "github.com ssh-ed25519" in publisher
    assert "MOTIONSMITH_PAGES_DEPLOY_KEY_FINGERPRINT" in workflow
    assert "MOTIONSMITH_PAGES_DEPLOY_KEY_FINGERPRINT" in publisher
    assert "ssh-keyscan" not in publisher
    assert "GIT_CONFIG_GLOBAL" in publisher
    assert "check_ota_reachability.retry_check" in publisher


def test_pages_payload_copy_preserves_unrelated_site_files(tmp_path):
    payload = tmp_path / "payload"
    destination = tmp_path / "site"
    payload.mkdir()
    destination.mkdir()
    (payload / "appcast.xml").write_text("<rss />", encoding="utf-8")
    (payload / "MotionSmith-macos-universal2.dmg").write_bytes(b"dmg")
    (destination / "index.html").write_text("<p>site</p>", encoding="utf-8")

    publish_ota_pages.copy_payload(payload, destination)

    assert (destination / "appcast.xml").read_text(encoding="utf-8") == "<rss />"
    assert (destination / "MotionSmith-macos-universal2.dmg").read_bytes() == b"dmg"
    assert (destination / "index.html").read_text(encoding="utf-8") == "<p>site</p>"


def test_pages_auth_uses_temp_git_config_for_token(monkeypatch, tmp_path):
    monkeypatch.setattr(publish_ota_pages, "check_token_push_permission", lambda token, repo: None)

    auth = publish_ota_pages.configure_git_auth(
        {"MOTIONSMITH_PAGES_TOKEN": "token-value"},
        temp_dir=tmp_path,
        check_token_permission=True,
    )

    git_config = Path(auth.env["GIT_CONFIG_GLOBAL"])
    assert auth.remote_url == "https://github.com/AlanSynn/motionsmith.git"
    assert git_config.parent == tmp_path
    assert "token-value" in git_config.read_text(encoding="utf-8")
    assert not any(
        "token-value" in value for key, value in auth.env.items() if key != "GIT_CONFIG_GLOBAL"
    )


def test_pages_auth_verifies_deploy_key_fingerprint(monkeypatch, tmp_path):
    monkeypatch.setattr(publish_ota_pages, "ensure_github_known_hosts", lambda path: None)

    def fake_run(cmd, **kwargs):
        if cmd[:3] == ["ssh-keygen", "-y", "-f"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="ssh-ed25519 AAAAC3 test-key\n")
        if cmd == ["ssh-keygen", "-l", "-E", "sha256", "-f", "-"]:
            assert kwargs["input"] == "ssh-ed25519 AAAAC3 test-key\n"
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout="256 SHA256:testFingerprint deploy-key (ED25519)\n",
            )
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(publish_ota_pages.subprocess, "run", fake_run)

    auth = publish_ota_pages.configure_git_auth(
        {
            "MOTIONSMITH_PAGES_DEPLOY_KEY": "private-key-material",
            "MOTIONSMITH_PAGES_DEPLOY_KEY_FINGERPRINT": "SHA256:testFingerprint",
        },
        temp_dir=tmp_path,
    )

    assert auth.remote_url == "git@github.com:AlanSynn/motionsmith.git"
    assert "motionsmith_pages_deploy_key" in auth.env["GIT_SSH_COMMAND"]
    assert "MOTIONSMITH_PAGES_DEPLOY_KEY" not in auth.env
    assert "MOTIONSMITH_PAGES_DEPLOY_KEY_FINGERPRINT" not in auth.env


def test_pages_auth_requires_deploy_key_fingerprint(monkeypatch, tmp_path):
    monkeypatch.setattr(publish_ota_pages, "ensure_github_known_hosts", lambda path: None)

    with pytest.raises(publish_ota_pages.PagesPublishError, match="DEPLOY_KEY_FINGERPRINT"):
        publish_ota_pages.configure_git_auth(
            {"MOTIONSMITH_PAGES_DEPLOY_KEY": "private-key-material"},
            temp_dir=tmp_path,
        )


def test_pages_auth_rejects_wrong_deploy_key_fingerprint(monkeypatch, tmp_path):
    monkeypatch.setattr(publish_ota_pages, "ensure_github_known_hosts", lambda path: None)

    def fake_run(cmd, **kwargs):
        if cmd[:3] == ["ssh-keygen", "-y", "-f"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="ssh-ed25519 AAAAC3 wrong-key\n")
        if cmd == ["ssh-keygen", "-l", "-E", "sha256", "-f", "-"]:
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout="256 SHA256:wrongFingerprint wrong-key (ED25519)\n",
            )
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(publish_ota_pages.subprocess, "run", fake_run)

    with pytest.raises(publish_ota_pages.PagesPublishError, match="fingerprint mismatch"):
        publish_ota_pages.configure_git_auth(
            {
                "MOTIONSMITH_PAGES_DEPLOY_KEY": "private-key-material",
                "MOTIONSMITH_PAGES_DEPLOY_KEY_FINGERPRINT": "SHA256:testFingerprint",
            },
            temp_dir=tmp_path,
        )


def test_ota_reachability_extracts_referenced_urls():
    appcast = _signed_appcast_xml(
        notes="https://alansynn.com/motionsmith/release-notes.html"
    ).encode("utf-8")

    assert check_ota_reachability.referenced_urls(appcast) == (
        "https://alansynn.com/motionsmith/MotionSmith-macos-universal2.dmg",
        "https://alansynn.com/motionsmith/release-notes.html",
    )


def test_ota_reachability_rejects_non_https_urls():
    result = check_ota_reachability.check_url(
        "http://alansynn.com/motionsmith/appcast.xml", timeout=1
    )

    assert result.ok is False
    assert "HTTPS" in str(result.error)


def test_ota_reachability_blocks_https_to_http_redirect():
    handler = check_ota_reachability.HTTPSOnlyRedirectHandler()
    request = check_ota_reachability.urllib.request.Request(
        "https://alansynn.com/motionsmith/appcast.xml"
    )

    with pytest.raises(check_ota_reachability.urllib.error.HTTPError) as excinfo:
        handler.redirect_request(
            request,
            None,
            301,
            "Moved",
            {},
            "http://alansynn.com/motionsmith/appcast.xml",
        )

    assert "insecure redirect blocked" in str(excinfo.value)


def test_local_sparkle_cache_is_ignored():
    assert ".sparkle/" in Path(".gitignore").read_text(encoding="utf-8")


def test_pyinstaller_spec_declares_sparkle_metadata_without_hardcoded_public_key():
    spec_text = Path("packaging/pyinstaller/automataii.spec").read_text(encoding="utf-8")

    assert "SUFeedURL" in spec_text
    assert "CFBundleVersion" in spec_text
    assert "sparkle_public_ed_key(os.environ)" in spec_text
    assert 'SUPublicEDKey": "' not in spec_text
