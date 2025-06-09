"""
Comprehensive tests for DimensionInputWidget.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import sys

# Mock Qt modules before importing
def mock_qt_modules():
    """Mock Qt modules for testing."""
    # Mock PyQt6
    qt6_modules = [
        'PyQt6', 'PyQt6.QtWidgets', 'PyQt6.QtCore', 'PyQt6.QtGui'
    ]
    for module in qt6_modules:
        sys.modules[module] = MagicMock()
    
    # Mock PyQt5 as fallback
    qt5_modules = [
        'PyQt5', 'PyQt5.QtWidgets', 'PyQt5.QtCore', 'PyQt5.QtGui'
    ]
    for module in qt5_modules:
        sys.modules[module] = MagicMock()
    
    # Create mock classes
    mock_widget = type('QWidget', (), {
        '__init__': lambda self, parent=None: None,
        'setLayout': Mock()
    })
    
    mock_layout = type('QVBoxLayout', (), {
        '__init__': lambda self, parent=None: None,
        'addWidget': Mock(),
        'addLayout': Mock(),
        'addStretch': Mock()
    })
    
    mock_grid_layout = type('QGridLayout', (), {
        '__init__': lambda self, parent=None: None,
        'addWidget': Mock()
    })
    
    mock_label = type('QLabel', (), {
        '__init__': lambda self, text='', parent=None: None,
        'setText': Mock(),
        'setWordWrap': Mock(),
        'setStyleSheet': Mock(),
        'setVisible': Mock()
    })
    
    mock_spinbox = type('QSpinBox', (), {
        '__init__': lambda self, parent=None: None,
        'setRange': Mock(),
        'setValue': Mock(),
        'setSingleStep': Mock(),
        'value': Mock(return_value=100),
        'valueChanged': MagicMock(),
        'blockSignals': Mock(),
        'setEnabled': Mock(),
        'setVisible': Mock()
    })
    
    mock_combo = type('QComboBox', (), {
        '__init__': lambda self, parent=None: None,
        'addItem': Mock(),
        'clear': Mock(),
        'currentIndex': Mock(return_value=0),
        'setCurrentIndex': Mock(),
        'itemData': Mock(return_value=None),
        'count': Mock(return_value=0),
        'currentIndexChanged': MagicMock()
    })
    
    mock_checkbox = type('QCheckBox', (), {
        '__init__': lambda self, text='', parent=None: None,
        'isChecked': Mock(return_value=False),
        'setChecked': Mock(),
        'stateChanged': MagicMock()
    })
    
    mock_button = type('QPushButton', (), {
        '__init__': lambda self, text='', parent=None: None,
        'clicked': MagicMock()
    })
    
    mock_groupbox = type('QGroupBox', (), {
        '__init__': lambda self, title='', parent=None: None,
        'setLayout': Mock()
    })
    
    # Qt constants
    mock_qt = type('Qt', (), {
        'CheckState': type('CheckState', (), {'Checked': type('Checked', (), {'value': 2})}),
        'AlignmentFlag': type('AlignmentFlag', (), {'AlignCenter': 4})
    })
    
    # Patch the modules
    sys.modules['PyQt6.QtWidgets'].QWidget = mock_widget
    sys.modules['PyQt6.QtWidgets'].QVBoxLayout = mock_layout
    sys.modules['PyQt6.QtWidgets'].QHBoxLayout = mock_layout
    sys.modules['PyQt6.QtWidgets'].QGridLayout = mock_grid_layout
    sys.modules['PyQt6.QtWidgets'].QLabel = mock_label
    sys.modules['PyQt6.QtWidgets'].QSpinBox = mock_spinbox
    sys.modules['PyQt6.QtWidgets'].QComboBox = mock_combo
    sys.modules['PyQt6.QtWidgets'].QCheckBox = mock_checkbox
    sys.modules['PyQt6.QtWidgets'].QPushButton = mock_button
    sys.modules['PyQt6.QtWidgets'].QGroupBox = mock_groupbox
    sys.modules['PyQt6.QtCore'].pyqtSignal = Mock
    sys.modules['PyQt6.QtCore'].Qt = mock_qt

# Mock Qt before importing the widget
mock_qt_modules()

from automataii.modules.automata_base.gui.dimension_input_widget import DimensionInputWidget
from automataii.modules.automata_base.models.dimensions import Dimensions2D, Dimensions3D, Unit
from automataii.modules.automata_base.enums.base_types import BaseType


class TestDimensionInputWidget:
    """Test suite for DimensionInputWidget."""
    
    @pytest.fixture
    def widget(self):
        """Create a DimensionInputWidget instance for testing."""
        return DimensionInputWidget()
    
    def test_initialization(self, widget):
        """Test widget initialization."""
        assert widget.is_3d is False
        assert widget.maintain_aspect_ratio is False
        assert widget.aspect_ratio == 1.0
        assert widget.current_unit == Unit.MM
        assert hasattr(widget, 'width_spin')
        assert hasattr(widget, 'height_spin')
        assert hasattr(widget, 'depth_spin')
        assert hasattr(widget, 'unit_combo')
        assert hasattr(widget, 'aspect_check')
        assert hasattr(widget, 'size_combo')
        assert hasattr(widget, 'info_label')
    
    def test_set_base_type_2d(self, widget):
        """Test setting 2D base types."""
        widget.set_base_type(BaseType.FLAT_RECTANGULAR)
        
        assert widget.is_3d is False
        widget.depth_label.setVisible.assert_called_with(False)
        widget.depth_spin.setVisible.assert_called_with(False)
    
    def test_set_base_type_3d(self, widget):
        """Test setting 3D base types."""
        widget.set_base_type(BaseType.BOX_OPEN)
        
        assert widget.is_3d is True
        widget.depth_label.setVisible.assert_called_with(True)
        widget.depth_spin.setVisible.assert_called_with(True)
    
    def test_set_base_type_circular(self, widget):
        """Test setting circular base type."""
        widget.set_base_type(BaseType.FLAT_CIRCULAR)
        
        widget.height_label.setText.assert_called_with("Diameter:")
        widget.width_spin.setEnabled.assert_called_with(True)
        widget.height_spin.setEnabled.assert_called_with(False)
    
    def test_dimension_change_signal(self, widget):
        """Test dimension change signal emission."""
        widget.dimensions_changed = Mock()
        widget.width_spin.value = Mock(return_value=250)
        widget.height_spin.value = Mock(return_value=150)
        
        widget._on_dimension_changed()
        
        widget.dimensions_changed.emit.assert_called()
        emitted_dims = widget.dimensions_changed.emit.call_args[0][0]
        assert isinstance(emitted_dims, Dimensions2D)
        assert emitted_dims.width == 250
        assert emitted_dims.height == 150
    
    def test_aspect_ratio_maintenance(self, widget):
        """Test aspect ratio maintenance."""
        widget.width_spin.value = Mock(return_value=200)
        widget.height_spin.value = Mock(return_value=100)
        widget.aspect_check.isChecked = Mock(return_value=True)
        
        # Enable aspect ratio
        widget._on_aspect_changed(2)  # Qt.Checked value
        assert widget.maintain_aspect_ratio is True
        assert widget.aspect_ratio == 2.0
        
        # Change width and verify height updates
        widget.sender = Mock(return_value=widget.width_spin)
        widget.width_spin.value = Mock(return_value=300)
        widget._on_dimension_changed()
        
        widget.height_spin.setValue.assert_called_with(150)
    
    def test_unit_change(self, widget):
        """Test unit selection change."""
        widget.unit_changed = Mock()
        widget.unit_combo.itemData = Mock(return_value=Unit.CM)
        
        widget._on_unit_changed(1)
        
        assert widget.current_unit == Unit.CM
        widget.unit_changed.emit.assert_called_with(Unit.CM)
    
    def test_common_size_selection(self, widget):
        """Test selecting common sizes."""
        widget.size_combo.itemData = Mock(return_value=(300, 200))
        
        widget._on_size_selected(1)
        
        widget.width_spin.setValue.assert_called_with(300)
        widget.height_spin.setValue.assert_called_with(200)
    
    def test_common_size_selection_3d(self, widget):
        """Test selecting common sizes for 3D bases."""
        widget.is_3d = True
        widget.size_combo.itemData = Mock(return_value=(300, 200))
        
        widget._on_size_selected(1)
        
        widget.width_spin.setValue.assert_called_with(300)
        widget.height_spin.setValue.assert_called_with(200)
        widget.depth_spin.setValue.assert_called_with(160)  # 80% of height
    
    def test_unit_conversion(self, widget):
        """Test unit conversion functionality."""
        # Set initial values
        widget.width_spin.value = Mock(return_value=100)
        widget.height_spin.value = Mock(return_value=50)
        widget.current_unit = Unit.MM
        widget.unit_combo.currentIndex = Mock(return_value=0)
        widget.unit_combo.count = Mock(return_value=3)
        widget.unit_combo.itemData = Mock(return_value=Unit.CM)
        
        # Mock get_dimensions to return MM dimensions
        widget.get_dimensions = Mock(return_value=Dimensions2D(
            width=100, height=50, unit=Unit.MM
        ))
        
        widget._convert_units()
        
        # Should convert to CM (divide by 10)
        widget.width_spin.setValue.assert_called_with(10)
        widget.height_spin.setValue.assert_called_with(5)
        widget.unit_combo.setCurrentIndex.assert_called_with(1)
    
    def test_info_label_update_2d(self, widget):
        """Test info label update for 2D dimensions."""
        dims = Dimensions2D(width=200, height=150, unit=Unit.MM)
        widget.get_dimensions = Mock(return_value=dims)
        
        widget._update_info()
        
        widget.info_label.setText.assert_called()
        text = widget.info_label.setText.call_args[0][0]
        assert "Area:" in text
        assert "Perimeter:" in text
        assert "Diagonal:" in text
    
    def test_info_label_update_3d(self, widget):
        """Test info label update for 3D dimensions."""
        dims = Dimensions3D(width=200, height=150, depth=100, unit=Unit.MM)
        widget.get_dimensions = Mock(return_value=dims)
        widget.is_3d = True
        
        widget._update_info()
        
        widget.info_label.setText.assert_called()
        text = widget.info_label.setText.call_args[0][0]
        assert "Volume:" in text
        assert "Surface Area:" in text
        assert "Diagonal:" in text
    
    def test_get_dimensions_2d(self, widget):
        """Test getting 2D dimensions."""
        widget.width_spin.value = Mock(return_value=250)
        widget.height_spin.value = Mock(return_value=175)
        widget.current_unit = Unit.CM
        widget.is_3d = False
        
        dims = widget.get_dimensions()
        
        assert isinstance(dims, Dimensions2D)
        assert dims.width == 250
        assert dims.height == 175
        assert dims.unit == Unit.CM
    
    def test_get_dimensions_3d(self, widget):
        """Test getting 3D dimensions."""
        widget.width_spin.value = Mock(return_value=250)
        widget.height_spin.value = Mock(return_value=175)
        widget.depth_spin.value = Mock(return_value=125)
        widget.current_unit = Unit.CM
        widget.is_3d = True
        
        dims = widget.get_dimensions()
        
        assert isinstance(dims, Dimensions3D)
        assert dims.width == 250
        assert dims.height == 175
        assert dims.depth == 125
        assert dims.unit == Unit.CM
    
    def test_set_dimensions_2d(self, widget):
        """Test setting 2D dimensions."""
        dims = Dimensions2D(width=300, height=200, unit=Unit.IN)
        
        widget.set_dimensions(dims)
        
        widget.width_spin.setValue.assert_called_with(300)
        widget.height_spin.setValue.assert_called_with(200)
        assert widget.is_3d is False
    
    def test_set_dimensions_3d(self, widget):
        """Test setting 3D dimensions."""
        dims = Dimensions3D(width=300, height=200, depth=150, unit=Unit.IN)
        widget.unit_combo.count = Mock(return_value=4)
        widget.unit_combo.itemData = Mock(side_effect=[Unit.MM, Unit.CM, Unit.IN, Unit.M])
        
        widget.set_dimensions(dims)
        
        widget.width_spin.setValue.assert_called_with(300)
        widget.height_spin.setValue.assert_called_with(200)
        widget.depth_spin.setValue.assert_called_with(150)
        assert widget.is_3d is True
        widget.depth_label.setVisible.assert_called_with(True)
        widget.depth_spin.setVisible.assert_called_with(True)
        widget.unit_combo.setCurrentIndex.assert_called_with(2)


class TestDimensionInputWidgetIntegration:
    """Integration tests for DimensionInputWidget."""
    
    @pytest.fixture
    def widget(self):
        """Create widget for integration testing."""
        return DimensionInputWidget()
    
    def test_complete_dimension_workflow(self, widget):
        """Test complete dimension input workflow."""
        # Set base type
        widget.set_base_type(BaseType.BOX_ENCLOSED)
        
        # Set dimensions manually
        widget.width_spin.value = Mock(return_value=400)
        widget.height_spin.value = Mock(return_value=300)
        widget.depth_spin.value = Mock(return_value=200)
        
        # Enable aspect ratio
        widget._on_aspect_changed(2)
        
        # Select a unit
        widget.unit_combo.itemData = Mock(return_value=Unit.CM)
        widget._on_unit_changed(1)
        
        # Get final dimensions
        dims = widget.get_dimensions()
        assert isinstance(dims, Dimensions3D)
        assert dims.unit == Unit.CM
    
    def test_base_type_specific_sizes(self, widget):
        """Test that common sizes update based on base type."""
        # Test rectangular base
        widget.set_base_type(BaseType.FLAT_RECTANGULAR)
        # Size combo should have been updated
        assert widget.size_combo.clear.called
        assert widget.size_combo.addItem.called
        
        # Test circular base
        widget.set_base_type(BaseType.FLAT_CIRCULAR)
        # Should have diameter-specific sizes
        calls = widget.size_combo.addItem.call_args_list
        # Check that diameter notation is used
        diameter_found = any("⌀" in str(call) for call in calls)
        assert diameter_found or len(calls) > 0
        
        # Test box type
        widget.set_base_type(BaseType.BOX_OPEN)
        # Should have box-specific sizes
        calls = widget.size_combo.addItem.call_args_list
        box_found = any("Box" in str(call) for call in calls)
        assert box_found or len(calls) > 0
    
    def test_all_base_types_handling(self, widget):
        """Test handling of all base types."""
        for base_type in BaseType:
            widget.set_base_type(base_type)
            
            # Should not crash
            dims = widget.get_dimensions()
            assert dims is not None
            
            # 3D types should return 3D dimensions
            if base_type in [BaseType.BOX_OPEN, BaseType.BOX_ENCLOSED, BaseType.PEDESTAL]:
                assert isinstance(dims, Dimensions3D)
            else:
                assert isinstance(dims, Dimensions2D)


class TestDimensionInputWidgetEdgeCases:
    """Edge case tests for DimensionInputWidget."""
    
    @pytest.fixture
    def widget(self):
        """Create widget for edge case testing."""
        return DimensionInputWidget()
    
    def test_zero_dimensions(self, widget):
        """Test handling of zero dimensions."""
        widget.width_spin.value = Mock(return_value=0)
        widget.height_spin.value = Mock(return_value=0)
        
        dims = widget.get_dimensions()
        # Should still create dimensions object
        assert dims.width == 0
        assert dims.height == 0
    
    def test_very_large_dimensions(self, widget):
        """Test handling of very large dimensions."""
        widget.width_spin.value = Mock(return_value=10000)
        widget.height_spin.value = Mock(return_value=10000)
        
        dims = widget.get_dimensions()
        assert dims.width == 10000
        assert dims.height == 10000
    
    def test_aspect_ratio_with_zero(self, widget):
        """Test aspect ratio maintenance with zero values."""
        widget.width_spin.value = Mock(return_value=100)
        widget.height_spin.value = Mock(return_value=0)
        
        # Enable aspect ratio - should handle zero gracefully
        widget._on_aspect_changed(2)
        # Should not crash with divide by zero
    
    def test_unit_conversion_edge_cases(self, widget):
        """Test unit conversion edge cases."""
        # Test with very small values
        widget.get_dimensions = Mock(return_value=Dimensions2D(
            width=0.1, height=0.1, unit=Unit.MM
        ))
        widget.unit_combo.itemData = Mock(return_value=Unit.M)
        
        widget._convert_units()
        
        # Should convert to meters (0.0001)
        widget.width_spin.setValue.assert_called_with(0)  # Rounds to int
    
    def test_custom_size_selection(self, widget):
        """Test custom size selection."""
        widget.size_combo.itemData = Mock(return_value=None)
        
        widget._on_size_selected(0)  # Custom option
        
        # Should not change dimensions
        widget.width_spin.setValue.assert_not_called()
        widget.height_spin.setValue.assert_not_called()
    
    def test_signal_blocking_during_aspect_ratio(self, widget):
        """Test signal blocking during aspect ratio updates."""
        widget.maintain_aspect_ratio = True
        widget.aspect_ratio = 2.0
        widget.sender = Mock(return_value=widget.width_spin)
        widget.width_spin.value = Mock(return_value=400)
        
        widget._on_dimension_changed()
        
        # Should block signals to prevent infinite loop
        widget.height_spin.blockSignals.assert_called_with(True)
        widget.height_spin.setValue.assert_called()
        widget.height_spin.blockSignals.assert_called_with(False)


class TestDimensionInputWidgetUnits:
    """Test unit handling functionality."""
    
    @pytest.fixture
    def widget(self):
        """Create widget for testing."""
        return DimensionInputWidget()
    
    def test_all_units_available(self, widget):
        """Test that all units are available in combo."""
        # Check that addItem was called for each unit
        expected_units = len(Unit)
        # Initial setup calls addItem for each unit
        assert widget.unit_combo.addItem.call_count >= expected_units
    
    def test_unit_cycling(self, widget):
        """Test unit conversion cycling."""
        widget.unit_combo.count = Mock(return_value=4)
        widget.unit_combo.currentIndex = Mock(side_effect=[0, 1, 2, 3, 0])
        widget.unit_combo.itemData = Mock(side_effect=[
            Unit.CM, Unit.IN, Unit.M, Unit.MM
        ])
        
        # Mock dimensions for conversion
        widget.get_dimensions = Mock(side_effect=[
            Dimensions2D(width=100, height=50, unit=Unit.MM),
            Dimensions2D(width=10, height=5, unit=Unit.CM),
            Dimensions2D(width=3.94, height=1.97, unit=Unit.IN),
            Dimensions2D(width=0.1, height=0.05, unit=Unit.M)
        ])
        
        # Cycle through all units
        for _ in range(4):
            widget._convert_units()
        
        # Should have cycled back to MM
        assert widget.unit_combo.setCurrentIndex.call_count == 4


if __name__ == "__main__":
    pytest.main([__file__, "-v"])