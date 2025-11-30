#!/usr/bin/env python3
"""
Visual test for MechanismFoundryView
Run with: uv run python test_foundry_view_visual.py
"""
import sys
from PyQt6.QtWidgets import QApplication, QMainWindow
from automataii.presentation.qt.tabs.mechanism_foundry.foundry_view import MechanismFoundryView


def main():
    app = QApplication(sys.argv)
    
    window = QMainWindow()
    window.setWindowTitle("Mechanism Foundry View Test")
    window.setGeometry(100, 100, 1200, 800)
    
    view = MechanismFoundryView()
    window.setCentralWidget(view)
    
    window.show()
    
    print("=" * 60)
    print("Mechanism Foundry View Visual Test")
    print("=" * 60)
    print(f"Mechanisms available: {view.mechanism_selector.count()}")
    print(f"Current mechanism: {view.current_mechanism.mechanism_type}")
    print(f"Parameters: {list(view.current_parameters.keys())}")
    print(f"Scene items: {len(view.scene.items())}")
    print("\nTest the following:")
    print("  1. Switch mechanisms using dropdown")
    print("  2. Adjust parameter sliders")
    print("  3. Click Play to animate")
    print("  4. Use angle slider to control position")
    print("=" * 60)
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
