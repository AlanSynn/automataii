"""Main recommendation dialog for mechanism selection."""

from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal as Signal
from PyQt6.QtGui import QPainterPath
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from .constants import (
    DIALOG_MIN_SIZE,
    BUTTON_SIZE,
    DEFAULT_NUM_SAMPLES_FOR_PATH
)
from .styles import StyleSheets
from .preview_container import PreviewContainer
from .recommendation_service import MechanismRecommendationService


class MechanismRecommendationDialog(QDialog):
    """Dialog for recommending and selecting mechanisms based on user motion path."""
    
    mechanism_selected = Signal(dict)  # Emitted when a mechanism is chosen
    mechanism_preview_selected = Signal(dict)  # Emitted when clicked for preview

    def __init__(
        self,
        user_motion_path: QPainterPath,
        generated_paths_filepath: str,
        num_samples_user_path: int = DEFAULT_NUM_SAMPLES_FOR_PATH,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Choose a Mechanism")
        self.setMinimumSize(*DIALOG_MIN_SIZE)
        self.selected_mechanism_data: Optional[Dict[str, Any]] = None

        self.user_motion_path_original = user_motion_path
        self.recommendation_service = MechanismRecommendationService(
            user_motion_path, generated_paths_filepath, num_samples_user_path
        )

        self._init_ui()

    def _init_ui(self) -> None:
        """Initialize the dialog UI."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Instructions
        self._add_instructions(main_layout)

        # Preview containers
        self._add_preview_containers(main_layout)

        # Buttons
        self._add_buttons(main_layout)

        self.setLayout(main_layout)

    def _add_instructions(self, layout: QVBoxLayout) -> None:
        """Add instruction labels to the layout."""
        instruction_label = QLabel(
            "Choose the mechanism that best matches your desired motion"
        )
        instruction_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        instruction_label.setStyleSheet(StyleSheets.INSTRUCTION_LABEL)
        layout.addWidget(instruction_label)
        
        subtitle_label = QLabel(
            "The red dashed line shows your drawn path. Click on a mechanism to select it."
        )
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_label.setStyleSheet(StyleSheets.SUBTITLE_LABEL)
        layout.addWidget(subtitle_label)

    def _add_preview_containers(self, layout: QVBoxLayout) -> None:
        """Add mechanism preview containers to the layout."""
        self.previews_layout = QHBoxLayout()
        self.previews_layout.setSpacing(10)
        self.previews_layout.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )

        recommendations = self.recommendation_service.get_best_recommendations()
        self.preview_containers = []

        if recommendations:
            for rec_data in recommendations:
                if rec_data:
                    # Add user motion path for preview
                    rec_data_with_user_path = rec_data.copy()
                    rec_data_with_user_path["user_motion_path_local"] = (
                        self.user_motion_path_original
                    )

                    container = PreviewContainer(rec_data_with_user_path, self)
                    container.selected.connect(self._on_select)
                    container.clicked.connect(self._on_preview_click)
                    self.previews_layout.addWidget(container)
                    self.preview_containers.append(container)
                else:
                    self._add_placeholder()
            self.previews_layout.addStretch()
        else:
            self._add_no_recommendations_label()

        layout.addLayout(self.previews_layout)

    def _add_placeholder(self) -> None:
        """Add a placeholder for missing recommendations."""
        placeholder_label = QLabel("No mechanism found")
        placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder_label.setFrameShape(QLabel.FrameShape.Box)
        placeholder_label.setFixedSize(220, 280)
        placeholder_label.setStyleSheet(StyleSheets.PLACEHOLDER_LABEL)
        self.previews_layout.addWidget(placeholder_label)

    def _add_no_recommendations_label(self) -> None:
        """Add label when no recommendations are available."""
        no_recs_label = QLabel(
            "No mechanism recommendations could be generated or found."
        )
        no_recs_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.previews_layout.addWidget(no_recs_label)

    def _add_buttons(self, layout: QVBoxLayout) -> None:
        """Add OK/Cancel buttons to the layout."""
        button_layout = QHBoxLayout()
        button_layout.setSpacing(20)
        
        self.ok_button = QPushButton("OK")
        self.ok_button.setFixedSize(*BUTTON_SIZE)
        self.ok_button.setStyleSheet(StyleSheets.OK_BUTTON)
        self.ok_button.clicked.connect(self.accept)
        self.ok_button.setEnabled(False)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setFixedSize(*BUTTON_SIZE)
        self.cancel_button.setStyleSheet(StyleSheets.CANCEL_BUTTON)
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        button_layout.addStretch()
        
        layout.addSpacing(20)
        layout.addLayout(button_layout)
        layout.addSpacing(10)

    def _on_select(self, mechanism_data: Dict[str, Any]) -> None:
        """Handle mechanism selection."""
        self.selected_mechanism_data = mechanism_data
        self.ok_button.setEnabled(True)
        # Update visual selection for all containers
        for container in self.preview_containers:
            container._set_selected_style(container.mechanism_data == mechanism_data)

    def _on_preview_click(self, mechanism_data: Dict[str, Any]) -> None:
        """Handle preview click to show mechanism in main view."""
        # Update visual selection for all containers
        for container in self.preview_containers:
            container._set_selected_style(container.mechanism_data == mechanism_data)
        # Emit the preview signal
        self.mechanism_preview_selected.emit(mechanism_data)

    @staticmethod
    def get_recommendation(
        user_motion_path: QPainterPath,
        generated_paths_filepath: str,
        num_samples_user_path: int = DEFAULT_NUM_SAMPLES_FOR_PATH,
        parent: Optional[QWidget] = None,
    ) -> Optional[Dict[str, Any]]:
        """Static method to show the dialog and return the selected mechanism data."""
        dialog = MechanismRecommendationDialog(
            user_motion_path, generated_paths_filepath, num_samples_user_path, parent
        )
        result = dialog.exec()
        if result == QDialog.DialogCode.Accepted:
            return dialog.selected_mechanism_data
        return None