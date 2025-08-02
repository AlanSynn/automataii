"""
UI Panel for the Mechanism Dictionary tab.
Provides sidebar navigation with categorized mechanism browsing and search.
"""

import logging
from typing import Optional, Dict, Any
from PyQt6.QtCore import QObject, pyqtSignal, Qt, QModelIndex
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QFont, QIcon
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTreeView, QLineEdit, QComboBox, QLabel, QPushButton,
    QGroupBox, QSlider, QDoubleSpinBox, QSpinBox,
    QFrame, QScrollArea, QSizePolicy
)

from automataii.domain.fabrication.mechanisms.catalog_manager import MechanismInfo, CategoryInfo

logger = logging.getLogger(__name__)


class MechanismTreeModel(QStandardItemModel):
    """
    Tree model for displaying categorized mechanisms.
    """
    
    def __init__(self):
        super().__init__()
        self.setHorizontalHeaderLabels(["Name", "Type"])
        
        # Store category and mechanism items for easy access
        self.category_items: Dict[str, QStandardItem] = {}
        self.mechanism_items: Dict[str, QStandardItem] = {}
    
    def add_category(self, category: CategoryInfo) -> QStandardItem:
        """Add a category to the tree."""
        category_item = QStandardItem(f"{category.icon} {category.name}")
        category_item.setData(category.id, Qt.ItemDataRole.UserRole)
        category_item.setData("category", Qt.ItemDataRole.UserRole + 1)
        category_item.setToolTip(category.description)
        
        # Make category bold
        font = category_item.font()
        font.setBold(True)
        category_item.setFont(font)
        
        # Category is not selectable, only expandable
        category_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        
        self.appendRow([category_item, QStandardItem("")])
        self.category_items[category.id] = category_item
        
        return category_item
    
    def add_mechanism(self, mechanism: MechanismInfo, category_item: QStandardItem) -> QStandardItem:
        """Add a mechanism to a category."""
        mechanism_item = QStandardItem(mechanism.name)
        mechanism_item.setData(mechanism.id, Qt.ItemDataRole.UserRole)
        mechanism_item.setData("mechanism", Qt.ItemDataRole.UserRole + 1)
        mechanism_item.setToolTip(mechanism.description)
        
        type_item = QStandardItem(mechanism.complexity.title())
        type_item.setToolTip(f"Complexity: {mechanism.complexity}")
        
        # Add complexity color coding
        if mechanism.complexity == "beginner":
            type_item.setForeground(Qt.GlobalColor.darkGreen)
        elif mechanism.complexity == "intermediate":
            type_item.setForeground(Qt.GlobalColor.darkYellow)
        elif mechanism.complexity == "advanced":
            type_item.setForeground(Qt.GlobalColor.darkRed)
        
        category_item.appendRow([mechanism_item, type_item])
        self.mechanism_items[mechanism.id] = mechanism_item
        
        return mechanism_item
    
    def clear_and_rebuild(self, categories: list[CategoryInfo]):
        """Clear the model and rebuild with new data."""
        self.clear()
        self.setHorizontalHeaderLabels(["Name", "Type"])
        self.category_items.clear()
        self.mechanism_items.clear()
        
        for category in categories:
            category_item = self.add_category(category)
            
            for mechanism in category.mechanisms:
                self.add_mechanism(mechanism, category_item)
    
    def get_item_data(self, index: QModelIndex) -> tuple[str, str]:
        """Get the ID and type of an item."""
        if not index.isValid():
            return "", ""
        
        item = self.itemFromIndex(index)
        if not item:
            return "", ""
        
        item_id = item.data(Qt.ItemDataRole.UserRole) or ""
        item_type = item.data(Qt.ItemDataRole.UserRole + 1) or ""
        
        return item_id, item_type


class ParameterWidget(QWidget):
    """Widget for editing a single mechanism parameter."""
    
    value_changed = pyqtSignal(str, object)  # parameter_name, value
    
    def __init__(self, param_name: str, param_info: Dict[str, Any]):
        super().__init__()
        self.param_name = param_name
        self.param_info = param_info
        
        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().setSpacing(4)
        
        # Parameter label
        label_text = param_info.get("name", param_name)
        unit = param_info.get("unit", "")
        if unit:
            label_text += f" ({unit})"
        
        self.label = QLabel(label_text)
        self.label.setFont(QFont("Arial", 9))
        self.layout().addWidget(self.label)
        
        # Parameter control based on type
        param_type = param_info.get("type", "float")
        self.control = self._create_control(param_type, param_info)
        self.layout().addWidget(self.control)
        
        # Description tooltip
        description = param_info.get("description", "")
        if description:
            self.setToolTip(description)
    
    def _create_control(self, param_type: str, param_info: Dict[str, Any]) -> QWidget:
        """Create the appropriate control widget for the parameter type."""
        if param_type == "int":
            control = QSpinBox()
            control.setMinimum(int(param_info.get("min", 0)))
            control.setMaximum(int(param_info.get("max", 100)))
            control.setValue(int(param_info.get("default", 0)))
            control.valueChanged.connect(lambda v: self.value_changed.emit(self.param_name, v))
        
        elif param_type == "float":
            control = QDoubleSpinBox()
            control.setDecimals(1)
            control.setMinimum(float(param_info.get("min", 0.0)))
            control.setMaximum(float(param_info.get("max", 100.0)))
            control.setValue(float(param_info.get("default", 0.0)))
            control.valueChanged.connect(lambda v: self.value_changed.emit(self.param_name, v))
        
        else:
            # Default to float
            control = QDoubleSpinBox()
            control.setDecimals(1)
            control.setValue(float(param_info.get("default", 0.0)))
            control.valueChanged.connect(lambda v: self.value_changed.emit(self.param_name, v))
        
        return control
    
    def set_value(self, value: Any):
        """Set the parameter value."""
        if hasattr(self.control, 'setValue'):
            self.control.setValue(value)
    
    def get_value(self) -> Any:
        """Get the current parameter value."""
        if hasattr(self.control, 'value'):
            return self.control.value()
        return None


class MechanismDictionaryUIPanel(QWidget):
    """
    Main UI panel for the Mechanism Dictionary tab.
    
    Provides:
    - Sidebar with categorized mechanism tree
    - Search and filter controls  
    - Parameter editing panel
    - Animation controls
    """
    
    # Signals
    category_selected = pyqtSignal(str)  # category_id
    mechanism_selected = pyqtSignal(str)  # mechanism_id
    search_query_changed = pyqtSignal(str)  # query
    parameter_changed = pyqtSignal(str, object)  # parameter_name, value
    animation_play_requested = pyqtSignal()
    animation_stop_requested = pyqtSignal()
    animation_reset_requested = pyqtSignal()
    animation_speed_changed = pyqtSignal(float)  # speed
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Models and state
        self.tree_model = MechanismTreeModel()
        self.current_mechanism_id: Optional[str] = None
        self.parameter_widgets: Dict[str, ParameterWidget] = {}
        
        # Setup UI
        self._setup_ui()
        self._connect_signals()
        
        logger.debug("MechanismDictionaryUIPanel initialized")
    
    def _setup_ui(self):
        """Setup the user interface."""
        self.setLayout(QHBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().setSpacing(0)
        
        # Create main splitter
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.layout().addWidget(self.splitter)
        
        # Create sidebar
        self.sidebar = self._create_sidebar()
        self.splitter.addWidget(self.sidebar)
        
        # Create parameter panel
        self.parameter_panel = self._create_parameter_panel()
        self.splitter.addWidget(self.parameter_panel)
        
        # Set splitter proportions (sidebar:parameters = 2:1)
        self.splitter.setStretchFactor(0, 2)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([400, 200])
    
    def _create_sidebar(self) -> QWidget:
        """Create the sidebar with mechanism tree and search."""
        sidebar = QWidget()
        sidebar.setLayout(QVBoxLayout())
        sidebar.setMinimumWidth(300)
        sidebar.setMaximumWidth(500)
        
        # Search section
        search_group = QGroupBox("Search & Filter")
        search_layout = QVBoxLayout(search_group)
        
        # Search box
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search mechanisms...")
        search_layout.addWidget(self.search_edit)
        
        # Filter controls
        filter_layout = QHBoxLayout()
        
        self.complexity_filter = QComboBox()
        self.complexity_filter.addItems(["All", "Beginner", "Intermediate", "Advanced"])
        filter_layout.addWidget(QLabel("Complexity:"))
        filter_layout.addWidget(self.complexity_filter)
        
        search_layout.addLayout(filter_layout)
        sidebar.layout().addWidget(search_group)
        
        # Mechanism tree
        tree_group = QGroupBox("Mechanisms")
        tree_layout = QVBoxLayout(tree_group)
        
        self.mechanism_tree = QTreeView()
        self.mechanism_tree.setModel(self.tree_model)
        self.mechanism_tree.setHeaderHidden(False)
        self.mechanism_tree.setRootIsDecorated(True)
        self.mechanism_tree.setAlternatingRowColors(True)
        self.mechanism_tree.expandAll()
        
        # Configure tree view
        self.mechanism_tree.setColumnWidth(0, 200)
        
        tree_layout.addWidget(self.mechanism_tree)
        sidebar.layout().addWidget(tree_group)
        
        return sidebar
    
    def _create_parameter_panel(self) -> QWidget:
        """Create the parameter editing and animation control panel."""
        panel = QWidget()
        panel.setLayout(QVBoxLayout())
        panel.setMinimumWidth(200)
        
        # Mechanism info section
        self.info_group = QGroupBox("Mechanism Info")
        info_layout = QVBoxLayout(self.info_group)
        
        self.mechanism_name_label = QLabel("No mechanism selected")
        self.mechanism_name_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        info_layout.addWidget(self.mechanism_name_label)
        
        self.mechanism_desc_label = QLabel("")
        self.mechanism_desc_label.setWordWrap(True)
        self.mechanism_desc_label.setFont(QFont("Arial", 9))
        info_layout.addWidget(self.mechanism_desc_label)
        
        panel.layout().addWidget(self.info_group)
        
        # Parameters section
        self.parameters_group = QGroupBox("Parameters")
        
        # Use scroll area for parameters
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.parameters_widget = QWidget()
        self.parameters_layout = QVBoxLayout(self.parameters_widget)
        self.parameters_layout.setSpacing(8)
        scroll_area.setWidget(self.parameters_widget)
        
        params_layout = QVBoxLayout(self.parameters_group)
        params_layout.addWidget(scroll_area)
        
        panel.layout().addWidget(self.parameters_group)
        
        # Animation controls section
        self.animation_group = QGroupBox("Animation")
        animation_layout = QVBoxLayout(self.animation_group)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        self.play_button = QPushButton("▶ Play")
        self.stop_button = QPushButton("⏸ Stop")
        self.reset_button = QPushButton("⏮ Reset")
        
        self.play_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.reset_button.setEnabled(False)
        
        button_layout.addWidget(self.play_button)
        button_layout.addWidget(self.stop_button)
        button_layout.addWidget(self.reset_button)
        
        animation_layout.addLayout(button_layout)
        
        # Speed control
        speed_layout = QHBoxLayout()
        speed_layout.addWidget(QLabel("Speed:"))
        
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setMinimum(1)
        self.speed_slider.setMaximum(50)
        self.speed_slider.setValue(10)  # 1.0x speed
        self.speed_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.speed_slider.setTickInterval(10)
        
        self.speed_label = QLabel("1.0x")
        self.speed_label.setMinimumWidth(40)
        
        speed_layout.addWidget(self.speed_slider)
        speed_layout.addWidget(self.speed_label)
        
        animation_layout.addLayout(speed_layout)
        
        panel.layout().addWidget(self.animation_group)
        
        # Add stretch to push everything to top
        panel.layout().addStretch()
        
        return panel
    
    def _connect_signals(self):
        """Connect UI signals."""
        # Tree selection
        self.mechanism_tree.selectionModel().currentChanged.connect(self._on_tree_selection_changed)
        
        # Search
        self.search_edit.textChanged.connect(self.search_query_changed.emit)
        
        # Animation controls
        self.play_button.clicked.connect(self.animation_play_requested.emit)
        self.stop_button.clicked.connect(self.animation_stop_requested.emit)
        self.reset_button.clicked.connect(self.animation_reset_requested.emit)
        
        # Speed control
        self.speed_slider.valueChanged.connect(self._on_speed_changed)
    
    def _on_tree_selection_changed(self, current: QModelIndex, previous: QModelIndex):
        """Handle tree view selection changes."""
        item_id, item_type = self.tree_model.get_item_data(current)
        
        if item_type == "category":
            self.category_selected.emit(item_id)
        elif item_type == "mechanism":
            self.mechanism_selected.emit(item_id)
    
    def _on_speed_changed(self, value: int):
        """Handle animation speed changes."""
        speed = value / 10.0  # Convert to 0.1x to 5.0x range
        self.speed_label.setText(f"{speed:.1f}x")
        self.animation_speed_changed.emit(speed)
    
    def load_categories(self, categories: list[CategoryInfo]):
        """Load categories into the tree view."""
        self.tree_model.clear_and_rebuild(categories)
        self.mechanism_tree.expandAll()
        logger.debug(f"Loaded {len(categories)} categories into tree")
    
    def set_current_mechanism(self, mechanism_info: Optional[MechanismInfo]):
        """Set the current mechanism and update the UI."""
        if mechanism_info:
            self.current_mechanism_id = mechanism_info.id
            
            # Update info section
            self.mechanism_name_label.setText(mechanism_info.name)
            self.mechanism_desc_label.setText(mechanism_info.description)
            
            # Enable animation controls
            self.play_button.setEnabled(True)
            self.stop_button.setEnabled(True)
            self.reset_button.setEnabled(True)
            
            # Load parameters
            self._load_parameters(mechanism_info.parameters)
            
        else:
            self.current_mechanism_id = None
            self.mechanism_name_label.setText("No mechanism selected")
            self.mechanism_desc_label.setText("")
            
            # Disable animation controls
            self.play_button.setEnabled(False)
            self.stop_button.setEnabled(False)
            self.reset_button.setEnabled(False)
            
            # Clear parameters
            self._clear_parameters()
    
    def _load_parameters(self, parameters: Dict[str, Dict[str, Any]]):
        """Load parameter controls for the current mechanism."""
        self._clear_parameters()
        
        for param_name, param_info in parameters.items():
            widget = ParameterWidget(param_name, param_info)
            widget.value_changed.connect(self.parameter_changed.emit)
            
            self.parameters_layout.addWidget(widget)
            self.parameter_widgets[param_name] = widget
        
        # Add stretch to push parameters to top
        self.parameters_layout.addStretch()
    
    def _clear_parameters(self):
        """Clear all parameter widgets."""
        # Remove all widgets
        while self.parameters_layout.count() > 0:
            child = self.parameters_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        self.parameter_widgets.clear()
    
    def update_parameter_value(self, param_name: str, value: Any):
        """Update a parameter value in the UI."""
        if param_name in self.parameter_widgets:
            self.parameter_widgets[param_name].set_value(value)
    
    def set_animation_state(self, is_playing: bool):
        """Update animation control states."""
        self.play_button.setEnabled(not is_playing)
        self.stop_button.setEnabled(is_playing)
        
        if is_playing:
            self.play_button.setText("▶ Playing...")
        else:
            self.play_button.setText("▶ Play")