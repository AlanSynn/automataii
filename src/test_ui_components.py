#!/usr/bin/env python3
"""
Test UI components without launching the full application
"""

import sys
import os
import logging

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

print("🧪 Testing Automataii UI Components\n")

# Test 1: PyQt6 availability and basic setup
print("1. Testing PyQt6 setup...")
try:
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget
    from PyQt6.QtGui import QPixmap, QPainter
    
    # Create a minimal application instance (required for many Qt operations)
    app = QApplication(sys.argv)
    print("   ✅ PyQt6 imports successful")
    print("   ✅ QApplication created")
except Exception as e:
    print(f"   ❌ PyQt6 setup error: {e}")
    sys.exit(1)

# Test 2: Graphics items
print("\n2. Testing graphics items...")
try:
    from automataii.gui.graphics_items.skeleton_item import SkeletonGraphicsItem
    from automataii.gui.graphics_items.part_item import PartGraphicsItem
    from automataii.gui.graphics_items.anchor_item import AnchorItem
    
    print("   ✅ Graphics items imported successfully")
    
    # Try to create basic items
    from automataii.core.models.skeleton import StandardizedSkeletonModel, StandardizedJointModel
    
    # Create a test skeleton
    skeleton = StandardizedSkeletonModel()
    joint1 = StandardizedJointModel(id="j1", name="Joint 1", position=(100, 100))
    joint2 = StandardizedJointModel(id="j2", name="Joint 2", position=(200, 200), parent_id="j1")
    skeleton.joints = {"j1": joint1, "j2": joint2}
    skeleton.root_joint_ids = ["j1"]
    skeleton.hierarchy = {"j1": ["j2"]}
    
    # Create skeleton item
    skeleton_item = SkeletonGraphicsItem(skeleton)
    print(f"   ✅ Created SkeletonGraphicsItem with {len(skeleton.joints)} joints")
    
except Exception as e:
    print(f"   ❌ Graphics items error: {e}")

# Test 3: Main window components
print("\n3. Testing main window components...")
try:
    from automataii.gui.main_window.main_window import AutomataDesigner
    print("   ✅ Main window class imported")
    
    # Don't create instance as it would show the window
    print("   ℹ️  Skipping window creation to avoid display")
except Exception as e:
    print(f"   ❌ Main window import error: {e}")

# Test 4: Tabs
print("\n4. Testing tab components...")
try:
    from automataii.gui.tabs.landing_tab import LandingTab
    print("   ✅ LandingTab imported")
    
    from automataii.gui.tabs.image_processing import ImageProcessingTab
    print("   ✅ ImageProcessingTab imported")
    
    from automataii.gui.tabs.editor import EditorTabCoordinator
    print("   ✅ EditorTabCoordinator imported")
    
    from automataii.gui.tabs.designer import DesignerTab
    print("   ✅ DesignerTab imported")
    
except Exception as e:
    print(f"   ❌ Tab components error: {e}")

# Test 5: Dialogs
print("\n5. Testing dialog components...")
try:
    from automataii.gui.dialogs.recommendation import RecommendationDialog
    print("   ✅ RecommendationDialog imported")
    
    from automataii.gui.dialogs.camera_dialog import CameraDialog
    print("   ✅ CameraDialog imported")
    
except Exception as e:
    print(f"   ❌ Dialog components error: {e}")

# Test 6: Views
print("\n6. Testing view components...")
try:
    from automataii.gui.views.image_view import ImageView
    from automataii.gui.views.editor_view import EditorView
    
    # Create test views
    image_view = ImageView()
    print("   ✅ Created ImageView")
    
    editor_view = EditorView()
    print("   ✅ Created EditorView")
    
    # Test basic functionality
    test_pixmap = QPixmap(100, 100)
    test_pixmap.fill(Qt.GlobalColor.white)
    image_view.setImage(test_pixmap)
    print("   ✅ Set test image in ImageView")
    
except Exception as e:
    print(f"   ❌ View components error: {e}")

# Test 7: Services
print("\n7. Testing service components...")
try:
    from automataii.services.animation_service import AnimationService
    from automataii.services.path_drawing_service import PathDrawingService
    from automataii.services.joint_connection_manager import JointConnectionManager
    
    print("   ✅ Service components imported successfully")
    
    # Create service instances
    animation_service = AnimationService()
    print("   ✅ Created AnimationService")
    
    path_service = PathDrawingService()
    print("   ✅ Created PathDrawingService")
    
except Exception as e:
    print(f"   ❌ Service components error: {e}")

# Test 8: Styling
print("\n8. Testing styling components...")
try:
    from automataii.utils.styling import apply_theme, get_icon
    
    # Test theme application
    test_widget = QWidget()
    apply_theme(test_widget)
    print("   ✅ Applied theme to test widget")
    
    # Test icon loading
    try:
        icon = get_icon("cil-home.png")
        print("   ✅ Loaded test icon")
    except:
        print("   ⚠️  Icon loading failed (icons may not be available)")
    
except Exception as e:
    print(f"   ❌ Styling components error: {e}")

# Test 9: Event handling
print("\n9. Testing event handling...")
try:
    from PyQt6.QtCore import pyqtSignal, QObject
    
    class TestEmitter(QObject):
        test_signal = pyqtSignal(str)
    
    emitter = TestEmitter()
    received = []
    
    def test_slot(msg):
        received.append(msg)
    
    emitter.test_signal.connect(test_slot)
    emitter.test_signal.emit("test message")
    
    if received == ["test message"]:
        print("   ✅ Signal/slot mechanism working")
    else:
        print("   ❌ Signal/slot mechanism failed")
        
except Exception as e:
    print(f"   ❌ Event handling error: {e}")

# Test 10: Scene management
print("\n10. Testing scene management...")
try:
    from PyQt6.QtWidgets import QGraphicsScene, QGraphicsView
    
    scene = QGraphicsScene()
    view = QGraphicsView(scene)
    
    # Add test items
    scene.addRect(0, 0, 100, 100)
    scene.addEllipse(50, 50, 50, 50)
    
    print(f"   ✅ Created scene with {len(scene.items())} items")
    
except Exception as e:
    print(f"   ❌ Scene management error: {e}")

# Summary
print("\n" + "="*50)
print("🎯 UI component testing completed!")
print("="*50)

# Clean up
app.quit()