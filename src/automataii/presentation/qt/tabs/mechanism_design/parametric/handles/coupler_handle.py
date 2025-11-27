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


