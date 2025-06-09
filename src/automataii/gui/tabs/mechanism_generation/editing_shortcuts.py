"""Keyboard shortcuts and context menu support for mechanism editing."""

from typing import Dict, List, Optional, Callable
from PyQt6.QtCore import Qt, QObject, pyqtSignal
from PyQt6.QtGui import QKeySequence, QAction, QKeyEvent
from PyQt6.QtWidgets import QMenu, QWidget


class ShortcutManager(QObject):
    """Manages keyboard shortcuts for mechanism editing."""
    
    # Signals
    shortcut_triggered = pyqtSignal(str)  # action_name
    
    def __init__(self, parent_widget: QWidget):
        super().__init__(parent_widget)
        self.parent_widget = parent_widget
        self.shortcuts: Dict[str, QAction] = {}
        self._create_shortcuts()
        
    def _create_shortcuts(self):
        """Create all keyboard shortcuts."""
        shortcuts_config = [
            # Edit mode shortcuts
            ("toggle_edit_mode", "Toggle Edit Mode", "E"),
            ("select_all", "Select All", "Ctrl+A"),
            ("deselect_all", "Deselect All", "Ctrl+D"),
            ("delete_selected", "Delete Selected", "Delete"),
            
            # Transform shortcuts
            ("move_mode", "Move Mode", "M"),
            ("rotate_mode", "Rotate Mode", "R"),
            ("scale_mode", "Scale Mode", "S"),
            
            # Snapping shortcuts
            ("toggle_grid_snap", "Toggle Grid Snap", "G"),
            ("toggle_angle_snap", "Toggle Angle Snap", "A"),
            ("increase_grid_size", "Increase Grid Size", "Ctrl+Plus"),
            ("decrease_grid_size", "Decrease Grid Size", "Ctrl+Minus"),
            
            # View shortcuts
            ("zoom_in", "Zoom In", "Ctrl+Plus"),
            ("zoom_out", "Zoom Out", "Ctrl+Minus"),
            ("zoom_fit", "Zoom to Fit", "Ctrl+0"),
            ("pan_mode", "Pan Mode", "Space"),
            
            # Constraint shortcuts
            ("add_constraint", "Add Constraint", "C"),
            ("toggle_constraints", "Toggle Constraints Display", "Ctrl+C"),
            
            # Animation shortcuts
            ("play_pause", "Play/Pause Animation", "Space"),
            ("stop_animation", "Stop Animation", "Escape"),
            ("step_forward", "Step Forward", "Right"),
            ("step_backward", "Step Backward", "Left"),
            
            # History shortcuts
            ("undo", "Undo", "Ctrl+Z"),
            ("redo", "Redo", "Ctrl+Shift+Z"),
            
            # Alignment shortcuts
            ("align_horizontal", "Align Horizontal", "Ctrl+H"),
            ("align_vertical", "Align Vertical", "Ctrl+V"),
            ("distribute_horizontal", "Distribute Horizontal", "Ctrl+Shift+H"),
            ("distribute_vertical", "Distribute Vertical", "Ctrl+Shift+V"),
            
            # Copy/Paste shortcuts
            ("copy", "Copy", "Ctrl+C"),
            ("paste", "Paste", "Ctrl+V"),
            ("duplicate", "Duplicate", "Ctrl+D"),
        ]
        
        for action_name, text, shortcut in shortcuts_config:
            action = QAction(text, self.parent_widget)
            action.setShortcut(QKeySequence(shortcut))
            action.triggered.connect(lambda checked, name=action_name: self.shortcut_triggered.emit(name))
            self.parent_widget.addAction(action)
            self.shortcuts[action_name] = action
            
    def set_shortcut_enabled(self, action_name: str, enabled: bool):
        """Enable or disable a shortcut."""
        if action_name in self.shortcuts:
            self.shortcuts[action_name].setEnabled(enabled)
            
    def update_shortcut(self, action_name: str, new_shortcut: str):
        """Update shortcut key binding."""
        if action_name in self.shortcuts:
            self.shortcuts[action_name].setShortcut(QKeySequence(new_shortcut))


class ContextMenuManager:
    """Manages context menus for mechanism editing."""
    
    def __init__(self):
        self.menu_actions: Dict[str, List[QAction]] = {}
        
    def create_anchor_menu(self, anchor_id: str) -> QMenu:
        """Create context menu for anchor points."""
        menu = QMenu()
        menu.setStyleSheet(self._get_menu_style())
        
        # Basic operations
        edit_action = QAction("Edit Properties", menu)
        edit_action.setData(("edit_properties", anchor_id))
        menu.addAction(edit_action)
        
        menu.addSeparator()
        
        # Constraints
        constraint_menu = menu.addMenu("Add Constraint")
        
        fixed_action = QAction("Fixed Position", constraint_menu)
        fixed_action.setData(("add_constraint", "fixed", anchor_id))
        constraint_menu.addAction(fixed_action)
        
        distance_action = QAction("Fixed Distance", constraint_menu)
        distance_action.setData(("add_constraint", "distance", anchor_id))
        constraint_menu.addAction(distance_action)
        
        angle_action = QAction("Fixed Angle", constraint_menu)
        angle_action.setData(("add_constraint", "angle", anchor_id))
        constraint_menu.addAction(angle_action)
        
        menu.addSeparator()
        
        # Transform operations
        snap_grid_action = QAction("Snap to Grid", menu)
        snap_grid_action.setData(("snap_to_grid", anchor_id))
        menu.addAction(snap_grid_action)
        
        round_position_action = QAction("Round Position", menu)
        round_position_action.setData(("round_position", anchor_id))
        menu.addAction(round_position_action)
        
        menu.addSeparator()
        
        # Delete
        delete_action = QAction("Delete", menu)
        delete_action.setData(("delete", anchor_id))
        delete_action.setShortcut("Delete")
        menu.addAction(delete_action)
        
        return menu
        
    def create_link_menu(self, link_id: str) -> QMenu:
        """Create context menu for links."""
        menu = QMenu()
        menu.setStyleSheet(self._get_menu_style())
        
        # Properties
        properties_action = QAction("Edit Properties", menu)
        properties_action.setData(("edit_properties", link_id))
        menu.addAction(properties_action)
        
        menu.addSeparator()
        
        # Length operations
        set_length_action = QAction("Set Length...", menu)
        set_length_action.setData(("set_length", link_id))
        menu.addAction(set_length_action)
        
        lock_length_action = QAction("Lock Length", menu)
        lock_length_action.setCheckable(True)
        lock_length_action.setData(("lock_length", link_id))
        menu.addAction(lock_length_action)
        
        menu.addSeparator()
        
        # Visual options
        visual_menu = menu.addMenu("Visual Style")
        
        solid_action = QAction("Solid", visual_menu)
        solid_action.setData(("set_style", "solid", link_id))
        visual_menu.addAction(solid_action)
        
        dashed_action = QAction("Dashed", visual_menu)
        dashed_action.setData(("set_style", "dashed", link_id))
        visual_menu.addAction(dashed_action)
        
        # Width submenu
        width_menu = visual_menu.addMenu("Width")
        for width in [2, 4, 6, 8]:
            width_action = QAction(f"{width}px", width_menu)
            width_action.setData(("set_width", width, link_id))
            width_menu.addAction(width_action)
            
        menu.addSeparator()
        
        # Delete
        delete_action = QAction("Delete", menu)
        delete_action.setData(("delete", link_id))
        menu.addAction(delete_action)
        
        return menu
        
    def create_mechanism_menu(self, mechanism_type: str) -> QMenu:
        """Create context menu for entire mechanism."""
        menu = QMenu()
        menu.setStyleSheet(self._get_menu_style())
        
        # Analysis
        analyze_action = QAction("Analyze Mechanism", menu)
        analyze_action.setData(("analyze", mechanism_type))
        menu.addAction(analyze_action)
        
        optimize_action = QAction("Optimize...", menu)
        optimize_action.setData(("optimize", mechanism_type))
        menu.addAction(optimize_action)
        
        menu.addSeparator()
        
        # Animation
        animate_action = QAction("Animate", menu)
        animate_action.setData(("animate", mechanism_type))
        menu.addAction(animate_action)
        
        trace_action = QAction("Show Motion Trace", menu)
        trace_action.setCheckable(True)
        trace_action.setData(("toggle_trace", mechanism_type))
        menu.addAction(trace_action)
        
        menu.addSeparator()
        
        # Export
        export_menu = menu.addMenu("Export")
        
        svg_action = QAction("Export as SVG", export_menu)
        svg_action.setData(("export", "svg", mechanism_type))
        export_menu.addAction(svg_action)
        
        dxf_action = QAction("Export as DXF", export_menu)
        dxf_action.setData(("export", "dxf", mechanism_type))
        export_menu.addAction(dxf_action)
        
        params_action = QAction("Export Parameters", export_menu)
        params_action.setData(("export", "params", mechanism_type))
        export_menu.addAction(params_action)
        
        menu.addSeparator()
        
        # Reset
        reset_action = QAction("Reset to Original", menu)
        reset_action.setData(("reset", mechanism_type))
        menu.addAction(reset_action)
        
        return menu
        
    def create_canvas_menu(self, pos) -> QMenu:
        """Create context menu for empty canvas area."""
        menu = QMenu()
        menu.setStyleSheet(self._get_menu_style())
        
        # Add elements
        add_menu = menu.addMenu("Add")
        
        add_anchor_action = QAction("Add Anchor", add_menu)
        add_anchor_action.setData(("add_anchor", pos))
        add_menu.addAction(add_anchor_action)
        
        add_link_action = QAction("Add Link", add_menu)
        add_link_action.setData(("add_link", pos))
        add_menu.addAction(add_link_action)
        
        menu.addSeparator()
        
        # View options
        view_menu = menu.addMenu("View")
        
        grid_action = QAction("Show Grid", view_menu)
        grid_action.setCheckable(True)
        grid_action.setChecked(True)
        grid_action.setData(("toggle_grid",))
        view_menu.addAction(grid_action)
        
        rulers_action = QAction("Show Rulers", view_menu)
        rulers_action.setCheckable(True)
        rulers_action.setData(("toggle_rulers",))
        view_menu.addAction(rulers_action)
        
        measurements_action = QAction("Show Measurements", view_menu)
        measurements_action.setCheckable(True)
        measurements_action.setChecked(True)
        measurements_action.setData(("toggle_measurements",))
        view_menu.addAction(measurements_action)
        
        menu.addSeparator()
        
        # Paste
        paste_action = QAction("Paste", menu)
        paste_action.setData(("paste", pos))
        paste_action.setShortcut("Ctrl+V")
        paste_action.setEnabled(False)  # Enable when clipboard has content
        menu.addAction(paste_action)
        
        menu.addSeparator()
        
        # Select all
        select_all_action = QAction("Select All", menu)
        select_all_action.setData(("select_all",))
        select_all_action.setShortcut("Ctrl+A")
        menu.addAction(select_all_action)
        
        return menu
        
    def _get_menu_style(self) -> str:
        """Get stylesheet for menus."""
        return """
            QMenu {
                background-color: white;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 3px;
            }
            QMenu::item:selected {
                background-color: #e3f2fd;
                color: #1976d2;
            }
            QMenu::separator {
                height: 1px;
                background-color: #e0e0e0;
                margin: 4px 10px;
            }
            QMenu::icon {
                margin-right: 8px;
            }
        """


class EditingToolbar(QWidget):
    """Toolbar for quick access to editing tools."""
    
    # Signals
    tool_selected = pyqtSignal(str)  # tool_name
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        
    def _init_ui(self):
        """Initialize UI."""
        from PyQt6.QtWidgets import QHBoxLayout, QToolButton, QButtonGroup
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)
        
        self.tool_group = QButtonGroup(self)
        
        # Tool definitions
        tools = [
            ("select", "Select", "Select and move elements"),
            ("add_anchor", "Add Anchor", "Add new anchor point"),
            ("add_link", "Add Link", "Add new link between anchors"),
            ("measure", "Measure", "Measure distances and angles"),
            ("constraint", "Constraint", "Add or edit constraints"),
            ("optimize", "Optimize", "Optimize mechanism parameters"),
        ]
        
        for tool_id, text, tooltip in tools:
            btn = QToolButton()
            btn.setText(text)
            btn.setToolTip(tooltip)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, tid=tool_id: self.tool_selected.emit(tid))
            
            self.tool_group.addButton(btn)
            layout.addWidget(btn)
            
            if tool_id == "select":
                btn.setChecked(True)
                
        layout.addStretch()
        
        # Additional quick actions
        layout.addSeparator()
        
        # Snap toggle
        self.snap_btn = QToolButton()
        self.snap_btn.setText("Snap")
        self.snap_btn.setCheckable(True)
        self.snap_btn.setChecked(True)
        self.snap_btn.setToolTip("Toggle snapping")
        layout.addWidget(self.snap_btn)
        
        # Grid toggle
        self.grid_btn = QToolButton()
        self.grid_btn.setText("Grid")
        self.grid_btn.setCheckable(True)
        self.grid_btn.setChecked(True)
        self.grid_btn.setToolTip("Toggle grid display")
        layout.addWidget(self.grid_btn)
        
        # Lock toggle
        self.lock_btn = QToolButton()
        self.lock_btn.setText("Lock")
        self.lock_btn.setCheckable(True)
        self.lock_btn.setToolTip("Lock selected elements")
        layout.addWidget(self.lock_btn)
        
    def set_active_tool(self, tool_name: str):
        """Set the active tool."""
        for btn in self.tool_group.buttons():
            if btn.text().lower() == tool_name.lower():
                btn.setChecked(True)
                break