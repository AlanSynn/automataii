"""Shared macOS architecture helpers for build scripts."""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path

MACOS_ARCH_CHOICES = ("auto", "arm64", "x86_64", "universal2")
THIN_MACOS_ARCHES = frozenset({"arm64", "x86_64"})
UNIVERSAL2_ARCHES = frozenset({"arm64", "x86_64"})
PYINSTALLER_TARGET_ARCH_ENV = "PYINSTALLER_TARGET_ARCH"


def host_arch() -> str:
    """Return the current thin macOS architecture label."""
    machine = platform.machine()
    return "arm64" if machine == "arm64" else "x86_64"


def pyinstaller_target_arch(arch: str) -> str | None:
    """Return the PyInstaller target architecture argument for an explicit arch."""
    if arch == "auto":
        return None
    return arch


def dmg_filename(app_name: str, arch_label: str | None = None) -> str:
    if arch_label:
        return f"Automataii-macos-{arch_label}.dmg"
    return f"{app_name}.dmg"


def executable_arches(executable: Path | None = None) -> set[str]:
    """Return Mach-O architectures for an executable when macOS tools can report them."""
    executable_path = Path(sys.executable if executable is None else executable).resolve()
    lipo = shutil.which("lipo")
    if lipo:
        result = subprocess.run(
            [lipo, "-archs", str(executable_path)],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return set(result.stdout.split())

    file_cmd = shutil.which("file")
    if not file_cmd:
        return set()

    result = subprocess.run(
        [file_cmd, str(executable_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return set()

    output = result.stdout
    return {arch for arch in UNIVERSAL2_ARCHES if arch in output}


def is_universal2_capable(executable: Path | None = None) -> bool | None:
    """Return whether an executable has both universal2 slices, or None if unknown."""
    arches = executable_arches(executable)
    if not arches:
        return None
    return UNIVERSAL2_ARCHES.issubset(arches)
