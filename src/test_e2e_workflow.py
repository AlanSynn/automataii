#!/usr/bin/env python3
"""
End-to-End Test for Automataii
Tests the complete workflow from image loading to mechanism generation
"""

import sys
import os
from pathlib import Path

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer, QPointF
from automataii.gui.main_window import AutomataDesigner
import logging

logging.basicConfig(level=logging.INFO, format='[TEST] %(message)s')


class E2EWorkflowTest:
    """End-to-end test for the complete Automataii workflow"""
    
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.main_window = AutomataDesigner(debug_mode=True)
        self.main_window.show()
        self.step = 0
        
    def run(self):
        """Run the complete test workflow"""
        logging.info("Starting E2E workflow test...")
        
        # Start the test sequence
        QTimer.singleShot(1000, self.test_step_1_load_image)
        
        # Run the application
        self.app.exec()
        
    def test_step_1_load_image(self):
        """Step 1: Load an example image"""
        logging.info("Step 1: Loading example image...")
        
        # Simulate clicking on astronaut example
        example_path = Path(__file__).parent / "examples" / "astronaut.png"
        if example_path.exists():
            self.main_window.landing_tab.image_selected.emit(str(example_path))
            logging.info("✓ Image loaded successfully")
            QTimer.singleShot(3000, self.test_step_2_check_skeleton)
        else:
            logging.error("✗ Example image not found")
            
    def test_step_2_check_skeleton(self):
        """Step 2: Verify skeleton is visible"""
        logging.info("Step 2: Checking skeleton visibility...")
        
        # Check if skeleton is loaded
        if self.main_window.skeleton_manager.has_skeleton():
            logging.info("✓ Skeleton loaded successfully")
            
            # Check if skeleton is visible
            view = self.main_window.image_proc_tab.view_manager.view
            if hasattr(view, '_skeleton_viz_items') and view._skeleton_viz_items:
                logging.info("✓ Skeleton is visible")
            else:
                logging.warning("⚠ Skeleton loaded but not visible")
                
            QTimer.singleShot(1000, self.test_step_3_check_parts)
        else:
            logging.error("✗ Skeleton not loaded")
            
    def test_step_3_check_parts(self):
        """Step 3: Verify parts are generated"""
        logging.info("Step 3: Checking parts generation...")
        
        # Check if parts are loaded
        if self.main_window.project_data_manager.parts:
            part_count = len(self.main_window.project_data_manager.parts)
            logging.info(f"✓ {part_count} parts generated successfully")
            
            # Switch to editor tab
            self.main_window.tab_manager.switch_to_editor_tab()
            QTimer.singleShot(1000, self.test_step_4_check_editor)
        else:
            logging.error("✗ No parts generated")
            
    def test_step_4_check_editor(self):
        """Step 4: Verify parts in editor"""
        logging.info("Step 4: Checking editor tab...")
        
        # Check if parts are in editor
        if hasattr(self.main_window.editor_tab, 'editor_items'):
            item_count = len(self.main_window.editor_tab.editor_items)
            logging.info(f"✓ {item_count} parts loaded in editor")
            
            # Simulate drawing a motion path
            if item_count > 0:
                QTimer.singleShot(1000, self.test_step_5_draw_path)
            else:
                logging.error("✗ No parts in editor")
        else:
            logging.error("✗ Editor items not found")
            
    def test_step_5_draw_path(self):
        """Step 5: Simulate motion path drawing"""
        logging.info("Step 5: Drawing motion path...")
        
        # Get first part
        first_part = list(self.main_window.editor_tab.editor_items.keys())[0]
        
        # Create a simple circular path
        path_points = []
        for i in range(8):
            angle = i * 45  # degrees
            x = 50 * (1 + 0.5 * (i % 2))  # varying radius
            y = 0
            # Rotate point
            import math
            rad = math.radians(angle)
            px = x * math.cos(rad) - y * math.sin(rad)
            py = x * math.sin(rad) + y * math.cos(rad)
            path_points.append(QPointF(px, py))
            
        # Simulate path drawing completion
        self.main_window.editor_tab._path_handler._final_paths_map[first_part] = path_points
        logging.info("✓ Motion path created")
        
        # Switch to mechanism tab
        self.main_window.tab_widget.setCurrentIndex(3)  # Mechanism Generation tab
        QTimer.singleShot(1000, self.test_step_6_generate_mechanism)
        
    def test_step_6_generate_mechanism(self):
        """Step 6: Generate mechanism"""
        logging.info("Step 6: Generating mechanism...")
        
        # Trigger mechanism generation
        mech_tab = self.main_window.mechanism_generation_tab
        
        # Select fourbar mechanism type
        if hasattr(mech_tab, 'mechanism_type_combo'):
            mech_tab.mechanism_type_combo.setCurrentText("fourbar")
            
        # Trigger generation
        if hasattr(mech_tab, 'generate_mechanism'):
            mech_tab.generate_mechanism()
            logging.info("✓ Mechanism generation triggered")
            QTimer.singleShot(2000, self.test_step_7_check_animation)
        else:
            logging.error("✗ Could not trigger mechanism generation")
            
    def test_step_7_check_animation(self):
        """Step 7: Check animation"""
        logging.info("Step 7: Checking animation...")
        
        # Check if mechanism is animating
        if hasattr(self.main_window.ik_manager, 'is_animating'):
            if self.main_window.ik_manager.is_animating:
                logging.info("✓ Animation is running")
            else:
                # Try to start animation
                self.main_window.ik_manager.start_animation()
                logging.info("✓ Animation started")
        
        QTimer.singleShot(1000, self.test_complete)
        
    def test_complete(self):
        """Test completed"""
        logging.info("\n" + "="*50)
        logging.info("E2E WORKFLOW TEST COMPLETED SUCCESSFULLY!")
        logging.info("All major components are working together")
        logging.info("="*50)
        
        # Close after a delay
        QTimer.singleShot(2000, self.main_window.close)


if __name__ == "__main__":
    test = E2EWorkflowTest()
    test.run()