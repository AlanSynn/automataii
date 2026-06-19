from __future__ import annotations

from pathlib import Path

from scripts import verify_windows_certificate as cert


def test_parse_env_file_handles_quotes_and_export(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "# comment",
                "export WINDOWS_CERT_PFX='abc='",
                'WINDOWS_CERT_PASSWORD="pw"',
                "IGNORED_LINE",
            ]
        ),
        encoding="utf-8",
    )

    assert cert.parse_env_file(env_file) == {
        "WINDOWS_CERT_PFX": "abc=",
        "WINDOWS_CERT_PASSWORD": "pw",
    }


def test_self_signed_or_test_certificate_is_rejected() -> None:
    assert cert.is_test_or_self_signed_certificate("CN=MotionSmith", "CN=MotionSmith")
    assert cert.is_test_or_self_signed_certificate(
        "CN=MotionSmith GitHub Secret Test Signing", "CN=Example CA"
    )
    assert not cert.is_test_or_self_signed_certificate("CN=MotionSmith", "CN=Trusted CA")


def test_code_signing_usage_detection_accepts_name_or_oid() -> None:
    assert cert.has_code_signing_usage("X509v3 Extended Key Usage: Code Signing")
    assert cert.has_code_signing_usage(cert.CODE_SIGNING_OID)
    assert not cert.has_code_signing_usage(
        "X509v3 Extended Key Usage: TLS Web Server Authentication"
    )


def test_pfx_base64_decode_accepts_wrapped_payload() -> None:
    pfx_path = cert.pfx_path_from_base64(" YWJj\nZA== ")
    try:
        assert pfx_path.read_bytes() == b"abcd"
    finally:
        pfx_path.unlink(missing_ok=True)


def test_validate_windows_certificate_rejects_self_signed_summary(
    monkeypatch, tmp_path: Path
) -> None:
    def fake_summary(
        _pfx_path: Path, _password_env: str, _env: dict[str, str]
    ) -> tuple[str, str, str]:
        return "CN=MotionSmith CI Test Signing", "CN=MotionSmith CI Test Signing", "Code Signing"

    monkeypatch.setattr(cert, "certificate_summary_from_pfx", fake_summary)

    try:
        cert.validate_windows_certificate(
            pfx_file=tmp_path / "cert.pfx",
            pfx_base64=None,
            password_env="WINDOWS_CERT_PASSWORD",
            env={"WINDOWS_CERT_PASSWORD": "pw"},
        )
    except cert.CertificateValidationError as exc:
        assert "self-signed/test-only" in str(exc)
    else:  # pragma: no cover - explicit assertion path
        raise AssertionError("self-signed certificate should fail")


def test_validate_windows_certificate_requires_code_signing_eku(
    monkeypatch, tmp_path: Path
) -> None:
    def fake_summary(
        _pfx_path: Path, _password_env: str, _env: dict[str, str]
    ) -> tuple[str, str, str]:
        return "CN=MotionSmith", "CN=Trusted CA", "TLS Web Server Authentication"

    monkeypatch.setattr(cert, "certificate_summary_from_pfx", fake_summary)

    try:
        cert.validate_windows_certificate(
            pfx_file=tmp_path / "cert.pfx",
            pfx_base64=None,
            password_env="WINDOWS_CERT_PASSWORD",
            env={"WINDOWS_CERT_PASSWORD": "pw"},
        )
    except cert.CertificateValidationError as exc:
        assert "Code Signing" in str(exc)
    else:  # pragma: no cover - explicit assertion path
        raise AssertionError("non-code-signing certificate should fail")


def test_validate_windows_certificate_accepts_ca_issued_code_signing(
    monkeypatch, tmp_path: Path
) -> None:
    def fake_summary(
        _pfx_path: Path, _password_env: str, _env: dict[str, str]
    ) -> tuple[str, str, str]:
        return "CN=MotionSmith", "CN=Trusted CA", "X509v3 Extended Key Usage: Code Signing"

    monkeypatch.setattr(cert, "certificate_summary_from_pfx", fake_summary)

    assert cert.validate_windows_certificate(
        pfx_file=tmp_path / "cert.pfx",
        pfx_base64=None,
        password_env="WINDOWS_CERT_PASSWORD",
        env={"WINDOWS_CERT_PASSWORD": "pw"},
    ) == ("CN=MotionSmith", "CN=Trusted CA")
