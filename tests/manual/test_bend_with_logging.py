#!/usr/bin/env python
"""Test bend direction with detailed logging"""

import sys
import time
import logging
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from automataii.presentation.qt.main_window import MainWindow

# Set up detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: [%(name)s] %(message)s'
)

def main():
    app = QApplication(sys.argv)
    
    # Create main window
    main_window = MainWindow()
    main_window.show()
    
    print("\n" + "="*80)
    print("BEND DIRECTION TEST - Watch for these log messages:")
    print("="*80)
    print("1. When you click a joint: 'Joint ... bend direction changed to ...'")
    print("2. When animation runs: 'IK: Passing bend direction to FABRIK: ...'")
    print("3. In FABRIK solver: 'Bend hint for ... set with direction ...'")
    print("\nSteps:")
    print("1. Go to Editor tab")
    print("2. Click on elbow/knee joints (blue = normal, green = inverted)")
    print("3. Press Play to see animation")
    print("4. Watch console for bend direction messages")
    print("="*80 + "\n")
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()