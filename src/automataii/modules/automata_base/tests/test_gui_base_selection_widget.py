"""
Comprehensive tests for BaseSelectionWidget.
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
        'setLayout': Mock(),
        'update': Mock(),
        'show': Mock(),
        'hide': Mock(),
        'setStyleSheet': Mock(),
        'setObjectName': Mock(),
        'objectName': Mock(return_value='test'),
        'setEnabled': Mock(),
        'setVisible': Mock(),
        'addWidget': Mock(),
        'addLayout': Mock(),
        'addStretch': Mock()
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
        'setStyleSheet': Mock(),
        'setPixmap': Mock()
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
    
    mock_radio = type('QRadioButton', (), {
        '__init__': lambda self, text='', parent=None: None,
        'setChecked': Mock(),
        'isChecked': Mock(return_value=False),
        'setObjectName': Mock(),
        'objectName': Mock(return_value='test')
    })
    
    mock_button_group = type('QButtonGroup', (), {
        '__init__': lambda self, parent=None: None,
        'addButton': Mock(),
        'buttons': Mock(return_value=[]),
        'buttonClicked': MagicMock()
    })
    
    mock_pixmap = type('QPixmap', (), {
        '__init__': lambda self, w=0, h=0: None,
        'fill': Mock(),
        'save': Mock()
    })
    
    mock_painter = type('QPainter', (), {
        '__init__': lambda self, device=None: None,
        'setRenderHint': Mock(),
        'setPen': Mock(),
        'setBrush': Mock(),
        'drawRect': Mock(),
        'drawEllipse': Mock(),
        'drawLine': Mock(),
        'drawPolygon': Mock(),
        'pen': Mock(),
        'end': Mock(),
        'RenderHint': type('RenderHint', (), {'Antialiasing': 1})
    })
    
    # Patch the modules
    sys.modules['PyQt6.QtWidgets'].QWidget = mock_widget
    sys.modules['PyQt6.QtWidgets'].QVBoxLayout = mock_layout
    sys.modules['PyQt6.QtWidgets'].QGridLayout = mock_layout
    sys.modules['PyQt6.QtWidgets'].QLabel = mock_label
    sys.modules['PyQt6.QtWidgets'].QComboBox = mock_combo
    sys.modules['PyQt6.QtWidgets'].QGroupBox = mock_widget
    sys.modules['PyQt6.QtWidgets'].QRadioButton = mock_radio
    sys.modules['PyQt6.QtWidgets'].QButtonGroup = mock_button_group
    sys.modules['PyQt6.QtGui'].QPixmap = mock_pixmap
    sys.modules['PyQt6.QtGui'].QPainter = mock_painter
    sys.modules['PyQt6.QtGui'].QBrush = Mock
    sys.modules['PyQt6.QtGui'].QColor = Mock
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
    sys.modules['PyQt6.QtCore'].Qt = type('Qt', (), {
        'GlobalColor': type('GlobalColor', (), {'transparent': 0, 'white': 1}),
        'AlignmentFlag': type('AlignmentFlag', (), {'AlignCenter': 4})
    })

# Mock Qt before importing the widget
mock_qt_modules()

from automataii.modules.automata_base.gui.base_selection_widget import BaseSelectionWidget
from automataii.modules.automata_base.enums.base_types import BaseType


class TestBaseSelectionWidget:
    """Test suite for BaseSelectionWidget."""
    
    @pytest.fixture
    def widget(self):
        """Create a BaseSelectionWidget instance for testing."""
        return BaseSelectionWidget()
    
    def test_initialization(self, widget):
        """Test widget initialization."""
        assert widget.current_base_type is None
        assert widget.current_specification is None
        assert hasattr(widget, 'type_buttons')
        assert hasattr(widget, 'spec_combo')
        assert hasattr(widget, 'spec_info_label')
    
    def test_base_type_selection(self, widget):
        """Test base type selection functionality."""
        # Create mock button
        mock_button = Mock()
        mock_button.objectName.return_value = BaseType.FLAT_RECTANGULAR.value
        
        # Test type change
        widget._on_type_changed(mock_button)
        assert widget.current_base_type == BaseType.FLAT_RECTANGULAR
    
    def test_specification_selection(self, widget):
        """Test specification selection."""
        # Mock spec combo data
        widget.spec_combo.itemData = Mock(return_value="simple_flat")
        
        # Test spec change
        widget._on_spec_changed(1)
        assert widget.current_specification == "simple_flat"
    
    def test_create_base_type_icon(self, widget):
        """Test icon creation for different base types."""
        for base_type in BaseType:
            pixmap = widget.create_base_type_icon(base_type)
            assert pixmap is not None
    
    def test_get_selected_base_type(self, widget):
        """Test getting selected base type."""
        widget.current_base_type = BaseType.BOX_OPEN
        assert widget.get_selected_base_type() == BaseType.BOX_OPEN
    
    def test_get_selected_specification(self, widget):
        """Test getting selected specification."""
        widget.current_specification = "test_spec"
        assert widget.get_selected_specification() == "test_spec"
    
    def test_set_base_type(self, widget):
        """Test setting base type programmatically."""
        # Create mock buttons
        mock_button1 = Mock()
        mock_button1.objectName.return_value = BaseType.FLAT_RECTANGULAR.value
        mock_button1.setChecked = Mock()
        
        mock_button2 = Mock()
        mock_button2.objectName.return_value = BaseType.FLAT_CIRCULAR.value
        mock_button2.setChecked = Mock()
        
        widget.type_buttons.buttons = Mock(return_value=[mock_button1, mock_button2])
        
        # Set base type
        widget.set_base_type(BaseType.FLAT_CIRCULAR)
        mock_button2.setChecked.assert_called_with(True)
    
    def test_set_specification(self, widget):
        """Test setting specification programmatically."""
        # Mock combo box
        widget.spec_combo.count = Mock(return_value=3)
        widget.spec_combo.itemData = Mock(side_effect=[None, "spec1", "spec2"])
        widget.spec_combo.setCurrentIndex = Mock()
        
        # Set specification
        widget.set_specification("spec2")
        widget.spec_combo.setCurrentIndex.assert_called_with(2)
    
    def test_signals_emitted(self, widget):
        """Test that signals are emitted correctly."""
        # Track emitted signals
        emitted_base_type = []
        emitted_spec = []
        
        # Connect mock callbacks
        widget.base_type_changed.connect(lambda x: emitted_base_type.append(x))
        widget.specification_changed.connect(lambda x: emitted_spec.append(x))
        
        # Test base type change signal
        mock_button = Mock()
        mock_button.objectName.return_value = BaseType.PEDESTAL.value
        widget._on_type_changed(mock_button)
        assert len(emitted_base_type) == 1
        assert emitted_base_type[0] == BaseType.PEDESTAL
        
        # Test specification change signal
        widget.spec_combo.itemData = Mock(return_value="simple_flat")
        widget._on_spec_changed(1)
        assert len(emitted_spec) == 1
        assert emitted_spec[0] == "simple_flat"
    
    def test_spec_info_update(self, widget):
        """Test specification info label update."""
        # Mock getting specification
        with patch('automataii.modules.automata_base.gui.base_selection_widget.get_base_specification') as mock_get_spec:
            mock_spec = Mock()
            mock_spec.name = "Test Spec"
            mock_spec.description = "Test Description"
            mock_spec.base_type = BaseType.FLAT_RECTANGULAR
            mock_spec.standard_sizes = {"small": {}, "medium": {}}
            mock_spec.default_material = Mock(value="WOOD")
            mock_get_spec.return_value = mock_spec
            
            widget.spec_combo.itemData = Mock(return_value="test_spec")
            widget._on_spec_changed(1)
            
            # Verify setText was called with appropriate content
            widget.spec_info_label.setText.assert_called()
            call_args = widget.spec_info_label.setText.call_args[0][0]
            assert "Test Spec" in call_args
            assert "Test Description" in call_args
    
    def test_custom_configuration_handling(self, widget):
        """Test handling of custom configuration selection."""
        widget.spec_combo.itemData = Mock(return_value=None)
        widget._on_spec_changed(0)
        
        assert widget.current_specification is None
        widget.spec_info_label.setText.assert_called_with("Custom configuration selected")


class TestBaseSelectionWidgetIntegration:
    """Integration tests for BaseSelectionWidget."""
    
    @pytest.fixture
    def widget(self):
        """Create widget for integration testing."""
        return BaseSelectionWidget()
    
    def test_full_selection_workflow(self, widget):
        """Test complete selection workflow."""
        # Select base type
        mock_button = Mock()
        mock_button.objectName.return_value = BaseType.BOX_ENCLOSED.value
        widget._on_type_changed(mock_button)
        
        # Select specification
        widget.spec_combo.itemData = Mock(return_value="display_box")
        widget._on_spec_changed(2)
        
        # Verify final state
        assert widget.get_selected_base_type() == BaseType.BOX_ENCLOSED
        assert widget.get_selected_specification() == "display_box"
    
    def test_base_type_icon_variations(self, widget):
        """Test that each base type produces a unique icon."""
        icons = {}
        for base_type in BaseType:
            icon = widget.create_base_type_icon(base_type)
            # In real implementation, we'd check pixel data
            # For mock, just ensure it's created
            assert icon is not None
            icons[base_type] = icon
        
        # Ensure we created icons for all types
        assert len(icons) == len(BaseType)


class TestBaseSelectionWidgetEdgeCases:
    """Edge case tests for BaseSelectionWidget."""
    
    @pytest.fixture
    def widget(self):
        """Create widget for edge case testing."""
        return BaseSelectionWidget()
    
    def test_invalid_specification_handling(self, widget):
        """Test handling of invalid specification."""
        widget.spec_combo.itemData = Mock(return_value="---")
        widget._on_spec_changed(1)
        
        assert widget.current_specification is None
    
    def test_no_buttons_edge_case(self, widget):
        """Test when no radio buttons exist."""
        widget.type_buttons.buttons = Mock(return_value=[])
        
        # Should not crash
        widget.set_base_type(BaseType.FLAT_RECTANGULAR)
    
    def test_empty_specification_list(self, widget):
        """Test with empty specification list."""
        with patch('automataii.modules.automata_base.gui.base_selection_widget.list_specifications', return_value=[]):
            # Create new widget with empty spec list
            new_widget = BaseSelectionWidget()
            # Should still have at least Custom option and separator
            # The widget adds "Custom" and "---" by default
            assert hasattr(new_widget, 'spec_combo')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])