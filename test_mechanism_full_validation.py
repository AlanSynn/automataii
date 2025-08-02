#!/usr/bin/env python3
"""
Complete end-to-end test to validate mechanism visualization.
This script traces the entire flow from recommendation dialog to final display.
"""

import sys
import json
import logging
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QTextEdit
from PyQt6.QtCore import QPointF, pyqtSlot
from PyQt6.QtGui import QPainterPath

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import the specific modules we need to test
from automataii.ui.main_window import MainWindow
from automataii.ui.dialogs.recommendation_dialog import MechanismRecommendationDialog
from automataii.utils.paths import resolve_path

class MechanismValidationTester(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mechanism Validation Test")
        self.setGeometry(100, 100, 1200, 800)
        
        # Main widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Test control buttons
        self.test_button = QPushButton("Run Validation Test")
        self.test_button.clicked.connect(self.run_validation_test)
        layout.addWidget(self.test_button)
        
        # Log output area
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output)
        
        # Keep reference to main window
        self.main_window = None
        
    def log(self, message):
        """Add message to log output"""
        self.log_output.append(message)
        logger.info(message)
        
    @pyqtSlot()
    def run_validation_test(self):
        """Run the complete validation test"""
        self.log("=== Starting Mechanism Validation Test ===")
        
        # Step 1: Create test motion path
        self.log("\n1. Creating test motion path...")
        test_path = QPainterPath()
        test_path.moveTo(100, 100)
        test_path.cubicTo(150, 50, 200, 150, 250, 100)
        test_path.cubicTo(300, 50, 350, 150, 400, 100)
        self.log(f"   Created path with {test_path.elementCount()} elements")
        
        # Step 2: Load mechanism data
        self.log("\n2. Loading mechanism data...")
        generated_paths_file = resolve_path(
            "src/automataii/domain/kinematics/generated_mechanism_paths.json"
        )
        
        try:
            with open(generated_paths_file, 'r') as f:
                mechanisms = json.load(f)
            self.log(f"   Loaded {len(mechanisms)} mechanisms")
            
            if mechanisms:
                first_mech = mechanisms[0]
                self.log(f"   First mechanism type: {first_mech.get('type')}")
                self.log(f"   Has transform_params: {'transform_params' in first_mech}")
                self.log(f"   Has full_simulation_data: {'full_simulation_data' in first_mech}")
                
                # Check simulation data structure
                if 'full_simulation_data' in first_mech:
                    sim_data = first_mech['full_simulation_data']
                    self.log(f"   Simulation data keys: {list(sim_data.keys())}")
                    
                    if 'joint_positions' in sim_data:
                        joint_pos = sim_data['joint_positions']
                        self.log(f"   Joint positions keys: {list(joint_pos.keys())}")
                        
                        # Check first position of each joint
                        for key, positions in joint_pos.items():
                            if positions and len(positions) > 0:
                                first_pos = positions[0]
                                self.log(f"   {key} first position: {first_pos}")
                
        except Exception as e:
            self.log(f"   ERROR loading mechanism data: {e}")
            return
        
        # Step 3: Create and show recommendation dialog
        self.log("\n3. Creating recommendation dialog...")
        dialog = MechanismRecommendationDialog(
            test_path, generated_paths_file, parent=self
        )
        
        # Connect to track what happens
        dialog.mechanism_selected.connect(self.on_mechanism_selected)
        dialog.mechanism_preview_selected.connect(self.on_mechanism_preview)
        
        # Show dialog (non-modal for testing)
        dialog.show()
        self.log("   Dialog shown - select a mechanism to continue test")
        
    def on_mechanism_preview(self, mechanism_data):
        """Track preview selection"""
        self.log(f"\n4. Preview selected: {mechanism_data.get('type')}")
        self.log(f"   Has transform_params: {mechanism_data.get('transform_params') is not None}")
        
        if mechanism_data.get('transform_params'):
            transform = mechanism_data['transform_params']
            self.log(f"   Transform center: {transform.get('center')}")
            self.log(f"   Transform scale: {transform.get('scale')}")
            self.log(f"   Transform rotation: {transform.get('rotation')}")
    
    def on_mechanism_selected(self, mechanism_data):
        """Track final selection"""
        self.log(f"\n5. MECHANISM SELECTED: {mechanism_data.get('type')}")
        self.log(f"   Parameters: {mechanism_data.get('parameters')}")
        
        # Validate data structure
        self.log("\n6. Validating data structure...")
        required_keys = ['type', 'parameters', 'full_simulation_data']
        for key in required_keys:
            has_key = key in mechanism_data
            self.log(f"   Has {key}: {has_key}")
            if has_key and key == 'parameters':
                params = mechanism_data[key]
                self.log(f"     Parameters: {params}")
        
        # Check what would be passed to visual creation
        self.log("\n7. Checking visual creation data...")
        if 'full_simulation_data' in mechanism_data:
            sim_data = mechanism_data['full_simulation_data']
            if 'joint_positions' in sim_data:
                joint_pos = sim_data['joint_positions']
                
                # Check the exact structure that linkage_visual.py expects
                expected_keys = ['p1_positions', 'p2_positions', 'p3_positions', 'p4_positions']
                for key in expected_keys:
                    if key in joint_pos:
                        positions = joint_pos[key]
                        if positions and len(positions) > 0:
                            self.log(f"   {key}: {len(positions)} frames, first: {positions[0]}")
                    else:
                        self.log(f"   WARNING: Missing {key}")
        
        self.log("\n=== Test Complete - Check if mechanism appears in main view ===")

def main():
    app = QApplication(sys.argv)
    
    # Create test window
    tester = MechanismValidationTester()
    tester.show()
    
    # Also create main window to see actual results
    main_window = MainWindow()
    main_window.show()
    main_window.move(100, 100)
    
    # Position test window next to main window
    tester.move(main_window.x() + main_window.width() + 20, main_window.y())
    tester.main_window = main_window
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()