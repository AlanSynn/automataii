"""
EditorTab UI Builder - Constructs the EditorTab user interface.

Extracted from EditorTab._init_ui() to reduce god class complexity.
Uses shared StyleFactory for consistent styling.

Design Pattern: Builder (UI construction)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSplitter,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from automataii.presentation.qt.widgets.common.styles import StyleFactory

if TYPE_CHECKING:
    from automataii.presentation.qt.views.editor_view import EditorView


@dataclass
class EditorTabUIRefs:
    """
    References to UI widgets created by the builder.

    This dataclass holds all widget references that need to be
    connected to signals or accessed by the EditorTab.
    """

    # Parts group
    parts_list: QListWidget

    # Motion path group
    define_motion_path_btn: QPushButton
    clear_motion_path_btn: QPushButton
    motion_path_status_label: QLabel
    motion_path_info_label: QLabel
    smoothness_slider: QSlider
    smoothness_value_label: QLabel
    closed_path_radio: QRadioButton
    open_path_radio: QRadioButton
    path_type_group: QButtonGroup

    # Animation group
    animation_status_label: QLabel
    play_btn: QPushButton
    stop_btn: QPushButton
    reset_sim_btn: QPushButton

    # View controls group
    zoom_in_btn: QPushButton
    zoom_out_btn: QPushButton
    zoom_fit_btn: QPushButton
    center_character_btn: QPushButton


class EditorTabUIBuilder:
    """
    Builder for EditorTab user interface.

    Responsibilities:
    - Create all UI widgets with consistent styling
    - Organize widgets into layout groups
    - Return widget references for signal connections

    Time Complexity: O(1) - fixed number of widgets
    """

    CONTROL_PANEL_MIN_WIDTH = 220
    CONTROL_PANEL_PREFERRED_WIDTH = 300
    CONTROL_PANEL_MAX_WIDTH = 460

    def __init__(self, parent: QWidget, editor_view: EditorView):
        """
        Initialize the UI builder.

        Args:
            parent: Parent widget (EditorTab)
            editor_view: The EditorView to include in the layout
        """
        self._parent = parent
        self._editor_view = editor_view
        self._style = parent.style()

    def build(self) -> EditorTabUIRefs:
        """
        Build the complete EditorTab UI.

        Returns:
            EditorTabUIRefs containing all widget references
        """
        layout = QHBoxLayout(self._parent)

        # Build control panel (left side)
        scroll_area, refs = self._build_control_panel()

        # Create splitter for left panel and editor view
        splitter = self._build_splitter(scroll_area)
        layout.addWidget(splitter)

        return refs

    def _build_control_panel(self) -> tuple[QScrollArea, EditorTabUIRefs]:
        """Build the left control panel with all groups."""
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumWidth(self.CONTROL_PANEL_MIN_WIDTH)
        scroll_area.setMaximumWidth(self.CONTROL_PANEL_MAX_WIDTH)
        scroll_area.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        control_panel = QWidget()
        panel_layout = QVBoxLayout(control_panel)
        panel_layout.setContentsMargins(10, 10, 10, 10)
        panel_layout.setSpacing(15)

        # Build groups
        parts_list = self._build_parts_group(panel_layout)
        motion_refs = self._build_motion_path_group(panel_layout)
        animation_refs = self._build_animation_group(panel_layout)
        view_refs = self._build_view_controls_group(panel_layout)

        panel_layout.addStretch(1)
        control_panel.setMinimumWidth(self.CONTROL_PANEL_MIN_WIDTH - 20)
        scroll_area.setWidget(control_panel)

        # Combine all refs
        refs = EditorTabUIRefs(
            parts_list=parts_list,
            **motion_refs,
            **animation_refs,
            **view_refs,
        )

        return scroll_area, refs

    def _build_parts_group(self, parent_layout: QVBoxLayout) -> QListWidget:
        """Build the Parts List group."""
        parts_group = QGroupBox("1 Parts")
        parts_group.setStyleSheet(StyleFactory.group_box_style())
        parts_layout = QVBoxLayout(parts_group)

        parts_list = QListWidget()
        parts_list.setToolTip("List of loaded character parts")
        parts_list.setMinimumHeight(180)
        parts_list.setStyleSheet(StyleFactory.parts_list_style())
        parts_layout.addWidget(parts_list)

        parent_layout.addWidget(parts_group)
        return parts_list

    def _build_motion_path_group(self, parent_layout: QVBoxLayout) -> dict:
        """Build the Motion Path group."""
        motion_path_group = QGroupBox("2 Motion Path")
        motion_path_group.setStyleSheet(StyleFactory.group_box_style())
        motion_path_layout = QVBoxLayout(motion_path_group)

        # Status label
        motion_path_status_label = QLabel("Select a part")
        motion_path_status_label.setStyleSheet(StyleFactory.status_label_style())
        motion_path_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        motion_path_layout.addWidget(motion_path_status_label)

        # Path type selection
        path_type_layout = QHBoxLayout()
        path_type_layout.setSpacing(10)

        path_type_label = QLabel("Path Type:")
        path_type_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #495057;")
        path_type_layout.addWidget(path_type_label)

        path_type_group = QButtonGroup()

        closed_path_radio = QRadioButton("Closed")
        closed_path_radio.setToolTip("Create a closed loop path")
        closed_path_radio.setChecked(True)
        path_type_group.addButton(closed_path_radio, 0)
        path_type_layout.addWidget(closed_path_radio)

        open_path_radio = QRadioButton("Open")
        open_path_radio.setToolTip("Create an open path")
        path_type_group.addButton(open_path_radio, 1)
        path_type_layout.addWidget(open_path_radio)

        path_type_layout.addStretch()
        motion_path_layout.addLayout(path_type_layout)

        # Buttons
        motion_path_buttons_layout = QHBoxLayout()
        motion_path_buttons_layout.setSpacing(8)

        define_motion_path_btn = QPushButton("Start Drawing")
        define_motion_path_btn.setCheckable(True)
        define_motion_path_btn.setToolTip(
            "Toggle mode to draw a motion path for the selected part."
        )
        define_motion_path_btn.setEnabled(False)
        define_motion_path_btn.setStyleSheet(StyleFactory.action_button_checked_style())

        clear_motion_path_btn = QPushButton("Clear")
        clear_motion_path_btn.setToolTip("Clear the motion path for the selected part.")
        clear_motion_path_btn.setEnabled(False)
        clear_motion_path_btn.setStyleSheet(StyleFactory.danger_button_style())

        motion_path_buttons_layout.addStretch()
        motion_path_buttons_layout.addWidget(define_motion_path_btn)
        motion_path_buttons_layout.addWidget(clear_motion_path_btn)
        motion_path_buttons_layout.addStretch()
        motion_path_layout.addLayout(motion_path_buttons_layout)

        # Info label
        motion_path_info_label = QLabel(
            "Click points in the view to draw path. Click 'Stop Drawing' when done."
        )
        motion_path_info_label.setWordWrap(True)
        motion_path_info_label.setStyleSheet(StyleFactory.info_label_style())
        motion_path_info_label.setVisible(False)
        motion_path_layout.addWidget(motion_path_info_label)

        # Smoothness control
        smoothness_layout = QHBoxLayout()
        smoothness_layout.setSpacing(8)

        smoothness_label = QLabel("Smoothness:")
        smoothness_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #495057;")
        smoothness_layout.addWidget(smoothness_label)

        smoothness_slider = QSlider(Qt.Orientation.Horizontal)
        smoothness_slider.setMinimum(0)
        smoothness_slider.setMaximum(100)
        smoothness_slider.setValue(50)
        smoothness_slider.setEnabled(False)
        smoothness_slider.setToolTip(
            "Adjust path smoothness (0% = raw points, 100% = perfect ellipse)"
        )
        smoothness_slider.setStyleSheet(StyleFactory.smoothness_slider_style())
        smoothness_layout.addWidget(smoothness_slider)

        smoothness_value_label = QLabel("50%")
        smoothness_value_label.setMinimumWidth(30)
        smoothness_value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        smoothness_value_label.setStyleSheet("font-size: 11px; color: #666;")
        smoothness_layout.addWidget(smoothness_value_label)

        motion_path_layout.addLayout(smoothness_layout)

        parent_layout.addWidget(motion_path_group)
        parent_layout.setStretchFactor(motion_path_group, 0)

        return {
            "define_motion_path_btn": define_motion_path_btn,
            "clear_motion_path_btn": clear_motion_path_btn,
            "motion_path_status_label": motion_path_status_label,
            "motion_path_info_label": motion_path_info_label,
            "smoothness_slider": smoothness_slider,
            "smoothness_value_label": smoothness_value_label,
            "closed_path_radio": closed_path_radio,
            "open_path_radio": open_path_radio,
            "path_type_group": path_type_group,
        }

    def _build_animation_group(self, parent_layout: QVBoxLayout) -> dict:
        """Build the Animation group."""
        animation_group = QGroupBox("3 Animation")
        animation_group.setStyleSheet(StyleFactory.group_box_style())
        animation_layout = QVBoxLayout(animation_group)

        animation_status_label = QLabel("No motion paths defined")
        animation_layout.addWidget(animation_status_label)

        anim_button_layout = QHBoxLayout()
        anim_button_layout.setSpacing(12)

        button_style = StyleFactory.compact_animation_button_style()

        # Play button
        play_btn = QPushButton(self._style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay), "")
        play_btn.setToolTip("Play Animation")
        play_btn.setStyleSheet(button_style)

        # Stop button
        stop_btn = QPushButton(self._style.standardIcon(QStyle.StandardPixmap.SP_MediaStop), "")
        stop_btn.setToolTip("Stop Animation")
        stop_btn.setEnabled(False)
        stop_btn.setStyleSheet(button_style)

        # Reset button
        reset_sim_btn = QPushButton(
            self._style.standardIcon(QStyle.StandardPixmap.SP_BrowserReload), ""
        )
        reset_sim_btn.setToolTip("Reset Animation")
        reset_sim_btn.setEnabled(False)
        reset_sim_btn.setStyleSheet(button_style)

        anim_button_layout.addStretch()
        anim_button_layout.addWidget(play_btn)
        anim_button_layout.addWidget(stop_btn)
        anim_button_layout.addWidget(reset_sim_btn)
        anim_button_layout.addStretch()
        animation_layout.addLayout(anim_button_layout)

        parent_layout.addWidget(animation_group)

        return {
            "animation_status_label": animation_status_label,
            "play_btn": play_btn,
            "stop_btn": stop_btn,
            "reset_sim_btn": reset_sim_btn,
        }

    def _build_view_controls_group(self, parent_layout: QVBoxLayout) -> dict:
        """Build the View Controls group."""
        view_controls_group = QGroupBox("4 View Controls")
        view_controls_group.setStyleSheet(StyleFactory.group_box_style())
        view_controls_layout = QVBoxLayout(view_controls_group)

        # Zoom controls
        zoom_controls_layout = QHBoxLayout()
        zoom_controls_layout.setSpacing(6)

        button_style = StyleFactory.zoom_button_style()

        zoom_in_btn = QPushButton("+")
        zoom_in_btn.setToolTip("Zoom In")
        zoom_in_btn.setStyleSheet(button_style)
        zoom_controls_layout.addWidget(zoom_in_btn)

        zoom_out_btn = QPushButton("−")
        zoom_out_btn.setToolTip("Zoom Out")
        zoom_out_btn.setStyleSheet(button_style)
        zoom_controls_layout.addWidget(zoom_out_btn)

        zoom_fit_btn = QPushButton("⌖")
        zoom_fit_btn.setToolTip("Zoom to Fit")
        zoom_fit_btn.setStyleSheet(button_style)
        zoom_controls_layout.addWidget(zoom_fit_btn)

        center_character_btn = QPushButton("⎈")
        center_character_btn.setToolTip("Center on Character")
        center_character_btn.setStyleSheet(button_style)
        zoom_controls_layout.addWidget(center_character_btn)

        view_controls_layout.addLayout(zoom_controls_layout)
        parent_layout.addWidget(view_controls_group)

        return {
            "zoom_in_btn": zoom_in_btn,
            "zoom_out_btn": zoom_out_btn,
            "zoom_fit_btn": zoom_fit_btn,
            "center_character_btn": center_character_btn,
        }

    def _build_splitter(self, scroll_area: QScrollArea) -> QSplitter:
        """Build the splitter containing control panel and editor view."""
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(True)

        # Left panel - resizable within guard rails
        splitter.addWidget(scroll_area)

        # Right canvas - resizable
        splitter.addWidget(self._editor_view)

        splitter.setCollapsible(0, True)
        splitter.setCollapsible(1, False)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([self.CONTROL_PANEL_PREFERRED_WIDTH, 900])

        return splitter
