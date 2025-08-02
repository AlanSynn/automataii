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
from abc import ABC, abstractmethod

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

from .panels.unified_visualization import UnifiedMechanismRenderer, RenderSettings, GridSettings
from .hci.physics_interaction import PhysicsInteractionLayer, InteractionMode
from .hci.parametric_controls import ParametricControlPanel, ParameterState, ParameterType


@dataclass
class MacanismStyleConfig:
    """Configuration for macanism-style visual design"""
    # Professional color palette
    background_color: QColor = QColor(250, 250, 250)  # Clean white
    primary_accent: QColor = QColor(0, 123, 255)      # Professional blue
    secondary_accent: QColor = QColor(108, 117, 125)   # Neutral gray
    success_color: QColor = QColor(40, 167, 69)       # Success green
    warning_color: QColor = QColor(255, 193, 7)       # Warning amber
    danger_color: QColor = QColor(220, 53, 69)        # Error red
    
    # Grid system (matching macanism)
    grid_major_size: float = 100.0   # Major grid lines every 100px
    grid_minor_size: float = 20.0    # Minor grid lines every 20px
    grid_show_measurements: bool = True
    grid_show_origin: bool = True
    
    # Typography
    header_font_size: int = 18
    body_font_size: int = 14
    small_font_size: int = 12
    
    # Performance settings
    target_fps: int = 60
    adaptive_quality: bool = True
    physics_update_rate: int = 120  # Hz
    
    def __post_init__(self):
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


class MacanismStyleTab(QWidget, ABC):
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
        self.parameter_panel: Optional[ParametricControlPanel] = None
        
        # Performance system
        self.performance_monitor = PerformanceMonitor(self.config.target_fps)
        self.physics_thread: Optional[PhysicsThread] = None
        
        # Animation system
        self.animation_timer = QTimer()\n        self.animation_timer.timeout.connect(self._update_animations)\n        \n        # Current state\n        self.current_mechanism_id: Optional[str] = None\n        self.current_mechanism_data: Dict[str, Any] = {}\n        self.is_initialized = False\n        \n        # UI components (will be set by subclasses)\n        self.main_splitter: Optional[QSplitter] = None\n        self.visualization_container: Optional[QFrame] = None\n        self.control_container: Optional[QFrame] = None\n        \n        self.setup_universal_architecture()\n        \n    def setup_universal_architecture(self):\n        \"\"\"Setup the universal macanism-style architecture\"\"\"\n        # Main layout\n        self.main_layout = QVBoxLayout(self)\n        self.main_layout.setContentsMargins(0, 0, 0, 0)\n        self.main_layout.setSpacing(0)\n        \n        # Status bar for performance and information\n        self.status_bar = self._create_status_bar()\n        \n        # Main content area\n        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)\n        self.main_splitter.setStyleSheet(self._get_splitter_stylesheet())\n        \n        # Visualization area (left side)\n        self.visualization_container = self._create_visualization_container()\n        self.main_splitter.addWidget(self.visualization_container)\n        \n        # Control area (right side)  \n        self.control_container = self._create_control_container()\n        self.main_splitter.addWidget(self.control_container)\n        \n        # Set initial splitter proportions (75% visualization, 25% controls)\n        self.main_splitter.setSizes([800, 300])\n        \n        # Add to main layout\n        self.main_layout.addWidget(self.main_splitter)\n        self.main_layout.addWidget(self.status_bar)\n        \n        # Initialize core components\n        self._initialize_core_components()\n        \n        # Setup tab-specific UI (implemented by subclasses)\n        self.setup_tab_specific_ui()\n        \n        # Start performance monitoring\n        self._start_performance_monitoring()\n        \n        self.is_initialized = True\n        \n    def _create_status_bar(self) -> QFrame:\n        \"\"\"Create professional status bar with performance metrics\"\"\"\n        status_frame = QFrame()\n        status_frame.setFixedHeight(24)\n        status_frame.setStyleSheet(\"\"\"\n            QFrame {\n                background-color: #f8f9fa;\n                border-top: 1px solid #dee2e6;\n            }\n        \"\"\")\n        \n        status_layout = QHBoxLayout(status_frame)\n        status_layout.setContentsMargins(8, 2, 8, 2)\n        status_layout.setSpacing(16)\n        \n        # Performance indicator\n        self.fps_label = QLabel(\"FPS: --\")\n        self.fps_label.setStyleSheet(\"color: #6c757d; font-size: 11px;\")\n        \n        # Quality indicator\n        self.quality_label = QLabel(\"Quality: 100%\")\n        self.quality_label.setStyleSheet(\"color: #6c757d; font-size: 11px;\")\n        \n        # Status message\n        self.status_message = QLabel(\"Ready\")\n        self.status_message.setStyleSheet(\"color: #495057; font-size: 11px;\")\n        \n        status_layout.addWidget(self.status_message)\n        status_layout.addStretch()\n        status_layout.addWidget(self.quality_label)\n        status_layout.addWidget(self.fps_label)\n        \n        return status_frame\n        \n    def _create_visualization_container(self) -> QFrame:\n        \"\"\"Create container for visualization components\"\"\"\n        container = QFrame()\n        container.setStyleSheet(\"\"\"\n            QFrame {\n                background-color: #fafafa;\n                border: 1px solid #dee2e6;\n                border-radius: 8px;\n            }\n        \"\"\")\n        \n        # Layout will be set up by subclasses\n        return container\n        \n    def _create_control_container(self) -> QFrame:\n        \"\"\"Create container for control components\"\"\"\n        container = QFrame()\n        container.setStyleSheet(\"\"\"\n            QFrame {\n                background-color: #f8f9fa;\n                border: 1px solid #dee2e6;\n                border-radius: 8px;\n            }\n        \"\"\")\n        \n        # Layout will be set up by subclasses\n        return container\n        \n    def _initialize_core_components(self):\n        \"\"\"Initialize the core macanism-style components\"\"\"\n        # Unified renderer with macanism styling\n        self.unified_renderer = UnifiedMechanismRenderer(self.config.render_settings)\n        \n        # Physics interaction layer\n        self.physics_layer = PhysicsInteractionLayer()\n        self.physics_layer.componentGrabbed.connect(self._on_component_grabbed)\n        self.physics_layer.componentDragged.connect(self._on_component_dragged)\n        self.physics_layer.componentReleased.connect(self._on_component_released)\n        \n        # Parameter control panel\n        self.parameter_panel = ParametricControlPanel()\n        self.parameter_panel.parameterChanged.connect(self._on_parameter_changed)\n        self.parameter_panel.configurationChanged.connect(self._on_configuration_changed)\n        \n        # Physics thread for smooth calculations\n        self.physics_thread = PhysicsThread(self.config.physics_update_rate)\n        self.physics_thread.physicsUpdated.connect(self._on_physics_updated)\n        \n    def _start_performance_monitoring(self):\n        \"\"\"Start the performance monitoring and animation system\"\"\"\n        # Start animation timer\n        target_interval = int(1000 / self.config.target_fps)  # ms\n        self.animation_timer.start(target_interval)\n        \n        # Start physics thread\n        if self.physics_thread:\n            self.physics_thread.start()\n            \n    def _update_animations(self):\n        \"\"\"Update animations and performance metrics\"\"\"\n        if not self.is_initialized:\n            return\n            \n        # Performance monitoring\n        self.performance_monitor.frame_start()\n        \n        # Update mechanism animations\n        if self.current_mechanism_data:\n            self._update_mechanism_animation()\n            \n        # Update UI components\n        self._update_ui_components()\n        \n        # Performance monitoring\n        self.performance_monitor.frame_end()\n        \n        # Update status bar\n        self._update_status_bar()\n        \n    def _update_mechanism_animation(self):\n        \"\"\"Update mechanism animation based on current state\"\"\"\n        # Animation logic specific to mechanism type\n        # This would be customized by subclasses\n        pass\n        \n    def _update_ui_components(self):\n        \"\"\"Update UI components with performance optimization\"\"\"\n        quality = self.performance_monitor.get_quality_settings()\n        \n        # Update renderer with quality settings\n        if self.unified_renderer:\n            # Adjust rendering quality based on performance\n            self.unified_renderer.settings.grid.show_grid = quality['grid_detail_level'] > 0.3\n            \n        # Update physics layer\n        if self.physics_layer:\n            # Adjust interaction sensitivity based on performance\n            pass\n            \n    def _update_status_bar(self):\n        \"\"\"Update status bar with current metrics\"\"\"\n        # FPS display\n        fps = self.performance_monitor.current_fps\n        if fps > 55:\n            color = \"#28a745\"  # Green\n        elif fps > 30:\n            color = \"#ffc107\"  # Yellow\n        else:\n            color = \"#dc3545\"  # Red\n            \n        self.fps_label.setText(f\"FPS: {fps:.1f}\")\n        self.fps_label.setStyleSheet(f\"color: {color}; font-size: 11px;\")\n        \n        # Quality display\n        quality = int(self.performance_monitor.quality_level * 100)\n        self.quality_label.setText(f\"Quality: {quality}%\")\n        \n    def _get_splitter_stylesheet(self) -> str:\n        \"\"\"Get stylesheet for the main splitter\"\"\"\n        return \"\"\"\n            QSplitter::handle {\n                background-color: #0d6efd;\n                width: 3px;\n                border-radius: 1px;\n            }\n            QSplitter::handle:hover {\n                background-color: #0b5ed7;\n            }\n        \"\"\"\n        \n    # Event handlers for universal component integration\n    def _on_component_grabbed(self, component_id: str, position: QPointF):\n        \"\"\"Handle component grab events\"\"\"\n        event_data = {\n            'component_id': component_id,\n            'position': (position.x(), position.y()),\n            'timestamp': time.time()\n        }\n        self.mechanismInteractionEvent.emit(\n            self.current_mechanism_id or \"\", \"component_grabbed\", event_data\n        )\n        \n    def _on_component_dragged(self, component_id: str, position: QPointF, physics_data: Dict):\n        \"\"\"Handle component drag events\"\"\"\n        event_data = {\n            'component_id': component_id,\n            'position': (position.x(), position.y()),\n            'physics': physics_data,\n            'timestamp': time.time()\n        }\n        self.mechanismInteractionEvent.emit(\n            self.current_mechanism_id or \"\", \"component_dragged\", event_data\n        )\n        \n    def _on_component_released(self, component_id: str, position: QPointF):\n        \"\"\"Handle component release events\"\"\"\n        event_data = {\n            'component_id': component_id,\n            'position': (position.x(), position.y()),\n            'timestamp': time.time()\n        }\n        self.mechanismInteractionEvent.emit(\n            self.current_mechanism_id or \"\", \"component_released\", event_data\n        )\n        \n    def _on_parameter_changed(self, param_name: str, value: float):\n        \"\"\"Handle parameter change events\"\"\"\n        if self.current_mechanism_id:\n            self.mechanismParameterChanged.emit(self.current_mechanism_id, param_name, value)\n            \n        # Update mechanism with new parameter\n        self._update_mechanism_parameters({param_name: value})\n        \n    def _on_configuration_changed(self, config: Dict[str, float]):\n        \"\"\"Handle full configuration change events\"\"\"\n        self._update_mechanism_parameters(config)\n        \n    def _on_physics_updated(self, physics_state: Dict[str, Any]):\n        \"\"\"Handle physics state updates from background thread\"\"\"\n        # Update visualization with new physics state\n        if self.unified_renderer:\n            self.unified_renderer.update_physics_data(\n                physics_state.get('forces', {}),\n                physics_state.get('velocities', {}),\n                physics_state.get('constraints', [])\n            )\n            \n    def _update_mechanism_parameters(self, parameters: Dict[str, float]):\n        \"\"\"Update mechanism with new parameters\"\"\"\n        # Update current mechanism data\n        if 'parameters' not in self.current_mechanism_data:\n            self.current_mechanism_data['parameters'] = {}\n            \n        self.current_mechanism_data['parameters'].update(parameters)\n        \n        # Send to physics thread\n        if self.physics_thread:\n            self.physics_thread.set_mechanism_data(self.current_mechanism_data)\n            \n    # Public interface methods\n    def select_mechanism(self, mechanism_id: str):\n        \"\"\"Select and display a mechanism\"\"\"\n        # Get mechanism data (implemented by subclasses)\n        mechanism_data = self.create_mechanism_data(mechanism_id)\n        \n        if mechanism_data:\n            self.current_mechanism_id = mechanism_id\n            self.current_mechanism_data = mechanism_data\n            \n            # Update all components\n            self._update_all_components(mechanism_data)\n            \n            # Trigger mechanism selection event\n            self.mechanismSelected.emit(mechanism_id, mechanism_data)\n            \n            # Handle mechanism-specific selection logic\n            self.handle_mechanism_selection(mechanism_id, mechanism_data)\n            \n    def _update_all_components(self, mechanism_data: Dict[str, Any]):\n        \"\"\"Update all components with new mechanism data\"\"\"\n        # Update renderer\n        if self.unified_renderer:\n            # Set renderer viewport if not already set\n            if hasattr(self, 'visualization_container'):\n                self.unified_renderer.set_viewport(QRectF(self.visualization_container.rect()))\n                \n        # Update physics layer\n        if self.physics_layer:\n            # Setup physics for new mechanism\n            pass\n            \n        # Update parameter panel\n        if self.parameter_panel and 'parameters' in mechanism_data:\n            self._setup_parameter_controls(mechanism_data['parameters'])\n            \n        # Update physics thread\n        if self.physics_thread:\n            self.physics_thread.set_mechanism_data(mechanism_data)\n            \n        # Update status\n        self.status_message.setText(f\"Loaded: {mechanism_data.get('name', mechanism_id)}\")\n        \n    def _setup_parameter_controls(self, parameter_definitions: Dict[str, Any]):\n        \"\"\"Setup parameter controls based on mechanism definition\"\"\"\n        # Clear existing parameters\n        # (This would need more sophisticated state management in practice)\n        \n        # Add parameter groups\n        for group_name, params in parameter_definitions.items():\n            if isinstance(params, dict):\n                parameter_states = []\n                \n                for param_name, param_config in params.items():\n                    # Create parameter state\n                    param_state = ParameterState(\n                        name=param_name,\n                        value=param_config.get('default', 0.0),\n                        parameter_type=ParameterType(param_config.get('type', 'length')),\n                        constraint=self._create_parameter_constraint(param_config)\n                    )\n                    parameter_states.append(param_state)\n                    \n                # Add to parameter panel\n                self.parameter_panel.add_parameter_group(group_name, parameter_states)\n                \n    def _create_parameter_constraint(self, param_config: Dict[str, Any]):\n        \"\"\"Create parameter constraint from configuration\"\"\"\n        from .hci.parametric_controls import ParameterConstraint\n        \n        return ParameterConstraint(\n            min_value=param_config.get('min', 0.0),\n            max_value=param_config.get('max', 100.0),\n            step_size=param_config.get('step', 0.1),\n            preferred_range=(param_config.get('pref_min', 0.0), param_config.get('pref_max', 100.0))\n        )\n        \n    def get_current_mechanism_data(self) -> Dict[str, Any]:\n        \"\"\"Get current mechanism data\"\"\"\n        return self.current_mechanism_data.copy()\n        \n    def get_performance_metrics(self) -> Dict[str, float]:\n        \"\"\"Get current performance metrics\"\"\"\n        return {\n            'fps': self.performance_monitor.current_fps,\n            'quality': self.performance_monitor.quality_level,\n            'dropped_frames': self.performance_monitor.dropped_frames\n        }\n        \n    def cleanup(self):\n        \"\"\"Clean up resources when tab is closed\"\"\"\n        # Stop animation timer\n        if self.animation_timer.isActive():\n            self.animation_timer.stop()\n            \n        # Stop physics thread\n        if self.physics_thread and self.physics_thread.isRunning():\n            self.physics_thread.stop()\n            \n    # Abstract methods that must be implemented by subclasses\n    @abstractmethod\n    def setup_tab_specific_ui(self):\n        \"\"\"Setup tab-specific UI components\"\"\"\n        pass\n        \n    @abstractmethod  \n    def create_mechanism_data(self, mechanism_id: str) -> Dict[str, Any]:\n        \"\"\"Create mechanism data for simulation\"\"\"\n        pass\n        \n    @abstractmethod\n    def handle_mechanism_selection(self, mechanism_id: str, mechanism_data: Dict[str, Any]):\n        \"\"\"Handle mechanism selection events\"\"\"\n        pass\n        \n    @abstractmethod\n    def get_educational_content(self, mechanism_id: str) -> Dict[str, Any]:\n        \"\"\"Get educational content for a mechanism\"\"\"\n        pass\n        \n    # Optional methods that can be overridden\n    def on_tab_activated(self):\n        \"\"\"Called when tab becomes active\"\"\"\n        # Resume animations\n        if not self.animation_timer.isActive():\n            self.animation_timer.start()\n            \n    def on_tab_deactivated(self):\n        \"\"\"Called when tab becomes inactive\"\"\"\n        # Pause animations to save CPU\n        if self.animation_timer.isActive():\n            self.animation_timer.stop()\n            \n    def closeEvent(self, event):\n        \"\"\"Handle tab close event\"\"\"\n        self.cleanup()\n        super().closeEvent(event)"