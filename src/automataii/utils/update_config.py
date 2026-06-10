"""Update and OTA configuration shared by app runtime and packaging scripts."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse

UPDATE_SITE_BASE_URL = "https://alansynn.com/motionsmith/"
DEFAULT_APPCAST_URL = f"{UPDATE_SITE_BASE_URL}appcast.xml"
DEFAULT_RELEASES_URL = "https://github.com/AlanSynn/motionsmith/releases/latest"
MOTIONSMITH_PAGES_REPO = "AlanSynn/motionsmith"
MOTIONSMITH_PAGES_BRANCH = "master"

SPARKLE_VERSION = "2.9.3"
SPARKLE_DISTRIBUTION_FILENAME = "Sparkle-2.9.3.tar.xz"
SPARKLE_DISTRIBUTION_URL = (
    "https://github.com/sparkle-project/Sparkle/releases/download/"
    f"{SPARKLE_VERSION}/{SPARKLE_DISTRIBUTION_FILENAME}"
)
SPARKLE_DISTRIBUTION_SHA256 = "74a07da821f92b79310009954c0e15f350173374a3abe39095b4fc5096916be6"

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
    referenced_urls: tuple[str, ...] = ()


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
    expected_url_prefix: str | None = None,
    payload_dir: str | Path | None = None,
) -> AppcastValidation:
    """Validate that an appcast contains signed Sparkle OTA metadata.

    This validates feed shape, HTTPS hosting, signatures, versions, and
    optionally that every appcast-referenced URL exists in a local publication
    payload. Cryptographic EdDSA verification remains Sparkle's responsibility.
    """
    path = Path(appcast_path)
    errors: list[str] = []
    referenced_urls: list[str] = []
    if not path.exists():
        return AppcastValidation(False, (f"Appcast does not exist: {path}",), 0)

    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        return AppcastValidation(False, (f"Appcast XML parse failed: {exc}",), 0)

    payload_root = Path(payload_dir) if payload_dir is not None else None
    normalized_prefix = expected_url_prefix.rstrip("/") + "/" if expected_url_prefix else None
    expected_normalized_version = normalize_release_version(expected_version)

    items = list(root.iter("item"))
    if not items:
        items = [root]

    matched_enclosures = 0
    enclosure_count = 0
    for item_index, item in enumerate(items, start=1):
        item_version = normalize_release_version(_sparkle_child_text(item, "version"))
        item_short_version = normalize_release_version(
            _sparkle_child_text(item, "shortVersionString")
        )
        _collect_release_notes_reference(
            item,
            item_index,
            referenced_urls,
            errors,
            normalized_prefix,
            payload_root,
        )

        for enclosure in item.findall("enclosure"):
            enclosure_count += 1
            url = (enclosure.get("url") or "").strip()
            length_value = (enclosure.get("length") or "").strip()
            ed_signature = _sparkle_attr(enclosure, "edSignature").strip()
            version = normalize_release_version(_sparkle_attr(enclosure, "version")) or item_version
            short_version = (
                normalize_release_version(_sparkle_attr(enclosure, "shortVersionString"))
                or item_short_version
                or version
            )

            if not url:
                errors.append(f"Enclosure #{enclosure_count} has an empty URL.")
            else:
                referenced_urls.append(url)
                _validate_referenced_url(
                    url,
                    f"Enclosure #{enclosure_count}",
                    errors,
                    normalized_prefix,
                    payload_root,
                )
            if not ed_signature:
                errors.append(f"Enclosure #{enclosure_count} has no non-empty sparkle:edSignature.")
            if not _positive_int(length_value):
                errors.append(
                    f"Enclosure #{enclosure_count} has invalid positive length: {length_value!r}."
                )

            artifact_matches = expected_artifact_name is None or expected_artifact_name in url
            if not artifact_matches:
                continue

            matched_enclosures += 1
            if expected_normalized_version and version != expected_normalized_version:
                errors.append(
                    f"Enclosure #{enclosure_count} sparkle:version {version!r} does not match "
                    f"{expected_normalized_version!r}."
                )
            if expected_normalized_version and short_version != expected_normalized_version:
                errors.append(
                    f"Enclosure #{enclosure_count} sparkle:shortVersionString "
                    f"{short_version!r} does not match {expected_normalized_version!r}."
                )

    if enclosure_count == 0:
        errors.append("Appcast contains no enclosure elements.")
    if expected_artifact_name is not None and matched_enclosures == 0:
        errors.append(f"No enclosure URL references expected artifact {expected_artifact_name!r}.")

    return AppcastValidation(
        not errors,
        tuple(errors),
        matched_enclosures,
        tuple(dict.fromkeys(referenced_urls)),
    )


def _collect_release_notes_reference(
    item: ET.Element,
    item_index: int,
    referenced_urls: list[str],
    errors: list[str],
    expected_url_prefix: str | None,
    payload_dir: Path | None,
) -> None:
    notes = _sparkle_child(item, "releaseNotesLink")
    if notes is None or notes.text is None:
        return
    url = notes.text.strip()
    if not url:
        return
    referenced_urls.append(url)
    _validate_referenced_url(
        url,
        f"Item #{item_index} releaseNotesLink",
        errors,
        expected_url_prefix,
        payload_dir,
    )


def _validate_referenced_url(
    url: str,
    label: str,
    errors: list[str],
    expected_url_prefix: str | None,
    payload_dir: Path | None,
) -> None:
    if not url.startswith("https://"):
        errors.append(f"{label} URL must use HTTPS: {url!r}.")
    if expected_url_prefix is not None and not url.startswith(expected_url_prefix):
        errors.append(f"{label} URL {url!r} does not start with {expected_url_prefix!r}.")
    if (
        payload_dir is None
        or expected_url_prefix is None
        or not url.startswith(expected_url_prefix)
    ):
        return
    relative = url.removeprefix(expected_url_prefix)
    expected_path = _safe_payload_path(relative, payload_dir)
    if expected_path is None:
        errors.append(f"{label} URL has unsafe payload path: {url!r}.")
        return
    if not expected_path.exists():
        errors.append(f"{label} references missing payload file: {expected_path}.")


def _safe_payload_path(relative_url_path: str, payload_dir: Path) -> Path | None:
    """Return the local payload path only when the URL path is safe."""
    parsed = urlparse(relative_url_path)
    if parsed.params or parsed.query or parsed.fragment:
        return None
    decoded_path = _unquote_repeated(parsed.path)
    if (
        decoded_path is None
        or not decoded_path
        or "%" in decoded_path
        or decoded_path.startswith(("/", "\\"))
        or "\\" in decoded_path
    ):
        return None
    parts = tuple(decoded_path.split("/"))
    if any(part in ("", ".", "..") for part in parts):
        return None
    payload_root = payload_dir.resolve()
    candidate = payload_root.joinpath(*parts).resolve()
    try:
        candidate.relative_to(payload_root)
    except ValueError:
        return None
    return candidate


def _unquote_repeated(value: str) -> str | None:
    """Decode URL escapes until stable, failing closed on over-encoded paths."""
    current = value
    for _ in range(32):
        decoded = unquote(current)
        if decoded == current:
            return decoded
        if decoded.count("/") > current.count("/") or decoded.count("\\") > current.count("\\"):
            return None
        current = decoded
    return None


def _sparkle_attr(element: ET.Element, name: str) -> str:
    return element.get(f"{{{SPARKLE_NAMESPACE}}}{name}") or element.get(f"sparkle:{name}") or ""


def _sparkle_child_text(element: ET.Element, name: str) -> str:
    child = _sparkle_child(element, name)
    if child is None or child.text is None:
        return ""
    return child.text.strip()


def _sparkle_child(element: ET.Element, name: str) -> ET.Element | None:
    namespaced = f"{{{SPARKLE_NAMESPACE}}}{name}"
    raw = f"sparkle:{name}"
    for child in element:
        if child.tag in (namespaced, raw):
            return child
    return None


def _positive_int(value: str) -> bool:
    try:
        return int(value) > 0
    except ValueError:
        return False
