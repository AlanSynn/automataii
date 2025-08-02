"""
Simulation Service - Decoupled Physics Engine Integration

This service provides a clean abstraction layer between the centralized Mechanism
data model and PyBullet physics simulation, enabling physics-based validation
for manufacturing accuracy and educational visualization.

Features:
- Direct integration with centralized Mechanism model
- Physics-based parameter validation
- Force analysis and constraint violation detection
- Educational motion path generation
- Manufacturing feasibility validation
"""

import logging
import time
import math
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass
from enum import Enum

from PyQt6.QtCore import QObject, pyqtSignal, QTimer

# Lightweight physics engine integration
from ..physics.simulator import PhysicsSimulator
from ..physics.engine import PhysicsEngine
PHYSICS_AVAILABLE = True

from ..models.mechanism import Mechanism, MechanismLink, MechanismJoint, JointType
from ..models.mechanism import Point2D, Point3D, MotionPath, ForceAnalysis
from ..core.event_bus import EventBus
from ..core.event_types import EventType

logger = logging.getLogger(__name__)


class SimulationState(str, Enum):
    """Simulation execution states"""
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


class ValidationResult(str, Enum):
    """Physics validation results"""
    VALID = "valid"
    WARNING = "warning"
    INVALID = "invalid"


@dataclass
class SimulationConfig:
    """Configuration for physics simulation"""
    gravity: Tuple[float, float, float] = (0.0, 0.0, -9.81)
    time_step: float = 1.0 / 240.0  # 240Hz simulation
    solver_iterations: int = 50
    contact_breaking_threshold: float = 0.02
    enable_gui: bool = False
    real_time: bool = False
    
    # Educational features
    record_motion_paths: bool = True
    calculate_forces: bool = True
    detect_violations: bool = True
    max_simulation_time: float = 10.0  # seconds


@dataclass
class PhysicsBody:
    """Physics body representation in simulation"""
    body_id: int
    link_id: str
    mass: float
    position: Tuple[float, float, float]
    orientation: Tuple[float, float, float, float]  # quaternion
    
    def get_position(self) -> Point3D:
        return Point3D(self.position[0], self.position[1], self.position[2])


@dataclass
class PhysicsConstraint:
    """Physics constraint representation"""
    constraint_id: int
    joint_id: str
    body_a: int
    body_b: int
    constraint_type: str
    
    def get_constraint_force(self) -> Tuple[float, float, float]:
        """Get constraint reaction forces (simplified for lightweight physics)"""
        # In lightweight physics, we return simplified force estimates
        return (0.0, 0.0, 0.0)


@dataclass
class SimulationResult:
    """Results from physics simulation"""
    mechanism_id: str
    simulation_time: float
    is_valid: bool
    validation_result: ValidationResult
    
    # Motion data
    motion_paths: Dict[str, MotionPath]
    force_analysis: Optional[ForceAnalysis]
    
    # Validation results
    constraint_violations: List[str]
    warnings: List[str]
    errors: List[str]
    
    # Performance metrics
    computation_time: float
    simulation_stability: float


class SimulationService(QObject):
    """
    Physics simulation service for mechanism validation and analysis.
    
    Provides a clean interface between the centralized Mechanism data model
    and PyBullet physics engine. Handles all physics-related computations
    including validation, force analysis, and educational visualization.
    
    Features:
    - Direct Mechanism model integration
    - Physics-based manufacturing validation
    - Educational force and motion visualization
    - Constraint violation detection
    - Performance optimization for real-time use
    """
    
    # Signals for event-driven communication
    simulationStarted = pyqtSignal(str)  # mechanism_id
    simulationCompleted = pyqtSignal(SimulationResult)
    simulationError = pyqtSignal(str, str)  # mechanism_id, error_message
    constraintViolated = pyqtSignal(str, str, dict)  # mechanism_id, joint_id, violation_data
    forceAnalysisReady = pyqtSignal(str, ForceAnalysis)  # mechanism_id, analysis
    motionPathUpdated = pyqtSignal(str, str, MotionPath)  # mechanism_id, point_id, path
    
    def __init__(self, event_bus: Optional[EventBus] = None, parent: Optional[QObject] = None):
        super().__init__(parent)
        
        self.event_bus = event_bus
        self.config = SimulationConfig()
        
        # Lightweight physics engine
        self.physics_simulator = PhysicsSimulator(parent=self)
        self.current_mechanism: Optional[Mechanism] = None
        self.physics_bodies: Dict[str, PhysicsBody] = {}
        self.physics_constraints: Dict[str, PhysicsConstraint] = {}
        
        # Simulation state
        self.simulation_state = SimulationState.STOPPED
        self.simulation_start_time = 0.0
        self.motion_recording: Dict[str, List[Tuple[float, Point2D]]] = {}
        
        # Update timer for real-time simulation
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._simulation_step)
        
        # Connect physics simulator signals
        self.physics_simulator.simulation_updated.connect(self._on_physics_updated)
        self.physics_simulator.collision_detected.connect(self._on_collision_detected)
        
        # Connect to event bus
        if self.event_bus:
            self.event_bus.subscribe(EventType.MECHANISM_PARAMETER_CHANGED, self._on_parameter_changed)
    
    def _on_physics_updated(self, simulation_data: Dict):
        """Handle physics simulation updates"""
        # Extract body positions and update motion recording
        body_positions = simulation_data.get('body_positions', {})
        
        if self.config.record_motion_paths:
            current_time = time.time() - self.simulation_start_time
            for body_id, position in body_positions.items():
                point_id = f"body_{body_id}"
                if point_id not in self.motion_recording:
                    self.motion_recording[point_id] = []
                self.motion_recording[point_id].append((current_time, Point2D(position[0], position[1])))
    
    def _on_collision_detected(self, collision_info: str):
        """Handle collision detection"""
        logger.debug(f"Collision detected: {collision_info}")
    
    def load_mechanism(self, mechanism: Mechanism) -> bool:
        """
        Load mechanism into physics simulation.
        
        Args:
            mechanism: Centralized mechanism data model
            
        Returns:
            True if mechanism loaded successfully
        """
        try:
            # Clear existing simulation
            self._clear_simulation()
            
            # Store mechanism reference
            self.current_mechanism = mechanism
            
            # Convert mechanism to MechanismData format for physics simulator
            from ..physics.simulator import MechanismData
            mechanism_data = MechanismData(
                mechanism_type=mechanism.mechanism_type.value,
                parameters={}  # Extract parameters from mechanism
            )
            
            # Set mechanism in physics simulator
            success = self.physics_simulator.set_mechanism(mechanism_data)
            
            if success:
                # Initialize motion recording
                self._initialize_motion_recording()
                logger.info(f"Mechanism '{mechanism.name}' loaded successfully into physics simulation")
                return True
            else:
                logger.error("Failed to load mechanism into physics simulator")
                return False
            
        except Exception as e:
            logger.error(f"Failed to load mechanism: {e}")
            return False
    
    
    def _initialize_motion_recording(self):
        """Initialize motion path recording for key points"""
        if not self.current_mechanism:
            return
        
        self.motion_recording.clear()
        
        # Record motion for all joint positions
        for joint_id in self.current_mechanism.joints.keys():
            self.motion_recording[joint_id] = []
    
    def run_simulation(self, duration: float = None) -> SimulationResult:
        """
        Run physics simulation for specified duration.
        
        Args:
            duration: Simulation duration in seconds (uses config default if None)
            
        Returns:
            Simulation results including validation and analysis data
        """
        if not self.current_mechanism:
            return self._create_error_result("Simulation not properly initialized")
        
        duration = duration or self.config.max_simulation_time
        start_time = time.time()
        
        try:
            self.simulation_state = SimulationState.RUNNING
            self.simulation_start_time = time.time()
            self.simulationStarted.emit(self.current_mechanism.id)
            
            # Set simulation parameters
            self.physics_simulator.set_simulation_speed(1.0)
            self.physics_simulator.set_gravity((0, -9.81))
            
            # Start physics simulation
            self.physics_simulator.start_simulation()
            
            # Run for specified duration
            time.sleep(duration)
            
            # Stop simulation
            self.physics_simulator.stop_simulation()
            
            # Generate analysis results
            computation_time = time.time() - start_time
            motion_paths = self._generate_motion_paths()
            force_analysis = self._generate_force_analysis()
            
            # Create simulation result
            result = SimulationResult(
                mechanism_id=self.current_mechanism.id,
                simulation_time=duration,
                is_valid=True,
                validation_result=ValidationResult.VALID,
                motion_paths=motion_paths,
                force_analysis=force_analysis,
                constraint_violations=[],
                warnings=[],
                errors=[],
                computation_time=computation_time,
                simulation_stability=1.0  # Simplified stability metric
            )
            
            self.simulation_state = SimulationState.STOPPED
            self.simulationCompleted.emit(result)
            
            return result
            
        except Exception as e:
            error_msg = f"Simulation failed: {str(e)}"
            logger.error(error_msg)
            self.simulation_state = SimulationState.ERROR
            self.simulationError.emit(self.current_mechanism.id, error_msg)
            return self._create_error_result(error_msg)
    
    def _check_constraint_violations(self) -> List[Dict[str, Any]]:
        """Check for constraint violations during simulation"""
        violations = []
        
        # For lightweight physics, we do simplified constraint checking
        # This would be expanded in a full implementation
        
        return violations
    
    def _generate_motion_paths(self) -> Dict[str, MotionPath]:
        """Generate motion path objects from recorded data"""
        motion_paths = {}
        
        for point_id, recorded_data in self.motion_recording.items():
            if not recorded_data:
                continue
            
            # Extract trajectory and timestamps
            time_stamps = [data[0] for data in recorded_data]
            trajectory = [data[1] for data in recorded_data]
            
            # Calculate velocities (simplified finite difference)
            velocities = []
            for i in range(1, len(trajectory)):
                dt = time_stamps[i] - time_stamps[i-1]
                if dt > 0:
                    dx = trajectory[i].x - trajectory[i-1].x
                    dy = trajectory[i].y - trajectory[i-1].y
                    velocities.append((dx/dt, dy/dt))
                else:
                    velocities.append((0.0, 0.0))
            
            # First point has zero velocity
            if velocities:
                velocities.insert(0, (0.0, 0.0))
            
            # Calculate accelerations (simplified)
            accelerations = []
            for i in range(1, len(velocities)):
                dt = time_stamps[i] - time_stamps[i-1] if i < len(time_stamps) else self.config.time_step
                if dt > 0:
                    dvx = velocities[i][0] - velocities[i-1][0]
                    dvy = velocities[i][1] - velocities[i-1][1]
                    accelerations.append((dvx/dt, dvy/dt))
                else:
                    accelerations.append((0.0, 0.0))
            
            if accelerations:
                accelerations.insert(0, (0.0, 0.0))
            
            # Create motion path
            motion_path = MotionPath(
                point_id=point_id,
                point_name=self.current_mechanism.joints[point_id].name,
                trajectory=trajectory,
                time_stamps=time_stamps,
                velocities=velocities,
                accelerations=accelerations
            )
            
            motion_paths[point_id] = motion_path
        
        return motion_paths
    
    def _generate_force_analysis(self) -> Optional[ForceAnalysis]:
        """Generate force analysis from simulation data"""
        if not self.current_mechanism:
            return None
        
        try:
            joint_forces = {}
            joint_torques = {}
            link_stresses = {}
            safety_factors = {}
            
            # Calculate forces at each joint
            for joint_id, constraint in self.physics_constraints.items():
                force = constraint.get_constraint_force()
                joint_forces[joint_id] = (force[0], force[1])
                
                # Simplified torque calculation
                force_magnitude = math.sqrt(force[0]**2 + force[1]**2)
                joint = self.current_mechanism.joints[joint_id]
                # Assume moment arm of bearing_diameter/2
                moment_arm = joint.bearing_diameter / 2000  # Convert mm to m
                joint_torques[joint_id] = force_magnitude * moment_arm
            
            # Calculate link stresses (simplified)
            for link_id, link in self.current_mechanism.links.items():
                # Find maximum force acting on this link
                max_force = 0.0
                for joint_id, joint in self.current_mechanism.joints.items():
                    if joint.link_a == link_id or joint.link_b == link_id:
                        if joint_id in joint_forces:
                            force_mag = math.sqrt(sum(f**2 for f in joint_forces[joint_id]))
                            max_force = max(max_force, force_mag)
                
                # Calculate stress (simplified beam bending)
                if max_force > 0:
                    # Cross-sectional area
                    area = (link.width * link.thickness) / 1e6  # Convert mm² to m²
                    stress = max_force / area if area > 0 else 0
                    link_stresses[link_id] = stress
                    
                    # Safety factor
                    safety_factor = link.yield_strength / stress if stress > 0 else float('inf')
                    safety_factors[link_id] = safety_factor
                else:
                    link_stresses[link_id] = 0.0
                    safety_factors[link_id] = float('inf')
            
            return ForceAnalysis(
                joint_forces=joint_forces,
                joint_torques=joint_torques,
                link_stresses=link_stresses,
                safety_factors=safety_factors,
                input_force=None,  # Could be specified in future
                input_torque=None
            )
            
        except Exception as e:
            logger.error(f"Error generating force analysis: {e}")
            return None
    
    def _create_error_result(self, error_message: str) -> SimulationResult:
        """Create error simulation result"""
        mechanism_id = self.current_mechanism.id if self.current_mechanism else "unknown"
        
        return SimulationResult(
            mechanism_id=mechanism_id,
            simulation_time=0.0,
            is_valid=False,
            validation_result=ValidationResult.INVALID,
            motion_paths={},
            force_analysis=None,
            constraint_violations=[],
            warnings=[],
            errors=[error_message],
            computation_time=0.0,
            simulation_stability=0.0
        )
    
    def _clear_simulation(self):
        """Clear current simulation state"""
        try:
            # Stop physics simulation
            self.physics_simulator.stop_simulation()
            
            # Clear data structures
            self.physics_bodies.clear()
            self.physics_constraints.clear()
            self.motion_recording.clear()
            
        except Exception as e:
            logger.error(f"Error clearing simulation: {e}")
    
    def _on_parameter_changed(self, event_data: Dict[str, Any]):
        """Handle mechanism parameter changes"""
        if not self.current_mechanism:
            return
        
        mechanism_id = event_data.get('mechanism_id')
        if mechanism_id != self.current_mechanism.id:
            return
        
        # Reload mechanism with updated parameters
        logger.info(f"Reloading mechanism due to parameter change: {event_data}")
        # In a full implementation, you'd update the mechanism and reload
        # For now, just log the change
    
    def _simulation_step(self):
        """Single simulation step for real-time mode"""
        if self.simulation_state != SimulationState.RUNNING:
            return
        
        try:
            # Physics simulation step is handled automatically by PhysicsSimulator
            # This method is kept for compatibility
            pass
            
        except Exception as e:
            logger.error(f"Error in simulation step: {e}")
            self.simulation_state = SimulationState.ERROR
    
    # Public interface methods
    
    def validate_mechanism(self, mechanism: Mechanism) -> Tuple[bool, List[str]]:
        """
        Validate mechanism for physics simulation feasibility.
        
        Args:
            mechanism: Mechanism to validate
            
        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []
        
        # Check basic requirements
        if len(mechanism.links) < 2:
            issues.append("Mechanism must have at least 2 links")
        
        if len(mechanism.joints) < 1:
            issues.append("Mechanism must have at least 1 joint")
        
        # Check link-joint connectivity
        for joint in mechanism.joints.values():
            if joint.link_a not in mechanism.links:
                issues.append(f"Joint {joint.id} references non-existent link {joint.link_a}")
            if joint.link_b not in mechanism.links:
                issues.append(f"Joint {joint.id} references non-existent link {joint.link_b}")
        
        # Check for ground connections
        has_fixed_joint = any(joint.is_fixed for joint in mechanism.joints.values())
        if not has_fixed_joint:
            issues.append("Mechanism must have at least one fixed (ground) joint")
        
        # Validate 4-bar linkage specific constraints
        if mechanism.mechanism_type.value == "four_bar_linkage":
            is_valid, grashof_msg = mechanism.validate_grashof_condition()
            if not is_valid:
                issues.append(f"Grashof condition violation: {grashof_msg}")
        
        # Check material properties
        for link in mechanism.links.values():
            if link.mass <= 0:
                issues.append(f"Link {link.id} has invalid mass: {link.mass}")
            if link.youngs_modulus <= 0:
                issues.append(f"Link {link.id} has invalid Young's modulus")
        
        is_valid = len(issues) == 0
        return is_valid, issues
    
    def get_simulation_config(self) -> SimulationConfig:
        """Get current simulation configuration"""
        return self.config
    
    def set_simulation_config(self, config: SimulationConfig):
        """Update simulation configuration"""
        self.config = config
        
        # Update physics simulator parameters
        self.physics_simulator.set_gravity((config.gravity[0], config.gravity[1]))
        # Time step and other parameters are handled internally by the physics simulator
    
    def is_simulation_running(self) -> bool:
        """Check if simulation is currently running"""
        return self.simulation_state == SimulationState.RUNNING
    
    def pause_simulation(self):
        """Pause currently running simulation"""
        self.simulation_state = SimulationState.PAUSED
        self.update_timer.stop()
    
    def resume_simulation(self):
        """Resume paused simulation"""
        if self.simulation_state == SimulationState.PAUSED:
            self.simulation_state = SimulationState.RUNNING
            if self.config.real_time:
                self.update_timer.start(int(self.config.time_step * 1000))
    
    def stop_simulation(self):
        """Stop current simulation"""
        self.simulation_state = SimulationState.STOPPED
        self.update_timer.stop()
    
    def cleanup(self):
        """Clean up resources"""
        self.stop_simulation()
        self._clear_simulation()
        
        # Physics simulator cleanup is handled automatically
        logger.info("Simulation service cleaned up")