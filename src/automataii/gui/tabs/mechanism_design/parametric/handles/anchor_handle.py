"""
Anchor Handle for Ground Pivot Manipulation

Specialized handle for manipulating fixed anchor points (ground pivots) 
in mechanism systems, particularly 4-bar linkages.

Author: AI Engineering Assistant
Architecture: Jeff Dean Performance + Kent Beck Simplicity + Rob Pike Clarity  
"""

import logging
import math
from collections.abc import Callable

from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QColor

from .base_handle import BaseHandle


class AnchorHandle(BaseHandle):
    """
    Handle for manipulating mechanism anchor points (ground pivots).
    
    Anchor points are fixed positions that serve as rotation centers
    for mechanism links. Moving them changes the overall mechanism geometry
    and motion characteristics.
    
    Features:
    - Ground pivot positioning for 4-bar linkages
    - Automatic constraint validation (minimum/maximum distances)
    - Real-time mechanism recalculation
    - Visual feedback for valid/invalid positions
    """

    # Anchor-specific appearance - VERY BRIGHT for visibility
    COLOR_ANCHOR = QColor(255, 0, 0)          # BRIGHT RED for visibility
    COLOR_ANCHOR_HOVER = QColor(255, 100, 100)  # Light red
    COLOR_ANCHOR_ACTIVE = QColor(255, 200, 200) # Very light red

    def __init__(self,
                 mechanism_id: str,
                 anchor_name: str,  # 'ground_pivot_1' or 'ground_pivot_2'
                 initial_position: QPointF,
                 mechanism_data: dict,
                 update_callback: Callable[[str, QPointF], None],
                 constraint_validator: Callable | None = None,
                 parent=None):
        """
        Initialize anchor handle for ground pivot manipulation.
        
        Args:
            mechanism_id: Unique mechanism identifier
            anchor_name: Name of anchor point ('ground_pivot_1', 'ground_pivot_2')
            initial_position: Starting position in scene coordinates  
            mechanism_data: Reference to mechanism layer data
            update_callback: Function to call when anchor moves
            constraint_validator: Optional constraint validation function
            parent: Qt parent object
        """
        super().__init__(mechanism_id, anchor_name, initial_position,
                        constraint_validator, None, parent)

        self.anchor_name = anchor_name
        self.mechanism_data = mechanism_data
        self.update_callback = update_callback

        # Anchor-specific constraints
        self.min_distance_to_other_anchor = 20.0  # Minimum pixel distance
        self.max_distance_to_other_anchor = 500.0 # Maximum pixel distance

        # Override colors for anchor-specific appearance
        self._setup_anchor_appearance()

        logging.debug(f"Created AnchorHandle for {self.anchor_name} at {initial_position}")

    def _setup_anchor_appearance(self):
        """Setup anchor-specific visual appearance."""
        # Override base colors with anchor-specific colors
        self.COLOR_NORMAL = self.COLOR_ANCHOR
        self.COLOR_HOVER = self.COLOR_ANCHOR_HOVER
        self.COLOR_ACTIVE = self.COLOR_ANCHOR_ACTIVE

        # Make anchors much larger for easy interaction
        self.HANDLE_RADIUS = 20.0
        self.HOVER_RADIUS = 25.0
        self.ACTIVE_RADIUS = 30.0

        # Update appearance
        self._update_visual_state()

        # FORCE visibility and interaction
        self.setVisible(True)
        self.setOpacity(1.0)
        self.show()

        logging.info(f"[ANCHOR] Created BRIGHT RED anchor handle: {self.anchor_name}")

    def _calculate_parameter_from_position(self, scene_pos: QPointF) -> QPointF:
        """
        Calculate anchor position from handle position.
        
        Args:
            scene_pos: Current handle position in scene coordinates
            
        Returns:
            New anchor position (same as scene position for anchors)
        """
        return scene_pos

    def _apply_parameter_change(self, new_position: QPointF):
        """
        Apply anchor position change to mechanism.
        
        Args:
            new_position: New anchor position in scene coordinates
        """
        try:
            # Update position in mechanism data immediately
            key_points = self.mechanism_data.get("key_points", {})
            if not key_points:
                key_points = {}
                self.mechanism_data["key_points"] = key_points

            # Update the anchor position
            key_points[self.anchor_name] = [new_position.x(), new_position.y()]

            # Trigger mechanism recalculation via callback
            self.update_callback(self.anchor_name, new_position)

            logging.debug(f"Updated {self.anchor_name} to {new_position}")

        except Exception as e:
            logging.error(f"Failed to apply anchor change: {e}")

    def get_current_parameter_value(self) -> QPointF:
        """
        Get current anchor position from mechanism data.
        
        Returns:
            Current anchor position as QPointF
        """
        # For anchors, the parameter value IS the position
        return self.pos()

    def _validate_anchor_constraints(self, new_position: QPointF) -> tuple[bool, str]:
        """
        Validate anchor position against constraints.
        
        Args:
            new_position: Proposed new anchor position
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Get other anchor position
            other_anchor_name = "ground_pivot_2" if self.anchor_name == "ground_pivot_1" else "ground_pivot_1"
            key_points = self.mechanism_data.get("key_points", {})

            if other_anchor_name in key_points:
                other_pos_data = key_points[other_anchor_name]
                other_pos = QPointF(other_pos_data[0], other_pos_data[1])

                # Calculate distance between anchors
                dx = new_position.x() - other_pos.x()
                dy = new_position.y() - other_pos.y()
                distance = math.sqrt(dx * dx + dy * dy)

                # Check minimum distance constraint
                if distance < self.min_distance_to_other_anchor:
                    return False, f"Anchors too close: {distance:.1f} < {self.min_distance_to_other_anchor}"

                # Check maximum distance constraint
                if distance > self.max_distance_to_other_anchor:
                    return False, f"Anchors too far: {distance:.1f} > {self.max_distance_to_other_anchor}"

                # Validate mechanism link length constraints
                params = self.mechanism_data.get("params", {})
                if params:
                    is_valid, msg = self._validate_linkage_geometry(new_position, other_pos, params)
                    if not is_valid:
                        return False, msg

            return True, ""

        except Exception as e:
            logging.warning(f"Constraint validation failed: {e}")
            return True, ""  # Allow movement if validation fails

    def _validate_linkage_geometry(self, pos1: QPointF, pos2: QPointF, params: dict) -> tuple[bool, str]:
        """
        Validate that linkage geometry remains valid with new anchor positions.
        
        Args:
            pos1: Position of this anchor
            pos2: Position of other anchor  
            params: Mechanism parameters (l1, l2, l3, l4)
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Extract link lengths
            l1 = params.get("l1", 0)
            l2 = params.get("l2", 0)
            l3 = params.get("l3", 0)
            l4 = params.get("l4", 0)

            if not all([l1, l2, l3, l4]):
                return True, ""  # Skip validation if parameters missing

            # Calculate ground link length (distance between anchors)
            dx = pos2.x() - pos1.x()
            dy = pos2.y() - pos1.y()
            ground_distance = math.sqrt(dx * dx + dy * dy)

            # Update l1 (ground link) in mechanism parameters
            # Note: This assumes l1 represents the ground link
            # Actual implementation may vary based on parameter mapping

            # Grashof's criterion for 4-bar linkage mobility
            lengths = [ground_distance, l2, l3, l4]
            lengths.sort()
            s, p, q, l = lengths  # s=shortest, l=longest

            # Check Grashof condition: s + l <= p + q (for continuous rotation)
            if s + l > p + q + 1e-6:  # Small tolerance for floating point
                return False, "Grashof condition violated: linkage may not be mobile"

            # Check triangle inequality for each triangle in the linkage
            # Additional geometric validations can be added here

            return True, ""

        except Exception as e:
            logging.warning(f"Linkage geometry validation failed: {e}")
            return True, ""

    def mouseMoveEvent(self, event):
        """
        Override mouse move to allow free dragging without real-time constraint validation.
        Constraint validation will be deferred to when exiting parametric editing mode.
        """
        if not self._is_dragging or not self._is_enabled:
            logging.info(f"[ANCHOR] ❌ Not dragging or not enabled: dragging={self._is_dragging}, enabled={self._is_enabled}")
            return
        
        new_position = event.scenePos()
        logging.info(f"[ANCHOR] 🎯 Mouse move to {new_position} for {self.anchor_name}")
        
        # Allow free dragging without constraint validation for smoother UX
        # Constraints will be validated when exiting parametric editing mode
        
        # Update position immediately for visual feedback
        old_pos = self.pos()
        self.setPos(new_position)
        actual_pos = self.pos()
        logging.info(f"[ANCHOR] ✅ Moved {self.anchor_name} from {old_pos} to {new_position}, actual: {actual_pos}")
        
        # CRITICAL: Call the update callback immediately to trigger mechanism update
        if hasattr(self, 'update_callback') and self.update_callback:
            self.update_callback(new_position)
            logging.info(f"[ANCHOR] 🔥 Called update callback for {self.anchor_name} at {new_position}")
        else:
            logging.warning(f"[ANCHOR] ⚠️ No update_callback for {self.anchor_name}")

        # Don't call super() as it may reset position
        # super().mouseMoveEvent(event)



    def __repr__(self) -> str:
        """String representation for debugging."""
        pos = self.pos()
        return f"AnchorHandle({self.mechanism_id}:{self.anchor_name} at {pos.x():.1f},{pos.y():.1f})"
