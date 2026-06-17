#!/usr/bin/env python
"""Debug test for bend direction"""

import logging
import sys

from PyQt6.QtWidgets import QApplication

from automataii.presentation.qt.main_window import MainWindow

# Set up detailed logging
logging.basicConfig(level=logging.INFO, format="%(message)s")


def main():
    app = QApplication(sys.argv)

    # Create and show main window
    main_window = MainWindow()
    main_window.show()

    print("\n" + "=" * 80)
    print("BEND DIRECTION DEBUG TEST")
    print("=" * 80)
    print("\nWatching for:")
    print("1. 'IKManager: Updated bend_direction' - when joints are stored")
    print("2. 'IK: Looking for bend_direction' - when two-bone IK searches for bend")
    print("3. 'IK: Using bend_direction' or 'IK: No bend_direction found'")
    print("\nSteps:")
    print("1. Go to Editor tab")
    print("2. Click on an elbow joint to change bend direction")
    print("3. Press Play")
    print("4. Watch the console output")
    print("=" * 80 + "\n")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
