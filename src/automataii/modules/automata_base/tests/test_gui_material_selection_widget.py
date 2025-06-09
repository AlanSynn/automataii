"""
Comprehensive tests for MaterialSelectionWidget.
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
    
    mock_label = type('QLabel', (), {
        '__init__': lambda self, text='', parent=None: None,
        'setText': Mock(),
        'setWordWrap': Mock(),
        'setStyleSheet': Mock()
    })
    
    mock_combo = type('QComboBox', (), {
        '__init__': lambda self, parent=None: None,
        'addItem': Mock(),
        'currentIndex': Mock(return_value=0),
        'setCurrentIndex': Mock(),
        'itemData': Mock(return_value=None),
        'count': Mock(return_value=0),
        'currentIndexChanged': MagicMock(),
        'model': Mock(return_value=Mock(item=Mock(return_value=Mock(setEnabled=Mock()))))
    })
    
    mock_spinbox = type('QDoubleSpinBox', (), {
        '__init__': lambda self, parent=None: None,
        'setRange': Mock(),
        'setValue': Mock(),
        'setSingleStep': Mock(),
        'setSuffix': Mock(),
        'value': Mock(return_value=10.0),
        'valueChanged': MagicMock()
    })
    
    mock_table = type('QTableWidget', (), {
        '__init__': lambda self, parent=None: None,
        'setColumnCount': Mock(),
        'setHorizontalHeaderLabels': Mock(),
        'horizontalHeader': Mock(return_value=Mock(setStretchLastSection=Mock())),
        'verticalHeader': Mock(return_value=Mock(setVisible=Mock())),
        'setMaximumHeight': Mock(),
        'setRowCount': Mock(),
        'insertRow': Mock(),
        'setItem': Mock(),
        'resizeRowsToContents': Mock(),
        'rowCount': Mock(return_value=0)
    })
    
    mock_table_item = type('QTableWidgetItem', (), {
        '__init__': lambda self, text='': None
    })
    
    mock_groupbox = type('QGroupBox', (), {
        '__init__': lambda self, title='', parent=None: None,
        'setLayout': Mock()
    })
    
    # Patch the modules
    sys.modules['PyQt6.QtWidgets'].QWidget = mock_widget
    sys.modules['PyQt6.QtWidgets'].QVBoxLayout = mock_layout
    sys.modules['PyQt6.QtWidgets'].QHBoxLayout = mock_layout
    sys.modules['PyQt6.QtWidgets'].QLabel = mock_label
    sys.modules['PyQt6.QtWidgets'].QComboBox = mock_combo
    sys.modules['PyQt6.QtWidgets'].QGroupBox = mock_groupbox
    sys.modules['PyQt6.QtWidgets'].QDoubleSpinBox = mock_spinbox
    sys.modules['PyQt6.QtWidgets'].QTableWidget = mock_table
    sys.modules['PyQt6.QtWidgets'].QTableWidgetItem = mock_table_item
    sys.modules['PyQt6.QtWidgets'].QHeaderView = Mock
    # Create proper signal mock
    class SignalMock:
        def __init__(self, *args):
            self.callbacks = []
            
        def connect(self, callback):
            self.callbacks.append(callback)
            
        def emit(self, *args):
            for callback in self.callbacks:
                callback(*args)
    
    sys.modules['PyQt6.QtCore'].pyqtSignal = lambda *args: SignalMock(*args)
    sys.modules['PyQt6.QtCore'].Qt = Mock

# Mock Qt before importing the widget
mock_qt_modules()

from automataii.modules.automata_base.gui.material_selection_widget import MaterialSelectionWidget
from automataii.modules.automata_base.enums.base_types import MaterialType, BaseType
from automataii.modules.automata_base.models.base_config import BaseConfiguration
from automataii.modules.automata_base.models.dimensions import Dimensions2D, Unit


class TestMaterialSelectionWidget:
    """Test suite for MaterialSelectionWidget."""
    
    @pytest.fixture
    def widget(self):
        """Create a MaterialSelectionWidget instance for testing."""
        return MaterialSelectionWidget()
    
    @pytest.fixture
    def mock_config(self):
        """Create a mock base configuration."""
        config = BaseConfiguration(
            name="Test Base",
            base_type=BaseType.FLAT_RECTANGULAR,
            dimensions=Dimensions2D(width=200, height=150, unit=Unit.MM),
            primary_material=MaterialType.WOOD,
            material_thickness=10.0,
            mounting_type=Mock(),
            assembly_method=Mock()
        )
        return config
    
    def test_initialization(self, widget):
        """Test widget initialization."""
        assert widget.current_material is None
        assert widget.current_thickness == 10.0
        assert hasattr(widget, 'cost_calculator')
        assert hasattr(widget, 'material_combo')
        assert hasattr(widget, 'thickness_spin')
        assert hasattr(widget, 'properties_table')
        assert hasattr(widget, 'cost_label')
    
    def test_material_selection(self, widget):
        """Test material selection functionality."""
        # Mock material type
        widget.material_combo.itemData = Mock(return_value=MaterialType.ALUMINUM)
        
        # Trigger material change
        widget._on_material_changed(1)
        
        assert widget.current_material == MaterialType.ALUMINUM
    
    def test_thickness_change(self, widget):
        """Test thickness change functionality."""
        widget._on_thickness_changed(15.5)
        assert widget.current_thickness == 15.5
    
    def test_material_properties_display(self, widget):
        """Test material properties display update."""
        with patch.object(MaterialType, 'get_properties') as mock_get_props:
            mock_get_props.return_value = {
                "category": "Metal",
                "workability": "Moderate",
                "durability": "High",
                "cost": "Medium",
                "weight": "Light"
            }
            
            widget.current_material = MaterialType.ALUMINUM
            widget._update_properties_display()
            
            # Verify table was populated
            assert widget.properties_table.setRowCount.called
            assert widget.properties_table.insertRow.called
            assert widget.properties_table.setItem.called
    
    def test_thickness_range_update(self, widget):
        """Test thickness range updates for different materials."""
        test_cases = [
            (MaterialType.CARDBOARD, 1.0, 10.0, 3.0),
            (MaterialType.ACRYLIC, 2.0, 20.0, 5.0),
            (MaterialType.STEEL, 1.0, 50.0, 5.0),
            (MaterialType.WOOD, 5.0, 100.0, 15.0),
        ]
        
        for material, min_t, max_t, default_t in test_cases:
            widget.current_material = material
            widget._update_thickness_range()
            
            widget.thickness_spin.setRange.assert_called_with(min_t, max_t)
            widget.thickness_spin.setValue.assert_called_with(default_t)
    
    def test_cost_estimate_update(self, widget, mock_config):
        """Test cost estimate update."""
        widget.current_material = MaterialType.WOOD
        
        with patch.object(widget.cost_calculator, 'calculate_material_cost') as mock_calc:
            mock_calc.return_value = {
                'material_cost': 12.50,
                'fastener_cost': 2.00,
                'finish_cost': 5.00,
                'subtotal': 19.50,
                'price_per_unit': '$0.05',
                'price_unit': 'per cm²'
            }
            
            widget.update_cost_estimate(mock_config)
            
            # Verify cost label was updated
            widget.cost_label.setText.assert_called()
            call_args = widget.cost_label.setText.call_args[0][0]
            assert "$12.50" in call_args
            assert "$19.50" in call_args
    
    def test_cost_estimate_error_handling(self, widget, mock_config):
        """Test cost estimate error handling."""
        widget.current_material = MaterialType.WOOD
        
        with patch.object(widget.cost_calculator, 'calculate_material_cost') as mock_calc:
            mock_calc.side_effect = Exception("Calculation error")
            
            widget.update_cost_estimate(mock_config)
            
            # Verify error message was displayed
            widget.cost_label.setText.assert_called()
            call_args = widget.cost_label.setText.call_args[0][0]
            assert "Cost calculation error" in call_args
    
    def test_get_selected_material(self, widget):
        """Test getting selected material."""
        widget.current_material = MaterialType.ACRYLIC
        assert widget.get_selected_material() == MaterialType.ACRYLIC
    
    def test_get_thickness(self, widget):
        """Test getting thickness value."""
        widget.current_thickness = 8.5
        assert widget.get_thickness() == 8.5
    
    def test_set_material(self, widget):
        """Test setting material programmatically."""
        # Mock combo box
        widget.material_combo.count = Mock(return_value=10)
        widget.material_combo.itemData = Mock(side_effect=[
            None, MaterialType.WOOD, MaterialType.PLYWOOD, MaterialType.MDF,
            None, MaterialType.ALUMINUM, MaterialType.STEEL
        ])
        widget.material_combo.setCurrentIndex = Mock()
        
        # Set material
        widget.set_material(MaterialType.ALUMINUM)
        widget.material_combo.setCurrentIndex.assert_called_with(5)
    
    def test_set_thickness(self, widget):
        """Test setting thickness programmatically."""
        widget.set_thickness(12.5)
        widget.thickness_spin.setValue.assert_called_with(12.5)
    
    def test_signals_emitted(self, widget):
        """Test that signals are emitted correctly."""
        # Mock signals
        widget.material_changed = Mock()
        widget.thickness_changed = Mock()
        
        # Test material change signal
        widget.material_combo.itemData = Mock(return_value=MaterialType.STEEL)
        widget._on_material_changed(1)
        widget.material_changed.emit.assert_called_with(MaterialType.STEEL)
        
        # Test thickness change signal
        widget._on_thickness_changed(20.0)
        widget.thickness_changed.emit.assert_called_with(20.0)


class TestMaterialSelectionWidgetIntegration:
    """Integration tests for MaterialSelectionWidget."""
    
    @pytest.fixture
    def widget(self):
        """Create widget for integration testing."""
        return MaterialSelectionWidget()
    
    def test_complete_material_selection_workflow(self, widget):
        """Test complete material selection workflow."""
        # Select material
        widget.material_combo.itemData = Mock(return_value=MaterialType.ACRYLIC)
        widget._on_material_changed(8)  # Acrylic index
        
        # Set thickness
        widget._on_thickness_changed(5.0)
        
        # Update cost with configuration
        config = BaseConfiguration(
            name="Test",
            base_type=BaseType.FLAT_RECTANGULAR,
            dimensions=Dimensions2D(width=300, height=200, unit=Unit.MM),
            primary_material=MaterialType.ACRYLIC,
            material_thickness=5.0,
            mounting_type=Mock(),
            assembly_method=Mock()
        )
        
        with patch.object(widget.cost_calculator, 'calculate_material_cost') as mock_calc:
            mock_calc.return_value = {
                'material_cost': 25.00,
                'fastener_cost': 0,
                'finish_cost': 0,
                'subtotal': 25.00,
                'price_per_unit': '$0.42',
                'price_unit': 'per 100cm²'
            }
            
            widget.update_cost_estimate(config)
        
        # Verify final state
        assert widget.get_selected_material() == MaterialType.ACRYLIC
        assert widget.get_thickness() == 5.0
    
    def test_material_category_grouping(self, widget):
        """Test that materials are properly grouped by category."""
        # Check that separators were added
        call_count = widget.material_combo.addItem.call_count
        
        # Should have multiple materials plus separators
        assert call_count > len(MaterialType)
    
    def test_all_materials_thickness_ranges(self, widget):
        """Test thickness ranges for all material types."""
        for material_type in MaterialType:
            widget.current_material = material_type
            widget._update_thickness_range()
            
            # Verify setRange was called
            widget.thickness_spin.setRange.assert_called()
            
            # Get the call args
            call_args = widget.thickness_spin.setRange.call_args[0]
            min_thickness, max_thickness = call_args
            
            # Verify reasonable ranges
            assert min_thickness > 0
            assert max_thickness > min_thickness
            assert max_thickness <= 100  # Reasonable max


class TestMaterialSelectionWidgetEdgeCases:
    """Edge case tests for MaterialSelectionWidget."""
    
    @pytest.fixture
    def widget(self):
        """Create widget for edge case testing."""
        return MaterialSelectionWidget()
    
    def test_no_material_selected(self, widget):
        """Test behavior when no material is selected."""
        widget.material_combo.itemData = Mock(return_value=None)
        widget._on_material_changed(0)
        
        assert widget.current_material is None
    
    def test_invalid_thickness_values(self, widget):
        """Test handling of invalid thickness values."""
        # Thickness should be clamped to valid range
        widget.current_material = MaterialType.CARDBOARD
        widget._update_thickness_range()
        
        # Try to set thickness outside range
        widget.thickness_spin.setValue = Mock()
        widget.set_thickness(-5.0)  # Negative value
        # The spinbox should handle clamping internally
    
    def test_cost_calculation_with_no_material(self, widget):
        """Test cost calculation when no material is selected."""
        config = Mock()
        widget.current_material = None
        
        widget.update_cost_estimate(config)
        # Should not crash
    
    def test_material_with_no_density(self, widget):
        """Test handling materials without density information."""
        widget.current_material = MaterialType.WOOD
        
        # Mock cost calculator without density info
        widget.cost_calculator.prices = {
            MaterialType.WOOD: Mock(density=None)
        }
        
        widget._update_properties_display()
        # Should handle missing density gracefully
    
    def test_separator_selection(self, widget):
        """Test that separator items cannot be selected."""
        # Try to select a separator
        widget.material_combo.itemData = Mock(return_value=None)
        widget.material_combo.model = Mock(return_value=Mock(
            item=Mock(return_value=Mock(setEnabled=Mock()))
        ))
        
        # Initialize creates separators
        widget = MaterialSelectionWidget()
        
        # Verify setEnabled(False) was called for separators
        assert widget.material_combo.model().item().setEnabled.called


class TestMaterialSelectionWidgetProperties:
    """Test material properties functionality."""
    
    @pytest.fixture
    def widget(self):
        """Create widget for testing."""
        return MaterialSelectionWidget()
    
    def test_properties_table_population(self, widget):
        """Test that properties table is populated correctly."""
        with patch.object(MaterialType, 'get_properties') as mock_get_props:
            mock_get_props.return_value = {
                "category": "Organic",
                "workability": "Easy",
                "durability": "Medium",
                "cost": "Low",
                "weight": "Light"
            }
            
            widget.current_material = MaterialType.WOOD
            widget._update_properties_display()
            
            # Check that all properties were added to table
            expected_rows = 5  # Base properties
            assert widget.properties_table.insertRow.call_count >= expected_rows
    
    def test_properties_with_density(self, widget):
        """Test properties display with density information."""
        widget.current_material = MaterialType.ALUMINUM
        
        # Mock cost calculator with density
        widget.cost_calculator.prices = {
            MaterialType.ALUMINUM: Mock(density=2700)
        }
        
        with patch.object(MaterialType, 'get_properties') as mock_get_props:
            mock_get_props.return_value = {
                "category": "Metal",
                "workability": "Moderate",
                "durability": "High",
                "cost": "Medium",
                "weight": "Light"
            }
            
            widget._update_properties_display()
            
            # Should have added density row
            assert widget.properties_table.insertRow.call_count > 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])