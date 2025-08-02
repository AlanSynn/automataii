"""
Central Design System for Automataii
Modern, unified design system based on Material Design 3.0 principles
"""

from __future__ import annotations

from typing import Dict, Any, Optional, ClassVar
from dataclasses import dataclass, field
from enum import Enum
from PyQt6.QtCore import QObject, pyqtSignal, QPropertyAnimation, QEasingCurve, Qt
from PyQt6.QtGui import QColor, QPalette, QFont, QFontDatabase
from PyQt6.QtWidgets import (
    QWidget, QPushButton, QLabel, QLineEdit, QTextEdit,
    QComboBox, QSlider, QCheckBox, QRadioButton,
    QGroupBox, QFrame, QScrollArea, QGraphicsDropShadowEffect
)


class ThemeMode(Enum):
    LIGHT = "light"
    DARK = "dark"
    SYSTEM = "system"


@dataclass
class ColorPalette:
    """Material Design 3.0 inspired color palette"""
    # Primary colors
    primary: str = "#5c6bc0"  # Indigo
    primary_variant: str = "#3949ab"
    on_primary: str = "#ffffff"
    
    # Secondary colors  
    secondary: str = "#ff6f00"  # Amber
    secondary_variant: str = "#ff8f00"
    on_secondary: str = "#000000"
    
    # Background colors
    background: str = "#fafafa"
    surface: str = "#ffffff"
    error: str = "#d32f2f"
    
    # Text colors
    on_background: str = "#212121"
    on_surface: str = "#212121"
    on_error: str = "#ffffff"
    
    # Additional colors
    success: str = "#388e3c"
    warning: str = "#f57c00"
    info: str = "#1976d2"
    
    # Neutral colors
    neutral_50: str = "#fafafa"
    neutral_100: str = "#f5f5f5"
    neutral_200: str = "#eeeeee"
    neutral_300: str = "#e0e0e0"
    neutral_400: str = "#bdbdbd"
    neutral_500: str = "#9e9e9e"
    neutral_600: str = "#757575"
    neutral_700: str = "#616161"
    neutral_800: str = "#424242"
    neutral_900: str = "#212121"


@dataclass
class DarkColorPalette(ColorPalette):
    """Dark theme color palette"""
    primary: str = "#9fa8da"
    primary_variant: str = "#c5cae9"
    on_primary: str = "#000000"
    
    secondary: str = "#ffb74d"
    secondary_variant: str = "#ffcc80"
    on_secondary: str = "#000000"
    
    background: str = "#121212"
    surface: str = "#1e1e1e"
    
    on_background: str = "#e0e0e0"
    on_surface: str = "#e0e0e0"
    
    neutral_50: str = "#303030"
    neutral_100: str = "#424242"
    neutral_200: str = "#616161"
    neutral_300: str = "#757575"
    neutral_400: str = "#9e9e9e"
    neutral_500: str = "#bdbdbd"
    neutral_600: str = "#e0e0e0"
    neutral_700: str = "#eeeeee"
    neutral_800: str = "#f5f5f5"
    neutral_900: str = "#fafafa"


@dataclass
class Typography:
    """Typography system with consistent font sizes and weights"""
    font_family: str = "SF Pro Display, Helvetica Neue, Arial, sans-serif"
    
    # Display styles
    display_large: Dict[str, Any] = field(default_factory=lambda: {
        "size": 57, "weight": QFont.Weight.Light, "line_height": 64
    })
    display_medium: Dict[str, Any] = field(default_factory=lambda: {
        "size": 45, "weight": QFont.Weight.Normal, "line_height": 52
    })
    display_small: Dict[str, Any] = field(default_factory=lambda: {
        "size": 36, "weight": QFont.Weight.Normal, "line_height": 44
    })
    
    # Headline styles
    headline_large: Dict[str, Any] = field(default_factory=lambda: {
        "size": 32, "weight": QFont.Weight.Normal, "line_height": 40
    })
    headline_medium: Dict[str, Any] = field(default_factory=lambda: {
        "size": 28, "weight": QFont.Weight.Normal, "line_height": 36
    })
    headline_small: Dict[str, Any] = field(default_factory=lambda: {
        "size": 24, "weight": QFont.Weight.Normal, "line_height": 32
    })
    
    # Title styles
    title_large: Dict[str, Any] = field(default_factory=lambda: {
        "size": 22, "weight": QFont.Weight.Medium, "line_height": 28
    })
    title_medium: Dict[str, Any] = field(default_factory=lambda: {
        "size": 16, "weight": QFont.Weight.Medium, "line_height": 24
    })
    title_small: Dict[str, Any] = field(default_factory=lambda: {
        "size": 14, "weight": QFont.Weight.Medium, "line_height": 20
    })
    
    # Body styles
    body_large: Dict[str, Any] = field(default_factory=lambda: {
        "size": 16, "weight": QFont.Weight.Normal, "line_height": 24
    })
    body_medium: Dict[str, Any] = field(default_factory=lambda: {
        "size": 14, "weight": QFont.Weight.Normal, "line_height": 20
    })
    body_small: Dict[str, Any] = field(default_factory=lambda: {
        "size": 12, "weight": QFont.Weight.Normal, "line_height": 16
    })
    
    # Label styles
    label_large: Dict[str, Any] = field(default_factory=lambda: {
        "size": 14, "weight": QFont.Weight.Medium, "line_height": 20
    })
    label_medium: Dict[str, Any] = field(default_factory=lambda: {
        "size": 12, "weight": QFont.Weight.Medium, "line_height": 16
    })
    label_small: Dict[str, Any] = field(default_factory=lambda: {
        "size": 11, "weight": QFont.Weight.Medium, "line_height": 16
    })


@dataclass
class Spacing:
    """Consistent spacing system (8px grid)"""
    xs: int = 4
    sm: int = 8
    md: int = 16
    lg: int = 24
    xl: int = 32
    xxl: int = 48


@dataclass
class Elevation:
    """Material Design elevation system"""
    level_0: int = 0
    level_1: int = 1  # Cards on background
    level_2: int = 3  # Raised buttons
    level_3: int = 6  # FAB
    level_4: int = 8  # Navigation drawer
    level_5: int = 12  # Dialogs


class DesignSystem(QObject):
    """Central design system manager"""
    
    theme_changed = pyqtSignal(ThemeMode)
    
    _instance: ClassVar[Optional['DesignSystem']] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        super().__init__()
        self._initialized = True
        self._current_theme = ThemeMode.LIGHT
        self._light_palette = ColorPalette()
        self._dark_palette = DarkColorPalette()
        self._typography = Typography()
        self._spacing = Spacing()
        self._elevation = Elevation()
        
        # Load custom fonts
        self._load_fonts()
    
    def _load_fonts(self):
        """Load custom fonts"""
        # Font files should be in ui/fonts/
        # This is handled by the main application
        pass
    
    @property
    def current_theme(self) -> ThemeMode:
        return self._current_theme
    
    @property
    def colors(self) -> ColorPalette:
        """Get current color palette based on theme"""
        return self._dark_palette if self._current_theme == ThemeMode.DARK else self._light_palette
    
    @property
    def typography(self) -> Typography:
        return self._typography
    
    @property
    def spacing(self) -> Spacing:
        return self._spacing
    
    @property
    def elevation(self) -> Elevation:
        return self._elevation
    
    def set_theme(self, theme: ThemeMode):
        """Change the application theme"""
        if theme != self._current_theme:
            self._current_theme = theme
            self.theme_changed.emit(theme)
    
    def get_font(self, style: str) -> QFont:
        """Get a QFont for a typography style"""
        style_data = getattr(self.typography, style, self.typography.body_medium)
        font = QFont(self.typography.font_family)
        font.setPointSize(style_data["size"])
        font.setWeight(style_data["weight"])
        return font
    
    def apply_shadow(self, widget: QWidget, elevation: int = 1):
        """Apply elevation shadow to widget"""
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(elevation * 2)
        shadow.setColor(QColor(0, 0, 0, 50))
        shadow.setOffset(0, elevation)
        widget.setGraphicsEffect(shadow)
    
    def get_stylesheet(self) -> str:
        """Get the complete stylesheet for the current theme"""
        colors = self.colors
        spacing = self.spacing
        
        return f"""
        /* Global Application Styles */
        QWidget {{
            font-family: "{self.typography.font_family}";
            font-size: {self.typography.body_medium['size']}px;
            color: {colors.on_background};
            background-color: {colors.background};
        }}
        
        /* Main Window */
        QMainWindow {{
            background-color: {colors.background};
        }}
        
        /* Tab Widget */
        QTabWidget::pane {{
            border: none;
            background-color: {colors.surface};
        }}
        
        QTabBar::tab {{
            background-color: {colors.surface};
            color: {colors.on_surface};
            padding: {spacing.sm}px {spacing.md}px;
            margin-right: {spacing.xs}px;
            border: none;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
            font-weight: 500;
            min-width: 120px;
        }}
        
        QTabBar::tab:selected {{
            background-color: {colors.primary};
            color: {colors.on_primary};
        }}
        
        QTabBar::tab:hover:!selected {{
            background-color: {colors.neutral_100};
        }}
        
        /* Buttons */
        QPushButton {{
            background-color: {colors.primary};
            color: {colors.on_primary};
            border: none;
            border-radius: 4px;
            padding: {spacing.sm}px {spacing.md}px;
            font-weight: 500;
            font-size: {self.typography.label_large['size']}px;
            min-height: 36px;
        }}
        
        QPushButton:hover {{
            background-color: {colors.primary_variant};
        }}
        
        QPushButton:pressed {{
            background-color: {colors.primary_variant};
        }}
        
        QPushButton:disabled {{
            background-color: {colors.neutral_300};
            color: {colors.neutral_500};
        }}
        
        /* Secondary Button */
        QPushButton.secondary {{
            background-color: {colors.surface};
            color: {colors.primary};
            border: 1px solid {colors.primary};
        }}
        
        QPushButton.secondary:hover {{
            background-color: {colors.primary};
            color: {colors.on_primary};
        }}
        
        /* Text Button */
        QPushButton.text {{
            background-color: transparent;
            color: {colors.primary};
            border: none;
            padding: {spacing.sm}px {spacing.md}px;
        }}
        
        QPushButton.text:hover {{
            background-color: {colors.primary}20;
        }}
        
        /* Input Fields */
        QLineEdit, QTextEdit, QPlainTextEdit {{
            background-color: {colors.surface};
            color: {colors.on_surface};
            border: 1px solid {colors.neutral_300};
            border-radius: 4px;
            padding: {spacing.sm}px;
            font-size: {self.typography.body_medium['size']}px;
        }}
        
        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
            border: 2px solid {colors.primary};
            padding: {spacing.sm - 1}px;
        }}
        
        /* ComboBox */
        QComboBox {{
            background-color: {colors.surface};
            color: {colors.on_surface};
            border: 1px solid {colors.neutral_300};
            border-radius: 4px;
            padding: {spacing.sm}px;
            min-height: 36px;
        }}
        
        QComboBox:hover {{
            border: 1px solid {colors.primary};
        }}
        
        QComboBox:focus {{
            border: 2px solid {colors.primary};
            padding: {spacing.sm - 1}px;
        }}
        
        QComboBox::drop-down {{
            border: none;
            width: 24px;
        }}
        
        QComboBox::down-arrow {{
            width: 12px;
            height: 12px;
        }}
        
        /* Sliders */
        QSlider::groove:horizontal {{
            background-color: {colors.neutral_300};
            height: 4px;
            border-radius: 2px;
        }}
        
        QSlider::handle:horizontal {{
            background-color: {colors.primary};
            width: 20px;
            height: 20px;
            margin: -8px 0;
            border-radius: 10px;
        }}
        
        QSlider::handle:horizontal:hover {{
            background-color: {colors.primary_variant};
        }}
        
        /* CheckBox and RadioButton */
        QCheckBox, QRadioButton {{
            color: {colors.on_surface};
            spacing: {spacing.sm}px;
        }}
        
        QCheckBox::indicator, QRadioButton::indicator {{
            width: 18px;
            height: 18px;
        }}
        
        QCheckBox::indicator:unchecked {{
            background-color: {colors.surface};
            border: 2px solid {colors.neutral_400};
            border-radius: 2px;
        }}
        
        QCheckBox::indicator:checked {{
            background-color: {colors.primary};
            border: none;
            border-radius: 2px;
            image: url(check.svg);
        }}
        
        QRadioButton::indicator:unchecked {{
            background-color: {colors.surface};
            border: 2px solid {colors.neutral_400};
            border-radius: 9px;
        }}
        
        QRadioButton::indicator:checked {{
            background-color: {colors.primary};
            border: 4px solid {colors.primary};
            border-radius: 9px;
        }}
        
        /* GroupBox */
        QGroupBox {{
            background-color: {colors.surface};
            border: 1px solid {colors.neutral_200};
            border-radius: 8px;
            margin-top: {spacing.md}px;
            padding-top: {spacing.md}px;
            font-weight: 500;
        }}
        
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: {spacing.md}px;
            padding: 0 {spacing.xs}px;
            background-color: {colors.surface};
            color: {colors.primary};
        }}
        
        /* Labels */
        QLabel {{
            color: {colors.on_surface};
        }}
        
        QLabel.heading {{
            font-size: {self.typography.headline_medium['size']}px;
            font-weight: 500;
            color: {colors.on_surface};
            margin-bottom: {spacing.md}px;
        }}
        
        QLabel.subheading {{
            font-size: {self.typography.title_medium['size']}px;
            font-weight: 500;
            color: {colors.on_surface};
            margin-bottom: {spacing.sm}px;
        }}
        
        QLabel.caption {{
            font-size: {self.typography.body_small['size']}px;
            color: {colors.neutral_600};
        }}
        
        /* Scroll Areas */
        QScrollArea {{
            background-color: {colors.background};
            border: none;
        }}
        
        QScrollBar:vertical {{
            background-color: {colors.neutral_100};
            width: 12px;
            border-radius: 6px;
        }}
        
        QScrollBar::handle:vertical {{
            background-color: {colors.neutral_400};
            border-radius: 6px;
            min-height: 20px;
        }}
        
        QScrollBar::handle:vertical:hover {{
            background-color: {colors.neutral_500};
        }}
        
        /* Tool Tips */
        QToolTip {{
            background-color: {colors.neutral_700};
            color: {colors.neutral_50};
            border: none;
            padding: {spacing.xs}px {spacing.sm}px;
            border-radius: 4px;
            font-size: {self.typography.body_small['size']}px;
        }}
        
        /* Status Bar */
        QStatusBar {{
            background-color: {colors.surface};
            color: {colors.on_surface};
            border-top: 1px solid {colors.neutral_200};
        }}
        
        /* Progress Bar */
        QProgressBar {{
            background-color: {colors.neutral_200};
            border-radius: 4px;
            height: 4px;
            text-align: center;
        }}
        
        QProgressBar::chunk {{
            background-color: {colors.primary};
            border-radius: 4px;
        }}
        
        /* Frames and Separators */
        QFrame.card {{
            background-color: {colors.surface};
            border-radius: 8px;
            padding: {spacing.md}px;
        }}
        
        QFrame.separator {{
            background-color: {colors.neutral_200};
            max-height: 1px;
            margin: {spacing.md}px 0;
        }}
        """


# Component Factory Classes
class StyledComponents:
    """Factory for creating styled components"""
    
    @staticmethod
    def create_button(text: str, variant: str = "primary", parent: Optional[QWidget] = None) -> QPushButton:
        """Create a styled button"""
        button = QPushButton(text, parent)
        button.setProperty("class", variant)
        
        if variant == "secondary":
            button.setObjectName("secondary")
        elif variant == "text":
            button.setObjectName("text")
        
        return button
    
    @staticmethod
    def create_heading(text: str, level: int = 1, parent: Optional[QWidget] = None) -> QLabel:
        """Create a styled heading label"""
        label = QLabel(text, parent)
        design_system = DesignSystem()
        
        if level == 1:
            label.setFont(design_system.get_font("headline_large"))
        elif level == 2:
            label.setFont(design_system.get_font("headline_medium"))
        elif level == 3:
            label.setFont(design_system.get_font("headline_small"))
        else:
            label.setFont(design_system.get_font("title_large"))
        
        label.setProperty("class", "heading")
        return label
    
    @staticmethod
    def create_card(parent: Optional[QWidget] = None) -> QFrame:
        """Create a card container"""
        card = QFrame(parent)
        card.setProperty("class", "card")
        design_system = DesignSystem()
        design_system.apply_shadow(card, design_system.elevation.level_1)
        return card
    
    @staticmethod
    def create_separator(parent: Optional[QWidget] = None) -> QFrame:
        """Create a horizontal separator"""
        separator = QFrame(parent)
        separator.setProperty("class", "separator")
        separator.setFrameShape(QFrame.Shape.HLine)
        return separator


# Export the singleton instance
design_system = DesignSystem()