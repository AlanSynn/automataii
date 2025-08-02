# src/automataii/ui/tabs/editor/ui_panel.py

import logging

from PyQt6.QtCore import Qt, pyqtSignal
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
)

from automataii.ui.design_system import design_system

logger = logging.getLogger(__name__)


class EditorControlPanel(QWidget):
    """The control panel for the EditorTab."""

    part_selected = pyqtSignal(str)
    start_drawing_clicked = pyqtSignal(bool)
    clear_path_clicked = pyqtSignal()
    path_closed_changed = pyqtSignal(bool)  # New signal for open/closed path
    play_clicked = pyqtSignal()
    stop_clicked = pyqtSignal()
    reset_clicked = pyqtSignal()
    smoothness_changed = pyqtSignal(int)
    zoom_in_clicked = pyqtSignal()
    zoom_out_clicked = pyqtSignal()
    zoom_fit_clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._init_ui()
        self._connect_signals()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            design_system.spacing.md,
            design_system.spacing.md,
            design_system.spacing.md,
            design_system.spacing.md
        )
        layout.setSpacing(design_system.spacing.md)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFixedWidth(320)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet(f"""
            QScrollArea {{
                background-color: {design_system.colors.surface};
                border: none;
                border-radius: 8px;
            }}
        """)
        design_system.apply_shadow(scroll_area, design_system.elevation.level_1)

        control_panel = QWidget()
        control_panel.setStyleSheet(f"background-color: {design_system.colors.surface};")
        panel_layout = QVBoxLayout(control_panel)
        panel_layout.setSpacing(design_system.spacing.lg)

        self._create_parts_group(panel_layout)
        self._create_motion_path_group(panel_layout)
        self._create_animation_group(panel_layout)
        self._create_view_controls_group(panel_layout)

        panel_layout.addStretch(1)
        control_panel.setMinimumWidth(300)
        scroll_area.setWidget(control_panel)
        layout.addWidget(scroll_area)

    def _create_parts_group(self, layout: QVBoxLayout) -> None:
        parts_group = QGroupBox("1. Parts")
        parts_group.setFont(design_system.get_font("title_medium"))
        parts_layout = QVBoxLayout(parts_group)
        parts_layout.setSpacing(design_system.spacing.sm)
        
        self.parts_list = QListWidget()
        self.parts_list.setToolTip("List of loaded character parts")
        self.parts_list.setMinimumHeight(180)
        self.parts_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {design_system.colors.background};
                border: 1px solid {design_system.colors.neutral_200};
                border-radius: 4px;
                padding: {design_system.spacing.xs}px;
            }}
            QListWidget::item {{
                padding: {design_system.spacing.sm}px;
                border-radius: 4px;
            }}
            QListWidget::item:selected {{
                background-color: {design_system.colors.primary};
                color: {design_system.colors.on_primary};
            }}
            QListWidget::item:hover:!selected {{
                background-color: {design_system.colors.neutral_100};
            }}
        """)
        parts_layout.addWidget(self.parts_list)
        layout.addWidget(parts_group)

    def _create_motion_path_group(self, layout: QVBoxLayout) -> None:
        motion_path_group = QGroupBox("2. Motion Path")
        motion_path_group.setFont(design_system.get_font("title_medium"))
        motion_path_layout = QVBoxLayout(motion_path_group)
        motion_path_layout.setSpacing(design_system.spacing.sm)

        self.motion_path_status_label = QLabel("Select a part")
        self.motion_path_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.motion_path_status_label.setFont(design_system.get_font("body_medium"))
        self.motion_path_status_label.setStyleSheet(f"""
            padding: {design_system.spacing.sm}px;
            background-color: {design_system.colors.neutral_100};
            border-radius: 4px;
            color: {design_system.colors.neutral_600};
        """)
        motion_path_layout.addWidget(self.motion_path_status_label)

        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(design_system.spacing.sm)
        
        # Create Start Drawing button with explicit styling
        self.define_motion_path_btn = QPushButton("Start Drawing")
        self.define_motion_path_btn.setCheckable(True)
        self.define_motion_path_btn.setMinimumHeight(36)
        self.define_motion_path_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {design_system.colors.primary};
                color: {design_system.colors.on_primary};
                border: none;
                border-radius: 4px;
                padding: {design_system.spacing.sm}px {design_system.spacing.md}px;
                font-weight: 500;
                font-size: 14px;
                min-width: 100px;
            }}
            QPushButton:hover {{
                background-color: {design_system.colors.primary_variant};
            }}
            QPushButton:checked {{
                background-color: {design_system.colors.secondary};
                color: {design_system.colors.on_secondary};
            }}
            QPushButton:disabled {{
                background-color: {design_system.colors.neutral_300};
                color: {design_system.colors.neutral_500};
            }}
        """)
        
        # Create Clear button with explicit styling
        self.clear_motion_path_btn = QPushButton("Clear")
        self.clear_motion_path_btn.setMinimumHeight(36)
        self.clear_motion_path_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {design_system.colors.surface};
                color: {design_system.colors.primary};
                border: 1px solid {design_system.colors.primary};
                border-radius: 4px;
                padding: {design_system.spacing.sm}px {design_system.spacing.md}px;
                font-weight: 500;
                font-size: 14px;
                min-width: 80px;
            }}
            QPushButton:hover {{
                background-color: {design_system.colors.primary};
                color: {design_system.colors.on_primary};
            }}
            QPushButton:disabled {{
                background-color: {design_system.colors.neutral_200};
                color: {design_system.colors.neutral_400};
                border-color: {design_system.colors.neutral_300};
            }}
        """)
        
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.define_motion_path_btn)
        buttons_layout.addWidget(self.clear_motion_path_btn)
        buttons_layout.addStretch()
        motion_path_layout.addLayout(buttons_layout)

        self.motion_path_info_label = QLabel(
            "Click points in the view to draw path. Click 'Stop Drawing' when done."
        )
        self.motion_path_info_label.setWordWrap(True)
        self.motion_path_info_label.setVisible(False)
        self.motion_path_info_label.setFont(design_system.get_font("body_small"))
        self.motion_path_info_label.setStyleSheet(f"""
            color: {design_system.colors.info};
            padding: {design_system.spacing.sm}px;
            background-color: {design_system.colors.info}10;
            border-radius: 4px;
        """)
        motion_path_layout.addWidget(self.motion_path_info_label)

        smoothness_layout = QHBoxLayout()
        smoothness_layout.setSpacing(design_system.spacing.sm)
        
        smoothness_label = QLabel("Smoothness:")
        smoothness_label.setFont(design_system.get_font("body_medium"))
        smoothness_layout.addWidget(smoothness_label)
        
        self.smoothness_slider = QSlider(Qt.Orientation.Horizontal)
        self.smoothness_slider.setRange(0, 100)
        self.smoothness_slider.setValue(50)
        self.smoothness_slider.setEnabled(False)
        self.smoothness_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                background-color: {design_system.colors.neutral_200};
                height: 6px;
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background-color: {design_system.colors.primary};
                width: 16px;
                height: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }}
            QSlider::handle:horizontal:hover {{
                background-color: {design_system.colors.primary_variant};
            }}
        """)
        smoothness_layout.addWidget(self.smoothness_slider)
        
        self.smoothness_value_label = QLabel("50%")
        self.smoothness_value_label.setFont(design_system.get_font("body_medium"))
        self.smoothness_value_label.setMinimumWidth(40)
        smoothness_layout.addWidget(self.smoothness_value_label)
        motion_path_layout.addLayout(smoothness_layout)

        # Add open/closed path option
        path_options_layout = QHBoxLayout()
        self.closed_path_checkbox = QCheckBox("Closed Path")
        self.closed_path_checkbox.setToolTip(
            "Create a closed loop that returns to the starting point"
        )
        self.closed_path_checkbox.setChecked(False)
        self.closed_path_checkbox.setFont(design_system.get_font("body_medium"))
        path_options_layout.addWidget(self.closed_path_checkbox)
        path_options_layout.addStretch()
        motion_path_layout.addLayout(path_options_layout)

        layout.addWidget(motion_path_group)

    def _create_animation_group(self, layout: QVBoxLayout) -> None:
        animation_group = QGroupBox("3. Animation")
        animation_group.setFont(design_system.get_font("title_medium"))
        animation_layout = QVBoxLayout(animation_group)
        animation_layout.setSpacing(design_system.spacing.sm)

        self.animation_status_label = QLabel("No motion paths defined")
        self.animation_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.animation_status_label.setFont(design_system.get_font("body_medium"))
        self.animation_status_label.setStyleSheet(f"""
            padding: {design_system.spacing.sm}px;
            background-color: {design_system.colors.neutral_100};
            border-radius: 4px;
            color: {design_system.colors.neutral_600};
        """)
        animation_layout.addWidget(self.animation_status_label)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(design_system.spacing.sm)
        
        style = self.style()
        self.play_btn = QPushButton(style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay), "Play")
        self.stop_btn = QPushButton(style.standardIcon(QStyle.StandardPixmap.SP_MediaStop), "Stop")
        self.reset_sim_btn = QPushButton(
            style.standardIcon(QStyle.StandardPixmap.SP_BrowserReload), "Reset"
        )
        
        # Style animation buttons
        for btn in [self.play_btn, self.stop_btn, self.reset_sim_btn]:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {design_system.colors.primary};
                    color: {design_system.colors.on_primary};
                    border: none;
                    border-radius: 4px;
                    padding: {design_system.spacing.sm}px {design_system.spacing.md}px;
                    font-weight: 500;
                    min-height: 32px;
                }}
                QPushButton:hover {{
                    background-color: {design_system.colors.primary_variant};
                }}
                QPushButton:pressed {{
                    background-color: {design_system.colors.primary_variant};
                }}
                QPushButton:disabled {{
                    background-color: {design_system.colors.neutral_300};
                    color: {design_system.colors.neutral_500};
                }}
            """)
        
        self.stop_btn.setEnabled(False)
        self.reset_sim_btn.setEnabled(False)

        button_layout.addStretch()
        button_layout.addWidget(self.play_btn)
        button_layout.addWidget(self.stop_btn)
        button_layout.addWidget(self.reset_sim_btn)
        button_layout.addStretch()
        animation_layout.addLayout(button_layout)
        layout.addWidget(animation_group)

    def _create_view_controls_group(self, layout: QVBoxLayout) -> None:
        view_controls_group = QGroupBox("4. View Controls")
        view_controls_group.setFont(design_system.get_font("title_medium"))
        view_controls_layout = QVBoxLayout(view_controls_group)
        view_controls_layout.setSpacing(design_system.spacing.sm)
        
        zoom_controls_layout = QHBoxLayout()
        zoom_controls_layout.setSpacing(design_system.spacing.sm)
        
        self.zoom_in_btn = QPushButton("Zoom In")
        self.zoom_out_btn = QPushButton("Zoom Out")
        self.zoom_fit_btn = QPushButton("Fit")
        
        # Style zoom buttons
        for btn in [self.zoom_in_btn, self.zoom_out_btn, self.zoom_fit_btn]:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {design_system.colors.surface};
                    color: {design_system.colors.primary};
                    border: 1px solid {design_system.colors.primary};
                    border-radius: 4px;
                    padding: {design_system.spacing.sm}px {design_system.spacing.md}px;
                    font-weight: 500;
                    min-height: 32px;
                }}
                QPushButton:hover {{
                    background-color: {design_system.colors.primary};
                    color: {design_system.colors.on_primary};
                }}
            """)
        
        zoom_controls_layout.addWidget(self.zoom_in_btn)
        zoom_controls_layout.addWidget(self.zoom_out_btn)
        zoom_controls_layout.addWidget(self.zoom_fit_btn)
        view_controls_layout.addLayout(zoom_controls_layout)
        layout.addWidget(view_controls_group)

    def _connect_signals(self) -> None:
        self.parts_list.currentItemChanged.connect(self._on_part_selection_changed)
        self.define_motion_path_btn.toggled.connect(self.start_drawing_clicked)
        self.clear_motion_path_btn.clicked.connect(self.clear_path_clicked)
        self.closed_path_checkbox.toggled.connect(self.path_closed_changed)
        self.play_btn.clicked.connect(self.play_clicked)
        self.stop_btn.clicked.connect(self.stop_clicked)
        self.reset_sim_btn.clicked.connect(self.reset_clicked)
        self.smoothness_slider.valueChanged.connect(self._on_smoothness_changed)
        self.zoom_in_btn.clicked.connect(self.zoom_in_clicked)
        self.zoom_out_btn.clicked.connect(self.zoom_out_clicked)
        self.zoom_fit_btn.clicked.connect(self.zoom_fit_clicked)

    def _on_part_selection_changed(
        self, current: QListWidgetItem, previous: QListWidgetItem
    ) -> None:
        if current:
            part_name = current.data(Qt.ItemDataRole.UserRole)
            self.part_selected.emit(part_name)

    def update_ui_from_state(self, state) -> None:
        # Update parts list
        self.parts_list.clear()
        for part_name in state.current_parts_info:
            item = QListWidgetItem(part_name)
            item.setData(Qt.ItemDataRole.UserRole, part_name)
            self.parts_list.addItem(item)

        # Update button states
        selected_part = state.selected_part_name
        has_path = selected_part in state.path_data
        self.define_motion_path_btn.setEnabled(bool(selected_part))
        self.clear_motion_path_btn.setEnabled(has_path)
        self.smoothness_slider.setEnabled(has_path)

        has_any_path = bool(state.path_data)
        self.play_btn.setEnabled(has_any_path)
        self.stop_btn.setEnabled(state.simulation_state == "playing")
        self.reset_sim_btn.setEnabled(has_any_path)  # Reset enabled whenever there are paths

        # Update labels
        self.motion_path_status_label.setText(selected_part or "Select a part")
        self.animation_status_label.setText(
            f"{len(state.path_data)} motion path(s) defined"
            if has_any_path
            else "No motion paths defined"
        )

    def _on_smoothness_changed(self, value: int) -> None:
        """Handle smoothness slider value changes."""
        self.smoothness_value_label.setText(f"{value}%")
        self.smoothness_changed.emit(value)
