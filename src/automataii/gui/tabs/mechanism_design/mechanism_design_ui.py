# MechanismDesignUI
# - Lines: ~400
# - Public API: setup
# - Deps In (Afferent): 1 [MechanismDesignTab]
# - Deps Out (Efferent): 2 [PyQt6, automataii.gui.parametric_editor]
# - Coupling: Low (UI-only, no business logic)
# - Cohesion: Feature (UI setup and styling)
# - Owner: Alan Synn, Reviewers: TBD
# - Last Updated: 2025-01-26

"""
UI setup class for MechanismDesignTab.

This class encapsulates all UI creation, styling, and layout logic,
providing a clean separation between the main tab logic and UI concerns.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QScrollArea,
    QStyle,
    QVBoxLayout,
    QWidget,
)

# Parametric Design System (ULTRATHINK Architecture)
try:
    from automataii.gui.parametric_editor import (
        ParametricEditor, MechanismEditor, FourBarEditor, 
        CamEditor, GearEditor, ParametricHandle
    )
    PARAMETRIC_AVAILABLE = True
except ImportError:
    PARAMETRIC_AVAILABLE = False


class MechanismDesignUI:
    """Handles UI setup for the MechanismDesignTab."""
    
    def __init__(self):
        """Initialize UI class."""
        # UI Elements that will be created
        self.mechanism_layers_list: QListWidget | None = None
        self.recommendation_btn: QPushButton | None = None
        self.play_btn: QPushButton | None = None
        self.stop_btn: QPushButton | None = None
        self.reset_btn: QPushButton | None = None
        self.blueprint_btn: QPushButton | None = None
        self.blueprint_info_label: QLabel | None = None
        
        # Parametric Design Elements (if available)
        self.parametric_edit_btn: QPushButton | None = None
        
        # View Control Elements
        self.zoom_in_btn: QPushButton | None = None
        self.zoom_out_btn: QPushButton | None = None
        self.zoom_fit_btn: QPushButton | None = None
        self.center_character_btn: QPushButton | None = None
        
        # Layout container (for potential recreation)
        self.control_panel: QWidget | None = None
    
    def setup(self, parent_widget):
        """Setup UI - Similar to EditorTab but with mechanism layers instead of parts."""
        main_layout = QHBoxLayout(parent_widget)

        # Left Control Panel (similar to EditorTab)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFixedWidth(300)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        control_panel = QWidget()
        self.control_panel = control_panel  # Store as instance variable for recreation methods
        panel_layout = QVBoxLayout(control_panel)
        panel_layout.setContentsMargins(10, 10, 10, 10)
        panel_layout.setSpacing(15)

        # 1. Parts List Group - EXACT COPY from EditorTab
        layers_group = QGroupBox("1 Parts for Mechanisms")
        layers_group.setStyleSheet("""
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
        """)
        layers_layout = QVBoxLayout(layers_group)
        self.mechanism_layers_list = QListWidget()
        self.mechanism_layers_list.setToolTip("Parts for mechanisms - black: has motion path, gray: no motion path")
        self.mechanism_layers_list.setMinimumHeight(180)
        self.mechanism_layers_list.setStyleSheet("""
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
        """)
        layers_layout.addWidget(self.mechanism_layers_list)
        panel_layout.addWidget(layers_group)

        # 2. Mechanism Generation Group
        generation_group = QGroupBox("2 Mechanism Generation")
        generation_group.setStyleSheet("""
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
        """)
        generation_layout = QVBoxLayout(generation_group)

        self.recommendation_btn = QPushButton("Get Mechanism")
        self.recommendation_btn.setEnabled(False)
        self.recommendation_btn.setToolTip("Get mechanism recommendations based on motion paths")
        self.recommendation_btn.setStyleSheet("""
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
        """)
        generation_layout.addWidget(self.recommendation_btn)

        # Parametric Design Button (ULTRATHINK Architecture)
        if PARAMETRIC_AVAILABLE:
            self.parametric_edit_btn = QPushButton("Parametric Edit")
            self.parametric_edit_btn.setToolTip("Enable interactive parameter editing with drag handles")
            self.parametric_edit_btn.setEnabled(False)  # Enable when mechanisms are loaded
            self.parametric_edit_btn.setStyleSheet("""
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
            """)
            generation_layout.addWidget(self.parametric_edit_btn)


        panel_layout.addWidget(generation_group)

        # 3. Animation Group
        animation_group = QGroupBox("3 Animation")
        animation_group.setStyleSheet("""
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
        """)
        animation_layout = QVBoxLayout(animation_group)

        # Use parent widget's style for the icons
        style = parent_widget.style()
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


        # 5. View Controls Group
        view_controls_group = QGroupBox("5 View Controls")
        view_controls_group.setStyleSheet("""
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
        """)
        view_controls_layout = QVBoxLayout(view_controls_group)

        # Zoom controls
        zoom_controls_layout = QHBoxLayout()
        zoom_controls_layout.setSpacing(6)

        zoom_button_style = """
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

        self.zoom_in_btn = QPushButton("+")
        self.zoom_in_btn.setToolTip("Zoom In")
        self.zoom_in_btn.setStyleSheet(zoom_button_style)
        zoom_controls_layout.addWidget(self.zoom_in_btn)

        self.zoom_out_btn = QPushButton("−")
        self.zoom_out_btn.setToolTip("Zoom Out")
        self.zoom_out_btn.setStyleSheet(zoom_button_style)
        zoom_controls_layout.addWidget(self.zoom_out_btn)

        self.zoom_fit_btn = QPushButton("⌖")
        self.zoom_fit_btn.setToolTip("Zoom to Fit")
        self.zoom_fit_btn.setStyleSheet(zoom_button_style)
        zoom_controls_layout.addWidget(self.zoom_fit_btn)

        # Center on Character button
        self.center_character_btn = QPushButton("⎈")
        self.center_character_btn.setToolTip("Center on Character")
        self.center_character_btn.setStyleSheet(zoom_button_style)
        zoom_controls_layout.addWidget(self.center_character_btn)

        view_controls_layout.addLayout(zoom_controls_layout)
        panel_layout.addWidget(view_controls_group)

        panel_layout.addStretch(1)

        control_panel.setMinimumWidth(280)
        scroll_area.setWidget(control_panel)
        main_layout.addWidget(scroll_area)
        
        # Note: The mechanism_view should be added by the parent after calling this method