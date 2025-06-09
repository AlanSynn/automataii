"""Main editor view class that coordinates all editor components."""

import logging
from typing import Optional, Dict, List, Any, Tuple
from PyQt6.QtWidgets import QGraphicsView, QApplication
from PyQt6.QtGui import QPainter, QBrush, QColor
from PyQt6.QtCore import Qt, QPointF, QRectF, pyqtSignal, QEvent

from ...graphics_items.part_item import CharacterPartItem
from ...graphics_items.anchor_item import AnchorItem
from ...graphics_items.skeleton_item import SkeletonGraphicsItem

from .constants import EditorMode, DEFAULT_DISPLAY_UNIT, DEFAULT_DPI
from .grid_drawer import GridDrawer
from .mode_manager import ModeManager
from .zoom_controller import ZoomController
from .joint_handler import JointHandler
from .motion_path_handler import MotionPathHandler
from .selection_handler import SelectionHandler
from .simulation_controller import SimulationController
from .context_menu_handler import ContextMenuHandler


class EditorView(QGraphicsView):
    """Custom QGraphicsView for editor with modular components.

    This view coordinates various handlers for different editing operations:
    - Grid drawing
    - Zoom and pan control
    - Mode management
    - Joint definition
    - Motion path drawing
    - Selection handling
    - Simulation control
    - Context menus
    """

    # Forward signals from handlers
    end_effector_selected = pyqtSignal(QPointF, QPointF)
    cam_center_selected = pyqtSignal(QPointF)
    drawing_cancelled = pyqtSignal()
    joint_defined = pyqtSignal(dict)
    pivot_a_selected = pyqtSignal(QPointF)
    pivot_d_selected = pyqtSignal(QPointF)
    driver_center_selected = pyqtSignal(QPointF)
    driven_center_selected = pyqtSignal(QPointF)
    freehandPathCompleted = pyqtSignal(list)
    zoom_changed = pyqtSignal(float)
    part_item_clicked = pyqtSignal(CharacterPartItem)
    part_item_double_clicked = pyqtSignal(CharacterPartItem)
    part_item_moved = pyqtSignal(CharacterPartItem, QPointF)
    path_data_cleared_for_component = pyqtSignal(str)

    def __init__(self, scene, parent_window=None):
        super().__init__(scene, parent_window)
        self.parent_window = parent_window

        # Basic view setup
        self._setup_view()

        # Initialize components
        self.grid_drawer = GridDrawer(self)
        self.mode_manager = ModeManager(self)
        self.zoom_controller = ZoomController(self)
        self.joint_handler = JointHandler(self)
        self.motion_path_handler = MotionPathHandler(self)
        self.selection_handler = SelectionHandler(self)
        self.simulation_controller = SimulationController(self)
        self.context_menu_handler = ContextMenuHandler(self)

        # Connect internal signals
        self._connect_signals()

        # Initialize display settings
        self._init_display_settings()

        # Setup context menu
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.context_menu_handler.show_context_menu)

    def _setup_view(self):
        """Sets up basic view properties."""
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)

        # Enable touch gestures
        self.grabGesture(Qt.GestureType.PinchGesture)

        # Style the viewport
        self.viewport().setStyleSheet("background-color: white; border-radius: 10px;")

    def _init_display_settings(self):
        """Initializes display settings."""
        self.display_unit = DEFAULT_DISPLAY_UNIT

        try:
            self.dpi = QApplication.primaryScreen().logicalDotsPerInch()
        except AttributeError:
            self.dpi = DEFAULT_DPI
            logging.warning(f"Could not get screen DPI, defaulting to {self.dpi} DPI.")

        self.grid_drawer.set_dpi(self.dpi)
        self.grid_drawer.set_display_unit(self.display_unit)

        logging.info(f"EditorView initialized with DPI: {self.dpi}, unit: {self.display_unit}")

    def _connect_signals(self):
        """Connects signals between components."""
        # Mode manager
        self.mode_manager.mode_changed.connect(self._on_mode_changed)

        # Zoom controller
        self.zoom_controller.zoom_changed.connect(self.zoom_changed.emit)

        # Joint handler
        self.joint_handler.joint_defined.connect(self.joint_defined.emit)

        # Motion path handler
        self.motion_path_handler.freehandPathCompleted.connect(self.freehandPathCompleted.emit)
        self.motion_path_handler.drawing_cancelled.connect(self.drawing_cancelled.emit)
        self.motion_path_handler.path_data_cleared_for_component.connect(
            self.path_data_cleared_for_component.emit
        )

        # Selection handler
        self.selection_handler.end_effector_selected.connect(self.end_effector_selected.emit)
        self.selection_handler.cam_center_selected.connect(self.cam_center_selected.emit)
        self.selection_handler.pivot_a_selected.connect(self.pivot_a_selected.emit)
        self.selection_handler.pivot_d_selected.connect(self.pivot_d_selected.emit)
        self.selection_handler.driver_center_selected.connect(self.driver_center_selected.emit)
        self.selection_handler.driven_center_selected.connect(self.driven_center_selected.emit)
        self.selection_handler.part_item_clicked.connect(self.part_item_clicked.emit)
        self.selection_handler.part_item_double_clicked.connect(self.part_item_double_clicked.emit)
        self.selection_handler.part_item_moved.connect(self.part_item_moved.emit)

    def _on_mode_changed(self, old_mode: str, new_mode: str):
        """Handles mode changes."""
        # Auto-return to select mode after certain selections
        if new_mode in [
            EditorMode.SELECT_CAM_CENTER,
            EditorMode.SELECT_PIVOT_A,
            EditorMode.SELECT_PIVOT_D,
            EditorMode.SELECT_DRIVER_CENTER,
            EditorMode.SELECT_DRIVEN_CENTER,
        ]:
            # These modes auto-return to select after click
            pass

    # --- Public API ---

    @property
    def current_mode(self) -> str:
        """Gets the current editor mode."""
        return self.mode_manager.current_mode

    def set_mode(self, mode: str):
        """Sets the editor mode."""
        self.mode_manager.set_mode(mode)

    def set_display_unit(self, unit: str):
        """Sets the display unit for the grid."""
        if unit.lower() in ["cm", "inch", "px"]:
            self.display_unit = unit.lower()
            self.grid_drawer.set_display_unit(self.display_unit)
            self.viewport().update()
        else:
            logging.warning(f"Invalid display unit '{unit}'")

    def set_joint_map(self, joint_map: Optional[Dict[str, str]]):
        """Sets the joint map for animation."""
        self.simulation_controller.set_joint_map(joint_map)

    def reset_temp_visuals(self):
        """Clears temporary visual items."""
        logging.debug("Resetting temporary visuals")
        self.joint_handler.cancel()
        self.motion_path_handler.cancel_drawing()
        self.selection_handler.clear_all_markers()

    def get_selected_item(self) -> Optional[CharacterPartItem]:
        """Returns the selected CharacterPartItem."""
        return self.selection_handler.get_selected_item()

    def set_selected_part(
        self,
        part_name: Optional[str],
        part_items: Dict[str, CharacterPartItem]
    ):
        """Sets the selected part."""
        self.selection_handler.set_selected_part(part_name, part_items)

    # --- Event Handling ---

    def drawBackground(self, painter: QPainter, rect: QRectF):
        """Draws the grid background."""
        super().drawBackground(painter, rect)
        self.grid_drawer.draw_background(painter, rect)

    def viewportEvent(self, event: QEvent):
        """Handle gesture events."""
        if event.type() == QEvent.Type.Gesture:
            return self.gestureEvent(event)
        return super().viewportEvent(event)

    def gestureEvent(self, event: QEvent):
        """Handle gesture events."""
        gesture = event.gesture(Qt.GestureType.PinchGesture)
        if gesture:
            self.pinchTriggered(gesture)
            return True
        return super().viewportEvent(event)

    def pinchTriggered(self, gesture):
        """Handle pinch gesture."""
        if gesture.state() == Qt.GestureState.GestureStarted:
            self.zoom_controller.handle_pinch_start()
        elif gesture.state() == Qt.GestureState.GestureUpdated:
            self.zoom_controller.handle_pinch_update(gesture.scaleFactor())
        elif gesture.state() == Qt.GestureState.GestureFinished:
            self.zoom_controller.handle_pinch_end()

    def wheelEvent(self, event):
        """Handle mouse wheel events."""
        if self.zoom_controller.handle_wheel_event(event):
            return
        super().wheelEvent(event)

    def mousePressEvent(self, event):
        """Handle mouse press events."""
        scene_pos = self.mapToScene(event.pos())

        # Check for pan
        if event.button() == Qt.MouseButton.MiddleButton or (
            event.button() == Qt.MouseButton.LeftButton and
            event.modifiers() & Qt.KeyboardModifier.AltModifier
        ):
            self.zoom_controller.start_pan(event.pos())
            return

        # Handle based on mode
        if event.button() == Qt.MouseButton.LeftButton:
            handled = False

            if self.current_mode == EditorMode.DEFINE_JOINT:
                handled = self.joint_handler.handle_click(scene_pos, event.pos())
            elif self.current_mode == EditorMode.DEFINE_MOTION_PATH:
                self.motion_path_handler.begin_drawing(scene_pos)
                handled = True
            elif self.current_mode.startswith("select_"):
                if self.selection_handler.handle_selection_click(self.current_mode, scene_pos):
                    self.set_mode(EditorMode.SELECT)
                    handled = True

            if not handled:
                super().mousePressEvent(event)
                # Check for part item clicks
                item = self.itemAt(event.pos())
                if isinstance(item, CharacterPartItem):
                    self.selection_handler.handle_part_click(item)

        elif event.button() == Qt.MouseButton.RightButton:
            # Right click cancels operations
            if self.current_mode == EditorMode.DEFINE_MOTION_PATH:
                self.motion_path_handler.cancel_drawing()
            elif self.current_mode == EditorMode.DEFINE_JOINT:
                self.joint_handler.cancel()
                self.set_mode(EditorMode.SELECT)
            elif self.current_mode.startswith("select_"):
                self.set_mode(EditorMode.SELECT)
            else:
                super().mousePressEvent(event)
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """Handle mouse release events."""
        if self.zoom_controller.is_panning() and (
            event.button() == Qt.MouseButton.MiddleButton or
            (event.button() == Qt.MouseButton.LeftButton and
             event.modifiers() & Qt.KeyboardModifier.AltModifier)
        ):
            self.zoom_controller.end_pan()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            if self.current_mode == EditorMode.DEFINE_MOTION_PATH:
                if self.motion_path_handler.finish_drawing():
                    self.set_mode(EditorMode.SELECT)

        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        """Handle mouse move events."""
        if self.zoom_controller.is_panning():
            self.zoom_controller.update_pan(event.pos())
            return

        if self.current_mode == EditorMode.DEFINE_MOTION_PATH:
            scene_pos = self.mapToScene(event.pos())
            self.motion_path_handler.add_point(scene_pos)
        else:
            super().mouseMoveEvent(event)

    def keyPressEvent(self, event):
        """Handle keyboard events."""
        if event.key() == Qt.Key.Key_Escape:
            if self.current_mode == EditorMode.DEFINE_JOINT:
                self.joint_handler.cancel()
                self.set_mode(EditorMode.SELECT)
            elif self.current_mode == EditorMode.DEFINE_MOTION_PATH:
                self.motion_path_handler.cancel_drawing()
            elif self.current_mode.startswith("select_"):
                self.set_mode(EditorMode.SELECT)
                self._show_status_message("Selection cancelled")
            else:
                super().keyPressEvent(event)
            return

        # Ctrl+0 for reset view
        if (event.key() == Qt.Key.Key_0 and
            event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            self.reset_view()
            return

        super().keyPressEvent(event)

    # --- View Control ---

    def reset_view(self):
        """Reset zoom and pan."""
        self.zoom_controller.reset_view()
        self._show_status_message("View reset")

    def zoom_to_fit(self):
        """Zoom to fit all items."""
        self.zoom_controller.zoom_to_fit()
        scale = self.transform().m11()
        self._show_status_message(f"Zoom to fit ({scale:.1f}x)")

    def zoom(self, step: int):
        """Zoom by steps."""
        self.zoom_controller.zoom(step)

    def set_zoom_level(self, zoom_factor: float):
        """Set zoom level directly."""
        self.zoom_controller.set_zoom_level(zoom_factor)

    # --- Mode-specific Operations ---

    def start_define_joint(self):
        """Start joint definition mode."""
        self.set_mode(EditorMode.DEFINE_JOINT)
        self.joint_handler.start_joint_definition()

    def start_define_motion_path(self, target_item: Optional[CharacterPartItem]):
        """Start motion path definition mode."""
        if self.current_mode == EditorMode.DEFINE_MOTION_PATH:
            return
        self.motion_path_handler.start_path_drawing(target_item)
        self.set_mode(EditorMode.DEFINE_MOTION_PATH)

    def finish_motion_path_drawing(self, emit_signal: bool = True):
        """Finish motion path drawing."""
        # This is called when mode is toggled off
        self.motion_path_handler.cancel_drawing()
        self.set_mode(EditorMode.SELECT)

    def clear_visual_path_for_component(self, component_key: str):
        """Clear visual path for a component."""
        self.motion_path_handler.clear_path_for_component(component_key)

    def start_select_end_effector(self, target_item: CharacterPartItem):
        """Start end effector selection."""
        self.selection_handler.start_end_effector_selection(target_item)
        self.set_mode(EditorMode.SELECT_END_EFFECTOR)

    # --- Simulation ---

    def start_simulation(self):
        """Start simulation mode."""
        self.simulation_controller.start_simulation()
        self.set_mode(EditorMode.SIMULATION)

    def stop_simulation(self):
        """Stop simulation mode."""
        self.simulation_controller.stop_simulation()
        self.set_mode(EditorMode.SELECT)

    def reset_simulation(self):
        """Reset simulation."""
        self.simulation_controller.reset_simulation()
        self.set_mode(EditorMode.SELECT)

    def visualize_skeleton(
        self,
        skeleton_data: List[Dict[str, Any]],
        hierarchy_data: Dict[str, List[str]]
    ):
        """Visualize skeleton."""
        self.simulation_controller.visualize_skeleton(skeleton_data, hierarchy_data)

    def update_skeleton_animation(
        self,
        animated_positions: Dict[str, Tuple[float, float]]
    ):
        """Update skeleton animation."""
        self.simulation_controller.update_skeleton_animation(animated_positions)

    def update_visuals_from_animation_data(
        self,
        joint_data: Dict[str, Dict[str, Any]]
    ):
        """Update visuals from animation data."""
        self.simulation_controller.update_visuals_from_animation_data(joint_data)

    def get_current_part_transforms(self) -> Dict[str, Tuple[QPointF, float]]:
        """Get current part transforms."""
        transforms = {}
        if hasattr(self.parent_window, 'editor_items'):
            for name, item in self.parent_window.editor_items.items():
                if isinstance(item, CharacterPartItem):
                    transforms[name] = (item.pos(), item.rotation())
        return transforms

    # --- Utility ---

    def _show_status_message(self, message: str):
        """Show status message."""
        if self.parent_window and hasattr(self.parent_window, 'statusBar'):
            self.parent_window.statusBar().showMessage(message, 5000)
        else:
            logging.info(f"Status: {message}")

    @property
    def final_paths_map(self):
        """Access to final paths map for compatibility."""
        return self.motion_path_handler._final_paths_map

    @property
    def skeleton_graphics_item(self):
        """Access to skeleton item for compatibility."""
        return self.simulation_controller._skeleton_item

    @property
    def selection_markers(self):
        """Access to selection markers for compatibility."""
        return self.selection_handler._selection_markers

    def clear_all_motion_paths(self):
        """Clear all visual motion paths."""
        # Clear motion paths from all items
        if hasattr(self, 'motion_path_handler'):
            self.motion_path_handler.clear_all_paths()
        # Also clear from scene items
        for item in self.scene().items():
            if hasattr(item, 'motion_path'):
                item.motion_path = None

    def clear_scene(self):
        """Clear all items from the scene."""
        # Reset skeleton item reference since it will be deleted
        if hasattr(self, 'simulation_controller'):
            self.simulation_controller._skeleton_item = None
        self.scene().clear()

    def update_view(self):
        """Update the view (compatibility method)."""
        self.viewport().update()