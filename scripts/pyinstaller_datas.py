"""Helpers for resilient PyInstaller data-file declarations."""

from __future__ import annotations

from collections.abc import Iterable
from glob import glob
from pathlib import Path

DataEntry = tuple[str, str]


def existing_datas(entries: Iterable[DataEntry]) -> list[DataEntry]:
    """Return only PyInstaller data entries whose source exists.

    PyInstaller fails the build when a spec's ``datas`` list contains a
    missing directory or an unmatched glob. Some MotionSmith data directories
    are optional or have been removed during refactors, so release specs should
    include them only when they are present in the checkout.
    """
    return [(source, destination) for source, destination in entries if source_exists(source)]


def source_exists(source: str) -> bool:
    """Return whether a PyInstaller data source path or glob has at least one match."""
    if any(pattern_char in source for pattern_char in "*?[]"):
        return bool(glob(source))
    return Path(source).exists()
