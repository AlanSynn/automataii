# src/automataii/ui/tabs/image_processing/ui_panel.py

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from automataii.ui.widgets.processing_steps_group import ProcessingStepsGroup
from automataii.ui.design_system import design_system, StyledComponents


class ImageProcessingControlPanel(QWidget):
    """
    UI panel for Image Processing tab controls.
    Contains all buttons and UI elements but no signal connections.
    """

    # Signals for user interactions
    load_image_clicked = pyqtSignal()
    capture_image_clicked = pyqtSignal()
    zoom_in_clicked = pyqtSignal()
    zoom_out_clicked = pyqtSignal()
    zoom_fit_clicked = pyqtSignal()
    zoom_reset_clicked = pyqtSignal()
    image_zoom_changed = pyqtSignal(str)
    image_fit_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        # Create UI components
        self._setup_ui()

        # Connect internal signals
        self._connect_signals()

    def _setup_ui(self):
        """Create and layout all UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            design_system.spacing.md,
            design_system.spacing.md,
            design_system.spacing.md,
            design_system.spacing.md
        )
        layout.setSpacing(design_system.spacing.md)
        
        # Apply panel styling
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {design_system.colors.surface};
                border-radius: 8px;
            }}
        """)
        design_system.apply_shadow(self, design_system.elevation.level_1)

        # Input group
        input_group = self._create_input_group()
        layout.addWidget(input_group)

        # Processing steps group
        self.processing_steps_group = ProcessingStepsGroup()
        self.processing_steps_group.setVisible(False)
        layout.addWidget(self.processing_steps_group)

        # View controls group
        view_controls_group = self._create_view_controls_group()
        layout.addWidget(view_controls_group)

        # Add stretch to push everything to top
        layout.addStretch()

    def _create_input_group(self) -> QGroupBox:
        """Create the input drawing group."""
        input_group = QGroupBox("Input Drawing")
        input_layout = QVBoxLayout(input_group)
        input_layout.setSpacing(10)

        self.load_image_btn = QPushButton("Load Image File")
        self.capture_image_btn = QPushButton("Capture Camera")

        input_layout.addWidget(self.load_image_btn)
        input_layout.addWidget(self.capture_image_btn)

        return input_group

    def _create_view_controls_group(self) -> QGroupBox:
        """Create the view controls group."""
        view_controls_group = QGroupBox("View Controls")
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

        self.zoom_in_btn = QPushButton("Zoom In")
        self.zoom_out_btn = QPushButton("Zoom Out")
        self.zoom_fit_btn = QPushButton("Zoom to Fit")
        self.zoom_reset_btn = QPushButton("Reset View")

        zoom_controls_layout.addWidget(self.zoom_in_btn)
        zoom_controls_layout.addWidget(self.zoom_out_btn)
        zoom_controls_layout.addWidget(self.zoom_fit_btn)
        zoom_controls_layout.addWidget(self.zoom_reset_btn)

        view_controls_layout.addLayout(zoom_controls_layout)

        # Image controls
        image_controls_layout = QHBoxLayout()

        self.image_zoom_combo = QComboBox()
        self.image_zoom_combo.setEditable(True)
        self.image_zoom_combo.addItems(["25%", "50%", "75%", "100%", "125%", "150%", "200%"])
        self.image_zoom_combo.setCurrentText("100%")

        self.image_fit_btn = QPushButton("Fit")

        image_controls_layout.addWidget(self.image_zoom_combo)
        image_controls_layout.addWidget(self.image_fit_btn)

        view_controls_layout.addLayout(image_controls_layout)

        return view_controls_group

    def _connect_signals(self):
        """Connect internal widget signals to our public signals."""
        self.load_image_btn.clicked.connect(self.load_image_clicked.emit)
        self.capture_image_btn.clicked.connect(self.capture_image_clicked.emit)
        self.zoom_in_btn.clicked.connect(self.zoom_in_clicked.emit)
        self.zoom_out_btn.clicked.connect(self.zoom_out_clicked.emit)
        self.zoom_fit_btn.clicked.connect(self.zoom_fit_clicked.emit)
        self.zoom_reset_btn.clicked.connect(self.zoom_reset_clicked.emit)
        self.image_zoom_combo.currentTextChanged.connect(self.image_zoom_changed.emit)
        self.image_fit_btn.clicked.connect(self.image_fit_clicked.emit)

    def update_ui_from_state(self, state):
        """Update UI elements based on state changes."""
        # Processing steps group visibility
        has_image = bool(state.input_image_path)
        self.processing_steps_group.setVisible(has_image)

        # Individual button states would be handled by the processing steps group
        # The main buttons here are always enabled except during processing
        processing = state.processing_in_progress

        self.load_image_btn.setEnabled(not processing)
        self.capture_image_btn.setEnabled(not processing)

        # View controls are always enabled
        self.zoom_in_btn.setEnabled(True)
        self.zoom_out_btn.setEnabled(True)
        self.zoom_fit_btn.setEnabled(True)
        self.zoom_reset_btn.setEnabled(True)
        self.image_zoom_combo.setEnabled(True)
        self.image_fit_btn.setEnabled(True)

    def get_processing_steps_group(self) -> ProcessingStepsGroup:
        """Get reference to the processing steps group widget."""
        return self.processing_steps_group
