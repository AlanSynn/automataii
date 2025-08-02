"""
Category Hub View - Level 1 of the Mechanism Foundry

Provides visual category browsing with search and filtering capabilities.
Users can explore mechanism categories and select specific mechanisms to study.
"""

from typing import Optional, Dict, List
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QScrollArea,
    QLabel, QLineEdit, QComboBox, QPushButton, QFrame, QSplitter,
    QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QPalette, QColor

from ..components import MechanismCard


class CategoryCard(QFrame):
    """Visual card representing a mechanism category"""
    
    clicked = pyqtSignal(str)  # category_name
    
    def __init__(self, category_name: str, description: str, mechanism_count: int, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.category_name = category_name
        self.setup_ui(description, mechanism_count)
        
    def setup_ui(self, description: str, mechanism_count: int):
        """Setup the category card UI"""
        self.setFixedSize(280, 200)
        self.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: none;
                border-radius: 12px;
                padding: 8px;
            }
            QFrame:hover {
                background-color: #f8f9fa;
            }
        """)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        
        # Category icon/emoji (placeholder)
        icon_label = QLabel(self.get_category_icon())
        icon_label.setStyleSheet("font-size: 48px;")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Category name
        name_label = QLabel(self.category_name)
        name_label.setStyleSheet("""
            QLabel {
                font-size: 19px;
                font-weight: 700;
                color: #000000;
                margin: 8px 0;
            }
        """)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Description
        desc_label = QLabel(description)
        desc_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #212529;
                line-height: 1.4;
            }
        """)
        desc_label.setWordWrap(True)
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Mechanism count
        count_label = QLabel(f"{mechanism_count} mechanisms")
        count_label.setStyleSheet("""
            QLabel {
                font-size: 13px;
                color: #0d6efd;
                font-weight: 600;
                margin-top: 8px;
            }
        """)
        count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(icon_label)
        layout.addWidget(name_label)
        layout.addWidget(desc_label)
        layout.addWidget(count_label)
        layout.addStretch()
        
        # Add subtle shadow effect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setXOffset(0)
        shadow.setYOffset(2)
        shadow.setColor(QColor(0, 0, 0, 30))
        self.setGraphicsEffect(shadow)
        
    def get_category_icon(self) -> str:
        """Get emoji icon for category"""
        icons = {
            "Linkages": "🔗",
            "Gears": "⚙️",
            "Cams": "🎯",
            "Springs": "🌀",
            "Belts & Chains": "🔗",
            "Levers": "⚖️",
            "Pulleys": "🎡",
            "Screws": "🔩"
        }
        return icons.get(self.category_name, "⚡")
        
    def mousePressEvent(self, event):
        """Handle click events"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.category_name)
        super().mousePressEvent(event)


class MechanismListView(QWidget):
    """List view showing mechanisms in a selected category"""
    
    mechanism_selected = pyqtSignal(dict)  # mechanism_data
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the mechanism list UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # Header
        header = QLabel("Select a Mechanism to Study")
        header.setStyleSheet("""
            QLabel {
                font-size: 20px;
                font-weight: bold;
                color: #212529;
                margin-bottom: 16px;
            }
        """)
        
        # Scroll area for mechanism cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.mechanism_container = QWidget()
        self.mechanism_layout = QGridLayout(self.mechanism_container)
        self.mechanism_layout.setSpacing(16)
        
        scroll.setWidget(self.mechanism_container)
        
        layout.addWidget(header)
        layout.addWidget(scroll)
        
    def show_mechanisms(self, category_name: str, mechanisms: List[Dict]):
        """Display mechanisms for the given category"""
        # Clear existing mechanisms
        for i in reversed(range(self.mechanism_layout.count())):
            child = self.mechanism_layout.itemAt(i).widget()
            if child:
                child.setParent(None)
                
        # Add mechanism cards
        row, col = 0, 0
        for mechanism in mechanisms:
            card = MechanismCard(mechanism)
            card.clicked.connect(lambda m=mechanism: self.mechanism_selected.emit(m))
            
            self.mechanism_layout.addWidget(card, row, col)
            col += 1
            if col >= 3:  # 3 cards per row
                col = 0
                row += 1


class CategoryHubView(QWidget):
    """
    Main category hub view providing visual browsing of mechanism categories.
    
    Features:
    - Visual category cards with icons and descriptions
    - Search and filtering capabilities
    - Smooth transition to mechanism selection
    - Progressive disclosure of complexity levels
    """
    
    category_selected = pyqtSignal(str)  # category_name
    mechanism_selected = pyqtSignal(dict)  # mechanism_data
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.categories_data = self.get_categories_data()
        self.mechanisms_data = self.get_mechanisms_data()
        self.setup_ui()
        self.connect_signals()
        
    def setup_ui(self):
        """Setup the main UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create splitter for category/mechanism views
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Categories panel (left)
        self.categories_panel = self.create_categories_panel()
        self.splitter.addWidget(self.categories_panel)
        
        # Mechanisms panel (right, initially hidden)
        self.mechanisms_panel = MechanismListView()
        self.mechanisms_panel.hide()
        self.splitter.addWidget(self.mechanisms_panel)
        
        layout.addWidget(self.splitter)
        
        # Initially show only categories
        self.splitter.setSizes([1000, 0])  # Hide mechanisms panel
        
    def create_categories_panel(self) -> QWidget:
        """Create the categories browsing panel"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 24, 24, 24)
        
        # Header
        header = QLabel("Mechanism Categories")
        header.setStyleSheet("""
            QLabel {
                font-size: 28px;
                font-weight: bold;
                color: #212529;
                margin-bottom: 8px;
            }
        """)
        
        subtitle = QLabel("Explore different types of mechanical systems")
        subtitle.setStyleSheet("""
            QLabel {
                font-size: 16px;
                color: #495057;
                margin-bottom: 24px;
            }
        """)
        
        # Search and filters
        search_layout = QHBoxLayout()
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search categories...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                padding: 12px 16px;
                font-size: 14px;
                border: none;
                border-radius: 8px;
                background-color: #f0f4f8;
                color: #212529;
            }
            QLineEdit:focus {
                background-color: #e9ecef;
                outline: none;
            }
        """)
        
        self.complexity_filter = QComboBox()
        self.complexity_filter.addItems(["All Levels", "Beginner", "Intermediate", "Advanced"])
        self.complexity_filter.setStyleSheet("""
            QComboBox {
                padding: 12px 16px;
                font-size: 14px;
                border: none;
                border-radius: 8px;
                background-color: #f0f4f8;
                color: #212529;
                min-width: 140px;
            }
            QComboBox:hover {
                background-color: #e9ecef;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #6c757d;
                margin-right: 5px;
            }
        """)
        
        search_layout.addWidget(self.search_input, 1)
        search_layout.addWidget(self.complexity_filter)
        
        # Categories grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        categories_container = QWidget()
        self.categories_layout = QGridLayout(categories_container)
        self.categories_layout.setSpacing(20)
        
        # Add category cards
        self.populate_categories()
        
        scroll.setWidget(categories_container)
        
        layout.addWidget(header)
        layout.addWidget(subtitle)
        layout.addLayout(search_layout)
        layout.addWidget(scroll)
        
        return panel
        
    def populate_categories(self):
        """Populate the categories grid"""
        row, col = 0, 0
        for category_name, category_info in self.categories_data.items():
            card = CategoryCard(
                category_name,
                category_info['description'],
                len(self.mechanisms_data.get(category_name, []))
            )
            card.clicked.connect(self.on_category_clicked)
            
            self.categories_layout.addWidget(card, row, col)
            col += 1
            if col >= 3:  # 3 cards per row
                col = 0
                row += 1
                
    def connect_signals(self):
        """Connect UI signals"""
        self.mechanisms_panel.mechanism_selected.connect(self.mechanism_selected.emit)
        
    def on_category_clicked(self, category_name: str):
        """Handle category selection"""
        self.category_selected.emit(category_name)
        self.show_category_mechanisms(category_name)
        
    def show_category_mechanisms(self, category_name: str):
        """Show mechanisms for the selected category"""
        mechanisms = self.mechanisms_data.get(category_name, [])
        self.mechanisms_panel.show_mechanisms(category_name, mechanisms)
        self.mechanisms_panel.show()
        
        # Adjust splitter to show both panels
        self.splitter.setSizes([500, 500])
        
    def get_categories_data(self) -> Dict:
        """Get mechanism categories data"""
        return {
            "Linkages": {
                "description": "Connected rigid bars that transform motion through joints and pivots.",
                "complexity": "Intermediate"
            },
            "Gears": {
                "description": "Toothed wheels that transmit rotational motion and change speed or torque.",
                "complexity": "Beginner"
            },
            "Cams": {
                "description": "Rotating or sliding pieces that convert rotary motion to linear motion.",
                "complexity": "Intermediate"
            },
            "Springs": {
                "description": "Elastic elements that store and release mechanical energy.",
                "complexity": "Beginner"
            },
            "Belts & Chains": {
                "description": "Flexible connectors that transmit power between rotating shafts.",
                "complexity": "Beginner"
            },
            "Levers": {
                "description": "Simple machines that amplify force using a fulcrum and rigid bar.",
                "complexity": "Beginner"
            },
            "Pulleys": {
                "description": "Wheels with grooves that change force direction and provide mechanical advantage.",
                "complexity": "Beginner"
            },
            "Screws": {
                "description": "Inclined planes wrapped around cylinders for fastening and lifting.",
                "complexity": "Intermediate"
            }
        }
        
    def get_mechanisms_data(self) -> Dict[str, List[Dict]]:
        """Get mechanisms data organized by category"""
        return {
            "Linkages": [
                {
                    "name": "Four-Bar Linkage",
                    "description": "The fundamental linkage mechanism with four rigid bars connected by joints.",
                    "complexity": "Intermediate",
                    "applications": ["Windshield wipers", "Robot arms", "Engine pistons"],
                    "key_concepts": ["Grashof condition", "Coupler curves", "Transmission angle"]
                },
                {
                    "name": "Slider-Crank Mechanism",
                    "description": "Converts rotary motion to linear motion using a crank and slider.",
                    "complexity": "Intermediate", 
                    "applications": ["Engine pistons", "Pumps", "Compressors"],
                    "key_concepts": ["Stroke length", "Compression ratio", "Dead points"]
                },
                {
                    "name": "Six-Bar Linkage",
                    "description": "Complex linkage with six bars providing advanced motion patterns.",
                    "complexity": "Advanced",
                    "applications": ["Walking machines", "Complex manufacturing", "Robotics"],
                    "key_concepts": ["Degrees of freedom", "Synthesis", "Motion generation"]
                }
            ],
            "Gears": [
                {
                    "name": "Spur Gears",
                    "description": "Straight-toothed gears for parallel shaft power transmission.",
                    "complexity": "Beginner",
                    "applications": ["Clocks", "Simple transmissions", "Toys"],
                    "key_concepts": ["Gear ratio", "Module", "Pressure angle"]
                },
                {
                    "name": "Planetary Gears",
                    "description": "Compact gear system with sun, planet, and ring gears.",
                    "complexity": "Advanced",
                    "applications": ["Automatic transmissions", "Wind turbines", "Robotics"],
                    "key_concepts": ["Speed ratios", "Torque distribution", "Efficiency"]
                }
            ],
            "Cams": [
                {
                    "name": "Plate Cam",
                    "description": "Rotating cam with follower that creates specific motion profiles.",
                    "complexity": "Intermediate",
                    "applications": ["Engine valves", "Automated machinery", "Packaging equipment"],
                    "key_concepts": ["Cam profile", "Follower motion", "Pressure angle"]
                }
            ],
            "Springs": [
                {
                    "name": "Compression Spring",
                    "description": "Coil spring that resists compression forces.",
                    "complexity": "Beginner",
                    "applications": ["Suspension systems", "Valves", "Mechanical devices"],
                    "key_concepts": ["Spring constant", "Deflection", "Energy storage"]
                }
            ],
            "Belts & Chains": [
                {
                    "name": "Belt Drive",
                    "description": "Flexible belt transmitting power between pulleys.",
                    "complexity": "Beginner",
                    "applications": ["Car engines", "Conveyor systems", "Exercise equipment"],
                    "key_concepts": ["Belt tension", "Slip", "Speed ratio"]
                }
            ],
            "Levers": [
                {
                    "name": "First Class Lever",
                    "description": "Lever with fulcrum between effort and load.",
                    "complexity": "Beginner",
                    "applications": ["Scissors", "Pliers", "Crowbars"],
                    "key_concepts": ["Mechanical advantage", "Fulcrum position", "Force balance"]
                }
            ],
            "Pulleys": [
                {
                    "name": "Fixed Pulley",
                    "description": "Stationary pulley that changes force direction.",
                    "complexity": "Beginner",
                    "applications": ["Flag poles", "Lifting systems", "Clotheslines"],
                    "key_concepts": ["Direction change", "Force transmission", "Mechanical advantage"]
                }
            ],
            "Screws": [
                {
                    "name": "Lead Screw",
                    "description": "Threaded rod that converts rotary to linear motion.",
                    "complexity": "Intermediate",
                    "applications": ["CNC machines", "Jacks", "Linear actuators"],
                    "key_concepts": ["Lead", "Pitch", "Mechanical advantage"]
                }
            ]
        }