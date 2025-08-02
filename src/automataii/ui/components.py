"""
Modern UI Components Library for Automataii
Provides reusable, styled components following the design system
"""

from typing import Optional, Callable
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QTimer
from PyQt6.QtGui import QIcon, QPainter, QPixmap, QColor
from PyQt6.QtWidgets import (
    QWidget, QPushButton, QLabel, QFrame, QVBoxLayout, 
    QHBoxLayout, QGraphicsDropShadowEffect, QToolButton,
    QProgressBar
)

from .design_system import design_system


class ModernCard(QFrame):
    """A modern card component with elevation and hover effects"""
    
    def __init__(self, title: Optional[str] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("ModernCard")
        self._title = title
        self._setup_ui()
        self._apply_styling()
        
    def _setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(
            design_system.spacing.lg,
            design_system.spacing.lg,
            design_system.spacing.lg,
            design_system.spacing.lg
        )
        self.main_layout.setSpacing(design_system.spacing.md)
        
        if self._title:
            self.title_label = QLabel(self._title)
            self.title_label.setFont(design_system.get_font("title_medium"))
            self.title_label.setStyleSheet(f"""
                color: {design_system.colors.on_surface};
                margin-bottom: {design_system.spacing.sm}px;
            """)
            self.main_layout.addWidget(self.title_label)
            
    def _apply_styling(self):
        self.setStyleSheet(f"""
            ModernCard {{
                background-color: {design_system.colors.surface};
                border-radius: 12px;
                border: 1px solid {design_system.colors.neutral_200};
            }}
        """)
        design_system.apply_shadow(self, design_system.elevation.level_1)
        
    def add_content(self, widget: QWidget):
        """Add content to the card"""
        self.main_layout.addWidget(widget)


class IconButton(QPushButton):
    """A modern icon button with hover effects"""
    
    def __init__(self, icon: QIcon, tooltip: str = "", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setIcon(icon)
        self.setToolTip(tooltip)
        self.setFixedSize(40, 40)
        self._setup_styling()
        
    def _setup_styling(self):
        self.setStyleSheet(f"""
            IconButton {{
                background-color: {design_system.colors.surface};
                border: 1px solid {design_system.colors.neutral_200};
                border-radius: 20px;
                padding: {design_system.spacing.sm}px;
            }}
            IconButton:hover {{
                background-color: {design_system.colors.primary};
                border-color: {design_system.colors.primary};
            }}
            IconButton:pressed {{
                background-color: {design_system.colors.primary_variant};
            }}
        """)
        design_system.apply_shadow(self, design_system.elevation.level_2)


class StatusIndicator(QFrame):
    """A status indicator with color and animation"""
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedSize(12, 12)
        self._status = "inactive"
        self._setup_ui()
        
    def _setup_ui(self):
        self.setStyleSheet(f"""
            StatusIndicator {{
                background-color: {design_system.colors.neutral_400};
                border-radius: 6px;
            }}
        """)
        
    def set_status(self, status: str):
        """Set status: 'active', 'warning', 'error', 'inactive'"""
        self._status = status
        colors = {
            'active': design_system.colors.success,
            'warning': design_system.colors.warning,
            'error': design_system.colors.error,
            'inactive': design_system.colors.neutral_400
        }
        color = colors.get(status, design_system.colors.neutral_400)
        
        self.setStyleSheet(f"""
            StatusIndicator {{
                background-color: {color};
                border-radius: 6px;
            }}
        """)
        
        # Add pulsing animation for active states
        if status in ['active', 'warning', 'error']:
            self._start_pulse_animation()
            
    def _start_pulse_animation(self):
        """Create a pulsing effect"""
        self.opacity_effect = QGraphicsDropShadowEffect()
        self.opacity_effect.setColor(QColor(self._get_status_color()))
        self.opacity_effect.setBlurRadius(10)
        self.opacity_effect.setOffset(0, 0)
        self.setGraphicsEffect(self.opacity_effect)
        
    def _get_status_color(self):
        colors = {
            'active': design_system.colors.success,
            'warning': design_system.colors.warning,
            'error': design_system.colors.error,
        }
        return colors.get(self._status, design_system.colors.neutral_400)


class ModernProgressBar(QProgressBar):
    """A modern progress bar with smooth animations"""
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setTextVisible(False)
        self.setMinimum(0)
        self.setMaximum(100)
        self._setup_styling()
        
    def _setup_styling(self):
        self.setStyleSheet(f"""
            QProgressBar {{
                background-color: {design_system.colors.neutral_200};
                border-radius: 6px;
                height: 12px;
            }}
            QProgressBar::chunk {{
                background-color: {design_system.colors.primary};
                border-radius: 6px;
            }}
        """)
        
    def set_value_animated(self, value: int):
        """Set value with smooth animation"""
        self.animation = QPropertyAnimation(self, b"value")
        self.animation.setDuration(300)
        self.animation.setStartValue(self.value())
        self.animation.setEndValue(value)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.animation.start()


class EmptyStateWidget(QWidget):
    """Widget to show when there's no content"""
    
    def __init__(self, 
                 icon: str = "📦",
                 title: str = "No Content",
                 subtitle: str = "Add some content to get started",
                 action_text: Optional[str] = None,
                 action_callback: Optional[Callable] = None,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui(icon, title, subtitle, action_text, action_callback)
        
    def _setup_ui(self, icon, title, subtitle, action_text, action_callback):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(design_system.spacing.md)
        
        # Icon
        icon_label = QLabel(icon)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet(f"""
            font-size: 48px;
            color: {design_system.colors.neutral_400};
        """)
        layout.addWidget(icon_label)
        
        # Title
        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setFont(design_system.get_font("headline_small"))
        title_label.setStyleSheet(f"color: {design_system.colors.neutral_600};")
        layout.addWidget(title_label)
        
        # Subtitle
        subtitle_label = QLabel(subtitle)
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_label.setFont(design_system.get_font("body_medium"))
        subtitle_label.setStyleSheet(f"color: {design_system.colors.neutral_500};")
        subtitle_label.setWordWrap(True)
        layout.addWidget(subtitle_label)
        
        # Action button
        if action_text and action_callback:
            action_btn = QPushButton(action_text)
            action_btn.clicked.connect(action_callback)
            action_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {design_system.colors.primary};
                    color: {design_system.colors.on_primary};
                    border: none;
                    border-radius: 4px;
                    padding: {design_system.spacing.sm}px {design_system.spacing.lg}px;
                    font-weight: 500;
                }}
                QPushButton:hover {{
                    background-color: {design_system.colors.primary_variant};
                }}
            """)
            layout.addWidget(action_btn, alignment=Qt.AlignmentFlag.AlignCenter)


class SectionHeader(QWidget):
    """A section header with optional action buttons"""
    
    def __init__(self, 
                 title: str,
                 subtitle: Optional[str] = None,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui(title, subtitle)
        
    def _setup_ui(self, title, subtitle):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, design_system.spacing.md)
        layout.setSpacing(design_system.spacing.xs)
        
        # Title
        self.title_label = QLabel(title)
        self.title_label.setFont(design_system.get_font("headline_medium"))
        self.title_label.setStyleSheet(f"color: {design_system.colors.on_surface};")
        layout.addWidget(self.title_label)
        
        # Subtitle
        if subtitle:
            self.subtitle_label = QLabel(subtitle)
            self.subtitle_label.setFont(design_system.get_font("body_medium"))
            self.subtitle_label.setStyleSheet(f"color: {design_system.colors.neutral_600};")
            layout.addWidget(self.subtitle_label)
            
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet(f"""
            background-color: {design_system.colors.neutral_200};
            max-height: 1px;
            margin-top: {design_system.spacing.sm}px;
        """)
        layout.addWidget(separator)
        
    def add_action(self, widget: QWidget):
        """Add an action widget to the header"""
        if not hasattr(self, 'action_layout'):
            # Create horizontal layout for title and actions
            h_layout = QHBoxLayout()
            h_layout.setContentsMargins(0, 0, 0, 0)
            
            # Move title to horizontal layout
            self.layout().removeWidget(self.title_label)
            h_layout.addWidget(self.title_label)
            h_layout.addStretch()
            
            self.action_layout = QHBoxLayout()
            self.action_layout.setSpacing(design_system.spacing.sm)
            h_layout.addLayout(self.action_layout)
            
            # Insert at the beginning
            self.layout().insertLayout(0, h_layout)
            
        self.action_layout.addWidget(widget)