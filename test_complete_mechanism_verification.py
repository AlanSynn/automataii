#!/usr/bin/env python3
"""
Complete verification test for mechanism visualization system.
Tests:
1. Visual style matches recommendation dialog exactly
2. Animation only starts when Play is pressed
3. Parametric edit mode works correctly
4. 4-bar linkage triangular coupler displays properly
"""

import sys
import logging
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import QTimer, pyqtSlot
from automataii.ui.main_window import MainWindow
from automataii.utils.logging_config import configure_logging

# Configure detailed logging
configure_logging()
logger = logging.getLogger(__name__)

# Enable debug logging for critical modules
debug_modules = [
    "automataii.ui.tabs.mechanism_design.scene_manager",
    "automataii.ui.tabs.mechanism_design.visuals.linkage_visual",
    "automataii.ui.tabs.mechanism_design.parametric_handler",
    "automataii.ui.tabs.mechanism_design.animation_controller",
]

for module in debug_modules:
    logging.getLogger(module).setLevel(logging.DEBUG)

class MechanismVerificationTest:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.window = MainWindow()
        self.window.show()
        
        # Test results
        self.test_results = []
        
        # Setup test timer
        QTimer.singleShot(1000, self.show_test_instructions)
        
    def show_test_instructions(self):
        """Show test instructions to user"""
        instructions = """
Complete Mechanism Verification Test

Please follow these steps exactly:

1. Load a character (e.g., astronaut)
2. Go to Editor tab and draw a motion path on a part
3. Go to Mechanism Design tab
4. Select the part with motion path from left panel
5. Click 'Get Mechanism' button
6. In the recommendation dialog:
   - Note the visual appearance (colors, shapes)
   - Select a 4-bar linkage mechanism
   - Click OK

Then verify:
✓ Mechanism appears with EXACT same visual style as dialog
✓ Animation is NOT running (mechanism is static)
✓ Press Play button - mechanism should animate
✓ Press Stop button - animation should stop
✓ Enable Parametric Edit mode
✓ Drag handles to modify mechanism parameters
✓ Triangular coupler should be visible (green triangle)
✓ Red coupler point marker should be visible

Watch the console for detailed logs.
        """
        
        msg = QMessageBox()
        msg.setWindowTitle("Mechanism Verification Test")
        msg.setText(instructions)
        msg.setIcon(QMessageBox.Icon.Information)
        msg.exec()
        
        # Monitor mechanism design tab
        self.setup_monitoring()
        
    def setup_monitoring(self):
        """Setup monitoring of mechanism design tab"""
        # Get reference to central widget
        central_widget = self.window.central_widget
        
        @pyqtSlot(int)
        def on_tab_changed(index):
            if index == 3:  # Mechanism Design tab
                self.verify_mechanism_tab()
        
        central_widget.currentChanged.connect(on_tab_changed)
        
    def verify_mechanism_tab(self):
        """Verify mechanism design tab state"""
        try:
            tab = self.window.central_widget.widget(3)
            if not tab:
                return
                
            logger.info("\n=== Mechanism Design Tab Verification ===")
            
            # Check animation controller state
            if hasattr(tab, 'animation_controller'):
                is_running = tab.animation_controller.timer.isActive()
                logger.info(f"Animation running: {is_running}")
                self.test_results.append(f"Animation auto-start: {'FAIL' if is_running else 'PASS'}")
            
            # Check scene items
            if hasattr(tab, 'scene_manager'):
                scene = tab.scene_manager.scene
                items = scene.items()
                logger.info(f"Scene items count: {len(items)}")
                
                # Count item types
                line_items = 0
                polygon_items = 0
                ellipse_items = 0
                
                for item in items:
                    item_type = type(item).__name__
                    if 'Line' in item_type:
                        line_items += 1
                        # Log line details
                        if hasattr(item, 'pen'):
                            pen = item.pen()
                            logger.info(f"  Line: color={pen.color().name()}, width={pen.width()}")
                    elif 'Polygon' in item_type:
                        polygon_items += 1
                        if hasattr(item, 'brush'):
                            brush = item.brush()
                            logger.info(f"  Polygon: brush color={brush.color().name()}")
                    elif 'Ellipse' in item_type:
                        ellipse_items += 1
                        if hasattr(item, 'rect'):
                            rect = item.rect()
                            logger.info(f"  Ellipse: size=({rect.width():.1f}x{rect.height():.1f})")
                
                logger.info(f"Item counts - Lines: {line_items}, Polygons: {polygon_items}, Ellipses: {ellipse_items}")
                
            # Check parametric mode
            if hasattr(tab, 'parametric_handler'):
                is_active = tab.parametric_handler.is_mode_active
                logger.info(f"Parametric mode active: {is_active}")
                
            logger.info("=== End Verification ===\n")
            
        except Exception as e:
            logger.error(f"Verification error: {e}")
    
    def run(self):
        """Run the test application"""
        # Add periodic verification
        timer = QTimer()
        timer.timeout.connect(self.verify_mechanism_tab)
        timer.start(5000)  # Check every 5 seconds
        
        return self.app.exec()

def main():
    print("Starting Complete Mechanism Verification Test...")
    print("="*60)
    print("Expected behavior:")
    print("1. Mechanism visuals match recommendation dialog exactly:")
    print("   - Red driver link (width: 4)")
    print("   - Orange rocker link (width: 4)")  
    print("   - Green triangular coupler (pen: 2, filled)")
    print("   - Red coupler point (6x6 circle)")
    print("   - NO pivot point markers")
    print("2. Animation does NOT auto-start")
    print("3. Parametric edit mode allows handle dragging")
    print("="*60)
    
    test = MechanismVerificationTest()
    sys.exit(test.run())

if __name__ == "__main__":
    main()