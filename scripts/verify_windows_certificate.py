#!/usr/bin/env python3
"""Validate Windows code-signing PFX release credentials without leaking secrets."""

from __future__ import annotations

import argparse
import base64
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path

TEST_CERT_PATTERNS = re.compile(r"(?:Test Signing|CI Test|Self[- ]Signed)", re.IGNORECASE)
CODE_SIGNING_OID = "1.3.6.1.5.5.7.3.3"


class CertificateValidationError(RuntimeError):
    """Raised when the configured release certificate is not production-ready."""


def parse_env_file(path: Path) -> dict[str, str]:
    """Parse a simple dotenv file without expanding values or printing secrets."""
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[key] = value
    return values


def merged_env(env_file: Path | None, base_env: Mapping[str, str]) -> dict[str, str]:
    merged = dict(base_env)
    if env_file is not None:
        for key, value in parse_env_file(env_file).items():
            merged.setdefault(key, value)
    return merged


def normalize_distinguished_name(value: str) -> str:
    value = value.strip()
    for prefix in ("subject=", "issuer="):
        if value.lower().startswith(prefix):
            value = value[len(prefix) :]
            break
    return " ".join(value.strip().split())


def is_test_or_self_signed_certificate(subject: str, issuer: str) -> bool:
    return normalize_distinguished_name(subject) == normalize_distinguished_name(issuer) or bool(
        TEST_CERT_PATTERNS.search(f"{subject}\n{issuer}")
    )


def has_code_signing_usage(certificate_text: str) -> bool:
    return "Code Signing" in certificate_text or CODE_SIGNING_OID in certificate_text


def run_openssl(args: list[str], *, env: Mapping[str, str]) -> str:
    completed = subprocess.run(
        ["openssl", *args],
        check=False,
        capture_output=True,
        text=True,
        env=dict(env),
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip() or completed.stdout.strip() or "openssl failed"
        raise CertificateValidationError(stderr)
    return completed.stdout


def certificate_summary_from_pfx(
    pfx_path: Path, password_env: str, env: Mapping[str, str]
) -> tuple[str, str, str]:
    if not shutil.which("openssl"):
        raise CertificateValidationError(
            "openssl is required to validate Windows release PFX files"
        )
    if not env.get(password_env):
        raise CertificateValidationError(f"{password_env} is required to validate the Windows PFX")

    with tempfile.TemporaryDirectory(prefix="motionsmith-win-cert-") as temp_dir:
        cert_path = Path(temp_dir) / "cert.pem"
        run_openssl(
            [
                "pkcs12",
                "-in",
                str(pfx_path),
                "-clcerts",
                "-nokeys",
                "-passin",
                f"env:{password_env}",
                "-out",
                str(cert_path),
            ],
            env=env,
        )
        identity = run_openssl(
            ["x509", "-in", str(cert_path), "-noout", "-subject", "-issuer"], env=env
        )
        text = run_openssl(["x509", "-in", str(cert_path), "-noout", "-text"], env=env)

    subject = ""
    issuer = ""
    for line in identity.splitlines():
        if line.startswith("subject="):
            subject = normalize_distinguished_name(line)
        elif line.startswith("issuer="):
            issuer = normalize_distinguished_name(line)
    if not subject or not issuer:
        raise CertificateValidationError(
            "openssl could not read certificate subject/issuer from PFX"
        )
    return subject, issuer, text


def pfx_path_from_base64(value: str) -> Path:
    try:
        data = base64.b64decode(re.sub(r"\s+", "", value), validate=True)
    except Exception as exc:  # noqa: BLE001 - keep validation error sanitized
        raise CertificateValidationError(
            "WINDOWS_CERT_PFX is not valid base64 PFX content"
        ) from exc
    temp = tempfile.NamedTemporaryFile(prefix="motionsmith-win-cert-", suffix=".pfx", delete=False)
    try:
        temp.write(data)
        temp.close()
        return Path(temp.name)
    except Exception:
        Path(temp.name).unlink(missing_ok=True)
        raise


def validate_windows_certificate(
    *,
    pfx_file: Path | None,
    pfx_base64: str | None,
    password_env: str,
    env: Mapping[str, str],
) -> tuple[str, str]:
    temp_path: Path | None = None
    if pfx_file is None:
        if not pfx_base64:
            raise CertificateValidationError(
                "WINDOWS_CERT_PFX or --pfx-file is required for production deploy preflight"
            )
        temp_path = pfx_path_from_base64(pfx_base64)
        pfx_file = temp_path

    try:
        subject, issuer, text = certificate_summary_from_pfx(pfx_file, password_env, env)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)

    if is_test_or_self_signed_certificate(subject, issuer):
        raise CertificateValidationError(
            "Windows release certificate is self-signed/test-only; production deploys require a CA-issued code-signing certificate."
        )
    if not has_code_signing_usage(text):
        raise CertificateValidationError(
            "Windows release certificate does not advertise Code Signing extended key usage."
        )
    return subject, issuer


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate production Windows code-signing PFX credentials."
    )
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--pfx-base64-env", default="WINDOWS_CERT_PFX")
    parser.add_argument("--password-env", default="WINDOWS_CERT_PASSWORD")
    parser.add_argument("--pfx-file", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    env = merged_env(args.env_file, os.environ)
    try:
        subject, issuer = validate_windows_certificate(
            pfx_file=args.pfx_file,
            pfx_base64=env.get(args.pfx_base64_env),
            password_env=args.password_env,
            env=env,
        )
    except CertificateValidationError as exc:
        print(f"Windows certificate preflight failed: {exc}", file=sys.stderr)
        return 1

    print("Windows certificate preflight passed.")
    print(f"Subject: {subject}")
    print(f"Issuer: {issuer}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
