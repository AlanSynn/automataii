"""
Style Factory - Consistent styling for Qt widgets across the application.

Extracted as shared component from EditorTab and ImageProcessingTab.
Provides factory methods for consistent styling of buttons, group boxes, etc.

Design Pattern: Factory (creates styled widget configurations)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ColorPalette:
    """Application color palette for consistent theming."""

    # Primary colors
    primary: str = "#5c85d6"
    primary_hover: str = "#4b74c5"
    primary_pressed: str = "#3a63b4"

    # Secondary colors (soft blue)
    secondary: str = "#a7c7e7"
    secondary_hover: str = "#96b6d6"
    secondary_pressed: str = "#85a5c5"

    # Neutral colors
    background: str = "#ffffff"
    surface: str = "#f8f9fa"
    border: str = "#dee2e6"
    border_hover: str = "#adb5bd"
    text: str = "#495057"
    text_muted: str = "#6c757d"

    # Status colors
    success: str = "#28a745"
    warning: str = "#ffc107"
    danger: str = "#e7a7a7"
    info: str = "#17a2b8"

    # Disabled state
    disabled_bg: str = "#e0e6ed"
    disabled_text: str = "#a0aab5"
    disabled_border: str = "#dbe4f0"


class StyleFactory:
    """
    Factory for creating consistent widget styles.

    Provides pre-defined styles for common widget types used across tabs.
    All styles are theme-aware and can be customized via the color palette.

    Usage:
        style = StyleFactory.zoom_button_style()
        button.setStyleSheet(style)

    Time Complexity: O(1) for all methods
    """

    _palette = ColorPalette()

    @classmethod
    def set_palette(cls, palette: ColorPalette) -> None:
        """Set a custom color palette."""
        cls._palette = palette

    @classmethod
    def zoom_button_style(cls) -> str:
        """Style for zoom control buttons."""
        p = cls._palette
        return f"""
            QPushButton {{
                background-color: {p.surface};
                border: 1px solid {p.border};
                border-radius: 4px;
                padding: 4px 8px;
                font-weight: bold;
                color: {p.text};
                min-height: 22px;
                min-width: 30px;
                font-size: 10pt;
            }}
            QPushButton:hover {{
                background-color: #e9ecef;
                border-color: {p.border_hover};
            }}
            QPushButton:pressed {{
                background-color: {p.border};
                border-color: {p.text_muted};
            }}
        """

    @classmethod
    def action_button_style(cls) -> str:
        """Style for action buttons (primary soft blue)."""
        p = cls._palette
        return f"""
            QPushButton {{
                background-color: {p.secondary};
                border: 1px solid {p.secondary_hover};
                border-radius: 5px;
                padding: 6px 12px;
                font-weight: bold;
                color: #ffffff;
                min-height: 24px;
            }}
            QPushButton:hover {{
                background-color: {p.secondary_hover};
                border-color: {p.secondary_pressed};
            }}
            QPushButton:pressed {{
                background-color: {p.secondary_pressed};
                border-color: #7494b4;
            }}
            QPushButton:disabled {{
                background-color: {p.disabled_bg};
                color: {p.disabled_text};
                border-color: {p.disabled_border};
            }}
        """

    @classmethod
    def action_button_checked_style(cls) -> str:
        """Style for checkable action buttons."""
        p = cls._palette
        base = cls.action_button_style()
        return (
            base
            + f"""
            QPushButton:checked {{
                background-color: {p.primary};
                border-color: {p.primary_hover};
                color: white;
            }}
        """
        )

    @classmethod
    def danger_button_style(cls) -> str:
        """Style for danger/clear buttons."""
        p = cls._palette
        return f"""
            QPushButton {{
                background-color: {p.danger};
                border: 1px solid #d69696;
                border-radius: 5px;
                padding: 6px 12px;
                font-weight: bold;
                color: #ffffff;
                min-height: 24px;
            }}
            QPushButton:hover {{
                background-color: #d69696;
                border-color: #c58585;
            }}
            QPushButton:pressed {{
                background-color: #c58585;
                border-color: #b47474;
            }}
            QPushButton:disabled {{
                background-color: {p.disabled_bg};
                color: {p.disabled_text};
                border-color: {p.disabled_border};
            }}
        """

    @classmethod
    def compact_animation_button_style(cls) -> str:
        """Style for compact animation control buttons (play, stop, reset)."""
        p = cls._palette
        return f"""
            QPushButton {{
                background-color: {p.secondary};
                border: 1px solid {p.secondary_hover};
                border-radius: 5px;
                padding: 4px 6px;
                font-weight: bold;
                color: #ffffff;
                min-height: 24px;
                min-width: 30px;
                max-width: 35px;
                font-size: 10pt;
            }}
            QPushButton:hover {{
                background-color: {p.secondary_hover};
                border-color: {p.secondary_pressed};
            }}
            QPushButton:pressed {{
                background-color: {p.secondary_pressed};
                border-color: #7494b4;
            }}
            QPushButton:disabled {{
                background-color: {p.disabled_bg};
                color: {p.disabled_text};
                border-color: {p.disabled_border};
            }}
        """

    @classmethod
    def group_box_style(cls) -> str:
        """Style for QGroupBox containers."""
        p = cls._palette
        return f"""
            QGroupBox {{
                background-color: {p.background};
                border: 1px solid #e3e9f0;
                border-radius: 9px;
                padding: 18px;
                margin-top: 15px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 10px;
                margin-left: 15px;
                font-size: 12pt;
                font-weight: bold;
                color: {p.primary};
                background-color: {p.background};
            }}
        """

    @classmethod
    def parts_list_style(cls) -> str:
        """Style for parts list widget."""
        p = cls._palette
        return f"""
            QListWidget {{
                background-color: white;
                border: 1px solid {p.border};
                border-radius: 6px;
                padding: 4px;
                font-size: 13px;
            }}
            QListWidget::item {{
                padding: 8px 12px;
                margin: 2px;
                border-radius: 4px;
                border: 1px solid transparent;
            }}
            QListWidget::item:selected {{
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #0078D7, stop: 1 #005a9e);
                color: white;
                border: 1px solid #004578;
            }}
            QListWidget::item:selected:!active {{
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #0078D7, stop: 1 #005a9e);
                color: white;
                border: 1px solid #004578;
            }}
            QListWidget::item:hover {{
                background-color: {p.surface};
                border: 1px solid {p.border};
            }}
        """

    @classmethod
    def smoothness_slider_style(cls) -> str:
        """Style for smoothness/parameter sliders."""
        return """
            QSlider::groove:horizontal {
                border: 1px solid #c5d9f0;
                background: white;
                height: 6px;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #e8f2ff, stop:1 #b8d4f0);
                border: 1px solid #7ba7d1;
                width: 15px;
                margin-top: -4px;
                margin-bottom: -4px;
                border-radius: 7px;
            }
            QSlider::handle:horizontal:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #f0f7ff, stop:1 #d0e4f5);
                border: 1px solid #5a8bb5;
            }
            QSlider::sub-page:horizontal {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #a7c7e7, stop: 1 #d4e7f7);
                border: 1px solid #7ba7d1;
                height: 6px;
                border-radius: 3px;
            }
        """

    @classmethod
    def info_label_style(cls) -> str:
        """Style for informational labels."""
        return """
            background-color: #E6F7FF;
            border: 1px solid #BCE0FF;
            padding: 5px;
            border-radius: 3px;
        """

    @classmethod
    def status_label_style(cls) -> str:
        """Style for status labels."""
        return """
            font-weight: bold;
            font-size: 14px;
            color: #495057;
            padding: 8px;
            text-align: center;
        """
