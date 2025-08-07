"""
Joint Handle for 4-bar linkage parametric control.

This module provides JointHandle class for manipulating moving joints
in 4-bar linkages, allowing direct control of link lengths.
"""

import logging
import math
from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QCursor
from PyQt6.QtWidgets import QGraphicsItem

from .draggable_handle import DraggableHandle


class JointHandle(DraggableHandle):
    """
    Handle for manipulating 4-bar linkage moving joints (crank-coupler, rocker-coupler).
    
    Moving a joint handle changes the length of its associated link by constraining
    the joint position to a circle around the corresponding anchor pivot.
    
    Features:
    - Link length control (l2 for crank, l3 for rocker)
    - Circular constraint around anchor pivot  
    - Real-time mechanism recalculation
    - Visual feedback for valid/invalid positions
    - Grashof criterion validation
    """

    # Joint-specific appearance - Blue for joint manipulation
    COLOR_JOINT = QColor(0, 100, 255)          # Blue for joints
    COLOR_JOINT_HOVER = QColor(50, 150, 255)   # Light blue
    COLOR_JOINT_ACTIVE = QColor(100, 200, 255) # Very light blue

    # Size constants
    RADIUS_NORMAL = 12.0
    RADIUS_HOVER = 15.0
    RADIUS_DRAG = 18.0

    def __init__(self,
                 mechanism_id: str,
                 joint_name: str,  # 'crank_joint' or 'rocker_joint'
                 anchor_name: str,  # 'ground_pivot_1' or 'ground_pivot_2'
                 link_param: str,   # 'l2' or 'l3'
                 initial_position: QPointF,
                 anchor_position: QPointF,
                 mechanism_data: dict[str, Any],
                 update_callback: Callable[[str, float], None],
                 parent=None):
        """
        Initialize joint handle for moving joint manipulation.
        
        Args:
            mechanism_id: Unique mechanism identifier
            joint_name: Name of joint ('crank_joint', 'rocker_joint')  
            anchor_name: Associated anchor point name
            link_param: Link parameter this joint controls ('l2', 'l3')
            initial_position: Starting position in scene coordinates
            anchor_position: Position of associated anchor point
            mechanism_data: Reference to mechanism layer data
            update_callback: Function to call when joint moves
            parent: Qt parent object
        """
        # Create update callback wrapper for joint-specific handling
        def joint_update_callback(handle_id: str, new_pos: QPointF):
            new_link_length = self._calculate_link_length_from_position(new_pos)
            update_callback(self.link_param, new_link_length)

        super().__init__(
            handle_id=f"{mechanism_id}_{joint_name}",
            initial_pos=initial_position,
            update_callback=joint_update_callback,
            parent=parent
        )

        self.mechanism_id = mechanism_id
        self.joint_name = joint_name
        self.anchor_name = anchor_name
        self.link_param = link_param
        self.anchor_position = anchor_position
        self.mechanism_data = mechanism_data

        # Joint-specific constraints
        self.min_link_length = 10.0   # Minimum link length in scene units
        self.max_link_length = 200.0  # Maximum link length in scene units

        # Override colors for joint-specific appearance
        self._setup_joint_appearance()

        logging.debug(f"Created JointHandle for {joint_name} controlling {link_param}")

    def _setup_joint_appearance(self):
        """Setup joint-specific visual appearance."""
        # Override colors
        self.COLOR_NORMAL = self.COLOR_JOINT
        self.COLOR_HOVER = self.COLOR_JOINT_HOVER
        self.COLOR_DRAG = self.COLOR_JOINT_ACTIVE

        # Update appearance
        self._update_visual_state()

        # FORCE visibility and interaction
        self.setVisible(True)
        self.setOpacity(1.0)
        self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))  # Different cursor for joints

        logging.info(f"[JOINT] Created BLUE joint handle: {self.joint_name}")

    def _calculate_link_length_from_position(self, joint_pos: QPointF) -> float:
        """
        Calculate link length from joint position.
        
        Args:
            joint_pos: Current joint position in scene coordinates
            
        Returns:
            New link length (distance from anchor to joint)
        """
        dx = joint_pos.x() - self.anchor_position.x()
        dy = joint_pos.y() - self.anchor_position.y()
        return math.sqrt(dx * dx + dy * dy)

    def _validate_joint_constraints(self, new_position: QPointF) -> tuple[bool, str]:
        """
        Validate joint position against constraints.
        
        Args:
            new_position: Proposed new joint position
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Calculate proposed link length
            new_length = self._calculate_link_length_from_position(new_position)

            # Check length constraints
            if new_length < self.min_link_length:
                return False, f"Link too short: {new_length:.1f} < {self.min_link_length}"

            if new_length > self.max_link_length:
                return False, f"Link too long: {new_length:.1f} > {self.max_link_length}"

            # Validate overall mechanism geometry with new link length
            return self._validate_mechanism_geometry(new_length)

        except Exception as e:
            logging.warning(f"Joint constraint validation failed: {e}")
            return True, ""  # Allow movement if validation fails

    def _validate_mechanism_geometry(self, new_link_length: float) -> tuple[bool, str]:
        """
        Validate that mechanism geometry remains valid with new link length.
        
        Args:
            new_link_length: Proposed new link length
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Get current mechanism parameters
            params = self.mechanism_data.get("params", {})
            if not params:
                return True, ""  # Skip validation if parameters missing

            # Create updated parameter set
            updated_params = params.copy()
            updated_params[self.link_param] = new_link_length

            # Extract all link lengths
            l1 = updated_params.get("l1", 0)  # Ground link
            l2 = updated_params.get("l2", 0)  # Crank
            l3 = updated_params.get("l3", 0)  # Rocker
            l4 = updated_params.get("l4", 0)  # Coupler

            if not all([l1, l2, l3, l4]):
                return True, ""  # Skip validation if any length missing

            # Grashof's criterion for 4-bar linkage mobility
            lengths = [l1, l2, l3, l4]
            lengths.sort()
            s, p, q, l = lengths  # s=shortest, l=longest

            # Check Grashof condition: s + l <= p + q (for continuous rotation)
            if s + l > p + q + 1e-6:  # Small tolerance for floating point
                return False, f"Grashof condition violated: linkage may not be mobile (s+l={s+l:.1f}, p+q={p+q:.1f})"

            # Additional geometric constraints can be added here
            # e.g., triangle inequality for linkage assembly

            return True, ""

        except Exception as e:
            logging.warning(f"Mechanism geometry validation failed: {e}")
            return True, ""

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any) -> Any:
        """
        Override itemChange to include joint-specific constraint validation.
        """
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            new_pos = value  # This is the proposed new position

            # Validate joint-specific constraints
            is_valid, error_msg = self._validate_joint_constraints(new_pos)

            if not is_valid:
                # Constrain to valid position
                constrained_pos = self._constrain_to_valid_position(new_pos)
                logging.debug(f"Joint constraint violation: {error_msg}, constraining to {constrained_pos}")
                return constrained_pos

            # Position is valid, proceed with normal processing
            return super().itemChange(change, value)

        return super().itemChange(change, value)

    def _constrain_to_valid_position(self, proposed_pos: QPointF) -> QPointF:
        """
        Constrain proposed position to valid range.
        
        Args:
            proposed_pos: Proposed new position
            
        Returns:
            Constrained valid position
        """
        try:
            # Calculate direction from anchor to proposed position
            dx = proposed_pos.x() - self.anchor_position.x()
            dy = proposed_pos.y() - self.anchor_position.y()
            current_length = math.sqrt(dx * dx + dy * dy)

            if current_length == 0:
                # If at anchor position, move to minimum valid distance
                return QPointF(self.anchor_position.x() + self.min_link_length, self.anchor_position.y())

            # Normalize direction vector
            unit_x = dx / current_length
            unit_y = dy / current_length

            # Constrain length to valid range
            constrained_length = max(self.min_link_length, min(self.max_link_length, current_length))

            # Calculate constrained position
            constrained_x = self.anchor_position.x() + unit_x * constrained_length
            constrained_y = self.anchor_position.y() + unit_y * constrained_length

            return QPointF(constrained_x, constrained_y)

        except Exception as e:
            logging.warning(f"Position constraint failed: {e}")
            return self.pos()  # Return current position if constraining fails

    def get_current_link_length(self) -> float:
        """
        Get current link length from joint position.
        
        Returns:
            Current link length
        """
        return self._calculate_link_length_from_position(self.pos())

    def update_anchor_position(self, new_anchor_pos: QPointF):
        """
        Update anchor position when anchor handle moves.
        
        Args:
            new_anchor_pos: New anchor position
        """
        # Store current link length
        current_length = self.get_current_link_length()

        # Update anchor position
        old_anchor = self.anchor_position
        self.anchor_position = new_anchor_pos

        # Update joint position to maintain link length
        dx = self.pos().x() - old_anchor.x()
        dy = self.pos().y() - old_anchor.y()

        # Maintain same relative position if possible
        if dx != 0 or dy != 0:
            length = math.sqrt(dx * dx + dy * dy)
            if length > 0:
                unit_x = dx / length
                unit_y = dy / length

                new_joint_x = new_anchor_pos.x() + unit_x * current_length
                new_joint_y = new_anchor_pos.y() + unit_y * current_length

                self.setPos(QPointF(new_joint_x, new_joint_y))

        logging.debug(f"Updated anchor position for {self.joint_name}: {old_anchor} -> {new_anchor_pos}")

    def get_link_parameter_name(self) -> str:
        """Get the link parameter this joint controls."""
        return self.link_param

    def get_joint_name(self) -> str:
        """Get the joint name."""
        return self.joint_name

    def __repr__(self) -> str:
        """String representation for debugging."""
        pos = self.pos()
        length = self.get_current_link_length()
        return f"JointHandle({self.mechanism_id}:{self.joint_name} {self.link_param}={length:.1f} at {pos.x():.1f},{pos.y():.1f})"
