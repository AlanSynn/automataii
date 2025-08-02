"""
Lightweight Physics Engine - Main simulation engine

Provides PyBullet-free physics simulation for mechanism visualization.
"""

import numpy as np
from typing import List, Dict, Optional, Tuple
import time

from .body import RigidBody
from .constraints import Joint, SpringConstraint
from .world import PhysicsWorld


class PhysicsEngine:
    """
    Lightweight physics simulation engine.
    
    Simulates rigid body dynamics, joints, springs, and collisions
    without requiring PyBullet dependency.
    """
    
    def __init__(self, gravity: Tuple[float, float] = (0, -9.81)):
        """Initialize physics engine with gravity"""
        self.world = PhysicsWorld(gravity)
        self.bodies: List[RigidBody] = []
        self.joints: List[Joint] = []
        self.springs: List[SpringConstraint] = []
        
        # Simulation parameters
        self.dt = 1.0 / 60.0  # 60 FPS
        self.max_substeps = 4
        self.damping = 0.98
        
        # Performance tracking
        self.last_step_time = 0.0
        self.is_running = False
        
    def add_body(self, body: RigidBody) -> int:
        """Add a rigid body to the simulation"""
        body.id = len(self.bodies)
        self.bodies.append(body)
        return body.id
        
    def add_joint(self, joint: Joint) -> int:
        """Add a joint constraint"""
        joint.id = len(self.joints)
        self.joints.append(joint)
        return joint.id
        
    def add_spring(self, spring: SpringConstraint) -> int:
        """Add a spring constraint"""
        spring.id = len(self.springs)
        self.springs.append(spring)
        return spring.id
        
    def remove_body(self, body_id: int):
        """Remove a body from simulation"""
        if 0 <= body_id < len(self.bodies):
            self.bodies[body_id] = None
            
    def get_body(self, body_id: int) -> Optional[RigidBody]:
        """Get body by ID"""
        if 0 <= body_id < len(self.bodies):
            return self.bodies[body_id]
        return None
        
    def step_simulation(self, dt: Optional[float] = None) -> None:
        """
        Step the physics simulation forward in time.
        
        Args:
            dt: Time step (uses default if None)
        """
        if dt is None:
            dt = self.dt
            
        start_time = time.time()
        
        # Use sub-stepping for stability
        sub_dt = dt / self.max_substeps
        
        for _ in range(self.max_substeps):
            self._integrate_step(sub_dt)
            
        self.last_step_time = time.time() - start_time
        
    def _integrate_step(self, dt: float) -> None:
        """Single integration step"""
        # Apply forces
        self._apply_forces()
        
        # Integrate velocities and positions
        self._integrate_bodies(dt)
        
        # Solve constraints
        self._solve_constraints(dt)
        
        # Apply damping
        self._apply_damping()
        
    def _apply_forces(self) -> None:
        """Apply external forces (gravity, springs, etc.)"""
        # Apply gravity
        for body in self.bodies:
            if body and not body.is_static:
                body.force[1] += body.mass * self.world.gravity[1]
                
        # Apply spring forces
        for spring in self.springs:
            if spring:
                spring.apply_force()
                
    def _integrate_bodies(self, dt: float) -> None:
        """Integrate body velocities and positions"""
        for body in self.bodies:
            if body and not body.is_static:
                # Integrate linear motion
                body.acceleration = body.force / body.mass
                body.velocity += body.acceleration * dt
                body.position += body.velocity * dt
                
                # Integrate angular motion
                body.angular_acceleration = body.torque / body.moment_of_inertia
                body.angular_velocity += body.angular_acceleration * dt
                body.angle += body.angular_velocity * dt
                
                # Clear forces for next frame
                body.force = np.array([0.0, 0.0])
                body.torque = 0.0
                
    def _solve_constraints(self, dt: float) -> None:
        """Solve joint and other constraints"""
        # Simple constraint solving using position correction
        for joint in self.joints:
            if joint:
                joint.solve_constraint(dt)
                
    def _apply_damping(self) -> None:
        """Apply velocity damping for stability"""
        for body in self.bodies:
            if body and not body.is_static:
                body.velocity *= self.damping
                body.angular_velocity *= self.damping
                
    def set_gravity(self, gravity: Tuple[float, float]) -> None:
        """Set world gravity"""
        self.world.gravity = np.array(gravity)
        
    def get_body_position(self, body_id: int) -> Optional[Tuple[float, float]]:
        """Get body position"""
        body = self.get_body(body_id)
        if body:
            return tuple(body.position)
        return None
        
    def get_body_angle(self, body_id: int) -> Optional[float]:
        """Get body rotation angle"""
        body = self.get_body(body_id)
        if body:
            return body.angle
        return None
        
    def set_body_position(self, body_id: int, position: Tuple[float, float]) -> None:
        """Set body position"""
        body = self.get_body(body_id)
        if body:
            body.position = np.array(position)
            
    def set_body_angle(self, body_id: int, angle: float) -> None:
        """Set body angle"""
        body = self.get_body(body_id)
        if body:
            body.angle = angle
            
    def apply_force(self, body_id: int, force: Tuple[float, float], 
                   position: Optional[Tuple[float, float]] = None) -> None:
        """Apply force to a body"""
        body = self.get_body(body_id)
        if body:
            body.force += np.array(force)
            
            # Apply torque if force is not at center of mass
            if position:
                rel_pos = np.array(position) - body.position
                torque = np.cross(rel_pos, force)
                body.torque += torque
                
    def apply_torque(self, body_id: int, torque: float) -> None:
        """Apply torque to a body"""
        body = self.get_body(body_id)
        if body:
            body.torque += torque
            
    def reset_simulation(self) -> None:
        """Reset simulation to initial state"""
        for body in self.bodies:
            if body:
                body.reset()
                
    def get_kinetic_energy(self) -> float:
        """Calculate total kinetic energy"""
        total_energy = 0.0
        for body in self.bodies:
            if body and not body.is_static:
                # Linear kinetic energy
                linear_ke = 0.5 * body.mass * np.dot(body.velocity, body.velocity)
                # Rotational kinetic energy
                rotational_ke = 0.5 * body.moment_of_inertia * body.angular_velocity**2
                total_energy += linear_ke + rotational_ke
        return total_energy
        
    def get_potential_energy(self) -> float:
        """Calculate total potential energy"""
        total_energy = 0.0
        for body in self.bodies:
            if body and not body.is_static:
                # Gravitational potential energy
                height = body.position[1]
                pe = body.mass * abs(self.world.gravity[1]) * height
                total_energy += pe
        return total_energy
        
    def get_performance_stats(self) -> Dict[str, float]:
        """Get performance statistics"""
        return {
            'last_step_time': self.last_step_time,
            'fps': 1.0 / max(self.last_step_time, 1e-6),
            'body_count': len([b for b in self.bodies if b]),
            'joint_count': len([j for j in self.joints if j]),
            'spring_count': len([s for s in self.springs if s]),
            'kinetic_energy': self.get_kinetic_energy(),
            'potential_energy': self.get_potential_energy()
        }