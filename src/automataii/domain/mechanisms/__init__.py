"""
Domain layer for rigorous mechanism implementations.

This module provides mathematically accurate, constraint-based mechanism models
that form the foundation for educational visualization and interactive manipulation.
"""

from .base import BaseMechanism, MechanismConstraint, MechanismState
from .four_bar_linkage import FourBarLinkage, GrashofClassification
from .slider_crank import SliderCrankMechanism
from .gear_train import GearTrain
from .cam_follower import CamFollowerMechanism
from .spring_system import SpringSystem

__all__ = [
    'BaseMechanism',
    'MechanismConstraint', 
    'MechanismState',
    'FourBarLinkage',
    'GrashofClassification',
    'SliderCrankMechanism',
    'GearTrain',
    'CamFollowerMechanism',
    'SpringSystem'
]