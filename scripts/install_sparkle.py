#!/usr/bin/env python3
"""Install the pinned Sparkle distribution for MotionSmith release builds."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from automataii.utils.update_config import (  # noqa: E402
    SPARKLE_DISTRIBUTION_FILENAME,
    SPARKLE_DISTRIBUTION_SHA256,
    SPARKLE_DISTRIBUTION_URL,
    SPARKLE_VERSION,
)


class SparkleInstallError(RuntimeError):
    """Raised when the pinned Sparkle distribution cannot be installed."""


def install_sparkle(output_dir: Path) -> dict[str, Path | str]:
    """Download, checksum-verify, and extract the pinned Sparkle distribution."""
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = output_dir / SPARKLE_DISTRIBUTION_FILENAME
    root_dir = output_dir / f"Sparkle-{SPARKLE_VERSION}"

    if not archive_path.exists() or _sha256(archive_path) != SPARKLE_DISTRIBUTION_SHA256:
        with tempfile.NamedTemporaryFile(
            prefix=f"Sparkle-{SPARKLE_VERSION}-", suffix=".tar.xz", delete=False
        ) as handle:
            temp_archive = Path(handle.name)
        try:
            urllib.request.urlretrieve(SPARKLE_DISTRIBUTION_URL, temp_archive)
            digest = _sha256(temp_archive)
            if digest != SPARKLE_DISTRIBUTION_SHA256:
                raise SparkleInstallError(
                    "Sparkle distribution checksum mismatch: "
                    f"got {digest}, expected {SPARKLE_DISTRIBUTION_SHA256}"
                )
            temp_archive.replace(archive_path)
        finally:
            temp_archive.unlink(missing_ok=True)

    if root_dir.exists():
        shutil.rmtree(root_dir)
    root_dir.mkdir(parents=True)
    with tarfile.open(archive_path, mode="r:xz") as archive:
        archive.extractall(root_dir, filter="data")

    generate_appcast = root_dir / "bin" / "generate_appcast"
    sign_update = root_dir / "bin" / "sign_update"
    framework = root_dir / "Sparkle.framework"
    missing = [path for path in (generate_appcast, sign_update, framework) if not path.exists()]
    if missing:
        formatted = ", ".join(str(path) for path in missing)
        raise SparkleInstallError(f"Sparkle distribution is missing expected files: {formatted}")

    return {
        "sparkle_version": SPARKLE_VERSION,
        "sparkle_root": root_dir,
        "sparkle_bin_dir": root_dir / "bin",
        "sparkle_framework": framework,
        "generate_appcast": generate_appcast,
        "sign_update": sign_update,
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".sparkle"),
        help="Directory for the downloaded/extracted Sparkle distribution.",
    )
    parser.add_argument(
        "--github-output",
        type=Path,
        help="Optional $GITHUB_OUTPUT path to receive Sparkle tool paths.",
    )
    args = parser.parse_args()

    try:
        result = install_sparkle(args.output_dir)
    except SparkleInstallError as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1

    lines = [f"{name}={value}" for name, value in result.items()]
    if args.github_output is not None:
        with args.github_output.open("a", encoding="utf-8") as handle:
            for line in lines:
                handle.write(f"{line}\n")
    for line in lines:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
