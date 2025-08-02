"""
Mechanism Index Card widget for displaying mechanisms in the sidebar.
Modern card design with animated previews and metadata.
"""

import logging
from typing import Optional, Dict, Any
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve, QRect
from PyQt6.QtGui import QFont, QPixmap, QPainter, QColor, QBrush, QPen, QLinearGradient
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, 
    QPushButton, QGraphicsDropShadowEffect
)

from automataii.domain.fabrication.mechanisms.catalog_manager import MechanismInfo
from .styling import ModernStyling

logger = logging.getLogger(__name__)


class MechanismIndexCard(QFrame):
    """
    Modern card widget for displaying mechanism information with animated preview.
    
    Features:
    - Card-based design with hover effects
    - Animated mechanism thumbnail
    - Complexity badge
    - Metadata display
    - Click to select functionality
    """
    
    clicked = pyqtSignal(str)  # mechanism_id
    
    def __init__(self, mechanism_info: MechanismInfo, parent=None):
        super().__init__(parent)
        self.mechanism_info = mechanism_info
        self.is_selected = False
        self.is_hovered = False
        
        # Animation components
        self.animation_timer = QTimer()
        self.animation_time = 0.0
        self.preview_pixmap: Optional[QPixmap] = None
        
        self._setup_ui()
        self._setup_animations()
        self._apply_styling()
        
        logger.debug(f"Created mechanism card: {mechanism_info.name}")
    
    def _setup_ui(self):
        """Setup the card UI."""
        self.setFixedHeight(120)
        self.setFrameStyle(QFrame.Shape.Box)
        
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)
        
        # Header row with name and complexity badge
        header_layout = QHBoxLayout()
        
        # Mechanism name
        self.name_label = QLabel(self.mechanism_info.name)
        self.name_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.name_label.setWordWrap(True)
        header_layout.addWidget(self.name_label)
        
        # Complexity badge
        self.complexity_badge = self._create_complexity_badge()
        header_layout.addWidget(self.complexity_badge)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # Content row with preview and description
        content_layout = QHBoxLayout()
        
        # Animated preview area
        self.preview_label = QLabel()
        self.preview_label.setFixedSize(60, 45)
        self.preview_label.setStyleSheet("""
            QLabel {
                border: 1px solid #E0E0E0;
                border-radius: 4px;
                background-color: #FAFAFA;
            }
        """)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(self.preview_label)
        
        # Description and metadata
        info_layout = QVBoxLayout()
        
        # Description (truncated)
        self.description_label = QLabel(self._truncate_text(self.mechanism_info.description, 80))
        self.description_label.setFont(QFont("Segoe UI", 9))
        self.description_label.setStyleSheet("color: #757575;")
        self.description_label.setWordWrap(True)
        info_layout.addWidget(self.description_label)
        
        # Tags
        self.tags_label = QLabel(self._format_tags(self.mechanism_info.tags[:3]))  # Show first 3 tags
        self.tags_label.setFont(QFont("Segoe UI", 8))
        self.tags_label.setStyleSheet("color: #9E9E9E;")
        info_layout.addWidget(self.tags_label)
        
        info_layout.addStretch()
        content_layout.addLayout(info_layout)
        
        layout.addLayout(content_layout)
        
        # Generate initial preview
        self._generate_preview()
    
    def _create_complexity_badge(self) -> QLabel:
        """Create complexity level badge."""
        badge = QLabel(self.mechanism_info.complexity.upper())
        badge.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedSize(60, 16)
        
        # Apply complexity-based styling using ModernStyling
        badge.setStyleSheet(ModernStyling.get_complexity_badge_style(self.mechanism_info.complexity))
        
        return badge
    
    def _truncate_text(self, text: str, max_length: int) -> str:
        """Truncate text to specified length."""
        if len(text) <= max_length:
            return text
        return text[:max_length - 3] + "..."
    
    def _format_tags(self, tags: list) -> str:
        """Format tags for display."""
        if not tags:
            return ""
        return " • ".join(f"#{tag}" for tag in tags)
    
    def _generate_preview(self):
        """Generate animated preview of the mechanism."""
        # Create a simple geometric preview based on mechanism type
        pixmap = QPixmap(60, 45)
        pixmap.fill(QColor("#FAFAFA"))
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw based on mechanism type
        mechanism_type = self.mechanism_info.type
        
        if "linkage" in mechanism_type:
            self._draw_linkage_preview(painter)
        elif "gear" in mechanism_type:
            self._draw_gear_preview(painter)
        elif "cam" in mechanism_type:
            self._draw_cam_preview(painter)
        elif "geneva" in mechanism_type:
            self._draw_geneva_preview(painter)
        else:
            self._draw_generic_preview(painter)
        
        painter.end()
        self.preview_pixmap = pixmap
        self.preview_label.setPixmap(pixmap)
    
    def _draw_linkage_preview(self, painter: QPainter):
        """Draw linkage mechanism preview."""
        pen = QPen(QColor("#1976D2"), 2)
        painter.setPen(pen)
        
        # Draw simplified four-bar linkage
        painter.drawLine(10, 35, 25, 20)  # Link 1
        painter.drawLine(25, 20, 45, 25)  # Link 2  
        painter.drawLine(45, 25, 50, 35)  # Link 3
        painter.drawLine(50, 35, 10, 35)  # Base
        
        # Draw pivots
        painter.setBrush(QBrush(QColor("#1976D2")))
        painter.drawEllipse(8, 33, 4, 4)
        painter.drawEllipse(48, 33, 4, 4)
        painter.drawEllipse(23, 18, 4, 4)
        painter.drawEllipse(43, 23, 4, 4)
    
    def _draw_gear_preview(self, painter: QPainter):
        """Draw gear mechanism preview."""
        pen = QPen(QColor("#1976D2"), 2)
        painter.setPen(pen)
        painter.setBrush(QBrush(QColor("#E3F2FD")))
        
        # Draw two meshing gears
        painter.drawEllipse(10, 15, 20, 20)  # Gear 1
        painter.drawEllipse(25, 15, 20, 20)  # Gear 2
        
        # Draw gear teeth (simplified)
        for i in range(8):
            angle = i * 45
            import math
            x1 = 20 + 12 * math.cos(math.radians(angle))
            y1 = 25 + 12 * math.sin(math.radians(angle))
            x2 = 20 + 8 * math.cos(math.radians(angle))
            y2 = 25 + 8 * math.sin(math.radians(angle))
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))
    
    def _draw_cam_preview(self, painter: QPainter):
        """Draw cam mechanism preview."""
        pen = QPen(QColor("#1976D2"), 2)
        painter.setPen(pen)
        painter.setBrush(QBrush(QColor("#E3F2FD")))
        
        # Draw cam profile (ellipse)
        painter.drawEllipse(15, 20, 25, 15)
        
        # Draw follower
        painter.drawLine(30, 10, 30, 20)
        painter.drawRect(27, 8, 6, 4)
    
    def _draw_geneva_preview(self, painter: QPainter):
        """Draw Geneva drive preview."""
        pen = QPen(QColor("#1976D2"), 2)
        painter.setPen(pen)
        painter.setBrush(QBrush(QColor("#E3F2FD")))
        
        # Draw Geneva wheel (simplified)
        painter.drawEllipse(25, 15, 20, 20)
        
        # Draw slots
        painter.drawLine(35, 15, 35, 35)
        painter.drawLine(25, 25, 45, 25)
        
        # Draw drive pin
        painter.drawEllipse(13, 23, 4, 4)
    
    def _draw_generic_preview(self, painter: QPainter):
        """Draw generic mechanism preview."""
        pen = QPen(QColor("#757575"), 2)
        painter.setPen(pen)
        
        # Draw generic mechanical symbol
        painter.drawRect(20, 20, 20, 10)
        painter.drawLine(15, 25, 20, 25)
        painter.drawLine(40, 25, 45, 25)
    
    def _setup_animations(self):
        """Setup preview animations."""
        self.animation_timer.timeout.connect(self._update_animation)
        self.animation_timer.setInterval(50)  # 20 FPS
    
    def _update_animation(self):
        """Update animation frame."""
        self.animation_time += 0.1
        if self.animation_time > 6.28:  # 2*pi
            self.animation_time = 0.0
        
        # Regenerate preview with animation
        self._generate_animated_preview()
    
    def _generate_animated_preview(self):
        """Generate animated frame of the preview."""
        if not self.preview_pixmap:
            return
        
        # For now, just update the static preview
        # Animation can be enhanced later with rotating elements
        pass
    
    def _apply_styling(self):
        """Apply card styling."""
        self.setStyleSheet(ModernStyling.get_card_style(hover_enabled=True))
        
        # Add subtle shadow effect using Qt native effects
        self.setGraphicsEffect(ModernStyling.create_card_shadow(self))
    
    def mousePressEvent(self, event):
        """Handle mouse press events."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.mechanism_info.id)
            self._set_selected(True)
        super().mousePressEvent(event)
    
    def enterEvent(self, event):
        """Handle mouse enter events."""
        self.is_hovered = True
        self.animation_timer.start()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """Handle mouse leave events."""
        self.is_hovered = False
        self.animation_timer.stop()
        super().leaveEvent(event)
    
    def _set_selected(self, selected: bool):
        """Set the selection state of the card."""
        self.is_selected = selected
        
        if selected:
            self.setStyleSheet(f"""
                MechanismIndexCard {{
                    background-color: {ModernStyling.COLORS['primary_container']};
                    border: 2px solid {ModernStyling.COLORS['primary']};
                    border-radius: 8px;
                    padding: 3px;
                }}
            """)
            # Enhanced shadow for selected state
            self.setGraphicsEffect(ModernStyling.create_elevated_shadow(self))
        else:
            self._apply_styling()
    
    def set_selected(self, selected: bool):
        """Public method to set selection state."""
        self._set_selected(selected)
    
    def get_mechanism_info(self) -> MechanismInfo:
        """Get the mechanism info for this card."""
        return self.mechanism_info