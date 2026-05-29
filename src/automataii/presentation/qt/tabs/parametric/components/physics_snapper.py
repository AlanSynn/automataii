"""
Physics Snapper - Physics constraint enforcement.

Extracted from ParametricEditingManager. Handles enforcing
physical constraints like Grashof condition and gear meshing.

Design Pattern: Service (constraint validation and correction)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np

from automataii.presentation.qt.mechanism_parameter_utils import positive_finite_float


@dataclass
class SnapResult:
    """Result of a physics snap operation."""

    success: bool
    modified: bool
    message: str
    corrected_params: dict[str, Any] | None = None


class PhysicsSnapper:
    """
    Enforces physics constraints on mechanism parameters.

    Responsibilities:
    - Enforce Grashof condition for 4-bar linkages
    - Enforce gear meshing constraints
    - Enforce cam-follower contact constraints

    Time Complexity: O(1) for all operations (pure geometric calculations)
    """

    # Snap modes
    SNAP_NONE = "none"
    SNAP_SOFT = "soft"  # Allow some violation
    SNAP_HARD = "hard"  # Strictly enforce

    def __init__(self) -> None:
        """Initialize physics snapper."""
        self._snap_mode: str = self.SNAP_SOFT

    @property
    def snap_mode(self) -> str:
        """Get current snap mode."""
        return self._snap_mode

    @snap_mode.setter
    def snap_mode(self, mode: str) -> None:
        """Set snap mode."""
        if mode in (self.SNAP_NONE, self.SNAP_SOFT, self.SNAP_HARD):
            self._snap_mode = mode

    def enforce_grashof(
        self,
        layer_data: dict[str, Any],
    ) -> SnapResult:
        """
        Enforce Grashof condition for 4-bar linkage.

        Grashof condition: shortest + longest <= sum of other two
        This ensures at least one link can rotate fully.

        Args:
            layer_data: Mechanism layer data with parameters

        Returns:
            SnapResult with corrected parameters if needed
        """
        if self._snap_mode == self.SNAP_NONE:
            return SnapResult(success=True, modified=False, message="Snap disabled")

        params = layer_data.get("parameters", {})

        try:
            # Get joint positions
            O0 = np.array(params.get("O0", [0, 0]), dtype=float)
            O1 = np.array(params.get("O1", [100, 0]), dtype=float)
            A = np.array(params.get("A", [30, -50]), dtype=float)
            B = np.array(params.get("B", [70, -50]), dtype=float)

            # Calculate link lengths
            L1 = float(np.linalg.norm(A - O0))  # Crank
            L2 = float(np.linalg.norm(B - A))  # Coupler
            L3 = float(np.linalg.norm(B - O1))  # Rocker
            L4 = float(np.linalg.norm(O1 - O0))  # Ground

            lengths = sorted([L1, L2, L3, L4])
            shortest = lengths[0]
            longest = lengths[3]
            others_sum = lengths[1] + lengths[2]

            # Check Grashof condition
            if shortest + longest <= others_sum:
                return SnapResult(
                    success=True,
                    modified=False,
                    message="Grashof condition satisfied",
                )

            # Need to correct - scale the shortest link up
            violation = (shortest + longest) - others_sum
            logging.info(f"Grashof violation: {violation:.2f}")

            if self._snap_mode == self.SNAP_SOFT:
                # Allow small violations
                if violation < 5.0:  # 5 unit tolerance
                    return SnapResult(
                        success=True,
                        modified=False,
                        message=f"Minor Grashof violation: {violation:.1f}",
                    )

            # Correct by adjusting the shortest link
            correction_factor = (others_sum - longest + 0.1) / shortest
            correction_factor = max(0.5, min(2.0, correction_factor))

            # Identify which link is shortest and correct it
            link_lengths: dict[str, float] = {"L1": L1, "L2": L2, "L3": L3, "L4": L4}
            shortest_link = min(link_lengths, key=lambda key: link_lengths[key])

            corrected_params = dict(params)

            # Apply correction based on which link is shortest
            if shortest_link == "L1":  # Crank
                direction = (A - O0) / L1 if L1 > 0 else np.array([0, -1])
                new_A = O0 + direction * L1 * correction_factor
                corrected_params["A"] = new_A.tolist()
            elif shortest_link == "L4":  # Ground
                direction = (O1 - O0) / L4 if L4 > 0 else np.array([1, 0])
                new_O1 = O0 + direction * L4 * correction_factor
                corrected_params["O1"] = new_O1.tolist()

            return SnapResult(
                success=True,
                modified=True,
                message=f"Grashof corrected (factor: {correction_factor:.2f})",
                corrected_params=corrected_params,
            )

        except Exception as e:
            logging.error(f"PhysicsSnapper: Grashof enforcement failed: {e}")
            return SnapResult(success=False, modified=False, message=str(e))

    def enforce_gear_meshing(
        self,
        layer_data: dict[str, Any],
    ) -> SnapResult:
        """
        Enforce gear meshing constraint.

        Gears must be tangent (center distance = sum of radii).

        Args:
            layer_data: Mechanism layer data with parameters

        Returns:
            SnapResult with corrected parameters if needed
        """
        if self._snap_mode == self.SNAP_NONE:
            return SnapResult(success=True, modified=False, message="Snap disabled")

        params = layer_data.get("parameters", {})

        try:
            r1 = params.get("r1", 30.0)
            r2 = params.get("r2", 20.0)
            c1 = np.array(params.get("center1", [0, 0]), dtype=float)
            c2 = np.array(params.get("center2", [r1 + r2, 0]), dtype=float)

            # Calculate current center distance
            current_distance = np.linalg.norm(c2 - c1)
            required_distance = r1 + r2

            error = abs(current_distance - required_distance)

            if error < 0.1:  # Within tolerance
                return SnapResult(
                    success=True,
                    modified=False,
                    message="Gear meshing satisfied",
                )

            if self._snap_mode == self.SNAP_SOFT and error < 5.0:
                return SnapResult(
                    success=True,
                    modified=False,
                    message=f"Minor gear meshing error: {error:.1f}",
                )

            # Correct by moving second gear center
            direction = (c2 - c1) / current_distance if current_distance > 0 else np.array([1, 0])
            new_c2 = c1 + direction * required_distance

            corrected_params = dict(params)
            corrected_params["center2"] = new_c2.tolist()

            return SnapResult(
                success=True,
                modified=True,
                message=f"Gear meshing corrected (error was {error:.1f})",
                corrected_params=corrected_params,
            )

        except Exception as e:
            logging.error(f"PhysicsSnapper: Gear meshing failed: {e}")
            return SnapResult(success=False, modified=False, message=str(e))

    def enforce_cam_follower(
        self,
        layer_data: dict[str, Any],
    ) -> SnapResult:
        """
        Enforce cam-follower contact constraint.

        Follower must maintain contact with cam profile.

        Args:
            layer_data: Mechanism layer data with parameters

        Returns:
            SnapResult with corrected parameters if needed
        """
        if self._snap_mode == self.SNAP_NONE:
            return SnapResult(success=True, modified=False, message="Snap disabled")

        params = layer_data.get("parameters", {})

        try:
            base_r = positive_finite_float(params.get("base_radius"), 30.0)
            params.get("lift", 15.0)
            follower_r = positive_finite_float(params.get("follower_radius"), 8.0)
            center = np.array(params.get("center", [0.0, 0.0]), dtype=float)
            if center.ndim != 1 or center.size < 2 or not bool(np.isfinite(center[:2]).all()):
                center = np.array([0.0, 0.0], dtype=float)
            else:
                center = center[:2]
            follower_pos = params.get("follower_position")

            if not follower_pos:
                # Set default follower position
                default_y = center[1] - base_r - follower_r
                corrected_params = dict(params)
                corrected_params["follower_position"] = [center[0], default_y]
                return SnapResult(
                    success=True,
                    modified=True,
                    message="Follower position initialized",
                    corrected_params=corrected_params,
                )

            follower = np.array(follower_pos, dtype=float)
            if follower.ndim != 1 or follower.size < 2 or not bool(np.isfinite(follower[:2]).all()):
                follower = np.array([center[0], center[1] - base_r - follower_r], dtype=float)
            else:
                follower = follower[:2]

            # Check follower is on the cam centerline (x alignment)
            x_error = abs(follower[0] - center[0])

            if x_error < 1.0:
                return SnapResult(
                    success=True,
                    modified=False,
                    message="Cam-follower contact satisfied",
                )

            # Correct follower x position
            corrected_params = dict(params)
            corrected_params["follower_position"] = [center[0], follower[1]]

            return SnapResult(
                success=True,
                modified=True,
                message=f"Cam-follower aligned (x error was {x_error:.1f})",
                corrected_params=corrected_params,
            )

        except Exception as e:
            logging.error(f"PhysicsSnapper: Cam-follower failed: {e}")
            return SnapResult(success=False, modified=False, message=str(e))
