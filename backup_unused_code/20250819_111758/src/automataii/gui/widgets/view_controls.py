"""
Hover view controls widget for canvas views.
"""


from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget


class HoverViewControls(QWidget):
    """Hover controls widget that appears in the bottom-right corner of views."""

    # Signals
    zoom_in_requested = pyqtSignal()
    zoom_out_requested = pyqtSignal()
    zoom_fit_requested = pyqtSignal()
    zoom_reset_requested = pyqtSignal()
    zoom_changed = pyqtSignal(float)  # zoom_factor

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(200, 120)

        # Auto-hide timer
        self._hide_timer = QTimer()
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._auto_hide)
        self._hide_delay = 2000  # 2 seconds

        self._setup_ui()
        self._setup_style()

        # Initially hidden
        self.hide()

    def _setup_ui(self):
        """Setup the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Title
        title_label = QLabel("View Controls")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setObjectName("title")
        layout.addWidget(title_label)

        # Zoom buttons row
        zoom_layout = QHBoxLayout()
        zoom_layout.setSpacing(5)

        self.zoom_in_btn = QPushButton("+")
        self.zoom_in_btn.setFixedSize(30, 30)
        self.zoom_in_btn.setToolTip("Zoom In")
        self.zoom_in_btn.clicked.connect(self.zoom_in_requested.emit)

        self.zoom_out_btn = QPushButton("-")
        self.zoom_out_btn.setFixedSize(30, 30)
        self.zoom_out_btn.setToolTip("Zoom Out")
        self.zoom_out_btn.clicked.connect(self.zoom_out_requested.emit)

        self.zoom_fit_btn = QPushButton("Fit")
        self.zoom_fit_btn.setFixedSize(35, 30)
        self.zoom_fit_btn.setToolTip("Zoom to Fit")
        self.zoom_fit_btn.clicked.connect(self.zoom_fit_requested.emit)

        self.zoom_reset_btn = QPushButton("1:1")
        self.zoom_reset_btn.setFixedSize(35, 30)
        self.zoom_reset_btn.setToolTip("Reset Zoom (100%)")
        self.zoom_reset_btn.clicked.connect(self.zoom_reset_requested.emit)

        zoom_layout.addWidget(self.zoom_in_btn)
        zoom_layout.addWidget(self.zoom_out_btn)
        zoom_layout.addWidget(self.zoom_fit_btn)
        zoom_layout.addWidget(self.zoom_reset_btn)
        zoom_layout.addStretch()

        layout.addLayout(zoom_layout)

        # Zoom slider
        slider_layout = QHBoxLayout()
        slider_layout.setSpacing(5)

        zoom_label = QLabel("Zoom:")
        zoom_label.setFixedWidth(40)

        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setMinimum(10)  # 10%
        self.zoom_slider.setMaximum(500)  # 500%
        self.zoom_slider.setValue(100)  # 100%
        self.zoom_slider.setToolTip("Zoom Level")
        self.zoom_slider.valueChanged.connect(self._on_slider_changed)

        self.zoom_value_label = QLabel("100%")
        self.zoom_value_label.setFixedWidth(40)
        self.zoom_value_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        slider_layout.addWidget(zoom_label)
        slider_layout.addWidget(self.zoom_slider)
        slider_layout.addWidget(self.zoom_value_label)

        layout.addLayout(slider_layout)

    def _setup_style(self):
        """Setup the widget styling."""
        self.setStyleSheet("""
            HoverViewControls {
                background-color: rgba(50, 50, 50, 240);
                border: 1px solid rgba(100, 100, 100, 200);
                border-radius: 8px;
            }
            
            QLabel#title {
                color: white;
                font-weight: bold;
                font-size: 12px;
                margin-bottom: 5px;
            }
            
            QLabel {
                color: white;
                font-size: 10px;
            }
            
            QPushButton {
                background-color: rgba(70, 70, 70, 200);
                border: 1px solid rgba(120, 120, 120, 150);
                border-radius: 4px;
                color: white;
                font-weight: bold;
                font-size: 11px;
            }
            
            QPushButton:hover {
                background-color: rgba(90, 90, 90, 220);
                border: 1px solid rgba(140, 140, 140, 200);
            }
            
            QPushButton:pressed {
                background-color: rgba(110, 110, 110, 240);
            }
            
            QSlider::groove:horizontal {
                border: 1px solid rgba(100, 100, 100, 150);
                height: 6px;
                background: rgba(40, 40, 40, 200);
                border-radius: 3px;
            }
            
            QSlider::handle:horizontal {
                background: rgba(150, 150, 150, 220);
                border: 1px solid rgba(120, 120, 120, 200);
                width: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }
            
            QSlider::handle:horizontal:hover {
                background: rgba(180, 180, 180, 240);
            }
            
            QSlider::sub-page:horizontal {
                background: rgba(100, 150, 200, 180);
                border-radius: 3px;
            }
        """)

    def _on_slider_changed(self, value: int):
        """Handle slider value change."""
        self.zoom_value_label.setText(f"{value}%")
        zoom_factor = value / 100.0
        self.zoom_changed.emit(zoom_factor)

    def set_zoom_level(self, zoom_percentage: float):
        """Set the zoom level display."""
        value = int(zoom_percentage)
        self.zoom_slider.blockSignals(True)
        self.zoom_slider.setValue(value)
        self.zoom_value_label.setText(f"{value}%")
        self.zoom_slider.blockSignals(False)

    def show_controls(self):
        """Show the controls and start auto-hide timer."""
        self.show()
        self._hide_timer.start(self._hide_delay)

    def hide_controls(self):
        """Hide the controls immediately."""
        self._hide_timer.stop()
        self.hide()

    def _auto_hide(self):
        """Auto-hide the controls."""
        self.hide()

    def enterEvent(self, event):
        """Mouse entered the widget - stop auto-hide."""
        self._hide_timer.stop()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Mouse left the widget - restart auto-hide."""
        self._hide_timer.start(self._hide_delay)
        super().leaveEvent(event)
