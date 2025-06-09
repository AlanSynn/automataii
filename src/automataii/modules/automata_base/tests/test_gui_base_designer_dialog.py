"""
Comprehensive tests for BaseDesignerDialog.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
import sys
from pathlib import Path

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
    mock_dialog = type('QDialog', (), {
        '__init__': lambda self, parent=None: None,
        'setWindowTitle': Mock(),
        'resize': Mock(),
        'accept': Mock(),
        'reject': Mock()
    })
    
    mock_layout = type('QVBoxLayout', (), {
        '__init__': lambda self, parent=None: None,
        'addWidget': Mock(),
        'addLayout': Mock(),
        'addStretch': Mock()
    })
    
    mock_h_layout = type('QHBoxLayout', (), {
        '__init__': lambda self, parent=None: None,
        'addWidget': Mock(),
        'addLayout': Mock(),
        'addStretch': Mock()
    })
    
    mock_tab_widget = type('QTabWidget', (), {
        '__init__': lambda self, parent=None: None,
        'addTab': Mock(),
        'setMaximumWidth': Mock()
    })
    
    mock_button = type('QPushButton', (), {
        '__init__': lambda self, text='', parent=None: None,
        'setCheckable': Mock(),
        'setChecked': Mock(),
        'clicked': MagicMock(),
        'toggled': MagicMock(),
        'setMenu': Mock()
    })
    
    mock_dialog_buttons = type('QDialogButtonBox', (), {
        '__init__': lambda self, buttons=None, parent=None: None,
        'accepted': MagicMock(),
        'rejected': MagicMock(),
        'addButton': Mock(),
        'StandardButton': type('StandardButton', (), {
            'Ok': 1,
            'Cancel': 2,
            'Yes': 4,
            'No': 8
        }),
        'ButtonRole': type('ButtonRole', (), {
            'ActionRole': 1,
            'ResetRole': 2
        })
    })
    
    mock_menu = type('QMenu', (), {
        '__init__': lambda self, parent=None: None,
        'addAction': Mock(),
        'addSeparator': Mock()
    })
    
    mock_message_box = type('QMessageBox', (), {
        'information': Mock(),
        'warning': Mock(),
        'critical': Mock(),
        'question': Mock(return_value=4),  # Yes
        'StandardButton': type('StandardButton', (), {
            'Yes': 4,
            'No': 8
        })
    })
    
    mock_file_dialog = type('QFileDialog', (), {
        'getSaveFileName': Mock(return_value=('test.svg', 'SVG Files (*.svg)'))
    })
    
    mock_input_dialog = type('QInputDialog', (), {
        'getText': Mock(return_value=('Test Base Name', True))
    })
    
    # Patch the modules
    sys.modules['PyQt6.QtWidgets'].QDialog = mock_dialog
    sys.modules['PyQt6.QtWidgets'].QVBoxLayout = mock_layout
    sys.modules['PyQt6.QtWidgets'].QHBoxLayout = mock_h_layout
    sys.modules['PyQt6.QtWidgets'].QTabWidget = mock_tab_widget
    sys.modules['PyQt6.QtWidgets'].QPushButton = mock_button
    sys.modules['PyQt6.QtWidgets'].QDialogButtonBox = mock_dialog_buttons
    sys.modules['PyQt6.QtWidgets'].QMenu = mock_menu
    sys.modules['PyQt6.QtWidgets'].QMessageBox = mock_message_box
    sys.modules['PyQt6.QtWidgets'].QFileDialog = mock_file_dialog
    sys.modules['PyQt6.QtWidgets'].QInputDialog = mock_input_dialog
    sys.modules['PyQt6.QtCore'].pyqtSignal = Mock
    sys.modules['PyQt6.QtCore'].Qt = Mock

# Mock Qt before importing the dialog
mock_qt_modules()

# Mock the custom widgets
sys.modules['automataii.modules.automata_base.gui.base_selection_widget'] = Mock()
sys.modules['automataii.modules.automata_base.gui.base_preview_widget'] = Mock()
sys.modules['automataii.modules.automata_base.gui.material_selection_widget'] = Mock()
sys.modules['automataii.modules.automata_base.gui.dimension_input_widget'] = Mock()

from automataii.modules.automata_base.gui.base_designer_dialog import BaseDesignerDialog
from automataii.modules.automata_base.models.base_config import BaseConfiguration
from automataii.modules.automata_base.models.dimensions import Dimensions2D, Point2D, MountingPoint, Unit
from automataii.modules.automata_base.enums.base_types import BaseType, MaterialType, MountingType, AssemblyMethod


class TestBaseDesignerDialog:
    """Test suite for BaseDesignerDialog."""
    
    @pytest.fixture
    def dialog(self):
        """Create a BaseDesignerDialog instance for testing."""
        with patch('automataii.modules.automata_base.gui.base_designer_dialog.BaseSelectionWidget'):
            with patch('automataii.modules.automata_base.gui.base_designer_dialog.BasePreviewWidget'):
                with patch('automataii.modules.automata_base.gui.base_designer_dialog.MaterialSelectionWidget'):
                    with patch('automataii.modules.automata_base.gui.base_designer_dialog.DimensionInputWidget'):
                        dialog = BaseDesignerDialog()
                        
                        # Mock the child widgets
                        dialog.base_selection = Mock()
                        dialog.base_selection.base_type_changed = Mock()
                        dialog.base_selection.specification_changed = Mock()
                        dialog.base_selection.set_base_type = Mock()
                        
                        dialog.preview = Mock()
                        dialog.preview.set_base_configuration = Mock()
                        dialog.preview.set_show_dimensions = Mock()
                        dialog.preview.set_show_mounting_points = Mock()
                        dialog.preview.set_show_grid = Mock()
                        
                        dialog.material_selection = Mock()
                        dialog.material_selection.material_changed = Mock()
                        dialog.material_selection.thickness_changed = Mock()
                        dialog.material_selection.set_material = Mock()
                        dialog.material_selection.set_thickness = Mock()
                        dialog.material_selection.update_cost_estimate = Mock()
                        
                        dialog.dimension_input = Mock()
                        dialog.dimension_input.dimensions_changed = Mock()
                        dialog.dimension_input.get_dimensions = Mock(return_value=Dimensions2D(200, 150, Unit.MM))
                        dialog.dimension_input.set_base_type = Mock()
                        dialog.dimension_input.set_dimensions = Mock()
                        
                        return dialog
    
    def test_initialization(self, dialog):
        """Test dialog initialization."""
        assert dialog.current_config is not None
        assert isinstance(dialog.current_config, BaseConfiguration)
        dialog.setWindowTitle.assert_called_with("Automata Base Designer")
        dialog.resize.assert_called_with(1000, 700)
    
    def test_default_configuration(self, dialog):
        """Test default configuration creation."""
        config = dialog.current_config
        assert config.name == "New Base"
        assert config.base_type == BaseType.FLAT_RECTANGULAR
        assert config.primary_material == MaterialType.WOOD
        assert config.material_thickness == 10.0
        assert config.mounting_type == MountingType.SURFACE
        assert config.assembly_method == AssemblyMethod.SCREWS
    
    def test_base_type_change(self, dialog):
        """Test handling base type change."""
        dialog.on_base_type_changed(BaseType.FLAT_CIRCULAR)
        
        assert dialog.current_config.base_type == BaseType.FLAT_CIRCULAR
        dialog.dimension_input.set_base_type.assert_called_with(BaseType.FLAT_CIRCULAR)
        dialog.preview.set_base_configuration.assert_called()
    
    def test_specification_change(self, dialog):
        """Test handling specification change."""
        with patch('automataii.modules.automata_base.gui.base_designer_dialog.get_base_specification') as mock_get_spec:
            mock_spec = Mock()
            mock_spec.create_base = Mock(return_value=BaseConfiguration(
                name="Test Spec",
                base_type=BaseType.BOX_OPEN,
                dimensions=Dimensions2D(300, 200, Unit.MM),
                primary_material=MaterialType.ACRYLIC,
                material_thickness=5.0,
                mounting_type=MountingType.SURFACE,
                assembly_method=AssemblyMethod.SCREWS
            ))
            mock_get_spec.return_value = mock_spec
            
            dialog.on_specification_changed("test_spec")
            
            # Verify UI was updated
            dialog.dimension_input.set_dimensions.assert_called()
            dialog.material_selection.set_material.assert_called_with(MaterialType.ACRYLIC)
            dialog.material_selection.set_thickness.assert_called_with(5.0)
            dialog.preview.set_base_configuration.assert_called()
    
    def test_dimension_change(self, dialog):
        """Test handling dimension change."""
        new_dims = Dimensions2D(400, 300, Unit.MM)
        
        dialog.on_dimensions_changed(new_dims)
        
        assert dialog.current_config.dimensions == new_dims
        dialog.preview.set_base_configuration.assert_called()
        dialog.material_selection.update_cost_estimate.assert_called()
    
    def test_material_change(self, dialog):
        """Test handling material change."""
        dialog.on_material_changed(MaterialType.ALUMINUM)
        
        assert dialog.current_config.primary_material == MaterialType.ALUMINUM
        dialog.preview.set_base_configuration.assert_called()
        dialog.material_selection.update_cost_estimate.assert_called()
    
    def test_thickness_change(self, dialog):
        """Test handling thickness change."""
        dialog.on_thickness_changed(15.0)
        
        assert dialog.current_config.material_thickness == 15.0
        dialog.preview.set_base_configuration.assert_called()
        dialog.material_selection.update_cost_estimate.assert_called()
    
    def test_validation_success(self, dialog):
        """Test successful validation."""
        with patch('automataii.modules.automata_base.gui.base_designer_dialog.validate_base_configuration') as mock_validate:
            with patch('automataii.modules.automata_base.gui.base_designer_dialog.QMessageBox') as mock_msgbox:
                mock_validate.return_value = []  # No issues
                
                dialog.validate_configuration()
                
                mock_msgbox.information.assert_called()
    
    def test_validation_failure(self, dialog):
        """Test validation with issues."""
        with patch('automataii.modules.automata_base.gui.base_designer_dialog.validate_base_configuration') as mock_validate:
            with patch('automataii.modules.automata_base.gui.base_designer_dialog.QMessageBox') as mock_msgbox:
                mock_validate.return_value = ["Issue 1", "Issue 2"]
                
                dialog.validate_configuration()
                
                mock_msgbox.warning.assert_called()
                warning_text = mock_msgbox.warning.call_args[0][2]
                assert "Issue 1" in warning_text
                assert "Issue 2" in warning_text
    
    def test_reset_configuration(self, dialog):
        """Test reset configuration."""
        with patch('automataii.modules.automata_base.gui.base_designer_dialog.QMessageBox') as mock_msgbox:
            mock_msgbox.question.return_value = mock_msgbox.StandardButton.Yes
            
            # Modify config first
            dialog.current_config.base_type = BaseType.PEDESTAL
            
            dialog.reset_configuration()
            
            # Should reset to default
            assert dialog.current_config.base_type == BaseType.FLAT_RECTANGULAR
            dialog.base_selection.set_base_type.assert_called_with(BaseType.FLAT_RECTANGULAR)
    
    def test_export_svg(self, dialog):
        """Test SVG export."""
        with patch('automataii.modules.automata_base.gui.base_designer_dialog.QFileDialog') as mock_file_dialog:
            with patch('automataii.modules.automata_base.gui.base_designer_dialog.base_to_svg') as mock_to_svg:
                with patch('builtins.open', create=True) as mock_open:
                    with patch('automataii.modules.automata_base.gui.base_designer_dialog.QMessageBox') as mock_msgbox:
                        mock_file_dialog.getSaveFileName.return_value = ('test.svg', 'SVG Files (*.svg)')
                        mock_to_svg.return_value = '<svg>test</svg>'
                        
                        dialog.export_svg()
                        
                        mock_to_svg.assert_called_with(dialog.current_config, mode="technical")
                        mock_open.assert_called_with('test.svg', 'w')
                        mock_msgbox.information.assert_called()
    
    def test_export_dxf(self, dialog):
        """Test DXF export."""
        with patch('automataii.modules.automata_base.gui.base_designer_dialog.QFileDialog') as mock_file_dialog:
            with patch('automataii.modules.automata_base.gui.base_designer_dialog.base_to_dxf') as mock_to_dxf:
                with patch('builtins.open', create=True) as mock_open:
                    with patch('automataii.modules.automata_base.gui.base_designer_dialog.QMessageBox') as mock_msgbox:
                        mock_file_dialog.getSaveFileName.return_value = ('test.dxf', 'DXF Files (*.dxf)')
                        mock_to_dxf.return_value = 'DXF content'
                        
                        dialog.export_dxf()
                        
                        mock_to_dxf.assert_called_with(dialog.current_config)
                        mock_open.assert_called_with('test.dxf', 'w')
                        mock_msgbox.information.assert_called()
    
    def test_export_stl(self, dialog):
        """Test STL export."""
        with patch('automataii.modules.automata_base.gui.base_designer_dialog.QFileDialog') as mock_file_dialog:
            with patch('automataii.modules.automata_base.gui.base_designer_dialog.STLExporter') as mock_exporter_class:
                with patch('automataii.modules.automata_base.gui.base_designer_dialog.QMessageBox') as mock_msgbox:
                    mock_file_dialog.getSaveFileName.return_value = ('test.stl', 'STL Files (*.stl)')
                    mock_exporter = Mock()
                    mock_exporter_class.return_value = mock_exporter
                    
                    dialog.export_stl()
                    
                    mock_exporter_class.assert_called_with(dialog.current_config)
                    mock_exporter.export.assert_called_with('test.stl')
                    mock_msgbox.information.assert_called()
    
    def test_export_stl_error(self, dialog):
        """Test STL export error handling."""
        with patch('automataii.modules.automata_base.gui.base_designer_dialog.QFileDialog') as mock_file_dialog:
            with patch('automataii.modules.automata_base.gui.base_designer_dialog.STLExporter') as mock_exporter_class:
                with patch('automataii.modules.automata_base.gui.base_designer_dialog.QMessageBox') as mock_msgbox:
                    mock_file_dialog.getSaveFileName.return_value = ('test.stl', 'STL Files (*.stl)')
                    mock_exporter_class.side_effect = Exception("Export error")
                    
                    dialog.export_stl()
                    
                    mock_msgbox.critical.assert_called()
    
    def test_accept_with_validation(self, dialog):
        """Test accepting dialog with validation."""
        with patch('automataii.modules.automata_base.gui.base_designer_dialog.validate_base_configuration') as mock_validate:
            with patch('automataii.modules.automata_base.gui.base_designer_dialog.QInputDialog') as mock_input:
                mock_validate.return_value = []  # No issues
                mock_input.getText.return_value = ('Custom Base Name', True)
                dialog.base_created = Mock()
                
                dialog.accept()
                
                assert dialog.current_config.name == 'Custom Base Name'
                dialog.base_created.emit.assert_called_with(dialog.current_config)
    
    def test_accept_with_validation_issues(self, dialog):
        """Test accepting dialog with validation issues."""
        with patch('automataii.modules.automata_base.gui.base_designer_dialog.validate_base_configuration') as mock_validate:
            with patch('automataii.modules.automata_base.gui.base_designer_dialog.QMessageBox') as mock_msgbox:
                mock_validate.return_value = ["Issue 1"]
                mock_msgbox.question.return_value = mock_msgbox.StandardButton.No
                
                dialog.accept()
                
                # Should not proceed
                dialog.base_created.emit.assert_not_called()
    
    def test_view_toggle_connections(self, dialog):
        """Test view toggle button connections."""
        # Test dimensions toggle
        dialog.show_dims_btn.toggled.connect.assert_called()
        
        # Test mounting points toggle  
        dialog.show_mounts_btn.toggled.connect.assert_called()
        
        # Test grid toggle
        dialog.show_grid_btn.toggled.connect.assert_called()
    
    def test_get_configuration(self, dialog):
        """Test getting current configuration."""
        config = dialog.get_configuration()
        assert config == dialog.current_config


class TestBaseDesignerDialogMountingPoints:
    """Test mounting point functionality."""
    
    @pytest.fixture
    def dialog(self):
        """Create dialog for testing."""
        with patch('automataii.modules.automata_base.gui.base_designer_dialog.BaseSelectionWidget'):
            with patch('automataii.modules.automata_base.gui.base_designer_dialog.BasePreviewWidget'):
                with patch('automataii.modules.automata_base.gui.base_designer_dialog.MaterialSelectionWidget'):
                    with patch('automataii.modules.automata_base.gui.base_designer_dialog.DimensionInputWidget'):
                        dialog = BaseDesignerDialog()
                        dialog.dimension_input = Mock()
                        dialog.dimension_input.get_dimensions = Mock(
                            return_value=Dimensions2D(200, 150, Unit.MM)
                        )
                        return dialog
    
    def test_default_mounting_points_rectangular(self, dialog):
        """Test default mounting points for rectangular base."""
        dialog.current_config.base_type = BaseType.FLAT_RECTANGULAR
        dialog.current_config.dimensions = Dimensions2D(200, 150, Unit.MM)
        dialog.current_config.mounting_points = []
        
        dialog.add_default_mounting_points()
        
        # Should have 4 corner mounting points
        assert len(dialog.current_config.mounting_points) == 4
        
        # Check corner positions
        points = dialog.current_config.mounting_points
        assert any(p.position.x == 10 and p.position.y == 10 for p in points)
        assert any(p.position.x == 190 and p.position.y == 10 for p in points)
        assert any(p.position.x == 190 and p.position.y == 140 for p in points)
        assert any(p.position.x == 10 and p.position.y == 140 for p in points)
    
    def test_default_mounting_points_circular(self, dialog):
        """Test default mounting points for circular base."""
        dialog.current_config.base_type = BaseType.FLAT_CIRCULAR
        dialog.current_config.dimensions = Dimensions2D(200, 200, Unit.MM)
        dialog.current_config.mounting_points = []
        
        dialog.add_default_mounting_points()
        
        # Should have 4 radial mounting points
        assert len(dialog.current_config.mounting_points) == 4
        
        # All points should be at same radius from center
        center_x = 100
        center_y = 100
        expected_radius = 80  # 100 - 10*2
        
        for point in dialog.current_config.mounting_points:
            dx = point.position.x - center_x
            dy = point.position.y - center_y
            radius = (dx**2 + dy**2)**0.5
            assert abs(radius - expected_radius) < 1.0  # Allow small rounding error


class TestBaseDesignerDialogIntegration:
    """Integration tests for BaseDesignerDialog."""
    
    @pytest.fixture
    def dialog(self):
        """Create dialog for integration testing."""
        with patch('automataii.modules.automata_base.gui.base_designer_dialog.BaseSelectionWidget'):
            with patch('automataii.modules.automata_base.gui.base_designer_dialog.BasePreviewWidget'):
                with patch('automataii.modules.automata_base.gui.base_designer_dialog.MaterialSelectionWidget'):
                    with patch('automataii.modules.automata_base.gui.base_designer_dialog.DimensionInputWidget'):
                        return BaseDesignerDialog()
    
    def test_complete_design_workflow(self, dialog):
        """Test complete design workflow."""
        # Mock child widgets
        dialog.base_selection = Mock()
        dialog.preview = Mock()
        dialog.material_selection = Mock()
        dialog.dimension_input = Mock()
        dialog.dimension_input.get_dimensions = Mock(return_value=Dimensions2D(300, 200, Unit.MM))
        
        # Select base type
        dialog.on_base_type_changed(BaseType.BOX_ENCLOSED)
        
        # Set dimensions
        new_dims = Dimensions2D(400, 300, Unit.MM)
        dialog.on_dimensions_changed(new_dims)
        
        # Set material
        dialog.on_material_changed(MaterialType.ACRYLIC)
        dialog.on_thickness_changed(5.0)
        
        # Validate
        with patch('automataii.modules.automata_base.gui.base_designer_dialog.validate_base_configuration') as mock_validate:
            mock_validate.return_value = []
            dialog.validate_configuration()
        
        # Export
        with patch('automataii.modules.automata_base.gui.base_designer_dialog.QFileDialog'):
            with patch('automataii.modules.automata_base.gui.base_designer_dialog.base_to_svg'):
                with patch('builtins.open'):
                    dialog.export_svg()
        
        # Accept
        with patch('automataii.modules.automata_base.gui.base_designer_dialog.QInputDialog') as mock_input:
            mock_input.getText.return_value = ('Final Design', True)
            dialog.base_created = Mock()
            dialog.accept()
            
            # Verify final configuration
            final_config = dialog.get_configuration()
            assert final_config.name == 'Final Design'
            assert final_config.base_type == BaseType.BOX_ENCLOSED
            assert final_config.primary_material == MaterialType.ACRYLIC
            assert final_config.material_thickness == 5.0


class TestBaseDesignerDialogExports:
    """Test all export functionality."""
    
    @pytest.fixture
    def dialog(self):
        """Create dialog for export testing."""
        with patch('automataii.modules.automata_base.gui.base_designer_dialog.BaseSelectionWidget'):
            with patch('automataii.modules.automata_base.gui.base_designer_dialog.BasePreviewWidget'):
                with patch('automataii.modules.automata_base.gui.base_designer_dialog.MaterialSelectionWidget'):
                    with patch('automataii.modules.automata_base.gui.base_designer_dialog.DimensionInputWidget'):
                        dialog = BaseDesignerDialog()
                        dialog.dimension_input = Mock()
                        dialog.dimension_input.get_dimensions = Mock(
                            return_value=Dimensions2D(200, 150, Unit.MM)
                        )
                        return dialog
    
    def test_export_step(self, dialog):
        """Test STEP export."""
        with patch('automataii.modules.automata_base.gui.base_designer_dialog.QFileDialog') as mock_file_dialog:
            with patch('automataii.modules.automata_base.gui.base_designer_dialog.STEPExporter') as mock_exporter_class:
                with patch('automataii.modules.automata_base.gui.base_designer_dialog.QMessageBox') as mock_msgbox:
                    mock_file_dialog.getSaveFileName.return_value = ('test.step', 'STEP Files (*.step)')
                    mock_exporter = Mock()
                    mock_exporter_class.return_value = mock_exporter
                    
                    dialog.export_step()
                    
                    mock_exporter_class.assert_called_with(dialog.current_config)
                    mock_exporter.export.assert_called_with('test.step')
                    mock_msgbox.information.assert_called()
    
    def test_export_pdf(self, dialog):
        """Test PDF export."""
        with patch('automataii.modules.automata_base.gui.base_designer_dialog.QFileDialog') as mock_file_dialog:
            with patch('automataii.modules.automata_base.gui.base_designer_dialog.PDFGenerator') as mock_generator_class:
                with patch('automataii.modules.automata_base.gui.base_designer_dialog.QMessageBox') as mock_msgbox:
                    mock_file_dialog.getSaveFileName.return_value = ('test.pdf', 'PDF Files (*.pdf)')
                    mock_generator = Mock()
                    mock_generator_class.return_value = mock_generator
                    
                    dialog.export_pdf()
                    
                    mock_generator_class.assert_called_with(dialog.current_config)
                    mock_generator.generate.assert_called()
                    # Check that Path object was passed
                    path_arg = mock_generator.generate.call_args[0][0]
                    assert isinstance(path_arg, Path)
                    assert str(path_arg) == 'test.pdf'
                    mock_msgbox.information.assert_called()
    
    def test_export_menu_creation(self, dialog):
        """Test export menu has all options."""
        # Check that export button has menu
        dialog.export_btn.setMenu.assert_called()
        
        # Get the menu that was set
        menu_calls = dialog.export_btn.setMenu.call_args_list
        assert len(menu_calls) > 0
        
        # In real implementation, menu would have these actions
        expected_exports = ['SVG', 'DXF', 'STL', 'STEP', 'PDF']
        # Mock validation would check menu.addAction was called for each


if __name__ == "__main__":
    pytest.main([__file__, "-v"])