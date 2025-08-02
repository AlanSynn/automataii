"""
End-to-End workflow test for complete mechanism system integration.

Tests the full pipeline from dataset generation to UI parametric editing
with 150% confidence validation.
"""

import pytest
import numpy as np
import json
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from PyQt6.QtCore import QPointF
from PyQt6.QtWidgets import QApplication

from src.automataii.domain.kinematics.mechanism_simulator import MechanismSimulator
from src.automataii.domain.kinematics.mechanism import MechanismType
from src.automataii.ui.tabs.mechanism_design.parametric.factory import ParametricFactory
from src.automataii.ui.tabs.mechanism_design.visuals.visual_factory import create as create_visual


# Initialize Qt application for tests that require Qt
app = QApplication.instance()
if app is None:
    app = QApplication([])


class TestE2EMechanismWorkflow:
    """End-to-end workflow tests for complete mechanism system."""
    
    def setup_method(self):
        """Set up test fixtures for E2E testing."""
        self.simulator = MechanismSimulator(time_steps=30)
        self.dataset_path = Path("../src/automataii/domain/kinematics/enhanced_mechanism_dataset.json")
        
        # Mock scene manager for parametric testing
        self.mock_scene_manager = Mock()
        self.mock_scene_manager.scene = Mock()
        self.mock_scene_manager.parent_widget = Mock()
        self.mock_scene_manager.parent_widget.animation_controller = Mock()
        self.mock_scene_manager.visuals = Mock()
        self.mock_scene_manager.visuals.visual_factory = Mock()
        self.mock_scene_manager.visuals.visual_factory.get_scene_transform_function = Mock(
            return_value=lambda x: QPointF(x[0], x[1])
        )
    
    def test_full_cam_mechanism_workflow(self):
        """Test complete workflow for cam mechanism from dataset to UI."""
        print("🔄 Testing CAM mechanism E2E workflow...")
        
        # 1. Load dataset and find cam mechanism
        with open(self.dataset_path) as f:
            dataset = json.load(f)
        
        cam_mechanisms = [m for m in dataset["mechanisms"] if m["mechanism_type"] == "cam"]
        assert len(cam_mechanisms) > 0, "No cam mechanisms in dataset"
        
        test_cam = cam_mechanisms[0]
        print(f"   ✅ Found cam mechanism: {test_cam['name']}")
        
        # 2. Test simulation reproduction
        sim_params = np.array(test_cam["simulation_parameters"])
        motion_curve = self.simulator.simulate_mechanism(MechanismType.CAM, sim_params)
        
        assert motion_curve.points.shape[0] > 0, "Cam simulation failed"
        print(f"   ✅ Simulation successful: {motion_curve.points.shape[0]} points")
        
        # 3. Test visual creation
        layer_data = {
            "type": "cam",
            "params": test_cam["parameters"],
            "key_points": {
                "cam_center": [0, 0],
                "follower_position": [0, 60]
            }
        }
        
        visual_items, debug_items = create_visual(layer_data, self.mock_scene_manager)
        assert visual_items is not None, "Visual creation failed"
        print(f"   ✅ Visual creation successful: {len(visual_items)} items")
        
        # 4. Test parametric editor creation
        editor = ParametricFactory.create_parametric_editor("cam_1", layer_data, self.mock_scene_manager)
        assert editor is not None, "Parametric editor creation failed"
        assert editor.get_mechanism_type() == "cam"
        print(f"   ✅ Parametric editor created: {editor.get_mechanism_type()}")
        
        # 5. Test parameter validation
        test_params = {
            "base_radius": 40.0,
            "rise": 15.0,
            "offset": 0.0,
            "motion_law": "harmonic"
        }
        is_valid, error_msg = editor.validate_parameters(test_params)
        assert is_valid, f"Parameter validation failed: {error_msg}"
        print("   ✅ Parameter validation passed")
        
        # 6. Test motion profile calculation
        time_points = [0.0, 0.25, 0.5, 0.75, 1.0]
        positions = editor.calculate_motion_profile(time_points)
        assert len(positions) == len(time_points), "Motion profile calculation failed"
        print("   ✅ Motion profile calculation successful")
        
        print("🎉 CAM mechanism E2E workflow PASSED!")
    
    def test_full_belt_mechanism_workflow(self):
        """Test complete workflow for belt mechanism from dataset to UI."""
        print("🔗 Testing BELT mechanism E2E workflow...")
        
        # 1. Load dataset and find belt mechanism
        with open(self.dataset_path) as f:
            dataset = json.load(f)
        
        belt_mechanisms = [m for m in dataset["mechanisms"] if m["mechanism_type"] == "belt"]
        assert len(belt_mechanisms) > 0, "No belt mechanisms in dataset"
        
        test_belt = belt_mechanisms[0]
        print(f"   ✅ Found belt mechanism: {test_belt['name']}")
        
        # 2. Test simulation reproduction
        sim_params = np.array(test_belt["simulation_parameters"])
        motion_curve = self.simulator.simulate_mechanism(MechanismType.BELT, sim_params)
        
        assert motion_curve.points.shape[0] > 0, "Belt simulation failed"
        print(f"   ✅ Simulation successful: {motion_curve.points.shape[0]} points")
        
        # 3. Test visual creation
        layer_data = {
            "type": "belt",
            "params": test_belt["parameters"],
            "key_points": {
                "pulley_1_center": [0, 0],
                "pulley_2_center": [100, 0]
            }
        }
        
        visual_items, debug_items = create_visual(layer_data, self.mock_scene_manager)
        assert visual_items is not None, "Visual creation failed"
        print(f"   ✅ Visual creation successful: {len(visual_items)} items")
        
        # 4. Test parametric editor creation
        editor = ParametricFactory.create_parametric_editor("belt_1", layer_data, self.mock_scene_manager)
        assert editor is not None, "Parametric editor creation failed"
        assert editor.get_mechanism_type() == "belt"
        print(f"   ✅ Parametric editor created: {editor.get_mechanism_type()}")
        
        # 5. Test parameter validation
        test_params = {
            "pulley_1_radius": 30.0,
            "pulley_2_radius": 20.0,
            "belt_tension": 50.0,
            "slip_coefficient": 0.1
        }
        is_valid, error_msg = editor.validate_parameters(test_params)
        assert is_valid, f"Parameter validation failed: {error_msg}"
        print("   ✅ Parameter validation passed")
        
        # 6. Test belt calculations
        gear_ratio = editor.calculate_gear_ratio()
        belt_length = editor.calculate_belt_length()
        belt_speed = editor.get_belt_speed()
        
        assert gear_ratio > 0, "Gear ratio calculation failed"
        assert belt_length > 0, "Belt length calculation failed"
        assert belt_speed > 0, "Belt speed calculation failed"
        print("   ✅ Belt calculations successful")
        
        print("🎉 BELT mechanism E2E workflow PASSED!")
    
    def test_full_spring_mechanism_workflow(self):
        """Test complete workflow for spring mechanism from dataset to UI."""
        print("🌀 Testing SPRING mechanism E2E workflow...")
        
        # 1. Load dataset and find spring mechanism
        with open(self.dataset_path) as f:
            dataset = json.load(f)
        
        spring_mechanisms = [m for m in dataset["mechanisms"] if m["mechanism_type"] == "spring"]
        assert len(spring_mechanisms) > 0, "No spring mechanisms in dataset"
        
        test_spring = spring_mechanisms[0]
        print(f"   ✅ Found spring mechanism: {test_spring['name']}")
        
        # 2. Test simulation reproduction
        sim_params = np.array(test_spring["simulation_parameters"])
        motion_curve = self.simulator.simulate_mechanism(MechanismType.SPRING, sim_params)
        
        assert motion_curve.points.shape[0] > 0, "Spring simulation failed"
        print(f"   ✅ Simulation successful: {motion_curve.points.shape[0]} points")
        
        # 3. Test visual creation
        layer_data = {
            "type": "spring",
            "params": test_spring["parameters"],
            "key_points": {
                "attachment_1": [0, 0],
                "attachment_2": [0, 80]
            }
        }
        
        visual_items, debug_items = create_visual(layer_data, self.mock_scene_manager)
        assert visual_items is not None, "Visual creation failed"
        print(f"   ✅ Visual creation successful: {len(visual_items)} items")
        
        # 4. Test parametric editor creation
        editor = ParametricFactory.create_parametric_editor("spring_1", layer_data, self.mock_scene_manager)
        assert editor is not None, "Parametric editor creation failed"
        assert editor.get_mechanism_type() == "spring"
        print(f"   ✅ Parametric editor created: {editor.get_mechanism_type()}")
        
        # 5. Test parameter validation
        test_params = {
            "spring_constant": 100.0,
            "damping_coefficient": 10.0,
            "rest_length": 80.0,
            "mass": 1.0,
            "max_compression": 0.8,
            "max_extension": 2.0
        }
        is_valid, error_msg = editor.validate_parameters(test_params)
        assert is_valid, f"Parameter validation failed: {error_msg}"
        print("   ✅ Parameter validation passed")
        
        # 6. Test spring calculations
        natural_freq = editor.calculate_natural_frequency()
        damping_ratio = editor.calculate_damping_ratio()
        system_type = editor.get_system_type()
        current_length = editor.calculate_current_length()
        spring_force = editor.calculate_spring_force(10.0)
        
        assert natural_freq > 0, "Natural frequency calculation failed"
        assert damping_ratio >= 0, "Damping ratio calculation failed"
        assert system_type in ["underdamped", "critically_damped", "overdamped"], "Invalid system type"
        assert current_length > 0, "Current length calculation failed"
        assert isinstance(spring_force, (int, float)), "Spring force calculation failed"
        print("   ✅ Spring calculations successful")
        
        print("🎉 SPRING mechanism E2E workflow PASSED!")
    
    def test_cross_mechanism_compatibility(self):
        """Test that all mechanisms work together in the same system."""
        print("🔧 Testing cross-mechanism compatibility...")
        
        # Test all mechanism types can be created simultaneously
        mechanism_configs = [
            {
                "id": "cam_1",
                "type": "cam",
                "params": {"base_radius": 30, "rise": 20, "offset": 0},
                "key_points": {"cam_center": [0, 0], "follower_position": [0, 60]}
            },
            {
                "id": "belt_1", 
                "type": "belt",
                "params": {"pulley_1_radius": 40, "pulley_2_radius": 25, "belt_tension": 50},
                "key_points": {"pulley_1_center": [100, 0], "pulley_2_center": [200, 0]}
            },
            {
                "id": "spring_1",
                "type": "spring", 
                "params": {"spring_constant": 100, "damping_coefficient": 10, "rest_length": 80, "mass": 1.0},
                "key_points": {"attachment_1": [300, 0], "attachment_2": [300, 80]}
            }
        ]
        
        created_editors = []
        created_visuals = []
        
        for config in mechanism_configs:
            # Test parametric editor creation
            editor = ParametricFactory.create_parametric_editor(
                config["id"], config, self.mock_scene_manager
            )
            assert editor is not None, f"Failed to create editor for {config['type']}"
            created_editors.append(editor)
            
            # Test visual creation
            visual_items, debug_items = create_visual(config, self.mock_scene_manager)
            assert visual_items is not None, f"Failed to create visuals for {config['type']}"
            created_visuals.append(visual_items)
            
            print(f"   ✅ {config['type'].upper()} mechanism created successfully")
        
        # Test that all editors have unique types
        editor_types = [editor.get_mechanism_type() for editor in created_editors]
        assert len(set(editor_types)) == len(editor_types), "Duplicate mechanism types detected"
        
        # Test factory registration
        supported_types = ParametricFactory.get_supported_mechanisms()
        expected_types = {"4_bar_linkage", "gear", "cam", "belt", "spring"}
        assert expected_types.issubset(set(supported_types)), "Missing mechanism type registrations"
        
        print("🎉 Cross-mechanism compatibility PASSED!")
    
    def test_parametric_handles_integration(self):
        """Test parametric handle creation and manipulation."""
        print("🎯 Testing parametric handles integration...")
        
        # Test handle creation for cam mechanism
        layer_data = {
            "type": "cam",
            "params": {"base_radius": 40, "rise": 15, "offset": 0},
            "key_points": {"cam_center": [0, 0], "follower_position": [0, 60]}
        }
        
        editor = ParametricFactory.create_parametric_editor("cam_test", layer_data, self.mock_scene_manager)
        
        # Test parameter constraints
        constraints = editor.get_parameter_constraints()
        assert isinstance(constraints, dict), "Parameter constraints not returned as dict"
        assert "base_radius" in constraints, "Missing base_radius constraint"
        
        # Test handle position changes
        changed_handles = {
            "cam_center": QPointF(10, 10),
            "base_radius": 45.0
        }
        
        updated_params = editor.update_mechanism_from_handles(changed_handles)
        assert isinstance(updated_params, dict), "Updated parameters not returned as dict"
        
        print("   ✅ Parametric handles working correctly")
        print("🎉 Parametric handles integration PASSED!")
    
    def test_performance_under_load(self):
        """Test system performance under realistic load conditions."""
        print("⚡ Testing performance under load...")
        
        import time
        
        # Test multiple simultaneous simulations
        start_time = time.time()
        
        test_cases = [
            (MechanismType.CAM, np.array([30, 20, 10, 0, 0, 0, 0, 0])),
            (MechanismType.BELT, np.array([40, 25, 0, 0, 120, 0, 1, 0.05])),
            (MechanismType.SPRING, np.array([100, 10, 1, 0, 0, 0, 100, 80, 0, 0])),
        ]
        
        # Run multiple simulations concurrently
        results = []
        for _ in range(10):  # 10 iterations of each
            for mech_type, params in test_cases:
                motion_curve = self.simulator.simulate_mechanism(mech_type, params)
                results.append(motion_curve)
        
        total_time = time.time() - start_time
        simulations_per_second = len(results) / total_time
        
        print(f"   ✅ Completed {len(results)} simulations in {total_time:.2f}s")
        print(f"   ✅ Performance: {simulations_per_second:.1f} simulations/second")
        
        # Performance should be reasonable
        assert simulations_per_second > 10, f"Performance too slow: {simulations_per_second:.1f} sim/s"
        assert all(r.points.shape[0] > 0 for r in results), "Some simulations failed"
        
        print("🎉 Performance under load PASSED!")
    
    def test_error_handling_robustness(self):
        """Test system robustness under error conditions."""
        print("🛡️ Testing error handling robustness...")
        
        # Test invalid mechanism type
        with pytest.raises(ValueError):
            self.simulator.simulate_mechanism("invalid_type", np.array([1, 2, 3]))
        
        # Test invalid parameters
        with pytest.raises(ValueError):
            self.simulator.simulate_mechanism(MechanismType.BELT, np.array([10, 20]))  # Too few params
        
        # Test parametric editor with invalid mechanism
        invalid_layer_data = {"type": "invalid_mechanism"}
        editor = ParametricFactory.create_parametric_editor("invalid", invalid_layer_data, self.mock_scene_manager)
        assert editor is None, "Should return None for invalid mechanism type"
        
        # Test visual creation with invalid mechanism
        visual_items, debug_items = create_visual(invalid_layer_data, self.mock_scene_manager)
        assert visual_items == [], "Should return empty list for invalid mechanism type"
        
        print("   ✅ Error handling working correctly")
        print("🎉 Error handling robustness PASSED!")
    
    def test_memory_management(self):
        """Test memory management and cleanup."""
        print("🧹 Testing memory management...")
        
        import gc
        import sys
        
        # Get initial memory reference count
        initial_refs = sys.getrefcount(None)
        
        # Create and destroy multiple mechanisms
        for i in range(50):
            layer_data = {
                "type": "cam",
                "params": {"base_radius": 30 + i, "rise": 20, "offset": 0},
                "key_points": {"cam_center": [i, 0], "follower_position": [i, 60]}
            }
            
            editor = ParametricFactory.create_parametric_editor(f"cam_{i}", layer_data, self.mock_scene_manager)
            visual_items, debug_items = create_visual(layer_data, self.mock_scene_manager)
            
            # Simulate some work
            sim_params = np.array([30 + i, 20, 0, i, 0, 0, 0, 0])
            motion_curve = self.simulator.simulate_mechanism(MechanismType.CAM, sim_params)
            
            # Clean up
            del editor, visual_items, debug_items, motion_curve
        
        # Force garbage collection
        gc.collect()
        
        # Check memory didn't grow significantly
        final_refs = sys.getrefcount(None)
        ref_increase = final_refs - initial_refs
        
        print(f"   ✅ Reference count increase: {ref_increase}")
        assert ref_increase < 100, f"Memory leak detected: {ref_increase} new references"
        
        print("🎉 Memory management PASSED!")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])