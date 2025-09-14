# ParametricEditingManager
# Lines: 1156
# Public API: toggle_parametric_mode, _on_parametric_mechanism_update, _on_parametric_visual_refresh, cleanup
# Deps In (Afferent): 1 [MechanismDesignTab]
# Deps Out (Efferent): 8 [PyQt6, numpy, math, parametric_editor, visualization, QTimer, QMessageBox, Optional]
# Coupling: Medium (rationale: depends on parent tab resources but provides isolated parametric editing)
# Cohesion: Feature (single responsibility: parametric editing system for mechanisms)
# Owner: Alan Synn, Reviewers: TBD
# Last Updated: 2025-08-26

"""
Parametric Editing Manager for Mechanism Design Tab

This module extracts the parametric editing functionality from MechanismDesignTab
to improve code organization and maintainability. It handles all parametric editing
operations including handle creation, mechanism parameter updates, and visual feedback.

The class uses delegation pattern to maintain access to parent tab resources while
providing a clean separation of concerns.
"""

import math
from typing import Any, Dict, Optional
import numpy as np
from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtWidgets import QMessageBox


class ParametricEditingManager:
    """
    Manages parametric editing functionality for mechanism design.
    
    This class extracts the parametric editing system from MechanismDesignTab
    to provide better modularity and maintainability. It handles interactive
    editing of mechanism parameters through visual handles.
    """
    
    def __init__(self, parent_tab):
        """
        Initialize the parametric editing manager.
        
        Args:
            parent_tab: Reference to MechanismDesignTab instance for accessing
                       shared resources like mechanism_layers, mechanism_scene, etc.
        """
        self.parent_tab = parent_tab
        self.parametric_mode_enabled = False
        
        # Parametric system will be initialized by parent tab after UI setup
        # This is due to initialization order requirements
    
    def _initialize_parametric_system(self):
        """
        Initialize the parametric editing system.
        
        ULTRATHINK: Enhanced parametric system initialization.
        """
        # Check if parametric functionality is available
        try:
            import sys
            parent_module = sys.modules[self.parent_tab.__class__.__module__]
            PARAMETRIC_AVAILABLE = getattr(parent_module, 'PARAMETRIC_AVAILABLE', False)
            if not PARAMETRIC_AVAILABLE:
                return
        except Exception as e:
            return
            
        try:
            # Import parametric editor classes from parent module
            ParametricEditor = getattr(parent_module, 'ParametricEditor', None)
            if not ParametricEditor:
                return
            
            # Check mechanism scene availability
            has_scene = hasattr(self.parent_tab, 'mechanism_scene')
            scene_exists = has_scene and self.parent_tab.mechanism_scene is not None
            
            # Initialize parametric editor with the mechanism scene
            if scene_exists:
                self.parent_tab.parametric_editor = ParametricEditor(self.parent_tab.mechanism_scene)
                
                # Connect parametric editor signals to parent tab's slot methods
                if hasattr(self.parent_tab.parametric_editor, 'mechanism_updated'):
                    self.parent_tab.parametric_editor.mechanism_updated.connect(
                        self.parent_tab._on_parametric_mechanism_update
                    )
                
                if hasattr(self.parent_tab.parametric_editor, 'visual_refresh_requested'):
                    self.parent_tab.parametric_editor.visual_refresh_requested.connect(
                        self.parent_tab._on_parametric_visual_refresh
                    )
                    
        except Exception as e:
            self.parent_tab.parametric_editor = None

    def toggle_parametric_mode(self, enabled: Optional[bool] = None):
        """
        Toggle parametric editing mode on/off.

        Args:
            enabled: Explicit enable/disable, or None to toggle current state
        """
        print(f"🔧 ParametricEditingManager: toggle_parametric_mode called with enabled={enabled}")
        
        # Check if parametric functionality is available
        # Get PARAMETRIC_AVAILABLE from parent tab's module
        try:
            import sys
            parent_module = sys.modules[self.parent_tab.__class__.__module__]
            PARAMETRIC_AVAILABLE = getattr(parent_module, 'PARAMETRIC_AVAILABLE', False)
            if not PARAMETRIC_AVAILABLE:
                print("❌ Parametric functionality not available")
                return
        except Exception as e:
            print(f"❌ Error checking parametric availability: {e}")
            return

        print(f"🔧 parametric_editor exists: {self.parent_tab.parametric_editor is not None}")
        if not self.parent_tab.parametric_editor:
            # Attempt lazy initialization if not already done
            try:
                self._initialize_parametric_system()
            except Exception as e:
                print(f"❌ Lazy init failed: {e}")
            if not self.parent_tab.parametric_editor:
                print("❌ No parametric editor available after init")
                # User-friendly message
                try:
                    from PyQt6.QtWidgets import QMessageBox
                    QMessageBox.information(self.parent_tab, "Parametric Edit", "Parametric system not available.")
                except Exception:
                    pass
                return

        if enabled is None:
            enabled = not self.parametric_mode_enabled

        print(f"🔧 Current parametric_mode_enabled: {self.parametric_mode_enabled}")
        print(f"🔧 Setting parametric mode to: {enabled}")
        print(f"🔧 Mechanism layers count: {len(self.parent_tab.mechanism_layers)}")

        # Check if we have mechanisms to edit
        if enabled and not self.parent_tab.mechanism_layers:
            print("ℹ️  No mechanisms available for parametric editing")
            # Show user-friendly message
            if hasattr(self.parent_tab, 'main_window'):
                QMessageBox.information(
                    self.parent_tab.main_window,
                    "Parametric Edit",
                    "Please generate mechanisms first using 'Get Mechanism' button.\n\n"
                    "Parametric editing allows you to interactively adjust mechanism parameters by dragging anchor points."
                )
            return

        # CRITICAL: Handle animation conflicts properly
        animation_was_running = False
        if enabled:
            # Enabling parametric mode - stop any running animation
            animation_was_running = self.parent_tab._is_animation_running()
            if animation_was_running:
                self.parent_tab._on_stop_animation()

            # Store animation state for potential restoration
            if not hasattr(self, '_animation_state_before_parametric'):
                self._animation_state_before_parametric = animation_was_running
        else:
            # Disabling parametric mode - check if we should restore animation
            should_restore_animation = getattr(self, '_animation_state_before_parametric', False)
            if hasattr(self, '_animation_state_before_parametric'):
                delattr(self, '_animation_state_before_parametric')

        print(f"🔧 Setting parametric_mode_enabled to: {enabled}")
        self.parametric_mode_enabled = enabled

        if enabled:
            print("🔧 Enabling parametric mode...")
            self._enable_parametric_mode()
        else:
            print("🔧 Disabling parametric mode...")
            self._disable_parametric_mode()

            # Restore animation if it was running before parametric mode
            if 'should_restore_animation' in locals() and should_restore_animation:
                # Small delay to ensure visual state is fully restored before starting animation
                QTimer.singleShot(100, self.parent_tab._on_start_animation)
        
        print("🔧 Updating UI state...")
        # Update UI state
        self.parent_tab.ui_state_manager.set_parametric_mode(enabled)
        self.parent_tab._update_all_ui_states()
        print("✅ toggle_parametric_mode completed")

    def _enable_parametric_mode(self):
        """Enable parametric editing mode - show interactive handles.

        ULTRATHINK: Enhanced to use new ParametricEditor system.
        """
        if not self.parent_tab.parametric_editor:
            return

        try:
            # Mark parametric mode on all mechanisms (visuals may switch mapping behavior)
            for mechanism_id in self.parent_tab.mechanism_layers.keys():
                self.parent_tab.mechanism_layers[mechanism_id]['parametric_mode'] = True

            # CRITICAL FIX: Clear all mechanism traces when entering parametric mode
            for mechanism_id in list(self.parent_tab.mechanism_layers.keys()):
                self.parent_tab._clear_mechanism_trace(mechanism_id)

            # Create editors for all existing mechanisms
            for mechanism_id, layer_data in self.parent_tab.mechanism_layers.items():
                part_name = layer_data.get("part_name")
                mechanism_type = layer_data.get("type")

                try:
                    if "params" not in layer_data:
                        layer_data["params"] = {}

                    # CRITICAL FIX: Ensure all required parameters are present for each mechanism type
                    self._ensure_mechanism_parameters(layer_data, mechanism_type)

                    # Create appropriate editor for mechanism type
                    editor = self.parent_tab.parametric_editor.create_editor(mechanism_id, layer_data)
                    if editor:
                        pass
                except Exception as e:
                    import traceback
                    print(f"Error creating parametric editor for {mechanism_id}: {e}")
                    print(traceback.format_exc())

            # Enable editing mode
            self.parent_tab.parametric_editor.enable_editing()

            # Set active editor based on currently selected part in the UI
            self._set_active_editor_from_selection()

            # Disable animation controls in parametric mode
            self._disable_animation_controls_for_parametric()

            # Disable mechanism visual interaction to allow handle interaction
            self._disable_mechanism_visual_interaction()

        except Exception as e:
            import traceback
            print(f"Error enabling parametric mode: {e}")
            print(traceback.format_exc())

    def _ensure_mechanism_parameters(self, layer_data: Dict[str, Any], mechanism_type: str):
        """
        Ensure all required parameters are present for each mechanism type.
        
        Args:
            layer_data: Mechanism layer data dictionary
            mechanism_type: Type of mechanism (cam, 4_bar_linkage, gear, etc.)
        """
        params = layer_data["params"]
        
        if mechanism_type == "cam":
            # CAM: Ensure center_x and center_y are in params
            cam_position = layer_data.get("cam_position")
            if cam_position and len(cam_position) >= 2:
                params["center_x"] = cam_position[0]
                params["center_y"] = cam_position[1]
            else:
                # Fallback to default position if cam_position not set
                params["center_x"] = 400
                params["center_y"] = 300

        elif mechanism_type == "4_bar_linkage":
            self._setup_4bar_parameters(layer_data, params)

        elif mechanism_type in ["gear", "simple_gear"]:
            self._setup_gear_parameters(layer_data, params)

        elif mechanism_type == "planetary_gear":
            self._setup_planetary_gear_parameters(layer_data, params)

    def _setup_4bar_parameters(self, layer_data: Dict[str, Any], params: Dict[str, Any]):
        """Setup parameters for 4-bar linkage mechanism."""
        # 4-BAR: Extract anchor positions from simulation data and transform to scene coords
        full_sim_data = layer_data.get("full_simulation_data", {})

        if "joint_positions" in full_sim_data:
            joint_positions = full_sim_data["joint_positions"]
            if (self._has_valid_joint_positions(joint_positions)):
                self._extract_4bar_positions_from_simulation(layer_data, params, joint_positions)
            else:
                self._set_default_4bar_parameters(params)
        else:
            self._set_default_4bar_parameters(params)

    def _has_valid_joint_positions(self, joint_positions: Dict[str, Any]) -> bool:
        """Check if joint positions data is valid."""
        return ("p1_positions" in joint_positions and len(joint_positions["p1_positions"]) > 0 and
                "p2_positions" in joint_positions and len(joint_positions["p2_positions"]) > 0)

    def _extract_4bar_positions_from_simulation(self, layer_data: Dict[str, Any], 
                                              params: Dict[str, Any], 
                                              joint_positions: Dict[str, Any]):
        """Extract 4-bar linkage positions from simulation data."""
        # Use first frame positions as anchor positions
        p1 = joint_positions["p1_positions"][0]
        p2 = joint_positions["p2_positions"][0]
        p3 = joint_positions["p3_positions"][0] if "p3_positions" in joint_positions else None
        p4 = joint_positions["p4_positions"][0] if "p4_positions" in joint_positions else None

        # Transform ALL positions to scene coordinates using the same function as visuals
        to_scene = self.parent_tab._get_scene_transform_function(layer_data)
        if to_scene:
            p1_scene = to_scene(np.array(p1))
            p2_scene = to_scene(np.array(p2))

            # Convert QPointF to x,y values
            params["anchor1_x"], params["anchor1_y"] = self._extract_coordinates(p1_scene)
            params["anchor2_x"], params["anchor2_y"] = self._extract_coordinates(p2_scene)

            # Transform p3 and p4 for angles and coupler position
            if p3 is not None:
                p3_scene = to_scene(np.array(p3))
                p3_x, p3_y = self._extract_coordinates(p3_scene)

                # Calculate crank angle in scene space
                dx = p3_x - params["anchor1_x"]
                dy = p3_y - params["anchor1_y"]
                params["crank_angle"] = math.degrees(math.atan2(dy, dx))
                params["crank_x"] = p3_x  # Store crank position
                params["crank_y"] = p3_y

            if p4 is not None:
                p4_scene = to_scene(np.array(p4))
                p4_x, p4_y = self._extract_coordinates(p4_scene)

                # Calculate rocker angle in scene space
                dx = p4_x - params["anchor2_x"]
                dy = p4_y - params["anchor2_y"]
                params["rocker_angle"] = math.degrees(math.atan2(dy, dx))
                params["rocker_x"] = p4_x  # Store rocker position
                params["rocker_y"] = p4_y

                # Calculate coupler position
                if p3 is not None:
                    self._calculate_coupler_position(layer_data, params, p3_x, p3_y, p4_x, p4_y)

        else:
            # No transformation available, use raw values
            params["anchor1_x"] = p1[0] if isinstance(p1, (list, tuple)) else p1
            params["anchor1_y"] = p1[1] if isinstance(p1, (list, tuple)) else 0
            params["anchor2_x"] = p2[0] if isinstance(p2, (list, tuple)) else p2
            params["anchor2_y"] = p2[1] if isinstance(p2, (list, tuple)) else 0
            params["crank_angle"] = 0
            params["rocker_angle"] = 45
            params["coupler_x"] = 350
            params["coupler_y"] = 250

    def _extract_coordinates(self, point):
        """Extract x,y coordinates from point object."""
        if hasattr(point, 'x'):
            return point.x(), point.y()
        else:
            x = float(point[0]) if isinstance(point, np.ndarray) else point[0]
            y = float(point[1]) if isinstance(point, np.ndarray) else point[1]
            return x, y

    def _calculate_coupler_position(self, layer_data: Dict[str, Any], params: Dict[str, Any],
                                  p3_x: float, p3_y: float, p4_x: float, p4_y: float):
        """Calculate coupler position for 4-bar linkage."""
        # Get coupler offset from original params
        coupler_point_x = params.get("coupler_point_x", 0.0)
        coupler_point_y = params.get("coupler_point_y", 0.0)

        # Calculate coupler position in scene space (like in visuals)
        coupler_vec_x = p4_x - p3_x
        coupler_vec_y = p4_y - p3_y
        coupler_length = math.sqrt(coupler_vec_x**2 + coupler_vec_y**2)

        if coupler_length > 0:
            coupler_unit_x = coupler_vec_x / coupler_length
            coupler_unit_y = coupler_vec_y / coupler_length
            coupler_normal_x = -coupler_unit_y
            coupler_normal_y = coupler_unit_x

            # Transform coupler offset to scene scale
            scale = layer_data.get("transform_params", {}).get("scale", 1.0)
            scaled_offset_x = coupler_point_x * scale
            scaled_offset_y = coupler_point_y * scale

            params["coupler_x"] = p3_x + scaled_offset_x * coupler_unit_x + scaled_offset_y * coupler_normal_x
            params["coupler_y"] = p3_y + scaled_offset_x * coupler_unit_y + scaled_offset_y * coupler_normal_y
        else:
            params["coupler_x"] = p3_x
            params["coupler_y"] = p3_y

    def _set_default_4bar_parameters(self, params: Dict[str, Any]):
        """Set default parameters for 4-bar linkage."""
        l1 = params.get("l1", 100)
        params["anchor1_x"] = 400
        params["anchor1_y"] = 300
        params["anchor2_x"] = 400 + l1
        params["anchor2_y"] = 300
        params["crank_angle"] = 0
        params["rocker_angle"] = 45
        params["coupler_x"] = 450
        params["coupler_y"] = 250

    def _setup_gear_parameters(self, layer_data: Dict[str, Any], params: Dict[str, Any]):
        """Setup parameters for gear mechanism."""
        # GEAR: Convert r1, r2 to gear parameters with scene positions
        full_sim_data = layer_data.get("full_simulation_data", {})

        # Map radius parameters
        if "r1" in params:
            params["gear1_radius"] = params["r1"]
        if "r2" in params:
            params["gear2_radius"] = params["r2"]

        # Try to get positions from simulation data
        to_scene = self.parent_tab._get_scene_transform_function(layer_data)

        if "gear_data" in full_sim_data and to_scene:
            self._extract_gear_positions_from_simulation(params, full_sim_data, to_scene)
        else:
            self._set_default_gear_positions(params)

    def _extract_gear_positions_from_simulation(self, params: Dict[str, Any], 
                                              full_sim_data: Dict[str, Any], 
                                              to_scene):
        """Extract gear positions from simulation data."""
        gear_data = full_sim_data["gear_data"]
        
        # Get first frame gear centers
        if "gear1_centers" in gear_data and len(gear_data["gear1_centers"]) > 0:
            g1_center = gear_data["gear1_centers"][0]
            g1_scene = to_scene(np.array(g1_center))
            params["gear1_x"], params["gear1_y"] = self._extract_coordinates(g1_scene)

        if "gear2_centers" in gear_data and len(gear_data["gear2_centers"]) > 0:
            g2_center = gear_data["gear2_centers"][0]
            g2_scene = to_scene(np.array(g2_center))
            params["gear2_x"], params["gear2_y"] = self._extract_coordinates(g2_scene)

    def _set_default_gear_positions(self, params: Dict[str, Any]):
        """Set default positions for gear mechanism."""
        if "gear1_x" not in params:
            params["gear1_x"] = 400
        if "gear1_y" not in params:
            params["gear1_y"] = 300
        if "gear2_x" not in params:
            # Position gear2 to mesh with gear1
            r1 = params.get("gear1_radius", params.get("r1", 40))
            r2 = params.get("gear2_radius", params.get("r2", 60))
            params["gear2_x"] = params["gear1_x"] + r1 + r2 + 2  # Small clearance
        if "gear2_y" not in params:
            params["gear2_y"] = params["gear1_y"]

    def _setup_planetary_gear_parameters(self, layer_data: Dict[str, Any], params: Dict[str, Any]):
        """Setup parameters for planetary gear mechanism."""
        # PLANETARY GEAR: Map to GearEditor parameters with scene coordinates
        full_sim_data = layer_data.get("full_simulation_data", {})

        # Map radius parameters
        if "r_sun" in params:
            params["gear1_radius"] = params["r_sun"]
        elif "sun_radius" in params:
            params["gear1_radius"] = params["sun_radius"]
        else:
            params["gear1_radius"] = 20  # Default sun radius

        if "r_planet" in params:
            params["gear2_radius"] = params["r_planet"]
        elif "planet_radius" in params:
            params["gear2_radius"] = params["planet_radius"]
        else:
            params["gear2_radius"] = 30  # Default planet radius

        # Try to get positions from simulation data
        to_scene = self.parent_tab._get_scene_transform_function(layer_data)

        if "gear_positions" in full_sim_data and to_scene:
            self._extract_planetary_positions_from_simulation(params, full_sim_data, to_scene)
        else:
            self._set_default_planetary_positions(params)

    def _extract_planetary_positions_from_simulation(self, params: Dict[str, Any], 
                                                   full_sim_data: Dict[str, Any], 
                                                   to_scene):
        """Extract planetary gear positions from simulation data."""
        gear_pos = full_sim_data["gear_positions"]
        
        # Get sun center
        if "sun_centers" in gear_pos and len(gear_pos["sun_centers"]) > 0:
            sun_center = gear_pos["sun_centers"][0]
            sun_scene = to_scene(np.array(sun_center))
            params["gear1_x"], params["gear1_y"] = self._extract_coordinates(sun_scene)

        # Get planet center
        if "planet_centers" in gear_pos and len(gear_pos["planet_centers"]) > 0:
            planet_center = gear_pos["planet_centers"][0]
            planet_scene = to_scene(np.array(planet_center))
            params["gear2_x"], params["gear2_y"] = self._extract_coordinates(planet_scene)

    def _set_default_planetary_positions(self, params: Dict[str, Any]):
        """Set default positions for planetary gear mechanism."""
        if "gear1_x" not in params:
            params["gear1_x"] = 400
        if "gear1_y" not in params:
            params["gear1_y"] = 300

        # Set planet position based on arm length
        arm_length = params.get("arm_length", params.get("carrier_length", 50))
        if "gear2_x" not in params:
            params["gear2_x"] = params["gear1_x"] + params["gear1_radius"] + params["gear2_radius"] + arm_length
        if "gear2_y" not in params:
            params["gear2_y"] = params["gear1_y"]

    def _set_active_editor_from_selection(self):
        """Set active editor based on currently selected part in the UI."""
        # Get the currently selected item from the mechanism layers list
        selected_items = self.parent_tab.ui_widgets['mechanism_layers_list'].selectedItems()
        if selected_items:
            selected_part = selected_items[0].data(Qt.ItemDataRole.UserRole)

            # Find mechanism for the UI-selected part
            found = False
            for mechanism_id, layer_data in self.parent_tab.mechanism_layers.items():
                part_name = layer_data.get("part_name")
                if part_name == selected_part:
                    self.parent_tab.parametric_editor.set_active_editor(mechanism_id)
                    found = True
                    break

            if not found:
                # Default to first mechanism if no match
                if self.parent_tab.mechanism_layers:
                    first_id = list(self.parent_tab.mechanism_layers.keys())[0]
                    self.parent_tab.parametric_editor.set_active_editor(first_id)
        else:
            if self.parent_tab.selected_part_name:
                # Find mechanism for selected part
                for mechanism_id, layer_data in self.parent_tab.mechanism_layers.items():
                    if layer_data.get("part_name") == self.parent_tab.selected_part_name:
                        self.parent_tab.parametric_editor.set_active_editor(mechanism_id)
                        break

    def _disable_parametric_mode(self):
        """Disable parametric editing mode."""
        if not self.parent_tab.parametric_editor:
            return

        try:
            # Disable editing mode
            self.parent_tab.parametric_editor.disable_editing()

            # Enable animation controls after parametric mode
            self._enable_animation_controls_after_parametric()

            # Re-enable mechanism visual interaction
            self._enable_mechanism_visual_interaction()

            # Unmark parametric mode flag on mechanisms
            for mechanism_id in self.parent_tab.mechanism_layers.keys():
                self.parent_tab.mechanism_layers[mechanism_id]['parametric_mode'] = False

        except Exception as e:
            import traceback
            print(f"Error disabling parametric mode: {e}")
            print(traceback.format_exc())

    def _disable_animation_controls_for_parametric(self):
        """Disable animation controls during parametric mode."""
        try:
            # Disable animation control buttons
            if hasattr(self.parent_tab, 'play_btn') and self.parent_tab.play_btn:
                self.parent_tab.play_btn.setEnabled(False)
            if hasattr(self.parent_tab, 'stop_btn') and self.parent_tab.stop_btn:
                self.parent_tab.stop_btn.setEnabled(False)
            if hasattr(self.parent_tab, 'reset_btn') and self.parent_tab.reset_btn:
                self.parent_tab.reset_btn.setEnabled(False)
        except Exception as e:
            print(f"Error disabling animation controls: {e}")

    def _enable_animation_controls_after_parametric(self):
        """Re-enable animation controls after parametric mode."""
        try:
            # Re-enable animation control buttons
            if hasattr(self.parent_tab, 'play_btn') and self.parent_tab.play_btn:
                self.parent_tab.play_btn.setEnabled(True)
            if hasattr(self.parent_tab, 'stop_btn') and self.parent_tab.stop_btn:
                self.parent_tab.stop_btn.setEnabled(True)
            if hasattr(self.parent_tab, 'reset_btn') and self.parent_tab.reset_btn:
                self.parent_tab.reset_btn.setEnabled(True)
        except Exception as e:
            print(f"Error enabling animation controls: {e}")

    def _disable_mechanism_visual_interaction(self):
        """Disable mechanism visual interaction to allow handle interaction."""
        try:
            # Disable interaction for mechanism visual items
            for mechanism_id in self.parent_tab.mechanism_layers:
                for item_list in [
                    self.parent_tab.mechanism_path_items.get(mechanism_id, []),
                    self.parent_tab.path_visual_items.get(mechanism_id, [])
                ]:
                    for item in item_list:
                        if hasattr(item, 'setFlag'):
                            item.setFlag(item.GraphicsItemFlag.ItemIsSelectable, False)
                            item.setFlag(item.GraphicsItemFlag.ItemIsMovable, False)
        except Exception as e:
            print(f"Error disabling mechanism visual interaction: {e}")

    def _enable_mechanism_visual_interaction(self):
        """Re-enable mechanism visual interaction."""
        try:
            # Re-enable interaction for mechanism visual items
            for mechanism_id in self.parent_tab.mechanism_layers:
                for item_list in [
                    self.parent_tab.mechanism_path_items.get(mechanism_id, []),
                    self.parent_tab.path_visual_items.get(mechanism_id, [])
                ]:
                    for item in item_list:
                        if hasattr(item, 'setFlag'):
                            item.setFlag(item.GraphicsItemFlag.ItemIsSelectable, True)
                            item.setFlag(item.GraphicsItemFlag.ItemIsMovable, True)
        except Exception as e:
            print(f"Error enabling mechanism visual interaction: {e}")

    @pyqtSlot(str, dict)
    def _on_parametric_mechanism_update(self, mechanism_id: str, params: Dict[str, Any]):
        """
        Handle mechanism parameter updates from parametric editor.
        
        Args:
            mechanism_id: ID of the mechanism that was updated
            params: Updated mechanism parameters
        """
        try:
            if mechanism_id not in self.parent_tab.mechanism_layers:
                return

            layer_data = self.parent_tab.mechanism_layers[mechanism_id]

            # Update the stored parameters
            if "params" not in layer_data:
                layer_data["params"] = {}
            layer_data["params"].update(params)

            # Regenerate mechanism simulation with updated parameters
            self._regenerate_mechanism_simulation(mechanism_id, layer_data)

            # Update visuals in real-time
            self._update_mechanism_visuals_realtime(mechanism_id, layer_data)

        except Exception as e:
            import traceback
            print(f"Error handling parametric mechanism update: {e}")
            print(traceback.format_exc())

    @pyqtSlot(str)
    def _on_parametric_visual_refresh(self, mechanism_id: str):
        """
        Handle visual refresh requests from parametric editor.
        
        Args:
            mechanism_id: ID of the mechanism to refresh
        """
        try:
            if mechanism_id not in self.parent_tab.mechanism_layers:
                return

            layer_data = self.parent_tab.mechanism_layers[mechanism_id]
            self._update_mechanism_visuals_realtime(mechanism_id, layer_data)

        except Exception as e:
            import traceback
            print(f"Error handling parametric visual refresh: {e}")
            print(traceback.format_exc())

    def _regenerate_mechanism_simulation(self, mechanism_id: str, layer_data: Dict[str, Any]):
        """
        Regenerate simulation data for a mechanism after parameters have changed.
        This recalculates joint positions and paths for the new configuration.
        """
        try:
            mech_type = layer_data.get("type")
            params = layer_data.get("params", {})

            # CRITICAL FIX: Clear existing mechanism traces to prevent old red paths from persisting
            self.parent_tab._clear_mechanism_trace(mechanism_id)

            if mech_type == "4_bar_linkage":
                self._regenerate_4bar_simulation(layer_data, params)
            elif mech_type == "5_bar_linkage":
                self._regenerate_5bar_simulation(layer_data, params)
            elif mech_type == "6_bar_linkage":
                self._regenerate_6bar_simulation(layer_data, params)
            elif mech_type == "cam":
                self._regenerate_cam_simulation(layer_data, params)
            elif mech_type == "gear":
                self._regenerate_gear_simulation(layer_data, params)
            elif mech_type == "planetary_gear":
                self._regenerate_planetary_gear_simulation(layer_data, params)

        except Exception as e:
            print(f"Error regenerating mechanism simulation: {e}")

    def _regenerate_4bar_simulation(self, layer_data: Dict[str, Any], params: Dict[str, Any]):
        """Generate new simulation data for 4-bar linkage."""
        num_frames = 100
        joint_positions = {
            "p1_positions": [],
            "p2_positions": [],
            "p3_positions": [],
            "p4_positions": []
        }

        p1 = np.array(params.get("ground_pivot_1", [0, 0]))
        p2 = np.array(params.get("ground_pivot_2", [100, 0]))
        L2 = params.get("L2", 40)  # Crank length
        L3 = params.get("L3", 60)  # Coupler length
        L4 = params.get("L4", 50)  # Rocker length

        for i in range(num_frames):
            theta = (i / num_frames) * 2 * np.pi

            # Calculate crank position (p3)
            p3 = p1 + L2 * np.array([np.cos(theta), np.sin(theta)])

            # Calculate rocker position (p4) using circle-circle intersection
            p4 = self._solve_circle_intersection(p3, L3, p2, L4)

            if p4 is not None:
                joint_positions["p1_positions"].append(p1.tolist())
                joint_positions["p2_positions"].append(p2.tolist())
                joint_positions["p3_positions"].append(p3.tolist())
                joint_positions["p4_positions"].append(p4.tolist())

        # Store the new simulation data
        layer_data["full_simulation_data"] = {
            "joint_positions": joint_positions
        }

    def _regenerate_5bar_simulation(self, layer_data: Dict[str, Any], params: Dict[str, Any]):
        """Generate new simulation data for 5-bar linkage."""
        num_frames = 100
        joint_positions = {
            "p1_positions": [],
            "p2_positions": [],
            "p3_positions": [],
            "p4_positions": [],
            "p5_positions": []
        }

        # Get updated positions from key_points
        key_points = layer_data.get("key_points", {})
        p1 = np.array(key_points.get("ground_pivot_1", [0, 0]))
        p2 = np.array(key_points.get("ground_pivot_2", [100, 0]))

        # Calculate link lengths from key points
        if "joint_3" in key_points and "joint_4" in key_points and "joint_5" in key_points:
            p3 = np.array(key_points["joint_3"])
            p4 = np.array(key_points["joint_4"])
            p5 = np.array(key_points["joint_5"])

            L2 = np.linalg.norm(p3 - p1)  # Input link
            L3 = np.linalg.norm(p4 - p3)  # Coupler 1
            L4 = np.linalg.norm(p5 - p4)  # Coupler 2
            L5 = np.linalg.norm(p5 - p2)  # Output link

            params["L2"] = float(L2)
            params["L3"] = float(L3)
            params["L4"] = float(L4)
            params["L5"] = float(L5)
        else:
            L2 = params.get("L2", 40)
            L3 = params.get("L3", 50)
            L4 = params.get("L4", 45)
            L5 = params.get("L5", 55)

        for i in range(num_frames):
            theta = (i / num_frames) * 2 * np.pi

            # Calculate positions for 5-bar linkage
            p3 = p1 + L2 * np.array([np.cos(theta), np.sin(theta)])
            p4 = p3 + L3 * np.array([np.cos(theta + 0.5), np.sin(theta + 0.5)])
            p5 = self._solve_circle_intersection(p4, L4, p2, L5)

            if p5 is not None:
                joint_positions["p1_positions"].append(p1.tolist())
                joint_positions["p2_positions"].append(p2.tolist())
                joint_positions["p3_positions"].append(p3.tolist())
                joint_positions["p4_positions"].append(p4.tolist())
                joint_positions["p5_positions"].append(p5.tolist())

        layer_data["full_simulation_data"] = {
            "joint_positions": joint_positions
        }

    def _regenerate_6bar_simulation(self, layer_data: Dict[str, Any], params: Dict[str, Any]):
        """Generate new simulation data for 6-bar linkage (Stephenson Type I)."""
        num_frames = 100
        joint_positions = {
            "p1_positions": [],
            "p2_positions": [],
            "p3_positions": [],
            "p4_positions": [],
            "p5_positions": [],
            "p6_positions": []
        }

        # Get updated positions from key_points
        key_points = layer_data.get("key_points", {})
        p1 = np.array(key_points.get("ground_pivot_1", [0, 0]))
        p2 = np.array(key_points.get("ground_pivot_2", [100, 0]))
        p6 = np.array(key_points.get("ground_pivot_3", [50, -30]))

        # Calculate link lengths
        if all(k in key_points for k in ["joint_3", "joint_4", "joint_5"]):
            p3 = np.array(key_points["joint_3"])
            p4 = np.array(key_points["joint_4"])
            p5 = np.array(key_points["joint_5"])

            L2 = np.linalg.norm(p3 - p1)
            L3 = np.linalg.norm(p4 - p3)
            L4 = np.linalg.norm(p4 - p2)
            L5 = np.linalg.norm(p5 - p4)
            L6 = np.linalg.norm(p5 - p6)

            params.update({
                "L2": float(L2), "L3": float(L3), "L4": float(L4),
                "L5": float(L5), "L6": float(L6)
            })
        else:
            L2 = params.get("L2", 40)
            L3 = params.get("L3", 60)
            L4 = params.get("L4", 50)
            L5 = params.get("L5", 45)
            L6 = params.get("L6", 55)

        for i in range(num_frames):
            theta = (i / num_frames) * 2 * np.pi

            # Calculate positions for 6-bar linkage
            p3 = p1 + L2 * np.array([np.cos(theta), np.sin(theta)])
            p4 = self._solve_circle_intersection(p3, L3, p2, L4)

            if p4 is not None:
                p5 = self._solve_circle_intersection(p4, L5, p6, L6)
                if p5 is not None:
                    joint_positions["p1_positions"].append(p1.tolist())
                    joint_positions["p2_positions"].append(p2.tolist())
                    joint_positions["p3_positions"].append(p3.tolist())
                    joint_positions["p4_positions"].append(p4.tolist())
                    joint_positions["p5_positions"].append(p5.tolist())
                    joint_positions["p6_positions"].append(p6.tolist())

        layer_data["full_simulation_data"] = {
            "joint_positions": joint_positions
        }

    def _regenerate_cam_simulation(self, layer_data: Dict[str, Any], params: Dict[str, Any]):
        """Generate cam mechanism data with correct physics."""
        num_frames = 100
        base_radius = params.get("base_radius", 25.0)
        eccentricity = params.get("eccentricity", 10.0)
        rod_length = params.get("follower_rod_length", 40.0)

        # Update from key_points if available
        key_points = layer_data.get("key_points", {})
        if "cam_center" in key_points:
            cam_center_base = np.array(key_points["cam_center"])
        else:
            cam_center_base = np.array([0, 0])

        cam_data = {
            "cam_centers": [],
            "follower_y_positions": []
        }

        for i in range(num_frames):
            # Cam rotates in place at cam_center_base
            angle = (i / num_frames) * 2 * np.pi

            # Calculate cam radius at this rotation angle using our corrected egg shape
            # Proper cam profile: lift when convex part is at bottom (pushes follower up)
            lift = eccentricity * (1 + np.cos(angle + np.pi/2)) / 2  # Shifted for proper phase
            cam_radius_at_angle = base_radius + lift

            # Cam center stays fixed (cam rotates in place)
            current_cam_center = cam_center_base

            # Follower rides on top of cam at the contact point
            # The follower's Y position is cam center Y + cam radius + rod length offset
            follower_y = current_cam_center[1] - cam_radius_at_angle - rod_length

            cam_data["cam_centers"].append(current_cam_center.tolist())
            cam_data["follower_y_positions"].append(follower_y)

        layer_data["full_simulation_data"] = {
            "cam_data": cam_data
        }

    def _regenerate_gear_simulation(self, layer_data: Dict[str, Any], params: Dict[str, Any]):
        """Generate gear rotation data."""
        num_frames = 100
        r1 = params.get("r1", 30)
        r2 = params.get("r2", 50)

        # Update gear positions from key_points if available
        key_points = layer_data.get("key_points", {})
        if "gear1_center" in key_points and "gear2_center" in key_points:
            g1 = np.array(key_points["gear1_center"])
            g2 = np.array(key_points["gear2_center"])
            distance = np.linalg.norm(g2 - g1)

            # Maintain gear ratio but adjust sizes to fit distance
            ratio = r2 / r1
            r1 = distance / (1 + ratio)
            r2 = r1 * ratio
            params["r1"] = float(r1)
            params["r2"] = float(r2)

        gear_data = {
            "gear1_angles": [],
            "gear2_angles": []
        }

        for i in range(num_frames):
            theta1 = (i / num_frames) * 2 * np.pi
            theta2 = -theta1 * (r1 / r2)  # Gear ratio

            gear_data["gear1_angles"].append(theta1)
            gear_data["gear2_angles"].append(theta2)

        layer_data["full_simulation_data"] = {
            "gear_data": gear_data
        }

    def _regenerate_planetary_gear_simulation(self, layer_data: Dict[str, Any], params: Dict[str, Any]):
        """Generate planetary gear data."""
        num_frames = 100
        r_sun = params.get("r_sun", 20)
        r_planet = params.get("r_planet", 30)
        arm_length = params.get("arm_length", 15)

        # Update from key_points if available
        key_points = layer_data.get("key_points", {})
        if "sun_center" in key_points:
            sun_center_base = np.array(key_points["sun_center"])
        else:
            sun_center_base = np.array([0, 0])

        gear_positions = {
            "sun_centers": [],
            "planet_centers": [],
            "tracking_points": []
        }

        for i in range(num_frames):
            angle = (i / num_frames) * 2 * np.pi
            planet_orbital_angle = angle
            planet_rotation_angle = -angle * (r_sun / r_planet)

            sun_center = sun_center_base
            planet_center = sun_center + (r_sun + r_planet) * np.array([
                np.cos(planet_orbital_angle), np.sin(planet_orbital_angle)
            ])
            tracking_point = planet_center + arm_length * np.array([
                np.cos(planet_rotation_angle), np.sin(planet_rotation_angle)
            ])

            gear_positions["sun_centers"].append(sun_center.tolist())
            gear_positions["planet_centers"].append(planet_center.tolist())
            gear_positions["tracking_points"].append(tracking_point.tolist())

        layer_data["full_simulation_data"] = {
            "gear_positions": gear_positions
        }

    def _solve_circle_intersection(self, center1: np.ndarray, radius1: float,
                                 center2: np.ndarray, radius2: float) -> Optional[np.ndarray]:
        """
        Find the intersection point of two circles.
        Returns the intersection point that maintains linkage continuity.
        """
        try:
            d = np.linalg.norm(center2 - center1)

            # Check if circles intersect
            if d > radius1 + radius2 or d < abs(radius1 - radius2) or d == 0:
                # No intersection - return approximate position
                direction = (center2 - center1) / d if d > 0 else np.array([1, 0])
                return center1 + direction * radius1

            # Calculate intersection points
            a = (radius1**2 - radius2**2 + d**2) / (2 * d)
            h = np.sqrt(radius1**2 - a**2)

            # Point on line between centers
            p = center1 + a * (center2 - center1) / d

            # Perpendicular offset
            offset = h * np.array([-(center2[1] - center1[1]), center2[0] - center1[0]]) / d

            # Two possible intersection points
            intersection1 = p + offset
            intersection2 = p - offset

            # Choose the one that maintains continuity (typically the upper one for 4-bar)
            if intersection1[1] >= intersection2[1]:
                return intersection1
            else:
                return intersection2

        except Exception as e:
            # Return a fallback position
            return center1 + np.array([radius1, 0])

    def _update_mechanism_visuals_realtime(self, mechanism_id: str, mechanism_data: Dict[str, Any]):
        """
        Update mechanism visuals in real-time during parametric editing.
        CRITICAL: This needs to be extremely fast for smooth interaction.

        Args:
            mechanism_id: ID of mechanism being updated
            mechanism_data: Full mechanism data (not just params)
        """
        try:
            # Use new visualization system if available for updates
            if (hasattr(self.parent_tab, 'visualization_adapter') and 
                self.parent_tab.visualization_adapter):
                try:
                    # Check if VISUALIZATION_AVAILABLE is imported
                    from ..visualization import VISUALIZATION_AVAILABLE
                    if VISUALIZATION_AVAILABLE:
                        # Set transform function if needed
                        transform_func = self.parent_tab._get_scene_transform_function(mechanism_data)
                        if transform_func:
                            mechanism_data["transform_function"] = transform_func

                        # Update existing visuals (much faster than recreating)
                        self.parent_tab.visualization_adapter.update_mechanism_visuals(mechanism_id, mechanism_data)

                        # Update display
                        if hasattr(self.parent_tab, 'mechanism_view'):
                            self.parent_tab.mechanism_view.update()
                        return
                except ImportError:
                    pass

            # Legacy fallback - recreate visuals (slower)
            layer_data = self.parent_tab.mechanism_layers.get(mechanism_id, mechanism_data)

            # Critical: Stop animation during update to prevent conflicts
            animation_was_running = False
            if hasattr(self.parent_tab, 'animation_timer') and self.parent_tab.animation_timer.isActive():
                animation_was_running = True
                self.parent_tab._on_stop_animation()

            # Extract the previous visual properties to restore later (for consistency)
            visual_items = layer_data.get("visual_items", [])
            original_visual_properties = []
            
            for item in visual_items:
                if item and self._is_item_valid(item):
                    try:
                        props = {
                            'pen': item.pen() if hasattr(item, 'pen') else None,
                            'brush': item.brush() if hasattr(item, 'brush') else None,
                            'z_value': item.zValue(),
                            'visible': item.isVisible(),
                            'enabled': item.isEnabled()
                        }
                        original_visual_properties.append(props)
                    except RuntimeError:
                        # Item was deleted
                        original_visual_properties.append({})

            # Remove old visual items from scene
            for item in visual_items:
                if item and self._is_item_valid(item):
                    try:
                        if (hasattr(self.parent_tab, 'mechanism_scene') and 
                            item.scene() == self.parent_tab.mechanism_scene):
                            self.parent_tab.mechanism_scene.removeItem(item)
                    except RuntimeError:
                        # Item was already deleted
                        pass

            # Recreate visual items with updated parameters
            mechanism_type = layer_data.get("type")
            new_items = self._create_mechanism_visuals(layer_data, mechanism_type)

            # Apply original visual properties to new items if available
            for i, item in enumerate(new_items):
                if i < len(original_visual_properties) and item:
                    try:
                        props = original_visual_properties[i]
                        if props.get('pen') and hasattr(item, 'setPen'):
                            item.setPen(props['pen'])
                        if props.get('brush') and hasattr(item, 'setBrush'):
                            item.setBrush(props['brush'])
                        if props.get('z_value'):
                            item.setZValue(props['z_value'])
                        if props.get('visible') is not None:
                            item.setVisible(props['visible'])
                        if props.get('enabled') is not None:
                            item.setEnabled(props['enabled'])
                    except (RuntimeError, KeyError):
                        # Item properties couldn't be restored - continue
                        continue

            # Store updated visual items
            layer_data["visual_items"] = new_items

            # Update handle positions if parametric mode is enabled
            if (hasattr(self.parent_tab, 'parametric_handles') and 
                mechanism_id in self.parent_tab.parametric_handles and 
                self.parametric_mode_enabled):
                self._update_handle_positions_for_mechanism(mechanism_id, layer_data)

            # Update display
            if hasattr(self.parent_tab, 'mechanism_view'):
                self.parent_tab.mechanism_view.update()

            # Resume animation if it was running (but only if parametric mode allows it)
            if animation_was_running and not self.parametric_mode_enabled:
                self.parent_tab._on_start_animation()

        except Exception as e:
            print(f"Error updating mechanism visuals: {e}")

    def _is_item_valid(self, item) -> bool:
        """Check if a graphics item is valid and not deleted."""
        try:
            # Try to access a basic property to check if item is valid
            _ = item.zValue()
            return True
        except (RuntimeError, AttributeError):
            return False

    def _create_mechanism_visuals(self, layer_data: Dict[str, Any], mechanism_type: str) -> list:
        """
        Create visual items for a mechanism based on its type.
        
        Args:
            layer_data: Mechanism layer data
            mechanism_type: Type of mechanism
            
        Returns:
            List of created visual items
        """
        new_items = []
        
        try:
            # Use visuals_factory from parent tab (authoritative visual creation)
            vf = getattr(self.parent_tab, 'visuals_factory', None)
            if not vf:
                return []

            transform_func = self.parent_tab._get_scene_transform_function(layer_data)

            if mechanism_type == "4_bar_linkage" and hasattr(vf, 'create_4bar_linkage_visuals'):
                new_items = vf.create_4bar_linkage_visuals(layer_data, transform_func)
            elif mechanism_type == "cam" and hasattr(vf, 'create_cam_visuals'):
                char_pos = self.parent_tab._get_character_position() if hasattr(self.parent_tab, '_get_character_position') else None
                new_items = vf.create_cam_visuals(layer_data, transform_func, char_pos)
            elif mechanism_type == "gear" and hasattr(vf, 'create_gear_visuals'):
                new_items = vf.create_gear_visuals(layer_data, transform_func)
            elif mechanism_type == "planetary_gear" and hasattr(vf, 'create_planetary_gear_visuals'):
                new_items = vf.create_planetary_gear_visuals(layer_data, transform_func)
        except Exception as e:
            print(f"Error creating visuals for {mechanism_type}: {e}")
            
        return new_items

    def _update_handle_positions_for_mechanism(self, mechanism_id: str, layer_data: Dict[str, Any]):
        """
        Update handle positions for a specific mechanism.
        
        Args:
            mechanism_id: ID of the mechanism
            layer_data: Mechanism layer data
        """
        try:
            # Delegate to parent tab method if it exists
            if hasattr(self.parent_tab, '_update_handle_positions_for_mechanism'):
                self.parent_tab._update_handle_positions_for_mechanism(mechanism_id, layer_data)
        except Exception as e:
            print(f"Error updating handle positions for mechanism {mechanism_id}: {e}")

    def is_parametric_mode_enabled(self) -> bool:
        """
        Check if parametric mode is currently enabled.
        
        Returns:
            True if parametric mode is enabled, False otherwise
        """
        return self.parametric_mode_enabled

    def cleanup(self):
        """Clean up resources used by the parametric editing manager."""
        try:
            # Disable parametric mode if enabled
            if self.parametric_mode_enabled:
                self.toggle_parametric_mode(False)
            
            # Clear any stored state
            if hasattr(self, '_animation_state_before_parametric'):
                delattr(self, '_animation_state_before_parametric')
                
        except Exception as e:
            print(f"Error during parametric editing manager cleanup: {e}")
