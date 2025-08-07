#!/usr/bin/env python
"""Test script to verify the enhanced mechanism tab functionality"""

import sys
from PyQt6.QtWidgets import QApplication
from automataii.ui.tabs.mechanism_foundry.enhanced_macanism_tab import EnhancedMacanismTab

def main():
    app = QApplication(sys.argv)
    
    # Create and show the enhanced tab
    tab = EnhancedMacanismTab()
    tab.setWindowTitle("Enhanced Mechanism Tab Test")
    tab.resize(1200, 800)
    tab.show()
    
    # Draw the mechanism if widget is available
    if hasattr(tab, 'mechanism_widget') and tab.mechanism_widget:
        print("Mechanism widget found, drawing mechanism...")
        tab.mechanism_widget.draw_mechanism()
    else:
        print("Warning: Mechanism widget not found!")
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()