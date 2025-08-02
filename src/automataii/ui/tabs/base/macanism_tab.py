"""
Macanism-Style Tab Base Class - Universal foundation for mechanism-related tabs

This base class provides the universal foundation for creating macanism-level 
simulation systems across multiple tabs with consistent:
- Visual design system with professional grid
- High-fidelity physics simulation 
- Natural interaction paradigms
- 60fps performance optimization
- Reusable component architecture
"""

import time
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QSplitter
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPainter, QResizeEvent

from ...mechanism_foundry.panels.unified_visualization import (
    UnifiedMechanismRenderer, RenderSettings, GridSettings
)
from ...mechanism_foundry.panels.interactive_mechanism import (
    InteractiveMechanismRenderer, PhysicsEngine
)
from ...mechanism_foundry.hci.physics_interaction import (
    PhysicsInteractionLayer, InteractionMode
)
from ...mechanism_foundry.hci.parametric_controls import (
    ParametricControlPanel, ParameterState, ParameterType, ParameterConstraint
)


@dataclass
class MacanismConfig:
    """Configuration for macanism-style simulation systems"""
    # Visual settings
    enable_professional_grid: bool = True
    show_force_vectors: bool = True
    show_motion_trails: bool = True
    show_stress_indicators: bool = True
    
    # Physics settings
    physics_timestep: float = 1.0/60.0  # 60 FPS
    constraint_iterations: int = 3
    enable_real_time_solving: bool = True
    
    # Interaction settings
    default_interaction_mode: InteractionMode = InteractionMode.POSITION
    enable_haptic_feedback: bool = True
    enable_parametric_controls: bool = True
    
    # Performance settings
    target_fps: int = 60
    enable_adaptive_quality: bool = True
    enable_occlusion_culling: bool = True


class MacanismStyleTab(QWidget, ABC):
    """
    Universal base class for macanism-style mechanism tabs.
    
    Provides consistent architecture across all mechanism-related tabs:
    - Professional engineering visualization
    - High-fidelity physics simulation
    - Natural interaction paradigms
    - Reusable component system
    - Performance optimization
    
    Signals:
    - mechanismChanged(mechanism_data: Dict)
    - parameterChanged(param_name: str, value: float)
    - simulationStateChanged(state: str)
    - performanceMetricsUpdated(metrics: Dict)
    """
    
    # Universal signals
    mechanismChanged = pyqtSignal(dict)
    parameterChanged = pyqtSignal(str, float)
    simulationStateChanged = pyqtSignal(str)
    performanceMetricsUpdated = pyqtSignal(dict)
    
    def __init__(self, config: Optional[MacanismConfig] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        # Configuration
        self.config = config or MacanismConfig()
        
        # Core components
        self.unified_renderer: Optional[UnifiedMechanismRenderer] = None
        self.interactive_renderer: Optional[InteractiveMechanismRenderer] = None
        self.physics_interaction: Optional[PhysicsInteractionLayer] = None
        self.parametric_controls: Optional[ParametricControlPanel] = None
        
        # State management
        self.mechanism_data: Dict[str, Any] = {}
        self.current_parameters: Dict[str, float] = {}
        self.simulation_state: str = "stopped"
        
        # Performance monitoring
        self.performance_timer = QTimer()
        self.performance_timer.timeout.connect(self._update_performance_metrics)
        self.frame_times: List[float] = []
        self.last_frame_time = time.time()
        
        # Initialize the tab
        self.initialize_tab()
        
    def initialize_tab(self):
        """Initialize the universal tab architecture"""
        # Setup core components
        self.setup_unified_renderer()
        self.setup_physics_system()
        self.setup_interaction_layer()
        self.setup_parametric_controls()
        
        # Create UI layout
        self.create_tab_layout()
        
        # Connect signals
        self.connect_component_signals()
        
        # Start performance monitoring
        if self.config.target_fps > 0:
            self.performance_timer.start(1000)  # Update every second
            
        # Let subclass perform custom initialization
        self.setup_mechanism_specific_components()
        
    def setup_unified_renderer(self):
        """Setup the unified macanism-style renderer"""
        # Professional engineering settings
        grid_settings = GridSettings(
            show_grid=self.config.enable_professional_grid,
            grid_size=20.0,
            major_grid_size=100.0,
            show_measurements=True,
            show_origin=True
        )
        
        render_settings = RenderSettings()
        render_settings.grid = grid_settings
        
        self.unified_renderer = UnifiedMechanismRenderer(render_settings)
        
    def setup_physics_system(self):
        """Setup high-fidelity physics simulation"""
        self.physics_engine = PhysicsEngine()
        self.physics_engine.constraint_iterations = self.config.constraint_iterations
        
        # Create interactive renderer with physics
        self.interactive_renderer = InteractiveMechanismRenderer(self)
        self.interactive_renderer.physics = self.physics_engine
        
        # Configure visualization options
        self.interactive_renderer.show_forces = self.config.show_force_vectors
        self.interactive_renderer.show_trails = self.config.show_motion_trails
        self.interactive_renderer.show_grid = self.config.enable_professional_grid
        
    def setup_interaction_layer(self):
        """Setup natural interaction paradigms"""
        if not self.config.enable_haptic_feedback:
            return
            
        self.physics_interaction = PhysicsInteractionLayer(self)
        self.physics_interaction.set_interaction_mode(self.config.default_interaction_mode)
        
    def setup_parametric_controls(self):
        """Setup real-time parametric controls"""
        if not self.config.enable_parametric_controls:
            return
            
        self.parametric_controls = ParametricControlPanel(self)
        
    def create_tab_layout(self):
        """Create the universal tab layout structure"""
        # Main horizontal splitter
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.setChildrenCollapsible(False)
        
        # Left panel for controls (if parametric controls enabled)
        if self.parametric_controls:
            main_splitter.addWidget(self.parametric_controls)
            main_splitter.setSizes([300, 800])  # 300px for controls, rest for visualization
        
        # Central visualization area
        visualization_widget = self.create_visualization_widget()
        main_splitter.addWidget(visualization_widget)
        
        # Main layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(main_splitter)
        
    def create_visualization_widget(self) -> QWidget:
        """Create the central visualization widget"""
        # Container for interactive renderer and physics interaction layer
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        
        if self.interactive_renderer:
            layout.addWidget(self.interactive_renderer)
            
        # Overlay physics interaction layer if enabled
        if self.physics_interaction:
            # The physics interaction layer will be overlaid on the renderer
            pass
            
        return container
        
    def connect_component_signals(self):
        """Connect signals between components"""
        # Interactive renderer signals
        if self.interactive_renderer:
            self.interactive_renderer.parameterChanged.connect(self.on_parameter_changed)
            
        # Parametric controls signals
        if self.parametric_controls:
            self.parametric_controls.parameterChanged.connect(self.on_parameter_changed)
            self.parametric_controls.configurationChanged.connect(self.on_configuration_changed)
            
        # Physics interaction signals
        if self.physics_interaction:
            self.physics_interaction.componentGrabbed.connect(self.on_component_grabbed)
            self.physics_interaction.componentDragged.connect(self.on_component_dragged)
            self.physics_interaction.componentReleased.connect(self.on_component_released)
            
    def set_mechanism(self, mechanism_data: Dict[str, Any]):
        """Set the mechanism data for visualization and interaction"""
        self.mechanism_data = mechanism_data
        
        # Update interactive renderer
        if self.interactive_renderer:
            self.interactive_renderer.set_mechanism(mechanism_data)
            
        # Update parametric controls with mechanism parameters
        if self.parametric_controls and 'parameters' in mechanism_data:
            self.setup_mechanism_parameters(mechanism_data['parameters'])
            
        # Let subclass handle mechanism-specific setup
        self.on_mechanism_changed(mechanism_data)
        
        # Emit signal
        self.mechanismChanged.emit(mechanism_data)
        
    def setup_mechanism_parameters(self, parameter_definitions: Dict[str, Any]):
        """Setup parametric controls based on mechanism parameters"""
        if not self.parametric_controls:
            return
            
        # Clear existing parameters
        self.parametric_controls.parameters.clear()
        self.parametric_controls.parameter_groups.clear()
        
        # Group parameters by category
        parameter_groups = {}
        
        for param_name, param_def in parameter_definitions.items():
            category = param_def.get('category', 'General')
            if category not in parameter_groups:
                parameter_groups[category] = []
                
            # Create parameter state
            param_state = ParameterState(
                name=param_name,
                value=param_def.get('default', 0.0),
                parameter_type=ParameterType(param_def.get('type', 'length')),
                constraint=ParameterConstraint(
                    min_value=param_def.get('min', 0.0),
                    max_value=param_def.get('max', 100.0),
                    step_size=param_def.get('step', 0.1)
                )
            )
            
            parameter_groups[category].append(param_state)
            
        # Add parameter groups to controls
        for category, parameters in parameter_groups.items():
            self.parametric_controls.add_parameter_group(category, parameters)
            
    def start_simulation(self):
        """Start the mechanism simulation"""
        if self.interactive_renderer and self.simulation_state != "running":
            self.interactive_renderer.start_animation()
            self.simulation_state = "running"
            self.simulationStateChanged.emit("running")
            
    def stop_simulation(self):
        """Stop the mechanism simulation"""
        if self.interactive_renderer and self.simulation_state != "stopped":
            self.interactive_renderer.stop_animation()
            self.simulation_state = "stopped"
            self.simulationStateChanged.emit("stopped")
            
    def reset_simulation(self):
        """Reset the simulation to initial state"""
        if self.interactive_renderer:
            self.interactive_renderer.animation_time = 0.0
            self.interactive_renderer.motion_trails.clear()
            
        self.simulation_state = "reset"
        self.simulationStateChanged.emit("reset")
        
    def _update_performance_metrics(self):
        """Update performance metrics for optimization"""
        current_time = time.time()
        
        # Calculate FPS
        if self.frame_times:
            avg_frame_time = sum(self.frame_times) / len(self.frame_times)
            current_fps = 1.0 / avg_frame_time if avg_frame_time > 0 else 0
        else:
            current_fps = 0
            
        # Performance metrics
        metrics = {
            'fps': current_fps,
            'target_fps': self.config.target_fps,
            'frame_count': len(self.frame_times),
            'physics_enabled': self.config.enable_real_time_solving,
            'constraint_iterations': self.config.constraint_iterations
        }
        
        # Adaptive quality adjustment
        if self.config.enable_adaptive_quality:
            if current_fps < self.config.target_fps * 0.8:  # 80% of target
                # Reduce quality
                if self.physics_engine and self.physics_engine.constraint_iterations > 1:
                    self.physics_engine.constraint_iterations -= 1
            elif current_fps > self.config.target_fps * 1.1:  # 110% of target
                # Increase quality
                if self.physics_engine and self.physics_engine.constraint_iterations < 5:
                    self.physics_engine.constraint_iterations += 1
                    
        # Clear frame times periodically
        if len(self.frame_times) > 60:
            self.frame_times = self.frame_times[-30:]
            
        self.performanceMetricsUpdated.emit(metrics)
        
    def paintEvent(self, event):
        """Track frame timing for performance monitoring"""
        current_time = time.time()
        if self.last_frame_time > 0:
            frame_time = current_time - self.last_frame_time
            self.frame_times.append(frame_time)
            
        self.last_frame_time = current_time
        super().paintEvent(event)
        
    # Signal handlers
    def on_parameter_changed(self, param_name: str, value: float):
        """Handle parameter changes from any source"""
        self.current_parameters[param_name] = value
        
        # Update interactive renderer with new parameters
        if self.interactive_renderer:
            self.interactive_renderer.update_parameters({param_name: value})
            
        # Let subclass handle parameter-specific logic
        self.handle_parameter_change(param_name, value)
        
        self.parameterChanged.emit(param_name, value)
        
    def on_configuration_changed(self, config: Dict[str, float]):
        """Handle complete configuration changes"""
        self.current_parameters.update(config)
        
        # Update interactive renderer
        if self.interactive_renderer:
            self.interactive_renderer.update_parameters(config)
            
        # Let subclass handle configuration changes
        self.handle_configuration_change(config)
        
    def on_component_grabbed(self, component_id: str, position):
        """Handle component grab events"""
        # Let subclass handle component interaction
        self.handle_component_grabbed(component_id, position)
        
    def on_component_dragged(self, component_id: str, position, physics_data: Dict):
        """Handle component drag events"""
        # Update mechanism based on physics data
        if 'forces' in physics_data:
            # Update force visualization
            pass
            
        # Let subclass handle drag events
        self.handle_component_dragged(component_id, position, physics_data)
        
    def on_component_released(self, component_id: str, position):
        """Handle component release events"""
        # Let subclass handle release events
        self.handle_component_released(component_id, position)
        
    # Abstract methods for subclass implementation
    @abstractmethod
    def setup_mechanism_specific_components(self):
        """Setup components specific to the mechanism type"""
        pass
        
    @abstractmethod
    def on_mechanism_changed(self, mechanism_data: Dict[str, Any]):
        """Handle mechanism data changes"""
        pass
        
    @abstractmethod
    def handle_parameter_change(self, param_name: str, value: float):
        """Handle parameter changes specific to the mechanism"""
        pass
        
    @abstractmethod
    def handle_configuration_change(self, config: Dict[str, float]):
        """Handle configuration changes specific to the mechanism"""
        pass
        
    @abstractmethod
    def handle_component_grabbed(self, component_id: str, position):
        """Handle component grab events specific to the mechanism"""
        pass
        
    @abstractmethod
    def handle_component_dragged(self, component_id: str, position, physics_data: Dict):
        """Handle component drag events specific to the mechanism"""
        pass
        
    @abstractmethod
    def handle_component_released(self, component_id: str, position):
        """Handle component release events specific to the mechanism"""
        pass
        
    # Utility methods
    def get_current_mechanism(self) -> Dict[str, Any]:
        """Get current mechanism data"""
        return self.mechanism_data.copy()
        
    def get_current_parameters(self) -> Dict[str, float]:
        """Get current parameter values"""
        return self.current_parameters.copy()
        
    def export_state(self) -> Dict[str, Any]:
        """Export current tab state"""
        return {
            'mechanism_data': self.mechanism_data,
            'parameters': self.current_parameters,
            'simulation_state': self.simulation_state,
            'config': {
                'enable_professional_grid': self.config.enable_professional_grid,
                'show_force_vectors': self.config.show_force_vectors,
                'show_motion_trails': self.config.show_motion_trails,
                'target_fps': self.config.target_fps
            }
        }
        
    def import_state(self, state: Dict[str, Any]):
        """Import tab state"""
        if 'mechanism_data' in state:
            self.set_mechanism(state['mechanism_data'])
            
        if 'parameters' in state:
            self.on_configuration_changed(state['parameters'])
            
        if 'config' in state:
            config = state['config']
            self.config.enable_professional_grid = config.get('enable_professional_grid', True)
            self.config.show_force_vectors = config.get('show_force_vectors', True)
            self.config.show_motion_trails = config.get('show_motion_trails', True)
            self.config.target_fps = config.get('target_fps', 60)