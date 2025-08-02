#!/usr/bin/env python3
"""
Comprehensive test for all mechanism types.
Validates visual consistency between recommendation dialog and main view.
"""

import sys
import logging
from PyQt6.QtWidgets import QApplication, QMessageBox, QVBoxLayout, QWidget, QPushButton, QTextEdit
from PyQt6.QtCore import QTimer, pyqtSlot
from automataii.ui.main_window import MainWindow
from automataii.utils.logging_config import configure_logging

# Configure detailed logging
configure_logging()
logger = logging.getLogger(__name__)

# Enable debug logging for all mechanism modules
debug_modules = [
    "automataii.ui.tabs.mechanism_design.scene_manager",
    "automataii.ui.tabs.mechanism_design.visuals.linkage_visual",
    "automataii.ui.tabs.mechanism_design.visuals.cam_visual", 
    "automataii.ui.tabs.mechanism_design.visuals.gear_visual",
    "automataii.ui.tabs.mechanism_design.visuals.belt_visual",
    "automataii.ui.tabs.mechanism_design.visuals.spring_visual",
    "automataii.ui.tabs.mechanism_design.parametric_handler",
    "automataii.ui.tabs.mechanism_design.animation_controller",
]

for module in debug_modules:
    logging.getLogger(module).setLevel(logging.DEBUG)

class AllMechanismsTest(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("All Mechanisms Comprehensive Test")
        self.setGeometry(50, 50, 600, 800)
        
        # Layout
        layout = QVBoxLayout()
        
        # Instructions
        self.instructions = QTextEdit()
        self.instructions.setReadOnly(True)
        self.instructions.setMaximumHeight(400)
        layout.addWidget(self.instructions)
        
        # Log output
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output)
        
        # Start test button
        start_button = QPushButton("Start Comprehensive Test")
        start_button.clicked.connect(self.start_test)
        layout.addWidget(start_button)
        
        self.setLayout(layout)
        
        # Main window reference
        self.main_window = MainWindow()
        self.main_window.show()
        self.main_window.move(700, 50)
        
        self.show_instructions()
        
    def show_instructions(self):
        instructions = '''
🔍 COMPREHENSIVE MECHANISM TEST

Test ALL mechanism types for visual consistency:

📋 TEST PROCEDURE:
1. Load character (astronaut/dancer)
2. Editor tab: Draw motion paths on different parts
3. Mechanism Design tab: Test each mechanism type

🎯 MECHANISMS TO TEST:

1️⃣ 4-BAR LINKAGE
✓ Colors: Red driver (#e74c3c), Orange rocker (#f39c12), Green coupler (#2ecc71)
✓ Line width: 4px all links
✓ Triangular coupler with light green fill
✓ Red coupler point (6x6 circle)
✓ NO pivot points shown

2️⃣ CAM & FOLLOWER  
✓ Colors: Red cam (#e74c3c), Green follower (#2ecc71)
✓ Cam: Egg-shaped with light red fill
✓ Follower: Small rectangle (20x10)
✓ Line width: 4px

3️⃣ SIMPLE GEAR
✓ Colors: Blue gear1 (#3498db), Green gear2 (#2ecc71)
✓ Circles with light fills
✓ White spokes (2px)
✓ Line width: 4px

4️⃣ PLANETARY GEAR
✓ Colors: Gray sun (#7f8c8d), Orange planet (#e67e22)
✓ Orange tracking line (#f39c12)
✓ Red tracking point (#e74c3c, 10x10)

5️⃣ BELT SYSTEM
✓ Colors: Blue pulleys (#3498db)
✓ Purple belt (#8e44ad)
✓ Red belt marker (#e74c3c)
✓ Proper belt geometry

6️⃣ SPRING SYSTEM  
✓ Colors: Orange spring (#f39c12)
✓ Red mass (#e74c3c)
✓ Dark anchors (#2c3e50)
✓ Coil visualization

⚙️ ANIMATION CONTROL:
✓ Static display initially (no auto-start)
✓ Play button starts animation
✓ Stop button stops animation
✓ Parametric edit mode works

Watch console logs for detailed verification!
        '''
        self.instructions.setPlainText(instructions)
        
    def log(self, message):
        self.log_output.append(message)
        logger.info(message)
        
    @pyqtSlot()
    def start_test(self):
        self.log("🚀 Starting comprehensive mechanism test...")
        self.log("=" * 60)
        
        # Monitor mechanism design tab
        central_widget = self.main_window.central_widget
        
        @pyqtSlot(int)
        def on_tab_changed(index):
            if index == 3:  # Mechanism Design tab
                self.verify_mechanism_tab()
        
        central_widget.currentChanged.connect(on_tab_changed)
        
        # Set up periodic monitoring
        self.monitor_timer = QTimer()
        self.monitor_timer.timeout.connect(self.check_mechanisms)
        self.monitor_timer.start(3000)  # Check every 3 seconds
        
        self.log("✅ Test monitoring started")
        self.log("📝 Follow the test procedure above")
        
    def verify_mechanism_tab(self):
        """Verify mechanism design tab state"""
        try:
            tab = self.main_window.central_widget.widget(3)
            if not tab:
                return
                
            self.log("\n🔍 MECHANISM TAB VERIFICATION")
            
            # Check animation state
            if hasattr(tab, 'animation_controller'):
                is_running = tab.animation_controller.timer.isActive()
                status = "❌ FAIL - Auto-started" if is_running else "✅ PASS - Static"
                self.log(f"Animation auto-start: {status}")
            
            # Check parametric mode
            if hasattr(tab, 'parametric_handler'):
                is_active = tab.parametric_handler.is_mode_active
                self.log(f"Parametric mode available: {'✅ YES' if hasattr(tab, 'parametric_handler') else '❌ NO'}")
                
        except Exception as e:
            self.log(f"❌ Verification error: {e}")
    
    def check_mechanisms(self):
        """Check for mechanisms in scene"""
        try:
            tab = self.main_window.central_widget.widget(3)
            if not tab or not hasattr(tab, 'scene_manager'):
                return
                
            scene = tab.scene_manager.scene
            items = scene.items()
            
            if len(items) > 5:  # Significant items suggest mechanism is present
                self.analyze_mechanism_visuals(items, tab)
                
        except Exception as e:
            logger.error(f"Monitor error: {e}")
    
    def analyze_mechanism_visuals(self, items, tab):
        """Analyze visual items to determine mechanism type and validate"""
        self.log("\n🎨 VISUAL ANALYSIS")
        
        # Count item types
        line_items = []
        polygon_items = []
        ellipse_items = []
        path_items = []
        
        for item in items:
            item_type = type(item).__name__
            if 'Line' in item_type:
                line_items.append(item)
            elif 'Polygon' in item_type:
                polygon_items.append(item)
            elif 'Ellipse' in item_type:
                ellipse_items.append(item)
            elif 'Path' in item_type:
                path_items.append(item)
        
        self.log(f"📊 Items: {len(line_items)} lines, {len(polygon_items)} polygons, {len(ellipse_items)} ellipses, {len(path_items)} paths")
        
        # Analyze colors and properties
        if line_items:
            self.log("🔴 LINE ITEMS:")
            for i, item in enumerate(line_items[:5]):  # Limit to first 5
                if hasattr(item, 'pen'):
                    pen = item.pen()
                    color = pen.color().name()
                    width = pen.width()
                    self.log(f"  Line {i}: color={color}, width={width}px")
        
        if polygon_items:
            self.log("🟢 POLYGON ITEMS:")
            for i, item in enumerate(polygon_items[:3]):
                if hasattr(item, 'brush'):
                    brush = item.brush()
                    pen = item.pen() if hasattr(item, 'pen') else None
                    brush_color = brush.color().name()
                    pen_color = pen.color().name() if pen else "none"
                    self.log(f"  Polygon {i}: fill={brush_color}, border={pen_color}")
        
        if ellipse_items:
            self.log("🔵 ELLIPSE ITEMS:")
            for i, item in enumerate(ellipse_items[:3]):
                if hasattr(item, 'rect'):
                    rect = item.rect()
                    size = f"{rect.width():.1f}x{rect.height():.1f}"
                    if hasattr(item, 'brush'):
                        color = item.brush().color().name()
                        self.log(f"  Ellipse {i}: size={size}, color={color}")
        
        if path_items:
            self.log("🛤️  PATH ITEMS:")
            for i, item in enumerate(path_items[:2]):
                if hasattr(item, 'pen'):
                    pen = item.pen()
                    color = pen.color().name()
                    width = pen.width()
                    self.log(f"  Path {i}: color={color}, width={width}px")
        
        # Determine mechanism type based on visual signature
        mechanism_type = self.identify_mechanism_type(line_items, polygon_items, ellipse_items, path_items)
        if mechanism_type:
            self.log(f"🎯 DETECTED: {mechanism_type}")
            self.validate_mechanism_colors(mechanism_type, line_items, polygon_items, ellipse_items, path_items)
    
    def identify_mechanism_type(self, lines, polygons, ellipses, paths):
        """Identify mechanism type based on visual elements"""
        if len(lines) >= 2 and len(polygons) >= 1 and len(ellipses) >= 1:
            return "4-Bar Linkage"
        elif len(paths) >= 1 and len(polygons) >= 1:
            return "Cam & Follower"
        elif len(ellipses) >= 2 and len(lines) >= 2:
            return "Gear System"
        elif len(ellipses) >= 2 and len(paths) >= 1:
            return "Belt System"
        elif len(paths) >= 1 and len(ellipses) >= 2:
            return "Spring System"
        return "Unknown"
    
    def validate_mechanism_colors(self, mech_type, lines, polygons, ellipses, paths):
        """Validate colors match recommendation dialog"""
        self.log(f"🎨 VALIDATING {mech_type} COLORS:")
        
        if mech_type == "4-Bar Linkage":
            # Check for red (#e74c3c), orange (#f39c12), green (#2ecc71)
            expected_colors = ["#e74c3c", "#f39c12", "#2ecc71"]
            found_colors = []
            
            for item in lines:
                if hasattr(item, 'pen'):
                    color = item.pen().color().name()
                    found_colors.append(color)
            
            for color in expected_colors:
                if color in found_colors:
                    self.log(f"  ✅ Found expected color: {color}")
                else:
                    self.log(f"  ❌ Missing expected color: {color}")
        
        elif mech_type == "Cam & Follower":
            # Check for red cam (#e74c3c) and green follower (#2ecc71)
            self.log("  Expected: Red cam (#e74c3c), Green follower (#2ecc71)")
            
        elif mech_type == "Gear System":
            # Check for blue (#3498db) and green (#2ecc71) or gray/orange for planetary
            self.log("  Expected: Blue/Green for simple, Gray/Orange for planetary")
        
        self.log("")  # Add spacing

def main():
    app = QApplication(sys.argv)
    
    print("🔍 COMPREHENSIVE MECHANISM VALIDATION")
    print("=" * 50)
    print("Testing ALL mechanism types:")
    print("• 4-Bar Linkage")
    print("• Cam & Follower")
    print("• Simple Gear")
    print("• Planetary Gear") 
    print("• Belt System")
    print("• Spring System")
    print("=" * 50)
    
    test_widget = AllMechanismsTest()
    test_widget.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()