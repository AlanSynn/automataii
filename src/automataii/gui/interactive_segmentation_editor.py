# Interactive Segmentation Editor for PyQt
# Lines: ~1200
# Public API: InteractiveSegmentationEditor
# Deps In (Afferent): 1 [ImageProcessingTab]
# Deps Out (Efferent): 6 [PyQt6, cv2, numpy, json, pathlib, matplotlib]
# Coupling: Medium (GUI integration, image processing, segmentation)
# Cohesion: Feature (interactive editing of body part boundaries)
# Owner: Alan Synn, Reviewers: Team
# Last Updated: 2025-01-15

import json
import sys
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PyQt6.QtCore import QPointF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QImage, QPainter, QPen, QPixmap, QPolygonF
from PyQt6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QGraphicsEllipseItem,
    QGraphicsPixmapItem,
    QGraphicsPolygonItem,
    QGraphicsScene,
    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from automataii.animate.part_definitions import BODY_PARTS


class ClickableGraphicsView(QGraphicsView):
    """Graphics view that handles mouse clicks for boundary definition"""

    point_clicked = pyqtSignal(float, float)  # x, y coordinates
    joint_clicked = pyqtSignal(str)  # joint name

    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.joint_items = {}  # joint_name -> QGraphicsEllipseItem
        self.current_boundary_points = []  # List of QPointF
        self.boundary_polygon_item = None
        self.preview_point_item = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            scene_pos = self.mapToScene(event.position().toPoint())

            # Check if clicking near a joint
            clicked_joint = self._find_joint_at_position(scene_pos)
            if clicked_joint:
                self.joint_clicked.emit(clicked_joint)
            else:
                self.point_clicked.emit(scene_pos.x(), scene_pos.y())
        elif event.button() == Qt.MouseButton.RightButton:
            # Right click to remove last point
            if self.current_boundary_points:
                self.remove_last_boundary_point()

        super().mousePressEvent(event)

    def _find_joint_at_position(self, pos: QPointF, threshold: float = 15.0) -> str | None:
        """Find joint near the clicked position"""
        for joint_name, joint_item in self.joint_items.items():
            joint_pos = joint_item.rect().center()
            distance = ((pos.x() - joint_pos.x())**2 + (pos.y() - joint_pos.y())**2)**0.5
            if distance <= threshold:
                return joint_name
        return None

    def add_joint(self, joint_name: str, x: float, y: float, selected: bool = False):
        """Add a joint marker to the view"""
        radius = 8
        color = QColor(255, 100, 100) if selected else QColor(100, 100, 255)

        joint_item = QGraphicsEllipseItem(x - radius, y - radius, radius * 2, radius * 2)
        joint_item.setBrush(QBrush(color))
        joint_item.setPen(QPen(QColor(255, 255, 255), 2))

        self.scene().addItem(joint_item)
        self.joint_items[joint_name] = joint_item

        # Add label
        label_item = self.scene().addText(joint_name, QFont("Arial", 8))
        label_item.setPos(x + radius + 2, y - radius)
        label_item.setDefaultTextColor(QColor(255, 255, 255))

    def update_joint_selection(self, joint_name: str, selected: bool):
        """Update joint visual to show selection state"""
        if joint_name in self.joint_items:
            color = QColor(255, 100, 100) if selected else QColor(100, 100, 255)
            self.joint_items[joint_name].setBrush(QBrush(color))

    def add_boundary_point(self, x: float, y: float):
        """Add a boundary point and update the polygon"""
        point = QPointF(x, y)
        self.current_boundary_points.append(point)

        # Add visual marker for the point
        marker = QGraphicsEllipseItem(x - 3, y - 3, 6, 6)
        marker.setBrush(QBrush(QColor(255, 255, 0)))
        marker.setPen(QPen(QColor(255, 255, 255), 2))
        self.scene().addItem(marker)

        # Update polygon
        self._update_boundary_polygon()

    def remove_last_boundary_point(self):
        """Remove the last added boundary point"""
        if self.current_boundary_points:
            self.current_boundary_points.pop()
            self._update_boundary_polygon()
            # Note: This is a simplified implementation
            # In a full implementation, you'd track and remove the visual markers too

    def clear_boundary_points(self):
        """Clear all boundary points for current part"""
        self.current_boundary_points.clear()
        if self.boundary_polygon_item:
            self.scene().removeItem(self.boundary_polygon_item)
            self.boundary_polygon_item = None

    def _update_boundary_polygon(self):
        """Update the visual boundary polygon"""
        if self.boundary_polygon_item:
            self.scene().removeItem(self.boundary_polygon_item)

        if len(self.current_boundary_points) >= 3:
            polygon = QPolygonF(self.current_boundary_points)
            self.boundary_polygon_item = QGraphicsPolygonItem(polygon)
            self.boundary_polygon_item.setBrush(QBrush(QColor(255, 255, 0, 100)))
            self.boundary_polygon_item.setPen(QPen(QColor(255, 255, 0), 2))
            self.scene().addItem(self.boundary_polygon_item)


    def set_boundary_points(self, points: list[tuple[float, float]]):
        """Set boundary points from list of tuples"""
        self.clear_boundary_points()
        for x, y in points:
            self.add_boundary_point(x, y)


class InteractiveSegmentationEditor(QDialog):
    """Interactive dialog for manual body part segmentation editing"""

    def __init__(self, image_path: str, skeleton_data: dict[str, Any] = None, parent=None):
        super().__init__(parent)
        self.image_path = Path(image_path)
        self.skeleton_data = skeleton_data or {}
        self.current_part = "torso"
        self.boundary_points = {}  # part_name -> list of (x, y) tuples
        self.selected_joints = set()  # Currently selected joints
        self.joint_positions = {}  # joint_name -> (x, y)
        self.segmentation_results = {}  # Final results

        # Load and process image
        print(f"Attempting to load image from: {image_path}")

        # Try different image loading approaches
        self.original_image = None

        # Method 1: Try with IMREAD_UNCHANGED first (preserves alpha channel)
        try:
            self.original_image = cv2.imread(str(image_path), cv2.IMREAD_UNCHANGED)
            if self.original_image is not None:
                print(f"Successfully loaded image with IMREAD_UNCHANGED: shape {self.original_image.shape}")
        except Exception as e:
            print(f"IMREAD_UNCHANGED failed: {e}")

        # Method 2: If that fails, try IMREAD_COLOR
        if self.original_image is None:
            try:
                self.original_image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
                if self.original_image is not None:
                    print(f"Successfully loaded image with IMREAD_COLOR: shape {self.original_image.shape}")
            except Exception as e:
                print(f"IMREAD_COLOR failed: {e}")

        # Method 3: If that fails, try using PIL as fallback
        if self.original_image is None:
            try:
                import numpy as np
                from PIL import Image

                pil_image = Image.open(str(image_path))
                print(f"PIL loaded image: mode={pil_image.mode}, size={pil_image.size}")

                # Convert PIL to OpenCV format
                if pil_image.mode == 'RGBA':
                    self.original_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGBA2BGRA)
                elif pil_image.mode == 'RGB':
                    self.original_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
                elif pil_image.mode == 'L':
                    self.original_image = np.array(pil_image)
                else:
                    # Convert to RGB first
                    rgb_image = pil_image.convert('RGB')
                    self.original_image = cv2.cvtColor(np.array(rgb_image), cv2.COLOR_RGB2BGR)

                if self.original_image is not None:
                    print(f"Successfully loaded image with PIL fallback: shape {self.original_image.shape}")

            except Exception as e:
                print(f"PIL fallback failed: {e}")

        if self.original_image is None:
            raise ValueError(f"Could not load image from any method: {image_path}")

        self.height, self.width = self.original_image.shape[:2]
        print(f"Final image dimensions: {self.width}x{self.height}")

        # Initialize boundary points for all parts
        for part_name in BODY_PARTS.keys():
            self.boundary_points[part_name] = []

        # Extract joint positions
        self._extract_joint_positions()

        # Setup UI
        self.setWindowTitle("Manual Segmentation Editor")
        self.setMinimumSize(900, 600)
        self.resize(1200, 700)

        self._init_ui()
        self._load_image()
        self._draw_skeleton()

        # Auto-save timer
        self.auto_save_timer = QTimer()
        self.auto_save_timer.timeout.connect(self._auto_save_boundaries)
        self.auto_save_timer.start(30000)  # Auto-save every 30 seconds

    def _extract_joint_positions(self):
        """Extract joint positions from skeleton data"""
        if 'joints' in self.skeleton_data:
            joints = self.skeleton_data['joints']
            if isinstance(joints, dict):
                for joint_id, joint_data in joints.items():
                    if isinstance(joint_data, dict) and 'position' in joint_data:
                        pos = joint_data['position']
                        if len(pos) >= 2:
                            joint_name = '_'.join(joint_id.split('_')[:-1])
                            if not joint_name:
                                joint_name = joint_id.split('_')[0]
                            self.joint_positions[joint_name] = (float(pos[0]), float(pos[1]))

        elif 'skeleton' in self.skeleton_data:
            skeleton = self.skeleton_data['skeleton']
            if isinstance(skeleton, list):
                for joint_data in skeleton:
                    if isinstance(joint_data, dict):
                        name = joint_data.get('name', '')
                        loc = joint_data.get('loc', [0, 0])
                        if name and len(loc) >= 2:
                            self.joint_positions[name] = (float(loc[0]), float(loc[1]))

        # If no skeleton data, create default positions based on image size
        if not self.joint_positions:
            self.joint_positions = self._create_default_joint_positions()

    def _create_default_joint_positions(self) -> dict[str, tuple[float, float]]:
        """Create default joint positions based on image dimensions"""
        return {
            'head_top': (self.width // 2, int(self.height * 0.05)),
            'neck': (self.width // 2, int(self.height * 0.12)),
            'torso': (self.width // 2, int(self.height * 0.25)),
            'pelvis': (self.width // 2, int(self.height * 0.45)),
            'left_shoulder': (int(self.width * 0.35), int(self.height * 0.18)),
            'right_shoulder': (int(self.width * 0.65), int(self.height * 0.18)),
            'left_elbow': (int(self.width * 0.20), int(self.height * 0.30)),
            'right_elbow': (int(self.width * 0.80), int(self.height * 0.30)),
            'left_wrist': (int(self.width * 0.15), int(self.height * 0.42)),
            'right_wrist': (int(self.width * 0.85), int(self.height * 0.42)),
            'left_hip': (int(self.width * 0.42), int(self.height * 0.45)),
            'right_hip': (int(self.width * 0.58), int(self.height * 0.45)),
            'left_knee': (int(self.width * 0.40), int(self.height * 0.65)),
            'right_knee': (int(self.width * 0.60), int(self.height * 0.65)),
            'left_ankle': (int(self.width * 0.38), int(self.height * 0.85)),
            'right_ankle': (int(self.width * 0.62), int(self.height * 0.85)),
        }

    def _init_ui(self):
        """Initialize the user interface"""
        layout = QHBoxLayout(self)

        # Left panel for controls
        left_panel = self._create_left_panel()
        layout.addWidget(left_panel)

        # Right panel for image view
        right_panel = self._create_right_panel()
        layout.addWidget(right_panel, 1)  # Give more space to image view

        self.setLayout(layout)

    def _create_left_panel(self) -> QWidget:
        """Create left control panel"""
        panel = QWidget()
        panel.setMinimumWidth(280)
        panel.setMaximumWidth(350)
        layout = QVBoxLayout(panel)

        # Part selection
        parts_group = QGroupBox("Select Body Part")
        parts_layout = QVBoxLayout(parts_group)

        self.part_buttons = QButtonGroup()
        for i, part_name in enumerate(BODY_PARTS.keys()):
            radio_btn = QRadioButton(part_name.replace('_', ' ').title())
            radio_btn.setObjectName(part_name)
            if i == 0:  # Select first part by default
                radio_btn.setChecked(True)
            self.part_buttons.addButton(radio_btn, i)
            parts_layout.addWidget(radio_btn)

        self.part_buttons.buttonClicked.connect(self._on_part_selected)
        layout.addWidget(parts_group)

        # Action buttons
        actions_group = QGroupBox("Actions")
        actions_layout = QVBoxLayout(actions_group)

        self.clear_btn = QPushButton("Clear Current Part")
        self.clear_btn.clicked.connect(self._clear_current_part)
        actions_layout.addWidget(self.clear_btn)

        self.preview_btn = QPushButton("Preview Segmentation")
        self.preview_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)
        self.preview_btn.clicked.connect(self._preview_segmentation)
        actions_layout.addWidget(self.preview_btn)

        self.save_btn = QPushButton("Save Boundaries")
        self.save_btn.clicked.connect(self._save_boundaries)
        actions_layout.addWidget(self.save_btn)

        self.load_btn = QPushButton("Load Boundaries")
        self.load_btn.clicked.connect(self._load_boundaries)
        actions_layout.addWidget(self.load_btn)

        layout.addWidget(actions_group)

        # Progress and status
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Ready to edit")
        self.status_label.setStyleSheet("color: #6c757d; font-size: 10pt;")
        layout.addWidget(self.status_label)

        layout.addStretch()

        # Final buttons
        button_layout = QHBoxLayout()

        self.apply_btn = QPushButton("Apply Segmentation")
        self.apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #198754;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 12px;
                font-weight: bold;
                font-size: 11pt;
            }
            QPushButton:hover {
                background-color: #157347;
            }
        """)
        self.apply_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.apply_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        layout.addLayout(button_layout)

        return panel

    def _create_right_panel(self) -> QWidget:
        """Create right image panel"""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Image view
        self.scene = QGraphicsScene()
        self.view = ClickableGraphicsView(self.scene)
        self.view.point_clicked.connect(self._on_point_clicked)
        self.view.joint_clicked.connect(self._on_joint_clicked)

        layout.addWidget(self.view)

        return panel

    def _load_image(self):
        """Load image into the graphics view"""
        print(f"Loading image: {self.image_path}")
        print(f"Image shape: {self.original_image.shape}")
        print(f"Image type: {self.original_image.dtype}")

        # Convert OpenCV image (BGR) to RGB for proper Qt display
        if len(self.original_image.shape) == 3:
            if self.original_image.shape[2] == 4:  # BGRA
                # Convert BGRA to RGBA
                rgb_image = cv2.cvtColor(self.original_image, cv2.COLOR_BGRA2RGBA)
                height, width, channel = rgb_image.shape
                bytes_per_line = 4 * width
                q_image = QImage(rgb_image.data, width, height, bytes_per_line, QImage.Format.Format_RGBA8888)
            else:  # BGR
                # Convert BGR to RGB
                rgb_image = cv2.cvtColor(self.original_image, cv2.COLOR_BGR2RGB)
                height, width, channel = rgb_image.shape
                bytes_per_line = 3 * width
                q_image = QImage(rgb_image.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
        else:
            # Grayscale image
            height, width = self.original_image.shape
            bytes_per_line = width
            q_image = QImage(self.original_image.data, width, height, bytes_per_line, QImage.Format.Format_Grayscale8)

        pixmap = QPixmap.fromImage(q_image)
        print(f"Pixmap created: {pixmap.width()}x{pixmap.height()}")

        # Add to scene
        self.pixmap_item = QGraphicsPixmapItem(pixmap)
        self.scene.addItem(self.pixmap_item)

        # Set scene rect to match image size
        self.scene.setSceneRect(0, 0, pixmap.width(), pixmap.height())

        # Fit image in view
        self.view.fitInView(self.pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)

        print("Image loaded successfully into view")

    def _draw_skeleton(self):
        """Draw skeleton joints on the image"""
        for joint_name, (x, y) in self.joint_positions.items():
            self.view.add_joint(joint_name, x, y, joint_name in self.selected_joints)

    def _on_part_selected(self, button):
        """Handle part selection"""
        self.current_part = button.objectName()

        # Update view with current part's boundary points
        if self.current_part in self.boundary_points:
            self.view.set_boundary_points(self.boundary_points[self.current_part])
        else:
            self.view.clear_boundary_points()

    def _on_point_clicked(self, x: float, y: float):
        """Handle point click on image"""
        self.view.add_boundary_point(x, y)

        # Update stored boundary points
        if self.current_part not in self.boundary_points:
            self.boundary_points[self.current_part] = []
        self.boundary_points[self.current_part].append((x, y))

        self.status_label.setText(f"Added boundary point ({x:.1f}, {y:.1f}) to {self.current_part}")

    def _on_joint_clicked(self, joint_name: str):
        """Handle joint click"""
        if joint_name in self.selected_joints:
            self.selected_joints.remove(joint_name)
            self.status_label.setText(f"Deselected joint: {joint_name}")
        else:
            self.selected_joints.add(joint_name)
            self.status_label.setText(f"Selected joint: {joint_name}")

        self.view.update_joint_selection(joint_name, joint_name in self.selected_joints)

    def _clear_current_part(self):
        """Clear boundary points for current part"""
        if self.current_part in self.boundary_points:
            self.boundary_points[self.current_part] = []

        self.view.clear_boundary_points()
        self.selected_joints.clear()

        # Update joint visuals
        for joint_name in self.joint_positions:
            self.view.update_joint_selection(joint_name, False)

        self.status_label.setText(f"Cleared {self.current_part}")


    def _preview_segmentation(self):
        """Generate and show segmentation preview"""
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        self.status_label.setText("Generating preview...")

        try:
            # Generate segmentation preview
            preview_results = self._generate_segmentation_preview()

            if preview_results:
                # Show preview (simplified - in full implementation you'd show in a separate dialog)
                parts_with_data = [name for name, data in preview_results.items() if data is not None]
                self.status_label.setText(f"Preview generated: {len(parts_with_data)} parts defined")
            else:
                self.status_label.setText("No boundary points defined yet")

        except Exception as e:
            QMessageBox.warning(self, "Preview Error", f"Error generating preview: {e}")
            self.status_label.setText("Preview generation failed")

        finally:
            self.progress_bar.setVisible(False)

    def _generate_segmentation_preview(self) -> dict[str, np.ndarray]:
        """Generate segmentation masks from current boundary definitions"""
        results = {}

        for part_name in BODY_PARTS.keys():
            boundary_points = self.boundary_points.get(part_name, [])

            if len(boundary_points) >= 3:
                # Create mask from polygon
                mask = np.zeros((self.height, self.width), dtype=np.uint8)
                points = np.array(boundary_points, dtype=np.int32)
                cv2.fillPoly(mask, [points], 255)
                results[part_name] = mask
            else:
                results[part_name] = None

        return results

    def _save_boundaries(self):
        """Save current boundary definitions"""
        save_path = self.image_path.parent / "manual_segmentation_boundaries.json"

        save_data = {
            'image_path': str(self.image_path),
            'boundary_points': self.boundary_points,
            'joint_positions': self.joint_positions,
            'selected_joints': list(self.selected_joints)
        }

        try:
            with open(save_path, 'w') as f:
                json.dump(save_data, f, indent=4)
            self.status_label.setText(f"Boundaries saved to {save_path.name}")
        except Exception as e:
            QMessageBox.warning(self, "Save Error", f"Error saving boundaries: {e}")

    def _load_boundaries(self):
        """Load boundary definitions"""
        load_path = self.image_path.parent / "manual_segmentation_boundaries.json"

        if not load_path.exists():
            QMessageBox.information(self, "No File", f"No boundary file found at {load_path}")
            return

        try:
            with open(load_path) as f:
                load_data = json.load(f)

            self.boundary_points = load_data.get('boundary_points', {})
            if 'selected_joints' in load_data:
                self.selected_joints = set(load_data['selected_joints'])

            # Update current view
            if self.current_part in self.boundary_points:
                self.view.set_boundary_points(self.boundary_points[self.current_part])

            # Update joint selections
            for joint_name in self.joint_positions:
                self.view.update_joint_selection(joint_name, joint_name in self.selected_joints)

            self._update_info_labels()
            self.status_label.setText(f"Boundaries loaded from {load_path.name}")

        except Exception as e:
            QMessageBox.warning(self, "Load Error", f"Error loading boundaries: {e}")

    def _auto_save_boundaries(self):
        """Auto-save boundaries periodically"""
        try:
            auto_save_path = self.image_path.parent / "auto_save_boundaries.json"
            save_data = {
                'timestamp': str(QTimer().remainingTime()),
                'boundary_points': self.boundary_points,
                'selected_joints': list(self.selected_joints)
            }
            with open(auto_save_path, 'w') as f:
                json.dump(save_data, f, indent=4)
        except:
            pass  # Ignore auto-save errors

    def get_segmentation_results(self) -> dict[str, np.ndarray]:
        """Get final segmentation results"""
        if not hasattr(self, '_final_results'):
            self._final_results = self._generate_segmentation_preview()
        return self._final_results

    def accept(self):
        """Handle accept button - generate final results"""
        try:
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)
            self.status_label.setText("Generating final segmentation...")

            self._final_results = self._generate_segmentation_preview()

            parts_with_data = [name for name, data in self._final_results.items() if data is not None]
            if not parts_with_data:
                reply = QMessageBox.question(
                    self, "No Boundaries",
                    "No boundary points have been defined. Do you want to continue anyway?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return

            super().accept()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error generating final segmentation: {e}")
        finally:
            self.progress_bar.setVisible(False)

    def closeEvent(self, event):
        """Handle dialog close"""
        # Stop auto-save timer
        if hasattr(self, 'auto_save_timer'):
            self.auto_save_timer.stop()

        # Check if there are unsaved changes
        has_changes = any(len(points) > 0 for points in self.boundary_points.values())

        if has_changes:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "You have unsaved boundary definitions. Do you want to save them before closing?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save
            )

            if reply == QMessageBox.StandardButton.Save:
                self._save_boundaries()
                event.accept()
            elif reply == QMessageBox.StandardButton.Discard:
                event.accept()
            else:  # Cancel
                event.ignore()
                return

        event.accept()


# For testing
if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # Test with a sample image
    dialog = InteractiveSegmentationEditor("test_image.png")
    result = dialog.exec()

    if result == QDialog.DialogCode.Accepted:
        results = dialog.get_segmentation_results()
        print(f"Segmentation completed with {len([r for r in results.values() if r is not None])} parts")
    else:
        print("Segmentation cancelled")

    app.quit()
