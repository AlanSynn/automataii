from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QGroupBox, QComboBox, QLabel, QSizePolicy, QCheckBox
)
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt

from ..editor_view import EditorView # Assuming EditorView is in the parent directory
from ..image_view import ImageProcessingView # Assuming ImageProcessingView is in the parent directory

class ImageProcessingTab(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)

        # Left Control Panel
        control_panel = QWidget()
        control_panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        panel_layout = QVBoxLayout(control_panel)
        panel_layout.setContentsMargins(5, 10, 5, 10)
        panel_layout.setSpacing(15)

        # Input Group
        input_group = QGroupBox("Input Drawing")
        input_layout = QVBoxLayout(input_group)
        self.main_window.load_image_btn = QPushButton("Load Image File")
        self.main_window.capture_image_btn = QPushButton("Capture Camera")
        input_layout.addWidget(self.main_window.load_image_btn)
        input_layout.addWidget(self.main_window.capture_image_btn)
        panel_layout.addWidget(input_group)

        # Processing Group
        # proc_group = QGroupBox("Editing")
        # proc_layout = QVBoxLayout(proc_group)
        # self.main_window.process_image_btn = QPushButton(" Process Image")
        # self.main_window.create_parts_btn = QPushButton(" Generate Body Parts")
        # proc_layout.addWidget(self.main_window.process_image_btn)
        # proc_layout.addWidget(self.main_window.create_parts_btn)
        # panel_layout.addWidget(proc_group)

        # Output Group
        output_group = QGroupBox("Next")
        output_layout = QVBoxLayout(output_group)
        self.main_window.next_stage_btn = QPushButton(" Next")
        output_layout.addWidget(self.main_window.next_stage_btn)
        panel_layout.addWidget(output_group)

        # View Options Group
        view_options_group = QGroupBox("View Options")
        view_options_layout = QVBoxLayout(view_options_group)
        self.show_skeleton_checkbox = QCheckBox("Show Skeleton")
        self.show_parts_checkbox = QCheckBox("Show Body Parts")
        view_options_layout.addWidget(self.show_skeleton_checkbox)
        view_options_layout.addWidget(self.show_parts_checkbox)
        panel_layout.addWidget(view_options_group)

        panel_layout.addStretch()

        # Right View Area
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(5, 5, 5, 5)
        right_layout.setSpacing(5)

        zoom_toolbar = QWidget()
        zoom_layout = QHBoxLayout(zoom_toolbar)
        zoom_layout.setContentsMargins(10, 8, 10, 8)
        zoom_layout.setSpacing(8)
        zoom_layout.addStretch()

        self.main_window.image_zoom_combo = QComboBox()
        self.main_window.image_zoom_combo.setEditable(True)
        self.main_window.image_zoom_combo.setFixedSize(80, 28)
        self.main_window.image_zoom_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #d0d7de;
                border-radius: 6px;
                padding: 4px 4px;
                background-color: white;
                font-size: 12px;
            }
            QComboBox:hover {
                border-color: #586069;
            }
        """)
        zoom_levels = ["50%", "75%", "90%", "100%", "125%", "150%", "200%"]
        self.main_window.image_zoom_combo.addItems(zoom_levels)
        self.main_window.image_zoom_combo.setCurrentText("100%")
        self.main_window.image_zoom_combo.setToolTip("Zoom level")

        self.main_window.image_fit_btn = QPushButton("Fit")
        self.main_window.image_fit_btn.setFixedSize(45, 28)
        self.main_window.image_fit_btn.setStyleSheet("""
            QPushButton {
                border: 1px solid #d0d7de;
                border-radius: 4px;
                padding: 4px 4px;
                background-color: white;
                font-size: 13px;
                color: #24292f;
            }
            QPushButton:hover {
                background-color: #f6f8fa;
                border-color: #586069;
            }
            QPushButton:pressed {
                background-color: #e9ecef;
            }
        """)
        self.main_window.image_fit_btn.setToolTip("Zoom to fit all items")

        zoom_layout.addWidget(self.main_window.image_zoom_combo)
        zoom_layout.addWidget(self.main_window.image_fit_btn)

        # The scene and view are managed by the main_window
        right_layout.addWidget(self.main_window.image_proc_view, 1)

        zoom_toolbar.setParent(right_panel)
        zoom_toolbar.setStyleSheet("""
            QWidget {
                background-color: rgba(248, 249, 250, 0.9);
                border: 1px solid rgba(208, 215, 222, 0.8);
                border-radius: 1px;
            }
        """)
        zoom_toolbar.show()

        def position_image_zoom_toolbar():
            toolbar_width = zoom_toolbar.sizeHint().width()
            toolbar_height = zoom_toolbar.sizeHint().height()
            x = right_panel.width() - toolbar_width - 20
            y = right_panel.height() - toolbar_height - 20
            zoom_toolbar.setGeometry(x, y, toolbar_width, toolbar_height)

        original_show_event = right_panel.showEvent
        def new_show_event(event):
            original_show_event(event)
            position_image_zoom_toolbar()
        right_panel.showEvent = new_show_event

        original_resize_event = right_panel.resizeEvent
        def new_resize_event(event):
            original_resize_event(event)
            position_image_zoom_toolbar()
        right_panel.resizeEvent = new_resize_event

        layout.addWidget(control_panel)
        layout.addWidget(right_panel, 1)
        self.setLayout(layout)

        # Connect signals for the new checkboxes
        self.show_skeleton_checkbox.toggled.connect(self._toggle_skeleton_visibility_in_view)
        self.show_parts_checkbox.toggled.connect(self._toggle_parts_visibility_in_view)

    def _toggle_skeleton_visibility_in_view(self, checked: bool):
        if self.main_window and hasattr(self.main_window, 'image_proc_view') and self.main_window.image_proc_view:
            self.main_window.image_proc_view.show_skeleton_visuals(checked)

    def _toggle_parts_visibility_in_view(self, checked: bool):
        if self.main_window and hasattr(self.main_window, 'image_proc_view') and self.main_window.image_proc_view:
            self.main_window.image_proc_view.show_part_visuals(checked)