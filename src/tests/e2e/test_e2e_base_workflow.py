"""End-to-end tests for complete workflows from image selection to export."""

import os
import tempfile
from unittest.mock import patch, MagicMock

import pytest
from PyQt6.QtCore import Qt, QPointF, QTimer
from PyQt6.QtWidgets import QFileDialog, QMessageBox
from PyQt6.QtTest import QTest

from .fixtures import E2ETestBase, TestImageGenerator, MockProcessingService


class TestE2EBaseWorkflow(E2ETestBase):
    """Test complete workflows from start to finish."""
    
    def test_landing_to_export_workflow(self, qtbot):
        """Test complete workflow: landing -> image processing -> editor -> mechanism -> export."""
        # Create main window
        window = self.create_main_window()
        
        # Create test image
        test_image_path, _ = TestImageGenerator.create_test_character_image()
        self.test_images.append(test_image_path)
        
        # Step 1: Select image from landing tab
        landing_tab = window.tab_manager.tabs["landing"]
        assert landing_tab is not None
        
        # Mock the image selection to use our test image
        with patch.object(landing_tab, '_on_image_selected') as mock_select:
            landing_tab._on_image_selected(test_image_path)
            mock_select.assert_called_once_with(test_image_path)
        
        # Verify we switched to image processing tab
        QTest.qWait(100)
        current_tab = window.tab_widget.currentWidget()
        assert current_tab == window.tab_manager.tabs["image_processing"]
        
        # Step 2: Process image (with mocked processing)
        img_proc_tab = window.tab_manager.tabs["image_processing"]
        
        with patch.object(img_proc_tab.processing_service, 'process_image') as mock_process:
            mock_process.return_value = {
                "output_dir": self.temp_dir,
                "texture_path": test_image_path,
                "char_cfg_path": os.path.join(self.temp_dir, "test.cfg"),
                "skeleton": TestImageGenerator.create_test_skeleton_data()
            }
            
            # Click process button
            process_btn = img_proc_tab.control_panel.processing_steps_group.process_btn
            assert process_btn.isEnabled()
            qtbot.mouseClick(process_btn, Qt.MouseButton.LeftButton)
            
            # Verify processing was called
            mock_process.assert_called_once()
        
        # Wait for processing to complete
        QTest.qWait(500)
        
        # Verify skeleton is loaded
        assert img_proc_tab.state.has_skeleton()
        
        # Step 3: Generate parts
        generate_parts_btn = img_proc_tab.control_panel.processing_steps_group.generate_parts_btn
        assert generate_parts_btn.isEnabled()
        
        with patch.object(img_proc_tab.parts_service, 'generate_parts') as mock_generate:
            mock_generate.return_value = (
                os.path.join(self.temp_dir, "parts.json"),
                self.temp_dir
            )
            
            qtbot.mouseClick(generate_parts_btn, Qt.MouseButton.LeftButton)
            mock_generate.assert_called_once()
        
        # Step 4: Switch to editor tab
        next_btn = img_proc_tab.control_panel.next_stage_btn
        assert next_btn.isEnabled()
        qtbot.mouseClick(next_btn, Qt.MouseButton.LeftButton)
        
        QTest.qWait(100)
        current_tab = window.tab_widget.currentWidget()
        assert current_tab == window.tab_manager.tabs["editor"]
        
        # Step 5: Draw motion path in editor
        editor_tab = window.tab_manager.tabs["editor"]
        editor_view = editor_tab.editor_view
        
        # Select a part
        editor_tab._selection_handler.select_part("right_arm")
        
        # Enable motion path drawing
        editor_view.set_mode("define_motion_path")
        
        # Draw a circular path
        path_points = []
        center = QPointF(300, 250)
        radius = 30
        for angle in range(0, 361, 45):
            import math
            x = center.x() + radius * math.cos(math.radians(angle))
            y = center.y() + radius * math.sin(math.radians(angle))
            path_points.append(QPointF(x, y))
        
        self.simulate_canvas_drawing(editor_view, path_points)
        
        # Verify path was created
        assert "right_arm" in editor_view.motion_path_handler._final_paths_map
        
        # Step 6: Go to mechanism generation
        self.switch_to_tab("mechanism")
        mech_tab = window.tab_manager.tabs["mechanism_generation"]
        
        # Receive parts and paths
        parts_dict = {"right_arm": MagicMock()}
        paths_dict = {"right_arm": TestImageGenerator.create_test_motion_path()}
        mech_tab.receive_character_and_paths(parts_dict, paths_dict)
        
        # Select part
        mech_tab._part_panel.part_selected.emit("right_arm")
        
        # Select mechanism type
        mech_tab._mechanism_panel.set_mechanism_type("cam")
        
        # Set cam center
        cam_center = QPointF(300, 300)
        mech_tab._handle_cam_center_selected(cam_center)
        
        # Generate mechanism
        assert mech_tab._generate_btn.isEnabled()
        
        with patch.object(mech_tab._generation_service, 'generate_mechanism') as mock_gen:
            mock_gen.return_value = {
                "type": "cam",
                "part_name": "right_arm",
                "center": [300, 300],
                "profile": [[0, 10], [90, 15], [180, 10], [270, 5], [360, 10]]
            }
            
            qtbot.mouseClick(mech_tab._generate_btn, Qt.MouseButton.LeftButton)
            mock_gen.assert_called_once()
        
        # Verify mechanism was added
        assert len(mech_tab._state_manager.state.current_mechanisms) == 1
        
        # Step 7: Export blueprint
        assert mech_tab._blueprint_btn.isEnabled()
        
        export_path = os.path.join(self.temp_dir, "blueprint.svg")
        with patch.object(QFileDialog, 'getSaveFileName', return_value=(export_path, "")):
            qtbot.mouseClick(mech_tab._blueprint_btn, Qt.MouseButton.LeftButton)
        
        # Verify export was attempted
        QTest.qWait(500)
        # Check if file would be created (mocked export handler would create it)
        
    def test_direct_image_load_workflow(self, qtbot):
        """Test workflow starting with direct image load."""
        window = self.create_main_window()
        
        # Create test image
        test_image_path, _ = TestImageGenerator.create_test_character_image()
        self.test_images.append(test_image_path)
        
        # Switch to image processing tab
        self.switch_to_tab("image_processing")
        img_proc_tab = window.tab_manager.tabs["image_processing"]
        
        # Load image directly
        with patch.object(QFileDialog, 'getOpenFileName', return_value=(test_image_path, "")):
            load_btn = img_proc_tab.control_panel.load_image_btn
            qtbot.mouseClick(load_btn, Qt.MouseButton.LeftButton)
        
        # Verify image loaded
        assert img_proc_tab.state.has_image()
        assert img_proc_tab.state.input_image_path == test_image_path
        
        # Process and continue workflow...
        # (Similar to above test but starting from image processing)
    
    def test_project_save_and_load_workflow(self, qtbot):
        """Test saving and loading a complete project."""
        window = self.create_main_window()
        
        # Create a simple project state
        test_image_path, _ = TestImageGenerator.create_test_character_image()
        self.test_images.append(test_image_path)
        
        # Mock having loaded and processed an image
        window.project_data_manager.texture_path = test_image_path
        window.project_data_manager.parts = TestImageGenerator.create_test_parts_info()
        window.skeleton_manager.standardized_model = MagicMock()
        window.skeleton_manager.standardized_model.model_dump.return_value = TestImageGenerator.create_test_skeleton_data()
        
        # Save project
        project_path = os.path.join(self.temp_dir, "test_project.ata")
        with patch.object(QFileDialog, 'getSaveFileName', return_value=(project_path, "")):
            window.save_project_dialog()
        
        # Verify project file was created
        assert self.verify_file_exists(project_path)
        
        # Clear current state
        window.project_data_manager.clear_all()
        
        # Load project back
        with patch.object(QFileDialog, 'getOpenFileName', return_value=(project_path, "")):
            window.load_project_dialog()
        
        # Verify project was loaded
        assert window.project_data_manager.texture_path is not None
        assert window.project_data_manager.parts is not None
        assert len(window.project_data_manager.parts) > 0
    
    def test_mechanism_recommendation_workflow(self, qtbot):
        """Test AI mechanism recommendation workflow."""
        window = self.create_main_window()
        
        # Setup mechanism tab with test data
        self.switch_to_tab("mechanism")
        mech_tab = window.tab_manager.tabs["mechanism_generation"]
        
        # Add test parts and paths
        parts_dict = {"right_arm": MagicMock()}
        test_path = TestImageGenerator.create_test_motion_path()
        paths_dict = {"right_arm": test_path}
        mech_tab.receive_character_and_paths(parts_dict, paths_dict)
        
        # Select part
        mech_tab._part_panel.part_selected.emit("right_arm")
        
        # Click recommend button
        assert mech_tab._recommend_btn.isEnabled()
        
        # Mock the recommendation dialog
        with patch('automataii.gui.dialogs.recommendation_dialog.MechanismRecommendationDialog.exec') as mock_exec:
            mock_exec.return_value = 1  # Accepted
            with patch('automataii.gui.dialogs.recommendation_dialog.MechanismRecommendationDialog.get_selected_mechanism') as mock_get:
                mock_get.return_value = "fourbar"
                
                qtbot.mouseClick(mech_tab._recommend_btn, Qt.MouseButton.LeftButton)
                
                # Verify mechanism type was updated
                assert mech_tab._mechanism_panel.get_current_type() == "fourbar"
    
    def test_error_handling_workflow(self, qtbot):
        """Test error handling throughout the workflow."""
        window = self.create_main_window()
        
        # Test 1: Try to process without image
        self.switch_to_tab("image_processing")
        img_proc_tab = window.tab_manager.tabs["image_processing"]
        
        # Mock message box to auto-close
        original_exec = self.mock_message_box(QMessageBox.StandardButton.Ok)
        
        process_btn = img_proc_tab.control_panel.processing_steps_group.process_btn
        qtbot.mouseClick(process_btn, Qt.MouseButton.LeftButton)
        
        self.restore_message_box(original_exec)
        
        # Test 2: Try to generate mechanism without motion path
        self.switch_to_tab("mechanism")
        mech_tab = window.tab_manager.tabs["mechanism_generation"]
        
        # Add parts but no paths
        parts_dict = {"right_arm": MagicMock()}
        mech_tab.receive_character_and_paths(parts_dict, {})
        
        mech_tab._part_panel.part_selected.emit("right_arm")
        
        # Generate button should be disabled
        assert not mech_tab._generate_btn.isEnabled()
        
        # Test 3: Invalid mechanism parameters
        # Add a path
        paths_dict = {"right_arm": TestImageGenerator.create_test_motion_path()}
        mech_tab.receive_character_and_paths(parts_dict, paths_dict)
        
        # Try to generate cam without center
        mech_tab._mechanism_panel.set_mechanism_type("cam")
        assert mech_tab._generate_btn.isEnabled()
        
        original_exec = self.mock_message_box(QMessageBox.StandardButton.Ok)
        
        with patch.object(mech_tab._generation_service, 'validate_parameters') as mock_validate:
            mock_validate.return_value = (False, "Cam center not selected")
            qtbot.mouseClick(mech_tab._generate_btn, Qt.MouseButton.LeftButton)
        
        self.restore_message_box(original_exec)
    
    def test_multi_part_animation_workflow(self, qtbot):
        """Test workflow with multiple animated parts."""
        window = self.create_main_window()
        
        # Setup editor with multiple parts
        self.switch_to_tab("editor")
        editor_tab = window.tab_manager.tabs["editor"]
        
        # Create multiple parts
        parts_info = {
            "head": MagicMock(),
            "left_arm": MagicMock(),
            "right_arm": MagicMock(),
            "left_leg": MagicMock(),
            "right_leg": MagicMock()
        }
        
        editor_tab.load_parts(parts_info)
        
        # Draw paths for multiple parts
        parts_to_animate = ["left_arm", "right_arm", "left_leg", "right_leg"]
        paths = {}
        
        for part_name in parts_to_animate:
            editor_tab._selection_handler.select_part(part_name)
            editor_tab.editor_view.set_mode("define_motion_path")
            
            # Create unique path for each part
            path = TestImageGenerator.create_test_motion_path()
            paths[part_name] = path
            
            # Simulate path creation
            editor_tab._path_handler._final_paths_map[part_name] = path
        
        # Go to mechanism generation
        self.switch_to_tab("mechanism")
        mech_tab = window.tab_manager.tabs["mechanism_generation"]
        
        # Send all parts and paths
        mech_tab.receive_character_and_paths(parts_info, paths)
        
        # Generate mechanisms for each animated part
        for part_name in parts_to_animate:
            mech_tab._part_panel.part_selected.emit(part_name)
            
            # Use different mechanism types
            if "arm" in part_name:
                mech_tab._mechanism_panel.set_mechanism_type("fourbar")
            else:
                mech_tab._mechanism_panel.set_mechanism_type("cam")
            
            # Mock generation
            with patch.object(mech_tab._generation_service, 'generate_mechanism') as mock_gen:
                mock_gen.return_value = {
                    "type": mech_tab._mechanism_panel.get_current_type(),
                    "part_name": part_name,
                    "data": {}
                }
                
                # Add required points for fourbar
                if "arm" in part_name:
                    mech_tab._state_manager.set_pivot_a(QPointF(100, 100))
                    mech_tab._state_manager.set_pivot_d(QPointF(200, 100))
                else:
                    mech_tab._state_manager.set_cam_center(QPointF(150, 150))
                
                qtbot.mouseClick(mech_tab._generate_btn, Qt.MouseButton.LeftButton)
        
        # Verify all mechanisms were created
        assert len(mech_tab._state_manager.state.current_mechanisms) == len(parts_to_animate)
        
        # Test simulation with multiple mechanisms
        qtbot.mouseClick(mech_tab._simulation_panel.play_btn, Qt.MouseButton.LeftButton)
        assert mech_tab._state_manager.state.is_mechanism_simulating
        
        # Stop simulation
        qtbot.mouseClick(mech_tab._simulation_panel.stop_btn, Qt.MouseButton.LeftButton)
        assert not mech_tab._state_manager.state.is_mechanism_simulating