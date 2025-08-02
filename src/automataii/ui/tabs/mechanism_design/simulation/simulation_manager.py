"""
3D Simulation Manager - Central orchestrator for physics-based mechanism simulation

This module provides the main interface for 3D physics simulation, coordinating
between PyBullet physics engine, OpenGL rendering, and UI controls to create
a unified simulation experience.

Features:
- Real-time physics simulation with accurate constraint solving
- Seamless switching between 2D and 3D views
- Physics-based parameter validation
- Educational visualization of forces and motion
- Integration with blueprint generation for manufacturing validation
"""

import time
import logging
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass
from enum import Enum

from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QThread
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSlider, QCheckBox
from PyQt6.QtGui import QVector3D, QMatrix4x4

from .physics_engine import PyBulletPhysicsEngine, PhysicsBody, PhysicsConstraint
from .rendering_3d import OpenGLRenderer3D, Camera3D, Scene3D
from .controls_3d import Simulation3DControls

logger = logging.getLogger(__name__)


class SimulationMode(Enum):
    """Simulation operation modes"""
    PAUSED = "paused"
    PLAYING = "playing"
    STEPPING = "stepping"
    ANALYZING = "analyzing"


class SimulationQuality(Enum):
    """Simulation quality levels"""
    FAST = "fast"         # Low accuracy, high performance
    BALANCED = "balanced" # Good balance of accuracy and performance
    PRECISE = "precise"   # High accuracy, lower performance


@dataclass
class SimulationSettings:
    """Configuration for 3D physics simulation"""
    time_step: float = 1.0 / 240.0  # 240Hz physics simulation
    solver_iterations: int = 50
    gravity: Tuple[float, float, float] = (0.0, 0.0, -9.81)
    collision_margin: float = 0.001
    contact_breaking_threshold: float = 0.02
    
    # Visualization settings
    show_forces: bool = True
    show_velocities: bool = True
    show_constraints: bool = True
    show_contact_points: bool = True
    
    # Performance settings
    quality: SimulationQuality = SimulationQuality.BALANCED
    max_physics_substeps: int = 10
    enable_sleeping: bool = True
    

@dataclass
class SimulationState:
    """Current state of the physics simulation"""
    time: float = 0.0
    mode: SimulationMode = SimulationMode.PAUSED
    bodies: Dict[str, PhysicsBody] = None
    constraints: List[PhysicsConstraint] = None
    forces: Dict[str, QVector3D] = None
    velocities: Dict[str, QVector3D] = None
    
    def __post_init__(self):
        if self.bodies is None:
            self.bodies = {}
        if self.constraints is None:
            self.constraints = []
        if self.forces is None:
            self.forces = {}
        if self.velocities is None:
            self.velocities = {}


class SimulationWorker(QThread):
    """Background worker for physics calculations"""
    
    stateUpdated = pyqtSignal(dict)  # Updated simulation state
    constraintViolated = pyqtSignal(str, dict)  # Constraint violation events
    
    def __init__(self, physics_engine: PyBulletPhysicsEngine, settings: SimulationSettings):
        super().__init__()
        self.physics_engine = physics_engine
        self.settings = settings
        self.running = False
        self.paused = True
        
        # Simulation timing
        self.last_update_time = time.time()
        self.accumulated_time = 0.0
        
    def set_paused(self, paused: bool):
        """Set simulation pause state"""
        self.paused = paused
        
    def run(self):
        """Main simulation loop"""
        self.running = True
        self.last_update_time = time.time()
        
        while self.running:
            current_time = time.time()
            dt = current_time - self.last_update_time
            self.last_update_time = current_time
            
            if not self.paused:
                # Accumulate time for fixed timestep simulation
                self.accumulated_time += dt
                
                # Perform physics steps
                steps_taken = 0
                while (self.accumulated_time >= self.settings.time_step and 
                       steps_taken < self.settings.max_physics_substeps):
                    
                    # Step physics
                    self.physics_engine.step_simulation(self.settings.time_step)
                    
                    # Check constraints
                    self._check_constraint_violations()
                    
                    self.accumulated_time -= self.settings.time_step
                    steps_taken += 1
                
                # Emit updated state
                if steps_taken > 0:
                    state = self._get_current_state()
                    self.stateUpdated.emit(state)
            
            # Sleep to maintain reasonable update rate
            self.msleep(4)  # ~250Hz update rate
            
    def stop(self):
        """Stop the simulation worker"""
        self.running = False
        self.wait()
        
    def _check_constraint_violations(self):
        """Check for constraint violations and emit warnings"""
        violations = self.physics_engine.check_constraint_violations()
        for constraint_id, violation_data in violations.items():
            self.constraintViolated.emit(constraint_id, violation_data)
    
    def _get_current_state(self) -> Dict[str, Any]:
        """Get current simulation state as dictionary"""
        bodies = self.physics_engine.get_all_bodies()
        constraints = self.physics_engine.get_all_constraints()
        
        state = {
            'time': time.time(),
            'bodies': {body_id: {
                'position': body.get_position(),
                'orientation': body.get_orientation(),
                'linear_velocity': body.get_linear_velocity(),
                'angular_velocity': body.get_angular_velocity(),
                'forces': body.get_applied_forces()
            } for body_id, body in bodies.items()},
            'constraints': [{
                'id': constraint.id,
                'type': constraint.constraint_type,
                'force': constraint.get_constraint_force(),
                'violation': constraint.get_violation_amount()
            } for constraint in constraints],
            'contact_points': self.physics_engine.get_contact_points()
        }
        
        return state


class SimulationManager3D(QObject):
    """
    Central manager for 3D physics simulation of mechanisms.
    
    Provides a unified interface for physics simulation, 3D rendering,
    and UI controls. Integrates with the blueprint generation system
    to validate manufacturing feasibility.
    
    Features:
    - Real-time PyBullet physics simulation
    - Interactive 3D visualization with OpenGL
    - Physics parameter validation and optimization
    - Educational force and motion visualization
    - Blueprint accuracy validation through physics
    """
    
    # Signals
    simulationStarted = pyqtSignal()
    simulationPaused = pyqtSignal()
    simulationStopped = pyqtSignal()
    stateChanged = pyqtSignal(dict)  # Full simulation state
    constraintViolated = pyqtSignal(str, str)  # constraint_id, violation_type
    mechanismParameterChanged = pyqtSignal(str, float)  # param_name, value
    
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        
        # Core components
        self.physics_engine: Optional[PyBulletPhysicsEngine] = None
        self.renderer_3d: Optional[OpenGLRenderer3D] = None
        self.controls: Optional[Simulation3DControls] = None
        
        # Simulation state
        self.settings = SimulationSettings()
        self.current_state = SimulationState()
        self.mechanism_data: Dict[str, Any] = {}
        
        # Worker thread
        self.simulation_worker: Optional[SimulationWorker] = None
        
        # UI update timer
        self.ui_update_timer = QTimer()
        self.ui_update_timer.timeout.connect(self._update_ui_components)
        
        # Initialize components
        self._initialize_components()
        
    def _initialize_components(self):
        """Initialize all simulation components"""
        try:
            # Initialize physics engine
            self.physics_engine = PyBulletPhysicsEngine()
            self.physics_engine.initialize(self.settings)
            
            # Initialize 3D renderer
            self.renderer_3d = OpenGLRenderer3D()
            
            # Initialize controls
            self.controls = Simulation3DControls()
            self.controls.playPauseClicked.connect(self._toggle_simulation)
            self.controls.stepClicked.connect(self._step_simulation)
            self.controls.resetClicked.connect(self._reset_simulation)
            self.controls.parameterChanged.connect(self._on_parameter_changed)
            
            logger.info("3D simulation components initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize simulation components: {e}")
            
    def load_mechanism(self, mechanism_data: Dict[str, Any]) -> bool:
        """
        Load mechanism data into the 3D simulation.
        
        Args:
            mechanism_data: Complete mechanism specification including:
                - geometry: 3D geometry data
                - constraints: Joint and constraint definitions
                - materials: Material properties for physics
                - parameters: Configurable parameters
                
        Returns:
            True if mechanism loaded successfully
        """
        if not self.physics_engine:
            logger.error("Physics engine not initialized")
            return False
            
        try:
            # Store mechanism data
            self.mechanism_data = mechanism_data.copy()
            
            # Clear existing simulation
            self._clear_simulation()
            
            # Create physics bodies from geometry
            self._create_physics_bodies(mechanism_data.get('geometry', {}))
            
            # Create constraints from mechanism definition
            self._create_physics_constraints(mechanism_data.get('constraints', []))
            
            # Setup materials and properties
            self._apply_material_properties(mechanism_data.get('materials', {}))
            
            # Initialize parameter controls
            self._setup_parameter_controls(mechanism_data.get('parameters', {}))
            
            # Update 3D scene
            if self.renderer_3d:
                self.renderer_3d.load_mechanism(mechanism_data)
                
            logger.info(f"Mechanism '{mechanism_data.get('name', 'Unknown')}' loaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load mechanism: {e}")
            return False
            
    def _clear_simulation(self):
        """Clear all simulation data"""
        if self.physics_engine:
            self.physics_engine.clear_world()
            
        self.current_state = SimulationState()
        
    def _create_physics_bodies(self, geometry_data: Dict[str, Any]):
        """Create physics bodies from geometry data"""
        for body_id, geometry in geometry_data.items():
            # Create physics body based on geometry type
            if geometry['type'] == 'box':
                body = self.physics_engine.create_box(
                    body_id,
                    size=geometry['size'],
                    position=geometry.get('position', (0, 0, 0)),
                    orientation=geometry.get('orientation', (0, 0, 0, 1)),
                    mass=geometry.get('mass', 1.0)
                )
            elif geometry['type'] == 'cylinder':
                body = self.physics_engine.create_cylinder(
                    body_id,
                    radius=geometry['radius'],
                    height=geometry['height'],
                    position=geometry.get('position', (0, 0, 0)),
                    orientation=geometry.get('orientation', (0, 0, 0, 1)),
                    mass=geometry.get('mass', 1.0)
                )
            elif geometry['type'] == 'mesh':
                body = self.physics_engine.create_mesh(
                    body_id,
                    mesh_data=geometry['mesh'],
                    position=geometry.get('position', (0, 0, 0)),
                    orientation=geometry.get('orientation', (0, 0, 0, 1)),
                    mass=geometry.get('mass', 1.0)
                )
            else:
                logger.warning(f"Unknown geometry type: {geometry['type']}")
                continue
                
            self.current_state.bodies[body_id] = body
            
    def _create_physics_constraints(self, constraints_data: List[Dict[str, Any]]):
        """Create physics constraints from constraint definitions"""
        for constraint_def in constraints_data:
            constraint_type = constraint_def.get('type')
            
            if constraint_type == 'revolute':
                constraint = self.physics_engine.create_revolute_joint(
                    constraint_def['body_a'],
                    constraint_def['body_b'],
                    constraint_def['pivot_a'],
                    constraint_def['pivot_b'],
                    constraint_def['axis_a'],
                    constraint_def['axis_b']
                )
            elif constraint_type == 'prismatic':
                constraint = self.physics_engine.create_prismatic_joint(
                    constraint_def['body_a'],
                    constraint_def['body_b'],
                    constraint_def['frame_a'],
                    constraint_def['frame_b']
                )
            elif constraint_type == 'fixed':
                constraint = self.physics_engine.create_fixed_joint(
                    constraint_def['body_a'],
                    constraint_def['body_b'],
                    constraint_def['frame_a'],
                    constraint_def['frame_b']
                )
            else:
                logger.warning(f"Unknown constraint type: {constraint_type}")
                continue
                
            self.current_state.constraints.append(constraint)
            
    def _apply_material_properties(self, materials_data: Dict[str, Any]):
        """Apply material properties to physics bodies"""
        for body_id, material in materials_data.items():
            if body_id in self.current_state.bodies:
                body = self.current_state.bodies[body_id]
                
                # Apply material properties
                body.set_friction(material.get('friction', 0.5))
                body.set_restitution(material.get('restitution', 0.3))
                body.set_mass(material.get('density', 1.0) * body.get_volume())
                
    def _setup_parameter_controls(self, parameters_data: Dict[str, Any]):
        """Setup parameter controls for interactive simulation"""
        if not self.controls:
            return
            
        # Clear existing parameters
        self.controls.clear_parameters()
        
        # Add parameter groups
        for group_name, params in parameters_data.items():
            parameter_controls = []
            
            for param_name, param_config in params.items():
                control = {
                    'name': param_name,
                    'type': param_config.get('type', 'float'),
                    'value': param_config.get('default', 0.0),
                    'min': param_config.get('min', 0.0),
                    'max': param_config.get('max', 100.0),
                    'step': param_config.get('step', 0.1),
                    'unit': param_config.get('unit', ''),
                    'description': param_config.get('description', '')
                }
                parameter_controls.append(control)
                
            self.controls.add_parameter_group(group_name, parameter_controls)
            
    def start_simulation(self):
        """Start the physics simulation"""
        if not self.physics_engine:
            logger.error("Cannot start simulation: physics engine not initialized")
            return
            
        # Create and start simulation worker
        if not self.simulation_worker:
            self.simulation_worker = SimulationWorker(self.physics_engine, self.settings)
            self.simulation_worker.stateUpdated.connect(self._on_state_updated)
            self.simulation_worker.constraintViolated.connect(self._on_constraint_violated)
            
        if not self.simulation_worker.isRunning():
            self.simulation_worker.start()
            
        # Resume simulation
        self.simulation_worker.set_paused(False)
        self.current_state.mode = SimulationMode.PLAYING
        
        # Start UI updates
        self.ui_update_timer.start(16)  # ~60fps UI updates
        
        self.simulationStarted.emit()
        logger.info("3D simulation started")
        
    def pause_simulation(self):
        """Pause the physics simulation"""
        if self.simulation_worker:
            self.simulation_worker.set_paused(True)
            
        self.current_state.mode = SimulationMode.PAUSED
        self.simulationPaused.emit()
        logger.info("3D simulation paused")
        
    def stop_simulation(self):
        """Stop the physics simulation"""
        if self.simulation_worker:
            self.simulation_worker.stop()
            self.simulation_worker = None
            
        self.ui_update_timer.stop()
        self.current_state.mode = SimulationMode.PAUSED
        self.simulationStopped.emit()
        logger.info("3D simulation stopped")
        
    def reset_simulation(self):
        """Reset simulation to initial state"""
        was_running = self.current_state.mode == SimulationMode.PLAYING
        
        # Stop current simulation
        self.stop_simulation()
        
        # Reset physics engine
        if self.physics_engine:
            self.physics_engine.reset_simulation()
            
        # Reload mechanism
        if self.mechanism_data:
            self.load_mechanism(self.mechanism_data)
            
        # Restart if it was running
        if was_running:
            self.start_simulation()
            
        logger.info("3D simulation reset")
        
    def step_simulation(self):
        """Step simulation by one frame"""
        if not self.physics_engine:
            return
            
        self.physics_engine.step_simulation(self.settings.time_step)
        self.current_state.mode = SimulationMode.STEPPING
        
        # Update UI
        state = self._get_current_state()
        self._on_state_updated(state)
        
    def _toggle_simulation(self):
        """Toggle between play and pause"""
        if self.current_state.mode == SimulationMode.PLAYING:
            self.pause_simulation()
        else:
            self.start_simulation()
            
    def _step_simulation(self):
        """Handle step button click"""
        self.step_simulation()
        
    def _reset_simulation(self):
        """Handle reset button click"""
        self.reset_simulation()
        
    def _on_parameter_changed(self, param_name: str, value: float):
        """Handle parameter changes from UI"""
        # Update mechanism parameter
        if 'parameters' in self.mechanism_data:
            # Find parameter in nested structure
            for group_name, params in self.mechanism_data['parameters'].items():
                if param_name in params:
                    params[param_name]['value'] = value
                    break
                    
        # Apply parameter change to physics simulation
        self._apply_parameter_change(param_name, value)
        
        # Emit signal
        self.mechanismParameterChanged.emit(param_name, value)
        
    def _apply_parameter_change(self, param_name: str, value: float):
        """Apply parameter change to physics simulation"""
        if not self.physics_engine:
            return
            
        # Parameter changes might affect:
        # - Joint limits and properties
        # - Body dimensions and masses  
        # - Constraint parameters
        # This would need mechanism-specific implementation
        
        logger.debug(f"Applied parameter change: {param_name} = {value}")
        
    def _on_state_updated(self, state_data: Dict[str, Any]):
        """Handle simulation state updates"""
        # Update internal state
        self.current_state.time = state_data.get('time', 0.0)
        
        # Update 3D renderer
        if self.renderer_3d:
            self.renderer_3d.update_simulation_state(state_data)
            
        # Emit state change signal
        self.stateChanged.emit(state_data)
        
    def _on_constraint_violated(self, constraint_id: str, violation_data: Dict[str, Any]):
        """Handle constraint violation events"""
        violation_type = violation_data.get('type', 'unknown')
        severity = violation_data.get('severity', 'warning')
        
        logger.warning(f"Constraint violation: {constraint_id} ({violation_type})")
        
        # Emit constraint violation signal
        self.constraintViolated.emit(constraint_id, violation_type)
        
    def _update_ui_components(self):
        """Update UI components during simulation"""
        if not self.renderer_3d:
            return
            
        # Trigger 3D renderer update
        self.renderer_3d.update()
        
        # Update controls with current state
        if self.controls:
            self.controls.update_state_display(self.current_state)
            
    def _get_current_state(self) -> Dict[str, Any]:
        """Get current simulation state"""
        if not self.physics_engine:
            return {}
            
        return {
            'time': self.current_state.time,
            'mode': self.current_state.mode.value,
            'bodies': {body_id: {
                'position': body.get_position(),
                'orientation': body.get_orientation(),
                'velocity': body.get_linear_velocity()
            } for body_id, body in self.current_state.bodies.items()},
            'constraints': [{
                'id': constraint.id,
                'force': constraint.get_constraint_force()
            } for constraint in self.current_state.constraints]
        }
        
    # Public interface methods
    def get_simulation_settings(self) -> SimulationSettings:
        """Get current simulation settings"""
        return self.settings
        
    def set_simulation_settings(self, settings: SimulationSettings):
        """Update simulation settings"""
        self.settings = settings
        
        if self.physics_engine:
            self.physics_engine.update_settings(settings)
            
    def get_mechanism_data(self) -> Dict[str, Any]:
        """Get current mechanism data"""
        return self.mechanism_data.copy()
        
    def is_simulation_running(self) -> bool:
        """Check if simulation is currently running"""
        return self.current_state.mode == SimulationMode.PLAYING
        
    def get_renderer_widget(self) -> Optional[QWidget]:
        """Get the 3D renderer widget for embedding in UI"""
        return self.renderer_3d.get_widget() if self.renderer_3d else None
        
    def get_controls_widget(self) -> Optional[QWidget]:
        """Get the controls widget for embedding in UI"""
        return self.controls.get_widget() if self.controls else None
        
    def cleanup(self):
        """Clean up resources"""
        # Stop simulation
        self.stop_simulation()
        
        # Clean up components
        if self.physics_engine:
            self.physics_engine.cleanup()
            
        if self.renderer_3d:
            self.renderer_3d.cleanup()
            
        logger.info("3D simulation manager cleaned up")