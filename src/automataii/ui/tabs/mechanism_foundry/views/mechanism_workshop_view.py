"""
Mechanism Workshop View - Level 3 of the Mechanism Foundry

Provides focused learning environment with three modes:
1. Overview: Educational content and conceptual understanding
2. Playground: Interactive exploration and parameter manipulation  
3. Analysis: Data-driven investigation and kinematic analysis
"""

from typing import Optional, Dict
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QPushButton, QFrame, QSplitter
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from ..panels import OverviewPanel, PlaygroundPanel


class WorkshopHeaderBar(QFrame):
    """Header bar showing mechanism information and controls"""
    
    back_requested = pyqtSignal()
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.mechanism_data = None
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the header bar UI"""
        self.setFixedHeight(80)
        self.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border-bottom: 1px solid #e9ecef;
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 12, 20, 12)
        
        # Mechanism info section
        info_layout = QVBoxLayout()
        
        self.name_label = QLabel("Select a Mechanism")
        self.name_label.setStyleSheet("""
            QLabel {
                font-size: 22px;
                font-weight: bold;
                color: #212529;
                margin: 0;
            }
        """)
        
        self.description_label = QLabel("Choose a mechanism to begin learning")
        self.description_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #6c757d;
                margin: 0;
            }
        """)
        
        info_layout.addWidget(self.name_label)
        info_layout.addWidget(self.description_label)
        
        # Complexity badge
        self.complexity_badge = QLabel("Beginner")
        self.complexity_badge.setStyleSheet("""
            QLabel {
                background-color: #198754;
                color: white;
                padding: 4px 12px;
                border-radius: 12px;
                font-size: 12px;
                font-weight: bold;
            }
        """)
        self.complexity_badge.hide()
        
        layout.addLayout(info_layout)
        layout.addStretch()
        layout.addWidget(self.complexity_badge)
        
    def set_mechanism(self, mechanism_data: Dict):
        """Update header with mechanism information"""
        self.mechanism_data = mechanism_data
        
        name = mechanism_data.get('name', 'Unknown Mechanism')
        description = mechanism_data.get('description', '')
        complexity = mechanism_data.get('complexity', 'Beginner')
        
        self.name_label.setText(name)
        self.description_label.setText(description)
        
        # Update complexity badge
        self.complexity_badge.setText(complexity)
        self.complexity_badge.show()
        
        # Set badge color based on complexity
        colors = {
            'Beginner': '#198754',    # Green
            'Intermediate': '#fd7e14', # Orange  
            'Advanced': '#dc3545'     # Red
        }
        color = colors.get(complexity, '#198754')
        self.complexity_badge.setStyleSheet(f"""
            QLabel {{
                background-color: {color};
                color: white;
                padding: 4px 12px;
                border-radius: 12px;
                font-size: 12px;
                font-weight: bold;
            }}
        """)


class WorkshopTabWidget(QTabWidget):
    """Custom tab widget for workshop modes"""
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the tab widget styling"""
        self.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background-color: #ffffff;
            }
            
            QTabBar::tab {
                background-color: transparent;
                border: none;
                padding: 12px 24px;
                margin-right: 8px;
                font-size: 14px;
                font-weight: 500;
                color: #6c757d;
            }
            
            QTabBar::tab:selected {
                background-color: transparent;
                color: #0d6efd;
                border-bottom: 3px solid #0d6efd;
                font-weight: 600;
            }
            
            QTabBar::tab:hover:!selected {
                color: #495057;
            }
        """)


class MechanismWorkshopView(QWidget):
    """
    Focused learning workspace for deep mechanism study.
    
    Features two complementary learning modes:
    
    1. Overview Tab:
       - Educational content and key concepts
       - Real-world applications and context
       - Interactive tutorials and guided learning
       
    2. Playground Tab:
       - Interactive mechanism visualization
       - Real-time parameter manipulation
       - Direct hands-on exploration with mathematical rigor
    """
    
    back_requested = pyqtSignal()
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.mechanism_data = None
        self.setup_ui()
        self.connect_signals()
        
    def setup_ui(self):
        """Setup the workshop UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header bar
        self.header = WorkshopHeaderBar()
        
        # Tab widget for the three learning modes
        self.tabs = WorkshopTabWidget()
        
        # Overview tab - Educational content
        print("MechanismWorkshopView: Creating overview panel...")
        self.overview_panel = OverviewPanel()
        self.tabs.addTab(self.overview_panel, "📚 Overview")
        print("MechanismWorkshopView: Overview panel created")
        
        # Playground tab - Interactive exploration
        print("MechanismWorkshopView: Creating playground panel...")
        self.playground_panel = PlaygroundPanel()
        self.tabs.addTab(self.playground_panel, "🎮 Playground")
        print("MechanismWorkshopView: Playground panel created")
        
        layout.addWidget(self.header)
        layout.addWidget(self.tabs)
        
    def connect_signals(self):
        """Connect UI signals"""
        self.header.back_requested.connect(self.back_requested.emit)
        
        # Tab change events
        self.tabs.currentChanged.connect(self.on_tab_changed)
        
    def set_mechanism(self, mechanism_data: Dict):
        """Set the mechanism for study"""
        if not mechanism_data:
            return
            
        self.mechanism_data = mechanism_data
        
        # Update header
        self.header.set_mechanism(mechanism_data)
        
        # Update all panels safely
        try:
            self.overview_panel.set_mechanism(mechanism_data)
            self.playground_panel.set_mechanism(mechanism_data)
        except Exception as e:
            print(f"Warning: Failed to update panels: {e}")
        
        # Start with overview tab
        self.tabs.setCurrentIndex(0)
        
    def on_tab_changed(self, index: int):
        """Handle tab change events"""
        if not self.mechanism_data:
            return
            
        # Notify the active panel that it's now visible
        current_widget = self.tabs.currentWidget()
        if hasattr(current_widget, 'on_tab_activated'):
            current_widget.on_tab_activated()
            
    def get_current_panel(self):
        """Get the currently active panel"""
        return self.tabs.currentWidget()
        
    def switch_to_tab(self, tab_name: str):
        """Switch to a specific tab by name"""
        tab_map = {
            'overview': 0,
            'playground': 1
        }
        index = tab_map.get(tab_name.lower())
        if index is not None:
            self.tabs.setCurrentIndex(index)