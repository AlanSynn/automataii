from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QGroupBox, QHBoxLayout, QPushButton, QVBoxLayout, QWidget


class ProcessingStepsGroup(QGroupBox):
    """A group box containing buttons for detailed image processing steps."""

    # Define signals for each button click if they need to be handled externally
    processImageClicked = pyqtSignal()
    editSkeletonClicked = pyqtSignal()
    saveSkeletonClicked = pyqtSignal()
    generatePartsClicked = pyqtSignal()
    extendSkeletonClicked = pyqtSignal()
    lockJointsClicked = pyqtSignal()

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

        # Add separator line
        separator = QWidget()
        separator.setFixedHeight(1)
        separator.setStyleSheet("background-color: #d0d7de;")
        layout.addWidget(separator)

        # Add skeleton manipulation buttons in a horizontal layout
        skeleton_tools_layout = QHBoxLayout()
        skeleton_tools_layout.setSpacing(5)

        self.extend_skeleton_btn = QPushButton("Extend Skeleton 10%")
        self.extend_skeleton_btn.setToolTip("Increase all skeleton bone lengths by 10%")
        self.extend_skeleton_btn.clicked.connect(self.extendSkeletonClicked.emit)
        skeleton_tools_layout.addWidget(self.extend_skeleton_btn)

        self.lock_joints_btn = QPushButton("Lock/Unlock Joints")
        self.lock_joints_btn.setToolTip("Select joints to lock/unlock for IK solving")
        self.lock_joints_btn.clicked.connect(self.lockJointsClicked.emit)
        skeleton_tools_layout.addWidget(self.lock_joints_btn)

        layout.addLayout(skeleton_tools_layout)

        # Initially, this group might be hidden
        # self.setVisible(False) # Visibility will be controlled by ImageProcessingTab

    def set_buttons_enabled_state(
        self,
        process_enabled: bool,
        edit_enabled: bool,
        save_enabled: bool,
        generate_enabled: bool,
        skeleton_tools_enabled: bool = False,
    ):
        """Allows external control over the enabled state of the buttons."""
        self.process_image_btn.setEnabled(process_enabled)
        self.edit_skeleton_btn.setEnabled(edit_enabled)
        self.save_skeleton_btn.setEnabled(save_enabled)
        self.create_parts_btn.setEnabled(generate_enabled)
        self.extend_skeleton_btn.setEnabled(skeleton_tools_enabled)
        self.lock_joints_btn.setEnabled(skeleton_tools_enabled)


if __name__ == "__main__":
    import sys

    from PyQt6.QtWidgets import QApplication, QWidget

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
    steps_group.extendSkeletonClicked.connect(lambda: print("Extend Skeleton Clicked"))
    steps_group.lockJointsClicked.connect(lambda: print("Lock/Unlock Joints Clicked"))

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
