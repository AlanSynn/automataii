"""
3D Simulation System for Mechanism Design

This module provides comprehensive 3D physics simulation capabilities that enable
realistic mechanism behavior analysis and visualization with PyBullet integration.

Features:
- PyBullet physics engine integration for accurate constraint solving
- Real-time 3D mechanism simulation with collision detection
- Physics-based parameter validation and optimization
- Interactive 3D visualization with OpenGL rendering
- Seamless integration with 2D blueprint generation system
- Educational physics visualization (forces, torques, motion paths)

The simulation system provides the physics foundation that ensures blueprint
accuracy and enables advanced mechanism analysis capabilities.
"""

from .simulation_manager import SimulationManager3D
from .physics_engine import PyBulletPhysicsEngine, PhysicsConstraint, PhysicsBody
from .rendering_3d import OpenGLRenderer3D, Camera3D, Scene3D
from .controls_3d import Simulation3DControls, ViewportController
from .constraints import ConstraintSolver, JointConstraint, ContactConstraint

__all__ = [
    'SimulationManager3D',
    'PyBulletPhysicsEngine',
    'PhysicsConstraint',
    'PhysicsBody',
    'OpenGLRenderer3D',
    'Camera3D',
    'Scene3D',
    'Simulation3DControls',
    'ViewportController',
    'ConstraintSolver',
    'JointConstraint',
    'ContactConstraint'
]