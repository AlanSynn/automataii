"""
UI Layout Manager for MechanismDesignTab.

Extracted from the monolithic MechanismDesignTab class to achieve single responsibility
for UI widget creation, styling, and layout management.

ULTRATHINK Architecture: Composition over inheritance, clear separation of concerns.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QGroupBox, QHBoxLayout, QLabel, QListWidget, QPushButton,
    QScrollArea, QStyle, QVBoxLayout, QWidget, QSplitter, QSizePolicy
)
from automataii.presentation.qt.views.editor_view import EditorView
from PyQt6.QtWidgets import QGraphicsScene


class MechanismDesignTabLayout:
    """
    Manages UI layout and widget positioning for MechanismDesignTab.
    
    Responsibilities:
    - Widget creation and styling
    - Layout management and positioning
    - Control panel organization
    - Button styling and initial states
    
    Does NOT handle:
    - Business logic
    - Event handling
    - Animation control
    - Data management
    """
    
    def __init__(self):
        """Initialize the layout manager."""
        self._created_widgets = {}  # Track created widgets for cleanup
        
    def setup_main_layout(self, tab_widget) -> None:
        """
        Setup the main layout for the mechanism design tab.
        
        Args:
            tab_widget: The MechanismDesignTab instance to setup
        """
        # Store parent widget for style access
        self._parent_widget = tab_widget
        
        # Clear existing layout if any to prevent conflicts
        existing_layout = tab_widget.layout()
        if existing_layout:
            # Clear the existing layout
            while existing_layout.count():
                child = existing_layout.takeAt(0)
                if child.widget():
                    child.widget().setParent(None)
            # Delete the old layout
            existing_layout.setParent(None)
        
        # Set layout on the tab widget with a splitter
        main_layout = QHBoxLayout()
        tab_widget.setLayout(main_layout)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Create and add control panel (left side, fixed width)
        control_panel_area = self._create_control_panel_area()
        control_panel_area.setMinimumWidth(300)
        control_panel_area.setMaximumWidth(300)
        control_panel_area.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        splitter.addWidget(control_panel_area)

        # Create mechanism scene and view (right side, resizable)
        mechanism_scene = QGraphicsScene(tab_widget)
        # Performance: reduce indexing overhead for many moving items
        try:
            mechanism_scene.setItemIndexMethod(QGraphicsScene.ItemIndexMethod.NoIndex)
        except Exception:
            pass
        mechanism_view = EditorView(mechanism_scene, tab_widget, mechanism_mode=True)
        
        # Store references on tab_widget for backward compatibility
        tab_widget.mechanism_scene = mechanism_scene
        tab_widget.mechanism_view = mechanism_view
        
        splitter.addWidget(mechanism_view)
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([300, 900])

        main_layout.addWidget(splitter)
        
    def _create_control_panel_area(self) -> QScrollArea:
        """Create the scrollable control panel area."""
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFixedWidth(300)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        control_panel = self._create_control_panel()
        scroll_area.setWidget(control_panel)
        
        return scroll_area
        
    def _create_control_panel(self) -> QWidget:
        """Create the main control panel with all sections."""
        control_panel = QWidget()
        panel_layout = QVBoxLayout(control_panel)
        panel_layout.setContentsMargins(10, 10, 10, 10)
        panel_layout.setSpacing(15)
        
        # 1. Parts List Group
        parts_group = self._create_parts_group()
        panel_layout.addWidget(parts_group)
        
        # 2. Mechanism Generation Group  
        generation_group = self._create_mechanism_generation_group()
        panel_layout.addWidget(generation_group)
        
        # 3. Animation Group
        animation_group = self._create_animation_group()
        panel_layout.addWidget(animation_group)
        
        # 4. Blueprint Export Group
        export_group = self._create_blueprint_export_group()
        panel_layout.addWidget(export_group)
        
        # 5. View Controls Group
        view_controls_group = self._create_view_controls_group()
        panel_layout.addWidget(view_controls_group)
        
        panel_layout.addStretch(1)
        control_panel.setMinimumWidth(280)
        
        return control_panel
        
    def _create_parts_group(self) -> QGroupBox:
        """Create the parts list group."""
        parts_group = QGroupBox("1 Parts for Mechanisms")
        parts_group.setStyleSheet(self._get_group_style())
        
        parts_layout = QVBoxLayout(parts_group)
        
        # Create mechanism layers list
        mechanism_layers_list = QListWidget()
        mechanism_layers_list.setToolTip("Parts for mechanisms - black: has motion path, gray: no motion path")
        mechanism_layers_list.setMinimumHeight(180)
        mechanism_layers_list.setStyleSheet(self._get_list_widget_style())
        
        # Store reference for external access
        self._created_widgets['mechanism_layers_list'] = mechanism_layers_list
        
        parts_layout.addWidget(mechanism_layers_list)
        return parts_group
        
    def _create_mechanism_generation_group(self) -> QGroupBox:
        """Create the mechanism generation group."""
        generation_group = QGroupBox("2 Mechanism Generation")
        generation_group.setStyleSheet(self._get_group_style())
        generation_layout = QVBoxLayout(generation_group)
        
        # Get Mechanism button
        recommendation_btn = QPushButton("Get Mechanism")
        recommendation_btn.setEnabled(False)
        recommendation_btn.setToolTip("Get mechanism recommendations based on motion paths")
        recommendation_btn.setStyleSheet(self._get_primary_button_style())
        generation_layout.addWidget(recommendation_btn)
        self._created_widgets['recommendation_btn'] = recommendation_btn
        
        # Parametric Design Button (conditionally created)
        try:
            from automataii.presentation.qt.parametric_editor import ParametricEditor
            PARAMETRIC_AVAILABLE = True
        except ImportError:
            PARAMETRIC_AVAILABLE = False
            
        if PARAMETRIC_AVAILABLE:
            parametric_edit_btn = QPushButton("Parametric Edit")
            parametric_edit_btn.setToolTip("Enable interactive parameter editing with drag handles")
            parametric_edit_btn.setEnabled(False)
            parametric_edit_btn.setStyleSheet(self._get_secondary_button_style())
            generation_layout.addWidget(parametric_edit_btn)
            self._created_widgets['parametric_edit_btn'] = parametric_edit_btn
            
        else:
            # Store None references for parametric features
            self._created_widgets['parametric_edit_btn'] = None
            
        return generation_group
        
    def _create_animation_group(self) -> QGroupBox:
        """Create the animation control group."""
        animation_group = QGroupBox("3 Animation")
        animation_group.setStyleSheet(self._get_group_style())
        animation_layout = QVBoxLayout(animation_group)
        
        # Animation buttons layout
        anim_button_layout = QHBoxLayout()
        anim_button_layout.setSpacing(12)
        
        # Get standard icons from parent widget style
        style = self._parent_widget.style()
        
        # Play button
        play_btn = QPushButton()
        play_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        play_btn.setToolTip("Play Animation")
        play_btn.setEnabled(False)
        self._created_widgets['play_btn'] = play_btn
        
        # Stop button  
        stop_btn = QPushButton()
        stop_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaStop))
        stop_btn.setToolTip("Stop Animation")
        stop_btn.setEnabled(False)
        self._created_widgets['stop_btn'] = stop_btn
        
        # Reset button
        reset_btn = QPushButton()
        reset_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        reset_btn.setToolTip("Reset Animation")
        reset_btn.setEnabled(False)
        self._created_widgets['reset_btn'] = reset_btn
        
        anim_button_layout.addStretch()
        anim_button_layout.addWidget(play_btn)
        anim_button_layout.addWidget(stop_btn)
        anim_button_layout.addWidget(reset_btn)
        anim_button_layout.addStretch()
        
        animation_layout.addLayout(anim_button_layout)
        return animation_group
        
    def _create_blueprint_export_group(self) -> QGroupBox:
        """Create the blueprint export group."""
        export_group = QGroupBox("4 Blueprint Export")
        export_group.setStyleSheet(self._get_group_style())
        export_layout = QVBoxLayout(export_group)
        
        # Export Blueprint button
        blueprint_btn = QPushButton("Export Blueprint")
        blueprint_btn.setEnabled(False)
        blueprint_btn.setToolTip("Export character parts and mechanisms as SVG blueprint")
        blueprint_btn.setStyleSheet(self._get_accent_button_style())
        export_layout.addWidget(blueprint_btn)
        self._created_widgets['blueprint_btn'] = blueprint_btn
        
        # Info label
        blueprint_info_label = QLabel("Exports to single large-format blueprint (1200×1600mm)")
        blueprint_info_label.setStyleSheet("""
            QLabel {
                color: #666;
                font-size: 10px;
                font-style: italic;
                padding: 2px;
            }
        """)
        export_layout.addWidget(blueprint_info_label)
        self._created_widgets['blueprint_info_label'] = blueprint_info_label
        
        return export_group
        
    def _create_view_controls_group(self) -> QGroupBox:
        """Create the view controls group."""
        view_controls_group = QGroupBox("5 View Controls")
        view_controls_group.setStyleSheet(self._get_group_style())
        view_controls_layout = QVBoxLayout(view_controls_group)
        
        # Zoom controls layout
        zoom_controls_layout = QHBoxLayout()
        zoom_controls_layout.setSpacing(6)
        
        zoom_button_style = self._get_zoom_button_style()
        
        # Zoom buttons
        zoom_in_btn = QPushButton("+")
        zoom_in_btn.setToolTip("Zoom In")
        zoom_in_btn.setStyleSheet(zoom_button_style)
        self._created_widgets['zoom_in_btn'] = zoom_in_btn
        
        zoom_out_btn = QPushButton("−")
        zoom_out_btn.setToolTip("Zoom Out")
        zoom_out_btn.setStyleSheet(zoom_button_style)
        self._created_widgets['zoom_out_btn'] = zoom_out_btn
        
        zoom_fit_btn = QPushButton("⌖")
        zoom_fit_btn.setToolTip("Zoom to Fit")
        zoom_fit_btn.setStyleSheet(zoom_button_style)
        self._created_widgets['zoom_fit_btn'] = zoom_fit_btn
        
        center_character_btn = QPushButton("⎈")
        center_character_btn.setToolTip("Center on Character")
        center_character_btn.setStyleSheet(zoom_button_style)
        self._created_widgets['center_character_btn'] = center_character_btn
        
        zoom_controls_layout.addWidget(zoom_in_btn)
        zoom_controls_layout.addWidget(zoom_out_btn)
        zoom_controls_layout.addWidget(zoom_fit_btn)
        zoom_controls_layout.addWidget(center_character_btn)
        
        view_controls_layout.addLayout(zoom_controls_layout)
        return view_controls_group
        
    def get_widget(self, widget_name: str):
        """
        Get a created widget by name.
        
        Args:
            widget_name: Name of the widget to retrieve
            
        Returns:
            The widget instance or None if not found
        """
        return self._created_widgets.get(widget_name)
        
    def get_all_widgets(self) -> dict:
        """Get all created widgets."""
        return self._created_widgets.copy()
        
    # =================== STYLING METHODS ===================
    
    def _get_group_style(self) -> str:
        """Get standard group box styling."""
        return """
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
        
    def _get_list_widget_style(self) -> str:
        """Get list widget styling."""
        return """
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
            QListWidget::item:selected:!active {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #0078D7, stop: 1 #005a9e);
                color: white;
                border: 1px solid #004578;
            }
            QListWidget::item:hover {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
            }
        """
        
    def _get_primary_button_style(self) -> str:
        """Get primary button styling (green)."""
        return """
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 13px;
                font-weight: normal;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: #229954;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
                color: #7f8c8d;
            }
        """
        
    def _get_secondary_button_style(self) -> str:
        """Get secondary button styling (blue)."""
        return """
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 13px;
                font-weight: normal;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
                color: #7f8c8d;
            }
        """
        
    def _get_success_button_style(self) -> str:
        """Get success button styling (green, smaller)."""
        return """
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: normal;
                min-height: 16px;
            }
            QPushButton:hover {
                background-color: #229954;
            }
        """
        
    def _get_warning_button_style(self) -> str:
        """Get warning button styling (orange, smaller)."""
        return """
            QPushButton {
                background-color: #e67e22;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: normal;
                min-height: 16px;
            }
            QPushButton:hover {
                background-color: #d35400;
            }
        """
        
    def _get_accent_button_style(self) -> str:
        """Get accent button styling (purple)."""
        return """
            QPushButton {
                background-color: #8e44ad;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 13px;
                font-weight: normal;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: #7d3c98;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
                color: #7f8c8d;
            }
        """
        
    def _get_zoom_button_style(self) -> str:
        """Get zoom button styling."""
        return """
            QPushButton {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                padding: 4px 8px;
                font-weight: bold;
                color: #495057;
                min-height: 22px;
                min-width: 30px;
                font-size: 10pt;
            }
            QPushButton:hover {
                background-color: #e9ecef;
                border-color: #adb5bd;
            }
            QPushButton:pressed {
                background-color: #dee2e6;
                border-color: #6c757d;
            }
        """
