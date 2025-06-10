"""
Control Panels for Image Processing Tab

Contains the UI control panels for the image processing tab.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QPushButton,
    QCheckBox, QSizePolicy
)

from automataii.gui.widgets.processing_steps_group import ProcessingStepsGroup


class ImageProcessingControlPanel(QWidget):
    """Main control panel for image processing tab."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Initialize UI components
        self.load_image_btn = QPushButton("Load Image File")
        self.capture_image_btn = QPushButton("Capture Camera")
        self.next_stage_btn = QPushButton("Proceed to Editor")
        self.show_skeleton_checkbox = QCheckBox("Show Skeleton")
        self.show_skeleton_checkbox.setChecked(True)  # Set checked by default
        self.show_parts_checkbox = QCheckBox("Show Body Parts")
        self.show_parts_checkbox.setChecked(True)  # Set checked by default
        
        # Processing steps group
        self.processing_steps_group = ProcessingStepsGroup()
        self.processing_steps_group.setVisible(False)  # Hide by default
        
        self._init_ui()
        
    def _init_ui(self):
        """Initialize the control panel UI."""
        self.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Expanding
        )
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 10, 5, 10)
        layout.setSpacing(10)
        
        # Input Group
        input_group = QGroupBox("1 Input Drawing")
        input_layout = QVBoxLayout(input_group)
        input_layout.setSpacing(10)
        input_layout.addWidget(self.load_image_btn)
        input_layout.addWidget(self.capture_image_btn)
        layout.addWidget(input_group)
        
        # Output Group
        self.output_group = QGroupBox("2 Next")
        output_layout = QVBoxLayout(self.output_group)
        output_layout.setSpacing(10)
        output_layout.addWidget(self.next_stage_btn)
        self.output_group.setVisible(False)  # Hide by default
        layout.addWidget(self.output_group)
        
        # Processing Group
        layout.addWidget(self.processing_steps_group)
        
        # View Options Group
        self.view_options_group = QGroupBox("3 View Options")
        view_options_layout = QVBoxLayout(self.view_options_group)
        view_options_layout.setSpacing(10)
        view_options_layout.addWidget(self.show_skeleton_checkbox)
        view_options_layout.addWidget(self.show_parts_checkbox)
        self.view_options_group.setVisible(False)  # Hide by default
        layout.addWidget(self.view_options_group)
        
        layout.addStretch()
        
    def update_button_states(
        self,
        has_image: bool,
        has_skeleton: bool,
        has_parts: bool,
        can_proceed: bool
    ):
        """Update button enabled states based on workflow state."""
        self.processing_steps_group.set_buttons_enabled_state(
            process_enabled=has_image,
            edit_enabled=has_skeleton,
            save_enabled=has_skeleton,
            generate_enabled=(has_skeleton and has_image),
            skeleton_tools_enabled=has_skeleton
        )
        
        self.next_stage_btn.setEnabled(can_proceed)
        
    def show_processing_steps(self, visible: bool):
        """Show or hide the processing steps group."""
        self.processing_steps_group.setVisible(visible)