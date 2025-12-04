import logging
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCursor, QFont, QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from automataii.presentation.qt.shared import clear_layout
from automataii.utils.paths import resolve_path


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
        self.setFixedSize(200, 250)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._init_ui()
        self._apply_normal_style()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Load and scale image
        pixmap = QPixmap(self.image_path)
        if not pixmap.isNull():
            scaled_pixmap = pixmap.scaled(
                160, 160,
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

        layout.addStretch(1)
        layout.addWidget(self.image_label)
        layout.addWidget(self.name_label)
        layout.addStretch(1)

    def _apply_normal_style(self):
        self.setStyleSheet(
            """
            ExampleImageWidget {
                background-color: #FFFFFF;
                border: 2px solid #E9ECEF;
                border-radius: 15px;
                padding: 10px;
            }
            ExampleImageWidget QLabel {
                background-color: transparent;
                color: #333333;
                font-weight: 500;
                border: none;
            }
        """
        )

    def _apply_hover_style(self):
        self.setStyleSheet(
            f"""
            ExampleImageWidget {{
                background-color: #F8F9FA;
                border: 2px solid {self.STEEL_BLUE};
                border-radius: 15px;
                padding: 10px;
            }}
            ExampleImageWidget QLabel {{
                background-color: transparent;
                color: #000000;
                font-weight: bold;
                border: none;
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

    def __init__(self, main_window, parent=None, experiment_mode=False):
        super().__init__(parent)
        self.main_window = main_window
        self.experiment_mode = experiment_mode

        # Use resolve_path to find examples directory in both development and bundled environments
        # Search both layouts: dev (src/examples) and bundled (examples)
        self.example_dirs = [
            resolve_path("examples"),
            resolve_path("src/examples"),
        ]

        self.image_widgets: list[ExampleImageWidget] = []
        self._init_ui()
        self._load_example_images()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 10)
        main_layout.setSpacing(15)

        # Hero section with image and title
        hero_widget = QWidget()
        hero_widget.setStyleSheet("background-color: white; border: none;")

        hero_layout = QHBoxLayout(hero_widget)
        hero_layout.setContentsMargins(0, 0, 0, 0)
        hero_layout.setSpacing(15)
        hero_layout.setAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)

        # Logo/Image
        logo_label = QLabel()
        logo_path = resolve_path("resources/img/landing.png")
        if logo_path and logo_path.exists():
            pixmap = QPixmap(str(logo_path))
            scaled_pixmap = pixmap.scaled(70, 70, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            logo_label.setPixmap(scaled_pixmap)
        else:
            logo_label.setText("🤖")
            logo_label.setStyleSheet("font-size: 50px;")

        # Title
        title_label = QLabel("MotionSmith")
        title_label.setStyleSheet(f"""
            color: {self.STEEL_BLUE};
            font-family: 'Segoe UI', 'Arial', sans-serif;
            font-size: 40px;
            font-weight: bold;
        """)

        hero_layout.addWidget(logo_label)
        hero_layout.addWidget(title_label)

        main_layout.addWidget(hero_widget)

        # Subtitle and progression options
        subtitle_label = QLabel("Get started by selecting an example character or continue with your own!")
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_label.setStyleSheet("""
            color: #6c757d;
            font-size: 14px;
            margin-top: 5px;
            margin-bottom: 10px;
        """)
        main_layout.addWidget(subtitle_label)

        # Scroll area for example images
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameStyle(QFrame.Shape.NoFrame)
        self.scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollArea > QWidget > QWidget {
                background-color: white;
                border-radius: 15px;
                border: 2px solid #e9ecef;
            }
            QScrollBar:vertical {
                background-color: #f8f9fa;
                width: 12px;
                border-radius: 6px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: #6c757d;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #495057;
            }
        """)

        # Container widget for grid layout
        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet("""
            QWidget {
                background-color: white;
                border-radius: 15px;
                border: 2px solid #e9ecef;
            }
        """)
        self.grid_layout = QGridLayout(self.scroll_content)
        self.grid_layout.setSpacing(25)
        self.grid_layout.setContentsMargins(30, 30, 30, 30)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.scroll_area.setWidget(self.scroll_content)
        main_layout.addWidget(self.scroll_area)

        # Status label
        self.status_label = QLabel("Loading example images...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet(f"""
            color: {self.STEEL_BLUE};
            font-style: italic;
            font-size: 14px;
            margin: 10px;
            padding: 10px;
            background-color: rgba(25, 130, 196, 0.1);
            border-radius: 8px;
        """)
        main_layout.addWidget(self.status_label)

    def _load_example_images(self):
        """Load example images from the examples directories."""
        # Clear existing widgets
        for widget in self.image_widgets:
            widget.deleteLater()
        self.image_widgets.clear()

        # Clear grid layout
        clear_layout(self.grid_layout)

        # Find all image files
        image_paths = []
        supported_formats = ["*.png", "*.jpg", "*.jpeg", "*.gif"]

        for example_dir in self.example_dirs:
            if example_dir.exists():
                logging.info(f"Looking for example images in: {example_dir}")
                for format_pattern in supported_formats:
                    # Get direct images in examples directory only (not recursive)
                    for img_path in example_dir.glob(format_pattern):
                        if img_path.is_file():
                            image_paths.append(img_path)
                            logging.debug(f"Found example image: {img_path}")

        # Remove duplicates and sort
        image_paths = sorted(set(image_paths))

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
