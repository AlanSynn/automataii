"""
Physics Constraints - Joint and spring constraints

Provides constraint solving for joints, springs, and other connections.
"""

import numpy as np
from typing import Optional, Tuple
from abc import ABC, abstractmethod

from .body import RigidBody


class Constraint(ABC):
    """Base class for physics constraints"""
    
    def __init__(self):
        self.id: Optional[int] = None
        self.enabled = True
        
    @abstractmethod
    def solve_constraint(self, dt: float) -> None:
        """Solve the constraint"""
        pass


class Joint(Constraint):
    """
    Joint constraint connecting two rigid bodies.
    
    Maintains a fixed distance between anchor points on two bodies.
    """
    
    def __init__(self, 
                 body_a: RigidBody, 
                 body_b: RigidBody,
                 anchor_a: Tuple[float, float] = (0, 0),
                 anchor_b: Tuple[float, float] = (0, 0),
                 allow_rotation: bool = True):
        """
        Initialize joint constraint.
        
        Args:
            body_a: First body
            body_b: Second body  
            anchor_a: Anchor point on body A (local coordinates)
            anchor_b: Anchor point on body B (local coordinates)
            allow_rotation: Whether bodies can rotate around joint
        """
        super().__init__()
        self.body_a = body_a
        self.body_b = body_b
        self.anchor_a = np.array(anchor_a)
        self.anchor_b = np.array(anchor_b)
        self.allow_rotation = allow_rotation
        
        # Constraint parameters
        self.stiffness = 0.8  # How strongly to enforce constraint
        self.damping = 0.1    # Velocity damping at joint
        
    def solve_constraint(self, dt: float) -> None:
        """Solve joint constraint using position correction"""
        if not self.enabled:
            return
            
        # Get world positions of anchor points
        world_a = self.body_a.get_world_point(self.anchor_a)
        world_b = self.body_b.get_world_point(self.anchor_b)
        
        # Calculate constraint error (distance between anchors)
        error = world_b - world_a
        error_magnitude = np.linalg.norm(error)
        
        if error_magnitude < 1e-6:
            return
            
        # Normalize error direction
        error_direction = error / error_magnitude
        
        # Calculate relative velocity at joint
        vel_a = self.body_a.get_velocity_at_point(self.anchor_a)
        vel_b = self.body_b.get_velocity_at_point(self.anchor_b)
        relative_velocity = vel_b - vel_a
        
        # Velocity along constraint direction
        velocity_error = np.dot(relative_velocity, error_direction)
        
        # Calculate impulse magnitude
        total_inv_mass = 0.0
        if not self.body_a.is_static:
            total_inv_mass += 1.0 / self.body_a.mass
        if not self.body_b.is_static:
            total_inv_mass += 1.0 / self.body_b.mass
            
        if total_inv_mass < 1e-6:
            return
            
        # Position correction impulse
        position_impulse = self.stiffness * error_magnitude / total_inv_mass
        
        # Velocity correction impulse  
        velocity_impulse = self.damping * velocity_error / total_inv_mass
        
        total_impulse = position_impulse + velocity_impulse
        impulse = total_impulse * error_direction
        
        # Apply impulses to bodies
        if not self.body_a.is_static:
            self.body_a.apply_impulse(-impulse, self.anchor_a)
            
        if not self.body_b.is_static:
            self.body_b.apply_impulse(impulse, self.anchor_b)


class SpringConstraint(Constraint):
    """
    Spring constraint between two bodies.
    
    Applies forces proportional to distance from rest length.
    """
    
    def __init__(self,
                 body_a: RigidBody,
                 body_b: RigidBody,
                 anchor_a: Tuple[float, float] = (0, 0),
                 anchor_b: Tuple[float, float] = (0, 0),
                 rest_length: float = 1.0,
                 stiffness: float = 100.0,
                 damping: float = 10.0):
        """
        Initialize spring constraint.
        
        Args:
            body_a: First body
            body_b: Second body
            anchor_a: Anchor point on body A (local coordinates)
            anchor_b: Anchor point on body B (local coordinates)
            rest_length: Natural length of spring
            stiffness: Spring constant (k)
            damping: Damping coefficient
        """
        super().__init__()
        self.body_a = body_a
        self.body_b = body_b
        self.anchor_a = np.array(anchor_a)
        self.anchor_b = np.array(anchor_b)
        self.rest_length = rest_length
        self.stiffness = stiffness
        self.damping = damping
        
    def apply_force(self) -> None:
        """Apply spring forces to connected bodies"""
        if not self.enabled:
            return
            
        # Get world positions of anchor points
        world_a = self.body_a.get_world_point(self.anchor_a)
        world_b = self.body_b.get_world_point(self.anchor_b)
        
        # Calculate spring vector and length
        spring_vector = world_b - world_a
        current_length = np.linalg.norm(spring_vector)
        
        if current_length < 1e-6:
            return
            
        # Unit vector along spring
        spring_direction = spring_vector / current_length
        
        # Spring force (Hooke's law)
        extension = current_length - self.rest_length
        spring_force_magnitude = self.stiffness * extension
        
        # Damping force
        vel_a = self.body_a.get_velocity_at_point(self.anchor_a)
        vel_b = self.body_b.get_velocity_at_point(self.anchor_b)
        relative_velocity = vel_b - vel_a
        
        # Velocity component along spring
        velocity_component = np.dot(relative_velocity, spring_direction)
        damping_force_magnitude = self.damping * velocity_component
        
        # Total force
        total_force_magnitude = spring_force_magnitude + damping_force_magnitude
        force = total_force_magnitude * spring_direction
        
        # Apply forces (Newton's third law)
        if not self.body_a.is_static:
            self.body_a.apply_force(force, self.anchor_a)
            
        if not self.body_b.is_static:
            self.body_b.apply_force(-force, self.anchor_b)
            
    def solve_constraint(self, dt: float) -> None:
        """Springs don't need constraint solving, just force application"""
        self.apply_force()
        
    def get_current_length(self) -> float:
        """Get current length of spring"""
        world_a = self.body_a.get_world_point(self.anchor_a)
        world_b = self.body_b.get_world_point(self.anchor_b)
        return np.linalg.norm(world_b - world_a)
        
    def get_extension(self) -> float:
        """Get spring extension from rest length"""
        return self.get_current_length() - self.rest_length
        
    def get_potential_energy(self) -> float:
        """Get elastic potential energy stored in spring"""
        extension = self.get_extension()
        return 0.5 * self.stiffness * extension**2


class DistanceConstraint(Constraint):
    """
    Distance constraint maintaining fixed distance between points.
    
    Similar to Joint but without rotation considerations.
    """
    
    def __init__(self,
                 body_a: RigidBody,
                 body_b: RigidBody,
                 anchor_a: Tuple[float, float] = (0, 0),
                 anchor_b: Tuple[float, float] = (0, 0),
                 distance: Optional[float] = None):
        """
        Initialize distance constraint.
        
        Args:
            body_a: First body
            body_b: Second body
            anchor_a: Point on body A (local coordinates)
            anchor_b: Point on body B (local coordinates)
            distance: Fixed distance (calculated from initial positions if None)
        """
        super().__init__()
        self.body_a = body_a
        self.body_b = body_b
        self.anchor_a = np.array(anchor_a)
        self.anchor_b = np.array(anchor_b)
        
        # Calculate distance if not provided
        if distance is None:
            world_a = self.body_a.get_world_point(self.anchor_a)
            world_b = self.body_b.get_world_point(self.anchor_b)
            self.distance = np.linalg.norm(world_b - world_a)
        else:
            self.distance = distance
            
        self.stiffness = 1.0
        
    def solve_constraint(self, dt: float) -> None:
        """Solve distance constraint"""
        if not self.enabled:
            return
            
        # Get world positions
        world_a = self.body_a.get_world_point(self.anchor_a)
        world_b = self.body_b.get_world_point(self.anchor_b)
        
        # Calculate current distance and error
        current_vector = world_b - world_a
        current_distance = np.linalg.norm(current_vector)
        
        if current_distance < 1e-6:
            return
            
        error = current_distance - self.distance
        direction = current_vector / current_distance
        
        # Position correction
        correction = self.stiffness * error * direction
        
        # Apply corrections
        if not self.body_a.is_static and not self.body_b.is_static:
            # Both bodies can move
            mass_ratio_a = self.body_b.mass / (self.body_a.mass + self.body_b.mass)
            mass_ratio_b = self.body_a.mass / (self.body_a.mass + self.body_b.mass)
            
            self.body_a.position += correction * mass_ratio_a
            self.body_b.position -= correction * mass_ratio_b
            
        elif not self.body_a.is_static:
            # Only body A can move
            self.body_a.position += correction
            
        elif not self.body_b.is_static:
            # Only body B can move
            self.body_b.position -= correction


class MotorConstraint(Constraint):
    """
    Motor constraint that applies torque to maintain angular velocity.
    """
    
    def __init__(self, body: RigidBody, target_velocity: float, max_torque: float = 100.0):
        """
        Initialize motor constraint.
        
        Args:
            body: Body to control
            target_velocity: Target angular velocity (rad/s)
            max_torque: Maximum torque to apply
        """
        super().__init__()
        self.body = body
        self.target_velocity = target_velocity
        self.max_torque = max_torque
        self.kp = 50.0  # Proportional gain
        self.kd = 5.0   # Derivative gain
        
    def solve_constraint(self, dt: float) -> None:
        """Apply motor torque"""
        if not self.enabled or self.body.is_static:
            return
            
        # PD control
        velocity_error = self.target_velocity - self.body.angular_velocity
        torque = self.kp * velocity_error - self.kd * self.body.angular_velocity
        
        # Clamp torque
        torque = np.clip(torque, -self.max_torque, self.max_torque)
        
        self.body.apply_torque(torque)
        
    def set_target_velocity(self, velocity: float) -> None:
        """Set new target velocity"""
        self.target_velocity = velocity