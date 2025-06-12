import logging
import math
from PyQt6.QtWidgets import (
    QGraphicsView,
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QGraphicsPathItem,
    QMenu,
    QGraphicsItem,
    QStyle,
    QApplication,
)
from PyQt6.QtGui import (
    QPainter,
    QPen,
    QColor,
    QBrush,
    QPainterPath,
    QMouseEvent,
    QWheelEvent,
    QTransform,
    QCursor,
    QAction,
    QIcon,
    QKeySequence,
)
from PyQt6.QtCore import (
    Qt,
    QPointF,
    QRectF,
    pyqtSignal,
    QObject,
    QLineF,
    QEvent,
    QTimer,
)
from typing import Optional, Dict, List, Any, Tuple

from ..graphics_items.part_item import CharacterPartItem  # UPDATED
from ..graphics_items.anchor_item import AnchorItem  # UPDATED
from ..graphics_items.skeleton_item import SkeletonGraphicsItem  # Added

# from ..styling import UIColors # UIColors is in main_window, pass if needed or use generic colors
from ...config.z_indices import (
    Z_MOTION_PATH_PREVIEW,
    Z_SKELETON_OVERLAY,
)  # Added Z_SKELETON_OVERLAY

TARGET_PATH_POINTS = 12


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

    def __init__(self, scene, parent_window=None):
        super().__init__(scene, parent_window)
        self.parent_window = parent_window  # Reference to the main window if needed
        self.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Set background color to gray
        # self.setBackgroundBrush(QBrush(QColor(200, 200, 200), Qt.BrushStyle.SolidPattern)) # REMOVED

        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)  # Default to selection

        # Enable touch gestures
        self.grabGesture(Qt.GestureType.PinchGesture)

        self._joint_map_original_to_std: Dict[str, str] = {}  # original_name -> std_id

        # Pinch-to-zoom variables
        self._pinch_mode = False
        self._pinch_start_view_scale = 1.0

        # Custom panning variables
        self._panning = False
        self._pan_start_pos = QPointF()
        self._pan_sensitivity = 0.0001  # Further reduced sensitivity (lower = less sensitive, previously 0.001 by user)

        # Zoom control variables (new)
        self._zoom_level = 0
        self._zoom_factor_base = (
            1.05  # Base factor for low sensitivity (each step is 5% zoom)
        )
        self._min_zoom_level = -47  # Approx 1.05^-47 ~= 0.1 (target 0.1x scale)
        self._max_zoom_level = 47  # Approx 1.05^47 ~= 10.0 (target 10x scale)
        # For 1.05: log_1.05(0.1) ~ -47.19, log_1.05(10) ~ 47.19.

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

        self.selection_markers: Dict[
            str, QGraphicsEllipseItem
        ] = {}  # For mechanism point markers
        self.final_paths_map: Dict[
            str, QGraphicsPathItem
        ] = {}  # NEW: To store final green paths

        # Rounded corners and white background for the viewport
        self.viewport().setStyleSheet("background-color: white; border-radius: 10px;")

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

    def set_joint_map(self, joint_map: Optional[Dict[str, str]]):
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
        """Handle pinch gesture for zooming."""
        if gesture.state() == Qt.GestureState.GestureStarted:
            self._pinch_mode = True
            # Store the current view scale when pinch starts
            self._pinch_start_view_scale = self.transform().m11()
            # It might be better to also store the initial _zoom_level here if we want to map pinch scale to zoom levels.
            # For now, let pinch directly manipulate scale, but clamped.
        elif gesture.state() == Qt.GestureState.GestureUpdated and self._pinch_mode:
            # Calculate target scale based on gesture's scale factor relative to the start of the pinch
            target_scale = self._pinch_start_view_scale * gesture.scaleFactor()

            # Clamp the target scale to overall min/max
            target_scale = max(
                self._zoom_factor_base**self._min_zoom_level,
                min(target_scale, self._zoom_factor_base**self._max_zoom_level),
            )
            target_scale = max(0.1, min(target_scale, 10.0))  # Absolute limits

            current_view_scale = self.transform().m11()
            if abs(target_scale - current_view_scale) > 0.001:
                zoom_factor_to_apply = target_scale / current_view_scale
                self.scale(zoom_factor_to_apply, zoom_factor_to_apply)
                self.zoom_changed.emit(self.transform().m11())

            # Update _zoom_level based on the new scale (optional, for consistency)
            # This can make pinch and wheel zoom interact more predictably.
            # If self.transform().m11() is new_scale, then new_scale = base ^ new_zoom_level
            # new_zoom_level = log_base(new_scale)
            # current_effective_scale = self.transform().m11()
            # self._zoom_level = round(math.log(current_effective_scale, self._zoom_factor_base)) if current_effective_scale > 0 and self._zoom_factor_base > 1 else 0
            # Clamping _zoom_level again might be needed.
            # For simplicity, let's not update _zoom_level from pinch directly to avoid complex feedback, pinch directly sets scale within bounds.

        elif gesture.state() == Qt.GestureState.GestureFinished:
            self._pinch_mode = False
            # After pinch, we might want to snap the current scale to the nearest zoom_level scale.
            # Or recalculate _zoom_level based on current scale.
            current_scale = self.transform().m11()
            # Update zoom level to closest discrete step after pinch zooming
            if (
                current_scale > 0
                and self._zoom_factor_base > 1
                and self._zoom_factor_base != 0
            ):
                closest_zoom_level = round(
                    math.log(current_scale, self._zoom_factor_base)
                )
                self._zoom_level = max(
                    self._min_zoom_level, min(closest_zoom_level, self._max_zoom_level)
                )
                # Optionally, snap the view to this discrete zoom level's scale:
                # target_snap_scale = self._zoom_factor_base ** self._zoom_level
                # if abs(target_snap_scale - current_scale) / current_scale > 0.01: # If significantly different
                #     self.set_zoom_level_absolute(self._zoom_level) # A new method to set scale for a zoom level

    def zoom(self, step: int):
        """Zooms the view by a given step, adjusting the discrete zoom level."""
        if step == 0:
            return

        new_zoom_level = self._zoom_level + step
        # Clamp zoom level
        new_zoom_level = max(
            self._min_zoom_level, min(new_zoom_level, self._max_zoom_level)
        )

        if new_zoom_level != self._zoom_level:
            current_scale = self.transform().m11()
            target_scale = self._zoom_factor_base**new_zoom_level
            target_scale = max(0.1, min(target_scale, 10.0))  # Absolute limits

            # If already at target scale (e.g. clamped at min/max) and trying to zoom further in the same direction
            if abs(target_scale - current_scale) < 0.00001 and (
                (step > 0 and self._zoom_level == self._max_zoom_level)
                or (step < 0 and self._zoom_level == self._min_zoom_level)
            ):
                self._zoom_level = (
                    new_zoom_level  # Ensure level is updated if it was clamped
                )
                # self.zoom_changed.emit(current_scale) # No actual scale change, so debatable if emit is needed
                return

            if current_scale <= 0:  # Safeguard for invalid current scale
                self.resetTransform()
                current_scale = 1.0
                self._zoom_level = 0
                # Recalculate target_scale based on reset state for the current step
                # This ensures the first zoom step after a reset is correctly applied
                effective_step = (
                    max(self._min_zoom_level, min(step, self._max_zoom_level))
                    if step != 0
                    else 0
                )
                new_zoom_level = (
                    self._zoom_level + effective_step
                )  # Apply step from level 0
                new_zoom_level = max(
                    self._min_zoom_level, min(new_zoom_level, self._max_zoom_level)
                )  # Re-clamp
                target_scale = self._zoom_factor_base**new_zoom_level
                target_scale = max(0.1, min(target_scale, 10.0))

            factor_to_apply = (
                target_scale / current_scale if current_scale != 0 else target_scale
            )  # Avoid division by zero if current_scale somehow became 0
            if (
                abs(factor_to_apply - 1.0) > 0.000001
            ):  # Only scale if factor is meaningfully different from 1
                self.scale(factor_to_apply, factor_to_apply)

            self._zoom_level = new_zoom_level
            self.zoom_changed.emit(self.transform().m11())
            self.scene().update()  # Ensure repaint after zoom
        # If new_zoom_level is the same as self._zoom_level (already at min/max), do nothing further.

    def wheelEvent(self, event: QWheelEvent):
        """Handle mouse wheel for zooming based on discrete zoom levels."""
        if self._pinch_mode:  # Do not process wheel events if pinching
            return

        delta = event.angleDelta().y()
        step = 0
        if delta > 0:
            step = 1
        elif delta < 0:
            step = -1

        self.zoom(step)

    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press events based on the current mode."""
        scene_pos = self.mapToScene(event.pos())
        item_at_click = self.itemAt(event.pos())  # Get item at view coordinates

        # --- Panning --- (Middle button or Alt+Left)
        if event.button() == Qt.MouseButton.MiddleButton or (
            event.button() == Qt.MouseButton.LeftButton
            and event.modifiers() & Qt.KeyboardModifier.AltModifier
        ):
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
        if self._panning and (
            event.button() == Qt.MouseButton.MiddleButton
            or (
                event.button() == Qt.MouseButton.LeftButton
                and event.modifiers() & Qt.KeyboardModifier.AltModifier
            )
        ):
            self._panning = False
            self.viewport().setCursor(Qt.CursorShape.ArrowCursor)  # Reset cursor
            super().mouseReleaseEvent(event)
            return  # Important: return after handling pan release

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

                    # Create the final closed spline path
                    final_path_data = self._create_spline_path(
                        points_for_spline, closed_loop=True, tension=0.5
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
                    logging.debug(
                        f"Completed and finalized closed spline motion path with {len(points_for_spline)} points (resampled from {num_original_points})."
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
        """Handle mouse move events for panning and drawing."""
        scene_pos = self.mapToScene(event.pos())

        if self._panning:
            delta = event.pos() - self._pan_start_pos
            self._pan_start_pos = event.pos()
            hs = self.horizontalScrollBar()
            vs = self.verticalScrollBar()
            hs.setValue(
                hs.value() - int(delta.x() * self._pan_sensitivity * 20)
            )  # Adjusted multiplier
            vs.setValue(
                vs.value() - int(delta.y() * self._pan_sensitivity * 20)
            )  # Adjusted multiplier
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

    # --- View Control ---

    def reset_view(self):
        """Reset zoom and pan to default."""
        self.resetTransform()
        self._zoom_level = 0  # Reset zoom level
        self.centerOn(0, 0)  # Or center on scene rect center if preferred
        self.zoom_changed.emit(1.0)  # Emit zoom signal for 100%
        self._show_status_message("View reset")

    def zoom_to_fit(self):
        """Zoom to fit all items in the view."""
        if not self.scene():
            return
        rect = self.scene().itemsBoundingRect()
        if not rect.isValid():
            return
        # Add some padding
        padding = 20
        rect.adjust(-padding, -padding, padding, padding)
        self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
        # After fitInView, update _zoom_level to match the new scale
        current_scale = self.transform().m11()
        if (
            current_scale > 0
            and self._zoom_factor_base > 1
            and self._zoom_factor_base != 0
        ):
            # Calculate the zoom level that would produce a scale closest to current_scale
            self._zoom_level = round(math.log(current_scale, self._zoom_factor_base))
            # Clamp it to permissible levels
            self._zoom_level = max(
                self._min_zoom_level, min(self._zoom_level, self._max_zoom_level)
            )
        else:
            self._zoom_level = 0  # Default if calculation is not possible

        self.zoom_changed.emit(current_scale)  # Emit zoom signal
        self._show_status_message(
            f"Zoom to fit ({current_scale:.1f}x, level {self._zoom_level})"
        )

    # --- Joint Definition --- #

    def start_define_joint(self):
        """Initiates the joint definition mode."""
        self.set_mode("define_joint")
        self._reset_joint_definition()  # Clear previous state
        self._show_status_message("Define Joint: 1. Click parent part.")

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

    def start_define_motion_path(self, target_item: Optional[CharacterPartItem]):
        """Starts the freehand motion path definition mode."""
        # For the new IK system, target_item might be None if AutomataDesigner
        # is managing the selected component via sim_selected_component_key.
        # The path is drawn on the scene, and AutomataDesigner will associate it.
        if self.current_mode == "define_motion_path":
            return  # Already in this mode

        if target_item is None and not getattr(self.parent_window, 'selected_part_name', None):
            # This case would be an issue: no CharacterPartItem and no selected part means no context for the path.
            logging.warning(
                "EditorView: start_define_motion_path called with no target_item and no selected part."
            )
            # Optionally, prevent entering mode or show a message.
            # For now, allow proceeding, as AutomataDesigner might handle it or log separately.

        # Clear any existing path for this component before starting new drawing
        if target_item and target_item.part_info and target_item.part_info.name:
            component_key = target_item.part_info.name
            if component_key in self.final_paths_map:
                old_path_item = self.final_paths_map.pop(component_key)
                if old_path_item and old_path_item.scene():
                    self.scene().removeItem(old_path_item)
                    logging.debug(f"Cleared existing green path for {component_key} before starting new drawing")
        elif hasattr(self.parent_window, 'selected_part_name') and self.parent_window.selected_part_name:
            component_key = self.parent_window.selected_part_name
            if component_key in self.final_paths_map:
                old_path_item = self.final_paths_map.pop(component_key)
                if old_path_item and old_path_item.scene():
                    self.scene().removeItem(old_path_item)
                    logging.debug(f"Cleared existing green path for {component_key} before starting new drawing")

        self.current_target_item_for_path = target_item  # Can be None
        self.current_freehand_path = QPainterPath()
        self.current_freehand_path_item = None
        self.set_mode("define_motion_path")
        self.setCursor(Qt.CursorShape.CrossCursor)
        logging.info("EditorView: Entered freehand motion path definition mode.")
        if target_item:
            logging.info(
                f"EditorView: Motion path target: {target_item.part_info.name}"
            )

    def finish_motion_path_drawing(self, emit_signal: bool = True):
        """Finalizes the motion path. Called when mode is toggled off by MainWindow.
        The actual path points are emitted by freehandPathCompleted signal.
        This method is now mainly for cleanup if the mode is exited while a path
        was partially drawn but not completed via mouse release.
        """
        if self.current_target_item_for_path:
            logging.debug(
                f"Finishing motion path definition for {self.current_target_item_for_path.part_info.name}"
            )
            if self._is_drawing_freehand and len(self._motion_path_points) > 1:
                # This case implies mode was toggled off mid-draw.
                # Emit the points accumulated so far.
                if emit_signal:
                    self.freehandPathCompleted.emit(list(self._motion_path_points))
                    logging.debug(
                        f"Emitted path from finish_motion_path_drawing due to mode toggle."
                    )

        self.current_target_item_for_path = None
        self._is_drawing_freehand = False
        self._cleanup_motion_path_visuals()
        self.set_mode("select")  # Revert to select mode

    def _cancel_motion_path_drawing(self):
        """Cancels the current motion path drawing operation and cleans up."""
        logging.debug("Motion path drawing cancelled.")
        self.current_target_item_for_path = None
        self._is_drawing_freehand = False
        self._motion_path_points.clear()
        self._cleanup_motion_path_visuals()
        self.drawing_cancelled.emit()  # Notify MainWindow if needed
        if (
            self.current_mode == "define_motion_path"
        ):  # Avoid recursive set_mode if called from set_mode
            self.set_mode("select")
        self._show_status_message("Motion path definition cancelled.")

    def _cleanup_motion_path_visuals(
        self, keep_target=False
    ):  # keep_target not used currently
        """Clears temporary visuals used for motion path definition (preview path)."""
        if self._motion_preview_path_item:
            if self._motion_preview_path_item.scene():
                self.scene().removeItem(self._motion_preview_path_item)
            self._motion_preview_path_item = None
        # self._path_points.clear() # This is now _motion_path_points, cleared in start/cancel
        logging.debug("Cleaned up motion path preview visuals.")

    # --- End Effector Selection --- #

    def start_select_end_effector(self, target_item: CharacterPartItem):
        """Prepares the view to select an end-effector point on the given item."""
        if not isinstance(target_item, CharacterPartItem):
            logging.warning("Invalid target item for end effector selection.")
            return

        self._target_part_for_end_effector = target_item
        self.set_mode("select_end_effector")
        self._show_status_message(
            f"Select End Effector: Click desired point on '{target_item.part_info.name}'. Esc to cancel."
        )

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

    def start_simulation(self):
        """Starts the simulation mode."""
        self.set_mode("simulation")
        # Parent window likely starts the timer/updates

    def stop_simulation(self):
        """Stops the simulation mode."""
        self.set_mode("select")
        # Parent window likely stops the timer/updates

    def reset_simulation(self):
        """Resets the simulation to the initial state."""
        self._restore_original_transforms()
        self._animation_time = 0.0
        self.set_mode("select")  # Usually stop simulation implies reset

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

    def get_part_item_by_name(self, part_name: str) -> Optional[CharacterPartItem]:
        """Finds a CharacterPartItem in the scene by its part_info.name."""
        if not self.scene():
            return None
        for item in self.scene().items():
            if (
                isinstance(item, CharacterPartItem)
                and item.part_info
                and item.part_info.name == part_name
            ):
                return item
        return None

    def visualize_skeleton(
        self, skeleton_data: List[Dict[str, Any]], hierarchy_data: Dict[str, List[str]]
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
                skeleton_data, hierarchy_data
            )
            self.scene().addItem(self.skeleton_graphics_item)
            self.skeleton_graphics_item.setZValue(Z_SKELETON_OVERLAY)
        else:
            logging.debug(
                "EditorView: visualize_skeleton - Updating existing SkeletonGraphicsItem."
            )
            # Call load_skeleton_data with both skeleton_data and hierarchy_data
            self.skeleton_graphics_item.load_skeleton_data(
                skeleton_data, hierarchy_data
            )

        self.scene().update()  # Trigger a repaint of the scene

    def update_skeleton_animation(
        self, animated_joint_positions: Dict[str, Tuple[float, float]]
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

    def update_visuals_from_animation_data(self, joint_data: Dict[str, Dict[str, Any]]):
        """Updates skeleton and part visuals based on joint-centric animation data."""
        if not self.scene():
            logging.warning("EditorView: No scene available for animation update.")
            return

        # 1. Update Skeleton Visualization
        # Extract all joint positions for the skeleton item
        all_joint_positions: Dict[str, Tuple[float, float]] = {}
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

        # 2. Update CharacterPartItems
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

                # Apply the calculated world rotation instead of fixing to 0
                part_item.setRotation(float(target_part_world_rotation))
                part_item.set_scene_position_from_anchor(target_joint_scene_pos)
        else:
            logging.warning(
                "EditorView: parent_window (EditorTab) does not have current_editor_items or it's not a dict. Cannot update part visuals."
            )

        self.scene().update()  # Update scene once after all items are processed

    def set_selected_part(
        self, part_name: Optional[str], part_items: Dict[str, CharacterPartItem]
    ):
        """Sets the visual state for the selected part and deselects others."""
        logging.debug(f"EditorView: Setting selected part to: {part_name}")
        for name, item in part_items.items():  # Use the passed dictionary
            if isinstance(item, CharacterPartItem):  # Ensure it's the correct type
                is_selected = name == part_name
                item.set_selected(is_selected)  # CharacterPartItem has set_selected
            else:
                logging.warning(
                    f"EditorView.set_selected_part: Item '{name}' is not a CharacterPartItem."
                )
        if self.scene():  # Check if scene exists before updating
            self.scene().update()  # Trigger redraw if selection changes visuals
        else:
            logging.warning(
                "EditorView.set_selected_part: Scene not available for update."
            )

    def get_current_part_transforms(self) -> Dict[str, Tuple[QPointF, float]]:
        """Returns a dictionary of part names to their (position, rotation_degrees)."""
        transforms = {}
        for name, item in self.part_items.items():
            transforms[name] = (item.pos(), item.rotation())
        return transforms

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
        self, points: List[QPointF], closed_loop: bool = False, tension: float = 0.5
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
        self, points: List[QPointF], num_target_points: int
    ) -> List[QPointF]:
        """Resamples the given points to num_target_points. Simple version."""
        if not points:
            return []
        n = len(points)
        if n == 0 or num_target_points <= 0:
            return []

        # If original points are less than target and also very few (e.g. <3 for a spline),
        # it might be better to return them as is, or an empty list if not usable.
        # For this function, we'll aim to produce num_target_points if possible.

        final_resampled: List[QPointF] = []
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
        if not component_key:
            logging.warning(
                "EditorView: clear_visual_path_for_component called with no component_key."
            )
            return

        logging.info(
            f"EditorView: Attempting to clear visual path for component '{component_key}'."
        )
        path_item_to_remove = self.final_paths_map.pop(component_key, None)

        if path_item_to_remove:
            if path_item_to_remove.scene():
                self.scene().removeItem(path_item_to_remove)
                logging.debug(
                    f"Removed visual path for component '{component_key}' from scene."
                )
            else:
                logging.debug(
                    f"Visual path for component '{component_key}' was in map but not in scene."
                )

            self.path_data_cleared_for_component.emit(component_key)
            self._show_status_message(f"Path cleared for {component_key}.")
        else:
            logging.debug(
                f"No visual path found in map for component '{component_key}' to clear."
            )
            # Still emit, as IKManager might have data even if visual wasn't shown or was already cleared
            self.path_data_cleared_for_component.emit(component_key)
            self._show_status_message(
                f"No visual path to clear for {component_key}, ensuring data is cleared."
            )

    def get_camera_state(self) -> Dict[str, Any]:
        """Get current camera state including transform and center position.
        
        Returns:
            Dict containing:
                - transform: QTransform matrix
                - center: QPointF of the view center
                - zoom_level: int current zoom level
        """
        transform = self.transform()
        center = self.mapToScene(self.viewport().rect().center())
        
        return {
            'transform': transform,
            'center': center,
            'zoom_level': self._zoom_level
        }
    
    def set_camera_state(self, state: Dict[str, Any]):
        """Set camera state from a previously saved state.
        
        Args:
            state: Dict containing transform, center, and zoom_level
        """
        if 'transform' in state:
            self.setTransform(state['transform'])
        
        if 'center' in state:
            self.centerOn(state['center'])
        
        if 'zoom_level' in state:
            self._zoom_level = state['zoom_level']
            # Emit zoom changed signal
            current_scale = self.transform().m11()
            self.zoom_changed.emit(current_scale)
