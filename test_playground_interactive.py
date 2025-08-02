#!/usr/bin/env python3
"""
Interactive test for playground functionality.
Opens the playground panel and tests parameter changes.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from PyQt6.QtCore import QTimer

from automataii.ui.tabs.mechanism_foundry.panels.playground_panel import PlaygroundPanel

class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Playground Parameter Test")
        self.setGeometry(100, 100, 1200, 800)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # Create playground panel
        self.playground = PlaygroundPanel()
        layout.addWidget(self.playground)
        
        # Auto-test timer
        self.test_timer = QTimer()
        self.test_timer.timeout.connect(self.run_parameter_test)
        self.test_timer.setSingleShot(True)
        self.test_timer.start(2000)  # Wait 2 seconds then test
        
    def run_parameter_test(self):
        """Test parameter updates"""
        print("\n🧪 Starting interactive parameter test...")
        
        # Get current parameter values
        all_values = self.playground.parameter_controls.get_all_values()
        print(f"Current parameters: {all_values}")
        
        # Try to update a parameter through the playground
        if hasattr(self.playground.parameter_controls, 'groups'):
            for group_name, group in self.playground.parameter_controls.groups.items():
                print(f"Group: {group_name}")
                for param_name, param_widget in group.parameters.items():
                    current_value = param_widget.get_value()
                    print(f"  {param_name}: {current_value}")
                    
                    # Try to change the first parameter slightly
                    if param_name:
                        new_value = current_value * 1.1  # Increase by 10%
                        param_widget.set_value(new_value)
                        print(f"  → Changed {param_name} to {new_value}")
                        break
                break

def main():
    app = QApplication(sys.argv)
    
    window = TestWindow()
    window.show()
    
    print("🚀 Playground test window opened")
    print("📋 Try changing parameters in the right panel")
    print("🎮 Check if animation works and parameters update correctly")
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()