import json  # Added import
import logging
import os

import numpy as np  # Added import
from PyQt6.QtCore import QLineF, QPointF
from PyQt6.QtGui import QTransform  # Import QTransform from QtGui

# --- Environment Setup ---




# --- Transformation Helpers ---






# --- Path Helpers ---






# --- Geometry Helpers ---




def distance(p1: QPointF, p2: QPointF) -> float:
    """Calculates the Euclidean distance between two QPointF points."""
    return QLineF(p1, p2).length()




# --- JSON Helpers ---
