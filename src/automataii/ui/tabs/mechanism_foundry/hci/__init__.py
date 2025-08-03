"""
Enhanced HCI (Human-Computer Interaction) Components for Mechanism Foundry

This module provides cutting-edge interactive components designed for maximum user engagement
and intuitive mechanism exploration. Features include:

- Real-time physics manipulation with haptic feedback
- Contextual parameter controls with live preview
- Challenge-based learning system with progression tracking
- Advanced measurement and analysis tools
- Micro-interaction animations and visual feedback

Components:
- PhysicsInteractionLayer: Direct manipulation of mechanism components
- ParametricControlPanel: Real-time parameter adjustment system
- ChallengeManager: Gamified learning progression
- VisualEffectsRenderer: Smooth animations and transitions
- MeasurementToolkit: Interactive analysis and measurement tools
"""

__version__ = "1.0.0"
__author__ = "Mechanism Foundry HCI Team"

from .physics_interaction import PhysicsInteractionLayer, HapticFeedbackEngine
from .parametric_controls import ParametricControlPanel, RealTimeSlider

__all__ = [
    'PhysicsInteractionLayer',
    'HapticFeedbackEngine', 
    'ParametricControlPanel',
    'RealTimeSlider'
]