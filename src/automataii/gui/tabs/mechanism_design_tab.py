import logging
from typing import Optional, Dict, Any
import math

from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QGroupBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QMessageBox,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QDialog,
    QGraphicsView,
    QGraphicsItem,
)
from PyQt6.QtCore import pyqtSignal, QPointF, Qt, QTimer
from PyQt6.QtCore import pyqtSlot
from PyQt6.QtGui import QPainterPath, QPen, QColor, QBrush, QTransform

from ..views.editor_view import EditorView
from PyQt6.QtWidgets import QGraphicsScene, QGraphicsPathItem, QGraphicsView, QGraphicsItem, QDialog
from automataii.core.models import PartInfo
from ..graphics_items.part_item import CharacterPartItem

from ..dialogs.recommendation_dialog import (
    MECHANISM_TYPE_USER_DISPLAY_4_BAR,
    MECHANISM_TYPE_USER_DISPLAY_3_BAR,
    MECHANISM_TYPE_USER_DISPLAY_CAM,
    MechanismRecommendationDialog,
)


class MechanismDesignTab(QWidget):
    """Tab-specific mechanism design and generation functionality"""

    # Signals for mechanism-related operations
    request_generate_mechanism = pyqtSignal(str, dict)  # mechanism_type, params
    request_generate_blueprint = pyqtSignal()
    mechanism_selection_changed = pyqtSignal(str)  # mechanism_type
    mechanism_path_generated = pyqtSignal(str, QPainterPath)  # part_name, generated_path

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.debug_mode = getattr(main_window, "debug_mode", False)

        # Path data from editor tab
        self.path_data: Dict[str, QPainterPath] = {}
        self.selected_part_name: Optional[str] = None
        self.parts_data: Dict[str, PartInfo] = {}  # Store parts data
        self.current_editor_items: Dict[str, CharacterPartItem] = {}

        # Mechanism generation state
        self.current_mechanism_type: Optional[str] = None
        self.mechanism_params: Dict[str, Any] = {}
        self.mechanism_layers: Dict[str, Any] = {}  # Store mechanism layers
        self.path_visual_items: Dict[str, QGraphicsPathItem] = {}  # Store path visuals
        self.mechanism_paths: Dict[str, QPainterPath] = {}

        # Graphics scene for mechanism preview
        self.mechanism_scene = QGraphicsScene(self)
        self.mechanism_view = EditorView(self.mechanism_scene, self)

        # Edit mode state
        self.edit_mode = False

        # Animation state
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self._update_animation)
        self.animation_time = 0.0
        self.animation_speed = 1.0  # radians per second
        self.animating_mechanisms = {}  # Store original positions for animation

        # UI Elements
        self.mechanism_type_combo: Optional[QComboBox] = None
        self.generate_mechanism_btn: Optional[QPushButton] = None
        self.mechanism_preview_group: Optional[QGroupBox] = None
        self.mechanism_params_group: Optional[QGroupBox] = None
        self.parts_selection_combo: Optional[QComboBox] = None
        self.blueprint_btn: Optional[QPushButton] = None
        self.recommendation_btn: Optional[QPushButton] = None
        self.start_edit_btn: Optional[QPushButton] = None
        self.mechanism_layers_list: Optional[QListWidget] = None
        self.animate_btn: Optional[QPushButton] = None
        self.stop_animate_btn: Optional[QPushButton] = None

        # Mechanism parameters widgets
        self.cam_center_x_spin: Optional[QDoubleSpinBox] = None
        self.cam_center_y_spin: Optional[QDoubleSpinBox] = None
        self.cam_radius_spin: Optional[QDoubleSpinBox] = None
        self.linkage_length_spin: Optional[QDoubleSpinBox] = None
        self.gear_ratio_spin: Optional[QDoubleSpinBox] = None

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Setup UI - Similar to EditorTab but with mechanism layers instead of parts"""
        main_layout = QHBoxLayout(self)

        # Left Control Panel (similar to EditorTab)
        from PyQt6.QtWidgets import QScrollArea, QSizePolicy
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFixedWidth(300)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        control_panel = QWidget()
        panel_layout = QVBoxLayout(control_panel)
        panel_layout.setContentsMargins(10, 10, 10, 10)
        panel_layout.setSpacing(15)

        # 1. Mechanism Layers Group (similar to Parts in EditorTab)
        layers_group = QGroupBox("1 Mechanism Layers")
        layers_group.setStyleSheet("""
            QGroupBox {
                background-color: #ffffff;
                border: 1px solid #e3e9f0;
                border-radius: 9px;
                padding: 18px;
                margin-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 10px;
                margin-left: 15px;
                font-size: 12pt;
                font-weight: bold;
                color: #5c85d6;
                background-color: #ffffff;
            }
        """)
        layers_layout = QVBoxLayout(layers_group)
        self.mechanism_layers_list = QListWidget()
        self.mechanism_layers_list.setToolTip("List of generated mechanism layers")
        self.mechanism_layers_list.setMinimumHeight(180)
        self.mechanism_layers_list.setStyleSheet(
            """
            QListWidget {
                background-color: white;
                border: 1px solid #dee2e6;
                border-radius: 6px;
                padding: 4px;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 8px 12px;
                margin: 2px;
                border-radius: 4px;
                border: 1px solid transparent;
            }
            QListWidget::item:selected {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #0078D7, stop: 1 #005a9e);
                color: white;
                border: 1px solid #004578;
            }
            QListWidget::item:selected:!active {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #0078D7, stop: 1 #005a9e);
                color: white;
                border: 1px solid #004578;
            }
            QListWidget::item:hover {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
            }
        """
        )
        layers_layout.addWidget(self.mechanism_layers_list)
        panel_layout.addWidget(layers_group)

        # 2. Mechanism Generation Group
        generation_group = QGroupBox("2 Mechanism Generation")
        generation_group.setStyleSheet("""
            QGroupBox {
                background-color: #ffffff;
                border: 1px solid #e3e9f0;
                border-radius: 9px;
                padding: 18px;
                margin-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 10px;
                margin-left: 15px;
                font-size: 12pt;
                font-weight: bold;
                color: #5c85d6;
                background-color: #ffffff;
            }
        """)
        generation_layout = QVBoxLayout(generation_group)

        # Target part selection
        part_selection_layout = QFormLayout()
        self.parts_selection_combo = QComboBox()
        part_selection_layout.addRow("Target Part:", self.parts_selection_combo)
        generation_layout.addLayout(part_selection_layout)

        # Mechanism type
        mechanism_type_layout = QFormLayout()
        self.mechanism_type_combo = QComboBox()
        self.mechanism_type_combo.addItems([
            MECHANISM_TYPE_USER_DISPLAY_4_BAR,
            MECHANISM_TYPE_USER_DISPLAY_3_BAR,
            MECHANISM_TYPE_USER_DISPLAY_CAM,
            "Gear System",
            "Custom Linkage"
        ])
        mechanism_type_layout.addRow("Type:", self.mechanism_type_combo)
        generation_layout.addLayout(mechanism_type_layout)

        # Buttons
        self.recommendation_btn = QPushButton("Get Recommendations")
        self.recommendation_btn.setEnabled(False)
        generation_layout.addWidget(self.recommendation_btn)

        self.generate_mechanism_btn = QPushButton("Generate Mechanism")
        self.generate_mechanism_btn.setEnabled(False)
        generation_layout.addWidget(self.generate_mechanism_btn)

        panel_layout.addWidget(generation_group)

        # 3. Mechanism Parameters Group
        self.mechanism_params_group = QGroupBox("3 Mechanism Parameters")
        self.mechanism_params_group.setStyleSheet("""
            QGroupBox {
                background-color: #ffffff;
                border: 1px solid #e3e9f0;
                border-radius: 9px;
                padding: 18px;
                margin-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 10px;
                margin-left: 15px;
                font-size: 12pt;
                font-weight: bold;
                color: #5c85d6;
                background-color: #ffffff;
            }
        """)
        self._setup_mechanism_params()
        panel_layout.addWidget(self.mechanism_params_group)

        # 4. Animation Group
        animation_group = QGroupBox("4 Animation")
        animation_group.setStyleSheet("""
            QGroupBox {
                background-color: #ffffff;
                border: 1px solid #e3e9f0;
                border-radius: 9px;
                padding: 18px;
                margin-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 10px;
                margin-left: 15px;
                font-size: 12pt;
                font-weight: bold;
                color: #5c85d6;
                background-color: #ffffff;
            }
        """)
        animation_layout = QVBoxLayout(animation_group)

        # Edit mode
        self.start_edit_btn = QPushButton("Start Editing")
        self.start_edit_btn.setCheckable(True)
        self.start_edit_btn.setEnabled(False)
        animation_layout.addWidget(self.start_edit_btn)

        # Animation controls
        anim_button_layout = QHBoxLayout()
        self.animate_btn = QPushButton("Play")
        self.animate_btn.setEnabled(False)
        self.stop_animate_btn = QPushButton("Stop")
        self.stop_animate_btn.setEnabled(False)
        anim_button_layout.addWidget(self.animate_btn)
        anim_button_layout.addWidget(self.stop_animate_btn)
        animation_layout.addLayout(anim_button_layout)

        # Blueprint button
        self.blueprint_btn = QPushButton("Generate Blueprint")
        self.blueprint_btn.setEnabled(False)
        animation_layout.addWidget(self.blueprint_btn)

        panel_layout.addWidget(animation_group)
        panel_layout.addStretch(1)

        control_panel.setMinimumWidth(280)
        scroll_area.setWidget(control_panel)
        main_layout.addWidget(scroll_area)

        # Right side - Editor view (same as EditorTab)
        main_layout.addWidget(self.mechanism_view, 1)

    def _setup_mechanism_params(self):
        """Setup mechanism parameters UI"""
        params_layout = QFormLayout(self.mechanism_params_group)

        # Cam parameters
        self.cam_center_x_spin = QDoubleSpinBox()
        self.cam_center_x_spin.setRange(-1000, 1000)
        self.cam_center_x_spin.setValue(0)
        params_layout.addRow("Cam Center X:", self.cam_center_x_spin)

        self.cam_center_y_spin = QDoubleSpinBox()
        self.cam_center_y_spin.setRange(-1000, 1000)
        self.cam_center_y_spin.setValue(0)
        params_layout.addRow("Cam Center Y:", self.cam_center_y_spin)

        self.cam_radius_spin = QDoubleSpinBox()
        self.cam_radius_spin.setRange(10, 500)
        self.cam_radius_spin.setValue(50)
        params_layout.addRow("Cam Radius:", self.cam_radius_spin)

        # Linkage parameters
        self.linkage_length_spin = QDoubleSpinBox()
        self.linkage_length_spin.setRange(10, 500)
        self.linkage_length_spin.setValue(100)
        params_layout.addRow("Linkage Length:", self.linkage_length_spin)

        # Gear parameters
        self.gear_ratio_spin = QDoubleSpinBox()
        self.gear_ratio_spin.setRange(0.1, 10.0)
        self.gear_ratio_spin.setValue(1.0)
        self.gear_ratio_spin.setSingleStep(0.1)
        params_layout.addRow("Gear Ratio:", self.gear_ratio_spin)

    def _connect_signals(self):
        """Connect signals"""
        self.mechanism_type_combo.currentTextChanged.connect(self._on_mechanism_type_changed)
        self.parts_selection_combo.currentTextChanged.connect(self._on_part_selection_changed)
        self.generate_mechanism_btn.clicked.connect(self._on_generate_mechanism)
        self.blueprint_btn.clicked.connect(self._on_generate_blueprint)
        self.recommendation_btn.clicked.connect(self._on_get_recommendations)
        self.start_edit_btn.toggled.connect(self._on_edit_mode_toggled)
        self.animate_btn.clicked.connect(self._on_start_animation)
        self.stop_animate_btn.clicked.connect(self._on_stop_animation)
        self.mechanism_layers_list.itemSelectionChanged.connect(self._on_layer_selection_changed)

        # Parameter changes
        self.cam_center_x_spin.valueChanged.connect(self._on_params_changed)
        self.cam_center_y_spin.valueChanged.connect(self._on_params_changed)
        self.cam_radius_spin.valueChanged.connect(self._on_params_changed)
        self.linkage_length_spin.valueChanged.connect(self._on_params_changed)
        self.gear_ratio_spin.valueChanged.connect(self._on_params_changed)

        # Connect internal signals
        self.mechanism_path_generated.connect(self.handle_mechanism_path_generated)

    @pyqtSlot(str)
    def _on_mechanism_type_changed(self, mechanism_type: str):
        """Mechanism type changed"""
        self.current_mechanism_type = mechanism_type
        self.mechanism_selection_changed.emit(mechanism_type)
        self._update_ui_for_mechanism_type()

    def _update_ui_for_mechanism_type(self):
        """Update UI based on selected mechanism type"""
        if not self.current_mechanism_type:
            return

        # Enable/disable parameter widgets based on mechanism type
        is_cam = "Cam" in self.current_mechanism_type
        is_linkage = "Bar" in self.current_mechanism_type or "Linkage" in self.current_mechanism_type
        is_gear = "Gear" in self.current_mechanism_type

        if self.cam_center_x_spin is not None:
            self.cam_center_x_spin.setVisible(is_cam)
        if self.cam_center_y_spin is not None:
            self.cam_center_y_spin.setVisible(is_cam)
        if self.cam_radius_spin is not None:
            self.cam_radius_spin.setVisible(is_cam)
        if self.linkage_length_spin is not None:
            self.linkage_length_spin.setVisible(is_linkage)
        if self.gear_ratio_spin is not None:
            self.gear_ratio_spin.setVisible(is_gear)

        self._check_generation_requirements()

    @pyqtSlot(str)
    def _on_part_selection_changed(self, part_name: str):
        """Target part selection changed"""
        self.selected_part_name = part_name
        self._check_generation_requirements()

    def _check_generation_requirements(self):
        """Check mechanism generation requirements"""
        if self.generate_mechanism_btn is None:
            return  # UI not initialized yet

        can_generate = bool(
            self.selected_part_name and
            self.current_mechanism_type and
            self.selected_part_name in self.path_data
        )
        self.generate_mechanism_btn.setEnabled(can_generate)
        self.recommendation_btn.setEnabled(bool(self.path_data))  # Enable if any paths exist

    @pyqtSlot()
    def _on_params_changed(self):
        """Parameters changed"""
        self._update_mechanism_params()

    def _update_mechanism_params(self):
        """Collect current parameter values"""
        self.mechanism_params = {
            "target_part_name": self.selected_part_name,
            "cam_center": QPointF(
                self.cam_center_x_spin.value(),
                self.cam_center_y_spin.value()
            ),
            "cam_radius": self.cam_radius_spin.value(),
            "linkage_length": self.linkage_length_spin.value(),
            "gear_ratio": self.gear_ratio_spin.value(),
        }

    @pyqtSlot()
    def _on_generate_mechanism(self):
        """Request mechanism generation"""
        if not self.selected_part_name or not self.current_mechanism_type:
            QMessageBox.warning(self, "Warning", "Please select a part and mechanism type.")
            return

        self._update_mechanism_params()

        # Convert display name to internal type
        mechanism_type_mapping = {
            MECHANISM_TYPE_USER_DISPLAY_4_BAR: "4_bar_linkage",
            MECHANISM_TYPE_USER_DISPLAY_3_BAR: "3_bar_linkage",
            MECHANISM_TYPE_USER_DISPLAY_CAM: "cam",
            "Gear System": "gear",
            "Custom Linkage": "custom_linkage"
        }

        internal_type = mechanism_type_mapping.get(self.current_mechanism_type, "4_bar_linkage")

        logging.info(f"Generating mechanism: {internal_type} for part {self.selected_part_name}")

        # Add mechanism layer to the list
        layer_name = f"{self.current_mechanism_type} - {self.selected_part_name}"
        layer_data = {
            "type": internal_type,
            "part_name": self.selected_part_name,
            "params": self.mechanism_params.copy(),
            "visual_items": []  # Will be populated when mechanism is generated
        }
        self._add_mechanism_layer(layer_name, layer_data)

        # Emit request to generate the actual mechanism
        self.request_generate_mechanism.emit(internal_type, self.mechanism_params)
        if self.blueprint_btn is not None:
            self.blueprint_btn.setEnabled(True)

    @pyqtSlot()
    def _on_generate_blueprint(self):
        """Request blueprint generation"""
        self.request_generate_blueprint.emit()

    def set_path_data_from_editor(self, path_data: Dict[str, QPainterPath]):
        """Receive path data from editor tab"""
        logging.info(f"MechanismDesignTab: Received path data for {len(path_data)} parts: {list(path_data.keys())}")
        self.path_data = path_data.copy()
        self._update_parts_selection()
        self._check_generation_requirements()
        self._display_paths_in_preview()  # Show paths in preview

    def _update_parts_selection(self):
        """Update parts selection combobox"""
        if self.parts_selection_combo is not None:
            self.parts_selection_combo.clear()
            if self.path_data:
                self.parts_selection_combo.addItems(list(self.path_data.keys()))

    def set_parts_data(self, parts_data: Dict[str, PartInfo]):
        """
        Set parts data, create CharacterPartItem instances, and add them to the scene.
        Synchronized with the EditorTab.
        """
        logging.info(f"MechanismDesignTab: Setting parts data for {list(parts_data.keys())}")

        # Clear existing items from the scene and the dictionary
        for item in self.current_editor_items.values():
            if item.scene() == self.mechanism_scene:
                self.mechanism_scene.removeItem(item)
        self.current_editor_items.clear()

        self.parts_data = parts_data.copy() if parts_data else {}

        if not self.parts_data:
            logging.warning("MechanismDesignTab: Received empty parts data.")
            # self.mechanism_view.zoom_to_fit() # This is called later
            return

        # Create and add new items
        for part_name, part_info in self.parts_data.items():
            if part_info.image_path:
                item = CharacterPartItem(part_info, self.debug_mode)
                self.mechanism_scene.addItem(item)
                self.current_editor_items[part_name] = item
                logging.debug(f"Added CharacterPartItem for '{part_name}' to mechanism scene.")
            else:
                logging.warning(f"Part '{part_name}' has no pixmap, cannot create item.")

        # Update the parts selection dropdown
        if self.parts_selection_combo is not None:
            part_names = list(self.parts_data.keys())
            self.parts_selection_combo.clear()
            self.parts_selection_combo.addItems(part_names)

        logging.info(f"MechanismDesignTab: Loaded {len(self.current_editor_items)} part items.")
        self.mechanism_view.zoom_to_fit()

    def clear_mechanism_data(self):
        """Clear mechanism data"""
        self.path_data.clear()
        self.selected_part_name = None
        self.current_mechanism_type = None
        self.mechanism_params.clear()
        self.mechanism_layers.clear()
        self.path_visual_items.clear()
        self.current_editor_items.clear()
        self.mechanism_paths.clear()

        if self.parts_selection_combo is not None:
            self.parts_selection_combo.clear()
        if self.mechanism_scene is not None:
            self.mechanism_scene.clear()
        if self.generate_mechanism_btn is not None:
            self.generate_mechanism_btn.setEnabled(False)
        if self.blueprint_btn is not None:
            self.blueprint_btn.setEnabled(False)
        if self.recommendation_btn is not None:
            self.recommendation_btn.setEnabled(False)
        if self.start_edit_btn is not None:
            self.start_edit_btn.setEnabled(False)
            self.start_edit_btn.setChecked(False)
        if self.mechanism_layers_list is not None:
            self.mechanism_layers_list.clear()

    @pyqtSlot(dict)
    def handle_mechanism_visuals(self, mechanism_graphics_data: dict):
        """Handle mechanism visualization data"""
        if not mechanism_graphics_data:
            return

        # Clear previous mechanism visuals
        self.mechanism_scene.clear()

        # Add mechanism graphics to preview
        for item_data in mechanism_graphics_data.get("graphics_items", []):
            # Process mechanism graphics items
            # This would depend on the structure of mechanism_graphics_data
            pass

        # Update view
        self.mechanism_view.zoom_to_fit()

    @pyqtSlot(str, QPainterPath)
    def handle_mechanism_path_generated(self, part_name: str, path: QPainterPath):
        """Receives the generated mechanism path and displays it."""
        logging.info(f"Received generated mechanism path for part '{part_name}'.")
        self.mechanism_paths[part_name] = path

        # Visualize the path
        path_item = QGraphicsPathItem(path)
        pen = QPen(QColor(255, 0, 255), 2.5, Qt.PenStyle.DashLine) # Magenta dashed line for generated path
        pen.setCosmetic(True)
        path_item.setPen(pen)
        path_item.setZValue(5) # Draw above other paths
        self.mechanism_scene.addItem(path_item)

        # Enable animation now that we have a path
        if self.animate_btn:
            self.animate_btn.setEnabled(True)

    def get_selected_part_name(self) -> Optional[str]:
        """Return selected part name"""
        return self.selected_part_name

    def get_current_mechanism_type(self) -> Optional[str]:
        """Return current mechanism type"""
        return self.current_mechanism_type

    def _display_paths_in_preview(self):
        """Display motion paths from editor tab in the preview"""
        logging.info(f"MechanismDesignTab: Displaying {len(self.path_data)} paths in preview")

        # Clear existing path visuals
        for item in self.path_visual_items.values():
            if item.scene():
                self.mechanism_scene.removeItem(item)
        self.path_visual_items.clear()

        # Add new path visuals
        for part_name, path in self.path_data.items():
            if not path.isEmpty():
                logging.debug(f"MechanismDesignTab: Adding path visual for {part_name}")
                path_item = QGraphicsPathItem(path)
                # Use green color similar to editor tab
                pen = QPen(QColor(0, 200, 0), 3.0)
                pen.setCosmetic(True)
                path_item.setPen(pen)
                path_item.setZValue(1)  # Draw above background

                self.mechanism_scene.addItem(path_item)
                self.path_visual_items[part_name] = path_item

        # Fit view to show all paths
        if self.path_visual_items:
            self.mechanism_view.zoom_to_fit()
            logging.info(f"MechanismDesignTab: Successfully displayed {len(self.path_visual_items)} path visuals")

    @pyqtSlot(dict)
    def on_recommendations_ready(self, recommendations: dict):
        """Handle received recommendations by showing the dialog."""
        # This will be called when MechanismManager emits the signal
        # ... existing code ...

    @pyqtSlot()
    def _on_get_recommendations(self):
        """Show mechanism recommendation dialog"""
        if not self.path_data:
            return

        # Get the selected part's path or first available path
        target_path = None
        if self.selected_part_name and self.selected_part_name in self.path_data:
            target_path = self.path_data[self.selected_part_name]
        else:
            # Get first non-empty path
            for path in self.path_data.values():
                if not path.isEmpty():
                    target_path = path
                    break

        if not target_path:
            QMessageBox.warning(self, "Warning", "No valid motion path found.")
            return

        # Show recommendation dialog with generated paths file
        import os
        from pathlib import Path

        # Get the project root by navigating up from the current file's location
        # This is more robust than assuming a fixed structure.
        project_root = Path(__file__).resolve().parents[4]

        # Get the path to the generated mechanism paths JSON file
        generated_paths_file = project_root / "src" / "automataii" / "kinematics" / "generated_mechanism_paths.json"

        if not os.path.exists(generated_paths_file):
            QMessageBox.warning(self, "Warning", "Generated mechanism paths file not found.")
            logging.error(f"Generated paths file not found at: {generated_paths_file}")
            return

        dialog = MechanismRecommendationDialog(target_path, generated_paths_file, parent=self)

        # Connect preview signal to handle mechanism preview clicks
        dialog.mechanism_preview_selected.connect(self._on_mechanism_preview_selected)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_mechanism = dialog.selected_mechanism_data
            if selected_mechanism:
                # Update mechanism type combo based on the selected mechanism
                mechanism_type = selected_mechanism.get("type", "")

                # Map from mechanism types to combo box display names
                type_mapping = {
                    MECHANISM_TYPE_USER_DISPLAY_4_BAR: MECHANISM_TYPE_USER_DISPLAY_4_BAR,
                    MECHANISM_TYPE_USER_DISPLAY_3_BAR: MECHANISM_TYPE_USER_DISPLAY_3_BAR,
                    MECHANISM_TYPE_USER_DISPLAY_CAM: MECHANISM_TYPE_USER_DISPLAY_CAM,
                    "Cam & Follower": MECHANISM_TYPE_USER_DISPLAY_CAM,
                    "4-Bar Linkage": MECHANISM_TYPE_USER_DISPLAY_4_BAR,
                    "3-Bar Linkage": MECHANISM_TYPE_USER_DISPLAY_3_BAR,
                    "Gears (Simple Pair)": "Gear System",
                    "gears": "Gear System",
                    "linkage": MECHANISM_TYPE_USER_DISPLAY_4_BAR,
                }

                display_name = type_mapping.get(mechanism_type, mechanism_type)
                index = self.mechanism_type_combo.findText(display_name)
                if index >= 0:
                    self.mechanism_type_combo.setCurrentIndex(index)

                # Apply recommended parameters from selected_mechanism
                params = selected_mechanism.get("parameters", {})
                if params:
                    # TODO: Apply parameters based on mechanism type
                    logging.info(f"Selected mechanism: {display_name} with parameters: {params}")
                else:
                    logging.info(f"Selected mechanism: {display_name}")

    @pyqtSlot(bool)
    def _on_edit_mode_toggled(self, checked: bool):
        """Toggle edit mode for drag and drop mechanism editing"""
        self.edit_mode = checked

        if checked:
            self.start_edit_btn.setText("Stop Editing")
            self.mechanism_view.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
            # Enable interactive editing
            for item in self.mechanism_scene.items():
                if hasattr(item, 'setFlag'):
                    item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
                    item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        else:
            self.start_edit_btn.setText("Start Editing")
            self.mechanism_view.setDragMode(QGraphicsView.DragMode.NoDrag)
            # Disable interactive editing
            for item in self.mechanism_scene.items():
                if hasattr(item, 'setFlag'):
                    item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
                    item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)

    @pyqtSlot()
    def _on_start_animation(self):
        """Start mechanism animation"""
        self.animate_btn.setEnabled(False)
        self.stop_animate_btn.setEnabled(True)

        # Store original positions for all mechanism items
        self.animating_mechanisms.clear()
        for layer_name, layer_data in self.mechanism_layers.items():
            visual_items = layer_data.get("visual_items", [])
            if visual_items:
                self.animating_mechanisms[layer_name] = {
                    "type": layer_data.get("type"),
                    "items": visual_items,
                    "params": layer_data.get("params", {}),
                    "original_transforms": {}
                }
                # Store original transforms
                for item in visual_items:
                    if item and item.scene():
                        self.animating_mechanisms[layer_name]["original_transforms"][item] = item.transform()

        # Start animation timer
        self.animation_time = 0.0
        self.animation_timer.start(33)  # ~30 FPS
        logging.info("Started mechanism animation")

    @pyqtSlot()
    def _on_stop_animation(self):
        """Stop mechanism animation"""
        self.animate_btn.setEnabled(True)
        self.stop_animate_btn.setEnabled(False)

        # Stop timer
        self.animation_timer.stop()

        # Restore original positions
        for layer_name, anim_data in self.animating_mechanisms.items():
            for item, original_transform in anim_data["original_transforms"].items():
                if item and item.scene():
                    item.setTransform(original_transform)

        self.animating_mechanisms.clear()
        self.animation_time = 0.0
        logging.info("Stopped mechanism animation")

    @pyqtSlot()
    def _on_layer_selection_changed(self):
        """Handle mechanism layer selection change"""
        selected_items = self.mechanism_layers_list.selectedItems()
        if selected_items:
            layer_name = selected_items[0].text()
            logging.info(f"Selected mechanism layer: {layer_name}")

            # Highlight selected layer in preview
            if layer_name in self.mechanism_layers:
                layer_data = self.mechanism_layers[layer_name]

                # Reset all items to normal appearance
                for item in self.mechanism_scene.items():
                    if isinstance(item, QGraphicsPathItem):
                        # Reset to default pen
                        pen = item.pen()
                        pen.setWidth(2.0)
                        item.setPen(pen)
                        item.setOpacity(0.7)

                # Highlight items belonging to selected layer
                visual_items = layer_data.get("visual_items", [])
                for item in visual_items:
                    if item and item.scene() == self.mechanism_scene:
                        # Highlight with thicker pen and full opacity
                        pen = item.pen()
                        pen.setWidth(4.0)
                        item.setPen(pen)
                        item.setOpacity(1.0)

    def _add_mechanism_layer(self, layer_name: str, layer_data: Any):
        """Add a mechanism layer to the layers list"""
        self.mechanism_layers[layer_name] = layer_data

        # Add to list widget
        item = QListWidgetItem(layer_name)
        self.mechanism_layers_list.addItem(item)

        # Enable edit and animation controls
        if self.start_edit_btn is not None:
            self.start_edit_btn.setEnabled(True)
        if self.animate_btn is not None:
            self.animate_btn.setEnabled(True)

    @pyqtSlot(dict)
    def _on_mechanism_preview_selected(self, mechanism_data: dict):
        """Handle mechanism preview selection from recommendation dialog"""
        logging.info(f"Mechanism preview selected: {mechanism_data.get('type', 'Unknown')}")
        # Could update a preview or show additional info here
        # Display the selected mechanism preview
        # TODO: Implement mechanism preview visualization based on mechanism_data
        # For now, just show the path if available
        path_coords = mechanism_data.get("path_coordinates")
        if path_coords:
            # Convert coordinates to QPainterPath
            preview_path = QPainterPath()
            for i, (x, y) in enumerate(path_coords):
                if i == 0:
                    preview_path.moveTo(x, y)
                else:
                    preview_path.lineTo(x, y)

            # Create path item
            path_item = QGraphicsPathItem(preview_path)
            pen = QPen(QColor(0, 100, 200), 2.0)
            pen.setCosmetic(True)
            path_item.setPen(pen)

            self.mechanism_scene.addItem(path_item)
            self.mechanism_view.zoom_to_fit()

        # Update UI to show mechanism type
        mechanism_type = mechanism_data.get("type", "")
        type_mapping = {
            "Cam & Follower": MECHANISM_TYPE_USER_DISPLAY_CAM,
            "4-Bar Linkage": MECHANISM_TYPE_USER_DISPLAY_4_BAR,
            "3-Bar Linkage": MECHANISM_TYPE_USER_DISPLAY_3_BAR,
            "Gears (Simple Pair)": "Gear System",
        }
        display_name = type_mapping.get(mechanism_type, mechanism_type)

        # Update status or info label if available
        # TODO: self.mechanism_preview_group is not initialized.
        # self.mechanism_preview_group.setTitle(f"Mechanism Preview - {display_name}")

    def _update_animation(self):
        """Update animation frame"""
        # Increment animation time
        dt = 0.033  # Corresponds to ~30 FPS timer
        self.animation_time += dt * self.animation_speed

        # Animate each mechanism layer's components
        for layer_name, anim_data in self.animating_mechanisms.items():
            mech_type = anim_data.get("type", "")

            # --- Animate mechanism components (gears, links) ---
            if mech_type == "cam":
                # Simple rotation animation for cam
                for item in anim_data["items"]:
                    if item and item.scene():
                        center = item.boundingRect().center()
                        transform = QTransform()
                        transform.translate(center.x(), center.y())
                        transform.rotate(self.animation_time * 180 / 3.14159)
                        transform.translate(-center.x(), -center.y())
                        item.setTransform(transform)

            elif mech_type in ["4_bar_linkage", "3_bar_linkage"]:
                # Simple oscillation for linkages
                angle = self.animation_time
                amplitude = 30  # degrees
                rotation = amplitude * math.sin(angle)

                for item in anim_data["items"]:
                    if item and item.scene():
                        center = item.boundingRect().center()
                        transform = QTransform()
                        transform.translate(center.x(), center.y())
                        transform.rotate(rotation)
                        transform.translate(-center.x(), -center.y())
                        item.setTransform(transform)

            elif mech_type == "gear":
                # Counter-rotating gears
                for i, item in enumerate(anim_data["items"]):
                    if item and item.scene():
                        center = item.boundingRect().center()
                        direction = 1 if i % 2 == 0 else -1
                        transform = QTransform()
                        transform.translate(center.x(), center.y())
                        transform.rotate(direction * self.animation_time * 180 / 3.14159)
                        transform.translate(-center.x(), -center.y())
                        item.setTransform(transform)

            # --- Animate the target character part along the generated path ---
            params = anim_data.get("params", {})
            target_part_name = params.get("target_part_name")

            if target_part_name:
                part_item = self.current_editor_items.get(target_part_name)
                # Use the path from the editor tab for animation
                mechanism_path = self.path_data.get(target_part_name)

                if part_item and mechanism_path and not mechanism_path.isEmpty():
                    # Animate the part along its generated path
                    # Loop animation every 5 seconds
                    percent = (self.animation_time / 5.0) % 1.0

                    # Get point at percent
                    pos = mechanism_path.pointAtPercent(percent)

                    # Calculate angle manually as angleAtPercent is not available in PyQt6
                    next_percent = (percent + 0.001) % 1.0
                    p1 = pos
                    p2 = mechanism_path.pointAtPercent(next_percent)

                    dx = p2.x() - p1.x()
                    dy = p2.y() - p1.y()

                    angle_rad = math.atan2(dy, dx)
                    angle_deg = math.degrees(angle_rad)

                    # Set position, compensating for the item's own center
                    # This assumes the pixmap's center should follow the path
                    item_center = part_item.boundingRect().center()
                    part_item.setPos(pos - item_center)

                    # Set rotation
                    # The angle from atan2 is counter-clockwise, which matches setRotation's default.
                    part_item.setRotation(angle_deg)


        # Update scene
        self.mechanism_scene.update()
