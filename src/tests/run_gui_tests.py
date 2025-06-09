#!/usr/bin/env python3
"""Runner script for GUI tests with proper setup and teardown."""

import sys
import unittest
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication


def run_tests(test_module=None, verbosity=2):
    """Run GUI tests with proper Qt application setup."""
    # Ensure QApplication exists
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    # Create test suite
    if test_module:
        # Run specific test module
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromName(test_module)
    else:
        # Discover and run all GUI tests
        loader = unittest.TestLoader()
        start_dir = os.path.dirname(os.path.abspath(__file__))
        suite = loader.discover(start_dir, pattern='test_gui*.py')
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    
    # Clean up
    app.quit()
    
    return result.wasSuccessful()


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Run GUI tests for automata base system')
    parser.add_argument('test', nargs='?', help='Specific test module to run (e.g., test_gui_base_selection)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Increase verbosity')
    parser.add_argument('-q', '--quiet', action='store_true', help='Decrease verbosity')
    
    args = parser.parse_args()
    
    # Determine verbosity
    if args.quiet:
        verbosity = 0
    elif args.verbose:
        verbosity = 2
    else:
        verbosity = 1
    
    # Run tests
    success = run_tests(args.test, verbosity)
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)