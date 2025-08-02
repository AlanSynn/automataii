"""
Enhanced Mechanism Dictionary Tab with Component Library Design.
Professional showcase interface for mechanical engineering education.
"""

import logging
from typing import Optional, Dict, Any
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QRect
from PyQt6.QtGui import QFont, QPixmap, QPainter, QColor, QBrush, QPen
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QSplitter, QTabWidget,
    QScrollArea, QFrame, QLabel, QPushButton, QGroupBox,
    QGridLayout, QTextEdit, QSlider, QSpinBox, QDoubleSpinBox,
    QComboBox, QCheckBox, QProgressBar, QGraphicsView
)

from automataii.ui.tabs.base.tab import BaseTab
from .state_manager import MechanismDictionaryStateManager
from .preview_manager import MechanismPreviewManager
from .educational_content import EducationalContentManager
from .mechanism_card import MechanismIndexCard
from .interactive_playground import InteractivePlayground
from .styling import ModernStyling
from .tutorial_system import TutorialManager, LearningPathManager

logger = logging.getLogger(__name__)


# ModernTheme class removed - replaced with ModernStyling from styling.py


class EnhancedSidebar(QWidget):
    """Enhanced sidebar with modern design and mechanism index cards."""
    
    mechanism_selected = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(320)
        self.setMaximumWidth(400)
        self._setup_ui()
        self._apply_styling()
    
    def _setup_ui(self):
        """Setup the sidebar UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(ModernStyling.SPACING['md'])
        layout.setContentsMargins(ModernStyling.SPACING['md'], ModernStyling.SPACING['md'], 
                                  ModernStyling.SPACING['md'], ModernStyling.SPACING['md'])
        
        # Header
        header = QLabel("Mechanism Library")
        header.setFont(QFont(ModernStyling.TYPOGRAPHY['font_family'], 
                           ModernStyling.TYPOGRAPHY['font_size_h2'], QFont.Weight.Bold))
        layout.addWidget(header)
        
        # Search and filters
        self._create_search_section(layout)
        
        # Mechanism cards scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.cards_widget = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_widget)
        self.cards_layout.setSpacing(ModernStyling.SPACING['sm'])
        
        self.scroll_area.setWidget(self.cards_widget)
        layout.addWidget(self.scroll_area)
        
        # Stats footer
        self._create_stats_footer(layout)
    
    def _create_search_section(self, layout: QVBoxLayout):
        """Create search and filter section."""
        search_frame = QFrame()
        search_layout = QVBoxLayout(search_frame)
        
        # Search input
        from PyQt6.QtWidgets import QLineEdit
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search mechanisms...")
        search_layout.addWidget(self.search_input)
        
        # Filter controls
        filter_layout = QHBoxLayout()
        
        self.complexity_filter = QComboBox()
        self.complexity_filter.addItems(["All Levels", "Beginner", "Intermediate", "Advanced"])
        filter_layout.addWidget(QLabel("Level:"))
        filter_layout.addWidget(self.complexity_filter)
        
        search_layout.addLayout(filter_layout)
        layout.addWidget(search_frame)
    
    def _create_stats_footer(self, layout: QVBoxLayout):
        """Create statistics footer."""
        stats_frame = QFrame()
        stats_layout = QVBoxLayout(stats_frame)
        
        self.stats_label = QLabel("6 mechanisms • 4 categories")
        self.stats_label.setStyleSheet(f"color: {ModernStyling.COLORS['on_surface_variant']}; font-size: {ModernStyling.TYPOGRAPHY['font_size_caption']}px;")
        stats_layout.addWidget(self.stats_label)
        
        layout.addWidget(stats_frame)
    
    def _apply_styling(self):
        """Apply modern styling."""
        self.setStyleSheet(f"""
        EnhancedSidebar {{
            background-color: {ModernStyling.COLORS['surface']};
            border-right: 1px solid {ModernStyling.COLORS['outline']};
        }}
        """ + ModernStyling.get_input_style() + ModernStyling.get_scroll_area_style())
    
    def load_mechanism_cards(self, categories):
        """Load mechanism cards into the sidebar."""
        # Clear existing cards
        while self.cards_layout.count():
            child = self.cards_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Add category headers and mechanism cards
        for category in categories:
            # Category header
            category_header = QLabel(f"{category.icon} {category.name}")
            category_header.setFont(QFont(ModernStyling.TYPOGRAPHY['font_family'], 
                                        ModernStyling.TYPOGRAPHY['font_size_h3'], QFont.Weight.Bold))
            category_header.setStyleSheet(f"color: {ModernStyling.COLORS['primary']}; margin-top: {ModernStyling.SPACING['md']}px;")
            self.cards_layout.addWidget(category_header)
            
            # Mechanism cards
            for mechanism in category.mechanisms:
                card = MechanismIndexCard(mechanism)
                card.clicked.connect(lambda m_id=mechanism.id: self.mechanism_selected.emit(m_id))
                self.cards_layout.addWidget(card)
        
        # Add stretch
        self.cards_layout.addStretch()


class CenterTabbedInterface(QTabWidget):
    """Central tabbed interface for different views of mechanisms."""
    
    def __init__(self, state_manager: MechanismDictionaryStateManager, parent=None):
        super().__init__(parent)
        self.state_manager = state_manager
        self._setup_tabs()
        self._apply_styling()
    
    def _setup_tabs(self):
        """Setup the tabbed interface."""
        # Interactive Playground (main simulation)
        self.playground = InteractivePlayground(self.state_manager)
        self.addTab(self.playground, "🎮 Playground")
        
        # Documentation
        self.documentation = EducationalContentManager()
        self.addTab(self.documentation, "📚 Documentation")
        
        # Examples & Use Cases
        self.examples = QWidget()
        self._setup_examples_tab()
        self.addTab(self.examples, "🔧 Examples")
        
        # Properties & API
        self.properties = QWidget()
        self._setup_properties_tab()
        self.addTab(self.properties, "⚙️ Properties")
    
    def _setup_examples_tab(self):
        """Setup examples and use cases tab."""
        layout = QVBoxLayout(self.examples)
        
        # Examples content
        examples_text = QTextEdit()
        examples_text.setHtml("""
        <h2>Real-World Applications</h2>
        <h3>Four-Bar Linkages</h3>
        <ul>
            <li><b>Automotive:</b> Windshield wipers, suspension systems</li>
            <li><b>Machinery:</b> Excavator arms, printing press mechanisms</li>
            <li><b>Robotics:</b> Robot arm joints, walking mechanisms</li>
        </ul>
        
        <h3>Gear Systems</h3>
        <ul>
            <li><b>Automotive:</b> Transmissions, differentials</li>
            <li><b>Industrial:</b> Conveyor systems, heavy machinery</li>
            <li><b>Aerospace:</b> Landing gear, control surfaces</li>
        </ul>
        
        <h3>Cam Mechanisms</h3>
        <ul>
            <li><b>Engines:</b> Valve timing systems</li>
            <li><b>Manufacturing:</b> Automated assembly lines</li>
            <li><b>Textiles:</b> Weaving and knitting machines</li>
        </ul>
        """)
        examples_text.setReadOnly(True)
        layout.addWidget(examples_text)
    
    def _setup_properties_tab(self):
        """Setup properties and API documentation tab."""
        layout = QVBoxLayout(self.properties)
        
        # Properties content
        properties_text = QTextEdit()
        properties_text.setHtml("""
        <h2>Mechanism Properties & Parameters</h2>
        
        <h3>Common Properties</h3>
        <table border="1" cellpadding="5">
            <tr><th>Parameter</th><th>Type</th><th>Description</th></tr>
            <tr><td>speed</td><td>float</td><td>Animation speed multiplier (0.1-5.0)</td></tr>
            <tr><td>scale</td><td>float</td><td>Visual scale factor</td></tr>
        </table>
        
        <h3>Linkage Mechanisms</h3>
        <table border="1" cellpadding="5">
            <tr><th>Parameter</th><th>Range</th><th>Unit</th></tr>
            <tr><td>link1_length</td><td>20-100</td><td>mm</td></tr>
            <tr><td>link2_length</td><td>30-150</td><td>mm</td></tr>
            <tr><td>base_length</td><td>50-200</td><td>mm</td></tr>
        </table>
        
        <h3>Gear Systems</h3>
        <table border="1" cellpadding="5">
            <tr><th>Parameter</th><th>Range</th><th>Unit</th></tr>
            <tr><td>gear1_teeth</td><td>8-30</td><td>teeth</td></tr>
            <tr><td>gear2_teeth</td><td>10-50</td><td>teeth</td></tr>
            <tr><td>module</td><td>1.0-4.0</td><td>mm</td></tr>
        </table>
        """)
        properties_text.setReadOnly(True)
        layout.addWidget(properties_text)
    
    def _apply_styling(self):
        """Apply modern tab styling."""
        self.setStyleSheet(ModernStyling.get_tab_style())


class InspectorPanel(QWidget):
    """Context-aware inspector panel showing detailed information."""
    
    def __init__(self, state_manager: MechanismDictionaryStateManager, parent=None):
        super().__init__(parent)
        self.state_manager = state_manager
        self.setMinimumWidth(280)
        self.setMaximumWidth(350)
        self._setup_ui()
        self._apply_styling()
        
        # Connect to state changes
        self.state_manager.mechanism_changed.connect(self._on_mechanism_changed)
        self.state_manager.parameter_changed.connect(self._on_parameter_changed)
    
    def _setup_ui(self):
        """Setup the inspector UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(ModernStyling.SPACING['md'])
        layout.setContentsMargins(ModernStyling.SPACING['md'], ModernStyling.SPACING['md'],
                                  ModernStyling.SPACING['md'], ModernStyling.SPACING['md'])
        
        # Header
        self.header_label = QLabel("Inspector")
        self.header_label.setFont(QFont(ModernStyling.TYPOGRAPHY['font_family'], 
                                      ModernStyling.TYPOGRAPHY['font_size_h2'], QFont.Weight.Bold))
        layout.addWidget(self.header_label)
        
        # Mechanism info card
        self.info_card = self._create_info_card()
        layout.addWidget(self.info_card)
        
        # Parameters section
        self.params_group = QGroupBox("Parameters")
        self.params_layout = QVBoxLayout(self.params_group)
        layout.addWidget(self.params_group)
        
        # Analysis section
        self.analysis_group = QGroupBox("Analysis")
        self.analysis_layout = QVBoxLayout(self.analysis_group)
        layout.addWidget(self.analysis_group)
        
        # Animation controls
        self.controls_group = QGroupBox("Animation")
        self.controls_layout = QVBoxLayout(self.controls_group)
        self._create_animation_controls()
        layout.addWidget(self.controls_group)
        
        layout.addStretch()
    
    def _create_info_card(self) -> QFrame:
        """Create mechanism information card."""
        card = QFrame()
        card.setStyleSheet(ModernStyling.get_card_style())
        
        # Add shadow effect
        card.setGraphicsEffect(ModernStyling.create_card_shadow(card))
        
        layout = QVBoxLayout(card)
        
        self.name_label = QLabel("No mechanism selected")
        self.name_label.setFont(QFont(ModernStyling.TYPOGRAPHY['font_family'], 
                                    ModernStyling.TYPOGRAPHY['font_size_h3'], QFont.Weight.Bold))
        layout.addWidget(self.name_label)
        
        self.description_label = QLabel("")
        self.description_label.setWordWrap(True)
        self.description_label.setStyleSheet(f"color: {ModernStyling.COLORS['on_surface_variant']};")
        layout.addWidget(self.description_label)
        
        # Complexity badge
        self.complexity_label = QLabel("")
        layout.addWidget(self.complexity_label)
        
        return card
    
    def _create_animation_controls(self):
        """Create animation control widgets."""
        # Control buttons
        button_layout = QHBoxLayout()
        
        self.play_button = QPushButton("▶")
        self.play_button.setStyleSheet(ModernStyling.get_button_style("primary"))
        self.stop_button = QPushButton("⏸")
        self.stop_button.setStyleSheet(ModernStyling.get_button_style("secondary"))
        self.reset_button = QPushButton("⏮")
        self.reset_button.setStyleSheet(ModernStyling.get_button_style("secondary"))
        
        button_layout.addWidget(self.play_button)
        button_layout.addWidget(self.stop_button)
        button_layout.addWidget(self.reset_button)
        
        self.controls_layout.addLayout(button_layout)
        
        # Speed control
        speed_layout = QHBoxLayout()
        speed_layout.addWidget(QLabel("Speed:"))
        
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(1, 50)
        self.speed_slider.setValue(10)
        speed_layout.addWidget(self.speed_slider)
        
        self.speed_label = QLabel("1.0x")
        speed_layout.addWidget(self.speed_label)
        
        self.controls_layout.addLayout(speed_layout)
    
    def _apply_styling(self):
        """Apply inspector panel styling."""
        self.setStyleSheet(f"""
        InspectorPanel {{
            background-color: {ModernStyling.COLORS['surface']};
            border-left: 1px solid {ModernStyling.COLORS['outline']};
        }}
        QGroupBox {{
            font-weight: bold;
            border: 1px solid {ModernStyling.COLORS['outline']};
            border-radius: 6px;
            margin-top: 8px;
            padding-top: 8px;
            background-color: {ModernStyling.COLORS['surface_variant']};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 8px;
            padding: 0 4px 0 4px;
            color: {ModernStyling.COLORS['primary']};
        }}
        """ + ModernStyling.get_slider_style())
    
    def _on_mechanism_changed(self, mechanism_id: str):
        """Handle mechanism selection changes."""
        mechanism_info = self.state_manager.get_current_mechanism_info()
        if mechanism_info:
            self.name_label.setText(mechanism_info.name)
            self.description_label.setText(mechanism_info.description)
            
            # Complexity badge
            self.complexity_label.setText(mechanism_info.complexity.upper())
            self.complexity_label.setStyleSheet(ModernStyling.get_complexity_badge_style(mechanism_info.complexity))
            
            self._update_parameters()
            self._update_analysis()
    
    def _on_parameter_changed(self, param_name: str, value):
        """Handle parameter changes."""
        self._update_analysis()
    
    def _update_parameters(self):
        """Update parameter controls."""
        # Clear existing parameters
        while self.params_layout.count():
            child = self.params_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Add current mechanism parameters
        param_info = self.state_manager.get_parameter_info()
        for param_name, info in param_info.items():
            param_widget = self._create_parameter_widget(param_name, info)
            self.params_layout.addWidget(param_widget)
    
    def _create_parameter_widget(self, param_name: str, param_info: Dict[str, Any]) -> QWidget:
        """Create a parameter control widget."""
        widget = QFrame()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Parameter label
        label = QLabel(param_info.get("name", param_name))
        label.setFont(QFont(ModernStyling.TYPOGRAPHY['font_family'], 
                          ModernStyling.TYPOGRAPHY['font_size_caption']))
        layout.addWidget(label)
        
        # Parameter control
        param_type = param_info.get("type", "float")
        if param_type == "int":
            control = QSpinBox()
            control.setRange(int(param_info.get("min", 0)), int(param_info.get("max", 100)))
            control.setValue(int(param_info.get("default", 0)))
        else:
            control = QDoubleSpinBox()
            control.setRange(float(param_info.get("min", 0.0)), float(param_info.get("max", 100.0)))
            control.setValue(float(param_info.get("default", 0.0)))
            control.setDecimals(1)
        
        layout.addWidget(control)
        return widget
    
    def _update_analysis(self):
        """Update analysis information."""
        # Clear existing analysis
        while self.analysis_layout.count():
            child = self.analysis_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Add mechanism-specific analysis
        mechanism_instance = self.state_manager.get_current_mechanism_instance()
        if mechanism_instance:
            analysis_text = QTextEdit()
            analysis_text.setMaximumHeight(120)
            analysis_text.setReadOnly(True)
            
            # Get mechanism-specific analysis
            if hasattr(mechanism_instance, 'get_gear_ratio'):
                ratio = mechanism_instance.get_gear_ratio()
                analysis_text.setPlainText(f"Gear Ratio: {ratio:.2f}:1")
            elif hasattr(mechanism_instance, 'is_valid_configuration'):
                valid = mechanism_instance.is_valid_configuration()
                analysis_text.setPlainText(f"Configuration: {'Valid' if valid else 'Invalid'}")
            else:
                analysis_text.setPlainText("Real-time analysis available during animation")
            
            self.analysis_layout.addWidget(analysis_text)


class EnhancedMechanismDictionaryTab(BaseTab):
    """Enhanced Mechanism Dictionary with component library design."""
    
    def __init__(self, main_window, parent=None):
        super().__init__(main_window, parent)
        self.state_manager: Optional[MechanismDictionaryStateManager] = None
        self._initialize_enhanced_tab()
        logger.info("Enhanced Mechanism Dictionary Tab initialized")
    
    def _initialize_enhanced_tab(self):
        """Initialize the enhanced tab."""
        try:
            # Initialize state manager
            self.state_manager = MechanismDictionaryStateManager(self)
            
            # Initialize tutorial and learning systems
            self.tutorial_manager = TutorialManager(self)
            self.learning_path_manager = LearningPathManager()
            
            # Setup enhanced UI
            self._setup_enhanced_ui()
            
            # Connect signals
            self._connect_enhanced_signals()
            
            # Load initial data
            self._load_initial_data()
            
            # Check if first visit for tutorial
            self._check_first_visit()
            
        except Exception as e:
            logger.error(f"Failed to initialize Enhanced Mechanism Dictionary: {e}")
            import traceback
            traceback.print_exc()
            # Continue with partial initialization
    
    def _setup_enhanced_ui(self):
        """Setup the enhanced three-panel layout."""
        # Main layout
        self.setLayout(QHBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().setSpacing(0)
        
        # Create main splitter
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.layout().addWidget(self.main_splitter)
        
        # Enhanced sidebar
        self.sidebar = EnhancedSidebar()
        self.main_splitter.addWidget(self.sidebar)
        
        # Center tabbed interface
        self.center_tabs = CenterTabbedInterface(self.state_manager)
        self.main_splitter.addWidget(self.center_tabs)
        
        # Inspector panel
        self.inspector = InspectorPanel(self.state_manager)
        self.main_splitter.addWidget(self.inspector)
        
        # Set splitter proportions (sidebar:center:inspector = 1:3:1)
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 3)
        self.main_splitter.setStretchFactor(2, 1)
        self.main_splitter.setSizes([320, 800, 300])
        
        # Apply global styling
        self._apply_global_styling()
    
    def _apply_global_styling(self):
        """Apply global component library styling."""
        self.setStyleSheet(f"""
        QWidget {{
            font-family: {ModernStyling.TYPOGRAPHY['font_family']};
            font-size: {ModernStyling.TYPOGRAPHY['font_size_body']}px;
            background-color: {ModernStyling.COLORS['background']};
        }}
        """ + ModernStyling.get_input_style())
    
    def _connect_enhanced_signals(self):
        """Connect enhanced component signals."""
        # Sidebar to mechanism selection
        self.sidebar.mechanism_selected.connect(self.state_manager.set_current_mechanism)
        
        # Animation controls
        self.inspector.play_button.clicked.connect(self.state_manager.start_animation)
        self.inspector.stop_button.clicked.connect(self.state_manager.stop_animation)
        self.inspector.reset_button.clicked.connect(self.state_manager.reset_animation)
        
        # Speed control
        self.inspector.speed_slider.valueChanged.connect(self._on_speed_changed)
    
    def _on_speed_changed(self, value: int):
        """Handle speed slider changes."""
        speed = value / 10.0
        self.inspector.speed_label.setText(f"{speed:.1f}x")
        self.state_manager.set_animation_speed(speed)
    
    def _load_initial_data(self):
        """Load initial data."""
        if self.state_manager:
            categories = self.state_manager.get_categories()
            self.sidebar.load_mechanism_cards(categories)
    
    def activate_tab(self):
        """Called when tab becomes active."""
        logger.debug("Enhanced Mechanism Dictionary tab activated")
    
    def deactivate_tab(self):
        """Called when tab becomes inactive."""
        logger.debug("Enhanced Mechanism Dictionary tab deactivated")
        if self.state_manager and self.state_manager.is_animating():
            self.state_manager.stop_animation()
    
    def _check_first_visit(self):
        """Check if this is user's first visit and start tutorial if needed."""
        # In a real implementation, this would check user preferences/settings
        # For now, we'll assume first visit
        recommended_tutorial = self.learning_path_manager.get_recommended_next_tutorial()
        if recommended_tutorial == "first_visit":
            # Delay tutorial start to allow UI to fully load
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(1000, lambda: self.tutorial_manager.start_tutorial("first_visit"))
    
    def _connect_tutorial_signals(self):
        """Connect tutorial system signals."""
        self.tutorial_manager.tutorial_completed.connect(self._on_tutorial_completed)
        self.tutorial_manager.tutorial_skipped.connect(self._on_tutorial_skipped)
    
    def _on_tutorial_completed(self, tutorial_name: str):
        """Handle tutorial completion."""
        self.learning_path_manager.complete_tutorial(tutorial_name)
        logger.info(f"Tutorial completed: {tutorial_name}")
        
        # Show progress feedback
        progress = self.learning_path_manager.get_progress_summary()
        # Could show a completion dialog or notification here
    
    def _on_tutorial_skipped(self, tutorial_name: str):
        """Handle tutorial skip."""
        logger.info(f"Tutorial skipped: {tutorial_name}")
        # Could track skip events for analytics
    
    def start_mechanism_tutorial(self, mechanism_type: str):
        """Start a tutorial specific to a mechanism type."""
        tutorial_name = f"{mechanism_type}_basics"
        if tutorial_name in self.tutorial_manager.tutorials:
            if self.learning_path_manager.can_access_tutorial(tutorial_name):
                self.tutorial_manager.start_tutorial(tutorial_name)
            else:
                # Show prerequisites dialog
                logger.info(f"Prerequisites not met for {tutorial_name}")
    
    def cleanup(self):
        """Cleanup resources."""
        if hasattr(self, 'tutorial_manager'):
            self.tutorial_manager.overlay.hide()
        if self.state_manager:
            self.state_manager.stop_animation()
            self.state_manager.deleteLater()
        super().cleanup()