#!/usr/bin/env python3
"""
Test motion path transfer from Editor tab to Mechanism Design tab
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

from automataii.ui.main_window import AutomataDesigner as MainWindow

def test_motion_path_transfer():
    app = QApplication(sys.argv)
    
    # Create main window
    window = MainWindow(experiment_mode=True, debug_mode=True)
    window.show()
    
    print("🎯 Test Instructions:")
    print("1. Load an example image from Landing tab")
    print("2. Process the image in Image Processing tab")
    print("3. Go to Editor tab")
    print("4. Select a part (e.g., left arm)")
    print("5. Click 'Define Motion Path' and draw a path")
    print("6. Complete the path (right-click or release mouse)")
    print("7. Switch to Mechanism Design tab")
    print("8. Check if the motion path is visible")
    print("\n📝 Watch console for debug messages about path transfer")
    
    sys.exit(app.exec())

if __name__ == "__main__":
    test_motion_path_transfer()