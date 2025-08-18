#!/usr/bin/env python
"""Final test for bend direction functionality"""

import sys
import logging
from PyQt6.QtWidgets import QApplication
from automataii.gui.main_window import MainWindow

# Set up logging to see bend direction messages
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)

def main():
    app = QApplication(sys.argv)
    
    # Create and show main window
    main_window = MainWindow()
    main_window.show()
    
    print("\n" + "="*80)
    print("BEND DIRECTION TEST - FINAL VERSION")
    print("="*80)
    print("\nExpected behavior:")
    print("1. In Editor tab, click on elbow/knee joints")
    print("   - Blue circle = normal bend (direction = 1.0)")
    print("   - Green circle = inverted bend (direction = -1.0)")
    print("   - Arrow shows bend direction")
    print("\n2. When you click Play:")
    print("   - Two-bone IK: 'IK: Using bend_direction X.X for middle joint'")
    print("   - FABRIK IK: 'IK: Passing bend direction to FABRIK'")
    print("   - FABRIK solver: 'FABRIK: Received bend_directions'")
    print("\n3. The animation should respect the bend direction:")
    print("   - Normal: elbow/knee bends naturally")
    print("   - Inverted: elbow/knee bends opposite way")
    print("="*80)
    print("\nWatch the console output for bend direction messages...")
    print("Press Ctrl+C to exit\n")
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()