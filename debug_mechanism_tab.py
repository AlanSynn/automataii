#!/usr/bin/env python
"""Debug script to verify mechanism rendering"""

import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton
from PyQt6.QtCore import QTimer
from automataii.ui.tabs.mechanism_foundry.enhanced_macanism_tab import (
    EnhancedMacanismTab, 
    InteractiveMechanismWidget
)

def debug_widget():
    """Test just the mechanism widget"""
    app = QApplication(sys.argv)
    
    # Test the mechanism widget directly
    widget = InteractiveMechanismWidget()
    widget.setWindowTitle("Direct Mechanism Widget Test")
    widget.resize(800, 600)
    widget.show()
    
    # Try to draw the mechanism
    print("Drawing mechanism...")
    widget.draw_mechanism()
    
    # Check scene contents
    scene = widget.scene
    print(f"Scene rect: {scene.sceneRect()}")
    print(f"Scene items count: {len(scene.items())}")
    
    # List all items
    for i, item in enumerate(scene.items()[:10]):  # First 10 items
        print(f"  Item {i}: {type(item).__name__} at {item.pos() if hasattr(item, 'pos') else 'N/A'}")
    
    # Start animation to see if it updates
    def start_animation():
        print("Starting animation...")
        widget.start_animation()
    
    QTimer.singleShot(1000, start_animation)
    
    sys.exit(app.exec())

if __name__ == "__main__":
    debug_widget()