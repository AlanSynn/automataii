"""Unit tests for BaseSelectionWidget following PySide/PyQt testing patterns."""

import unittest
from unittest.mock import patch, MagicMock
from PyQt6.QtWidgets import QRadioButton, QSpinBox, QDoubleSpinBox, QComboBox, QPushButton
from PyQt6.QtCore import Qt

# Add parent directory to path
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automataii.ui.base_selection_widget import BaseSelectionWidget
from tests.gui_test_utils import (
    QtTestCase, SignalSpy, click_widget, type_text, 
    get_child_widget, process_events_for, wait_for_condition,
    assert_signal_emitted, assert_signal_not_emitted,
    create_mock_config
)


class TestBaseSelectionWidget(QtTestCase, unittest.TestCase):
    """Test BaseSelectionWidget functionality."""
    
    def setUp(self):
        """Set up test widget."""
        super().setUp()
        self.widget = self.register_widget(BaseSelectionWidget())
        self.widget.show()
        process_events_for(50)
        
    def test_initial_state(self):
        """Test widget initializes with correct default values."""
        # Check default type is rectangular
        rect_button = self.widget.type_buttons['rectangular']
        self.assertTrue(rect_button.isChecked())
        
        # Check default rectangular values
        self.assertEqual(self.widget.rect_width.value(), 200)
        self.assertEqual(self.widget.rect_depth.value(), 150)
        self.assertEqual(self.widget.rect_height.value(), 50)
        
        # Check default material
        self.assertEqual(self.widget.material_combo.currentText(), "Wood - Plywood")
        self.assertEqual(self.widget.thickness_spin.value(), 6.0)
        
        # Check configuration
        config = self.widget.get_configuration()
        self.assertEqual(config['type'], 'rectangular')
        self.assertEqual(config['width'], 200)
        self.assertEqual(config['depth'], 150)
        self.assertEqual(config['height'], 50)
        
    def test_type_selection_changes_stack(self):
        """Test selecting different base types changes the configuration stack."""
        # Test cylindrical
        cyl_button = self.widget.type_buttons['cylindrical']
        click_widget(cyl_button)
        
        self.assertEqual(self.widget.config_stack.currentIndex(), 1)
        self.assertTrue(cyl_button.isChecked())
        
        # Test custom
        custom_button = self.widget.type_buttons['custom']
        click_widget(custom_button)
        
        self.assertEqual(self.widget.config_stack.currentIndex(), 2)
        self.assertTrue(custom_button.isChecked())
        
        # Test back to rectangular
        rect_button = self.widget.type_buttons['rectangular']
        click_widget(rect_button)
        
        self.assertEqual(self.widget.config_stack.currentIndex(), 0)
        self.assertTrue(rect_button.isChecked())
        
    def test_rectangular_configuration_updates(self):
        """Test updating rectangular configuration values."""
        spy = SignalSpy(self.widget.base_changed)
        
        # Change width
        self.widget.rect_width.setValue(300)
        process_events_for(50)
        
        assert_signal_emitted(spy, 1)
        config = self.widget.get_configuration()
        self.assertEqual(config['width'], 300)
        
        # Change depth
        spy.clear()
        self.widget.rect_depth.setValue(200)
        process_events_for(50)
        
        assert_signal_emitted(spy, 1)
        config = self.widget.get_configuration()
        self.assertEqual(config['depth'], 200)
        
        # Change height
        spy.clear()
        self.widget.rect_height.setValue(75)
        process_events_for(50)
        
        assert_signal_emitted(spy, 1)
        config = self.widget.get_configuration()
        self.assertEqual(config['height'], 75)
        
    def test_cylindrical_configuration_updates(self):
        """Test updating cylindrical configuration values."""
        # Switch to cylindrical
        cyl_button = self.widget.type_buttons['cylindrical']
        click_widget(cyl_button)
        
        spy = SignalSpy(self.widget.base_changed)
        
        # Change radius
        self.widget.cyl_radius.setValue(150)
        process_events_for(50)
        
        assert_signal_emitted(spy, 1)
        config = self.widget.get_configuration()
        self.assertEqual(config['type'], 'cylindrical')
        self.assertEqual(config['radius'], 150)
        
        # Change height
        spy.clear()
        self.widget.cyl_height.setValue(80)
        process_events_for(50)
        
        assert_signal_emitted(spy, 1)
        config = self.widget.get_configuration()
        self.assertEqual(config['height'], 80)
        
    def test_material_configuration_updates(self):
        """Test updating material configuration."""
        spy = SignalSpy(self.widget.base_changed)
        
        # Change material type
        self.widget.material_combo.setCurrentText("Acrylic - Clear")
        process_events_for(50)
        
        assert_signal_emitted(spy, 1)
        config = self.widget.get_configuration()
        self.assertEqual(config['material'], "Acrylic - Clear")
        
        # Change thickness
        spy.clear()
        self.widget.thickness_spin.setValue(3.5)
        process_events_for(50)
        
        assert_signal_emitted(spy, 1)
        config = self.widget.get_configuration()
        self.assertEqual(config['thickness'], 3.5)
        
    @patch('PyQt6.QtWidgets.QFileDialog.getOpenFileName')
    def test_custom_file_selection(self, mock_dialog):
        """Test custom file selection."""
        # Switch to custom
        custom_button = self.widget.type_buttons['custom']
        click_widget(custom_button)
        
        spy = SignalSpy(self.widget.base_changed)
        
        # Mock file dialog
        test_file = "/path/to/test.stl"
        mock_dialog.return_value = (test_file, "3D Models (*.stl *.obj)")
        
        # Click browse button
        browse_btn = get_child_widget(self.widget, QPushButton, "Browse...")
        self.assertIsNotNone(browse_btn)
        click_widget(browse_btn)
        
        # Check file was set
        self.assertEqual(self.widget.custom_file.text(), test_file)
        assert_signal_emitted(spy, 1)
        
        config = self.widget.get_configuration()
        self.assertEqual(config['type'], 'custom')
        self.assertEqual(config['file'], test_file)
        
    def test_preview_request_signal(self):
        """Test preview request signal emission."""
        spy = SignalSpy(self.widget.preview_requested)
        
        # Find and click preview button
        preview_btn = None
        for btn in self.widget.findChildren(QPushButton):
            if btn.text() == "Update Preview":
                preview_btn = btn
                break
                
        self.assertIsNotNone(preview_btn)
        click_widget(preview_btn)
        
        assert_signal_emitted(spy, 1)
        
        # Check emitted configuration
        emitted_config = spy.last_emission()[0]
        current_config = self.widget.get_configuration()
        self.assertEqual(emitted_config, current_config)
        
    def test_set_configuration(self):
        """Test setting configuration programmatically."""
        # Test rectangular configuration
        rect_config = create_mock_config('rectangular', width=250, depth=180, height=60)
        self.widget.set_configuration(rect_config)
        process_events_for(50)
        
        self.assertTrue(self.widget.type_buttons['rectangular'].isChecked())
        self.assertEqual(self.widget.rect_width.value(), 250)
        self.assertEqual(self.widget.rect_depth.value(), 180)
        self.assertEqual(self.widget.rect_height.value(), 60)
        
        # Test cylindrical configuration
        cyl_config = create_mock_config('cylindrical', radius=120, height=70)
        self.widget.set_configuration(cyl_config)
        process_events_for(50)
        
        self.assertTrue(self.widget.type_buttons['cylindrical'].isChecked())
        self.assertEqual(self.widget.cyl_radius.value(), 120)
        self.assertEqual(self.widget.cyl_height.value(), 70)
        
        # Test custom configuration
        custom_config = create_mock_config('custom', file='custom_base.obj')
        self.widget.set_configuration(custom_config)
        process_events_for(50)
        
        self.assertTrue(self.widget.type_buttons['custom'].isChecked())
        self.assertEqual(self.widget.custom_file.text(), 'custom_base.obj')
        
        # Test material settings
        material_config = create_mock_config('rectangular')
        material_config['material'] = '3D Print - PLA'
        material_config['thickness'] = 4.5
        self.widget.set_configuration(material_config)
        process_events_for(50)
        
        self.assertEqual(self.widget.material_combo.currentText(), '3D Print - PLA')
        self.assertEqual(self.widget.thickness_spin.value(), 4.5)
        
    def test_value_constraints(self):
        """Test spin box value constraints."""
        # Test rectangular constraints
        self.widget.rect_width.setValue(1000)  # Beyond max
        self.assertEqual(self.widget.rect_width.value(), 500)  # Should be clamped
        
        self.widget.rect_width.setValue(10)  # Below min
        self.assertEqual(self.widget.rect_width.value(), 50)  # Should be clamped
        
        # Test cylindrical constraints
        cyl_button = self.widget.type_buttons['cylindrical']
        click_widget(cyl_button)
        
        self.widget.cyl_radius.setValue(400)  # Beyond max
        self.assertEqual(self.widget.cyl_radius.value(), 300)  # Should be clamped
        
        # Test thickness constraints
        self.widget.thickness_spin.setValue(0.5)  # Below min
        self.assertEqual(self.widget.thickness_spin.value(), 1.0)  # Should be clamped
        
        self.widget.thickness_spin.setValue(25.0)  # Beyond max
        self.assertEqual(self.widget.thickness_spin.value(), 20.0)  # Should be clamped
        
    def test_signal_emission_on_type_change(self):
        """Test base_changed signal is emitted when type changes."""
        spy = SignalSpy(self.widget.base_changed)
        
        # Change to cylindrical
        cyl_button = self.widget.type_buttons['cylindrical']
        click_widget(cyl_button)
        
        assert_signal_emitted(spy, 1)
        config = spy.last_emission()[0]
        self.assertEqual(config['type'], 'cylindrical')
        
        # Change to custom
        spy.clear()
        custom_button = self.widget.type_buttons['custom']
        click_widget(custom_button)
        
        assert_signal_emitted(spy, 1)
        config = spy.last_emission()[0]
        self.assertEqual(config['type'], 'custom')
        
    def test_configuration_persistence(self):
        """Test configuration values persist when switching types."""
        # Set custom rectangular values
        self.widget.rect_width.setValue(300)
        self.widget.rect_depth.setValue(200)
        self.widget.rect_height.setValue(75)
        
        # Switch to cylindrical
        cyl_button = self.widget.type_buttons['cylindrical']
        click_widget(cyl_button)
        
        # Set cylindrical values
        self.widget.cyl_radius.setValue(150)
        self.widget.cyl_height.setValue(80)
        
        # Switch back to rectangular
        rect_button = self.widget.type_buttons['rectangular']
        click_widget(rect_button)
        
        # Values should be preserved
        self.assertEqual(self.widget.rect_width.value(), 300)
        self.assertEqual(self.widget.rect_depth.value(), 200)
        self.assertEqual(self.widget.rect_height.value(), 75)
        
        # Switch back to cylindrical
        click_widget(cyl_button)
        
        # Cylindrical values should be preserved
        self.assertEqual(self.widget.cyl_radius.value(), 150)
        self.assertEqual(self.widget.cyl_height.value(), 80)


if __name__ == '__main__':
    unittest.main()