"""Coordinator for the refactored editor tab."""

import json
import logging
from typing import Optional, Dict, Any

from PyQt6.QtWidgets import QWidget, QHBoxLayout
from PyQt6.QtCore import pyqtSignal, QPointF
from PyQt6.QtGui import QPainterPath

from .state import EditorState
from .handlers import (
    PartSelectionHandler,
    PathDrawingHandler,
    SimulationHandler,
    ViewHandler
)
from .components import EditorMainPanel, EditorControlPanel
from automataii.gui.views.editor.editor_view import EditorView
from PyQt6.QtWidgets import QGraphicsScene
from automataii.services import PathDrawingService, AnimationService
from automataii.interfaces import IKManagerInterface, ProjectManagerInterface, SkeletonManagerInterface
from automataii.controllers import EditorController


class EditorTabCoordinator(QWidget):
    """Main coordinator for the editor tab.

    This class coordinates all editor functionality while keeping
    the implementation under 200 lines by delegating to specialized
    components and handlers.
    """

    # Signals for external communication
    paths_ready_for_mechanism = pyqtSignal(dict, dict)  # parts_dict, paths_dict
    request_save_alignment = pyqtSignal()
    request_play_simulation = pyqtSignal()
    request_stop_simulation = pyqtSignal()
    request_reset_simulation = pyqtSignal()
    motion_path_updated = pyqtSignal(str, QPainterPath)  # part_name, QPainterPath

    def __init__(
        self,
        ik_manager: IKManagerInterface,
        project_manager: ProjectManagerInterface,
        skeleton_manager: SkeletonManagerInterface,
        parent=None
    ):
        super().__init__(parent)

        # State
        self._state = EditorState()

        # Store managers
        self._ik_manager = ik_manager
        self._project_manager = project_manager
        self._skeleton_manager = skeleton_manager

        # Services
        self._path_service = PathDrawingService()
        self._animation_service = AnimationService()

        # Controller
        self._controller = EditorController(
            self._path_service,
            self._animation_service,
            ik_manager,
            project_manager,
            skeleton_manager
        )

        # Handlers
        self._selection_handler = PartSelectionHandler(self._state)
        self._path_handler = PathDrawingHandler(self._state, self._path_service)
        self._simulation_handler = SimulationHandler(
            self._state,
            self._animation_service,
            ik_manager
        )
        self._view_handler = ViewHandler(self._state)

        # Scene and view
        self._scene = QGraphicsScene()
        self._view = EditorView(self._scene, self)

        # UI components
        self._control_panel = EditorControlPanel(
            self._state,
            self._selection_handler,
            self._path_handler,
            self._simulation_handler,
            parent=self
        )

        self._main_panel = EditorMainPanel(
            self._view,
            self._view_handler,
            parent=self
        )

        self._init_ui()
        self._connect_signals()

        logging.info("EditorTabCoordinator initialized")

    def _init_ui(self):
        """Initialize the UI layout."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Add control panel and main panel
        layout.addWidget(self._control_panel)
        layout.addWidget(self._main_panel, 1)

    def _connect_signals(self):
        """Connect internal signals."""
        # Controller signals
        self._controller.state_changed.connect(self._on_controller_state_changed)
        self._controller.parts_updated.connect(self._on_parts_updated)
        self._controller.skeleton_updated.connect(self._on_skeleton_updated)

        # View signals
        self._view.part_item_clicked.connect(lambda item: self._selection_handler.select_part(item.part_name))
        self._view.freehandPathCompleted.connect(self._handle_freehand_path_completed)
        # TODO: Add proper point_clicked signal handling

        # Control panel signals
        self._control_panel.goto_mechanism_requested.connect(
            self._prepare_mechanism_generation
        )
        self._control_panel.save_alignment_requested.connect(
            self.request_save_alignment
        )

        # Path drawing signals
        self._control_panel._path_controls.define_path_requested.connect(
            self._start_path_drawing_mode
        )
        self._control_panel._path_controls.clear_path_requested.connect(
            self._clear_selected_part_path
        )

        # Connect simulation handler signals to public signals
        self._simulation_handler.simulation_started.connect(
            lambda: self.request_play_simulation.emit()
        )
        self._simulation_handler.simulation_stopped.connect(
            lambda: self.request_stop_simulation.emit()
        )
        self._simulation_handler.simulation_reset.connect(
            lambda: self.request_reset_simulation.emit()
        )

    def load_parts(self, parts_data: Dict[str, Any]) -> None:
        """Load parts into the editor."""
        logging.info(f"EditorTabCoordinator.load_parts called with {len(parts_data) if parts_data else 0} parts")
        success = self._controller.load_parts(parts_data)
        if success:
            self._view.clear_scene()
            # Add parts to view
            for part_name, part_info in parts_data.items():
                # Create visual representation
                self._create_part_visual(part_name, part_info)
                logging.info(f"Created visual for part: {part_name}")

            # Try to load skeleton data if available
            if hasattr(self, '_skeleton_manager') and self._skeleton_manager:
                skeleton_data = self._skeleton_manager.raw_input_data
                if skeleton_data:
                    self.load_skeleton(skeleton_data)
                    logging.info("EditorTabCoordinator: Loaded skeleton data with parts")

    def load_skeleton(self, skeleton_data: Dict[str, Any]) -> None:
        """Load skeleton data."""
        self._controller.load_skeleton(skeleton_data)

    def clear_all(self) -> None:
        """Clear all editor content."""
        self._controller.clear_parts()
        self._view.clear_scene()
        self._path_service.clear_all()
        self._animation_service.clear()

    def _create_part_visual(self, part_name: str, part_info: Any) -> None:
        """Create visual representation of a part."""
        from automataii.gui.graphics_items.part_item import CharacterPartItem
        from PyQt6.QtCore import QPointF
        from pathlib import Path
        import logging

        # Get project directory from part info image path or use a default
        if hasattr(part_info, 'image_path') and part_info.image_path:
            project_dir = Path(part_info.image_path).parent
        else:
            # Fallback to a temporary directory
            project_dir = Path("/tmp")

        # Create the CharacterPartItem
        part_item = CharacterPartItem(part_info, project_dir, parent=None)
        # Name is already set in part_info.name, no need to set it separately

        # Position part based on anchor joint if available
        pos = QPointF(0, 0)  # Default position

        # Try to get position from anchor joint (preferred method)
        if hasattr(part_info, 'anchor_joint_id') and part_info.anchor_joint_id:
            joint_position = self._get_joint_position(part_info.anchor_joint_id)
            if joint_position:
                # Use set_scene_position_from_anchor to properly position the part
                part_item.set_scene_position_from_anchor(joint_position)
                pos = part_item.pos()
                logging.info(f"Positioned part '{part_name}' using anchor joint '{part_info.anchor_joint_id}' at {joint_position}")

        # Fallback to position from part_info
        elif hasattr(part_info, 'position') and part_info.position:
            pos = QPointF(part_info.position[0], part_info.position[1])
            part_item.setPos(pos)
            logging.info(f"Positioned part '{part_name}' using part_info.position at {pos}")

        # Add to scene
        self._scene.addItem(part_item)

        # Store in state for tracking
        if part_name not in self._state.parts:
            from automataii.gui.tabs.editor.state.editor_state import PartState
            part_state = PartState(
                name=part_name,
                position=pos if 'pos' in locals() else QPointF(0, 0),
                z_value=getattr(part_info, 'z_value', 0.0),
                is_fixed=getattr(part_info, 'fixed', False),
                anchor_joint_id=getattr(part_info, 'anchor_joint_id', None)
            )
            self._state.add_part(part_state)

        # Store reference for editor_items compatibility
        if not hasattr(self, 'editor_items'):
            self.editor_items = {}
        self.editor_items[part_name] = part_item

        # Also store in view's parent_window for compatibility
        if hasattr(self._view, 'parent_window') and self._view.parent_window:
            if not hasattr(self._view.parent_window, 'editor_items'):
                self._view.parent_window.editor_items = {}
            self._view.parent_window.editor_items[part_name] = part_item

        logging.info(f"Created visual for part: {part_name}")

    def _get_joint_position(self, joint_id: str) -> Optional[QPointF]:
        """Get the position of a joint from the skeleton data."""
        from PyQt6.QtCore import QPointF

        # Try to get skeleton data from the controller
        if hasattr(self._controller, '_skeleton_data') and self._controller._skeleton_data:
            skeleton_data = self._controller._skeleton_data

            # Handle different skeleton data formats
            if isinstance(skeleton_data, dict):
                skeleton_list = skeleton_data.get('skeleton', [])
                if isinstance(skeleton_list, list):
                    # Find joint by name or id
                    for joint in skeleton_list:
                        if isinstance(joint, dict):
                            joint_name = joint.get('name', joint.get('id'))
                            if joint_name == joint_id:
                                loc = joint.get('loc')
                                if loc and len(loc) >= 2:
                                    # Add bbox offset if available
                                    bbox_x = skeleton_data.get('bbox_origin_x', 0)
                                    bbox_y = skeleton_data.get('bbox_origin_y', 0)
                                    return QPointF(float(loc[0]) + bbox_x, float(loc[1]) + bbox_y)

        # Try to get from skeleton manager if available
        if hasattr(self, '_main_window') and hasattr(self._main_window, 'skeleton_manager'):
            skeleton_manager = self._main_window.skeleton_manager
            if hasattr(skeleton_manager, 'get_joint_position'):
                return skeleton_manager.get_joint_position(joint_id)

        return None

    def _start_path_drawing_mode(self):
        """Start path drawing mode for selected part."""
        selected_part = self._state.get_selected_part()
        if not selected_part:
            logging.warning("No part selected for path drawing")
            return

        # Get corresponding part item from scene
        part_item = None
        if hasattr(self, 'editor_items') and selected_part.name in self.editor_items:
            part_item = self.editor_items[selected_part.name]

        # Start path drawing mode in view
        self._view.start_define_motion_path(part_item)

        logging.info(f"Started path drawing mode for part: {selected_part.name}")

    def _clear_selected_part_path(self):
        """Clear motion path for selected part."""
        selected_part = self._state.get_selected_part()
        if not selected_part:
            return

        # Clear path through view
        if hasattr(self._view, 'clear_visual_path_for_component'):
            self._view.clear_visual_path_for_component(selected_part.name)

        # Update state
        if selected_part.name in self._state.parts:
            self._state.parts[selected_part.name].has_motion_path = False
            self._state.parts[selected_part.name].motion_path = None

        logging.info(f"Cleared motion path for part: {selected_part.name}")

    def _handle_freehand_path_completed(self, path_points):
        """Handle freehand path completion from EditorView."""
        from PyQt6.QtGui import QPainterPath
        from PyQt6.QtCore import QPointF

        selected_part = self._state.selected_part_name
        if not selected_part:
            logging.warning("EditorTabCoordinator: freehandPathCompleted but no part selected")
            return

        logging.info(f"EditorTabCoordinator: freehandPathCompleted for '{selected_part}' with {len(path_points)} points")

        # Convert points to QPainterPath
        motion_qpath = QPainterPath()
        if path_points:
            motion_qpath.moveTo(path_points[0])
            for point in path_points[1:]:
                motion_qpath.lineTo(point)

        # Update EditorState
        if selected_part in self._state.parts:
            part_state = self._state.parts[selected_part]
            part_state.motion_path = motion_qpath
            part_state.has_motion_path = True
            logging.info(f"EditorTabCoordinator: Updated EditorState for '{selected_part}' with motion path")

        # Emit signal for MainWindow
        self.motion_path_updated.emit(selected_part, motion_qpath)

        # Update UI - both path UI and selection UI to refresh the path status
        self._control_panel._update_path_ui()
        self._control_panel._update_selection_ui()

    def _handle_view_click(self, point) -> None:
        """Handle click in view based on current mode."""
        if self._state.is_drawing_path:
            self._path_handler.add_point(point)
        elif self._state.mode.value == "define_joint":
            # Handle joint definition
            pass

    def _on_controller_state_changed(self, state) -> None:
        """Handle controller state changes."""
        # Update UI based on state
        self._control_panel.update_state(state)

    def _on_parts_updated(self, parts_info) -> None:
        """Handle parts update from controller."""
        # Update EditorState with parts info
        from .state.editor_state import PartState

        # Clear existing parts
        self._state.clear_parts()

        # Add parts to state
        for part_name, part_info in parts_info.items():
            # Get position from part info or default
            position = QPointF(0, 0)
            if hasattr(part_info, 'x') and hasattr(part_info, 'y'):
                position = QPointF(part_info.x, part_info.y)

            # Create PartState
            part_state = PartState(
                name=part_name,
                position=position,
                z_value=getattr(part_info, 'z_value', 0.0),
                is_fixed=getattr(part_info, 'fixed', False),
                has_motion_path=getattr(part_info, 'motion_path_data', None) is not None,
                motion_path=getattr(part_info, 'motion_path_data', None),
                anchor_joint_id=getattr(part_info, 'anchor_joint_id', None)
            )

            self._state.add_part(part_state)

        logging.info(f"EditorTabCoordinator: Updated state with {len(parts_info)} parts")

        # Check for existing motion paths in project data and update EditorState
        self._load_existing_motion_paths()

        # Force update path UI after parts are loaded
        self._control_panel._update_path_ui()

    def _on_skeleton_updated(self, skeleton_data: Optional[Dict[str, Any]]) -> None:
        """Handle skeleton data updates from the controller."""
        if skeleton_data:
            joints = skeleton_data.get("joints", [])
            hierarchy = skeleton_data.get("hierarchy", {})

            # Update the view with the skeleton
            self._view.visualize_skeleton(joints, hierarchy)
        else:
            # Skeleton is being cleared.
            # Stop any ongoing simulation that depends on it to prevent errors.
            if self._simulation_handler.is_playing():
                self._simulation_handler.stop()

            # Clear skeleton from view if data is None
            self._view.visualize_skeleton([], {})

    def _prepare_mechanism_generation(self) -> None:
        """Prepare data for mechanism generation tab."""
        parts_dict = {}
        paths_dict = self._controller.get_all_paths()

        # Gather parts data
        for part_name, part_state in self._state.parts.items():
            parts_dict[part_name] = part_state

        self.paths_ready_for_mechanism.emit(parts_dict, paths_dict)

    # Compatibility methods for existing code
    def set_parts_data(self, parts_info: Dict[str, Any]) -> None:
        """Set parts data (compatibility method)."""
        logging.info(f"EditorTabCoordinator.set_parts_data called with {len(parts_info) if parts_info else 0} parts")
        self.load_parts(parts_info)

    def clear_editor_content(self) -> None:
        """Clear editor content (compatibility method)."""
        self.clear_all()

    def cache_initial_skeleton(self, skeleton_data: Optional[Dict[str, Any]]) -> None:
        """Cache initial skeleton data (compatibility method)."""
        if skeleton_data:
            self.load_skeleton(skeleton_data)

    def on_skeleton_updated(self, skeleton_data: Dict[str, Any]) -> None:
        """Handle skeleton update (compatibility method)."""
        self.load_skeleton(skeleton_data)

    def handle_ik_update(self, part_transforms: Dict[str, Any]) -> None:
        """Handle IK update (compatibility method)."""
        # Convert part transforms to joint data format for the simulation controller
        joint_data = {}

        for part_name, transform_data in part_transforms.items():
            if not isinstance(transform_data, dict):
                continue

            # Get anchor joint ID from transform data or from state
            anchor_joint_id = transform_data.get('anchor_joint_id')
            if not anchor_joint_id and part_name in self._state.parts:
                anchor_joint_id = self._state.parts[part_name].anchor_joint_id

            if not anchor_joint_id:
                logging.warning(f"No anchor joint ID for part '{part_name}'")
                continue

            # Create joint data entry
            position = transform_data.get('position')
            if isinstance(position, QPointF):
                scene_position = position
            elif isinstance(position, (list, tuple)) and len(position) >= 2:
                scene_position = QPointF(position[0], position[1])
            else:
                logging.warning(f"Invalid position data for part '{part_name}'")
                continue

            joint_data[anchor_joint_id] = {
                'scene_position': scene_position,
                'world_rotation_degrees': transform_data.get('rotation', 0.0)
            }

        # Pass to view's simulation controller
        if hasattr(self._view, 'simulation_controller'):
            self._view.simulation_controller.update_visuals_from_animation_data(joint_data)
            logging.debug(f"EditorTabCoordinator: Updated visuals for {len(joint_data)} joints")
        else:
            logging.warning("EditorTabCoordinator: View has no simulation controller")

    def clear_all_visual_motion_paths(self) -> None:
        """Clear all visual motion paths (compatibility method)."""
        self._view.clear_all_motion_paths()

    def _update_button_states(self) -> None:
        """Update button states (compatibility method)."""
        # TODO: Implement button state updates
        pass

    @property
    def editor_view(self):
        """Get editor view (compatibility property)."""
        return self._view

    def on_simulation_state_changed(self, state: str) -> None:
        """Handle simulation state changes (compatibility method)."""
        # This method is called from IKManager's animation_state_changed signal
        # We should only update UI state, NOT trigger more simulation actions
        from .state import SimulationState

        # Add a guard to prevent recursive calls
        if hasattr(self, '_processing_state_change') and self._processing_state_change:
            return

        current_state = self._state.simulation_state.value
        if current_state == state:
            # Already in this state, ignore to prevent recursion
            return

        # Set guard flag
        self._processing_state_change = True

        try:
            print(f"EditorTabCoordinator: IK state changed from '{current_state}' to '{state}' - updating UI only")

            # Update simulation state in EditorState
            if state == "playing":
                self._state.simulation_state = SimulationState.PLAYING
            elif state == "stopped":
                self._state.simulation_state = SimulationState.STOPPED
            elif state == "paused":
                self._state.simulation_state = SimulationState.PAUSED

            # Only update UI, don't trigger any simulation actions
            if hasattr(self, '_control_panel'):
                if state == "playing":
                    self._control_panel._on_simulation_started()
                elif state == "stopped":
                    self._control_panel._on_simulation_stopped()

        finally:
            # Always clear the guard flag
            self._processing_state_change = False

    def on_motion_path_updated(self, part_name: str, motion_path) -> None:
        """Handle motion path updates from external sources (e.g., MainWindow)."""
        logging.info(f"EditorTabCoordinator: Motion path updated for '{part_name}'")

        # Update the EditorState with the motion path
        if part_name in self._state.parts:
            part_state = self._state.parts[part_name]
            part_state.motion_path = motion_path
            part_state.has_motion_path = True
            logging.info(f"EditorTabCoordinator: Updated EditorState for '{part_name}' with motion path")

            # Trigger UI update
            self._control_panel._update_path_ui()
        else:
            logging.warning(f"EditorTabCoordinator: Part '{part_name}' not found in EditorState")

    def _load_existing_motion_paths(self) -> None:
        """Load existing motion paths from project data manager into EditorState."""
        if not self._project_manager:
            return

        # Get motion paths from project data manager
        try:
            motion_paths = self._project_manager.get_motion_paths()
            if motion_paths:
                logging.info(f"EditorTabCoordinator: Found {len(motion_paths)} existing motion paths")
                for part_name, motion_path in motion_paths.items():
                    if part_name in self._state.parts and motion_path:
                        part_state = self._state.parts[part_name]
                        part_state.motion_path = motion_path
                        part_state.has_motion_path = True
                        logging.info(f"EditorTabCoordinator: Loaded existing motion path for '{part_name}'")
            else:
                logging.info("EditorTabCoordinator: No existing motion paths found in project data")
        except Exception as e:
            logging.warning(f"EditorTabCoordinator: Error loading existing motion paths: {e}")
