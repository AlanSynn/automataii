"""Reusable test fixtures and helpers for E2E tests."""

import os
import tempfile
import shutil
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List
from unittest.mock import MagicMock

import pytest
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt, QPoint, QPointF, QTimer
from PyQt6.QtGui import QImage, QPainter, QColor, QPainterPath
from PyQt6.QtTest import QTest

from automataii.gui.main_window.main_window import AutomataDesigner
from automataii.processing.animation.parts_extraction.models import PartInfo


class TestImageGenerator:
    """Helper class to generate test images and data."""
    
    @staticmethod
    def create_test_character_image(width: int = 400, height: int = 600) -> Tuple[str, QImage]:
        """Create a test character image with distinct body parts."""
        image = QImage(width, height, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.white)
        
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw a simple character with distinct parts
        # Head (circle)
        painter.setBrush(QColor(255, 200, 150))  # Skin color
        painter.drawEllipse(QPoint(width//2, height//4), 80, 80)
        
        # Body (rectangle)
        painter.setBrush(QColor(100, 150, 200))  # Blue shirt
        painter.drawRect(width//2 - 60, height//4 + 80, 120, 150)
        
        # Arms (rectangles)
        painter.setBrush(QColor(255, 200, 150))  # Skin color
        painter.drawRect(width//2 - 100, height//4 + 100, 40, 100)  # Left arm
        painter.drawRect(width//2 + 60, height//4 + 100, 40, 100)   # Right arm
        
        # Legs (rectangles)
        painter.setBrush(QColor(50, 50, 50))  # Dark pants
        painter.drawRect(width//2 - 50, height//4 + 230, 40, 120)  # Left leg
        painter.drawRect(width//2 + 10, height//4 + 230, 40, 120)   # Right leg
        
        painter.end()
        
        # Save to temporary file
        temp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        image.save(temp_file.name)
        
        return temp_file.name, image
    
    @staticmethod
    def create_test_skeleton_data() -> Dict[str, Any]:
        """Create test skeleton data."""
        return {
            "joints": [
                {"name": "head", "position": [200, 150], "parent": "neck"},
                {"name": "neck", "position": [200, 200], "parent": "spine"},
                {"name": "spine", "position": [200, 300], "parent": None},
                {"name": "left_shoulder", "position": [150, 220], "parent": "spine"},
                {"name": "left_elbow", "position": [120, 280], "parent": "left_shoulder"},
                {"name": "left_hand", "position": [100, 340], "parent": "left_elbow"},
                {"name": "right_shoulder", "position": [250, 220], "parent": "spine"},
                {"name": "right_elbow", "position": [280, 280], "parent": "right_shoulder"},
                {"name": "right_hand", "position": [300, 340], "parent": "right_elbow"},
                {"name": "left_hip", "position": [180, 350], "parent": "spine"},
                {"name": "left_knee", "position": [170, 420], "parent": "left_hip"},
                {"name": "left_foot", "position": [165, 490], "parent": "left_knee"},
                {"name": "right_hip", "position": [220, 350], "parent": "spine"},
                {"name": "right_knee", "position": [230, 420], "parent": "right_hip"},
                {"name": "right_foot", "position": [235, 490], "parent": "right_knee"}
            ],
            "hierarchy": {
                "spine": ["neck", "left_shoulder", "right_shoulder", "left_hip", "right_hip"],
                "neck": ["head"],
                "left_shoulder": ["left_elbow"],
                "left_elbow": ["left_hand"],
                "right_shoulder": ["right_elbow"],
                "right_elbow": ["right_hand"],
                "left_hip": ["left_knee"],
                "left_knee": ["left_foot"],
                "right_hip": ["right_knee"],
                "right_knee": ["right_foot"]
            }
        }
    
    @staticmethod
    def create_test_parts_info() -> Dict[str, PartInfo]:
        """Create test body parts information."""
        parts = {}
        
        # Create part info for each body part
        part_data = [
            ("head", [200, 150], [160, 240]),
            ("torso", [200, 300], [300, 150]),
            ("left_arm", [100, 250], [40, 100]),
            ("right_arm", [300, 250], [40, 100]),
            ("left_leg", [170, 410], [40, 120]),
            ("right_leg", [230, 410], [40, 120])
        ]
        
        for name, center, size in part_data:
            part_info = PartInfo()
            part_info.name = name
            part_info.center = center
            part_info.size = size
            part_info.angle = 0.0
            part_info.z_index = 1
            parts[name] = part_info
            
        return parts
    
    @staticmethod
    def create_test_motion_path() -> QPainterPath:
        """Create a test motion path (circular)."""
        path = QPainterPath()
        center = QPointF(200, 300)
        radius = 50
        
        # Create circular path
        path.moveTo(center.x() + radius, center.y())
        for angle in range(0, 361, 10):
            import math
            x = center.x() + radius * math.cos(math.radians(angle))
            y = center.y() + radius * math.sin(math.radians(angle))
            path.lineTo(x, y)
        
        return path


class E2ETestBase:
    """Base class for E2E tests with common setup and utilities."""
    
    @pytest.fixture(autouse=True)
    def setup_and_teardown(self, qtbot):
        """Setup and teardown for each test."""
        self.qtbot = qtbot
        self.temp_dir = tempfile.mkdtemp()
        self.test_images = []
        self.main_window = None
        
        yield
        
        # Cleanup
        if self.main_window:
            self.main_window.close()
        
        for image_path in self.test_images:
            if os.path.exists(image_path):
                os.remove(image_path)
        
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def create_main_window(self, debug_mode: bool = False) -> AutomataDesigner:
        """Create and return main window instance."""
        self.main_window = AutomataDesigner(debug_mode=debug_mode)
        self.qtbot.addWidget(self.main_window)
        self.main_window.show()
        self.qtbot.waitExposed(self.main_window)
        return self.main_window
    
    def click_button(self, button_text: str, tab_widget=None):
        """Click a button with given text."""
        if tab_widget:
            button = self._find_button_in_widget(tab_widget, button_text)
        else:
            button = self._find_button_in_widget(self.main_window, button_text)
        
        if button and button.isEnabled():
            self.qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
            return True
        return False
    
    def _find_button_in_widget(self, widget, text: str):
        """Recursively find button with given text."""
        from PyQt6.QtWidgets import QPushButton
        
        for child in widget.findChildren(QPushButton):
            if text in child.text():
                return child
        return None
    
    def simulate_canvas_drawing(self, view, points: List[QPointF]):
        """Simulate drawing on canvas by clicking and dragging."""
        if not points:
            return
        
        # Mouse press at first point
        first_point = view.mapFromScene(points[0])
        self.qtbot.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=first_point)
        
        # Mouse move through intermediate points
        for point in points[1:-1]:
            viewport_point = view.mapFromScene(point)
            self.qtbot.mouseMove(view.viewport(), pos=viewport_point)
            QTest.qWait(10)  # Small delay for realistic drawing
        
        # Mouse release at last point
        last_point = view.mapFromScene(points[-1])
        self.qtbot.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=last_point)
    
    def simulate_canvas_click(self, view, scene_pos: QPointF, button=Qt.MouseButton.LeftButton):
        """Simulate a click on the canvas at given scene position."""
        viewport_pos = view.mapFromScene(scene_pos)
        self.qtbot.mouseClick(view.viewport(), button, pos=viewport_pos)
    
    def wait_for_processing(self, timeout: int = 5000):
        """Wait for processing to complete with timeout."""
        def check_processing():
            status_text = self.main_window.statusBar().currentMessage()
            return "processing" not in status_text.lower()
        
        self.qtbot.waitUntil(check_processing, timeout=timeout)
    
    def verify_file_exists(self, file_path: str, timeout: int = 5000) -> bool:
        """Verify that a file exists within timeout."""
        def check_file():
            return os.path.exists(file_path)
        
        try:
            self.qtbot.waitUntil(check_file, timeout=timeout)
            return True
        except:
            return False
    
    def get_current_tab(self):
        """Get the currently active tab widget."""
        if hasattr(self.main_window, 'tab_manager'):
            return self.main_window.tab_manager.get_current_tab()
        return None
    
    def switch_to_tab(self, tab_name: str):
        """Switch to a specific tab by name."""
        tab_map = {
            "landing": 0,
            "image_processing": 1,
            "editor": 2,
            "mechanism": 3,
            "designer": 4,
            "options": 5
        }
        
        if tab_name.lower() in tab_map:
            index = tab_map[tab_name.lower()]
            if hasattr(self.main_window, 'tab_widget'):
                self.main_window.tab_widget.setCurrentIndex(index)
                QTest.qWait(100)  # Wait for tab switch
                return True
        return False
    
    def mock_message_box(self, button=QMessageBox.StandardButton.Ok):
        """Mock QMessageBox to automatically click specified button."""
        original_exec = QMessageBox.exec
        
        def mock_exec(self):
            return button
        
        QMessageBox.exec = mock_exec
        return original_exec
    
    def restore_message_box(self, original_exec):
        """Restore original QMessageBox.exec."""
        QMessageBox.exec = original_exec
    
    def get_scene_items_by_type(self, scene, item_type):
        """Get all items of a specific type from a scene."""
        return [item for item in scene.items() if isinstance(item, item_type)]
    
    def count_visible_items(self, scene):
        """Count visible items in a scene."""
        return sum(1 for item in scene.items() if item.isVisible())
    
    def verify_mechanism_animation(self, view, duration: int = 2000) -> bool:
        """Verify that mechanism animation is running."""
        initial_transforms = {}
        
        # Get initial positions of mechanism items
        for item in view.scene().items():
            if hasattr(item, 'mechanism_id'):
                initial_transforms[item] = (item.pos(), item.rotation())
        
        # Wait for animation
        QTest.qWait(duration)
        
        # Check if any items moved
        moved = False
        for item, (initial_pos, initial_rot) in initial_transforms.items():
            if item.pos() != initial_pos or item.rotation() != initial_rot:
                moved = True
                break
        
        return moved
    
    def create_test_project_file(self) -> str:
        """Create a test project file."""
        project_data = {
            "version": "1.0",
            "created": "2024-01-01",
            "character_data": {
                "texture_path": "test_character.png",
                "parts": TestImageGenerator.create_test_parts_info(),
                "skeleton": TestImageGenerator.create_test_skeleton_data()
            },
            "mechanisms": []
        }
        
        project_path = os.path.join(self.temp_dir, "test_project.json")
        import json
        with open(project_path, 'w') as f:
            json.dump(project_data, f)
        
        return project_path


class MockProcessingService:
    """Mock service for image processing to speed up tests."""
    
    def __init__(self):
        self.process_called = False
        self.last_image_path = None
    
    def process_image(self, image_path: str) -> Dict[str, Any]:
        """Mock image processing."""
        self.process_called = True
        self.last_image_path = image_path
        
        # Return mock annotation results
        output_dir = tempfile.mkdtemp()
        return {
            "output_dir": output_dir,
            "texture_path": image_path,
            "char_cfg_path": self._create_mock_config(output_dir),
            "skeleton": TestImageGenerator.create_test_skeleton_data()
        }
    
    def _create_mock_config(self, output_dir: str) -> str:
        """Create mock character config file."""
        config_path = os.path.join(output_dir, "character.cfg")
        config_data = {
            "skeleton": TestImageGenerator.create_test_skeleton_data(),
            "parts": {}
        }
        
        import json
        with open(config_path, 'w') as f:
            json.dump(config_data, f)
        
        return config_path