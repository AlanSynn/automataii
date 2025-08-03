"""
Macanism-Style Tab Base Class - Universal architecture for mechanism simulation

This module provides the foundational architecture for creating mechanism tabs that
match the professional quality and aesthetics of github.com/AlanSynn/macanism.

Features:
- Universal component integration system
- 60fps performance optimization with adaptive rendering
- Professional macanism-style visual design system
- Consistent interaction patterns across all mechanism tabs
- Real-time physics simulation with constraint solving
- Educational content integration with professional presentation

The architecture enables any mechanism tab to achieve macanism-level quality
while maintaining unique functionality and educational objectives.
"""

import math
import time
from typing import Optional, Dict, List, Tuple, Any, Protocol
from dataclasses import dataclass
from abc import abstractmethod

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QFrame,
    QLabel, QPushButton, QProgressBar, QStatusBar
)
from PyQt6.QtCore import (
    Qt, QTimer, QThread, pyqtSignal, QRectF, QPointF,
    QPropertyAnimation, QEasingCurve, QParallelAnimationGroup
)
from PyQt6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QLinearGradient,
    QPainterPath, QTransform
)

from .hci.unified_visualization import UnifiedMechanismRenderer, RenderSettings, GridSettings
from .hci.physics_interaction import PhysicsInteractionLayer, InteractionMode
from .hci.parametric_controls import ParametricControlPanel, ParameterState, ParameterType


class MacanismStyleConfig:
    """Configuration for macanism-style visual design"""
    
    def __init__(self):
        # Professional color palette
        self.background_color = QColor(250, 250, 250)  # Clean white
        self.primary_accent = QColor(0, 123, 255)      # Professional blue
        self.secondary_accent = QColor(108, 117, 125)   # Neutral gray
        self.success_color = QColor(40, 167, 69)       # Success green
        self.warning_color = QColor(255, 193, 7)       # Warning amber
        self.danger_color = QColor(220, 53, 69)        # Error red
        
        # Grid system (matching macanism)
        self.grid_major_size = 100.0   # Major grid lines every 100px
        self.grid_minor_size = 20.0    # Minor grid lines every 20px
        self.grid_show_measurements = True
        self.grid_show_origin = True
        
        # Typography
        self.header_font_size = 18
        self.body_font_size = 14
        self.small_font_size = 12
        
        # Performance settings
        self.target_fps = 60
        self.adaptive_quality = True
        self.physics_update_rate = 120  # Hz
        
        self._setup_derived_settings()
    
    def _setup_derived_settings(self):
        """Initialize derived colors and settings"""
        # Create grid settings
        self.grid_settings = GridSettings(
            show_grid=True,
            grid_size=self.grid_minor_size,
            major_grid_size=self.grid_major_size,
            show_measurements=self.grid_show_measurements,
            show_origin=self.grid_show_origin
        )
        
        # Create render settings
        self.render_settings = RenderSettings()
        self.render_settings.background_color = self.background_color
        self.render_settings.grid = self.grid_settings


class PerformanceMonitor:
    """Monitor and optimize rendering performance for smooth 60fps"""
    
    def __init__(self, target_fps: int = 60):
        self.target_fps = target_fps
        self.target_frame_time = 1000.0 / target_fps  # ms
        
        # Performance tracking
        self.frame_times: List[float] = []
        self.last_frame_time = time.time()
        self.current_fps = 0.0
        self.dropped_frames = 0
        
        # Adaptive quality settings
        self.quality_level = 1.0  # 0.0 to 1.0
        self.min_quality = 0.3
        self.quality_adjustment_rate = 0.05
        
    def frame_start(self):
        """Mark the start of a frame"""
        self.last_frame_time = time.time()
        
    def frame_end(self):
        """Mark the end of a frame and update performance metrics"""
        current_time = time.time()
        frame_time = (current_time - self.last_frame_time) * 1000  # Convert to ms
        
        # Update frame time history
        self.frame_times.append(frame_time)
        if len(self.frame_times) > 60:  # Keep last 60 frames
            self.frame_times.pop(0)
            
        # Calculate current FPS
        if len(self.frame_times) > 10:
            avg_frame_time = sum(self.frame_times[-10:]) / 10
            self.current_fps = 1000.0 / avg_frame_time if avg_frame_time > 0 else 0
            
        # Adaptive quality adjustment
        if frame_time > self.target_frame_time * 1.2:  # Frame taking too long
            self.quality_level = max(self.min_quality, 
                                   self.quality_level - self.quality_adjustment_rate)
            self.dropped_frames += 1
        elif frame_time < self.target_frame_time * 0.8:  # Frame finished early
            self.quality_level = min(1.0, 
                                   self.quality_level + self.quality_adjustment_rate * 0.5)
            
    def get_quality_settings(self) -> Dict[str, Any]:
        """Get current quality settings for rendering"""
        return {
            'grid_detail_level': self.quality_level,
            'physics_substeps': max(1, int(4 * self.quality_level)),
            'force_vector_detail': self.quality_level > 0.7,
            'motion_trail_length': int(50 * self.quality_level),
            'antialiasing': self.quality_level > 0.5
        }


class PhysicsThread(QThread):
    """Dedicated thread for physics calculations to maintain smooth UI"""
    
    physicsUpdated = pyqtSignal(dict)  # Updated physics state
    
    def __init__(self, update_rate: int = 120):
        super().__init__()
        self.update_rate = update_rate
        self.update_interval = 1.0 / update_rate
        self.running = False
        
        # Physics state
        self.mechanism_data = {}
        self.constraint_data = {}
        self.force_data = {}
        
    def set_mechanism_data(self, data: Dict[str, Any]):
        """Update mechanism data for physics calculations"""
        self.mechanism_data = data
        
    def run(self):
        """Main physics calculation loop"""
        self.running = True
        last_update = time.time()
        
        while self.running:
            current_time = time.time()
            dt = current_time - last_update
            
            if dt >= self.update_interval:
                # Perform physics calculations
                updated_state = self._calculate_physics_state(dt)
                
                # Emit updated state
                self.physicsUpdated.emit(updated_state)
                
                last_update = current_time
            else:
                # Sleep for remaining time
                sleep_time = self.update_interval - dt
                self.msleep(int(sleep_time * 1000))
                
    def stop(self):
        """Stop the physics thread"""
        self.running = False
        self.wait()
        
    def _calculate_physics_state(self, dt: float) -> Dict[str, Any]:
        """Calculate updated physics state"""
        # Advanced physics calculations would go here
        # For now, return placeholder data
        return {
            'timestamp': time.time(),
            'dt': dt,
            'forces': {},
            'velocities': {},
            'positions': {},
            'constraints': []
        }


class MacanismStyleTab(QWidget):
    """
    Abstract base class for mechanism tabs with macanism-style architecture.
    
    This class provides the foundational infrastructure for creating professional
    mechanism simulation tabs that match the quality and aesthetics of macanism.
    
    Features:
    - Universal component integration (renderer, physics, controls)
    - 60fps performance optimization with adaptive quality
    - Professional visual design system
    - Real-time physics simulation
    - Consistent interaction patterns
    - Educational content integration
    
    Subclasses must implement:
    - setup_tab_specific_ui(): Create tab-specific UI components
    - create_mechanism_data(): Generate mechanism data for simulation  
    - handle_mechanism_selection(): Handle mechanism selection events
    - get_educational_content(): Provide educational content for mechanisms
    """
    
    # Universal signals for mechanism interactions
    mechanismSelected = pyqtSignal(str, dict)  # mechanism_id, mechanism_data
    mechanismParameterChanged = pyqtSignal(str, str, float)  # mechanism_id, param_name, value
    mechanismInteractionEvent = pyqtSignal(str, str, dict)  # mechanism_id, event_type, event_data
    educationalContentRequested = pyqtSignal(str)  # mechanism_id
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        # Configuration
        self.config = MacanismStyleConfig()
        
        # Core components
        self.unified_renderer: Optional[UnifiedMechanismRenderer] = None
        self.physics_layer: Optional[PhysicsInteractionLayer] = None
        self.parametric_controls: Optional[ParametricControlPanel] = None
        
        # Performance system
        self.performance_monitor = PerformanceMonitor(self.config.target_fps)
        self.physics_thread: Optional[PhysicsThread] = None
        
        # Animation system
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self._update_animations)
        
        # Current state
        self.current_mechanism_id: Optional[str] = None
        self.current_mechanism_data: Dict[str, Any] = {}
        self.is_initialized = False
        
        # UI components (will be set by subclasses)
        self.main_splitter: Optional[QSplitter] = None
        self.visualization_container: Optional[QFrame] = None
        self.control_container: Optional[QFrame] = None
        
        self.setup_universal_architecture()
        
    def setup_universal_architecture(self):
        """Setup the universal macanism-style architecture"""
        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # Status bar for performance and information
        self.status_bar = self._create_status_bar()
        
        # Main content area  
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setStyleSheet(self._get_splitter_stylesheet())
        
        # Visualization area (left side)
        self.visualization_container = self._create_visualization_container()
        self.main_splitter.addWidget(self.visualization_container)
        
        # Control area (right side)
        self.control_container = self._create_control_container()
        self.main_splitter.addWidget(self.control_container)
        
        # Set initial splitter proportions (75% visualization, 25% controls)
        self.main_splitter.setSizes([800, 300])
        
        # Add to main layout
        self.main_layout.addWidget(self.main_splitter)
        self.main_layout.addWidget(self.status_bar)
        
        # Initialize core components
        self._initialize_core_components()
        
        # Setup tab-specific UI (implemented by subclasses)
        self.setup_tab_specific_ui()
        
        # Start performance monitoring
        self._start_performance_monitoring()
        
        self.is_initialized = True
        
    def _create_status_bar(self) -> QFrame:
        """Create professional status bar with performance metrics"""
        status_frame = QFrame()
        status_frame.setFixedHeight(24)
        status_frame.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border-top: 1px solid #dee2e6;
            }
        """)
        
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(8, 2, 8, 2)
        status_layout.setSpacing(16)
        
        # Performance indicator
        self.fps_label = QLabel("FPS: --")
        self.fps_label.setStyleSheet("color: #6c757d; font-size: 11px;")
        
        # Quality indicator
        self.quality_label = QLabel("Quality: 100%")
        self.quality_label.setStyleSheet("color: #6c757d; font-size: 11px;")
        
        # Status message
        self.status_message = QLabel("Ready")
        self.status_message.setStyleSheet("color: #495057; font-size: 11px;")
        
        status_layout.addWidget(self.status_message)
        status_layout.addStretch()
        status_layout.addWidget(self.quality_label)
        status_layout.addWidget(self.fps_label)
        
        return status_frame
        
    def _create_visualization_container(self) -> QFrame:
        """Create container for visualization components"""
        container = QFrame()
        container.setStyleSheet("""
            QFrame {
                background-color: #fafafa;
                border: 1px solid #dee2e6;
                border-radius: 8px;
            }
        """)
        
        # Layout will be set up by subclasses
        return container
        
    def _create_control_container(self) -> QFrame:
        """Create container for control components"""
        container = QFrame()
        container.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 8px;
            }
        """)
        
        # Layout will be set up by subclasses
        return container
        
    def _initialize_core_components(self):
        """Initialize the core macanism-style components"""
        # Unified renderer with macanism styling
        self.unified_renderer = UnifiedMechanismRenderer(self.config.render_settings)
        
        # Physics interaction layer
        self.physics_layer = PhysicsInteractionLayer()
        self.physics_layer.componentGrabbed.connect(self._on_component_grabbed)
        self.physics_layer.componentDragged.connect(self._on_component_dragged)
        self.physics_layer.componentReleased.connect(self._on_component_released)
        
        # Parameter control panel
        self.parameter_panel = ParametricControlPanel()
        self.parameter_panel.parameterChanged.connect(self._on_parameter_changed)
        self.parameter_panel.configurationChanged.connect(self._on_configuration_changed)
        
        # Physics thread for smooth calculations
        self.physics_thread = PhysicsThread(self.config.physics_update_rate)
        self.physics_thread.physicsUpdated.connect(self._on_physics_updated)
        
    def _start_performance_monitoring(self):
        """Start the performance monitoring and animation system"""
        # Start animation timer
        target_interval = int(1000 / self.config.target_fps)  # ms
        self.animation_timer.start(target_interval)
        
        # Start physics thread
        if self.physics_thread:
            self.physics_thread.start()
            
    def _update_animations(self):
        """Update animations and performance metrics"""
        if not self.is_initialized:
            return
            
        # Performance monitoring
        self.performance_monitor.frame_start()
        
        # Update mechanism animations
        if self.current_mechanism_data:
            self._update_mechanism_animation()
            
        # Update UI components
        self._update_ui_components()
        
        # Performance monitoring
        self.performance_monitor.frame_end()
        
        # Update status bar
        self._update_status_bar()
        
    def _update_mechanism_animation(self):
        """Update mechanism animation based on current state"""
        # Animation logic specific to mechanism type
        # This would be customized by subclasses
        pass
        
    def _update_ui_components(self):
        """Update UI components with performance optimization"""
        quality = self.performance_monitor.get_quality_settings()
        
        # Update renderer with quality settings
        if self.unified_renderer:
            # Adjust rendering quality based on performance
            self.unified_renderer.settings.grid.show_grid = quality['grid_detail_level'] > 0.3
            
        # Update physics layer
        if self.physics_layer:
            # Adjust interaction sensitivity based on performance
            pass
            
    def _update_status_bar(self):
        """Update status bar with current metrics"""
        # FPS display
        fps = self.performance_monitor.current_fps
        if fps > 55:
            color = "#28a745"  # Green
        elif fps > 30:
            color = "#ffc107"  # Yellow
        else:
            color = "#dc3545"  # Red
            
        self.fps_label.setText(f"FPS: {fps:.1f}")
        self.fps_label.setStyleSheet(f"color: {color}; font-size: 11px;")
        
        # Quality display
        quality = int(self.performance_monitor.quality_level * 100)
        self.quality_label.setText(f"Quality: {quality}%")
        
    def _get_splitter_stylesheet(self) -> str:
        """Get stylesheet for the main splitter"""
        return """
            QSplitter::handle {
                background-color: #0d6efd;
                width: 3px;
                border-radius: 1px;
            }
            QSplitter::handle:hover {
                background-color: #0b5ed7;
            }
        """
        
    # Event handlers for universal component integration
    def _on_component_grabbed(self, component_id: str, position: QPointF):
        """Handle component grab events"""
        event_data = {
            'component_id': component_id,
            'position': (position.x(), position.y()),
            'timestamp': time.time()
        }
        self.mechanismInteractionEvent.emit(
            self.current_mechanism_id or "", "component_grabbed", event_data
        )
        
    def _on_component_dragged(self, component_id: str, position: QPointF, physics_data: Dict):
        """Handle component drag events"""
        event_data = {
            'component_id': component_id,
            'position': (position.x(), position.y()),
            'physics': physics_data,
            'timestamp': time.time()
        }
        self.mechanismInteractionEvent.emit(
            self.current_mechanism_id or "", "component_dragged", event_data
        )
        
    def _on_component_released(self, component_id: str, position: QPointF):
        """Handle component release events"""
        event_data = {
            'component_id': component_id,
            'position': (position.x(), position.y()),
            'timestamp': time.time()
        }
        self.mechanismInteractionEvent.emit(
            self.current_mechanism_id or "", "component_released", event_data
        )
        
    def _on_parameter_changed(self, param_name: str, value: float):
        """Handle parameter change events"""
        if self.current_mechanism_id:
            self.mechanismParameterChanged.emit(self.current_mechanism_id, param_name, value)
            
        # Update mechanism with new parameter
        self._update_mechanism_parameters({param_name: value})
        
    def _on_configuration_changed(self, config: Dict[str, float]):
        """Handle full configuration change events"""
        self._update_mechanism_parameters(config)
        
    def _on_physics_updated(self, physics_state: Dict[str, Any]):
        """Handle physics state updates from background thread"""
        # Update visualization with new physics state
        if self.unified_renderer:
            self.unified_renderer.update_physics_data(
                physics_state.get('forces', {}),
                physics_state.get('velocities', {}),
                physics_state.get('constraints', [])
            )
            
    def _update_mechanism_parameters(self, parameters: Dict[str, float]):
        """Update mechanism with new parameters"""
        # Update current mechanism data
        if 'parameters' not in self.current_mechanism_data:
            self.current_mechanism_data['parameters'] = {}
            
        self.current_mechanism_data['parameters'].update(parameters)
        
        # Send to physics thread
        if self.physics_thread:
            self.physics_thread.set_mechanism_data(self.current_mechanism_data)
            
    # Public interface methods
    def select_mechanism(self, mechanism_id: str):
        """Select and display a mechanism"""
        # Get mechanism data (implemented by subclasses)
        mechanism_data = self.create_mechanism_data(mechanism_id)
        
        if mechanism_data:
            self.current_mechanism_id = mechanism_id
            self.current_mechanism_data = mechanism_data
            
            # Update all components
            self._update_all_components(mechanism_data)
            
            # Trigger mechanism selection event
            self.mechanismSelected.emit(mechanism_id, mechanism_data)
            
            # Handle mechanism-specific selection logic
            self.handle_mechanism_selection(mechanism_id, mechanism_data)
            
    def _update_all_components(self, mechanism_data: Dict[str, Any]):
        """Update all components with new mechanism data"""
        # Update renderer
        if self.unified_renderer:
            # Set renderer viewport if not already set
            if hasattr(self, 'visualization_container'):
                self.unified_renderer.set_viewport(QRectF(self.visualization_container.rect()))
                
        # Update physics layer
        if self.physics_layer:
            # Setup physics for new mechanism
            pass
            
        # Update parameter panel
        if self.parameter_panel and 'parameters' in mechanism_data:
            self._setup_parameter_controls(mechanism_data['parameters'])
            
        # Update physics thread
        if self.physics_thread:
            self.physics_thread.set_mechanism_data(mechanism_data)
            
        # Update status
        self.status_message.setText(f"Loaded: {mechanism_data.get('name', mechanism_id)}")
        
    def _setup_parameter_controls(self, parameter_definitions: Dict[str, Any]):
        """Setup parameter controls based on mechanism definition"""
        # Clear existing parameters
        # (This would need more sophisticated state management in practice)
        
        # Add parameter groups
        for group_name, params in parameter_definitions.items():
            if isinstance(params, dict):
                parameter_states = []
                
                for param_name, param_config in params.items():
                    # Create parameter state
                    param_state = ParameterState(
                        name=param_name,
                        value=param_config.get('default', 0.0),
                        parameter_type=ParameterType(param_config.get('type', 'length')),
                        constraint=self._create_parameter_constraint(param_config)
                    )
                    parameter_states.append(param_state)
                    
                # Add to parameter panel
                self.parameter_panel.add_parameter_group(group_name, parameter_states)
                
    def _create_parameter_constraint(self, param_config: Dict[str, Any]):
        """Create parameter constraint from configuration"""
        from .hci.parametric_controls import ParameterConstraint
        
        return ParameterConstraint(
            min_value=param_config.get('min', 0.0),
            max_value=param_config.get('max', 100.0),
            step_size=param_config.get('step', 0.1),
            preferred_range=(param_config.get('pref_min', 0.0), param_config.get('pref_max', 100.0))
        )
        
    def get_current_mechanism_data(self) -> Dict[str, Any]:
        """Get current mechanism data"""
        return self.current_mechanism_data.copy()
        
    def get_performance_metrics(self) -> Dict[str, float]:
        """Get current performance metrics"""
        return {
            'fps': self.performance_monitor.current_fps,
            'quality': self.performance_monitor.quality_level,
            'dropped_frames': self.performance_monitor.dropped_frames
        }
        
    def cleanup(self):
        """Clean up resources when tab is closed"""
        # Stop animation timer
        if self.animation_timer.isActive():
            self.animation_timer.stop()
            
        # Stop physics thread
        if self.physics_thread and self.physics_thread.isRunning():
            self.physics_thread.stop()
            
    # Abstract methods that must be implemented by subclasses
    @abstractmethod
    def setup_tab_specific_ui(self):
        """Setup tab-specific UI components"""
        pass
        
    @abstractmethod
    def create_mechanism_data(self, mechanism_id: str) -> Dict[str, Any]:
        """Create mechanism data for simulation"""
        pass
        
    @abstractmethod
    def handle_mechanism_selection(self, mechanism_id: str, mechanism_data: Dict[str, Any]):
        """Handle mechanism selection events"""
        pass
        
    @abstractmethod
    def get_educational_content(self, mechanism_id: str) -> Dict[str, Any]:
        """Get educational content for a mechanism"""
        pass
        
    # Optional methods that can be overridden
    def on_tab_activated(self):
        """Called when tab becomes active"""
        # Resume animations
        if not self.animation_timer.isActive():
            self.animation_timer.start()
            
    def on_tab_deactivated(self):
        """Called when tab becomes inactive"""
        # Pause animations to save CPU
        if self.animation_timer.isActive():
            self.animation_timer.stop()
            
    def closeEvent(self, event):
        """Handle tab close event"""
        self.cleanup()
        super().closeEvent(event)