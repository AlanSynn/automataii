#!/usr/bin/env python3
"""
Build script for native C++ extensions.

Usage:
    python build.py           # Build in release mode
    python build.py --debug   # Build in debug mode
    python build.py --clean   # Clean build directory

Requirements:
    - CMake >= 3.15
    - C++17 compiler (clang++, g++)
    - pybind11
    - Eigen3

Install dependencies (macOS):
    brew install cmake eigen pybind11

Install dependencies (Ubuntu):
    apt install cmake libeigen3-dev python3-pybind11
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def get_script_dir() -> Path:
    """Get the directory containing this script."""
    return Path(__file__).parent.resolve()


def check_dependencies() -> bool:
    """Check if required build dependencies are available."""
    missing = []

    # Check CMake
    if shutil.which("cmake") is None:
        missing.append("cmake")

    # Check C++ compiler
    if shutil.which("c++") is None and shutil.which("g++") is None:
        missing.append("C++ compiler (g++ or clang++)")

    if missing:
        print("Missing dependencies:")
        for dep in missing:
            print(f"  - {dep}")
        print("\nInstall with:")
        print("  macOS: brew install cmake")
        print("  Ubuntu: apt install cmake build-essential")
        return False

    return True


def build(debug: bool = False) -> int:
    """
    Build the native extension.

    Args:
        debug: Build in debug mode

    Returns:
        Exit code (0 = success)
    """
    script_dir = get_script_dir()
    build_dir = script_dir / "build"

    # Create build directory
    build_dir.mkdir(exist_ok=True)

    # Configure with CMake
    build_type = "Debug" if debug else "Release"
    cmake_args = [
        "cmake",
        "..",
        f"-DCMAKE_BUILD_TYPE={build_type}",
        f"-DCMAKE_INSTALL_PREFIX={script_dir}",
        "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
    ]

    # Use Ninja if available
    if shutil.which("ninja"):
        cmake_args.extend(["-G", "Ninja"])

    print(f"Configuring CMake ({build_type})...")
    result = subprocess.run(cmake_args, cwd=build_dir)
    if result.returncode != 0:
        print("CMake configuration failed")
        return result.returncode

    # Build
    print("Building...")
    build_args = ["cmake", "--build", ".", "--parallel"]
    result = subprocess.run(build_args, cwd=build_dir)
    if result.returncode != 0:
        print("Build failed")
        return result.returncode

    # Install to package directory
    print("Installing...")
    install_args = ["cmake", "--install", "."]
    result = subprocess.run(install_args, cwd=build_dir)
    if result.returncode != 0:
        print("Install failed")
        return result.returncode

    print("Build successful!")
    print(f"Module installed to: {script_dir}")
    return 0


def clean() -> int:
    """Remove build artifacts."""
    script_dir = get_script_dir()
    build_dir = script_dir / "build"

    if build_dir.exists():
        print(f"Removing {build_dir}")
        shutil.rmtree(build_dir)

    # Remove compiled modules
    for pattern in ["*.so", "*.pyd", "*.dylib"]:
        for f in script_dir.glob(pattern):
            if f.name.startswith("arap_native"):
                print(f"Removing {f}")
                f.unlink()

    print("Clean complete")
    return 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Build native C++ extensions")
    parser.add_argument("--debug", action="store_true", help="Build in debug mode")
    parser.add_argument("--clean", action="store_true", help="Clean build directory")
    args = parser.parse_args()

    if args.clean:
        return clean()

    if not check_dependencies():
        return 1

    return build(debug=args.debug)


if __name__ == "__main__":
    sys.exit(main())
