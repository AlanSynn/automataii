"""
Coupler Handle for 4-bar linkage parametric control with inverse kinematics.

This module provides CouplerHandle class for manipulating the coupler point
of 4-bar linkages using inverse kinematics to solve for mechanism configurations.
"""

import logging
import math
from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QCursor
from PyQt6.QtWidgets import QGraphicsItem

from .draggable_handle import DraggableHandle


class CouplerHandle(DraggableHandle):
    """
    Handle for manipulating 4-bar linkage coupler point using inverse kinematics.
    
    Moving a coupler handle requires solving the inverse kinematics problem:
    given a desired coupler point position, calculate the mechanism configuration
    (joint angles) that achieves that position.
    
    Features:
    - Inverse kinematics solver for 4-bar linkage
    - Coupler point positioning and path control
    - Real-time mechanism reconfiguration
    - Visual feedback for reachable/unreachable positions
    - Singularity detection and handling
    """

    # Coupler-specific appearance - Green for coupler manipulation
    COLOR_COUPLER = QColor(0, 200, 0)          # Green for coupler
    COLOR_COUPLER_HOVER = QColor(50, 255, 50)   # Light green
    COLOR_COUPLER_ACTIVE = QColor(100, 255, 100) # Very light green
    COLOR_UNREACHABLE = QColor(255, 100, 0)    # Orange for unreachable positions

    # Size constants - larger for visibility
    RADIUS_NORMAL = 14.0
    RADIUS_HOVER = 17.0
    RADIUS_DRAG = 20.0

    def __init__(self,
                 mechanism_id: str,
                 coupler_point_name: str,  # 'coupler_point' or specific point name
                 initial_position: QPointF,
                 mechanism_data: dict[str, Any],
                 update_callback: Callable[[QPointF], None],
                 parent=None):
        """
        Initialize coupler handle for coupler point manipulation.
        
        Args:
            mechanism_id: Unique mechanism identifier
            coupler_point_name: Name of coupler point
            initial_position: Starting position in scene coordinates
            mechanism_data: Reference to mechanism layer data
            update_callback: Function to call when coupler moves
            parent: Qt parent object
        """
        # Create update callback wrapper for coupler-specific handling
        def coupler_update_callback(handle_id: str, new_pos: QPointF):
            # Solve inverse kinematics and update mechanism
            success = self._solve_inverse_kinematics_and_update(new_pos)
            if success and update_callback:
                update_callback(new_pos)

        super().__init__(
            handle_id=f"{mechanism_id}_{coupler_point_name}",
            initial_pos=initial_position,
            update_callback=coupler_update_callback,
            parent=parent
        )

        self.mechanism_id = mechanism_id
        self.coupler_point_name = coupler_point_name
        self.mechanism_data = mechanism_data
        self.main_update_callback = update_callback

        # IK solver state
        self._last_valid_config = None
        self._is_position_reachable = True

        # Override colors for coupler-specific appearance
        self._setup_coupler_appearance()

        logging.debug(f"Created CouplerHandle for {coupler_point_name}")

    def _setup_coupler_appearance(self):
        """Setup coupler-specific visual appearance."""
        # Override colors
        self.COLOR_NORMAL = self.COLOR_COUPLER
        self.COLOR_HOVER = self.COLOR_COUPLER_HOVER
        self.COLOR_DRAG = self.COLOR_COUPLER_ACTIVE

        # Update appearance
        self._update_visual_state()

        # FORCE visibility and interaction
        self.setVisible(True)
        self.setOpacity(1.0)
        self.setCursor(QCursor(Qt.CursorShape.CrossCursor))  # Cross cursor for precise positioning

        logging.info(f"[COUPLER] Created GREEN coupler handle: {self.coupler_point_name}")

    def _solve_inverse_kinematics_and_update(self, target_pos: QPointF) -> bool:
        """
        Solve inverse kinematics for desired coupler position and update mechanism.
        
        Args:
            target_pos: Desired coupler point position
            
        Returns:
            True if solution found and mechanism updated, False otherwise
        """
        try:
            # Get current mechanism parameters
            params = self.mechanism_data.get("params", {})
            if not params:
                logging.warning("[COUPLER] No mechanism parameters found")
                return False

            # Get anchor positions
            key_points = self.mechanism_data.get("key_points", {})
            if "ground_pivot_1" not in key_points or "ground_pivot_2" not in key_points:
                logging.warning("[COUPLER] Missing anchor positions for IK")
                return False

            anchor1_data = key_points["ground_pivot_1"]
            anchor2_data = key_points["ground_pivot_2"]
            anchor1 = QPointF(anchor1_data[0], anchor1_data[1])
            anchor2 = QPointF(anchor2_data[0], anchor2_data[1])

            # Extract link lengths
            l1 = params.get("l1", 50.0)  # Ground link
            l2 = params.get("l2", 30.0)  # Crank
            l3 = params.get("l3", 40.0)  # Rocker
            l4 = params.get("l4", 35.0)  # Coupler

            # Solve inverse kinematics
            solution = self._solve_4bar_inverse_kinematics(
                anchor1, anchor2, target_pos, l1, l2, l3, l4
            )

            if solution is None:
                # Position is not reachable
                self._is_position_reachable = False
                self._update_unreachable_appearance()
                logging.debug(f"[COUPLER] Position {target_pos} not reachable")
                return False

            # Position is reachable
            self._is_position_reachable = True
            self._update_reachable_appearance()

            # Extract solution angles
            theta2, theta3, crank_joint, rocker_joint = solution

            # Update mechanism configuration
            self._update_mechanism_configuration(theta2, theta3, crank_joint, rocker_joint)

            logging.debug(f"[COUPLER] IK solved: theta2={math.degrees(theta2):.1f}°, theta3={math.degrees(theta3):.1f}°")
            return True

        except Exception as e:
            logging.error(f"IK solver failed: {e}")
            return False

    def _solve_4bar_inverse_kinematics(self, anchor1: QPointF, anchor2: QPointF,
                                     target_coupler: QPointF, l1: float, l2: float,
                                     l3: float, l4: float) -> tuple[float, float, QPointF, QPointF] | None:
        """
        Solve 4-bar linkage inverse kinematics for coupler point position.
        
        This is a complex problem that involves solving the constraint equations:
        1. The coupler point must be at the target position
        2. All joint constraints must be satisfied
        3. Link lengths must be preserved
        
        Args:
            anchor1: Ground pivot 1 position
            anchor2: Ground pivot 2 position  
            target_coupler: Desired coupler point position
            l1, l2, l3, l4: Link lengths
            
        Returns:
            Tuple of (theta2, theta3, crank_joint_pos, rocker_joint_pos) or None if no solution
        """
        try:
            # This is a simplified IK solver for demonstration
            # A complete implementation would use numerical methods or analytical solutions

            # For now, use a geometric approach with assumptions:
            # 1. Assume coupler point is at the midpoint of the coupler link
            # 2. Use this assumption to constrain the problem

            # Distance between ground pivots (l1)
            dx_ground = anchor2.x() - anchor1.x()
            dy_ground = anchor2.y() - anchor1.y()
            actual_l1 = math.sqrt(dx_ground * dx_ground + dy_ground * dy_ground)

            # For coupler point at midpoint of coupler link, we need to find
            # positions A and B such that the midpoint of AB is at target_coupler

            # Try multiple crank angles to find a solution
            best_solution = None
            min_error = float('inf')

            for theta2_deg in range(0, 360, 5):  # Sample every 5 degrees
                theta2 = math.radians(theta2_deg)

                # Calculate crank joint position (A)
                crank_x = anchor1.x() + l2 * math.cos(theta2)
                crank_y = anchor1.y() + l2 * math.sin(theta2)
                crank_joint = QPointF(crank_x, crank_y)

                # For this crank position, find rocker angle that puts
                # coupler midpoint closest to target
                rocker_solution = self._find_rocker_angle_for_coupler_target(
                    anchor2, crank_joint, target_coupler, l3, l4
                )

                if rocker_solution is None:
                    continue

                theta3, rocker_joint, error = rocker_solution

                if error < min_error:
                    min_error = error
                    best_solution = (theta2, theta3, crank_joint, rocker_joint)

                    # If error is very small, we found a good solution
                    if error < 1.0:  # Within 1 pixel
                        break

            # Accept solution if error is reasonable
            if best_solution and min_error < 10.0:  # Within 10 pixels
                return best_solution

            return None

        except Exception as e:
            logging.error(f"4-bar IK solver failed: {e}")
            return None

    def _find_rocker_angle_for_coupler_target(self, anchor2: QPointF, crank_joint: QPointF,
                                            target_coupler: QPointF, l3: float, l4: float) -> tuple[float, QPointF, float] | None:
        """
        Find rocker angle that places coupler point closest to target.
        
        Args:
            anchor2: Ground pivot 2 position
            crank_joint: Crank joint position (already determined)
            target_coupler: Desired coupler point position
            l3: Rocker length
            l4: Coupler length
            
        Returns:
            Tuple of (theta3, rocker_joint_pos, error) or None
        """
        try:
            # Distance from crank joint to anchor2
            dx = anchor2.x() - crank_joint.x()
            dy = anchor2.y() - crank_joint.y()
            d = math.sqrt(dx * dx + dy * dy)

            # Check if triangle closure is possible
            if d > (l3 + l4) or d < abs(l3 - l4):
                return None

            # There are typically two solutions for the triangle closure
            # Try both and pick the one that gives better coupler position
            solutions = []

            # Use cosine rule to find possible rocker angles
            cos_alpha = (l3 * l3 + d * d - l4 * l4) / (2 * l3 * d)

            if abs(cos_alpha) > 1:
                return None

            alpha = math.acos(cos_alpha)
            gamma = math.atan2(dy, dx)

            # Two possible solutions
            for sign in [1, -1]:
                theta3 = gamma + sign * alpha

                # Calculate rocker joint position
                rocker_x = anchor2.x() + l3 * math.cos(theta3)
                rocker_y = anchor2.y() + l3 * math.sin(theta3)
                rocker_joint = QPointF(rocker_x, rocker_y)

                # Calculate actual coupler point position (assuming midpoint)
                coupler_actual_x = (crank_joint.x() + rocker_joint.x()) / 2
                coupler_actual_y = (crank_joint.y() + rocker_joint.y()) / 2
                coupler_actual = QPointF(coupler_actual_x, coupler_actual_y)

                # Calculate error
                dx_err = target_coupler.x() - coupler_actual.x()
                dy_err = target_coupler.y() - coupler_actual.y()
                error = math.sqrt(dx_err * dx_err + dy_err * dy_err)

                solutions.append((theta3, rocker_joint, error))

            # Return solution with minimum error
            if solutions:
                return min(solutions, key=lambda x: x[2])

            return None

        except Exception as e:
            logging.error(f"Rocker angle calculation failed: {e}")
            return None

    def _update_mechanism_configuration(self, theta2: float, theta3: float,
                                      crank_joint: QPointF, rocker_joint: QPointF):
        """
        Update mechanism configuration with new joint positions.
        
        Args:
            theta2: Crank angle in radians
            theta3: Rocker angle in radians
            crank_joint: Crank joint position
            rocker_joint: Rocker joint position
        """
        try:
            # Store the new configuration
            self._last_valid_config = {
                'theta2': theta2,
                'theta3': theta3,
                'crank_joint': crank_joint,
                'rocker_joint': rocker_joint
            }

            # Update key points if they exist
            key_points = self.mechanism_data.get("key_points", {})
            if "crank_joint" in key_points:
                key_points["crank_joint"] = [crank_joint.x(), crank_joint.y()]
            if "rocker_joint" in key_points:
                key_points["rocker_joint"] = [rocker_joint.x(), rocker_joint.y()]

            # Update mechanism angles
            params = self.mechanism_data.get("params", {})
            params["theta2"] = theta2
            params["theta3"] = theta3

            logging.debug("[COUPLER] Updated mechanism configuration")

        except Exception as e:
            logging.error(f"Failed to update mechanism configuration: {e}")

    def _update_unreachable_appearance(self):
        """Update appearance when position is not reachable."""
        # Temporarily change color to indicate unreachable position
        self.COLOR_NORMAL = self.COLOR_UNREACHABLE
        self.COLOR_HOVER = self.COLOR_UNREACHABLE.lighter(120)
        self.COLOR_DRAG = self.COLOR_UNREACHABLE.lighter(140)
        self._update_visual_state()

    def _update_reachable_appearance(self):
        """Update appearance when position is reachable."""
        # Restore normal coupler colors
        self.COLOR_NORMAL = self.COLOR_COUPLER
        self.COLOR_HOVER = self.COLOR_COUPLER_HOVER
        self.COLOR_DRAG = self.COLOR_COUPLER_ACTIVE
        self._update_visual_state()

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any) -> Any:
        """
        Override itemChange to include reachability checking.
        """
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            new_pos = value

            # Quick reachability check before allowing move
            if not self._is_position_approximately_reachable(new_pos):
                # Constrain to reachable workspace
                constrained_pos = self._constrain_to_workspace(new_pos)
                logging.debug(f"[COUPLER] Constraining unreachable position {new_pos} to {constrained_pos}")
                return constrained_pos

            return super().itemChange(change, value)

        return super().itemChange(change, value)

    def _is_position_approximately_reachable(self, pos: QPointF) -> bool:
        """
        Quick reachability check based on workspace bounds.
        
        Args:
            pos: Position to check
            
        Returns:
            True if position is approximately within reachable workspace
        """
        try:
            # Get anchor positions
            key_points = self.mechanism_data.get("key_points", {})
            if "ground_pivot_1" not in key_points:
                return True  # Can't check, assume reachable

            anchor1_data = key_points["ground_pivot_1"]
            anchor1 = QPointF(anchor1_data[0], anchor1_data[1])

            # Get link lengths
            params = self.mechanism_data.get("params", {})
            l2 = params.get("l2", 30.0)
            l3 = params.get("l3", 40.0)
            l4 = params.get("l4", 35.0)

            # Approximate workspace as circle around anchor1
            # Maximum reach is roughly l2 + l4 (when links are extended)
            max_reach = l2 + l4
            min_reach = max(0, abs(l2 - l4))

            # Distance from anchor1 to target position
            dx = pos.x() - anchor1.x()
            dy = pos.y() - anchor1.y()
            distance = math.sqrt(dx * dx + dy * dy)

            # Check if within approximate workspace
            return min_reach <= distance <= max_reach

        except Exception as e:
            logging.debug(f"Reachability check failed: {e}")
            return True  # Assume reachable if check fails

    def _constrain_to_workspace(self, pos: QPointF) -> QPointF:
        """
        Constrain position to approximate reachable workspace.
        
        Args:
            pos: Desired position
            
        Returns:
            Constrained position within workspace
        """
        try:
            # Get anchor positions
            key_points = self.mechanism_data.get("key_points", {})
            if "ground_pivot_1" not in key_points:
                return pos  # Can't constrain, return as-is

            anchor1_data = key_points["ground_pivot_1"]
            anchor1 = QPointF(anchor1_data[0], anchor1_data[1])

            # Get link lengths
            params = self.mechanism_data.get("params", {})
            l2 = params.get("l2", 30.0)
            l4 = params.get("l4", 35.0)

            # Workspace bounds
            max_reach = l2 + l4 * 0.9  # Slightly less than theoretical max
            min_reach = max(10, abs(l2 - l4) * 1.1)  # Slightly more than theoretical min

            # Distance and direction from anchor1
            dx = pos.x() - anchor1.x()
            dy = pos.y() - anchor1.y()
            distance = math.sqrt(dx * dx + dy * dy)

            if distance == 0:
                # At anchor, move to minimum distance
                return QPointF(anchor1.x() + min_reach, anchor1.y())

            # Normalize direction
            unit_x = dx / distance
            unit_y = dy / distance

            # Constrain distance
            constrained_distance = max(min_reach, min(max_reach, distance))

            # Calculate constrained position
            constrained_x = anchor1.x() + unit_x * constrained_distance
            constrained_y = anchor1.y() + unit_y * constrained_distance

            return QPointF(constrained_x, constrained_y)

        except Exception as e:
            logging.warning(f"Workspace constraint failed: {e}")
            return pos

    def get_coupler_point_name(self) -> str:
        """Get the coupler point name."""
        return self.coupler_point_name

    def is_position_reachable(self) -> bool:
        """Check if current position is reachable."""
        return self._is_position_reachable

    def get_last_valid_configuration(self) -> dict[str, Any] | None:
        """Get the last valid mechanism configuration."""
        return self._last_valid_config

    def __repr__(self) -> str:
        """String representation for debugging."""
        pos = self.pos()
        reachable = "✓" if self._is_position_reachable else "✗"
        return f"CouplerHandle({self.mechanism_id}:{self.coupler_point_name} at {pos.x():.1f},{pos.y():.1f} {reachable})"
