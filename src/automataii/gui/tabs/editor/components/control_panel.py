"""Control panel for editor tab."""

import logging
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea, 
    QPushButton, QGroupBox
)
from PyQt6.QtCore import pyqtSignal, Qt

from ....components.common import PartListWidget, PartPropertiesPanel
from ....components.path_drawing import PathControlsWidget, AnimationControlsWidget
from ..state import EditorState
from ..handlers import PartSelectionHandler, PathDrawingHandler, SimulationHandler


class EditorControlPanel(QWidget):
    """Left control panel for editor tab."""
    
    # Signals
    goto_mechanism_requested = pyqtSignal()
    save_alignment_requested = pyqtSignal()
    
    def __init__(
        self,
        state: EditorState,
        selection_handler: PartSelectionHandler,
        path_handler: PathDrawingHandler,
        simulation_handler: SimulationHandler,
        parent=None
    ):
        super().__init__(parent)
        
        self._state = state
        self._selection_handler = selection_handler
        self._path_handler = path_handler
        self._simulation_handler = simulation_handler
        
        # Components
        self._part_list = PartListWidget()
        self._properties_panel = PartPropertiesPanel()
        self._path_controls = PathControlsWidget()
        self._animation_controls = AnimationControlsWidget()
        
        self._init_ui()
        self._connect_signals()
    
    def _init_ui(self):
        """Initialize UI."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFixedWidth(320)
        
        # Content widget
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(10)
        
        # Add components
        content_layout.addWidget(self._create_part_section())
        content_layout.addWidget(self._properties_panel)
        content_layout.addWidget(self._path_controls)
        content_layout.addWidget(self._animation_controls)
        content_layout.addWidget(self._create_alignment_section())
        content_layout.addStretch()
        
        scroll.setWidget(content)
        layout.addWidget(scroll)
    
    def _create_part_section(self) -> QGroupBox:
        """Create part selection section."""
        group = QGroupBox("Parts")
        layout = QVBoxLayout(group)
        layout.addWidget(self._part_list)
        return group
    
    def _create_alignment_section(self) -> QGroupBox:
        """Create character alignment section."""
        group = QGroupBox("Character Alignment")
        layout = QVBoxLayout(group)
        
        save_btn = QPushButton("Save Current Alignment")
        save_btn.setToolTip("Save the current character position as default")
        save_btn.clicked.connect(self.save_alignment_requested.emit)
        
        layout.addWidget(save_btn)
        return group
    
    def _connect_signals(self):
        """Connect internal signals."""
        # Part selection
        self._part_list.part_selected.connect(self._on_part_selected)
        self._part_list.part_deselected.connect(self._on_part_deselected)
        
        # Properties
        self._properties_panel.z_value_changed.connect(self._on_z_value_changed)
        self._properties_panel.fixed_state_changed.connect(self._on_fixed_changed)
        
        # Path controls
        self._path_controls.define_path_requested.connect(self._start_path_drawing)
        self._path_controls.clear_path_requested.connect(self._clear_path)
        
        # Animation controls
        self._animation_controls.play_requested.connect(self._simulation_handler.play)
        self._animation_controls.stop_requested.connect(self._simulation_handler.stop)
        self._animation_controls.reset_requested.connect(self._simulation_handler.reset)
        self._animation_controls.goto_mechanism_generation.connect(
            self.goto_mechanism_requested.emit
        )
        
        # Handler signals
        self._selection_handler.selection_changed.connect(self._update_selection_ui)
        self._path_handler.drawing_completed.connect(self._on_path_completed)
        self._simulation_handler.simulation_started.connect(self._on_simulation_started)
        self._simulation_handler.simulation_stopped.connect(self._on_simulation_stopped)
    
    def _on_part_selected(self, part_name: str):
        """Handle part selection from list."""
        self._selection_handler.select_part(part_name)
    
    def _on_part_deselected(self):
        """Handle part deselection."""
        self._selection_handler.clear_selection()
    
    def _on_z_value_changed(self, part_name: str, value: float):
        """Handle z-value change."""
        self._state.update_part_property(part_name, 'z_value', value)
    
    def _on_fixed_changed(self, part_name: str, is_fixed: bool):
        """Handle fixed state change."""
        self._state.update_part_property(part_name, 'is_fixed', is_fixed)
    
    def _start_path_drawing(self):
        """Start path drawing mode."""
        # The actual path drawing start is handled by the coordinator
        # This method just updates the UI state
        self._path_controls.set_drawing_mode(True)
    
    def _clear_path(self):
        """Clear path for selected part."""
        self._path_handler.clear_path()
        self._update_path_ui()
    
    def _on_path_completed(self, part_name: str, path):
        """Handle path completion."""
        self._path_controls.set_drawing_mode(False)
        self._update_path_ui()
        self._part_list.update_part_status(part_name, True)
    
    def _on_simulation_started(self):
        """Handle simulation start."""
        self._animation_controls.set_playing_state(True)
        self._path_controls.set_enabled_state(False, True)
    
    def _on_simulation_stopped(self):
        """Handle simulation stop."""
        self._animation_controls.set_playing_state(False)
        self._path_controls.set_enabled_state(True, False)
    
    def _update_selection_ui(self):
        """Update UI based on selection."""
        selected = self._state.selected_part_name
        
        if selected and selected in self._state.parts:
            part_state = self._state.parts[selected]
            self._properties_panel.load_part(selected, part_state.__dict__)
            self._path_controls.set_selected_part(selected, part_state.has_motion_path)
        else:
            self._properties_panel.clear_part()
            self._path_controls.set_selected_part(None)
    
    def _update_path_ui(self):
        """Update path-related UI."""
        has_any_path = bool(self._state.get_parts_with_paths())
        self._animation_controls.set_has_paths(has_any_path)
    
    def update_state(self, state):
        """Update UI based on editor state."""
        # Update components based on state
        if hasattr(state, 'has_parts'):
            parts_data = {name: part.__dict__ for name, part in self._state.parts.items()}
            self._part_list.load_parts(parts_data)