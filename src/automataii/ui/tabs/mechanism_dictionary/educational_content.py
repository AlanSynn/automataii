"""
Educational Content Manager for mechanism documentation and learning materials.
Rich content system with interactive tutorials, examples, and theoretical background.
"""

import logging
from typing import Dict, Any, List, Optional
from PyQt6.QtCore import Qt, pyqtSignal, QUrl
from PyQt6.QtGui import QFont, QPixmap, QPainter, QColor, QTextDocument
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QTextEdit, 
    QLabel, QPushButton, QScrollArea, QFrame, QSplitter,
    QTreeWidget, QTreeWidgetItem, QGroupBox
)

logger = logging.getLogger(__name__)


class TheorySection(QWidget):
    """Widget for displaying theoretical background of mechanisms."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._load_theory_content()
    
    def _setup_ui(self):
        """Setup the theory section UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        
        # Header
        header = QLabel("Theoretical Background")
        header.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        header.setStyleSheet("color: #1976D2; margin-bottom: 8px;")
        layout.addWidget(header)
        
        # Content area
        self.content_area = QTextEdit()
        self.content_area.setReadOnly(True)
        self.content_area.setStyleSheet("""
            QTextEdit {
                border: 1px solid #E0E0E0;
                border-radius: 4px;
                background-color: #FFFFFF;
                padding: 12px;
                font-size: 14px;
                line-height: 1.6;
            }
        """)
        layout.addWidget(self.content_area)
    
    def _load_theory_content(self):
        """Load theoretical content."""
        theory_html = """
        <h2 style="color: #1976D2;">Mechanism Theory Fundamentals</h2>
        
        <h3>What are Mechanisms?</h3>
        <p>Mechanisms are mechanical systems designed to transform motion, force, or energy from one form to another. They are the building blocks of machines and are essential in countless applications from simple tools to complex machinery.</p>
        
        <h3>Key Concepts</h3>
        
        <h4>Degrees of Freedom (DOF)</h4>
        <p>The number of independent parameters needed to define the position of a mechanism. For planar mechanisms:</p>
        <p><strong>DOF = 3(n-1) - 2j - h</strong></p>
        <ul>
            <li><strong>n</strong> = number of links</li>
            <li><strong>j</strong> = number of joints</li>
            <li><strong>h</strong> = number of higher-order joints</li>
        </ul>
        
        <h4>Types of Joints</h4>
        <ul>
            <li><strong>Revolute (Pin) Joint:</strong> Allows rotation about a fixed axis</li>
            <li><strong>Prismatic (Sliding) Joint:</strong> Allows linear translation</li>
            <li><strong>Higher Pairs:</strong> Cam-follower, gear teeth contact</li>
        </ul>
        
        <h4>Mechanical Advantage</h4>
        <p>The ratio of output force to input force, or the factor by which a mechanism multiplies force:</p>
        <p><strong>MA = F_out / F_in = d_in / d_out</strong></p>
        
        <h3>Common Mechanism Types</h3>
        
        <h4>Linkage Mechanisms</h4>
        <p>Systems of rigid links connected by joints. The four-bar linkage is the most fundamental, capable of generating various motion patterns including:</p>
        <ul>
            <li>Crank-rocker motion</li>
            <li>Double-crank motion</li>
            <li>Double-rocker motion</li>
        </ul>
        
        <h4>Gear Systems</h4>
        <p>Mechanisms that transmit power through meshing teeth. Key relationships:</p>
        <ul>
            <li><strong>Gear Ratio:</strong> N₁/N₂ = ω₂/ω₁ (inverse relationship)</li>
            <li><strong>Module:</strong> m = d/N (pitch diameter / number of teeth)</li>
        </ul>
        
        <h4>Cam Mechanisms</h4>
        <p>Provide precise motion control with specifically designed profiles. Types include:</p>
        <ul>
            <li>Radial cams with translating followers</li>
            <li>Cylindrical cams</li>
            <li>End cams</li>
        </ul>
        
        <h3>Design Considerations</h3>
        
        <h4>Grashof's Law</h4>
        <p>For four-bar linkages, if s + l ≤ p + q (where s is shortest, l is longest, p and q are intermediate lengths), the mechanism can rotate continuously.</p>
        
        <h4>Transmission Angle</h4>
        <p>The angle between the coupler and output link in a four-bar mechanism. Optimal range: 40° to 140° for good force transmission.</p>
        
        <h4>Dynamic Analysis</h4>
        <p>Considers forces, torques, and accelerations in moving mechanisms. Essential for:</p>
        <ul>
            <li>Balancing rotating and reciprocating masses</li>
            <li>Minimizing vibrations</li>
            <li>Optimizing energy efficiency</li>
        </ul>
        """
        
        self.content_area.setHtml(theory_html)


class TutorialSection(QWidget):
    """Interactive tutorial section with step-by-step guides."""
    
    tutorial_selected = pyqtSignal(str)  # tutorial_id
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._load_tutorials()
    
    def _setup_ui(self):
        """Setup tutorial section UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        # Tutorial list (left side)
        tutorial_frame = QFrame()
        tutorial_frame.setFixedWidth(250)
        tutorial_layout = QVBoxLayout(tutorial_frame)
        
        tutorial_header = QLabel("Interactive Tutorials")
        tutorial_header.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        tutorial_header.setStyleSheet("color: #1976D2; margin-bottom: 8px;")
        tutorial_layout.addWidget(tutorial_header)
        
        self.tutorial_tree = QTreeWidget()
        self.tutorial_tree.setHeaderHidden(True)
        self.tutorial_tree.setStyleSheet("""
            QTreeWidget {
                border: 1px solid #E0E0E0;
                border-radius: 4px;
                background-color: #FFFFFF;
            }
            QTreeWidget::item {
                padding: 4px;
                border: none;
            }
            QTreeWidget::item:selected {
                background-color: #E3F2FD;
            }
        """)
        tutorial_layout.addWidget(self.tutorial_tree)
        
        layout.addWidget(tutorial_frame)
        
        # Tutorial content (right side)
        self.content_widget = QTextEdit()
        self.content_widget.setReadOnly(True)
        self.content_widget.setStyleSheet("""
            QTextEdit {
                border: 1px solid #E0E0E0;
                border-radius: 4px;
                background-color: #FFFFFF;
                padding: 16px;
                font-size: 14px;
            }
        """)
        layout.addWidget(self.content_widget)
        
        # Connect signals
        self.tutorial_tree.itemClicked.connect(self._on_tutorial_selected)
    
    def _load_tutorials(self):
        """Load tutorial content."""
        tutorials = {
            "Getting Started": {
                "Understanding Mechanisms": """
                <h2>Understanding Mechanisms</h2>
                <p>Welcome to the world of mechanisms! This tutorial will help you understand the basics.</p>
                
                <h3>Step 1: What is a Mechanism?</h3>
                <p>A mechanism is a system of rigid bodies connected by joints that transform motion from input to output.</p>
                
                <h3>Step 2: Basic Components</h3>
                <ul>
                    <li><strong>Links:</strong> Rigid bodies that form the structure</li>
                    <li><strong>Joints:</strong> Connections that allow relative motion</li>
                    <li><strong>Actuators:</strong> Sources of input motion</li>
                </ul>
                
                <h3>Step 3: Try It Yourself</h3>
                <p>1. Select a mechanism from the sidebar</p>
                <p>2. Press the play button to start animation</p>
                <p>3. Adjust parameters to see how they affect motion</p>
                """,
                
                "Navigation Basics": """
                <h2>Navigation Basics</h2>
                <p>Learn how to navigate and interact with the mechanism dictionary.</p>
                
                <h3>Sidebar Navigation</h3>
                <ul>
                    <li>Browse mechanisms by category</li>
                    <li>Use search to find specific mechanisms</li>
                    <li>Filter by complexity level</li>
                </ul>
                
                <h3>Playground Controls</h3>
                <ul>
                    <li>Play/Pause: Control animation</li>
                    <li>Speed: Adjust animation speed</li>
                    <li>Path Trace: Show motion trails</li>
                    <li>Reset View: Fit mechanism to screen</li>
                </ul>
                
                <h3>Parameter Adjustment</h3>
                <ul>
                    <li>Use the inspector panel to modify parameters</li>
                    <li>See real-time effects on mechanism behavior</li>
                    <li>Experiment with different configurations</li>
                </ul>
                """
            },
            
            "Linkage Mechanisms": {
                "Four-Bar Linkage Design": """
                <h2>Four-Bar Linkage Design</h2>
                <p>Master the fundamentals of four-bar linkage design and analysis.</p>
                
                <h3>Design Process</h3>
                <ol>
                    <li><strong>Define Requirements:</strong> What motion do you need?</li>
                    <li><strong>Choose Configuration:</strong> Crank-rocker, double-crank, etc.</li>
                    <li><strong>Apply Grashof's Law:</strong> Check for full rotation capability</li>
                    <li><strong>Optimize Geometry:</strong> Ensure good transmission angles</li>
                </ol>
                
                <h3>Key Parameters</h3>
                <ul>
                    <li><strong>Link Lengths:</strong> Determine motion type</li>
                    <li><strong>Base Length:</strong> Fixed distance between ground pivots</li>
                    <li><strong>Input Speed:</strong> Controls animation rate</li>
                </ul>
                
                <h3>Practice Exercise</h3>
                <p>1. Load the Four-Bar Linkage mechanism</p>
                <p>2. Try different link length combinations</p>
                <p>3. Observe how Grashof's law affects rotation capability</p>
                """,
                
                "Path Generation": """
                <h2>Path Generation with Linkages</h2>
                <p>Learn how to design linkages that generate specific paths.</p>
                
                <h3>Coupler Curves</h3>
                <p>Points on the coupler link trace curves called coupler curves. These can approximate:</p>
                <ul>
                    <li>Straight lines</li>
                    <li>Circles</li>
                    <li>Complex closed curves</li>
                </ul>
                
                <h3>Design Techniques</h3>
                <ol>
                    <li><strong>Graphical Synthesis:</strong> Use geometric construction</li>
                    <li><strong>Analytical Methods:</strong> Solve constraint equations</li>
                    <li><strong>Optimization:</strong> Minimize error between desired and actual paths</li>
                </ol>
                """
            },
            
            "Gear Systems": {
                "Gear Ratio Calculations": """
                <h2>Gear Ratio Calculations</h2>
                <p>Understanding gear ratios is fundamental to gear system design.</p>
                
                <h3>Basic Gear Ratio</h3>
                <p>For two meshing gears:</p>
                <p><strong>Gear Ratio = N₁/N₂ = ω₂/ω₁ = T₂/T₁</strong></p>
                <ul>
                    <li>N = Number of teeth</li>
                    <li>ω = Angular velocity</li>
                    <li>T = Torque</li>
                </ul>
                
                <h3>Compound Gear Trains</h3>
                <p>For multiple gear stages:</p>
                <p><strong>Overall Ratio = Product of individual ratios</strong></p>
                
                <h3>Planetary Gears</h3>
                <p>More complex with three main components:</p>
                <ul>
                    <li>Sun gear (center)</li>
                    <li>Planet gears (orbiting)</li>
                    <li>Ring gear (outer)</li>
                </ul>
                """
            }
        }
        
        # Populate tree widget
        for category, items in tutorials.items():
            category_item = QTreeWidgetItem([category])
            category_item.setFont(0, QFont("Segoe UI", 10, QFont.Weight.Bold))
            self.tutorial_tree.addTopLevelItem(category_item)
            
            for tutorial_name, content in items.items():
                tutorial_item = QTreeWidgetItem([tutorial_name])
                tutorial_item.setData(0, Qt.ItemDataRole.UserRole, content)
                category_item.addChild(tutorial_item)
        
        self.tutorial_tree.expandAll()
    
    def _on_tutorial_selected(self, item: QTreeWidgetItem, column: int):
        """Handle tutorial selection."""
        content = item.data(0, Qt.ItemDataRole.UserRole)
        if content:
            self.content_widget.setHtml(content)


class ExampleGallery(QWidget):
    """Gallery of real-world mechanism examples and applications."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._load_examples()
    
    def _setup_ui(self):
        """Setup example gallery UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        
        # Header
        header = QLabel("Real-World Applications")
        header.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        header.setStyleSheet("color: #1976D2; margin-bottom: 8px;")
        layout.addWidget(header)
        
        # Scroll area for examples
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.examples_widget = QWidget()
        self.examples_layout = QVBoxLayout(self.examples_widget)
        self.examples_layout.setSpacing(16)
        
        scroll.setWidget(self.examples_widget)
        layout.addWidget(scroll)
    
    def _load_examples(self):
        """Load example applications."""
        examples = [
            {
                "title": "Automotive Windshield Wipers",
                "mechanism": "Four-Bar Linkage",
                "description": "Windshield wipers use four-bar linkages to convert rotary motion from the motor into the sweeping motion needed to clear the windshield. The mechanism ensures uniform contact pressure across the entire sweep.",
                "applications": ["Cars", "Trucks", "Aircraft", "Boats"],
                "key_features": ["Parallel motion", "Uniform pressure", "Compact design"]
            },
            {
                "title": "Excavator Arm System",
                "mechanism": "Multiple Four-Bar Linkages",
                "description": "Excavators use a series of four-bar linkages to provide the complex motion needed for digging. Each joint is hydraulically actuated, providing both precision and power.",
                "applications": ["Construction", "Mining", "Demolition"],
                "key_features": ["High force capability", "Precise positioning", "Large workspace"]
            },
            {
                "title": "Automotive Transmission",
                "mechanism": "Planetary Gear System",
                "description": "Modern automatic transmissions use planetary gear sets to provide multiple gear ratios in a compact package. The system allows for smooth shifting without interrupting power flow.",
                "applications": ["Cars", "Trucks", "Heavy machinery"],
                "key_features": ["Multiple ratios", "Compact design", "Smooth operation"]
            },
            {
                "title": "Engine Valve System",
                "mechanism": "Cam and Follower",
                "description": "Internal combustion engines use cam mechanisms to precisely control valve timing. The cam profile determines when and how far valves open, critically affecting engine performance.",
                "applications": ["Automotive engines", "Motorcycles", "Marine engines"],
                "key_features": ["Precise timing", "High speed operation", "Reliable actuation"]
            },
            {
                "title": "Watch Movement",
                "mechanism": "Geneva Drive",
                "description": "Mechanical watches use Geneva drives for the intermittent motion needed in timekeeping mechanisms. The system ensures precise, step-wise motion for accurate time display.",
                "applications": ["Mechanical watches", "Precision instruments", "Indexing mechanisms"],
                "key_features": ["Precise indexing", "No backlash", "Reliable operation"]
            },
            {
                "title": "Robotic Arm Joints",
                "mechanism": "Six-Bar Linkage",
                "description": "Advanced robotic arms use six-bar linkages to achieve complex motion patterns while maintaining structural rigidity. This allows for both dexterity and strength.",
                "applications": ["Industrial robots", "Medical robots", "Research platforms"],
                "key_features": ["Complex motion", "High precision", "Flexible configuration"]
            }
        ]
        
        for example in examples:
            example_card = self._create_example_card(example)
            self.examples_layout.addWidget(example_card)
        
        self.examples_layout.addStretch()
    
    def _create_example_card(self, example: Dict[str, Any]) -> QFrame:
        """Create an example card widget."""
        card = QFrame()
        card.setFrameStyle(QFrame.Shape.Box)
        card.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #E0E0E0;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        
        layout = QVBoxLayout(card)
        layout.setSpacing(8)
        
        # Title and mechanism type
        header_layout = QHBoxLayout()
        
        title = QLabel(example["title"])
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #1976D2;")
        header_layout.addWidget(title)
        
        mechanism_badge = QLabel(example["mechanism"])
        mechanism_badge.setStyleSheet("""
            QLabel {
                background-color: #E3F2FD;
                color: #1976D2;
                border-radius: 12px;
                padding: 4px 12px;
                font-weight: bold;
                font-size: 10px;
            }
        """)
        header_layout.addWidget(mechanism_badge)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # Description
        description = QLabel(example["description"])
        description.setWordWrap(True)
        description.setStyleSheet("color: #424242; line-height: 1.4;")
        layout.addWidget(description)
        
        # Features and applications
        details_layout = QHBoxLayout()
        
        # Applications
        app_group = QGroupBox("Applications")
        app_layout = QVBoxLayout(app_group)
        for app in example["applications"]:
            app_label = QLabel(f"• {app}")
            app_label.setStyleSheet("color: #757575;")
            app_layout.addWidget(app_label)
        details_layout.addWidget(app_group)
        
        # Key features
        features_group = QGroupBox("Key Features")
        features_layout = QVBoxLayout(features_group)
        for feature in example["key_features"]:
            feature_label = QLabel(f"• {feature}")
            feature_label.setStyleSheet("color: #757575;")
            features_layout.addWidget(feature_label)
        details_layout.addWidget(features_group)
        
        layout.addLayout(details_layout)
        
        return card


class EducationalContentManager(QTabWidget):
    """
    Main educational content manager with multiple learning modules.
    
    Provides:
    - Theoretical background
    - Interactive tutorials
    - Real-world examples
    - Design guidelines
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_tabs()
        self._apply_styling()
        
        logger.debug("EducationalContentManager initialized")
    
    def _setup_tabs(self):
        """Setup education content tabs."""
        # Theory tab
        self.theory_section = TheorySection()
        self.addTab(self.theory_section, "📖 Theory")
        
        # Tutorial tab
        self.tutorial_section = TutorialSection()
        self.addTab(self.tutorial_section, "🎓 Tutorials")
        
        # Examples tab
        self.example_gallery = ExampleGallery()
        self.addTab(self.example_gallery, "🏭 Examples")
        
        # Set default tab
        self.setCurrentIndex(0)
    
    def _apply_styling(self):
        """Apply educational content styling."""
        self.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #E0E0E0;
                background-color: #FFFFFF;
            }
            QTabBar::tab {
                background-color: #F5F5F5;
                border: 1px solid #E0E0E0;
                border-bottom: none;
                padding: 8px 16px;
                margin-right: 2px;
                font-weight: 500;
            }
            QTabBar::tab:selected {
                background-color: #FFFFFF;
                color: #1976D2;
                border-bottom: 2px solid #1976D2;
            }
            QTabBar::tab:hover {
                background-color: #E3F2FD;
            }
        """)
    
    def load_mechanism_specific_content(self, mechanism_type: str):
        """Load content specific to a mechanism type."""
        # This could dynamically load content based on the selected mechanism
        # For now, the content is static
        pass
    
    def search_content(self, query: str):
        """Search through educational content."""
        # Could implement content search functionality
        pass