"""
Comprehensive system integration test for Mechanism Dictionary Tab.

Tests the complete workflow from mechanism selection through interaction to analysis.
This is the ultimate validation that all systems work together correctly.
"""

import pytest
import math
from typing import List, Dict, Any, Tuple
from unittest.mock import Mock, MagicMock, patch
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtTest import QTest

# Import the classes we're testing
from automataii.ui.tabs.mechanism_dictionary.tab import MechanismDictionaryTab
from automataii.ui.tabs.mechanism_dictionary.interaction_handlers import (
    InteractionHandlerFactory,
    FourBarLinkageInteractionHandler,
    SixBarLinkageInteractionHandler,
    PlanetaryGearInteractionHandler,
    BeltSystemInteractionHandler,
    SpringSystemInteractionHandler,
    GenevaDriveInteractionHandler,
    GearSystemInteractionHandler,
    CamFollowerInteractionHandler,
    BaseLinkageHandler,
    BaseRotaryHandler,
    BasePowerTransmissionHandler,
    BaseElasticHandler,
    DragHandle
)
from automataii.ui.tabs.mechanism_dictionary.motion_analysis import (
    MotionAnalysisManager,
    VelocityAnalysisStrategy,
    AccelerationAnalysisStrategy,
    TrajectoryAnalysisStrategy
)
from automataii.ui.tabs.mechanism_dictionary.tutorial_system import TutorialManager
from automataii.ui.tabs.mechanism_dictionary.styling import ModernStyling
from automataii.domain.fabrication.mechanisms.base_mechanism import BaseMechanism


class TestMechanismDictionaryIntegration:
    """Comprehensive integration tests for the Mechanism Dictionary system."""
    
    @pytest.fixture
    def app(self):
        """Create QApplication instance for testing."""
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        return app
    
    @pytest.fixture
    def mock_mechanism(self):
        """Create a mock mechanism for testing."""
        mechanism = Mock(spec=BaseMechanism)
        mechanism.get_mechanism_type.return_value = "four_bar_linkage"
        mechanism.get_parameter.return_value = 50.0
        mechanism.set_parameter.return_value = None
        return mechanism
    
    @pytest.fixture
    def mechanism_tab(self, app, mock_mechanism):
        """Create MechanismDictionaryTab instance for testing."""
        with patch('automataii.ui.tabs.mechanism_dictionary.tab.CatalogManager'):
            tab = MechanismDictionaryTab()
            return tab
    
    # ===========================================================================
    # BASE HANDLER CLASS TESTS
    # ===========================================================================
    
    def test_base_linkage_handler_functionality(self, app, mock_mechanism):
        """Test BaseLinkageHandler provides correct linkage analysis."""
        handler = BaseLinkageHandler(mock_mechanism)
        
        # Test Grashof condition checking
        is_grashof, mech_type = handler.check_grashof_condition(40, 90, 70, 120)
        assert isinstance(is_grashof, bool)
        assert mech_type in ["Crank-Rocker", "Rocker-Crank", "Double-Crank", "Triple-Rocker", "Grashof Linkage"]
        
        # Test transmission angle calculation
        joint_positions = [(0, 0), (40, 0), (70, 50), (30, 50)]
        angle = handler.calculate_transmission_angle(joint_positions)
        assert 0 <= angle <= 180
        
    def test_base_rotary_handler_functionality(self, app, mock_mechanism):
        """Test BaseRotaryHandler provides correct gear analysis."""
        handler = BaseRotaryHandler(mock_mechanism)
        
        # Test gear ratio calculation
        ratio_data = handler.calculate_gear_ratio(12, 48, "spur")
        assert ratio_data["ratio"] == 4.0
        assert ratio_data["mechanical_advantage"] == 4.0
        assert ratio_data["speed_multiplier"] == 0.25
        assert ratio_data["torque_multiplier"] == 4.0
        
        # Test gear mesh validation
        is_valid = handler.validate_gear_mesh(12, 48, 30.0, 1.0)
        assert isinstance(is_valid, bool)
    
    def test_base_power_transmission_handler_functionality(self, app, mock_mechanism):
        """Test BasePowerTransmissionHandler provides correct belt analysis."""
        handler = BasePowerTransmissionHandler(mock_mechanism)
        
        # Test belt length calculation
        length = handler.calculate_belt_length(30, 75, 150, is_crossed=False)
        assert length > 0
        
        # Test contact angle calculation  
        angle1, angle2 = handler.calculate_contact_angles(30, 75, 150, is_crossed=False)
        assert 0 < angle1 <= 2 * math.pi
        assert 0 < angle2 <= 2 * math.pi
    
    def test_base_elastic_handler_functionality(self, app, mock_mechanism):
        """Test BaseElasticHandler provides correct spring analysis."""
        handler = BaseElasticHandler(mock_mechanism)
        
        # Test spring energy calculation
        energy_data = handler.calculate_spring_energy(500, 0.02, 1.0, 0.1)
        assert energy_data["potential"] > 0
        assert energy_data["kinetic"] > 0
        assert energy_data["total"] == energy_data["potential"] + energy_data["kinetic"]
        
        # Test natural frequency calculation
        freq_data = handler.calculate_natural_frequency(500, 1.0, 5.0)
        assert freq_data["natural_frequency"] > 0
        assert freq_data["period"] > 0
        assert 0 <= freq_data["damping_ratio"] <= 2
    
    # ===========================================================================
    # SPECIFIC HANDLER INTEGRATION TESTS
    # ===========================================================================
    
    def test_four_bar_linkage_complete_workflow(self, app, mock_mechanism):
        """Test complete four-bar linkage interaction workflow."""
        mock_mechanism.get_mechanism_type.return_value = "four_bar_linkage"
        handler = FourBarLinkageInteractionHandler(mock_mechanism)
        
        # Test UI creation
        widget = handler.create_interaction_controls()
        assert widget is not None
        assert isinstance(widget, QWidget)
        
        # Test analysis data generation
        analysis_data = handler.get_analysis_data()
        assert "grashof_condition" in analysis_data
        assert "mechanism_type" in analysis_data
        assert "link_lengths" in analysis_data
        assert "transmission_angle" in analysis_data
    
    def test_planetary_gear_willis_equation_analysis(self, app, mock_mechanism):
        """Test planetary gear Willis equation implementation."""
        mock_mechanism.get_mechanism_type.return_value = "planetary_gear"
        
        # Mock specific planetary gear parameters
        def get_param(name, default):
            params = {
                "sun_teeth": 12,
                "planet_teeth": 18, 
                "ring_teeth": 48,
                "num_planets": 3,
                "input_config": "sun"
            }
            return params.get(name, default)
        
        mock_mechanism.get_parameter.side_effect = get_param
        handler = PlanetaryGearInteractionHandler(mock_mechanism)
        
        analysis_data = handler.get_analysis_data()
        
        # Validate Willis equation calculations
        assert "basic_ratio" in analysis_data
        assert "speed_ratio" in analysis_data
        assert "torque_ratio" in analysis_data
        assert "assembly_valid" in analysis_data
        assert "clearance_ok" in analysis_data
        assert "willis_equation" in analysis_data
        
        # Check that gear relationship is validated: ring = sun + 2×planet
        sun = analysis_data["gear_teeth"]["sun"]
        planet = analysis_data["gear_teeth"]["planet"]
        ring = analysis_data["gear_teeth"]["ring"]
        assert ring == sun + 2 * planet
    
    def test_belt_system_tension_analysis(self, app, mock_mechanism):
        """Test belt system Euler-Eytelwein formula implementation."""
        mock_mechanism.get_mechanism_type.return_value = "belt"
        
        def get_param(name, default):
            params = {
                "pulley1_radius": 30.0,
                "pulley2_radius": 75.0,
                "center_distance": 150.0,
                "initial_tension": 80.0,
                "belt_type": "timing",
                "input_speed": 1000.0,
                "input_torque": 10.0
            }
            return params.get(name, default)
        
        mock_mechanism.get_parameter.side_effect = get_param
        handler = BeltSystemInteractionHandler(mock_mechanism)
        
        analysis_data = handler.get_analysis_data()
        
        # Validate belt analysis
        assert "belt_length" in analysis_data
        assert "speed_ratio" in analysis_data
        assert "tensions" in analysis_data
        assert "contact_angles" in analysis_data
        assert "power" in analysis_data
        
        tensions = analysis_data["tensions"]
        assert tensions["tight_side"] > tensions["slack_side"]
        assert tensions["ratio"] > 1.0
    
    def test_spring_system_hookes_law_implementation(self, app, mock_mechanism):
        """Test spring system Hooke's law and energy calculations."""
        mock_mechanism.get_mechanism_type.return_value = "spring"
        
        def get_param(name, default):
            params = {
                "spring_constant": 500.0,
                "displacement": 20.0,  # mm
                "mass": 1.0,
                "damping_coefficient": 5.0,
                "velocity": 0.0,
                "rest_length": 80.0
            }
            return params.get(name, default)
        
        mock_mechanism.get_parameter.side_effect = get_param
        handler = SpringSystemInteractionHandler(mock_mechanism)
        
        analysis_data = handler.get_analysis_data()
        
        # Validate Hooke's law implementation
        assert "hookes_law" in analysis_data
        assert "energy" in analysis_data
        assert "dynamics" in analysis_data
        
        hookes = analysis_data["hookes_law"]
        assert hookes["force"] == hookes["spring_constant"] * abs(hookes["displacement"] / 1000)
        
        energy = analysis_data["energy"]
        assert energy["total"] == energy["potential"] + energy["kinetic"]
    
    # ===========================================================================
    # DRAG HANDLE INTERACTION TESTS
    # ===========================================================================
    
    def test_drag_handle_parameter_updates(self, app, mock_mechanism):
        """Test drag handle parameter update workflow."""
        handler = FourBarLinkageInteractionHandler(mock_mechanism)
        
        # Create a mock scene
        mock_scene = Mock()
        handler.create_drag_handles(mock_scene)
        
        # Verify drag handles were created
        assert len(handler.drag_handles) > 0
        
        # Test parameter value conversion
        if handler.drag_handles:
            handle = handler.drag_handles[0]
            handle.parameter_name = "link1_length"
            handle.value_range = (20.0, 100.0)
            
            # Test position to parameter conversion
            test_position = QPointF(150.0, 100.0)
            value = handler._position_to_parameter_value(handle, test_position)
            assert value is not None
            assert handle.value_range[0] <= value <= handle.value_range[1]
    
    def test_drag_handle_visual_feedback(self, app):
        """Test drag handle visual feedback system."""
        handle = DragHandle(100, 100)
        handle.set_parameter("test_param", 50.0, (10.0, 100.0))
        
        # Test hover effects
        assert not handle.is_hovered
        handle.hoverEnterEvent(None)
        assert handle.is_hovered
        
        handle.hoverLeaveEvent(None)
        assert not handle.is_hovered
        
        # Test constraint validation
        handle.setIsValid(False)
        assert not handle.is_valid
        
        handle.setIsValid(True)
        assert handle.is_valid
    
    # ===========================================================================
    # MOTION ANALYSIS SYSTEM TESTS
    # ===========================================================================
    
    def test_motion_analysis_strategies(self, app):
        """Test motion analysis strategy pattern implementation."""
        manager = MotionAnalysisManager()
        
        # Test velocity analysis
        velocity_strategy = VelocityAnalysisStrategy()
        test_points = [(0, 0), (10, 5), (20, 15)]
        velocity_data = velocity_strategy.analyze(test_points, 0.1)
        
        assert "velocities" in velocity_data
        assert "max_velocity" in velocity_data
        assert len(velocity_data["velocities"]) == len(test_points)
        
        # Test acceleration analysis
        acceleration_strategy = AccelerationAnalysisStrategy()
        accel_data = acceleration_strategy.analyze(test_points, 0.1)
        
        assert "accelerations" in accel_data
        assert "max_acceleration" in accel_data
        
        # Test trajectory analysis
        trajectory_strategy = TrajectoryAnalysisStrategy()
        traj_data = trajectory_strategy.analyze(test_points, 0.1)
        
        assert "path_length" in traj_data
        assert "curvature" in traj_data
    
    # ===========================================================================
    # TUTORIAL SYSTEM INTEGRATION TESTS
    # ===========================================================================
    
    def test_tutorial_system_workflow(self, app):
        """Test tutorial system integration."""
        with patch('automataii.ui.tabs.mechanism_dictionary.tutorial_system.QWidget'):
            tutorial_manager = TutorialManager()
            
            # Test tutorial availability
            assert hasattr(tutorial_manager, 'tutorials')
            assert "first_visit" in tutorial_manager.tutorials
            assert "four_bar_basics" in tutorial_manager.tutorials
            
            # Test tutorial step management
            tutorial_manager.start_tutorial("first_visit")
            assert tutorial_manager.current_tutorial == "first_visit"
            assert tutorial_manager.current_step == 0
    
    # ===========================================================================
    # FACTORY PATTERN TESTS
    # ===========================================================================
    
    def test_interaction_handler_factory_complete_registry(self, app):
        """Test that factory correctly creates all handler types."""
        test_mechanisms = [
            ("four_bar_linkage", FourBarLinkageInteractionHandler),
            ("six_bar_linkage", SixBarLinkageInteractionHandler),
            ("gear_train", GearSystemInteractionHandler),
            ("planetary_gear", PlanetaryGearInteractionHandler),
            ("geneva_drive", GenevaDriveInteractionHandler),
            ("cam_follower", CamFollowerInteractionHandler),
            ("belt", BeltSystemInteractionHandler),
            ("spring", SpringSystemInteractionHandler)
        ]
        
        for mechanism_type, expected_handler_class in test_mechanisms:
            mock_mechanism = Mock(spec=BaseMechanism)
            mock_mechanism.get_mechanism_type.return_value = mechanism_type
            
            handler = InteractionHandlerFactory.create_handler(mock_mechanism)
            assert isinstance(handler, expected_handler_class)
            
            # Test support level reporting
            support_level = InteractionHandlerFactory.get_support_level(mechanism_type)
            assert support_level in ["basic", "limited", "full"]
    
    def test_factory_feature_matrix_accuracy(self, app):
        """Test that feature matrix accurately reflects capabilities."""
        feature_matrix = InteractionHandlerFactory.get_feature_matrix()
        
        # Test that all registered mechanisms have feature entries
        supported_types = InteractionHandlerFactory.get_supported_types()
        for mech_type in supported_types:
            if mech_type in feature_matrix:
                features = feature_matrix[mech_type]
                
                # Verify feature completeness
                required_features = [
                    "drag_handles", 
                    "constraint_validation", 
                    "real_time_analysis",
                    "specialized_analysis", 
                    "path_optimization"
                ]
                
                for feature in required_features:
                    assert feature in features
                    assert isinstance(features[feature], bool)
    
    # ===========================================================================
    # PERFORMANCE AND MEMORY TESTS
    # ===========================================================================
    
    def test_handler_memory_efficiency(self, app, mock_mechanism):
        """Test that handlers don't create memory leaks."""
        initial_handlers = []
        
        # Create multiple handlers
        for i in range(10):
            handler = FourBarLinkageInteractionHandler(mock_mechanism)
            initial_handlers.append(handler)
        
        # Cleanup handlers
        for handler in initial_handlers:
            handler.cleanup()
        
        # Verify cleanup worked
        for handler in initial_handlers:
            assert len(handler.drag_handles) == 0
    
    def test_analysis_performance_benchmarks(self, app, mock_mechanism):
        """Test that analysis calculations meet performance requirements."""
        import time
        
        handler = PlanetaryGearInteractionHandler(mock_mechanism)
        
        # Benchmark analysis speed
        start_time = time.time()
        for _ in range(100):
            analysis_data = handler.get_analysis_data()
        end_time = time.time()
        
        # Analysis should be fast (< 10ms per call on average)
        avg_time = (end_time - start_time) / 100
        assert avg_time < 0.01, f"Analysis too slow: {avg_time:.4f}s per call"
    
    # ===========================================================================
    # ERROR HANDLING AND EDGE CASES
    # ===========================================================================
    
    def test_invalid_mechanism_parameters(self, app, mock_mechanism):
        """Test handling of invalid mechanism parameters."""
        handler = FourBarLinkageInteractionHandler(mock_mechanism)
        
        # Test with invalid link lengths
        mock_mechanism.get_parameter.side_effect = lambda name, default: {
            "link1_length": -10.0,  # Invalid negative length
            "link2_length": 0.0,    # Invalid zero length
            "link3_length": float('inf'),  # Invalid infinite length
            "link4_length": 50.0
        }.get(name, default)
        
        # Analysis should handle invalid parameters gracefully
        analysis_data = handler.get_analysis_data()
        assert analysis_data is not None
        assert isinstance(analysis_data, dict)
    
    def test_missing_mechanism_type_handling(self, app):
        """Test factory handling of unsupported mechanism types."""
        mock_mechanism = Mock(spec=BaseMechanism)
        mock_mechanism.get_mechanism_type.return_value = "unsupported_mechanism"
        
        # Should fall back to base handler
        handler = InteractionHandlerFactory.create_handler(mock_mechanism)
        assert handler is not None
        
        # Should report basic support level
        support_level = InteractionHandlerFactory.get_support_level("unsupported_mechanism")
        assert support_level == "basic"
    
    # ===========================================================================
    # STYLING AND UI CONSISTENCY TESTS  
    # ===========================================================================
    
    def test_modern_styling_consistency(self, app):
        """Test that ModernStyling provides consistent theming."""
        # Test color scheme completeness
        required_colors = [
            'primary', 'primary_light', 'primary_dark',
            'secondary', 'surface', 'on_surface',
            'success', 'warning', 'error', 'info'
        ]
        
        for color_name in required_colors:
            assert color_name in ModernStyling.COLORS
            color_value = ModernStyling.COLORS[color_name]
            assert color_value.startswith('#')
            assert len(color_value) == 7  # #RRGGBB format
    
    def test_ui_widget_creation_consistency(self, app, mock_mechanism):
        """Test that all handlers create consistent UI layouts."""
        handler_classes = [
            FourBarLinkageInteractionHandler,
            SixBarLinkageInteractionHandler,
            PlanetaryGearInteractionHandler,
            BeltSystemInteractionHandler,
            SpringSystemInteractionHandler
        ]
        
        for handler_class in handler_classes:
            handler = handler_class(mock_mechanism)
            widget = handler.create_interaction_controls()
            
            # All handlers should create valid widgets
            assert widget is not None
            assert isinstance(widget, QWidget)
            
            # Widgets should have reasonable dimensions
            size_hint = widget.sizeHint()
            assert size_hint.width() > 0
            assert size_hint.height() > 0


if __name__ == "__main__":
    """Run integration tests with detailed output."""
    pytest.main([
        __file__, 
        "-v", 
        "--tb=short",
        "--capture=no",
        "-x"  # Stop on first failure for easier debugging
    ])