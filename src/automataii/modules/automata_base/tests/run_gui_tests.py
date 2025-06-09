#!/usr/bin/env python
"""
GUI Test Runner for Automata Base Module

This script runs all GUI tests with proper configuration and reporting.
Can be run directly or through pytest.
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))
sys.path.insert(0, str(project_root))

import pytest


def run_gui_tests(verbose=True, coverage=False):
    """
    Run all GUI tests with options.
    
    Args:
        verbose: Show detailed test output
        coverage: Generate coverage report
    """
    args = [
        str(Path(__file__).parent),  # Test directory
        "-v" if verbose else "",
        "--tb=short",  # Short traceback format
        "-k", "gui",  # Only run GUI tests
    ]
    
    if coverage:
        args.extend([
            "--cov=automataii.modules.automata_base.gui",
            "--cov-report=html",
            "--cov-report=term-missing"
        ])
    
    # Filter out empty strings
    args = [arg for arg in args if arg]
    
    print("Running GUI tests...")
    print(f"Command: pytest {' '.join(args)}")
    
    return pytest.main(args)


def run_specific_test(test_name):
    """
    Run a specific GUI test file.
    
    Args:
        test_name: Name of test file (without .py extension)
    """
    test_path = Path(__file__).parent / f"test_gui_{test_name}.py"
    
    if not test_path.exists():
        print(f"Test file not found: {test_path}")
        return 1
    
    args = [
        str(test_path),
        "-v",
        "--tb=short"
    ]
    
    print(f"Running {test_name} tests...")
    return pytest.main(args)


def list_gui_tests():
    """List all available GUI test files."""
    test_dir = Path(__file__).parent
    test_files = sorted(test_dir.glob("test_gui_*.py"))
    
    print("Available GUI test files:")
    for test_file in test_files:
        print(f"  - {test_file.stem}")
    
    return test_files


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run GUI tests for Automata Base module")
    parser.add_argument(
        "test",
        nargs="?",
        help="Specific test to run (e.g., 'base_selection_widget')"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available test files"
    )
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Generate coverage report"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Less verbose output"
    )
    
    args = parser.parse_args()
    
    if args.list:
        list_gui_tests()
        sys.exit(0)
    
    if args.test:
        # Run specific test
        exit_code = run_specific_test(args.test)
    else:
        # Run all GUI tests
        exit_code = run_gui_tests(
            verbose=not args.quiet,
            coverage=args.coverage
        )
    
    # Print summary
    if exit_code == 0:
        print("\n✅ All tests passed!")
    else:
        print("\n❌ Some tests failed!")
    
    sys.exit(exit_code)