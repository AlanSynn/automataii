#!/usr/bin/env python3
"""Validate MotionSmith Sparkle appcast metadata before OTA publication."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from automataii.utils.update_config import validate_signed_appcast  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a signed Sparkle appcast.")
    parser.add_argument("appcast", type=Path, help="Path to appcast.xml")
    parser.add_argument(
        "--expected-artifact",
        help="Expected DMG filename that at least one enclosure URL must reference.",
    )
    parser.add_argument(
        "--expected-version",
        help="Expected release version for sparkle:version and sparkle:shortVersionString.",
    )
    args = parser.parse_args()

    validation = validate_signed_appcast(
        args.appcast,
        expected_artifact_name=args.expected_artifact,
        expected_version=args.expected_version,
    )
    if validation.passed:
        print(
            "Signed appcast validation passed "
            f"({validation.matched_enclosure_count} matching enclosure(s))."
        )
        return 0

    for error in validation.errors:
        print(f"::error::{error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
