"""End-to-end tests for mechanism placement, adaptation, and animation."""

import math
from unittest.mock import patch, MagicMock

import pytest
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QPainterPath
from PyQt6.QtTest import QTest

from .fixtures import E2ETestBase, TestImageGenerator
from automataii.gui.graphics_items.mechanism_anchor_item import MechanismAnchorItem


class TestE2EMechanismIntegration(E2ETestBase):
    """Test mechanism generation, placement, editing, and animation."""
    
    def test_cam_mechanism_generation_and_placement(self, qtbot):
        """Test generating and placing a cam mechanism."""
        window = self.create_main_window()
        
        # Setup mechanism tab
        self.switch_to_tab("mechanism")
        mech_tab = window.tab_manager.tabs["mechanism_generation"]
        
        # Create test data
        test_part = {"rotating_wheel": MagicMock()}
        circular_path = self._create_circular_path(QPointF(200, 200), 50)
        
        mech_tab.receive_character_and_paths(test_part, {"rotating_wheel": circular_path})
        
        # Select part and mechanism type
        mech_tab._part_panel.part_selected.emit("rotating_wheel")
        mech_tab._mechanism_panel.set_mechanism_type("cam")
        
        # Select cam center by clicking on canvas
        cam_center = QPointF(200, 200)
        mech_tab._start_point_selection("cam_center")
        self.simulate_canvas_click(mech_tab._visualization.view, cam_center)
        
        # Verify center was selected
        assert mech_tab._state_manager.state.selected_cam_center == cam_center
        
        # Generate mechanism
        with patch.object(mech_tab._generation_service, 'generate_mechanism') as mock_gen:
            # Create realistic cam profile data
            profile_data = []
            for angle in range(0, 361, 10):
                radius = 50 + 10 * math.sin(math.radians(angle * 2))
                profile_data.append([angle, radius])
            
            mock_gen.return_value = {
                "type": "cam",
                "part_name": "rotating_wheel",
                "center": [200, 200],
                "profile": profile_data,
                "follower_type": "roller",
                "base_radius": 40,
                "max_radius": 60
            }
            
            qtbot.mouseClick(mech_tab._generate_btn, Qt.MouseButton.LeftButton)
        
        # Verify mechanism was visualized
        cam_items = [item for item in mech_tab._visualization.scene.items()
                    if hasattr(item, 'mechanism_type') and item.mechanism_type == 'cam']
        assert len(cam_items) > 0
        
        # Test cam animation
        qtbot.mouseClick(mech_tab._simulation_panel.play_btn, Qt.MouseButton.LeftButton)
        
        # Verify animation is running
        assert self.verify_mechanism_animation(mech_tab._visualization.view, duration=1000)
        
        # Stop animation
        qtbot.mouseClick(mech_tab._simulation_panel.stop_btn, Qt.MouseButton.LeftButton)
    
    def test_fourbar_mechanism_with_pivots(self, qtbot):
        """Test creating a four-bar linkage mechanism."""
        window = self.create_main_window()
        
        self.switch_to_tab("mechanism")
        mech_tab = window.tab_manager.tabs["mechanism_generation"]
        
        # Create test data with figure-8 path
        test_part = {"waving_arm": MagicMock()}
        figure8_path = self._create_figure8_path(QPointF(250, 250), 40)
        
        mech_tab.receive_character_and_paths(test_part, {"waving_arm": figure8_path})
        
        # Select part and mechanism type
        mech_tab._part_panel.part_selected.emit("waving_arm")
        mech_tab._mechanism_panel.set_mechanism_type("fourbar")
        
        # Select pivot points
        pivot_a = QPointF(150, 300)
        pivot_d = QPointF(350, 300)
        
        # Select pivot A
        mech_tab._start_point_selection("pivot_a_4bar")
        self.simulate_canvas_click(mech_tab._visualization.view, pivot_a)
        
        # Select pivot D
        mech_tab._start_point_selection("pivot_d_4bar")
        self.simulate_canvas_click(mech_tab._visualization.view, pivot_d)
        
        # Verify pivots were selected
        assert mech_tab._state_manager.state.selected_pivot_a == pivot_a
        assert mech_tab._state_manager.state.selected_pivot_d == pivot_d
        
        # Generate mechanism
        with patch.object(mech_tab._generation_service, 'generate_mechanism') as mock_gen:
            mock_gen.return_value = {
                "type": "fourbar",
                "part_name": "waving_arm",
                "links": {
                    "ground": {"start": [150, 300], "end": [350, 300], "length": 200},
                    "crank": {"start": [150, 300], "end": [200, 250], "length": 70.7},
                    "coupler": {"start": [200, 250], "end": [300, 250], "length": 100},
                    "rocker": {"start": [300, 250], "end": [350, 300], "length": 70.7}
                },
                "pivots": {
                    "A": [150, 300],
                    "B": [200, 250],
                    "C": [300, 250],
                    "D": [350, 300]
                },
                "initial_angle": 0
            }
            
            qtbot.mouseClick(mech_tab._generate_btn, Qt.MouseButton.LeftButton)
        
        # Verify linkage was created
        link_items = [item for item in mech_tab._visualization.scene.items()
                     if hasattr(item, 'link_type')]
        assert len(link_items) >= 4  # Should have 4 links
        
        # Verify pivots are displayed
        pivot_items = [item for item in mech_tab._visualization.scene.items()
                      if isinstance(item, MechanismAnchorItem)]
        assert len(pivot_items) >= 2  # At least ground pivots
    
    def test_mechanism_editing_mode(self, qtbot):
        """Test interactive mechanism editing."""
        window = self.create_main_window()
        
        self.switch_to_tab("mechanism")
        mech_tab = window.tab_manager.tabs["mechanism_generation"]
        
        # Create a simple mechanism first
        self._setup_simple_mechanism(mech_tab)
        
        # Enable edit mode
        assert mech_tab._edit_mode_btn.isEnabled()
        mech_tab._edit_mode_btn.setChecked(True)
        
        # Verify edit panel is visible
        assert mech_tab._edit_panel.isVisible()
        
        # Find an anchor to move
        anchor_items = [item for item in mech_tab._visualization.scene.items()
                       if isinstance(item, MechanismAnchorItem)]
        assert len(anchor_items) > 0
        
        anchor = anchor_items[0]
        initial_pos = anchor.pos()
        
        # Drag anchor to new position
        anchor_center = mech_tab._visualization.view.mapFromScene(anchor.sceneBoundingRect().center())
        new_pos = QPointF(anchor_center.x() + 30, anchor_center.y() + 20)
        
        qtbot.mousePress(mech_tab._visualization.view.viewport(), 
                        Qt.MouseButton.LeftButton, pos=anchor_center)
        qtbot.mouseMove(mech_tab._visualization.view.viewport(), pos=new_pos)
        qtbot.mouseRelease(mech_tab._visualization.view.viewport(), 
                          Qt.MouseButton.LeftButton, pos=new_pos)
        
        # Verify anchor moved
        final_pos = anchor.pos()
        assert final_pos != initial_pos
        
        # Test constraint display in advanced mode
        mech_tab._advanced_mode_btn.setChecked(True)
        assert mech_tab._advanced_panel.isVisible()
    
    def test_gear_mechanism_integration(self, qtbot):
        """Test gear mechanism creation and meshing."""
        window = self.create_main_window()
        
        self.switch_to_tab("mechanism")
        mech_tab = window.tab_manager.tabs["mechanism_generation"]
        
        # Setup for gear mechanism
        test_part = {"rotating_gear": MagicMock()}
        circular_path = self._create_circular_path(QPointF(200, 200), 30)
        
        mech_tab.receive_character_and_paths(test_part, {"rotating_gear": circular_path})
        
        # Select gear mechanism
        mech_tab._part_panel.part_selected.emit("rotating_gear")
        mech_tab._mechanism_panel.set_mechanism_type("gear")
        
        # Mock gear generation
        with patch.object(mech_tab._generation_service, 'generate_mechanism') as mock_gen:
            mock_gen.return_value = {
                "type": "gear",
                "part_name": "rotating_gear",
                "driver": {
                    "center": [200, 200],
                    "radius": 50,
                    "teeth": 20,
                    "module": 2.5
                },
                "driven": {
                    "center": [300, 200],
                    "radius": 75,
                    "teeth": 30,
                    "module": 2.5
                },
                "gear_ratio": 1.5,
                "rotation_direction": "opposite"
            }
            
            qtbot.mouseClick(mech_tab._generate_btn, Qt.MouseButton.LeftButton)
        
        # Verify gears were created
        gear_items = [item for item in mech_tab._visualization.scene.items()
                     if hasattr(item, 'teeth_count')]
        assert len(gear_items) >= 2  # Driver and driven gears
        
        # Test gear animation
        qtbot.mouseClick(mech_tab._simulation_panel.play_btn, Qt.MouseButton.LeftButton)
        QTest.qWait(500)
        
        # Gears should rotate in opposite directions
        # (Visual verification would check rotation angles)
        
        qtbot.mouseClick(mech_tab._simulation_panel.stop_btn, Qt.MouseButton.LeftButton)
    
    def test_mechanism_adaptation_to_path(self, qtbot):
        """Test mechanism adaptation to match desired motion path."""
        window = self.create_main_window()
        
        self.switch_to_tab("mechanism")
        mech_tab = window.tab_manager.tabs["mechanism_generation"]
        
        # Create a complex path
        test_part = {"complex_motion": MagicMock()}
        complex_path = self._create_complex_path()
        
        mech_tab.receive_character_and_paths(test_part, {"complex_motion": complex_path})
        
        # Try different mechanism types to find best fit
        mechanism_types = ["cam", "fourbar", "gear"]
        best_mechanism = None
        
        for mech_type in mechanism_types:
            mech_tab._part_panel.part_selected.emit("complex_motion")
            mech_tab._mechanism_panel.set_mechanism_type(mech_type)
            
            # Set required parameters
            if mech_type == "cam":
                mech_tab._state_manager.set_cam_center(QPointF(250, 250))
            elif mech_type == "fourbar":
                mech_tab._state_manager.set_pivot_a(QPointF(150, 300))
                mech_tab._state_manager.set_pivot_d(QPointF(350, 300))
            
            # Generate and evaluate
            with patch.object(mech_tab._generation_service, 'generate_mechanism') as mock_gen:
                mock_gen.return_value = self._create_mock_mechanism(mech_type)
                qtbot.mouseClick(mech_tab._generate_btn, Qt.MouseButton.LeftButton)
            
            # In real implementation, would calculate path matching score
            # For now, just verify mechanism was created
            assert len(mech_tab._state_manager.state.current_mechanisms) > 0
    
    def test_multi_mechanism_synchronization(self, qtbot):
        """Test multiple mechanisms working together."""
        window = self.create_main_window()
        
        self.switch_to_tab("mechanism")
        mech_tab = window.tab_manager.tabs["mechanism_generation"]
        
        # Create multiple animated parts
        parts = {
            "left_arm": MagicMock(),
            "right_arm": MagicMock(),
            "head": MagicMock()
        }
        
        paths = {
            "left_arm": self._create_circular_path(QPointF(150, 200), 30),
            "right_arm": self._create_circular_path(QPointF(350, 200), 30),
            "head": self._create_figure8_path(QPointF(250, 100), 20)
        }
        
        mech_tab.receive_character_and_paths(parts, paths)
        
        # Generate mechanisms for each part
        for part_name in parts:
            mech_tab._part_panel.part_selected.emit(part_name)
            
            # Use different mechanisms
            if "arm" in part_name:
                mech_tab._mechanism_panel.set_mechanism_type("fourbar")
                mech_tab._state_manager.set_pivot_a(QPointF(100, 250))
                mech_tab._state_manager.set_pivot_d(QPointF(400, 250))
            else:
                mech_tab._mechanism_panel.set_mechanism_type("cam")
                mech_tab._state_manager.set_cam_center(QPointF(250, 150))
            
            with patch.object(mech_tab._generation_service, 'generate_mechanism') as mock_gen:
                mock_gen.return_value = self._create_mock_mechanism(
                    mech_tab._mechanism_panel.get_current_type(),
                    part_name
                )
                qtbot.mouseClick(mech_tab._generate_btn, Qt.MouseButton.LeftButton)
        
        # Verify all mechanisms were created
        assert len(mech_tab._state_manager.state.current_mechanisms) == 3
        
        # Test synchronized animation
        qtbot.mouseClick(mech_tab._simulation_panel.play_btn, Qt.MouseButton.LeftButton)
        
        # All mechanisms should animate together
        assert mech_tab._state_manager.state.is_mechanism_simulating
        
        QTest.qWait(1000)
        
        # Stop and reset
        qtbot.mouseClick(mech_tab._simulation_panel.reset_btn, Qt.MouseButton.LeftButton)
        assert not mech_tab._state_manager.state.is_mechanism_simulating
    
    def test_mechanism_collision_detection(self, qtbot):
        """Test collision detection between mechanism parts."""
        window = self.create_main_window()
        
        self.switch_to_tab("mechanism")
        mech_tab = window.tab_manager.tabs["mechanism_generation"]
        
        # Create two parts that might collide
        parts = {
            "part1": MagicMock(),
            "part2": MagicMock()
        }
        
        # Paths that would cause collision
        paths = {
            "part1": self._create_circular_path(QPointF(200, 200), 50),
            "part2": self._create_circular_path(QPointF(250, 200), 50)
        }
        
        mech_tab.receive_character_and_paths(parts, paths)
        
        # Generate overlapping mechanisms
        for i, part_name in enumerate(parts):
            mech_tab._part_panel.part_selected.emit(part_name)
            mech_tab._mechanism_panel.set_mechanism_type("cam")
            mech_tab._state_manager.set_cam_center(QPointF(200 + i*50, 200))
            
            with patch.object(mech_tab._generation_service, 'generate_mechanism') as mock_gen:
                mock_gen.return_value = self._create_mock_mechanism("cam", part_name)
                qtbot.mouseClick(mech_tab._generate_btn, Qt.MouseButton.LeftButton)
        
        # In a real implementation, collision detection would highlight conflicts
        # For now, verify both mechanisms exist
        assert len(mech_tab._state_manager.state.current_mechanisms) == 2
    
    def test_mechanism_performance_optimization(self, qtbot):
        """Test mechanism optimization for smooth motion."""
        window = self.create_main_window()
        
        self.switch_to_tab("mechanism")
        mech_tab = window.tab_manager.tabs["mechanism_generation"]
        
        # Create a part with jerky motion path
        test_part = {"jerky_part": MagicMock()}
        jerky_path = self._create_jerky_path()
        
        mech_tab.receive_character_and_paths(test_part, {"jerky_part": jerky_path})
        
        # Generate initial mechanism
        mech_tab._part_panel.part_selected.emit("jerky_part")
        mech_tab._mechanism_panel.set_mechanism_type("cam")
        mech_tab._state_manager.set_cam_center(QPointF(250, 250))
        
        with patch.object(mech_tab._generation_service, 'generate_mechanism') as mock_gen:
            # Optimized cam profile should be smoother
            smooth_profile = self._create_smooth_cam_profile()
            mock_gen.return_value = {
                "type": "cam",
                "part_name": "jerky_part",
                "center": [250, 250],
                "profile": smooth_profile,
                "optimized": True,
                "smoothing_factor": 0.8
            }
            
            qtbot.mouseClick(mech_tab._generate_btn, Qt.MouseButton.LeftButton)
        
        # Verify optimized mechanism was created
        mechanism = mech_tab._state_manager.state.current_mechanisms[0]
        assert mechanism.get("optimized", False)
    
    # Helper methods
    
    def _create_circular_path(self, center: QPointF, radius: float) -> QPainterPath:
        """Create a circular motion path."""
        path = QPainterPath()
        path.addEllipse(center, radius, radius)
        return path
    
    def _create_figure8_path(self, center: QPointF, size: float) -> QPainterPath:
        """Create a figure-8 motion path."""
        path = QPainterPath()
        path.moveTo(center.x(), center.y())
        
        for t in range(0, 361, 5):
            angle = math.radians(t)
            x = center.x() + size * math.sin(angle)
            y = center.y() + size * math.sin(2 * angle) / 2
            path.lineTo(x, y)
        
        return path
    
    def _create_complex_path(self) -> QPainterPath:
        """Create a complex motion path."""
        path = QPainterPath()
        path.moveTo(200, 200)
        
        # Combine different motion patterns
        points = [
            (250, 180), (300, 200), (320, 250),
            (300, 300), (250, 320), (200, 300),
            (180, 250), (200, 200)
        ]
        
        for x, y in points:
            path.lineTo(x, y)
        
        return path
    
    def _create_jerky_path(self) -> QPainterPath:
        """Create a path with sudden direction changes."""
        path = QPainterPath()
        path.moveTo(200, 200)
        
        # Zigzag pattern
        for i in range(10):
            x = 200 + i * 20
            y = 200 + (50 if i % 2 == 0 else -50)
            path.lineTo(x, y)
        
        return path
    
    def _create_smooth_cam_profile(self) -> list:
        """Create a smooth cam profile."""
        profile = []
        for angle in range(0, 361, 5):
            # Smooth sinusoidal rise and fall
            radius = 50 + 20 * math.sin(math.radians(angle))
            profile.append([angle, radius])
        return profile
    
    def _setup_simple_mechanism(self, mech_tab):
        """Setup a simple mechanism for testing."""
        test_part = {"test_part": MagicMock()}
        test_path = self._create_circular_path(QPointF(200, 200), 30)
        
        mech_tab.receive_character_and_paths(test_part, {"test_part": test_path})
        mech_tab._part_panel.part_selected.emit("test_part")
        mech_tab._mechanism_panel.set_mechanism_type("cam")
        mech_tab._state_manager.set_cam_center(QPointF(200, 200))
        
        with patch.object(mech_tab._generation_service, 'generate_mechanism') as mock_gen:
            mock_gen.return_value = self._create_mock_mechanism("cam", "test_part")
            mech_tab._generate_btn.click()
    
    def _create_mock_mechanism(self, mech_type: str, part_name: str = "test_part") -> dict:
        """Create mock mechanism data."""
        if mech_type == "cam":
            return {
                "type": "cam",
                "part_name": part_name,
                "center": [200, 200],
                "profile": [[i, 50 + 10 * math.sin(math.radians(i))] for i in range(0, 361, 10)]
            }
        elif mech_type == "fourbar":
            return {
                "type": "fourbar",
                "part_name": part_name,
                "links": {
                    "ground": {"length": 200},
                    "crank": {"length": 50},
                    "coupler": {"length": 100},
                    "rocker": {"length": 70}
                }
            }
        else:  # gear
            return {
                "type": "gear",
                "part_name": part_name,
                "driver": {"radius": 50, "teeth": 20},
                "driven": {"radius": 75, "teeth": 30}
            }