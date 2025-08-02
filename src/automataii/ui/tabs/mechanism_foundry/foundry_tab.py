"""
Mechanism Foundry Tab - Main educational interface for mechanism learning

This tab provides a hierarchical learning experience:
1. Category Hub: Browse mechanism categories visually
2. Mechanism Workshop: Deep-dive learning environment with three modes
"""

from typing import Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget, 
    QPushButton, QLabel, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QFont

from .views import CategoryHubView, MechanismWorkshopView


class NavigationBar(QFrame):
    """Navigation breadcrumb bar for the foundry"""
    
    home_clicked = pyqtSignal()
    back_clicked = pyqtSignal()
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the navigation bar UI"""
        self.setFixedHeight(50)
        self.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border-bottom: 1px solid #dee2e6;
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        
        # Home button
        self.home_btn = QPushButton("🏠 Foundry")
        self.home_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                padding: 8px 12px;
                font-weight: bold;
                color: #0d6efd;
            }
            QPushButton:hover {
                background-color: rgba(13, 110, 253, 0.1);
                border-radius: 4px;
            }
        """)
        self.home_btn.clicked.connect(self.home_clicked.emit)
        
        # Back button
        self.back_btn = QPushButton("← Back")
        self.back_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                padding: 8px 12px;
                color: #6c757d;
            }
            QPushButton:hover {
                background-color: rgba(108, 117, 125, 0.1);
                border-radius: 4px;
            }
        """)
        self.back_btn.clicked.connect(self.back_clicked.emit)
        self.back_btn.hide()  # Initially hidden
        
        # Breadcrumb label
        self.breadcrumb = QLabel("Mechanism Categories")
        self.breadcrumb.setStyleSheet("""
            QLabel {
                color: #495057;
                font-size: 14px;
                margin-left: 8px;
            }
        """)
        
        layout.addWidget(self.home_btn)
        layout.addWidget(self.back_btn)
        layout.addWidget(self.breadcrumb)
        layout.addStretch()
        
    def set_breadcrumb(self, text: str, show_back: bool = False):
        """Update breadcrumb text and back button visibility"""
        self.breadcrumb.setText(text)
        self.back_btn.setVisible(show_back)


class MechanismFoundryTab(QWidget):
    """
    Main Mechanism Foundry tab providing hierarchical mechanism learning.
    
    Features:
    - Category-based browsing with visual cards
    - Progressive learning flow from basic to advanced
    - Three-mode workshop: Overview, Playground, Analysis
    - Smooth navigation with breadcrumbs
    """
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        print("MechanismFoundryTab: Initializing...")
        self.current_mechanism = None
        self.current_category = None
        self.setup_ui()
        self.connect_signals()
        print("MechanismFoundryTab: Initialization completed")
        
    def setup_ui(self):
        """Setup the main UI structure"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Set overall background style
        self.setStyleSheet("""
            MechanismFoundryTab {
                background-color: #f8f9fa;
            }
        """)
        
        # Navigation bar
        self.nav_bar = NavigationBar()
        
        # Stacked widget for different views
        self.stack = QStackedWidget()
        self.stack.setStyleSheet("""
            QStackedWidget {
                background-color: #f8f9fa;
            }
        """)
        
        # Category hub view (Level 1)
        self.category_hub = CategoryHubView()
        self.stack.addWidget(self.category_hub)
        
        # Mechanism workshop view (Level 3)
        self.workshop = MechanismWorkshopView()
        self.stack.addWidget(self.workshop)
        
        layout.addWidget(self.nav_bar)
        layout.addWidget(self.stack)
        
        # Start with category hub
        self.show_category_hub()
        
    def connect_signals(self):
        """Connect all UI signals"""
        # Navigation
        self.nav_bar.home_clicked.connect(self.show_category_hub)
        self.nav_bar.back_clicked.connect(self.go_back)
        
        # Category hub signals
        self.category_hub.category_selected.connect(self.on_category_selected)
        self.category_hub.mechanism_selected.connect(self.show_mechanism_workshop)
        
        # Workshop signals
        self.workshop.back_requested.connect(self.go_back)
        
    def show_category_hub(self):
        """Show the category hub (Level 1)"""
        self.stack.setCurrentWidget(self.category_hub)
        self.nav_bar.set_breadcrumb("Mechanism Categories", show_back=False)
        self.current_mechanism = None
        self.current_category = None
        
    def on_category_selected(self, category_name: str):
        """Handle category selection"""
        self.current_category = category_name
        self.nav_bar.set_breadcrumb(f"{category_name} Mechanisms", show_back=True)
        
    def show_mechanism_workshop(self, mechanism_data: dict):
        """Show the mechanism workshop (Level 3)"""
        self.current_mechanism = mechanism_data
        self.workshop.set_mechanism(mechanism_data)
        self.stack.setCurrentWidget(self.workshop)
        
        mechanism_name = mechanism_data.get('name', 'Unknown Mechanism')
        self.nav_bar.set_breadcrumb(f"Workshop: {mechanism_name}", show_back=True)
        
    def go_back(self):
        """Handle back navigation"""
        if self.current_mechanism:
            # From workshop back to category view
            self.current_mechanism = None
            if self.current_category:
                # Ensure we're showing category hub first
                self.stack.setCurrentWidget(self.category_hub)
                self.category_hub.show_category_mechanisms(self.current_category)
                self.nav_bar.set_breadcrumb(f"{self.current_category} Mechanisms", show_back=True)
            else:
                self.show_category_hub()
        elif self.current_category:
            # From category view back to hub
            self.show_category_hub()
        else:
            # Already at hub
            pass