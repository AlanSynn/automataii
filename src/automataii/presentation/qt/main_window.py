import json
import logging
import os
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import yaml
from PyQt6.QtCore import (
    QPointF,
    Qt,
    pyqtSlot,
)
from PyQt6.QtGui import QCloseEvent, QPainterPath
from PyQt6.QtWidgets import (
    QFileDialog,
    QGraphicsItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QMainWindow,
    QMessageBox,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

# Import MechanismManager
# Import ProjectDataManager
# Import SkeletonManager
from automataii.application.managers import MechanismManager, ProjectDataManager, SkeletonManager

# Import ProjectStateManager, adapters, and serializer (SSOT architecture)
from automataii.application.project import (
    BoneData,
    JointData,
    MechanismData,
    PartData,
    PathData,
    Point,
    ProjectSerializer,
    ProjectStateManager,
    SkeletonData,
    Transform,
)
from automataii.application.project.adapters import (
    EditorTabAdapter,
    ImageProcessingTabAdapter,
    MechanismDesignTabAdapter,
)

# Import ActionManager for centralized action management
from automataii.presentation.qt.actions.action_manager import ActionManager

# Import AcceleratedAnimationScheduler for unified real-time animation
from automataii.presentation.qt.animation import AcceleratedAnimationScheduler
from automataii.presentation.qt.graphics_items.part_item import CharacterPartItem

# Import IKManager (Qt-coupled, in presentation layer)
from automataii.presentation.qt.kinematics.ik_manager import IKManager
from automataii.presentation.qt.models import PartInfo  # ProjectFileModel is in models_pydantic
from automataii.presentation.qt.tabs.editor.tab import EditorTab
from automataii.presentation.qt.tabs.image_processing_tab import ImageProcessingTab
from automataii.presentation.qt.tabs.lab import LabTab

# Import new tab modules
from automataii.presentation.qt.tabs.landing_tab import LandingTab
from automataii.presentation.qt.tabs.mechanism_design.tab import MechanismDesignTab
from automataii.presentation.qt.tabs.mechanism_foundry import MechanismFoundryView
from automataii.presentation.qt.tabs.options_tab import OptionsTab

# Local imports (adjust paths as needed)
from automataii.presentation.qt.views.editor_view import EditorView  # ADD THIS IMPORT

# Import extracted components for tab lifecycle management
from automataii.presentation.qt.windows.components import (
    ProjectController,
    SignalConnector,
    TabOrchestrator,
    WorkflowStateMachine,
    WorkspaceLayoutManager,
)
from automataii.utils.paths import resolve_path
from automataii.utils.styling import DARK_STYLE, LIGHT_STYLE

# from qframelesswindow import FramelessMainWindow

TARGET_CONTROL_POINTS = 8
_PROJECT_TRANSIENT_LAYER_KEYS = frozenset(
    {
        "id",
        "part_name",
        "type",
        "mechanism_type",
        "params",
        "enabled",
        "visual_items",
    }
)
_PROJECT_RUNTIME_LAYER_KEY_SUFFIXES = ("_cache", "_cached")
_DEFAULT_DUMMY_REFERENCE_HEIGHT_PX = 960.0
_CHARACTER_SCALE_LOWER_RATIO = 0.8
_CHARACTER_SCALE_UPPER_RATIO = 1.25
_CHARACTER_SCALE_MIN = 0.5
_CHARACTER_SCALE_MAX = 4.0
_SKELETON_PART_HEIGHT_RATIO_MIN = 0.6
_SKELETON_PART_HEIGHT_RATIO_MAX = 1.8
_PART_TO_SKELETON_MIN_RATIO = 0.9
_PART_TO_SKELETON_MAX_SCALE = 4.0


def _calculate_parts_bbox(parts_info: dict[str, Any]) -> tuple[float, float, float, float] | None:
    min_x: float | None = None
    min_y: float | None = None
    max_x: float | None = None
    max_y: float | None = None

    for part in parts_info.values():
        roi = getattr(part, "roi", None)
        if not isinstance(roi, list | tuple) or len(roi) < 4:
            continue
        try:
            x = float(roi[0])
            y = float(roi[1])
            w = float(roi[2])
            h = float(roi[3])
        except (TypeError, ValueError):
            continue
        if w <= 0.0 or h <= 0.0:
            continue

        x2 = x + w
        y2 = y + h
        min_x = x if min_x is None else min(min_x, x)
        min_y = y if min_y is None else min(min_y, y)
        max_x = x2 if max_x is None else max(max_x, x2)
        max_y = y2 if max_y is None else max(max_y, y2)

    if min_x is None or min_y is None or max_x is None or max_y is None:
        return None
    return (min_x, min_y, max_x, max_y)


def _calculate_visible_parts_bbox(parts_info: dict[str, Any]) -> tuple[float, float, float, float] | None:
    """
    Calculate bbox from actually visible part pixels (alpha/content), not ROI rectangles.

    This is more robust than raw ROI when extraction includes generous padding.
    """
    min_x: float | None = None
    min_y: float | None = None
    max_x: float | None = None
    max_y: float | None = None

    for part in parts_info.values():
        roi = getattr(part, "roi", None)
        image_path = getattr(part, "image_path", None)
        if not isinstance(roi, list | tuple) or len(roi) < 4:
            continue
        if not image_path:
            continue

        try:
            roi_x = float(roi[0])
            roi_y = float(roi[1])
            roi_w = float(roi[2])
            roi_h = float(roi[3])
        except (TypeError, ValueError):
            continue
        if roi_w <= 0.0 or roi_h <= 0.0:
            continue

        try:
            img = cv2.imread(str(image_path), cv2.IMREAD_UNCHANGED)
        except Exception:
            img = None
        if img is None or img.size == 0:
            continue

        if img.ndim == 2:
            visible = img > 0
        elif img.shape[2] == 4:
            # Prefer alpha for extracted part textures.
            visible = img[:, :, 3] > 8
        else:
            # Fallback for non-alpha images.
            visible = np.any(img > 8, axis=2)

        ys, xs = np.where(visible)
        if xs.size == 0 or ys.size == 0:
            continue

        img_h, img_w = img.shape[:2]
        if img_w <= 0 or img_h <= 0:
            continue
        sx = roi_w / float(img_w)
        sy = roi_h / float(img_h)

        x1 = roi_x + (float(xs.min()) * sx)
        y1 = roi_y + (float(ys.min()) * sy)
        x2 = roi_x + ((float(xs.max()) + 1.0) * sx)
        y2 = roi_y + ((float(ys.max()) + 1.0) * sy)

        min_x = x1 if min_x is None else min(min_x, x1)
        min_y = y1 if min_y is None else min(min_y, y1)
        max_x = x2 if max_x is None else max(max_x, x2)
        max_y = y2 if max_y is None else max(max_y, y2)

    if min_x is None or min_y is None or max_x is None or max_y is None:
        return None
    return (min_x, min_y, max_x, max_y)


def _extract_joint_position(joint_raw: dict[str, Any]) -> tuple[float, float] | None:
    for key in ("position", "coordinates", "loc", "scene_position"):
        value = joint_raw.get(key)
        if isinstance(value, list | tuple) and len(value) >= 2:
            try:
                return (float(value[0]), float(value[1]))
            except (TypeError, ValueError):
                continue

    if "x" in joint_raw and "y" in joint_raw:
        try:
            return (float(joint_raw["x"]), float(joint_raw["y"]))
        except (TypeError, ValueError):
            return None

    return None


def _calculate_skeleton_bbox(
    raw_skeleton_data: list[dict[str, Any]] | None,
) -> tuple[float, float, float, float] | None:
    if not raw_skeleton_data:
        return None

    min_x: float | None = None
    min_y: float | None = None
    max_x: float | None = None
    max_y: float | None = None

    for joint_raw in raw_skeleton_data:
        if not isinstance(joint_raw, dict):
            continue
        joint_pos = _extract_joint_position(joint_raw)
        if joint_pos is None:
            continue
        x, y = joint_pos
        min_x = x if min_x is None else min(min_x, x)
        min_y = y if min_y is None else min(min_y, y)
        max_x = x if max_x is None else max(max_x, x)
        max_y = y if max_y is None else max(max_y, y)

    if min_x is None or min_y is None or max_x is None or max_y is None:
        return None
    return (min_x, min_y, max_x, max_y)


def _scale_parts_in_place(
    parts_info: dict[str, PartInfo],
    scale_factor: float,
    center: tuple[float, float],
) -> None:
    if abs(scale_factor - 1.0) < 1e-6:
        return

    cx, cy = center
    for part in parts_info.values():
        roi = getattr(part, "roi", None)
        if isinstance(roi, list | tuple) and len(roi) >= 4:
            try:
                x = float(roi[0])
                y = float(roi[1])
                w = float(roi[2])
                h = float(roi[3])
            except (TypeError, ValueError):
                continue

            new_x = cx + (x - cx) * scale_factor
            new_y = cy + (y - cy) * scale_factor
            new_w = max(1.0, w * scale_factor)
            new_h = max(1.0, h * scale_factor)

            part.roi = [new_x, new_y, new_w, new_h]
            part.x = new_x
            part.y = new_y

        local_pivot_offset = getattr(part, "local_pivot_offset", None)
        if isinstance(local_pivot_offset, list | tuple) and len(local_pivot_offset) >= 2:
            try:
                part.local_pivot_offset = [
                    float(local_pivot_offset[0]) * scale_factor,
                    float(local_pivot_offset[1]) * scale_factor,
                ]
            except (TypeError, ValueError):
                pass

        if hasattr(part, "effective_bbox_offset_x"):
            try:
                part.effective_bbox_offset_x = float(part.effective_bbox_offset_x) * scale_factor
            except (TypeError, ValueError):
                pass
        if hasattr(part, "effective_bbox_offset_y"):
            try:
                part.effective_bbox_offset_y = float(part.effective_bbox_offset_y) * scale_factor
            except (TypeError, ValueError):
                pass


def _translate_parts_in_place(
    parts_info: dict[str, PartInfo],
    dx: float,
    dy: float,
) -> None:
    if abs(dx) < 1e-6 and abs(dy) < 1e-6:
        return

    for part in parts_info.values():
        roi = getattr(part, "roi", None)
        if isinstance(roi, list | tuple) and len(roi) >= 4:
            try:
                x = float(roi[0]) + dx
                y = float(roi[1]) + dy
                w = float(roi[2])
                h = float(roi[3])
            except (TypeError, ValueError):
                continue
            part.roi = [x, y, w, h]
            part.x = x
            part.y = y


def _align_parts_bbox_to_skeleton_in_place(
    parts_info: dict[str, PartInfo],
    raw_skeleton_data: list[dict[str, Any]] | None,
) -> bool:
    """
    Upscale/recenter parts when they are noticeably smaller than the loaded skeleton.

    This guards cases where segmentation output is valid but too tight compared to
    skeleton coordinates, causing visual "tiny parts vs large skeleton" mismatch.
    """
    if not parts_info or not raw_skeleton_data:
        return False

    parts_bbox = _calculate_visible_parts_bbox(parts_info) or _calculate_parts_bbox(parts_info)
    skeleton_bbox = _calculate_skeleton_bbox(raw_skeleton_data)
    if not parts_bbox or not skeleton_bbox:
        return False

    parts_h = max(0.0, parts_bbox[3] - parts_bbox[1])
    skeleton_h = max(0.0, skeleton_bbox[3] - skeleton_bbox[1])
    if parts_h <= 1.0 or skeleton_h <= 1.0:
        return False

    part_to_skeleton_ratio = parts_h / skeleton_h
    if part_to_skeleton_ratio >= _PART_TO_SKELETON_MIN_RATIO:
        return False

    scale_factor = skeleton_h / parts_h
    scale_factor = max(1.0, min(_PART_TO_SKELETON_MAX_SCALE, scale_factor))
    parts_center = (
        float(parts_bbox[0] + parts_bbox[2]) * 0.5,
        float(parts_bbox[1] + parts_bbox[3]) * 0.5,
    )
    skeleton_center = (
        float(skeleton_bbox[0] + skeleton_bbox[2]) * 0.5,
        float(skeleton_bbox[1] + skeleton_bbox[3]) * 0.5,
    )

    _scale_parts_in_place(parts_info, scale_factor, parts_center)
    updated_parts_bbox = _calculate_parts_bbox(parts_info)
    if not updated_parts_bbox:
        return True

    updated_parts_center = (
        float(updated_parts_bbox[0] + updated_parts_bbox[2]) * 0.5,
        float(updated_parts_bbox[1] + updated_parts_bbox[3]) * 0.5,
    )
    _translate_parts_in_place(
        parts_info,
        dx=skeleton_center[0] - updated_parts_center[0],
        dy=skeleton_center[1] - updated_parts_center[1],
    )
    return True


def _scale_skeleton_raw_in_place(
    raw_skeleton_data: list[dict[str, Any]],
    scale_factor: float,
    center: tuple[float, float],
) -> None:
    if abs(scale_factor - 1.0) < 1e-6:
        return

    cx, cy = center
    for joint_raw in raw_skeleton_data:
        if not isinstance(joint_raw, dict):
            continue

        for key in ("position", "coordinates", "loc", "scene_position"):
            value = joint_raw.get(key)
            if not isinstance(value, list | tuple) or len(value) < 2:
                continue
            try:
                x = float(value[0])
                y = float(value[1])
            except (TypeError, ValueError):
                continue
            joint_raw[key] = [
                cx + (x - cx) * scale_factor,
                cy + (y - cy) * scale_factor,
            ]

        if "x" in joint_raw and "y" in joint_raw:
            try:
                x = float(joint_raw["x"])
                y = float(joint_raw["y"])
                joint_raw["x"] = cx + (x - cx) * scale_factor
                joint_raw["y"] = cy + (y - cy) * scale_factor
            except (TypeError, ValueError):
                continue


def _translate_skeleton_raw_in_place(
    raw_skeleton_data: list[dict[str, Any]],
    dx: float,
    dy: float,
) -> None:
    if abs(dx) < 1e-6 and abs(dy) < 1e-6:
        return

    for joint_raw in raw_skeleton_data:
        if not isinstance(joint_raw, dict):
            continue

        for key in ("position", "coordinates", "loc", "scene_position"):
            value = joint_raw.get(key)
            if not isinstance(value, list | tuple) or len(value) < 2:
                continue
            try:
                x = float(value[0])
                y = float(value[1])
            except (TypeError, ValueError):
                continue
            joint_raw[key] = [x + dx, y + dy]

        if "x" in joint_raw and "y" in joint_raw:
            try:
                joint_raw["x"] = float(joint_raw["x"]) + dx
                joint_raw["y"] = float(joint_raw["y"]) + dy
            except (TypeError, ValueError):
                continue


def _align_skeleton_bbox_to_parts_in_place(
    raw_skeleton_data: list[dict[str, Any]],
    parts_bbox: tuple[float, float, float, float] | None,
    *,
    force: bool = False,
) -> bool:
    if not raw_skeleton_data or not parts_bbox:
        return False

    skeleton_bbox = _calculate_skeleton_bbox(raw_skeleton_data)
    if not skeleton_bbox:
        return False

    parts_h = max(0.0, parts_bbox[3] - parts_bbox[1])
    skeleton_h = max(0.0, skeleton_bbox[3] - skeleton_bbox[1])
    if parts_h <= 1.0 or skeleton_h <= 1.0:
        return False

    ratio = skeleton_h / parts_h
    if not force and _SKELETON_PART_HEIGHT_RATIO_MIN <= ratio <= _SKELETON_PART_HEIGHT_RATIO_MAX:
        return False

    skeleton_center = (
        float(skeleton_bbox[0] + skeleton_bbox[2]) * 0.5,
        float(skeleton_bbox[1] + skeleton_bbox[3]) * 0.5,
    )
    parts_center = (
        float(parts_bbox[0] + parts_bbox[2]) * 0.5,
        float(parts_bbox[1] + parts_bbox[3]) * 0.5,
    )

    prealign_scale = parts_h / skeleton_h
    _scale_skeleton_raw_in_place(raw_skeleton_data, prealign_scale, skeleton_center)
    _translate_skeleton_raw_in_place(
        raw_skeleton_data,
        dx=parts_center[0] - skeleton_center[0],
        dy=parts_center[1] - skeleton_center[1],
    )
    return True


class AutomataDesigner(QMainWindow):
    """Main application window for the Automata Designer.

    Integrates image processing, skeleton editing, part assembly, motion definition,
    simulation, and blueprint generation.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        debug_mode: bool = False,
        experiment_mode: bool = False,
        editing_mode: bool = False,
    ):
        super().__init__(parent)
        self.debug_mode = debug_mode
        self.experiment_mode = experiment_mode
        self.editing_mode = editing_mode
        logging.info(
            f"Initializing AutomataDesigner... Debug mode: {self.debug_mode}, Editing mode: {self.editing_mode}"
        )
        self.resize(1200, 680)
        self.setMinimumSize(800, 600)
        logging.info("Initializing AutomataDesigner...")

        # Initialize updater (will be set from main)
        self.updater = None

        # Create action manager for centralized action management
        self.action_manager = ActionManager(self)

        # Create ProjectDataManager
        self.project_data_manager = ProjectDataManager(self)

        # Create SkeletonManager
        self.skeleton_manager = SkeletonManager(self)

        # Create IKManager
        self.ik_manager = IKManager(self)

        # Create MechanismManager
        self.mechanism_manager = MechanismManager(self)

        # Create AcceleratedAnimationScheduler (unified real-time animation with off-thread compute)
        self.animation_scheduler = AcceleratedAnimationScheduler(
            target_fps=60,
            enable_threading=True,
            parent=self,
        )

        # Create ProjectStateManager (SSOT architecture)
        self.project_state_manager = ProjectStateManager(self)

        # Create ProjectSerializer for save/load
        self._project_serializer = ProjectSerializer()

        # Tab adapters (initialized after tabs are created in _init_ui)
        self._image_proc_adapter: ImageProcessingTabAdapter | None = None
        self._editor_adapter: EditorTabAdapter | None = None
        self._mechanism_design_adapter: MechanismDesignTabAdapter | None = None

        self.viewer_char_texture_item: QGraphicsPixmapItem | None = None
        self.viewer_skeleton_items: list[QGraphicsItem] = []
        self.viewer_body_part_items: dict[str, CharacterPartItem] = {}
        self.viewer_loaded_parts_info: dict | None = None
        self.viewer_loaded_texture_path: str | None = None
        self.viewer_scene: QGraphicsScene | None = None
        self.viewer_view: EditorView | None = None

        # --- Initialize scenes and views that were previously in tab creation methods ---

        # Mechanism Design State - These are now managed by EditorTab or via signals

        # Markers for selected points - these are drawn by EditorView, state might be in MainWindow if needed globally

        self.project_dir: str | None = None  # Renamed/clarified for project scope

        # IK Animation Timer (New)
        # IK Animation Timer (New)

        self.main_toolbar = None

        # TabOrchestrator handles tab lifecycle and camera state sharing
        # Initialized after _init_ui() where tab_widget is created
        self._tab_orchestrator: TabOrchestrator | None = None
        self._workspace_layout_manager: WorkspaceLayoutManager | None = None
        self._workflow_state_machine: WorkflowStateMachine | None = None

        # SignalConnector handles centralized signal wiring
        self._signal_connector = SignalConnector(self)

        # ProjectController handles SSOT project operations
        self._project_controller = ProjectController(
            self.project_state_manager,
            self._project_serializer,
            parent=self,
        )

        # Tracking active dialogs
        # self.active_camera_dialogs = [] # Moved to ImageProcessingTab

        # --- Stylesheet Data --- (No longer need _define_stylesheets method)
        self.light_style = LIGHT_STYLE
        self.dark_style = DARK_STYLE

        self.visualization_layer_x_offset = 10.0  # Horizontal offset for visualization layers
        self._grid_system_enabled = True
        self._grid_cell_size_cm = 2.5
        self._auto_scale_character_to_dummy_next_load = False
        self._suppress_project_data_cleared_ui_once = False
        self._character_swap_load_in_progress = False
        self._runtime_to_ssot_sync_in_progress = False
        self._force_skeleton_parts_alignment_next_load = False
        self._dummy_reference_height_px: float | None = None

        # Load Parts and Styles

        # Load custom application fonts
        self._load_custom_fonts()

        # Setup UI, Menus, Toolbar, and connections
        self._init_ui()  # This creates self.editor_tab and other UI elements

        # Initialize TabOrchestrator after tab_widget is created
        self._init_tab_orchestrator()

        self._create_menus()  # Defines QActions and populates menubar
        self._create_toolbar()  # Defines QActions or uses existing ones for toolbar
        self._init_workspace_and_workflow()
        self._connect_global_signals()
        self._connect_manager_signals()  # New method for connecting manager signals
        self._setup_state_adapters()  # Setup SSOT state adapters
        self._setup_animation_scheduler()  # Setup unified animation scheduler

        # AFTER ALL MANAGERS AND UI ARE CREATED AND CONNECTED
        if self.skeleton_manager and self.ik_manager:
            logging.info(
                f"AutomataDesigner.__init__ (END): Linking SkeletonManager (id:{id(self.skeleton_manager)}) to IKManager (id:{id(self.ik_manager)})."
            )
            self.ik_manager.set_skeleton_manager(self.skeleton_manager)
            ik_sm_ref = self.ik_manager.skeleton_manager_ref
            logging.info(
                f"AutomataDesigner.__init__ (END): IKManager's skeleton_manager_ref is now id:{id(ik_sm_ref) if ik_sm_ref else 'None'}. Type: {type(ik_sm_ref)}"
            )
            if ik_sm_ref is None:
                logging.error(
                    "AutomataDesigner.__init__ (END): CRITICAL - IKManager.skeleton_manager_ref is None immediately after setting!"
                )
            elif ik_sm_ref != self.skeleton_manager:
                logging.error(
                    f"AutomataDesigner.__init__ (END): CRITICAL - IKManager.skeleton_manager_ref (id:{id(ik_sm_ref)}) MISMATCHES self.skeleton_manager (id:{id(self.skeleton_manager)})!"
                )
        else:
            logging.error(
                "AutomataDesigner.__init__ (END): Critical error - SkeletonManager or IKManager not initialized before linking."
            )

        # Setup status bar
        # if self.experiment_mode:
        #     # Add permanent experiment indicator to status bar
        #     experiment_label = QLabel("🧪 Experiment")
        #     experiment_label.setStyleSheet("""
        #         QLabel {
        #             color: #1982c4;
        #             font-weight: bold;
        #             padding: 2px 8px;
        #         }
        #     """)
        #     self.statusBar().addPermanentWidget(experiment_label)

        # if self.editing_mode:
        #     # Add permanent editing mode indicator to status bar
        #     editing_label = QLabel("✏️ Editing Mode")
        #     editing_label.setStyleSheet("""
        #         QLabel {
        #             color: #e63946;
        #             font-weight: bold;
        #             padding: 2px 8px;
        #         }
        #     """)
        #     self.statusBar().addPermanentWidget(editing_label)

        self.statusBar().showMessage("Ready")
        logging.info("AutomataDesigner initialized.")

    def set_updater(self, updater):
        """Set the auto-updater instance"""
        self.updater = updater
        logging.info("Auto-updater set in main window")

        # Update the action manager with updater
        if hasattr(self.action_manager, "set_updater"):
            self.action_manager.set_updater(updater)

    def check_for_updates(self):
        """Check for updates manually"""
        if self.updater:
            self.updater.check_for_updates(show_ui=True)
        else:
            QMessageBox.information(
                self, "Updates", "Auto-updater is not available on this platform."
            )

    # --- UI Initialization ---

    def _init_ui(self):
        """Sets up the main user interface layout and widgets."""
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        self.tab_widget = QTabWidget()
        self.tab_widget.setObjectName("mainTabWidget")
        self.tab_widget.setUsesScrollButtons(True)
        self.tab_widget.setElideMode(Qt.TextElideMode.ElideNone)
        main_layout.addWidget(self.tab_widget)

        # --- Tab 0: Landing Page ---
        self.landing_tab = LandingTab(self, experiment_mode=self.experiment_mode)
        self.landing_tab.setObjectName("tab_welcome")
        welcome_title = "1. Welcome" if self.experiment_mode else "Welcome"
        self.tab_widget.addTab(self.landing_tab, welcome_title)

        # --- Tab 1: Image Processing ---
        self.image_proc_tab = ImageProcessingTab(self, editing_mode=self.editing_mode)
        self.image_proc_tab.setObjectName("tab_character_selection")
        character_title = (
            "2. Character Selection" if self.experiment_mode else "Character Selection"
        )
        self.tab_widget.addTab(self.image_proc_tab, character_title)

        # --- Tab 2: Editor & Simulation ---
        self.editor_tab = EditorTab(self)
        self.editor_tab.setObjectName("tab_path_editor")
        path_title = "3. Path Editor" if self.experiment_mode else "Path Editor"
        self.tab_widget.addTab(self.editor_tab, path_title)

        # --- Tab 3: Mechanism Design ---
        self.mechanism_design_tab = MechanismDesignTab(self)
        self.mechanism_design_tab.setObjectName("tab_mechanism_design")
        mechanism_title = "4. Mechanism Design" if self.experiment_mode else "Mechanism Design"
        self.tab_widget.addTab(self.mechanism_design_tab, mechanism_title)

        # --- Tab 4: Mechanism Foundry ---
        self.mechanism_foundry_tab = MechanismFoundryView(self)
        self.mechanism_foundry_tab.setObjectName("tab_mechanism_foundry")
        foundry_title = "5. Mechanism Foundry" if self.experiment_mode else "Mechanism Foundry"
        self.tab_widget.addTab(self.mechanism_foundry_tab, foundry_title)

        # --- Tab 5: Lab ---
        self.lab_tab = LabTab(self)
        self.lab_tab.setObjectName("tab_lab")
        lab_title = "6. Lab" if self.experiment_mode else "Lab"
        self.tab_widget.addTab(self.lab_tab, lab_title)

        # --- Tab 6: Options ---
        self.options_tab = OptionsTab(initial_anim_duration=self.ik_manager.animation_duration)
        self.options_tab.setObjectName("tab_options")
        if not self.experiment_mode:
            self.tab_widget.addTab(self.options_tab, "Options")

        # --- Connect Signals from LandingTab ---
        self.landing_tab.image_selected.connect(self._handle_landing_image_selected)

        # --- Connect Signals from ImageProcessingTab ---
        self.image_proc_tab.parts_generated.connect(self.handle_parts_generated_from_tab)
        self.image_proc_tab.skeleton_updated.connect(self.handle_skeleton_updated_from_tab)
        self.image_proc_tab.request_editor_tab_switch.connect(self.switch_to_editor_tab)

        # Character assignment from ImageProcessing is image-driven.
        # (Legacy preset signal remains available for backward compatibility.)

        # --- Connect Signals from EditorTab ---
        self.editor_tab.request_play_simulation.connect(self.ik_manager.start_animation)
        self.editor_tab.request_stop_simulation.connect(self.ik_manager.stop_animation)
        self.editor_tab.request_reset_simulation.connect(self.ik_manager.reset_animation_state)
        self.editor_tab.request_generate_blueprint.connect(self.generate_blueprint_impl)
        self.editor_tab.request_save_alignment.connect(self.save_character_alignment_impl)
        # Connect path data sharing between editor and mechanism design tabs
        # NOTE: path_data_changed → set_path_data_from_editor now handled by SSOT adapters
        # EditorTabAdapter catches path changes, stores in ProjectStateManager
        # MechanismDesignTabAdapter listens to paths_changed, forwards to tab

        # --- Connect Signals from MechanismDesignTab ---
        self.mechanism_design_tab.request_generate_mechanism.connect(
            self.handle_generate_mechanism_request
        )
        self.mechanism_design_tab.request_generate_blueprint.connect(self.generate_blueprint_impl)

        # --- Connect Signals from MechanismFoundryTab ---
        self.mechanism_foundry_tab.export_to_design_requested.connect(
            self._handle_foundry_export_to_mechanism_tab
        )

        # --- Bidirectional Sync: Foundry ↔ Design Tab ---
        # Foundry → Design Tab: Parameter changes
        self.mechanism_foundry_tab.mechanism_parameters_changed.connect(
            self.mechanism_design_tab.update_from_foundry
        )
        # Design Tab → Foundry: Parameter changes
        self.mechanism_design_tab.mechanism_parameters_changed.connect(
            self.mechanism_foundry_tab.update_from_design_tab
        )

        # --- Connect Signals from OptionsTab ---
        self.options_tab.animationDurationChanged.connect(self.ik_manager.set_animation_duration)
        if hasattr(self.options_tab, "timingProfileChanged") and hasattr(
            self.ik_manager, "set_timing_profile"
        ):
            self.options_tab.timingProfileChanged.connect(self.ik_manager.set_timing_profile)
        self.options_tab.themeChanged.connect(self._apply_theme)
        self.options_tab.toolbarVisibilityChanged.connect(self._toggle_toolbar_visibility)
        self.options_tab.partPropertiesVisibilityChanged.connect(
            self._toggle_part_properties_visibility
        )
        self.options_tab.partPropertiesVisibilityChanged.connect(
            self.editor_tab.toggle_part_properties_panel_visibility
        )
        self.options_tab.setting_changed.connect(self._handle_option_change)
        # Connect advanced processing visibility toggle
        if hasattr(self.options_tab, "advancedProcessingVisibilityChanged") and hasattr(
            self.image_proc_tab, "_toggle_detailed_processing_visibility"
        ):
            self.options_tab.advancedProcessingVisibilityChanged.connect(
                self.image_proc_tab._toggle_detailed_processing_visibility
            )
        # Connect unit changed signal (assuming OptionsTab will have it)
        if hasattr(self.options_tab, "unitChanged"):
            self.options_tab.unitChanged.connect(self._handle_unit_changed)
        else:
            logging.warning(
                "MainWindow: OptionsTab does not have unitChanged signal. Unit selection may not work."
            )

        # Physics snap mode from OptionsTab → ParametricEditingManager
        if hasattr(self.options_tab, "physicsSnapModeChanged"):
            try:
                setter = getattr(
                    self.mechanism_design_tab.parametric_manager, "set_physics_snap_mode", None
                )
                if callable(setter):
                    self.options_tab.physicsSnapModeChanged.connect(setter)
                    # Initialize UI to manager's default
                    if hasattr(self.options_tab, "set_physics_snap_mode_input"):
                        self.options_tab.set_physics_snap_mode_input(
                            self.mechanism_design_tab.parametric_manager.physics_snap_mode
                        )
            except Exception:
                logging.exception("Failed to connect physics snap mode option")

        if hasattr(self.options_tab, "set_grid_system_input"):
            self.options_tab.set_grid_system_input(
                self._grid_system_enabled,
                self._grid_cell_size_cm,
            )
        self._apply_grid_system_settings()

        # Connect menu actions using ActionManager
        self.action_manager.connect_action("new_project", self.new_project_ssot)
        self.action_manager.connect_action("load_parts", self.load_parts_dialog)
        self.action_manager.connect_action("save_project", self.save_project_dialog)
        self.action_manager.connect_action("exit", self.close)
        self.action_manager.connect_action(
            "zoom_in",
            lambda: (
                self.editor_tab.editor_view.zoom_in()  # Call on EditorTab's view
                if self.tab_widget.currentWidget() == self.editor_tab
                else None
            ),  # Add a default None if no active tab matches known views
        )
        self.action_manager.connect_action(
            "zoom_out",
            lambda: (
                self.editor_tab.editor_view.zoom_out()  # Call on EditorTab's view
                if self.tab_widget.currentWidget() == self.editor_tab
                else None
            ),  # Add a default None
        )
        self.action_manager.connect_action(
            "zoom_fit",
            lambda: (
                self.editor_tab.editor_view.zoom_to_fit()  # Call on EditorTab's view
                if self.tab_widget.currentWidget() == self.editor_tab
                else None
            ),  # Add a default None
        )
        self.action_manager.connect_action(
            "reset_view",
            lambda: (
                self.editor_tab.editor_view.reset_view()  # Call on EditorTab's view
                if self.tab_widget.currentWidget() == self.editor_tab
                else None
            ),
        )
        # Connect undo/redo to SSOT ProjectStateManager (Ctrl+Z, Ctrl+Y)
        self.action_manager.connect_action("undo", self.undo_ssot)
        self.action_manager.connect_action("redo", self.redo_ssot)
        self.action_manager.connect_action("about", self.show_about_dialog)
        self.action_manager.connect_action("save_workspace_layout", self.save_workspace_layout)
        self.action_manager.connect_action("restore_workspace_layout", self.restore_workspace_layout)
        self.action_manager.connect_action("reset_workspace_layout", self.reset_workspace_layout)
        self.action_manager.connect_action(
            "toggle_workflow_navigator",
            lambda checked=False: self.toggle_workflow_navigator(bool(checked)),
        )
        self.action_manager.connect_action(
            "workflow_mode_flexible",
            lambda checked=False: self.set_workflow_mode("flexible") if checked else None,
        )
        self.action_manager.connect_action(
            "workflow_mode_guided",
            lambda checked=False: self.set_workflow_mode("guided") if checked else None,
        )
        self.action_manager.connect_action(
            "capture_workflow_sequence", self.capture_workflow_from_tab_order
        )
        self.action_manager.connect_action("reset_workflow_sequence", self.reset_workflow_sequence)

        # Test Anchors Button Connection (This button is now in EditorTab, EditorTab should handle its toggled signal)
        # self.toggle_anchors_btn.toggled.connect(self._toggle_test_anchors_visibility)

        # Tab switching is handled by TabOrchestrator (initialized in _init_tab_orchestrator)

    def _load_custom_fonts(self):
        """Loads custom application fonts.

        Placeholder method. Implement font loading logic here.
        """
        logging.info("Placeholder: _load_custom_fonts() called.")
        # Example: Add font loading logic using QFontDatabase
        # font_db = QFontDatabase()
        # font_id = font_db.addApplicationFont(":/fonts/my_custom_font.ttf")
        # if font_id == -1:
        #     logging.warning("Failed to load custom font.")
        # else:
        #     font_families = QFontDatabase.applicationFontFamilies(font_id)
        #     if font_families:
        #         logging.info(f"Loaded custom font: {font_families[0]}")

    def _init_tab_orchestrator(self) -> None:
        """
        Initialize the TabOrchestrator for tab lifecycle management.

        This component handles:
        - Tab switch events
        - Camera state sharing between tabs
        - Tab activation/deactivation lifecycle
        - Initial zoom on first tab visit

        Extracted from _on_tab_changed to reduce god class complexity.
        """
        self._tab_orchestrator = TabOrchestrator(self.tab_widget, parent=self)

        # Configure callbacks for external state access
        self._tab_orchestrator.configure_callbacks(
            get_status_bar=lambda: self.statusBar(),
            get_skeleton_manager=lambda: self.skeleton_manager,
            on_tab_activated=self._on_tab_activated_callback,
        )

        # Set tabs that share camera state
        shared_tabs = [self.editor_tab, self.mechanism_design_tab]
        self._tab_orchestrator.set_shared_view_tabs(shared_tabs)

        logging.info("TabOrchestrator initialized for tab lifecycle management")

    def _init_workspace_and_workflow(self) -> None:
        """
        Initialize workspace customization (dock/tab layout) and workflow state guidance.
        """
        self._workspace_layout_manager = WorkspaceLayoutManager(
            self, self.tab_widget, parent=self
        )
        self._workspace_layout_manager.initialize()

        default_sequence = self._workspace_layout_manager.get_current_tab_order()
        self._workflow_state_machine = WorkflowStateMachine(
            default_sequence=default_sequence,
            parent=self,
        )
        self._workflow_state_machine.recommendation_changed.connect(
            self._on_workflow_recommendation_changed
        )
        self._workflow_state_machine.mode_changed.connect(self._on_workflow_mode_changed)
        self._workflow_state_machine.sequence_changed.connect(
            self._on_workflow_sequence_changed
        )

        workflow_dock = self._workspace_layout_manager.navigator_dock
        toggle_action = self.action_manager.get_action("toggle_workflow_navigator")
        if workflow_dock and toggle_action:
            workflow_dock.visibilityChanged.connect(toggle_action.setChecked)
            toggle_action.setChecked(workflow_dock.isVisible())

        self._sync_workflow_mode_actions()
        self._mark_workflow_tab_visited(self.tab_widget.currentWidget())
        self._announce_workflow_status()

    def _on_tab_activated_callback(self, current_tab: QWidget, index: int) -> None:
        """
        Callback invoked by TabOrchestrator after a tab is activated.

        Handles mechanism-specific data synchronization and any custom
        post-activation logic not covered by the orchestrator.

        Args:
            current_tab: The newly activated tab widget
            index: The tab index
        """
        # Data synchronization for mechanism tab
        if current_tab == self.mechanism_design_tab:
            logging.info("MechanismDesignTab: Now uses editor tab data directly - no sync needed")

            # Sync skeleton data if needed
            if hasattr(self.skeleton_manager, "get_current_skeleton_data") and (
                not hasattr(self.mechanism_design_tab, "_initial_skeleton_data_cache")
                or not self.mechanism_design_tab._initial_skeleton_data_cache
            ):
                current_skeleton = self.skeleton_manager.get_current_skeleton_data()
                if current_skeleton:
                    self.mechanism_design_tab.cache_initial_skeleton(current_skeleton)
                    logging.info("MechanismDesignTab: Synchronized skeleton data on tab switch")

        self._mark_workflow_tab_visited(current_tab)

    def _get_tab_id(self, tab: QWidget | None) -> str | None:
        if tab is None:
            return None
        tab_id = tab.objectName()
        if tab_id:
            return tab_id
        return None

    def _tab_label_lookup(self) -> dict[str, str]:
        lookup: dict[str, str] = {}
        for index in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(index)
            tab_id = self._get_tab_id(tab)
            if tab_id:
                lookup[tab_id] = self.tab_widget.tabText(index)
        return lookup

    def _mark_workflow_tab_visited(self, tab: QWidget | None) -> None:
        if not self._workflow_state_machine:
            return
        tab_id = self._get_tab_id(tab)
        self._workflow_state_machine.on_tab_activated(tab_id)
        self._announce_workflow_status()

    def _mark_workflow_stage_complete(self, tab_id: str | None) -> None:
        if not self._workflow_state_machine:
            return
        self._workflow_state_machine.mark_stage_complete(tab_id)
        self._announce_workflow_status()

    def _announce_workflow_status(self) -> None:
        if not self._workflow_state_machine:
            return
        status = self._workflow_state_machine.build_status_message(self._tab_label_lookup())
        self.statusBar().showMessage(status, 3500)

    @pyqtSlot(str)
    def _on_workflow_recommendation_changed(self, _tab_id: str) -> None:
        self._announce_workflow_status()

    @pyqtSlot(str)
    def _on_workflow_mode_changed(self, _mode: str) -> None:
        self._sync_workflow_mode_actions()
        self._announce_workflow_status()

    @pyqtSlot(list)
    def _on_workflow_sequence_changed(self, _sequence: list) -> None:
        self._announce_workflow_status()

    def _sync_workflow_mode_actions(self) -> None:
        if not self._workflow_state_machine:
            return
        flexible_action = self.action_manager.get_action("workflow_mode_flexible")
        guided_action = self.action_manager.get_action("workflow_mode_guided")
        is_flexible = self._workflow_state_machine.mode.value == "flexible"
        if flexible_action:
            flexible_action.setChecked(is_flexible)
        if guided_action:
            guided_action.setChecked(not is_flexible)

    @pyqtSlot()
    def save_workspace_layout(self) -> None:
        if self._workspace_layout_manager:
            self._workspace_layout_manager.save_workspace_layout()
            self.statusBar().showMessage("Workspace layout saved.", 3000)

    @pyqtSlot()
    def restore_workspace_layout(self) -> None:
        if self._workspace_layout_manager:
            self._workspace_layout_manager.restore_workspace_layout()
            self._workspace_layout_manager.refresh_navigator_items()
            self.statusBar().showMessage("Workspace layout restored.", 3000)

    @pyqtSlot()
    def reset_workspace_layout(self) -> None:
        if self._workspace_layout_manager:
            self._workspace_layout_manager.reset_workspace_layout()
            self.statusBar().showMessage("Workspace layout reset to defaults.", 3000)

    @pyqtSlot(bool)
    def toggle_workflow_navigator(self, visible: bool) -> None:
        if (
            self._workspace_layout_manager
            and self._workspace_layout_manager.navigator_dock is not None
        ):
            self._workspace_layout_manager.navigator_dock.setVisible(visible)

    def set_workflow_mode(self, mode: str) -> None:
        if not self._workflow_state_machine:
            return
        self._workflow_state_machine.set_mode(mode)
        self._sync_workflow_mode_actions()

    @pyqtSlot()
    def capture_workflow_from_tab_order(self) -> None:
        if not self._workflow_state_machine or not self._workspace_layout_manager:
            return
        sequence = self._workspace_layout_manager.get_current_tab_order()
        self._workflow_state_machine.capture_sequence(sequence)
        self.statusBar().showMessage("Captured current tab order as workflow sequence.", 3000)

    @pyqtSlot()
    def reset_workflow_sequence(self) -> None:
        if not self._workflow_state_machine:
            return
        self._workflow_state_machine.reset_sequence()
        self.statusBar().showMessage("Workflow sequence reset to defaults.", 3000)


    # --- Menu Creation ---
    def _create_menus(self):
        """Creates the main application menus using the ActionManager."""
        menubar = self.menuBar()
        self.action_manager.setup_menus(menubar)

    # --- Toolbar Creation ---
    def _create_toolbar(self):
        """Creates the main application toolbar using the ActionManager."""
        self.main_toolbar = QToolBar("Main Toolbar")
        self.main_toolbar.setObjectName("mainToolbar")
        self.main_toolbar.setMovable(False)

        # Setup toolbar using the action manager
        self.action_manager.setup_toolbar(self.main_toolbar)

        # Add to main window and hide by default
        self.addToolBar(self.main_toolbar)
        self.main_toolbar.hide()

    # --- Tab Management ---
    # Tab switching is now handled by TabOrchestrator (see _init_tab_orchestrator)
    # The _on_tab_activated_callback method handles any custom post-activation logic

    # --- New Slots for ImageProcessingTab Signals ---
    @pyqtSlot(dict, str)
    def handle_parts_generated_from_tab(
        self, annotation_results: dict, final_bpe_char_dir_str: str
    ):
        """Handles the parts_generated signal from ImageProcessingTab."""
        logging.info(
            f"MainWindow: Received parts_generated. Annotation results output_dir: {annotation_results.get('output_dir')}, Final BPE dir: {final_bpe_char_dir_str}"
        )

        parts_info_json_path = Path(final_bpe_char_dir_str) / "parts_info.json"
        source_char_cfg_path_str = annotation_results.get("char_cfg_path")

        if not source_char_cfg_path_str:
            logging.error(
                "handle_parts_generated_from_tab: 'char_cfg_path' not found in annotation_results."
            )
            QMessageBox.critical(self, "Error", "char_cfg.yaml path not found in annotation data.")
            return

        source_char_cfg_path = Path(source_char_cfg_path_str)
        dest_char_cfg_path = Path(final_bpe_char_dir_str) / "char_cfg.yaml"

        if source_char_cfg_path.exists():
            try:
                import shutil

                if source_char_cfg_path.resolve() != dest_char_cfg_path.resolve():
                    shutil.copy2(source_char_cfg_path, dest_char_cfg_path)
                    logging.info(
                        f"Copied {source_char_cfg_path} to {dest_char_cfg_path} for ProjectDataManager."
                    )
                else:
                    logging.info(
                        "Source char_cfg.yaml already in target directory, skipping copy."
                    )

                # texture.png is no longer copied as it's not used as an atlas.
                # Individual part PNGs/SVGs are expected in final_bpe_char_dir_str.

                source_mask_path_str = annotation_results.get("mask_path")
                if source_mask_path_str:
                    source_mask_path = Path(source_mask_path_str)
                    dest_mask_path = Path(final_bpe_char_dir_str) / "mask.png"
                    if source_mask_path.exists():
                        if source_mask_path.resolve() != dest_mask_path.resolve():
                            shutil.copy2(source_mask_path, dest_mask_path)
                            logging.info(f"Copied {source_mask_path} to {dest_mask_path}.")
                        else:
                            logging.info("Source mask.png already in target directory, skipping copy.")
                    else:
                        logging.warning(
                            f"Source mask.png not found at {source_mask_path}, cannot copy."
                        )
                else:
                    logging.warning("'mask_path' not in annotation_results, cannot copy mask.png.")

            except Exception as e:
                logging.error(f"Failed to copy files to BPE output dir: {e}", exc_info=True)
                QMessageBox.warning(
                    self,
                    "File Copy Error",
                    f"Could not copy necessary files for project loading: {e}",
                )
        else:
            logging.warning(
                f"Source char_cfg.yaml not found at {source_char_cfg_path}, cannot copy to BPE output dir. ProjectDataManager might fail to load skeleton."
            )

        if not parts_info_json_path.exists():
            logging.error(
                f"CRITICAL ERROR IN MAINWINDOW: parts_info.json path derived as {parts_info_json_path} but file does not exist."
            )
            QMessageBox.critical(
                self,
                "Project Load Error",
                f"Internal error: Could not locate parts_info.json at {parts_info_json_path}.",
            )
            return

        logging.info(
            f"Attempting to load project data from parts_info.json: {parts_info_json_path}"
        )

        # Replacement context is only when user is replacing an active dummy-based
        # mechanism session. Plain "Load Image" should not preserve/rebind/scale-to-dummy.
        is_dummy_replacement_session = False
        image_proc_tab = getattr(self, "image_proc_tab", None)
        if (
            image_proc_tab is not None
            and hasattr(image_proc_tab, "_is_dummy_mechanism_design_session")
        ):
            try:
                is_dummy_replacement_session = bool(
                    image_proc_tab._is_dummy_mechanism_design_session()
                )
            except Exception:
                logging.debug(
                    "MainWindow: Failed to evaluate dummy replacement session flag.",
                    exc_info=True,
                )

        if hasattr(self, "mechanism_design_tab") and self.mechanism_design_tab:
            try:
                if is_dummy_replacement_session:
                    self.mechanism_design_tab.prepare_character_rebind()
                else:
                    self.mechanism_design_tab.cancel_character_rebind()
            except Exception:
                logging.debug(
                    "Suppressed exception while updating character rebind state",
                    exc_info=True,
                )

        # Preserve runtime mechanisms/state only for dummy replacement.
        self._suppress_project_data_cleared_ui_once = is_dummy_replacement_session
        self._character_swap_load_in_progress = is_dummy_replacement_session
        self._auto_scale_character_to_dummy_next_load = is_dummy_replacement_session
        # Keep aggressive skeleton/parts bbox reconciliation off for plain Load Image.
        # It is only needed for dummy replacement sessions where we intentionally
        # preserve existing mechanism runtime state and rebind in-place.
        self._force_skeleton_parts_alignment_next_load = is_dummy_replacement_session
        logging.info(
            "MainWindow: parts_generated context resolved (dummy_replacement=%s, preserve_ui=%s, scale_to_dummy=%s, force_skel_align=%s)",
            is_dummy_replacement_session,
            self._suppress_project_data_cleared_ui_once,
            self._auto_scale_character_to_dummy_next_load,
            self._force_skeleton_parts_alignment_next_load,
        )
        success = self.project_data_manager.load_project_from_file(str(parts_info_json_path))

        if success:
            self.statusBar().showMessage("Part data loaded successfully.", 3000)
            self.current_temp_char_dir = Path(final_bpe_char_dir_str)
            logging.info(
                f"MainWindow: Project loaded. Updated current_temp_char_dir to BPE output: {self.current_temp_char_dir}"
            )
            self._mark_workflow_stage_complete("tab_character_selection")

        else:
            self._suppress_project_data_cleared_ui_once = False
            self._character_swap_load_in_progress = False
            self._auto_scale_character_to_dummy_next_load = False
            self._force_skeleton_parts_alignment_next_load = False
            self.statusBar().showMessage("Failed to load part data. Check logs.", 5000)
            if hasattr(self, "mechanism_design_tab") and self.mechanism_design_tab:
                try:
                    self.mechanism_design_tab.cancel_character_rebind()
                except Exception:
                    logging.debug(
                        "Suppressed exception while cancelling character rebind",
                        exc_info=True,
                    )

    @pyqtSlot(dict)
    def handle_skeleton_updated_from_tab(self, skeleton_data: dict):
        """Handles the skeleton_updated signal from ImageProcessingTab."""
        logging.info(
            "MainWindow: Received skeleton_updated signal from tab. Forwarding to SkeletonManager."
        )
        # self.skeleton_data = skeleton_data # OLD: MainWindow should not hold its own copy like this
        # self._initialize_new_ik_skeleton_definitions()  # Re-initialize IK system with new skeleton # OLD: This will be triggered by SkeletonManager's update
        # # Notify editor tab if it needs to update its view based on the new skeleton
        # if hasattr(self.editor_tab, "on_skeleton_updated"): # OLD: This will be triggered by SkeletonManager's update
        #     self.editor_tab.on_skeleton_updated(self.skeleton_data)
        # # Also update the image_proc_view if it's showing this skeleton (though ImageProcessingTab manages this primarily)
        # # self.image_proc_view.load_skeleton(self.skeleton_data)

        # NEW: Pass the raw skeleton data from the tab to the SkeletonManager
        # Assuming the data from ImageProcessingTab is in 'animated_drawings' format (char_cfg.yaml like)
        if self.skeleton_manager:
            self.skeleton_manager.load_skeleton_from_dict(
                skeleton_data, source_format="animated_drawings"
            )
        else:
            logging.error("MainWindow: SkeletonManager not available to handle skeleton update.")
            QMessageBox.warning(
                self,
                "Error",
                "SkeletonManager not initialized. Cannot process skeleton.",
            )

    @pyqtSlot(str)
    def _handle_landing_image_selected(self, image_path: str):
        """Handles image selection from the landing tab."""
        logging.info(f"MainWindow: Landing tab selected image: {image_path}")

        if hasattr(self, "image_proc_tab") and self.image_proc_tab is not None:
            # Load the image in the image processing tab
            loaded_successfully = self.image_proc_tab._load_image_from_path(image_path)

            if loaded_successfully:
                # Switch to the image processing tab
                for i in range(self.tab_widget.count()):
                    if self.tab_widget.widget(i) == self.image_proc_tab:
                        self.tab_widget.setCurrentIndex(i)
                        logging.info(
                            f"MainWindow: Switched to Image Processing Tab and loaded {Path(image_path).name}"
                        )
                        self.statusBar().showMessage(f"Loaded: {Path(image_path).name}", 3000)
                        # Ensure detailed processing group is hidden on this specific transition
                        if hasattr(
                            self.image_proc_tab,
                            "_toggle_detailed_processing_visibility",
                        ):
                            self.image_proc_tab._toggle_detailed_processing_visibility(False)
                        break
            else:
                logging.error(
                    f"MainWindow: Failed to load image {image_path} in ImageProcessingTab."
                )
                QMessageBox.warning(
                    self,
                    "Image Load Error",
                    f"Could not load the selected image: {Path(image_path).name}",
                )
        else:
            logging.error("MainWindow: image_proc_tab is not available or not initialized.")
            QMessageBox.critical(self, "Error", "Image Processing Tab is not available.")

    @pyqtSlot()
    def switch_to_editor_tab(self):
        """Switches the main tab widget to the Editor Tab."""
        editor_idx = -1
        for i in range(self.tab_widget.count()):
            if self.tab_widget.widget(i) == self.editor_tab:
                editor_idx = i
                break
        if editor_idx != -1:
            logging.info("Switching to Editor tab by request.")
            self.tab_widget.setCurrentIndex(editor_idx)
            self._mark_workflow_stage_complete("tab_path_editor")
        else:
            logging.warning("Could not find EditorTab to switch to.")

    # --- Styling and Themes ---
    def _apply_theme(self, _theme_name: str):
        """Applies the selected theme (stylesheet) to the application."""
        # ... existing code ...

    def _toggle_toolbar_visibility(self, visible: bool):
        """Toggles the visibility of the main toolbar."""
        if self.main_toolbar:
            self.main_toolbar.setVisible(visible)
            logging.info(f"Main toolbar visibility set to: {visible}")
        else:
            logging.warning("_toggle_toolbar_visibility called but main_toolbar is None.")

    def _toggle_part_properties_visibility(self, visible: bool):
        """Toggles the visibility of the part properties panel in the EditorTab."""
        if hasattr(self, "editor_tab") and self.editor_tab:
            if hasattr(self.editor_tab, "toggle_part_properties_panel_visibility"):
                self.editor_tab.toggle_part_properties_panel_visibility(visible)
                logging.info(f"Part properties panel visibility set to: {visible}")
            else:
                logging.warning(
                    "EditorTab does not have 'toggle_part_properties_panel_visibility' method."
                )
        else:
            logging.warning(
                "_toggle_part_properties_visibility called but editor_tab is not available."
            )

    # --- Project Data Handling ---
    def load_parts_dialog(self):
        """Open a file dialog and load either a full project or legacy parts JSON."""
        state_project_dir = self.project_state_manager.state.project_dir
        if state_project_dir:
            start_dir = str(state_project_dir)
        elif self.project_data_manager.project_dir:
            start_dir = str(self.project_data_manager.project_dir)
        else:
            start_dir = os.path.expanduser("~")

        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Load Project",
            start_dir,
            "Automataii Projects (*.automataii);;JSON files (*.json);;All files (*)",
        )
        if not filepath:
            return

        file_path_obj = Path(filepath)
        if file_path_obj.suffix.lower() == ".automataii":
            self._project_controller.set_status_bar(self.statusBar())
            self._project_controller.load_project(file_path_obj)
            return

        # Fallback: legacy character parts JSON.
        self.project_data_manager.load_project_from_file(filepath)

    def _get_dummy_reference_height_px(self) -> float:
        """Get/calculate reference character height from bundled dummy assets."""
        if self._dummy_reference_height_px is not None:
            return self._dummy_reference_height_px

        candidates: list[Path] = [resolve_path("resources/presets/characters/dummy")]
        module_path = Path(__file__).resolve()
        for parent_idx in (4, 3):
            try:
                candidates.append(
                    module_path.parents[parent_idx]
                    / "resources"
                    / "presets"
                    / "characters"
                    / "dummy"
                )
            except IndexError:
                continue

        for dummy_dir in candidates:
            parts_path = dummy_dir / "parts_info.json"
            if not parts_path.exists():
                continue
            try:
                with open(parts_path, encoding="utf-8") as f:
                    payload = json.load(f)
                parts_payload = payload.get("character", {}).get("parts", {})
                parts_info_dummy: dict[str, Any] = {}
                if isinstance(parts_payload, dict):
                    for part_name, part_dict in parts_payload.items():
                        if not isinstance(part_dict, dict):
                            continue
                        roi = part_dict.get("roi")
                        parts_info_dummy[str(part_name)] = type(
                            "_DummyPartInfo",
                            (),
                            {"roi": roi},
                        )()
                dummy_bbox = _calculate_parts_bbox(parts_info_dummy)
                if dummy_bbox:
                    self._dummy_reference_height_px = max(1.0, dummy_bbox[3] - dummy_bbox[1])
                    return self._dummy_reference_height_px
            except Exception:
                logging.debug(
                    "MainWindow: Failed reading dummy reference parts_info for scale normalization.",
                    exc_info=True,
                )

        self._dummy_reference_height_px = _DEFAULT_DUMMY_REFERENCE_HEIGHT_PX
        return self._dummy_reference_height_px

    def _normalize_character_scale_to_dummy(
        self,
        parts_info: dict[str, PartInfo],
        raw_skeleton_data: list[dict[str, Any]] | None,
    ) -> tuple[dict[str, PartInfo], list[dict[str, Any]] | None, float]:
        """Normalize loaded character size to dummy reference if size diverges too much."""
        if not parts_info:
            return parts_info, raw_skeleton_data, 1.0

        parts_bbox = _calculate_parts_bbox(parts_info)
        skeleton_bbox = _calculate_skeleton_bbox(raw_skeleton_data)

        if (
            parts_bbox
            and isinstance(raw_skeleton_data, list)
            and raw_skeleton_data
            and _align_skeleton_bbox_to_parts_in_place(raw_skeleton_data, parts_bbox)
        ):
            skeleton_bbox = _calculate_skeleton_bbox(raw_skeleton_data)
            logging.info(
                "MainWindow: Pre-aligned skeleton bbox to parts bbox before dummy-scale normalization."
            )

        current_height = 0.0
        if parts_bbox:
            current_height = max(0.0, parts_bbox[3] - parts_bbox[1])
        if current_height <= 1.0 and skeleton_bbox:
            current_height = max(0.0, skeleton_bbox[3] - skeleton_bbox[1])

        if current_height <= 1.0:
            return parts_info, raw_skeleton_data, 1.0

        target_height = max(1.0, self._get_dummy_reference_height_px())
        scale_factor = target_height / current_height

        if _CHARACTER_SCALE_LOWER_RATIO <= scale_factor <= _CHARACTER_SCALE_UPPER_RATIO:
            return parts_info, raw_skeleton_data, 1.0

        scale_factor = max(_CHARACTER_SCALE_MIN, min(_CHARACTER_SCALE_MAX, scale_factor))

        center_bbox = parts_bbox or skeleton_bbox
        if not center_bbox:
            return parts_info, raw_skeleton_data, 1.0
        center = (
            float(center_bbox[0] + center_bbox[2]) * 0.5,
            float(center_bbox[1] + center_bbox[3]) * 0.5,
        )

        _scale_parts_in_place(parts_info, scale_factor, center)
        if isinstance(raw_skeleton_data, list) and raw_skeleton_data:
            _scale_skeleton_raw_in_place(raw_skeleton_data, scale_factor, center)

        logging.info(
            "MainWindow: Normalized character scale to dummy reference (scale=%.3f, current_h=%.1f, target_h=%.1f).",
            scale_factor,
            current_height,
            target_height,
        )
        return parts_info, raw_skeleton_data, scale_factor

    # REFACTORED: The old content of load_parts is now largely in ProjectDataManager.
    # UI updates and manager notifications will be handled by a slot connected to
    # ProjectDataManager.project_data_loaded.

    @pyqtSlot(bool, str, dict)
    def _handle_project_data_loaded(
        self,
        success: bool,
        project_directory_path: str,
        parts_info: dict[str, PartInfo],  # from ProjectDataManager
    ):
        """Handles the project_data_loaded signal from ProjectDataManager."""
        character_swap_load = bool(self._character_swap_load_in_progress)
        self._character_swap_load_in_progress = False
        self._suppress_project_data_cleared_ui_once = False
        if success:
            logging.info(
                f"MainWindow: Project data loaded successfully from {project_directory_path}"
            )
            apply_dummy_scale = bool(self._auto_scale_character_to_dummy_next_load)
            self._auto_scale_character_to_dummy_next_load = False
            force_skeleton_align = bool(
                self.__dict__.get("_force_skeleton_parts_alignment_next_load", False)
            )
            self.__dict__["_force_skeleton_parts_alignment_next_load"] = False

            self.project_dir = Path(
                project_directory_path
            )  # Update project_dir in MainWindow, ensure it's Path

            current_skeleton_data_raw = (
                self.project_data_manager.raw_skeleton_data
            )  # This is List[Dict]

            scale_factor_applied = 1.0
            if apply_dummy_scale:
                parts_info, current_skeleton_data_raw, scale_factor_applied = (
                    self._normalize_character_scale_to_dummy(parts_info, current_skeleton_data_raw)
                )

            apply_alignment_reconcile = bool(apply_dummy_scale or force_skeleton_align)
            parts_upscaled_to_skeleton = False
            if apply_alignment_reconcile and (
                isinstance(current_skeleton_data_raw, list)
                and current_skeleton_data_raw
                and _align_parts_bbox_to_skeleton_in_place(
                    parts_info, current_skeleton_data_raw
                )
            ):
                parts_upscaled_to_skeleton = True
                logging.info(
                    "MainWindow: Upscaled/recentered parts to match skeleton bbox for replacement flow."
                )

            # Reconcile skeleton/parts bbox only during replacement flows.
            # Plain Load Image should keep extractor-produced coordinates untouched.
            parts_bbox = _calculate_visible_parts_bbox(parts_info) or _calculate_parts_bbox(parts_info)
            if apply_alignment_reconcile and (
                (force_skeleton_align or not parts_upscaled_to_skeleton)
                and parts_bbox
                and isinstance(current_skeleton_data_raw, list)
                and current_skeleton_data_raw
                and _align_skeleton_bbox_to_parts_in_place(
                    current_skeleton_data_raw,
                    parts_bbox,
                    force=force_skeleton_align,
                )
            ):
                logging.info(
                    "MainWindow: Reconciled skeleton/parts bbox before scene load (force=%s).",
                    force_skeleton_align,
                )

            # Clear stale cached skeleton in tabs before applying new parts.
            # This prevents previous dummy skeleton anchors from being reused while new data loads.
            if hasattr(self.editor_tab, "cache_initial_skeleton"):
                self.editor_tab.cache_initial_skeleton(None)
            if hasattr(self.mechanism_design_tab, "cache_initial_skeleton"):
                self.mechanism_design_tab.cache_initial_skeleton(None)

            # Pass PartInfo data to EditorTab. It no longer needs texture_atlas_pixmap.
            self.editor_tab.set_parts_data(parts_info)

            # Pass PartInfo data to MechanismDesignTab as well
            self.mechanism_design_tab.set_parts_data(parts_info)

            # Update other tabs/managers as needed
            if hasattr(self.ik_manager, "set_project_parts_data"):
                self.ik_manager.set_project_parts_data(parts_info)

            if current_skeleton_data_raw:
                # SkeletonManager loads from raw, then emits standardized data
                skeleton_loaded = self.skeleton_manager.load_skeleton_from_project_data(
                    current_skeleton_data_raw, parts_info
                )
                if not skeleton_loaded:
                    logging.warning(
                        "MainWindow: Skeleton load failed for project %s; clearing stale skeleton state.",
                        project_directory_path,
                    )
                    self.skeleton_manager.clear_data()
                # The actual caching in EditorTab happens when skeleton_manager.skeleton_updated is emitted
                # and handled by _on_skeleton_manager_updated, which then calls editor_tab.cache_initial_skeleton.
            else:
                # Fallback: if parts load succeeded but skeleton list was omitted, try char_cfg.yaml
                # in the same directory before clearing skeleton state.
                fallback_loaded = False
                fallback_char_cfg = Path(project_directory_path) / "char_cfg.yaml"
                if fallback_char_cfg.exists():
                    try:
                        with open(fallback_char_cfg, encoding="utf-8") as f:
                            fallback_payload = yaml.safe_load(f)
                        if (
                            isinstance(fallback_payload, dict)
                            and isinstance(fallback_payload.get("skeleton"), list)
                            and fallback_payload.get("skeleton")
                        ):
                            if apply_dummy_scale and scale_factor_applied != 1.0:
                                skeleton_list = fallback_payload.get("skeleton")
                                fallback_bbox = _calculate_skeleton_bbox(skeleton_list)
                                if fallback_bbox:
                                    fallback_center = (
                                        float(fallback_bbox[0] + fallback_bbox[2]) * 0.5,
                                        float(fallback_bbox[1] + fallback_bbox[3]) * 0.5,
                                    )
                                    _scale_skeleton_raw_in_place(
                                        skeleton_list,
                                        scale_factor_applied,
                                        fallback_center,
                                    )
                            fallback_loaded = self.skeleton_manager.load_skeleton_from_dict(
                                fallback_payload,
                                source_format="animated_drawings",
                            )
                            if fallback_loaded:
                                logging.info(
                                    "MainWindow: Loaded skeleton from fallback char_cfg.yaml at %s",
                                    fallback_char_cfg,
                                )
                    except Exception:
                        logging.exception(
                            "MainWindow: Failed to load fallback char_cfg.yaml for skeleton"
                        )

                if not fallback_loaded:
                    self.skeleton_manager.clear_data()  # Will emit skeleton_updated(None)
                    if hasattr(self.editor_tab, "cache_initial_skeleton"):
                        self.editor_tab.cache_initial_skeleton(
                            None
                        )  # Ensure cache is cleared if no skeleton

            self.image_proc_tab.on_parts_loaded_in_editor(True)

            if apply_dummy_scale and scale_factor_applied != 1.0:
                self.statusBar().showMessage(
                    f"Project loaded: {project_directory_path} (scaled {scale_factor_applied:.2f}x to dummy baseline)."
                )
            else:
                self.statusBar().showMessage(f"Project loaded: {project_directory_path}")
            self.action_manager.update_actions_for_project_state(True)
            # Mirror loaded runtime data into SSOT so Save Project captures complete state.
            self._sync_runtime_state_to_ssot(mark_saved=False)
            self._mark_workflow_stage_complete("tab_character_selection")

            if parts_info:
                logging.info(
                    f"MainWindow: Project and parts data ({len(parts_info)} parts) loaded. Switching to editor tab if needed."
                )
                if self.tab_widget.currentWidget() != self.editor_tab:
                    self.switch_to_editor_tab()
            else:
                logging.info(
                    "MainWindow: Project loaded, but no specific parts data found in parts_info dict."
                )

        else:
            logging.error(f"MainWindow: Project loading failed from {project_directory_path}")
            self._auto_scale_character_to_dummy_next_load = False
            self._force_skeleton_parts_alignment_next_load = False
            if hasattr(self, "mechanism_design_tab") and self.mechanism_design_tab:
                try:
                    self.mechanism_design_tab.cancel_character_rebind()
                except Exception:
                    logging.debug(
                        "Suppressed exception while cancelling character rebind",
                        exc_info=True,
                    )
            if not character_swap_load:
                self._clear_ui_for_failed_load()
            QMessageBox.critical(
                self,
                "Load Project Error",
                f"Failed to load project from {project_directory_path}.",
            )
            if character_swap_load:
                self.statusBar().showMessage(
                    "Character assignment failed. Keeping previous mechanism/character state.",
                    5000,
                )
            else:
                self.statusBar().showMessage("Project loading failed.")
                self.action_manager.update_actions_for_project_state(False)

    def _clear_ui_for_failed_load(self):
        """Helper to clear relevant UI parts when project loading fails after an attempt."""
        # This is similar to clear_project_data's UI impact but more targeted for a failed load.
        if hasattr(self, "editor_tab") and self.editor_tab:
            self.editor_tab.clear_editor_content()  # EditorTab now clears its own scene

        # Clear mechanism design tab as well
        if hasattr(self, "mechanism_design_tab") and self.mechanism_design_tab:
            self.mechanism_design_tab.clear_mechanism_data()

        # self.image_proc_tab.clear_display() # Assuming ImageProcessingTab has a method to clear its display
        if hasattr(self.image_proc_tab, "clear_display_and_data"):  # More robust check
            self.image_proc_tab.clear_display_and_data()

        self.skeleton_manager.clear_data()
        if self.ik_manager:
            self.ik_manager.reset_all_ik_systems_and_data()
        logging.info("UI cleared due to failed project load.")

    @pyqtSlot()
    def _handle_project_data_cleared(self):
        """Handles the project_data_cleared signal from ProjectDataManager."""
        if self._suppress_project_data_cleared_ui_once:
            logging.info(
                "MainWindow: Suppressing project_data_cleared UI reset for in-place character replacement."
            )
            return

        logging.info("MainWindow: Handling project data cleared signal.")
        self.editor_tab.clear_editor_content()  # This will also clear EditorTab's _initial_skeleton_data_cache
        self.mechanism_design_tab.clear_mechanism_data()  # Clear mechanism design tab
        self.skeleton_manager.clear_data()  # This will emit skeleton_updated with None
        if self.ik_manager:
            self.ik_manager.reset_all_ik_systems_and_data()  # Use the new method name
        self.project_state_manager.new_project()
        self.action_manager.update_actions_for_project_state(False)
        self.statusBar().showMessage("Project data cleared.")
        # Any other UI elements that need to be reset when project is cleared

    def save_project_dialog(self):
        """Save a full project snapshot (state + assets) via SSOT serializer."""
        self._sync_runtime_state_to_ssot(mark_saved=False)
        self._project_controller.set_status_bar(self.statusBar())
        self._project_controller.save_project()

    def _sync_runtime_state_to_ssot(self, mark_saved: bool = False) -> None:
        """
        Snapshot current runtime tab state into ProjectStateManager.

        This keeps edits temporary in-memory until explicit Save, and guarantees
        the serializer captures the latest UI state and generated outcomes.
        """
        try:
            self._runtime_to_ssot_sync_in_progress = True
            parts = self._collect_parts_for_state()
            skeleton = self._collect_skeleton_for_state()
            paths = self._collect_paths_for_state()
            mechanisms = self._collect_mechanisms_for_state()

            project_dir = (
                self.project_data_manager.project_dir
                or self.project_state_manager.state.project_dir
                or getattr(self, "current_temp_char_dir", None)
            )

            image_path = None
            if getattr(self.image_proc_tab, "input_image_path", None):
                image_path = Path(self.image_proc_tab.input_image_path)
            elif self.project_state_manager.state.image_path is not None:
                image_path = self.project_state_manager.state.image_path

            self.project_state_manager.begin_batch()
            try:
                self.project_state_manager.load_parts(parts)
                if skeleton is not None:
                    self.project_state_manager.load_skeleton(skeleton)
                else:
                    self.project_state_manager.clear_skeleton()
                self.project_state_manager.load_paths(paths)
                self.project_state_manager.load_mechanisms(mechanisms)
                self.project_state_manager.set_project_dir(Path(project_dir) if project_dir else None)
                self.project_state_manager.set_image_path(image_path)
            finally:
                self.project_state_manager.end_batch()

            if mark_saved:
                self.project_state_manager.mark_saved()

            has_project_content = bool(parts or skeleton or paths or mechanisms)
            self.action_manager.update_actions_for_project_state(has_project_content)
        except Exception:
            logging.exception("Failed to sync runtime state to SSOT snapshot")
        finally:
            self._runtime_to_ssot_sync_in_progress = False

    def _collect_parts_for_state(self) -> dict[str, PartData]:
        """Collect parts from runtime tabs/managers into immutable PartData models."""
        source_parts: dict[str, Any] = {}
        if hasattr(self, "editor_tab") and self.editor_tab:
            source_parts = getattr(self.editor_tab, "current_parts_info", {}) or {}
        if not source_parts:
            source_parts = self.project_data_manager.get_current_parts_data() or {}

        project_dir = self.project_data_manager.project_dir
        parts: dict[str, PartData] = {}

        for part_name, part_info in source_parts.items():
            try:
                roi_raw = list(getattr(part_info, "roi", []) or [])
                while len(roi_raw) < 4:
                    roi_raw.append(0.0)
                roi = (
                    float(roi_raw[0]),
                    float(roi_raw[1]),
                    float(roi_raw[2]),
                    float(roi_raw[3]),
                )

                image_path = str(getattr(part_info, "image_path", "") or "")
                if image_path and not Path(image_path).is_absolute() and project_dir is not None:
                    image_path = str((project_dir / image_path).resolve())

                local_pivot_raw = getattr(part_info, "local_pivot_offset", None)
                local_pivot = None
                if isinstance(local_pivot_raw, list | tuple) and len(local_pivot_raw) >= 2:
                    local_pivot = (float(local_pivot_raw[0]), float(local_pivot_raw[1]))

                parts[str(part_name)] = PartData(
                    name=str(part_name),
                    texture_path=image_path,
                    mask_path=image_path,
                    anchor_joint=str(getattr(part_info, "anchor_joint_id", "") or "root"),
                    transform=Transform(x=roi[0], y=roi[1], rotation=0.0, scale=1.0),
                    z_index=int(float(getattr(part_info, "z_value", 0.0) or 0.0)),
                    roi=roi,
                    fill_color=str(
                        getattr(part_info, "fill_color", "rgba(128,128,128,0.5)")
                        or "rgba(128,128,128,0.5)"
                    ),
                    fixed=bool(getattr(part_info, "fixed", False)),
                    opacity=float(getattr(part_info, "opacity", 1.0) or 1.0),
                    group=getattr(part_info, "group", None),
                    original_svg_path=getattr(part_info, "original_svg_path", None),
                    enhanced_svg_path=getattr(part_info, "enhanced_svg_path", None),
                    effective_bbox_offset_x=float(
                        getattr(part_info, "effective_bbox_offset_x", 0.0) or 0.0
                    ),
                    effective_bbox_offset_y=float(
                        getattr(part_info, "effective_bbox_offset_y", 0.0) or 0.0
                    ),
                    show_anchor=bool(getattr(part_info, "show_anchor", False)),
                    local_pivot_offset=local_pivot,
                )
            except Exception:
                logging.exception("Failed to snapshot part '%s' into SSOT", part_name)

        return parts

    def _collect_skeleton_for_state(self) -> SkeletonData | None:
        """Collect current standardized skeleton into SkeletonData."""
        if not self.skeleton_manager:
            return None

        skeleton_dict = self.skeleton_manager.get_current_skeleton_data()
        if not skeleton_dict:
            return None

        raw_joints = skeleton_dict.get("joints", {})
        if not isinstance(raw_joints, dict) or not raw_joints:
            return None

        joints: dict[str, JointData] = {}
        bones: list[BoneData] = []
        root_joint = ""

        for joint_id, joint_payload in raw_joints.items():
            if not isinstance(joint_payload, dict):
                continue

            raw_position = joint_payload.get("position", [0.0, 0.0])
            x = float(raw_position[0]) if isinstance(raw_position, list | tuple) and len(raw_position) > 0 else 0.0
            y = float(raw_position[1]) if isinstance(raw_position, list | tuple) and len(raw_position) > 1 else 0.0
            parent_id = joint_payload.get("parent_id") or joint_payload.get("parent")

            bend_direction_raw = joint_payload.get("bend_direction")
            bend_direction = 1.0
            if isinstance(bend_direction_raw, int | float):
                bend_direction = float(bend_direction_raw)

            joints[str(joint_id)] = JointData(
                id=str(joint_id),
                position=Point(x=x, y=y),
                name=str(joint_payload.get("name") or joint_id),
                parent=str(parent_id) if parent_id else None,
                is_locked=bool(joint_payload.get("is_locked", False)),
                bend_direction=bend_direction,
            )

            if parent_id:
                bones.append(BoneData(from_joint=str(parent_id), to_joint=str(joint_id)))
            elif not root_joint:
                root_joint = str(joint_id)

        if not root_joint:
            root_ids = skeleton_dict.get("root_joint_ids", [])
            if isinstance(root_ids, list) and root_ids:
                root_joint = str(root_ids[0])

        return SkeletonData(
            joints=joints,
            bones=tuple(bones),
            root_joint=root_joint,
        )

    def _collect_paths_for_state(self) -> dict[str, PathData]:
        """Collect editor motion paths into PathData."""
        if not hasattr(self, "editor_tab") or not self.editor_tab:
            return {}

        path_data = {}
        qpaths = self.editor_tab.get_current_path_data()
        for part_name, qpath in qpaths.items():
            try:
                if not qpath or qpath.isEmpty():
                    continue

                points: list[Point] = []
                for i in range(qpath.elementCount()):
                    element = qpath.elementAt(i)
                    points.append(Point(x=float(element.x), y=float(element.y)))

                if not points:
                    continue

                first = points[0]
                last = points[-1]
                is_closed = abs(first.x - last.x) < 1.0 and abs(first.y - last.y) < 1.0

                path_data[str(part_name)] = PathData(
                    part_name=str(part_name),
                    points=tuple(points),
                    is_closed=is_closed,
                    enabled=True,
                )
            except Exception:
                logging.exception("Failed to snapshot path for part '%s'", part_name)

        return path_data

    def _serialize_qpainter_path(self, qpath: Any) -> dict[str, Any] | None:
        """Serialize QPainterPath to portable JSON-friendly structure."""
        if not isinstance(qpath, QPainterPath) or qpath.isEmpty():
            return None

        points: list[list[float]] = []
        try:
            for idx in range(qpath.elementCount()):
                elem = qpath.elementAt(idx)
                points.append([float(elem.x), float(elem.y)])
        except Exception:
            return None

        if not points:
            return None

        first = points[0]
        last = points[-1]
        is_closed = abs(first[0] - last[0]) < 1.0 and abs(first[1] - last[1]) < 1.0
        return {"points": points, "is_closed": is_closed}

    def _sanitize_for_project(
        self,
        value: Any,
        *,
        _memo: dict[int, Any] | None = None,
        _seen: set[int] | None = None,
    ) -> Any:
        """Recursively sanitize runtime values for JSON serialization."""
        if value is None or isinstance(value, bool | int | float | str):
            return value

        if callable(value):
            return None

        if isinstance(value, Path):
            return str(value)

        if isinstance(value, QPointF):
            return [float(value.x()), float(value.y())]

        if isinstance(value, QPainterPath):
            return self._serialize_qpainter_path(value)

        memo = _memo if _memo is not None else {}
        seen = _seen if _seen is not None else set()
        obj_id = id(value)

        if obj_id in seen:
            return None
        if obj_id in memo:
            return memo[obj_id]

        seen.add(obj_id)
        try:
            if isinstance(value, dict):
                out: dict[str, Any] = {}
                memo[obj_id] = out
                for k, v in value.items():
                    sanitized = self._sanitize_for_project(v, _memo=memo, _seen=seen)
                    if sanitized is not None:
                        out[str(k)] = sanitized
                return out

            if isinstance(value, list | tuple | set):
                out_list: list[Any] = []
                memo[obj_id] = out_list
                for item in value:
                    sanitized = self._sanitize_for_project(item, _memo=memo, _seen=seen)
                    if sanitized is not None:
                        out_list.append(sanitized)
                return out_list

            # NumPy arrays/scalars and similar types
            if hasattr(value, "tolist"):
                try:
                    sanitized = self._sanitize_for_project(value.tolist(), _memo=memo, _seen=seen)
                    memo[obj_id] = sanitized
                    return sanitized
                except Exception:
                    return None

            return None
        finally:
            seen.discard(obj_id)

    def _collect_mechanisms_for_state(self) -> dict[str, MechanismData]:
        """Collect mechanism layers into immutable MechanismData."""
        if not hasattr(self, "mechanism_design_tab") or not self.mechanism_design_tab:
            return {}

        mechanisms: dict[str, MechanismData] = {}
        layer_map = getattr(self.mechanism_design_tab, "mechanism_layers", {}) or {}
        enabled_map = getattr(self.mechanism_design_tab, "mechanism_enabled_state", {}) or {}

        for mechanism_id, layer_data in layer_map.items():
            if not isinstance(layer_data, dict):
                continue

            part_name = str(layer_data.get("part_name", "") or "")
            mechanism_type = str(
                layer_data.get("type", layer_data.get("mechanism_type", "unknown")) or "unknown"
            )
            params = layer_data.get("params", {})
            if not isinstance(params, dict):
                params = {}

            payload: dict[str, Any] = {}
            sanitize_memo: dict[int, Any] = {}
            for key, value in layer_data.items():
                if isinstance(key, str):
                    if key.startswith("_") or key.endswith(_PROJECT_RUNTIME_LAYER_KEY_SUFFIXES):
                        continue
                if key in _PROJECT_TRANSIENT_LAYER_KEYS:
                    continue
                if callable(value):
                    continue
                if key == "generated_path":
                    generated_path_data = self._serialize_qpainter_path(value)
                    if generated_path_data is not None:
                        payload["generated_path_data"] = generated_path_data
                    continue

                sanitized = self._sanitize_for_project(value, _memo=sanitize_memo)
                if sanitized is not None:
                    payload[str(key)] = sanitized

            mechanisms[str(mechanism_id)] = MechanismData(
                id=str(mechanism_id),
                part_name=part_name,
                type=mechanism_type,
                params=dict(params),
                layer_data=payload,
                enabled=bool(enabled_map.get(mechanism_id, layer_data.get("enabled", True))),
            )

        return mechanisms

    # --- Slots for EditorTab Signals (Implement these) ---
    @pyqtSlot(str, dict)
    def handle_generate_mechanism_request(self, mechanism_type: str, params: dict):
        logging.info(
            f"MainWindow: Received request to generate mechanism: {mechanism_type} with params {params}"
        )
        target_part_name = params.get("target_part_name")
        if not target_part_name:
            QMessageBox.warning(
                self,
                "Mechanism Error",
                "No target part specified for mechanism generation.",
            )
            return

        current_parts_data = self.project_data_manager.get_current_parts_data()
        if not current_parts_data and hasattr(self, "editor_tab") and self.editor_tab:
            current_parts_data = self.editor_tab.current_parts_info
        if not current_parts_data or target_part_name not in current_parts_data:
            QMessageBox.warning(
                self,
                "Mechanism Error",
                f"Target part '{target_part_name}' not found in project data.",
            )
            return

        target_part_info = current_parts_data[target_part_name]

        # Use editor scene center as reference point
        editor_scene_ref_point = QPointF(target_part_info.x, target_part_info.y)
        if self.editor_tab and self.editor_tab.editor_view:
            scene_rect = self.editor_tab.editor_view.sceneRect()
            editor_scene_ref_point = scene_rect.center()

        self.mechanism_manager.generate_mechanism(
            mechanism_type=mechanism_type,
            params=params,  # These params include selected points like cam_center from EditorTab
            target_part_info=target_part_info,
            all_parts_info=current_parts_data,
            editor_scene_center=editor_scene_ref_point,
        )

        self.statusBar().showMessage(
            f"Mechanism generation initiated for {target_part_name}: {mechanism_type}"
        )
        self._mark_workflow_stage_complete("tab_mechanism_design")

    @pyqtSlot()
    def generate_blueprint_impl(self):
        logging.info("MainWindow: Received request to generate blueprint.")
        # Call actual blueprint generation logic here
        # Example: generate_blueprint_svg(self.parts, self.editor_items, "blueprint.svg")
        self.statusBar().showMessage("Blueprint generation requested.")

    @pyqtSlot()
    def save_character_alignment_impl(self):
        logging.info("MainWindow: Received request to save character alignment.")
        # Call actual alignment saving logic here
        self.statusBar().showMessage("Character alignment save requested.")

    @pyqtSlot(str, str, dict, tuple)
    def _handle_foundry_export_to_mechanism_tab(
        self, mechanism_id: str, mechanism_type: str, parameters: dict, pivot_point: tuple
    ):
        """Handle mechanism export from Foundry to Mechanism Design Tab.

        Routes the mechanism configuration from Mechanism Foundry to the
        Mechanism Design Tab for simulation and character assignment.
        """
        logging.info(
            f"MainWindow: Received foundry export - id={mechanism_id}, type={mechanism_type}, "
            f"params={parameters}, pivot={pivot_point}"
        )

        imported = False
        import_error: Exception | None = None

        import_method = getattr(self.mechanism_design_tab, "import_mechanism_from_foundry", None)

        # Forward to Mechanism Design Tab's import method (with mechanism_id for sync)
        if callable(import_method):
            try:
                imported = bool(
                    import_method(
                        mechanism_type=mechanism_type,
                        parameters=parameters,
                        pivot_point=pivot_point,
                        mechanism_id=mechanism_id,
                    )
                )
            except Exception as exc:
                import_error = exc
                logging.exception(
                    "Failed to import Foundry mechanism into Design Tab for id=%s",
                    mechanism_id,
                )
            if imported:
                self.statusBar().showMessage(
                    f"Mechanism '{mechanism_type}' added to Mechanism Tab"
                )
                self._mark_workflow_stage_complete("tab_mechanism_foundry")
                self._mark_workflow_stage_complete("tab_mechanism_design")
                # Register sync target in Foundry so subsequent Design edits flow back.
                if hasattr(self.mechanism_foundry_tab, "set_synced_mechanism"):
                    self.mechanism_foundry_tab.set_synced_mechanism(
                        mechanism_id, mechanism_type
                    )
            else:
                self._clear_foundry_sync_target()
                if import_error is None:
                    logging.warning(
                        "MechanismDesignTab.import_mechanism_from_foundry returned False for id=%s",
                        mechanism_id,
                    )
                self.statusBar().showMessage(
                    f"Failed to add mechanism '{mechanism_type}' to Mechanism Tab"
                )
        else:
            self._clear_foundry_sync_target()
            logging.warning(
                "MechanismDesignTab.import_mechanism_from_foundry not available"
            )

        # Switch to Mechanism Design Tab
        self._switch_to_mechanism_design_tab()

    def _clear_foundry_sync_target(self) -> None:
        """Clear stale Foundry sync state when export-to-Design does not attach."""
        clear_sync = getattr(self.mechanism_foundry_tab, "clear_synced_mechanism", None)
        if not callable(clear_sync):
            return
        try:
            clear_sync()
        except Exception:
            logging.debug("Suppressed exception while clearing Foundry sync target", exc_info=True)

    def _switch_to_mechanism_design_tab(self):
        """Switches the main tab widget to the Mechanism Design Tab."""
        for i in range(self.tab_widget.count()):
            if self.tab_widget.widget(i) == self.mechanism_design_tab:
                logging.info("Switching to Mechanism Design tab by request.")
                self.tab_widget.setCurrentIndex(i)
                self._mark_workflow_stage_complete("tab_mechanism_design")
                return
        logging.warning("Could not find MechanismDesignTab to switch to.")

    # Method for reset_all_animations_btn in EditorTab (if EditorTab calls it directly)
    def _reset_all_animations_button_clicked(self):
        logging.info("MainWindow: Resetting all animation paths and poses.")

        # Delegate clearing of motion path data from PartInfo objects to ProjectDataManager
        if hasattr(self.project_data_manager, "clear_all_motion_paths"):
            self.project_data_manager.clear_all_motion_paths()
        else:
            logging.warning("ProjectDataManager does not have clear_all_motion_paths method.")
            # Fallback to old direct manipulation if method doesn't exist (for safety during refactor)
            current_parts_data = self.project_data_manager.get_current_parts_data()
            if current_parts_data:
                for part_info in current_parts_data.values():
                    if hasattr(part_info, "motion_path_data"):
                        part_info.motion_path_data = None
                    if hasattr(part_info, "motion_path"):
                        part_info.motion_path = []
            else:
                logging.warning("Cannot clear motion path data: No parts data loaded.")

        # Instruct EditorTab to clear its visual motion paths
        if self.editor_tab and hasattr(self.editor_tab, "clear_all_visual_motion_paths"):
            self.editor_tab.clear_all_visual_motion_paths()
        else:
            logging.warning("EditorTab or its clear_all_visual_motion_paths method not found.")

        # Reset character pose to initial skeleton definition via IKManager
        self.ik_manager.reset_animation_state()  # This should reset poses to initial

        # Update EditorTab's view and button states
        if self.editor_tab:
            if hasattr(self.editor_tab, "editor_view") and hasattr(
                self.editor_tab.editor_view, "update_view"
            ):
                self.editor_tab.editor_view.update_view()
            if hasattr(self.editor_tab, "_update_button_states"):
                self.editor_tab._update_button_states()

        self.statusBar().showMessage("All animation paths and character poses reset.")

    def _connect_global_signals(self):
        """Connects global signals like tab changes or theme changes."""
        # Tab switching is handled by TabOrchestrator (see _init_tab_orchestrator)

        # Connect SkeletonManager signals
        self.skeleton_manager.skeleton_updated.connect(self._on_skeleton_manager_updated)

        # Connect IKManager signals
        self.ik_manager.character_visuals_updated.connect(self._handle_ik_visuals_update)
        if (
            hasattr(self, "editor_tab")
            and self.editor_tab
            and hasattr(self.ik_manager, "animation_state_changed")
        ):
            self.ik_manager.animation_state_changed.connect(
                self.editor_tab.on_simulation_state_changed
            )

        # OptionsTab signals
        if hasattr(self, "options_tab") and self.options_tab:
            self.options_tab.themeChanged.connect(self._apply_theme)
            # Connect animation duration change from OptionsTab to IKManager
            self.options_tab.animationDurationChanged.connect(
                self.ik_manager.set_animation_duration
            )
            # Initialize OptionsTab with current animation duration from IKManager
            self.options_tab.set_animation_duration_input(
                self.ik_manager.animation_duration / 1000.0
            )
            # Connect advanced processing visibility toggle
            if hasattr(self.options_tab, "advancedProcessingVisibilityChanged") and hasattr(
                self.image_proc_tab, "_toggle_detailed_processing_visibility"
            ):
                self.options_tab.advancedProcessingVisibilityChanged.connect(
                    self.image_proc_tab._toggle_detailed_processing_visibility
                )
            # Connect unit changed signal (assuming OptionsTab will have it)
            if hasattr(self.options_tab, "unitChanged"):
                self.options_tab.unitChanged.connect(self._handle_unit_changed)
            else:
                logging.warning(
                    "MainWindow: OptionsTab does not have unitChanged signal. Unit selection may not work."
                )

            # Physics snap mode from OptionsTab → ParametricEditingManager (redundant safety connect)
            if hasattr(self.options_tab, "physicsSnapModeChanged"):
                try:
                    setter = getattr(
                        self.mechanism_design_tab.parametric_manager, "set_physics_snap_mode", None
                    )
                    if callable(setter):
                        self.options_tab.physicsSnapModeChanged.connect(setter)
                        # Initialize UI to manager's default
                        if hasattr(self.options_tab, "set_physics_snap_mode_input"):
                            self.options_tab.set_physics_snap_mode_input(
                                self.mechanism_design_tab.parametric_manager.physics_snap_mode
                            )
                except Exception:
                    logging.exception("Failed to connect physics snap mode option (global connect)")

        # EditorTab signals
        if hasattr(self, "editor_tab") and self.editor_tab:
            # More robust connections to IKManager, checking method existence
            if hasattr(self.ik_manager, "start_animation"):
                self.editor_tab.request_play_simulation.connect(self.ik_manager.start_animation)
            if hasattr(self.ik_manager, "stop_animation"):
                self.editor_tab.request_stop_simulation.connect(self.ik_manager.stop_animation)
            if hasattr(
                self.ik_manager, "reset_animation_state"
            ):  # Ensure this method name is correct in IKManager
                self.editor_tab.request_reset_simulation.connect(
                    self.ik_manager.reset_animation_state
                )

            # If save_character_alignment_impl is the final destination for the signal from EditorTab
            if hasattr(self, "save_character_alignment_impl"):
                self.editor_tab.request_save_alignment.connect(self.save_character_alignment_impl)

            # If generate_blueprint_impl is the final destination
            if hasattr(self, "generate_blueprint_impl"):
                self.editor_tab.request_generate_blueprint.connect(self.generate_blueprint_impl)

            # Connect the new request_reset_all_animations signal
            if hasattr(self.editor_tab, "request_reset_all_animations") and hasattr(
                self, "_reset_all_animations_button_clicked"
            ):
                self.editor_tab.request_reset_all_animations.connect(
                    self._reset_all_animations_button_clicked
                )

            # Connect EditorTab.motion_path_updated to MainWindow handler
            if hasattr(self.editor_tab, "motion_path_updated") and hasattr(
                self, "_handle_part_motion_path_update_from_editor_tab"
            ):
                if not self._is_signal_connected(
                    self.editor_tab.motion_path_updated,
                    self._handle_part_motion_path_update_from_editor_tab,
                ):
                    self.editor_tab.motion_path_updated.connect(
                        self._handle_part_motion_path_update_from_editor_tab
                    )

        # MechanismManager connections - temporarily disabled for debugging
        # if hasattr(self, "mechanism_manager") and hasattr(
        #     self.mechanism_manager, "mechanism_visuals_ready"
        # ):
        #     # Connect to MechanismDesignTab instead of EditorTab
        #     if hasattr(self, "mechanism_design_tab") and hasattr(
        #         self.mechanism_design_tab, "handle_mechanism_visuals"
        #     ):
        #         if not self._is_signal_connected(
        #             self.mechanism_manager.mechanism_visuals_ready,
        #             self.mechanism_design_tab.handle_mechanism_visuals,
        #         ):
        #             self.mechanism_manager.mechanism_visuals_ready.connect(
        #                 self.mechanism_design_tab.handle_mechanism_visuals
        #             )
        #     else:
        #         logging.warning(
        #             "MechanismDesignTab or handle_mechanism_visuals slot not found for MechanismManager signal."
        #         )
        # else:
        #     logging.warning(
        #         "MechanismManager or its mechanism_visuals_ready signal not found."
        #     )

    def _connect_manager_signals(self):
        """Connect signals from various managers to MainWindow slots or other manager slots.

        Delegates to SignalConnector component for centralized connection management.
        """
        logging.debug("MainWindow: Connecting manager signals via SignalConnector...")

        # Use SignalConnector for centralized signal management
        if self.project_data_manager:
            self._signal_connector.connect_project_data_manager(
                self.project_data_manager, self
            )

        if self.skeleton_manager:
            self._signal_connector.connect_skeleton_manager(
                self.skeleton_manager, self, self.ik_manager
            )

        if self.ik_manager:
            self._signal_connector.connect_ik_manager(
                self.ik_manager, self, self.editor_tab if hasattr(self, "editor_tab") else None
            )

        logging.debug("MainWindow: Finished connecting manager signals.")

    def _setup_animation_scheduler(self) -> None:
        """
        Setup central animation scheduler for tabs that need it.

        The scheduler provides unified animation timing to eliminate
        frame jitter from multiple independent timers.
        """
        logging.info("MainWindow: Setting up animation scheduler...")

        # Pass scheduler to MechanismDesignTab
        if hasattr(self, "mechanism_design_tab") and self.mechanism_design_tab:
            if hasattr(self.mechanism_design_tab, "set_animation_scheduler"):
                self.mechanism_design_tab.set_animation_scheduler(self.animation_scheduler)
                logging.debug("Animation scheduler attached to MechanismDesignTab")

        logging.info("MainWindow: Animation scheduler setup complete")

    def _setup_state_adapters(self) -> None:
        """
        Setup SSOT state adapters for each tab.

        Adapters bridge tabs to the centralized ProjectStateManager,
        enabling reactive state updates without modifying tab internals.
        This is an additive integration - existing signal connections remain.
        """
        logging.info("MainWindow: Setting up state adapters...")

        # Create and attach ImageProcessingTab adapter
        if hasattr(self, "image_proc_tab") and self.image_proc_tab:
            self._image_proc_adapter = ImageProcessingTabAdapter(
                self.project_state_manager,
                parent=self,
                prefer_main_window_pipeline=True,
            )
            self._image_proc_adapter.attach(self.image_proc_tab)
            logging.debug("ImageProcessingTab adapter attached")

        # Create and attach EditorTab adapter
        if hasattr(self, "editor_tab") and self.editor_tab:
            self._editor_adapter = EditorTabAdapter(
                self.project_state_manager, parent=self
            )
            self._editor_adapter.attach(self.editor_tab)
            logging.debug("EditorTab adapter attached")

        # Create and attach MechanismDesignTab adapter
        if hasattr(self, "mechanism_design_tab") and self.mechanism_design_tab:
            self._mechanism_design_adapter = MechanismDesignTabAdapter(
                self.project_state_manager, parent=self
            )
            self._mechanism_design_adapter.attach(self.mechanism_design_tab)
            logging.debug("MechanismDesignTab adapter attached")

        logging.info("MainWindow: State adapters setup complete")

        # Connect undo/redo availability signals to action enable/disable
        self.project_state_manager.undo_available.connect(
            lambda available: self.action_manager.get_action("undo").setEnabled(available)
        )
        self.project_state_manager.redo_available.connect(
            lambda available: self.action_manager.get_action("redo").setEnabled(available)
        )

    # =========================================================================
    # SSOT PROJECT SAVE/LOAD (Delegated to ProjectController)
    # =========================================================================

    def new_project_ssot(self) -> None:
        """Create a new project using SSOT architecture.

        Delegates to ProjectController for implementation.
        """
        self._project_controller.set_status_bar(self.statusBar())
        self._project_controller.new_project()

    def save_project_ssot(self) -> bool:
        """
        Save project using SSOT architecture.

        Returns:
            True if save was successful, False otherwise
        """
        self._sync_runtime_state_to_ssot(mark_saved=False)
        self._project_controller.set_status_bar(self.statusBar())
        return self._project_controller.save_project()

    def load_project_ssot(self) -> bool:
        """
        Load project using SSOT architecture.

        Returns:
            True if load was successful, False otherwise
        """
        self._project_controller.set_status_bar(self.statusBar())
        return self._project_controller.load_project()

    def undo_ssot(self) -> None:
        """Undo last state mutation."""
        self._project_controller.set_status_bar(self.statusBar())
        self._project_controller.undo()

    def redo_ssot(self) -> None:
        """Redo last undone mutation."""
        self._project_controller.set_status_bar(self.statusBar())
        self._project_controller.redo()

    def _is_signal_connected(self, signal, slot) -> bool:
        # Helper to check if a signal is connected to a specific slot
        # This is a basic check and might not be foolproof for all cases (e.g., lambdas, functools.partial)
        # For more robust checking, you might need to inspect receiver objects and names.
        # Qt doesn't provide a straightforward public API to list all connections easily.
        try:
            # This is a simplified check, real check is more complex.
            # For now, assume we need to ensure connections are made once.
            # A common pattern is to disconnect all first, then connect, to avoid duplicates.
            # However, for this refactoring, we focus on making the connections.
            # In a real scenario, one might track connections or use a more robust check.
            return False  # Placeholder, assume not connected to allow connection
        except Exception:
            return False

    @pyqtSlot(dict)
    def _on_skeleton_manager_updated(self, standardized_skeleton_data_dict: dict | None):
        """Slot called when SkeletonManager has new processed skeleton data (dictionary format)."""
        logging.info(
            "MainWindow: SkeletonManager updated. Notifying tabs. IKManager will handle its own re-initialization if needed."
        )

        # Cache the initial skeleton data in EditorTab
        if hasattr(self.editor_tab, "cache_initial_skeleton"):
            self.editor_tab.cache_initial_skeleton(standardized_skeleton_data_dict)
        else:
            logging.warning("MainWindow: EditorTab does not have cache_initial_skeleton method.")

        # Cache the initial skeleton data in MechanismDesignTab as well
        if hasattr(self.mechanism_design_tab, "cache_initial_skeleton"):
            self.mechanism_design_tab.cache_initial_skeleton(standardized_skeleton_data_dict)
        else:
            logging.warning(
                "MainWindow: MechanismDesignTab does not have cache_initial_skeleton method."
            )

        # Notify tabs that might need the direct standardized skeleton data for display
        if hasattr(self.image_proc_tab, "on_skeleton_updated_externally"):
            self.image_proc_tab.on_skeleton_updated_externally(standardized_skeleton_data_dict)

        if hasattr(self.editor_tab, "on_skeleton_updated"):
            self.editor_tab.on_skeleton_updated(standardized_skeleton_data_dict)

        # Update status bar
        self.update_status_bar_with_skeleton_info(standardized_skeleton_data_dict)

    # MODIFIED: Method now accepts the skeleton data dictionary
    def update_status_bar_with_skeleton_info(self, skeleton_data_dict: dict | None):
        if skeleton_data_dict and skeleton_data_dict.get("joints"):
            num_joints = len(skeleton_data_dict.get("joints", {}))
            self.statusBar().showMessage(f"Skeleton loaded/updated: {num_joints} joints.", 3000)
        else:
            self.statusBar().showMessage("Skeleton cleared or not loaded.", 3000)

    # --- New Slot for IKManager Signals ---
    @pyqtSlot(dict)
    def _handle_ik_visuals_update(self, part_transforms: dict[str, dict[str, Any]]):
        """Handles updates to part visuals from the IKManager.
        Transforms part-centric data to joint-centric for EditorView.
        """
        # Send IK updates to BOTH editor_tab AND mechanism_design_tab
        # This ensures both tabs can display natural skeleton movement

        if self.editor_tab:
            self.editor_tab.handle_ik_update(part_transforms)

        # CRITICAL FIX: Send IK updates to mechanism design tab with safety checks
        if (
            self.mechanism_design_tab
            and hasattr(self.mechanism_design_tab, "handle_ik_update")
            and self.mechanism_design_tab.isVisible()
            and hasattr(self.mechanism_design_tab, "_tab_active")
            and self.mechanism_design_tab._tab_active
        ):
            self.mechanism_design_tab.handle_ik_update(part_transforms)
        elif self.mechanism_design_tab:
            # Tab exists but is not active - this is normal during tab switching
            pass

    def _handle_option_change(self, setting_name: str, value: Any):
        """Handles generic setting changes from the OptionsTab."""
        logging.info(f"Option changed: {setting_name} = {value}")
        # Add logic here to handle specific settings if needed,
        # though most are directly connected to their respective handlers.
        # This slot can be used for logging or for settings that don't have direct handlers.
        if setting_name == "theme":
            self._apply_theme(str(value))  # Already connected, but shows example
        elif setting_name == "animation_duration":
            self.ik_manager.set_animation_duration(
                int(float(value) * 1000)
            )  # Convert seconds to ms
        elif setting_name == "timing_profile":
            if hasattr(self.ik_manager, "set_timing_profile"):
                # Value may be human-readable or normalized
                val = str(value).lower().replace("-", "_").replace(" ", "_")
                self.ik_manager.set_timing_profile(val)
        elif setting_name == "toolbar_visibility":
            self._toggle_toolbar_visibility(bool(value))
        elif setting_name == "part_properties_visibility":
            self._toggle_part_properties_visibility(bool(value))
        elif (
            setting_name == "unit_system"
        ):  # Assuming this will be the setting_name from OptionsTab
            self._handle_unit_changed(str(value))
        elif setting_name == "grid_system_enabled":
            self._grid_system_enabled = bool(value)
            self._apply_grid_system_settings()
        elif setting_name == "grid_cell_size_cm":
            try:
                self._grid_cell_size_cm = max(0.1, float(value))
            except (TypeError, ValueError):
                self._grid_cell_size_cm = 2.5
            self._apply_grid_system_settings()
        elif setting_name == "performance_preset":
            try:
                preset = str(value)
                if hasattr(self, "mechanism_design_tab") and self.mechanism_design_tab:
                    apply = getattr(self.mechanism_design_tab, "apply_performance_preset", None)
                    if callable(apply):
                        apply(preset)
            except Exception:
                logging.debug("Suppressed exception", exc_info=True)
        elif setting_name == "debug_mode":
            # Assuming ImageProcessingTab has a method to set debug mode
            if hasattr(self.image_proc_tab, "set_debug_mode"):
                self.image_proc_tab.set_debug_mode(bool(value))
            else:
                logging.warning("ImageProcessingTab does not have set_debug_mode method.")
        else:
            logging.warning(f"Unhandled option change: {setting_name}")

    def show_about_dialog(self):
        """Displays the 'About' dialog."""
        QMessageBox.about(
            self,
            "About Automata Designer",
            "<p><b>Automata Designer</b></p>"
            "<p>Version 0.1.0</p>"
            "<p>Copyright &copy; 2024 Automataii Contributors</p>"
            "<p>This application helps design and simulate automata mechanisms.</p>",
        )

    @pyqtSlot(str)
    def _handle_unit_changed(self, unit: str):
        """Handles the unit system change from OptionsTab."""
        logging.info(f"MainWindow: Unit system changed to: {unit}")
        # Pass the new unit to EditorView
        if hasattr(self.editor_tab, "editor_view") and hasattr(
            self.editor_tab.editor_view, "set_display_unit"
        ):
            self.editor_tab.editor_view.set_display_unit(unit)
        else:
            logging.warning("MainWindow: EditorView or its set_display_unit method not found.")

        # Pass the new unit to ImageProcessingView (via ImageProcessingTab)
        if hasattr(self.image_proc_tab, "image_proc_view") and hasattr(
            self.image_proc_tab.image_proc_view, "set_display_unit"
        ):
            self.image_proc_tab.image_proc_view.set_display_unit(unit)
        else:
            logging.warning(
                "MainWindow: ImageProcessingView or its set_display_unit method not found."
            )

        if (
            hasattr(self, "mechanism_design_tab")
            and self.mechanism_design_tab
            and hasattr(self.mechanism_design_tab, "mechanism_view")
            and self.mechanism_design_tab.mechanism_view
            and hasattr(self.mechanism_design_tab.mechanism_view, "set_display_unit")
        ):
            self.mechanism_design_tab.mechanism_view.set_display_unit(unit)
        else:
            logging.warning(
                "MainWindow: MechanismDesignView or its set_display_unit method not found."
            )

        self.statusBar().showMessage(f"Display unit set to {unit}", 3000)

    def _apply_grid_system_settings(self) -> None:
        enabled = bool(self._grid_system_enabled)
        cell_cm = max(0.1, float(self._grid_cell_size_cm))

        if hasattr(self, "mechanism_foundry_tab") and self.mechanism_foundry_tab:
            setter = getattr(self.mechanism_foundry_tab, "set_grid_system", None)
            if callable(setter):
                setter(enabled, cell_cm)

        if hasattr(self, "mechanism_design_tab") and self.mechanism_design_tab:
            setter = getattr(self.mechanism_design_tab, "configure_grid_system", None)
            if callable(setter):
                setter(enabled, cell_cm)

    def _handle_project_manager_error(self, error_message: str):
        """Handles error signals from the ProjectDataManager."""
        logging.error(f"ProjectDataManager error: {error_message}")
        QMessageBox.critical(self, "Project Error", f"An error occurred: {error_message}")

    @pyqtSlot(str, QPainterPath)
    def _handle_part_motion_path_update_from_editor_tab(
        self, part_name: str, motion_qpath: QPainterPath
    ):
        """Handles the motion_path_updated signal from EditorTab and passes it to IKManager."""
        if not self.ik_manager:
            logging.warning("MainWindow: IKManager not available to handle motion path update.")
            return
        if hasattr(self.ik_manager, "update_part_motion_path"):
            self.ik_manager.update_part_motion_path(part_name, motion_qpath)
            logging.info(f"MainWindow: Relayed motion path update for '{part_name}' to IKManager.")
        else:
            logging.warning("MainWindow: IKManager does not have 'update_part_motion_path' method.")

    @pyqtSlot(dict)
    def _handle_skeleton_pose_updated_from_ik(
        self, animated_pose_data_dict: dict[str, tuple[float, float]]
    ):
        """Handles the raw animated skeleton pose update from IKManager."""
        logging.debug(
            f"MainWindow:_handle_skeleton_pose_updated_from_ik - Received animated_pose_data_dict (count: {len(animated_pose_data_dict)}): {animated_pose_data_dict if len(animated_pose_data_dict) < 5 else str(list(animated_pose_data_dict.items())[:5]) + '...'}"
        )
        if self.editor_tab and self.editor_tab.editor_view:
            # Pass the raw animated data directly
            self.editor_tab.editor_view.update_skeleton_animation(animated_pose_data_dict)
        else:
            logging.warning(
                "MainWindow: Cannot relay skeleton pose update, EditorTab or EditorView not available."
            )

    def closeEvent(self, event: QCloseEvent) -> None:
        """Persist workspace state before shutdown."""
        try:
            if self._workspace_layout_manager:
                self._workspace_layout_manager.save_workspace_layout()
        except Exception:
            logging.debug("Suppressed exception while saving workspace layout on close", exc_info=True)
        super().closeEvent(event)


# Backward compatibility: some callers/tests import MainWindow
MainWindow = AutomataDesigner
