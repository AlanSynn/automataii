"""
Enhanced Mechanism Control Panel - Physics Integration

Enhanced UI panel for mechanism design with integrated physics validation
controls following the strategic architecture for manufacturing-grade
mechanism design.

Features:
- Physics validation controls with status indicators
- Event-driven architecture integration
- Real-time physics feedback during parametric editing
- Educational visualization controls
- Manufacturing validation workflow
"""

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QBrush, QColor, QPainter, QPen, QMovie
from PyQt6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSlider,
    QStyle,
    QVBoxLayout,
    QWidget,
    QFrame,
    QProgressBar,
    QToolTip
)

from ....models.physics import (
    ValidationState, 
    ValidationStatusIndicatorState, 
    PhysicsVisualizationSettings
)


class ValidationStatusIndicator(QWidget):
    """
    Custom widget for displaying physics validation status.
    
    Shows colored circular indicator with status message and optional spinner
    for validation in progress.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(120, 30)
        
        # State
        self._state = ValidationStatusIndicatorState.not_validated()
        
        # Spinner for validating state
        self._spinner_angle = 0
        self._spinner_timer = QTimer()
        self._spinner_timer.timeout.connect(self._update_spinner)
        
    def set_state(self, state: ValidationStatusIndicatorState):
        """Update the indicator state"""
        self._state = state
        
        # Manage spinner
        if state.show_spinner:
            self._spinner_timer.start(50)  # 20fps spinner
        else:
            self._spinner_timer.stop()
            self._spinner_angle = 0
        
        # Update tooltip
        if state.tooltip:
            self.setToolTip(state.tooltip)
        
        self.update()  # Trigger repaint
    
    def _update_spinner(self):
        """Update spinner animation"""
        self._spinner_angle = (self._spinner_angle + 15) % 360
        self.update()
    
    def paintEvent(self, event):
        """Custom paint for status indicator"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw indicator circle
        circle_size = 16
        circle_x = 5
        circle_y = (self.height() - circle_size) // 2
        
        color = QColor(self._state.color)
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(color.darker(150), 2))
        
        if self._state.show_spinner:
            # Draw spinning arc for validating state
            painter.drawArc(circle_x, circle_y, circle_size, circle_size, 
                          self._spinner_angle * 16, 120 * 16)
        else:
            # Draw solid circle for other states
            painter.drawEllipse(circle_x, circle_y, circle_size, circle_size)
        
        # Draw status text
        painter.setPen(QPen(QColor("#333333")))
        text_rect = self.rect().adjusted(circle_size + 10, 0, 0, 0)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, 
                        self._state.message)


class PhysicsVisualizationControls(QWidget):
    """
    Controls for physics visualization options in 2D scene.
    
    Provides checkboxes and settings for educational visualization
    of forces, constraints, and motion paths.
    """
    
    # Signals for visualization changes
    visualization_changed = pyqtSignal(PhysicsVisualizationSettings)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._settings = PhysicsVisualizationSettings()
        self._setup_ui()
        self._connect_signals()
        
        # Initially disabled until validation succeeds
        self.setEnabled(False)
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # Force vectors checkbox
        self.force_vectors_cb = QCheckBox("Show Force Vectors")
        self.force_vectors_cb.setToolTip("Display force vectors at each joint for educational visualization")
        layout.addWidget(self.force_vectors_cb)
        
        # Force scale slider
        force_scale_layout = QHBoxLayout()
        force_scale_layout.addWidget(QLabel("Force Scale:"))
        self.force_scale_slider = QSlider(Qt.Orientation.Horizontal)
        self.force_scale_slider.setRange(1, 50)  # 0.1x to 5.0x scale
        self.force_scale_slider.setValue(10)  # Default 1.0x
        self.force_scale_slider.setToolTip("Adjust the scale of force vectors")
        self.force_scale_label = QLabel("1.0x")
        force_scale_layout.addWidget(self.force_scale_slider)
        force_scale_layout.addWidget(self.force_scale_label)
        layout.addLayout(force_scale_layout)
        
        # Constraint violations checkbox
        self.constraint_violations_cb = QCheckBox("Highlight Constraint Violations")
        self.constraint_violations_cb.setToolTip("Highlight joints and links with constraint violations")
        self.constraint_violations_cb.setChecked(True)  # Default enabled
        layout.addWidget(self.constraint_violations_cb)
        
        # Motion paths checkbox
        self.motion_paths_cb = QCheckBox("Show Motion Paths")
        self.motion_paths_cb.setToolTip("Display animated motion paths of key points")
        layout.addWidget(self.motion_paths_cb)
        
        # Safety factors checkbox
        self.safety_factors_cb = QCheckBox("Show Safety Factors")
        self.safety_factors_cb.setToolTip("Display color-coded safety factors for each component")
        layout.addWidget(self.safety_factors_cb)
    
    def _connect_signals(self):
        """Connect checkbox signals to update settings"""
        self.force_vectors_cb.toggled.connect(self._update_settings)
        self.force_scale_slider.valueChanged.connect(self._on_force_scale_changed)
        self.constraint_violations_cb.toggled.connect(self._update_settings)
        self.motion_paths_cb.toggled.connect(self._update_settings)
        self.safety_factors_cb.toggled.connect(self._update_settings)

    
    def _on_force_scale_changed(self, value):
        """Handle force scale slider changes"""
        scale_factor = value / 10.0  # Convert to 0.1x - 5.0x range
        self.force_scale_label.setText(f"{scale_factor:.1f}x")
        self._update_settings()
    
    def _update_settings(self):
        """Update settings and emit change signal"""
        self._settings.show_force_vectors = self.force_vectors_cb.isChecked()
        self._settings.show_constraint_violations = self.constraint_violations_cb.isChecked()
        self._settings.show_motion_paths = self.motion_paths_cb.isChecked()
        self._settings.show_safety_factors = self.safety_factors_cb.isChecked()
        
        # Add force scale setting
        if hasattr(self, 'force_scale_slider'):
            self._settings.force_scale = self.force_scale_slider.value() / 10.0
        
        self.visualization_changed.emit(self._settings)
    
    def set_enabled_for_validation_state(self, state: ValidationState):
        """Enable/disable controls based on validation state"""
        is_validated = state in [ValidationState.SUCCESS, ValidationState.WARNING]
        self.setEnabled(is_validated)
        
        if not is_validated:
            # Reset all checkboxes when disabled
            self.force_vectors_cb.setChecked(False)
            self.motion_paths_cb.setChecked(False)
            self.safety_factors_cb.setChecked(False)
            # Keep constraint violations checked for when validation succeeds
    
    def get_settings(self) -> PhysicsVisualizationSettings:
        """Get current visualization settings"""
        return self._settings


class EnhancedMechanismControlPanel(QWidget):
    """
    Enhanced mechanism control panel with physics validation integration.
    
    Implements Gemini's strategic architecture for physics-validated
    mechanism design with clear workflow and user feedback.
    
    Workflow:
    1. Parts - Load and select character parts
    2. Generation - Generate mechanism recommendations  
    3. Animation - Test 2D animation behavior
    4. Physics - Validate physics and forces (NEW)
    5. Export - Export manufacturing blueprints
    6. Debug - Development and troubleshooting tools
    """
    
    # Existing signals
    recommendation_requested = pyqtSignal()
    play_clicked = pyqtSignal()
    stop_clicked = pyqtSignal()
    reset_clicked = pyqtSignal()
    parametric_mode_toggled = pyqtSignal(bool)
    export_blueprint_requested = pyqtSignal()
    part_selected = pyqtSignal(str)
    part_toggled = pyqtSignal(str)
    mechanism_toggled = pyqtSignal(str)
    debug_mode_toggled = pyqtSignal(bool)
    
    # New physics validation signals
    validate_physics_requested = pyqtSignal()
    physics_visualization_changed = pyqtSignal(PhysicsVisualizationSettings)
    live_physics_feedback_toggled = pyqtSignal(bool)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.state = parent.state if parent else None
        
        # Physics validation state
        self._validation_state = ValidationState.NOT_VALIDATED
        self._physics_validation_enabled = False
        
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        """Setup the enhanced UI with physics validation controls"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFixedWidth(320)  # Slightly wider for new controls
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        control_panel = QWidget()
        panel_layout = QVBoxLayout(control_panel)
        panel_layout.setContentsMargins(10, 10, 10, 10)
        panel_layout.setSpacing(15)

        # Group style template
        group_style = """
            QGroupBox {
                background-color: #ffffff;
                border: 1px solid #e3e9f0;
                border-radius: 9px;
                padding: 18px;
                margin-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 10px;
                margin-left: 15px;
                font-size: 12pt;
                font-weight: bold;
                color: #5c85d6;
                background-color: #ffffff;
            }
        """

        # 1. Parts List Group (unchanged)
        parts_group = QGroupBox("1. Parts for Mechanisms")
        parts_group.setStyleSheet(group_style)
        parts_layout = QVBoxLayout(parts_group)
        
        self.parts_list = QListWidget()
        self.parts_list.setToolTip("Click to toggle mechanism generation for a part")
        self.parts_list.setMinimumHeight(180)
        self.parts_list.setStyleSheet("""
            QListWidget {
                background-color: white;
                border: 1px solid #dee2e6;
                border-radius: 6px;
                padding: 4px;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 8px 12px;
                margin: 2px;
                border-radius: 4px;
                border: 1px solid transparent;
            }
            QListWidget::item:selected {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #0078D7, stop: 1 #005a9e);
                color: white;
                border: 1px solid #004578;
            }
            QListWidget::item:hover {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
            }
        """)
        parts_layout.addWidget(self.parts_list)
        panel_layout.addWidget(parts_group)

        # 2. Mechanism Generation Group (unchanged)
        generation_group = QGroupBox("2. Mechanism Generation")
        generation_group.setStyleSheet(group_style)
        generation_layout = QVBoxLayout(generation_group)

        self.recommendation_btn = QPushButton("Get Mechanism")
        self.recommendation_btn.setEnabled(False)
        self.recommendation_btn.setToolTip("Get mechanism recommendations for the selected part")
        self.recommendation_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60; color: white; border: none;
                padding: 8px 16px; border-radius: 4px; font-size: 13px;
            }
            QPushButton:hover { background-color: #229954; }
            QPushButton:disabled { background-color: #bdc3c7; color: #7f8c8d; }
        """)
        generation_layout.addWidget(self.recommendation_btn)

        self.parametric_mode_btn = QPushButton("Parametric Edit")
        self.parametric_mode_btn.setToolTip("Enable interactive parameter editing")
        self.parametric_mode_btn.setEnabled(False)
        self.parametric_mode_btn.setCheckable(True)
        self.parametric_mode_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db; color: white; border: none;
                padding: 8px 16px; border-radius: 4px; font-size: 13px;
            }
            QPushButton:hover { background-color: #2980b9; }
            QPushButton:checked { background-color: #e74c3c; }
            QPushButton:disabled { background-color: #bdc3c7; color: #7f8c8d; }
        """)
        generation_layout.addWidget(self.parametric_mode_btn)
        panel_layout.addWidget(generation_group)

        # 3. Animation Group (unchanged)
        animation_group = QGroupBox("3. Animation")
        animation_group.setStyleSheet(group_style)
        animation_layout = QVBoxLayout(animation_group)

        style = self.style()
        anim_button_layout = QHBoxLayout()
        anim_button_layout.setSpacing(12)

        self.play_btn = QPushButton(style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay), "")
        self.play_btn.setToolTip("Play Animation")
        self.play_btn.setEnabled(False)

        self.stop_btn = QPushButton(style.standardIcon(QStyle.StandardPixmap.SP_MediaStop), "")
        self.stop_btn.setToolTip("Stop Animation")
        self.stop_btn.setEnabled(False)

        self.reset_btn = QPushButton(style.standardIcon(QStyle.StandardPixmap.SP_BrowserReload), "")
        self.reset_btn.setToolTip("Reset Animation")
        self.reset_btn.setEnabled(False)

        anim_button_layout.addStretch()
        anim_button_layout.addWidget(self.play_btn)
        anim_button_layout.addWidget(self.stop_btn)
        anim_button_layout.addWidget(self.reset_btn)
        anim_button_layout.addStretch()

        animation_layout.addLayout(anim_button_layout)
        panel_layout.addWidget(animation_group)

        # 4. Physics Validation Group (Hidden for now)
        physics_group = QGroupBox("4. Physics Validation")
        physics_group.setVisible(False)  # Hide physics validation UI
        physics_group.setStyleSheet(group_style)
        physics_layout = QVBoxLayout(physics_group)

        # Physics validation status and button
        status_layout = QHBoxLayout()
        status_layout.setSpacing(10)
        
        status_label = QLabel("Status:")
        status_label.setStyleSheet("font-weight: bold;")
        status_layout.addWidget(status_label)
        
        self.validation_status = ValidationStatusIndicator()
        status_layout.addWidget(self.validation_status)
        
        status_layout.addStretch()
        physics_layout.addLayout(status_layout)

        # Validate physics button
        self.validate_physics_btn = QPushButton("Run Physics Validation")
        self.validate_physics_btn.setEnabled(False)
        self.validate_physics_btn.setToolTip("Validate mechanism physics for manufacturing safety")
        self.validate_physics_btn.setStyleSheet("""
            QPushButton {
                background-color: #e67e22; color: white; border: none;
                padding: 10px 16px; border-radius: 4px; font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #d35400; }
            QPushButton:disabled { background-color: #bdc3c7; color: #7f8c8d; }
        """)
        physics_layout.addWidget(self.validate_physics_btn)

        # Separator line
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setStyleSheet("color: #dee2e6;")
        physics_layout.addWidget(separator)

        # Physics visualization controls
        viz_label = QLabel("Visualization:")
        viz_label.setStyleSheet("font-weight: bold; margin-top: 5px;")
        physics_layout.addWidget(viz_label)
        
        self.physics_viz_controls = PhysicsVisualizationControls()
        physics_layout.addWidget(self.physics_viz_controls)

        # Live feedback toggle
        self.live_feedback_cb = QCheckBox("Real-time Physics Feedback")
        self.live_feedback_cb.setToolTip("Get instant physics feedback during parameter editing (may impact performance)")
        self.live_feedback_cb.setEnabled(False)
        physics_layout.addWidget(self.live_feedback_cb)

        panel_layout.addWidget(physics_group)

        # 5. Blueprint Export Group (Modified - now requires physics validation)
        export_group = QGroupBox("5. Blueprint Export")
        export_group.setStyleSheet(group_style)
        export_layout = QVBoxLayout(export_group)

        self.export_blueprint_btn = QPushButton("Export Manufacturing Blueprint")
        self.export_blueprint_btn.setEnabled(False)
        self.export_blueprint_btn.setToolTip("Export physics-validated blueprint for manufacturing")
        self.export_blueprint_btn.setStyleSheet("""
            QPushButton {
                background-color: #8e44ad; color: white; border: none;
                padding: 10px 16px; border-radius: 4px; font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #7d3c98; }
            QPushButton:disabled { background-color: #bdc3c7; color: #7f8c8d; }
        """)
        export_layout.addWidget(self.export_blueprint_btn)

        # Export requirements notice
        requirements_label = QLabel("⚠ Requires successful physics validation")
        requirements_label.setStyleSheet("color: #e67e22; font-size: 11px; font-style: italic; margin-top: 5px;")
        export_layout.addWidget(requirements_label)

        info_label = QLabel("Exports multi-layer blueprint optimized for letter-size printing")
        info_label.setStyleSheet("color: #666; font-size: 10px; font-style: italic; margin-top: 3px;")
        export_layout.addWidget(info_label)
        panel_layout.addWidget(export_group)

        # 6. Debug Group (renumbered)
        debug_group = QGroupBox("6. Debug")
        debug_group.setStyleSheet(group_style)
        debug_layout = QVBoxLayout(debug_group)
        self.debug_mode_checkbox = QCheckBox("Show Debug Visuals")
        debug_layout.addWidget(self.debug_mode_checkbox)
        panel_layout.addWidget(debug_group)

        panel_layout.addStretch(1)
        scroll_area.setWidget(control_panel)
        main_layout.addWidget(scroll_area)

    def _connect_signals(self):
        """Connect all UI signals"""
        # Existing signals
        self.recommendation_btn.clicked.connect(self._on_recommendation_btn_clicked)
        self.play_btn.clicked.connect(self.play_clicked)
        self.stop_btn.clicked.connect(self.stop_clicked)
        self.reset_btn.clicked.connect(self.reset_clicked)
        self.parametric_mode_btn.toggled.connect(self.parametric_mode_toggled)
        self.export_blueprint_btn.clicked.connect(self.export_blueprint_requested)
        self.debug_mode_checkbox.toggled.connect(self.debug_mode_toggled)
        
        self.parts_list.itemClicked.connect(self._on_part_item_clicked)
        self.parts_list.itemSelectionChanged.connect(self._on_selection_changed)
        
        # New physics signals
        self.validate_physics_btn.clicked.connect(self.validate_physics_requested)
        self.physics_viz_controls.visualization_changed.connect(self.physics_visualization_changed)
        self.live_feedback_cb.toggled.connect(self.live_physics_feedback_toggled)

    def _on_recommendation_btn_clicked(self):
        """Debug wrapper for recommendation button click"""
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"UIPanel: Get Mechanism button clicked - enabled: {self.recommendation_btn.isEnabled()}")
        self.recommendation_requested.emit()

    def _on_part_item_clicked(self, item: QListWidgetItem):
        """Handle part item click"""
        part_name = item.data(Qt.ItemDataRole.UserRole)
        mechanism_id = item.data(Qt.ItemDataRole.UserRole + 1)

        if mechanism_id:
            self.mechanism_toggled.emit(mechanism_id)
        else:
            self.part_toggled.emit(part_name)

    def _on_selection_changed(self):
        """Handle selection change"""
        selected_items = self.parts_list.selectedItems()
        if selected_items:
            part_name = selected_items[0].data(Qt.ItemDataRole.UserRole)
            self.part_selected.emit(part_name)
        else:
            self.part_selected.emit("")

    def update_ui_from_state(self):
        """Update the entire UI panel based on current state"""
        self._update_parts_list()
        self._update_button_states()

    def _update_parts_list(self):
        """Update parts list widget"""
        if not self.state:
            return
            
        self.parts_list.blockSignals(True)

        current_selection = self.state.selected_part_name if hasattr(self.state, 'selected_part_name') else ""

        self.parts_list.clear()
        
        # Get parts data safely
        parts_data = getattr(self.state, 'parts_data', {})
        path_data = getattr(self.state, 'path_data', {})
        part_enabled_state = getattr(self.state, 'part_enabled_state', {})
        mechanism_layers = getattr(self.state, 'mechanism_layers', {})
        mechanism_enabled_state = getattr(self.state, 'mechanism_enabled_state', {})
        
        # Sort to show parts with paths first, then by name
        sorted_parts = sorted(
            parts_data.keys(), 
            key=lambda p: (p not in path_data, p)
        )

        item_to_select = None
        for name in sorted_parts:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, name)

            has_path = (
                name in path_data
                and path_data[name]
                and not path_data[name].isEmpty()
            )
            part_is_enabled = part_enabled_state.get(name, False)

            mechanism_id = None
            mechanism_is_enabled = False
            for mid, layer in mechanism_layers.items():
                if layer.get("part_name") == name:
                    mechanism_id = mid
                    mechanism_is_enabled = mechanism_enabled_state.get(mid, False)
                    break

            item.setData(Qt.ItemDataRole.UserRole + 1, mechanism_id)

            if mechanism_id:
                color = QColor("#27ae60") if mechanism_is_enabled else QColor("#9b59b6")
                item.setForeground(QBrush(color))
                item.setText(f"{name} (Mechanism {'On' if mechanism_is_enabled else 'Off'})")
            elif has_path:
                color = QColor("black") if part_is_enabled else QColor("gray")
                item.setForeground(QBrush(color))
                item.setText(name)
            else:
                item.setForeground(QBrush(QColor("lightgray")))
                item.setText(name)

            self.parts_list.addItem(item)
            if name == current_selection:
                item_to_select = item

        if item_to_select:
            item_to_select.setSelected(True)

        self.parts_list.blockSignals(False)

    def _update_button_states(self):
        """Update button enabled state based on current conditions"""
        import logging
        logger = logging.getLogger(__name__)
        
        if not self.state:
            logger.warning("UIPanel: _update_button_states called with no state")
            return
            
        # Get state data safely
        parts_data = getattr(self.state, 'parts_data', {})
        path_data = getattr(self.state, 'path_data', {})
        part_enabled_state = getattr(self.state, 'part_enabled_state', {})
        mechanism_layers = getattr(self.state, 'mechanism_layers', {})
        selected_part_name = getattr(self.state, 'selected_part_name', "")
        
        logger.info(f"UIPanel: Button state update - parts_data: {list(parts_data.keys())}")
        logger.info(f"UIPanel: Button state update - path_data: {list(path_data.keys())}")
        logger.info(f"UIPanel: Button state update - part_enabled_state: {part_enabled_state}")
        logger.info(f"UIPanel: Button state update - selected_part_name: '{selected_part_name}'")
        
        has_enabled_paths = any(
            part_enabled_state.get(name)
            for name, path in path_data.items()
            if path and not path.isEmpty()
        )
        has_mechanisms = bool(mechanism_layers)
        
        logger.info(f"UIPanel: Button state conditions - has_enabled_paths: {has_enabled_paths}, has_mechanisms: {has_mechanisms}")
        logger.info(f"UIPanel: Recommendation button will be enabled: {has_enabled_paths and bool(selected_part_name)}")

        # Existing button states
        self.recommendation_btn.setEnabled(has_enabled_paths and bool(selected_part_name))
        self.play_btn.setEnabled(has_mechanisms)
        self.stop_btn.setEnabled(has_mechanisms)
        self.reset_btn.setEnabled(has_mechanisms)
        self.parametric_mode_btn.setEnabled(has_mechanisms)
        
        # Physics validation button - enabled when we have mechanisms
        self.validate_physics_btn.setEnabled(has_mechanisms)
        self.live_feedback_cb.setEnabled(has_mechanisms)
        
        # Export button - only enabled when physics validation passes
        can_export = (has_mechanisms and 
                     self._validation_state in [ValidationState.SUCCESS, ValidationState.WARNING])
        self.export_blueprint_btn.setEnabled(can_export)
        
        # Physics visualization controls
        self.physics_viz_controls.set_enabled_for_validation_state(self._validation_state)

    # Physics validation state management methods
    
    def set_physics_validation_state(self, state: ValidationStatusIndicatorState):
        """Update physics validation status indicator"""
        self._validation_state = state.validation_state
        self.validation_status.set_state(state)
        
        # Update button states when validation state changes
        self._update_button_states()
    
    def set_validation_in_progress(self, message: str = "Running physics validation..."):
        """Set validation to in-progress state"""
        state = ValidationStatusIndicatorState.validating(message)
        self.set_physics_validation_state(state)
    
    def set_validation_success(self, result_summary: str = ""):
        """Set validation to success state"""
        message = f"Validation Successful{' - ' + result_summary if result_summary else ''}"
        state = ValidationStatusIndicatorState(
            validation_state=ValidationState.SUCCESS,
            message=message,
            color="#00AA00",
            tooltip="Physics validation passed - ready for blueprint export"
        )
        self.set_physics_validation_state(state)
    
    def set_validation_failure(self, error_summary: str = ""):
        """Set validation to failure state"""
        message = f"Validation Failed{' - ' + error_summary if error_summary else ''}"
        state = ValidationStatusIndicatorState(
            validation_state=ValidationState.FAILURE,
            message=message,
            color="#FF4444",
            tooltip="Physics validation failed - see details and fix issues before export"
        )
        self.set_physics_validation_state(state)
    
    def reset_validation_state(self):
        """Reset validation to not validated state"""
        state = ValidationStatusIndicatorState.not_validated()
        self.set_physics_validation_state(state)
    
    def get_physics_visualization_settings(self) -> PhysicsVisualizationSettings:
        """Get current physics visualization settings"""
        return self.physics_viz_controls.get_settings()
    
    def is_live_physics_feedback_enabled(self) -> bool:
        """Check if live physics feedback is enabled"""
        return self.live_feedback_cb.isChecked()
    
    def enable_physics_features(self, enabled: bool):
        """Enable or disable physics-related features"""
        self._physics_validation_enabled = enabled
        self.validate_physics_btn.setEnabled(enabled and hasattr(self.state, 'mechanism_layers') and bool(self.state.mechanism_layers))
        self.live_feedback_cb.setEnabled(enabled)
        
        if not enabled:
            self.reset_validation_state()
            self.physics_viz_controls.setEnabled(False)