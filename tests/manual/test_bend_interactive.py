#!/usr/bin/env python
"""Interactive test for bend direction changes"""

import sys
import time
from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QLabel
from PyQt6.QtCore import QTimer
from automataii.presentation.qt.main_window import MainWindow
import logging

logging.basicConfig(level=logging.INFO)

def main():
    app = QApplication(sys.argv)
    
    # Create main window
    main_window = MainWindow()
    main_window.show()
    
    print("\n" + "="*60)
    print("BEND DIRECTION TEST INSTRUCTIONS:")
    print("="*60)
    print("1. Load an image (astronaut is loaded by default)")
    print("2. Go to Editor tab")
    print("3. Click on any elbow/knee joint (they will change color)")
    print("   - Blue = normal bend direction (1.0)")
    print("   - Green = inverted bend direction (-1.0)")
    print("4. Press Play to see animation with new bend directions")
    print("5. Watch console for 'IK: Using bend_direction' messages")
    print("="*60 + "\n")
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()