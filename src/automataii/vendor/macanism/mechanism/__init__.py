"""
Mechanism kinematic analysis library.

This module provides classes and functions for analyzing mechanical linkages,
including position, velocity, and acceleration analysis with 3D support.
"""

import os
import sys
import warnings

# Warning that arise due to using quiver:
warnings.filterwarnings("ignore", "divide by zero encountered in double_scalars")
warnings.filterwarnings("ignore", "invalid value encountered in multiply")

# Warning that arises due to the 'move circle' function:
warnings.filterwarnings("ignore", "invalid value encountered in sqrt")

# Import from new modular structure
from .core.joint import Joint
from .core.mechanism import Mechanism
from .utils.factory import get_joints
from .utils.vector_ops import get_sum

# Import other components (these remain in original locations for now)
from .dataframe import Data, read_csv, print_matrix
from .vectors import Vector
from .cams import Cam
from .gears import SpurGear

THIS_DIR = os.path.dirname(__file__)
sys.path.append(THIS_DIR)

# Version info
__version__ = "1.0.0"

__all__ = [
    "Data",
    "read_csv",
    "print_matrix",
    "Joint",
    "Vector",
    "Mechanism",
    "get_joints",
    "get_sum",
    "Cam",
    "SpurGear",
]
