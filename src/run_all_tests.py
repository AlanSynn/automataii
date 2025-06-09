#!/usr/bin/env python3
"""
Comprehensive test runner for Automataii
Runs all available tests and generates a summary report
"""

import sys
import os
import subprocess
import time
from pathlib import Path
from typing import List, Dict, Tuple

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class TestRunner:
    """Manages running all tests and collecting results"""
    
    def __init__(self):
        self.results = []
        self.start_time = None
        
    def run_python_test(self, test_file: str, description: str) -> Tuple[bool, str]:
        """Run a Python test file and return success status and output"""
        print(f"\n{'='*60}")
        print(f"Running: {description}")
        print(f"File: {test_file}")
        print(f"{'='*60}")
        
        try:
            result = subprocess.run(
                [sys.executable, test_file],
                capture_output=True,
                text=True,
                timeout=60  # 60 second timeout
            )
            
            output = result.stdout + result.stderr
            success = result.returncode == 0
            
            # Print output
            print(output)
            
            return success, output
            
        except subprocess.TimeoutExpired:
            print("❌ Test timed out after 60 seconds")
            return False, "Test timed out"
        except Exception as e:
            print(f"❌ Error running test: {e}")
            return False, str(e)
    
    def find_test_files(self) -> List[Dict[str, str]]:
        """Find all test files in the project"""
        tests = []
        
        # Specific test files we know about
        known_tests = [
            {
                "file": "test_basic_functionality.py",
                "description": "Basic Functionality Tests"
            },
            {
                "file": "test_ui_components.py", 
                "description": "UI Component Tests"
            },
            {
                "file": "automataii/modules/automata_base/quick_test.py",
                "description": "Automata Base Module Tests"
            }
        ]
        
        # Add tests that exist
        for test in known_tests:
            if Path(test["file"]).exists():
                tests.append(test)
        
        # Search for more test files
        for pattern in ["test_*.py", "*_test.py"]:
            for test_file in Path("automataii").rglob(pattern):
                # Skip vendor and __pycache__ directories
                if "vendor" in str(test_file) or "__pycache__" in str(test_file):
                    continue
                    
                # Skip files we already have
                if any(str(test_file) == t["file"] for t in tests):
                    continue
                    
                tests.append({
                    "file": str(test_file),
                    "description": f"Test: {test_file.stem}"
                })
        
        return tests
    
    def run_all_tests(self):
        """Run all discovered tests"""
        self.start_time = time.time()
        
        print("🧪 Automataii Comprehensive Test Suite")
        print("="*60)
        
        # Find all tests
        tests = self.find_test_files()
        print(f"\nFound {len(tests)} test files")
        
        # Run each test
        for test in tests:
            success, output = self.run_python_test(test["file"], test["description"])
            
            self.results.append({
                "file": test["file"],
                "description": test["description"],
                "success": success,
                "output": output
            })
        
        # Generate summary
        self.print_summary()
    
    def print_summary(self):
        """Print test summary"""
        duration = time.time() - self.start_time
        
        print("\n" + "="*60)
        print("📊 TEST SUMMARY")
        print("="*60)
        
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r["success"])
        failed_tests = total_tests - passed_tests
        
        print(f"\nTotal tests run: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"⏱️  Duration: {duration:.2f} seconds")
        
        if failed_tests > 0:
            print("\nFailed tests:")
            for result in self.results:
                if not result["success"]:
                    print(f"  ❌ {result['description']} ({result['file']})")
        
        # Success rate
        if total_tests > 0:
            success_rate = (passed_tests / total_tests) * 100
            print(f"\nSuccess rate: {success_rate:.1f}%")
            
            if success_rate == 100:
                print("\n🎉 All tests passed!")
            elif success_rate >= 80:
                print("\n✅ Most tests passed")
            elif success_rate >= 50:
                print("\n⚠️  Some tests failed")
            else:
                print("\n❌ Many tests failed")
        
        # Write detailed report
        self.write_report()
    
    def write_report(self):
        """Write detailed test report to file"""
        report_path = Path("test_report.txt")
        
        with open(report_path, "w") as f:
            f.write("Automataii Test Report\n")
            f.write("=" * 60 + "\n")
            f.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Duration: {time.time() - self.start_time:.2f} seconds\n")
            f.write("\n")
            
            for result in self.results:
                f.write(f"\nTest: {result['description']}\n")
                f.write(f"File: {result['file']}\n")
                f.write(f"Result: {'PASSED' if result['success'] else 'FAILED'}\n")
                f.write("-" * 40 + "\n")
                f.write(result['output'][:5000])  # Limit output length
                if len(result['output']) > 5000:
                    f.write("\n... (output truncated) ...\n")
                f.write("\n" + "=" * 60 + "\n")
        
        print(f"\n📝 Detailed report written to: {report_path}")

def main():
    """Main entry point"""
    print("Starting Automataii test suite...\n")
    
    runner = TestRunner()
    runner.run_all_tests()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())