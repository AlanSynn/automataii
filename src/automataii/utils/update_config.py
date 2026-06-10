"""Update and OTA configuration shared by app runtime and packaging scripts."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

UPDATE_SITE_BASE_URL = "https://alansynn.github.io/motionsmith/"
DEFAULT_APPCAST_URL = f"{UPDATE_SITE_BASE_URL}appcast.xml"
DEFAULT_RELEASES_URL = "https://github.com/AlanSynn/motionsmith/releases/latest"

UPDATE_URL_ENV = "MOTIONSMITH_UPDATE_URL"
APPCAST_URL_ENV = "MOTIONSMITH_APPCAST_URL"
OTA_ENABLED_ENV = "MOTIONSMITH_OTA_ENABLED"
AUTOMATIC_CHECKS_ENV = "MOTIONSMITH_ENABLE_AUTOMATIC_CHECKS"
SPARKLE_PUBLIC_KEY_ENVS = ("SPARKLE_PUBLIC_ED_KEY", "SPARKLE_PUBLIC_KEY")
SIGNED_APPCAST_PATH_ENV = "MOTIONSMITH_SIGNED_APPCAST_PATH"
SPARKLE_NAMESPACE = "http://www.andymatuschak.org/xml-namespaces/sparkle"

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


@dataclass(frozen=True)
class AppcastValidation:
    """Validation result for a signed Sparkle appcast."""

    passed: bool
    errors: tuple[str, ...]
    matched_enclosure_count: int


def configured_update_url(env: Mapping[str, str]) -> str:
    """Return the release/update landing URL for users."""
    return env.get(UPDATE_URL_ENV, "").strip() or DEFAULT_RELEASES_URL


def configured_appcast_url(env: Mapping[str, str]) -> str:
    """Return the Sparkle appcast URL."""
    return env.get(APPCAST_URL_ENV, "").strip() or DEFAULT_APPCAST_URL


def env_flag(name: str, env: Mapping[str, str]) -> bool:
    """Return whether an environment flag is enabled."""
    return env.get(name, "").strip().lower() in _TRUE_VALUES


def env_flag_optional(name: str, env: Mapping[str, str]) -> bool | None:
    """Parse an optional boolean env flag, returning None when unset/unknown."""
    value = env.get(name, "").strip().lower()
    if not value:
        return None
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    return None


def ota_enabled(env: Mapping[str, str]) -> bool:
    """Return whether strict OTA readiness gates are enabled for this build."""
    return env_flag(OTA_ENABLED_ENV, env)


def sparkle_public_ed_key(env: Mapping[str, str]) -> str | None:
    """Return the configured public EdDSA key without exposing private material."""
    for name in SPARKLE_PUBLIC_KEY_ENVS:
        value = env.get(name, "").strip()
        if value:
            return value
    return None


def signed_appcast_path(env: Mapping[str, str]) -> str | None:
    """Return the local signed appcast evidence path when supplied."""
    value = env.get(SIGNED_APPCAST_PATH_ENV, "").strip()
    return value or None


def normalize_release_version(version: str | None) -> str:
    """Normalize a release version for matching appcast and bundle metadata."""
    return (version or "").strip().removeprefix("v")


def validate_signed_appcast(
    appcast_path: str | Path,
    *,
    expected_artifact_name: str | None = None,
    expected_version: str | None = None,
) -> AppcastValidation:
    """Validate that an appcast contains signed enclosure metadata.

    This intentionally validates metadata shape only. Cryptographic EdDSA
    verification is performed by Sparkle at runtime and by Sparkle's official
    signing tooling when generating the appcast.
    """
    path = Path(appcast_path)
    errors: list[str] = []
    if not path.exists():
        return AppcastValidation(False, (f"Appcast does not exist: {path}",), 0)

    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        return AppcastValidation(False, (f"Appcast XML parse failed: {exc}",), 0)

    enclosures = list(root.iter("enclosure"))
    if not enclosures:
        errors.append("Appcast contains no enclosure elements.")

    expected_normalized_version = normalize_release_version(expected_version)
    matched_enclosures = 0
    for index, enclosure in enumerate(enclosures, start=1):
        url = (enclosure.get("url") or "").strip()
        length_value = (enclosure.get("length") or "").strip()
        ed_signature = _sparkle_attr(enclosure, "edSignature").strip()
        version = normalize_release_version(_sparkle_attr(enclosure, "version"))
        short_version = normalize_release_version(_sparkle_attr(enclosure, "shortVersionString"))

        if not url:
            errors.append(f"Enclosure #{index} has an empty URL.")
        elif not url.startswith("https://"):
            errors.append(f"Enclosure #{index} URL must use HTTPS: {url!r}.")
        if not ed_signature:
            errors.append(f"Enclosure #{index} has no non-empty sparkle:edSignature.")
        if not _positive_int(length_value):
            errors.append(f"Enclosure #{index} has invalid positive length: {length_value!r}.")

        artifact_matches = expected_artifact_name is None or expected_artifact_name in url
        if not artifact_matches:
            continue

        matched_enclosures += 1
        if expected_normalized_version and version != expected_normalized_version:
            errors.append(
                f"Enclosure #{index} sparkle:version {version!r} does not match "
                f"{expected_normalized_version!r}."
            )
        if expected_normalized_version and short_version != expected_normalized_version:
            errors.append(
                f"Enclosure #{index} sparkle:shortVersionString {short_version!r} does not "
                f"match {expected_normalized_version!r}."
            )

    if expected_artifact_name is not None and matched_enclosures == 0:
        errors.append(f"No enclosure URL references expected artifact {expected_artifact_name!r}.")

    return AppcastValidation(not errors, tuple(errors), matched_enclosures)


def _sparkle_attr(element: ET.Element, name: str) -> str:
    return element.get(f"{{{SPARKLE_NAMESPACE}}}{name}") or element.get(f"sparkle:{name}") or ""


def _positive_int(value: str) -> bool:
    try:
        return int(value) > 0
    except ValueError:
        return False
