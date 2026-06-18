from __future__ import annotations

import logging
import math
from collections.abc import Callable
from pathlib import Path
from typing import Any, SupportsFloat, SupportsIndex, cast

import numpy as np
from PyQt6.QtCore import QPointF
from PyQt6.QtWidgets import QMessageBox, QWidget

from automataii.application.fabrication import FabricationLayerSelection
from automataii.infrastructure.telemetry import telemetry_span
from automataii.shared.physical_kit import (
    DEFAULT_GRID_CELL_CM,
    gear_center_distance,
    gear_clearance_from_params,
    gear_teeth_from_params,
    grid_enabled_from_params,
    physical_context_from_params,
    physical_profile_from_params,
    snap_physical_params,
)

_NumericPayload = str | bytes | bytearray | SupportsFloat | SupportsIndex


def _finite_float(value: object, default: float = 0.0) -> float:
    try:
        result = float(cast(_NumericPayload, value))
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _first_value(params: dict[str, Any], *names: str, default: object = None) -> object:
    for name in names:
        if name in params:
            return params[name]
    return default


class BlueprintExporter:
    """Encapsulates blueprint-related functionality for MechanismDesignTab.

    Provides a thin UI adapter around the application-layer blueprint composer
    so the tab can drive exports without embedding layout logic.
    """

    def __init__(
        self,
        *,
        parent: QWidget,
        mechanism_view: Any,
        get_mechanism_layers: Callable[[], dict[str, Any]],
        get_current_editor_items: Callable[[], dict[str, Any]],
        get_scene_transform_function: Callable[
            [dict[str, Any]], Callable[[np.ndarray], QPointF] | None
        ],
        get_blueprint_export_format: Callable[[], str] | None = None,
    ) -> None:
        self._parent = parent
        self._mechanism_view = mechanism_view
        self._get_mechanism_layers = get_mechanism_layers
        self._get_current_editor_items = get_current_editor_items
        self._get_scene_transform_function = get_scene_transform_function
        self._get_blueprint_export_format = get_blueprint_export_format or (lambda: "pdf")

    # ---------- Public API ----------

    def _default_output_directory(self) -> str:
        """Return a user-friendly default directory for export package dialogs."""
        from pathlib import Path

        downloads = Path.home() / "Downloads"
        return str(downloads if downloads.is_dir() else Path.home())

    def _assembly_recipe_keys_for_layers(
        self,
        guide_exporter: Any,
        mechanism_layers: dict[str, Any],
    ) -> set[str]:
        """Map current app mechanisms to the smallest matching board-guide set."""
        recipe_keys: set[str] = set()
        for layer_data in mechanism_layers.values():
            if not isinstance(layer_data, dict):
                continue
            selection = FabricationLayerSelection.from_layer_data(layer_data)
            summary = guide_exporter.resolve_app_state_to_guide(
                selection.mechanism_type,
                active_part_ids=selection.active_part_ids,
            )
            if summary is not None:
                recipe_keys.add(summary.key)
        return recipe_keys

    def _fabrication_ready_mechanism_layers(
        self,
        mechanism_layers: dict[str, Any],
    ) -> dict[str, Any]:
        """Return export-only layers snapped to the current physical-kit preset.

        The app can remain flexible while drawing/simulating, but the PDF package
        must be internally buildable: cut sheet, physical contract, selected
        kit parts, and board guide all need the same snapped values.
        """
        ready_layers: dict[str, Any] = {}
        for layer_id, layer_data in mechanism_layers.items():
            if not isinstance(layer_data, dict):
                ready_layers[layer_id] = layer_data
                continue

            ready_layer = dict(layer_data)
            params = ready_layer.get("params")
            if not isinstance(params, dict):
                ready_layers[layer_id] = ready_layer
                continue

            export_params = dict(params)
            export_params["grid_system_enabled"] = True
            export_params.setdefault("grid_cell_cm", DEFAULT_GRID_CELL_CM)
            context = physical_context_from_params(export_params, default_enabled=True)
            export_params.update(context.as_params())

            selection = FabricationLayerSelection.from_layer_data(ready_layer)
            ready_layer["params"] = snap_physical_params(
                selection.mechanism_type,
                export_params,
                context.grid_cell_cm,
                enabled=True,
                profile=context.profile,
            )
            ready_layer["params"].update(context.as_params())
            raw_fabrication = ready_layer.get("fabrication")
            fabrication = dict(raw_fabrication) if isinstance(raw_fabrication, dict) else {}
            fabrication["preset_snapped_for_export"] = True
            ready_layer["fabrication"] = fabrication
            ready_layers[layer_id] = ready_layer
        return ready_layers

    def export_all(self) -> None:
        """Export one PDF-first fabrication package for the current design.

        The default user flow intentionally mirrors a LEGO guide book: one folder
        contains the current character/mechanism cut sheet, the matching board
        assembly PDF, and the needed fabrication part blueprints only. Users no
        longer choose between assembly versus cut sheets because a physical build
        needs both directions side-by-side.
        """
        try:
            from PyQt6.QtWidgets import QFileDialog, QMessageBox

            from automataii.application.fabrication import FabricationAssemblyGuideExporter
            from automataii.application.managers import BlueprintExportManager

            logging.info("[BLUEPRINT] Using PDF-first fabrication package export flow")
            output_dir_text = QFileDialog.getExistingDirectory(
                self._parent,
                "Export Blueprint Package",
                self._default_output_directory(),
            )
            if not output_dir_text:
                return
            output_dir = Path(output_dir_text)
            output_dir.mkdir(parents=True, exist_ok=True)
            for legacy_name in (
                "cut-sheets.pdf",
                "cut-sheets.svg",
                "current-design-cut-sheets.pdf",
                "current-design-cut-sheets.svg",
            ):
                legacy_path = output_dir / legacy_name
                if legacy_path.is_file():
                    legacy_path.unlink()

            blueprint_manager = BlueprintExportManager.get_instance()

            try:
                part_items = self._collect_part_items()
            except Exception as e:
                logging.error(f"[BLUEPRINT] Failed to collect part items: {e}")
                part_items = []

            try:
                mechanism_layers_raw = self._get_mechanism_layers() or {}
            except Exception as e:
                logging.error(f"[BLUEPRINT] Failed to get mechanism layers: {e}")
                mechanism_layers_raw = {}

            logging.info("[BLUEPRINT] Calculating screen-to-blueprint scale for all mechanisms...")
            try:
                screen_scale_info = self.calculate_screen_to_blueprint_scale()
            except Exception as e:
                logging.error(f"[BLUEPRINT] Error calculating screen scale: {e}")
                screen_scale_info = {
                    "pixels_per_mm": 2.78,
                    "mm_per_pixel": 0.36,
                    "pixels_per_scene_unit": 1.0,
                    "character_height_mm": 300.0,
                    "character_height_pixels": 800,
                    "character_width_pixels": 400,
                    "mechanism_scale_factors": {},
                }

            try:
                mechanism_layers = self.enhance_mechanism_layers_with_scale_info(screen_scale_info)
            except Exception as e:
                logging.error(f"[BLUEPRINT] Error enhancing mechanism layers: {e}")
                mechanism_layers = mechanism_layers_raw
            mechanism_layers = self._fabrication_ready_mechanism_layers(mechanism_layers)

            if not part_items and not mechanism_layers:
                QMessageBox.warning(
                    self._parent,
                    "Blueprint Export",
                    "No mechanisms or character parts available for export.\n"
                    "Please create some mechanisms or load character parts first.",
                )
                return

            for mech_id, mech_data in mechanism_layers.items():
                scale_factor = mech_data.get("total_scale_factor", "N/A")
                logging.info(
                    f"[BLUEPRINT] Enhanced mechanism {mech_id}: scale_factor={scale_factor}"
                )

            output_format = self._blueprint_output_format()
            cut_sheet_name = (
                "current-design-cut-sheets.svg"
                if output_format == "svg"
                else "current-design-cut-sheets.pdf"
            )
            guide_exporter = FabricationAssemblyGuideExporter("fabrication")
            recipe_keys = self._assembly_recipe_keys_for_layers(guide_exporter, mechanism_layers)
            assembly_result = None
            physical_contract = guide_exporter.build_app_physical_contract(
                mechanism_layers,
                recipe_keys=recipe_keys,
            )
            raw_contract_warnings = physical_contract.get("warnings", ())
            contract_warnings = (
                tuple(str(item) for item in raw_contract_warnings)
                if isinstance(raw_contract_warnings, list | tuple)
                else ()
            )
            assembly_contract_ready = bool(recipe_keys) and not contract_warnings

            logging.info(
                "[BLUEPRINT] Package export request: %s parts, %s mechanisms, recipes=%s",
                len(part_items),
                len(mechanism_layers),
                sorted(recipe_keys),
            )

            with telemetry_span(
                "ui.blueprint.export_all",
                unit_system="metric",
                mechanism_count=len(mechanism_layers),
                part_count=len(part_items),
                recipe_count=len(recipe_keys),
                output_format=output_format,
            ) as span:
                export_cut_sheet = getattr(
                    blueprint_manager,
                    "export_blueprint_to_path_result",
                    blueprint_manager.export_blueprint_to_path,
                )
                cut_sheet_result = export_cut_sheet(
                    part_items=part_items,
                    mechanism_layers=mechanism_layers,
                    file_path=output_dir / cut_sheet_name,
                    snapshot_png_bytes=None,
                    unit_system="metric",
                    output_format=output_format,
                )
                cut_sheet_success = bool(getattr(cut_sheet_result, "success", cut_sheet_result))
                actual_cut_sheet_path = getattr(cut_sheet_result, "path", None)
                if actual_cut_sheet_path is not None:
                    actual_cut_sheet_path = Path(actual_cut_sheet_path)
                actual_cut_sheet_format = getattr(cut_sheet_result, "actual_format", None)
                if actual_cut_sheet_format is None and cut_sheet_success:
                    actual_cut_sheet_format = output_format
                actual_cut_sheet_name = (
                    actual_cut_sheet_path.name
                    if actual_cut_sheet_path is not None
                    else cut_sheet_name
                )
                cut_sheet_error = getattr(cut_sheet_result, "error", None)

                assembly_success = True
                if assembly_contract_ready:
                    assembly_result = guide_exporter.export_guides(
                        output_dir,
                        recipe_keys=recipe_keys,
                        app_contract=physical_contract,
                    )
                    assembly_success = bool(
                        assembly_result.pdf_files or assembly_result.fallback_files
                    )
                elif recipe_keys:
                    guide_exporter.export_contract_report(output_dir, physical_contract)
                    logging.warning(
                        "[BLUEPRINT] Board assembly PDFs gated by physical contract warnings: %s",
                        contract_warnings,
                    )
                else:
                    guide_exporter.clear_exported_package(output_dir)
                    if mechanism_layers:
                        logging.warning(
                            "[BLUEPRINT] No matching board assembly recipe for current mechanisms"
                        )

                success = cut_sheet_success and assembly_success
                span.set(status="success" if success else "failure")

            if success:
                if assembly_result is not None:
                    if assembly_result.pdf_files:
                        guide_text = (
                            "Kit parts to cut: assembly/kit-parts-to-cut.pdf\n"
                            "Assembly guide: assembly/assembly-guide.pdf\n"
                            "Physical contract: assembly/physical-contract.json\n"
                            f"Assembly PDFs: {len(assembly_result.pdf_files)}\n"
                        )
                        next_steps_text = (
                            "Use it like a LEGO guide book: print/cut the current-design cut "
                            f"sheet ({str(actual_cut_sheet_format).upper()}) and kit-parts "
                            "PDF first, then follow assembly-guide.pdf one "
                            "step card at a time."
                        )
                    else:
                        guide_text = (
                            "Kit parts to cut: assembly/svg-fallback/parts/\n"
                            "Assembly guide: assembly/svg-fallback/assembly/\n"
                            "Physical contract: assembly/physical-contract.json\n"
                            "Assembly PDFs: none (SVG fallback generated)\n"
                        )
                        next_steps_text = (
                            "PDF rendering was unavailable, so the export generated the same "
                            "LEGO-style guide as SVG fallback files. Open the files under "
                            "assembly/svg-fallback/ and print them from the browser or vector "
                            "editor."
                        )
                    recipe_text = ", ".join(assembly_result.recipe_keys)
                elif recipe_keys and contract_warnings:
                    guide_text = (
                        "Kit parts to cut: gated by physical contract warnings\n"
                        "Assembly guide: gated by physical contract warnings\n"
                        "Physical contract: assembly/physical-contract.json\n"
                        "Assembly PDFs: none\n"
                    )
                    recipe_text = ", ".join(sorted(recipe_keys))
                    next_steps_text = (
                        "Custom / Simulation-only values were exported as a cut sheet, but "
                        "LEGO-style board assembly PDFs were not generated. Open "
                        "physical-contract.json, then convert the design to the nearest "
                        "fabrication-ready kit presets before assembling on the board."
                    )
                else:
                    guide_text = (
                        "Kit parts to cut: not generated (no matching board recipe)\n"
                        "Assembly guide: not generated (no matching board recipe)\n"
                        "Physical contract: not written (no matching board recipe)\n"
                        "Assembly PDFs: none\n"
                    )
                    recipe_text = "none"
                    next_steps_text = (
                        "Only the current-design cut sheet was exported; add a supported "
                        "board mechanism to generate LEGO-style assembly PDFs."
                    )
                warning_count = (
                    len(assembly_result.contract_warnings)
                    if assembly_result is not None
                    else len(contract_warnings)
                )
                logging.info("[BLUEPRINT] Fabrication package export completed: %s", output_dir)
                package_label = (
                    "PDF-first blueprint package exported successfully."
                    if actual_cut_sheet_format == "pdf"
                    else "Blueprint package exported successfully with SVG cut sheet."
                )
                message = (
                    f"{package_label}\n\n"
                    f"Folder: {output_dir}\n"
                    f"Current design cut sheet: {actual_cut_sheet_name}\n"
                    f"{guide_text}"
                    f"Parts: {len(part_items)}\n"
                    f"Mechanisms: {len(mechanism_layers)}\n"
                    f"Selected guide recipes: {recipe_text}\n"
                    f"Physical contract warnings: {warning_count}\n\n"
                    f"{next_steps_text}"
                )
                if warning_count:
                    QMessageBox.warning(
                        self._parent,
                        "Blueprint Package Exported as Custom / Simulation-only",
                        message,
                    )
                else:
                    QMessageBox.information(
                        self._parent,
                        "Blueprint Package Exported",
                        message,
                    )
            else:
                logging.warning("[BLUEPRINT] Fabrication package export failed")
                QMessageBox.warning(
                    self._parent,
                    "Blueprint Package Export Failed",
                    "Blueprint package export failed.\n"
                    f"{cut_sheet_error or 'Check the console for details.'}",
                )

        except ImportError as e:
            logging.error(f"[BLUEPRINT] Blueprint import error: {e}")
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.critical(
                self._parent,
                "Fabrication Export Error",
                "Fabrication export functionality is not available.\n"
                "Some required modules may be missing.\n\n"
                f"Error: {str(e)}",
            )
        except Exception as e:
            logging.error(f"[BLUEPRINT] Fabrication export unexpected error: {e}")
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.critical(
                self._parent,
                "Fabrication Export Error",
                f"An unexpected error occurred while exporting:\n\n{str(e)}",
            )

    def export_mechanism(self, mechanism_id: str, filename: str | None = None) -> None:
        """Export a single mechanism using the composer-backed system.

        If `filename` is provided, saves directly to that SVG path using the
        shared blueprint composer. Otherwise delegates to the manager's dialog.
        """
        try:
            from PyQt6.QtWidgets import (
                QButtonGroup,
                QDialog,
                QDialogButtonBox,
                QLabel,
                QRadioButton,
                QVBoxLayout,
            )

            logging.info(f"[BLUEPRINT] Exporting mechanism {mechanism_id} via composer pipeline")

            mechanism_layers_all = self._get_mechanism_layers()
            layer_data = mechanism_layers_all.get(mechanism_id) if mechanism_layers_all else None
            if not layer_data:
                logging.error(f"[BLUEPRINT] No mechanism found with ID {mechanism_id}")
                return

            # Show unit system selection dialog
            unit_dialog = QDialog(self._parent)
            unit_dialog.setWindowTitle("Select Unit System")
            unit_dialog.setModal(True)
            unit_dialog.resize(300, 150)

            layout = QVBoxLayout()

            title_label = QLabel("Choose the unit system for your mechanism blueprint:")
            title_label.setStyleSheet("font-weight: bold; margin-bottom: 10px;")
            layout.addWidget(title_label)

            unit_group = QButtonGroup()

            metric_radio = QRadioButton("Metric (millimeters)")
            metric_radio.setChecked(True)
            unit_group.addButton(metric_radio, 0)
            layout.addWidget(metric_radio)

            imperial_radio = QRadioButton("Imperial (inches/feet)")
            unit_group.addButton(imperial_radio, 1)
            layout.addWidget(imperial_radio)

            button_box = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            )
            button_box.accepted.connect(unit_dialog.accept)
            button_box.rejected.connect(unit_dialog.reject)
            layout.addWidget(button_box)

            unit_dialog.setLayout(layout)

            if unit_dialog.exec() != QDialog.DialogCode.Accepted:
                return

            unit_system = "imperial" if imperial_radio.isChecked() else "metric"
            unit_label = "Imperial" if unit_system == "imperial" else "Metric"

            from automataii.application.managers import BlueprintExportManager

            blueprint_manager = BlueprintExportManager.get_instance()

            # CRITICAL FIX: Apply scale enhancement before optimization
            logging.info("[BLUEPRINT] Calculating screen-to-blueprint scale...")
            screen_scale_info = self.calculate_screen_to_blueprint_scale()

            mechanism_layers = self.enhance_mechanism_layers_with_scale_info(screen_scale_info)
            # Filter to only the requested mechanism
            mechanism_layers = {mechanism_id: mechanism_layers.get(mechanism_id, layer_data)}

            part_items = self._collect_part_items()

            logging.info(
                f"[BLUEPRINT] Scale enhanced mechanism data: "
                f"total_scale_factor={mechanism_layers[mechanism_id].get('total_scale_factor', 'N/A')}"
            )

            with telemetry_span(
                "ui.blueprint.export_mechanism",
                mechanism_id=mechanism_id,
                unit_system=unit_system,
                mode="file" if filename else "dialog",
                mechanism_count=len(mechanism_layers),
                part_count=len(part_items),
            ) as span:
                if filename:
                    import os

                    os.makedirs(
                        os.path.dirname(filename) if os.path.dirname(filename) else ".",
                        exist_ok=True,
                    )
                    result = blueprint_manager.compose_single_page(
                        part_items=part_items,
                        mechanism_layers=mechanism_layers,
                        snapshot_png_bytes=None,
                        unit_system=unit_system,
                    )
                    with open(filename, "w", encoding="utf-8") as f:
                        f.write(result.svg)

                    span.set(
                        status="success",
                        output_path=filename,
                        width_mm=result.width_mm,
                        height_mm=result.height_mm,
                        item_count=result.item_count,
                    )

                    logging.info(
                        "[BLUEPRINT] Blueprint exported to %s (items=%s, size=%.1fx%.1fmm)",
                        filename,
                        result.item_count,
                        result.width_mm,
                        result.height_mm,
                    )
                    from PyQt6.QtWidgets import QMessageBox

                    QMessageBox.information(
                        self._parent,
                        "Export Successful",
                        f"Blueprint exported successfully:\n{filename}\n\n"
                        f"Mechanism: {layer_data.get('type', 'Unknown')}\n"
                        f"Parts included: {len(part_items)}\n"
                        f"Scale Factor: {mechanism_layers[mechanism_id].get('total_scale_factor', 'N/A'):.3f}\n"
                        f"Units: {unit_label}\n\n"
                        "Blueprint uses measured scene scale and current mechanism details.",
                    )
                else:
                    success = blueprint_manager.export_blueprint(
                        part_items=part_items,
                        mechanism_layers=mechanism_layers,
                        parent_widget=self._parent,
                        single_large_page=True,
                        snapshot_png_bytes=None,
                        unit_system=unit_system,
                        output_format=self._blueprint_output_format(),
                    )

                    span.set(status="success" if success else "failure")

                    if success:
                        logging.info(
                            f"[BLUEPRINT] Blueprint export successful for mechanism {mechanism_id}"
                        )
                    else:
                        logging.warning(
                            f"[BLUEPRINT] Blueprint export failed for mechanism {mechanism_id}"
                        )

        except Exception as e:
            logging.error(
                f"[BLUEPRINT] Failed to export blueprint for mechanism {mechanism_id}: {e}"
            )
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.critical(
                self._parent, "Export Failed", f"Failed to export blueprint:\n{str(e)}"
            )

    def _blueprint_output_format(self) -> str:
        fmt = str(self._get_blueprint_export_format()).strip().lower()
        return fmt if fmt in {"pdf", "svg"} else "pdf"

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
        dimensions_text += 'Printable on: Letter size (8.5" x 11")\n\n'

        if mech_type == "4_bar_linkage":
            L1 = params.get("L1", 0) * scale_factor
            L2 = params.get("L2", 0) * scale_factor
            L3 = params.get("L3", 0) * scale_factor
            L4 = params.get("L4", 0) * scale_factor

            dimensions_text += "Link Lengths (mm):\n"
            dimensions_text += f'  Ground Link (L1): {L1:.1f} mm ({L1 / mm_per_inch:.2f}")\n'
            dimensions_text += f'  Crank (L2): {L2:.1f} mm ({L2 / mm_per_inch:.2f}")\n'
            dimensions_text += f'  Coupler (L3): {L3:.1f} mm ({L3 / mm_per_inch:.2f}")\n'
            dimensions_text += f'  Rocker (L4): {L4:.1f} mm ({L4 / mm_per_inch:.2f}")\n'

        elif mech_type == "cam":
            base_radius = params.get("base_radius", 0) * scale_factor
            eccentricity = params.get("eccentricity", 0) * scale_factor
            rod_length = params.get("follower_rod_length", 0) * scale_factor

            dimensions_text += "Cam Dimensions (mm):\n"
            dimensions_text += (
                f'  Base Radius: {base_radius:.1f} mm ({base_radius / mm_per_inch:.2f}")\n'
            )
            dimensions_text += (
                f'  Eccentricity: {eccentricity:.1f} mm ({eccentricity / mm_per_inch:.2f}")\n'
            )
            dimensions_text += f"  Max Radius: {base_radius + eccentricity:.1f} mm\n"
            dimensions_text += f"  Min Radius: {base_radius - eccentricity:.1f} mm\n"
            dimensions_text += (
                f'  Follower Rod Length: {rod_length:.1f} mm ({rod_length / mm_per_inch:.2f}")\n'
            )

        elif mech_type == "gear":
            r1 = (
                _finite_float(_first_value(params, "r1", "gear1_radius", default=0.0))
                * scale_factor
            )
            r2 = (
                _finite_float(_first_value(params, "r2", "gear2_radius", default=0.0))
                * scale_factor
            )
            profile = physical_profile_from_params(params)
            clearance = gear_clearance_from_params(params, profile=profile) * scale_factor

            dimensions_text += "Gear Dimensions (mm):\n"
            dimensions_text += f'  Gear 1 Radius: {r1:.1f} mm ({r1 / mm_per_inch:.2f}")\n'
            dimensions_text += f'  Gear 2 Radius: {r2:.1f} mm ({r2 / mm_per_inch:.2f}")\n'
            dimensions_text += f"  Center Distance: {gear_center_distance(r1, r2, clearance, profile=profile):.1f} mm\n"
            dimensions_text += f"  Gear Ratio: {r2 / r1:.2f}:1\n" if r1 else "  Gear Ratio: n/a\n"

        elif mech_type == "planetary_gear":
            r_sun = params.get("r_sun", 0) * scale_factor
            r_planet = params.get("r_planet", 0) * scale_factor
            arm_length = params.get("arm_length", 0) * scale_factor

            dimensions_text += "Planetary Gear Dimensions (mm):\n"
            dimensions_text += f'  Sun Gear Radius: {r_sun:.1f} mm ({r_sun / mm_per_inch:.2f}")\n'
            dimensions_text += (
                f'  Planet Gear Radius: {r_planet:.1f} mm ({r_planet / mm_per_inch:.2f}")\n'
            )
            dimensions_text += (
                f'  Arm Length: {arm_length:.1f} mm ({arm_length / mm_per_inch:.2f}")\n'
            )
            dimensions_text += f"  Orbital Radius: {r_sun + r_planet:.1f} mm\n"

        msg_box = QMessageBox()
        msg_box.setWindowTitle("Mechanism Dimensions")
        msg_box.setText(dimensions_text)
        msg_box.setDetailedText(
            self.generate_blueprint_instructions(mech_type, params, scale_factor)
        )
        msg_box.setIcon(QMessageBox.Icon.Information)
        msg_box.exec()

        logging.info(f"[DIMENSIONS] {dimensions_text}")

    def show_current_mechanism_dimensions(self) -> None:
        """Show dimensions for an arbitrary available mechanism (first one)."""
        mechanism_layers = self._get_mechanism_layers()
        if not mechanism_layers:
            QMessageBox.warning(
                self._parent, "No Mechanism", "No mechanism available to show dimensions."
            )
            return
        mechanism_id = next(iter(mechanism_layers.keys()))
        self.show_mechanism_dimensions(mechanism_id)

    def calculate_screen_to_blueprint_scale(self) -> dict[str, Any]:
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

            mechanism_scale_factors: dict[str, float] = {}
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
                        mechanism_scale_factors[mech_id] = (
                            scene_distance / 100.0 if scene_distance > 0 else 1.0
                        )
                    except Exception:
                        mechanism_scale_factors[mech_id] = 1.0

            scale_info: dict[str, Any] = {
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

    def enhance_mechanism_layers_with_scale_info(
        self, screen_scale_info: dict[str, Any]
    ) -> dict[str, Any]:
        """Attach scale info and real-world params to each mechanism layer."""
        enhanced_layers: dict[str, Any] = {}

        try:
            mechanism_layers = self._get_mechanism_layers() or {}
            for mech_id, layer_data in mechanism_layers.items():
                enhanced_layer = layer_data.copy()
                enhanced_layer["screen_scale_info"] = screen_scale_info

                # Safely get mechanism_scale_factors with fallback
                mechanism_scale_factors = screen_scale_info.get("mechanism_scale_factors", {})
                mech_scale_factor = mechanism_scale_factors.get(mech_id, 1.0)
                enhanced_layer["mechanism_to_screen_scale"] = mech_scale_factor
                enhanced_layer["screen_to_blueprint_scale"] = screen_scale_info.get(
                    "mm_per_pixel", 0.36
                )
                enhanced_layer["total_scale_factor"] = mech_scale_factor * screen_scale_info.get(
                    "mm_per_pixel", 0.36
                )

                if "params" in enhanced_layer:
                    real_world_params = self.calculate_real_world_mechanism_params(
                        enhanced_layer["params"],
                        enhanced_layer["total_scale_factor"],
                        enhanced_layer.get("type", "unknown"),
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

    def calculate_real_world_mechanism_params(
        self, params: dict[str, Any], scale_factor: float, mech_type: str
    ) -> dict[str, Any]:
        """Convert mechanism params to mm using total scale factor."""
        real_world_params: dict[str, Any] = {}
        try:
            if mech_type == "4_bar_linkage":
                for param_name in ["l1", "l2", "l3", "l4"]:
                    if param_name in params:
                        real_world_params[f"{param_name}_mm"] = params[param_name] * scale_factor
                for param_name in ["coupler_point_x", "coupler_point_y"]:
                    if param_name in params:
                        real_world_params[f"{param_name}_mm"] = params[param_name] * scale_factor
            elif mech_type == "cam":
                for param_name in ["base_radius", "eccentricity", "follower_rod_length"]:
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

    def generate_blueprint_instructions(
        self, mech_type: str, params: dict[str, Any], scale_factor: float
    ) -> str:
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
            instructions += f'   - Ground link: {L1:.1f} mm ({L1 / mm_per_inch:.2f}")\n'
            instructions += f'   - Crank: {L2:.1f} mm ({L2 / mm_per_inch:.2f}")\n'
            instructions += f'   - Coupler: {L3:.1f} mm ({L3 / mm_per_inch:.2f}")\n'
            instructions += f'   - Rocker: {L4:.1f} mm ({L4 / mm_per_inch:.2f}")\n\n'
            instructions += "2. Drill holes at both ends of each bar (5-6mm diameter)\n"
            instructions += "3. Mount ground link to base plate\n"
            instructions += "4. Connect crank to left ground pivot\n"
            instructions += "5. Connect rocker to right ground pivot\n"
            instructions += "6. Connect coupler between crank and rocker\n"
            instructions += "7. Ensure all joints move freely\n"
        elif mech_type == "cam":
            base_radius = (
                _finite_float(
                    _first_value(params, "base_radius", "cam_radius", "base_radius_mm"),
                    0.0,
                )
                * scale_factor
            )
            eccentricity = (
                _finite_float(
                    _first_value(
                        params,
                        "eccentricity",
                        "cam_offset",
                        "lift_mm",
                        "eccentricity_mm",
                    ),
                    0.0,
                )
                * scale_factor
            )
            rod_length = (
                _finite_float(
                    _first_value(params, "follower_rod_length", "follower_length"),
                    0.0,
                )
                * scale_factor
            )
            instructions += "Materials Needed:\n"
            instructions += "- Cam material (wood, acrylic, or metal)\n"
            instructions += (
                f'- Follower rod: {rod_length:.1f} mm ({rod_length / mm_per_inch:.2f}")\n'
            )
            instructions += "- Linear bearing or guide\n"
            instructions += "- Rotation shaft and bearing\n\n"
            instructions += "Cam Profile Creation:\n"
            instructions += "1. Use the generated CAM profile from the blueprint/SVG export:\n"
            instructions += (
                f"   - Base radius/reference: {base_radius:.1f} mm "
                f'({base_radius / mm_per_inch:.2f}")\n'
            )
            instructions += (
                f"   - Lift/eccentricity input: {eccentricity:.1f} mm "
                f'({eccentricity / mm_per_inch:.2f}")\n'
            )
            if "cam_lobes" in params or "profile_harmonic" in params:
                lobes = max(1, int(_finite_float(params.get("cam_lobes"), 1.0)))
                harmonic = _finite_float(params.get("profile_harmonic"), math.nan)
                instructions += f"   - Lobes: {lobes}\n"
                if math.isfinite(harmonic):
                    instructions += f"   - Harmonic: {harmonic:.2f}\n"
            instructions += (
                "   - Follow the plotted outline; do not approximate a generic profile.\n"
            )
            instructions += "2. Mark center hole for shaft\n"
            instructions += "3. Cut cam profile carefully\n"
            instructions += "4. Smooth edges for proper follower contact\n"
            instructions += f"5. Install follower guide {rod_length:.1f} mm above cam center\n"
        elif mech_type == "gear":
            r1 = (
                _finite_float(_first_value(params, "r1", "gear1_radius", default=0.0))
                * scale_factor
            )
            r2 = (
                _finite_float(_first_value(params, "r2", "gear2_radius", default=0.0))
                * scale_factor
            )
            profile = physical_profile_from_params(params)
            grid_enabled = grid_enabled_from_params(params)
            teeth1 = gear_teeth_from_params(
                params,
                ("gear1_teeth",),
                ("r1", "gear1_radius"),
                16,
                enabled=grid_enabled,
                profile=profile,
            )
            teeth2 = gear_teeth_from_params(
                params,
                ("gear2_teeth",),
                ("r2", "gear2_radius"),
                24,
                enabled=grid_enabled,
                profile=profile,
            )
            clearance = gear_clearance_from_params(params, profile=profile) * scale_factor
            instructions += "Materials Needed:\n"
            instructions += "- 2 gears or gear blanks\n"
            instructions += "- 2 shafts and bearings\n"
            instructions += "- Mounting plate\n\n"
            instructions += "Gear Specifications:\n"
            instructions += "Gear 1:\n"
            instructions += f"  - Pitch diameter: {2 * r1:.1f} mm\n"
            instructions += f"  - Estimated teeth: {teeth1}\n"
            instructions += "Gear 2:\n"
            instructions += f"  - Pitch diameter: {2 * r2:.1f} mm\n"
            instructions += f"  - Estimated teeth: {teeth2}\n"
            instructions += f"Center distance: {gear_center_distance(r1, r2, clearance, profile=profile):.1f} mm\n\n"
            instructions += "Assembly:\n"
            instructions += "1. Mount bearings at specified center distance\n"
            instructions += "2. Install gears on shafts\n"
            instructions += "3. Ensure proper meshing without binding\n"

        return instructions

    # ---------- Internal helpers ----------

    def _collect_part_items(self) -> list[Any]:
        part_items: list[Any] = []
        try:
            current_items = self._get_current_editor_items() or {}
            for part_name, part_item in current_items.items():
                try:
                    if part_item and hasattr(part_item, "shape") and callable(part_item.shape):
                        # Test that shape() doesn't crash
                        _ = part_item.shape()
                        part_items.append(part_item)
                        logging.debug(f"[BLUEPRINT] Added part: {part_name}")
                except Exception as e:
                    logging.warning(f"[BLUEPRINT] Skipping invalid part {part_name}: {e}")
                    continue
        except Exception as e:
            logging.error(f"[BLUEPRINT] Error collecting part items: {e}")
        return part_items
