"""
Custom skeleton builder dialog for creating and editing non-standard skeletons.
"""

from typing import Dict, List, Optional, Tuple, Any
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QGraphicsView,
    QGraphicsScene, QGraphicsEllipseItem, QGraphicsLineItem, QListWidget,
    QListWidgetItem, QGroupBox, QLineEdit, QComboBox, QSpinBox, QCheckBox,
    QSplitter, QWidget, QMessageBox, QToolBar, QFileDialog
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QPen, QBrush, QColor, QPainter, QIcon

from automataii.core.models.skeleton import StandardizedJointModel, StandardizedSkeletonModel
from automataii.core.models.skeleton_types import SkeletonType, SkeletonTemplate, create_skeleton_from_template
from automataii.gui.graphics_items import BoneItem, JointItem


class SkeletonEditorView(QGraphicsView):
    """Graphics view for editing skeleton structure."""

    joint_selected = pyqtSignal(str)  # Emitted when a joint is selected

    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.setRenderHint(QPainter.Antialiasing)

        # Set up the view
        self.setMinimumSize(600, 400)
        self.setSceneRect(-300, -200, 600, 400)

        # Joint tracking
        self.joints: Dict[str, JointItem] = {}
        self.bones: List[BoneItem] = []
        self.selected_joint: Optional[JointItem] = None

        # Interaction modes
        self.mode = "select"  # "select", "add_joint", "add_bone"
        self.bone_start_joint: Optional[JointItem] = None

    def set_mode(self, mode: str):
        """Set the interaction mode."""
        self.mode = mode
        self.bone_start_joint = None

        # Update cursor
        if mode == "add_joint":
            self.setCursor(Qt.CrossCursor)
        elif mode == "add_bone":
            self.setCursor(Qt.PointingHandCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

    def add_joint(self, joint_id: str, x: float, y: float) -> JointItem:
        """Add a joint to the skeleton."""
        if joint_id in self.joints:
            return self.joints[joint_id]

        joint = JointItem(joint_id, x, y)
        self.scene.addItem(joint)
        self.joints[joint_id] = joint
        return joint

    def add_bone(self, start_id: str, end_id: str) -> Optional[BoneItem]:
        """Add a bone between two joints."""
        if start_id not in self.joints or end_id not in self.joints:
            return None

        # Check if bone already exists
        start_joint = self.joints[start_id]
        end_joint = self.joints[end_id]

        for bone in self.bones:
            if (bone.start_joint == start_joint and bone.end_joint == end_joint) or \
               (bone.start_joint == end_joint and bone.end_joint == start_joint):
                return bone

        bone = BoneItem(start_joint, end_joint)
        self.scene.addItem(bone)
        self.bones.append(bone)
        return bone

    def remove_joint(self, joint_id: str):
        """Remove a joint and its connections."""
        if joint_id not in self.joints:
            return

        joint = self.joints[joint_id]

        # Remove connected bones
        bones_to_remove = []
        for bone in self.bones:
            if bone.start_joint == joint or bone.end_joint == joint:
                bones_to_remove.append(bone)

        for bone in bones_to_remove:
            self.scene.removeItem(bone)
            self.bones.remove(bone)

        # Remove joint
        self.scene.removeItem(joint)
        del self.joints[joint_id]

    def clear_skeleton(self):
        """Clear all joints and bones."""
        self.scene.clear()
        self.joints.clear()
        self.bones.clear()
        self.selected_joint = None
        self.bone_start_joint = None

    def mousePressEvent(self, event):
        """Handle mouse press events."""
        if event.button() == Qt.LeftButton:
            scene_pos = self.mapToScene(event.pos())

            if self.mode == "add_joint":
                # Create new joint at click position
                joint_id = f"joint_{len(self.joints) + 1}"
                self.add_joint(joint_id, scene_pos.x(), scene_pos.y())

            elif self.mode == "add_bone":
                # Check if clicking on a joint
                item = self.scene.itemAt(scene_pos, self.transform())
                if isinstance(item, JointItem):
                    if self.bone_start_joint is None:
                        # Start bone creation
                        self.bone_start_joint = item
                        item.setBrush(QBrush(QColor(255, 150, 100)))
                    else:
                        # Complete bone creation
                        if item != self.bone_start_joint:
                            self.add_bone(self.bone_start_joint.joint_id, item.joint_id)
                        self.bone_start_joint.setBrush(QBrush(QColor(100, 150, 255)))
                        self.bone_start_joint = None

            elif self.mode == "select":
                # Handle selection
                item = self.scene.itemAt(scene_pos, self.transform())
                if isinstance(item, JointItem):
                    self.selected_joint = item
                    self.joint_selected.emit(item.joint_id)

        super().mousePressEvent(event)

    def get_skeleton_data(self) -> Dict[str, Any]:
        """Get the current skeleton structure as data."""
        joints_data = {}
        bones_data = []

        # Collect joint data
        for joint_id, joint in self.joints.items():
            pos = joint.scenePos()
            joints_data[joint_id] = {
                "position": (pos.x(), pos.y()),
                "name": joint_id  # Can be customized later
            }

        # Collect bone data
        for bone in self.bones:
            bones_data.append((
                bone.start_joint.joint_id,
                bone.end_joint.joint_id
            ))

        return {
            "joints": joints_data,
            "bones": bones_data
        }

    def load_skeleton_data(self, data: Dict[str, Any]):
        """Load skeleton structure from data."""
        self.clear_skeleton()

        # Add joints
        for joint_id, joint_data in data.get("joints", {}).items():
            x, y = joint_data["position"]
            self.add_joint(joint_id, x, y)

        # Add bones
        for start_id, end_id in data.get("bones", []):
            self.add_bone(start_id, end_id)


class CustomSkeletonDialog(QDialog):
    """Dialog for creating and editing custom skeletons."""

    skeleton_created = pyqtSignal(StandardizedSkeletonModel)

    def __init__(self, parent=None, initial_skeleton: Optional[StandardizedSkeletonModel] = None):
        super().__init__(parent)
        self.setWindowTitle("Custom Skeleton Builder")
        self.setModal(True)
        self.resize(1000, 700)

        self.initial_skeleton = initial_skeleton
        self.setup_ui()

        if initial_skeleton:
            self.load_skeleton(initial_skeleton)

    def setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # Toolbar
        toolbar = self.create_toolbar()
        layout.addWidget(toolbar)

        # Main content area
        splitter = QSplitter(Qt.Horizontal)

        # Left panel - skeleton editor
        editor_widget = QWidget()
        editor_layout = QVBoxLayout(editor_widget)

        self.editor_view = SkeletonEditorView()
        self.editor_view.joint_selected.connect(self.on_joint_selected)
        editor_layout.addWidget(self.editor_view)

        # Editor mode buttons
        mode_layout = QHBoxLayout()
        self.select_btn = QPushButton("Select")
        self.select_btn.setCheckable(True)
        self.select_btn.setChecked(True)
        self.select_btn.clicked.connect(lambda: self.set_editor_mode("select"))

        self.add_joint_btn = QPushButton("Add Joint")
        self.add_joint_btn.setCheckable(True)
        self.add_joint_btn.clicked.connect(lambda: self.set_editor_mode("add_joint"))

        self.add_bone_btn = QPushButton("Add Bone")
        self.add_bone_btn.setCheckable(True)
        self.add_bone_btn.clicked.connect(lambda: self.set_editor_mode("add_bone"))

        mode_layout.addWidget(self.select_btn)
        mode_layout.addWidget(self.add_joint_btn)
        mode_layout.addWidget(self.add_bone_btn)
        mode_layout.addStretch()
        editor_layout.addLayout(mode_layout)

        splitter.addWidget(editor_widget)

        # Right panel - properties and joint list
        right_panel = self.create_right_panel()
        splitter.addWidget(right_panel)

        splitter.setSizes([700, 300])
        layout.addWidget(splitter)

        # Dialog buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)

        self.create_btn = QPushButton("Create Skeleton")
        self.create_btn.clicked.connect(self.create_skeleton)

        button_layout.addWidget(self.cancel_btn)
        button_layout.addWidget(self.create_btn)
        layout.addLayout(button_layout)

    def create_toolbar(self) -> QToolBar:
        """Create the toolbar."""
        toolbar = QToolBar()

        # Template actions
        template_action = QAction("Load Template", self)
        template_action.triggered.connect(self.load_template)
        toolbar.addAction(template_action)

        toolbar.addSeparator()

        # File actions
        save_action = QAction("Save Skeleton", self)
        save_action.triggered.connect(self.save_skeleton)
        toolbar.addAction(save_action)

        load_action = QAction("Load Skeleton", self)
        load_action.triggered.connect(self.load_skeleton_file)
        toolbar.addAction(load_action)

        toolbar.addSeparator()

        # Edit actions
        clear_action = QAction("Clear All", self)
        clear_action.triggered.connect(self.clear_skeleton)
        toolbar.addAction(clear_action)

        return toolbar

    def create_right_panel(self) -> QWidget:
        """Create the right panel with properties and joint list."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Skeleton properties
        props_group = QGroupBox("Skeleton Properties")
        props_layout = QVBoxLayout(props_group)

        # Name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Name:"))
        self.name_edit = QLineEdit("Custom Skeleton")
        name_layout.addWidget(self.name_edit)
        props_layout.addLayout(name_layout)

        # Type
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Type:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems([t.value for t in SkeletonType])
        self.type_combo.setCurrentText(SkeletonType.CUSTOM.value)
        type_layout.addWidget(self.type_combo)
        props_layout.addLayout(type_layout)

        layout.addWidget(props_group)

        # Joint list
        joint_group = QGroupBox("Joints")
        joint_layout = QVBoxLayout(joint_group)

        self.joint_list = QListWidget()
        self.joint_list.itemSelectionChanged.connect(self.on_joint_list_selection)
        joint_layout.addWidget(self.joint_list)

        # Joint properties
        joint_props_layout = QHBoxLayout()
        joint_props_layout.addWidget(QLabel("Joint Name:"))
        self.joint_name_edit = QLineEdit()
        self.joint_name_edit.setEnabled(False)
        joint_props_layout.addWidget(self.joint_name_edit)

        self.rename_btn = QPushButton("Rename")
        self.rename_btn.setEnabled(False)
        self.rename_btn.clicked.connect(self.rename_joint)
        joint_props_layout.addWidget(self.rename_btn)

        joint_layout.addLayout(joint_props_layout)

        # Joint actions
        joint_actions_layout = QHBoxLayout()
        self.delete_joint_btn = QPushButton("Delete Joint")
        self.delete_joint_btn.setEnabled(False)
        self.delete_joint_btn.clicked.connect(self.delete_selected_joint)
        joint_actions_layout.addWidget(self.delete_joint_btn)
        joint_actions_layout.addStretch()
        joint_layout.addLayout(joint_actions_layout)

        layout.addWidget(joint_group)
        layout.addStretch()

        return widget

    def set_editor_mode(self, mode: str):
        """Set the editor interaction mode."""
        self.editor_view.set_mode(mode)

        # Update button states
        self.select_btn.setChecked(mode == "select")
        self.add_joint_btn.setChecked(mode == "add_joint")
        self.add_bone_btn.setChecked(mode == "add_bone")

    def on_joint_selected(self, joint_id: str):
        """Handle joint selection in the editor."""
        self.update_joint_list()

        # Select in list
        for i in range(self.joint_list.count()):
            item = self.joint_list.item(i)
            if item.data(Qt.UserRole) == joint_id:
                self.joint_list.setCurrentItem(item)
                break

    def on_joint_list_selection(self):
        """Handle joint selection in the list."""
        current = self.joint_list.currentItem()
        if current:
            joint_id = current.data(Qt.UserRole)
            self.joint_name_edit.setText(current.text())
            self.joint_name_edit.setEnabled(True)
            self.rename_btn.setEnabled(True)
            self.delete_joint_btn.setEnabled(True)

            # Highlight in editor
            for jid, joint in self.editor_view.joints.items():
                if jid == joint_id:
                    joint.setBrush(QBrush(QColor(255, 200, 100)))
                else:
                    joint.setBrush(QBrush(QColor(100, 150, 255)))
        else:
            self.joint_name_edit.clear()
            self.joint_name_edit.setEnabled(False)
            self.rename_btn.setEnabled(False)
            self.delete_joint_btn.setEnabled(False)

    def update_joint_list(self):
        """Update the joint list widget."""
        self.joint_list.clear()

        skeleton_data = self.editor_view.get_skeleton_data()
        for joint_id, joint_data in skeleton_data["joints"].items():
            item = QListWidgetItem(joint_data.get("name", joint_id))
            item.setData(Qt.UserRole, joint_id)
            self.joint_list.addItem(item)

    def rename_joint(self):
        """Rename the selected joint."""
        current = self.joint_list.currentItem()
        if current and self.joint_name_edit.text():
            current.setText(self.joint_name_edit.text())

    def delete_selected_joint(self):
        """Delete the selected joint."""
        current = self.joint_list.currentItem()
        if current:
            joint_id = current.data(Qt.UserRole)
            self.editor_view.remove_joint(joint_id)
            self.update_joint_list()

    def clear_skeleton(self):
        """Clear the entire skeleton."""
        reply = QMessageBox.question(
            self, "Clear Skeleton",
            "Are you sure you want to clear the entire skeleton?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.editor_view.clear_skeleton()
            self.update_joint_list()

    def load_template(self):
        """Load a skeleton template."""
        from automataii.gui.dialogs.template_selection_dialog import TemplateSelectionDialog

        dialog = TemplateSelectionDialog(self)
        if dialog.exec_():
            template = dialog.selected_template
            if template:
                # Convert template to skeleton data
                skeleton = create_skeleton_from_template(template, scale=200.0)
                self.load_skeleton(skeleton)

    def save_skeleton(self):
        """Save the skeleton to a file."""
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Skeleton", "", "JSON Files (*.json)"
        )

        if filename:
            import json
            skeleton_data = self.editor_view.get_skeleton_data()
            skeleton_data["name"] = self.name_edit.text()
            skeleton_data["type"] = self.type_combo.currentText()

            with open(filename, 'w') as f:
                json.dump(skeleton_data, f, indent=2)

    def load_skeleton_file(self):
        """Load a skeleton from a file."""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Load Skeleton", "", "JSON Files (*.json)"
        )

        if filename:
            import json
            with open(filename, 'r') as f:
                skeleton_data = json.load(f)

            self.editor_view.load_skeleton_data(skeleton_data)
            self.name_edit.setText(skeleton_data.get("name", "Custom Skeleton"))
            self.type_combo.setCurrentText(skeleton_data.get("type", SkeletonType.CUSTOM.value))
            self.update_joint_list()

    def load_skeleton(self, skeleton: StandardizedSkeletonModel):
        """Load a StandardizedSkeletonModel into the editor."""
        skeleton_data = {
            "joints": {},
            "bones": []
        }

        # Convert joints
        for joint_id, joint in skeleton.joints.items():
            skeleton_data["joints"][joint_id] = {
                "position": joint.position,
                "name": joint.name
            }

        # Convert hierarchy to bones
        for parent_id, children in skeleton.hierarchy.items():
            for child_id in children:
                skeleton_data["bones"].append((parent_id, child_id))

        self.editor_view.load_skeleton_data(skeleton_data)
        self.update_joint_list()

    def create_skeleton(self):
        """Create a StandardizedSkeletonModel from the editor data."""
        skeleton_data = self.editor_view.get_skeleton_data()

        if not skeleton_data["joints"]:
            QMessageBox.warning(self, "No Joints", "Please add at least one joint to the skeleton.")
            return

        # Build StandardizedSkeletonModel
        joints = {}
        hierarchy = {}

        # First pass: create all joints
        for joint_id, joint_data in skeleton_data["joints"].items():
            joint = StandardizedJointModel(
                id=joint_id,
                name=joint_data.get("name", joint_id),
                position=joint_data["position"],
                parent_id=None  # Will be set in second pass
            )
            joints[joint_id] = joint

        # Second pass: establish hierarchy from bones
        for start_id, end_id in skeleton_data["bones"]:
            # Assume start is parent of end (can be customized)
            joints[end_id].parent_id = start_id

            if start_id not in hierarchy:
                hierarchy[start_id] = []
            hierarchy[start_id].append(end_id)

        # Find root joints
        root_joint_ids = [
            joint_id for joint_id, joint in joints.items()
            if joint.parent_id is None
        ]

        skeleton = StandardizedSkeletonModel(
            joints=joints,
            root_joint_ids=root_joint_ids,
            hierarchy=hierarchy,
            source_format="custom_builder",
            metadata={
                "name": self.name_edit.text(),
                "type": self.type_combo.currentText(),
                "custom": True
            }
        )

        self.skeleton_created.emit(skeleton)
        self.accept()