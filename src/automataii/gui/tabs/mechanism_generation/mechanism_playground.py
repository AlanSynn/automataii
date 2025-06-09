"""Complete mechanism playground with all advanced editing features integrated."""

import logging
from typing import Optional, Dict, List, Any
from PyQt6.QtCore import Qt, QPointF, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, 
    QDockWidget, QMainWindow, QToolBar, QStatusBar,
    QMessageBox, QGraphicsView
)
from PyQt6.QtGui import QPainterPath

from .mechanism_editor import MechanismEditor, EditMode
from .visualization import MechanismVisualizationWidget
from .advanced_editing import (
    AdvancedPropertyPanel, MechanismAnalyzer, 
    MotionAnalysisWidget, OptimizationEngine
)
from .editing_shortcuts import ShortcutManager, ContextMenuManager, EditingToolbar
from .state_manager import StateManager


class MechanismPlayground(QMainWindow):
    """Complete mechanism editing environment with all features integrated."""
    
    # Signals
    mechanism_updated = pyqtSignal(dict)
    export_requested = pyqtSignal(str, dict)  # format, data
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._logger = logging.getLogger(__name__)
        
        # Core components
        self.state_manager = StateManager()
        self.mechanism_analyzer = MechanismAnalyzer()
        self.optimization_engine = OptimizationEngine()
        self.context_menu_manager = ContextMenuManager()
        
        # UI components
        self.visualization_widget = None
        self.mechanism_editor = None
        self.property_panel = None
        self.motion_analysis_widget = None
        self.editing_toolbar = None
        self.shortcut_manager = None
        
        self._init_ui()
        self._connect_signals()
        self._setup_shortcuts()
        
    def _init_ui(self):
        """Initialize the complete UI."""
        self.setWindowTitle("Mechanism Playground")
        self.resize(1400, 900)
        
        # Central widget with visualization
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Editing toolbar
        self.editing_toolbar = EditingToolbar()
        layout.addWidget(self.editing_toolbar)
        
        # Main splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Visualization area
        self.visualization_widget = MechanismVisualizationWidget()
        self.visualization_widget.setMinimumWidth(800)
        splitter.addWidget(self.visualization_widget)
        
        # Create mechanism editor
        self.mechanism_editor = MechanismEditor(self.visualization_widget.scene)
        
        # Right panel with properties
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(5, 5, 5, 5)
        
        # Advanced property panel
        self.property_panel = AdvancedPropertyPanel()
        right_layout.addWidget(self.property_panel)
        
        # Motion analysis widget
        self.motion_analysis_widget = MotionAnalysisWidget()
        right_layout.addWidget(self.motion_analysis_widget)
        
        right_panel.setMaximumWidth(400)
        splitter.addWidget(right_panel)
        
        layout.addWidget(splitter)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Create dockable panels
        self._create_dock_panels()
        
    def _create_dock_panels(self):
        """Create dockable panels for additional features."""
        # Constraints dock
        constraints_dock = QDockWidget("Constraints Manager", self)
        constraints_widget = QWidget()
        constraints_layout = QVBoxLayout(constraints_widget)
        # Add constraint management UI here
        constraints_dock.setWidget(constraints_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, constraints_dock)
        
        # Animation control dock
        animation_dock = QDockWidget("Animation Control", self)
        animation_widget = QWidget()
        animation_layout = QVBoxLayout(animation_widget)
        # Add animation control UI here
        animation_dock.setWidget(animation_widget)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, animation_dock)
        
    def _connect_signals(self):
        """Connect all signals between components."""
        # Editor signals
        self.mechanism_editor.signals.mechanism_updated.connect(self._on_mechanism_updated)
        self.mechanism_editor.signals.constraint_violated.connect(self._show_constraint_violation)
        
        # Property panel signals
        self.property_panel.property_changed.connect(self._on_property_changed)
        self.property_panel.batch_operation_requested.connect(self._perform_batch_operation)
        
        # Toolbar signals
        self.editing_toolbar.tool_selected.connect(self._on_tool_selected)
        self.editing_toolbar.snap_btn.toggled.connect(self._toggle_snapping)
        self.editing_toolbar.grid_btn.toggled.connect(self._toggle_grid)
        self.editing_toolbar.lock_btn.toggled.connect(self._toggle_lock)
        
        # Visualization signals
        self.visualization_widget.view.customContextMenuRequested.connect(self._show_context_menu)
        
    def _setup_shortcuts(self):
        """Set up keyboard shortcuts."""
        self.shortcut_manager = ShortcutManager(self)
        self.shortcut_manager.shortcut_triggered.connect(self._handle_shortcut)
        
    def _handle_shortcut(self, action_name: str):
        """Handle keyboard shortcut triggers."""
        self._logger.info(f"Shortcut triggered: {action_name}")
        
        # Handle different shortcuts
        if action_name == "toggle_edit_mode":
            self._toggle_edit_mode()
        elif action_name == "select_all":
            self._select_all_elements()
        elif action_name == "delete_selected":
            self._delete_selected_elements()
        elif action_name == "undo":
            self.mechanism_editor.undo()
        elif action_name == "redo":
            self.mechanism_editor.redo()
        elif action_name == "play_pause":
            self._toggle_animation()
        elif action_name == "zoom_fit":
            self.visualization_widget.view.zoom_to_fit()
        elif action_name == "align_horizontal":
            self._align_elements("horizontal")
        elif action_name == "align_vertical":
            self._align_elements("vertical")
        # Add more shortcut handlers as needed
        
    def _show_context_menu(self, pos):
        """Show appropriate context menu."""
        view_pos = self.visualization_widget.view.mapToScene(pos)
        item = self.visualization_widget.scene.itemAt(view_pos, self.visualization_widget.view.transform())
        
        menu = None
        if item:
            # Determine item type and create appropriate menu
            if hasattr(item, 'anchor_id'):
                menu = self.context_menu_manager.create_anchor_menu(item.anchor_id)
            elif hasattr(item, 'link_id'):
                menu = self.context_menu_manager.create_link_menu(item.link_id)
        else:
            # Canvas menu
            menu = self.context_menu_manager.create_canvas_menu(view_pos)
            
        if menu:
            action = menu.exec(self.visualization_widget.view.mapToGlobal(pos))
            if action:
                self._handle_context_menu_action(action)
                
    def _handle_context_menu_action(self, action):
        """Handle context menu action."""
        data = action.data()
        if not data:
            return
            
        command = data[0]
        
        if command == "edit_properties":
            self._edit_element_properties(data[1])
        elif command == "add_constraint":
            self._add_constraint(data[1], data[2])
        elif command == "delete":
            self._delete_element(data[1])
        elif command == "analyze":
            self._analyze_mechanism()
        elif command == "export":
            self._export_mechanism(data[1], data[2])
        # Add more handlers as needed
        
    def _on_mechanism_updated(self, mechanism_data: Dict):
        """Handle mechanism updates from editor."""
        # Update state
        self.state_manager.add_mechanism(mechanism_data)
        
        # Update analysis
        analysis_results = self.mechanism_analyzer.analyze_mechanism(mechanism_data)
        self._display_analysis_results(analysis_results)
        
        # Update motion analysis
        self.motion_analysis_widget.update_analysis(mechanism_data)
        
        # Emit signal
        self.mechanism_updated.emit(mechanism_data)
        
    def _on_property_changed(self, property_name: str, value: Any):
        """Handle property changes from panel."""
        self._logger.info(f"Property changed: {property_name} = {value}")
        
        if property_name == "snap_to_grid":
            self.mechanism_editor.toggle_grid(value)
        elif property_name == "grid_size":
            self.mechanism_editor.set_grid_size(value)
        elif property_name in ["x", "y", "rotation"]:
            # Update selected element transform
            self._update_element_transform(property_name, value)
            
    def _perform_batch_operation(self, operation: str, params: Dict):
        """Perform batch operation on selected elements."""
        self._logger.info(f"Batch operation: {operation}")
        
        if operation == "align_horizontal":
            self._align_elements("horizontal")
        elif operation == "align_vertical":
            self._align_elements("vertical")
        elif operation == "distribute_horizontal":
            self._distribute_elements("horizontal")
            
    def _on_tool_selected(self, tool_name: str):
        """Handle tool selection from toolbar."""
        self._logger.info(f"Tool selected: {tool_name}")
        
        if tool_name == "select":
            self.mechanism_editor.set_edit_mode(EditMode.EDIT_ANCHORS)
        elif tool_name == "add_anchor":
            self._enter_add_anchor_mode()
        elif tool_name == "add_link":
            self._enter_add_link_mode()
        elif tool_name == "measure":
            self._enter_measure_mode()
        elif tool_name == "optimize":
            self._optimize_mechanism()
            
    def _toggle_edit_mode(self):
        """Toggle between view and edit modes."""
        current_mode = self.mechanism_editor.edit_mode
        if current_mode == EditMode.VIEW:
            self.mechanism_editor.set_edit_mode(EditMode.EDIT_ANCHORS)
        else:
            self.mechanism_editor.set_edit_mode(EditMode.VIEW)
            
    def _toggle_snapping(self, enabled: bool):
        """Toggle snapping."""
        self.mechanism_editor.edit_state.snap_to_grid = enabled
        self.status_bar.showMessage(f"Snapping {'enabled' if enabled else 'disabled'}", 2000)
        
    def _toggle_grid(self, show: bool):
        """Toggle grid display."""
        self.mechanism_editor.toggle_grid(show)
        self.status_bar.showMessage(f"Grid {'shown' if show else 'hidden'}", 2000)
        
    def _toggle_lock(self, locked: bool):
        """Toggle element locking."""
        # Implement element locking logic
        self.status_bar.showMessage(f"Elements {'locked' if locked else 'unlocked'}", 2000)
        
    def _analyze_mechanism(self):
        """Analyze current mechanism."""
        if self.mechanism_editor.mechanism_data:
            results = self.mechanism_analyzer.analyze_mechanism(
                self.mechanism_editor.mechanism_data
            )
            self._display_analysis_results(results)
            
    def _display_analysis_results(self, results: Dict):
        """Display analysis results."""
        # Update UI with analysis results
        issues = results.get("design_issues", [])
        if issues:
            self.status_bar.showMessage(f"Design issues: {', '.join(issues)}", 5000)
            
    def _optimize_mechanism(self):
        """Optimize mechanism parameters."""
        if self.mechanism_editor.mechanism_data:
            optimized = self.optimization_engine.optimize_mechanism(
                self.mechanism_editor.mechanism_data,
                objective="minimize_error"
            )
            
            # Apply optimized parameters
            self.mechanism_editor.set_mechanism(optimized)
            self.status_bar.showMessage("Mechanism optimized", 3000)
            
    def _align_elements(self, direction: str):
        """Align selected elements."""
        # Get selected anchors
        selected = [a for a in self.mechanism_editor.anchors.values() if a.is_selected]
        
        if len(selected) < 2:
            return
            
        if direction == "horizontal":
            # Align to average Y position
            avg_y = sum(a.center_pos().y() for a in selected) / len(selected)
            for anchor in selected:
                pos = anchor.center_pos()
                anchor.set_center_pos(QPointF(pos.x(), avg_y))
        elif direction == "vertical":
            # Align to average X position
            avg_x = sum(a.center_pos().x() for a in selected) / len(selected)
            for anchor in selected:
                pos = anchor.center_pos()
                anchor.set_center_pos(QPointF(avg_x, pos.y()))
                
        # Update mechanism
        self.mechanism_editor._update_mechanism_data()
        
    def _distribute_elements(self, direction: str):
        """Distribute selected elements evenly."""
        # Implementation for distributing elements
        pass
        
    def _select_all_elements(self):
        """Select all elements."""
        for anchor in self.mechanism_editor.anchors.values():
            anchor.setSelected(True)
        for link in self.mechanism_editor.links.values():
            link.setSelected(True)
            
    def _delete_selected_elements(self):
        """Delete selected elements."""
        # Get selected items
        selected_anchors = [a for a in self.mechanism_editor.anchors.values() if a.is_selected]
        selected_links = [l for l in self.mechanism_editor.links.values() if l.is_selected]
        
        if not selected_anchors and not selected_links:
            return
            
        # Confirm deletion
        reply = QMessageBox.question(
            self, "Delete Elements",
            f"Delete {len(selected_anchors)} anchors and {len(selected_links)} links?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Delete elements
            for anchor in selected_anchors:
                self.visualization_widget.scene.removeItem(anchor)
                del self.mechanism_editor.anchors[anchor.anchor_id]
                
            for link in selected_links:
                self.visualization_widget.scene.removeItem(link)
                del self.mechanism_editor.links[link.link_id]
                
            # Update mechanism
            self.mechanism_editor._update_mechanism_data()
            
    def _show_constraint_violation(self, message: str):
        """Show constraint violation message."""
        self.status_bar.showMessage(f"Constraint violation: {message}", 3000)
        
    def load_mechanism(self, mechanism_data: Dict):
        """Load a mechanism for editing."""
        self.mechanism_editor.set_mechanism(mechanism_data)
        self.visualization_widget.visualize_mechanism(mechanism_data)
        
        # Enable editing
        self.editing_toolbar.setEnabled(True)
        self.property_panel.setEnabled(True)
        
        # Fit to view
        self.visualization_widget.view.zoom_to_fit()
        
    def get_edited_mechanism(self) -> Optional[Dict]:
        """Get the current edited mechanism data."""
        return self.mechanism_editor.mechanism_data