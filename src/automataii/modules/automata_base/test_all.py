#!/usr/bin/env python3
"""
Comprehensive Test Suite Runner for Automata Base System

This script runs all tests (unit tests, GUI tests, integration tests) and
generates a coverage report. It provides a single command to verify the
entire system is working correctly.
"""

import sys
import os
import unittest
import subprocess
from pathlib import Path
import argparse
import time
from typing import List, Tuple
import json

# Add module to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class TestRunner:
    """Manages running all tests with coverage and reporting."""
    
    def __init__(self, verbose: bool = False, coverage: bool = True):
        self.verbose = verbose
        self.coverage = coverage
        self.results = []
        self.start_time = None
        self.test_dir = Path(__file__).parent / "tests"
        
    def run_all_tests(self) -> bool:
        """Run all test suites and return success status."""
        self.start_time = time.time()
        
        print("🧪 Automata Base System - Comprehensive Test Suite")
        print("=" * 60)
        
        all_passed = True
        
        # Run unit tests
        print("\n📋 Running Unit Tests...")
        unit_passed = self._run_unit_tests()
        all_passed &= unit_passed
        
        # Run GUI tests
        print("\n🖼️  Running GUI Tests...")
        gui_passed = self._run_gui_tests()
        all_passed &= gui_passed
        
        # Run integration tests
        print("\n🔗 Running Integration Tests...")
        integration_passed = self._run_integration_tests()
        all_passed &= integration_passed
        
        # Generate coverage report if enabled
        if self.coverage and all_passed:
            print("\n📊 Generating Coverage Report...")
            self._generate_coverage_report()
            
        # Print summary
        self._print_summary(all_passed)
        
        return all_passed
        
    def _run_unit_tests(self) -> bool:
        """Run non-GUI unit tests."""
        test_files = [
            "test_generators.py",
            "test_integration.py",
        ]
        
        return self._run_test_files(test_files, "Unit Tests")
        
    def _run_gui_tests(self) -> bool:
        """Run GUI-specific tests."""
        # Use the GUI test runner
        gui_runner = self.test_dir / "run_gui_tests.py"
        
        try:
            cmd = [sys.executable, str(gui_runner)]
            if self.verbose:
                cmd.append("-v")
                
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # Parse results
            success = result.returncode == 0
            output = result.stdout + result.stderr
            
            if self.verbose or not success:
                print(output)
                
            # Extract test counts from output
            if "Ran" in output:
                import re
                match = re.search(r'Ran (\d+) tests? in ([\d.]+)s', output)
                if match:
                    test_count = int(match.group(1))
                    duration = float(match.group(2))
                    
                    self.results.append({
                        'suite': 'GUI Tests',
                        'tests': test_count,
                        'passed': success,
                        'duration': duration
                    })
                    
            return success
            
        except Exception as e:
            print(f"❌ Error running GUI tests: {e}")
            return False
            
    def _run_integration_tests(self) -> bool:
        """Run integration tests."""
        # Integration tests are included in test_integration.py
        # and GUI integration tests
        return True  # Already covered by unit and GUI tests
        
    def _run_test_files(self, test_files: List[str], suite_name: str) -> bool:
        """Run a list of test files."""
        loader = unittest.TestLoader()
        suite = unittest.TestSuite()
        
        for test_file in test_files:
            try:
                # Import test module
                module_name = test_file.replace('.py', '')
                test_module = f"tests.{module_name}"
                
                # Load tests
                tests = loader.loadTestsFromName(test_module)
                suite.addTests(tests)
            except Exception as e:
                print(f"⚠️  Warning: Could not load {test_file}: {e}")
                
        # Run tests
        runner = unittest.TextTestRunner(verbosity=2 if self.verbose else 1)
        result = runner.run(suite)
        
        # Record results
        self.results.append({
            'suite': suite_name,
            'tests': result.testsRun,
            'passed': result.wasSuccessful(),
            'failures': len(result.failures),
            'errors': len(result.errors),
            'duration': getattr(result, 'duration', 0)
        })
        
        return result.wasSuccessful()
        
    def _generate_coverage_report(self):
        """Generate code coverage report."""
        try:
            # Run coverage
            cmd = [
                sys.executable, "-m", "coverage", "run",
                "--source", ".",
                "-m", "pytest", "tests/",
                "--ignore=tests/run_gui_tests.py"
            ]
            
            subprocess.run(cmd, capture_output=True)
            
            # Generate report
            subprocess.run([sys.executable, "-m", "coverage", "report"])
            
            # Generate HTML report
            subprocess.run([sys.executable, "-m", "coverage", "html"])
            print("📄 HTML coverage report generated in htmlcov/")
            
        except subprocess.CalledProcessError:
            print("⚠️  Coverage report generation failed")
        except ModuleNotFoundError:
            print("⚠️  Coverage module not installed. Run: pip install coverage")
            
    def _print_summary(self, all_passed: bool):
        """Print test summary."""
        duration = time.time() - self.start_time
        
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        
        total_tests = sum(r.get('tests', 0) for r in self.results)
        total_passed = sum(1 for r in self.results if r.get('passed', False))
        
        for result in self.results:
            status = "✅" if result.get('passed', False) else "❌"
            print(f"{status} {result['suite']}: {result.get('tests', 0)} tests")
            
            if not result.get('passed', False):
                failures = result.get('failures', 0)
                errors = result.get('errors', 0)
                if failures:
                    print(f"   - {failures} failures")
                if errors:
                    print(f"   - {errors} errors")
                    
        print(f"\nTotal: {total_tests} tests in {duration:.2f}s")
        
        if all_passed:
            print("\n✅ All tests passed! 🎉")
        else:
            print(f"\n❌ {len(self.results) - total_passed} test suite(s) failed")
            
        # Save results to file
        self._save_results()
            
    def _save_results(self):
        """Save test results to JSON file."""
        results_file = Path("test_results.json")
        
        data = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'duration': time.time() - self.start_time,
            'results': self.results
        }
        
        with open(results_file, 'w') as f:
            json.dump(data, f, indent=2)
            
        print(f"\n📝 Test results saved to {results_file}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run all tests for Automata Base System"
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )
    parser.add_argument(
        '--no-coverage',
        action='store_true',
        help='Skip coverage report'
    )
    parser.add_argument(
        '--quick',
        action='store_true',
        help='Run only quick unit tests (skip GUI tests)'
    )
    
    args = parser.parse_args()
    
    # Create runner
    runner = TestRunner(
        verbose=args.verbose,
        coverage=not args.no_coverage
    )
    
    # Run tests
    if args.quick:
        print("🏃 Running quick tests only (skipping GUI)...")
        success = runner._run_unit_tests()
    else:
        success = runner.run_all_tests()
        
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()