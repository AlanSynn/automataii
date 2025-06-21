"""
Parametric Design Module for Interactive Mechanism Manipulation

This module provides interactive drag-and-drop editing of mechanism parameters
through visual handles and real-time feedback.

Author: AI Engineering Assistant
Architecture: ULTRATHINK + Jeff Dean + Kent Beck + Rob Pike Principles
"""

from .handles.base_handle import BaseHandle
from .handles.anchor_handle import AnchorHandle
from .controllers.parameter_controller import ParameterController

__all__ = [
    'BaseHandle',
    'AnchorHandle', 
    'ParameterController'
]