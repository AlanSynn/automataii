"""
Comprehensive tests for BasePreviewWidget.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
import sys
import math

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
        'rect': Mock(return_value=type('QRect', (), {
            'width': Mock(return_value=400),
            'height': Mock(return_value=400)
        })()),
        'setMinimumSize': Mock(),
        'setStyleSheet': Mock()
    })
    
    mock_layout = type('QVBoxLayout', (), {
        '__init__': lambda self, parent=None: None,
        'addWidget': Mock(),
        'addLayout': Mock()
    })
    
    mock_label = type('QLabel', (), {
        '__init__': lambda self, text='', parent=None: None,
        'setText': Mock()
    })
    
    mock_slider = type('QSlider', (), {
        '__init__': lambda self, orientation=None: None,
        'setRange': Mock(),
        'setValue': Mock(),
        'setTickPosition': Mock(),
        'setTickInterval': Mock(),
        'valueChanged': MagicMock(),
        'value': Mock(return_value=100),
        'TickPosition': type('TickPosition', (), {'TicksBelow': 1})
    })
    
    mock_painter = type('QPainter', (), {
        '__init__': lambda self, device=None: None,
        'setRenderHint': Mock(),
        'setPen': Mock(),
        'setBrush': Mock(),
        'drawRect': Mock(),
        'drawEllipse': Mock(),
        'drawLine': Mock(),
        'drawText': Mock(),
        'save': Mock(),
        'restore': Mock(),
        'translate': Mock(),
        'rotate': Mock(),
        'fontMetrics': Mock(return_value=Mock(boundingRect=Mock(return_value=Mock(width=Mock(return_value=50))))),
        'setFont': Mock(),
        'end': Mock(),
        'RenderHint': type('RenderHint', (), {'Antialiasing': 1})
    })
    
    mock_pen = type('QPen', (), {
        '__init__': lambda self, color=None, width=1, style=None: None
    })
    
    mock_brush = type('QBrush', (), {
        '__init__': lambda self, color=None: None
    })
    
    mock_color = type('QColor', (), {
        '__init__': lambda self, *args: None
    })
    
    mock_font = type('QFont', (), {
        '__init__': lambda self: None,
        'setPointSize': Mock()
    })
    
    # Qt constants
    mock_qt = type('Qt', (), {
        'Orientation': type('Orientation', (), {'Horizontal': 1}),
        'PenStyle': type('PenStyle', (), {'DotLine': 3, 'DashLine': 2}),
        'GlobalColor': type('GlobalColor', (), {'white': 1})
    })
    
    # Patch the modules
    sys.modules['PyQt6.QtWidgets'].QWidget = mock_widget
    sys.modules['PyQt6.QtWidgets'].QVBoxLayout = mock_layout
    sys.modules['PyQt6.QtWidgets'].QHBoxLayout = mock_layout
    sys.modules['PyQt6.QtWidgets'].QLabel = mock_label
    sys.modules['PyQt6.QtWidgets'].QSlider = mock_slider
    sys.modules['PyQt6.QtGui'].QPainter = mock_painter
    sys.modules['PyQt6.QtGui'].QPen = mock_pen
    sys.modules['PyQt6.QtGui'].QBrush = mock_brush
    sys.modules['PyQt6.QtGui'].QColor = mock_color
    sys.modules['PyQt6.QtGui'].QFont = mock_font
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
    sys.modules['PyQt6.QtCore'].Qt = mock_qt
    sys.modules['PyQt6.QtCore'].QRectF = Mock

# Mock Qt before importing the widget
mock_qt_modules()

from automataii.modules.automata_base.gui.base_preview_widget import BasePreviewWidget
from automataii.modules.automata_base.models.base_config import BaseConfiguration
from automataii.modules.automata_base.models.dimensions import Dimensions2D, Dimensions3D, Point2D, MountingPoint, Unit
from automataii.modules.automata_base.enums.base_types import BaseType, MaterialType, MountingType, AssemblyMethod


class TestBasePreviewWidget:
    """Test suite for BasePreviewWidget."""
    
    @pytest.fixture
    def widget(self):
        """Create a BasePreviewWidget instance for testing."""
        return BasePreviewWidget()
    
    @pytest.fixture
    def mock_config(self):
        """Create a mock base configuration."""
        config = BaseConfiguration(
            name="Test Base",
            base_type=BaseType.FLAT_RECTANGULAR,
            dimensions=Dimensions2D(width=200, height=150, unit=Unit.MM),
            primary_material=MaterialType.WOOD,
            material_thickness=10.0,
            mounting_type=MountingType.SURFACE,
            assembly_method=AssemblyMethod.SCREWS
        )
        # Add mounting points
        config.mounting_points = [
            MountingPoint(position=Point2D(10, 10), hole_diameter=5.0, thread_type="M5"),
            MountingPoint(position=Point2D(190, 10), hole_diameter=5.0, thread_type="M5"),
            MountingPoint(position=Point2D(190, 140), hole_diameter=5.0, thread_type="M5"),
            MountingPoint(position=Point2D(10, 140), hole_diameter=5.0, thread_type="M5")
        ]
        return config
    
    def test_initialization(self, widget):
        """Test widget initialization."""
        assert widget.base_config is None
        assert widget.zoom_level == 1.0
        assert widget.show_dimensions is True
        assert widget.show_mounting_points is True
        assert widget.show_grid is True
        assert widget.grid_size == 10
        assert hasattr(widget, 'zoom_slider')
        assert hasattr(widget, 'zoom_label')
        assert hasattr(widget, 'preview_area')
    
    def test_set_base_configuration(self, widget, mock_config):
        """Test setting base configuration."""
        widget.set_base_configuration(mock_config)
        assert widget.base_config == mock_config
        widget.update.assert_called_once()
    
    def test_zoom_functionality(self, widget):
        """Test zoom slider functionality."""
        # Test zoom change
        widget._on_zoom_changed(150)
        assert widget.zoom_level == 1.5
        widget.zoom_label.setText.assert_called_with("150%")
        widget.update.assert_called()
    
    def test_display_toggles(self, widget):
        """Test display option toggles."""
        # Test dimensions toggle
        widget.set_show_dimensions(False)
        assert widget.show_dimensions is False
        widget.update.assert_called()
        
        # Test mounting points toggle
        widget.set_show_mounting_points(False)
        assert widget.show_mounting_points is False
        widget.update.assert_called()
        
        # Test grid toggle
        widget.set_show_grid(False)
        assert widget.show_grid is False
        widget.update.assert_called()
    
    def test_paint_event_no_config(self, widget):
        """Test paint event with no configuration."""
        mock_event = Mock()
        widget.paintEvent(mock_event)
        # Should not crash and return early
    
    @patch('automataii.modules.automata_base.gui.base_preview_widget.QPainter')
    def test_paint_event_with_config(self, mock_painter_class, widget, mock_config):
        """Test paint event with configuration."""
        mock_painter = Mock()
        mock_painter_class.return_value = mock_painter
        
        widget.set_base_configuration(mock_config)
        widget.paintEvent(Mock())
        
        # Verify painter methods were called
        mock_painter.setRenderHint.assert_called()
        mock_painter.drawRect.assert_called()  # For rectangular base
    
    def test_different_base_types_rendering(self, widget):
        """Test rendering different base types."""
        # Test each base type
        for base_type in BaseType:
            config = BaseConfiguration(
                name=f"Test {base_type.value}",
                base_type=base_type,
                dimensions=Dimensions2D(width=200, height=150, unit=Unit.MM),
                primary_material=MaterialType.WOOD,
                material_thickness=10.0,
                mounting_type=MountingType.SURFACE,
                assembly_method=AssemblyMethod.SCREWS
            )
            widget.set_base_configuration(config)
            # Should not crash
            widget.paintEvent(Mock())
    
    def test_3d_dimensions_handling(self, widget):
        """Test handling of 3D dimensions."""
        config = BaseConfiguration(
            name="3D Box",
            base_type=BaseType.BOX_OPEN,
            dimensions=Dimensions3D(width=200, height=150, depth=100, unit=Unit.MM),
            primary_material=MaterialType.WOOD,
            material_thickness=10.0,
            mounting_type=MountingType.SURFACE,
            assembly_method=AssemblyMethod.SCREWS
        )
        widget.set_base_configuration(config)
        # Should handle 3D dimensions correctly
        widget.paintEvent(Mock())
    
    def test_export_image(self, widget, mock_config):
        """Test image export functionality."""
        widget.set_base_configuration(mock_config)
        
        with patch('PyQt6.QtGui.QPixmap') as mock_pixmap_class:
            mock_pixmap = Mock()
            mock_pixmap_class.return_value = mock_pixmap
            
            widget.export_image("test.png", 800, 600)
            
            mock_pixmap.save.assert_called_with("test.png")
    
    def test_zoom_range(self, widget):
        """Test zoom slider range limits."""
        # Test minimum zoom
        widget._on_zoom_changed(50)
        assert widget.zoom_level == 0.5
        
        # Test maximum zoom
        widget._on_zoom_changed(200)
        assert widget.zoom_level == 2.0
    
    def test_grid_drawing_calculations(self, widget):
        """Test grid drawing calculations."""
        widget.show_grid = True
        widget.grid_size = 25  # Larger grid for testing
        
        # Mock painter and test grid drawing
        mock_painter = Mock()
        mock_rect = Mock(width=Mock(return_value=500), height=Mock(return_value=500))
        
        widget._draw_grid(mock_painter, mock_rect, 2.0)  # scale = 2.0
        
        # Grid spacing should be grid_size * scale = 25 * 2 = 50
        # Should draw multiple lines
        assert mock_painter.drawLine.call_count > 0


class TestBasePreviewWidgetDrawingMethods:
    """Test individual drawing methods."""
    
    @pytest.fixture
    def widget(self):
        """Create widget for testing."""
        return BasePreviewWidget()
    
    @pytest.fixture
    def mock_painter(self):
        """Create mock painter."""
        return Mock()
    
    def test_draw_base_outline_rectangular(self, widget, mock_painter):
        """Test drawing rectangular base outline."""
        config = Mock()
        config.base_type = BaseType.FLAT_RECTANGULAR
        config.dimensions = Mock(width=200, height=150)
        widget.base_config = config
        
        widget._draw_base_outline(mock_painter, 10, 20, 1.0)
        mock_painter.drawRect.assert_called_with(10, 20, 200, 150)
    
    def test_draw_base_outline_circular(self, widget, mock_painter):
        """Test drawing circular base outline."""
        config = Mock()
        config.base_type = BaseType.FLAT_CIRCULAR
        config.dimensions = Mock(width=200, height=200)
        widget.base_config = config
        
        widget._draw_base_outline(mock_painter, 10, 20, 1.0)
        mock_painter.drawEllipse.assert_called()
    
    def test_draw_mounting_points(self, widget, mock_painter):
        """Test drawing mounting points."""
        config = Mock()
        config.mounting_points = [
            MountingPoint(position=Point2D(50, 50), hole_diameter=10, thread_type="M5")
        ]
        widget.base_config = config
        
        widget._draw_mounting_points(mock_painter, 0, 0, 1.0)
        
        # Should draw circle and crosshair
        mock_painter.drawEllipse.assert_called()
        assert mock_painter.drawLine.call_count >= 2  # At least 2 lines for crosshair
        mock_painter.drawText.assert_called()  # Thread type label
    
    def test_draw_dimensions(self, widget, mock_painter):
        """Test drawing dimension lines."""
        config = Mock()
        config.dimensions = Mock(
            width=200, 
            height=150,
            unit=Mock(value="mm")
        )
        widget.base_config = config
        
        # Mock font metrics
        mock_painter.fontMetrics.return_value.boundingRect.return_value.width.return_value = 50
        
        widget._draw_dimensions(mock_painter, 10, 20, 1.0)
        
        # Should draw dimension lines and text
        assert mock_painter.drawLine.call_count >= 4  # Width and height lines with markers
        assert mock_painter.drawText.call_count >= 2  # Width and height labels
    
    def test_draw_info_text(self, widget, mock_painter):
        """Test drawing info text."""
        config = Mock()
        config.name = "Test Base"
        config.base_type = Mock(value="Flat Rectangular")
        widget.base_config = config
        
        mock_rect = Mock(height=Mock(return_value=400))
        widget._draw_info_text(mock_painter, mock_rect)
        
        mock_painter.drawText.assert_called_with(
            10, 390, "Test Base - Flat Rectangular"
        )


class TestBasePreviewWidgetEdgeCases:
    """Edge case tests for BasePreviewWidget."""
    
    @pytest.fixture
    def widget(self):
        """Create widget for edge case testing."""
        return BasePreviewWidget()
    
    def test_very_small_base(self, widget):
        """Test rendering very small base."""
        config = BaseConfiguration(
            name="Tiny Base",
            base_type=BaseType.FLAT_RECTANGULAR,
            dimensions=Dimensions2D(width=10, height=10, unit=Unit.MM),
            primary_material=MaterialType.WOOD,
            material_thickness=1.0,
            mounting_type=MountingType.SURFACE,
            assembly_method=AssemblyMethod.SCREWS
        )
        widget.set_base_configuration(config)
        widget.paintEvent(Mock())  # Should not crash
    
    def test_very_large_base(self, widget):
        """Test rendering very large base."""
        config = BaseConfiguration(
            name="Huge Base",
            base_type=BaseType.FLAT_RECTANGULAR,
            dimensions=Dimensions2D(width=10000, height=10000, unit=Unit.MM),
            primary_material=MaterialType.WOOD,
            material_thickness=100.0,
            mounting_type=MountingType.SURFACE,
            assembly_method=AssemblyMethod.SCREWS
        )
        widget.set_base_configuration(config)
        widget.paintEvent(Mock())  # Should scale appropriately
    
    def test_no_mounting_points(self, widget):
        """Test rendering without mounting points."""
        config = BaseConfiguration(
            name="No Mounts",
            base_type=BaseType.FLAT_RECTANGULAR,
            dimensions=Dimensions2D(width=200, height=150, unit=Unit.MM),
            primary_material=MaterialType.WOOD,
            material_thickness=10.0,
            mounting_type=MountingType.SURFACE,
            assembly_method=AssemblyMethod.SCREWS
        )
        config.mounting_points = []
        widget.set_base_configuration(config)
        widget.paintEvent(Mock())  # Should not crash
    
    def test_extreme_zoom_levels(self, widget):
        """Test extreme zoom levels."""
        config = Mock()
        config.base_type = BaseType.FLAT_RECTANGULAR
        config.dimensions = Mock(width=200, height=150)
        widget.base_config = config
        
        # Test very low zoom
        widget._on_zoom_changed(10)
        widget.paintEvent(Mock())
        
        # Test very high zoom
        widget._on_zoom_changed(500)
        widget.paintEvent(Mock())


class TestBasePreviewWidgetIntegration:
    """Integration tests for BasePreviewWidget."""
    
    @pytest.fixture
    def widget(self):
        """Create widget for integration testing."""
        return BasePreviewWidget()
    
    def test_complete_preview_workflow(self, widget):
        """Test complete preview workflow."""
        # Create configuration
        config = BaseConfiguration(
            name="Integration Test",
            base_type=BaseType.BOX_ENCLOSED,
            dimensions=Dimensions3D(width=300, height=200, depth=150, unit=Unit.MM),
            primary_material=MaterialType.ACRYLIC,
            material_thickness=5.0,
            mounting_type=MountingType.SURFACE,
            assembly_method=AssemblyMethod.INTERLOCKING
        )
        
        # Add mounting points
        for x in [50, 250]:
            for y in [50, 150]:
                config.add_mounting_point(
                    MountingPoint(position=Point2D(x, y), hole_diameter=6.0, thread_type="M6")
                )
        
        # Set configuration
        widget.set_base_configuration(config)
        
        # Adjust display settings
        widget.set_show_grid(True)
        widget.set_show_dimensions(True)
        widget.set_show_mounting_points(True)
        
        # Adjust zoom
        widget._on_zoom_changed(125)
        
        # Test rendering
        widget.paintEvent(Mock())
        
        # Export image
        with patch('PyQt6.QtGui.QPixmap'):
            widget.export_image("integration_test.png", 1024, 768)
    
    def test_all_base_types_preview(self, widget):
        """Test preview of all base types."""
        for base_type in BaseType:
            # Create appropriate dimensions
            if base_type in [BaseType.BOX_OPEN, BaseType.BOX_ENCLOSED, BaseType.PEDESTAL]:
                dims = Dimensions3D(width=200, height=150, depth=100, unit=Unit.MM)
            else:
                dims = Dimensions2D(width=200, height=150, unit=Unit.MM)
            
            config = BaseConfiguration(
                name=f"{base_type.value} Test",
                base_type=base_type,
                dimensions=dims,
                primary_material=MaterialType.WOOD,
                material_thickness=10.0,
                mounting_type=MountingType.SURFACE,
                assembly_method=AssemblyMethod.SCREWS
            )
            
            widget.set_base_configuration(config)
            widget.paintEvent(Mock())
            
            # Test with different zoom levels
            for zoom in [50, 100, 150]:
                widget._on_zoom_changed(zoom)
                widget.paintEvent(Mock())


if __name__ == "__main__":
    pytest.main([__file__, "-v"])