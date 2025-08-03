"""
Mechanism Foundry Tab - A modern, interactive educational workshop for mechanisms.

This tab provides an advanced, unified environment for learning about mechanical systems,
inspired by professional HCI and physics simulation principles. It replaces the previous
hierarchical navigation with a direct, immersive workshop experience.
"""

import time
import json
import math
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QTabWidget,
    QGroupBox, QLabel, QPushButton, QComboBox, QSlider, QSpinBox,
    QTextEdit, QProgressBar, QFrame, QScrollArea, QCheckBox,
    QButtonGroup, QRadioButton, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve, QObject
from PyQt6.QtGui import QIcon, QFont, QPixmap, QPainter, QColor, QPen, QBrush

# Base classes removed - using standard QWidget inheritance like other tabs
from .hci.parametric_controls import (
    ParameterState, ParameterType, ParameterConstraint, ParametricControlPanel
)
from .hci.physics_interaction import PhysicsInteractionLayer
# Removed MechanismService dependency - using direct implementation

class MockMechanismService(QObject):
    """Simple mock service to replace MechanismService dependency"""
    mechanismUpdated = pyqtSignal(dict, str)  # Mock signal

    def __init__(self):
        super().__init__()

    def create_mechanism(self, mechanism_type: str, mechanism_id: str):
        pass

    def get_parameter_info(self, mechanism_id: str):
        return None

    def get_educational_analysis(self, mechanism_id: str):
        return None

    def get_animation_speed(self, mechanism_id: str):
        return 1.0

    def update_input_angle(self, mechanism_id: str, angle: float):
        pass

    def update_parameter(self, mechanism_id: str, param_name: str, value):
        pass


class LearningMode(Enum):
    """Different learning modes for the foundry"""
    GUIDED_TUTORIAL = "guided_tutorial"
    FREE_EXPLORATION = "free_exploration"
    DESIGN_CHALLENGE = "design_challenge"


@dataclass
class TutorialStep:
    """Single step in a guided tutorial"""
    id: str
    title: str
    description: str
    target_parameter: Optional[str]
    target_value: Optional[float]
    success_criteria: Dict[str, Any]
    hints: List[str]


class TutorialOverlay(QWidget):
    """Professional tutorial overlay with step-by-step guidance"""

    tutorialCompleted = pyqtSignal(str)  # tutorial_id
    stepCompleted = pyqtSignal(str, int)  # tutorial_id, step_index

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 150);")
        self.current_tutorial: Optional[str] = None
        self.current_step: int = 0
        self.tutorial_steps: List[TutorialStep] = []
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tutorial_panel = QFrame()
        self.tutorial_panel.setMaximumWidth(400)
        self.tutorial_panel.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 12px;
                padding: 20px;
                border: 2px solid #0d6efd;
            }
        """)
        panel_layout = QVBoxLayout(self.tutorial_panel)
        self.title_label = QLabel()
        self.title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #0d6efd; margin-bottom: 12px;")
        self.description_label = QLabel()
        self.description_label.setWordWrap(True)
        self.description_label.setStyleSheet("font-size: 12px; line-height: 1.4; color: #495057; margin-bottom: 16px;")
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar { border: 2px solid #dee2e6; border-radius: 6px; text-align: center; background-color: #f8f9fa; }
            QProgressBar::chunk { background-color: #0d6efd; border-radius: 4px; }
        """)
        button_layout = QHBoxLayout()
        self.prev_button = QPushButton("← Previous")
        self.next_button = QPushButton("Next →")
        self.skip_button = QPushButton("Skip Tutorial")
        for btn in [self.prev_button, self.next_button, self.skip_button]:
            btn.setStyleSheet("""
                QPushButton { background-color: #0d6efd; color: white; border: none; border-radius: 6px; padding: 8px 16px; font-weight: 500; }
                QPushButton:hover { background-color: #0b5ed7; }
                QPushButton:disabled { background-color: #6c757d; }
            """)
        button_layout.addWidget(self.prev_button)
        button_layout.addWidget(self.next_button)
        button_layout.addStretch()
        button_layout.addWidget(self.skip_button)
        panel_layout.addWidget(self.title_label)
        panel_layout.addWidget(self.description_label)
        panel_layout.addWidget(self.progress_bar)
        panel_layout.addLayout(button_layout)
        layout.addWidget(self.tutorial_panel)
        self.prev_button.clicked.connect(self.go_to_previous_step)
        self.next_button.clicked.connect(self.go_to_next_step)
        self.skip_button.clicked.connect(self.skip_tutorial)
        self.hide()

    def start_tutorial(self, tutorial_id: str, steps: List[TutorialStep]):
        self.current_tutorial = tutorial_id
        self.tutorial_steps = steps
        self.current_step = 0
        self.progress_bar.setMaximum(len(steps))
        self.update_step_display()
        self.show()

    def update_step_display(self):
        if not self.tutorial_steps or self.current_step >= len(self.tutorial_steps): return
        step = self.tutorial_steps[self.current_step]
        self.title_label.setText(f"Step {self.current_step + 1}: {step.title}")
        self.description_label.setText(step.description)
        self.progress_bar.setValue(self.current_step + 1)
        self.prev_button.setEnabled(self.current_step > 0)
        self.next_button.setEnabled(self.current_step < len(self.tutorial_steps) - 1)
        self.next_button.setText("Complete Tutorial" if self.current_step == len(self.tutorial_steps) - 1 else "Next →")

    def go_to_previous_step(self):
        if self.current_step > 0:
            self.current_step -= 1
            self.update_step_display()

    def go_to_next_step(self):
        if self.current_step < len(self.tutorial_steps) - 1:
            self.current_step += 1
            self.update_step_display()
            self.stepCompleted.emit(self.current_tutorial, self.current_step - 1)
        else:
            self.complete_tutorial()

    def complete_tutorial(self):
        if self.current_tutorial:
            self.tutorialCompleted.emit(self.current_tutorial)
            self.hide()

    def skip_tutorial(self):
        self.hide()


class VisualizationControls(QGroupBox):
    """Controls for visualization options"""
    labelsToggled = pyqtSignal(bool)
    gridToggled = pyqtSignal(bool)
    animationToggled = pyqtSignal(bool)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__("🎛️ Visualization Controls", parent)
        self.setup_ui()

    def setup_ui(self):
        self.setStyleSheet("""
            QGroupBox { font-size: 14px; font-weight: bold; color: #212529; border: none; border-radius: 12px; margin-top: 12px; padding-top: 12px; background-color: #ffffff; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 8px 0 8px; background-color: #ffffff; color: #0d6efd; }
            QCheckBox { font-size: 13px; color: #212529; padding: 6px; }
            QCheckBox::indicator { width: 18px; height: 18px; border-radius: 4px; border: none; background-color: #e9ecef; }
            QCheckBox::indicator:checked { background-color: #0d6efd; border: none; image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTAiIGhlaWdodD0iOCIgdmlld0JveD0iMCAwIDEwIDgiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxwYXRoIGQ9Ik04LjUgMUwzLjUgNkwxLjUgNCIgc3Ryb2tlPSJ3aGl0ZSIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiLz4KPC9zdmc+); }
            QCheckBox::indicator:hover { background-color: #dee2e6; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 20, 16, 16)
        layout.setSpacing(8)
        self.show_labels = QCheckBox("📋 Component Labels")
        self.show_grid = QCheckBox("📐 Grid")
        self.animate = QCheckBox("▶️ Animation")
        self.animate.setChecked(True)
        self.show_labels.setChecked(True)
        self.show_grid.setChecked(True)
        layout.addWidget(self.show_labels)
        layout.addWidget(self.show_grid)
        layout.addWidget(self.animate)
        layout.addStretch()
        self.show_labels.toggled.connect(self.labelsToggled.emit)
        self.show_grid.toggled.connect(self.gridToggled.emit)
        self.animate.toggled.connect(self.animationToggled.emit)


class MechanismSelector(QGroupBox):
    """Mechanism selection control"""
    mechanismChanged = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__("🔧 Mechanism Type", parent)
        self.setup_ui()

    def setup_ui(self):
        self.setStyleSheet("""
            QGroupBox { font-size: 14px; font-weight: bold; color: #212529; border: none; border-radius: 12px; margin-top: 12px; padding-top: 12px; background-color: #ffffff; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 8px 0 8px; background-color: #ffffff; color: #0d6efd; }
            QComboBox { font-size: 13px; color: #212529; padding: 8px 12px; border: 2px solid #dee2e6; border-radius: 6px; background-color: #ffffff; }
            QComboBox:hover { border-color: #0d6efd; }
            QComboBox::drop-down { border: none; width: 20px; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 20, 16, 16)
        self.mechanism_combo = QComboBox()
        self.mechanism_combo.addItem("Four-Bar Linkage", "four_bar_linkage")
        self.mechanism_combo.addItem("Slider-Crank", "slider_crank")
        self.mechanism_combo.addItem("Gear Train", "gear_train")
        self.mechanism_combo.addItem("Cam-Follower", "cam_follower")
        self.mechanism_combo.addItem("Gear Train", "gear_train")
        self.mechanism_combo.addItem("Scotch Yoke", "scotch_yoke")
        self.mechanism_combo.addItem("Spring System", "spring_system")
        self.mechanism_combo.currentIndexChanged.connect(self._on_mechanism_changed)
        layout.addWidget(self.mechanism_combo)

    def _on_mechanism_changed(self, index: int):
        mechanism_type = self.mechanism_combo.itemData(index)
        self.mechanismChanged.emit(mechanism_type)


class EducationalAnalysisPanel(QGroupBox):
    """Educational analysis display panel - macanism style"""
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__("📊 Analysis & Education", parent)
        self.setup_ui()

    def setup_ui(self):
        self.setStyleSheet("""
            QGroupBox { font-size: 14px; font-weight: bold; color: #212529; border: none; border-radius: 12px; margin-top: 12px; padding-top: 12px; background-color: #ffffff; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 8px 0 8px; background-color: #ffffff; color: #0d6efd; }
            QTextEdit { font-size: 12px; color: #495057; background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 6px; padding: 8px; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 20, 16, 16)
        layout.setSpacing(8)
        self.analysis_text = QTextEdit()
        self.analysis_text.setMaximumHeight(200)
        self.analysis_text.setReadOnly(True)
        font = QFont("Monaco", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.analysis_text.setFont(font)
        self.analysis_text.setHtml("<div style='font-family: system-ui; font-size: 12px; color: #6c757d;'><h4 style='color: #0d6efd; margin: 0 0 8px 0;'>🔧 Mechanism Analysis</h4><p style='margin: 4px 0;'>Select a mechanism to view detailed analysis...</p></div>")
        layout.addWidget(self.analysis_text)

    def update_analysis(self, educational_data: Dict):
        if not educational_data: return
        html_content = f"""<div style='font-family: system-ui; font-size: 12px;'><h4 style='color: #0d6efd; margin: 0 0 8px 0;'>🔧 {educational_data.get('current_state', {}).get('mechanism_name', 'Mechanism')} Analysis</h4>"""
        if 'key_concepts' in educational_data:
            html_content += "<h5 style='color: #6f42c1; margin: 8px 0 4px 0;'>📚 Key Concepts:</h5><ul style='margin: 4px 0 8px 16px;'>"
            for concept in educational_data['key_concepts'][:3]: html_content += f"<li style='margin: 2px 0;'>{concept}</li>"
            html_content += "</ul>"
        if 'grashof_analysis' in educational_data:
            grashof = educational_data['grashof_analysis']
            html_content += f"<h5 style='color: #dc3545; margin: 8px 0 4px 0;'>⚙️ Grashof Analysis:</h5><p style='margin: 2px 0;'><strong>Type:</strong> {grashof.get('mechanism_type', 'N/A')}</p><p style='margin: 2px 0;'><strong>Ratio:</strong> {grashof.get('grashof_ratio', 'N/A')}</p>"
        if 'current_state' in educational_data:
            state = educational_data['current_state']
            html_content += f"<h5 style='color: #17a2b8; margin: 8px 0 4px 0;'>📊 Current State:</h5><p style='margin: 2px 0;'><strong>Valid:</strong> {'✅' if state.get('is_valid', False) else '❌'}</p><p style='margin: 2px 0;'><strong>Params:</strong> {state.get('parameter_count', 0)}</p>"
        html_content += "</div>"
        self.analysis_text.setHtml(html_content)


class MechanismFoundryTab(QWidget):
    """
    The unified, interactive Mechanism Foundry. This tab provides a single, immersive
    workshop for exploring, analyzing, and learning about various mechanisms.
    """
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        # Initialize services and configuration
        self.mechanism_service = MockMechanismService()
        self.mechanism_id = "foundry_mechanism"
        self.current_tutorial: Optional[str] = None
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.drive_animation)
        self.animation_angle = 0.0

        # Connect signals
        self.mechanism_service.mechanismUpdated.connect(self.on_mechanism_state_updated)

        # Setup UI components
        self.setup_mechanism_specific_components()

    def on_educational_data_updated(self, data: Dict, mechanism_id: str):
        if mechanism_id == self.mechanism_id and self.analysis_panel:
            self.analysis_panel.update_analysis(data)

    def setup_mechanism_specific_components(self):
        self.create_foundry_layout()
        self.connect_component_signals()
        self.setup_default_mechanism()
        self.animation_timer.start(33)  # ~30 FPS

    def create_foundry_layout(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet("QSplitter::handle { background-color: #0d6efd; width: 3px; } QSplitter::handle:hover { background-color: #0b5ed7; }")

        # Left side: Visualization
        viz_container = QFrame()
        viz_container.setStyleSheet("background-color: #fafafa; border-radius: 12px; border: none;")
        viz_layout = QVBoxLayout(viz_container)
        viz_layout.setContentsMargins(4, 4, 4, 4)
        viz_shadow = QGraphicsDropShadowEffect(blurRadius=20, xOffset=0, yOffset=2, color=QColor(0, 0, 0, 40))
        viz_container.setGraphicsEffect(viz_shadow)
        self.visualization = PhysicsInteractionLayer()
        viz_layout.addWidget(self.visualization)
        splitter.addWidget(viz_container)

        # Right side: Controls
        controls_scroll = QScrollArea()
        controls_scroll.setWidgetResizable(True)
        controls_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        controls_scroll.setStyleSheet("QScrollArea { border: none; background-color: #ffffff; border-radius: 12px; }")
        controls_shadow = QGraphicsDropShadowEffect(blurRadius=20, xOffset=0, yOffset=2, color=QColor(0, 0, 0, 40))
        controls_scroll.setGraphicsEffect(controls_shadow)

        controls_panel = QWidget()
        controls_layout = QVBoxLayout(controls_panel)
        controls_layout.setContentsMargins(12, 12, 12, 12)
        controls_layout.setSpacing(12)

        title = QLabel("⚙️ Mechanism Workshop")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #212529; padding: 12px; background-color: #f8f9fa; border-radius: 8px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        controls_layout.addWidget(title)

        self.mechanism_selector = MechanismSelector()
        self.parametric_controls = ParametricControlPanel()
        self.viz_controls = VisualizationControls()
        self.analysis_panel = EducationalAnalysisPanel()

        controls_layout.addWidget(self.mechanism_selector)
        controls_layout.addWidget(self.parametric_controls)
        controls_layout.addWidget(self.viz_controls)
        controls_layout.addWidget(self.analysis_panel)
        controls_layout.addStretch()

        controls_scroll.setWidget(controls_panel)
        splitter.addWidget(controls_scroll)

        splitter.setSizes([700, 400])
        layout.addWidget(splitter)

    def connect_component_signals(self):
        self.mechanism_selector.mechanismChanged.connect(self.on_mechanism_type_changed)
        if self.parametric_controls:
            self.parametric_controls.parameterChanged.connect(self.handle_parameter_change)
        if self.visualization:
            self.visualization.componentDragged.connect(self.handle_component_dragged)
        if self.viz_controls:
            self.viz_controls.animationToggled.connect(self.on_animation_toggled)

    def setup_default_mechanism(self):
        self.on_mechanism_type_changed("four_bar_linkage")

    def on_mechanism_type_changed(self, mechanism_type: str):
        self.mechanism_service.create_mechanism(mechanism_type=mechanism_type, mechanism_id=self.mechanism_id)
        param_info = self.mechanism_service.get_parameter_info(self.mechanism_id)
        if self.parametric_controls and param_info:
            self.parametric_controls.configure_for_mechanism(param_info)
        educational_data = self.mechanism_service.get_educational_analysis(self.mechanism_id)
        if educational_data:
            self.on_educational_data_updated(educational_data, self.mechanism_id)

    def drive_animation(self):
        if not self.animation_timer.isActive(): return
        speed = self.mechanism_service.get_animation_speed(self.mechanism_id)
        self.animation_angle = (self.animation_angle + 0.05 * speed) % (2 * math.pi)
        self.mechanism_service.update_input_angle(self.mechanism_id, self.animation_angle)

    def on_mechanism_state_updated(self, state: Dict[str, Any], mechanism_id: str):
        if mechanism_id != self.mechanism_id: return
        if self.visualization and hasattr(self.visualization, 'update_state'):
            self.visualization.update_state(state)
            self.visualization.update()

    def on_educational_data_updated(self, data: Dict, mechanism_id: str):
        if mechanism_id == self.mechanism_id and self.analysis_panel:
            self.analysis_panel.update_analysis(data)

    def on_animation_toggled(self, is_running: bool):
        if is_running: self.animation_timer.start()
        else: self.animation_timer.stop()

    def handle_parameter_change(self, param_name: str, value: float):
        self.mechanism_service.update_parameter(self.mechanism_id, param_name, value)

    def handle_component_dragged(self, component_id: str, position, physics_data: Dict):
        self.mechanism_service.update_parameter(self.mechanism_id, f"{component_id}_position", (position.x(), position.y()))

    def on_mechanism_changed(self, mechanism_data: Dict[str, Any]):
        self.on_mechanism_type_changed(mechanism_data.get('id', 'four_bar_linkage'))

    def handle_component_grabbed(self, component_id: str, position):
        """Handle component interaction in educational context"""
        # This can be used for contextual hints in tutorial mode
        pass

    def handle_component_released(self, component_id: str, position):
        """Handle component release in workshop context"""
        # Could trigger analysis updates or tutorial step checks
        pass

    def handle_configuration_change(self, config: Dict[str, float]):
        """Handle configuration changes in workshop context"""
        # Placeholder for handling configuration changes
        pass
