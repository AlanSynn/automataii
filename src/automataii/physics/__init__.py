"""
Lightweight Physics Engine - PyBullet-free physics simulation

Provides basic physics simulation capabilities for mechanism visualization:
- Rigid body dynamics
- Spring forces
- Collision detection
- Joint constraints
- Simple gravity and friction
"""

from .engine import PhysicsEngine
from .body import RigidBody
from .constraints import Joint, SpringConstraint
from .world import PhysicsWorld

__all__ = [
    'PhysicsEngine',
    'RigidBody', 
    'Joint',
    'SpringConstraint',
    'PhysicsWorld'
]