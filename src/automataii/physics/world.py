"""
Physics World - World settings and environment

Manages global physics settings like gravity, boundaries, and collision detection.
"""

import numpy as np
from typing import Tuple, List, Optional
from dataclasses import dataclass


@dataclass
class CollisionInfo:
    """Information about a collision between two bodies"""
    body_a_id: int
    body_b_id: int
    contact_point: Tuple[float, float]
    normal: Tuple[float, float]
    penetration: float
    

class PhysicsWorld:
    """
    Physics world containing global settings and collision detection.
    """
    
    def __init__(self, gravity: Tuple[float, float] = (0, -9.81)):
        """
        Initialize physics world.
        
        Args:
            gravity: Gravity vector (gx, gy) in m/s²
        """
        self.gravity = np.array(gravity, dtype=float)
        
        # World boundaries
        self.has_boundaries = False
        self.boundary_min = np.array([-10.0, -10.0])
        self.boundary_max = np.array([10.0, 10.0])
        self.boundary_restitution = 0.8
        
        # Collision detection
        self.collision_enabled = True
        self.collision_iterations = 4
        
        # Performance settings
        self.broad_phase_enabled = True
        self.sleep_enabled = True
        self.sleep_velocity_threshold = 0.01
        self.sleep_angular_threshold = 0.01
        
    def set_gravity(self, gravity: Tuple[float, float]) -> None:
        """Set world gravity"""
        self.gravity = np.array(gravity, dtype=float)
        
    def set_boundaries(self, 
                      min_point: Tuple[float, float],
                      max_point: Tuple[float, float],
                      enabled: bool = True) -> None:
        """
        Set world boundaries.
        
        Args:
            min_point: Minimum (bottom-left) boundary point
            max_point: Maximum (top-right) boundary point
            enabled: Whether boundaries are active
        """
        self.boundary_min = np.array(min_point)
        self.boundary_max = np.array(max_point)
        self.has_boundaries = enabled
        
    def check_boundaries(self, body) -> None:
        """
        Check and enforce world boundaries for a body.
        
        Args:
            body: RigidBody to check
        """
        if not self.has_boundaries or body.is_static:
            return
            
        # Check X boundaries
        if body.position[0] < self.boundary_min[0]:
            body.position[0] = self.boundary_min[0]
            body.velocity[0] = -body.velocity[0] * self.boundary_restitution
            
        elif body.position[0] > self.boundary_max[0]:
            body.position[0] = self.boundary_max[0]
            body.velocity[0] = -body.velocity[0] * self.boundary_restitution
            
        # Check Y boundaries  
        if body.position[1] < self.boundary_min[1]:
            body.position[1] = self.boundary_min[1]
            body.velocity[1] = -body.velocity[1] * self.boundary_restitution
            
        elif body.position[1] > self.boundary_max[1]:
            body.position[1] = self.boundary_max[1]
            body.velocity[1] = -body.velocity[1] * self.boundary_restitution
            
    def detect_collisions(self, bodies: List) -> List[CollisionInfo]:
        """
        Detect collisions between bodies.
        
        Args:
            bodies: List of RigidBody objects
            
        Returns:
            List of collision information
        """
        collisions = []
        
        if not self.collision_enabled:
            return collisions
            
        # Simple O(n²) collision detection
        for i, body_a in enumerate(bodies):
            if not body_a:
                continue
                
            for j, body_b in enumerate(bodies[i+1:], i+1):
                if not body_b:
                    continue
                    
                # Skip if both bodies are static
                if body_a.is_static and body_b.is_static:
                    continue
                    
                collision = self._check_body_collision(body_a, body_b)
                if collision:
                    collisions.append(collision)
                    
        return collisions
        
    def _check_body_collision(self, body_a, body_b) -> Optional[CollisionInfo]:
        """
        Check collision between two bodies (simplified as circles).
        
        Args:
            body_a: First body
            body_b: Second body
            
        Returns:
            CollisionInfo if collision detected, None otherwise
        """
        # Simple circle-circle collision detection
        # Assume bodies have a radius based on their mass
        radius_a = np.sqrt(body_a.mass) * 0.5
        radius_b = np.sqrt(body_b.mass) * 0.5
        
        distance_vector = body_b.position - body_a.position
        distance = np.linalg.norm(distance_vector)
        
        min_distance = radius_a + radius_b
        
        if distance < min_distance:
            # Collision detected
            if distance > 1e-6:
                normal = distance_vector / distance
            else:
                normal = np.array([1.0, 0.0])  # Arbitrary direction
                
            penetration = min_distance - distance
            contact_point = body_a.position + normal * radius_a
            
            return CollisionInfo(
                body_a_id=body_a.id,
                body_b_id=body_b.id,
                contact_point=tuple(contact_point),
                normal=tuple(normal),
                penetration=penetration
            )
            
        return None
        
    def resolve_collision(self, collision: CollisionInfo, body_a, body_b) -> None:
        """
        Resolve a collision between two bodies.
        
        Args:
            collision: Collision information
            body_a: First body
            body_b: Second body
        """
        normal = np.array(collision.normal)
        
        # Separate bodies
        if not body_a.is_static and not body_b.is_static:
            # Both bodies can move
            separation = collision.penetration * 0.5 * normal
            body_a.position -= separation
            body_b.position += separation
        elif not body_a.is_static:
            # Only body A can move
            body_a.position -= collision.penetration * normal
        elif not body_b.is_static:
            # Only body B can move
            body_b.position += collision.penetration * normal
            
        # Calculate collision response
        relative_velocity = body_b.velocity - body_a.velocity
        velocity_along_normal = np.dot(relative_velocity, normal)
        
        # Don't resolve if velocities are separating
        if velocity_along_normal > 0:
            return
            
        # Calculate restitution (bounciness)
        restitution = min(body_a.restitution, body_b.restitution)
        
        # Calculate impulse magnitude
        impulse_magnitude = -(1 + restitution) * velocity_along_normal
        
        if not body_a.is_static and not body_b.is_static:
            impulse_magnitude /= (1/body_a.mass + 1/body_b.mass)
        elif not body_a.is_static:
            impulse_magnitude /= (1/body_a.mass)
        elif not body_b.is_static:
            impulse_magnitude /= (1/body_b.mass)
        else:
            return  # Both static
            
        impulse = impulse_magnitude * normal
        
        # Apply impulse
        if not body_a.is_static:
            body_a.velocity -= impulse / body_a.mass
            
        if not body_b.is_static:
            body_b.velocity += impulse / body_b.mass
            
        # Apply friction
        self._apply_friction(collision, body_a, body_b, impulse_magnitude)
        
    def _apply_friction(self, collision: CollisionInfo, body_a, body_b, normal_impulse: float) -> None:
        """Apply friction forces during collision"""
        normal = np.array(collision.normal)
        relative_velocity = body_b.velocity - body_a.velocity
        
        # Calculate tangent vector
        velocity_along_normal = np.dot(relative_velocity, normal)
        tangent = relative_velocity - velocity_along_normal * normal
        
        if np.linalg.norm(tangent) < 1e-6:
            return
            
        tangent = tangent / np.linalg.norm(tangent)
        
        # Calculate friction impulse
        friction_coefficient = (body_a.friction + body_b.friction) * 0.5
        friction_impulse_magnitude = -np.dot(relative_velocity, tangent)
        
        if not body_a.is_static and not body_b.is_static:
            friction_impulse_magnitude /= (1/body_a.mass + 1/body_b.mass)
        elif not body_a.is_static:
            friction_impulse_magnitude /= (1/body_a.mass)
        elif not body_b.is_static:
            friction_impulse_magnitude /= (1/body_b.mass)
        else:
            return
            
        # Coulomb friction
        max_friction = friction_coefficient * normal_impulse
        friction_impulse_magnitude = np.clip(friction_impulse_magnitude, -max_friction, max_friction)
        
        friction_impulse = friction_impulse_magnitude * tangent
        
        # Apply friction impulse
        if not body_a.is_static:
            body_a.velocity -= friction_impulse / body_a.mass
            
        if not body_b.is_static:
            body_b.velocity += friction_impulse / body_b.mass
            
    def is_body_sleeping(self, body) -> bool:
        """
        Check if a body should be put to sleep (optimization).
        
        Args:
            body: RigidBody to check
            
        Returns:
            True if body can sleep
        """
        if not self.sleep_enabled or body.is_static:
            return False
            
        velocity_magnitude = np.linalg.norm(body.velocity)
        angular_velocity_magnitude = abs(body.angular_velocity)
        
        return (velocity_magnitude < self.sleep_velocity_threshold and 
                angular_velocity_magnitude < self.sleep_angular_threshold)
                
    def get_world_info(self) -> dict:
        """Get world information for debugging"""
        return {
            'gravity': tuple(self.gravity),
            'has_boundaries': self.has_boundaries,
            'boundary_min': tuple(self.boundary_min),
            'boundary_max': tuple(self.boundary_max),
            'collision_enabled': self.collision_enabled,
            'sleep_enabled': self.sleep_enabled
        }