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


