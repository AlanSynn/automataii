"""
Rigid Body - Physics body representation

Represents rigid bodies in the physics simulation.
"""

import numpy as np
from typing import Tuple, Optional
from enum import Enum


class BodyType(Enum):
    """Types of rigid bodies"""
    STATIC = "static"        # Fixed in place
    DYNAMIC = "dynamic"      # Affected by forces
    KINEMATIC = "kinematic"  # User-controlled motion


class RigidBody:
    """
    Rigid body for physics simulation.
    
    Represents a solid object with mass, position, velocity, and rotation.
    """
    
    def __init__(self, 
                 position: Tuple[float, float] = (0, 0),
                 angle: float = 0.0,
                 mass: float = 1.0,
                 body_type: BodyType = BodyType.DYNAMIC):
        """
        Initialize rigid body.
        
        Args:
            position: Initial position (x, y)
            angle: Initial rotation angle in radians
            mass: Body mass (kg)
            body_type: Type of body (static, dynamic, kinematic)
        """
        # Identification
        self.id: Optional[int] = None
        self.body_type = body_type
        
        # Physical properties
        self.mass = mass
        self.moment_of_inertia = mass * 0.1  # Simple approximation
        
        # State variables
        self.position = np.array(position, dtype=float)
        self.velocity = np.array([0.0, 0.0])
        self.acceleration = np.array([0.0, 0.0])
        
        self.angle = angle
        self.angular_velocity = 0.0
        self.angular_acceleration = 0.0
        
        # Forces and torques
        self.force = np.array([0.0, 0.0])
        self.torque = 0.0
        
        # Initial state (for reset)
        self.initial_position = np.copy(self.position)
        self.initial_angle = angle
        
        # Properties
        self.restitution = 0.5  # Bounce factor
        self.friction = 0.3     # Friction coefficient
        
    @property
    def is_static(self) -> bool:
        """Check if body is static"""
        return self.body_type == BodyType.STATIC
        
    @property
    def is_dynamic(self) -> bool:
        """Check if body is dynamic"""
        return self.body_type == BodyType.DYNAMIC
        
    @property
    def is_kinematic(self) -> bool:
        """Check if body is kinematic"""
        return self.body_type == BodyType.KINEMATIC
        
    def set_position(self, position: Tuple[float, float]) -> None:
        """Set body position"""
        self.position = np.array(position, dtype=float)
        
    def set_angle(self, angle: float) -> None:
        """Set body angle"""
        self.angle = angle
        
    def set_velocity(self, velocity: Tuple[float, float]) -> None:
        """Set body velocity"""
        if not self.is_static:
            self.velocity = np.array(velocity, dtype=float)
            
    def set_angular_velocity(self, angular_velocity: float) -> None:
        """Set body angular velocity"""
        if not self.is_static:
            self.angular_velocity = angular_velocity
            
    def apply_force(self, force: Tuple[float, float], 
                   point: Optional[Tuple[float, float]] = None) -> None:
        """
        Apply force to the body.
        
        Args:
            force: Force vector (fx, fy)
            point: Point of application relative to center of mass
        """
        if self.is_static:
            return
            
        self.force += np.array(force)
        
        # Apply torque if force is not at center of mass
        if point is not None:
            rel_pos = np.array(point)
            torque = np.cross(rel_pos, force)
            self.torque += torque
            
    def apply_torque(self, torque: float) -> None:
        """Apply torque to the body"""
        if not self.is_static:
            self.torque += torque
            
    def apply_impulse(self, impulse: Tuple[float, float],
                     point: Optional[Tuple[float, float]] = None) -> None:
        """
        Apply impulse (instantaneous change in momentum).
        
        Args:
            impulse: Impulse vector (px, py)
            point: Point of application relative to center of mass
        """
        if self.is_static:
            return
            
        # Change linear velocity
        self.velocity += np.array(impulse) / self.mass
        
        # Change angular velocity if point is specified
        if point is not None:
            rel_pos = np.array(point)
            angular_impulse = np.cross(rel_pos, impulse)
            self.angular_velocity += angular_impulse / self.moment_of_inertia
            
    def get_velocity_at_point(self, point: Tuple[float, float]) -> np.ndarray:
        """
        Get velocity at a specific point on the body.
        
        Args:
            point: Point relative to center of mass
            
        Returns:
            Velocity vector at that point
        """
        rel_pos = np.array(point)
        # Linear velocity + velocity due to rotation
        tangent_velocity = np.array([-rel_pos[1], rel_pos[0]]) * self.angular_velocity
        return self.velocity + tangent_velocity
        
    def get_world_point(self, local_point: Tuple[float, float]) -> np.ndarray:
        """
        Transform local point to world coordinates.
        
        Args:
            local_point: Point in body's local coordinate system
            
        Returns:
            Point in world coordinates
        """
        cos_a = np.cos(self.angle)
        sin_a = np.sin(self.angle)
        
        # Rotation matrix
        rotation = np.array([[cos_a, -sin_a],
                           [sin_a, cos_a]])
        
        local = np.array(local_point)
        world = rotation @ local + self.position
        return world
        
    def get_local_point(self, world_point: Tuple[float, float]) -> np.ndarray:
        """
        Transform world point to local coordinates.
        
        Args:
            world_point: Point in world coordinates
            
        Returns:
            Point in body's local coordinate system
        """
        cos_a = np.cos(-self.angle)  # Inverse rotation
        sin_a = np.sin(-self.angle)
        
        # Inverse rotation matrix
        rotation = np.array([[cos_a, -sin_a],
                           [sin_a, cos_a]])
        
        world = np.array(world_point) - self.position
        local = rotation @ world
        return local
        
    def reset(self) -> None:
        """Reset body to initial state"""
        self.position = np.copy(self.initial_position)
        self.angle = self.initial_angle
        self.velocity = np.array([0.0, 0.0])
        self.angular_velocity = 0.0
        self.force = np.array([0.0, 0.0])
        self.torque = 0.0
        
    def get_kinetic_energy(self) -> float:
        """Calculate kinetic energy"""
        if self.is_static:
            return 0.0
            
        linear_ke = 0.5 * self.mass * np.dot(self.velocity, self.velocity)
        rotational_ke = 0.5 * self.moment_of_inertia * self.angular_velocity**2
        return linear_ke + rotational_ke
        
    def get_momentum(self) -> np.ndarray:
        """Get linear momentum"""
        return self.mass * self.velocity
        
    def get_angular_momentum(self) -> float:
        """Get angular momentum"""
        return self.moment_of_inertia * self.angular_velocity
        
    def set_mass(self, mass: float) -> None:
        """Set body mass and update moment of inertia"""
        self.mass = mass
        # Simple approximation for moment of inertia
        self.moment_of_inertia = mass * 0.1
        
    def __repr__(self) -> str:
        return (f"RigidBody(id={self.id}, pos={self.position}, "
                f"angle={self.angle:.2f}, mass={self.mass}, "
                f"type={self.body_type.value})")


class LinkageBody(RigidBody):
    """Specialized rigid body for linkage mechanisms"""
    
    def __init__(self, length: float, **kwargs):
        super().__init__(**kwargs)
        self.length = length
        # Update moment of inertia for rod
        self.moment_of_inertia = self.mass * self.length**2 / 12
        
    def get_end_position(self) -> np.ndarray:
        """Get position of end of linkage"""
        end_local = np.array([self.length / 2, 0])
        return self.get_world_point(end_local)
        
    def get_start_position(self) -> np.ndarray:
        """Get position of start of linkage"""
        start_local = np.array([-self.length / 2, 0])
        return self.get_world_point(start_local)


class GearBody(RigidBody):
    """Specialized rigid body for gear mechanisms"""
    
    def __init__(self, radius: float, teeth: int = 20, **kwargs):
        super().__init__(**kwargs)
        self.radius = radius
        self.teeth = teeth
        # Update moment of inertia for disc
        self.moment_of_inertia = 0.5 * self.mass * self.radius**2
        
    def get_pitch_circle_velocity(self) -> float:
        """Get velocity at pitch circle"""
        return self.radius * self.angular_velocity
        
    def get_gear_ratio(self, other_gear: 'GearBody') -> float:
        """Calculate gear ratio with another gear"""
        return other_gear.radius / self.radius