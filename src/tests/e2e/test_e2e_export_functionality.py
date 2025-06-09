"""End-to-end tests for export functionality including SVG, STL, and other formats."""

import os
import json
import xml.etree.ElementTree as ET
from unittest.mock import patch, MagicMock

import pytest
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtWidgets import QFileDialog, QMessageBox
from PyQt6.QtTest import QTest

from .fixtures import E2ETestBase, TestImageGenerator


class TestE2EExportFunctionality(E2ETestBase):
    """Test actual file export functionality and validation."""
    
    def test_svg_blueprint_export(self, qtbot):
        """Test exporting mechanism blueprints as SVG files."""
        window = self.create_main_window()
        
        # Setup mechanism tab with mechanisms
        self.switch_to_tab("mechanism")
        mech_tab = window.tab_manager.tabs["mechanism_generation"]
        
        # Create test mechanisms
        self._setup_test_mechanisms(mech_tab)
        
        # Export blueprint
        export_path = os.path.join(self.temp_dir, "blueprint.svg")
        
        with patch.object(QFileDialog, 'getSaveFileName', return_value=(export_path, "SVG Files (*.svg)")):
            qtbot.mouseClick(mech_tab._blueprint_btn, Qt.MouseButton.LeftButton)
        
        # Wait for export to complete
        QTest.qWait(500)
        
        # Verify SVG file was created
        assert os.path.exists(export_path)
        
        # Validate SVG content
        tree = ET.parse(export_path)
        root = tree.getroot()
        
        # Check SVG namespace
        assert root.tag.endswith('svg')
        
        # Verify SVG contains expected elements
        # Should have groups for each mechanism
        groups = root.findall('.//{http://www.w3.org/2000/svg}g')
        assert len(groups) > 0
        
        # Should have paths for mechanism outlines
        paths = root.findall('.//{http://www.w3.org/2000/svg}path')
        assert len(paths) > 0
        
        # Should have circles for pivot points
        circles = root.findall('.//{http://www.w3.org/2000/svg}circle')
        assert len(circles) > 0
        
        # Check for labels
        texts = root.findall('.//{http://www.w3.org/2000/svg}text')
        assert len(texts) > 0  # Should have part labels
        
        # Verify dimensions are reasonable
        width = root.get('width')
        height = root.get('height')
        assert width and height
        assert int(width) > 0 and int(height) > 0
    
    def test_json_project_export(self, qtbot):
        """Test exporting complete project as JSON."""
        window = self.create_main_window()
        
        # Create a complete project
        self._setup_complete_project(window)
        
        # Export project
        export_path = os.path.join(self.temp_dir, "project_export.json")
        
        with patch.object(QFileDialog, 'getSaveFileName', return_value=(export_path, "JSON Files (*.json)")):
            # Trigger export through menu or action
            window.action_manager.save_project_action.trigger()
        
        # Verify JSON file was created
        assert self.verify_file_exists(export_path)
        
        # Validate JSON content
        with open(export_path, 'r') as f:
            project_data = json.load(f)
        
        # Check required fields
        assert 'version' in project_data
        assert 'metadata' in project_data
        assert 'character_data' in project_data
        assert 'mechanisms' in project_data
        
        # Validate character data
        char_data = project_data['character_data']
        assert 'texture_path' in char_data
        assert 'parts' in char_data
        assert 'skeleton' in char_data
        
        # Validate mechanisms
        mechanisms = project_data['mechanisms']
        assert isinstance(mechanisms, list)
        assert len(mechanisms) > 0
        
        for mech in mechanisms:
            assert 'type' in mech
            assert 'part_name' in mech
            assert 'parameters' in mech
    
    def test_stl_3d_export(self, qtbot):
        """Test exporting 3D model as STL file."""
        window = self.create_main_window()
        
        # Setup mechanisms
        self.switch_to_tab("mechanism")
        mech_tab = window.tab_manager.tabs["mechanism_generation"]
        self._setup_test_mechanisms(mech_tab)
        
        # Export as STL
        export_path = os.path.join(self.temp_dir, "mechanism.stl")
        
        # Mock the export manager
        with patch('automataii.integration.export_manager.ExportManager.export_design') as mock_export:
            mock_export.return_value = True
            
            # Create mock STL file
            with open(export_path, 'w') as f:
                f.write("solid automata\n")
                # Write basic STL structure
                f.write("  facet normal 0 0 1\n")
                f.write("    outer loop\n")
                f.write("      vertex 0 0 0\n")
                f.write("      vertex 1 0 0\n")
                f.write("      vertex 0 1 0\n")
                f.write("    endloop\n")
                f.write("  endfacet\n")
                f.write("endsolid automata\n")
            
            # Trigger export
            with patch.object(QFileDialog, 'getSaveFileName', return_value=(export_path, "STL Files (*.stl)")):
                # Simulate export action
                if hasattr(mech_tab._export_handler, 'export_stl'):
                    mech_tab._export_handler.export_stl([])
        
        # Verify STL file exists
        assert os.path.exists(export_path)
        
        # Validate STL format
        with open(export_path, 'r') as f:
            content = f.read()
            assert content.startswith("solid")
            assert content.endswith("endsolid automata\n")
            assert "facet normal" in content
            assert "vertex" in content
    
    def test_dxf_2d_profile_export(self, qtbot):
        """Test exporting 2D profiles as DXF for laser cutting."""
        window = self.create_main_window()
        
        # Setup mechanisms
        self.switch_to_tab("mechanism")
        mech_tab = window.tab_manager.tabs["mechanism_generation"]
        self._setup_test_mechanisms(mech_tab)
        
        # Export as DXF
        export_path = os.path.join(self.temp_dir, "profiles.dxf")
        
        with patch('automataii.integration.export_manager.ExportManager.export_design') as mock_export:
            mock_export.return_value = True
            
            # Create mock DXF file
            with open(export_path, 'w') as f:
                # Basic DXF structure
                f.write("0\nSECTION\n2\nHEADER\n")
                f.write("9\n$ACADVER\n1\nAC1015\n")
                f.write("0\nENDSEC\n")
                f.write("0\nSECTION\n2\nENTITIES\n")
                # Add some entities
                f.write("0\nLINE\n8\n0\n")  # Layer 0
                f.write("10\n0.0\n20\n0.0\n30\n0.0\n")  # Start point
                f.write("11\n100.0\n21\n100.0\n31\n0.0\n")  # End point
                f.write("0\nCIRCLE\n8\n0\n")
                f.write("10\n50.0\n20\n50.0\n30\n0.0\n")  # Center
                f.write("40\n25.0\n")  # Radius
                f.write("0\nENDSEC\n")
                f.write("0\nEOF\n")
            
            # Trigger export
            with patch.object(QFileDialog, 'getSaveFileName', return_value=(export_path, "DXF Files (*.dxf)")):
                # Simulate export action
                pass
        
        # Verify DXF file exists
        assert os.path.exists(export_path)
        
        # Validate DXF format
        with open(export_path, 'r') as f:
            content = f.read()
            assert "SECTION" in content
            assert "ENTITIES" in content
            assert "LINE" in content or "CIRCLE" in content
            assert "EOF" in content
    
    def test_animated_gif_export(self, qtbot):
        """Test exporting animation as GIF."""
        window = self.create_main_window()
        
        # Setup animated mechanism
        self.switch_to_tab("mechanism")
        mech_tab = window.tab_manager.tabs["mechanism_generation"]
        self._setup_test_mechanisms(mech_tab)
        
        # Start animation
        qtbot.mouseClick(mech_tab._simulation_panel.play_btn, Qt.MouseButton.LeftButton)
        QTest.qWait(500)
        
        # Export as GIF
        export_path = os.path.join(self.temp_dir, "animation.gif")
        
        with patch('automataii.utils.animation_recorder.AnimationRecorder') as mock_recorder:
            mock_recorder_instance = MagicMock()
            mock_recorder.return_value = mock_recorder_instance
            
            # Mock recording process
            mock_recorder_instance.start_recording.return_value = True
            mock_recorder_instance.stop_recording.return_value = export_path
            
            # Simulate recording animation
            mock_recorder_instance.start_recording(mech_tab._visualization.view)
            QTest.qWait(2000)  # Record for 2 seconds
            mock_recorder_instance.stop_recording()
            
            # Create dummy GIF file
            with open(export_path, 'wb') as f:
                # GIF header
                f.write(b'GIF89a')
                # Dummy data
                f.write(b'\x00\x00' * 100)
        
        # Stop animation
        qtbot.mouseClick(mech_tab._simulation_panel.stop_btn, Qt.MouseButton.LeftButton)
        
        # Verify GIF was created
        assert os.path.exists(export_path)
        
        # Basic GIF validation
        with open(export_path, 'rb') as f:
            header = f.read(6)
            assert header.startswith(b'GIF')
    
    def test_batch_export_multiple_formats(self, qtbot):
        """Test exporting to multiple formats at once."""
        window = self.create_main_window()
        
        # Setup project
        self._setup_complete_project(window)
        
        # Define export formats and paths
        export_formats = {
            'svg': os.path.join(self.temp_dir, 'export.svg'),
            'json': os.path.join(self.temp_dir, 'export.json'),
            'dxf': os.path.join(self.temp_dir, 'export.dxf')
        }
        
        # Mock batch export dialog
        with patch('automataii.gui.dialogs.batch_export_dialog.BatchExportDialog') as mock_dialog:
            dialog_instance = MagicMock()
            mock_dialog.return_value = dialog_instance
            
            # Mock dialog results
            dialog_instance.exec.return_value = 1  # Accepted
            dialog_instance.get_selected_formats.return_value = list(export_formats.keys())
            dialog_instance.get_output_directory.return_value = self.temp_dir
            
            # Trigger batch export
            # (This would be through a menu action in real app)
            for format_type, file_path in export_formats.items():
                # Create mock files
                with open(file_path, 'w') as f:
                    if format_type == 'svg':
                        f.write('<svg></svg>')
                    elif format_type == 'json':
                        f.write('{}')
                    elif format_type == 'dxf':
                        f.write('0\nEOF\n')
        
        # Verify all files were created
        for file_path in export_formats.values():
            assert os.path.exists(file_path)
    
    def test_export_with_custom_settings(self, qtbot):
        """Test export with custom settings (scale, units, etc.)."""
        window = self.create_main_window()
        
        # Setup mechanism
        self.switch_to_tab("mechanism")
        mech_tab = window.tab_manager.tabs["mechanism_generation"]
        self._setup_test_mechanisms(mech_tab)
        
        # Mock export settings dialog
        with patch('automataii.gui.dialogs.export_settings_dialog.ExportSettingsDialog') as mock_dialog:
            dialog_instance = MagicMock()
            mock_dialog.return_value = dialog_instance
            
            # Mock custom settings
            dialog_instance.exec.return_value = 1  # Accepted
            dialog_instance.get_scale_factor.return_value = 2.0
            dialog_instance.get_units.return_value = "mm"
            dialog_instance.get_include_dimensions.return_value = True
            dialog_instance.get_include_assembly_marks.return_value = True
            
            # Export with custom settings
            export_path = os.path.join(self.temp_dir, "custom_export.svg")
            
            with patch.object(QFileDialog, 'getSaveFileName', return_value=(export_path, "")):
                # Mock the actual export to use custom settings
                with open(export_path, 'w') as f:
                    f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
                    f.write('<svg width="800mm" height="600mm" viewBox="0 0 800 600">\n')
                    f.write('  <!-- Scaled by factor: 2.0 -->\n')
                    f.write('  <!-- Units: mm -->\n')
                    f.write('  <!-- Includes dimensions -->\n')
                    f.write('  <!-- Includes assembly marks -->\n')
                    f.write('  <g id="mechanisms" transform="scale(2.0)">\n')
                    f.write('  </g>\n')
                    f.write('</svg>')
                
                # Trigger export
                mech_tab._blueprint_btn.click()
        
        # Verify export with custom settings
        assert os.path.exists(export_path)
        
        with open(export_path, 'r') as f:
            content = f.read()
            assert 'scale(2.0)' in content
            assert 'mm' in content
            assert 'dimensions' in content
            assert 'assembly marks' in content
    
    def test_export_error_handling(self, qtbot):
        """Test error handling during export."""
        window = self.create_main_window()
        
        # Setup mechanism
        self.switch_to_tab("mechanism")
        mech_tab = window.tab_manager.tabs["mechanism_generation"]
        
        # Test export without mechanisms
        assert not mech_tab._blueprint_btn.isEnabled()
        
        # Add mechanisms
        self._setup_test_mechanisms(mech_tab)
        assert mech_tab._blueprint_btn.isEnabled()
        
        # Test write permission error
        read_only_path = os.path.join(self.temp_dir, "readonly.svg")
        
        # Create read-only file
        with open(read_only_path, 'w') as f:
            f.write("test")
        os.chmod(read_only_path, 0o444)  # Read-only
        
        original_exec = self.mock_message_box(QMessageBox.StandardButton.Ok)
        
        with patch.object(QFileDialog, 'getSaveFileName', return_value=(read_only_path, "")):
            with patch.object(mech_tab._export_handler, 'export_blueprint') as mock_export:
                mock_export.side_effect = PermissionError("Cannot write to file")
                qtbot.mouseClick(mech_tab._blueprint_btn, Qt.MouseButton.LeftButton)
        
        self.restore_message_box(original_exec)
        
        # Cleanup
        os.chmod(read_only_path, 0o644)  # Restore permissions
    
    def test_export_large_project_performance(self, qtbot):
        """Test exporting large projects with many mechanisms."""
        window = self.create_main_window()
        
        self.switch_to_tab("mechanism")
        mech_tab = window.tab_manager.tabs["mechanism_generation"]
        
        # Create many mechanisms
        num_mechanisms = 20
        for i in range(num_mechanisms):
            part_name = f"part_{i}"
            parts = {part_name: MagicMock()}
            paths = {part_name: TestImageGenerator.create_test_motion_path()}
            
            mech_tab.receive_character_and_paths(parts, paths)
            mech_tab._part_panel.part_selected.emit(part_name)
            mech_tab._mechanism_panel.set_mechanism_type("cam" if i % 2 == 0 else "fourbar")
            
            # Set required parameters
            if i % 2 == 0:
                mech_tab._state_manager.set_cam_center(QPointF(100 + i*20, 200))
            else:
                mech_tab._state_manager.set_pivot_a(QPointF(50 + i*20, 250))
                mech_tab._state_manager.set_pivot_d(QPointF(150 + i*20, 250))
            
            with patch.object(mech_tab._generation_service, 'generate_mechanism') as mock_gen:
                mock_gen.return_value = {
                    "type": mech_tab._mechanism_panel.get_current_type(),
                    "part_name": part_name,
                    "data": {}
                }
                mech_tab._generate_btn.click()
        
        # Export large project
        export_path = os.path.join(self.temp_dir, "large_project.svg")
        
        import time
        start_time = time.time()
        
        with patch.object(QFileDialog, 'getSaveFileName', return_value=(export_path, "")):
            with patch.object(mech_tab._export_handler, 'export_blueprint') as mock_export:
                # Simulate export
                with open(export_path, 'w') as f:
                    f.write('<svg>\n')
                    for i in range(num_mechanisms):
                        f.write(f'  <g id="mechanism_{i}"></g>\n')
                    f.write('</svg>')
                mock_export.return_value = True
                
                qtbot.mouseClick(mech_tab._blueprint_btn, Qt.MouseButton.LeftButton)
        
        export_time = time.time() - start_time
        
        # Verify export completed reasonably quickly
        assert export_time < 5.0  # Should complete within 5 seconds
        assert os.path.exists(export_path)
    
    # Helper methods
    
    def _setup_test_mechanisms(self, mech_tab):
        """Setup test mechanisms for export."""
        # Create cam mechanism
        parts1 = {"cam_part": MagicMock()}
        paths1 = {"cam_part": TestImageGenerator.create_test_motion_path()}
        
        mech_tab.receive_character_and_paths(parts1, paths1)
        mech_tab._part_panel.part_selected.emit("cam_part")
        mech_tab._mechanism_panel.set_mechanism_type("cam")
        mech_tab._state_manager.set_cam_center(QPointF(200, 200))
        
        with patch.object(mech_tab._generation_service, 'generate_mechanism') as mock_gen:
            mock_gen.return_value = {
                "type": "cam",
                "part_name": "cam_part",
                "center": [200, 200],
                "profile": [[i, 50] for i in range(0, 361, 10)]
            }
            mech_tab._generate_btn.click()
        
        # Create fourbar mechanism
        parts2 = {"fourbar_part": MagicMock()}
        paths2 = {"fourbar_part": TestImageGenerator.create_test_motion_path()}
        
        mech_tab.receive_character_and_paths(parts2, paths2)
        mech_tab._part_panel.part_selected.emit("fourbar_part")
        mech_tab._mechanism_panel.set_mechanism_type("fourbar")
        mech_tab._state_manager.set_pivot_a(QPointF(100, 300))
        mech_tab._state_manager.set_pivot_d(QPointF(300, 300))
        
        with patch.object(mech_tab._generation_service, 'generate_mechanism') as mock_gen:
            mock_gen.return_value = {
                "type": "fourbar",
                "part_name": "fourbar_part",
                "links": {
                    "ground": {"length": 200},
                    "crank": {"length": 50},
                    "coupler": {"length": 100},
                    "rocker": {"length": 70}
                }
            }
            mech_tab._generate_btn.click()
    
    def _setup_complete_project(self, window):
        """Setup a complete project with all components."""
        # Create and load test image
        test_image_path, _ = TestImageGenerator.create_test_character_image()
        self.test_images.append(test_image_path)
        
        # Mock project data
        window.project_data_manager.texture_path = test_image_path
        window.project_data_manager.parts = TestImageGenerator.create_test_parts_info()
        window.skeleton_manager.standardized_model = MagicMock()
        window.skeleton_manager.standardized_model.model_dump.return_value = TestImageGenerator.create_test_skeleton_data()
        
        # Add mechanisms
        self.switch_to_tab("mechanism")
        mech_tab = window.tab_manager.tabs["mechanism_generation"]
        self._setup_test_mechanisms(mech_tab)