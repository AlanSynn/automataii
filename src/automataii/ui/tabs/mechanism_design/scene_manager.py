# src/automataii/gui/tabs/mechanism_design/scene_manager.py
import logging

from PyQt6.QtCore import QObject, QPointF
from PyQt6.QtGui import QColor, QPainterPath, QPen
from PyQt6.QtWidgets import QGraphicsPathItem

from automataii.config.z_indices import (
    Z_MECHANISM_PIVOT,
    Z_MOTION_PATH_LINE,
    Z_PART_DEFAULT,
    Z_SKELETON_OVERLAY,
)
from automataii.ui.graphics_items.part_item import CharacterPartItem
from automataii.ui.graphics_items.skeleton_item import SkeletonGraphicsItem

from .utils import extract_key_points_from_simulation
from .visuals import visual_factory

logger = logging.getLogger(__name__)


class MechanismSceneManager(QObject):
    """
    (View/Facade) Manages all visual elements and their complex interactions in the QGraphicsScene.
    """

    def __init__(self, scene, state_manager, parent=None):
        super().__init__(parent)
        self.scene = scene
        self.state = state_manager
        self.parent_widget = parent

        self.path_items = {}
        self.part_items = {}
        self.mechanism_visuals = {}
        self.trace_path_items = {}
        self.preview_items = []
        self.skeleton_item = None
        self.debug_items = []
        self.show_debug_visuals = False

        # Connect to state changes for part selection
        self.state.part_selection_changed.connect(self._on_part_selection_changed)

        # Force visualization system
        from automataii.ui.tabs.mechanism_design.visuals.force_visual import ForceSystemVisualizer
        self.force_visualizer = ForceSystemVisualizer(self)

    def update_scene_from_state(self):
        self._update_motion_paths()
        self._update_part_visuals()

    def _update_motion_paths(self):
        visible_paths = {
            name: path
            for name, path in self.state.path_data.items()
            if self.state.part_enabled_state.get(name, True)
        }
        for name in list(self.path_items.keys()):
            if name not in visible_paths:
                self._safe_remove_item(self.path_items.pop(name))
        for name, path_data in visible_paths.items():
            if name not in self.path_items:
                path_item = QGraphicsPathItem()
                path_item.setZValue(Z_MOTION_PATH_LINE)
                self.scene.addItem(path_item)
                self.path_items[name] = path_item
            pen_color = (
                QColor("#3498db") if name == self.state.selected_part_name else QColor("#bdc3c7")
            )
            self.path_items[name].setPen(QPen(pen_color, 2))
            self.path_items[name].setPath(path_data)

    def _update_part_visuals(self):
        project_dir = self.parent_widget.main_window.project_data_manager.project_dir
        if not project_dir:
            return

        for name in list(self.part_items.keys()):
            if name not in self.state.parts_data:
                self._safe_remove_item(self.part_items.pop(name))

        for name, part_info in self.state.parts_data.items():
            if name not in self.part_items:
                item = CharacterPartItem(part_info=part_info, project_dir=project_dir)
                item.setZValue(Z_PART_DEFAULT)
                item.setFlag(item.GraphicsItemFlag.ItemIsMovable, False)
                item.setFlag(item.GraphicsItemFlag.ItemIsSelectable, True)
                self.scene.addItem(item)
                self.part_items[name] = item

        self._position_parts_at_anchor_joints()

    def _position_parts_at_anchor_joints(self):
        if not self.state.initial_skeleton_data:
            return
        joints_dict = self.state.initial_skeleton_data.get("joints", {})
        for name, part_item in self.part_items.items():
            part_info = self.state.parts_data.get(name)
            if part_info and part_info.anchor_joint_id in joints_dict:
                joint_data = joints_dict[part_info.anchor_joint_id]
                joint_pos = joint_data.get("position", [0, 0])
                scene_pos = QPointF(joint_pos[0], joint_pos[1])
                part_item.set_scene_position_from_anchor(scene_pos)

    def add_mechanism_visuals(self, mechanism_id):
        logger.info(f"SceneManager: Adding visuals for mechanism {mechanism_id}")

        # First, remove any existing visuals for this mechanism to prevent duplicates
        self.remove_mechanism_visuals(mechanism_id)

        layer_data = self.state.mechanism_layers.get(mechanism_id)
        if not layer_data:
            logger.error(f"SceneManager: No layer data found for mechanism {mechanism_id}")
            return

        logger.info(f"SceneManager: Creating visuals for mechanism type {layer_data.get('type')} with {len(layer_data)} data keys")
        logger.info(f"SceneManager: Layer data keys: {list(layer_data.keys())}")

        visual_items, debug_items = visual_factory.create(layer_data, self)
        self.mechanism_visuals[mechanism_id] = visual_items
        logger.info(f"SceneManager: Created {len(visual_items)} visual items for mechanism {mechanism_id}")

        # Log each visual item's properties
        for i, item in enumerate(visual_items):
            logger.info(f"SceneManager: Visual item {i}: type={type(item).__name__}, in_scene={item.scene() is not None}, visible={item.isVisible() if hasattr(item, 'isVisible') else 'N/A'}")

        # Add debug items and set their visibility
        for item in debug_items:
            self.scene.addItem(item)
            item.setVisible(self.show_debug_visuals)
            self.debug_items.append(item)

        self._init_mechanism_path_trace(mechanism_id)
        self.update_animation_frame(0)

        # Force scene update
        self.scene.update()
        logger.info(f"SceneManager: Scene updated after adding mechanism visuals")

        # Debug: Check actual positions of visual items
        if visual_items:
            scene_rect = self.scene.sceneRect()
            logger.info(f"SceneManager: Scene rect: {scene_rect}")

            for i, item in enumerate(visual_items):
                if hasattr(item, 'line'):
                    line = item.line()
                    logger.info(f"SceneManager: Line item {i} - start: ({line.x1():.1f}, {line.y1():.1f}), end: ({line.x2():.1f}, {line.y2():.1f})")
                elif hasattr(item, 'rect'):
                    rect = item.rect()
                    logger.info(f"SceneManager: Rect item {i} - pos: ({rect.x():.1f}, {rect.y():.1f}), size: ({rect.width():.1f}, {rect.height():.1f})")
                elif hasattr(item, 'polygon'):
                    poly = item.polygon()
                    if not poly.isEmpty():
                        first_point = poly.at(0)
                        logger.info(f"SceneManager: Polygon item {i} - first point: ({first_point.x():.1f}, {first_point.y():.1f})")

        # Don't auto-start animation - user must press Play button
        logger.info("SceneManager: Mechanism added. Press Play button to start animation.")

    def update_mechanism_visuals(self, mechanism_id):
        """Re-creates the visuals for a specific mechanism, e.g., after a parameter change."""
        self.add_mechanism_visuals(mechanism_id)

    def remove_mechanism_visuals(self, mechanism_id):
        """Safely removes all visual items associated with a mechanism."""
        if mechanism_id in self.mechanism_visuals:
            for item in self.mechanism_visuals[mechanism_id]:
                self._safe_remove_item(item)
            del self.mechanism_visuals[mechanism_id]

        if mechanism_id in self.trace_path_items:
            self._safe_remove_item(self.trace_path_items[mechanism_id])
            del self.trace_path_items[mechanism_id]

    def update_animation_frame(self, time):
        mechanism_outputs = {}
        for mid, layer_data in self.state.mechanism_layers.items():
            # Check if the mechanism itself is enabled
            if self.state.mechanism_enabled_state.get(mid, True):
                visuals = self.mechanism_visuals.get(mid, [])
                if not visuals:  # If visuals were cleared, recreate them
                    self.add_mechanism_visuals(mid)
                    visuals = self.mechanism_visuals.get(mid, [])

                output_pos = visual_factory.update(mid, layer_data, time, visuals)
                if output_pos:
                    mechanism_outputs[layer_data["part_name"]] = output_pos
                    self._update_mechanism_path_trace(mid, output_pos)

                # Update force visualization if enabled
                self.force_visualizer.update_forces(layer_data, time)

        if mechanism_outputs:
            self._update_ik_from_mechanism(mechanism_outputs)

    def get_mechanism_output_position(self, mechanism_id, time):
        """
        Calculates the output position of a single mechanism at a given time
        without altering the visual state.
        """
        layer_data = self.state.mechanism_layers.get(mechanism_id)
        if not layer_data:
            return None

        # This is a simulation-only call, so we pass temporary empty lists for visuals.
        # The factory's `update` function for some types might not need actual visual items.
        # This relies on the factory being able to calculate output without real items.
        output_pos = visual_factory.update(mechanism_id, layer_data, time, [])
        return output_pos

    def _update_ik_from_mechanism(self, mechanism_outputs):
        """Triggers IK updates based on the mechanism's output positions."""
        ik_manager = self.parent_widget.main_window.ik_manager
        if not ik_manager:
            return

        targets = {}
        for part_name, position in mechanism_outputs.items():
            part_info = self.state.parts_data.get(part_name)
            if not part_info:
                continue

            # Determine the end-effector joint for this part
            target_joint_id = ik_manager.get_end_effector_for_part(part_name)
            if not target_joint_id:
                logger.warning(f"No end-effector found for part '{part_name}'. IK not triggered.")
                continue

            # Collect targets for batch solving
            targets[target_joint_id] = position

        # Solve IK for all targets at once
        if targets:
            ik_manager.solve_for_targets(targets)

    def clear_all_mechanisms(self):
        """Enhanced mechanism clearing with comprehensive memory cleanup"""
        logger.info("Clearing all mechanisms with enhanced memory management")

        # Clear mechanism visuals first
        for mid in list(self.mechanism_visuals.keys()):
            self.remove_mechanism_visuals(mid)
        self.mechanism_visuals.clear()

        # Clear trace path items
        for item in list(self.trace_path_items):
            self._safe_remove_item(item)
        self.trace_path_items.clear()

        # Clear debug items
        for item in list(self.debug_items):
            self._safe_remove_item(item)
        self.debug_items.clear()

        # Clear preview items
        for item in list(self.preview_items):
            self._safe_remove_item(item)
        self.preview_items.clear()

        # Clear skeleton joint highlights
        if self.skeleton_item:
            self.skeleton_item.clear_highlights()

        # Force garbage collection hint
        import gc
        gc.collect()

        logger.info("All mechanisms cleared successfully")

    def reset_all_visuals(self):
        self.update_animation_frame(0)
        self._position_parts_at_anchor_joints()
        if self.skeleton_item and self.state.initial_skeleton_data:
            self.update_skeleton_from_ik(self.state.initial_skeleton_data)
        for tpi in self.trace_path_items.values():
            tpi.setPath(QPainterPath())

    def ensure_skeleton_visualization(self, skeleton_data):
        if not skeleton_data:
            self._safe_remove_item(self.skeleton_item)
            self.skeleton_item = None
            return
        if not self.skeleton_item:
            skeleton_for_view, hierarchy = self._format_skeleton_for_viz(skeleton_data)
            if skeleton_for_view:
                self.skeleton_item = SkeletonGraphicsItem(
                    skeleton_for_view,
                    hierarchy,
                    mechanism_mode=True,  # Enable mechanism mode for proper Z-indexing
                )
                self.skeleton_item.setZValue(Z_SKELETON_OVERLAY)
                self.scene.addItem(self.skeleton_item)

                # Connect skeleton interaction signals
                self.skeleton_item.signals.joint_clicked.connect(self._on_joint_clicked)
                self.skeleton_item.signals.joint_double_clicked.connect(
                    self._on_joint_double_clicked
                )

                logger.info(
                    "MechanismSceneManager: Skeleton visualization added with joint interactions"
                )
        self.update_skeleton_from_ik(skeleton_data)

    def update_skeleton_from_ik(self, ik_results):
        if not self.skeleton_item:
            self.ensure_skeleton_visualization(ik_results)
            return

        # Check if ik_results is already in tuple format (from IKManager)
        if isinstance(ik_results, dict) and all(isinstance(v, tuple) for v in ik_results.values()):
            # IK results are already in the correct format (joint_id -> (x, y))
            pose_data = ik_results
            logger.debug(f"Using direct IK results: {len(pose_data)} joints")
        else:
            # Legacy format - convert from skeleton data format
            pose_data = self._convert_skeleton_data_for_animation(ik_results)
            logger.debug(f"Converted skeleton data to pose: {len(pose_data)} joints")

        if pose_data:
            self.skeleton_item.set_animated_pose(pose_data)

        # Update parts only if we have legacy skeleton data format
        if not isinstance(ik_results, dict) or not all(isinstance(v, tuple) for v in ik_results.values()):
            self._update_parts_from_skeleton(ik_results)

    def _update_parts_from_skeleton(self, skeleton_data):
        joints_dict = skeleton_data.get("joints", {})
        for name, part_item in self.part_items.items():
            # Parts controlled by a mechanism are positioned by the IK, not directly here
            if any(
                layer.get("part_name") == name for layer in self.state.mechanism_layers.values()
            ):
                # Let IK handle the position of mechanism-driven parts and their chains
                pass

            part_info = self.state.parts_data.get(name)
            if part_info and part_info.anchor_joint_id in joints_dict:
                joint_data = joints_dict[part_info.anchor_joint_id]
                pos_data = joint_data.get("scene_position") or joint_data.get("position")
                if pos_data:
                    part_item.set_scene_position_from_anchor(QPointF(pos_data[0], pos_data[1]))
                # Rotation logic would go here as well

    def preview_mechanism(self, mechanism_data: dict):
        """Shows a temporary preview of a mechanism."""
        self.clear_preview()

        # Construct a temporary layer_data for the preview
        # Extract key points from the full simulation data if available
        key_points = extract_key_points_from_simulation(
            mechanism_data.get("full_simulation_data", {}), mechanism_data.get("type")
        )

        layer_data = {
            "type": mechanism_data.get("type"),
            "params": mechanism_data.get("parameters"),
            "transform_params": mechanism_data.get("transform_params"),
            "full_simulation_data": mechanism_data.get("full_simulation_data", {}),
            "key_points": key_points,
            "generated_path": self.state.path_data.get(self.state.selected_part_name),
        }

        self.preview_items, _ = visual_factory.create(layer_data, self, is_preview=True)
        # Animate the preview to the initial position
        visual_factory.update("preview", layer_data, 0, self.preview_items)

    def clear_preview(self):
        """Removes any temporary preview items from the scene."""
        for item in self.preview_items:
            self._safe_remove_item(item)
        self.preview_items.clear()

    def toggle_debug_visuals(self, show: bool):
        """Shows or hides debug graphics."""
        self.show_debug_visuals = show
        for item in self.debug_items:
            item.setVisible(show)

    def toggle_force_visualization(self, enabled: bool):
        """Toggle force visualization on/off"""
        self.force_visualizer.set_show_forces(enabled)
        logger.info(f"Force visualization {'enabled' if enabled else 'disabled'}")

    def set_force_scale(self, scale: float):
        """Set force vector scale factor"""
        self.force_visualizer.set_scale_factor(scale)
        logger.info(f"Force scale set to {scale}")

    def is_force_visualization_enabled(self) -> bool:
        """Check if force visualization is currently enabled"""
        return self.force_visualizer.show_forces

    def _init_mechanism_path_trace(self, mechanism_id):
        path_item = QGraphicsPathItem()
        path_item.setPen(QPen(QColor("#f39c12"), 1.5))
        path_item.setZValue(Z_MECHANISM_PIVOT - 1)
        self.scene.addItem(path_item)
        self.trace_path_items[mechanism_id] = path_item

    def _update_mechanism_path_trace(self, mechanism_id, point):
        if mechanism_id in self.trace_path_items:
            path = self.trace_path_items[mechanism_id].path()
            if path.isEmpty():
                path.moveTo(point)
            else:
                path.lineTo(point)
            self.trace_path_items[mechanism_id].setPath(path)

    def _safe_remove_item(self, item):
        """Enhanced safe item removal with memory leak prevention"""
        if not item:
            return

        try:
            # Check if item is still valid and in scene
            if item.scene():
                # Disconnect any signals first to prevent callbacks during deletion
                if hasattr(item, 'disconnect'):
                    item.disconnect()

                # Remove from scene
                self.scene.removeItem(item)

            # Clear highlights if removing skeleton item
            if item is self.skeleton_item:
                if self.skeleton_item:
                    self.skeleton_item.clear_highlights()
                self.skeleton_item = None

            # Force cleanup of item properties
            if hasattr(item, 'setParentItem'):
                item.setParentItem(None)

            # Clear any references in our tracking lists
            for item_list in [self.mechanism_visuals, self.preview_items,
                            self.debug_items, self.trace_path_items]:
                if isinstance(item_list, dict):
                    # Handle dict values that might be lists
                    for key, value in list(item_list.items()):
                        if isinstance(value, list) and item in value:
                            value.remove(item)
                        elif value is item:
                            del item_list[key]
                elif isinstance(item_list, list) and item in item_list:
                    item_list.remove(item)

        except RuntimeError as e:
            # Item already deleted
            logger.debug(f"Item already deleted during removal: {e}")
        except Exception as e:
            logger.warning(f"Error during safe item removal: {e}")

        finally:
            # Ensure item reference is cleared
            item = None

    def _format_skeleton_for_viz(self, skeleton_data):
        skeleton_for_view, hierarchy = [], {}
        if "joints" not in skeleton_data:
            return skeleton_for_view, hierarchy
        for joint_id, joint_info in skeleton_data["joints"].items():
            pos = joint_info.get("position", [0, 0])
            parent = joint_info.get("parent")
            skeleton_for_view.append(
                {
                    "id": joint_id,
                    "name": joint_id,
                    "parent": parent,
                    "position": QPointF(pos[0], pos[1]),
                    "color": "blue",
                    "label": joint_id,
                }
            )
            if parent:
                if parent not in hierarchy:
                    hierarchy[parent] = []
                hierarchy[parent].append(joint_id)
        return skeleton_for_view, hierarchy

    def _convert_skeleton_data_for_animation(self, skeleton_data):
        pose_data = {}
        if "joints" not in skeleton_data:
            return pose_data
        for joint_id, joint_info in skeleton_data["joints"].items():
            pos = joint_info.get("scene_position") or joint_info.get("position")
            if pos:
                pose_data[joint_id] = (pos[0], pos[1])
        return pose_data

    def _on_part_selection_changed(self, part_name: str) -> None:
        """Handle part selection changes to highlight associated joints."""
        if not self.skeleton_item:
            return

        # Clear previous highlights
        self.skeleton_item.clear_highlights()

        # Highlight joints for selected part
        if part_name:
            joint_ids = self._get_joint_ids_for_part(part_name)
            if joint_ids:
                self.skeleton_item.highlight_joints(joint_ids, "orange")
                logger.debug(
                    f"MechanismSceneManager: Highlighted {len(joint_ids)} joints for part '{part_name}': {joint_ids}"
                )

    def _get_joint_ids_for_part(self, part_name: str) -> list[str]:
        """Get the joint IDs associated with a part."""
        joint_ids = []

        # Get part info
        part_info = self.state.parts_data.get(part_name)
        if not part_info or not part_info.anchor_joint_id:
            return joint_ids

        # Add the anchor joint
        joint_ids.append(part_info.anchor_joint_id)

        # Add related joints based on part type
        # This mapping defines which joints are visually related to each part
        part_joint_mapping = {
            "left_arm_upper": ["left_shoulder", "left_elbow"],
            "left_arm_lower": ["left_elbow", "left_wrist"],
            "right_arm_upper": ["right_shoulder", "right_elbow"],
            "right_arm_lower": ["right_elbow", "right_wrist"],
            "left_leg_upper": ["left_hip", "left_knee"],
            "left_leg_lower": ["left_knee", "left_ankle"],
            "right_leg_upper": ["right_hip", "right_knee"],
            "right_leg_lower": ["right_knee", "right_ankle"],
            "torso": ["hip", "chest", "neck"],
            "head": ["neck", "head"],
            # Legacy names for backward compatibility
            "left_upper_arm": ["left_shoulder", "left_elbow"],
            "left_forearm": ["left_elbow", "left_wrist"],
            "right_upper_arm": ["right_shoulder", "right_elbow"],
            "right_forearm": ["right_elbow", "right_wrist"],
            "left_shin": ["left_knee", "left_ankle"],
            "right_shin": ["right_knee", "right_ankle"],
        }

        # Add related joints
        related_joints = part_joint_mapping.get(part_name, [])
        for joint_name in related_joints:
            # Try to find the actual joint ID from skeleton data
            if self.state.initial_skeleton_data:
                joints_dict = self.state.initial_skeleton_data.get("joints", {})

                # Look for joint by name (abstract name -> standardized ID)
                for joint_id, joint_data in joints_dict.items():
                    if joint_data.get("name") == joint_name or joint_id.startswith(joint_name):
                        if joint_id not in joint_ids:
                            joint_ids.append(joint_id)
                        break

        return joint_ids

    def _on_joint_clicked(self, joint_id: str) -> None:
        """Handle joint click events."""
        logger.debug(f"MechanismSceneManager: Joint clicked: {joint_id}")
        # You can add additional logic here, such as selecting the related part

    def _on_joint_double_clicked(self, joint_id: str) -> None:
        """Handle joint double-click events."""
        logger.debug(
            f"MechanismSceneManager: Joint double-clicked: {joint_id} - bend direction toggled"
        )
        # The skeleton item already handles the bend direction toggle
