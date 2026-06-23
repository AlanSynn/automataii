"""
Recommendation Handler - Handle mechanism recommendations and selection.

Extracted from MechanismDesignTab. Manages the mechanism recommendation
dialog, preview rendering, and selection workflow.

Design Pattern: Handler (recommendation event handling)
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QPainterPath

from automataii.domain.animation.part_definitions import BODY_PARTS

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QWidget


class RecommendationHandler:
    """
    Handles mechanism recommendation workflow.

    Responsibilities:
    - Extract path points from QPainterPath for recommendation
    - Process recommendation dialog results
    - Generate mechanism from candidate data
    - Setup mechanism layer data

    Time Complexity: O(p) where p = number of path points
    """

    def __init__(
        self,
        get_parts_data: Callable[[], dict[str, Any]],
        get_path_data: Callable[[], dict[str, QPainterPath]],
        get_character_position: Callable[[], tuple[float, float] | None],
        add_mechanism_layer: Callable[[str, dict], None],
        on_mechanism_added: Callable[[str, dict], None] | None = None,
    ) -> None:
        """
        Initialize handler.

        Args:
            get_parts_data: Callback to get parts data
            get_path_data: Callback to get path data
            get_character_position: Callback to get character position
            add_mechanism_layer: Callback to add mechanism layer
            on_mechanism_added: Optional callback when mechanism is added
        """
        self._get_parts_data = get_parts_data
        self._get_path_data = get_path_data
        self._get_character_position = get_character_position
        self._add_mechanism_layer = add_mechanism_layer
        self._on_mechanism_added = on_mechanism_added

    def extract_paths_for_recommendation(
        self,
    ) -> dict[str, list[tuple[float, float]]]:
        """
        Extract path points from QPainterPath for recommendation service.

        Returns:
            Dictionary mapping part names to list of (x, y) points

        Time Complexity: O(p * n) where p = parts, n = points per path
        """
        paths_dict = {}
        path_data = self._get_path_data()

        for part_name, painter_path in path_data.items():
            if painter_path and not painter_path.isEmpty():
                points = self._qpainterpath_to_points(painter_path)
                if points:
                    paths_dict[part_name] = points

        return paths_dict

    def _qpainterpath_to_points(
        self,
        path: QPainterPath,
        num_samples: int = 100,
    ) -> list[tuple[float, float]]:
        """
        Convert QPainterPath to list of points.

        Args:
            path: QPainterPath to convert
            num_samples: Number of sample points

        Returns:
            List of (x, y) tuples

        Time Complexity: O(n) where n = num_samples
        """
        points = []
        length = path.length()

        if length <= 0:
            return points

        for i in range(num_samples + 1):
            t = i / num_samples
            percent = path.percentAtLength(t * length)
            point = path.pointAtPercent(percent)
            points.append((point.x(), point.y()))

        return points

    def get_recommendation_context(
        self,
    ) -> dict[str, Any]:
        """
        Build context data for recommendation dialog.

        Returns:
            Context dictionary with paths, parts, and position info

        Time Complexity: O(p * n)
        """
        return {
            "paths": self.extract_paths_for_recommendation(),
            "parts_data": self._get_parts_data(),
            "character_position": self._get_character_position(),
        }

    def process_recommendation_selection(
        self,
        mechanism_data: dict[str, Any],
        parent_widget: QWidget | None = None,
    ) -> dict[str, Any] | None:
        """
        Process selected mechanism recommendation.

        Args:
            mechanism_data: Selected mechanism data from dialog
            parent_widget: Parent widget for dialogs

        Returns:
            Processed layer data or None if processing failed

        Time Complexity: O(1)
        """
        try:
            mechanism_type = mechanism_data.get("type", "unknown")
            part_name = mechanism_data.get("part_name", "unknown")
            params = mechanism_data.get("params", {})

            # Get target path for this part
            path_data = self._get_path_data()
            target_path = path_data.get(part_name)

            # Get anchor position
            parts_data = self._get_parts_data()
            part_info = parts_data.get(part_name)

            anchor_position = None
            anchor_joint_id = None

            if part_info:
                anchor_joint_id = getattr(part_info, "anchor_joint_id", None) or BODY_PARTS.get(
                    part_name, {}
                ).get("anchor_joint")
                anchor_pos = getattr(part_info, "anchor_position", None)
                if anchor_pos:
                    if isinstance(anchor_pos, QPointF):
                        anchor_position = anchor_pos
                    elif isinstance(anchor_pos, list | tuple) and len(anchor_pos) >= 2:
                        anchor_position = QPointF(anchor_pos[0], anchor_pos[1])

            # Build layer data
            layer_data = self._build_layer_data(
                mechanism_type=mechanism_type,
                part_name=part_name,
                params=params,
                anchor_position=anchor_position,
                anchor_joint_id=anchor_joint_id,
                target_path=target_path,
                mechanism_data=mechanism_data,
            )

            return layer_data

        except Exception:
            return None

    def _build_layer_data(
        self,
        mechanism_type: str,
        part_name: str,
        params: dict,
        anchor_position: QPointF | None,
        anchor_joint_id: str | None,
        target_path: QPainterPath | None,
        mechanism_data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Build layer data for a mechanism.

        Args:
            mechanism_type: Type of mechanism
            part_name: Associated part name
            params: Mechanism parameters
            anchor_position: Anchor position in scene
            anchor_joint_id: Associated joint ID
            target_path: Target motion path
            mechanism_data: Full mechanism data from recommendation

        Returns:
            Layer data dictionary

        Time Complexity: O(1)
        """
        layer_data = {
            "type": mechanism_type,
            "part_name": part_name,
            "params": params.copy(),
            "anchor_joint_id": anchor_joint_id,
            "visual_items": [],
            "enabled": True,
        }

        # Add anchor position
        if anchor_position:
            layer_data["anchor_position"] = anchor_position
            layer_data["anchor_scene_x"] = anchor_position.x()
            layer_data["anchor_scene_y"] = anchor_position.y()

        # Add key points from mechanism data
        if "key_points" in mechanism_data:
            layer_data["key_points"] = mechanism_data["key_points"].copy()

        # Add simulation data if available
        if "full_simulation_data" in mechanism_data:
            layer_data["full_simulation_data"] = mechanism_data["full_simulation_data"]

        # Add scale and rotation
        layer_data["scale"] = mechanism_data.get("scale", 1.0)
        layer_data["rotation"] = mechanism_data.get("rotation", 0.0)

        # Add target path points
        if target_path:
            layer_data["target_path"] = self._qpainterpath_to_points(target_path)

        return layer_data

    def generate_mechanism_from_candidate(
        self,
        candidate_data: dict[str, Any],
        mechanism_service: Any | None = None,
    ) -> dict[str, Any] | None:
        """
        Generate a mechanism from recommendation candidate data.

        Args:
            candidate_data: Candidate mechanism data
            mechanism_service: Optional mechanism generation service

        Returns:
            Generated mechanism data or None

        Time Complexity: O(n) for simulation generation
        """
        try:
            mechanism_type = candidate_data.get("type")
            params = candidate_data.get("params", {})
            part_name = candidate_data.get("part_name")

            if not mechanism_type or not part_name:
                return None

            # Get parts data for anchor info
            parts_data = self._get_parts_data()
            part_info = parts_data.get(part_name)

            # Build basic mechanism data
            mechanism_data = {
                "type": mechanism_type,
                "part_name": part_name,
                "params": params.copy(),
            }

            # Add anchor information
            if part_info:
                anchor_joint_id = getattr(part_info, "anchor_joint_id", None) or BODY_PARTS.get(
                    part_name, {}
                ).get("anchor_joint")
                anchor_pos = getattr(part_info, "anchor_position", None)

                mechanism_data["anchor_joint_id"] = anchor_joint_id

                if anchor_pos:
                    if isinstance(anchor_pos, QPointF):
                        mechanism_data["anchor_position"] = anchor_pos
                        mechanism_data["anchor_scene_x"] = anchor_pos.x()
                        mechanism_data["anchor_scene_y"] = anchor_pos.y()
                    elif isinstance(anchor_pos, list | tuple) and len(anchor_pos) >= 2:
                        mechanism_data["anchor_position"] = QPointF(anchor_pos[0], anchor_pos[1])
                        mechanism_data["anchor_scene_x"] = anchor_pos[0]
                        mechanism_data["anchor_scene_y"] = anchor_pos[1]

            # Generate simulation data if service available
            if mechanism_service:
                try:
                    simulation_result = mechanism_service.generate_mechanism(
                        mechanism_type=mechanism_type,
                        params=params,
                    )
                    if simulation_result:
                        mechanism_data["full_simulation_data"] = simulation_result
                        mechanism_data["key_points"] = self._extract_key_points(
                            simulation_result, mechanism_type
                        )
                except Exception:
                    logging.debug("Suppressed exception", exc_info=True)

            # Add candidate-specific data
            if "key_points" in candidate_data:
                mechanism_data["key_points"] = candidate_data["key_points"]
            if "scale" in candidate_data:
                mechanism_data["scale"] = candidate_data["scale"]
            if "rotation" in candidate_data:
                mechanism_data["rotation"] = candidate_data["rotation"]

            return mechanism_data

        except Exception:
            return None

    def _extract_key_points(
        self,
        simulation_data: dict,
        mechanism_type: str,
    ) -> dict[str, list[float]]:
        """
        Extract key points from simulation data.

        Args:
            simulation_data: Full simulation data
            mechanism_type: Type of mechanism

        Returns:
            Dictionary of key point positions

        Time Complexity: O(1)
        """
        key_points = {}

        try:
            if mechanism_type == "4_bar_linkage" and "joint_positions" in simulation_data:
                joint_pos = simulation_data["joint_positions"]
                if "p1_positions" in joint_pos and len(joint_pos["p1_positions"]) > 0:
                    key_points["ground_pivot_1"] = list(joint_pos["p1_positions"][0])
                if "p2_positions" in joint_pos and len(joint_pos["p2_positions"]) > 0:
                    key_points["ground_pivot_2"] = list(joint_pos["p2_positions"][0])
                if "p3_positions" in joint_pos and len(joint_pos["p3_positions"]) > 0:
                    key_points["crank_end"] = list(joint_pos["p3_positions"][0])
                if "p4_positions" in joint_pos and len(joint_pos["p4_positions"]) > 0:
                    key_points["rocker_end"] = list(joint_pos["p4_positions"][0])

            elif mechanism_type == "cam" and "cam_data" in simulation_data:
                cam_data = simulation_data["cam_data"]
                if "cam_centers" in cam_data and len(cam_data["cam_centers"]) > 0:
                    key_points["cam_center"] = list(cam_data["cam_centers"][0])

            elif mechanism_type in ["gear", "planetary_gear"]:
                if "gear_positions" in simulation_data:
                    gear_pos = simulation_data["gear_positions"]
                    if "sun_centers" in gear_pos and len(gear_pos["sun_centers"]) > 0:
                        key_points["sun_center"] = list(gear_pos["sun_centers"][0])
                    if "planet_centers" in gear_pos and len(gear_pos["planet_centers"]) > 0:
                        key_points["planet_center"] = list(gear_pos["planet_centers"][0])

        except (KeyError, IndexError, TypeError):
            pass

        return key_points

    def add_mechanism_from_data(
        self,
        mechanism_id: str,
        layer_data: dict[str, Any],
    ) -> bool:
        """
        Add mechanism to the tab using layer data.

        Args:
            mechanism_id: Unique mechanism identifier
            layer_data: Mechanism layer data

        Returns:
            True if mechanism was added successfully

        Time Complexity: O(1)
        """
        try:
            self._add_mechanism_layer(mechanism_id, layer_data)

            if self._on_mechanism_added:
                self._on_mechanism_added(mechanism_id, layer_data)

            return True

        except Exception:
            return False

    def validate_mechanism_data(
        self,
        mechanism_data: dict[str, Any],
    ) -> tuple[bool, str]:
        """
        Validate mechanism data before adding.

        Args:
            mechanism_data: Mechanism data to validate

        Returns:
            Tuple of (is_valid, error_message)

        Time Complexity: O(1)
        """
        if not mechanism_data:
            return False, "No mechanism data provided"

        mechanism_type = mechanism_data.get("type")
        if not mechanism_type:
            return False, "Missing mechanism type"

        part_name = mechanism_data.get("part_name")
        if not part_name:
            return False, "Missing part name"

        params = mechanism_data.get("params", {})

        # Type-specific validation
        if mechanism_type == "4_bar_linkage":
            required_params = ["l2", "l3", "l4"]
            for param in required_params:
                if param not in params:
                    return False, f"Missing required parameter: {param}"

        elif mechanism_type == "cam":
            if "base_radius" not in params and "eccentricity" not in params:
                return False, "Missing cam parameters"

        elif mechanism_type in ["gear", "planetary_gear"]:
            if mechanism_type == "gear":
                if "r1" not in params or "r2" not in params:
                    return False, "Missing gear radii"
            else:
                if "r_sun" not in params or "r_planet" not in params:
                    return False, "Missing planetary gear radii"

        return True, ""
