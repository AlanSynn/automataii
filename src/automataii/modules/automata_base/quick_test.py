#!/usr/bin/env python3
"""
Quick Test Script for Automata Base System

This script allows quick testing of specific functionality without
running the entire test suite. Useful for development and debugging.
"""

import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

# Add module to path
module_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(os.path.dirname(os.path.dirname(module_dir)))
sys.path.insert(0, src_dir)

from automataii.modules.automata_base.enums.base_types import BaseType, MaterialType, MountingType, AssemblyMethod
from automataii.modules.automata_base.models.base_config import BaseConfiguration
from automataii.modules.automata_base.models.dimensions import Dimensions2D, Dimensions3D, MountingPoint, Point2D, Unit
from automataii.modules.automata_base.utils.validators import validate_base_configuration

# These components are not yet implemented
StructuredGenerator = None
MechanismAdapter = None
ExportManager = None
UI_AVAILABLE = False
BaseSelectionWidget = None
BasePreviewWidget = None


class QuickTester:
    """Quick test runner for specific functionality."""
    
    def __init__(self):
        self.app = QApplication(sys.argv)
        
    def test_base_generation(self):
        """Test base generation without UI."""
        print("🧪 Testing Base Configuration...")
        
        # Create configuration
        config = BaseConfiguration(
            name="Test Box Base",
            base_type=BaseType.BOX_ENCLOSED,
            dimensions=Dimensions3D(width=200, height=150, depth=100, unit=Unit.MM),
            primary_material=MaterialType.PLYWOOD,
            material_thickness=3.0,
            mounting_type=MountingType.FREESTANDING,
            assembly_method=AssemblyMethod.SCREWS
        )
        
        print(f"✅ Created base configuration: {config.name}")
        print(f"   Type: {config.base_type.value}")
        print(f"   Dimensions: {config.dimensions.width} x {config.dimensions.height} x {config.dimensions.depth} {config.dimensions.unit.value}")
        print(f"   Material: {config.primary_material.value}")
        
        # Add mounting points
        config.add_mounting_point(MountingPoint(
            position=Point2D(100, 75),
            hole_diameter=6.0,
            thread_type="M6"
        ))
        
        print(f"   Mounting points: {len(config.mounting_points)}")
        
        # Validate configuration
        issues = validate_base_configuration(config)
        print(f"   Validation: {'✅ Passed' if not issues else '❌ Failed'}")
        if issues:
            for issue in issues:
                print(f"      - {issue}")
        
        # Test scaling
        print("\n🧪 Testing Scaling...")
        scaled = config.scale(1.5)
        print(f"✅ Scaled configuration by 1.5x")
        print(f"   New dimensions: {scaled.dimensions.width} x {scaled.dimensions.height} x {scaled.dimensions.depth} {scaled.dimensions.unit.value}")
        
        # Test conversion to dict
        print("\n🧪 Testing Serialization...")
        config_dict = config.to_dict()
        print(f"✅ Converted to dictionary with {len(config_dict)} fields")
        
        print("\n📊 Configuration Summary:")
        print(f"   Volume: {config.dimensions.volume / 1000000:.2f} liters")
        print(f"   Surface area: {config.dimensions.surface_area / 100:.2f} cm²")
        print(f"   Bounding box diagonal: {config.dimensions.diagonal:.1f} mm")
                
    def test_ui_interaction(self):
        """Test UI components interactively."""
        if not UI_AVAILABLE:
            print("❌ UI components not available")
            return
            
        print("🧪 Testing UI Components...")
        
        # Create main window
        from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QWidget
        
        window = QMainWindow()
        window.setWindowTitle("Quick UI Test")
        
        central = QWidget()
        window.setCentralWidget(central)
        
        layout = QVBoxLayout(central)
        
        # Add selection widget
        print("   Adding BaseSelectionWidget...")
        selection = BaseSelectionWidget()
        layout.addWidget(selection)
        
        # Add preview widget
        print("   Adding BasePreviewWidget...")
        preview = BasePreviewWidget()
        preview.setMinimumHeight(400)
        layout.addWidget(preview)
        
        # Connect signals
        def on_config_changed(config):
            print(f"   Configuration changed: {config}")
            # Update preview with dummy mechanism
            preview.set_mechanisms([{
                'id': 'test',
                'type': 'fourbar',
                'bounds': {'width': 60, 'height': 40}
            }])
            
        selection.configuration_changed.connect(on_config_changed)
        
        # Show window
        window.show()
        
        # Auto-test sequence
        def test_sequence():
            print("\n🔄 Running automated UI test sequence...")
            
            # Test 1: Change base type
            print("   Test 1: Changing base type to cylindrical...")
            selection.base_type_combo.setCurrentText("Cylindrical")
            
            # Test 2: Update dimensions
            QTimer.singleShot(1000, lambda: (
                print("   Test 2: Updating dimensions..."),
                selection.dimension_spinners['diameter'].setValue(180),
                selection.dimension_spinners['height'].setValue(120)
            ))
            
            # Test 3: Change material
            QTimer.singleShot(2000, lambda: (
                print("   Test 3: Changing material..."),
                selection.material_combo.setCurrentText("Acrylic")
            ))
            
            # Test 4: Test preview zoom
            QTimer.singleShot(3000, lambda: (
                print("   Test 4: Testing preview zoom..."),
                preview.zoom_in(),
                preview.zoom_in()
            ))
            
            # Test 5: Toggle view mode
            QTimer.singleShot(4000, lambda: (
                print("   Test 5: Toggling view mode..."),
                preview.view_mode_button.click()
            ))
            
            print("\n✅ UI test sequence completed!")
            
        # Start test sequence after window is shown
        QTimer.singleShot(500, test_sequence)
        
        # Run app
        return self.app.exec()
        
    def test_specific_feature(self, feature: str):
        """Test a specific feature."""
        feature_tests = {
            'validation': self._test_validation,
            'materials': self._test_materials,
            'dimensions': self._test_dimensions,
            'mounting': self._test_mounting_points
        }
        
        if feature in feature_tests:
            print(f"\n🧪 Testing {feature}...")
            feature_tests[feature]()
        else:
            print(f"❌ Unknown feature: {feature}")
            print(f"   Available: {', '.join(feature_tests.keys())}")
            
    def _test_materials(self):
        """Test material properties and compatibility."""
        print("Testing material properties...")
        
        materials = [MaterialType.WOOD, MaterialType.ALUMINUM, MaterialType.PLASTIC_3D_PRINTED]
        
        for material in materials:
            props = MaterialType.get_properties(material)
            print(f"\n{material.value}:")
            print(f"   Density: {props.get('density', 'N/A')} kg/m³")
            print(f"   Strength: {props.get('strength', 'N/A')}")
            print(f"   Cost: {props.get('cost', 'N/A')}")
            print(f"   Workability: {props.get('workability', 'N/A')}")
        
    def _test_dimensions(self):
        """Test dimension calculations and conversions."""
        print("Testing dimension operations...")
        
        # Test 2D dimensions
        dim2d = Dimensions2D(width=100, height=50, unit=Unit.MM)
        print(f"\n2D Dimensions: {dim2d.width} x {dim2d.height} {dim2d.unit.value}")
        print(f"   Area: {dim2d.area} {dim2d.unit.value}²")
        print(f"   Perimeter: {dim2d.perimeter} {dim2d.unit.value}")
        print(f"   Aspect ratio: {dim2d.aspect_ratio:.2f}")
        
        # Convert to inches
        dim2d_inch = dim2d.to_unit(Unit.INCH)
        print(f"   In inches: {dim2d_inch.width:.2f} x {dim2d_inch.height:.2f} {dim2d_inch.unit.value}")
        
        # Test 3D dimensions
        dim3d = Dimensions3D(width=100, height=50, depth=80, unit=Unit.MM)
        print(f"\n3D Dimensions: {dim3d.width} x {dim3d.height} x {dim3d.depth} {dim3d.unit.value}")
        print(f"   Volume: {dim3d.volume / 1000:.1f} cm³")
        print(f"   Surface area: {dim3d.surface_area} {dim3d.unit.value}²")
        print(f"   Diagonal: {dim3d.diagonal:.1f} {dim3d.unit.value}")
        
    def _test_mounting_points(self):
        """Test mounting point creation and validation."""
        print("Testing mounting points...")
        
        # Create various mounting points
        mp1 = MountingPoint(
            position=Point2D(50, 50),
            hole_diameter=4.0,
            thread_type="M4"
        )
        
        mp2 = MountingPoint(
            position=Point2D(100, 100),
            hole_diameter=6.0,
            thread_type="M6",
            countersink=True,
            countersink_diameter=12.0
        )
        
        print(f"\nMounting Point 1:")
        print(f"   Position: ({mp1.position.x}, {mp1.position.y})")
        print(f"   Hole: {mp1.hole_diameter}mm {mp1.thread_type}")
        print(f"   Threaded: {mp1.is_threaded()}")
        
        print(f"\nMounting Point 2:")
        print(f"   Position: ({mp2.position.x}, {mp2.position.y})")
        print(f"   Hole: {mp2.hole_diameter}mm {mp2.thread_type}")
        print(f"   Countersink: {mp2.countersink} ({mp2.countersink_diameter}mm)")
        
        # Calculate distance between points
        distance = mp1.position.distance_to(mp2.position)
        print(f"\nDistance between points: {distance:.1f}mm")
                
    def _test_validation(self):
        """Test configuration validation."""
        print("Testing configuration validation...")
        
        # Test valid configuration
        print("\n1. Valid configuration:")
        valid_config = BaseConfiguration(
            name="Valid Test Base",
            base_type=BaseType.BOX_ENCLOSED,
            dimensions=Dimensions3D(width=150, height=100, depth=80),
            primary_material=MaterialType.PLYWOOD,
            material_thickness=3.0,
            mounting_type=MountingType.FREESTANDING
        )
        
        issues = validate_base_configuration(valid_config)
        print(f"   Result: {'✅ Passed' if not issues else '❌ Failed'}")
        if issues:
            for issue in issues:
                print(f"   - {issue}")
        
        # Test invalid configurations
        print("\n2. Testing invalid configurations:")
        
        # Negative dimensions
        try:
            invalid1 = BaseConfiguration(
                name="Invalid Dimensions",
                base_type=BaseType.FLAT_RECTANGULAR,
                dimensions=Dimensions2D(width=-100, height=50),
                primary_material=MaterialType.WOOD
            )
            print("   ❌ Should have failed on negative dimensions")
        except ValueError as e:
            print(f"   ✅ Correctly rejected negative dimensions: {e}")
        
        # Missing material thickness for flat base
        try:
            invalid2 = BaseConfiguration(
                name="Missing Thickness",
                base_type=BaseType.FLAT_RECTANGULAR,
                dimensions=Dimensions2D(width=100, height=50),
                primary_material=MaterialType.WOOD,
                material_thickness=None
            )
            issues = validate_base_configuration(invalid2)
            print(f"\n   Missing thickness test: {'❌ Failed' if not issues else '✅ Passed'}")
            if issues:
                print(f"   ✅ Correctly identified: {issues[0]}")
        except ValueError as e:
            print(f"\n   ✅ Correctly rejected missing thickness: {e}")
        
        # Incompatible mounting type
        try:
            invalid3 = BaseConfiguration(
                name="Bad Mounting",
                base_type=BaseType.FLAT_RECTANGULAR,
                dimensions=Dimensions2D(width=100, height=50),
                primary_material=MaterialType.WOOD,
                material_thickness=5.0,
                mounting_type=MountingType.CEILING
            )
            print("\n   ❌ Should have failed on incompatible mounting")
        except ValueError as e:
            print(f"\n   ✅ Correctly rejected incompatible mounting: {e}")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Quick test for Automata Base System")
    parser.add_argument('--ui', action='store_true', help="Test UI components")
    parser.add_argument('--feature', type=str, help="Test specific feature")
    parser.add_argument('--all', action='store_true', help="Run all quick tests")
    
    args = parser.parse_args()
    
    tester = QuickTester()
    
    if args.ui:
        sys.exit(tester.test_ui_interaction())
    elif args.feature:
        tester.test_specific_feature(args.feature)
    elif args.all:
        tester.test_base_generation()
        tester.test_specific_feature('materials')
        tester.test_specific_feature('dimensions')
        tester.test_specific_feature('mounting')
        tester.test_specific_feature('validation')
    else:
        # Default: run base generation test
        tester.test_base_generation()
        

if __name__ == "__main__":
    main()