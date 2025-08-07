"""
Enhanced Mechanism Action Handler - Physics Integration

Enhanced action handler implementing Gemini's event-driven architecture
for physics-validated mechanism design. Coordinates between UI events
and service layer through the event bus system.

Features:
- Event-driven communication with SimulationService and BlueprintService
- Physics validation workflow with proper error handling
- Manufacturing safety checks before blueprint export
- Educational feedback and visualization integration
"""

import logging
import uuid
from typing import Dict, Any, Optional

import numpy as np
from PyQt6.QtCore import QObject, QPointF, QTimer
from PyQt6.QtWidgets import QDialog, QFileDialog, QMessageBox

from ....core.event_bus import EventBus
from ....core.event_types import EventType
from ....models.mechanism import Mechanism
from ....models.physics import (
    ValidatePhysicsRequested,
    PhysicsValidationCompleted,
    LivePhysicsUpdateRequested,
    LivePhysicsUpdateCompleted,
    ValidationState,
    ValidationStatusIndicatorState,
    PhysicsValidationResult
)
from ....services.simulation_service import SimulationService
from ....services.blueprint_service import BlueprintService
from ....ui.dialogs.recommendation_dialog import MechanismRecommendationDialog
from ....utils.paths import resolve_path

from .utils import (
    convert_json_params_to_internal,
    extract_key_points_from_simulation,
    get_scene_transform_function,
)
from .visuals import visual_factory

logger = logging.getLogger(__name__)


class EnhancedMechanismActionHandler(QObject):
    """
    Enhanced action handler implementing physics-validated mechanism design.

    Follows Gemini's strategic architecture with strict separation of concerns:
    - UI layer emits action signals
    - ActionHandler publishes events to EventBus
    - Services subscribe to events and process requests
    - ActionHandler subscribes to service results and updates UI

    This ensures clean decoupling and maintainable architecture.
    """

    def __init__(self, main_window, state_manager, scene_manager, ui_panel,
                 event_bus: EventBus, parent=None):
        super().__init__(parent)

        # Core components
        self.main_window = main_window
        self.state = state_manager
        self.scene_manager = scene_manager
        self.ui_panel = ui_panel
        self.event_bus = event_bus

        # Current mechanism for physics validation
        self._current_mechanism: Optional[Mechanism] = None
        self._last_validation_result: Optional[PhysicsValidationResult] = None

        # Live physics feedback (debounced)
        self._live_feedback_timer = QTimer()
        self._live_feedback_timer.setSingleShot(True)
        self._live_feedback_timer.timeout.connect(self._request_live_physics_update)
        self._pending_parameter_changes: Dict[str, Any] = {}

        # Subscribe to physics validation events
        self._subscribe_to_events()

        logger.info("Enhanced action handler initialized with physics validation support")

    def _subscribe_to_events(self):
        """Subscribe to relevant events from services"""

        # Physics validation events
        self.event_bus.subscribe(
            EventType.PHYSICS_VALIDATION_COMPLETED,
            self._on_physics_validation_completed
        )
        self.event_bus.subscribe(
            EventType.LIVE_PHYSICS_UPDATE_COMPLETED,
            self._on_live_physics_update_completed
        )

        # Blueprint service events
        self.event_bus.subscribe(
            EventType.BLUEPRINT_GENERATION_COMPLETED,
            self._on_blueprint_generation_completed
        )
        self.event_bus.subscribe(
            EventType.BLUEPRINT_GENERATION_ERROR,
            self._on_blueprint_generation_error
        )

        # Mechanism state changes for live feedback
        self.event_bus.subscribe(
            EventType.MECHANISM_PARAMETER_CHANGED,
            self._on_parameter_changed
        )

    # Existing mechanism generation methods (unchanged)

    def handle_get_recommendations(self):
        """Handle the 'Get Mechanism' button click."""
        logger.info(f"ActionHandler: Get Mechanism button clicked")
        logger.info(f"ActionHandler: Available path data: {list(self.state.path_data.keys())}")
        logger.info(f"ActionHandler: Part enabled states: {self.state.part_enabled_state}")

        # Debug path data in detail
        for name, path in self.state.path_data.items():
            if path:
                logger.info(f"ActionHandler: Path '{name}' - type: {type(path).__name__}, empty: {path.isEmpty() if hasattr(path, 'isEmpty') else 'N/A'}")
            else:
                logger.info(f"ActionHandler: Path '{name}' - None/empty")

        enabled_parts_with_paths = {
            name: path
            for name, path in self.state.path_data.items()
            if self.state.part_enabled_state.get(name, True) and path and not path.isEmpty()
        }
        logger.info(f"ActionHandler: Enabled parts with paths: {list(enabled_parts_with_paths.keys())}")

        if not enabled_parts_with_paths:
            logger.warning("ActionHandler: No enabled parts with motion paths found")
            QMessageBox.warning(self.main_window, "Warning", "No enabled parts with motion paths.\n\nPlease draw motion paths in the Editor tab first, then come back to the Mechanism Design tab.")
            return

        target_part_name = self.state.selected_part_name
        logger.info(f"ActionHandler: Selected part: {target_part_name}")

        if not target_part_name or target_part_name not in enabled_parts_with_paths:
            logger.warning(f"ActionHandler: Invalid part selection. Selected: {target_part_name}, Available: {list(enabled_parts_with_paths.keys())}")
            QMessageBox.warning(
                self.main_window,
                "Warning",
                "Please select a part with a motion path from the list.",
            )
            return

        target_path = enabled_parts_with_paths[target_part_name]

        generated_paths_file = resolve_path(
            "src/automataii/domain/kinematics/generated_mechanism_paths.json"
        )
        dialog = MechanismRecommendationDialog(
            target_path, generated_paths_file, parent=self.main_window
        )
        dialog.setWindowTitle(f"Mechanism Recommendations for {target_part_name}")

        dialog.mechanism_preview_selected.connect(self.scene_manager.preview_mechanism)

        logger.info("ActionHandler: Showing mechanism recommendation dialog")
        dialog_result = dialog.exec()
        logger.info(f"ActionHandler: Dialog result: {dialog_result} (Accepted={QDialog.DialogCode.Accepted})")

        if dialog_result == QDialog.DialogCode.Accepted:
            selected_mechanism = dialog.selected_mechanism_data
            logger.info(f"ActionHandler: Dialog accepted, selected mechanism: {selected_mechanism is not None}")
            if selected_mechanism:
                logger.info(f"ActionHandler: Selected mechanism type: {selected_mechanism.get('type', 'unknown')}")
                self._generate_mechanism_from_candidate(selected_mechanism)
            else:
                logger.warning("ActionHandler: Dialog accepted but no mechanism selected")
        else:
            logger.info("ActionHandler: Dialog was cancelled or rejected")

        self.scene_manager.clear_preview()

    def _generate_mechanism_from_candidate(self, candidate_data):
        """Generate and add a new mechanism from recommendation."""
        part_name = self.state.selected_part_name
        self.state.clear_mechanisms_for_part(part_name)

        mechanism_id = str(uuid.uuid4())[:8]
        mechanism_type_value = candidate_data.get("type", "Unknown")
        raw_params = candidate_data.get("parameters", {})
        params = convert_json_params_to_internal(mechanism_type_value, raw_params)

        mechanism_type_mapping = {
            "4-Bar Linkage": "4_bar_linkage",
            "4-bar Coupler": "4_bar_linkage",
            "Cam & Follower": "cam",
            "Cam-Follower": "cam",
            "Gears (Simple Pair)": "gear",
            "Gear Contact": "gear",
            "Simple Gear": "gear",
            "Planetary Gear": "planetary_gear",
        }
        internal_type = mechanism_type_mapping.get(mechanism_type_value, "4_bar_linkage")

        layer_data = {
            "id": mechanism_id,
            "type": internal_type,
            "part_name": part_name,
            "params": params,
            "generated_path": self.state.path_data.get(part_name),
            "transform_params": candidate_data.get("transform_params"),
            "full_simulation_data": candidate_data.get("full_simulation_data", {}),
            # Preserve EXACT dialog alignment data for visual consistency
            "user_path_aligned_np": candidate_data.get("user_path_aligned_np"),
            "mech_path_aligned_np": candidate_data.get("mech_path_aligned_np"),
            "original_json_type": candidate_data.get("original_json_type"),
            "visualization_params": candidate_data.get("visualization_params"),
        }

        key_points = extract_key_points_from_simulation(
            layer_data["full_simulation_data"], internal_type
        )
        layer_data["key_points"] = key_points

        self._adjust_mechanism_to_target_joint(layer_data)

        logger.info(f"Adding mechanism {mechanism_id} for part {part_name} with data: {layer_data.keys()}")
        self.state.add_mechanism(mechanism_id, layer_data)
        logger.info(f"Successfully added mechanism {mechanism_id} to state. Total mechanisms: {len(self.state.mechanism_layers)}")

        # Reset physics validation when mechanism changes
        self.ui_panel.reset_validation_state()
        self._current_mechanism = None
        self._last_validation_result = None

        logger.info(f"Generated mechanism {mechanism_id}, physics validation reset")

    def _adjust_mechanism_to_target_joint(self, layer_data: dict):
        """Adjust mechanism position to align with target skeleton joint."""
        part_name = layer_data.get("part_name")
        part_info = self.state.parts_data.get(part_name)
        ik_manager = self.main_window.ik_manager

        if not all([part_name, part_info, ik_manager, self.state.initial_skeleton_data]):
            return

        target_joint_id = ik_manager.get_end_effector_for_part(part_name)
        if not target_joint_id:
            return

        joints_dict = self.state.initial_skeleton_data.get("joints", {})
        joint_data = joints_dict.get(target_joint_id)
        if not joint_data:
            return

        target_joint_pos = QPointF(*joint_data.get("position", [0, 0]))

        # Calculate mechanism's initial output position in scene coordinates
        initial_output_pos = visual_factory.get_initial_output(layer_data)
        if not initial_output_pos:
            return

        # Calculate offset needed to align mechanism
        offset = target_joint_pos - initial_output_pos

        if offset.manhattanLength() < 1:  # No significant offset
            return

        # Apply offset to mechanism's key points
        if "key_points" in layer_data and layer_data["key_points"]:
            to_scene = get_scene_transform_function(layer_data)

            # Find inverse of scene transform
            p1 = to_scene([0, 0])
            p2 = to_scene([1, 1])
            dx = p2.x() - p1.x()
            dy = p2.y() - p1.y()

            # Assuming uniform scaling for simplicity
            scale = (dx + dy) / 2.0
            if abs(scale) < 1e-6:
                return

            offset_in_mech_space = np.array([offset.x() / scale, offset.y() / scale])

            for key, point in layer_data["key_points"].items():
                if point:
                    layer_data["key_points"][key] = (
                        np.array(point) + offset_in_mech_space
                    ).tolist()

        # Also adjust transform parameters' center
        if "transform_params" in layer_data and "center" in layer_data["transform_params"]:
            layer_data["transform_params"]["center"] = (
                np.array(layer_data["transform_params"]["center"]) + offset_in_mech_space
            ).tolist()

        logger.info(f"Adjusted mechanism '{layer_data['id']}' by offset {offset}")

    # NEW: Physics validation methods

    def handle_validate_physics(self):
        """
        Handle physics validation request from UI.

        Implements Gemini's event-driven architecture:
        1. Convert current mechanism state to centralized Mechanism model
        2. Publish ValidatePhysicsRequested event
        3. SimulationService will handle the request and publish results
        4. This handler subscribes to results and updates UI
        """
        try:
            # Update UI to show validation in progress
            self.ui_panel.set_validation_in_progress("Converting mechanism data...")

            # Convert current state to centralized Mechanism model
            mechanism = self._create_mechanism_from_current_state()
            if not mechanism:
                self.ui_panel.set_validation_failure("Invalid mechanism data")
                return

            self._current_mechanism = mechanism

            # Update progress
            self.ui_panel.set_validation_in_progress("Running physics simulation...")

            # Publish validation request event
            event_data = ValidatePhysicsRequested(
                mechanism_id=mechanism.id,
                mechanism_data=mechanism.to_dict(),
                validation_level="full",
                requester="ui"
            )

            self.event_bus.publish(EventType.PHYSICS_VALIDATION_REQUESTED, event_data.__dict__)

            logger.info(f"Physics validation requested for mechanism {mechanism.id}")

        except Exception as e:
            error_msg = f"Failed to start physics validation: {str(e)}"
            logger.error(error_msg)
            self.ui_panel.set_validation_failure("Validation startup failed")
            QMessageBox.critical(self.main_window, "Validation Error", error_msg)

    def _create_mechanism_from_current_state(self) -> Optional[Mechanism]:
        """
        Convert current UI state to centralized Mechanism model.

        This bridges the gap between the existing state management
        and the new centralized architecture.
        """
        try:
            if not self.state.mechanism_layers:
                logger.warning("No mechanisms available for physics validation")
                return None

            # For now, take the first mechanism (could be enhanced to handle multiple)
            first_mechanism_id = next(iter(self.state.mechanism_layers.keys()))
            layer_data = self.state.mechanism_layers[first_mechanism_id]

            # Extract mechanism type and parameters
            mechanism_type = layer_data.get("type", "4_bar_linkage")
            params = layer_data.get("params", {})
            part_name = layer_data.get("part_name", "unknown")
            key_points = layer_data.get("key_points", {})

            # Create mechanism based on type
            if mechanism_type == "4_bar_linkage":
                # Extract 4-bar linkage parameters
                l1 = params.get("l1", 100.0)  # Ground link
                l2 = params.get("l2", 80.0)   # Driver link
                l3 = params.get("l3", 120.0)  # Coupler link
                l4 = params.get("l4", 90.0)   # Rocker link

                # Get ground pivot positions from key points
                pivot1_data = key_points.get("ground_pivot_1", [0, 0])
                pivot2_data = key_points.get("ground_pivot_2", [l1, 0])

                from ....models.mechanism import Point2D
                ground_pivot_1 = Point2D(pivot1_data[0], pivot1_data[1])
                ground_pivot_2 = Point2D(pivot2_data[0], pivot2_data[1])

                # Create 4-bar linkage mechanism
                mechanism = Mechanism.create_four_bar_linkage(
                    name=f"Mechanism for {part_name}",
                    ground_length=l1,
                    driver_length=l2,
                    coupler_length=l3,
                    rocker_length=l4,
                    ground_pivot_1=ground_pivot_1,
                    ground_pivot_2=ground_pivot_2
                )

                logger.info(f"Created 4-bar linkage mechanism: l1={l1}, l2={l2}, l3={l3}, l4={l4}")
                return mechanism

            else:
                # For other mechanism types, create a generic mechanism
                # This would be expanded to handle cams, gears, etc.
                logger.warning(f"Mechanism type {mechanism_type} not yet supported for physics validation")
                return None

        except Exception as e:
            logger.error(f"Failed to create mechanism from current state: {e}")
            return None

    def _on_physics_validation_completed(self, event_data: Dict[str, Any]):
        """Handle physics validation completion event from SimulationService"""
        try:
            # Extract validation result from event data
            result_data = event_data.get('result')
            if not result_data:
                logger.error("Physics validation completed but no result data received")
                return

            # Create validation result object
            if isinstance(result_data, dict):
                result = PhysicsValidationResult(**result_data)
            else:
                result = result_data

            self._last_validation_result = result

            # Update UI based on validation results
            if result.validation_state == ValidationState.SUCCESS:
                summary = f"Safety factor: {result.min_safety_factor:.1f}"
                self.ui_panel.set_validation_success(summary)

                # Add educational insights to UI (could be displayed in a side panel)
                if result.educational_insights:
                    logger.info(f"Educational insights: {result.educational_insights}")

            elif result.validation_state == ValidationState.WARNING:
                warning_count = len(result.get_failures_by_severity("warning"))
                summary = f"{warning_count} warnings"

                state = ValidationStatusIndicatorState(
                    validation_state=ValidationState.WARNING,
                    message=f"Validated with warnings ({warning_count})",
                    color="#FFAA00",
                    tooltip="Physics validation passed but has warnings - review before export"
                )
                self.ui_panel.set_physics_validation_state(state)

            elif result.validation_state == ValidationState.FAILURE:
                error_count = len(result.get_failures_by_severity("error"))
                summary = f"{error_count} errors"
                self.ui_panel.set_validation_failure(summary)

                # Show detailed error information
                self._show_validation_errors(result)

            # Update physics visualization in 2D scene
            self._update_physics_visualization(result)

            logger.info(f"Physics validation completed: {result.validation_state.value}")

        except Exception as e:
            logger.error(f"Error handling physics validation completion: {e}")
            self.ui_panel.set_validation_failure("Result processing failed")

    def _show_validation_errors(self, result: PhysicsValidationResult):
        """Show detailed validation errors to user"""
        errors = result.get_failures_by_severity("error")
        if not errors:
            return

        # Create error message
        error_messages = []
        for error in errors[:5]:  # Show first 5 errors
            error_messages.append(f"• {error.message}")

        if len(errors) > 5:
            error_messages.append(f"... and {len(errors) - 5} more errors")

        full_message = (
            f"Physics validation failed with {len(errors)} errors:\n\n" +
            "\n".join(error_messages) +
            "\n\nPlease fix these issues before exporting the blueprint."
        )

        QMessageBox.critical(
            self.main_window,
            "Physics Validation Failed",
            full_message
        )

    def _update_physics_visualization(self, result: PhysicsValidationResult):
        """Update physics visualization in 2D scene"""
        try:
            # Get current visualization settings
            viz_settings = self.ui_panel.get_physics_visualization_settings()

            # Update scene manager with physics data
            if hasattr(self.scene_manager, 'update_physics_visualization'):
                self.scene_manager.update_physics_visualization(result, viz_settings)
            else:
                logger.warning("Scene manager does not support physics visualization yet")

        except Exception as e:
            logger.error(f"Failed to update physics visualization: {e}")

    def _on_live_physics_update_completed(self, event_data: Dict[str, Any]):
        """Handle live physics update completion"""
        try:
            update_data = event_data.get('update')
            if not update_data:
                return

            # Update UI with live feedback (subtle visual cues)
            # This could highlight problematic components in real-time
            logger.debug(f"Live physics update: {update_data.get('overall_status', 'unknown')}")

        except Exception as e:
            logger.error(f"Error handling live physics update: {e}")

    def _on_parameter_changed(self, event_data: Dict[str, Any]):
        """Handle mechanism parameter changes for live feedback"""
        if not self.ui_panel.is_live_physics_feedback_enabled():
            return

        # Debounce parameter changes
        param_name = event_data.get('param_name')
        param_value = event_data.get('param_value')

        if param_name and param_value is not None:
            self._pending_parameter_changes[param_name] = param_value

            # Restart debounce timer
            self._live_feedback_timer.start(300)  # 300ms debounce

    def _request_live_physics_update(self):
        """Request live physics update with debounced parameters"""
        if not self._current_mechanism or not self._pending_parameter_changes:
            return

        try:
            event_data = LivePhysicsUpdateRequested(
                mechanism_id=self._current_mechanism.id,
                changed_parameters=self._pending_parameter_changes.copy()
            )

            self.event_bus.publish(EventType.LIVE_PHYSICS_UPDATE_REQUESTED, event_data.__dict__)

            # Clear pending changes
            self._pending_parameter_changes.clear()

        except Exception as e:
            logger.error(f"Failed to request live physics update: {e}")

    def handle_physics_visualization_changed(self, settings):
        """Handle physics visualization settings changes"""
        try:
            # Update force visualization in scene manager
            if hasattr(self.scene_manager, 'toggle_force_visualization'):
                self.scene_manager.toggle_force_visualization(settings.show_force_vectors)

            # Update force scale if changed
            if hasattr(self.scene_manager, 'set_force_scale') and hasattr(settings, 'force_scale'):
                self.scene_manager.set_force_scale(settings.force_scale)

            # Update physics visualization in 2D scene immediately
            if self._last_validation_result:
                self._update_physics_visualization(self._last_validation_result)

            logger.info(f"Physics visualization settings updated: forces={settings.show_force_vectors}, "
                       f"constraints={settings.show_constraint_violations}, paths={settings.show_motion_paths}, "
                       f"force_scale={getattr(settings, 'force_scale', 1.0)}")

        except Exception as e:
            logger.error(f"Failed to handle physics visualization change: {e}")

    def handle_live_physics_feedback_toggled(self, enabled: bool):
        """Handle live physics feedback toggle"""
        try:
            if enabled:
                logger.info("Live physics feedback enabled - will provide real-time validation during parameter changes")

                # If we have a current mechanism, enable live feedback
                if self._current_mechanism:
                    # Start monitoring parameter changes for live feedback
                    pass  # The parameter change monitoring is already set up in _on_parameter_changed
                else:
                    logger.warning("Live physics feedback enabled but no mechanism available")

            else:
                logger.info("Live physics feedback disabled")

                # Stop any pending live feedback updates
                self._live_feedback_timer.stop()
                self._pending_parameter_changes.clear()

        except Exception as e:
            logger.error(f"Failed to handle live physics feedback toggle: {e}")

    # Enhanced blueprint export with physics validation

    def handle_export_blueprint(self):
        """
        Handle blueprint export with mandatory physics validation.

        Implements Gemini's manufacturing safety strategy:
        - Requires successful physics validation before export
        - Integrates validation results into blueprint
        - Uses enhanced BlueprintService for multi-layer export
        """

        # Check if physics validation is required and completed
        if not self._last_validation_result:
            QMessageBox.warning(
                self.main_window,
                "Physics Validation Required",
                "Physics validation is required before exporting blueprints.\n\n"
                "Please run physics validation first to ensure manufacturing safety."
            )
            return

        if not self._last_validation_result.can_export_blueprint:
            error_count = len(self._last_validation_result.get_failures_by_severity("error"))
            QMessageBox.critical(
                self.main_window,
                "Cannot Export Blueprint",
                f"Cannot export blueprint due to {error_count} physics validation errors.\n\n"
                "Please fix all errors before attempting to export."
            )
            return

        # Proceed with blueprint export
        if not self.state.mechanism_layers:
            QMessageBox.warning(self.main_window, "Warning", "No mechanisms to export.")
            return

        save_path, _ = QFileDialog.getSaveFileName(
            self.main_window, "Save Manufacturing Blueprint", "", "PDF Files (*.pdf);;SVG Files (*.svg)"
        )

        if not save_path:
            return

        try:
            # Use enhanced blueprint service if available
            if hasattr(self.main_window, 'blueprint_service'):
                self._export_with_enhanced_service(save_path)
            else:
                # Fallback to existing export method
                self._export_with_legacy_method(save_path)

        except Exception as e:
            logger.error(f"Failed to export blueprint: {e}")
            QMessageBox.critical(self.main_window, "Export Error", f"Failed to export blueprint: {e}")

    def _export_with_enhanced_service(self, save_path: str):
        """Export using enhanced BlueprintService with physics integration"""

        # Create export request event
        event_data = {
            'mechanism': self._current_mechanism.to_dict() if self._current_mechanism else {},
            'validation_result': self._last_validation_result.dict() if self._last_validation_result else {},
            'output_path': save_path,
            'paper_size': 'letter',
            'quality': 'manufacturing'
        }

        self.event_bus.publish(EventType.BLUEPRINT_EXPORT_REQUESTED, event_data)

        logger.info(f"Enhanced blueprint export requested to {save_path}")

    def _export_with_legacy_method(self, save_path: str):
        """Fallback to existing blueprint export method"""
        from ....ui.exporters.blueprint_exporter import BlueprintExporter

        exporter = BlueprintExporter(
            self.state.parts_data,
            self.state.mechanism_layers,
            self.state.initial_skeleton_data
        )
        exporter.export(save_path)

        # Add physics validation summary to export
        if self._last_validation_result:
            logger.info(f"Blueprint exported with physics validation summary: "
                       f"Safety factor: {self._last_validation_result.min_safety_factor:.1f}")

        QMessageBox.information(
            self.main_window,
            "Export Successful",
            f"Physics-validated blueprint exported to {save_path}"
        )

    def _on_blueprint_generation_completed(self, event_data: Dict[str, Any]):
        """Handle blueprint generation completion"""
        output_path = event_data.get('output_path', 'unknown location')
        QMessageBox.information(
            self.main_window,
            "Export Successful",
            f"Manufacturing blueprint exported successfully to:\n{output_path}"
        )
        logger.info(f"Blueprint export completed: {output_path}")

    def _on_blueprint_generation_error(self, event_data: Dict[str, Any]):
        """Handle blueprint generation errors"""
        error_message = event_data.get('error_message', 'Unknown error')
        QMessageBox.critical(
            self.main_window,
            "Export Failed",
            f"Blueprint export failed:\n{error_message}"
        )
        logger.error(f"Blueprint export failed: {error_message}")

    # Public interface methods

    def get_current_mechanism(self) -> Optional[Mechanism]:
        """Get current mechanism model for physics validation"""
        return self._current_mechanism

    def get_last_validation_result(self) -> Optional[PhysicsValidationResult]:
        """Get last physics validation result"""
        return self._last_validation_result

    def reset_physics_validation(self):
        """Reset physics validation state (called when mechanism changes)"""
        self._current_mechanism = None
        self._last_validation_result = None
        self.ui_panel.reset_validation_state()
        logger.info("Physics validation state reset")

    def cleanup(self):
        """Clean up resources and event subscriptions"""
        self._live_feedback_timer.stop()
        # Event bus subscriptions are automatically cleaned up
        logger.info("Enhanced action handler cleaned up")