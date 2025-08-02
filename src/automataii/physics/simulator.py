"""
Physics Simulator Integration

Integrates the lightweight physics engine with the existing mechanism visualization system.
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from PyQt6.QtCore import QTimer, QObject, pyqtSignal
import time
from dataclasses import dataclass

from .engine import PhysicsEngine
from .mechanisms import create_mechanism, PhysicsMechanism


@dataclass
class MechanismData:
    """Simple mechanism data structure for physics simulation"""
    mechanism_type: str
    parameters: Dict[str, Any]


class PhysicsSimulator(QObject):
    """
    Physics simulator that integrates with the existing mechanism system.
    
    Provides PyBullet-free physics simulation with Qt integration.
    """
    
    # Signals
    simulation_updated = pyqtSignal(dict)  # positions, velocities, etc.
    collision_detected = pyqtSignal(str)   # collision info
    energy_changed = pyqtSignal(float, float)  # kinetic, potential
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Physics engine
        self.engine = PhysicsEngine(gravity=(0, -9.81))
        
        # Current mechanism
        self.current_mechanism: Optional[PhysicsMechanism] = None
        self.mechanism_data: Optional[MechanismData] = None
        
        # Simulation state
        self.is_running = False
        self.simulation_speed = 1.0
        self.time_step = 1.0 / 60.0  # 60 FPS
        
        # Qt timer for simulation loop
        self.timer = QTimer()
        self.timer.timeout.connect(self._simulation_step)
        
        # Performance tracking
        self.frame_count = 0
        self.last_fps_time = time.time()
        self.current_fps = 0.0
        
        # Visualization data
        self.body_positions: Dict[int, Tuple[float, float]] = {}
        self.body_angles: Dict[int, float] = {}
        self.constraint_forces: Dict[int, float] = {}
        
    def set_mechanism(self, mechanism_data: MechanismData) -> bool:
        """
        Set the mechanism to simulate.
        
        Args:
            mechanism_data: Mechanism configuration
            
        Returns:
            True if mechanism was successfully created
        """
        try:
            self.stop_simulation()
            
            # Store mechanism data
            self.mechanism_data = mechanism_data
            
            # Create physics mechanism based on type
            mechanism_type = self._get_physics_mechanism_type(mechanism_data)
            
            if mechanism_type:
                # Reset engine
                self.engine = PhysicsEngine(gravity=(0, -9.81))
                
                # Create mechanism
                self.current_mechanism = create_mechanism(
                    mechanism_type, 
                    self.engine,
                    **self._extract_mechanism_parameters(mechanism_data)
                )
                
                if self.current_mechanism:
                    self._initialize_visualization_data()
                    return True
                    
        except Exception as e:
            print(f"Error creating physics mechanism: {e}")
            
        return False
        
    def start_simulation(self) -> None:
        """Start physics simulation"""
        if self.current_mechanism and not self.is_running:
            self.is_running = True
            # Run at 60 FPS (16.67ms intervals)
            self.timer.start(int(1000 * self.time_step / self.simulation_speed))
            
    def stop_simulation(self) -> None:
        """Stop physics simulation"""
        self.is_running = False
        self.timer.stop()
        
    def pause_simulation(self) -> None:
        """Pause/unpause simulation"""
        if self.is_running:
            self.stop_simulation()
        else:
            self.start_simulation()
            
    def reset_simulation(self) -> None:
        """Reset simulation to initial state"""
        if self.current_mechanism:
            self.current_mechanism.reset()
            self._update_visualization_data()
            
    def set_simulation_speed(self, speed: float) -> None:
        """
        Set simulation speed multiplier.
        
        Args:
            speed: Speed multiplier (1.0 = normal, 2.0 = 2x speed, etc.)
        """
        self.simulation_speed = max(0.1, min(10.0, speed))
        
        if self.is_running:
            # Restart timer with new speed
            self.timer.start(int(1000 * self.time_step / self.simulation_speed))
            
    def set_gravity(self, gravity: Tuple[float, float]) -> None:
        """Set world gravity"""
        self.engine.set_gravity(gravity)
        
    def update_mechanism_parameters(self, parameters: Dict[str, float]) -> None:
        """Update mechanism parameters in real-time"""
        if self.current_mechanism:
            self.current_mechanism.update_parameters(parameters)
            
    def get_simulation_data(self) -> Dict[str, Any]:
        """
        Get current simulation data for visualization.
        
        Returns:
            Dictionary containing positions, angles, velocities, etc.
        """
        if not self.current_mechanism:
            return {}
            
        return {
            'body_positions': self.body_positions.copy(),
            'body_angles': self.body_angles.copy(),
            'constraint_forces': self.constraint_forces.copy(),
            'kinetic_energy': self.engine.get_kinetic_energy(),
            'potential_energy': self.engine.get_potential_energy(),
            'fps': self.current_fps,
            'is_running': self.is_running
        }
        
    def get_body_position(self, body_id: int) -> Optional[Tuple[float, float]]:
        """Get position of specific body"""
        return self.body_positions.get(body_id)
        
    def get_body_angle(self, body_id: int) -> Optional[float]:
        """Get angle of specific body"""
        return self.body_angles.get(body_id)
        
    def apply_force_to_body(self, body_id: int, force: Tuple[float, float]) -> None:
        """Apply external force to a body"""
        self.engine.apply_force(body_id, force)
        
    def _simulation_step(self) -> None:
        """Single simulation step"""
        if not self.current_mechanism:
            return
            
        try:
            # Step physics
            self.engine.step_simulation(self.time_step)
            
            # Update visualization data
            self._update_visualization_data()
            
            # Update FPS
            self._update_fps()
            
            # Check for collisions
            self._check_collisions()
            
            # Emit update signal
            self.simulation_updated.emit(self.get_simulation_data())
            
        except Exception as e:
            print(f"Physics simulation error: {e}")
            self.stop_simulation()
            
    def _update_visualization_data(self) -> None:
        """Update visualization data from physics bodies"""
        if not self.current_mechanism:
            return
            
        # Update body positions and angles
        for i, body in enumerate(self.current_mechanism.bodies):
            if body:
                self.body_positions[i] = tuple(body.position)
                self.body_angles[i] = body.angle
                
    def _initialize_visualization_data(self) -> None:
        """Initialize visualization data structures"""
        self.body_positions.clear()
        self.body_angles.clear()
        self.constraint_forces.clear()
        
        if self.current_mechanism:
            for i, body in enumerate(self.current_mechanism.bodies):
                if body:
                    self.body_positions[i] = tuple(body.position)
                    self.body_angles[i] = body.angle
                    
    def _update_fps(self) -> None:
        """Update FPS calculation"""
        self.frame_count += 1
        current_time = time.time()
        
        if current_time - self.last_fps_time >= 1.0:  # Update every second
            self.current_fps = self.frame_count / (current_time - self.last_fps_time)
            self.frame_count = 0
            self.last_fps_time = current_time
            
    def _check_collisions(self) -> None:
        """Check for collisions and emit signals"""
        if not self.current_mechanism:
            return
            
        collisions = self.engine.world.detect_collisions(self.current_mechanism.bodies)
        
        for collision in collisions:
            # Resolve collision
            body_a = self.engine.get_body(collision.body_a_id)
            body_b = self.engine.get_body(collision.body_b_id)
            
            if body_a and body_b:
                self.engine.world.resolve_collision(collision, body_a, body_b)
                
            # Emit collision signal
            collision_info = f"Collision between body {collision.body_a_id} and {collision.body_b_id}"
            self.collision_detected.emit(collision_info)
            
    def _get_physics_mechanism_type(self, mechanism_data: MechanismData) -> Optional[str]:
        """
        Map mechanism data to physics mechanism type.
        
        Args:
            mechanism_data: Mechanism configuration
            
        Returns:
            Physics mechanism type string
        """
        mechanism_type = mechanism_data.mechanism_type.lower()
        
        # Map mechanism types to physics implementations
        type_mapping = {
            'four_bar_linkage': 'four_bar_linkage',
            'fourbar': 'four_bar_linkage',
            'four-bar': 'four_bar_linkage',
            'slider_crank': 'slider_crank',
            'slider-crank': 'slider_crank',
            'crank_slider': 'slider_crank',
            'gear_train': 'gear_train',
            'gears': 'gear_train',
            'spring_mass': 'spring_mass_damper',
            'spring': 'spring_mass_damper'
        }
        
        return type_mapping.get(mechanism_type)
        
    def _extract_mechanism_parameters(self, mechanism_data: MechanismData) -> Dict[str, Any]:
        """
        Extract parameters for physics mechanism creation.
        
        Args:
            mechanism_data: Mechanism configuration
            
        Returns:
            Parameters dictionary
        """
        parameters = {}
        
        # Extract common parameters
        if hasattr(mechanism_data, 'parameters') and mechanism_data.parameters:
            for param_name, param_value in mechanism_data.parameters.items():
                if isinstance(param_value, (int, float)):
                    parameters[param_name] = float(param_value)
                    
        # Set reasonable defaults if parameters are missing
        mechanism_type = mechanism_data.mechanism_type.lower()
        
        if 'four_bar' in mechanism_type or 'fourbar' in mechanism_type:
            parameters.setdefault('a', 2.0)
            parameters.setdefault('b', 3.0)
            parameters.setdefault('c', 4.0)
            parameters.setdefault('d', 3.5)
            parameters.setdefault('input_speed', 1.0)
            
        elif 'slider_crank' in mechanism_type:
            parameters.setdefault('crank_length', 2.0)
            parameters.setdefault('rod_length', 4.0)
            parameters.setdefault('input_speed', 2.0)
            
        elif 'gear' in mechanism_type:
            parameters.setdefault('gear_radii', [1.0, 1.5, 0.8])
            parameters.setdefault('input_speed', 3.0)
            
        elif 'spring' in mechanism_type:
            parameters.setdefault('mass', 2.0)
            parameters.setdefault('spring_constant', 100.0)
            parameters.setdefault('damping', 10.0)
            
        return parameters
        
    def get_performance_stats(self) -> Dict[str, float]:
        """Get performance statistics"""
        stats = self.engine.get_performance_stats()
        stats['visualization_fps'] = self.current_fps
        stats['simulation_speed'] = self.simulation_speed
        return stats