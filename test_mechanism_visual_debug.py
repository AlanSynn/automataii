#!/usr/bin/env python3
"""
Debug script to test mechanism visual display issue.

This script helps diagnose why mechanism visuals are not appearing after selection
from the recommendation dialog.
"""

import sys
import logging
from PyQt6.QtWidgets import QApplication
from automataii.ui.main_window import MainWindow
from automataii.utils.logging_config import configure_logging

# Configure detailed logging
configure_logging()
logger = logging.getLogger(__name__)

# Set specific loggers to DEBUG level
loggers_to_debug = [
    "automataii.ui.tabs.mechanism_design.scene_manager",
    "automataii.ui.tabs.mechanism_design.action_handler", 
    "automataii.ui.tabs.mechanism_design.state_manager",
    "automataii.ui.tabs.mechanism_design.visuals.linkage_visual",
    "automataii.ui.tabs.mechanism_design.visuals.visual_factory",
]

for logger_name in loggers_to_debug:
    logging.getLogger(logger_name).setLevel(logging.DEBUG)

def main():
    print("=== Mechanism Visual Debug Test ===")
    print("Steps to reproduce the issue:")
    print("1. Load a character (e.g., astronaut)")
    print("2. Go to Editor tab and draw a motion path on a part")
    print("3. Go to Mechanism Design tab")
    print("4. Select the part with the motion path from the left panel")
    print("5. Click 'Get Mechanism' button")
    print("6. Select a mechanism from the recommendation dialog")
    print("7. Check if the mechanism visual appears")
    print("\nWatch the console for detailed logging output...")
    print("=" * 50)
    
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    
    # Add a hook to monitor scene changes
    def on_tab_changed(index):
        if index == 3:  # Mechanism Design tab
            tab = window.central_widget.currentWidget()
            scene = tab.scene_manager.scene
            print(f"\n[DEBUG] Mechanism Design tab active. Scene items: {len(scene.items())}")
            for item in scene.items():
                print(f"  - {type(item).__name__}: visible={item.isVisible()}, z={item.zValue()}")
    
    window.central_widget.currentChanged.connect(on_tab_changed)
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()