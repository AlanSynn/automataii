#!/usr/bin/env python
"""
Test script for the experimental joint connection system.
"""

import sys
import numpy as np
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QHBoxLayout, QLabel, QSlider
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap, QPainter, QColor

from automataii.processing.animation.joint_connection_system import (
    JointConnectionRenderer, 
    ConnectionType,
    JointConnectionAnalyzer
)
from automataii.processing.animation.joint_visual_effects import JointVisualEffects


class JointConnectionDemo(QMainWindow):
    """Demo window for testing joint connection system."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Joint Connection System Demo")
        self.setGeometry(100, 100, 800, 600)
        
        # Initialize renderer
        self.renderer = JointConnectionRenderer(enabled=True)
        
        # Create test data
        self.create_test_data()
        
        # Setup UI
        self.setup_ui()
        
        # Animation timer
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.animate)
        self.animation_phase = 0.0
        
    def create_test_data(self):
        """Create test skeleton and parts data."""
        # Simple skeleton with torso, head, and arm
        self.skeleton_data = {
            'joints': {
                'root': {'position': (400, 400), 'parent_id': None, 'name': 'root'},
                'neck': {'position': (400, 300), 'parent_id': 'root', 'name': 'neck'},
                'shoulder': {'position': (350, 320), 'parent_id': 'root', 'name': 'shoulder'},
                'elbow': {'position': (300, 370), 'parent_id': 'shoulder', 'name': 'elbow'},
            },
            'hierarchy': {
                'root': ['neck', 'shoulder'],
                'shoulder': ['elbow'],
                'neck': [],
                'elbow': []
            },
            'root_joint_ids': ['root']
        }
        
        # Parts info
        self.parts_info = {
            'torso': {
                'anchor_joint_id': 'root',
                'position': (350, 350),
                'size': (100, 150)
            },
            'head': {
                'anchor_joint_id': 'neck',
                'position': (375, 250),
                'size': (50, 60)
            },
            'upper_arm': {
                'anchor_joint_id': 'shoulder',
                'position': (325, 320),
                'size': (30, 80)
            },
            'forearm': {
                'anchor_joint_id': 'elbow',
                'position': (285, 370),
                'size': (25, 70)
            }
        }
        
        # Create part images
        self.parts_data = {}
        for name, info in self.parts_info.items():
            # Create simple colored rectangle as part image
            width, height = info['size']
            image = np.zeros((height, width, 4), dtype=np.uint8)
            
            # Different colors for different parts
            if name == 'torso':
                color = (100, 100, 200, 255)  # Blue
            elif name == 'head':
                color = (200, 100, 100, 255)  # Red
            elif name == 'upper_arm':
                color = (100, 200, 100, 255)  # Green
            else:
                color = (200, 200, 100, 255)  # Yellow
                
            image[:, :] = color
            
            self.parts_data[name] = {
                'image': image,
                'position': info['position'],
                'rotation': 0,
                'scale': 1.0
            }
        
        # Analyze connections
        self.renderer.analyze_and_setup(self.skeleton_data, self.parts_info)
        
    def setup_ui(self):
        """Setup the user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # Display area
        self.display_label = QLabel()
        self.display_label.setMinimumHeight(400)
        self.display_label.setStyleSheet("border: 1px solid black; background-color: white;")
        layout.addWidget(self.display_label)
        
        # Controls
        controls_layout = QHBoxLayout()
        
        # Connection type selector
        self.type_button = QPushButton("Type: Mesh Deform")
        self.type_button.clicked.connect(self.toggle_connection_type)
        controls_layout.addWidget(self.type_button)
        
        # Stiffness slider
        controls_layout.addWidget(QLabel("Stiffness:"))
        self.stiffness_slider = QSlider(Qt.Orientation.Horizontal)
        self.stiffness_slider.setRange(10, 100)
        self.stiffness_slider.setValue(70)
        self.stiffness_slider.valueChanged.connect(self.update_stiffness)
        controls_layout.addWidget(self.stiffness_slider)
        
        # Animation button
        self.animate_button = QPushButton("Start Animation")
        self.animate_button.clicked.connect(self.toggle_animation)
        controls_layout.addWidget(self.animate_button)
        
        # Debug visualization
        self.debug_button = QPushButton("Show Debug")
        self.debug_button.setCheckable(True)
        self.debug_button.clicked.connect(self.update_display)
        controls_layout.addWidget(self.debug_button)
        
        layout.addLayout(controls_layout)
        
        # Initial display
        self.update_display()
        
    def toggle_connection_type(self):
        """Toggle through connection types."""
        current_type = self.renderer.connections[0].connection_type if self.renderer.connections else ConnectionType.MESH_DEFORM
        
        types = list(ConnectionType)
        current_index = types.index(current_type)
        next_index = (current_index + 1) % len(types)
        next_type = types[next_index]
        
        # Update all connections
        for connection in self.renderer.connections:
            connection.connection_type = next_type
            
        self.type_button.setText(f"Type: {next_type.value.replace('_', ' ').title()}")
        self.update_display()
        
    def update_stiffness(self, value):
        """Update connection stiffness."""
        stiffness = value / 100.0
        for connection in self.renderer.connections:
            connection.stiffness = stiffness
        self.update_display()
        
    def toggle_animation(self):
        """Start or stop animation."""
        if self.animation_timer.isActive():
            self.animation_timer.stop()
            self.animate_button.setText("Start Animation")
        else:
            self.animation_timer.start(50)  # 20 FPS
            self.animate_button.setText("Stop Animation")
            
    def animate(self):
        """Animate the parts."""
        # Simple sine wave animation for arm movement
        self.animation_phase += 0.1
        
        # Update forearm position
        base_x, base_y = self.parts_info['forearm']['position']
        offset = np.sin(self.animation_phase) * 30
        self.parts_data['forearm']['position'] = (base_x + offset, base_y)
        
        # Update upper arm rotation
        self.parts_data['upper_arm']['rotation'] = np.sin(self.animation_phase) * 15
        
        self.update_display()
        
    def update_display(self):
        """Update the display with rendered parts."""
        # Create canvas
        canvas = QPixmap(800, 600)
        canvas.fill(QColor(240, 240, 240))
        
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Render parts with joint connections
        rendered_parts = self.renderer.render_connected_parts(self.parts_data)
        
        # Draw each part
        for name, image in rendered_parts.items():
            pos = self.parts_data[name]['position']
            rotation = self.parts_data[name]['rotation']
            
            # Convert numpy array to QPixmap
            height, width = image.shape[:2]
            bytes_per_line = 4 * width
            qimage = QImage(image.data, width, height, bytes_per_line, QImage.Format.Format_RGBA8888)
            part_pixmap = QPixmap.fromImage(qimage)
            
            # Draw with rotation
            painter.save()
            painter.translate(pos[0], pos[1])
            painter.rotate(rotation)
            painter.drawPixmap(-width//2, -height//2, part_pixmap)
            painter.restore()
            
        # Draw joint effects
        for connection in self.renderer.connections:
            # Draw glow effect at joint
            glow = JointVisualEffects.create_glow_effect(
                QPointF(*connection.joint_position),
                20.0,
                QColor(255, 255, 0, 128),
                0.6
            )
            painter.drawPixmap(
                int(connection.joint_position[0] - glow.width()//2),
                int(connection.joint_position[1] - glow.height()//2),
                glow
            )
            
        # Draw debug info if enabled
        if self.debug_button.isChecked():
            painter.setPen(QColor(255, 0, 0))
            
            # Draw skeleton
            for joint_id, joint in self.skeleton_data['joints'].items():
                painter.drawEllipse(
                    int(joint['position'][0] - 3),
                    int(joint['position'][1] - 3),
                    6, 6
                )
                painter.drawText(
                    int(joint['position'][0] + 5),
                    int(joint['position'][1] - 5),
                    joint_id
                )
                
            # Draw connections
            painter.setPen(QColor(0, 255, 0))
            for connection in self.renderer.connections:
                painter.drawText(
                    int(connection.joint_position[0] - 30),
                    int(connection.joint_position[1] + 20),
                    f"{connection.part1_name}-{connection.part2_name}"
                )
                
        painter.end()
        
        # Display
        self.display_label.setPixmap(canvas.scaled(
            self.display_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        ))


def main():
    """Run the demo."""
    app = QApplication(sys.argv)
    
    demo = JointConnectionDemo()
    demo.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()