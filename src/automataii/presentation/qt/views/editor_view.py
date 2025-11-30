"""
EditorView - Custom QGraphicsView for the editor.

Responsibilities delegated to extracted components:
- MotionPathManager: Motion path drawing, preview, splines, overlays
"""

import logging
from typing import Any

from PyQt6.QtCore import (
    QEvent,
    QLineF,
    QPointF,
    QRectF,
    Qt,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QColor,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
)
from PyQt6.QtWidgets import (
    QApplication,
    QGraphicsEllipseItem,
    QGraphicsPathItem,
    QGraphicsView,
    QMenu,
)

from automataii.config.z_indices import Z_MOTION_PATH_PREVIEW, Z_SKELETON_OVERLAY
from automataii.presentation.qt.animation import ViewportConfig, ViewportController
from automataii.presentation.qt.graphics_items.part_item import CharacterPartItem
from automataii.presentation.qt.graphics_items.skeleton_item import SkeletonGraphicsItem
from automataii.presentation.qt.views.motion_path_manager import (
    MotionPathDrawer,
    TARGET_PATH_POINTS,
)


class EditorView(QGraphicsView):
    """Custom QGraphicsView for editor with joint definition, path drawing, and panning/zooming.

    Signals:
        end_effector_selected(QPointF, QPointF): Emitted when end effector point is selected.
                                                 Payload: (local_pos, scene_pos)
        cam_center_selected(QPointF): Emitted when cam center point is selected.
                                      Payload: scene_pos
        drawing_cancelled(): Emitted when drawing (e.g., motion path) is cancelled.
        joint_defined(dict): Emitted when a joint is fully defined via mouse clicks.
                             Payload: { 'parent_item': ..., 'child_item': ..., 'parent_pos': ..., 'child_pos': ... }
        pivot_a_selected(QPointF): Emitted when pivot A is selected.
        pivot_d_selected(QPointF): Emitted when pivot D is selected.
        driver_center_selected(QPointF): Emitted when driver center is selected.
        driven_center_selected(QPointF): Emitted when driven center is selected.
        freehandPathCompleted = pyqtSignal(list) # Emits list of QPointF
        part_item_clicked = pyqtSignal(CharacterPartItem) # Emits the CharacterPartItem instance
        part_item_double_clicked = pyqtSignal(CharacterPartItem) # Emits the CharacterPartItem instance
        part_item_moved = pyqtSignal(CharacterPartItem, QPointF) # Emits item and its new scene position
        path_data_cleared_for_component = pyqtSignal(str) # NEW: Emits component_key when its path data should be cleared
    """

    end_effector_selected = pyqtSignal(QPointF, QPointF)
    cam_center_selected = pyqtSignal(QPointF)
    drawing_cancelled = pyqtSignal()
    joint_defined = pyqtSignal(dict)
    pivot_a_selected = pyqtSignal(QPointF)
    pivot_d_selected = pyqtSignal(QPointF)
    driver_center_selected = pyqtSignal(QPointF)
    driven_center_selected = pyqtSignal(QPointF)
    freehandPathCompleted = pyqtSignal(list)  # New signal for freehand path points
    zoom_changed = pyqtSignal(float)  # Emitted when zoom level changes

    # Signals for item interactions
    part_item_clicked = pyqtSignal(
        CharacterPartItem
    )  # Emits the CharacterPartItem instance
    part_item_double_clicked = pyqtSignal(
        CharacterPartItem
    )  # Emits the CharacterPartItem instance
    part_item_moved = pyqtSignal(
        CharacterPartItem, QPointF
    )  # Emits item and its new scene position
    path_data_cleared_for_component = pyqtSignal(
        str
    )  # NEW: Emits component_key when its path data should be cleared
    joint_bend_direction_changed = pyqtSignal(
        str, float
    )  # Emits joint_id and new bend_direction when a joint's bend direction is changed

    def __init__(self, scene, parent_window=None, mechanism_mode=False):
        super().__init__(scene, parent_window)
        self.parent_window = parent_window  # Reference to the main window if needed
        self.mechanism_mode = mechanism_mode  # Flag for mechanism design tab context
        # Rendering hints: favor performance in mechanism mode
        if self.mechanism_mode:
            # Disable antialiasing for faster redraws in mechanism preview
            self.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        else:
            self.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Set background color to gray
        # self.setBackgroundBrush(QBrush(QColor(200, 200, 200), Qt.BrushStyle.SolidPattern)) # REMOVED

        # Reduce overdraw: update only affected regions (performance win)
        # Use BoundingRectViewportUpdate to avoid artifacts common with Minimal mode
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)  # Default to selection

        # Enable touch gestures
        self.grabGesture(Qt.GestureType.PinchGesture)

        self._joint_map_original_to_std: dict[str, str] = {}  # original_name -> std_id

        # Pinch-to-zoom variables
        self._pinch_mode = False
        self._pinch_start_view_scale = 1.0

        # Custom panning variables
        self._panning = False
        self._pan_start_pos = QPointF()
        self._pan_sensitivity = 1.0  # Direct pixel-based panning for intuitive feel

        # Viewport controller (unified zoom/pan/reset)
        self._viewport_controller = ViewportController(
            self,
            ViewportConfig(
                zoom_factor_base=1.05,
                min_zoom_level=-47,
                max_zoom_level=47,
                anchor_under_mouse=True,
            ),
        )
        # Forward zoom_changed signal from controller
        self._viewport_controller.zoom_changed.connect(
            lambda level, scale: self.zoom_changed.emit(scale)
        )

        # State modes
        self.current_mode = "select"  # Modes: 'select', 'define_joint', 'define_motion_path', 'select_end_effector', 'select_cam_center', 'simulation', 'select_pivot_a', 'select_pivot_d', 'select_driver_center', 'select_driven_center'

        # Joint definition attributes
        self._joint_parent_item = None
        self._joint_parent_pos = None
        self._joint_parent_item_marker = None

        # Motion path attributes (revised for freehand)
        self._motion_path_points = []  # Stores QPointF for the current freehand path
        self._motion_preview_path_item = None  # QGraphicsPathItem for live preview
        self._is_drawing_freehand = False  # Flag for active drawing
        self.current_target_item_for_path = (
            None  # CharacterPartItem for which path is being defined
        )
        self.current_path_is_closed = True  # Default to closed path

        # Old motion path attributes (to be phased out or repurposed if needed)
        # self._motion_path = QPainterPath() # No longer primary storage here
        # self._temp_path_item = None # Replaced by _motion_preview_path_item
        # self._path_points = [] # Replaced by _motion_path_points
        # self._point_markers = [] # Not used for freehand
        # self._connection_lines = [] # Not used for freehand

        # End effector selection attributes
        self._target_part_for_end_effector = None

        # Simulation attributes
        self._animation_time = 0.0
        self._animation_duration = 30.0
        self._original_transforms = {}

        # Context menu
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

        # Skeleton visualization attributes (NEW)
        self.skeleton_graphics_item = SkeletonGraphicsItem()
        self.scene().addItem(self.skeleton_graphics_item)
        self.skeleton_graphics_item.setZValue(Z_SKELETON_OVERLAY)  # Set Z-value

        self.selection_markers: dict[
            str, QGraphicsEllipseItem
        ] = {}  # For mechanism point markers

        # MotionPathDrawer handles low-level path drawing, visualization, and overlays
        self._motion_path_drawer = MotionPathDrawer(self.scene(), parent=self)
        self._motion_path_drawer.freehand_path_completed.connect(
            lambda points: self.freehandPathCompleted.emit(points)
        )
        self._motion_path_drawer.drawing_cancelled.connect(
            lambda: self.drawing_cancelled.emit()
        )
        self._motion_path_drawer.path_data_cleared.connect(
            lambda key: self.path_data_cleared_for_component.emit(key)
        )

        # Expose final_paths_map for backward compatibility
        self.final_paths_map = self._motion_path_drawer.final_paths_map

        # Rounded corners and white background for the viewport
        self.viewport().setStyleSheet("background-color: white; border-radius: 10px;")

        # Initialize hover view controls
        self._setup_hover_controls()

        # Unit and DPI settings
        self.display_unit = "cm"  # Default unit: 'cm', 'inch', or 'px'
        try:
            self.dpi = QApplication.primaryScreen().logicalDotsPerInch()
        except AttributeError:
            # Fallback for environments where primaryScreen might not be available (e.g. some test setups)
            self.dpi = 96  # Common default DPI
            logging.warning(f"Could not get screen DPI, defaulting to {self.dpi} DPI.")
        logging.info(
            f"EditorView initialized with DPI: {self.dpi}, default unit: {self.display_unit}"
        )

    # ---- Overlay path helpers (delegated to MotionPathManager) ----
    def set_raw_overlay_path(self, key: str, path: QPainterPath | None, pen: QPen | None = None) -> None:
        """Set or clear the raw path overlay for a component key (part name)."""
        self._motion_path_drawer.set_raw_overlay_path(key, path, pen)

    def set_corrected_overlay_path(self, key: str, path: QPainterPath | None, pen: QPen | None = None) -> None:
        """Set or clear the feasibility-corrected path overlay for a component key."""
        self._motion_path_drawer.set_corrected_overlay_path(key, path, pen)

    def clear_overlays_for(self, key: str) -> None:
        """Clear raw and corrected overlays for a component key."""
        self._motion_path_drawer.clear_overlays_for(key)

    def clear_corrected_overlay_for(self, key: str) -> None:
        """Clear only the corrected overlay for a component key, keeping raw overlay intact."""
        self._motion_path_drawer.clear_corrected_overlay_for(key)

    def set_display_unit(self, unit: str):
        """Sets the display unit for the grid and updates the view."""
        if unit.lower() in ["cm", "inch", "px"]:
            self.display_unit = unit.lower()
            logging.info(f"EditorView: Display unit set to {self.display_unit}")
            self.viewport().update()  # Trigger a repaint of the background
        else:
            logging.warning(
                f"EditorView: Invalid display unit '{unit}'. Using current: {self.display_unit}"
            )

    def set_joint_map(self, joint_map: dict[str, str] | None):
        """Sets the joint map (original name to standardized ID)."""
        if joint_map:
            self._joint_map_original_to_std = joint_map
            logging.debug(f"EditorView: Joint map set with {len(joint_map)} entries.")
        else:
            self._joint_map_original_to_std = {}
            logging.debug("EditorView: Joint map cleared.")

    def drawBackground(self, painter: QPainter, rect: QRectF):
        """Draws a grid background based on the current display unit."""
        super().drawBackground(
            painter, rect
        )  # Draw the default background first (e.g., if a brush is set)

        painter.save()
        painter.setBrush(Qt.BrushStyle.NoBrush)  # No fill for the grid lines themselves

        # Define grid properties
        # grid_size_pixels = 20  # Original fixed pixel size

        # Calculate grid_size_pixels based on display_unit and DPI
        if self.display_unit == "cm":
            cm_to_inch = 1 / 2.54
            grid_size_pixels = int(self.dpi * cm_to_inch)  # 1 cm in pixels
        elif self.display_unit == "inch":
            grid_size_pixels = int(self.dpi)  # 1 inch in pixels
        else:  # Default to pixels or if unit is 'px'
            grid_size_pixels = 20  # Default pixel grid size

        if grid_size_pixels <= 0:  # Safety check
            grid_size_pixels = 20
            logging.warning(
                f"Calculated grid size is invalid ({grid_size_pixels}), defaulting to 20px."
            )

        light_pen = QPen(QColor(230, 230, 230), 1)  # Light gray for minor grid lines
        dark_pen = QPen(QColor(200, 200, 200), 1.5)  # Darker gray for major grid lines
        major_interval = 5  # Every 5th line is a major line if pixel based, or every unit for cm/inch

        if self.display_unit in ["cm", "inch"]:
            major_interval = 1  # Every line is a major line when unit-based for clarity
        else:  # pixel based
            major_interval = 5
            # Adjust grid_size for major/minor if pixel based to be multiples of 5 of base grid_size_pixels
            # This part might be complex if we want minor lines *within* the grid_size_pixels
            # For now, let's keep it simple: grid_size_pixels is the minor line spacing for 'px' mode.
            # And major_interval controls which of these are darker.

        # Get the visible rectangle in scene coordinates
        visible_rect = self.mapToScene(self.viewport().rect()).boundingRect()

        left = int(visible_rect.left() / grid_size_pixels) * grid_size_pixels
        top = int(visible_rect.top() / grid_size_pixels) * grid_size_pixels
        right = visible_rect.right()
        bottom = visible_rect.bottom()

        # Draw vertical lines
        x = left
        # count needs to be based on how many grid_size_pixels intervals from origin
        count_v = int(round(visible_rect.left() / grid_size_pixels))
        while x < right:
            painter.setPen(dark_pen if count_v % major_interval == 0 else light_pen)
            painter.drawLine(QLineF(x, top, x, bottom))
            x += grid_size_pixels
            count_v += 1

        # Draw horizontal lines
        y = top
        count_h = int(round(visible_rect.top() / grid_size_pixels))
        while y < bottom:
            painter.setPen(dark_pen if count_h % major_interval == 0 else light_pen)
            painter.drawLine(QLineF(left, y, right, y))
            y += grid_size_pixels
            count_h += 1

        painter.restore()

    def reset_temp_visuals(self):
        """Clears temporary visual items like drawing guides or markers."""
        logging.debug("EditorView: reset_temp_visuals called.")
        # Call specific cleanup methods for different types of temporary visuals
        self._reset_joint_definition_state()  # Clears joint definition markers
        self._cleanup_motion_path_visuals()  # Clears motion path drawing previews
        # Add other specific clear calls here if new temp visuals are added

    # --- Mode Management ---

    def set_mode(self, mode: str):
        """Sets the interaction mode of the editor view."""
        logging.info(f"Setting EditorView mode to: {mode}")
        previous_mode = self.current_mode
        self.current_mode = mode

        # Reset states from previous modes if necessary
        if previous_mode == "define_joint" and mode != "define_joint":
            self._reset_joint_definition()
        if previous_mode == "define_motion_path" and mode != "define_motion_path":
            self._cancel_motion_path_drawing()  # This will clear previews etc.
        if previous_mode == "select_end_effector" and mode != "select_end_effector":
            self._target_part_for_end_effector = None
        if previous_mode == "select_cam_center" and mode != "select_cam_center":
            pass  # No specific reset needed
        if previous_mode == "simulation" and mode != "simulation":
            self._reset_simulation_state()  # Ensure interactive state is restored

        # Configure view based on new mode
        if mode == "simulation":
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.setInteractive(False)
            self.viewport().setCursor(Qt.CursorShape.ForbiddenCursor)
        elif mode == "select":
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
            self.setInteractive(True)
            self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        elif (
            mode.startswith("select_") or mode == "define_joint"
        ):  # Point selection modes
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.setInteractive(
                True
            )  # Allow item clicks if needed, but main action is scene click
            self.viewport().setCursor(Qt.CursorShape.CrossCursor)
        elif mode == "define_motion_path":
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.setInteractive(True)
            self.viewport().setCursor(
                Qt.CursorShape.CrossCursor
            )  # Or a custom pen cursor
        else:  # Default/fallback
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
            self.setInteractive(True)
            self.viewport().setCursor(Qt.CursorShape.ArrowCursor)

    def get_selected_item(self):
        """Returns the single selected CharacterPartItem, or None."""
        selected_items = self.scene().selectedItems()
        if len(selected_items) == 1 and isinstance(
            selected_items[0], CharacterPartItem
        ):
            return selected_items[0]
        return None

    # --- Event Handling ---

    def viewportEvent(self, event: QEvent):
        """Handle gesture events like pinch-to-zoom."""
        if event.type() == QEvent.Type.Gesture:
            return self.gestureEvent(event)
        return super().viewportEvent(event)

    def gestureEvent(self, event: QEvent):
        """Handle gesture events."""
        gesture = event.gesture(Qt.GestureType.PinchGesture)
        if gesture:
            self.pinchTriggered(gesture)
            return True
        # Allow other gestures to be handled by the base class if needed
        return super().viewportEvent(event)

    def pinchTriggered(self, gesture):
        """Handle pinch gesture for zooming. Uses ViewportController for state sync."""
        config = self._viewport_controller.config

        if gesture.state() == Qt.GestureState.GestureStarted:
            self._pinch_mode = True
            self._pinch_start_view_scale = self.transform().m11()

        elif gesture.state() == Qt.GestureState.GestureUpdated and self._pinch_mode:
            target_scale = self._pinch_start_view_scale * gesture.scaleFactor()

            # Clamp to ViewportController's configured limits
            min_scale = config.zoom_factor_base ** config.min_zoom_level
            max_scale = config.zoom_factor_base ** config.max_zoom_level
            target_scale = max(min_scale, min(target_scale, max_scale))
            target_scale = max(0.1, min(target_scale, 10.0))  # Absolute limits

            current_view_scale = self.transform().m11()
            if abs(target_scale - current_view_scale) > 0.001:
                zoom_factor_to_apply = target_scale / current_view_scale
                self.scale(zoom_factor_to_apply, zoom_factor_to_apply)
                self.zoom_changed.emit(self.transform().m11())

        elif gesture.state() == Qt.GestureState.GestureFinished:
            self._pinch_mode = False
            # Sync ViewportController state with current scale
            current_scale = self.transform().m11()
            if current_scale > 0:
                self._viewport_controller.zoom_to_scale(current_scale)

    # --- Zoom Methods (delegated to ViewportController) ---

    def zoom(self, step: int):
        """Zooms the view by a given step. Delegates to ViewportController."""
        if step > 0:
            self._viewport_controller.zoom_in(step)
        elif step < 0:
            self._viewport_controller.zoom_out(-step)

    def zoom_in(self, steps: int = 1):
        """Zoom in by specified steps. Delegates to ViewportController."""
        self._viewport_controller.zoom_in(steps)

    def zoom_out(self, steps: int = 1):
        """Zoom out by specified steps. Delegates to ViewportController."""
        self._viewport_controller.zoom_out(steps)


    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press events based on the current mode."""
        scene_pos = self.mapToScene(event.pos())

        # --- Panning --- (Middle button, Alt+Left, or Right button)
        if (event.button() == Qt.MouseButton.MiddleButton or
            event.button() == Qt.MouseButton.RightButton or
            (event.button() == Qt.MouseButton.LeftButton
             and event.modifiers() & Qt.KeyboardModifier.AltModifier)):
            self._panning = True
            self._pan_start_pos = event.pos()
            self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
            # Do not call super().mousePressEvent(event) here to prevent unwanted item selection during pan attempt.
            return

        # --- Mode-Specific Handling --- (Left Button primarily)
        if event.button() == Qt.MouseButton.LeftButton:
            if self.current_mode == "define_joint":
                self._handle_joint_definition_click(scene_pos, event.pos())
            elif self.current_mode == "define_motion_path":
                # When starting a new path drawing, clear any previous points for this drawing session
                self._motion_path_points.clear()
                self._motion_path_points.append(scene_pos)
                self._is_drawing_freehand = True
                self._update_motion_path_preview()  # Ensure preview starts/clears appropriately
            elif self.current_mode == "select_end_effector":
                self._handle_end_effector_selection_click(scene_pos)
            elif self.current_mode == "select_cam_center":
                self.cam_center_selected.emit(scene_pos)
                self.set_mode("select")
            elif self.current_mode == "select_pivot_a":
                self.pivot_a_selected.emit(scene_pos)
                self.set_mode("select")
            elif self.current_mode == "select_pivot_d":
                self.pivot_d_selected.emit(scene_pos)
                self.set_mode("select")
            elif self.current_mode == "select_driver_center":
                self.driver_center_selected.emit(scene_pos)
                self.set_mode("select")
            elif self.current_mode == "select_driven_center":
                self.driven_center_selected.emit(scene_pos)
                self.set_mode("select")
            else:  # Default to 'select' mode behavior or general item interaction
                super().mousePressEvent(
                    event
                )  # IMPORTANT: Call super for item selection, drag, etc.
                # Now that super has handled selection, check if a CharacterPartItem was clicked
                # Re-fetch item_at_click as super() might change focus or selection state
                # selected_items = self.scene().selectedItems()
                # if len(selected_items) == 1 and isinstance(selected_items[0], CharacterPartItem):
                #    clicked_part_item = selected_items[0]
                #    self.part_item_clicked.emit(clicked_part_item)
                # Check item directly under cursor AFTER super call if super() doesn't select
                final_item_at_click = self.itemAt(event.pos())  # item after super call
                if isinstance(final_item_at_click, CharacterPartItem):
                    self.part_item_clicked.emit(final_item_at_click)
                # else: # Click was on background or non-CharacterPartItem
                # super().mousePressEvent(event) was already called
        elif event.button() == Qt.MouseButton.RightButton:
            # Right click cancels drawing modes and point selection modes
            if self.current_mode == "define_motion_path":
                self._cancel_motion_path_drawing()  # This now also emits drawing_cancelled
                # self.drawing_cancelled.emit() # _cancel_motion_path_drawing should handle this
            elif self.current_mode == "define_joint":
                self._reset_joint_definition()
            elif self.current_mode.startswith("select_"):
                logging.info(
                    f"Point selection mode '{self.current_mode}' cancelled by right-click."
                )
                self.set_mode("select")  # Cancel point selection
                # Optionally emit a cancellation signal if needed by MainWindow
            else:
                # Allow context menu in select mode
                super().mousePressEvent(event)
        else:
            # Allow other buttons to be handled by base class
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle mouse release, primarily to stop panning and finalize freehand path."""
        # 🔧 PANNING FIX: More robust panning state reset
        if self._panning:
            # Check if the released button matches any panning button
            if (event.button() == Qt.MouseButton.MiddleButton
                or event.button() == Qt.MouseButton.RightButton
                or (event.button() == Qt.MouseButton.LeftButton
                    and event.modifiers() & Qt.KeyboardModifier.AltModifier)):
                self._panning = False
                self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
                logging.debug(f"Panning stopped - button: {event.button()}")
                super().mouseReleaseEvent(event)
                return
            # Also check for any button release when panning (safety fallback)
            elif event.button() in [Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton, Qt.MouseButton.MiddleButton]:
                self._panning = False
                self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
                logging.debug(f"Panning force-stopped - fallback for button: {event.button()}")
                super().mouseReleaseEvent(event)
                return

        if event.button() == Qt.MouseButton.LeftButton:
            if self.current_mode == "define_motion_path" and self._is_drawing_freehand:
                num_original_points = len(self._motion_path_points)
                if (
                    num_original_points >= 3
                ):  # Need at least 3 points for a meaningful curve
                    # Resample points
                    # If fewer than TARGET_PATH_POINTS but >=3, use original points for spline for better representation
                    # If more than TARGET_PATH_POINTS, resample down to TARGET_PATH_POINTS
                    # _resample_points_simple currently pads if less, which might not be ideal for spline if too few.
                    # Let's adjust the logic for spline points preparation here.

                    points_for_spline = []
                    if num_original_points < TARGET_PATH_POINTS:
                        # If we have 3 to TARGET_PATH_POINTS-1 points, use them directly for the spline.
                        # The spline creation will handle fewer points appropriately.
                        points_for_spline = list(self._motion_path_points)
                    else:
                        # If more than or equal to TARGET_PATH_POINTS, resample to exactly TARGET_PATH_POINTS.
                        points_for_spline = self._resample_points_simple(
                            list(self._motion_path_points), TARGET_PATH_POINTS
                        )

                    if not points_for_spline or len(points_for_spline) < 3:
                        logging.warning(
                            f"Not enough points ({len(points_for_spline)}) for spline after resampling from {num_original_points}. Cancelling path."
                        )
                        self._cancel_motion_path_drawing()
                        self._is_drawing_freehand = False
                        self.set_mode("select")
                        super().mouseReleaseEvent(event)  # Call base before returning
                        return

                    # Create the final spline path (open or closed based on user selection)
                    final_path_data = self._create_spline_path(
                        points_for_spline, closed_loop=self.current_path_is_closed, tension=0.5
                    )

                    final_path_item = QGraphicsPathItem()
                    # User modified pen thickness to 5.0
                    final_pen = QPen(QColor(0, 200, 0), 5.0)  # Green, solid, very thick
                    final_pen.setCosmetic(True)
                    final_path_item.setPen(final_pen)
                    final_path_item.setPath(final_path_data)
                    final_path_item.setZValue(
                        Z_MOTION_PATH_PREVIEW - 1
                    )  # Draw below future previews

                    # Determine component_key for this path
                    component_key = None
                    if (
                        self.parent_window
                        and hasattr(self.parent_window, "selected_part_name")
                        and self.parent_window.selected_part_name
                    ):
                        component_key = self.parent_window.selected_part_name
                    elif (
                        self.current_target_item_for_path
                    ):  # Fallback if selected_part_name is not available
                        component_key = self.current_target_item_for_path.part_info.name

                    if component_key:
                        # Remove previous final path for this component, if any
                        if component_key in self.final_paths_map:
                            old_path_item = self.final_paths_map.pop(component_key)
                            if old_path_item and old_path_item.scene():
                                self.scene().removeItem(old_path_item)
                                logging.debug(
                                    f"Removed previous final path for component '{component_key}'."
                                )

                        self.scene().addItem(final_path_item)
                        self.final_paths_map[component_key] = final_path_item
                        logging.debug(
                            f"Added final path for component '{component_key}'."
                        )
                    else:
                        # If no key, path is orphaned, but still add to scene for now (might be an error condition)
                        self.scene().addItem(final_path_item)
                        logging.warning(
                            "Final path created without a component key. It might be orphaned."
                        )

                    # Emit the RESAMPLED points for external handling (e.g., by IKManager)
                    # as these are the points that define the final visual shape.
                    self.freehandPathCompleted.emit(points_for_spline)
                    path_type_str = "closed" if self.current_path_is_closed else "open"
                    logging.debug(
                        f"Completed and finalized {path_type_str} spline motion path with {len(points_for_spline)} points (resampled from {num_original_points})."
                    )

                    # Clear the red dashed preview path
                    if (
                        self._motion_preview_path_item
                        and self._motion_preview_path_item.scene()
                    ):
                        self.scene().removeItem(self._motion_preview_path_item)
                        self._motion_preview_path_item = None
                    self._motion_path_points.clear()  # Clear original drawn points for next session

                else:  # Path had less than 3 points originally, not enough for a curve
                    logging.debug(
                        f"Freehand path too short ({num_original_points} points), cancelling. Need at least 3 for a curve."
                    )
                    self._cancel_motion_path_drawing()  # Clears preview, resets state

                self._is_drawing_freehand = False
                self.set_mode("select")  # Switch to select mode

        super().mouseReleaseEvent(event)  # Call base for other release events

    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move events for panning, drawing, and hover controls."""
        scene_pos = self.mapToScene(event.pos())

        if self._panning:
            # 🔧 IMPROVED PANNING: Direct view transform for smooth panning feel
            delta = event.pos() - self._pan_start_pos
            self._pan_start_pos = event.pos()

            # Apply translation directly to the view transform
            current_transform = self.transform()
            current_transform.translate(delta.x() * self._pan_sensitivity, delta.y() * self._pan_sensitivity)
            self.setTransform(current_transform)
            return

        if (
            self.current_mode == "define_motion_path"
            and self._is_drawing_freehand
            and self._motion_path_points
        ):
            self._motion_path_points.append(scene_pos)
            self._update_motion_path_preview()
        else:
            super().mouseMoveEvent(event)
            # After super().mouseMoveEvent, which handles item dragging if ItemIsMovable,
            # check if a selected CharacterPartItem was moved.
            # This relies on the item being selected and moved by QGraphicsView's default drag.
            # This is a bit indirect. A more robust way is for CharacterPartItem.itemChange
            # to emit a signal (if it could), or for EditorView to track drags.
            # For now, let's assume standard dragging updates item.pos().
            # We need a way to know *which* item finished moving. QGraphicsItem.ItemPositionHasChanged
            # is emitted by the item itself. If CharacterPartItem cannot emit signals, EditorView
            # might need to listen to scene selection changes and then monitor position of selected items.
            # This signal is tricky to implement robustly from EditorView without item cooperation.
            # Let's defer emitting part_item_moved from here unless a clear mechanism is found.

        # Handle hover controls visibility (merged from duplicate method)
        view_rect = self.rect()
        corner_size = 150  # Size of the corner area to trigger controls

        view_rect.adjusted(
            view_rect.width() - corner_size,
            view_rect.height() - corner_size,
            0, 0
        )

        # 🔧 VIEW CONTROLS FIX: Hover controls disabled
        # if corner_rect.contains(event.pos()):
        #     self.hover_controls.show_controls()
        #     # Update zoom level display
        #     current_scale = self.transform().m11()
        #     zoom_percentage = current_scale * 100
        #     self.hover_controls.set_zoom_level(zoom_percentage)

    def keyPressEvent(self, event: QEvent):
        """Handle keyboard shortcuts."""
        if event.key() == Qt.Key.Key_Escape:
            if self.current_mode == "define_joint":
                self._reset_joint_definition()
            elif self.current_mode == "define_motion_path":
                self._cancel_motion_path_drawing()
            elif self.current_mode == "select_end_effector":
                self.set_mode("select")
                self._show_status_message("End effector selection cancelled")
            elif self.current_mode == "select_cam_center":
                self.set_mode("select")
                self._show_status_message("Cam center selection cancelled")
            else:
                super().keyPressEvent(event)
            return

        # Ctrl+0 for reset view
        if (
            event.key() == Qt.Key.Key_0
            and event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            self.reset_view()
            return

        super().keyPressEvent(event)

    # --- Context Menu ---

    def show_context_menu(self, pos: QPointF):
        """Show context menu for the view."""
        menu = QMenu(self)
        zoom_in_action = menu.addAction("Zoom In")
        zoom_out_action = menu.addAction("Zoom Out")
        zoom_fit_action = menu.addAction("Zoom to Fit")
        menu.addSeparator()
        reset_action = menu.addAction("Reset View")

        # Connect actions
        zoom_in_action.triggered.connect(lambda: self.scale(1.15, 1.15))
        zoom_out_action.triggered.connect(lambda: self.scale(1 / 1.15, 1 / 1.15))
        zoom_fit_action.triggered.connect(self.zoom_to_fit)
        reset_action.triggered.connect(self.reset_view)

        selected_item = self.get_selected_item()
        if selected_item:
            menu.addAction(
                f"Set '{selected_item.part_info.name}' as Cam Follower",
                lambda: self.parent_window.set_cam_follower(),
            )

        # Execute menu at global position
        global_pos = self.mapToGlobal(pos)
        menu.exec(global_pos)

    # --- View Control (delegated to ViewportController) ---

    def reset_view(self):
        """Reset zoom and pan to default. Delegates to ViewportController."""
        self._viewport_controller.reset_view()
        self._show_status_message("View reset")

    def zoom_to_fit(self):
        """Zoom to fit all items in the view. Delegates to ViewportController."""
        self._viewport_controller.zoom_to_fit(margin=20)
        current_scale = self.transform().m11()
        self._show_status_message(
            f"Zoom to fit ({current_scale:.1f}x, level {self._viewport_controller.zoom_level})"
        )

    # --- Joint Definition --- #


    def _handle_joint_definition_click(self, scene_pos: QPointF, view_pos: QPointF):
        item_at_click = self.itemAt(view_pos)  # Use view_pos for itemAt

        # Ensure a CharacterPartItem is clicked
        if not isinstance(item_at_click, CharacterPartItem):
            logging.debug("Joint definition click missed a character part.")
            # Optionally show a status message
            # self._show_status_message("Please click on a character part.")
            return

        if self._joint_parent_item is None:
            # First click: select parent item and mark joint point on it
            self._joint_parent_item = item_at_click
            self._joint_parent_pos = item_at_click.mapFromScene(
                scene_pos
            )  # Store local pos
            # Update status or visual cue
            self.setCursor(Qt.CursorShape.CrossCursor)  # Change cursor
            logging.info(
                f"Joint parent selected: {self._joint_parent_item.part_info.name}, local pos: {self._joint_parent_pos}"
            )
            self._show_status_message(
                f"Selected {self._joint_parent_item.part_info.name} as parent. Click another part to define joint."
            )

        elif (
            self._joint_parent_item
        ):  # If parent is already selected, this click is for child
            if item_at_click == self._joint_parent_item:
                logging.debug(
                    "Clicked the same item again for joint definition. Resetting."
                )
                self._reset_joint_definition_state()
                self._show_status_message("Joint definition reset. Click first part.")
                return

            # Ensure child item is different from parent
            self._joint_child_item = item_at_click
            self._joint_child_pos = item_at_click.mapFromScene(scene_pos)
            logging.info(
                f"Joint child selected: {item_at_click.part_info.name}, local pos: {self._joint_child_pos}. Emitting joint_defined."
            )

            # Emit signal with all necessary data
            self.joint_defined.emit(
                {
                    "parent_item_name": self._joint_parent_item.part_info.name,
                    "child_item_name": self._joint_child_item.part_info.name,
                    "parent_pos_local": self._joint_parent_pos,  # QPointF
                    "child_pos_local": self._joint_child_pos,  # QPointF
                }
            )
            logging.info(
                f"Joint defined between {self._joint_parent_item.part_info.name} and {self._joint_child_item.part_info.name}"
            )
            self._show_status_message(
                f"Joint defined: {self._joint_parent_item.part_info.name} <> {self._joint_child_item.part_info.name}. Define another or switch mode."
            )

            # Reset for next joint definition
            self._reset_joint_definition_state()  # Keep markers until mode change

    def _reset_joint_definition_state(self):
        """Resets only the state for defining the *next* joint, keeps markers for completed one."""
        self._joint_parent_item = None
        self._joint_parent_pos = None
        # self._joint_parent_item_marker is not cleared here, cleared in _reset_joint_definition

    def _reset_joint_definition(self):
        """Full reset of joint definition mode, including visuals."""
        if self._joint_parent_item_marker and self._joint_parent_item_marker.scene():
            self.scene().removeItem(self._joint_parent_item_marker)
            self._joint_parent_item_marker.setParentItem(
                None
            )  # Clear parent before removing from scene
            self._joint_parent_item_marker = None
        self._reset_joint_definition_state()
        logging.debug("Joint definition mode reset.")
        self._show_status_message("Joint definition cancelled.")

    # --- Motion Path Definition --- #

    def start_define_motion_path(self, target_item: CharacterPartItem | None, is_closed: bool = True):
        """Starts the freehand motion path definition mode."""
        if self.current_mode == "define_motion_path":
            return  # Already in this mode

        if target_item is None and not getattr(self.parent_window, 'selected_part_name', None):
            logging.warning(
                "EditorView: start_define_motion_path called with no target_item and no selected part."
            )

        # Determine component key for path clearing
        component_key = None
        if target_item and target_item.part_info and target_item.part_info.name:
            component_key = target_item.part_info.name
        elif hasattr(self.parent_window, 'selected_part_name') and self.parent_window.selected_part_name:
            component_key = self.parent_window.selected_part_name

        # Delegate to MotionPathManager - it handles clearing existing paths
        self._motion_path_drawer.start_drawing(target_item, is_closed, component_key)

        # Update EditorView state for compatibility
        self.current_target_item_for_path = target_item
        self.current_path_is_closed = is_closed
        self.current_freehand_path = QPainterPath()
        self.current_freehand_path_item = None
        self.set_mode("define_motion_path")
        self.setCursor(Qt.CursorShape.CrossCursor)
        logging.info("EditorView: Entered freehand motion path definition mode.")
        if target_item:
            logging.info(f"EditorView: Motion path target: {target_item.part_info.name}")


    def _cancel_motion_path_drawing(self):
        """Cancels the current motion path drawing operation and cleans up."""
        logging.debug("Motion path drawing cancelled.")
        # Delegate to MotionPathManager - it handles cleanup and emits drawing_cancelled
        self._motion_path_drawer.cancel_drawing()
        # Also reset EditorView state for compatibility
        self.current_target_item_for_path = None
        self._is_drawing_freehand = False
        self._motion_path_points.clear()
        self._cleanup_motion_path_visuals()
        if self.current_mode == "define_motion_path":
            self.set_mode("select")
        self._show_status_message("Motion path definition cancelled.")

    def _cleanup_motion_path_visuals(self, _keep_target: bool = False) -> None:
        """Clears temporary visuals used for motion path definition (preview path)."""
        if self._motion_preview_path_item:
            if self._motion_preview_path_item.scene():
                self.scene().removeItem(self._motion_preview_path_item)
            self._motion_preview_path_item = None
        logging.debug("Cleaned up motion path preview visuals.")

    # --- End Effector Selection --- #


    def _handle_end_effector_selection_click(self, scene_pos: QPointF):
        """Handles the click to set the end effector position."""
        if not self._target_part_for_end_effector:
            self.set_mode("select")  # Should not happen, but reset if it does
            return

        local_pos = self._target_part_for_end_effector.mapFromScene(scene_pos)
        self.end_effector_selected.emit(local_pos, scene_pos)  # Emit signal
        self._target_part_for_end_effector.end_effector_offset = (
            local_pos  # Update item directly
        )
        self._target_part_for_end_effector._update_end_effector_marker()  # Update visual
        self._show_status_message(
            f"End effector set for '{self._target_part_for_end_effector.part_info.name}'"
        )
        self.set_mode("select")  # Return to select mode

    # --- Simulation Control --- #

        # Parent window likely starts the timer/updates

        # Parent window likely stops the timer/updates


    def _restore_original_transforms(self):
        """Restores the saved transforms of all part items."""
        logging.debug(
            f"Restoring {len(self._original_transforms)} original item transforms."
        )
        for item_name, initial_transform in self._original_transforms.items():
            item = self.parent_window.editor_items.get(item_name)
            if (
                item and item.scene() == self.scene()
            ):  # Check if item still exists in the scene
                # logging.debug(f"  Restoring {item_name}: transform={initial_transform}")
                item.setTransform(initial_transform)
            else:
                logging.warning(
                    f"Could not restore transform for {item_name}: Item not found or not in scene."
                )

        self.scene().update()

    def _reset_simulation_state(self):
        """Ensures the view is interactive after simulation stops/resets."""
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setInteractive(True)

    # --- Skeleton Visualization --- #


    def visualize_skeleton(
        self, skeleton_data: list[dict[str, Any]], hierarchy_data: dict[str, list[str]]
    ):
        """
        Visualizes the skeleton using SkeletonGraphicsItem.
        The skeleton_data should be a list of joint dictionaries as expected by SkeletonGraphicsItem.
        Example: [{'id': 'neck', 'position': [100,100], 'parent': 'torso'}, ...]
        """
        logging.debug(
            f"EditorView:visualize_skeleton - Received skeleton_data (count: {len(skeleton_data)}): {skeleton_data}"
        )
        logging.debug(
            f"EditorView:visualize_skeleton - Received hierarchy_data (keys: {list(hierarchy_data.keys()) if hierarchy_data else 'None'}): {hierarchy_data}"
        )

        if not self.scene():
            logging.error("EditorView: No scene available to visualize skeleton.")
            return

        if (
            not skeleton_data
        ):  # This now implies skeleton_data is an empty list if clearing
            # If skeleton_data is empty or None, clear the current skeleton display
            if self.skeleton_graphics_item:
                logging.debug(
                    "EditorView: visualize_skeleton - Clearing existing skeleton item."
                )
                # load_skeleton_data with empty data will clear it
                self.skeleton_graphics_item.load_skeleton_data(
                    [], {}
                )  # Pass empty hierarchy too
            else:
                logging.debug(
                    "EditorView: visualize_skeleton - No skeleton data and no existing item to clear."
                )
            return

        if self.skeleton_graphics_item is None:
            logging.debug(
                "EditorView: visualize_skeleton - Creating new SkeletonGraphicsItem."
            )
            # Pass both skeleton_data and hierarchy_data to the constructor or load_skeleton_data
            self.skeleton_graphics_item = SkeletonGraphicsItem(
                skeleton_data, hierarchy_data, mechanism_mode=self.mechanism_mode
            )
            self.scene().addItem(self.skeleton_graphics_item)
            self.skeleton_graphics_item.setZValue(Z_SKELETON_OVERLAY)

            # Connect the joint_clicked signal
            self.skeleton_graphics_item.joint_clicked.connect(self._handle_joint_bend_direction_changed)
        else:
            logging.debug(
                "EditorView: visualize_skeleton - Updating existing SkeletonGraphicsItem."
            )
            # Disconnect existing signal connections to avoid duplicates
            try:
                self.skeleton_graphics_item.joint_clicked.disconnect()
            except (TypeError, RuntimeError):
                pass  # No connections to disconnect or object deleted

            # Call load_skeleton_data with both skeleton_data and hierarchy_data
            self.skeleton_graphics_item.load_skeleton_data(
                skeleton_data, hierarchy_data
            )

            # Reconnect the signal
            self.skeleton_graphics_item.joint_clicked.connect(self._handle_joint_bend_direction_changed)
            logging.debug("EditorView: Reconnected joint_clicked signal after skeleton reload")

        self.scene().update()  # Trigger a repaint of the scene  # Trigger a repaint of the scene

    def update_skeleton_animation(
        self, animated_joint_positions: dict[str, tuple[float, float]]
    ):
        """Updates the skeleton item with new animated joint positions."""
        logging.debug(
            f"EditorView:update_skeleton_animation - Received animated_joint_positions (count: {len(animated_joint_positions)}): {animated_joint_positions if len(animated_joint_positions) < 5 else str(list(animated_joint_positions.items())[:5]) + '...'}"
        )
        if self.skeleton_graphics_item:  # Check if skeleton_graphics_item exists
            self.skeleton_graphics_item.set_animated_pose(
                animated_joint_positions
            )  # Corrected method name
        else:
            logging.warning(
                "EditorView:update_skeleton_animation - skeleton_graphics_item is None. Cannot update pose."
            )

    def update_visuals_from_animation_data(self, joint_data: dict[str, dict[str, Any]]):
        """Updates skeleton and part visuals based on joint-centric animation data with FABRIK constraint preservation."""
        if not self.scene():
            logging.warning("EditorView: No scene available for animation update.")
            return

        # 1. Update Skeleton Visualization
        # Extract all joint positions for the skeleton item
        all_joint_positions: dict[str, tuple[float, float]] = {}
        for (
            joint_id,
            data,
        ) in joint_data.items():  # joint_id here is the key from the input joint_data
            pos = data.get("scene_position")
            if pos and isinstance(pos, QPointF):
                all_joint_positions[joint_id] = (pos.x(), pos.y())
            # else: logging.warning(f"Joint {joint_id} missing scene_position in animation data") # Can be noisy

        if self.skeleton_graphics_item:
            self.skeleton_graphics_item.set_animated_pose(all_joint_positions)
        else:
            logging.warning(
                "EditorView: SkeletonGraphicsItem not available to update animated pose."
            )

        # 2. Update CharacterPartItems WITH SKELETON LENGTH VALIDATION
        # Iterate over known CharacterPartItems from the parent EditorTab for efficiency
        if hasattr(self.parent_window, "current_editor_items") and isinstance(
            self.parent_window.current_editor_items, dict
        ):
            for part_item in self.parent_window.current_editor_items.values():
                if not isinstance(
                    part_item, CharacterPartItem
                ):  # Should not happen if current_editor_items is well-maintained
                    continue

                original_anchor_joint_name = (
                    part_item.anchor_joint_id
                )  # This is an ORIGINAL NAME (e.g., "left_shoulder")

                if not original_anchor_joint_name:
                    # logging.debug(f"Part item '{part_item.name()}' has no anchor_joint_id. Skipping animation update for it.")
                    continue

                standardized_anchor_joint_id = self._joint_map_original_to_std.get(
                    original_anchor_joint_name
                )

                if not standardized_anchor_joint_id:
                    logging.warning(
                        f"EditorView: Could not find standardized ID for part '{part_item.name()}'s original anchor joint '{original_anchor_joint_name}'. Joint map has {len(self._joint_map_original_to_std)} entries. Skipping part update."
                    )
                    continue

                if standardized_anchor_joint_id not in joint_data:
                    logging.warning(
                        f"EditorView: Standardized anchor joint '{standardized_anchor_joint_id}' (orig: '{original_anchor_joint_name}') for part '{part_item.name()}' not found as a key in joint_data. Skipping part update."
                    )
                    continue

                joint_transform_data = joint_data[standardized_anchor_joint_id]
                target_joint_scene_pos = joint_transform_data.get("scene_position")
                target_part_world_rotation = joint_transform_data.get(
                    "world_rotation_degrees", part_item.rotation()
                )

                if not isinstance(target_joint_scene_pos, QPointF):
                    logging.warning(
                        f"Invalid or missing 'scene_position' for joint '{standardized_anchor_joint_id}' affecting part '{part_item.name()}'. Skipping position update."
                    )
                    continue

                # 🔧 CRITICAL FIX: Validate skeleton length preservation before applying position
                new_position_valid = self._validate_skeleton_length_preservation(
                    part_item, target_joint_scene_pos, joint_data
                )

                if new_position_valid:
                    # Apply the calculated world rotation
                    part_item.setRotation(float(target_part_world_rotation))
                    # Use bypass for legitimate animation - the validation was done above
                    part_item.set_scene_position_from_anchor(target_joint_scene_pos, bypass_validation=True)
                else:
                    # Skip position update that would violate skeleton constraints
                    logging.debug(f"Skeleton length constraint violation prevented for part '{part_item.name()}'")
                    # Still update rotation if valid
                    if target_part_world_rotation is not None:
                        part_item.setRotation(float(target_part_world_rotation))
        else:
            logging.warning(
                "EditorView: parent_window (EditorTab) does not have current_editor_items or it's not a dict. Cannot update part visuals."
            )

        self.scene().update()  # Update scene once after all items are processed

    def _validate_skeleton_length_preservation(
        self,
        part_item: CharacterPartItem,
        new_anchor_pos: QPointF,
        joint_data: dict[str, dict[str, Any]]
    ) -> bool:
        """
        Validates that applying a new position won't violate skeleton bone length constraints.

        Args:
            part_item: The part being moved
            new_anchor_pos: Proposed new anchor position (currently unused in basic implementation)
            joint_data: Current joint data with positions

        Returns:
            True if the new position preserves skeleton constraints, False otherwise
        """
        # Define bone length tolerance (matching FABRIK solver constraint)
        MAX_BONE_LENGTH_DEVIATION = 0.01  # 1% tolerance for floating point precision

        # Check if this part is connected to other joints in a bone chain
        connected_joints = self._get_connected_joints_for_part(part_item, joint_data)

        for parent_joint_id, child_joint_id, expected_length in connected_joints:
            # Get current positions
            parent_data = joint_data.get(parent_joint_id)
            child_data = joint_data.get(child_joint_id)

            if not parent_data or not child_data:
                continue

            parent_pos = parent_data.get("scene_position")
            child_pos = child_data.get("scene_position")

            if not isinstance(parent_pos, QPointF) or not isinstance(child_pos, QPointF):
                continue

            # Calculate current bone length
            from PyQt6.QtCore import QLineF
            current_length = QLineF(parent_pos, child_pos).length()

            # Check if length deviation exceeds tolerance
            if expected_length > 0:
                length_deviation = abs(current_length - expected_length) / expected_length
                if length_deviation > MAX_BONE_LENGTH_DEVIATION:
                    logging.debug(
                        f"Skeleton length violation: {parent_joint_id}->{child_joint_id} "
                        f"expected={expected_length:.1f}, current={current_length:.1f}, "
                        f"deviation={length_deviation:.3f} > {MAX_BONE_LENGTH_DEVIATION}"
                    )
                    return False

        # If we reach here, all bone lengths are within tolerance
        return True

    def _get_connected_joints_for_part(
        self,
        part_item: CharacterPartItem,
        joint_data: dict[str, dict[str, Any]]
    ) -> list[tuple[str, str, float]]:
        """
        Get the bone connections (parent-child joint pairs) that this part participates in.

        Returns:
            List of tuples: (parent_joint_id, child_joint_id, expected_bone_length)
        """
        connections = []

        # This is a simplified implementation - in a full system, you'd want to:
        # 1. Get the original bone lengths from the IK system initialization
        # 2. Track which parts correspond to which bones in the skeleton
        # 3. Use a proper skeleton hierarchy to find connections

        # For now, we'll do basic validation by checking if this part has
        # joint relationships defined in the current animation data
        part_anchor_joint = part_item.anchor_joint_id
        if not part_anchor_joint:
            return connections

        # Map original joint name to standardized ID
        standardized_joint_id = self._joint_map_original_to_std.get(part_anchor_joint)
        if not standardized_joint_id or standardized_joint_id not in joint_data:
            return connections

        # For this simplified fix, we'll assume bone lengths should remain constant
        # A more complete implementation would maintain a bone length database
        # from the initial skeleton setup

        # Basic bone length estimation from current positions
        # This is not ideal but provides basic protection against extreme violations
        for other_joint_id, other_data in joint_data.items():
            if other_joint_id == standardized_joint_id:
                continue

            other_pos = other_data.get("scene_position")
            current_pos = joint_data[standardized_joint_id].get("scene_position")

            if isinstance(other_pos, QPointF) and isinstance(current_pos, QPointF):
                from PyQt6.QtCore import QLineF
                distance = QLineF(current_pos, other_pos).length()

                # Only consider reasonable bone lengths (not too short or too long)
                if 20 < distance < 200:  # Reasonable pixel distance for character parts
                    connections.append((standardized_joint_id, other_joint_id, distance))

        return connections



    # --- Utility --- #

    def _show_status_message(self, message: str):
        """Safely displays a message in the parent window's status bar."""
        if self.parent_window and hasattr(self.parent_window, "statusBar"):
            self.parent_window.statusBar().showMessage(
                message, 5000
            )  # Show for 5 seconds
        else:
            logging.info(f"Status: {message}")  # Fallback logging

    def set_zoom_level(self, zoom_factor: float):
        """Sets the zoom level of the view.

        Args:
            zoom_factor: The desired zoom factor (e.g., 1.0 for 100%, 0.5 for 50%).
        """
        # It's generally better to transform from the current scale
        # to avoid compounding errors or drifting from the original identity matrix.
        # However, a direct scale set is often what's intended by "set_zoom_level".

        # Get current transform
        current_transform = self.transform()

        # Reset scaling part of the transform to identity
        # M11 = sx, M22 = sy
        # Assuming isotropic scaling (sx = sy)
        current_scale_x = current_transform.m11()
        current_scale_y = current_transform.m22()

        if (
            current_scale_x == 0 or current_scale_y == 0
        ):  # Avoid division by zero if already scaled to nothing
            logging.warning(
                "EditorView: Current scale is zero, cannot apply relative zoom. Resetting to new zoom_factor."
            )
            self.resetTransform()  # Reset to identity before applying new scale
            self.scale(zoom_factor, zoom_factor)
            return

        # Calculate how much to scale from current to get to zoom_factor
        scale_x_needed = zoom_factor / current_scale_x
        scale_y_needed = zoom_factor / current_scale_y

        self.scale(scale_x_needed, scale_y_needed)
        logging.info(
            f"EditorView: Zoom set to {zoom_factor:.2f}x. Current transform m11: {self.transform().m11():.2f}"
        )

    def _update_motion_path_preview(self):
        """Updates the visual preview of the motion path being drawn."""
        if not self._is_drawing_freehand or not self._motion_path_points:
            if self._motion_preview_path_item:  # Clear if not drawing or no points
                if self._motion_preview_path_item.scene():
                    self.scene().removeItem(self._motion_preview_path_item)
                self._motion_preview_path_item = None
            return

        if len(self._motion_path_points) < 2:  # Need at least two points to draw a line
            if self._motion_preview_path_item:  # Clear if less than 2 points
                if self._motion_preview_path_item.scene():
                    self.scene().removeItem(self._motion_preview_path_item)
                self._motion_preview_path_item = None
            return

        path = QPainterPath()
        path.moveTo(self._motion_path_points[0])
        for point in self._motion_path_points[1:]:
            path.lineTo(point)

        if self._motion_preview_path_item is None:
            self._motion_preview_path_item = QGraphicsPathItem()
            # Updated pen style for drawing phase
            pen = QPen(QColor(255, 0, 0, 180), 4.0)  # Red, thicker, semi-transparent
            pen.setStyle(Qt.PenStyle.DashLine)
            pen.setCosmetic(True)  # Ensures consistent thickness regardless of zoom
            self._motion_preview_path_item.setPen(pen)
            self._motion_preview_path_item.setZValue(
                Z_MOTION_PATH_PREVIEW
            )  # Use the new Z-index
            self.scene().addItem(self._motion_preview_path_item)

        self._motion_preview_path_item.setPath(path)
        # logging.debug(f"Motion path preview updated with {len(self._motion_path_points)} points.")

    def _create_spline_path(
        self, points: list[QPointF], closed_loop: bool = False, tension: float = 0.5
    ) -> QPainterPath:
        """Creates a QPainterPath from a list of points using Catmull-Rom like splines (approximated with Bezier curves)."""
        path = QPainterPath()
        if not points or len(points) < 2:
            # If only one point, move to it. If empty, return empty path.
            if len(points) == 1:
                path.moveTo(points[0])
            return path

        n = len(points)
        path.moveTo(points[0])

        if n < 2:  # Should have been caught above, but defensive
            return path

        # If only 2 points, draw a straight line
        if n == 2:
            path.lineTo(points[1])
            if closed_loop:
                path.lineTo(points[0])  # Close the loop
            return path

        # For Catmull-Rom like splines, we need to calculate control points
        # for each segment P_i to P_{i+1}. The control points depend on P_{i-1} and P_{i+2}.

        # Create a list of points for easy looping, handling closed loops
        plot_points = list(points)  # Make a mutable copy
        if closed_loop:
            # For a closed loop, extend the list with points from the other end to calculate edge control points
            # P[-1], P[0], P[1], P[2], ... P[n-1], P[n], P[n+1] (where P[n]=P[0], P[n+1]=P[1] etc.)
            plot_points.insert(0, points[n - 1])  # P[-1] = P[n-1]
            plot_points.append(points[0])  # P[n]   = P[0]
            plot_points.append(points[1])  # P[n+1] = P[1]
        else:
            # For open loop, duplicate first and last points to handle endpoints
            plot_points.insert(0, points[0])  # P[-1] = P[0]
            plot_points.append(points[n - 1])  # P[n]   = P[n-1]

        # Iterate through the original points (from index 1 to n if open, or 1 to n+1 if closed for segments)
        # The actual segments are from points[i] to points[i+1]
        # plot_points indices will be one more than original points indices due to prepended point.

        for i in range(
            1, len(plot_points) - 2
        ):  # Iterate up to the point before the last two extended points
            p0 = plot_points[i - 1]
            p1 = plot_points[i]  # Current point (start of Bezier segment)
            p2 = plot_points[i + 1]  # Next point (end of Bezier segment)
            p3 = plot_points[i + 2]

            # Adjusting the scaling factor for control points might make the curve "gentler"
            control_point_scale_factor = (
                tension / 3
            )  # tension is 0.5 by default, so factor is ~0.167

            # Calculate Bezier control points for segment p1 to p2
            # Control point 1: p1 + (p2 - p0) * control_point_scale_factor
            cp1_x = p1.x() + (p2.x() - p0.x()) * control_point_scale_factor
            cp1_y = p1.y() + (p2.y() - p0.y()) * control_point_scale_factor
            cp1 = QPointF(cp1_x, cp1_y)

            # Control point 2: p2 - (p3 - p1) * control_point_scale_factor
            cp2_x = p2.x() - (p3.x() - p1.x()) * control_point_scale_factor
            cp2_y = p2.y() - (p3.y() - p1.y()) * control_point_scale_factor
            cp2 = QPointF(cp2_x, cp2_y)

            path.cubicTo(cp1, cp2, p2)

        if closed_loop:
            # path.closeSubpath() # This might draw a straight line to close it.
            # For a smooth close, the last cubicTo should naturally lead to points[0]
            # The loop above should have handled the segment from points[n-1] to points[0]
            # if plot_points was extended correctly.
            # If not perfectly closed by the loop, QPainterPath.closeSubpath() can be used,
            # or ensure the loop handles the last segment to the first point correctly.
            # The current loop goes up to len(plot_points) - 3 segment starts.
            # For a closed loop points = [A,B,C], plot_points = [C,A,B,C,A]
            # i=1: p0=C, p1=A, p2=B, p3=C -> A to B (using C,A,B,C)
            # i=2: p0=A, p1=B, p2=C, p3=A -> B to C (using A,B,C,A)
            # i=3: p0=B, p1=C, p2=A, p3=B -> C to A (using B,C,A,B)
            # This seems correct. It will generate n cubicTo segments for n original points.
            pass  # The loop should handle closing if points are set up right.

        return path

    def _resample_points_simple(
        self, points: list[QPointF], num_target_points: int
    ) -> list[QPointF]:
        """Resamples the given points to num_target_points. Simple version."""
        if not points:
            return []
        n = len(points)
        if n == 0 or num_target_points <= 0:
            return []

        # If original points are less than target and also very few (e.g. <3 for a spline),
        # it might be better to return them as is, or an empty list if not usable.
        # For this function, we'll aim to produce num_target_points if possible.

        final_resampled: list[QPointF] = []
        if n <= num_target_points:
            final_resampled = points.copy()
            # Pad with the last point if fewer points than num_target_points
            if final_resampled:  # Check if list is not empty after copy
                while len(final_resampled) < num_target_points:
                    final_resampled.append(final_resampled[-1])
            elif num_target_points > 0:  # Original points was empty, but target > 0
                # Cannot meaningfully create points from nothing. Return empty.
                # Or raise error, or return a default point list (e.g. [QPointF(0,0)] * num_target_points)
                # For path drawing, empty is safer.
                return []
        else:  # n > num_target_points
            for i in range(num_target_points):
                # Distribute selection across the original points
                # Ensures that the first point is points[0] (for i=0)
                # and for i=num_target_points-1, index should be n-1.
                # float_idx = i * (n - 1) / (num_target_points - 1) if num_target_points > 1 else 0
                # However, simple division often works well enough for visual representation.
                idx = int(i * n / num_target_points)  # Simple distribution
                final_resampled.append(points[idx])
        return final_resampled

    def clear_visual_path_for_component(self, component_key: str):
        """Removes the final visual path associated with the given component_key from the scene and map."""
        # Delegate to MotionPathManager - it handles final path, overlays, and emits signal
        self._motion_path_drawer.clear_visual_path_for_component(component_key)
        self._show_status_message(f"Path cleared for {component_key}.")

    def get_camera_state(self) -> dict[str, Any]:
        """Get current camera state including transform and center position.

        Returns:
            Dict containing:
                - transform: QTransform matrix
                - center: QPointF of the view center
                - zoom_level: int current zoom level
        """
        # Use ViewportController's camera state with additional EditorView-specific data
        controller_state = self._viewport_controller.get_camera_state()
        center = self.mapToScene(self.viewport().rect().center())

        return {
            'transform': self.transform(),
            'center': center,
            'zoom_level': controller_state['zoom_level'],
            'h_scroll': controller_state['h_scroll'],
            'v_scroll': controller_state['v_scroll'],
        }

    def set_camera_state(self, state: dict[str, Any]):
        """Set camera state from a previously saved state.

        Args:
            state: Dict containing transform, center, and zoom_level
        """
        # Handle legacy format (transform + center) for backward compatibility
        if 'transform' in state:
            self.setTransform(state['transform'])

        if 'center' in state:
            self.centerOn(state['center'])

        # Use ViewportController for zoom_level if available
        if 'zoom_level' in state:
            self._viewport_controller.zoom_to_level(state['zoom_level'])

    def _setup_hover_controls(self):
        """Setup hover view controls - DISABLED for mouse-only control."""
        # 🔧 VIEW CONTROLS FIX: Disable hover controls, use mouse-only interaction
        # self.hover_controls = HoverViewControls(self)
        # Hover controls disabled - use right-click pan + mouse wheel zoom instead
        self.hover_controls = None

        # Position controls in bottom-right corner
        self._position_hover_controls()

        # Track mouse movement to show/hide controls
        self.setMouseTracking(True)

    def _position_hover_controls(self):
        """Position hover controls in bottom-right corner - DISABLED."""
        # 🔧 VIEW CONTROLS FIX: Hover controls disabled
        pass

    def _on_zoom_slider_changed(self, zoom_factor: float):
        """Handle zoom slider change. Uses ViewportController."""
        self._viewport_controller.zoom_to_scale(zoom_factor)

    def resizeEvent(self, event):
        """Handle resize events to reposition hover controls."""
        super().resizeEvent(event)
        self._position_hover_controls()

    def _handle_joint_bend_direction_changed(self, joint_id: str, new_direction: float):
        """Handle joint bend direction change from SkeletonGraphicsItem."""
        logging.info(f"EditorView: Joint '{joint_id}' bend direction changed to {new_direction}")

        # Emit signal to notify EditorTab and other components
        self.joint_bend_direction_changed.emit(joint_id, new_direction)

        # Update the scene
        self.scene().update()
