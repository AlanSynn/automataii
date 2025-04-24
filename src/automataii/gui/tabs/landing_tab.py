import os
import logging
from pathlib import Path
from typing import Optional, List
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QScrollArea,
    QFrame,
    QGridLayout,
    QSizePolicy,
    QFileDialog,
    QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QTimer
from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont, QPalette, QCursor
from PyQt6.QtSvg import QSvgRenderer

from automataii.utils.paths import resolve_path, get_project_root


class ExampleImageWidget(QFrame):
    """Widget displaying a single example image that can be clicked."""

    clicked = pyqtSignal(str)  # Emits the image path when clicked

    # Color palette
    BITTERSWEET = "#ff595e"
    SUNGLOW = "#ffca3a"
    YELLOW_GREEN = "#8ac926"
    STEEL_BLUE = "#1982c4"
    ULTRA_VIOLET = "#6a4c93"

    def __init__(self, image_path: str, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.setFrameStyle(QFrame.Shape.Box)
        self.setFixedSize(200, 250)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._init_ui()
        self._apply_normal_style()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)

        # Image label
        self.image_label = QLabel()
        self.image_label.setScaledContents(False)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setFixedSize(180, 180)

        # Load and scale image
        pixmap = QPixmap(self.image_path)
        if not pixmap.isNull():
            scaled_pixmap = pixmap.scaled(
                180,
                180,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.image_label.setPixmap(scaled_pixmap)
        else:
            self.image_label.setText("Failed to load image")

        # Image name label
        image_name = Path(self.image_path).stem
        self.name_label = QLabel(image_name)
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setWordWrap(True)
        font = QFont()
        font.setPointSize(10)
        self.name_label.setFont(font)

        layout.addWidget(self.image_label)
        layout.addWidget(self.name_label)

    def _apply_normal_style(self):
        self.setStyleSheet(
            f"""
            ExampleImageWidget {{
                background-color: white;
                border: 2px solid {self.STEEL_BLUE};
                border-radius: 10px;
            }}
            QLabel {{
                color: #333333;
            }}
        """
        )

    def _apply_hover_style(self):
        self.setStyleSheet(
            f"""
            ExampleImageWidget {{
                background-color: {self.SUNGLOW}20;
                border: 3px solid {self.BITTERSWEET};
                border-radius: 10px;
            }}
            QLabel {{
                color: #333333;
            }}
        """
        )

    def enterEvent(self, event):
        self._apply_hover_style()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._apply_normal_style()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.image_path)
        super().mousePressEvent(event)


class LandingTab(QWidget):
    """Landing tab showing example images for quick selection."""

    # Signal emitted when an image is selected
    image_selected = pyqtSignal(str)  # Emits the selected image path

    # Color palette
    BITTERSWEET = "#ff595e"
    SUNGLOW = "#ffca3a"
    YELLOW_GREEN = "#8ac926"
    STEEL_BLUE = "#1982c4"
    ULTRA_VIOLET = "#6a4c93"

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window

        # Use resolve_path to find examples directory in both development and bundled environments
        self.example_dirs = [
            resolve_path("src/examples"),
            # Add fallback paths if needed
            get_project_root() / "src" / "examples",
        ]

        self.image_widgets: List[ExampleImageWidget] = []
        self._init_ui()
        self._load_example_images()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # Header
        header_layout = QVBoxLayout()
        header_layout.setSpacing(10)

        title_label = QLabel("Welcome to Automataii")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet(
            f"""
            color: {self.STEEL_BLUE};
            font-family: 'Comic Sans MS', 'Papyrus', cursive, fantasy;
            font-size: 64px;
            font-weight: bold;
            margin-bottom: 5px;
        """
        )

        # Description Label
        description_text = (
            "Create 2D character animations and generate mechanical automata designs."
        )
        description_label = QLabel(description_text)
        description_font = QFont()
        description_font.setPointSize(14)  # Slightly smaller than subtitle
        description_font.setBold(True)  # Make bold
        description_label.setFont(description_font)
        description_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        description_label.setStyleSheet(
            """
            color: black;
            margin-top: 2px;
            margin-bottom: 15px;
        """
        )
        description_label.setWordWrap(True)

        # Subtitle
        subtitle_label = QLabel(
            '"Select an example character to get started, or load your own image"'
        )
        subtitle_font = QFont()
        subtitle_font.setPointSize(16)  # Adjusted font size
        subtitle_font.setItalic(True)  # Make italic
        subtitle_font.setBold(True)  # Make bold
        subtitle_label.setFont(subtitle_font)
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_label.setStyleSheet(
            f"""
            color: black;
            margin-top: 10px;
            margin-bottom: 20px;
        """
        )

        header_layout.addWidget(title_label)
        header_layout.addWidget(description_label)  # Added description label
        header_layout.addWidget(subtitle_label)
        # header_layout.setSpacing(20) # Spacing will be handled by margins now
        main_layout.addLayout(header_layout)

        # self.refresh_btn = QPushButton("Refresh Examples")
        # self.refresh_btn.setFixedSize(150, 40)
        # self.refresh_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        # self.refresh_btn.setStyleSheet(f"""
        #     QPushButton {{
        #         background-color: {self.STEEL_BLUE};
        #         color: white;
        #         border-radius: 8px;
        #         font-size: 14px;
        #     }}
        #     QPushButton:hover {{
        #         background-color: {self.STEEL_BLUE}dd;
        #     }}
        #     QPushButton:pressed {{
        #         background-color: {self.STEEL_BLUE}bb;
        #     }}
        # """)
        # self.refresh_btn.clicked.connect(self._load_example_images)

        # button_layout.addStretch()
        # button_layout.addWidget(self.load_custom_btn)
        # button_layout.addStretch()
        # main_layout.addLayout(button_layout)

        # Scroll area for example images
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameStyle(
            QFrame.Shape.Box
        )  # Changed from NoFrame to Box for border
        self.scroll_area.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )  # Center content if smaller than viewport
        self.scroll_area.setStyleSheet(
            """
            QScrollArea {
                background-color: white;
                border: 1px solid black;
                border-radius: 10px;
            }
        """
        )

        # Container widget for grid layout
        self.scroll_content = QWidget()
        self.grid_layout = QGridLayout(self.scroll_content)
        self.grid_layout.setSpacing(20)
        self.grid_layout.setContentsMargins(20, 20, 20, 20)
        # To help center items if they don't fill the whole area
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.scroll_area.setWidget(self.scroll_content)
        main_layout.addWidget(self.scroll_area)

        # Status label
        self.status_label = QLabel("Loading example images...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet(
            f"color: {self.STEEL_BLUE}; font-style: italic;"
        )
        main_layout.addWidget(self.status_label)

    def _load_example_images(self):
        """Load example images from the examples directories."""
        # Clear existing widgets
        for widget in self.image_widgets:
            widget.deleteLater()
        self.image_widgets.clear()

        # Clear grid layout
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Find all image files
        image_paths = []
        supported_formats = ["*.png", "*.jpg", "*.jpeg", "*.gif"]

        for example_dir in self.example_dirs:
            if example_dir.exists():
                logging.info(f"Looking for example images in: {example_dir}")
                for format_pattern in supported_formats:
                    # Get direct images in examples directory
                    for img_path in example_dir.glob(format_pattern):
                        if img_path.is_file():
                            image_paths.append(img_path)
                            logging.debug(f"Found example image: {img_path}")

                    # Also check one level deep for character folders
                    for img_path in example_dir.glob(f"*/{format_pattern}"):
                        if img_path.is_file() and "character_data" not in str(img_path):
                            image_paths.append(img_path)
                            logging.debug(f"Found example image in subfolder: {img_path}")

        # Remove duplicates and sort
        image_paths = sorted(list(set(image_paths)))

        if not image_paths:
            self.status_label.setText("No example images found")
            self.status_label.setVisible(True)
            logging.warning("No example images found in any of the example directories")
            return
        else:
            self.status_label.setVisible(False)

        # Create image widgets in a grid
        columns = 4
        for idx, img_path in enumerate(image_paths):
            row = idx // columns
            col = idx % columns

            img_widget = ExampleImageWidget(str(img_path))
            img_widget.clicked.connect(self._on_image_selected)
            self.image_widgets.append(img_widget)
            self.grid_layout.addWidget(img_widget, row, col)

        # Add spacer to push items to the top - REMOVED to allow vertical centering by scroll_area.setAlignment
        # spacer_row = (len(image_paths) // columns) + 1
        # self.grid_layout.setRowStretch(spacer_row, 1)

        logging.info(f"Loaded {len(image_paths)} example images")

    def _on_image_selected(self, image_path: str):
        """Handle image selection."""
        logging.info(f"Example image selected: {image_path}")
        self.image_selected.emit(image_path)
        # The MainWindow._handle_landing_image_selected slot will handle
        # loading the image into ImageProcessingTab, switching tabs,
        # and updating the status bar.
        # Therefore, the direct calls to switch tab and load image here are removed.

    def _load_custom_image(self):
        """Open file dialog to load a custom image."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Character Image",
            str(Path.home()),
            "Image Files (*.png *.jpg *.jpeg *.gif);;All Files (*)",
        )

        if file_path:
            logging.info(f"Custom image selected: {file_path}")
            self.image_selected.emit(file_path)

            # Switch to image processing tab and load the image
            if hasattr(self.main_window, "image_proc_tab"):
                self.main_window.image_proc_tab._load_image_from_path(file_path)

                # Switch to the image processing tab
                for i in range(self.main_window.tab_widget.count()):
                    if (
                        self.main_window.tab_widget.widget(i)
                        == self.main_window.image_proc_tab
                    ):
                        self.main_window.tab_widget.setCurrentIndex(i)
                        break

            self.main_window.statusBar().showMessage(
                f"Loaded: {Path(file_path).name}", 3000
            )

    def refresh(self):
        """Refresh the example images display."""
        self._load_example_images()
