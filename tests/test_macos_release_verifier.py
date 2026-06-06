from __future__ import annotations

import subprocess
from pathlib import Path

from scripts import verify_macos_release


def _completed(cmd: list[str], returncode: int = 0, stdout: str = "", stderr: str = ""):
    return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr=stderr)


def _empty_otool_response(command: list[str]):
    if command[:2] == ["otool", "-L"]:
        return _completed(command, stdout=f"{command[-1]}:\n")
    if command[:2] == ["otool", "-D"]:
        return _completed(command, stdout=f"{command[-1]}:\n")
    if command[:2] == ["otool", "-l"]:
        return _completed(command)
    return None


def _write_minimal_app(app: Path) -> Path:
    executable = app / "Contents" / "MacOS" / "MotionSmith"
    executable.parent.mkdir(parents=True)
    executable.write_text("#!/bin/sh\n")
    (app / "Contents" / "Info.plist").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleExecutable</key><string>MotionSmith</string>
</dict></plist>
"""
    )
    return executable


def test_missing_artifact_is_not_ready(tmp_path):
    result = verify_macos_release.verify_release(tmp_path / "missing.app")

    assert result.passed is False
    assert result.distribution_ready is False
    assert result.checks[0].name == "artifact_exists"


def test_signed_notarized_app_is_distribution_ready(monkeypatch, tmp_path):
    app = tmp_path / "MotionSmith.app"
    _write_minimal_app(app)

    def fake_tool_exists(name: str) -> bool:
        return name in {"codesign", "spctl", "xcrun", "otool"}

    def fake_run(command: list[str]):
        if otool := _empty_otool_response(command):
            return otool
        joined = " ".join(command)
        if command[:2] == ["codesign", "--verify"]:
            return _completed(command)
        if command[:2] == ["codesign", "-dv"]:
            return _completed(
                command,
                stderr=(
                    "CodeDirectory v=20500 flags=0x10000(runtime)\\n"
                    "Authority=Developer ID Application: Example (TEAMID)\\n"
                ),
            )
        if command[:2] == ["spctl", "--assess"]:
            return _completed(command, stderr=f"{app}: accepted\\nsource=Notarized Developer ID")
        if joined.startswith("xcrun stapler validate"):
            return _completed(command, stdout="The validate action worked!\n")
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(verify_macos_release, "_tool_exists", fake_tool_exists)
    monkeypatch.setattr(verify_macos_release, "_run", fake_run)
    monkeypatch.setattr(verify_macos_release, "executable_arches", lambda path: {"x86_64"})

    result = verify_macos_release.verify_release(app, expected_arch="x86_64")

    assert result.passed is True
    assert result.distribution_ready is True


def test_unstapled_app_is_not_distribution_ready_but_can_be_non_required(monkeypatch, tmp_path):
    app = tmp_path / "MotionSmith.app"
    _write_minimal_app(app)

    def fake_tool_exists(name: str) -> bool:
        return name in {"codesign", "spctl", "xcrun", "otool"}

    def fake_run(command: list[str]):
        if otool := _empty_otool_response(command):
            return otool
        if command[:2] == ["codesign", "--verify"]:
            return _completed(command)
        if command[:2] == ["codesign", "-dv"]:
            return _completed(
                command,
                stderr=(
                    "CodeDirectory v=20500 flags=0x10000(runtime)\\n"
                    "Authority=Developer ID Application: Example (TEAMID)\\n"
                ),
            )
        if command[:2] == ["spctl", "--assess"]:
            return _completed(command, stderr="accepted")
        if command[:3] == ["xcrun", "stapler", "validate"]:
            return _completed(command, returncode=1, stderr="The validate action failed.")
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(verify_macos_release, "_tool_exists", fake_tool_exists)
    monkeypatch.setattr(verify_macos_release, "_run", fake_run)
    monkeypatch.setattr(verify_macos_release, "executable_arches", lambda path: {"x86_64"})

    result = verify_macos_release.verify_release(app, expected_arch="x86_64")

    assert result.passed is True
    assert result.distribution_ready is False


def test_dmg_verification_requires_app_inside(monkeypatch, tmp_path):
    dmg = tmp_path / "MotionSmith.dmg"
    dmg.write_text("not really a dmg")

    monkeypatch.setattr(verify_macos_release, "_tool_exists", lambda name: name == "hdiutil")
    monkeypatch.setattr(
        verify_macos_release,
        "_run",
        lambda command: _completed(command, stdout="attached")
        if command[1] == "attach"
        else _completed(command),
    )

    result = verify_macos_release.verify_release(dmg)

    assert result.passed is False
    assert result.distribution_ready is False
    assert any(check.name == "dmg_contains_app" for check in result.checks)


def test_dmg_app_is_copied_before_signature_checks(monkeypatch, tmp_path):
    dmg = tmp_path / "MotionSmith.dmg"
    dmg.write_text("not really a dmg")

    checked_apps: list[Path] = []

    def fake_tool_exists(name: str) -> bool:
        return name in {"hdiutil", "codesign", "spctl", "xcrun", "otool"}

    def fake_run(command: list[str]):
        if otool := _empty_otool_response(command):
            return otool
        if command[1] == "attach":
            mountpoint = Path(command[command.index("-mountpoint") + 1])
            _write_minimal_app(mountpoint / "MotionSmith.app")
            return _completed(command)
        if command[1] == "detach":
            return _completed(command)
        if command[:3] == ["codesign", "--verify", "--verbose=2"]:
            return _completed(command)
        if command[:2] == ["codesign", "--verify"]:
            checked_app = Path(command[-1])
            assert checked_app.exists()
            checked_apps.append(checked_app)
            return _completed(command)
        if command[:2] == ["codesign", "-dv"]:
            return _completed(
                command,
                stderr=(
                    "CodeDirectory v=20500 flags=0x10000(runtime)\\n"
                    "Authority=Developer ID Application: Example (TEAMID)\\n"
                ),
            )
        if command[:2] == ["spctl", "--assess"]:
            return _completed(command, stderr="accepted")
        if command[:3] == ["xcrun", "stapler", "validate"]:
            return _completed(command, stdout="The validate action worked!\n")
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(verify_macos_release, "_tool_exists", fake_tool_exists)
    monkeypatch.setattr(verify_macos_release, "_run", fake_run)
    monkeypatch.setattr(verify_macos_release, "executable_arches", lambda path: {"x86_64"})

    result = verify_macos_release.verify_release(dmg, expected_arch="x86_64")

    assert result.passed is True
    assert result.distribution_ready is True
    assert checked_apps
    assert any(check.name == "dmg_extract_app" and check.passed for check in result.checks)


def test_dmg_embedded_app_strict_codesign_failure_blocks_distribution(
    monkeypatch, tmp_path
):
    dmg = tmp_path / "MotionSmith.dmg"
    dmg.write_text("not really a dmg")

    def fake_tool_exists(name: str) -> bool:
        return name in {"hdiutil", "codesign", "spctl", "xcrun", "otool"}

    def fake_run(command: list[str]):
        if otool := _empty_otool_response(command):
            return otool
        if command[1] == "attach":
            mountpoint = Path(command[command.index("-mountpoint") + 1])
            _write_minimal_app(mountpoint / "MotionSmith.app")
            return _completed(command)
        if command[1] == "detach":
            return _completed(command)
        if command[:4] == ["codesign", "--verify", "--strict", "--verbose=2"]:
            return _completed(
                command,
                returncode=1,
                stderr="resource fork, Finder information, or similar detritus not allowed",
            )
        if command[:3] == ["codesign", "--verify", "--verbose=2"]:
            return _completed(command)
        if command[:2] == ["codesign", "--verify"]:
            return _completed(command)
        if command[:2] == ["codesign", "-dv"]:
            return _completed(
                command,
                stderr=(
                    "CodeDirectory v=20500 flags=0x10000(runtime)\n"
                    "Authority=Developer ID Application: Example (TEAMID)\n"
                ),
            )
        if command[:2] == ["spctl", "--assess"]:
            return _completed(command, stderr="accepted")
        if command[:3] == ["xcrun", "stapler", "validate"]:
            return _completed(command, stdout="The validate action worked!\n")
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(verify_macos_release, "_tool_exists", fake_tool_exists)
    monkeypatch.setattr(verify_macos_release, "_run", fake_run)
    monkeypatch.setattr(verify_macos_release, "executable_arches", lambda path: {"x86_64"})

    result = verify_macos_release.verify_release(dmg, expected_arch="x86_64")

    assert result.passed is False
    assert result.distribution_ready is False
    assert any(
        check.name == "dmg_embedded_app_codesign_verify"
        and not check.passed
        and "Finder information" in check.message
        for check in result.checks
    )


def test_universal2_verification_fails_on_nested_thin_macho(monkeypatch, tmp_path):
    app = tmp_path / "MotionSmith.app"
    executable = _write_minimal_app(app)
    nested = app / "Contents" / "Frameworks" / "thin.dylib"
    nested.parent.mkdir(parents=True)
    nested.write_text("macho")

    def fake_tool_exists(name: str) -> bool:
        return name in {"codesign", "spctl", "xcrun", "otool"}

    def fake_run(command: list[str]):
        if otool := _empty_otool_response(command):
            return otool
        if command[:2] == ["codesign", "--verify"]:
            return _completed(command)
        if command[:2] == ["codesign", "-dv"]:
            return _completed(
                command,
                stderr=(
                    "CodeDirectory v=20500 flags=0x10000(runtime)\n"
                    "Authority=Developer ID Application: Example (TEAMID)\n"
                ),
            )
        if command[:2] == ["spctl", "--assess"]:
            return _completed(command, stderr="accepted")
        if command[:3] == ["xcrun", "stapler", "validate"]:
            return _completed(command, stdout="The validate action worked!\n")
        raise AssertionError(f"unexpected command: {command}")

    def fake_arches(path: Path) -> set[str]:
        if path == executable:
            return {"x86_64", "arm64"}
        if path == nested:
            return {"x86_64"}
        return set()

    monkeypatch.setattr(verify_macos_release, "_tool_exists", fake_tool_exists)
    monkeypatch.setattr(verify_macos_release, "_run", fake_run)
    monkeypatch.setattr(verify_macos_release, "executable_arches", fake_arches)

    result = verify_macos_release.verify_release(app, expected_arch="universal2")

    assert result.passed is False
    assert any(
        check.name == "nested_architecture" and not check.passed for check in result.checks
    )


def test_dmg_container_signature_is_required(monkeypatch, tmp_path):
    dmg = tmp_path / "MotionSmith.dmg"
    dmg.write_text("not really a dmg")

    def fake_tool_exists(name: str) -> bool:
        return name in {"hdiutil", "codesign", "spctl", "xcrun", "otool"}

    def fake_run(command: list[str]):
        if otool := _empty_otool_response(command):
            return otool
        if command[1] == "attach":
            mountpoint = Path(command[command.index("-mountpoint") + 1])
            _write_minimal_app(mountpoint / "MotionSmith.app")
            return _completed(command)
        if command[1] == "detach":
            return _completed(command)
        if command[:3] == ["codesign", "--verify", "--verbose=2"]:
            return _completed(command, returncode=1, stderr="code object is not signed")
        if command[:2] == ["codesign", "--verify"]:
            return _completed(command)
        if command[:2] == ["codesign", "-dv"]:
            return _completed(
                command,
                stderr=(
                    "CodeDirectory v=20500 flags=0x10000(runtime)\n"
                    "Authority=Developer ID Application: Example (TEAMID)\n"
                ),
            )
        if command[:2] == ["spctl", "--assess"]:
            return _completed(command, stderr="accepted")
        if command[:3] == ["xcrun", "stapler", "validate"]:
            return _completed(command, stdout="The validate action worked!\n")
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(verify_macos_release, "_tool_exists", fake_tool_exists)
    monkeypatch.setattr(verify_macos_release, "_run", fake_run)
    monkeypatch.setattr(verify_macos_release, "executable_arches", lambda path: {"x86_64"})

    result = verify_macos_release.verify_release(dmg, expected_arch="x86_64")

    assert result.passed is False
    assert result.distribution_ready is False
    assert any(check.name == "dmg_codesign_verify" and not check.passed for check in result.checks)


def test_dependency_closure_fails_on_missing_loader_path_dependency(monkeypatch, tmp_path):
    app = tmp_path / "MotionSmith.app"
    executable = _write_minimal_app(app)
    nested = app / "Contents" / "Frameworks" / "needs_missing.dylib"
    nested.parent.mkdir(parents=True)
    nested.write_text("macho")

    def fake_tool_exists(name: str) -> bool:
        return name in {"codesign", "spctl", "xcrun", "otool"}

    def fake_run(command: list[str]):
        if command[:2] == ["otool", "-L"]:
            if Path(command[-1]) == nested:
                return _completed(command, stdout=f"{nested}:\n\t@loader_path/missing.dylib (compatibility version 1.0.0, current version 1.0.0)\n")
            return _completed(command, stdout=f"{command[-1]}:\n")
        if command[:2] == ["otool", "-D"]:
            return _completed(command, stdout=f"{command[-1]}:\n")
        if command[:2] == ["otool", "-l"]:
            return _completed(command)
        if command[:2] == ["codesign", "--verify"]:
            return _completed(command)
        if command[:2] == ["codesign", "-dv"]:
            return _completed(
                command,
                stderr=(
                    "CodeDirectory v=20500 flags=0x10000(runtime)\n"
                    "Authority=Developer ID Application: Example (TEAMID)\n"
                ),
            )
        if command[:2] == ["spctl", "--assess"]:
            return _completed(command, stderr="accepted")
        if command[:3] == ["xcrun", "stapler", "validate"]:
            return _completed(command, stdout="The validate action worked!\n")
        raise AssertionError(f"unexpected command: {command}")

    def fake_arches(path: Path) -> set[str]:
        if path in {executable, nested}:
            return {"x86_64", "arm64"}
        return set()

    monkeypatch.setattr(verify_macos_release, "_tool_exists", fake_tool_exists)
    monkeypatch.setattr(verify_macos_release, "_run", fake_run)
    monkeypatch.setattr(verify_macos_release, "executable_arches", fake_arches)

    result = verify_macos_release.verify_release(app, expected_arch="universal2")

    assert result.passed is False
    assert any(check.name == "dependency_closure" and not check.passed for check in result.checks)
