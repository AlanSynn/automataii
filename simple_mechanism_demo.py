#!/usr/bin/env python
"""Simple demo to show the enhanced mechanism visualization working"""

import sys
import math
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget,
    QGraphicsView, QGraphicsScene, QSlider, QLabel, QPushButton,
    QGroupBox, QToolBar
)
from PyQt6.QtCore import Qt, QTimer, QPointF
from PyQt6.QtGui import QAction, QPen, QBrush, QColor, QPolygonF, QFont

class SimpleMechanismWidget(QGraphicsView):
    """Simplified version of the mechanism widget for demo"""
    
    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.setRenderHint(self.painter().RenderHint.Antialiasing)
        
        # Scene setup
        self.scene.setSceneRect(-300, -200, 600, 400)
        self.scene.setBackgroundBrush(QBrush(QColor(250, 250, 250)))
        
        # Mechanism parameters
        self.animation_angle = 0.0
        self.animation_speed = 2.0
        
        # Animation timer
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.update_animation)
        
        self.draw_mechanism()
    
    def draw_mechanism(self):
        """Draw a four-bar linkage"""
        self.scene.clear()
        
        # Draw grid
        self._draw_grid()
        
        # Draw four-bar mechanism
        self._draw_four_bar()
        
    def _draw_grid(self):
        """Draw simple grid"""
        pen = QPen(QColor(200, 200, 200), 1, Qt.PenStyle.DotLine)
        
        # Vertical lines
        for x in range(-300, 301, 50):
            self.scene.addLine(x, -200, x, 200, pen)
        
        # Horizontal lines
        for y in range(-200, 201, 50):
            self.scene.addLine(-300, y, 300, y, pen)
        
        # Axes
        axis_pen = QPen(QColor(100, 100, 100), 2)
        self.scene.addLine(-300, 0, 300, 0, axis_pen)
        self.scene.addLine(0, -200, 0, 200, axis_pen)
    
    def _draw_four_bar(self):
        """Draw animated four-bar linkage with forces"""
        # Parameters
        ground_link = 150
        input_link = 80
        coupler_link = 120
        output_link = 100
        
        # Joint positions
        O1 = QPointF(-ground_link/2, 0)
        O4 = QPointF(ground_link/2, 0)
        
        # Input angle
        input_angle = math.radians(self.animation_angle)
        
        # Moving joint A
        A = QPointF(
            O1.x() + input_link * math.cos(input_angle),
            O1.y() + input_link * math.sin(input_angle)
        )
        
        # Simple output calculation
        output_angle = -input_angle * 0.7 + math.radians(30)
        B = QPointF(
            O4.x() + output_link * math.cos(output_angle),
            O4.y() + output_link * math.sin(output_angle)
        )
        
        # Draw links with different colors for stress
        self._draw_link(O1, A, QColor(255, 100, 100))  # Red (compression)
        self._draw_link(A, B, QColor(100, 100, 255))   # Blue (tension)
        self._draw_link(B, O4, QColor(100, 200, 100))  # Green (normal)
        
        # Draw joints
        self._draw_joint(O1, "O1", fixed=True)
        self._draw_joint(O4, "O4", fixed=True)
        self._draw_joint(A, "A", fixed=False)
        self._draw_joint(B, "B", fixed=False)
        
        # Draw force vectors
        self._draw_force_vector(A, 40, math.radians(90))
        self._draw_force_vector(O1, 30, math.radians(45))
        self._draw_force_vector(O4, 35, math.radians(135))
    
    def _draw_link(self, start, end, color):
        """Draw a mechanism link"""
        # Main line
        pen = QPen(color.darker(120), 4)
        self.scene.addLine(start.x(), start.y(), end.x(), end.y(), pen)
        
        # Create link body
        angle = math.atan2(end.y() - start.y(), end.x() - start.x())
        width = 8
        
        perp_x = -math.sin(angle) * width / 2
        perp_y = math.cos(angle) * width / 2
        
        polygon = QPolygonF([
            QPointF(start.x() + perp_x, start.y() + perp_y),
            QPointF(start.x() - perp_x, start.y() - perp_y),
            QPointF(end.x() - perp_x, end.y() - perp_y),
            QPointF(end.x() + perp_x, end.y() + perp_y)
        ])
        
        brush = QBrush(color.lighter(150))
        pen = QPen(color, 1)
        self.scene.addPolygon(polygon, pen, brush)
    
    def _draw_joint(self, position, label, fixed=False):
        """Draw a joint"""
        size = 16 if fixed else 12
        color = QColor(105, 105, 105) if fixed else QColor(220, 20, 60)
        
        # Joint circle
        brush = QBrush(color)
        pen = QPen(color.darker(120), 2)
        self.scene.addEllipse(
            position.x() - size/2, position.y() - size/2, 
            size, size, pen, brush
        )
        
        # Label
        text = self.scene.addText(label, QFont("Arial", 10))
        text.setPos(position.x() + size/2 + 5, position.y() - 10)
        text.setDefaultTextColor(QColor(60, 60, 60))
    
    def _draw_force_vector(self, position, magnitude, angle):
        """Draw force vector"""
        scale = 2.0
        end_x = position.x() + magnitude * math.cos(angle) * scale
        end_y = position.y() + magnitude * math.sin(angle) * scale
        end_point = QPointF(end_x, end_y)
        
        # Vector line
        pen = QPen(QColor(255, 69, 0, 200), 3)
        self.scene.addLine(position.x(), position.y(), end_x, end_y, pen)
        
        # Arrowhead
        arrow_length = 12
        arrow_angle = 0.4
        
        arrow_p1 = QPointF(
            end_x - arrow_length * math.cos(angle - arrow_angle),
            end_y - arrow_length * math.sin(angle - arrow_angle)
        )
        arrow_p2 = QPointF(
            end_x - arrow_length * math.cos(angle + arrow_angle),
            end_y - arrow_length * math.sin(angle + arrow_angle)
        )
        
        arrow_polygon = QPolygonF([end_point, arrow_p1, arrow_p2])
        brush = QBrush(QColor(255, 69, 0, 200))
        pen = QPen(QColor(255, 69, 0, 200))
        self.scene.addPolygon(arrow_polygon, pen, brush)
        
        # Force label
        text = self.scene.addText(f"F={magnitude:.0f}N", QFont("Arial", 8, QFont.Weight.Bold))
        text.setPos((position.x() + end_x) / 2 + 10, (position.y() + end_y) / 2 - 10)
        text.setDefaultTextColor(QColor(255, 69, 0, 200))
    
    def update_animation(self):
        """Update animation"""
        self.animation_angle += self.animation_speed
        if self.animation_angle >= 360:
            self.animation_angle = 0
        self.draw_mechanism()
    
    def start_animation(self):
        """Start animation"""
        self.animation_timer.start(33)  # ~30 FPS
    
    def stop_animation(self):
        """Stop animation"""
        self.animation_timer.stop()


class MechanismDemo(QMainWindow):
    """Demo window showing the mechanism visualization"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Enhanced Mechanism Visualization Demo")
        self.setGeometry(100, 100, 1000, 700)
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        
        # Layout
        layout = QHBoxLayout(central)
        
        # Mechanism widget
        self.mechanism_widget = SimpleMechanismWidget()
        layout.addWidget(self.mechanism_widget, 3)
        
        # Control panel
        controls = self._create_controls()
        layout.addWidget(controls, 1)
        
        # Start with animation
        self.mechanism_widget.start_animation()
    
    def _create_controls(self):
        """Create control panel"""
        panel = QGroupBox("Controls")
        layout = QVBoxLayout(panel)
        
        # Play/Stop button
        self.play_btn = QPushButton("⏸ Pause")
        self.play_btn.clicked.connect(self._toggle_animation)
        layout.addWidget(self.play_btn)
        
        # Speed control
        layout.addWidget(QLabel("Animation Speed:"))
        speed_slider = QSlider(Qt.Orientation.Horizontal)
        speed_slider.setRange(1, 10)
        speed_slider.setValue(2)
        speed_slider.valueChanged.connect(self._on_speed_changed)
        layout.addWidget(speed_slider)
        
        # Info
        info = QLabel("""
Features Demonstrated:
• Real-time force visualization
• Color-coded stress in links
• Professional grid system
• Animated mechanism motion
• Interactive controls
• Engineering annotations

Red links = Compression
Blue links = Tension  
Green links = Normal
Orange arrows = Forces
        """)
        info.setStyleSheet("color: #666; font-size: 12px;")
        info.setWordWrap(True)
        layout.addWidget(info)
        
        layout.addStretch()
        return panel
    
    def _toggle_animation(self):
        """Toggle animation"""
        if self.mechanism_widget.animation_timer.isActive():
            self.mechanism_widget.stop_animation()
            self.play_btn.setText("▶ Play")
        else:
            self.mechanism_widget.start_animation()
            self.play_btn.setText("⏸ Pause")
    
    def _on_speed_changed(self, value):
        """Change animation speed"""
        self.mechanism_widget.animation_speed = value


def main():
    app = QApplication(sys.argv)
    
    demo = MechanismDemo()
    demo.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()