"""
Analysis Panel - Data-driven investigation and kinematic analysis

Provides scientific investigation tools for mechanism analysis:
- Synchronized mechanism visualization
- Real-time kinematic plotting (position, velocity, acceleration)
- Analysis controls for different study modes
- Data export capabilities
- Multiple analysis points selection
"""

from typing import Optional, Dict
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QFrame, QPushButton, QComboBox, QGroupBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor


class KinematicPlotView(QFrame):
    """Kinematic data plotting widget"""
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.mechanism_data = None
        self.plot_data = []
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the plotting widget"""
        self.setMinimumSize(400, 300)
        self.setStyleSheet("""
            QFrame {
                border: 1px solid #dee2e6;
                border-radius: 8px;
                background-color: white;
            }
        """)
        
    def set_mechanism(self, mechanism_data: Dict):
        """Set the mechanism for analysis"""
        self.mechanism_data = mechanism_data
        self.update()
        
    def update_plot_data(self, data: dict):
        """Update plot with new kinematic data"""
        self.plot_data.append(data)
        # Keep only last 100 data points
        if len(self.plot_data) > 100:
            self.plot_data = self.plot_data[-100:]
        self.update()
        
    def paintEvent(self, event):
        """Draw the kinematic plots"""
        super().paintEvent(event)
        
        painter = QPainter(self)
        painter.setPen(QPen(QColor('#6c757d'), 1))
        
        if not self.mechanism_data:
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, 
                           "Kinematic analysis plots\nwill appear here")
        else:
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, 
                           f"Analysis for: {self.mechanism_data.get('name', 'Unknown')}\n"
                           f"Data points: {len(self.plot_data)}")


class AnalysisMechanismView(QFrame):
    """Synchronized mechanism visualization for analysis"""
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.mechanism_data = None
        self.analysis_points = []
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the analysis visualization"""
        self.setMinimumSize(400, 300)
        self.setStyleSheet("""
            QFrame {
                border: 1px solid #dee2e6;
                border-radius: 8px;
                background-color: #fafbfc;
            }
        """)
        
    def set_mechanism(self, mechanism_data: Dict):
        """Set the mechanism to analyze"""
        self.mechanism_data = mechanism_data
        self.update()
        
    def add_analysis_point(self, x: float, y: float):
        """Add a point for kinematic analysis"""
        self.analysis_points.append((x, y))
        self.update()
        
    def clear_analysis_points(self):
        """Clear all analysis points"""
        self.analysis_points.clear()
        self.update()
        
    def paintEvent(self, event):
        """Draw the mechanism with analysis points"""
        super().paintEvent(event)
        
        painter = QPainter(self)
        painter.setPen(QPen(QColor('#6c757d'), 1))
        
        if not self.mechanism_data:
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, 
                           "Mechanism visualization\nfor analysis will appear here")
        else:
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, 
                           f"Analyzing: {self.mechanism_data.get('name', 'Unknown')}\n"
                           f"Analysis points: {len(self.analysis_points)}")
            
            # Draw analysis points
            painter.setPen(QPen(QColor('#dc3545'), 2))
            for i, (x, y) in enumerate(self.analysis_points):
                painter.drawEllipse(int(x - 3), int(y - 3), 6, 6)
                painter.drawText(int(x + 5), int(y - 5), str(i + 1))


class AnalysisControls(QGroupBox):
    """Controls for analysis options"""
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__("Analysis Controls", parent)
        self.setup_ui()
        
    def setup_ui(self):
        """Setup analysis controls"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 16, 12, 12)
        
        # Analysis type selector
        type_label = QLabel("Analysis Type:")
        type_label.setStyleSheet("font-weight: bold; margin-bottom: 4px;")
        
        self.analysis_type = QComboBox()
        self.analysis_type.addItems([
            "Position Analysis",
            "Velocity Analysis", 
            "Acceleration Analysis",
            "Force Analysis",
            "Complete Kinematic Analysis"
        ])
        
        # Plot type selector
        plot_label = QLabel("Plot Type:")
        plot_label.setStyleSheet("font-weight: bold; margin-bottom: 4px; margin-top: 8px;")
        
        self.plot_type = QComboBox()
        self.plot_type.addItems([
            "Position vs Time",
            "Velocity vs Time",
            "Acceleration vs Time", 
            "Position vs Position",
            "Phase Plot",
            "Frequency Analysis"
        ])
        
        # Control buttons
        self.start_analysis_btn = QPushButton("Start Analysis")
        self.start_analysis_btn.setStyleSheet("""
            QPushButton {
                background-color: #198754;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                margin-top: 8px;
            }
            QPushButton:hover {
                background-color: #157347;
            }
        """)
        
        self.export_data_btn = QPushButton("Export Data")
        self.export_data_btn.setStyleSheet("""
            QPushButton {
                background-color: #0d6efd;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0b5ed7;
            }
        """)
        
        self.clear_points_btn = QPushButton("Clear Points")
        self.clear_points_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
        """)
        
        layout.addWidget(type_label)
        layout.addWidget(self.analysis_type)
        layout.addWidget(plot_label)
        layout.addWidget(self.plot_type)
        layout.addWidget(self.start_analysis_btn)
        layout.addWidget(self.export_data_btn)
        layout.addWidget(self.clear_points_btn)
        layout.addStretch()


class AnalysisPanel(QWidget):
    """
    Analysis panel for data-driven mechanism investigation.
    
    Features:
    - Synchronized mechanism visualization
    - Real-time kinematic plotting
    - Multiple analysis modes and plot types
    - Analysis point selection and tracking
    - Data export capabilities
    """
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.mechanism_data = None
        self.setup_ui()
        self.connect_signals()
        
    def setup_ui(self):
        """Setup the analysis panel UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Create splitter for visualization and plots
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left side: Mechanism visualization and controls
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(16)
        
        # Mechanism visualization
        self.mechanism_view = AnalysisMechanismView()
        left_layout.addWidget(self.mechanism_view)
        
        # Analysis controls
        self.analysis_controls = AnalysisControls()
        left_layout.addWidget(self.analysis_controls)
        
        main_splitter.addWidget(left_panel)
        
        # Right side: Kinematic plots
        self.plot_view = KinematicPlotView()
        main_splitter.addWidget(self.plot_view)
        
        # Set initial splitter proportions (50% each)
        main_splitter.setSizes([500, 500])
        
        layout.addWidget(main_splitter)
        
    def connect_signals(self):
        """Connect UI signals"""
        self.analysis_controls.start_analysis_btn.clicked.connect(self.start_analysis)
        self.analysis_controls.export_data_btn.clicked.connect(self.export_data)
        self.analysis_controls.clear_points_btn.clicked.connect(self.clear_analysis_points)
        
    def set_mechanism(self, mechanism_data: Dict):
        """Set the mechanism for analysis"""
        self.mechanism_data = mechanism_data
        
        # Update both views
        self.mechanism_view.set_mechanism(mechanism_data)
        self.plot_view.set_mechanism(mechanism_data)
        
    def start_analysis(self):
        """Start kinematic analysis"""
        if not self.mechanism_data:
            return
            
        # TODO: Implement actual analysis
        # For now, just show that analysis started
        analysis_type = self.analysis_controls.analysis_type.currentText()
        print(f"Starting {analysis_type} for {self.mechanism_data.get('name', 'Unknown')}")
        
    def export_data(self):
        """Export analysis data"""
        # TODO: Implement data export functionality
        print("Exporting analysis data...")
        
    def clear_analysis_points(self):
        """Clear all analysis points"""
        self.mechanism_view.clear_analysis_points()
        
    def on_tab_activated(self):
        """Called when this tab becomes active"""
        # Refresh analysis if needed
        pass