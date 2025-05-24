from PyQt6.QtWidgets import QGroupBox, QVBoxLayout, QPushButton
from PyQt6.QtCore import pyqtSignal

class ProcessingStepsGroup(QGroupBox):
    """A group box containing buttons for detailed image processing steps."""
    # Define signals for each button click if they need to be handled externally
    processImageClicked = pyqtSignal()
    editSkeletonClicked = pyqtSignal()
    saveSkeletonClicked = pyqtSignal()
    generatePartsClicked = pyqtSignal()

    def __init__(self, title: str = "Detailed Processing Steps", parent=None):
        super().__init__(title, parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)  # Consistent spacing

        self.process_image_btn = QPushButton("Process Image (Skeleton)")
        self.process_image_btn.clicked.connect(self.processImageClicked.emit)
        layout.addWidget(self.process_image_btn)

        self.edit_skeleton_btn = QPushButton("Edit Skeleton")
        self.edit_skeleton_btn.clicked.connect(self.editSkeletonClicked.emit)
        layout.addWidget(self.edit_skeleton_btn)

        self.save_skeleton_btn = QPushButton("Save Skeleton")
        self.save_skeleton_btn.clicked.connect(self.saveSkeletonClicked.emit)
        layout.addWidget(self.save_skeleton_btn)

        self.create_parts_btn = QPushButton("Generate Body Parts")
        self.create_parts_btn.clicked.connect(self.generatePartsClicked.emit)
        layout.addWidget(self.create_parts_btn)

        # Initially, this group might be hidden
        # self.setVisible(False) # Visibility will be controlled by ImageProcessingTab

    def set_buttons_enabled_state(self, process_enabled: bool, edit_enabled: bool, save_enabled: bool, generate_enabled: bool):
        """Allows external control over the enabled state of the buttons."""
        self.process_image_btn.setEnabled(process_enabled)
        self.edit_skeleton_btn.setEnabled(edit_enabled)
        self.save_skeleton_btn.setEnabled(save_enabled)
        self.create_parts_btn.setEnabled(generate_enabled)

if __name__ == '__main__':
    from PyQt6.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)
    # Example usage:
    main_widget = QWidget()
    main_layout = QVBoxLayout(main_widget)

    steps_group = ProcessingStepsGroup()
    # Connect signals to dummy slots for testing
    steps_group.processImageClicked.connect(lambda: print("Process Image Clicked"))
    steps_group.editSkeletonClicked.connect(lambda: print("Edit Skeleton Clicked"))
    steps_group.saveSkeletonClicked.connect(lambda: print("Save Skeleton Clicked"))
    steps_group.generatePartsClicked.connect(lambda: print("Generate Parts Clicked"))

    # Example of setting enabled states
    steps_group.set_buttons_enabled_state(True, False, False, False)

    main_layout.addWidget(steps_group)

    # Toggle visibility button for testing
    toggle_btn = QPushButton("Toggle Steps Visibility")
    def toggle_visibility():
        steps_group.setVisible(not steps_group.isVisible())
    toggle_btn.clicked.connect(toggle_visibility)
    main_layout.addWidget(toggle_btn)

    main_widget.show()
    sys.exit(app.exec())