"""
Playground Panel - Interactive exploration and parameter manipulation

Provides hands-on learning through interactive mechanism manipulation:
- Large interactive mechanism visualization with real-time animation
- Parameter controls with sliders and spinboxes
- Visualization options (trace paths, labels, grid)
- Layer toggling and trace clearing
- Direct manipulation capabilities

Updated to use event-driven architecture with MechanismService.
"""

from typing import Optional, Dict
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QFrame, QPushButton, QCheckBox, QGroupBox,
    QGraphicsDropShadowEffect, QComboBox, QTextEdit, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QFont

from ..components import ParameterControls
from .interactive_mechanism import InteractiveMechanismRenderer
from automataii.services.mechanism_service import MechanismService


class VisualizationControls(QGroupBox):
    """Controls for visualization options"""
    
    # Signals for control changes
    labelsToggled = pyqtSignal(bool)
    gridToggled = pyqtSignal(bool)
    tracesToggled = pyqtSignal(bool)
    forcesToggled = pyqtSignal(bool)
    animationToggled = pyqtSignal(bool)
    clearTraces = pyqtSignal()
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__("🎛️ Visualization Controls", parent)
        self.setup_ui()
        
    def setup_ui(self):
        """Setup visualization controls"""
        self.setStyleSheet("""
            QGroupBox {
                font-size: 14px;
                font-weight: bold;
                color: #212529;
                border: none;
                border-radius: 12px;
                margin-top: 12px;
                padding-top: 12px;
                background-color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px 0 8px;
                background-color: #ffffff;
                color: #0d6efd;
            }
            QCheckBox {
                font-size: 13px;
                color: #212529;
                padding: 6px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: none;
                background-color: #e9ecef;
            }
            QCheckBox::indicator:checked {
                background-color: #0d6efd;
                border: none;
                image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTAiIGhlaWdodD0iOCIgdmlld0JveD0iMCAwIDEwIDgiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxwYXRoIGQ9Ik04LjUgMUwzLjUgNkwxLjUgNCIgc3Ryb2tlPSJ3aGl0ZSIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiLz4KPC9zdmc+);
            }
            QCheckBox::indicator:hover {
                background-color: #dee2e6;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 20, 16, 16)
        layout.setSpacing(8)
        
        # Simplified controls - only essential options
        self.show_labels = QCheckBox("📋 Component Labels")
        self.show_grid = QCheckBox("📐 Grid")
        self.animate = QCheckBox("▶️ Animation")
        
        # Set defaults for essential visualization
        self.animate.setChecked(True)
        self.show_labels.setChecked(True)
        self.show_grid.setChecked(True)
        
        # Add widgets - simplified layout
        layout.addWidget(self.show_labels)
        layout.addWidget(self.show_grid)
        layout.addWidget(self.animate)
        layout.addStretch()
        
        # Connect signals - simplified
        self.show_labels.toggled.connect(self.labelsToggled.emit)
        self.show_grid.toggled.connect(self.gridToggled.emit)
        self.animate.toggled.connect(self.animationToggled.emit)


class MechanismSelector(QGroupBox):
    """Mechanism selection control"""
    
    mechanismChanged = pyqtSignal(str)  # mechanism_type
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__("🔧 Mechanism Type", parent)
        self.setup_ui()
        
    def setup_ui(self):
        """Setup mechanism selector UI"""
        self.setStyleSheet("""
            QGroupBox {
                font-size: 14px;
                font-weight: bold;
                color: #212529;
                border: none;
                border-radius: 12px;
                margin-top: 12px;
                padding-top: 12px;
                background-color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px 0 8px;
                background-color: #ffffff;
                color: #0d6efd;
            }
            QComboBox {
                font-size: 13px;
                color: #212529;
                padding: 8px 12px;
                border: 2px solid #dee2e6;
                border-radius: 6px;
                background-color: #ffffff;
            }
            QComboBox:hover {
                border-color: #0d6efd;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 20, 16, 16)
        
        self.mechanism_combo = QComboBox()
        self.mechanism_combo.addItem("Four-Bar Linkage", "four_bar_linkage")
        self.mechanism_combo.addItem("Slider-Crank", "slider_crank")
        self.mechanism_combo.addItem("Gear Train", "gear_train")
        self.mechanism_combo.addItem("Cam-Follower", "cam_follower")
        self.mechanism_combo.addItem("Spring System", "spring_system")
        
        self.mechanism_combo.currentIndexChanged.connect(self._on_mechanism_changed)
        layout.addWidget(self.mechanism_combo)
        
    def _on_mechanism_changed(self, index: int):
        """Handle mechanism selection change"""
        mechanism_type = self.mechanism_combo.itemData(index)
        self.mechanismChanged.emit(mechanism_type)
        
    def get_selected_mechanism(self) -> str:
        """Get currently selected mechanism type"""
        return self.mechanism_combo.currentData()


class EducationalAnalysisPanel(QGroupBox):
    """Educational analysis display panel - macanism style"""
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__("📊 Analysis & Education", parent)
        self.setup_ui()
        
    def setup_ui(self):
        """Setup educational analysis UI"""
        self.setStyleSheet("""
            QGroupBox {
                font-size: 14px;
                font-weight: bold;
                color: #212529;
                border: none;
                border-radius: 12px;
                margin-top: 12px;
                padding-top: 12px;
                background-color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px 0 8px;
                background-color: #ffffff;
                color: #0d6efd;
            }
            QTextEdit {
                font-size: 12px;
                color: #495057;
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 6px;
                padding: 8px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 20, 16, 16)
        layout.setSpacing(8)
        
        # Create scrollable text area for analysis
        self.analysis_text = QTextEdit()
        self.analysis_text.setMaximumHeight(200)
        self.analysis_text.setReadOnly(True)
        
        # Set professional font
        font = QFont("Monaco", 10)  # Monospace font for technical data
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.analysis_text.setFont(font)
        
        # Initialize with placeholder text
        self.analysis_text.setHtml("""
        <div style='font-family: system-ui; font-size: 12px; color: #6c757d;'>
            <h4 style='color: #0d6efd; margin: 0 0 8px 0;'>🔧 Mechanism Analysis</h4>
            <p style='margin: 4px 0;'>Select a mechanism to view detailed analysis...</p>
        </div>
        """)
        
        layout.addWidget(self.analysis_text)
        
    def update_analysis(self, educational_data: Dict):
        """Update analysis display with mechanism data"""
        if not educational_data:
            return
            
        # Build formatted analysis HTML
        html_content = f"""
        <div style='font-family: system-ui; font-size: 12px;'>
            <h4 style='color: #0d6efd; margin: 0 0 8px 0;'>🔧 {educational_data.get('current_state', {}).get('mechanism_name', 'Mechanism')} Analysis</h4>
        """
        
        # Add key concepts
        if 'key_concepts' in educational_data:
            html_content += "<h5 style='color: #6f42c1; margin: 8px 0 4px 0;'>📚 Key Concepts:</h5><ul style='margin: 4px 0 8px 16px;'>"
            for concept in educational_data['key_concepts'][:3]:  # Show top 3
                html_content += f"<li style='margin: 2px 0;'>{concept}</li>"
            html_content += "</ul>"
        
        # Add mechanism-specific analysis
        if 'grashof_analysis' in educational_data:
            grashof = educational_data['grashof_analysis']
            html_content += f"<h5 style='color: #dc3545; margin: 8px 0 4px 0;'>⚙️ Grashof Analysis:</h5>"
            html_content += f"<p style='margin: 2px 0;'><strong>Type:</strong> {grashof.get('mechanism_type', 'N/A')}</p>"
            html_content += f"<p style='margin: 2px 0;'><strong>Ratio:</strong> {grashof.get('grashof_ratio', 'N/A')}</p>"
            
        elif 'spring_analysis' in educational_data:
            spring = educational_data['spring_analysis']
            html_content += f"<h5 style='color: #28a745; margin: 8px 0 4px 0;'>🌀 Spring Analysis:</h5>"
            html_content += f"<p style='margin: 2px 0;'><strong>Natural Freq:</strong> {spring.get('natural_frequency', 'N/A')}</p>"
            html_content += f"<p style='margin: 2px 0;'><strong>Damping:</strong> {spring.get('damping_type', 'N/A')}</p>"
            
        elif 'cam_analysis' in educational_data:
            cam = educational_data['cam_analysis']
            html_content += f"<h5 style='color: #fd7e14; margin: 8px 0 4px 0;'>📐 Cam Analysis:</h5>"
            html_content += f"<p style='margin: 2px 0;'><strong>Motion Law:</strong> {cam.get('motion_law', 'N/A')}</p>"
            html_content += f"<p style='margin: 2px 0;'><strong>Max Accel:</strong> {cam.get('max_acceleration', 'N/A')}</p>"
        
        # Add current state info
        if 'current_state' in educational_data:
            state = educational_data['current_state']
            html_content += f"<h5 style='color: #17a2b8; margin: 8px 0 4px 0;'>📊 Current State:</h5>"
            html_content += f"<p style='margin: 2px 0;'><strong>Valid:</strong> {'✅' if state.get('is_valid', False) else '❌'}</p>"
            html_content += f"<p style='margin: 2px 0;'><strong>Params:</strong> {state.get('parameter_count', 0)}</p>"
        
        html_content += "</div>"
        
        self.analysis_text.setHtml(html_content)


class PlaygroundPanel(QWidget):
    """
    Playground panel for interactive mechanism exploration.
    
    Features:
    - Mechanism type selection
    - Large interactive mechanism visualization  
    - Real-time parameter manipulation via MechanismService
    - Visualization controls and options
    - Direct hands-on exploration
    - Animation controls with physics integration
    """
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        print("PlaygroundPanel: Initializing...")
        
        # Initialize mechanism service
        self.mechanism_service = MechanismService()
        self.current_mechanism_id = "playground_mechanism"
        print(f"PlaygroundPanel: Service initialized with ID {self.current_mechanism_id}")
        
        # Animation control
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self._update_animation)
        self.animation_angle = 0.0
        self.animation_running = True
        
        self.setup_ui()
        self.connect_signals()
        
        # Create initial mechanism (four-bar linkage)
        self._create_initial_mechanism()
        
    def setup_ui(self):
        """Setup the playground panel UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        # Create splitter for visualization and controls
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #0d6efd;
                width: 3px;
                border-radius: 1px;
            }
            QSplitter::handle:hover {
                background-color: #0b5ed7;
            }
        """)
        
        # Left side: Professional macanism-style visualization
        viz_container = QFrame()
        viz_container.setStyleSheet("""
            QFrame {
                background-color: #fafafa;
                border-radius: 12px;
                border: none;
            }
        """)
        viz_layout = QVBoxLayout(viz_container)
        viz_layout.setContentsMargins(4, 4, 4, 4)
        
        # Add shadow effect
        viz_shadow = QGraphicsDropShadowEffect()
        viz_shadow.setBlurRadius(20)
        viz_shadow.setXOffset(0)
        viz_shadow.setYOffset(2)
        viz_shadow.setColor(QColor(0, 0, 0, 40))
        viz_container.setGraphicsEffect(viz_shadow)
        
        self.visualization = InteractiveMechanismRenderer()
        viz_layout.addWidget(self.visualization)
        
        splitter.addWidget(viz_container)
        
        # Right side: Enhanced Controls panel with scroll area
        controls_scroll = QScrollArea()
        controls_scroll.setWidgetResizable(True)
        controls_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        controls_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        controls_scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #ffffff;
                border-radius: 12px;
            }
            QScrollBar:vertical {
                width: 8px;
                background-color: #f8f9fa;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background-color: #dee2e6;
                border-radius: 4px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #adb5bd;
            }
        """)
        
        controls_panel = QWidget()
        controls_layout = QVBoxLayout(controls_panel)
        controls_layout.setContentsMargins(12, 12, 12, 12)
        controls_layout.setSpacing(12)
        
        # Add shadow effect to scroll area instead
        controls_shadow = QGraphicsDropShadowEffect()
        controls_shadow.setBlurRadius(20)
        controls_shadow.setXOffset(0)
        controls_shadow.setYOffset(2)
        controls_shadow.setColor(QColor(0, 0, 0, 40))
        controls_scroll.setGraphicsEffect(controls_shadow)
        
        # Title for controls (macanism-style professional)
        controls_title = QLabel("⚙️ Mechanism Controls")
        controls_title.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #212529;
                padding: 12px;
                background-color: #f8f9fa;
                border-radius: 8px;
                border: none;
            }
        """)
        controls_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        controls_layout.addWidget(controls_title)
        
        # Mechanism selector
        self.mechanism_selector = MechanismSelector()
        controls_layout.addWidget(self.mechanism_selector)
        
        # Parameter controls with enhanced styling
        params_container = QFrame()
        params_container.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border-radius: 8px;
                border: none;
            }
        """)
        params_layout = QVBoxLayout(params_container)
        params_layout.setContentsMargins(8, 8, 8, 8)
        
        self.parameter_controls = ParameterControls()
        params_layout.addWidget(self.parameter_controls)
        controls_layout.addWidget(params_container)
        
        # Visualization controls
        self.viz_controls = VisualizationControls()
        controls_layout.addWidget(self.viz_controls)
        
        controls_layout.addStretch()
        
        # Set up scroll area
        controls_scroll.setWidget(controls_panel)
        splitter.addWidget(controls_scroll)
        
        # Set initial splitter proportions (70% visualization, 30% controls) for better right panel space
        splitter.setSizes([700, 400])
        
        layout.addWidget(splitter)
        
    def connect_signals(self):
        """Connect UI signals to mechanism service"""
        # Mechanism selection
        self.mechanism_selector.mechanismChanged.connect(self._on_mechanism_type_changed)
        
        # Parameter changes from UI controls
        self.parameter_controls.parametersChanged.connect(self._on_parameters_changed)
        
        # Mechanism service signals
        self.mechanism_service.mechanismUpdated.connect(self._on_mechanism_updated)
        self.mechanism_service.parameterValidated.connect(self._on_parameter_validated)
        self.mechanism_service.constraintsValidated.connect(self._on_constraints_validated)
        
        # Visualization control signals - simplified
        self.viz_controls.labelsToggled.connect(self.visualization.set_show_labels)
        self.viz_controls.gridToggled.connect(self.visualization.set_show_grid)
        self.viz_controls.animationToggled.connect(self._on_animation_toggled)
        
        # Interactive mechanism signals
        self.visualization.parameterChanged.connect(self._on_interactive_parameter_changed)
        
    def _create_initial_mechanism(self):
        """Create initial four-bar linkage mechanism"""
        print(f"Creating initial mechanism with ID: {self.current_mechanism_id}")
        success = self.mechanism_service.create_mechanism(
            mechanism_type="four_bar_linkage",
            mechanism_id=self.current_mechanism_id
        )
        
        if success:
            print("Initial mechanism created successfully")
            self._setup_parameter_controls()
            self._start_animation_timer()
            print("Initial mechanism setup completed")
        else:
            print("Failed to create initial mechanism")
    
    def _on_mechanism_type_changed(self, mechanism_type: str):
        """Handle mechanism type change from selector"""
        # Remove current mechanism
        self.mechanism_service.remove_mechanism(self.current_mechanism_id)
        
        # Create new mechanism
        success = self.mechanism_service.create_mechanism(
            mechanism_type=mechanism_type,
            mechanism_id=self.current_mechanism_id
        )
        
        if success:
            self._setup_parameter_controls()
            print(f"Created new mechanism: {mechanism_type}")
        else:
            print(f"Failed to create mechanism: {mechanism_type}")
    
    def _setup_parameter_controls(self):
        """Setup parameter controls based on current mechanism"""
        param_info = self.mechanism_service.get_parameter_info()
        print(f"PlaygroundPanel: Setting up parameter controls, got param_info: {param_info is not None}")
        if param_info:
            print(f"PlaygroundPanel: Parameter count: {len(param_info)}")
            # Configure parameter controls with mechanism-specific parameters
            self.parameter_controls.configure_for_mechanism(param_info)
        else:
            print("PlaygroundPanel: No parameter info available")
    
    def _on_parameters_changed(self, parameters: Dict[str, float]):
        """Handle parameter changes from UI controls"""
        for param_name, value in parameters.items():
            success = self.mechanism_service.update_parameter(param_name, value)
            if not success:
                print(f"Failed to update parameter {param_name} = {value}")
    
    def _on_mechanism_updated(self, state_data: Dict, mechanism_id: str):
        """Handle mechanism state updates from service"""
        if mechanism_id == self.current_mechanism_id:
            # Update visualization with new state data
            self.visualization.update_from_mechanism_state(state_data)
    
    def _on_parameter_validated(self, param_name: str, is_valid: bool, error_msg: str):
        """Handle parameter validation results"""
        if not is_valid:
            print(f"Parameter validation error for {param_name}: {error_msg}")
            # Could update UI to show validation error
    
    def _on_constraints_validated(self, is_valid: bool, errors: list):
        """Handle constraint validation results"""
        if not is_valid:
            print(f"Constraint validation errors: {errors}")
            # Could update UI to show constraint violations
    
    def _on_animation_toggled(self, enabled: bool):
        """Handle animation toggle"""
        self.animation_running = enabled
        if enabled:
            self._start_animation_timer()
        else:
            self._stop_animation_timer()
    
    def _on_interactive_parameter_changed(self, param_name: str, value: float):
        """Handle parameter changes from direct interaction"""
        # Update mechanism service with interactive parameter change
        success = self.mechanism_service.update_parameter(param_name, value)
        if success:
            # Update parameter controls to reflect the change
            self.parameter_controls.update_parameter_value(param_name, value)
        else:
            print(f"Failed to update interactive parameter {param_name} = {value}")
    
    def _start_animation_timer(self):
        """Start animation timer"""
        if not self.animation_timer.isActive():
            self.animation_timer.start(33)  # ~30 FPS for better performance
    
    def _stop_animation_timer(self):
        """Stop animation timer"""
        if self.animation_timer.isActive():
            self.animation_timer.stop()
    
    def _update_animation(self):
        """Update animation frame"""
        if not self.animation_running:
            return
        
        # Update animation angle with faster increment for visible motion
        speed_multiplier = self.mechanism_service.get_animation_speed()
        self.animation_angle += 0.1 * speed_multiplier  # Doubled increment for better visibility
        
        # Update mechanism with new input angle
        self.mechanism_service.update_input_angle(self.animation_angle)
        
    def on_tab_activated(self):
        """Called when this tab becomes active"""
        # Resume animation if it was enabled
        if self.viz_controls.animate.isChecked():
            self._start_animation_timer()
            
        # Apply current visualization settings
        self.visualization.set_show_labels(self.viz_controls.show_labels.isChecked())
        self.visualization.set_show_grid(self.viz_controls.show_grid.isChecked())
        
        # Update unified renderer settings
        if hasattr(self.visualization, 'update_unified_renderer_settings'):
            self.visualization.update_unified_renderer_settings()
    
    def on_tab_deactivated(self):
        """Called when this tab becomes inactive"""
        # Pause animation to save CPU
        self._stop_animation_timer()
    
    def set_mechanism(self, mechanism_data: Dict):
        """Set mechanism data for the playground (compatibility method)"""
        if not mechanism_data:
            return
            
        mechanism_type = mechanism_data.get('type', 'four_bar_linkage')
        
        # Remove current mechanism if exists
        if self.current_mechanism_id:
            self.mechanism_service.remove_mechanism(self.current_mechanism_id)
        
        # Create new mechanism with provided data
        parameters = mechanism_data.get('parameters', {})
        success = self.mechanism_service.create_mechanism(
            mechanism_type=mechanism_type,
            mechanism_id=self.current_mechanism_id,
            parameters=parameters
        )
        
        if success:
            self._setup_parameter_controls()
            print(f"Set mechanism in playground: {mechanism_type}")
        else:
            print(f"Failed to set mechanism in playground: {mechanism_type}")