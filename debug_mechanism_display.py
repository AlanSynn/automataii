#!/usr/bin/env python3
"""
Debug script to diagnose why mechanisms are not displaying visually.
"""

import sys
import json
import logging
from PyQt6.QtWidgets import QApplication, QGraphicsScene, QGraphicsView, QVBoxLayout, QWidget, QPushButton
from PyQt6.QtCore import QPointF, QTimer
from PyQt6.QtGui import QPen, QBrush, QColor

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class DebugMechanismView(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mechanism Debug View")
        self.setGeometry(100, 100, 800, 600)
        
        # Create scene and view
        self.scene = QGraphicsScene()
        self.scene.setSceneRect(-400, -300, 800, 600)
        self.view = QGraphicsView(self.scene)
        
        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.view)
        
        # Button to test mechanism creation
        btn = QPushButton("Test Create 4-Bar Linkage")
        btn.clicked.connect(self.test_create_linkage)
        layout.addWidget(btn)
        
        self.setLayout(layout)
        
    def test_create_linkage(self):
        """Create a simple 4-bar linkage visualization for testing"""
        logger.info("Creating test 4-bar linkage...")
        
        # Clear scene
        self.scene.clear()
        
        # Define test points (ground pivots and moving joints)
        p1 = QPointF(0, 0)      # Ground pivot 1
        p2 = QPointF(100, 0)    # Ground pivot 2  
        p3 = QPointF(30, 50)    # Crank end
        p4 = QPointF(80, 60)    # Rocker end
        
        # Draw ground pivots (fixed points)
        pivot_pen = QPen(QColor("#2c3e50"), 2)
        pivot_brush = QBrush(QColor("#34495e"))
        
        pivot1 = self.scene.addEllipse(p1.x()-5, p1.y()-5, 10, 10, pivot_pen, pivot_brush)
        pivot2 = self.scene.addEllipse(p2.x()-5, p2.y()-5, 10, 10, pivot_pen, pivot_brush)
        
        # Draw links
        link_pen = QPen(QColor("#e74c3c"), 4)  # Red for driver
        driver = self.scene.addLine(p1.x(), p1.y(), p3.x(), p3.y(), link_pen)
        
        link_pen = QPen(QColor("#f39c12"), 4)  # Orange for rocker
        rocker = self.scene.addLine(p2.x(), p2.y(), p4.x(), p4.y(), link_pen)
        
        link_pen = QPen(QColor("#2ecc71"), 4)  # Green for coupler
        coupler = self.scene.addLine(p3.x(), p3.y(), p4.x(), p4.y(), link_pen)
        
        # Draw joint points
        joint_pen = QPen(QColor("#3498db"), 2)
        joint_brush = QBrush(QColor("#3498db"))
        
        joint3 = self.scene.addEllipse(p3.x()-4, p3.y()-4, 8, 8, joint_pen, joint_brush)
        joint4 = self.scene.addEllipse(p4.x()-4, p4.y()-4, 8, 8, joint_pen, joint_brush)
        
        # Add coupler point (red marker)
        coupler_point = QPointF((p3.x() + p4.x())/2, (p3.y() + p4.y())/2 - 20)
        coupler_marker = self.scene.addEllipse(
            coupler_point.x()-6, coupler_point.y()-6, 12, 12,
            QPen(QColor("#cc0000"), 2), QBrush(QColor("#ff0000"))
        )
        
        logger.info(f"Created mechanism with {len(self.scene.items())} items")
        logger.info(f"Scene bounds: {self.scene.itemsBoundingRect()}")
        
        # Test animation
        self.angle = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self.animate_mechanism)
        self.timer.start(16)  # 60 FPS
        
    def animate_mechanism(self):
        """Simple animation test"""
        self.angle += 0.05
        # Update positions based on angle
        # (simplified - not proper kinematics)
        import math
        
        # Update crank position
        p1 = QPointF(0, 0)
        p3_x = p1.x() + 50 * math.cos(self.angle)
        p3_y = p1.y() + 50 * math.sin(self.angle)
        
        # Find the first line item (driver) and update it
        for item in self.scene.items():
            if hasattr(item, 'line'):
                line = item.line()
                if abs(line.x1()) < 1 and abs(line.y1()) < 1:  # This is the driver
                    item.setLine(p1.x(), p1.y(), p3_x, p3_y)
                    break

def main():
    app = QApplication(sys.argv)
    window = DebugMechanismView()
    window.show()
    
    # Also load and print mechanism data structure
    try:
        with open("src/automataii/domain/kinematics/generated_mechanism_paths.json", 'r') as f:
            data = json.load(f)
            logger.info(f"Loaded {len(data)} mechanisms from JSON")
            if data:
                first = data[0]
                logger.info(f"First mechanism type: {first.get('type')}")
                logger.info(f"Has full_simulation_data: {'full_simulation_data' in first}")
                if 'full_simulation_data' in first:
                    sim_data = first['full_simulation_data']
                    logger.info(f"Simulation data keys: {list(sim_data.keys())}")
    except Exception as e:
        logger.error(f"Failed to load mechanism data: {e}")
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()