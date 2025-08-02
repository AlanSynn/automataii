#!/usr/bin/env python3
"""
Test skeleton IK in the actual application context.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QPainter, QColor, QPen

from automataii.ui.views.editor.view import EditorView
from automataii.models.skeleton import StandardizedSkeletonModel

class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Skeleton IK Test - Bone Length Preservation")
        self.setGeometry(100, 100, 800, 600)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # Add instruction label
        label = QLabel("Click and drag joints to test IK. Bone lengths should remain constant.")
        label.setStyleSheet("QLabel { font-size: 14px; padding: 10px; background-color: #f0f0f0; }")
        layout.addWidget(label)
        
        # Create editor view
        self.editor_view = EditorView(mechanism_mode=False)
        layout.addWidget(self.editor_view)
        
        # Load a simple skeleton
        self.load_test_skeleton()
        
    def load_test_skeleton(self):
        """Load a simple test skeleton"""
        # Create a simple human-like skeleton
        skeleton_data = {
            "format_version": "2.0",
            "skeleton": {
                "body": {
                    "name": "body", 
                    "id": "body",
                    "position": [400, 200],
                    "children": ["left_arm", "right_arm", "left_leg", "right_leg"]
                },
                "left_arm": {
                    "name": "left_arm",
                    "id": "left_arm", 
                    "position": [350, 200],
                    "parent": "body",
                    "children": ["left_forearm"]
                },
                "left_forearm": {
                    "name": "left_forearm",
                    "id": "left_forearm",
                    "position": [300, 250],
                    "parent": "left_arm",
                    "children": ["left_hand"]
                },
                "left_hand": {
                    "name": "left_hand",
                    "id": "left_hand",
                    "position": [280, 300],
                    "parent": "left_forearm"
                },
                "right_arm": {
                    "name": "right_arm",
                    "id": "right_arm",
                    "position": [450, 200],
                    "parent": "body",
                    "children": ["right_forearm"]
                },
                "right_forearm": {
                    "name": "right_forearm",
                    "id": "right_forearm",
                    "position": [500, 250],
                    "parent": "right_arm",
                    "children": ["right_hand"]
                },
                "right_hand": {
                    "name": "right_hand",
                    "id": "right_hand",
                    "position": [520, 300],
                    "parent": "right_forearm"
                },
                "left_leg": {
                    "name": "left_leg",
                    "id": "left_leg",
                    "position": [380, 300],
                    "parent": "body",
                    "children": ["left_shin"]
                },
                "left_shin": {
                    "name": "left_shin",
                    "id": "left_shin",
                    "position": [370, 400],
                    "parent": "left_leg",
                    "children": ["left_foot"]
                },
                "left_foot": {
                    "name": "left_foot",
                    "id": "left_foot",
                    "position": [365, 480],
                    "parent": "left_shin"
                },
                "right_leg": {
                    "name": "right_leg",
                    "id": "right_leg",
                    "position": [420, 300],
                    "parent": "body",
                    "children": ["right_shin"]
                },
                "right_shin": {
                    "name": "right_shin",
                    "id": "right_shin",
                    "position": [430, 400],
                    "parent": "right_leg",
                    "children": ["right_foot"]
                },
                "right_foot": {
                    "name": "right_foot",
                    "id": "right_foot",
                    "position": [435, 480],
                    "parent": "right_shin"
                }
            }
        }
        
        # Create skeleton model
        skeleton = StandardizedSkeletonModel.from_v2_dict(skeleton_data)
        
        # Set skeleton in editor
        from automataii.services.skeleton_manager import SkeletonManager
        skeleton_manager = SkeletonManager()
        skeleton_manager.set_skeleton(skeleton)
        
        # Trigger skeleton data preservation
        from automataii.core.event_bus import EventBus
        from automataii.core.types import Event
        
        class SkeletonDataChangedEvent(Event):
            def __init__(self, skeleton_data):
                super().__init__()
                self.skeleton_data = skeleton_data
        
        event_bus = EventBus()
        event_bus.publish(SkeletonDataChangedEvent(skeleton.to_dict()))
        
        print("✅ Test skeleton loaded")
        print("🎯 Try dragging the hand or foot joints to see FABRIK in action")
        print("📏 Bone lengths should remain constant during IK solving")

def main():
    app = QApplication(sys.argv)
    
    window = TestWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()