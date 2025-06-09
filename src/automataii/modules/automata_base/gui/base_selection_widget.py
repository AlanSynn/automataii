"""
Base type selection widget for automata base designer.
"""

try:
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
        QComboBox, QGroupBox, QRadioButton, QButtonGroup,
        QPushButton, QGridLayout
    )
    from PyQt6.QtCore import pyqtSignal, Qt
    from PyQt6.QtGui import QPixmap, QPainter, QBrush, QColor
except ImportError:
    from PyQt5.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel,
        QComboBox, QGroupBox, QRadioButton, QButtonGroup,
        QPushButton, QGridLayout
    )
    from PyQt5.QtCore import pyqtSignal, Qt
    from PyQt5.QtGui import QPixmap, QPainter, QBrush, QColor

from automataii.modules.automata_base.enums.base_types import BaseType
from automataii.modules.automata_base.config.base_specs import (
    get_base_specification, list_specifications
)


class BaseSelectionWidget(QWidget):
    """Widget for selecting base type and configuration."""
    
    # Signals
    base_type_changed = pyqtSignal(BaseType)
    specification_changed = pyqtSignal(str)
    
    def __init__(self, parent=None):
        """Initialize the base selection widget."""
        super().__init__(parent)
        self.setup_ui()
        self.current_base_type = None
        self.current_specification = None
    
    def setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        
        # Title
        title_label = QLabel("Select Base Type")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title_label)
        
        # Base type selection
        type_group = QGroupBox("Base Type")
        type_layout = QGridLayout()
        
        self.type_buttons = QButtonGroup(self)
        
        # Create radio buttons for each base type
        base_types = [
            (BaseType.FLAT_RECTANGULAR, "Flat Rectangular", 0, 0),
            (BaseType.FLAT_CIRCULAR, "Flat Circular", 0, 1),
            (BaseType.BOX_OPEN, "Open Box", 1, 0),
            (BaseType.BOX_ENCLOSED, "Enclosed Box", 1, 1),
            (BaseType.PEDESTAL, "Pedestal", 2, 0),
            (BaseType.WALL_MOUNTED, "Wall Mounted", 2, 1),
        ]
        
        for base_type, label, row, col in base_types:
            radio = QRadioButton(label)
            radio.setObjectName(base_type.value)
            type_layout.addWidget(radio, row, col)
            self.type_buttons.addButton(radio)
            
            # Add preview icon
            icon_label = QLabel()
            pixmap = self.create_base_type_icon(base_type)
            icon_label.setPixmap(pixmap)
            type_layout.addWidget(icon_label, row + 3, col, Qt.AlignmentFlag.AlignCenter)
        
        # Set default selection
        if self.type_buttons.buttons():
            self.type_buttons.buttons()[0].setChecked(True)
        
        type_group.setLayout(type_layout)
        layout.addWidget(type_group)
        
        # Specification selection
        spec_group = QGroupBox("Pre-defined Specifications")
        spec_layout = QVBoxLayout()
        
        self.spec_combo = QComboBox()
        self.spec_combo.addItem("Custom", None)
        self.spec_combo.addItem("---", None)
        
        # Add available specifications
        for spec_name in list_specifications():
            spec = get_base_specification(spec_name)
            self.spec_combo.addItem(spec.name, spec_name)
        
        spec_layout.addWidget(QLabel("Select Specification:"))
        spec_layout.addWidget(self.spec_combo)
        
        # Specification info
        self.spec_info_label = QLabel("Select a specification to see details")
        self.spec_info_label.setWordWrap(True)
        self.spec_info_label.setStyleSheet("padding: 10px; background-color: #f0f0f0;")
        spec_layout.addWidget(self.spec_info_label)
        
        spec_group.setLayout(spec_layout)
        layout.addWidget(spec_group)
        
        # Connect signals
        self.type_buttons.buttonClicked.connect(self._on_type_changed)
        self.spec_combo.currentIndexChanged.connect(self._on_spec_changed)
        
        layout.addStretch()
    
    def create_base_type_icon(self, base_type: BaseType) -> QPixmap:
        """Create a simple icon for the base type."""
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw different shapes for different types
        pen = painter.pen()
        pen.setWidth(2)
        painter.setPen(pen)
        
        if base_type == BaseType.FLAT_RECTANGULAR:
            painter.drawRect(8, 20, 48, 24)
        elif base_type == BaseType.FLAT_CIRCULAR:
            painter.drawEllipse(8, 8, 48, 48)
        elif base_type == BaseType.BOX_OPEN:
            # Draw open box
            painter.drawRect(8, 16, 48, 32)
            painter.drawLine(8, 16, 8, 8)
            painter.drawLine(56, 16, 56, 8)
            painter.drawLine(8, 48, 8, 56)
            painter.drawLine(56, 48, 56, 56)
        elif base_type == BaseType.BOX_ENCLOSED:
            # Draw closed box
            painter.drawRect(8, 24, 48, 32)
            painter.drawPolygon([
                (8, 24), (20, 8), (68, 8), (56, 24)
            ])
            painter.drawLine(56, 24, 56, 56)
            painter.drawLine(56, 56, 68, 40)
            painter.drawLine(68, 40, 68, 8)
        elif base_type == BaseType.PEDESTAL:
            # Draw pedestal
            painter.drawPolygon([
                (16, 48), (48, 48), (40, 16), (24, 16)
            ])
        elif base_type == BaseType.WALL_MOUNTED:
            # Draw wall mount
            painter.drawRect(16, 8, 32, 40)
            painter.drawLine(8, 8, 8, 48)
            painter.drawLine(8, 8, 16, 8)
            painter.drawLine(8, 48, 16, 48)
        
        painter.end()
        return pixmap
    
    def _on_type_changed(self, button):
        """Handle base type selection change."""
        base_type_str = button.objectName()
        self.current_base_type = BaseType(base_type_str)
        self.base_type_changed.emit(self.current_base_type)
        
        # Update specification combo to show compatible specs
        self._update_spec_combo()
    
    def _on_spec_changed(self, index):
        """Handle specification selection change."""
        spec_name = self.spec_combo.itemData(index)
        
        if spec_name and spec_name != "---":
            self.current_specification = spec_name
            self.specification_changed.emit(spec_name)
            
            # Update info label
            spec = get_base_specification(spec_name)
            info_text = f"<b>{spec.name}</b><br>"
            info_text += f"<i>{spec.description}</i><br><br>"
            info_text += f"Base Type: {spec.base_type.value}<br>"
            info_text += f"Sizes: {', '.join(spec.standard_sizes.keys())}<br>"
            info_text += f"Default Material: {spec.default_material.value}"
            self.spec_info_label.setText(info_text)
        else:
            self.current_specification = None
            self.spec_info_label.setText("Custom configuration selected")
    
    def _update_spec_combo(self):
        """Update specification combo based on selected base type."""
        # This could filter specs by compatible base type
        # For now, just reset to Custom
        self.spec_combo.setCurrentIndex(0)
    
    def get_selected_base_type(self) -> BaseType:
        """Get the currently selected base type."""
        return self.current_base_type
    
    def get_selected_specification(self) -> str:
        """Get the currently selected specification name."""
        return self.current_specification
    
    def set_base_type(self, base_type: BaseType):
        """Set the base type selection."""
        for button in self.type_buttons.buttons():
            if button.objectName() == base_type.value:
                button.setChecked(True)
                self._on_type_changed(button)
                break
    
    def set_specification(self, spec_name: str):
        """Set the specification selection."""
        for i in range(self.spec_combo.count()):
            if self.spec_combo.itemData(i) == spec_name:
                self.spec_combo.setCurrentIndex(i)
                break