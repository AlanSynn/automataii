"""
Visualization overlay for motion analysis results.
Renders analysis data directly on the graphics scene with interactive controls.
"""

import logging
import math
from typing import Dict, List, Any, Optional
from PyQt6.QtCore import Qt, pyqtSignal, QPointF, QRectF
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QPolygonF
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QSlider, QGroupBox, QTabWidget, QTextEdit,
    QComboBox, QProgressBar, QGraphicsItem, QGraphicsTextItem,
    QGraphicsLineItem, QGraphicsEllipseItem, QGraphicsPolygonItem
)

from .motion_analysis import MotionAnalysisManager, AnalysisResult
from .styling import ModernStyling

logger = logging.getLogger(__name__)


class AnalysisVisualizationOverlay(QGraphicsItem):
    """Graphics overlay for displaying motion analysis results."""
    
    def __init__(self, analysis_manager: MotionAnalysisManager):
        super().__init__()
        self.analysis_manager = analysis_manager
        self.analysis_results: Dict[str, AnalysisResult] = {}
        self.visible_layers = {"velocity": True, "acceleration": True, "trajectory": True}
        
        # Visual properties
        self.velocity_color = QColor(ModernStyling.COLORS['info'])
        self.acceleration_color = QColor(ModernStyling.COLORS['warning'])
        self.trajectory_color = QColor(ModernStyling.COLORS['success'])
        self.curvature_color = QColor(ModernStyling.COLORS['error'])
        
        # Connect to analysis updates
        self.analysis_manager.analysis_updated.connect(self.update_analysis_results)
        
        self.setZValue(100)  # Render on top of mechanism
    
    def boundingRect(self) -> QRectF:
        """Return bounding rectangle for the overlay."""
        return QRectF(-1000, -1000, 2000, 2000)  # Large area to cover entire scene
    
    def paint(self, painter: QPainter, option, widget):
        """Paint the analysis visualization overlay."""
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw each analysis layer
        if self.visible_layers.get("velocity", False):
            self._draw_velocity_vectors(painter)
        
        if self.visible_layers.get("acceleration", False):
            self._draw_acceleration_vectors(painter)
        
        if self.visible_layers.get("trajectory", False):
            self._draw_trajectory_analysis(painter)
    
    def _draw_velocity_vectors(self, painter: QPainter):
        """Draw velocity vectors."""
        if "velocity" not in self.analysis_results:
            return
        
        result = self.analysis_results["velocity"]
        
        # Set up pen for velocity vectors
        pen = QPen(self.velocity_color, 2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        
        # Draw vectors
        for element in result.visualization_elements:
            if element["type"] == "velocity_vector":
                pos = element["position"]
                vel = element["velocity"]
                scale = element["scale"]
                
                # Calculate vector end point
                end_x = pos.x() + vel.x() * scale
                end_y = pos.y() + vel.y() * scale
                
                # Draw vector line
                painter.drawLine(pos, QPointF(end_x, end_y))
                
                # Draw arrowhead
                self._draw_arrowhead(painter, pos, QPointF(end_x, end_y), 8)
    
    def _draw_acceleration_vectors(self, painter: QPainter):
        """Draw acceleration vectors."""
        if "acceleration" not in self.analysis_results:
            return
        
        result = self.analysis_results["acceleration"]
        
        for element in result.visualization_elements:
            if element["type"] == "acceleration_vector":
                pos = element["position"]
                accel = element["acceleration"]
                scale = element["scale"]
                is_peak = element.get("is_peak", False)
                
                # Use different colors for peaks
                color = QColor(ModernStyling.COLORS['error']) if is_peak else self.acceleration_color
                pen = QPen(color, 3 if is_peak else 2)
                painter.setPen(pen)
                
                # Calculate vector end point
                end_x = pos.x() + accel.x() * scale
                end_y = pos.y() + accel.y() * scale
                
                # Draw vector
                painter.drawLine(pos, QPointF(end_x, end_y))
                self._draw_arrowhead(painter, pos, QPointF(end_x, end_y), 6)
                
                # Draw peak indicator
                if is_peak:
                    painter.setBrush(QBrush(color))
                    painter.drawEllipse(pos, 4, 4)
    
    def _draw_trajectory_analysis(self, painter: QPainter):
        """Draw trajectory analysis visualization."""
        if "trajectory" not in self.analysis_results:
            return
        
        result = self.analysis_results["trajectory"]
        
        for element in result.visualization_elements:
            if element["type"] == "trajectory_path":
                self._draw_trajectory_path(painter, element["points"], element.get("curvatures", []))
            
            elif element["type"] == "curvature_indicator":
                self._draw_curvature_indicator(painter, element["position"], element["curvature"])
    
    def _draw_trajectory_path(self, painter: QPainter, points: List[QPointF], curvatures: List[float]):
        """Draw trajectory path with curvature heat map."""
        if len(points) < 2:
            return
        
        # Draw path segments with curvature-based coloring
        for i in range(len(points) - 1):
            # Calculate color based on curvature
            if i < len(curvatures):
                curvature = curvatures[i]
                # Normalize curvature to 0-1 range for color mapping
                normalized_curvature = min(1.0, curvature * 10)  # Scale factor
                
                # Interpolate between green (low curvature) and red (high curvature)
                red = int(255 * normalized_curvature)
                green = int(255 * (1 - normalized_curvature))
                color = QColor(red, green, 0)
            else:
                color = self.trajectory_color
            
            pen = QPen(color, 3)
            painter.setPen(pen)
            painter.drawLine(points[i], points[i + 1])
    
    def _draw_curvature_indicator(self, painter: QPainter, position: QPointF, curvature: float):
        """Draw curvature indicator at a point."""
        # Size based on curvature magnitude
        size = max(3, min(15, curvature * 100))
        
        # Color intensity based on curvature
        intensity = min(255, int(curvature * 1000))
        color = QColor(intensity, 255 - intensity, 0, 150)  # Semi-transparent
        
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(color.darker(), 1))
        painter.drawEllipse(position, size, size)
    
    def _draw_arrowhead(self, painter: QPainter, start: QPointF, end: QPointF, size: float):
        """Draw an arrowhead at the end of a vector."""
        if start == end:
            return
        
        # Calculate arrow direction
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        length = math.sqrt(dx*dx + dy*dy)
        
        if length == 0:
            return
        
        # Normalize direction
        dx /= length
        dy /= length
        
        # Calculate arrowhead points
        arrow_length = size
        arrow_width = size * 0.6
        
        # Arrowhead vertices
        tip = end
        base1 = QPointF(end.x() - arrow_length * dx - arrow_width * dy,
                       end.y() - arrow_length * dy + arrow_width * dx)
        base2 = QPointF(end.x() - arrow_length * dx + arrow_width * dy,
                       end.y() - arrow_length * dy - arrow_width * dx)
        
        # Draw filled arrowhead
        arrow_polygon = QPolygonF([tip, base1, base2])
        painter.setBrush(QBrush(painter.pen().color()))
        painter.drawPolygon(arrow_polygon)
    
    def update_analysis_results(self, results: Dict[str, AnalysisResult]):
        """Update analysis results and trigger redraw."""
        self.analysis_results = results
        self.update()  # Trigger repaint
    
    def set_layer_visibility(self, layer_name: str, visible: bool):
        """Set visibility of an analysis layer."""
        self.visible_layers[layer_name] = visible
        self.update()
    
    def get_layer_visibility(self, layer_name: str) -> bool:
        """Get visibility of an analysis layer."""
        return self.visible_layers.get(layer_name, False)


class AnalysisControlPanel(QWidget):
    """Control panel for motion analysis settings and results."""
    
    layer_visibility_changed = pyqtSignal(str, bool)  # layer_name, visible
    strategy_parameter_changed = pyqtSignal(str, str, object)  # strategy, parameter, value
    export_requested = pyqtSignal()
    
    def __init__(self, analysis_manager: MotionAnalysisManager, parent=None):
        super().__init__(parent)
        self.analysis_manager = analysis_manager
        self._setup_ui()
        self._connect_signals()
        
        # Connect to analysis updates
        self.analysis_manager.analysis_updated.connect(self._update_results_display)
    
    def _setup_ui(self):
        """Setup the control panel UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        # Header
        header = QLabel("Motion Analysis")
        header.setFont(QFont(ModernStyling.TYPOGRAPHY['font_family'], 
                           ModernStyling.TYPOGRAPHY['font_size_h3'], QFont.Weight.Bold))
        header.setStyleSheet(f"color: {ModernStyling.COLORS['primary']}; margin-bottom: 8px;")
        layout.addWidget(header)
        
        # Visualization controls
        viz_group = QGroupBox("Visualization Layers")
        viz_layout = QVBoxLayout(viz_group)
        
        self.velocity_checkbox = QCheckBox("Velocity Vectors")
        self.velocity_checkbox.setChecked(True)
        viz_layout.addWidget(self.velocity_checkbox)
        
        self.acceleration_checkbox = QCheckBox("Acceleration Vectors")
        self.acceleration_checkbox.setChecked(True)
        viz_layout.addWidget(self.acceleration_checkbox)
        
        self.trajectory_checkbox = QCheckBox("Trajectory Analysis")
        self.trajectory_checkbox.setChecked(True)
        viz_layout.addWidget(self.trajectory_checkbox)
        
        layout.addWidget(viz_group)
        
        # Analysis strategy tabs
        self.strategy_tabs = QTabWidget()
        self.strategy_tabs.setStyleSheet(ModernStyling.get_tab_style())
        
        # Create tabs for each strategy
        self._create_velocity_tab()
        self._create_acceleration_tab()
        self._create_trajectory_tab()
        
        layout.addWidget(self.strategy_tabs)
        
        # Results display
        results_group = QGroupBox("Analysis Results")
        results_layout = QVBoxLayout(results_group)
        
        self.results_text = QTextEdit()
        self.results_text.setMaximumHeight(120)
        self.results_text.setReadOnly(True)
        self.results_text.setStyleSheet(ModernStyling.get_input_style())
        results_layout.addWidget(self.results_text)
        
        layout.addWidget(results_group)
        
        # Export button
        self.export_button = QPushButton("Export Analysis Data")
        self.export_button.setStyleSheet(ModernStyling.get_button_style("secondary"))
        layout.addWidget(self.export_button)
        
        layout.addStretch()
    
    def _create_velocity_tab(self):
        """Create velocity analysis controls tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Vector scale
        scale_layout = QHBoxLayout()
        scale_layout.addWidget(QLabel("Vector Scale:"))
        self.velocity_scale_slider = QSlider(Qt.Orientation.Horizontal)
        self.velocity_scale_slider.setRange(1, 50)
        self.velocity_scale_slider.setValue(10)
        scale_layout.addWidget(self.velocity_scale_slider)
        self.velocity_scale_label = QLabel("10")
        scale_layout.addWidget(self.velocity_scale_label)
        layout.addLayout(scale_layout)
        
        # Threshold
        threshold_layout = QHBoxLayout()
        threshold_layout.addWidget(QLabel("Min Threshold:"))
        self.velocity_threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.velocity_threshold_slider.setRange(1, 100)
        self.velocity_threshold_slider.setValue(10)
        threshold_layout.addWidget(self.velocity_threshold_slider)
        self.velocity_threshold_label = QLabel("0.1")
        threshold_layout.addWidget(self.velocity_threshold_label)
        layout.addLayout(threshold_layout)
        
        # Options
        self.velocity_instantaneous = QCheckBox("Show Instantaneous")
        self.velocity_instantaneous.setChecked(True)
        layout.addWidget(self.velocity_instantaneous)
        
        self.velocity_average = QCheckBox("Show Average")
        layout.addWidget(self.velocity_average)
        
        layout.addStretch()
        
        self.strategy_tabs.addTab(tab, "Velocity")
    
    def _create_acceleration_tab(self):
        """Create acceleration analysis controls tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Vector scale
        scale_layout = QHBoxLayout()
        scale_layout.addWidget(QLabel("Vector Scale:"))
        self.accel_scale_slider = QSlider(Qt.Orientation.Horizontal)
        self.accel_scale_slider.setRange(1, 20)
        self.accel_scale_slider.setValue(5)
        scale_layout.addWidget(self.accel_scale_slider)
        self.accel_scale_label = QLabel("5")
        scale_layout.addWidget(self.accel_scale_label)
        layout.addLayout(scale_layout)
        
        # Smoothing
        smoothing_layout = QHBoxLayout()
        smoothing_layout.addWidget(QLabel("Smoothing:"))
        self.accel_smoothing_slider = QSlider(Qt.Orientation.Horizontal)
        self.accel_smoothing_slider.setRange(1, 10)
        self.accel_smoothing_slider.setValue(5)
        smoothing_layout.addWidget(self.accel_smoothing_slider)
        self.accel_smoothing_label = QLabel("5")
        smoothing_layout.addWidget(self.accel_smoothing_label)
        layout.addLayout(smoothing_layout)
        
        # Options
        self.accel_highlight_peaks = QCheckBox("Highlight Peaks")
        self.accel_highlight_peaks.setChecked(True)
        layout.addWidget(self.accel_highlight_peaks)
        
        layout.addStretch()
        
        self.strategy_tabs.addTab(tab, "Acceleration")
    
    def _create_trajectory_tab(self):
        """Create trajectory analysis controls tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Smoothness weight
        smoothness_layout = QHBoxLayout()
        smoothness_layout.addWidget(QLabel("Smoothness Weight:"))
        self.traj_smoothness_slider = QSlider(Qt.Orientation.Horizontal)
        self.traj_smoothness_slider.setRange(0, 100)
        self.traj_smoothness_slider.setValue(50)
        smoothness_layout.addWidget(self.traj_smoothness_slider)
        self.traj_smoothness_label = QLabel("0.5")
        smoothness_layout.addWidget(self.traj_smoothness_label)
        layout.addLayout(smoothness_layout)
        
        # Options
        self.traj_curvature_analysis = QCheckBox("Curvature Analysis")
        self.traj_curvature_analysis.setChecked(True)
        layout.addWidget(self.traj_curvature_analysis)
        
        self.traj_optimization = QCheckBox("Enable Optimization")
        layout.addWidget(self.traj_optimization)
        
        # Optimization button
        self.optimize_button = QPushButton("Optimize Path")
        self.optimize_button.setStyleSheet(ModernStyling.get_button_style("primary"))
        self.optimize_button.setEnabled(False)
        layout.addWidget(self.optimize_button)
        
        layout.addStretch()
        
        self.strategy_tabs.addTab(tab, "Trajectory")
    
    def _connect_signals(self):
        """Connect UI signals."""
        # Visualization layer checkboxes
        self.velocity_checkbox.toggled.connect(
            lambda checked: self.layer_visibility_changed.emit("velocity", checked))
        self.acceleration_checkbox.toggled.connect(
            lambda checked: self.layer_visibility_changed.emit("acceleration", checked))
        self.trajectory_checkbox.toggled.connect(
            lambda checked: self.layer_visibility_changed.emit("trajectory", checked))
        
        # Velocity controls
        self.velocity_scale_slider.valueChanged.connect(self._on_velocity_scale_changed)
        self.velocity_threshold_slider.valueChanged.connect(self._on_velocity_threshold_changed)
        self.velocity_instantaneous.toggled.connect(
            lambda checked: self.strategy_parameter_changed.emit("velocity", "show_instantaneous", checked))
        self.velocity_average.toggled.connect(
            lambda checked: self.strategy_parameter_changed.emit("velocity", "show_average", checked))
        
        # Acceleration controls
        self.accel_scale_slider.valueChanged.connect(self._on_accel_scale_changed)
        self.accel_smoothing_slider.valueChanged.connect(self._on_accel_smoothing_changed)
        self.accel_highlight_peaks.toggled.connect(
            lambda checked: self.strategy_parameter_changed.emit("acceleration", "highlight_peaks", checked))
        
        # Trajectory controls
        self.traj_smoothness_slider.valueChanged.connect(self._on_traj_smoothness_changed)
        self.traj_curvature_analysis.toggled.connect(
            lambda checked: self.strategy_parameter_changed.emit("trajectory", "curvature_analysis", checked))
        self.traj_optimization.toggled.connect(self._on_optimization_toggled)
        
        # Export button
        self.export_button.clicked.connect(self.export_requested.emit)
    
    def _on_velocity_scale_changed(self, value: int):
        """Handle velocity scale changes."""
        scale = float(value)
        self.velocity_scale_label.setText(str(value))
        self.strategy_parameter_changed.emit("velocity", "vector_scale", scale)
    
    def _on_velocity_threshold_changed(self, value: int):
        """Handle velocity threshold changes."""
        threshold = value / 100.0
        self.velocity_threshold_label.setText(f"{threshold:.2f}")
        self.strategy_parameter_changed.emit("velocity", "min_velocity_threshold", threshold)
    
    def _on_accel_scale_changed(self, value: int):
        """Handle acceleration scale changes."""
        scale = float(value)
        self.accel_scale_label.setText(str(value))
        self.strategy_parameter_changed.emit("acceleration", "vector_scale", scale)
    
    def _on_accel_smoothing_changed(self, value: int):
        """Handle acceleration smoothing changes."""
        self.accel_smoothing_label.setText(str(value))
        self.strategy_parameter_changed.emit("acceleration", "smoothing_window", value)
    
    def _on_traj_smoothness_changed(self, value: int):
        """Handle trajectory smoothness changes."""
        smoothness = value / 100.0
        self.traj_smoothness_label.setText(f"{smoothness:.2f}")
        self.strategy_parameter_changed.emit("trajectory", "path_smoothness_weight", smoothness)
    
    def _on_optimization_toggled(self, checked: bool):
        """Handle optimization toggle."""
        self.optimize_button.setEnabled(checked)
        self.strategy_parameter_changed.emit("trajectory", "optimization_enabled", checked)
    
    def _update_results_display(self, results: Dict[str, Any]):
        """Update the results text display."""
        text_parts = []
        
        for strategy_name, result in results.items():
            text_parts.append(f"**{strategy_name.title()} Analysis:**")
            
            # Display statistics
            for stat_name, stat_value in result.statistics.items():
                if isinstance(stat_value, float):
                    text_parts.append(f"  {stat_name}: {stat_value:.3f}")
                else:
                    text_parts.append(f"  {stat_name}: {stat_value}")
            
            # Display recommendations
            if result.recommendations:
                text_parts.append("  Recommendations:")
                for rec in result.recommendations:
                    text_parts.append(f"    • {rec}")
            
            text_parts.append("")  # Empty line
        
        self.results_text.setPlainText("\n".join(text_parts))