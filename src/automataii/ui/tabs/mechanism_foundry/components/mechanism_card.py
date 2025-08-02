"""
Mechanism Card Component - Visual card for displaying mechanism information

Provides a consistent card layout for mechanism browsing with:
- Visual preview/thumbnail
- Mechanism name and description
- Complexity level badge
- Key concepts and applications
- Click interaction for selection
"""

from typing import Optional, Dict, List
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QFrame, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor


class ComplexityBadge(QLabel):
    """Badge showing mechanism complexity level"""
    
    def __init__(self, complexity: str, parent: Optional[QWidget] = None):
        super().__init__(complexity, parent)
        self.setup_ui(complexity)
        
    def setup_ui(self, complexity: str):
        """Setup the badge styling"""
        colors = {
            'Beginner': ('#198754', 'white'),      # Green
            'Intermediate': ('#fd7e14', 'white'),  # Orange
            'Advanced': ('#dc3545', 'white')       # Red
        }
        
        bg_color, text_color = colors.get(complexity, ('#6c757d', 'white'))
        
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {bg_color};
                color: {text_color};
                padding: 4px 8px;
                border-radius: 10px;
                font-size: 11px;
                font-weight: bold;
            }}
        """)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)


class KeyConceptsList(QWidget):
    """Widget displaying key concepts as tags"""
    
    def __init__(self, concepts: List[str], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.concepts = concepts
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the concepts list"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        # Show first 3 concepts
        for i, concept in enumerate(self.concepts[:3]):
            tag = QLabel(concept)
            tag.setStyleSheet("""
                QLabel {
                    background-color: #e7f3ff;
                    color: #0d6efd;
                    padding: 3px 8px;
                    border-radius: 10px;
                    font-size: 11px;
                    font-weight: 500;
                    border: none;
                }
            """)
            layout.addWidget(tag)
            
        if len(self.concepts) > 3:
            more_label = QLabel(f"+{len(self.concepts) - 3}")
            more_label.setStyleSheet("""
                QLabel {
                    color: #6c757d;
                    font-size: 10px;
                    font-weight: 500;
                }
            """)
            layout.addWidget(more_label)
            
        layout.addStretch()


class MechanismCard(QFrame):
    """
    Visual card component for displaying mechanism information.
    
    Features:
    - Mechanism preview/thumbnail
    - Name, description, and complexity
    - Key concepts as tags
    - Applications list
    - Click interaction for selection
    - Hover effects for better UX
    """
    
    clicked = pyqtSignal(dict)  # mechanism_data
    
    def __init__(self, mechanism_data: Dict, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.mechanism_data = mechanism_data
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the card UI"""
        self.setFixedSize(320, 220)
        self.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: none;
                border-radius: 16px;
                padding: 0px;
            }
            QFrame:hover {
                background-color: #f8f9fa;
            }
        """)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Add shadow effect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 20))
        self.setGraphicsEffect(shadow)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        
        # Visual icon based on mechanism type
        icon = self.get_mechanism_icon()
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("""
            QLabel {
                font-size: 32px;
                background-color: #f0f4f8;
                border-radius: 20px;
                padding: 12px;
            }
        """)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setFixedSize(64, 64)
        
        # Header with icon, name and complexity
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)
        
        name_label = QLabel(self.mechanism_data.get('name', 'Unknown'))
        name_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: 600;
                color: #000000;
            }
        """)
        name_label.setWordWrap(False)
        
        complexity_badge = ComplexityBadge(self.mechanism_data.get('complexity', 'Beginner'))
        
        header_layout.addWidget(icon_label)
        header_layout.addWidget(name_label)
        header_layout.addStretch()
        header_layout.addWidget(complexity_badge)
        
        layout.addLayout(header_layout)
        
        # Description
        description = QLabel(self.mechanism_data.get('description', ''))
        description.setStyleSheet("""
            QLabel {
                font-size: 13px;
                color: #495057;
                line-height: 1.4;
            }
        """)
        description.setWordWrap(True)
        description.setMaximumHeight(50)
        layout.addWidget(description)
        
        layout.addStretch()
        
        # Key concepts (simplified)
        concepts = self.mechanism_data.get('key_concepts', [])
        if concepts:
            concepts_widget = KeyConceptsList(concepts)
            layout.addWidget(concepts_widget)
        
        # Applications (show first one as subtitle)
        applications = self.mechanism_data.get('applications', [])
        if applications:
            apps_text = QLabel(applications[0])
            apps_text.setStyleSheet("""
                QLabel {
                    font-size: 11px;
                    color: #6c757d;
                    font-style: italic;
                }
            """)
            layout.addWidget(apps_text)
        
    def get_mechanism_icon(self) -> str:
        """Get emoji icon for mechanism type"""
        mechanism_name = self.mechanism_data.get('name', '').lower()
        
        if 'linkage' in mechanism_name or 'bar' in mechanism_name:
            return "🔗"
        elif 'gear' in mechanism_name:
            return "⚙️"
        elif 'cam' in mechanism_name:
            return "🎯"
        elif 'spring' in mechanism_name:
            return "🌀"
        elif 'belt' in mechanism_name or 'chain' in mechanism_name:
            return "🔗"
        elif 'lever' in mechanism_name:
            return "⚖️"
        elif 'pulley' in mechanism_name:
            return "🎡"
        elif 'screw' in mechanism_name:
            return "🔩"
        elif 'slider' in mechanism_name or 'crank' in mechanism_name:
            return "↔️"
        else:
            return "⚡"
        
    def mousePressEvent(self, event):
        """Handle click events"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.mechanism_data)
        super().mousePressEvent(event)