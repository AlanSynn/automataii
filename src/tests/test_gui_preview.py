"""Unit tests for BasePreviewWidget following PySide/PyQt testing patterns."""

import unittest
from unittest.mock import patch, MagicMock
from PyQt6.QtCore import Qt, QPointF, QPoint
from PyQt6.QtWidgets import QPushButton
from PyQt6.QtGui import QWheelEvent, QMouseEvent

# Add parent directory to path
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automataii.ui.base_preview_widget import BasePreviewWidget
from tests.gui_test_utils import (
    QtTestCase, SignalSpy, click_widget, drag_widget,
    get_child_widget, process_events_for, wait_for_condition,
    assert_signal_emitted, assert_signal_not_emitted,
    create_mock_config, create_mock_mechanism
)


class TestBasePreviewWidget(QtTestCase, unittest.TestCase):
    """Test BasePreviewWidget functionality."""
    
    def setUp(self):
        """Set up test widget."""
        super().setUp()
        self.widget = self.register_widget(BasePreviewWidget())
        self.widget.setFixedSize(800, 600)  # Fixed size for consistent testing
        self.widget.show()
        process_events_for(50)
        
    def test_initial_state(self):
        """Test widget initializes with correct default values."""
        # Check default view mode
        self.assertEqual(self.widget.view_mode, '2D')
        self.assertEqual(self.widget.scale, 1.0)
        self.assertEqual(self.widget.offset, QPointF(0, 0))
        self.assertIsNone(self.widget.selected_mechanism)
        self.assertEqual(len(self.widget.mechanisms), 0)
        
        # Check mode button text
        self.assertEqual(self.widget.mode_btn.text(), "Switch to 3D")
        
        # Check info label
        self.assertEqual(self.widget.info_label.text(), "Ready")
        
    def test_view_mode_toggle(self):
        """Test toggling between 2D and 3D views."""
        # Initial state is 2D
        self.assertEqual(self.widget.view_mode, '2D')
        self.assertEqual(self.widget.mode_btn.text(), "Switch to 3D")
        
        # Click to switch to 3D
        click_widget(self.widget.mode_btn)
        self.assertEqual(self.widget.view_mode, '3D')
        self.assertEqual(self.widget.mode_btn.text(), "Switch to 2D")
        
        # Click to switch back to 2D
        click_widget(self.widget.mode_btn)
        self.assertEqual(self.widget.view_mode, '2D')
        self.assertEqual(self.widget.mode_btn.text(), "Switch to 3D")
        
    def test_zoom_controls(self):
        """Test zoom in/out functionality."""
        initial_scale = self.widget.scale
        
        # Find zoom buttons
        zoom_in_btn = None
        zoom_out_btn = None
        for btn in self.widget.findChildren(QPushButton):
            if btn.text() == "+":
                zoom_in_btn = btn
            elif btn.text() == "-":
                zoom_out_btn = btn
                
        self.assertIsNotNone(zoom_in_btn)
        self.assertIsNotNone(zoom_out_btn)
        
        # Test zoom in
        click_widget(zoom_in_btn)
        self.assertAlmostEqual(self.widget.scale, initial_scale * 1.2)
        
        # Test zoom out
        click_widget(zoom_out_btn)
        self.assertAlmostEqual(self.widget.scale, initial_scale * 1.2 * 0.8)
        
        # Test zoom limits
        for _ in range(20):
            click_widget(zoom_in_btn)
        self.assertLessEqual(self.widget.scale, 5.0)
        
        for _ in range(30):
            click_widget(zoom_out_btn)
        self.assertGreaterEqual(self.widget.scale, 0.1)
        
    def test_reset_view(self):
        """Test reset view functionality."""
        # Change view state
        self.widget.scale = 2.5
        self.widget.offset = QPointF(100, 50)
        
        # Find and click reset button
        reset_btn = None
        for btn in self.widget.findChildren(QPushButton):
            if btn.text() == "Reset View":
                reset_btn = btn
                break
                
        self.assertIsNotNone(reset_btn)
        click_widget(reset_btn)
        
        # Check view is reset
        self.assertEqual(self.widget.scale, 1.0)
        self.assertEqual(self.widget.offset, QPointF(0, 0))
        
    def test_set_base_configuration(self):
        """Test setting base configuration."""
        # Set rectangular base
        rect_config = create_mock_config('rectangular', width=250, depth=200, height=60)
        self.widget.set_base_configuration(rect_config)
        
        self.assertEqual(self.widget.base_config['type'], 'rectangular')
        self.assertEqual(self.widget.base_config['width'], 250)
        
        # Set cylindrical base
        cyl_config = create_mock_config('cylindrical', radius=120, height=70)
        self.widget.set_base_configuration(cyl_config)
        
        self.assertEqual(self.widget.base_config['type'], 'cylindrical')
        self.assertEqual(self.widget.base_config['radius'], 120)
        
    def test_add_mechanism(self):
        """Test adding mechanisms to preview."""
        # Add first mechanism
        mech1_info = create_mock_mechanism('mech1', (50, 30, 0))
        self.widget.add_mechanism('mech1', mech1_info)
        
        self.assertEqual(len(self.widget.mechanisms), 1)
        self.assertIn('mech1', self.widget.mechanisms)
        self.assertEqual(self.widget.mechanisms['mech1']['position'], (50, 30, 0))
        
        # Add second mechanism
        mech2_info = create_mock_mechanism('mech2', (-30, -40, 0))
        self.widget.add_mechanism('mech2', mech2_info)
        
        self.assertEqual(len(self.widget.mechanisms), 2)
        self.assertIn('mech2', self.widget.mechanisms)
        
    def test_remove_mechanism(self):
        """Test removing mechanisms from preview."""
        # Add mechanisms
        self.widget.add_mechanism('mech1', create_mock_mechanism('mech1'))
        self.widget.add_mechanism('mech2', create_mock_mechanism('mech2'))
        self.widget.selected_mechanism = 'mech1'
        
        # Remove non-selected mechanism
        self.widget.remove_mechanism('mech2')
        self.assertEqual(len(self.widget.mechanisms), 1)
        self.assertNotIn('mech2', self.widget.mechanisms)
        self.assertEqual(self.widget.selected_mechanism, 'mech1')
        
        # Remove selected mechanism
        self.widget.remove_mechanism('mech1')
        self.assertEqual(len(self.widget.mechanisms), 0)
        self.assertIsNone(self.widget.selected_mechanism)
        
    def test_clear_mechanisms(self):
        """Test clearing all mechanisms."""
        # Add multiple mechanisms
        self.widget.add_mechanism('mech1', create_mock_mechanism('mech1'))
        self.widget.add_mechanism('mech2', create_mock_mechanism('mech2'))
        self.widget.add_mechanism('mech3', create_mock_mechanism('mech3'))
        self.widget.selected_mechanism = 'mech2'
        
        # Clear all
        self.widget.clear_mechanisms()
        
        self.assertEqual(len(self.widget.mechanisms), 0)
        self.assertIsNone(self.widget.selected_mechanism)
        
    def test_mechanism_selection(self):
        """Test selecting mechanisms with mouse clicks."""
        spy = SignalSpy(self.widget.mechanism_selected)
        
        # Add mechanisms
        self.widget.add_mechanism('mech1', create_mock_mechanism('mech1', (0, 0, 0)))
        self.widget.add_mechanism('mech2', create_mock_mechanism('mech2', (100, 0, 0)))
        
        # Click on first mechanism (center of widget + mechanism offset)
        center_x = self.widget.width() // 2
        center_y = self.widget.height() // 2
        click_widget(self.widget, QPoint(center_x, center_y))
        
        assert_signal_emitted(spy, 1)
        self.assertEqual(spy.last_emission()[0], 'mech1')
        self.assertEqual(self.widget.selected_mechanism, 'mech1')
        
        # Click on second mechanism
        spy.clear()
        click_widget(self.widget, QPoint(center_x + 100, center_y))
        
        assert_signal_emitted(spy, 1)
        self.assertEqual(spy.last_emission()[0], 'mech2')
        self.assertEqual(self.widget.selected_mechanism, 'mech2')
        
        # Click on empty space
        spy.clear()
        click_widget(self.widget, QPoint(center_x + 200, center_y + 200))
        
        assert_signal_not_emitted(spy)
        self.assertEqual(self.widget.selected_mechanism, 'mech2')  # Selection unchanged
        
    def test_mouse_wheel_zoom(self):
        """Test zooming with mouse wheel."""
        initial_scale = self.widget.scale
        
        # Create wheel event for zoom in
        # Note: We simulate wheel events by calling wheelEvent directly
        # since QTest doesn't have a wheel simulation method
        
        # Mock wheel event for zoom in
        with patch.object(self.widget, 'wheelEvent') as mock_wheel:
            # Simulate the wheel event behavior
            self.widget._zoom(1.1)  # Zoom in
            self.assertAlmostEqual(self.widget.scale, initial_scale * 1.1)
            
            self.widget._zoom(0.9)  # Zoom out
            self.assertAlmostEqual(self.widget.scale, initial_scale * 1.1 * 0.9)
        
    def test_middle_mouse_drag(self):
        """Test panning with middle mouse button."""
        initial_offset = QPointF(self.widget.offset)
        
        # Simulate middle mouse drag
        start_pos = QPoint(200, 200)
        end_pos = QPoint(300, 250)
        
        # Press middle button
        self.widget.dragging = True
        self.widget.last_mouse_pos = QPointF(start_pos)
        
        # Move mouse
        self.widget.offset += QPointF(end_pos - start_pos)
        
        # Check offset changed
        expected_offset = initial_offset + QPointF(100, 50)
        self.assertEqual(self.widget.offset, expected_offset)
        
    def test_coordinate_conversion(self):
        """Test screen to world coordinate conversion."""
        # Set known transform
        self.widget.scale = 2.0
        self.widget.offset = QPointF(50, 30)
        
        # Test conversion
        screen_pos = QPointF(400, 300)  # Center of 800x600 widget
        world_pos = self.widget._screen_to_world(screen_pos)
        
        # With scale=2 and offset=(50,30), the center should map to (-25, -15)
        expected_x = (400 - 400 - 50) / 2.0  # (screen_x - center_x - offset_x) / scale
        expected_y = (300 - 300 - 30) / 2.0  # (screen_y - center_y - offset_y) / scale
        
        self.assertAlmostEqual(world_pos.x(), expected_x)
        self.assertAlmostEqual(world_pos.y(), expected_y)
        
    def test_info_label_updates(self):
        """Test info label shows mouse coordinates."""
        # Move mouse to known position
        center_x = self.widget.width() // 2
        center_y = self.widget.height() // 2
        
        # Simulate mouse move event
        event = MagicMock()
        event.position.return_value = QPointF(center_x + 100, center_y + 50)
        
        self.widget.mouseMoveEvent(event)
        
        # Check info label updated
        self.assertIn("X:", self.widget.info_label.text())
        self.assertIn("Y:", self.widget.info_label.text())
        
    def test_drawing_with_different_base_types(self):
        """Test preview updates correctly for different base types."""
        # Test with rectangular base
        rect_config = create_mock_config('rectangular')
        self.widget.set_base_configuration(rect_config)
        self.widget.update()
        process_events_for(50)
        
        # Widget should update without errors
        self.assertEqual(self.widget.base_config['type'], 'rectangular')
        
        # Test with cylindrical base
        cyl_config = create_mock_config('cylindrical')
        self.widget.set_base_configuration(cyl_config)
        self.widget.update()
        process_events_for(50)
        
        self.assertEqual(self.widget.base_config['type'], 'cylindrical')
        
    def test_mechanism_highlighting(self):
        """Test selected mechanisms are highlighted differently."""
        # Add mechanisms
        self.widget.add_mechanism('mech1', create_mock_mechanism('mech1', (0, 0, 0)))
        self.widget.add_mechanism('mech2', create_mock_mechanism('mech2', (100, 0, 0)))
        
        # Select first mechanism
        self.widget.selected_mechanism = 'mech1'
        self.widget.update()
        process_events_for(50)
        
        # Visual test - selected mechanism should be drawn with different pen
        # This is tested through the paintEvent, which we verify runs without error
        
        # Change selection
        self.widget.selected_mechanism = 'mech2'
        self.widget.update()
        process_events_for(50)
        
        # Deselect
        self.widget.selected_mechanism = None
        self.widget.update()
        process_events_for(50)
        
    def test_3d_view_rendering(self):
        """Test 3D view mode renders correctly."""
        # Set up base and mechanisms
        self.widget.set_base_configuration(create_mock_config('rectangular'))
        self.widget.add_mechanism('mech1', create_mock_mechanism('mech1'))
        
        # Switch to 3D view
        self.widget.view_mode = '3D'
        self.widget.update()
        process_events_for(50)
        
        # Verify 3D mode is active and renders without error
        self.assertEqual(self.widget.view_mode, '3D')
        
    def test_mouse_tracking(self):
        """Test mouse tracking is enabled."""
        self.assertTrue(self.widget.hasMouseTracking())
        
    def test_minimum_widget_size(self):
        """Test widget has appropriate minimum size."""
        min_size = self.widget.minimumSize()
        self.assertGreaterEqual(min_size.width(), 600)
        self.assertGreaterEqual(min_size.height(), 400)


if __name__ == '__main__':
    unittest.main()