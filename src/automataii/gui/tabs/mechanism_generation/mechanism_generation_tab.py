"""Main coordinator for mechanism generation tab."""

import logging
from typing import Optional, Dict, Any

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
    QGroupBox, QScrollArea, QMessageBox, QDialog, QGraphicsView
)
from PyQt6.QtCore import Qt, pyqtSignal, QPointF
from PyQt6.QtGui import QPainterPath, QColor

from .state_manager import StateManager
from .control_panels import (
    PartSelectionPanel, MechanismTypePanel, 
    SimulationControlPanel, MechanismListPanel
)
from .visualization import MechanismVisualizationWidget
from .generation_service import MechanismGenerationService, MechanismParameters
from .export_handler import ExportHandler
from .mechanism_editor import MechanismEditor, EditMode
from .editing_shortcuts import ShortcutManager, ContextMenuManager
from .advanced_editing import AdvancedPropertyPanel

from ...graphics_items.part_item import CharacterPartItem
from ...dialogs.recommendation_dialog import MechanismRecommendationDialog


class MechanismGenerationTab(QWidget):
    """Main tab for mechanism generation."""
    
    # Signals for external communication
    request_generate_mechanism = pyqtSignal(str, dict)  # mechanism_type, params
    request_generate_blueprint = pyqtSignal()
    request_play_simulation = pyqtSignal()
    request_stop_simulation = pyqtSignal()
    request_reset_simulation = pyqtSignal()
    
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.debug_mode = getattr(main_window, "debug_mode", False)
        self._logger = logging.getLogger(__name__)
        
        # Initialize components
        self._state_manager = StateManager()
        self._generation_service = MechanismGenerationService()
        self._export_handler = ExportHandler(self)
        
        # UI components will be created in _init_ui
        self._part_panel: Optional[PartSelectionPanel] = None
        self._mechanism_panel: Optional[MechanismTypePanel] = None
        self._simulation_panel: Optional[SimulationControlPanel] = None
        self._mechanism_list_panel: Optional[MechanismListPanel] = None
        self._visualization: Optional[MechanismVisualizationWidget] = None
        self._mechanism_editor: Optional[MechanismEditor] = None
        self._edit_panel: Optional[QWidget] = None
        self._shortcut_manager: Optional[ShortcutManager] = None
        self._context_menu_manager: Optional[ContextMenuManager] = None
        self._advanced_panel: Optional[AdvancedPropertyPanel] = None
        
        self._init_ui()
        self._connect_signals()
        self._update_ui_state()
    
    def _init_ui(self):
        """Initialize the UI layout."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Right Visualization Area (create first for scene)
        self._visualization = MechanismVisualizationWidget(self)
        layout.addWidget(self._visualization, 1)
        
        # Create mechanism editor with scene
        self._mechanism_editor = MechanismEditor(self._visualization.scene)
        self._mechanism_editor.signals.mechanism_updated.connect(self._on_mechanism_edited)
        
        # Left Control Panel (create after editor is initialized)
        left_panel = self._create_control_panel()
        layout.addWidget(left_panel, 0)
        self._mechanism_editor.signals.undo_requested.connect(self._handle_undo)
        self._mechanism_editor.signals.redo_requested.connect(self._handle_redo)
        
        # Set up shortcuts and context menus
        self._shortcut_manager = ShortcutManager(self)
        self._shortcut_manager.shortcut_triggered.connect(self._handle_shortcut)
        
        self._context_menu_manager = ContextMenuManager()
        self._visualization.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._visualization.view.customContextMenuRequested.connect(self._show_context_menu)
    
    def _create_control_panel(self) -> QScrollArea:
        """Create the left control panel."""
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setFixedWidth(320)
        
        control_widget = QWidget()
        panel_layout = QVBoxLayout(control_widget)
        panel_layout.setContentsMargins(10, 10, 10, 10)
        panel_layout.setSpacing(10)
        
        # Part Selection
        self._part_panel = PartSelectionPanel()
        panel_layout.addWidget(self._part_panel)
        
        # Mechanism Generation
        mech_group = QGroupBox("Mechanism Generation")
        mech_layout = QVBoxLayout(mech_group)
        
        self._mechanism_panel = MechanismTypePanel()
        mech_layout.addWidget(self._mechanism_panel)
        
        # Generate and Recommend buttons
        self._generate_btn = QPushButton("Generate Mechanism")
        self._generate_btn.setToolTip("Generate mechanism for the selected part's motion")
        mech_layout.addWidget(self._generate_btn)
        
        self._recommend_btn = QPushButton("🤖 Recommend Mechanism")
        self._recommend_btn.setToolTip("Get AI recommendation for the best mechanism type")
        self._recommend_btn.setEnabled(False)
        mech_layout.addWidget(self._recommend_btn)
        
        panel_layout.addWidget(mech_group)
        
        # Simulation Controls
        self._simulation_panel = SimulationControlPanel()
        panel_layout.addWidget(self._simulation_panel)
        
        # Edit Mode Controls
        edit_group = QGroupBox("Mechanism Editing")
        edit_layout = QVBoxLayout(edit_group)
        
        self._edit_mode_btn = QPushButton("Enable Edit Mode")
        self._edit_mode_btn.setCheckable(True)
        self._edit_mode_btn.setToolTip("Toggle mechanism editing mode")
        edit_layout.addWidget(self._edit_mode_btn)
        
        # Create property panel from editor
        self._edit_panel = self._mechanism_editor.create_property_panel()
        self._edit_panel.setVisible(False)
        edit_layout.addWidget(self._edit_panel)
        
        # Advanced editing panel (initially hidden)
        self._advanced_panel = AdvancedPropertyPanel()
        self._advanced_panel.property_changed.connect(self._on_advanced_property_changed)
        self._advanced_panel.batch_operation_requested.connect(self._perform_batch_operation)
        self._advanced_panel.setVisible(False)
        edit_layout.addWidget(self._advanced_panel)
        
        # Advanced mode toggle
        self._advanced_mode_btn = QPushButton("Advanced Mode")
        self._advanced_mode_btn.setCheckable(True)
        self._advanced_mode_btn.toggled.connect(self._toggle_advanced_mode)
        edit_layout.addWidget(self._advanced_mode_btn)
        
        panel_layout.addWidget(edit_group)
        
        # Generated Mechanisms
        self._mechanism_list_panel = MechanismListPanel()
        panel_layout.addWidget(self._mechanism_list_panel)
        
        # Export
        export_group = QGroupBox("Export")
        export_layout = QVBoxLayout(export_group)
        self._blueprint_btn = QPushButton("Generate Blueprint (SVG)")
        self._blueprint_btn.setToolTip("Generate an SVG blueprint of all parts for fabrication")
        export_layout.addWidget(self._blueprint_btn)
        panel_layout.addWidget(export_group)
        
        panel_layout.addStretch()
        scroll_area.setWidget(control_widget)
        
        return scroll_area
    
    def _connect_signals(self):
        """Connect all internal signals."""
        # State manager signals
        self._state_manager.state_changed.connect(self._update_ui_state)
        self._state_manager.part_selection_changed.connect(self._on_part_selected)
        
        # Part selection
        self._part_panel.part_selected.connect(self._state_manager.set_selected_part)
        
        # Mechanism type and point selection
        self._mechanism_panel.mechanism_type_changed.connect(self._on_mechanism_type_changed)
        self._mechanism_panel.select_cam_center.connect(
            lambda: self._start_point_selection("cam_center")
        )
        self._mechanism_panel.select_pivot_a_3bar.connect(
            lambda: self._start_point_selection("pivot_a_3bar")
        )
        self._mechanism_panel.select_pivot_a_4bar.connect(
            lambda: self._start_point_selection("pivot_a_4bar")
        )
        self._mechanism_panel.select_pivot_d_4bar.connect(
            lambda: self._start_point_selection("pivot_d_4bar")
        )
        
        # Visualization point selection
        self._visualization.cam_center_selected.connect(self._handle_cam_center_selected)
        self._visualization.pivot_a_selected.connect(self._handle_pivot_a_selected)
        self._visualization.pivot_d_selected.connect(self._handle_pivot_d_selected)
        
        # Generation
        self._generate_btn.clicked.connect(self._generate_mechanism)
        self._recommend_btn.clicked.connect(self._recommend_mechanism)
        self._generation_service.generation_completed.connect(self._on_mechanism_generated)
        self._generation_service.generation_failed.connect(self._on_generation_failed)
        
        # Simulation controls
        self._simulation_panel.play_clicked.connect(self._play_simulation)
        self._simulation_panel.stop_clicked.connect(self._stop_simulation)
        self._simulation_panel.reset_clicked.connect(self._reset_simulation)
        
        # Mechanism list
        self._mechanism_list_panel.show_requested.connect(self._show_mechanism)
        self._mechanism_list_panel.hide_requested.connect(self._hide_mechanism)
        self._mechanism_list_panel.delete_requested.connect(self._delete_mechanism)
        
        # Export
        self._blueprint_btn.clicked.connect(self._export_blueprint)
        self._export_handler.export_completed.connect(self._on_export_completed)
        
        # Edit mode
        self._edit_mode_btn.toggled.connect(self._toggle_edit_mode)
    
    def _update_ui_state(self):
        """Update UI elements based on current state."""
        state = self._state_manager.state
        
        # Update button states
        has_part_with_path = self._state_manager.has_selected_part_with_path()
        has_mechanisms = self._state_manager.has_mechanisms()
        
        self._generate_btn.setEnabled(has_part_with_path)
        self._recommend_btn.setEnabled(has_part_with_path)
        self._blueprint_btn.setEnabled(has_mechanisms)
        
        # Update simulation panel
        self._simulation_panel.update_button_states(
            state.is_mechanism_simulating,
            has_mechanisms
        )
    
    def _on_part_selected(self, part_name: str):
        """Handle part selection change."""
        if part_name:
            self._visualization.highlight_part(part_name)
            
            # Show motion path if available
            path = self._state_manager.state.motion_paths.get(part_name)
            if path and not path.isEmpty():
                self._visualization.visualize_motion_path(path)
    
    def _on_mechanism_type_changed(self, mechanism_type: str):
        """Handle mechanism type change."""
        self._logger.info(f"Mechanism type changed to: {mechanism_type}")
        self._update_ui_state()
    
    def _start_point_selection(self, point_type: str):
        """Start point selection mode."""
        self._state_manager.set_mechanism_selecting_mode(point_type)
        
        # Set appropriate view mode
        if point_type in ["cam_center", "pivot_a_3bar", "pivot_a_4bar"]:
            self._visualization.set_selection_mode("select_pivot_a")
        elif point_type == "pivot_d_4bar":
            self._visualization.set_selection_mode("select_pivot_d")
    
    def _handle_cam_center_selected(self, point: QPointF):
        """Handle cam center selection."""
        if self._state_manager.state.mechanism_selecting_mode == "cam_center":
            self._state_manager.set_cam_center(point)
            self._visualization.add_point_marker("cam_center", point, QColor(255, 0, 0))
            self._visualization.set_selection_mode("select")
            self._state_manager.set_mechanism_selecting_mode(None)
    
    def _handle_pivot_a_selected(self, point: QPointF):
        """Handle pivot A selection."""
        mode = self._state_manager.state.mechanism_selecting_mode
        if mode in ["pivot_a_3bar", "pivot_a_4bar"]:
            self._state_manager.set_pivot_a(point)
            self._visualization.add_point_marker("pivot_a", point, QColor(0, 255, 0))
            self._visualization.set_selection_mode("select")
            self._state_manager.set_mechanism_selecting_mode(None)
    
    def _handle_pivot_d_selected(self, point: QPointF):
        """Handle pivot D selection."""
        if self._state_manager.state.mechanism_selecting_mode == "pivot_d_4bar":
            self._state_manager.set_pivot_d(point)
            self._visualization.add_point_marker("pivot_d", point, QColor(0, 0, 255))
            self._visualization.set_selection_mode("select")
            self._state_manager.set_mechanism_selecting_mode(None)
    
    def _generate_mechanism(self):
        """Generate mechanism with current parameters."""
        state = self._state_manager.state
        
        if not state.selected_part_name:
            return
        
        # Prepare parameters
        params = MechanismParameters(
            mechanism_type=self._mechanism_panel.get_current_type(),
            part_name=state.selected_part_name,
            motion_path=state.motion_paths.get(state.selected_part_name, QPainterPath()),
            cam_center=state.selected_cam_center,
            pivot_a=state.selected_pivot_a,
            pivot_d=state.selected_pivot_d,
        )
        
        # Validate and generate
        is_valid, error_msg = self._generation_service.validate_parameters(params)
        if not is_valid:
            QMessageBox.warning(self, "Invalid Parameters", error_msg)
            return
        
        # Generate mechanism
        mechanism_data = self._generation_service.generate_mechanism(params)
        
        if mechanism_data:
            # Emit signal for main window
            self.request_generate_mechanism.emit(
                params.mechanism_type,
                mechanism_data
            )
    
    def _recommend_mechanism(self):
        """Show mechanism recommendation dialog."""
        state = self._state_manager.state
        
        if not state.selected_part_name:
            return
        
        motion_path = state.motion_paths.get(state.selected_part_name)
        if not motion_path or motion_path.isEmpty():
            return
        
        # Show recommendation dialog
        dialog = MechanismRecommendationDialog(motion_path, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            recommended_type = dialog.get_selected_mechanism()
            if recommended_type:
                self._mechanism_panel.set_mechanism_type(recommended_type)
    
    def _on_mechanism_generated(self, mechanism_data: Dict):
        """Handle successful mechanism generation."""
        # Add to state
        self._state_manager.add_mechanism(mechanism_data)
        
        # Add to list
        self._mechanism_list_panel.add_mechanism(
            mechanism_data.get("type", "Unknown"),
            mechanism_data.get("part_name", "Unknown")
        )
        
        # Visualize mechanism
        self._visualize_mechanism(mechanism_data)
    
    def _on_generation_failed(self, error_msg: str):
        """Handle mechanism generation failure."""
        QMessageBox.critical(self, "Generation Failed", error_msg)
    
    def _visualize_mechanism(self, mechanism_data: Dict):
        """Visualize a generated mechanism."""
        # Set mechanism in editor for interactive editing
        self._mechanism_editor.set_mechanism(mechanism_data)
        
        # Also create animated visualization
        self._visualization.visualize_mechanism(mechanism_data)
        
        # Enable edit mode button
        self._edit_mode_btn.setEnabled(True)
    
    def set_parts_data(self, parts_info: Dict[str, Any]) -> None:
        """Set parts data from project manager."""
        from automataii.gui.graphics_items.part_item import CharacterPartItem
        from PyQt6.QtCore import QPointF
        from pathlib import Path
        
        self._logger.info(f"MechanismGenerationTab.set_parts_data called with {len(parts_info) if parts_info else 0} parts")
        if parts_info:
            self._logger.info(f"Parts: {list(parts_info.keys())}")
        
        # Clear existing parts from scene
        for item in list(self._visualization.scene.items()):
            if isinstance(item, CharacterPartItem):
                self._visualization.scene.removeItem(item)
        
        # Add new parts to scene
        character_parts = {}
        for part_name, part_info in parts_info.items():
            # Get project directory from part info image path
            if hasattr(part_info, 'image_path') and part_info.image_path:
                project_dir = Path(part_info.image_path).parent
            else:
                # Fallback to a temporary directory
                project_dir = Path("/tmp")
            
            # Create the CharacterPartItem
            part_item = CharacterPartItem(part_info, project_dir, parent=None)
            # Name is already set in part_info.name, no need to set it separately
            
            # Set position if available
            if hasattr(part_info, 'position') and part_info.position:
                pos = QPointF(part_info.position[0], part_info.position[1])
                part_item.setPos(pos)
            
            # Add to scene
            self._visualization.scene.addItem(part_item)
            character_parts[part_name] = part_item
        
        # Update state manager with parts
        self._state_manager.set_character_parts(character_parts)
        
        # Update part selection panel
        self._part_panel.update_parts_list(list(parts_info.keys()))
        
        # Update UI state
        self._update_ui_state()
        
        self._logger.info(f"Parts data set successfully. Scene now has {len(self._visualization.scene.items())} items")
    
    def set_skeleton_data(self, skeleton_data: Optional[Dict[str, Any]]) -> None:
        """Set skeleton data from project manager."""
        if skeleton_data:
            self._logger.info("Setting skeleton data")
            # If visualization needs skeleton, add it here
            # For now, just log it
            self._state_manager.state.skeleton_data = skeleton_data
        else:
            self._logger.info("Clearing skeleton data")
            if hasattr(self._state_manager.state, 'skeleton_data'):
                self._state_manager.state.skeleton_data = None
    
    def receive_character_and_paths(self, parts_dict: Dict, paths_dict: Dict, skeleton_data: Optional[Dict] = None) -> None:
        """Receive character parts and motion paths from editor tab."""
        self._logger.info(f"Received {len(parts_dict)} parts and {len(paths_dict)} paths for mechanism generation")
        
        # Update motion paths in state
        self._state_manager.update_motion_paths(paths_dict)
        
        # If we have parts dict with CharacterPartItem objects, add them to visualization
        if parts_dict:
            self._visualization.add_character_parts(parts_dict)
        
        # Update skeleton if provided
        if skeleton_data:
            self.set_skeleton_data(skeleton_data)
        
        # Update parts panel with parts that have paths
        parts_with_paths = []
        for part_name in parts_dict:
            has_path = part_name in paths_dict and not paths_dict[part_name].isEmpty()
            parts_with_paths.append((part_name, has_path))
        self._part_panel.update_parts(parts_with_paths)
        
        # Update UI state
        self._update_ui_state()
        
        self._logger.info("Character and paths data loaded for mechanism generation")
    
    def _show_mechanism(self, index: int):
        """Show mechanism at index."""
        if 0 <= index < len(self._state_manager.state.current_mechanisms):
            mechanism_data = self._state_manager.state.current_mechanisms[index]
            self._visualize_mechanism(mechanism_data)
    
    def _hide_mechanism(self, index: int):
        """Hide mechanism at index."""
        # Clear visualization for now
        self._mechanism_editor.clear_elements()
    
    def _delete_mechanism(self, index: int):
        """Delete mechanism at index."""
        self._state_manager.remove_mechanism(index)
        self._mechanism_list_panel.remove_mechanism(index)
    
    def _play_simulation(self):
        """Start mechanism simulation."""
        self._state_manager.set_simulation_state("playing")
        self._visualization.start_mechanism_animation()
        self.request_play_simulation.emit()
    
    def _stop_simulation(self):
        """Stop mechanism simulation."""
        self._state_manager.set_simulation_state("stopped")
        self._visualization.stop_mechanism_animation()
        self.request_stop_simulation.emit()
    
    def _reset_simulation(self):
        """Reset mechanism simulation."""
        self._state_manager.set_simulation_state("stopped")
        self._visualization.reset_mechanism_animation()
        self.request_reset_simulation.emit()
    
    def _export_blueprint(self):
        """Export mechanisms as blueprint."""
        mechanisms = self._state_manager.state.current_mechanisms
        self._export_handler.export_blueprint(mechanisms)
    
    def _on_export_completed(self, file_path: str):
        """Handle export completion."""
        QMessageBox.information(
            self,
            "Export Complete",
            f"Blueprint exported to:\n{file_path}"
        )
    
    # Public API methods
    
    def receive_character_and_paths(self, 
                                  character_parts: Dict[str, CharacterPartItem],
                                  motion_paths: Dict[str, QPainterPath],
                                  skeleton_data: Optional[Dict] = None):
        """Receive character parts and motion paths from Path Drawing tab."""
        self._logger.info(
            f"Received {len(character_parts)} parts and {len(motion_paths)} paths"
        )
        
        # Update state
        self._state_manager.update_character_parts(character_parts)
        self._state_manager.update_motion_paths(motion_paths)
        
        # Update UI
        parts_with_paths = [
            (name, name in motion_paths and not motion_paths[name].isEmpty())
            for name in sorted(character_parts.keys())
        ]
        self._part_panel.update_parts(parts_with_paths)
        
        # Update visualization
        self._visualization.add_character_parts(character_parts)
        
        if skeleton_data:
            self._visualization.visualize_skeleton(skeleton_data)
        
        # Fit view
        self._visualization.view.zoom_to_fit()
    
    def on_mechanism_generated(self, mechanism_data: Dict):
        """Handle mechanism generation from external source."""
        self._on_mechanism_generated(mechanism_data)
    
    def on_simulation_state_changed(self, state_string: str):
        """Handle simulation state changes."""
        self._state_manager.set_simulation_state(state_string)
    
    def clear_all(self):
        """Clear all data and reset the tab."""
        self._state_manager.clear_all()
        self._part_panel.clear()
        self._mechanism_list_panel.clear()
        self._visualization.clear_all()
        self._mechanism_editor.clear_elements()
        self._edit_mode_btn.setChecked(False)
        self._edit_mode_btn.setEnabled(False)
        self._update_ui_state()
    
    def _toggle_edit_mode(self, checked: bool):
        """Toggle mechanism edit mode."""
        if checked:
            self._mechanism_editor.set_edit_mode(EditMode.EDIT_ANCHORS)
            self._edit_panel.setVisible(True)
            self._edit_mode_btn.setText("Disable Edit Mode")
            self._visualization.view.setDragMode(QGraphicsView.DragMode.NoDrag)
            # Enable advanced mode button
            self._advanced_mode_btn.setEnabled(True)
        else:
            self._mechanism_editor.set_edit_mode(EditMode.VIEW)
            self._edit_panel.setVisible(False)
            self._advanced_panel.setVisible(False)
            self._advanced_mode_btn.setChecked(False)
            self._advanced_mode_btn.setEnabled(False)
            self._edit_mode_btn.setText("Enable Edit Mode")
            self._visualization.view.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
    
    def _toggle_advanced_mode(self, checked: bool):
        """Toggle advanced editing features."""
        self._advanced_panel.setVisible(checked)
        if checked:
            self._advanced_mode_btn.setText("Basic Mode")
            # Enable additional features
            self._mechanism_editor.toggle_constraints_display(True)
            self._mechanism_editor.toggle_dimensions_display(True)
        else:
            self._advanced_mode_btn.setText("Advanced Mode")
            self._mechanism_editor.toggle_constraints_display(False)
            self._mechanism_editor.toggle_dimensions_display(False)
    
    def _on_mechanism_edited(self, updated_data: Dict):
        """Handle mechanism edits."""
        # Update the mechanism data in state
        current_mechanisms = self._state_manager.state.current_mechanisms
        
        # Find and update the edited mechanism
        for i, mech in enumerate(current_mechanisms):
            if mech.get("type") == updated_data.get("type") and \
               mech.get("part_name") == updated_data.get("part_name"):
                current_mechanisms[i] = updated_data
                break
        
        # Emit signal for main window if needed
        self.request_generate_mechanism.emit(
            updated_data.get("type", ""),
            updated_data
        )
    
    def _handle_undo(self):
        """Handle undo request."""
        self._mechanism_editor.undo()
    
    def _handle_redo(self):
        """Handle redo request."""
        self._mechanism_editor.redo()
    
    def _handle_shortcut(self, action_name: str):
        """Handle keyboard shortcuts."""
        if action_name == "toggle_edit_mode":
            self._edit_mode_btn.toggle()
        elif action_name == "undo":
            self._mechanism_editor.undo()
        elif action_name == "redo":
            self._mechanism_editor.redo()
        elif action_name == "play_pause":
            if self._state_manager.state.is_mechanism_simulating:
                self._stop_simulation()
            else:
                self._play_simulation()
        elif action_name == "zoom_fit":
            self._visualization.view.zoom_to_fit()
        elif action_name == "delete_selected":
            self._delete_selected_elements()
            
    def _show_context_menu(self, pos):
        """Show context menu."""
        scene_pos = self._visualization.view.mapToScene(pos)
        item = self._visualization.scene.itemAt(scene_pos, self._visualization.view.transform())
        
        menu = None
        if item and hasattr(item, 'anchor_id'):
            menu = self._context_menu_manager.create_anchor_menu(item.anchor_id)
        elif item and hasattr(item, 'link_id'):
            menu = self._context_menu_manager.create_link_menu(item.link_id)
        else:
            menu = self._context_menu_manager.create_canvas_menu(scene_pos)
            
        if menu:
            action = menu.exec(self._visualization.view.mapToGlobal(pos))
            if action:
                self._handle_context_action(action)
                
    def _handle_context_action(self, action):
        """Handle context menu action."""
        data = action.data()
        if not data:
            return
            
        command = data[0]
        if command == "edit_properties":
            # Show properties for element
            pass
        elif command == "delete":
            # Delete element
            element_id = data[1]
            self._delete_element(element_id)
            
    def _on_advanced_property_changed(self, property_name: str, value):
        """Handle advanced property changes."""
        if property_name == "snap_to_grid":
            self._mechanism_editor.toggle_grid(value)
        elif property_name == "grid_size":
            self._mechanism_editor.set_grid_size(value)
            
    def _perform_batch_operation(self, operation: str, params: Dict):
        """Perform batch operation on elements."""
        # Implement batch operations
        pass
        
    def _delete_selected_elements(self):
        """Delete selected mechanism elements."""
        # Implement deletion logic
        pass
        
    def _delete_element(self, element_id: str):
        """Delete specific element."""
        # Implement deletion logic
        pass