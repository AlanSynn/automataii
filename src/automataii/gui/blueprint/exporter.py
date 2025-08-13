from __future__ import annotations

import logging
import os
from typing import Any, Callable, Dict, Optional

import numpy as np
from PyQt6.QtCore import QPointF
from PyQt6.QtWidgets import QMessageBox, QWidget


class BlueprintExporter:
    """Encapsulates blueprint-related functionality for MechanismDesignTab.

    This class extracts legacy blueprint export logic and helpers from the
    tab into a self-contained module. It avoids behavioral changes and can be
    reused from the tab by delegating calls.
    """

    def __init__(
        self,
        *,
        parent: QWidget,
        mechanism_view: Any,
        get_mechanism_layers: Callable[[], Dict[str, Any]],
        get_current_editor_items: Callable[[], Dict[str, Any]],
        get_scene_transform_function: Callable[[Dict[str, Any]], Optional[Callable[[np.ndarray], QPointF]]],
    ) -> None:
        self._parent = parent
        self._mechanism_view = mechanism_view
        self._get_mechanism_layers = get_mechanism_layers
        self._get_current_editor_items = get_current_editor_items
        self._get_scene_transform_function = get_scene_transform_function

    # ---------- Public API ----------

    def export_all(self) -> None:
        """Export all parts and mechanisms using the legacy simple system."""
        try:
            from automataii.core.blueprint_manager import BlueprintExportManager

            logging.info("[BLUEPRINT] Using legacy simple blueprint export system")

            blueprint_manager = BlueprintExportManager.get_instance()

            part_items = self._collect_part_items()
            mechanism_layers = self._get_mechanism_layers() or {}

            if not part_items and not mechanism_layers:
                QMessageBox.warning(
                    self._parent,
                    "Blueprint Export",
                    "No mechanisms or character parts available for export.\n"
                    "Please create some mechanisms or load character parts first.",
                )
                return

            logging.info(
                f"[BLUEPRINT] Legacy export: {len(part_items)} parts, {len(mechanism_layers)} mechanisms"
            )

            success = blueprint_manager.export_blueprint(
                part_items=part_items,
                mechanism_layers=mechanism_layers,
                parent_widget=self._parent,
                single_large_page=True,
                snapshot_png_bytes=None,
            )

            if success:
                logging.info("[BLUEPRINT] Legacy blueprint export successful")
                QMessageBox.information(
                    self._parent,
                    "Blueprint Export Complete",
                    "Blueprint exported successfully using the legacy system!\n\n"
                    f"Parts: {len(part_items)}\n"
                    f"Mechanisms: {len(mechanism_layers)}\n\n"
                    "The blueprint uses the original large-format layout\n"
                    "with proper part outlines and mechanism details.",
                )
            else:
                logging.warning("[BLUEPRINT] Legacy blueprint export failed")
                QMessageBox.warning(
                    self._parent,
                    "Blueprint Export Failed",
                    "Blueprint export failed using the legacy system.\n"
                    "Check the console for details.",
                )

        except ImportError as e:
            logging.error(f"[BLUEPRINT] Legacy import error: {e}")
            QMessageBox.critical(
                self._parent,
                "Blueprint Export Error",
                "Legacy blueprint export functionality is not available.\n"
                "Some required modules may be missing.\n\n"
                f"Error: {str(e)}",
            )
        except Exception as e:
            logging.error(f"[BLUEPRINT] Legacy unexpected error: {e}")
            QMessageBox.critical(
                self._parent,
                "Blueprint Export Error",
                f"An unexpected error occurred with legacy export:\n\n{str(e)}",
            )

    def export_mechanism(self, mechanism_id: str, filename: str | None = None) -> None:
        """Export a single mechanism using the legacy system.

        If `filename` is provided, saves directly to that SVG path using the
        legacy layout/generation. Otherwise delegates to the manager's dialog.
        """
        try:
            logging.info(f"[BLUEPRINT] Exporting mechanism {mechanism_id} using legacy system")

            mechanism_layers_all = self._get_mechanism_layers()
            layer_data = mechanism_layers_all.get(mechanism_id) if mechanism_layers_all else None
            if not layer_data:
                logging.error(f"[BLUEPRINT] No mechanism found with ID {mechanism_id}")
                return

            from automataii.core.blueprint_manager import BlueprintExportManager

            blueprint_manager = BlueprintExportManager.get_instance()

            mechanism_layers = {mechanism_id: layer_data}
            part_items = self._collect_part_items()

            if filename:
                from automataii.generation.blueprint import generate_single_large_blueprint
                from automataii.generation.blueprint_optimizer import BlueprintLayoutOptimizer

                optimizer = BlueprintLayoutOptimizer(target_character_height_mm=300.0)
                layout_items, _, _ = optimizer.optimize_blueprint_layout(part_items, mechanism_layers)

                page_width_mm = 800.0
                page_height_mm = 600.0

                svg_content = generate_single_large_blueprint(
                    layout_items,
                    page_width_mm,
                    page_height_mm,
                    title=f"Mechanism Blueprint - {layer_data.get('type', 'Unknown')}",
                    scale_info="Legacy Blueprint System",
                    snapshot_data_uri=None,
                )

                os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else ".", exist_ok=True)
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(svg_content)

                logging.info(f"[BLUEPRINT] Blueprint exported to {filename}")
                QMessageBox.information(
                    self._parent,
                    "Export Successful",
                    f"Blueprint exported using legacy system:\n{filename}\n\n"
                    f"Mechanism: {layer_data.get('type', 'Unknown')}\n"
                    f"Parts included: {len(part_items)}\n\n"
                    "Legacy blueprint with proper scaling and layout.",
                )
            else:
                success = blueprint_manager.export_blueprint(
                    part_items=part_items,
                    mechanism_layers=mechanism_layers,
                    parent_widget=self._parent,
                    single_large_page=True,
                    snapshot_png_bytes=None,
                )

                if success:
                    logging.info(
                        f"[BLUEPRINT] Legacy blueprint export successful for mechanism {mechanism_id}"
                    )
                else:
                    logging.warning(
                        f"[BLUEPRINT] Legacy blueprint export failed for mechanism {mechanism_id}"
                    )

        except Exception as e:
            logging.error(f"[BLUEPRINT] Failed to export blueprint for mechanism {mechanism_id}: {e}")
            QMessageBox.critical(
                self._parent, "Export Failed", f"Failed to export blueprint using legacy system:\n{str(e)}"
            )

    def show_mechanism_dimensions(self, mechanism_id: str) -> None:
        """Show a dimension summary for a specific mechanism."""
        mechanism_layers_all = self._get_mechanism_layers()
        if not mechanism_layers_all or mechanism_id not in mechanism_layers_all:
            return

        layer_data = mechanism_layers_all[mechanism_id]
        mech_type = layer_data.get("type")
        params = layer_data.get("params", {})

        scene_rect = self._mechanism_view.scene().itemsBoundingRect()
        scene_width = scene_rect.width()
        scene_height = scene_rect.height()

        mm_per_inch = 25.4
        letter_width_mm = 8.5 * mm_per_inch
        letter_height_mm = 11 * mm_per_inch

        margin_factor = 0.9
        scale_x = (letter_width_mm * margin_factor) / scene_width if scene_width > 0 else 1
        scale_y = (letter_height_mm * margin_factor) / scene_height if scene_height > 0 else 1
        scale_factor = min(scale_x, scale_y)

        dimensions_text = "=== MECHANISM DIMENSIONS ===\n"
        dimensions_text += f"Type: {mech_type}\n"
        dimensions_text += f"Scale: 1 pixel = {scale_factor:.2f} mm\n"
        dimensions_text += "Printable on: Letter size (8.5\" x 11\")\n\n"

        if mech_type == "4_bar_linkage":
            L1 = params.get("L1", 0) * scale_factor
            L2 = params.get("L2", 0) * scale_factor
            L3 = params.get("L3", 0) * scale_factor
            L4 = params.get("L4", 0) * scale_factor

            dimensions_text += "Link Lengths (mm):\n"
            dimensions_text += f"  Ground Link (L1): {L1:.1f} mm ({L1/mm_per_inch:.2f}\")\n"
            dimensions_text += f"  Crank (L2): {L2:.1f} mm ({L2/mm_per_inch:.2f}\")\n"
            dimensions_text += f"  Coupler (L3): {L3:.1f} mm ({L3/mm_per_inch:.2f}\")\n"
            dimensions_text += f"  Rocker (L4): {L4:.1f} mm ({L4/mm_per_inch:.2f}\")\n"

        elif mech_type == "cam":
            base_radius = params.get("base_radius", 0) * scale_factor
            eccentricity = params.get("eccentricity", 0) * scale_factor

            dimensions_text += "Cam Dimensions (mm):\n"
            dimensions_text += f"  Base Radius: {base_radius:.1f} mm ({base_radius/mm_per_inch:.2f}\")\n"
            dimensions_text += f"  Eccentricity: {eccentricity:.1f} mm ({eccentricity/mm_per_inch:.2f}\")\n"
            dimensions_text += f"  Max Radius: {base_radius + eccentricity:.1f} mm\n"
            dimensions_text += f"  Min Radius: {base_radius - eccentricity:.1f} mm\n"

        elif mech_type == "gear":
            r1 = params.get("r1", 0) * scale_factor
            r2 = params.get("r2", 0) * scale_factor

            dimensions_text += "Gear Dimensions (mm):\n"
            dimensions_text += f"  Gear 1 Radius: {r1:.1f} mm ({r1/mm_per_inch:.2f}\")\n"
            dimensions_text += f"  Gear 2 Radius: {r2:.1f} mm ({r2/mm_per_inch:.2f}\")\n"
            dimensions_text += f"  Center Distance: {r1 + r2:.1f} mm\n"
            dimensions_text += f"  Gear Ratio: {r2/r1:.2f}:1\n"

        elif mech_type == "planetary_gear":
            r_sun = params.get("r_sun", 0) * scale_factor
            r_planet = params.get("r_planet", 0) * scale_factor
            arm_length = params.get("arm_length", 0) * scale_factor

            dimensions_text += "Planetary Gear Dimensions (mm):\n"
            dimensions_text += f"  Sun Gear Radius: {r_sun:.1f} mm ({r_sun/mm_per_inch:.2f}\")\n"
            dimensions_text += f"  Planet Gear Radius: {r_planet:.1f} mm ({r_planet/mm_per_inch:.2f}\")\n"
            dimensions_text += f"  Arm Length: {arm_length:.1f} mm ({arm_length/mm_per_inch:.2f}\")\n"
            dimensions_text += f"  Orbital Radius: {r_sun + r_planet:.1f} mm\n"

        msg_box = QMessageBox()
        msg_box.setWindowTitle("Mechanism Dimensions")
        msg_box.setText(dimensions_text)
        msg_box.setDetailedText(self.generate_blueprint_instructions(mech_type, params, scale_factor))
        msg_box.setIcon(QMessageBox.Icon.Information)
        msg_box.exec()

        logging.info(f"[DIMENSIONS] {dimensions_text}")

    def show_current_mechanism_dimensions(self) -> None:
        """Show dimensions for an arbitrary available mechanism (first one)."""
        mechanism_layers = self._get_mechanism_layers()
        if not mechanism_layers:
            QMessageBox.warning(self._parent, "No Mechanism", "No mechanism available to show dimensions.")
            return
        mechanism_id = next(iter(mechanism_layers.keys()))
        self.show_mechanism_dimensions(mechanism_id)

    def calculate_screen_to_blueprint_scale(self) -> Dict[str, Any]:
        """Calculate screen-to-blueprint scale info based on the current view."""
        try:
            view_rect = self._mechanism_view.viewport().rect()
            scene_rect = self._mechanism_view.mapToScene(view_rect).boundingRect()

            if scene_rect.width() > 0 and scene_rect.height() > 0:
                pixels_per_scene_unit_x = view_rect.width() / scene_rect.width()
                pixels_per_scene_unit_y = view_rect.height() / scene_rect.height()
                pixels_per_scene_unit = (pixels_per_scene_unit_x + pixels_per_scene_unit_y) / 2.0
            else:
                pixels_per_scene_unit = 1.0

            character_height_pixels = 0
            character_width_pixels = 0

            current_items = self._get_current_editor_items() or {}
            if current_items:
                all_bounds = []
                for part_item in current_items.values():
                    try:
                        scene_bounds = part_item.sceneBoundingRect()
                        all_bounds.append(scene_bounds)
                    except Exception:
                        continue

                if all_bounds:
                    min_x = min(b.left() for b in all_bounds)
                    max_x = max(b.right() for b in all_bounds)
                    min_y = min(b.top() for b in all_bounds)
                    max_y = max(b.bottom() for b in all_bounds)

                    character_height_pixels = (max_y - min_y) * pixels_per_scene_unit
                    character_width_pixels = (max_x - min_x) * pixels_per_scene_unit

            target_character_height_mm = 300.0

            if character_height_pixels > 0:
                mm_per_pixel = target_character_height_mm / character_height_pixels
                pixels_per_mm = 1.0 / mm_per_pixel
                actual_character_height_mm = target_character_height_mm
            else:
                mm_per_pixel = 0.36
                pixels_per_mm = 1.0 / mm_per_pixel
                actual_character_height_mm = target_character_height_mm

            mechanism_scale_factors: Dict[str, float] = {}
            mechanism_layers = self._get_mechanism_layers() or {}
            for mech_id, layer_data in mechanism_layers.items():
                transform_func = self._get_scene_transform_function(layer_data)
                if transform_func:
                    test_point = np.array([0.0, 100.0])
                    test_origin = np.array([0.0, 0.0])
                    try:
                        transformed_point = transform_func(test_point)
                        transformed_origin = transform_func(test_origin)
                        scene_distance = (
                            (transformed_point.x() - transformed_origin.x()) ** 2
                            + (transformed_point.y() - transformed_origin.y()) ** 2
                        ) ** 0.5
                        mechanism_scale_factors[mech_id] = scene_distance / 100.0 if scene_distance > 0 else 1.0
                    except Exception:
                        mechanism_scale_factors[mech_id] = 1.0

            scale_info: Dict[str, Any] = {
                "pixels_per_mm": pixels_per_mm,
                "mm_per_pixel": mm_per_pixel,
                "pixels_per_scene_unit": pixels_per_scene_unit,
                "character_height_mm": actual_character_height_mm,
                "character_height_pixels": character_height_pixels,
                "character_width_pixels": character_width_pixels,
                "view_rect": view_rect,
                "scene_rect": scene_rect,
                "mechanism_scale_factors": mechanism_scale_factors,
                "target_character_height_mm": target_character_height_mm,
            }

            logging.info(
                f"Screen-to-blueprint scale calculated: {pixels_per_mm:.2f} pixels/mm, character: {actual_character_height_mm:.0f}mm"
            )
            return scale_info

        except Exception as e:
            logging.warning(f"Error calculating screen scale, using defaults: {e}")
            return {
                "pixels_per_mm": 2.78,
                "mm_per_pixel": 0.36,
                "pixels_per_scene_unit": 1.0,
                "character_height_mm": 300.0,
                "character_height_pixels": 800,
                "character_width_pixels": 400,
                "mechanism_scale_factors": {},
                "target_character_height_mm": 300.0,
            }

    def enhance_mechanism_layers_with_scale_info(self, screen_scale_info: Dict[str, Any]) -> Dict[str, Any]:
        """Attach scale info and real-world params to each mechanism layer."""
        enhanced_layers: Dict[str, Any] = {}

        try:
            mechanism_layers = self._get_mechanism_layers() or {}
            for mech_id, layer_data in mechanism_layers.items():
                enhanced_layer = layer_data.copy()
                enhanced_layer["screen_scale_info"] = screen_scale_info

                mech_scale_factor = screen_scale_info["mechanism_scale_factors"].get(mech_id, 1.0)
                enhanced_layer["mechanism_to_screen_scale"] = mech_scale_factor
                enhanced_layer["screen_to_blueprint_scale"] = screen_scale_info["mm_per_pixel"]
                enhanced_layer["total_scale_factor"] = mech_scale_factor * screen_scale_info["mm_per_pixel"]

                if "params" in enhanced_layer:
                    real_world_params = self.calculate_real_world_mechanism_params(
                        enhanced_layer["params"], enhanced_layer["total_scale_factor"], enhanced_layer.get("type", "unknown")
                    )
                    enhanced_layer["real_world_params"] = real_world_params

                transform_func = self._get_scene_transform_function(layer_data)
                if transform_func:
                    enhanced_layer["has_transform_function"] = True

                enhanced_layers[mech_id] = enhanced_layer
                logging.debug(
                    f"Enhanced mechanism {mech_id}: scale={mech_scale_factor:.3f}, total={enhanced_layer['total_scale_factor']:.3f}"
                )

        except Exception as e:
            logging.error(f"Error enhancing mechanism layers: {e}")
            return (self._get_mechanism_layers() or {}).copy()

        return enhanced_layers

    def calculate_real_world_mechanism_params(self, params: Dict[str, Any], scale_factor: float, mech_type: str) -> Dict[str, Any]:
        """Convert mechanism params to mm using total scale factor."""
        real_world_params: Dict[str, Any] = {}
        try:
            if mech_type == "4_bar_linkage":
                for param_name in ["l1", "l2", "l3", "l4"]:
                    if param_name in params:
                        real_world_params[f"{param_name}_mm"] = params[param_name] * scale_factor
                for param_name in ["coupler_point_x", "coupler_point_y"]:
                    if param_name in params:
                        real_world_params[f"{param_name}_mm"] = params[param_name] * scale_factor
            elif mech_type == "cam":
                for param_name in ["base_radius", "eccentricity"]:
                    if param_name in params:
                        real_world_params[f"{param_name}_mm"] = params[param_name] * scale_factor
            elif mech_type in ["gear", "planetary_gear"]:
                for param_name in [
                    "r1",
                    "r2",
                    "r_sun",
                    "r_planet",
                    "arm_length",
                    "distance",
                    "tracking_radius",
                ]:
                    if param_name in params:
                        real_world_params[f"{param_name}_mm"] = params[param_name] * scale_factor

            real_world_params["scale_factor_used"] = scale_factor
            real_world_params["mechanism_type"] = mech_type

        except Exception as e:
            logging.warning(f"Error calculating real-world params for {mech_type}: {e}")
            real_world_params = {"scale_factor_used": scale_factor, "mechanism_type": mech_type}

        return real_world_params

    def generate_blueprint_instructions(self, mech_type: str, params: Dict[str, Any], scale_factor: float) -> str:
        """Generate printable assembly instructions text for the mechanism."""
        instructions = "=== CONSTRUCTION INSTRUCTIONS ===\n\n"
        mm_per_inch = 25.4

        if mech_type == "4_bar_linkage":
            instructions += "Materials Needed:\n"
            instructions += "- 4 rigid bars (wood, metal, or plastic)\n"
            instructions += "- 4 pivot joints (bolts, pins, or bearings)\n"
            instructions += "- Base plate for mounting\n\n"
            instructions += "Assembly Steps:\n"
            instructions += "1. Cut bars to the following lengths:\n"
            L1 = params.get("L1", 0) * scale_factor
            L2 = params.get("L2", 0) * scale_factor
            L3 = params.get("L3", 0) * scale_factor
            L4 = params.get("L4", 0) * scale_factor
            instructions += f"   - Ground link: {L1:.1f} mm ({L1/mm_per_inch:.2f}\")\n"
            instructions += f"   - Crank: {L2:.1f} mm ({L2/mm_per_inch:.2f}\")\n"
            instructions += f"   - Coupler: {L3:.1f} mm ({L3/mm_per_inch:.2f}\")\n"
            instructions += f"   - Rocker: {L4:.1f} mm ({L4/mm_per_inch:.2f}\")\n\n"
            instructions += "2. Drill holes at both ends of each bar (5-6mm diameter)\n"
            instructions += "3. Mount ground link to base plate\n"
            instructions += "4. Connect crank to left ground pivot\n"
            instructions += "5. Connect rocker to right ground pivot\n"
            instructions += "6. Connect coupler between crank and rocker\n"
            instructions += "7. Ensure all joints move freely\n"
        elif mech_type == "cam":
            base_radius = params.get("base_radius", 0) * scale_factor
            eccentricity = params.get("eccentricity", 0) * scale_factor
            instructions += "Materials Needed:\n"
            instructions += "- Cam material (wood, acrylic, or metal)\n"
            instructions += "- Follower rod\n"
            instructions += "- Linear bearing or guide\n"
            instructions += "- Rotation shaft and bearing\n\n"
            instructions += "Cam Profile Creation:\n"
            instructions += "1. Draw egg-shaped profile:\n"
            instructions += f"   - Maximum radius: {base_radius + eccentricity:.1f} mm\n"
            instructions += f"   - Minimum radius: {base_radius - eccentricity:.1f} mm\n"
            instructions += "2. Mark center hole for shaft\n"
            instructions += "3. Cut cam profile carefully\n"
            instructions += "4. Smooth edges for proper follower contact\n"
            instructions += "5. Install follower guide above cam\n"
        elif mech_type == "gear":
            r1 = params.get("r1", 0) * scale_factor
            r2 = params.get("r2", 0) * scale_factor
            module = 2
            teeth1 = int(2 * r1 / module)
            teeth2 = int(2 * r2 / module)
            instructions += "Materials Needed:\n"
            instructions += "- 2 gears or gear blanks\n"
            instructions += "- 2 shafts and bearings\n"
            instructions += "- Mounting plate\n\n"
            instructions += "Gear Specifications:\n"
            instructions += f"Gear 1:\n"
            instructions += f"  - Pitch diameter: {2*r1:.1f} mm\n"
            instructions += f"  - Estimated teeth: {teeth1}\n"
            instructions += f"Gear 2:\n"
            instructions += f"  - Pitch diameter: {2*r2:.1f} mm\n"
            instructions += f"  - Estimated teeth: {teeth2}\n"
            instructions += f"Center distance: {r1 + r2:.1f} mm\n\n"
            instructions += "Assembly:\n"
            instructions += "1. Mount bearings at specified center distance\n"
            instructions += "2. Install gears on shafts\n"
            instructions += "3. Ensure proper meshing without binding\n"

        return instructions

    # ---------- Internal helpers ----------

    def _collect_part_items(self) -> list[Any]:
        part_items: list[Any] = []
        current_items = self._get_current_editor_items() or {}
        for part_name, part_item in current_items.items():
            if hasattr(part_item, "shape") and callable(part_item.shape):
                part_items.append(part_item)
                logging.debug(f"[BLUEPRINT] Added part: {part_name}")
        return part_items

