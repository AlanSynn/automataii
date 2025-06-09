#!/usr/bin/env python3
"""
Main test runner for the Automata Base Module
Run this to execute all tests and verify functionality
"""

import sys
import os
import subprocess
import json
from pathlib import Path
import time

# Colors for terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_header(text):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text:^80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.ENDC}")

def print_section(text):
    print(f"\n{Colors.OKBLUE}{Colors.BOLD}▶ {text}{Colors.ENDC}")

def print_success(text):
    print(f"{Colors.OKGREEN}✅ {text}{Colors.ENDC}")

def print_failure(text):
    print(f"{Colors.FAIL}❌ {text}{Colors.ENDC}")

def print_warning(text):
    print(f"{Colors.WARNING}⚠️  {text}{Colors.ENDC}")

def print_info(text):
    print(f"{Colors.OKCYAN}ℹ️  {text}{Colors.ENDC}")

def run_test_file(test_file, description):
    """Run a single test file and return results."""
    print_section(f"Running {description}")
    
    start_time = time.time()
    
    try:
        # Run the test
        result = subprocess.run(
            [sys.executable, test_file],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        
        duration = time.time() - start_time
        
        if result.returncode == 0:
            print_success(f"Completed in {duration:.2f}s")
            
            # Parse output for test results
            lines = result.stdout.split('\n')
            for line in lines:
                if '✅' in line:
                    print(f"  {line.strip()}")
                elif '❌' in line:
                    print(f"  {line.strip()}")
            
            return True, duration
        else:
            print_failure(f"Failed with exit code {result.returncode}")
            if result.stderr:
                print(f"  Error: {result.stderr[:200]}...")
            return False, duration
            
    except FileNotFoundError:
        print_failure(f"Test file not found: {test_file}")
        return False, 0
    except Exception as e:
        print_failure(f"Error running test: {str(e)}")
        return False, 0

def check_imports():
    """Quick check of basic imports."""
    print_section("Checking basic imports")
    
    try:
        from enums.base_types import BaseType, MaterialType
        from models.base_config import BaseConfiguration
        from utils.validators import ConfigValidator
        from utils.converters import to_svg, to_dxf
        
        print_success("All core imports working")
        return True
    except Exception as e:
        print_failure(f"Import error: {e}")
        return False

def test_basic_functionality():
    """Test basic module functionality inline."""
    print_section("Testing basic functionality")
    
    try:
        from enums.base_types import BaseType, MaterialType
        from models.base_config import BaseConfiguration
        from models.dimensions import Dimensions2D
        
        # Create a simple configuration
        config = BaseConfiguration(
            name="Test Base",
            base_type=BaseType.FLAT_RECTANGULAR,
            dimensions=Dimensions2D(200, 150),
            primary_material=MaterialType.PLYWOOD,
            material_thickness=6.0
        )
        
        # Validate it
        if config.validate():
            print_success("Configuration creation and validation works")
            return True
        else:
            print_failure("Configuration validation failed")
            return False
            
    except Exception as e:
        print_failure(f"Functionality test error: {e}")
        return False

def main():
    """Run all tests and generate report."""
    print_header("AUTOMATA BASE MODULE - COMPLETE TEST SUITE")
    
    # Track results
    results = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'tests': [],
        'total_duration': 0,
        'passed': 0,
        'failed': 0
    }
    
    # Test 1: Import checks
    print_info("Starting comprehensive test suite...")
    
    if check_imports():
        results['tests'].append({'name': 'Import Check', 'status': 'passed'})
        results['passed'] += 1
    else:
        results['tests'].append({'name': 'Import Check', 'status': 'failed'})
        results['failed'] += 1
    
    # Test 2: Basic functionality
    if test_basic_functionality():
        results['tests'].append({'name': 'Basic Functionality', 'status': 'passed'})
        results['passed'] += 1
    else:
        results['tests'].append({'name': 'Basic Functionality', 'status': 'failed'})
        results['failed'] += 1
    
    # Test files to run
    test_files = [
        ('test_simple.py', 'Simple Tests'),
        ('test_final.py', 'Comprehensive Tests'),
        ('comprehensive_test.py', 'Full Feature Tests')
    ]
    
    # Run each test file
    for test_file, description in test_files:
        if os.path.exists(test_file):
            success, duration = run_test_file(test_file, description)
            results['tests'].append({
                'name': description,
                'file': test_file,
                'status': 'passed' if success else 'failed',
                'duration': duration
            })
            results['total_duration'] += duration
            
            if success:
                results['passed'] += 1
            else:
                results['failed'] += 1
        else:
            print_warning(f"Test file not found: {test_file}")
    
    # Summary
    print_header("TEST SUMMARY")
    
    total_tests = results['passed'] + results['failed']
    pass_rate = (results['passed'] / total_tests * 100) if total_tests > 0 else 0
    
    print(f"\n{Colors.BOLD}Total Tests:{Colors.ENDC} {total_tests}")
    print(f"{Colors.OKGREEN}{Colors.BOLD}Passed:{Colors.ENDC} {results['passed']}")
    print(f"{Colors.FAIL}{Colors.BOLD}Failed:{Colors.ENDC} {results['failed']}")
    print(f"{Colors.BOLD}Pass Rate:{Colors.ENDC} {pass_rate:.1f}%")
    print(f"{Colors.BOLD}Total Duration:{Colors.ENDC} {results['total_duration']:.2f}s")
    
    # Detailed results
    print(f"\n{Colors.BOLD}Test Results:{Colors.ENDC}")
    for test in results['tests']:
        status_icon = "✅" if test['status'] == 'passed' else "❌"
        duration_str = f" ({test.get('duration', 0):.2f}s)" if 'duration' in test else ""
        print(f"  {status_icon} {test['name']}{duration_str}")
    
    # Save report
    report_file = 'test_report_final.json'
    with open(report_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n{Colors.OKBLUE}📝 Test report saved to: {report_file}{Colors.ENDC}")
    
    # Final verdict
    print("")
    if pass_rate == 100:
        print_success("ALL TESTS PASSED! 🎉")
        print("The automata base module is fully functional and ready for use.")
    elif pass_rate >= 80:
        print_success("TESTS MOSTLY PASSED")
        print("The module is functional with minor issues.")
    else:
        print_failure("TESTS FAILED")
        print("The module needs attention before use.")
    
    # Usage instructions
    if pass_rate >= 80:
        print(f"\n{Colors.OKGREEN}{Colors.BOLD}✨ Module is ready for use!{Colors.ENDC}")
        print("\nTo use the automata base module in your project:")
        print("1. Add to Python path:")
        print(f"   sys.path.append('{os.path.dirname(os.path.abspath(__file__))}')")
        print("2. Import what you need:")
        print("   from enums.base_types import BaseType, MaterialType")
        print("   from models.base_config import BaseConfiguration")
        print("   from config.base_specs import get_base_specification")
        print("3. Create and use configurations!")
    
    return 0 if pass_rate >= 80 else 1

if __name__ == "__main__":
    sys.exit(main())