import logging
import math
from PyQt6.QtWidgets import (
    QGraphicsView, QGraphicsEllipseItem, QGraphicsLineItem,
    QGraphicsPathItem, QMenu
)
from PyQt6.QtGui import (
    QPainter, QPen, QColor, QBrush, QPainterPath, QMouseEvent, QWheelEvent, QTransform
)
from PyQt6.QtCore import Qt, QPointF, QRectF, pyqtSignal, QObject, QLineF, QEvent, QTimer

from .part_item import CharacterPartItem # Assuming part_item.py is in the same directory

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
    """
    end_effector_selected = pyqtSignal(QPointF, QPointF)
    cam_center_selected = pyqtSignal(QPointF)
    drawing_cancelled = pyqtSignal()
    joint_defined = pyqtSignal(dict)
    pivot_a_selected = pyqtSignal(QPointF)
    pivot_d_selected = pyqtSignal(QPointF)
    driver_center_selected = pyqtSignal(QPointF)
    driven_center_selected = pyqtSignal(QPointF)
    freehandPathCompleted = pyqtSignal(list) # New signal for freehand path points
    zoom_changed = pyqtSignal(float) # Emitted when zoom level changes

    def __init__(self, scene, parent_window=None):
        super().__init__(scene, parent_window)
        self.parent_window = parent_window # Reference to the main window if needed
        self.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Set background color to gray
        self.setBackgroundBrush(QBrush(QColor(200, 200, 200), Qt.BrushStyle.SolidPattern))

        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag) # Default to selection

        # Enable touch gestures
        self.grabGesture(Qt.GestureType.PinchGesture)

        # Pinch-to-zoom variables
        self._pinch_mode = False
        self._pinch_start_scale = 1.0

        # Custom panning variables
        self._panning = False
        self._pan_start_pos = QPointF()
        self._pan_sensitivity = 0.3  # Reduce sensitivity (lower = less sensitive)

        # State modes
        self.current_mode = 'select' # Modes: 'select', 'define_joint', 'define_motion_path', 'select_end_effector', 'select_cam_center', 'simulation', 'select_pivot_a', 'select_pivot_d', 'select_driver_center', 'select_driven_center'

        # Joint definition attributes
        self._joint_parent_item = None
        self._joint_parent_pos = None
        self._joint_parent_item_marker = None

        # Motion path attributes (revised for freehand)
        self._motion_path_points = [] # Stores QPointF for the current freehand path
        self._motion_preview_path_item = None # QGraphicsPathItem for live preview
        self._is_drawing_freehand = False # Flag for active drawing
        self._target_part_for_path = None # CharacterPartItem for which path is being defined

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
        self._animation_duration = 5.0
        self._original_transforms = {}

        # Context menu
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

        # Skeleton visualization attributes
        self._skeleton_viz_items = []
        self._skeleton_viz_timer = QTimer(self)
        self._skeleton_viz_timer.setSingleShot(True)
        self._skeleton_viz_timer.setInterval(3000) # Display for 3 seconds
        self._skeleton_viz_timer.timeout.connect(self._clear_skeleton_visualization)

    # --- Mode Management ---

    def set_mode(self, mode: str):
        """Sets the interaction mode of the editor view."""
        logging.info(f"Setting EditorView mode to: {mode}")
        previous_mode = self.current_mode
        self.current_mode = mode

        # Reset states from previous modes if necessary
        if previous_mode == 'define_joint' and mode != 'define_joint':
            self._reset_joint_definition()
        if previous_mode == 'define_motion_path' and mode != 'define_motion_path':
            self._cancel_motion_path_drawing() # This will clear previews etc.
        if previous_mode == 'select_end_effector' and mode != 'select_end_effector':
            self._target_part_for_end_effector = None
        if previous_mode == 'select_cam_center' and mode != 'select_cam_center':
            pass # No specific reset needed
        if previous_mode == 'simulation' and mode != 'simulation':
            self._reset_simulation_state() # Ensure interactive state is restored

        # Configure view based on new mode
        if mode == 'simulation':
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.setInteractive(False)
            self.viewport().setCursor(Qt.CursorShape.ForbiddenCursor)
        elif mode == 'select':
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
            self.setInteractive(True)
            self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        elif mode.startswith('select_') or mode == 'define_joint': # Point selection modes
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.setInteractive(True) # Allow item clicks if needed, but main action is scene click
            self.viewport().setCursor(Qt.CursorShape.CrossCursor)
        elif mode == 'define_motion_path':
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.setInteractive(True)
            self.viewport().setCursor(Qt.CursorShape.CrossCursor) # Or a custom pen cursor
        else: # Default/fallback
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
            self.setInteractive(True)
            self.viewport().setCursor(Qt.CursorShape.ArrowCursor)

    def get_selected_item(self):
        """Returns the single selected CharacterPartItem, or None."""
        selected_items = self.scene().selectedItems()
        if len(selected_items) == 1 and isinstance(selected_items[0], CharacterPartItem):
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
            # Store the scale factor relative to the view's current transform
            self._pinch_start_scale = self.transform().m11() * gesture.scaleFactor()
        elif gesture.state() == Qt.GestureState.GestureUpdated and self._pinch_mode:
            # Calculate the target scale based on the gesture's scale factor
            target_scale = self._pinch_start_scale * gesture.scaleFactor()
            current_scale = self.transform().m11()
            if abs(target_scale - current_scale) > 0.01: # Threshold
                 zoom_factor = target_scale / current_scale
                 self.scale(zoom_factor, zoom_factor)
                 # Emit zoom signal with new scale
                 new_scale = self.transform().m11()
                 self.zoom_changed.emit(new_scale)
        elif gesture.state() == Qt.GestureState.GestureFinished:
            self._pinch_mode = False

    def wheelEvent(self, event: QWheelEvent):
        """Handle mouse wheel for zooming when no pinch is active."""
        if not self._pinch_mode:
            zoom_in = event.angleDelta().y() > 0
            # Reduced zoom sensitivity
            factor = 1.08 if zoom_in else 1 / 1.08
            
            # Get current scale and check limits
            current_scale = self.transform().m11()
            new_scale = current_scale * factor
            
            # Limit zoom range (10% to 500%)
            if 0.1 <= new_scale <= 5.0:
                self.scale(factor, factor)
                self.scene().update() # Ensure clean rendering
                
                # Emit zoom change signal
                self.zoom_changed.emit(new_scale)

    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press events based on the current mode."""
        scene_pos = self.mapToScene(event.pos())

        # --- Panning --- (Middle button or Alt+Left)
        # Handle panning (middle click or Alt+Left click)
        if event.button() == Qt.MouseButton.MiddleButton or \
           (event.button() == Qt.MouseButton.LeftButton and event.modifiers() & Qt.KeyboardModifier.AltModifier):
            self._panning = True
            self._pan_start_pos = event.pos()
            self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
            return

        # --- Mode-Specific Handling --- (Left Button primarily)
        if event.button() == Qt.MouseButton.LeftButton:
            if self.current_mode == 'define_joint':
                self._handle_joint_definition_click(scene_pos, event.pos())
            elif self.current_mode == 'define_motion_path':
                if self._target_part_for_path: # Ensure a target part is set
                    self._motion_path_points.clear()
                    self._motion_path_points.append(scene_pos)

                    if self._motion_preview_path_item is None:
                        pen = QPen(QColor("red"), 2, Qt.PenStyle.DashLine)
                        self._motion_preview_path_item = QGraphicsPathItem()
                        self._motion_preview_path_item.setPen(pen)
                        self.scene().addItem(self._motion_preview_path_item)

                    temp_path = QPainterPath()
                    temp_path.moveTo(scene_pos)
                    self._motion_preview_path_item.setPath(temp_path)
                    self._is_drawing_freehand = True
                    logging.debug(f"Started freehand motion path at {scene_pos}")
                else:
                    logging.warning("Attempted to draw motion path without a target part.")
            elif self.current_mode == 'select_end_effector':
                self._handle_end_effector_selection_click(scene_pos)
            elif self.current_mode == 'select_cam_center':
                self.cam_center_selected.emit(scene_pos)
                self.set_mode('select') # Revert to select mode after click
            elif self.current_mode == 'select_pivot_a':
                self.pivot_a_selected.emit(scene_pos)
                self.set_mode('select')
            elif self.current_mode == 'select_pivot_d':
                self.pivot_d_selected.emit(scene_pos)
                self.set_mode('select')
            elif self.current_mode == 'select_driver_center':
                self.driver_center_selected.emit(scene_pos)
                self.set_mode('select')
            elif self.current_mode == 'select_driven_center':
                self.driven_center_selected.emit(scene_pos)
                self.set_mode('select')
            elif self.current_mode == 'select':
                # Default behavior for selection mode
                super().mousePressEvent(event)
            # Ignore left clicks in simulation mode

        elif event.button() == Qt.MouseButton.RightButton:
             # Right click cancels drawing modes and point selection modes
            if self.current_mode == 'define_motion_path':
                 self._cancel_motion_path_drawing() # This now also emits drawing_cancelled
                 # self.drawing_cancelled.emit() # _cancel_motion_path_drawing should handle this
            elif self.current_mode == 'define_joint':
                 self._reset_joint_definition()
            elif self.current_mode.startswith('select_'):
                 logging.info(f"Point selection mode '{self.current_mode}' cancelled by right-click.")
                 self.set_mode('select') # Cancel point selection
                 # Optionally emit a cancellation signal if needed by MainWindow
            else:
                 # Allow context menu in select mode
                 super().mousePressEvent(event)

        else:
             # Allow other buttons to be handled by base class
             super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle mouse release, primarily to stop panning and finalize freehand path."""
        if self._panning and (event.button() == Qt.MouseButton.MiddleButton or \
           (event.button() == Qt.MouseButton.LeftButton and event.modifiers() & Qt.KeyboardModifier.AltModifier)):
            self._panning = False
            self.viewport().setCursor(Qt.CursorShape.ArrowCursor) # Reset cursor
            super().mouseReleaseEvent(event)
            return # Important: return after handling pan release

        if event.button() == Qt.MouseButton.LeftButton:
            if self.current_mode == 'define_motion_path' and self._is_drawing_freehand:
                if len(self._motion_path_points) > 1: # Ensure there's more than just a click
                    self.freehandPathCompleted.emit(list(self._motion_path_points)) # Emit copies
                    logging.debug(f"Completed freehand motion path with {len(self._motion_path_points)} points.")
                else: # Path was just a click, or something went wrong
                    logging.debug("Freehand path too short, cancelling.")
                    self._cancel_motion_path_drawing() # Clears preview, resets state
                self._is_drawing_freehand = False
                # Preview remains until mode changes or new path started for this item

        super().mouseReleaseEvent(event) # Call base for other release events

    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move events, especially for freehand drawing and custom panning."""
        scene_pos = self.mapToScene(event.pos())

        # Handle custom panning
        if self._panning:
            delta = event.pos() - self._pan_start_pos
            # Apply sensitivity reduction
            delta *= self._pan_sensitivity
            
            # Get current scroll bar values
            h_scroll = self.horizontalScrollBar()
            v_scroll = self.verticalScrollBar()
            
            # Update scroll positions (inverted for natural panning feel)
            h_scroll.setValue(h_scroll.value() - int(delta.x()))
            v_scroll.setValue(v_scroll.value() - int(delta.y()))
            
            # Update start position for next move
            self._pan_start_pos = event.pos()
            return

        # Handle freehand motion path drawing
        if self._is_drawing_freehand and self.current_mode == 'define_motion_path':
            if self._motion_path_points and self._motion_path_points[-1] != scene_pos:
                self._motion_path_points.append(scene_pos)

                if self._motion_preview_path_item:
                    current_path = QPainterPath()
                    current_path.moveTo(self._motion_path_points[0])
                    for point in self._motion_path_points[1:]:
                        current_path.lineTo(point)
                    self._motion_preview_path_item.setPath(current_path)
            super().mouseMoveEvent(event) # Allow panning if Alt is pressed during drawing
            return

        super().mouseMoveEvent(event)

    def keyPressEvent(self, event: QEvent):
        """Handle keyboard shortcuts."""
        if event.key() == Qt.Key.Key_Escape:
            if self.current_mode == 'define_joint':
                self._reset_joint_definition()
            elif self.current_mode == 'define_motion_path':
                self._cancel_motion_path_drawing()
            elif self.current_mode == 'select_end_effector':
                self.set_mode('select')
                self._show_status_message("End effector selection cancelled")
            elif self.current_mode == 'select_cam_center':
                self.set_mode('select')
                self._show_status_message("Cam center selection cancelled")
            else:
                 super().keyPressEvent(event)
            return

        # Ctrl+0 for reset view
        if event.key() == Qt.Key.Key_0 and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
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
            menu.addAction(f"Set '{selected_item.part_info.name}' as Cam Follower", lambda: self.parent_window.set_cam_follower())

        # Execute menu at global position
        global_pos = self.mapToGlobal(pos)
        menu.exec(global_pos)

    # --- View Control ---

    def reset_view(self):
        """Reset zoom and pan to default."""
        self.resetTransform()
        self.centerOn(0,0) # Or center on scene rect center if preferred
        self.zoom_changed.emit(1.0)  # Emit zoom signal for 100%
        self._show_status_message("View reset")

    def zoom_to_fit(self):
        """Zoom to fit all items in the view."""
        if not self.scene(): return
        rect = self.scene().itemsBoundingRect()
        if not rect.isValid(): return
        # Add some padding
        padding = 20
        rect.adjust(-padding, -padding, padding, padding)
        self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
        scale = self.transform().m11()
        self.zoom_changed.emit(scale)  # Emit zoom signal
        self._show_status_message(f"Zoom to fit ({scale:.1f}x)")

    # --- Joint Definition --- #

    def start_define_joint(self):
        """Initiates the joint definition mode."""
        self.set_mode('define_joint')
        self._reset_joint_definition() # Clear previous state
        self._show_status_message("Define Joint: 1. Click parent part.")

    def _handle_joint_definition_click(self, scene_pos: QPointF, view_pos: QPointF):
        item_at_click = self.itemAt(view_pos) # Use view_pos for itemAt

        # Ensure a CharacterPartItem is clicked
        if not isinstance(item_at_click, CharacterPartItem):
            logging.debug("Joint definition click missed a character part.")
            # Optionally show a status message
            # self._show_status_message("Please click on a character part.")
            return

        if self._joint_parent_item is None:
            # First click: select parent item and mark joint point on it
            self._joint_parent_item = item_at_click
            self._joint_parent_pos = item_at_click.mapFromScene(scene_pos) # Store local pos
            # Update status or visual cue
            self.setCursor(Qt.CursorShape.CrossCursor) # Change cursor
            logging.info(f"Joint parent selected: {self._joint_parent_item.part_info.name}, local pos: {self._joint_parent_pos}")
            self._show_status_message(f"Selected {self._joint_parent_item.part_info.name} as parent. Click another part to define joint.")

        elif self._joint_parent_item: # If parent is already selected, this click is for child
            if item_at_click == self._joint_parent_item:
                logging.debug("Clicked the same item again for joint definition. Resetting.")
                self._reset_joint_definition_state()
                self._show_status_message("Joint definition reset. Click first part.")
                return

            # Ensure child item is different from parent
            self._joint_child_item = item_at_click
            self._joint_child_pos = item_at_click.mapFromScene(scene_pos)
            logging.info(f"Joint child selected: {item_at_click.part_info.name}, local pos: {self._joint_child_pos}. Emitting joint_defined.")

            # Emit signal with all necessary data
            self.joint_defined.emit({
                'parent_item_name': self._joint_parent_item.part_info.name,
                'child_item_name': self._joint_child_item.part_info.name,
                'parent_pos_local': self._joint_parent_pos, # QPointF
                'child_pos_local': self._joint_child_pos # QPointF
            })
            logging.info(f"Joint defined between {self._joint_parent_item.part_info.name} and {self._joint_child_item.part_info.name}")
            self._show_status_message(f"Joint defined: {self._joint_parent_item.part_info.name} <> {self._joint_child_item.part_info.name}. Define another or switch mode.")

            # Reset for next joint definition
            self._reset_joint_definition_state() # Keep markers until mode change

    def _reset_joint_definition_state(self):
        """Resets only the state for defining the *next* joint, keeps markers for completed one."""
        self._joint_parent_item = None
        self._joint_parent_pos = None
        # self._joint_parent_item_marker is not cleared here, cleared in _reset_joint_definition

    def _reset_joint_definition(self):
        """Full reset of joint definition mode, including visuals."""
        if self._joint_parent_item_marker and self._joint_parent_item_marker.scene():
            self.scene().removeItem(self._joint_parent_item_marker)
            self._joint_parent_item_marker.setParentItem(None) # Clear parent before removing from scene
            self._joint_parent_item_marker = None
        self._reset_joint_definition_state()
        logging.debug("Joint definition mode reset.")
        self._show_status_message("Joint definition cancelled.")

    # --- Motion Path Definition --- #

    def start_define_motion_path(self, target_item: CharacterPartItem):
        """Prepares the view for defining a motion path for the given item."""
        if not isinstance(target_item, CharacterPartItem):
            logging.warning("Cannot define motion path: Invalid target item.")
            return

        self._target_part_for_path = target_item
        self.set_mode('define_motion_path')
        self._cleanup_motion_path_visuals() # Clear any previous preview/points
        self._motion_path_points.clear()
        self._is_drawing_freehand = False # Ready to start new drawing
        logging.info(f"Ready to define motion path for: {target_item.part_info.name}")
        self._show_status_message(f"Draw motion path for {target_item.part_info.name}. Right-click or uncheck to cancel/finish.")

    def finish_motion_path_drawing(self):
        """Finalizes the motion path. Called when mode is toggled off by MainWindow.
           The actual path points are emitted by freehandPathCompleted signal.
           This method is now mainly for cleanup if the mode is exited while a path
           was partially drawn but not completed via mouse release.
        """
        if self._target_part_for_path:
            logging.debug(f"Finishing motion path definition for {self._target_part_for_path.part_info.name}")
            if self._is_drawing_freehand and len(self._motion_path_points) > 1 :
                 # This case implies mode was toggled off mid-draw.
                 # Emit the points accumulated so far.
                self.freehandPathCompleted.emit(list(self._motion_path_points))
                logging.debug(f"Emitted path from finish_motion_path_drawing due to mode toggle.")

        self._target_part_for_path = None
        self._is_drawing_freehand = False
        self._cleanup_motion_path_visuals()
        self.set_mode('select') # Revert to select mode

    def _cancel_motion_path_drawing(self):
        """Cancels the current motion path drawing operation and cleans up."""
        logging.debug("Motion path drawing cancelled.")
        self._target_part_for_path = None
        self._is_drawing_freehand = False
        self._motion_path_points.clear()
        self._cleanup_motion_path_visuals()
        self.drawing_cancelled.emit() # Notify MainWindow if needed
        if self.current_mode == 'define_motion_path': # Avoid recursive set_mode if called from set_mode
            self.set_mode('select')
        self._show_status_message("Motion path definition cancelled.")

    def _cleanup_motion_path_visuals(self, keep_target=False): # keep_target not used currently
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
        self.set_mode('select_end_effector')
        self._show_status_message(f"Select End Effector: Click desired point on '{target_item.part_info.name}'. Esc to cancel.")

    def _handle_end_effector_selection_click(self, scene_pos: QPointF):
        """Handles the click to set the end effector position."""
        if not self._target_part_for_end_effector:
             self.set_mode('select') # Should not happen, but reset if it does
             return

        local_pos = self._target_part_for_end_effector.mapFromScene(scene_pos)
        self.end_effector_selected.emit(local_pos, scene_pos) # Emit signal
        self._target_part_for_end_effector.end_effector_offset = local_pos # Update item directly
        self._target_part_for_end_effector._update_end_effector_marker() # Update visual
        self._show_status_message(f"End effector set for '{self._target_part_for_end_effector.part_info.name}'")
        self.set_mode('select') # Return to select mode

    # --- Simulation Control --- #

    def start_simulation(self):
        """Starts the simulation mode."""
        self.set_mode('simulation')
        # Parent window likely starts the timer/updates

    def stop_simulation(self):
        """Stops the simulation mode."""
        self.set_mode('select')
        # Parent window likely stops the timer/updates

    def reset_simulation(self):
        """Resets the simulation to the initial state."""
        self._restore_original_transforms()
        self._animation_time = 0.0
        self.set_mode('select') # Usually stop simulation implies reset

    def _save_original_transforms(self):
        """Saves the current transforms of all part items."""
        self._original_transforms.clear()
        logging.debug("Saving original item transforms.")
        for item_name, item in self.parent_window.editor_items.items(): # Use main window's dictionary
            if isinstance(item, CharacterPartItem) and item.scene() == self.scene():
                self._original_transforms[item_name] = item.transform() # Store the full QTransform
                # logging.debug(f"  Saved {item_name}: transform={item.transform()}")

    def _restore_original_transforms(self):
        """Restores the saved transforms of all part items."""
        logging.debug(f"Restoring {len(self._original_transforms)} original item transforms.")
        for item_name, initial_transform in self._original_transforms.items():
            item = self.parent_window.editor_items.get(item_name)
            if item and item.scene() == self.scene(): # Check if item still exists in the scene
                # logging.debug(f"  Restoring {item_name}: transform={initial_transform}")
                item.setTransform(initial_transform)
            else:
                logging.warning(f"Could not restore transform for {item_name}: Item not found or not in scene.")

        self.scene().update()

    def _reset_simulation_state(self):
        """Ensures the view is interactive after simulation stops/resets."""
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setInteractive(True)

    # --- Skeleton Visualization --- #

    def visualize_skeleton(self, skeleton_data: dict, joint_items: list):
        """Temporarily draws the skeleton structure and joints on the scene."""
        self._clear_skeleton_visualization() # Clear previous visualization

        if not skeleton_data or 'skeleton' not in skeleton_data or not isinstance(skeleton_data['skeleton'], list):
            logging.warning("visualize_skeleton called with invalid or missing skeleton data.")
            return

        skeleton_list = skeleton_data['skeleton']
        joint_locations = {j['name']: QPointF(float(j['loc'][0]), float(j['loc'][1]))
                           for j in skeleton_list if j.get('name') and j.get('loc') and len(j.get('loc')) >= 2}

        bone_pen = QPen(QColor("#FF5733"), 2, Qt.PenStyle.SolidLine) # Bright orange for bones
        joint_brush = QBrush(QColor("#FFC300")) # Yellow for joints
        joint_pen = QPen(QColor("#C70039"), 1)    # Dark red outline for joints
        joint_radius = 4

        # Draw bones
        for joint_info in skeleton_list:
            child_name = joint_info.get('name')
            parent_name = joint_info.get('parent')

            if child_name in joint_locations and parent_name and parent_name in joint_locations:
                p1 = joint_locations[parent_name]
                p2 = joint_locations[child_name]
                bone_line = QGraphicsLineItem(QLineF(p1, p2))
                bone_line.setPen(bone_pen)
                bone_line.setZValue(500) # Draw on top
                self.scene().addItem(bone_line)
                self._skeleton_viz_items.append(bone_line)

        # Draw joints (circles)
        for name, loc in joint_locations.items():
            joint_circle = QGraphicsEllipseItem(loc.x() - joint_radius, loc.y() - joint_radius,
                                                joint_radius * 2, joint_radius * 2)
            joint_circle.setBrush(joint_brush)
            joint_circle.setPen(joint_pen)
            joint_circle.setZValue(501) # Draw on top of bones
            self.scene().addItem(joint_circle)
            self._skeleton_viz_items.append(joint_circle)

        logging.info(f"Visualizing skeleton with {len(joint_locations)} joints and associated bones.")
        self._skeleton_viz_timer.start() # Start timer to auto-clear visualization

    def _clear_skeleton_visualization(self):
        """Removes temporary skeleton visualization items from the scene."""
        if not self._skeleton_viz_items:
            return
        logging.debug(f"Clearing {len(self._skeleton_viz_items)} skeleton visualization items.")
        for item in self._skeleton_viz_items:
            self.scene().removeItem(item)
        self._skeleton_viz_items.clear()

    # --- Utility --- #

    def _show_status_message(self, message: str):
        """Safely displays a message in the parent window's status bar."""
        if self.parent_window and hasattr(self.parent_window, 'statusBar'):
            self.parent_window.statusBar().showMessage(message, 5000) # Show for 5 seconds
        else:
            logging.info(f"Status: {message}") # Fallback logging