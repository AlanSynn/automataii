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
    """
    end_effector_selected = pyqtSignal(QPointF, QPointF)
    cam_center_selected = pyqtSignal(QPointF)
    drawing_cancelled = pyqtSignal()
    joint_defined = pyqtSignal(dict)

    def __init__(self, scene, parent_window=None):
        super().__init__(scene, parent_window)
        self.parent_window = parent_window # Reference to the main window if needed
        self.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Set background color to gray
        self.setBackgroundBrush(QBrush(QColor(200, 200, 200), Qt.BrushStyle.SolidPattern))

        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag) # Default to selection

        # Enable touch gestures
        self.viewport().setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents)
        self.grabGesture(Qt.GestureType.PinchGesture)

        # Pinch-to-zoom variables
        self._pinch_mode = False
        self._pinch_start_scale = 1.0

        # State modes
        self.current_mode = 'select' # Modes: 'select', 'define_joint', 'define_motion_path', 'select_end_effector', 'select_cam_center', 'simulation'

        # Joint definition attributes
        self._joint_parent_item = None
        self._joint_parent_pos = None
        self._joint_parent_item_marker = None

        # Motion path attributes
        self._motion_path = QPainterPath()
        self._temp_path_item = None
        self._path_points = []
        self._point_markers = []
        self._connection_lines = []
        self._target_part_for_path = None

        # End effector selection attributes
        self._target_part_for_end_effector = None

        # Simulation attributes
        self._animation_time = 0.0
        self._animation_duration = 5.0
        self._original_transforms = {}

        # Context menu
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

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
            self._cancel_motion_path_drawing()
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
            self._save_original_transforms()
        elif mode == 'select':
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
            self.setInteractive(True)
        else:
            # Other definition modes typically don't need drag/interactive changes
            # but might need specific cursors
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.setInteractive(True) # Allow item clicks

        self._show_status_message(f"Mode: {mode.replace('_', ' ').title()}")

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
        elif gesture.state() == Qt.GestureState.GestureFinished:
            self._pinch_mode = False

    def wheelEvent(self, event: QWheelEvent):
        """Handle mouse wheel for zooming when no pinch is active."""
        if not self._pinch_mode:
            zoom_in = event.angleDelta().y() > 0
            factor = 1.15 if zoom_in else 1 / 1.15
            self.scale(factor, factor)
            self.scene().update() # Ensure clean rendering

    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press events based on the current mode."""
        scene_pos = self.mapToScene(event.pos())

        # --- Panning --- (Middle button or Alt+Left)
        if event.button() == Qt.MouseButton.MiddleButton or \
           (event.button() == Qt.MouseButton.LeftButton and event.modifiers() & Qt.KeyboardModifier.AltModifier):
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            # Create a fake event with LeftButton to activate ScrollHandDrag
            fake_event = QMouseEvent(event.type(), QPointF(event.pos()), event.globalPosition(),
                                     Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, event.modifiers())
            super().mousePressEvent(fake_event)
            return

        # --- Mode-Specific Handling --- (Left Button primarily)
        if event.button() == Qt.MouseButton.LeftButton:
            if self.current_mode == 'define_joint':
                self._handle_joint_definition_click(scene_pos, event.pos())
            elif self.current_mode == 'define_motion_path':
                self._handle_motion_path_click(scene_pos)
            elif self.current_mode == 'select_end_effector':
                self._handle_end_effector_selection_click(scene_pos)
            elif self.current_mode == 'select_cam_center':
                self._handle_cam_center_selection_click(scene_pos)
            elif self.current_mode == 'select':
                # Default behavior for selection mode
                super().mousePressEvent(event)
            # Ignore left clicks in simulation mode

        elif event.button() == Qt.MouseButton.RightButton:
             # Right click often cancels drawing modes
             if self.current_mode == 'define_motion_path':
                 self._cancel_motion_path_drawing()
             elif self.current_mode == 'define_joint':
                 self._reset_joint_definition()
             else:
                 # Allow context menu in select mode
                 super().mousePressEvent(event)

        else:
             # Allow other buttons to be handled by base class
             super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle mouse release, primarily to stop panning."""
        if self.dragMode() == QGraphicsView.DragMode.ScrollHandDrag and \
           event.button() == Qt.MouseButton.LeftButton: # Release matching the fake pan event
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag if self.current_mode == 'select' else QGraphicsView.DragMode.NoDrag)
            # Create a fake event for the base class
            fake_event = QMouseEvent(event.type(), QPointF(event.pos()), event.globalPosition(),
                                     Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, event.modifiers())
            super().mouseReleaseEvent(fake_event)
            return
        super().mouseReleaseEvent(event)

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
        zoom_in_action.triggered.connect(lambda: self.scale(1.15, 1.15))
        zoom_out_action = menu.addAction("Zoom Out")
        zoom_out_action.triggered.connect(lambda: self.scale(1 / 1.15, 1 / 1.15))
        zoom_fit_action = menu.addAction("Zoom to Fit")
        zoom_fit_action.triggered.connect(self.zoom_to_fit)
        menu.addSeparator()
        reset_action = menu.addAction("Reset View")
        reset_action.triggered.connect(self.reset_view)
        menu.addSeparator()

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
        self._show_status_message(f"Zoom to fit ({scale:.1f}x)")

    # --- Joint Definition --- #

    def start_define_joint(self):
        """Initiates the joint definition mode."""
        self.set_mode('define_joint')
        self._reset_joint_definition() # Clear previous state
        self._show_status_message("Define Joint: 1. Click parent part.")

    def _handle_joint_definition_click(self, scene_pos: QPointF, view_pos: QPointF):
        """Handles clicks during the joint definition process."""
        item = self.itemAt(view_pos)
        part_item = item if isinstance(item, CharacterPartItem) else None

        if not part_item:
            self._show_status_message("Define Joint: Please click ON a character part.")
            return

        local_pos = part_item.mapFromScene(scene_pos)

        # Step 1: Select parent part
        if self._joint_parent_item is None:
            self._joint_parent_item = part_item
            self._show_status_message(f"Define Joint: Parent '{part_item.part_info.name}' selected. 2. Click joint location ON parent.")

        # Step 2: Select parent position (must click on the same parent item)
        elif self._joint_parent_item == part_item and self._joint_parent_pos is None:
            self._joint_parent_pos = local_pos
            # Add visual marker for parent position
            if self._joint_parent_item_marker:
                 self.scene().removeItem(self._joint_parent_item_marker)
            marker = QGraphicsEllipseItem(-3, -3, 6, 6, parent=self._joint_parent_item)
            marker.setPos(local_pos)
            marker.setBrush(QBrush(Qt.GlobalColor.red))
            marker.setPen(QPen(Qt.GlobalColor.black))
            self._joint_parent_item_marker = marker
            self._show_status_message(f"Define Joint: Parent location set. 3. Click child part.")

        # Step 3: Select child part (must be different from parent)
        elif self._joint_parent_item != part_item and self._joint_parent_pos is not None:
            child_item = part_item
            child_pos = local_pos # Joint location on child is where it was clicked

            # Finalize: We have all data
            joint_data = {
                'parent_item': self._joint_parent_item,
                'child_item': child_item,
                'parent_pos': self._joint_parent_pos,
                'child_pos': child_pos
            }
            self.joint_defined.emit(joint_data) # Emit signal
            self._show_status_message(f"Joint defined between '{self._joint_parent_item.part_info.name}' and '{child_item.part_info.name}'.")
            self._reset_joint_definition() # Reset for next joint definition
            # Optionally switch back to select mode:
            # self.set_mode('select')

        # Invalid clicks (e.g., clicking parent again after setting position)
        else:
            self._show_status_message("Define Joint: Invalid click. Follow the steps.")

    def _reset_joint_definition(self):
        """Resets the state of the joint definition process."""
        if self._joint_parent_item_marker:
            if self._joint_parent_item_marker.scene(): # Check if still in scene
                 self.scene().removeItem(self._joint_parent_item_marker)
            self._joint_parent_item_marker = None
        self._joint_parent_item = None
        self._joint_parent_pos = None
        if self.current_mode == 'define_joint':
             self._show_status_message("Define Joint: Process reset. 1. Click parent part.")

    # --- Motion Path Definition --- #

    def start_define_motion_path(self):
        """Starts the motion path drawing mode for the selected part."""
        selected_item = self.get_selected_item()
        if not selected_item:
            self._show_status_message("Define Motion Path: Please select a part first.")
            return

        self._target_part_for_path = selected_item
        self.set_mode('define_motion_path')
        self._motion_path = QPainterPath()
        self._path_points = []
        self._cleanup_path_visuals() # Clear any previous drawing artifacts
        self._show_status_message(f"Define Path for '{selected_item.part_info.name}': Click to add points. Press Esc or Right-click to cancel.")

    def _handle_motion_path_click(self, scene_pos: QPointF):
        """Handles clicks during motion path definition."""
        # First point
        if not self._path_points:
            self._motion_path.moveTo(scene_pos)
            self._path_points.append(scene_pos)
            self._add_path_point_marker(scene_pos)
            # Create the temporary visual path item
            if not self._temp_path_item:
                pen = QPen(QColor(0, 200, 0, 150), 2, Qt.PenStyle.DashLine)
                self._temp_path_item = self.scene().addPath(self._motion_path, pen)
                self._temp_path_item.setZValue(50) # Ensure visible
            self._show_status_message("Define Path: First point added. Click to add more, Esc/Right-click to cancel, Uncheck button to finish.")
        # Subsequent points
        else:
            self._path_points.append(scene_pos)
            self._add_path_point_marker(scene_pos)
            self._update_interpolated_path_visual()

    def _update_interpolated_path_visual(self):
        """Updates the visual representation of the motion path using smooth curves."""
        if len(self._path_points) < 2:
            # Path is just a point, update moveTo if needed
            if self._temp_path_item and self._path_points:
                 self._motion_path = QPainterPath()
                 self._motion_path.moveTo(self._path_points[0])
                 self._temp_path_item.setPath(self._motion_path)
            return

        # Clean up old connection lines
        for line in self._connection_lines:
            if line.scene(): self.scene().removeItem(line)
        self._connection_lines.clear()

        # Generate smooth path
        self._motion_path = QPainterPath() # Start fresh
        self._motion_path.moveTo(self._path_points[0])

        # Catmull-Rom spline generation (or similar) could be used here
        # Simple cubic bezier for now:
        for i in range(len(self._path_points) - 1):
            p0 = self._path_points[i]
            p1 = self._path_points[i+1]

            # Draw straight dashed line segment for reference
            line_item = QGraphicsLineItem(QLineF(p0, p1))
            line_item.setPen(QPen(QColor(100, 200, 100, 100), 1, Qt.PenStyle.DashLine))
            line_item.setZValue(49)
            self.scene().addItem(line_item)
            self._connection_lines.append(line_item)

            # --- Simple Bezier Calculation ---
            # This is a very basic approach; more sophisticated needed for smoothness
            mid_point = (p0 + p1) / 2
            # For simplicity, just lineTo for now, replace with bezier later
            # TODO: Implement proper bezier control point calculation
            self._motion_path.lineTo(p1)
            # Example cubicTo (needs control points c1, c2):
            # self._motion_path.cubicTo(c1, c2, p1)

        # Update the visible path item
        if self._temp_path_item:
            self._temp_path_item.setPath(self._motion_path)
            # Make path solid once there are multiple points
            pen = QPen(QColor(0, 200, 0), 3, Qt.PenStyle.SolidLine)
            self._temp_path_item.setPen(pen)

    def _add_path_point_marker(self, pos: QPointF):
        """Adds a visual marker for a point added to the motion path."""
        marker = self.scene().addEllipse(-4, -4, 8, 8,
                                         QPen(Qt.GlobalColor.darkGreen),
                                         QBrush(QColor(150, 255, 150)))
        marker.setPos(pos)
        marker.setZValue(100) # Above path
        self._point_markers.append(marker)

    def finish_motion_path_drawing(self):
        """Finalizes the motion path and assigns it to the target part."""
        if self.current_mode != 'define_motion_path' or not self._target_part_for_path or self._motion_path.isEmpty():
            logging.warning("Cannot finish motion path: Invalid state.")
            self._cleanup_path_visuals()
            self.set_mode('select')
            return

        # Smooth the final path if needed (re-run interpolation)
        self._update_interpolated_path_visual() # Ensure final path is smooth

        # Assign path to the part
        # End effector point should ideally be selected *before* path definition
        # Or prompted now. Using default if not set.
        end_effector = self._target_part_for_path.end_effector_offset
        if not end_effector:
            bbox = self._target_part_for_path.boundingRect()
            end_effector = QPointF(bbox.right(), bbox.center().y())
            self._target_part_for_path.end_effector_offset = end_effector
            logging.warning(f"End effector for {self._target_part_for_path.part_info.name} not set, using default.")

        self._target_part_for_path.set_motion_path(self._motion_path, end_effector)

        self._show_status_message(f"Motion path assigned to '{self._target_part_for_path.part_info.name}'")
        self._cleanup_path_visuals()
        self.set_mode('select')

    def _cancel_motion_path_drawing(self):
        """Cancels the current motion path drawing operation."""
        if self.current_mode == 'define_motion_path':
            self._cleanup_path_visuals()
            self._target_part_for_path = None
            self.drawing_cancelled.emit()
            self.set_mode('select')
            self._show_status_message("Motion path cancelled")

    def _cleanup_path_visuals(self):
        """Removes temporary visuals used during path drawing."""
        if self._temp_path_item:
            if self._temp_path_item.scene(): self.scene().removeItem(self._temp_path_item)
            self._temp_path_item = None
        for marker in self._point_markers:
            if marker.scene(): self.scene().removeItem(marker)
        self._point_markers.clear()
        for line in self._connection_lines:
            if line.scene(): self.scene().removeItem(line)
        self._connection_lines.clear()
        self._motion_path = QPainterPath()
        self._path_points = []

    # --- End Effector Selection --- #

    def start_select_end_effector(self):
        """Starts the mode to select the end effector point on the selected part."""
        selected_item = self.get_selected_item()
        if not selected_item:
            self._show_status_message("Select End Effector: Please select a part first.")
            return

        self._target_part_for_end_effector = selected_item
        self.set_mode('select_end_effector')
        self._show_status_message(f"Select End Effector: Click desired point on '{selected_item.part_info.name}'. Esc to cancel.")

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

    # --- Cam Center Selection --- #

    def start_select_cam_center(self):
        """Starts the mode to select the cam center point in the scene."""
        self.set_mode('select_cam_center')
        self._show_status_message("Select Cam Center: Click desired location in the scene. Esc to cancel.")

    def _handle_cam_center_selection_click(self, scene_pos: QPointF):
        """Handles the click to set the cam center position."""
        self.cam_center_selected.emit(scene_pos) # Emit signal
        self._show_status_message(f"Cam center selected at ({scene_pos.x():.1f}, {scene_pos.y():.1f})")
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
        for item in self.scene().items():
            if isinstance(item, CharacterPartItem):
                self._original_transforms[item] = item.transform()

    def _restore_original_transforms(self):
        """Restores the saved transforms of all part items."""
        for item, transform in self._original_transforms.items():
            if item.scene(): # Check if item still exists
                item.setTransform(transform)
        self.scene().update()

    def _reset_simulation_state(self):
        """Ensures the view is interactive after simulation stops/resets."""
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setInteractive(True)

    # --- Utility --- #

    def _show_status_message(self, message: str):
        """Safely displays a message in the parent window's status bar."""
        if self.parent_window and hasattr(self.parent_window, 'statusBar'):
            self.parent_window.statusBar().showMessage(message, 5000) # Show for 5 seconds
        else:
            logging.info(f"Status: {message}") # Fallback logging