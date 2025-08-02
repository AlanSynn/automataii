# src/automataii/ui/tabs/landing/ui_panel.py

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

from automataii.utils.paths import resolve_path
from automataii.ui.design_system import design_system, StyledComponents

logger = logging.getLogger(__name__)


class ExampleImageWidget(QFrame):
    """Widget displaying a single example image that can be clicked."""

    clicked = pyqtSignal(str)  # Emits the image path when clicked

    def __init__(self, image_path: str, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.setFixedSize(220, 280)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._init_ui()
        self._apply_normal_style()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            design_system.spacing.md,
            design_system.spacing.md,
            design_system.spacing.md,
            design_system.spacing.md
        )
        layout.setSpacing(design_system.spacing.sm)

        # Image container with background
        image_container = QWidget()
        image_container.setFixedSize(180, 180)
        image_container.setStyleSheet(f"""
            QWidget {{
                background-color: {design_system.colors.neutral_100};
                border-radius: 8px;
            }}
        """)
        
        image_layout = QVBoxLayout(image_container)
        image_layout.setContentsMargins(0, 0, 0, 0)
        
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image_layout.addWidget(self.image_label)

        # Load and scale image
        pixmap = QPixmap(self.image_path)
        if not pixmap.isNull():
            scaled_pixmap = pixmap.scaled(
                160,
                160,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.image_label.setPixmap(scaled_pixmap)
        else:
            self.image_label.setText("Failed to load image")
            self.image_label.setStyleSheet(f"color: {design_system.colors.error};")

        # Image name label
        image_name = Path(self.image_path).stem.replace("_", " ").title()
        self.name_label = QLabel(image_name)
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setWordWrap(True)
        self.name_label.setFont(design_system.get_font("title_small"))
        self.name_label.setStyleSheet(f"""
            color: {design_system.colors.on_surface};
            padding: {design_system.spacing.xs}px;
        """)

        layout.addWidget(image_container)
        layout.addWidget(self.name_label)
        layout.addStretch()

    def _apply_normal_style(self):
        self.setStyleSheet(f"""
            ExampleImageWidget {{
                background-color: {design_system.colors.surface};
                border: 1px solid {design_system.colors.neutral_200};
                border-radius: 12px;
            }}
        """)
        design_system.apply_shadow(self, design_system.elevation.level_1)

    def _apply_hover_style(self):
        self.setStyleSheet(f"""
            ExampleImageWidget {{
                background-color: {design_system.colors.surface};
                border: 2px solid {design_system.colors.primary};
                border-radius: 12px;
            }}
        """)
        design_system.apply_shadow(self, design_system.elevation.level_3)

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


class LandingUIPanel(QWidget):
    """
    UI panel for Landing tab.
    Contains all UI components for the landing page layout.
    """

    # Signal for image selection
    image_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.image_widgets: list[ExampleImageWidget] = []
        self._setup_ui()

    def _setup_ui(self):
        """Create and layout all UI components."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(
            design_system.spacing.xl,
            design_system.spacing.xl,
            design_system.spacing.xl,
            design_system.spacing.lg
        )
        main_layout.setSpacing(design_system.spacing.lg)

        # Hero section with image and title
        hero_widget = self._create_hero_section()
        main_layout.addWidget(hero_widget)

        # Subtitle
        subtitle_label = QLabel(
            "Get started by selecting an example character or continue with your own!"
        )
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_label.setFont(design_system.get_font("body_large"))
        subtitle_label.setStyleSheet(f"""
            color: {design_system.colors.neutral_600};
            margin-top: {design_system.spacing.sm}px;
            margin-bottom: {design_system.spacing.lg}px;
        """)
        main_layout.addWidget(subtitle_label)

        # Scroll area for example images
        self.scroll_area = self._create_scroll_area()
        main_layout.addWidget(self.scroll_area)

        # Status label
        self.status_label = QLabel("Loading example images...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setFont(design_system.get_font("body_medium"))
        self.status_label.setStyleSheet(f"""
            color: {design_system.colors.primary};
            font-style: italic;
            margin: {design_system.spacing.md}px;
            padding: {design_system.spacing.md}px;
            background-color: {design_system.colors.primary}20;
            border-radius: 8px;
        """)
        main_layout.addWidget(self.status_label)

    def _create_hero_section(self) -> QWidget:
        """Create the hero section with logo and title."""
        hero_widget = QWidget()
        hero_widget.setStyleSheet(f"background-color: {design_system.colors.background}; border: none;")

        hero_layout = QHBoxLayout(hero_widget)
        hero_layout.setContentsMargins(0, 0, 0, 0)
        hero_layout.setSpacing(design_system.spacing.lg)
        hero_layout.setAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)

        # Logo/Image with shadow effect
        logo_container = QFrame()
        logo_container.setFixedSize(80, 80)
        logo_container.setStyleSheet(f"""
            QFrame {{
                background-color: {design_system.colors.surface};
                border-radius: 16px;
            }}
        """)
        design_system.apply_shadow(logo_container, design_system.elevation.level_2)
        
        logo_layout = QVBoxLayout(logo_container)
        logo_layout.setContentsMargins(10, 10, 10, 10)
        
        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_path = resolve_path("resources/img/landing.png")
        if logo_path and logo_path.exists():
            pixmap = QPixmap(str(logo_path))
            scaled_pixmap = pixmap.scaled(
                60,
                60,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            logo_label.setPixmap(scaled_pixmap)
        else:
            logo_label.setText("🤖")
            logo_label.setStyleSheet("font-size: 40px;")
        
        logo_layout.addWidget(logo_label)

        # Title with gradient effect (simulated with primary color)
        title_label = QLabel("Automataii")
        title_label.setFont(design_system.get_font("display_medium"))
        title_label.setStyleSheet(f"""
            color: {design_system.colors.primary};
            font-weight: 700;
        """)

        hero_layout.addWidget(logo_container)
        hero_layout.addWidget(title_label)

        return hero_widget

    def _create_scroll_area(self) -> QScrollArea:
        """Create the scroll area for example images."""
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameStyle(QFrame.Shape.NoFrame)
        scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scroll_area.setStyleSheet(f"""
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
            QScrollArea > QWidget > QWidget {{
                background-color: {design_system.colors.surface};
                border-radius: 16px;
                border: 1px solid {design_system.colors.neutral_200};
            }}
            QScrollBar:vertical {{
                background-color: {design_system.colors.neutral_100};
                width: 12px;
                border-radius: 6px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {design_system.colors.neutral_400};
                border-radius: 6px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {design_system.colors.neutral_500};
            }}
        """)

        # Container widget for grid layout
        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet(f"""
            QWidget {{
                background-color: {design_system.colors.surface};
                border-radius: 16px;
            }}
        """)
        design_system.apply_shadow(self.scroll_content, design_system.elevation.level_1)
        
        self.grid_layout = QGridLayout(self.scroll_content)
        self.grid_layout.setSpacing(design_system.spacing.lg)
        self.grid_layout.setContentsMargins(
            design_system.spacing.xl,
            design_system.spacing.xl,
            design_system.spacing.xl,
            design_system.spacing.xl
        )
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        scroll_area.setWidget(self.scroll_content)
        return scroll_area

    def update_images_display(self, image_paths: list[Path]) -> None:
        """Update the display with new image paths."""
        # Clear existing widgets
        for widget in self.image_widgets:
            widget.deleteLater()
        self.image_widgets.clear()

        # Clear grid layout
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not image_paths:
            self.status_label.setText("No example images found")
            self.status_label.setVisible(True)
            logger.warning("No example images found")
            return
        else:
            self.status_label.setVisible(False)

        # Create image widgets in a grid
        columns = 4
        for idx, img_path in enumerate(image_paths):
            row = idx // columns
            col = idx % columns

            img_widget = ExampleImageWidget(str(img_path))
            img_widget.clicked.connect(self._on_image_clicked)
            self.image_widgets.append(img_widget)
            self.grid_layout.addWidget(img_widget, row, col)

        logger.info(f"Updated display with {len(image_paths)} example images")

    def _on_image_clicked(self, image_path: str) -> None:
        """Handle image click and emit signal."""
        self.image_selected.emit(image_path)

    def update_ui_from_state(self, state) -> None:
        """Update UI elements based on state changes."""
        # Update loading status
        if state.is_loading:
            self.status_label.setText(state.status_message)
            self.status_label.setVisible(True)
        else:
            if state.example_image_paths:
                self.status_label.setVisible(False)
            else:
                self.status_label.setText(state.status_message)
                self.status_label.setVisible(True)

        # Update status message if not loading
        if not state.is_loading and state.status_message:
            self.status_label.setText(state.status_message)
            self.status_label.setVisible(True)

    def clear_images(self) -> None:
        """Clear all displayed images."""
        for widget in self.image_widgets:
            widget.deleteLater()
        self.image_widgets.clear()

        # Clear grid layout
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.status_label.setText("Loading example images...")
        self.status_label.setVisible(True)

    def clear_temporary_states(self) -> None:
        """Clear any temporary UI states when tab is deactivated."""
        # Clear any temporary hover states or selections
        # Reset status to empty if it's showing temporary messages
        if hasattr(self, 'status_label') and self.status_label:
            # Only clear temporary status messages, not permanent ones
            current_text = self.status_label.text()
            if "Loading" in current_text or "Error" in current_text:
                self.status_label.setText("")
                self.status_label.setVisible(False)
        
        # Clear any temporary visual states
        if hasattr(self, 'scroll_area') and self.scroll_area:
            # Reset scroll position to top for consistency
            scrollbar = self.scroll_area.verticalScrollBar()
            if scrollbar:
                scrollbar.setValue(0)
