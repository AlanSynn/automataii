from __future__ import annotations

import subprocess
import zipfile
from collections.abc import Sequence
from pathlib import Path

from pytest import MonkeyPatch
from scripts import build, build_windows


def test_sign_executable_uses_sha256_timestamp(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    builder = build_windows.WindowsBuilder(tmp_path)
    exe = tmp_path / "dist" / "MotionSmith" / "MotionSmith.exe"
    cert = tmp_path / "windows-cert.pfx"
    signtool = tmp_path / "signtool.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"exe")
    cert.write_bytes(b"cert")
    signtool.write_bytes(b"tool")
    calls: list[list[str]] = []

    def fake_run(
        cmd: Sequence[str], cwd: object = None, check: bool = False
    ) -> subprocess.CompletedProcess[str]:
        calls.append(list(cmd))
        return subprocess.CompletedProcess(list(cmd), 0, "", "")

    monkeypatch.setenv("WINDOWS_CERT_PASSWORD", "secret")
    monkeypatch.setattr(build_windows.subprocess, "run", fake_run)

    builder.sign_executable(exe, cert, signtool=signtool)

    command = calls[0]
    assert command[:8] == [
        str(signtool),
        "sign",
        "/v",
        "/fd",
        "SHA256",
        "/tr",
        build_windows.DEFAULT_TIMESTAMP_URL,
        "/td",
    ]
    assert "SHA256" in command
    assert command[command.index("/f") + 1] == str(cert)
    assert command[command.index("/p") + 1] == "secret"
    assert command[-1] == str(exe)


def test_verify_signature_uses_policy_verification(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    builder = build_windows.WindowsBuilder(tmp_path)
    exe = tmp_path / "MotionSmith.exe"
    signtool = tmp_path / "signtool.exe"
    exe.write_bytes(b"exe")
    signtool.write_bytes(b"tool")
    calls: list[list[str]] = []

    def fake_run(
        cmd: Sequence[str], cwd: object = None, check: bool = False
    ) -> subprocess.CompletedProcess[str]:
        calls.append(list(cmd))
        return subprocess.CompletedProcess(list(cmd), 0, "", "")

    monkeypatch.setattr(build_windows.subprocess, "run", fake_run)

    builder.verify_signature(exe, signtool=signtool)

    assert calls == [[str(signtool), "verify", "/pa", "/v", str(exe)]]


def test_build_fails_closed_when_signing_certificate_missing(tmp_path: Path) -> None:
    builder = build_windows.WindowsBuilder(tmp_path)

    assert builder.build(sign=True) is False


def test_signtool_discovery_prefers_env(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    signtool = tmp_path / "signtool.exe"
    signtool.write_bytes(b"tool")
    monkeypatch.setenv("WINDOWS_SIGNTOOL_PATH", str(signtool))

    assert build_windows.WindowsBuilder(tmp_path).find_signtool() == signtool


def test_distribution_zip_contains_pyinstaller_one_folder(tmp_path: Path) -> None:
    builder = build_windows.WindowsBuilder(tmp_path)
    app_dir = tmp_path / "dist" / "MotionSmith"
    exe = app_dir / "MotionSmith.exe"
    dll = app_dir / "support.dll"
    app_dir.mkdir(parents=True)
    exe.write_bytes(b"exe")
    dll.write_bytes(b"dll")

    archive = builder.create_distribution_zip(exe)

    with zipfile.ZipFile(archive) as zipped:
        assert {"MotionSmith/MotionSmith.exe", "MotionSmith/support.dll"} <= set(zipped.namelist())


def test_verify_file_sha256_rejects_unexpected_download(tmp_path: Path) -> None:
    builder = build_windows.WindowsBuilder(tmp_path)
    payload = tmp_path / "payload.zip"
    payload.write_bytes(b"payload")

    builder.verify_file_sha256(
        payload, "239f59ed55e737c77147cf55ad0c1b030b6d7ee748a7426952f9b852d5a935e5"
    )

    try:
        builder.verify_file_sha256(payload, "0" * 64)
    except RuntimeError as exc:
        assert "SHA256 mismatch" in str(exc)
    else:  # pragma: no cover - assertion path
        raise AssertionError("unexpected WinSparkle checksum should fail")


def test_build_py_forwards_windows_signing_flags(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []
    cert = tmp_path / "windows-cert.pfx"
    cert.write_bytes(b"cert")

    class FakeWindowsBuilder:
        def __init__(self, project_root: Path) -> None:
            self.project_root = project_root

        def build(self, **kwargs: object) -> bool:
            calls.append(kwargs)
            return True

    monkeypatch.setattr(build, "_import_windows_builder", lambda: FakeWindowsBuilder)
    monkeypatch.setattr(
        build.sys,
        "argv",
        [
            "build.py",
            "--platform",
            "windows",
            "--windows-sign",
            "--windows-certificate",
            str(cert),
            "--windows-cert-password-env",
            "WIN_PW",
            "--windows-signtool",
            "signtool.exe",
            "--windows-timestamp-url",
            "http://timestamp.example.com",
            "--windows-verify-signature",
        ],
    )

    assert build.main() == 0
    assert calls == [
        {
            "sign": True,
            "certificate": cert,
            "cert_password_env": "WIN_PW",
            "signtool": "signtool.exe",
            "verify_signature": True,
            "timestamp_url": "http://timestamp.example.com",
        }
    ]


def test_windows_build_regression_files_are_release_ready() -> None:
    workflow = Path(".github/workflows/release.yml").read_text(encoding="utf-8")
    makefile = Path("Makefile").read_text(encoding="utf-8")
    docs = Path("docs/deployment.md").read_text(encoding="utf-8")
    windows_builder = Path("scripts/build_windows.py").read_text(encoding="utf-8")
    linux_builder = Path("scripts/build_linux.py").read_text(encoding="utf-8")
    build_windows_target = makefile.split("build-windows:", 1)[1].split("build-linux:", 1)[0]

    assert "$(UV) sync --group build" in build_windows_target
    assert "--sign" in build_windows_target
    assert "--certificate" in build_windows_target
    assert "--verify-signature" in build_windows_target
    assert "WINDOWS_CERTIFICATE is required" in build_windows_target
    assert "sync --group build-windows" not in makefile

    assert "Building signed Windows distribution zip" in build_windows_target
    assert "Build signed Windows distribution zip" in makefile
    assert build_windows.WINSPARKLE_ZIP_SHA256 in windows_builder
    assert "verify_file_sha256" in windows_builder
    assert "--no-installer" not in Path("scripts/build.py").read_text(encoding="utf-8")
    assert "--no-installer" not in windows_builder
    assert "create_installer" not in windows_builder
    spec = Path("packaging/pyinstaller/automataii.spec").read_text(encoding="utf-8")
    assert 'if sys.platform == "darwin":' in spec
    assert spec.index('if sys.platform == "darwin":') < spec.index("app = BUNDLE(")
    assert "import requests" not in windows_builder
    assert "import requests" not in linux_builder
    assert "download_file" in windows_builder
    assert "download_file" in linux_builder
    assert "'wget'" not in linux_builder

    for required in (
        "uv sync --group build",
        "WINDOWS_CERT_PFX",
        "WINDOWS_CERT_PASSWORD",
        "WINDOWS_SIGNTOOL_PATH",
        "WINDOWS_ALLOW_TEST_CERTIFICATE",
        "WINDOWS_TEST_CERTIFICATE_MODE",
        "WINDOWS_CERT_PASSWORD=$env:WINDOWS_CERT_PASSWORD",
        "Public, test-only PFX",
        "Loaded public Windows test signing certificate payload",
        "python -u scripts/build_windows.py",
        "Get-AuthenticodeSignature",
        "permissions:\n  contents: read",
        "permissions:\n      contents: write",
        '$buildArgs = @("--sign"',
        "--verify-signature",
        "Smoke Windows executable",
        "Start-Process",
        "WaitForExit(120000)",
        '"--scenario", "blueprint-export"',
        "windows-release",
        "dist/MotionSmith-windows.zip",
    ):
        assert required in workflow
    assert workflow.index('if ($env:WINDOWS_ALLOW_TEST_CERTIFICATE -eq "1")') < workflow.index(
        "elseif ($env:WINDOWS_CERT_PFX -and $env:WINDOWS_CERT_PASSWORD)"
    )
    assert "path: dist/*.exe" not in workflow

    for required in (
        "WINDOWS_CERT_PFX",
        "WINDOWS_CERT_PASSWORD",
        "WINDOWS_SIGNTOOL_PATH",
        "scripts/build_windows.py --sign",
        "MotionSmith.exe --scenario blueprint-export",
        "dist/MotionSmith-windows.zip",
        "PyInstaller is not a cross-compiler",
        "trusted public release",
        "Authenticode signature is present",
        "trust-chain verification",
        "WinSparkle download is SHA256-verified",
    ):
        assert required in docs


def test_signable_payload_files_include_exe_dll_and_pyd(tmp_path: Path) -> None:
    builder = build_windows.WindowsBuilder(tmp_path)
    app_dir = tmp_path / "dist" / "MotionSmith"
    for name in ("MotionSmith.exe", "support.dll", "extension.pyd", "notes.txt"):
        path = app_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")

    files = {path.name for path in builder.signable_payload_files(app_dir / "MotionSmith.exe")}

    assert files == {"MotionSmith.exe", "support.dll", "extension.pyd"}


def test_build_signs_and_verifies_all_payload_pe_files(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    builder = build_windows.WindowsBuilder(tmp_path)
    app_dir = tmp_path / "dist" / "MotionSmith"
    exe = app_dir / "MotionSmith.exe"
    dll = app_dir / "support.dll"
    winsparkle = tmp_path / "WinSparkle" / "bin" / "WinSparkle.dll"
    cert = tmp_path / "windows-cert.pfx"
    for path in (exe, dll, winsparkle, cert):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")
    signed: list[Path] = []
    verified: list[Path] = []

    monkeypatch.setattr(builder, "check_dependencies", lambda: True)
    monkeypatch.setattr(builder, "download_winsparkle", lambda: tmp_path / "WinSparkle")
    monkeypatch.setattr(builder, "build_executable", lambda: exe)
    monkeypatch.setattr(builder, "sign_executable", lambda file, **kwargs: signed.append(file))
    monkeypatch.setattr(builder, "verify_signature", lambda file, **kwargs: verified.append(file))

    assert builder.build(sign=True, certificate=cert, verify_signature=True) is True
    staged_winsparkle = app_dir / "WinSparkle.dll"
    assert signed == [exe, staged_winsparkle, dll]
    assert verified == [exe, staged_winsparkle, dll]
    archive = tmp_path / "dist" / "MotionSmith-windows.zip"
    assert archive.exists()
    with zipfile.ZipFile(archive) as zipped:
        assert "MotionSmith/WinSparkle.dll" in zipped.namelist()


def test_stage_winsparkle_copies_dll_beside_executable(tmp_path: Path) -> None:
    builder = build_windows.WindowsBuilder(tmp_path)
    winsparkle_dll = tmp_path / "WinSparkle" / "bin" / "WinSparkle.dll"
    exe = tmp_path / "dist" / "MotionSmith" / "MotionSmith.exe"
    winsparkle_dll.parent.mkdir(parents=True)
    exe.parent.mkdir(parents=True)
    winsparkle_dll.write_bytes(b"dll")
    exe.write_bytes(b"exe")

    staged = builder.stage_winsparkle(tmp_path / "WinSparkle", exe)

    assert staged == exe.parent / "WinSparkle.dll"
    assert staged.read_bytes() == b"dll"


def test_find_built_executable_rejects_flat_layout(tmp_path: Path) -> None:
    builder = build_windows.WindowsBuilder(tmp_path)
    flat_exe = tmp_path / "dist" / "MotionSmith.exe"
    flat_exe.parent.mkdir(parents=True)
    flat_exe.write_bytes(b"exe")

    try:
        builder.find_built_executable()
    except FileNotFoundError as exc:
        assert "one-folder" in str(exc)
    else:  # pragma: no cover - assertion path
        raise AssertionError("flat Windows layout should not be accepted")
