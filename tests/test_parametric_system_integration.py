"""
Integration tests for the parametric editing system.

Tests the complete workflow from handle creation to mechanism updates,
including all mechanism types and their specific constraints.

Author: AI Engineering Assistant
"""

import pytest
import math
from unittest.mock import Mock, MagicMock, patch
from PyQt6.QtCore import QPointF
from PyQt6.QtWidgets import QApplication

from src.automataii.ui.tabs.mechanism_design.parametric.factory import ParametricFactory
from src.automataii.ui.tabs.mechanism_design.parametric.controllers.parameter_controller import ParameterController

# Initialize Qt application for tests that require Qt
app = QApplication.instance()
if app is None:
    app = QApplication([])


class TestParametricSystemIntegration:
    """Integration tests for the complete parametric editing system."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_state_manager = Mock()
        self.mock_scene_manager = Mock()
        self.mock_scene_manager.parent_widget = Mock()
        self.mock_scene_manager.parent_widget.animation_controller = Mock()
        
        # Create parameter controller
        self.parameter_controller = ParameterController(self.mock_state_manager)
        
        # Mock mechanism layers
        self.mock_state_manager.mechanism_layers = {
            "linkage_1": {
                "type": "4_bar_linkage",
                "params": {
                    "l1": 100.0,
                    "l2": 80.0,
                    "l3": 60.0,
                    "l4": 90.0
                },
                "key_points": {
                    "ground_pivot_1": [0, 0],
                    "ground_pivot_2": [100, 0]
                }
            },
            "gear_1": {
                "type": "gear",
                "params": {
                    "gear_1_radius": 50.0,
                    "gear_2_radius": 30.0
                },
                "key_points": {
                    "gear_1_center": [0, 0],
                    "gear_2_center": [80, 0]
                }
            },
            "cam_1": {
                "type": "cam",
                "params": {
                    "base_radius": 40.0,
                    "rise": 15.0,
                    "offset": 0.0,
                    "motion_law": "harmonic"
                },
                "key_points": {
                    "cam_center": [0, 0],
                    "follower_position": [0, 60]
                }
            },
            "belt_1": {
                "type": "belt",
                "params": {
                    "pulley_1_radius": 30.0,
                    "pulley_2_radius": 20.0,
                    "belt_tension": 50.0,
                    "angular_velocity_1": 2.0
                },
                "key_points": {
                    "pulley_1_center": [0, 0],
                    "pulley_2_center": [100, 0]
                }
            },
            "spring_1": {
                "type": "spring",
                "params": {
                    "spring_constant": 100.0,
                    "damping_coefficient": 10.0,
                    "rest_length": 80.0,
                    "mass": 1.0
                },
                "key_points": {
                    "attachment_1": [0, 0],
                    "attachment_2": [0, 80]
                }
            }
        }
    
    def test_factory_mechanism_registration(self):
        """Test that all mechanism types are properly registered."""
        supported_mechanisms = ParametricFactory.get_supported_mechanisms()
        
        # Check that all expected mechanism types are registered
        assert "4_bar_linkage" in supported_mechanisms
        assert "gear" in supported_mechanisms
        assert "cam" in supported_mechanisms
        assert "belt" in supported_mechanisms
        assert "spring" in supported_mechanisms
        
        # Test mechanism support detection
        assert ParametricFactory.is_supported({"type": "4_bar_linkage"})
        assert ParametricFactory.is_supported({"type": "gear"})
        assert ParametricFactory.is_supported({"type": "cam"})
        assert ParametricFactory.is_supported({"type": "belt"})
        assert ParametricFactory.is_supported({"type": "spring"})
        assert not ParametricFactory.is_supported({"type": "unknown_mechanism"})
    
    @pytest.mark.skipif(not QApplication.instance(), reason="Requires Qt application")
    def test_linkage_parametric_editor_creation(self):
        """Test creation and operation of linkage parametric editor."""
        layer_data = self.mock_state_manager.mechanism_layers["linkage_1"]
        
        # Create parametric editor
        editor = ParametricFactory.create_parametric_editor("linkage_1", layer_data, self.mock_scene_manager)
        
        assert editor is not None
        assert editor.mechanism_type == "4_bar_linkage"
        assert editor.mechanism_id == "linkage_1"
        
        # Test parameter validation
        valid_params = {
            "l1": 100.0,
            "l2": 80.0,
            "l3": 60.0,
            "l4": 90.0
        }
        is_valid, error_msg = editor.validate_parameters(valid_params)
        assert is_valid, f"Valid parameters should pass validation: {error_msg}"
        
        # Test invalid parameters (violate Grashof condition)
        invalid_params = {
            "l1": 10.0,
            "l2": 80.0,
            "l3": 60.0,
            "l4": 90.0
        }
        is_valid, error_msg = editor.validate_parameters(invalid_params)
        assert not is_valid, "Invalid parameters should fail validation"
    
    @pytest.mark.skipif(not QApplication.instance(), reason="Requires Qt application")
    def test_gear_parametric_editor_creation(self):
        """Test creation and operation of gear parametric editor."""
        layer_data = self.mock_state_manager.mechanism_layers["gear_1"]
        
        # Create parametric editor
        editor = ParametricFactory.create_parametric_editor("gear_1", layer_data, self.mock_scene_manager)
        
        assert editor is not None
        assert editor.mechanism_type == "gear"
        assert editor.mechanism_id == "gear_1"
        
        # Test parameter validation
        valid_params = {
            "gear_1_radius": 50.0,
            "gear_2_radius": 30.0
        }
        is_valid, error_msg = editor.validate_parameters(valid_params)
        assert is_valid, f"Valid parameters should pass validation: {error_msg}"
        
        # Test gear ratio calculation
        gear_ratio = editor.calculate_gear_ratio()
        expected_ratio = 50.0 / 30.0
        assert abs(gear_ratio - expected_ratio) < 0.001, f"Gear ratio should be {expected_ratio}, got {gear_ratio}"
    
    @pytest.mark.skipif(not QApplication.instance(), reason="Requires Qt application")
    def test_cam_parametric_editor_creation(self):
        """Test creation and operation of cam parametric editor."""
        layer_data = self.mock_state_manager.mechanism_layers["cam_1"]
        
        # Create parametric editor
        editor = ParametricFactory.create_parametric_editor("cam_1", layer_data, self.mock_scene_manager)
        
        assert editor is not None
        assert editor.mechanism_type == "cam"
        assert editor.mechanism_id == "cam_1"
        
        # Test parameter validation
        valid_params = {
            "base_radius": 40.0,
            "rise": 15.0,
            "offset": 0.0,
            "motion_law": "harmonic"
        }
        is_valid, error_msg = editor.validate_parameters(valid_params)
        assert is_valid, f"Valid parameters should pass validation: {error_msg}"
        
        # Test invalid parameters
        invalid_params = {
            "base_radius": -10.0,  # Negative radius
            "rise": 0.0,  # Zero rise
            "motion_law": "invalid_law"
        }
        is_valid, error_msg = editor.validate_parameters(invalid_params)
        assert not is_valid, "Invalid parameters should fail validation"
        
        # Test motion profile calculation
        time_points = [0.0, 0.25, 0.5, 0.75, 1.0]
        positions = editor.calculate_motion_profile(time_points)
        assert len(positions) == len(time_points), "Motion profile should have same length as time points"
        assert all(isinstance(pos, (int, float)) for pos in positions), "All positions should be numeric"
    
    @pytest.mark.skipif(not QApplication.instance(), reason="Requires Qt application")
    def test_belt_parametric_editor_creation(self):
        """Test creation and operation of belt parametric editor."""
        layer_data = self.mock_state_manager.mechanism_layers["belt_1"]
        
        # Create parametric editor
        editor = ParametricFactory.create_parametric_editor("belt_1", layer_data, self.mock_scene_manager)
        
        assert editor is not None
        assert editor.mechanism_type == "belt"
        assert editor.mechanism_id == "belt_1"
        
        # Test parameter validation
        valid_params = {
            "pulley_1_radius": 30.0,
            "pulley_2_radius": 20.0,
            "belt_tension": 50.0,
            "slip_coefficient": 0.1
        }
        is_valid, error_msg = editor.validate_parameters(valid_params)
        assert is_valid, f"Valid parameters should pass validation: {error_msg}"
        
        # Test gear ratio calculation
        gear_ratio = editor.calculate_gear_ratio()
        expected_ratio = 30.0 / 20.0
        assert abs(gear_ratio - expected_ratio) < 0.001, f"Gear ratio should be {expected_ratio}, got {gear_ratio}"
        
        # Test belt length calculation
        belt_length = editor.calculate_belt_length()
        assert belt_length > 0, "Belt length should be positive"
        
        # Test belt speed calculation
        belt_speed = editor.get_belt_speed()
        assert belt_speed > 0, "Belt speed should be positive"
    
    @pytest.mark.skipif(not QApplication.instance(), reason="Requires Qt application")
    def test_spring_parametric_editor_creation(self):
        """Test creation and operation of spring parametric editor."""
        layer_data = self.mock_state_manager.mechanism_layers["spring_1"]
        
        # Create parametric editor
        editor = ParametricFactory.create_parametric_editor("spring_1", layer_data, self.mock_scene_manager)
        
        assert editor is not None
        assert editor.mechanism_type == "spring"
        assert editor.mechanism_id == "spring_1"
        
        # Test parameter validation
        valid_params = {
            "spring_constant": 100.0,
            "damping_coefficient": 10.0,
            "rest_length": 80.0,
            "mass": 1.0,
            "max_compression": 0.8,
            "max_extension": 2.0
        }
        is_valid, error_msg = editor.validate_parameters(valid_params)
        assert is_valid, f"Valid parameters should pass validation: {error_msg}"
        
        # Test natural frequency calculation
        natural_freq = editor.calculate_natural_frequency()
        expected_freq = (100.0 / 1.0)**0.5 / (2 * 3.14159)
        assert abs(natural_freq - expected_freq) < 0.1, f"Natural frequency should be ~{expected_freq}, got {natural_freq}"
        
        # Test damping ratio calculation
        damping_ratio = editor.calculate_damping_ratio()
        assert 0 <= damping_ratio <= 2, f"Damping ratio should be reasonable, got {damping_ratio}"
        
        # Test system type determination
        system_type = editor.get_system_type()
        assert system_type in ["underdamped", "critically_damped", "overdamped"], f"Invalid system type: {system_type}"
        
        # Test current length calculation
        current_length = editor.calculate_current_length()
        assert current_length == 80.0, f"Current length should be 80.0, got {current_length}"
        
        # Test spring force calculation
        spring_force = editor.calculate_spring_force(10.0)  # 10 units displacement
        expected_force = 100.0 * 10.0
        assert abs(spring_force - expected_force) < 0.001, f"Spring force should be {expected_force}, got {spring_force}"
    
    
    
    def test_parameter_controller_integration(self):
        """Test integration with parameter controller."""
        # Test basic parameter controller functionality without Qt handles
        
        # Test parameter change handling without real handles
        self.parameter_controller.handle_parameter_change("linkage_1", "ground_pivot_1", QPointF(10, 10))
        
        # Verify update was queued
        assert len(self.parameter_controller.pending_updates) > 0
        
        # Process pending updates
        self.parameter_controller._process_pending_updates()
        
        # Verify signals were emitted
        assert self.parameter_controller.update_count > 0
    
    @pytest.mark.skipif(not QApplication.instance(), reason="Requires Qt application")
    def test_complete_workflow_linkage(self):
        """Test complete workflow for linkage parametric editing."""
        layer_data = self.mock_state_manager.mechanism_layers["linkage_1"]
        
        # 1. Create parametric editor
        editor = ParametricFactory.create_parametric_editor("linkage_1", layer_data, self.mock_scene_manager)
        assert editor is not None
        
        # 2. Simulate parameter change
        changed_handles = {
            "ground_pivot_1": QPointF(20, 0),
            "ground_pivot_2": QPointF(120, 0)
        }
        
        # 3. Update mechanism from handles
        updated_params = editor.update_mechanism_from_handles(changed_handles)
        
        # 4. Verify updates
        assert "ground_pivot_1" in updated_params
        assert "ground_pivot_2" in updated_params
        
        # 5. Validate final parameters
        is_valid, error_msg = editor.validate_parameters(updated_params)
        assert is_valid, f"Updated parameters should be valid: {error_msg}"
    
    def test_performance_statistics(self):
        """Test performance monitoring capabilities."""
        # Perform several operations
        for i in range(10):
            self.parameter_controller.handle_parameter_change(f"mech_{i}", f"param_{i}", i * 10)
        
        # Get performance stats
        stats = self.parameter_controller.get_performance_stats()
        
        # Verify stats structure
        assert "update_count" in stats
        assert "validation_count" in stats
        assert "error_count" in stats
        assert "elapsed_time" in stats
        assert "updates_per_second" in stats
        assert "active_handles" in stats
        assert "registered_handles" in stats
        
        # Verify reasonable values
        assert stats["update_count"] >= 0
        assert stats["elapsed_time"] > 0
        assert stats["updates_per_second"] >= 0
    
    def test_error_handling(self):
        """Test error handling in various scenarios."""
        # Test invalid mechanism type
        invalid_layer_data = {"type": "invalid_mechanism"}
        editor = ParametricFactory.create_parametric_editor("invalid_1", invalid_layer_data, self.mock_scene_manager)
        assert editor is None
        
        # Test malformed layer data
        malformed_layer_data = {"type": "4_bar_linkage"}  # Missing required fields
        editor = ParametricFactory.create_parametric_editor("malformed_1", malformed_layer_data, self.mock_scene_manager)
        assert editor is not None  # Should handle gracefully
        
        # Test constraint violations
        layer_data = self.mock_state_manager.mechanism_layers["linkage_1"]
        editor = ParametricFactory.create_parametric_editor("linkage_1", layer_data, self.mock_scene_manager)
        
        # Test invalid parameters
        invalid_params = {
            "l1": -10.0,  # Negative length
            "l2": 0.0,    # Zero length
            "l3": 1000.0, # Extremely large
            "l4": 90.0
        }
        
        is_valid, error_msg = editor.validate_parameters(invalid_params)
        assert not is_valid
        assert error_msg != ""
    
    def test_memory_management(self):
        """Test memory management and cleanup."""
        initial_handle_count = len(self.parameter_controller.handle_registry)
        
        # Create multiple handles
        handles = []
        for i in range(5):
            layer_data = self.mock_state_manager.mechanism_layers["linkage_1"]
            handle = AnchorHandle(
                mechanism_id=f"linkage_{i}",
                anchor_name=f"anchor_{i}",
                initial_position=QPointF(i * 10, 0),
                mechanism_data=layer_data,
                update_callback=Mock()
            )
            handle_id = self.parameter_controller.register_handle(handle)
            handles.append((handle, handle_id))
        
        # Verify handles were registered
        assert len(self.parameter_controller.handle_registry) == initial_handle_count + 5
        
        # Cleanup handles
        for handle, handle_id in handles:
            success = self.parameter_controller.unregister_handle(handle_id)
            assert success
        
        # Verify cleanup
        assert len(self.parameter_controller.handle_registry) == initial_handle_count
        
        # Test controller shutdown
        self.parameter_controller.shutdown()
        assert len(self.parameter_controller.handle_registry) == 0
        assert len(self.parameter_controller.pending_updates) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])