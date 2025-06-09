#!/usr/bin/env python3
"""
Comprehensive verification script for Automata Base System
Tests all components and reports their status
"""

import sys
import os
import json
from pathlib import Path
from typing import Dict, List, Tuple
import traceback

# Add module to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class SystemVerifier:
    """Verifies all components of the automata base system."""
    
    def __init__(self):
        self.results = {
            'core': {},
            'generators': {},
            'integration': {},
            'ui': {},
            'exports': {},
            'tests': {}
        }
        
    def verify_all(self) -> bool:
        """Run all verification tests."""
        print("🔍 Automata Base System - Comprehensive Verification")
        print("=" * 60)
        
        all_passed = True
        
        # Test core components
        print("\n📦 Core Components:")
        all_passed &= self.verify_core()
        
        # Test generators
        print("\n🏗️ Generators:")
        all_passed &= self.verify_generators()
        
        # Test integration
        print("\n🔗 Integration:")
        all_passed &= self.verify_integration()
        
        # Test UI (if available)
        print("\n🖼️ UI Components:")
        all_passed &= self.verify_ui()
        
        # Test exports
        print("\n📤 Export Formats:")
        all_passed &= self.verify_exports()
        
        # Test suite
        print("\n🧪 Test Suite:")
        all_passed &= self.verify_tests()
        
        # Summary
        self.print_summary()
        
        return all_passed
        
    def verify_core(self) -> bool:
        """Verify core components."""
        passed = True
        
        # Test imports
        components = [
            ('Enums', 'from enums.base_types import BaseType, MaterialType, AssemblyMethod'),
            ('Models', 'from models.base_config import BaseConfiguration; from models.dimensions import Dimensions2D, Dimensions3D'),
            ('Config', 'from config.base_specs import BASE_SPECIFICATIONS'),
        ]
        
        for name, import_stmt in components:
            try:
                exec(import_stmt)
                self.results['core'][name] = '✅ Pass'
                print(f"  ✅ {name}")
            except Exception as e:
                self.results['core'][name] = f'❌ Fail: {str(e)}'
                print(f"  ❌ {name}: {str(e)}")
                passed = False
                
        # Test basic functionality
        try:
            from models.base_config import BaseConfiguration
            from enums.base_types import BaseType, MaterialType
            
            config = BaseConfiguration(
                base_type=BaseType.BOX_BASE,
                dimensions={'width': 100, 'height': 80, 'depth': 60},
                material=MaterialType.PLYWOOD,
                thickness=3.0
            )
            
            # Test validation
            if config.validate():
                print("  ✅ Configuration validation")
                self.results['core']['Validation'] = '✅ Pass'
            else:
                print("  ❌ Configuration validation failed")
                self.results['core']['Validation'] = '❌ Fail'
                passed = False
                
        except Exception as e:
            print(f"  ❌ Configuration test: {str(e)}")
            self.results['core']['Configuration'] = f'❌ Fail: {str(e)}'
            passed = False
            
        return passed
        
    def verify_generators(self) -> bool:
        """Verify generator components."""
        passed = True
        
        generators = [
            ('StructuredGenerator', 'structured'),
            ('BodyCavityGenerator', 'cavity'),
            ('AxisGenerator', 'axis')
        ]
        
        for gen_name, gen_type in generators:
            try:
                if gen_type == 'structured':
                    from generators.structured_generator import StructuredGenerator
                    from models.base_config import BaseConfiguration
                    from enums.base_types import BaseType
                    
                    config = BaseConfiguration(
                        base_type=BaseType.BOX_BASE,
                        dimensions={'width': 150, 'height': 100, 'depth': 80}
                    )
                    
                    generator = StructuredGenerator(config)
                    result = generator.generate()
                    
                    if 'components' in result and 'mounting_points' in result:
                        print(f"  ✅ {gen_name}")
                        self.results['generators'][gen_name] = '✅ Pass'
                    else:
                        print(f"  ❌ {gen_name}: Invalid output")
                        self.results['generators'][gen_name] = '❌ Invalid output'
                        passed = False
                        
                elif gen_type == 'cavity':
                    from generators.body_cavity_generator import BodyCavityGenerator, CavityConfig
                    
                    config = CavityConfig(
                        body_shape={'type': 'ellipse', 'width': 100, 'height': 150},
                        cavity_depth=20
                    )
                    
                    generator = BodyCavityGenerator(config)
                    result = generator.generate()
                    
                    print(f"  ✅ {gen_name}")
                    self.results['generators'][gen_name] = '✅ Pass'
                    
                elif gen_type == 'axis':
                    from generators.axis_generator import AxisGenerator, AxisConfig
                    
                    config = AxisConfig(shaft_diameter=8, shaft_length=100)
                    generator = AxisGenerator(config)
                    result = generator.generate()
                    
                    print(f"  ✅ {gen_name}")
                    self.results['generators'][gen_name] = '✅ Pass'
                    
            except Exception as e:
                print(f"  ❌ {gen_name}: {str(e)}")
                self.results['generators'][gen_name] = f'❌ Fail: {str(e)}'
                passed = False
                
        return passed
        
    def verify_integration(self) -> bool:
        """Verify integration components."""
        passed = True
        
        try:
            from integration.mechanism_adapter import MechanismAdapter
            from integration.export_manager import ExportManager
            
            # Test mechanism adapter
            base_data = {
                'components': [],
                'mounting_points': [(50, 50), (100, 50)],
                'dimensions': {'width': 150, 'height': 100}
            }
            
            adapter = MechanismAdapter(base_data)
            adapter.add_mechanism(
                {'type': 'fourbar', 'bounds': {'width': 40, 'height': 30}},
                'test_mech'
            )
            
            adapted = adapter.adapt()
            if 'mechanisms' in adapted:
                print("  ✅ MechanismAdapter")
                self.results['integration']['MechanismAdapter'] = '✅ Pass'
            else:
                print("  ❌ MechanismAdapter: No mechanisms in output")
                self.results['integration']['MechanismAdapter'] = '❌ No mechanisms'
                passed = False
                
            # Test export manager
            exporter = ExportManager(adapted)
            print("  ✅ ExportManager")
            self.results['integration']['ExportManager'] = '✅ Pass'
            
        except Exception as e:
            print(f"  ❌ Integration: {str(e)}")
            self.results['integration']['Integration'] = f'❌ Fail: {str(e)}'
            passed = False
            
        return passed
        
    def verify_ui(self) -> bool:
        """Verify UI components if available."""
        passed = True
        
        try:
            # Check if PyQt6 is available
            try:
                import PyQt6
                UI_AVAILABLE = True
            except ImportError:
                UI_AVAILABLE = False
            
            if UI_AVAILABLE:
                from ui.base_selection_widget import BaseSelectionWidget
                from ui.base_preview_widget import BasePreviewWidget
                
                # Test if we can create widgets (requires QApplication)
                print("  ✅ UI components available")
                self.results['ui']['Available'] = '✅ Yes'
                
                # List available widgets
                widgets = ['BaseSelectionWidget', 'BasePreviewWidget']
                for widget in widgets:
                    print(f"    • {widget}")
                    self.results['ui'][widget] = '✅ Available'
            else:
                print("  ⚠️  UI components not available (PyQt6 may not be installed)")
                self.results['ui']['Available'] = '⚠️ Not available'
                
        except Exception as e:
            print(f"  ❌ UI verification: {str(e)}")
            self.results['ui']['Error'] = f'❌ Fail: {str(e)}'
            passed = False
            
        return passed
        
    def verify_exports(self) -> bool:
        """Verify export functionality."""
        passed = True
        
        # Create test design
        test_design = {
            'base': {'type': 'box', 'dimensions': {'width': 100, 'height': 80}},
            'components': [
                {'type': 'wall', 'points': [(0, 0), (100, 0), (100, 80), (0, 80)]}
            ],
            'mechanisms': {}
        }
        
        try:
            from integration.export_manager import ExportManager
            exporter = ExportManager(test_design)
            
            # Test each export format
            formats = {
                'json': ('export_json', 'test_verify.json'),
                'svg': ('export_svg', 'test_verify.svg'),
                'dxf': ('export_dxf', 'test_verify.dxf')
            }
            
            for fmt, (method, filename) in formats.items():
                try:
                    getattr(exporter, method)(filename)
                    
                    # Verify file exists and has content
                    if os.path.exists(filename):
                        size = os.path.getsize(filename)
                        if size > 0:
                            print(f"  ✅ {fmt.upper()} export ({size} bytes)")
                            self.results['exports'][fmt] = f'✅ Pass ({size} bytes)'
                            
                            # Verify content for specific formats
                            if fmt == 'json':
                                with open(filename, 'r') as f:
                                    data = json.load(f)
                                    if 'base' in data:
                                        print(f"    • Valid JSON structure")
                                        
                            elif fmt == 'svg':
                                with open(filename, 'r') as f:
                                    content = f.read()
                                    if '<svg' in content and '</svg>' in content:
                                        print(f"    • Valid SVG structure")
                                        
                            # Clean up
                            os.remove(filename)
                        else:
                            print(f"  ❌ {fmt.upper()}: Empty file")
                            self.results['exports'][fmt] = '❌ Empty file'
                            passed = False
                    else:
                        print(f"  ❌ {fmt.upper()}: File not created")
                        self.results['exports'][fmt] = '❌ File not created'
                        passed = False
                        
                except Exception as e:
                    print(f"  ❌ {fmt.upper()}: {str(e)}")
                    self.results['exports'][fmt] = f'❌ Fail: {str(e)}'
                    passed = False
                    
        except Exception as e:
            print(f"  ❌ Export verification: {str(e)}")
            self.results['exports']['Error'] = f'❌ Fail: {str(e)}'
            passed = False
            
        return passed
        
    def verify_tests(self) -> bool:
        """Verify test suite."""
        passed = True
        
        # Check if test files exist
        test_files = [
            'tests/test_generators.py',
            'tests/test_integration.py',
            'tests/test_gui_base_selection.py',
            'tests/test_gui_preview.py',
            'tests/test_gui_integration.py',
            'tests/e2e/test_e2e_base_workflow.py',
            'tests/e2e/test_e2e_canvas_operations.py',
            'tests/e2e/test_e2e_mechanism_integration.py',
            'tests/e2e/test_e2e_export_functionality.py'
        ]
        
        existing_tests = 0
        for test_file in test_files:
            if os.path.exists(test_file):
                existing_tests += 1
                
        print(f"  ✅ Test files: {existing_tests}/{len(test_files)} found")
        self.results['tests']['Files'] = f'{existing_tests}/{len(test_files)} found'
        
        # Try to run a simple test
        try:
            import subprocess
            result = subprocess.run(
                [sys.executable, '-m', 'pytest', 'tests/', '--collect-only'],
                capture_output=True,
                text=True
            )
            
            if 'collected' in result.stdout:
                # Extract number of tests
                import re
                match = re.search(r'collected (\d+) items?', result.stdout)
                if match:
                    num_tests = match.group(1)
                    print(f"  ✅ Collected {num_tests} tests")
                    self.results['tests']['Collected'] = f'✅ {num_tests} tests'
            else:
                print("  ⚠️  Could not collect tests")
                self.results['tests']['Collected'] = '⚠️ Collection failed'
                
        except Exception as e:
            print(f"  ⚠️  Test collection: {str(e)}")
            self.results['tests']['Collection'] = f'⚠️ {str(e)}'
            
        return passed
        
    def print_summary(self):
        """Print verification summary."""
        print("\n" + "=" * 60)
        print("📊 VERIFICATION SUMMARY")
        print("=" * 60)
        
        # Count results
        total_tests = 0
        passed_tests = 0
        failed_tests = 0
        warnings = 0
        
        for category, results in self.results.items():
            print(f"\n{category.upper()}:")
            for test, result in results.items():
                print(f"  {test}: {result}")
                total_tests += 1
                
                if '✅' in result:
                    passed_tests += 1
                elif '❌' in result:
                    failed_tests += 1
                elif '⚠️' in result:
                    warnings += 1
                    
        # Overall summary
        print("\n" + "-" * 60)
        print(f"Total checks: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"⚠️  Warnings: {warnings}")
        
        if failed_tests == 0:
            print("\n✅ All critical components verified successfully!")
        else:
            print(f"\n❌ {failed_tests} components need attention")
            
        # Save results
        with open('verification_report.json', 'w') as f:
            json.dump(self.results, f, indent=2)
        print("\n📝 Detailed report saved to verification_report.json")


def main():
    """Main entry point."""
    verifier = SystemVerifier()
    success = verifier.verify_all()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()