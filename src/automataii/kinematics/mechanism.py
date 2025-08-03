from dataclasses import dataclass
from typing import Dict
from enum import Enum
import numpy as np


class MechanismType(Enum):
    THREE_BAR = "3bar"
    FOUR_BAR = "4bar"
    CAM = "cam"
    PARAMETRIC = "parametric"


@dataclass
class MotionCurve:
    points: np.ndarray
    period: float
    attachment_point: np.ndarray
    parameter_vector: np.ndarray


@dataclass
class MechanismCandidate:
    mechanism_type: MechanismType
    parameters: Dict[str, float]
    motion_curve: MotionCurve
    similarity_score: float
    transform_matrix: np.ndarray
