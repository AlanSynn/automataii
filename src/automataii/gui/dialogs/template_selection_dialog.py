"""
Template selection dialog for choosing skeleton templates.
"""

from typing import Optional
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QPushButton, QTextEdit, QSplitter, QWidget
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont, QIcon, QPixmap, QPainter, QPen, QBrush, QColor

from automataii.core.models.skeleton_types import (
    SkeletonType, SkeletonTemplate, SKELETON_TEMPLATES
)


class TemplatePreviewWidget(QWidget):
    """Widget to preview a skeleton template."""
    
    def __init__(self):
        super().__init__()
        self.template: Optional[SkeletonTemplate] = None
        self.setMinimumSize(300, 300)
        
    def set_template(self, template: Optional[SkeletonTemplate]):
        """Set the template to preview."""
        self.template = template
        self.update()
        
    def paintEvent(self, event):
        """Paint the template preview."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        if not self.template:
            painter.drawText(self.rect(), Qt.AlignCenter, "Select a template to preview")
            return
        
        # Draw background
        painter.fillRect(self.rect(), QColor(240, 240, 240))
        
        # Calculate scale and offset
        width = self.width()
        height = self.height()
        margin = 20
        
        # Draw joints and bones
        joint_positions = {}
        
        # First pass: draw bones
        painter.setPen(QPen(QColor(150, 150, 150), 2))
        for parent_id, child_id in self.template.bone_connections:
            if parent_id in self.template.joint_definitions and child_id in self.template.joint_definitions:
                parent_def = self.template.joint_definitions[parent_id]
                child_def = self.template.joint_definitions[child_id]
                
                # Scale positions to widget size
                x1 = margin + parent_def["default_position"][0] * (width - 2 * margin)
                y1 = margin + parent_def["default_position"][1] * (height - 2 * margin)
                x2 = margin + child_def["default_position"][0] * (width - 2 * margin)
                y2 = margin + child_def["default_position"][1] * (height - 2 * margin)
                
                painter.drawLine(int(x1), int(y1), int(x2), int(y2))
                
                joint_positions[parent_id] = (x1, y1)
                joint_positions[child_id] = (x2, y2)
        
        # Second pass: draw joints
        painter.setBrush(QBrush(QColor(100, 150, 255)))
        painter.setPen(QPen(QColor(50, 100, 200), 2))
        
        for joint_id, (x, y) in joint_positions.items():
            painter.drawEllipse(int(x - 5), int(y - 5), 10, 10)
        
        # Draw template name
        painter.setPen(QPen(QColor(0, 0, 0)))
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(10, 20, self.template.name)


class TemplateSelectionDialog(QDialog):
    """Dialog for selecting a skeleton template."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Skeleton Template")
        self.setModal(True)
        self.resize(800, 500)
        
        self.selected_template: Optional[SkeletonTemplate] = None
        self.setup_ui()
        
    def setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("Choose a skeleton template for your character:")
        header.setStyleSheet("font-size: 14px; padding: 10px;")
        layout.addWidget(header)
        
        # Main content
        splitter = QSplitter(Qt.Horizontal)
        
        # Left panel - template list
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        self.template_list = QListWidget()
        self.template_list.itemSelectionChanged.connect(self.on_template_selected)
        
        # Add templates to list
        for skeleton_type, template in SKELETON_TEMPLATES.items():
            item = QListWidgetItem(f"{template.name} - {template.description}")
            item.setData(Qt.UserRole, skeleton_type)
            
            # Add icon based on type
            if skeleton_type == SkeletonType.HUMANOID:
                item.setIcon(self.create_icon("👤"))
            elif skeleton_type == SkeletonType.QUADRUPED:
                item.setIcon(self.create_icon("🐕"))
            elif skeleton_type == SkeletonType.BIRD:
                item.setIcon(self.create_icon("🦅"))
            elif skeleton_type == SkeletonType.INSECT:
                item.setIcon(self.create_icon("🐛"))
            
            self.template_list.addItem(item)
        
        left_layout.addWidget(self.template_list)
        splitter.addWidget(left_widget)
        
        # Right panel - preview and details
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        # Preview
        self.preview_widget = TemplatePreviewWidget()
        right_layout.addWidget(self.preview_widget)
        
        # Details
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setMaximumHeight(150)
        right_layout.addWidget(self.details_text)
        
        splitter.addWidget(right_widget)
        splitter.setSizes([300, 500])
        
        layout.addWidget(splitter)
        
        # Dialog buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        
        self.select_btn = QPushButton("Select Template")
        self.select_btn.setEnabled(False)
        self.select_btn.clicked.connect(self.accept_selection)
        
        button_layout.addWidget(self.cancel_btn)
        button_layout.addWidget(self.select_btn)
        layout.addLayout(button_layout)
        
    def create_icon(self, emoji: str) -> QIcon:
        """Create an icon from an emoji."""
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        font = QFont()
        font.setPointSize(20)
        painter.setFont(font)
        
        painter.drawText(pixmap.rect(), Qt.AlignCenter, emoji)
        painter.end()
        
        return QIcon(pixmap)
    
    def on_template_selected(self):
        """Handle template selection."""
        current = self.template_list.currentItem()
        if current:
            skeleton_type = current.data(Qt.UserRole)
            template = SKELETON_TEMPLATES.get(skeleton_type)
            
            if template:
                self.selected_template = template
                self.preview_widget.set_template(template)
                
                # Update details
                details = f"<h3>{template.name}</h3>"
                details += f"<p><b>Type:</b> {template.type.value}</p>"
                details += f"<p><b>Description:</b> {template.description}</p>"
                details += f"<p><b>Joints:</b> {len(template.joint_definitions)}</p>"
                details += f"<p><b>Bones:</b> {len(template.bone_connections)}</p>"
                
                if template.mechanism_hints:
                    details += "<p><b>Recommended Mechanisms:</b></p><ul>"
                    for part, mechanisms in template.mechanism_hints.items():
                        details += f"<li>{part}: {', '.join(mechanisms)}</li>"
                    details += "</ul>"
                
                self.details_text.setHtml(details)
                self.select_btn.setEnabled(True)
        else:
            self.selected_template = None
            self.preview_widget.set_template(None)
            self.details_text.clear()
            self.select_btn.setEnabled(False)
    
    def accept_selection(self):
        """Accept the selected template."""
        if self.selected_template:
            self.accept()