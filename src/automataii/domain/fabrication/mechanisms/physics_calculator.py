"""
Physics calculator for mechanism analysis.
Calculates forces, velocities, and stresses for visualization.
"""

import math
from typing import Dict, List, Tuple, Optional
from PyQt6.QtCore import QPointF


class MechanismPhysicsCalculator:
    """
    Calculates physics properties for mechanism visualization.
    
    This includes:
    - Force analysis (static and dynamic)
    - Velocity analysis
    - Acceleration analysis
    - Stress in links
    """
    
    def __init__(self):
        self.prev_positions = {}  # For velocity calculation
        self.prev_velocities = {}  # For acceleration calculation
        self.time_step = 0.016  # 60 FPS
        
    def calculate_velocities(self, mechanism) -> Dict[int, Tuple[float, float]]:
        """Calculate velocity vectors for all points."""
        velocities = {}
        
        for i, point in enumerate(mechanism.points):
            if point.fixed:
                velocities[i] = (0.0, 0.0)
            else:
                # Calculate velocity from position difference
                if i in self.prev_positions:
                    prev_x, prev_y = self.prev_positions[i]
                    vx = (point.x - prev_x) / self.time_step
                    vy = (point.y - prev_y) / self.time_step
                    velocities[i] = (vx, vy)
                else:
                    velocities[i] = (0.0, 0.0)
                
                # Store current position for next frame
                self.prev_positions[i] = (point.x, point.y)
                
                # Store motion trail for visual effect
                if not hasattr(point, 'prev_positions'):
                    point.prev_positions = []
                point.prev_positions.append((point.x, point.y))
                if len(point.prev_positions) > 10:
                    point.prev_positions.pop(0)
        
        return velocities
    
    def calculate_forces(self, mechanism) -> Dict[int, Tuple[float, float]]:
        """
        Calculate forces at each joint.
        For now, simplified force analysis based on motion.
        """
        forces = {}
        velocities = self.calculate_velocities(mechanism)
        
        for i, point in enumerate(mechanism.points):
            if point.fixed:
                # Fixed points experience reaction forces
                # Calculate based on connected links
                fx, fy = 0.0, 0.0
                
                for link in mechanism.links:
                    if link.point1 == point or link.point2 == point:
                        # Simple force calculation based on link angle
                        other_point = link.point2 if link.point1 == point else link.point1
                        dx = other_point.x - point.x
                        dy = other_point.y - point.y
                        length = math.sqrt(dx*dx + dy*dy) if dx*dx + dy*dy > 0 else 1
                        
                        # Normalize and scale force
                        force_magnitude = 50.0  # Base force
                        fx += (dx / length) * force_magnitude
                        fy += (dy / length) * force_magnitude
                
                forces[i] = (fx, fy)
            else:
                # Moving points - calculate inertial forces
                if i in velocities and i in self.prev_velocities:
                    prev_vx, prev_vy = self.prev_velocities[i]
                    vx, vy = velocities[i]
                    
                    # F = ma (simplified with unit mass)
                    ax = (vx - prev_vx) / self.time_step
                    ay = (vy - prev_vy) / self.time_step
                    
                    # Scale for visualization
                    mass = 1.0
                    forces[i] = (mass * ax * 0.1, mass * ay * 0.1)
                else:
                    forces[i] = (0.0, 0.0)
        
        # Store velocities for next frame
        self.prev_velocities = velocities
        
        return forces
    
    def calculate_link_stresses(self, mechanism) -> Dict[int, float]:
        """
        Calculate stress in each link.
        Positive = tension, Negative = compression
        """
        stresses = {}
        forces = self.calculate_forces(mechanism)
        
        for i, link in enumerate(mechanism.links):
            # Find points indices
            p1_idx = mechanism.points.index(link.point1)
            p2_idx = mechanism.points.index(link.point2)
            
            # Get forces at endpoints
            f1 = forces.get(p1_idx, (0, 0))
            f2 = forces.get(p2_idx, (0, 0))
            
            # Calculate link direction
            dx = link.point2.x - link.point1.x
            dy = link.point2.y - link.point1.y
            length = math.sqrt(dx*dx + dy*dy) if dx*dx + dy*dy > 0 else 1
            
            # Unit vector along link
            ux = dx / length
            uy = dy / length
            
            # Project forces onto link direction
            # Tension is positive when forces pull apart
            tension1 = f1[0] * ux + f1[1] * uy
            tension2 = -f2[0] * ux - f2[1] * uy
            
            # Average stress (normalized to -1 to 1 range)
            stress = (tension1 + tension2) / 2.0 / 100.0
            stress = max(-1.0, min(1.0, stress))
            
            stresses[i] = stress
        
        return stresses
    
    def calculate_mechanical_advantage(self, mechanism, input_link_idx: int, 
                                     output_link_idx: int) -> float:
        """Calculate mechanical advantage between input and output."""
        velocities = self.calculate_velocities(mechanism)
        
        # Get angular velocities of input and output
        if input_link_idx < len(mechanism.links) and output_link_idx < len(mechanism.links):
            input_link = mechanism.links[input_link_idx]
            output_link = mechanism.links[output_link_idx]
            
            # Calculate angular velocities
            # (simplified - assumes one end is fixed)
            input_omega = self._calculate_angular_velocity(input_link, velocities, mechanism)
            output_omega = self._calculate_angular_velocity(output_link, velocities, mechanism)
            
            if abs(output_omega) > 0.001:
                return abs(input_omega / output_omega)
        
        return 1.0
    
    def _calculate_angular_velocity(self, link, velocities: Dict, mechanism) -> float:
        """Calculate angular velocity of a link."""
        # Find point indices
        p1_idx = mechanism.points.index(link.point1)
        p2_idx = mechanism.points.index(link.point2)
        
        v1 = velocities.get(p1_idx, (0, 0))
        v2 = velocities.get(p2_idx, (0, 0))
        
        # Relative velocity
        dvx = v2[0] - v1[0]
        dvy = v2[1] - v1[1]
        
        # Link vector
        dx = link.point2.x - link.point1.x
        dy = link.point2.y - link.point1.y
        length_sq = dx*dx + dy*dy
        
        if length_sq > 0.001:
            # Angular velocity = perpendicular component / length
            omega = (dvx * (-dy) + dvy * dx) / length_sq
            return omega
        
        return 0.0
    
    def reset(self):
        """Reset calculator state."""
        self.prev_positions.clear()
        self.prev_velocities.clear()