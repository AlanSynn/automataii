"""Service for mechanism generation business logic."""

import logging
import math
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass

from PyQt6.QtCore import QObject, pyqtSignal, QPointF
from PyQt6.QtGui import QPainterPath

from automataii.gui.dialogs.recommendation.constants import (
    MECHANISM_TYPE_USER_DISPLAY_4_BAR,
    MECHANISM_TYPE_USER_DISPLAY_3_BAR,
    MECHANISM_TYPE_USER_DISPLAY_CAM,
)


@dataclass
class MechanismParameters:
    """Parameters for mechanism generation."""
    mechanism_type: str
    part_name: str
    motion_path: QPainterPath
    cam_center: Optional[QPointF] = None
    pivot_a: Optional[QPointF] = None
    pivot_d: Optional[QPointF] = None
    gear_ratio: float = 1.0
    driver_center: Optional[QPointF] = None
    driven_center: Optional[QPointF] = None


class MechanismGenerationService(QObject):
    """Service for generating mechanisms."""

    # Signals
    generation_started = pyqtSignal(str)  # mechanism_type
    generation_completed = pyqtSignal(dict)  # mechanism_data
    generation_failed = pyqtSignal(str)  # error_message

    def __init__(self):
        super().__init__()
        self._logger = logging.getLogger(__name__)

    def validate_parameters(self, params: MechanismParameters) -> Tuple[bool, str]:
        """Validate mechanism generation parameters."""
        if not params.part_name:
            return False, "No part selected"

        if params.motion_path.isEmpty():
            return False, "Motion path is empty"

        # Type-specific validation
        if params.mechanism_type == MECHANISM_TYPE_USER_DISPLAY_CAM:
            if not params.cam_center:
                return False, "Cam center point not selected"

        elif params.mechanism_type == MECHANISM_TYPE_USER_DISPLAY_3_BAR:
            if not params.pivot_a:
                return False, "Fixed pivot point not selected"

        elif params.mechanism_type == MECHANISM_TYPE_USER_DISPLAY_4_BAR:
            if not params.pivot_a or not params.pivot_d:
                return False, "Both fixed pivot points must be selected"

        return True, ""

    def generate_mechanism(self, params: MechanismParameters) -> Optional[Dict]:
        """Generate mechanism based on parameters."""
        # Validate parameters
        is_valid, error_msg = self.validate_parameters(params)
        if not is_valid:
            self._logger.error(f"Invalid parameters: {error_msg}")
            self.generation_failed.emit(error_msg)
            return None

        self._logger.info(f"Generating {params.mechanism_type} for {params.part_name}")
        self.generation_started.emit(params.mechanism_type)

        try:
            # Prepare mechanism data
            mechanism_data = self._prepare_mechanism_data(params)

            # Here would be the actual mechanism generation logic
            # For now, we just prepare the data structure

            self._logger.info(f"Successfully generated {params.mechanism_type}")
            self.generation_completed.emit(mechanism_data)
            return mechanism_data

        except Exception as e:
            error_msg = f"Failed to generate mechanism: {str(e)}"
            self._logger.error(error_msg)
            self.generation_failed.emit(error_msg)
            return None

    def _prepare_mechanism_data(self, params: MechanismParameters) -> Dict:
        """Prepare mechanism data structure."""
        data = {
            "type": params.mechanism_type,
            "part_name": params.part_name,
            "motion_path": params.motion_path,
        }

        # Add type-specific data
        if params.mechanism_type == MECHANISM_TYPE_USER_DISPLAY_CAM:
            data["cam_center"] = params.cam_center
            # Generate cam profile from motion path
            data["cam_profile"] = self._generate_cam_profile(params.motion_path, params.cam_center)
            data["follower_type"] = "roller"  # Default to roller follower

        elif params.mechanism_type == MECHANISM_TYPE_USER_DISPLAY_3_BAR:
            data["pivot_a"] = params.pivot_a
            # Generate joints for 3-bar linkage
            joints = self._generate_3bar_joints(params.motion_path, params.pivot_a)
            data.update(joints)

        elif params.mechanism_type == MECHANISM_TYPE_USER_DISPLAY_4_BAR:
            data["pivot_a"] = params.pivot_a
            data["pivot_d"] = params.pivot_d
            # Generate joints for 4-bar linkage
            joints = self._generate_4bar_joints(params.motion_path, params.pivot_a, params.pivot_d)
            data.update(joints)

        return data
    
    def _generate_cam_profile(self, motion_path: QPainterPath, center: QPointF) -> List[QPointF]:
        """Generate cam profile points from motion path."""
        profile_points = []
        
        # Sample points from motion path
        num_samples = 100
        for i in range(num_samples):
            t = i / (num_samples - 1)
            point = motion_path.pointAtPercent(t)
            
            # Transform to cam-centered coordinates
            relative_point = QPointF(
                point.x() - center.x(),
                point.y() - center.y()
            )
            profile_points.append(relative_point)
            
        return profile_points
    
    def _generate_3bar_joints(self, motion_path: QPainterPath, pivot_a: QPointF) -> Dict:
        """Generate joint positions for 3-bar linkage."""
        # Sample a point from the motion path for joint B
        mid_point = motion_path.pointAtPercent(0.5)
        
        # Calculate link length
        link_length = math.sqrt(
            (mid_point.x() - pivot_a.x())**2 + 
            (mid_point.y() - pivot_a.y())**2
        )
        
        return {
            "joint_b": mid_point,
            "link_length": link_length
        }
    
    def _generate_4bar_joints(self, motion_path: QPainterPath, 
                            pivot_a: QPointF, pivot_d: QPointF) -> Dict:
        """Generate joint positions for 4-bar linkage."""
        # Sample points from motion path
        point1 = motion_path.pointAtPercent(0.25)
        point2 = motion_path.pointAtPercent(0.75)
        
        # Use these as initial positions for joints B and C
        joint_b = point1
        joint_c = point2
        
        # Adjust positions to ensure valid linkage
        # This is a simplified approach - real implementation would use
        # kinematic synthesis algorithms
        
        return {
            "joint_b": joint_b,
            "joint_c": joint_c
        }

    def get_required_points(self, mechanism_type: str) -> List[str]:
        """Get list of required points for a mechanism type."""
        if mechanism_type == MECHANISM_TYPE_USER_DISPLAY_CAM:
            return ["cam_center"]
        elif mechanism_type == MECHANISM_TYPE_USER_DISPLAY_3_BAR:
            return ["pivot_a"]
        elif mechanism_type == MECHANISM_TYPE_USER_DISPLAY_4_BAR:
            return ["pivot_a", "pivot_d"]
        else:
            return []

    def estimate_mechanism_complexity(self, motion_path: QPainterPath) -> Dict[str, float]:
        """Estimate complexity scores for different mechanism types."""
        # This would analyze the motion path and return complexity scores
        # For now, return dummy values
        return {
            MECHANISM_TYPE_USER_DISPLAY_CAM: 0.7,
            MECHANISM_TYPE_USER_DISPLAY_3_BAR: 0.5,
            MECHANISM_TYPE_USER_DISPLAY_4_BAR: 0.3,
        }