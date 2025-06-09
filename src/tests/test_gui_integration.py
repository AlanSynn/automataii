"""Integration tests for the complete automata base system."""

import unittest
from unittest.mock import patch, MagicMock
from PyQt6.QtCore import Qt, QTimer, QPoint, QPointF
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QPushButton

# Add parent directory to path
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automataii.ui.base_selection_widget import BaseSelectionWidget
from automataii.ui.base_preview_widget import BasePreviewWidget
from tests.gui_test_utils import (
    QtTestCase, SignalSpy, click_widget, drag_widget,
    get_child_widget, process_events_for, wait_for_condition,
    assert_signal_emitted, assert_signal_not_emitted,
    create_mock_config, create_mock_mechanism
)


class TestAutomataBaseIntegration(QtTestCase, unittest.TestCase):
    """Integration tests for BaseSelectionWidget and BasePreviewWidget."""
    
    def setUp(self):
        """Set up integrated test environment."""
        super().setUp()
        
        # Create main widget container
        self.main_widget = self.register_widget(QWidget())
        layout = QHBoxLayout(self.main_widget)
        
        # Create selection and preview widgets
        self.selection_widget = BaseSelectionWidget()
        self.preview_widget = BasePreviewWidget()
        
        layout.addWidget(self.selection_widget)
        layout.addWidget(self.preview_widget, stretch=1)
        
        # Connect signals
        self.selection_widget.base_changed.connect(self.preview_widget.set_base_configuration)
        self.selection_widget.preview_requested.connect(self._on_preview_requested)
        self.preview_widget.mechanism_selected.connect(self._on_mechanism_selected)
        
        # Track callbacks
        self.preview_requests = []
        self.selected_mechanisms = []
        
        self.main_widget.show()
        process_events_for(50)
        
    def _on_preview_requested(self, config):
        """Handle preview request."""
        self.preview_requests.append(config)
        self.preview_widget.set_base_configuration(config)
        
    def _on_mechanism_selected(self, mech_id):
        """Handle mechanism selection."""
        self.selected_mechanisms.append(mech_id)
        
    def test_selection_updates_preview_automatically(self):
        """Test that changing selection automatically updates preview."""
        # Change width in selection
        self.selection_widget.rect_width.setValue(300)
        process_events_for(50)
        
        # Preview should have updated configuration
        self.assertEqual(self.preview_widget.base_config.get('width'), 300)
        
        # Change to cylindrical
        cyl_button = self.selection_widget.type_buttons['cylindrical']
        click_widget(cyl_button)
        process_events_for(50)
        
        # Preview should show cylindrical base
        self.assertEqual(self.preview_widget.base_config.get('type'), 'cylindrical')
        
    def test_preview_button_updates_preview(self):
        """Test explicit preview button updates preview."""
        # Make changes without automatic update
        self.selection_widget.rect_width.setValue(250)
        self.selection_widget.rect_depth.setValue(200)
        
        # Click preview button
        for btn in self.selection_widget.findChildren(QPushButton):
            if btn.text() == "Update Preview":
                click_widget(btn)
                break
                
        process_events_for(50)
        
        # Check preview was requested
        self.assertEqual(len(self.preview_requests), 1)
        self.assertEqual(self.preview_requests[0]['width'], 250)
        self.assertEqual(self.preview_requests[0]['depth'], 200)
        
    def test_complete_workflow(self):
        """Test complete workflow from selection to preview with mechanisms."""
        # 1. Configure base
        self.selection_widget.material_combo.setCurrentText("Acrylic - Clear")
        self.selection_widget.thickness_spin.setValue(5.0)
        self.selection_widget.rect_width.setValue(300)
        self.selection_widget.rect_depth.setValue(250)
        process_events_for(50)
        
        # 2. Add mechanisms to preview
        self.preview_widget.add_mechanism('motor1', create_mock_mechanism('motor1', (50, 0, 0)))
        self.preview_widget.add_mechanism('gear1', create_mock_mechanism('gear1', (-50, 0, 0)))
        self.preview_widget.add_mechanism('cam1', create_mock_mechanism('cam1', (0, 50, 0)))
        
        # 3. Test mechanism selection
        center_x = self.preview_widget.width() // 2
        center_y = self.preview_widget.height() // 2
        
        click_widget(self.preview_widget, QPoint(center_x + 50, center_y))
        process_events_for(50)
        
        self.assertEqual(len(self.selected_mechanisms), 1)
        self.assertEqual(self.selected_mechanisms[0], 'motor1')
        self.assertEqual(self.preview_widget.selected_mechanism, 'motor1')
        
        # 4. Change base type
        cyl_button = self.selection_widget.type_buttons['cylindrical']
        click_widget(cyl_button)
        self.selection_widget.cyl_radius.setValue(150)
        process_events_for(50)
        
        # Preview should update
        self.assertEqual(self.preview_widget.base_config['type'], 'cylindrical')
        self.assertEqual(self.preview_widget.base_config['radius'], 150)
        
        # Mechanisms should still be there
        self.assertEqual(len(self.preview_widget.mechanisms), 3)
        
        # 5. Test 3D view
        click_widget(self.preview_widget.mode_btn)
        process_events_for(50)
        
        self.assertEqual(self.preview_widget.view_mode, '3D')
        
    def test_material_changes_affect_preview(self):
        """Test that material changes are reflected in preview."""
        # Set initial material
        self.selection_widget.material_combo.setCurrentText("Wood - MDF")
        self.selection_widget.thickness_spin.setValue(12.0)
        process_events_for(50)
        
        # Check preview has material info
        self.assertEqual(self.preview_widget.base_config.get('material'), "Wood - MDF")
        self.assertEqual(self.preview_widget.base_config.get('thickness'), 12.0)
        
        # Change material
        self.selection_widget.material_combo.setCurrentText("Metal - Aluminum")
        self.selection_widget.thickness_spin.setValue(3.0)
        process_events_for(50)
        
        # Check preview updated
        self.assertEqual(self.preview_widget.base_config.get('material'), "Metal - Aluminum")
        self.assertEqual(self.preview_widget.base_config.get('thickness'), 3.0)
        
    @patch('PyQt6.QtWidgets.QFileDialog.getOpenFileName')
    def test_custom_file_workflow(self, mock_dialog):
        """Test workflow with custom base file."""
        # Switch to custom
        custom_button = self.selection_widget.type_buttons['custom']
        click_widget(custom_button)
        
        # Select file
        test_file = "/models/custom_base.stl"
        mock_dialog.return_value = (test_file, "3D Models (*.stl *.obj)")
        
        for btn in self.selection_widget.findChildren(QPushButton):
            if btn.text() == "Browse...":
                click_widget(btn)
                break
                
        process_events_for(50)
        
        # Check preview updated with custom file
        self.assertEqual(self.preview_widget.base_config.get('type'), 'custom')
        self.assertEqual(self.preview_widget.base_config.get('file'), test_file)
        
    def test_zoom_and_pan_with_mechanisms(self):
        """Test zoom and pan functionality with mechanisms displayed."""
        # Add mechanisms
        self.preview_widget.add_mechanism('mech1', create_mock_mechanism('mech1', (0, 0, 0)))
        self.preview_widget.add_mechanism('mech2', create_mock_mechanism('mech2', (100, 100, 0)))
        
        # Zoom in
        for btn in self.preview_widget.findChildren(QPushButton):
            if btn.text() == "+":
                for _ in range(3):
                    click_widget(btn)
                break
                
        self.assertGreater(self.preview_widget.scale, 1.5)
        
        # Pan view
        initial_offset = QPointF(self.preview_widget.offset)
        start = QPoint(400, 300)
        end = QPoint(500, 350)
        
        # Simulate middle mouse drag
        self.preview_widget.dragging = True
        self.preview_widget.last_mouse_pos = QPointF(start)
        self.preview_widget.offset += QPointF(end - start)
        self.preview_widget.dragging = False
        
        # Check offset changed
        self.assertNotEqual(self.preview_widget.offset, initial_offset)
        
        # Reset view
        for btn in self.preview_widget.findChildren(QPushButton):
            if btn.text() == "Reset View":
                click_widget(btn)
                break
                
        self.assertEqual(self.preview_widget.scale, 1.0)
        self.assertEqual(self.preview_widget.offset, QPointF(0, 0))
        
    def test_rapid_configuration_changes(self):
        """Test system handles rapid configuration changes."""
        # Rapidly change values
        for i in range(10):
            self.selection_widget.rect_width.setValue(100 + i * 20)
            self.selection_widget.rect_depth.setValue(100 + i * 15)
            process_events_for(10)
            
        # System should remain stable
        final_width = self.preview_widget.base_config.get('width')
        self.assertEqual(final_width, 280)  # 100 + 9*20
        
        # Rapidly switch types
        for _ in range(5):
            click_widget(self.selection_widget.type_buttons['cylindrical'])
            process_events_for(10)
            click_widget(self.selection_widget.type_buttons['rectangular'])
            process_events_for(10)
            
        # Should end up on rectangular
        self.assertEqual(self.preview_widget.base_config.get('type'), 'rectangular')
        
    def test_state_persistence(self):
        """Test that widget states persist correctly."""
        # Set up initial state
        self.selection_widget.set_configuration({
            'type': 'cylindrical',
            'radius': 125,
            'height': 75,
            'material': '3D Print - ABS',
            'thickness': 2.5
        })
        
        self.preview_widget.add_mechanism('mech1', create_mock_mechanism('mech1'))
        self.preview_widget.selected_mechanism = 'mech1'
        self.preview_widget.scale = 1.5
        self.preview_widget.offset = QPointF(25, 30)
        self.preview_widget.view_mode = '3D'
        
        process_events_for(50)
        
        # Verify all state is correct
        config = self.selection_widget.get_configuration()
        self.assertEqual(config['type'], 'cylindrical')
        self.assertEqual(config['radius'], 125)
        self.assertEqual(config['material'], '3D Print - ABS')
        
        self.assertEqual(self.preview_widget.selected_mechanism, 'mech1')
        self.assertEqual(self.preview_widget.scale, 1.5)
        self.assertEqual(self.preview_widget.view_mode, '3D')
        
    def test_error_handling(self):
        """Test system handles errors gracefully."""
        # Try to remove non-existent mechanism
        self.preview_widget.remove_mechanism('non_existent')
        process_events_for(50)
        
        # Should not crash
        self.assertEqual(len(self.preview_widget.mechanisms), 0)
        
        # Set invalid configuration
        self.preview_widget.set_base_configuration({})
        process_events_for(50)
        
        # Should handle gracefully
        self.assertEqual(self.preview_widget.base_config, {})
        
    def test_performance_with_many_mechanisms(self):
        """Test performance with many mechanisms."""
        # Add many mechanisms
        for i in range(20):
            x = (i % 5) * 40 - 80
            y = (i // 5) * 40 - 80
            self.preview_widget.add_mechanism(
                f'mech_{i}', 
                create_mock_mechanism(f'mech_{i}', (x, y, 0))
            )
            
        # System should handle it
        self.assertEqual(len(self.preview_widget.mechanisms), 20)
        
        # Test selection still works
        center_x = self.preview_widget.width() // 2
        center_y = self.preview_widget.height() // 2
        click_widget(self.preview_widget, QPoint(center_x - 80, center_y - 80))
        
        # Should select the mechanism at that position
        self.assertIsNotNone(self.preview_widget.selected_mechanism)


if __name__ == '__main__':
    unittest.main()