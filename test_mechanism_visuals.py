#!/usr/bin/env python3
"""Test script to debug mechanism visual display issues."""

import sys
import json
import logging
try:
    from PyQt6.QtWidgets import QApplication, QMainWindow
    from PyQt6.QtGui import QPainterPath
    from PyQt6.QtCore import QTimer
except ImportError:
    from PyQt5.QtWidgets import QApplication, QMainWindow
    from PyQt5.QtGui import QPainterPath
    from PyQt5.QtCore import QTimer

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def test_mechanism_visuals():
    """Test mechanism visuals directly in the tab."""
    
    app = QApplication(sys.argv)
    
    # Create a minimal main window
    main_window = QMainWindow()
    main_window.debug_mode = True  # Enable debug mode
    
    # Import the tab after creating the app
    from automataii.gui.tabs.mechanism_design_tab import MechanismDesignTab
    
    # Create the mechanism design tab
    tab = MechanismDesignTab(main_window)
    
    # Create a test path
    user_path = QPainterPath()
    user_path.moveTo(100, 100)
    user_path.lineTo(200, 150)
    user_path.lineTo(300, 100)
    user_path.lineTo(400, 200)
    
    # Load the dataset
    dataset_path = "src/automataii/kinematics/generated_mechanism_paths.json"
    try:
        with open(dataset_path, 'r') as f:
            dataset = json.load(f)
        logging.info(f"Loaded {len(dataset)} mechanisms from dataset")
    except Exception as e:
        logging.error(f"Failed to load dataset: {e}")
        return 1
    
    # Get first 4-bar linkage mechanism
    four_bar_mech = None
    for mech in dataset:
        if mech.get('type') == '4_bar_linkage':
            four_bar_mech = mech
            break
    
    if not four_bar_mech:
        logging.error("No 4-bar linkage found in dataset")
        return 1
    
    logging.info(f"Found 4-bar mechanism: {four_bar_mech.get('name')}")
    
    # Set up the main window
    main_window.setCentralWidget(tab)
    main_window.resize(1200, 800)
    main_window.show()
    
    # After a short delay, programmatically add the mechanism
    def add_mechanism():
        logging.info("Adding mechanism to tab...")
        
        # Create layer data similar to what recommendation dialog would provide
        layer_data = {
            "type": "4_bar_linkage",
            "params": four_bar_mech.get("params"),
            "generated_path": user_path,
            "full_simulation_data": four_bar_mech.get("full_simulation_data"),
            "key_points": four_bar_mech.get("key_points"),
            "transform_params": {
                "center": [0, 0],
                "scale": 1.0,
                "rotation": 0.0
            }
        }
        
        # Directly call the method to add mechanism
        tab._add_mechanism_from_json(four_bar_mech, user_path)
        
        logging.info("Mechanism added. Check if visuals are displayed.")
        
        # Start animation after adding
        QTimer.singleShot(500, lambda: tab._on_start_animation())
    
    QTimer.singleShot(1000, add_mechanism)
    
    return app.exec()

if __name__ == "__main__":
    sys.exit(test_mechanism_visuals())