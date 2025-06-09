"""
Integration tests for the complete GUI system.
Tests interactions between multiple GUI components.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
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

# Mock Qt and custom widgets
mock_qt_modules()
sys.modules['automataii.modules.automata_base.gui.base_selection_widget'] = Mock()
sys.modules['automataii.modules.automata_base.gui.base_preview_widget'] = Mock()
sys.modules['automataii.modules.automata_base.gui.material_selection_widget'] = Mock()
sys.modules['automataii.modules.automata_base.gui.dimension_input_widget'] = Mock()

from automataii.modules.automata_base.gui.base_designer_dialog import BaseDesignerDialog
from automataii.modules.automata_base.models.base_config import BaseConfiguration
from automataii.modules.automata_base.models.dimensions import Dimensions2D, Dimensions3D, Unit
from automataii.modules.automata_base.enums.base_types import BaseType, MaterialType


class TestGUIIntegration:
    """Test integration between GUI components."""
    
    @pytest.fixture
    def mock_widgets(self):
        """Create mock widgets for testing."""
        widgets = {
            'base_selection': Mock(),
            'preview': Mock(), 
            'material_selection': Mock(),
            'dimension_input': Mock()
        }
        
        # Setup common mock behaviors
        widgets['dimension_input'].get_dimensions.return_value = Dimensions2D(200, 150, Unit.MM)
        widgets['base_selection'].base_type_changed = Mock()
        widgets['base_selection'].specification_changed = Mock()
        widgets['material_selection'].material_changed = Mock()
        widgets['material_selection'].thickness_changed = Mock()
        widgets['dimension_input'].dimensions_changed = Mock()
        
        return widgets
    
    def test_base_type_change_updates_all_widgets(self, mock_widgets):
        """Test that changing base type updates all related widgets."""
        with patch('automataii.modules.automata_base.gui.base_designer_dialog.BaseSelectionWidget', return_value=mock_widgets['base_selection']):
            with patch('automataii.modules.automata_base.gui.base_designer_dialog.BasePreviewWidget', return_value=mock_widgets['preview']):
                with patch('automataii.modules.automata_base.gui.base_designer_dialog.MaterialSelectionWidget', return_value=mock_widgets['material_selection']):
                    with patch('automataii.modules.automata_base.gui.base_designer_dialog.DimensionInputWidget', return_value=mock_widgets['dimension_input']):
                        dialog = BaseDesignerDialog()
                        
                        # Simulate base type change
                        dialog.on_base_type_changed(BaseType.BOX_ENCLOSED)
                        
                        # Verify all widgets were updated
                        mock_widgets['dimension_input'].set_base_type.assert_called_with(BaseType.BOX_ENCLOSED)
                        mock_widgets['preview'].set_base_configuration.assert_called()
                        assert dialog.current_config.base_type == BaseType.BOX_ENCLOSED
    
    def test_dimension_change_cascade(self, mock_widgets):
        """Test that dimension changes cascade through the system."""
        with patch('automataii.modules.automata_base.gui.base_designer_dialog.BaseSelectionWidget', return_value=mock_widgets['base_selection']):
            with patch('automataii.modules.automata_base.gui.base_designer_dialog.BasePreviewWidget', return_value=mock_widgets['preview']):
                with patch('automataii.modules.automata_base.gui.base_designer_dialog.MaterialSelectionWidget', return_value=mock_widgets['material_selection']):
                    with patch('automataii.modules.automata_base.gui.base_designer_dialog.DimensionInputWidget', return_value=mock_widgets['dimension_input']):
                        dialog = BaseDesignerDialog()
                        
                        # Simulate dimension change
                        new_dims = Dimensions3D(300, 200, 150, Unit.MM)
                        dialog.on_dimensions_changed(new_dims)
                        
                        # Verify updates
                        mock_widgets['preview'].set_base_configuration.assert_called()
                        mock_widgets['material_selection'].update_cost_estimate.assert_called()
                        assert dialog.current_config.dimensions == new_dims
    
    def test_material_selection_cost_update(self, mock_widgets):
        """Test material selection triggers cost update."""
        with patch('automataii.modules.automata_base.gui.base_designer_dialog.BaseSelectionWidget', return_value=mock_widgets['base_selection']):
            with patch('automataii.modules.automata_base.gui.base_designer_dialog.BasePreviewWidget', return_value=mock_widgets['preview']):
                with patch('automataii.modules.automata_base.gui.base_designer_dialog.MaterialSelectionWidget', return_value=mock_widgets['material_selection']):
                    with patch('automataii.modules.automata_base.gui.base_designer_dialog.DimensionInputWidget', return_value=mock_widgets['dimension_input']):
                        dialog = BaseDesignerDialog()
                        
                        # Change material
                        dialog.on_material_changed(MaterialType.ALUMINUM)
                        dialog.on_thickness_changed(3.0)
                        
                        # Verify cost update
                        assert mock_widgets['material_selection'].update_cost_estimate.call_count >= 2
                        mock_widgets['preview'].set_base_configuration.assert_called()
    
    def test_preview_display_toggles(self, mock_widgets):
        """Test preview display toggle integration."""
        with patch('automataii.modules.automata_base.gui.base_designer_dialog.BaseSelectionWidget', return_value=mock_widgets['base_selection']):
            with patch('automataii.modules.automata_base.gui.base_designer_dialog.BasePreviewWidget', return_value=mock_widgets['preview']):
                with patch('automataii.modules.automata_base.gui.base_designer_dialog.MaterialSelectionWidget', return_value=mock_widgets['material_selection']):
                    with patch('automataii.modules.automata_base.gui.base_designer_dialog.DimensionInputWidget', return_value=mock_widgets['dimension_input']):
                        dialog = BaseDesignerDialog()
                        
                        # Get the connected callbacks
                        dims_callback = dialog.show_dims_btn.toggled.connect.call_args[0][0]
                        mounts_callback = dialog.show_mounts_btn.toggled.connect.call_args[0][0]
                        grid_callback = dialog.show_grid_btn.toggled.connect.call_args[0][0]
                        
                        # Test callbacks
                        dims_callback(False)
                        mock_widgets['preview'].set_show_dimensions.assert_called_with(False)
                        
                        mounts_callback(False)
                        mock_widgets['preview'].set_show_mounting_points.assert_called_with(False)
                        
                        grid_callback(False)
                        mock_widgets['preview'].set_show_grid.assert_called_with(False)


class TestGUIWorkflows:
    """Test complete GUI workflows."""
    
    def test_specification_to_export_workflow(self):
        """Test workflow from specification selection to export."""
        with patch('automataii.modules.automata_base.gui.base_designer_dialog.BaseSelectionWidget') as mock_selection:
            with patch('automataii.modules.automata_base.gui.base_designer_dialog.BasePreviewWidget') as mock_preview:
                with patch('automataii.modules.automata_base.gui.base_designer_dialog.MaterialSelectionWidget') as mock_material:
                    with patch('automataii.modules.automata_base.gui.base_designer_dialog.DimensionInputWidget') as mock_dimension:
                        # Setup mocks
                        mock_dim_instance = Mock()
                        mock_dim_instance.get_dimensions.return_value = Dimensions2D(200, 150, Unit.MM)
                        mock_dim_instance.set_dimensions = Mock()
                        mock_dimension.return_value = mock_dim_instance
                        
                        mock_mat_instance = Mock()
                        mock_mat_instance.set_material = Mock()
                        mock_mat_instance.set_thickness = Mock()
                        mock_material.return_value = mock_mat_instance
                        
                        dialog = BaseDesignerDialog()
                        
                        # Select specification
                        with patch('automataii.modules.automata_base.gui.base_designer_dialog.get_base_specification') as mock_get_spec:
                            mock_spec = Mock()
                            mock_spec.create_base.return_value = BaseConfiguration(
                                name="Test Base",
                                base_type=BaseType.FLAT_RECTANGULAR,
                                dimensions=Dimensions2D(250, 200, Unit.MM),
                                primary_material=MaterialType.WOOD,
                                material_thickness=15.0,
                                mounting_type=Mock(),
                                assembly_method=Mock()
                            )
                            mock_get_spec.return_value = mock_spec
                            
                            dialog.on_specification_changed("standard_base")
                        
                        # Verify configuration was applied
                        mock_dim_instance.set_dimensions.assert_called()
                        mock_mat_instance.set_material.assert_called_with(MaterialType.WOOD)
                        mock_mat_instance.set_thickness.assert_called_with(15.0)
                        
                        # Export to SVG
                        with patch('automataii.modules.automata_base.gui.base_designer_dialog.QFileDialog') as mock_file_dialog:
                            with patch('automataii.modules.automata_base.gui.base_designer_dialog.base_to_svg') as mock_to_svg:
                                with patch('builtins.open'):
                                    mock_file_dialog.getSaveFileName.return_value = ('output.svg', 'SVG Files')
                                    mock_to_svg.return_value = '<svg></svg>'
                                    
                                    dialog.export_svg()
                                    
                                    mock_to_svg.assert_called_with(dialog.current_config, mode="technical")
    
    def test_3d_base_workflow(self):
        """Test workflow for 3D base types."""
        with patch('automataii.modules.automata_base.gui.base_designer_dialog.BaseSelectionWidget'):
            with patch('automataii.modules.automata_base.gui.base_designer_dialog.BasePreviewWidget'):
                with patch('automataii.modules.automata_base.gui.base_designer_dialog.MaterialSelectionWidget'):
                    with patch('automataii.modules.automata_base.gui.base_designer_dialog.DimensionInputWidget') as mock_dimension:
                        # Setup dimension mock to return 3D
                        mock_dim_instance = Mock()
                        mock_dim_instance.get_dimensions.return_value = Dimensions3D(300, 200, 150, Unit.MM)
                        mock_dim_instance.set_base_type = Mock()
                        mock_dimension.return_value = mock_dim_instance
                        
                        dialog = BaseDesignerDialog()
                        
                        # Select 3D base type
                        dialog.on_base_type_changed(BaseType.BOX_ENCLOSED)
                        
                        # Update dimensions
                        new_dims = Dimensions3D(400, 300, 200, Unit.MM)
                        dialog.on_dimensions_changed(new_dims)
                        
                        # Export to STL (3D format)
                        with patch('automataii.modules.automata_base.gui.base_designer_dialog.QFileDialog') as mock_file_dialog:
                            with patch('automataii.modules.automata_base.gui.base_designer_dialog.STLExporter') as mock_stl_exporter:
                                mock_file_dialog.getSaveFileName.return_value = ('output.stl', 'STL Files')
                                mock_exporter = Mock()
                                mock_stl_exporter.return_value = mock_exporter
                                
                                dialog.export_stl()
                                
                                mock_stl_exporter.assert_called_with(dialog.current_config)
                                mock_exporter.export.assert_called_with('output.stl')


class TestGUISignalConnections:
    """Test signal connections between components."""
    
    def test_all_signals_connected(self):
        """Test that all required signals are connected."""
        with patch('automataii.modules.automata_base.gui.base_designer_dialog.BaseSelectionWidget') as mock_selection:
            with patch('automataii.modules.automata_base.gui.base_designer_dialog.BasePreviewWidget'):
                with patch('automataii.modules.automata_base.gui.base_designer_dialog.MaterialSelectionWidget') as mock_material:
                    with patch('automataii.modules.automata_base.gui.base_designer_dialog.DimensionInputWidget') as mock_dimension:
                        # Create mock instances with signals
                        selection_instance = Mock()
                        selection_instance.base_type_changed = Mock()
                        selection_instance.specification_changed = Mock()
                        mock_selection.return_value = selection_instance
                        
                        material_instance = Mock()
                        material_instance.material_changed = Mock()
                        material_instance.thickness_changed = Mock()
                        mock_material.return_value = material_instance
                        
                        dimension_instance = Mock()
                        dimension_instance.dimensions_changed = Mock()
                        dimension_instance.get_dimensions = Mock(return_value=Dimensions2D(200, 150, Unit.MM))
                        mock_dimension.return_value = dimension_instance
                        
                        dialog = BaseDesignerDialog()
                        
                        # Verify all signals are connected
                        selection_instance.base_type_changed.connect.assert_called()
                        selection_instance.specification_changed.connect.assert_called()
                        material_instance.material_changed.connect.assert_called()
                        material_instance.thickness_changed.connect.assert_called()
                        dimension_instance.dimensions_changed.connect.assert_called()


class TestGUIErrorHandling:
    """Test error handling in GUI integration."""
    
    def test_export_error_recovery(self):
        """Test that export errors are handled gracefully."""
        with patch('automataii.modules.automata_base.gui.base_designer_dialog.BaseSelectionWidget'):
            with patch('automataii.modules.automata_base.gui.base_designer_dialog.BasePreviewWidget'):
                with patch('automataii.modules.automata_base.gui.base_designer_dialog.MaterialSelectionWidget'):
                    with patch('automataii.modules.automata_base.gui.base_designer_dialog.DimensionInputWidget'):
                        dialog = BaseDesignerDialog()
                        
                        # Test each export format error handling
                        export_methods = [
                            ('export_stl', 'STLExporter'),
                            ('export_step', 'STEPExporter'),
                            ('export_pdf', 'PDFGenerator')
                        ]
                        
                        for method_name, exporter_name in export_methods:
                            with patch('automataii.modules.automata_base.gui.base_designer_dialog.QFileDialog') as mock_file_dialog:
                                with patch(f'automataii.modules.automata_base.gui.base_designer_dialog.{exporter_name}') as mock_exporter:
                                    with patch('automataii.modules.automata_base.gui.base_designer_dialog.QMessageBox') as mock_msgbox:
                                        mock_file_dialog.getSaveFileName.return_value = ('test.file', 'Files')
                                        mock_exporter.side_effect = Exception("Test error")
                                        
                                        method = getattr(dialog, method_name)
                                        method()
                                        
                                        # Should show error message
                                        mock_msgbox.critical.assert_called()
    
    def test_invalid_configuration_handling(self):
        """Test handling of invalid configurations."""
        with patch('automataii.modules.automata_base.gui.base_designer_dialog.BaseSelectionWidget'):
            with patch('automataii.modules.automata_base.gui.base_designer_dialog.BasePreviewWidget'):
                with patch('automataii.modules.automata_base.gui.base_designer_dialog.MaterialSelectionWidget'):
                    with patch('automataii.modules.automata_base.gui.base_designer_dialog.DimensionInputWidget'):
                        dialog = BaseDesignerDialog()
                        
                        # Create invalid configuration
                        dialog.current_config = None
                        
                        # Try to validate
                        dialog.validate_configuration()
                        # Should not crash
                        
                        # Try to export
                        with patch('automataii.modules.automata_base.gui.base_designer_dialog.base_to_svg') as mock_to_svg:
                            dialog.export_svg()
                            # Should handle gracefully


class TestGUIStateManagement:
    """Test GUI state management."""
    
    def test_state_consistency_after_reset(self):
        """Test that GUI state is consistent after reset."""
        with patch('automataii.modules.automata_base.gui.base_designer_dialog.BaseSelectionWidget') as mock_selection:
            with patch('automataii.modules.automata_base.gui.base_designer_dialog.BasePreviewWidget'):
                with patch('automataii.modules.automata_base.gui.base_designer_dialog.MaterialSelectionWidget') as mock_material:
                    with patch('automataii.modules.automata_base.gui.base_designer_dialog.DimensionInputWidget') as mock_dimension:
                        # Setup mocks
                        selection_instance = Mock()
                        material_instance = Mock()
                        dimension_instance = Mock()
                        dimension_instance.get_dimensions.return_value = Dimensions2D(200, 150, Unit.MM)
                        
                        mock_selection.return_value = selection_instance
                        mock_material.return_value = material_instance
                        mock_dimension.return_value = dimension_instance
                        
                        dialog = BaseDesignerDialog()
                        
                        # Modify state
                        dialog.current_config.base_type = BaseType.PEDESTAL
                        dialog.current_config.primary_material = MaterialType.STEEL
                        
                        # Reset
                        with patch('automataii.modules.automata_base.gui.base_designer_dialog.QMessageBox') as mock_msgbox:
                            mock_msgbox.question.return_value = mock_msgbox.StandardButton.Yes
                            dialog.reset_configuration()
                        
                        # Verify all widgets were reset
                        selection_instance.set_base_type.assert_called_with(BaseType.FLAT_RECTANGULAR)
                        material_instance.set_material.assert_called_with(MaterialType.WOOD)
                        dimension_instance.set_dimensions.assert_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])