"""
Enhanced Mechanism Dictionary Tab - Macanism-style reference and catalog system

This tab provides a comprehensive mechanism reference with:
- Professional catalog browsing with live previews
- Interactive mechanism exploration
- Educational content integration
- Real-time parameter visualization
- Export capabilities for mechanism data
"""

import json
import math
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QListWidget, 
    QListWidgetItem, QLabel, QPushButton, QGroupBox, QTextEdit,
    QScrollArea, QFrame, QTabWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QFont

from ..base.macanism_tab import MacanismStyleTab, MacanismConfig
from ...mechanism_foundry.hci.parametric_controls import (
    ParameterState, ParameterType, ParameterConstraint
)


@dataclass
class MechanismCatalogEntry:
    """Complete mechanism catalog entry"""
    id: str
    name: str
    category: str
    description: str
    complexity_level: int  # 1-5
    key_concepts: List[str]
    parameters: Dict[str, Any]
    educational_content: Dict[str, str]
    thumbnail_data: Optional[bytes] = None
    animation_data: Optional[Dict] = None


class MechanismCatalogWidget(QListWidget):
    """Professional mechanism catalog with live previews"""
    
    mechanismSelected = pyqtSignal(dict)
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        # Setup catalog appearance
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setIconSize(QSize(120, 90))
        self.setSpacing(12)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setMovement(QListWidget.Movement.Static)
        
        # Professional styling
        self.setStyleSheet("""
            QListWidget {
                background-color: #f8f9fa;
                border: 2px solid #dee2e6;
                border-radius: 8px;
                padding: 12px;
            }
            QListWidget::item {
                background-color: white;
                border: 2px solid #e9ecef;
                border-radius: 8px;
                padding: 8px;
                margin: 4px;
            }
            QListWidget::item:selected {
                background-color: #e3f2fd;
                border-color: #0d6efd;
            }
            QListWidget::item:hover {
                background-color: #f5f5f5;
                border-color: #adb5bd;
            }
        """)
        
        # Load mechanism catalog
        self.catalog_entries: Dict[str, MechanismCatalogEntry] = {}
        self.load_mechanism_catalog()
        
        # Connect signals
        self.itemClicked.connect(self.on_item_clicked)
        
    def load_mechanism_catalog(self):
        """Load comprehensive mechanism catalog"""
        # Professional mechanism catalog with educational content
        mechanisms = [
            {
                'id': 'four_bar_linkage',
                'name': 'Four-Bar Linkage',
                'category': 'Linkages',
                'description': 'The fundamental planar linkage mechanism with four rigid links connected by four revolute joints.',
                'complexity_level': 2,
                'key_concepts': ['Grashof Condition', 'Coupler Curves', 'Transmission Angle', 'Dead Positions'],
                'parameters': {
                    'Link Lengths': {
                        'Link 1 (Ground)': {'default': 120.0, 'min': 50.0, 'max': 200.0, 'type': 'length', 'category': 'Geometry'},
                        'Link 2 (Input)': {'default': 60.0, 'min': 20.0, 'max': 150.0, 'type': 'length', 'category': 'Geometry'},
                        'Link 3 (Coupler)': {'default': 100.0, 'min': 40.0, 'max': 180.0, 'type': 'length', 'category': 'Geometry'},
                        'Link 4 (Output)': {'default': 80.0, 'min': 30.0, 'max': 160.0, 'type': 'length', 'category': 'Geometry'},
                    },
                    'Motion Parameters': {
                        'Input Speed': {'default': 60.0, 'min': 10.0, 'max': 300.0, 'type': 'speed', 'category': 'Motion'},
                        'Input Angle': {'default': 0.0, 'min': 0.0, 'max': 360.0, 'type': 'angle', 'category': 'Motion'},
                    }
                },
                'educational_content': {
                    'theory': '''The four-bar linkage is the simplest and most fundamental of all closed-loop linkages. 
                    It consists of four rigid bodies (links) connected in a loop by four lower pairs (revolute joints).
                    
                    Key Principles:
                    • Grashof's Law determines the type of motion possible
                    • Coupler curves trace complex paths useful for motion generation
                    • Transmission angle affects force transmission efficiency
                    • Dead positions occur when input and output links are collinear''',
                    
                    'applications': '''Four-bar linkages are ubiquitous in mechanical systems:
                    • Automotive: Suspension systems, windshield wipers
                    • Industrial: Packaging machinery, conveyor systems  
                    • Consumer: Exercise equipment, desk lamps
                    • Robotics: Robot arms, walking mechanisms''',
                    
                    'design_tips': '''Design Guidelines:
                    • Ensure Grashof condition is satisfied for continuous rotation
                    • Optimize transmission angle (ideally 45°-135°)
                    • Consider coupler curve shape for path generation
                    • Account for dead positions in mechanism design'''
                }
            },
            
            {
                'id': 'cam_follower',
                'name': 'Cam-Follower System',
                'category': 'Cams',
                'description': 'Mechanism that transforms rotary motion into oscillating or reciprocating motion through a shaped cam profile.',
                'complexity_level': 3,
                'key_concepts': ['Cam Profile Design', 'Follower Motion', 'Pressure Angle', 'Jerk Analysis'],
                'parameters': {
                    'Cam Profile': {
                        'Base Radius': {'default': 40.0, 'min': 20.0, 'max': 80.0, 'type': 'length', 'category': 'Geometry'},
                        'Lift Height': {'default': 20.0, 'min': 5.0, 'max': 50.0, 'type': 'length', 'category': 'Geometry'},
                        'Profile Type': {'default': 'harmonic', 'options': ['harmonic', 'cycloidal', 'polynomial'], 'type': 'enum', 'category': 'Profile'},
                    },
                    'Motion Parameters': {
                        'Cam Speed': {'default': 120.0, 'min': 30.0, 'max': 600.0, 'type': 'speed', 'category': 'Motion'},
                        'Dwell Angle': {'default': 60.0, 'min': 0.0, 'max': 180.0, 'type': 'angle', 'category': 'Motion'},
                    }
                },
                'educational_content': {
                    'theory': '''Cam mechanisms provide precise control over follower motion through carefully designed cam profiles.
                    The cam profile determines the displacement, velocity, and acceleration of the follower.
                    
                    Key Principles:
                    • Profile design affects motion smoothness and dynamic forces
                    • Pressure angle influences force transmission and cam size
                    • Jerk (acceleration derivative) affects vibration and wear
                    • Contact stress limits determine material requirements''',
                    
                    'applications': '''Cam systems are essential in precision machinery:
                    • Automotive: Engine valve systems, fuel injection
                    • Manufacturing: Automated assembly, indexing mechanisms
                    • Textiles: Looms, knitting machines
                    • Printing: Paper feed mechanisms''',
                }
            },
            
            {
                'id': 'gear_train',
                'name': 'Gear Train System',
                'category': 'Gears',
                'description': 'System of gears that transmits motion and torque with precise speed ratios.',
                'complexity_level': 2,
                'key_concepts': ['Gear Ratio', 'Involute Profiles', 'Contact Ratio', 'Efficiency'],
                'parameters': {
                    'Gear Specifications': {
                        'Gear 1 Teeth': {'default': 24, 'min': 12, 'max': 80, 'type': 'count', 'category': 'Geometry'},
                        'Gear 2 Teeth': {'default': 36, 'min': 18, 'max': 120, 'type': 'count', 'category': 'Geometry'},
                        'Module': {'default': 2.0, 'min': 0.5, 'max': 5.0, 'type': 'length', 'category': 'Geometry'},
                        'Pressure Angle': {'default': 20.0, 'min': 14.5, 'max': 25.0, 'type': 'angle', 'category': 'Geometry'},
                    },
                    'Operation': {
                        'Input Speed': {'default': 100.0, 'min': 10.0, 'max': 1000.0, 'type': 'speed', 'category': 'Motion'},
                        'Input Torque': {'default': 50.0, 'min': 5.0, 'max': 500.0, 'type': 'force', 'category': 'Loading'},
                    }
                },
                'educational_content': {
                    'theory': '''Gear trains provide precise speed and torque conversion through meshing teeth.
                    The involute tooth profile ensures constant velocity ratio and smooth power transmission.
                    
                    Key Principles:
                    • Speed ratio equals inverse of teeth ratio
                    • Torque ratio equals teeth ratio (neglecting losses)
                    • Contact ratio affects load sharing and smoothness
                    • Efficiency depends on geometry and lubrication''',
                }
            },
            
            {
                'id': 'spring_system',
                'name': 'Spring-Mass System',
                'category': 'Elastic Elements',
                'description': 'Dynamic system demonstrating spring behavior, natural frequency, and harmonic motion.',
                'complexity_level': 2,
                'key_concepts': ['Spring Constant', 'Natural Frequency', 'Damping', 'Resonance'],
                'parameters': {
                    'Spring Properties': {
                        'Spring Constant': {'default': 50.0, 'min': 10.0, 'max': 200.0, 'type': 'stiffness', 'category': 'Properties'},
                        'Free Length': {'default': 120.0, 'min': 60.0, 'max': 200.0, 'type': 'length', 'category': 'Geometry'},
                        'Damping Coefficient': {'default': 5.0, 'min': 0.0, 'max': 20.0, 'type': 'damping', 'category': 'Properties'},
                    },
                    'Loading': {
                        'Applied Force': {'default': 100.0, 'min': 0.0, 'max': 500.0, 'type': 'force', 'category': 'Loading'},
                        'Mass': {'default': 2.0, 'min': 0.5, 'max': 10.0, 'type': 'mass', 'category': 'Properties'},
                    }
                },
                'educational_content': {
                    'theory': '''Spring systems demonstrate fundamental principles of elasticity and vibration.
                    The spring force is proportional to displacement (Hooke's Law).
                    
                    Key Principles:
                    • Natural frequency depends on spring constant and mass
                    • Damping affects system response and stability
                    • Resonance occurs when forcing frequency matches natural frequency
                    • Energy storage and release in elastic deformation''',
                }
            }
        ]
        
        # Create catalog entries and list items
        for mech_data in mechanisms:
            entry = MechanismCatalogEntry(
                id=mech_data['id'],
                name=mech_data['name'],
                category=mech_data['category'],
                description=mech_data['description'],
                complexity_level=mech_data['complexity_level'],
                key_concepts=mech_data['key_concepts'],
                parameters=mech_data['parameters'],
                educational_content=mech_data['educational_content']
            )
            
            self.catalog_entries[entry.id] = entry
            
            # Create list item with professional styling
            item = QListWidgetItem()
            item.setText(entry.name)
            item.setData(Qt.ItemDataRole.UserRole, entry.id)
            
            # Create professional thumbnail
            thumbnail = self.create_mechanism_thumbnail(entry)
            item.setIcon(QIcon(thumbnail))
            
            # Add complexity and category info to tooltip
            tooltip = f"{entry.name}\nCategory: {entry.category}\nComplexity: {'⭐' * entry.complexity_level}\n\n{entry.description}"
            item.setToolTip(tooltip)
            
            self.addItem(item)
            
    def create_mechanism_thumbnail(self, entry: MechanismCatalogEntry) -> QPixmap:
        """Create professional mechanism thumbnail"""
        pixmap = QPixmap(120, 90)
        pixmap.fill(Qt.GlobalColor.white)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw simplified mechanism representation based on type
        if 'linkage' in entry.id.lower():
            self.draw_linkage_thumbnail(painter, pixmap.rect())
        elif 'cam' in entry.id.lower():
            self.draw_cam_thumbnail(painter, pixmap.rect())
        elif 'gear' in entry.id.lower():
            self.draw_gear_thumbnail(painter, pixmap.rect())
        elif 'spring' in entry.id.lower():
            self.draw_spring_thumbnail(painter, pixmap.rect())
        else:
            self.draw_generic_thumbnail(painter, pixmap.rect())
            
        # Add category badge
        painter.fillRect(5, 5, 60, 20, Qt.GlobalColor.blue)
        painter.setPen(Qt.GlobalColor.white)
        painter.setFont(QFont("Arial", 8, QFont.Weight.Bold))
        painter.drawText(7, 18, entry.category)
        
        painter.end()
        return pixmap
        
    def draw_linkage_thumbnail(self, painter: QPainter, rect):
        """Draw four-bar linkage thumbnail"""
        # Simplified four-bar representation
        painter.setPen(Qt.GlobalColor.blue)
        painter.setBrush(Qt.GlobalColor.lightGray)
        
        # Joint positions
        joints = [(20, 60), (100, 60), (80, 30), (40, 35)]
        
        # Draw links
        for i in range(4):
            j1, j2 = joints[i], joints[(i+1) % 4]
            painter.drawLine(j1[0], j1[1], j2[0], j2[1])
            
        # Draw joints
        for x, y in joints:
            painter.drawEllipse(x-4, y-4, 8, 8)
            
    def draw_cam_thumbnail(self, painter: QPainter, rect):
        """Draw cam mechanism thumbnail"""
        # Cam profile
        painter.setPen(Qt.GlobalColor.red)
        painter.setBrush(Qt.GlobalColor.lightGray)
        
        center_x, center_y = 40, 45
        painter.drawEllipse(center_x-20, center_y-20, 40, 40)
        
        # Follower
        painter.drawRect(70, 35, 15, 20)
        painter.drawLine(85, 45, 100, 45)
        
    def draw_gear_thumbnail(self, painter: QPainter, rect):
        """Draw gear system thumbnail"""
        # Two meshing gears
        painter.setPen(Qt.GlobalColor.darkGreen)
        painter.setBrush(Qt.GlobalColor.lightGray)
        
        # Gear 1
        painter.drawEllipse(15, 30, 30, 30)
        # Gear 2  
        painter.drawEllipse(40, 30, 40, 40)
        
        # Simplified teeth
        for angle in range(0, 360, 30):
            x1 = 30 + 18 * math.cos(math.radians(angle))
            y1 = 45 + 18 * math.sin(math.radians(angle))
            painter.drawLine(30, 45, x1, y1)
            
    def draw_spring_thumbnail(self, painter: QPainter, rect):
        """Draw spring system thumbnail"""
        painter.setPen(Qt.GlobalColor.darkBlue)
        
        # Spring coils
        x, y = 40, 20
        for i in range(8):
            y_pos = y + i * 8
            painter.drawLine(x-10, y_pos, x+10, y_pos+4)
            painter.drawLine(x+10, y_pos+4, x-10, y_pos+8)
            
        # Mass
        painter.fillRect(30, 75, 20, 10, Qt.GlobalColor.gray)
        
    def draw_generic_thumbnail(self, painter: QPainter, rect):
        """Draw generic mechanism thumbnail"""
        painter.setPen(Qt.GlobalColor.gray)
        painter.drawEllipse(30, 30, 30, 30)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Mech")
        
    def on_item_clicked(self, item: QListWidgetItem):
        """Handle mechanism selection"""
        entry_id = item.data(Qt.ItemDataRole.UserRole)
        entry = self.catalog_entries[entry_id]
        
        # Convert to mechanism data format
        mechanism_data = {
            'id': entry.id,
            'name': entry.name,
            'category': entry.category,
            'description': entry.description,
            'parameters': entry.parameters,
            'educational_content': entry.educational_content
        }
        
        self.mechanismSelected.emit(mechanism_data)


class EducationalContentPanel(QTabWidget):
    """Professional educational content panel"""
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        # Setup tabs
        self.theory_tab = QTextEdit()
        self.applications_tab = QTextEdit()
        self.design_tips_tab = QTextEdit()
        
        self.addTab(self.theory_tab, "📚 Theory")
        self.addTab(self.applications_tab, "🏭 Applications")  
        self.addTab(self.design_tips_tab, "💡 Design Tips")
        
        # Professional styling
        self.setStyleSheet("""
            QTabWidget::pane {
                border: 2px solid #dee2e6;
                border-radius: 8px;
                background-color: white;
            }
            QTabBar::tab {
                background-color: #f8f9fa;
                border: 2px solid #dee2e6;
                border-bottom: none;
                border-radius: 4px 4px 0 0;
                padding: 8px 16px;
                margin-right: 2px;
                font-weight: 500;
            }
            QTabBar::tab:selected {
                background-color: white;
                border-color: #0d6efd;
                color: #0d6efd;
            }
            QTextEdit {
                border: none;
                padding: 16px;
                font-size: 11px;
                line-height: 1.4;
            }
        """)
        
        for text_edit in [self.theory_tab, self.applications_tab, self.design_tips_tab]:
            text_edit.setReadOnly(True)
            
    def set_educational_content(self, content: Dict[str, str]):
        """Set educational content for the mechanism"""
        self.theory_tab.setHtml(self.format_content(content.get('theory', 'No theory content available.')))
        self.applications_tab.setHtml(self.format_content(content.get('applications', 'No applications content available.')))
        self.design_tips_tab.setHtml(self.format_content(content.get('design_tips', 'No design tips available.')))
        
    def format_content(self, content: str) -> str:
        """Format content with professional HTML styling"""
        return f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
                    color: #495057; line-height: 1.6;">
            {content.replace('\n', '<br>')}
        </div>
        """


class EnhancedMechanismDictionaryTab(MacanismStyleTab):
    """
    Enhanced Mechanism Dictionary Tab with macanism-level visualization.
    
    Features:
    - Professional mechanism catalog with live previews
    - Interactive exploration with real-time parameter adjustment
    - Comprehensive educational content integration
    - High-fidelity physics simulation
    - Export capabilities for mechanism configurations
    """
    
    def __init__(self, parent: Optional[QWidget] = None):
        # Configure for dictionary/catalog use case
        config = MacanismConfig(
            enable_professional_grid=True,
            show_force_vectors=True,
            show_motion_trails=True,
            enable_parametric_controls=True,
            target_fps=60
        )
        
        super().__init__(config, parent)
        
        # Dictionary-specific components
        self.catalog_widget: Optional[MechanismCatalogWidget] = None
        self.educational_panel: Optional[EducationalContentPanel] = None
        self.current_mechanism: Optional[Dict] = None
        
    def setup_mechanism_specific_components(self):
        """Setup dictionary-specific components"""
        # Create mechanism catalog
        self.catalog_widget = MechanismCatalogWidget()
        self.catalog_widget.mechanismSelected.connect(self.set_mechanism)
        
        # Create educational content panel
        self.educational_panel = EducationalContentPanel()
        
        # Modify layout to include catalog and educational content
        self.create_dictionary_layout()
        
    def create_dictionary_layout(self):
        """Create the dictionary-specific layout"""
        # Replace the standard layout with dictionary layout
        main_layout = self.layout()
        if main_layout:
            # Clear existing layout
            while main_layout.count():
                item = main_layout.takeAt(0)
                if item.widget():
                    item.widget().setParent(None)
                    
        # Create three-panel layout
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.setChildrenCollapsible(False)
        
        # Left panel: Mechanism catalog
        catalog_frame = QFrame()
        catalog_layout = QVBoxLayout(catalog_frame)
        catalog_layout.setContentsMargins(8, 8, 8, 8)
        
        catalog_title = QLabel("🔧 Mechanism Catalog")
        catalog_title.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #0d6efd;
                padding: 8px;
                border-bottom: 2px solid #dee2e6;
                margin-bottom: 8px;
            }
        """)
        
        catalog_layout.addWidget(catalog_title)
        catalog_layout.addWidget(self.catalog_widget)
        
        # Center panel: Interactive visualization
        visualization_widget = self.create_visualization_widget()
        
        # Right panel: Educational content and parameters
        right_panel = QSplitter(Qt.Orientation.Vertical)
        
        # Parameters at top
        if self.parametric_controls:
            right_panel.addWidget(self.parametric_controls)
            
        # Educational content at bottom
        if self.educational_panel:
            right_panel.addWidget(self.educational_panel)
            
        right_panel.setSizes([300, 400])  # Give more space to educational content
        
        # Add panels to main splitter
        main_splitter.addWidget(catalog_frame)
        main_splitter.addWidget(visualization_widget)
        main_splitter.addWidget(right_panel)
        
        # Set splitter sizes (catalog: 300px, visualization: rest, right panel: 400px)
        main_splitter.setSizes([300, 600, 400])
        
        # Set as main layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(main_splitter)
        
    def on_mechanism_changed(self, mechanism_data: Dict[str, Any]):
        """Handle mechanism selection from catalog"""
        self.current_mechanism = mechanism_data
        
        # Update educational content
        if self.educational_panel and 'educational_content' in mechanism_data:
            self.educational_panel.set_educational_content(mechanism_data['educational_content'])
            
        # Start simulation for live preview
        self.start_simulation()
        
    def handle_parameter_change(self, param_name: str, value: float):
        """Handle parameter changes specific to dictionary use"""
        # Dictionary tab shows immediate visual feedback
        # No special handling needed - base class handles visualization updates
        pass
        
    def handle_configuration_change(self, config: Dict[str, float]):
        """Handle configuration changes for educational exploration"""
        # Could add configuration history for educational comparison
        pass
        
    def handle_component_grabbed(self, component_id: str, position):
        """Handle component interaction for educational exploration"""
        # Dictionary tab allows exploration but with educational context
        pass
        
    def handle_component_dragged(self, component_id: str, position, physics_data: Dict):
        """Handle drag events with educational feedback"""
        # Could show real-time physics data in educational panel
        pass
        
    def handle_component_released(self, component_id: str, position):
        """Handle release events"""
        # Could capture interesting configurations for educational purposes
        pass
        
    def export_mechanism_data(self) -> Dict[str, Any]:
        """Export current mechanism configuration"""
        if not self.current_mechanism:
            return {}
            
        return {
            'mechanism': self.current_mechanism,
            'parameters': self.get_current_parameters(),
            'educational_notes': 'Exported from Mechanism Dictionary',
            'timestamp': time.time()
        }