"""
Constraint Solver - Handle movement constraint calculations.

Extracted from ParametricHandle. Provides constraint validation and
position adjustment for parametric handles.

Design Pattern: Strategy (constraint-type-specific calculations)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from PyQt6.QtCore import QPointF


@dataclass(frozen=True)
class ConstraintResult:
    """Result of constraint application."""

    position: QPointF
    was_constrained: bool
    constraint_type: str | None = None


class ConstraintSolver:
    """
    Solves movement constraints for parametric handles.

    Responsibilities:
    - Apply bounding box constraints
    - Apply axis locking constraints
    - Apply grid snapping
    - Apply distance/radial constraints
    - Validate constraint combinations

    Time Complexity: O(1) per constraint application
    """

    def apply_constraints(
        self,
        position: QPointF,
        constraints: dict[str, Any],
    ) -> ConstraintResult:
        """
        Apply all constraints to a position.

        Args:
            position: Input position
            constraints: Constraint dictionary

        Returns:
            ConstraintResult with adjusted position

        Time Complexity: O(c) where c = number of constraints
        """
        x, y = position.x(), position.y()
        was_constrained = False
        applied_type = None

        # 1. Bounding box constraints (highest priority)
        x, y, constrained = self._apply_bounds(x, y, constraints)
        if constrained:
            was_constrained = True
            applied_type = "bounds"

        # 2. Fixed axis constraints
        x, y, constrained = self._apply_fixed_axis(x, y, constraints)
        if constrained:
            was_constrained = True
            applied_type = "fixed_axis"

        # 3. Grid snapping
        x, y, constrained = self._apply_grid_snap(x, y, constraints)
        if constrained:
            was_constrained = True
            applied_type = "grid"

        # 4. Distance constraints
        x, y, constrained = self._apply_distance_constraint(x, y, constraints)
        if constrained:
            was_constrained = True
            applied_type = "distance"

        # 5. Radial constraints
        x, y, constrained = self._apply_radial_constraint(x, y, constraints)
        if constrained:
            was_constrained = True
            applied_type = "radial"

        return ConstraintResult(
            position=QPointF(x, y),
            was_constrained=was_constrained,
            constraint_type=applied_type,
        )

    def _apply_bounds(
        self,
        x: float,
        y: float,
        constraints: dict[str, Any],
    ) -> tuple[float, float, bool]:
        """Apply bounding box constraints."""
        constrained = False

        if "min_x" in constraints and x < constraints["min_x"]:
            x = constraints["min_x"]
            constrained = True
        if "max_x" in constraints and x > constraints["max_x"]:
            x = constraints["max_x"]
            constrained = True
        if "min_y" in constraints and y < constraints["min_y"]:
            y = constraints["min_y"]
            constrained = True
        if "max_y" in constraints and y > constraints["max_y"]:
            y = constraints["max_y"]
            constrained = True

        return x, y, constrained

    def _apply_fixed_axis(
        self,
        x: float,
        y: float,
        constraints: dict[str, Any],
    ) -> tuple[float, float, bool]:
        """Apply fixed axis constraints."""
        constrained = False

        if "fixed_x" in constraints:
            try:
                x = float(constraints["fixed_x"])
                constrained = True
            except (ValueError, TypeError):
                pass

        if "fixed_y" in constraints:
            try:
                y = float(constraints["fixed_y"])
                constrained = True
            except (ValueError, TypeError):
                pass

        return x, y, constrained

    def _apply_grid_snap(
        self,
        x: float,
        y: float,
        constraints: dict[str, Any],
    ) -> tuple[float, float, bool]:
        """Apply grid snapping."""
        if "snap_grid" not in constraints:
            return x, y, False

        grid_size = constraints["snap_grid"]
        if grid_size <= 0:
            return x, y, False

        x = round(x / grid_size) * grid_size
        y = round(y / grid_size) * grid_size

        return x, y, True

    def _apply_distance_constraint(
        self,
        x: float,
        y: float,
        constraints: dict[str, Any],
    ) -> tuple[float, float, bool]:
        """Apply fixed distance from anchor constraint."""
        if "fixed_distance" not in constraints:
            return x, y, False

        anchor = constraints["fixed_distance"].get("anchor")
        distance = constraints["fixed_distance"].get("distance")

        if anchor is None or distance is None:
            return x, y, False

        dx = x - anchor.x()
        dy = y - anchor.y()
        current_dist = math.sqrt(dx * dx + dy * dy)

        if current_dist < 1e-10:
            # At anchor point, maintain previous direction or default
            return anchor.x() + distance, anchor.y(), True

        scale = distance / current_dist
        x = anchor.x() + dx * scale
        y = anchor.y() + dy * scale

        return x, y, True

    def _apply_radial_constraint(
        self,
        x: float,
        y: float,
        constraints: dict[str, Any],
    ) -> tuple[float, float, bool]:
        """Apply radial constraint around a center point."""
        if "center" not in constraints:
            return x, y, False

        has_radial = (
            "min_radius" in constraints or "max_radius" in constraints or "angle" in constraints
        )
        if not has_radial:
            return x, y, False

        center = constraints["center"]
        dx = x - center.x()
        dy = y - center.y()
        r = math.sqrt(dx * dx + dy * dy)

        # Clamp radius
        r_min = constraints.get("min_radius", 0.0)
        r_max = constraints.get("max_radius", float("inf"))
        r = max(r_min, min(r_max, r if r > 0 else r_min))

        # Lock angle if provided
        if "angle" in constraints:
            ang_deg = float(constraints["angle"])
            ang = math.radians(ang_deg)
            x = center.x() + r * math.cos(ang)
            y = center.y() + r * math.sin(ang)
        else:
            if dx != 0 or dy != 0:
                ang = math.atan2(dy, dx)
                x = center.x() + r * math.cos(ang)
                y = center.y() + r * math.sin(ang)

        return x, y, True

    def validate_constraints(
        self,
        constraints: dict[str, Any],
    ) -> tuple[bool, str]:
        """
        Validate constraint configuration.

        Args:
            constraints: Constraint dictionary

        Returns:
            Tuple of (is_valid, error_message)

        Time Complexity: O(c)
        """
        # Check for conflicting constraints
        if "fixed_x" in constraints and "min_x" in constraints:
            if constraints["fixed_x"] < constraints["min_x"]:
                return False, "fixed_x is less than min_x"

        if "fixed_x" in constraints and "max_x" in constraints:
            if constraints["fixed_x"] > constraints["max_x"]:
                return False, "fixed_x is greater than max_x"

        if "fixed_y" in constraints and "min_y" in constraints:
            if constraints["fixed_y"] < constraints["min_y"]:
                return False, "fixed_y is less than min_y"

        if "fixed_y" in constraints and "max_y" in constraints:
            if constraints["fixed_y"] > constraints["max_y"]:
                return False, "fixed_y is greater than max_y"

        # Validate radial constraints
        if "min_radius" in constraints and "max_radius" in constraints:
            if constraints["min_radius"] > constraints["max_radius"]:
                return False, "min_radius is greater than max_radius"

        # Validate grid snap
        if "snap_grid" in constraints and constraints["snap_grid"] <= 0:
            return False, "snap_grid must be positive"

        return True, ""

    def create_bounds_constraint(
        self,
        min_x: float | None = None,
        max_x: float | None = None,
        min_y: float | None = None,
        max_y: float | None = None,
    ) -> dict[str, Any]:
        """Create a bounds constraint dictionary."""
        constraints = {}
        if min_x is not None:
            constraints["min_x"] = min_x
        if max_x is not None:
            constraints["max_x"] = max_x
        if min_y is not None:
            constraints["min_y"] = min_y
        if max_y is not None:
            constraints["max_y"] = max_y
        return constraints

    def create_radial_constraint(
        self,
        center: QPointF,
        min_radius: float | None = None,
        max_radius: float | None = None,
        fixed_angle: float | None = None,
    ) -> dict[str, Any]:
        """Create a radial constraint dictionary."""
        constraints = {"center": center}
        if min_radius is not None:
            constraints["min_radius"] = min_radius
        if max_radius is not None:
            constraints["max_radius"] = max_radius
        if fixed_angle is not None:
            constraints["angle"] = fixed_angle
        return constraints

    def create_distance_constraint(
        self,
        anchor: QPointF,
        distance: float,
    ) -> dict[str, Any]:
        """Create a fixed distance constraint dictionary."""
        return {
            "fixed_distance": {
                "anchor": anchor,
                "distance": distance,
            }
        }
