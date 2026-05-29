#!/usr/bin/env python3
"""Shared macOS notarization command helpers."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

APPLE_NOTARY_PROFILE_ENV = "APPLE_NOTARY_PROFILE"
APPLE_ID_ENV = "APPLE_ID"
APPLE_TEAM_ID_ENV = "APPLE_TEAM_ID"
APPLE_APP_SPECIFIC_PASSWORD_ENV = "APPLE_APP_SPECIFIC_PASSWORD"


@dataclass(frozen=True)
class NotarySubmitPlan:
    """Safe-to-log metadata plus the command used for notarytool submission."""

    command: list[str]
    auth_description: str


def notarization_credentials_help() -> str:
    """Return a safe diagnostic for missing notarytool credentials."""
    return (
        "Set APPLE_NOTARY_PROFILE to a notarytool keychain profile. Store the "
        "profile first with: xcrun notarytool store-credentials <profile> "
        "--apple-id <apple-id> --team-id <team-id>. This repository also "
        "provides: make store-notary-profile PROFILE=AutomataiiNotary "
        "APPLE_ID=<apple-id> APPLE_TEAM_ID=<team-id>. Verify it with: "
        "xcrun notarytool history --keychain-profile <profile>."
    )


def notarytool_submit_plan(
    target_path: Path,
    env: Mapping[str, str] | None = None,
) -> NotarySubmitPlan | None:
    """Build a notarytool submit command without logging secrets.

    Require a keychain profile because it keeps Apple credentials out of both
    process arguments and command logs. CI jobs should create the temporary
    keychain profile immediately before calling this helper, then pass only the
    profile name through APPLE_NOTARY_PROFILE.
    """
    env = os.environ if env is None else env

    profile = env.get(APPLE_NOTARY_PROFILE_ENV, "").strip()
    if profile:
        return NotarySubmitPlan(
            command=[
                "xcrun",
                "notarytool",
                "submit",
                str(target_path),
                "--keychain-profile",
                profile,
                "--wait",
            ],
            auth_description=f"{APPLE_NOTARY_PROFILE_ENV} keychain profile '{profile}'",
        )

    return None
