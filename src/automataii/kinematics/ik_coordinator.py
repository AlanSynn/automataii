"""Main coordinator for the IK system."""

import logging
from typing import Dict, Any, Optional, List

from PyQt6.QtCore import QObject, pyqtSignal, QPointF

from .core import (
    IKState,
    JointConfigurationManager,
    LimbConfigurationManager,
    SolverType
)
from .solvers import SolverFactory, IKSolution
from .animation import AnimationManager


class IKCoordinator(QObject):
    """Coordinates all IK system components.
    
    This class acts as the main entry point for IK operations,
    managing state, configuration, solving, and animation.
    """
    
    # Signals
    solver_initialized = pyqtSignal(bool, dict)  # success, joint_config
    ik_solved = pyqtSignal(dict)  # solution data
    animation_updated = pyqtSignal(float)  # progress
    error_occurred = pyqtSignal(str)
    
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        
        # Core components
        self._state = IKState(self)
        self._joint_config = JointConfigurationManager()
        self._limb_config = LimbConfigurationManager()
        self._animation = AnimationManager(self._state, self)
        
        # Solvers
        self._solvers: Dict[SolverType, Any] = {}
        
        # Joint name mapping (skeleton names -> IK names)
        self._joint_name_mapping: Dict[str, str] = {}
        
        # Connect signals
        self._setup_connections()
        
        logging.info("IKCoordinator initialized")
    
    def _setup_connections(self):
        """Set up internal signal connections."""
        # Animation signals
        self._animation.frame_updated.connect(self.animation_updated)
        self._animation.target_positions_updated.connect(self._solve_frame)
        
        # State signals
        self._state.state_changed.connect(self._on_state_changed)
    
    def initialize_from_skeleton(self, skeleton_data: Dict[str, Any]) -> bool:
        """Initialize IK system from skeleton data.
        
        Args:
            skeleton_data: Skeleton joint and hierarchy data
            
        Returns:
            True if successful
        """
        try:
            # Clear existing configuration
            self.clear()
            
            # Extract joints and build configuration
            joints = skeleton_data.get('joints', {})
            hierarchy = skeleton_data.get('hierarchy', {})
            
            # Create joint name mapping from skeleton names to IK names
            self._joint_name_mapping = self._create_joint_name_mapping(joints)
            
            # Add joints to configuration with mapped names
            for joint_id, joint_info in joints.items():
                position = joint_info.get('position', QPointF(0, 0))
                angle = joint_info.get('angle', 0.0)
                joint_name = joint_info.get('name', joint_id)
                
                # Map to IK joint name
                ik_joint_name = self._joint_name_mapping.get(joint_name, joint_name)
                
                # Add to state with IK name
                self._state.add_joint(ik_joint_name, position, angle)
            
            # Set up standard humanoid limbs if applicable
            if self._detect_humanoid_skeleton(joints):
                # Don't use prefix since we've already mapped names
                self._limb_config.create_standard_humanoid_limbs(joint_prefix="")
                
                # Add limbs to state
                for limb_name, limb_config in self._limb_config.get_all_limbs().items():
                    self._state.add_limb(
                        limb_name,
                        limb_config.joints,
                        limb_config.bend_direction
                    )
            
            # Create solvers
            self._create_solvers()
            
            # Mark as initialized
            self._state.set_solver_initialized(True)
            
            # Emit success signal
            self.solver_initialized.emit(True, self._state.get_all_joints())
            
            logging.info("IK system initialized from skeleton")
            return True
            
        except Exception as e:
            error_msg = f"Failed to initialize IK system: {str(e)}"
            logging.error(error_msg)
            self.error_occurred.emit(error_msg)
            return False
    
    def _create_joint_name_mapping(self, joints: Dict[str, Any]) -> Dict[str, str]:
        """Create mapping from skeleton joint names to IK joint names.
        
        Maps names like 'left_shoulder_0' to 'left_shoulder'
        """
        mapping = {}
        
        for joint_id, joint_info in joints.items():
            joint_name = joint_info.get('name', joint_id)
            
            # Extract base name by removing trailing numbers and underscore
            base_name = joint_name
            if '_' in joint_name:
                parts = joint_name.split('_')
                if parts[-1].isdigit():
                    base_name = '_'.join(parts[:-1])
            
            # Map to expected IK name
            mapping[joint_name] = base_name
            
        return mapping
    
    def _detect_humanoid_skeleton(self, joints: Dict[str, Any]) -> bool:
        """Detect if skeleton is humanoid based on joint names."""
        # Look for common humanoid joint patterns
        humanoid_joints = [
            'shoulder', 'elbow', 'wrist',
            'hip', 'knee', 'ankle',
            'spine', 'neck', 'head'
        ]
        
        # Check joint names from the actual data
        joint_names_lower = []
        for joint_info in joints.values():
            if isinstance(joint_info, dict):
                name = joint_info.get('name', '')
                joint_names_lower.append(name.lower())
        
        matches = sum(1 for joint in humanoid_joints 
                     if any(joint in name for name in joint_names_lower))
        
        return matches >= 4  # At least 4 humanoid joints
    
    def _create_solvers(self):
        """Create solvers for configured limbs."""
        self._solvers.clear()
        
        for limb_config in self._limb_config.get_all_limbs().values():
            if limb_config.solver_type not in self._solvers:
                solver = SolverFactory.create_solver(limb_config.solver_type)
                self._solvers[limb_config.solver_type] = solver
    
    def solve_limb(self, limb_name: str, target: QPointF) -> Optional[IKSolution]:
        """Solve IK for a specific limb.
        
        Args:
            limb_name: Name of limb to solve
            target: Target position for end effector
            
        Returns:
            IK solution or None if failed
        """
        # Get limb configuration
        limb_config = self._limb_config.get_limb(limb_name)
        if not limb_config:
            logging.error(f"Limb '{limb_name}' not found")
            return None
        
        # Get solver
        solver = self._solvers.get(limb_config.solver_type)
        if not solver:
            logging.error(f"No solver for type {limb_config.solver_type}")
            return None
        
        # Prepare joint positions
        joint_positions = {}
        for i, joint_name in enumerate(limb_config.joints):
            joint_state = self._state.get_joint(joint_name)
            if not joint_state:
                # Try with j_ prefix for backward compatibility
                if not joint_name.startswith('j_'):
                    joint_state = self._state.get_joint(f'j_{joint_name}')
                if not joint_state:
                    logging.error(f"Joint '{joint_name}' not found in state")
                    return None
            
            # Map to solver's expected names
            if i == 0:
                joint_positions['root'] = joint_state.position
            elif i == 1 and len(limb_config.joints) == 3:
                joint_positions['middle'] = joint_state.position
            elif i == len(limb_config.joints) - 1:
                joint_positions['end'] = joint_state.position
        
        # Prepare constraints
        constraints = {
            'bend_direction': limb_config.bend_direction
        }
        
        # Solve
        solution = solver.solve(target, joint_positions, constraints)
        
        if solution.success:
            # Update state with solution
            self._apply_solution(limb_config, solution)
            
            # Emit solved signal
            self.ik_solved.emit({
                'limb': limb_name,
                'solution': solution
            })
        
        return solution
    
    def _apply_solution(self, limb_config, solution: IKSolution):
        """Apply IK solution to state."""
        # Map solution back to actual joint names
        joint_mapping = {
            'root': limb_config.joints[0],
            'middle': limb_config.joints[1] if len(limb_config.joints) == 3 else None,
            'end': limb_config.joints[-1]
        }
        
        for solver_joint, position in solution.joint_positions.items():
            actual_joint = joint_mapping.get(solver_joint)
            if actual_joint:
                self._state.update_joint_position(actual_joint, position)
        
        for solver_joint, angle in solution.joint_angles.items():
            actual_joint = joint_mapping.get(solver_joint)
            if actual_joint:
                self._state.update_joint_angle(actual_joint, angle)
    
    def _solve_frame(self, targets: Dict[str, QPointF]):
        """Solve IK for animation frame."""
        for limb_name, target in targets.items():
            self.solve_limb(limb_name, target)
    
    def _on_state_changed(self, state_key: str):
        """Handle state changes."""
        logging.debug(f"IK state changed: {state_key}")
    
    def set_motion_paths(self, motion_paths: Dict[str, Any]):
        """Set motion paths for animation.
        
        Args:
            motion_paths: Dict mapping limb names to motion paths
        """
        self._animation.load_motion_paths(motion_paths)
    
    def start_animation(self):
        """Start IK animation."""
        self._animation.start()
    
    def stop_animation(self):
        """Stop IK animation."""
        self._animation.stop()
    
    def reset_animation(self):
        """Reset animation to beginning."""
        self._animation.reset()
    
    @property
    def state(self) -> IKState:
        """Get IK state."""
        return self._state
    
    @property
    def animation(self) -> AnimationManager:
        """Get animation manager."""
        return self._animation
    
    def clear(self):
        """Clear all IK data."""
        self._state.clear()
        self._joint_config.clear()
        self._limb_config.clear()
        self._animation.clear_keyframes()
        self._solvers.clear()
        
        logging.info("IK coordinator cleared")