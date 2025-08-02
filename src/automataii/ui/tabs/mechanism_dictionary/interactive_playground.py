"""
Interactive Playground for mechanism simulation and direct manipulation.
Advanced canvas with real-time interaction, parameter adjustment, and visualization.
"""

import logging
import math
from typing import Optional, Dict, Any, List, Tuple
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QPointF, QRectF
from PyQt6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QLinearGradient, 
    QRadialGradient, QPolygonF, QPainterPath, QPixmap
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QToolBar, QLabel, 
    QPushButton, QSlider, QFrame, QGraphicsView, QGraphicsScene,
    QGraphicsItem, QGraphicsEllipseItem, QGraphicsLineItem,
    QGraphicsTextItem, QSizePolicy, QTabWidget
)

from automataii.domain.fabrication.mechanisms.base_mechanism import BaseMechanism
from .state_manager import MechanismDictionaryStateManager
from .styling import ModernStyling
from .interaction_handlers import InteractionHandlerFactory, BaseMechanismInteractionHandler
from .motion_analysis import MotionAnalysisManager
from .analysis_visualization import AnalysisVisualizationOverlay, AnalysisControlPanel

logger = logging.getLogger(__name__)


class MechanismGraphicsItem(QGraphicsItem):
    """Custom graphics item for rendering mechanisms with interactive elements."""
    
    def __init__(self, mechanism: BaseMechanism):
        super().__init__()
        self.mechanism = mechanism
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        
        # Visual properties
        self.link_pen = QPen(QColor("#1976D2"), 3)
        self.point_brush = QBrush(QColor("#1976D2"))
        self.highlight_pen = QPen(QColor("#FF5722"), 4)
        self.path_pen = QPen(QColor("#4CAF50"), 2, Qt.PenStyle.DashLine)
        
        # Animation state
        self.animation_time = 0.0
        self.show_path_trace = True
        self.path_points: List[QPointF] = []
        
    def boundingRect(self) -> QRectF:
        """Return the bounding rectangle of the mechanism."""
        if not self.mechanism or not self.mechanism.points:
            return QRectF(0, 0, 400, 300)
        
        # Calculate bounds from mechanism points
        min_x = min(point.x for point in self.mechanism.points)
        max_x = max(point.x for point in self.mechanism.points)
        min_y = min(point.y for point in self.mechanism.points)
        max_y = max(point.y for point in self.mechanism.points)
        
        # Add padding
        padding = 50
        return QRectF(min_x - padding, min_y - padding, 
                     max_x - min_x + 2*padding, max_y - min_y + 2*padding)
    
    def paint(self, painter: QPainter, option, widget):
        """Paint the mechanism."""
        if not self.mechanism:
            return
        
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw path trace first (underneath mechanism)
        if self.show_path_trace and self.path_points:
            self._draw_path_trace(painter)
        
        # Draw mechanism links
        self._draw_links(painter)
        
        # Draw mechanism points
        self._draw_points(painter)
        
        # Draw additional visualizations
        self._draw_force_vectors(painter)
        self._draw_velocity_vectors(painter)
        
        # Draw info overlay
        self._draw_info_overlay(painter)
    
    def _draw_links(self, painter: QPainter):
        """Draw mechanism links."""
        painter.setPen(self.link_pen)
        
        for link in self.mechanism.links:
            start_point = link.point1
            end_point = link.point2
            
            painter.drawLine(
                QPointF(start_point.x, start_point.y),
                QPointF(end_point.x, end_point.y)
            )
    
    def _draw_points(self, painter: QPainter):
        """Draw mechanism points (joints, pivots)."""
        for point in self.mechanism.points:
            # Different visualization for fixed vs moving points
            if point.fixed:
                painter.setBrush(QBrush(QColor("#F44336")))  # Red for fixed
                painter.setPen(QPen(QColor("#D32F2F"), 2))
                radius = 6
            else:
                painter.setBrush(self.point_brush)
                painter.setPen(QPen(QColor("#0D47A1"), 2))
                radius = 4
            
            painter.drawEllipse(
                QPointF(point.x, point.y),
                radius, radius
            )
    
    def _draw_path_trace(self, painter: QPainter):
        """Draw motion path trace."""
        if len(self.path_points) < 2:
            return
        
        painter.setPen(self.path_pen)
        
        for i in range(len(self.path_points) - 1):
            painter.drawLine(self.path_points[i], self.path_points[i + 1])
        
        # Draw direction arrows
        if len(self.path_points) > 10:
            step = len(self.path_points) // 5  # Show 5 arrows
            for i in range(step, len(self.path_points), step):
                self._draw_arrow(painter, self.path_points[i-1], self.path_points[i])
    
    def _draw_arrow(self, painter: QPainter, start: QPointF, end: QPointF):
        """Draw a direction arrow."""
        # Calculate arrow direction
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        length = math.sqrt(dx*dx + dy*dy)
        
        if length < 1:
            return
        
        # Normalize and create arrow
        dx /= length
        dy /= length
        
        arrow_length = 8
        arrow_width = 3
        
        # Arrow tip
        tip_x = end.x()
        tip_y = end.y()
        
        # Arrow base points
        base1_x = tip_x - arrow_length * dx - arrow_width * dy
        base1_y = tip_y - arrow_length * dy + arrow_width * dx
        base2_x = tip_x - arrow_length * dx + arrow_width * dy
        base2_y = tip_y - arrow_length * dy - arrow_width * dx
        
        # Draw arrow
        arrow = QPolygonF([
            QPointF(tip_x, tip_y),
            QPointF(base1_x, base1_y),
            QPointF(base2_x, base2_y)
        ])
        
        painter.setBrush(QBrush(self.path_pen.color()))
        painter.drawPolygon(arrow)
    
    def _draw_force_vectors(self, painter: QPainter):
        """Draw force vectors (placeholder for advanced analysis)."""
        # This could show force analysis in the future
        pass
    
    def _draw_velocity_vectors(self, painter: QPainter):
        """Draw velocity vectors (placeholder for kinematic analysis)."""
        # This could show velocity analysis in the future
        pass
    
    def _draw_info_overlay(self, painter: QPainter):
        """Draw information overlay."""
        # Draw current mechanism state info
        info_rect = QRectF(10, 10, 200, 60)
        painter.fillRect(info_rect, QBrush(QColor(255, 255, 255, 200)))
        painter.setPen(QPen(QColor("#212121")))
        painter.setFont(QFont("Segoe UI", 9))
        
        y_offset = 25
        painter.drawText(15, y_offset, f"Type: {self.mechanism.get_mechanism_type()}")
        
        # Show current animation time
        painter.drawText(15, y_offset + 15, f"Time: {self.animation_time:.2f}s")
        
        # Show mechanism-specific info
        if hasattr(self.mechanism, 'get_gear_ratio'):
            ratio = self.mechanism.get_gear_ratio()
            painter.drawText(15, y_offset + 30, f"Ratio: {ratio:.2f}:1")
    
    def update_animation(self, time: float):
        """Update animation state."""
        self.animation_time = time
        
        # Update mechanism positions
        if hasattr(self.mechanism, '_update_positions'):
            self.mechanism._update_positions(time)
        
        # Record path trace for moving points (e.g., end effector)
        if self.mechanism.points and not self.mechanism.points[-1].fixed:
            last_point = self.mechanism.points[-1]
            self.path_points.append(QPointF(last_point.x, last_point.y))
            
            # Limit path length
            if len(self.path_points) > 200:
                self.path_points = self.path_points[-200:]
        
        self.update()
    
    def clear_path_trace(self):
        """Clear the motion path trace."""
        self.path_points.clear()
        self.update()
    
    def set_path_trace_visible(self, visible: bool):
        """Set path trace visibility."""
        self.show_path_trace = visible
        self.update()


class InteractiveToolbar(QFrame):
    """Toolbar for interactive controls."""
    
    path_trace_toggled = pyqtSignal(bool)
    animation_speed_changed = pyqtSignal(float)
    zoom_changed = pyqtSignal(float)
    reset_view_requested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_toolbar()
    
    def _setup_toolbar(self):
        """Setup toolbar controls."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(16)
        
        # View controls
        view_label = QLabel("View:")
        view_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        layout.addWidget(view_label)
        
        # Path trace toggle
        self.path_trace_btn = QPushButton("Path Trace")
        self.path_trace_btn.setCheckable(True)
        self.path_trace_btn.setChecked(True)
        self.path_trace_btn.clicked.connect(self.path_trace_toggled.emit)
        layout.addWidget(self.path_trace_btn)
        
        # Reset view
        reset_btn = QPushButton("Reset View")
        reset_btn.clicked.connect(self.reset_view_requested.emit)
        layout.addWidget(reset_btn)
        
        layout.addWidget(QLabel("|"))  # Separator
        
        # Animation controls
        anim_label = QLabel("Animation:")
        anim_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        layout.addWidget(anim_label)
        
        # Speed control
        layout.addWidget(QLabel("Speed:"))
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(1, 50)
        self.speed_slider.setValue(10)  # 1.0x speed
        self.speed_slider.setFixedWidth(100)
        self.speed_slider.valueChanged.connect(self._on_speed_changed)
        layout.addWidget(self.speed_slider)
        
        self.speed_label = QLabel("1.0x")
        self.speed_label.setFixedWidth(35)
        layout.addWidget(self.speed_label)
        
        layout.addWidget(QLabel("|"))  # Separator
        
        # Zoom controls
        zoom_label = QLabel("Zoom:")
        zoom_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        layout.addWidget(zoom_label)
        
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(25, 200)  # 0.25x to 2.0x
        self.zoom_slider.setValue(100)      # 1.0x zoom
        self.zoom_slider.setFixedWidth(100)
        self.zoom_slider.valueChanged.connect(self._on_zoom_changed)
        layout.addWidget(self.zoom_slider)
        
        self.zoom_label = QLabel("100%")
        self.zoom_label.setFixedWidth(40)
        layout.addWidget(self.zoom_label)
        
        layout.addStretch()
    
    def _on_speed_changed(self, value: int):
        """Handle speed slider changes."""
        speed = value / 10.0
        self.speed_label.setText(f"{speed:.1f}x")
        self.animation_speed_changed.emit(speed)
    
    def _on_zoom_changed(self, value: int):
        """Handle zoom slider changes."""
        zoom = value / 100.0
        self.zoom_label.setText(f"{value}%")
        self.zoom_changed.emit(zoom)


class InteractivePlayground(QWidget):
    """
    Interactive playground for mechanism simulation and exploration.
    
    Features:
    - Real-time mechanism animation
    - Interactive parameter adjustment
    - Motion path tracing
    - Multiple visualization modes
    - Direct manipulation interface
    """
    
    def __init__(self, state_manager: MechanismDictionaryStateManager, parent=None):
        super().__init__(parent)
        self.state_manager = state_manager
        self.current_mechanism: Optional[BaseMechanism] = None
        self.mechanism_item: Optional[MechanismGraphicsItem] = None
        self.interaction_handler: Optional[BaseMechanismInteractionHandler] = None
        
        # Motion analysis system
        self.motion_analysis_manager = MotionAnalysisManager()
        self.analysis_overlay: Optional[AnalysisVisualizationOverlay] = None
        self.analysis_control_panel: Optional[AnalysisControlPanel] = None
        
        # Animation and motion tracking
        self.animation_timer = QTimer()
        self.animation_time = 0.0
        self.animation_speed = 1.0
        self.is_animating = False
        self.previous_positions = {}  # For velocity/acceleration calculation
        
        self._setup_ui()
        self._connect_signals()
        
        logger.debug("InteractivePlayground initialized")
    
    def _setup_ui(self):
        """Setup the playground UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Interactive toolbar
        self.toolbar = InteractiveToolbar()
        layout.addWidget(self.toolbar)
        
        # Main content area with splitter
        main_splitter = QWidget()
        main_layout = QHBoxLayout(main_splitter)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(8)
        
        # Graphics view for mechanism display
        self.graphics_view = QGraphicsView()
        self.graphics_scene = QGraphicsScene()
        self.graphics_view.setScene(self.graphics_scene)
        
        # Configure view
        self.graphics_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.graphics_view.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.graphics_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.graphics_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Set background using ModernStyling
        self.graphics_view.setStyleSheet(f"""
            QGraphicsView {{
                background-color: {ModernStyling.COLORS['surface_container']};
                border: 1px solid {ModernStyling.COLORS['outline']};
                border-radius: 6px;
            }}
        """)
        
        main_layout.addWidget(self.graphics_view, 2)  # 2/3 of space
        
        # Right panel with tabs for different controls
        right_panel = QTabWidget()
        right_panel.setFixedWidth(320)
        right_panel.setStyleSheet(ModernStyling.get_tab_style())
        
        # Interaction controls tab
        self.interaction_controls = QWidget()
        
        # Initially empty - will be populated when mechanism is loaded
        self.interaction_layout = QVBoxLayout(self.interaction_controls)
        self.interaction_layout.setContentsMargins(8, 8, 8, 8)
        
        no_mechanism_label = QLabel("Select a mechanism to see interaction controls")
        no_mechanism_label.setStyleSheet(f"""
            color: {ModernStyling.COLORS['on_surface_variant']};
            font-style: italic;
            padding: 16px;
        """)
        no_mechanism_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.interaction_layout.addWidget(no_mechanism_label)
        self.interaction_layout.addStretch()
        
        right_panel.addTab(self.interaction_controls, "🎛️ Controls")
        
        # Motion analysis control panel
        self.analysis_control_panel = AnalysisControlPanel(self.motion_analysis_manager)
        right_panel.addTab(self.analysis_control_panel, "📊 Analysis")
        
        main_layout.addWidget(right_panel, 1)  # 1/3 of space
        
        layout.addWidget(main_splitter)
        
        # Setup animation timer
        self.animation_timer.timeout.connect(self._update_animation)
        self.animation_timer.setInterval(33)  # ~30 FPS
    
    def _connect_signals(self):
        """Connect toolbar signals."""
        self.toolbar.path_trace_toggled.connect(self._on_path_trace_toggled)
        self.toolbar.animation_speed_changed.connect(self._on_speed_changed)
        self.toolbar.zoom_changed.connect(self._on_zoom_changed)
        self.toolbar.reset_view_requested.connect(self._reset_view)
        
        # Connect to state manager
        if self.state_manager:
            self.state_manager.mechanism_changed.connect(self._on_mechanism_changed)
            self.state_manager.animation_state_changed.connect(self._on_animation_state_changed)
        
        # Connect analysis control panel signals
        if self.analysis_control_panel:
            self.analysis_control_panel.layer_visibility_changed.connect(self._on_analysis_layer_visibility_changed)
            self.analysis_control_panel.strategy_parameter_changed.connect(self._on_analysis_parameter_changed)
            self.analysis_control_panel.export_requested.connect(self._on_analysis_export_requested)
    
    def load_mechanism(self, mechanism: BaseMechanism):
        """Load a mechanism into the playground."""
        if mechanism is None:
            logger.warning("Cannot load None mechanism")
            return
        
        # Clear existing mechanism and handlers first
        self.clear_mechanism()
        
        # Now set the new mechanism
        self.current_mechanism = mechanism
        
        # Create new mechanism graphics item
        self.mechanism_item = MechanismGraphicsItem(mechanism)
        self.graphics_scene.addItem(self.mechanism_item)
        
        # Create mechanism-specific interaction handler
        self.interaction_handler = InteractionHandlerFactory.create_handler(mechanism)
        self.interaction_handler.set_graphics_scene(self.graphics_scene)
        
        # Connect interaction handler signals
        self.interaction_handler.parameter_changed.connect(self._on_parameter_changed)
        self.interaction_handler.analysis_updated.connect(self._on_analysis_updated)
        
        # Setup motion analysis system
        self.motion_analysis_manager.set_mechanism(mechanism)
        
        # Create and add analysis visualization overlay
        self.analysis_overlay = AnalysisVisualizationOverlay(self.motion_analysis_manager)
        self.graphics_scene.addItem(self.analysis_overlay)
        
        # Load interaction controls
        self._load_interaction_controls()
        
        # Start analysis systems
        self.interaction_handler.start_analysis()
        self.motion_analysis_manager.start_analysis()
        
        # Fit mechanism in view
        self._reset_view()
        
        logger.debug(f"Loaded mechanism: {mechanism.get_mechanism_type()}")
    
    def clear_mechanism(self):
        """Clear the current mechanism."""
        # Stop animation
        self.stop_animation()
        
        # Stop analysis systems
        self.motion_analysis_manager.stop_analysis()
        
        # Clean up interaction handler
        if self.interaction_handler:
            self.interaction_handler.cleanup()
            self.interaction_handler = None
        
        # Remove analysis overlay
        if self.analysis_overlay:
            self.graphics_scene.removeItem(self.analysis_overlay)
            self.analysis_overlay = None
        
        # Remove mechanism graphics item
        if self.mechanism_item:
            self.graphics_scene.removeItem(self.mechanism_item)
            self.mechanism_item = None
        
        # Clear interaction controls
        self._clear_interaction_controls()
        
        # Reset motion tracking
        self.previous_positions.clear()
        
        self.current_mechanism = None
    
    def start_animation(self):
        """Start mechanism animation."""
        if not self.current_mechanism:
            return
        
        self.is_animating = True
        self.animation_timer.start()
        logger.debug("Animation started")
    
    def stop_animation(self):
        """Stop mechanism animation."""
        self.is_animating = False
        self.animation_timer.stop()
        logger.debug("Animation stopped")
    
    def reset_animation(self):
        """Reset animation to start."""
        self.animation_time = 0.0
        if self.mechanism_item:
            self.mechanism_item.clear_path_trace()
            self.mechanism_item.update_animation(0.0)
        logger.debug("Animation reset")
    
    def _update_animation(self):
        """Update animation frame."""
        if not self.is_animating or not self.mechanism_item:
            return
        
        # Update animation time
        dt = 0.033 * self.animation_speed  # Time step in seconds
        self.animation_time += dt
        
        # Update mechanism
        self.mechanism_item.update_animation(self.animation_time)
        
        # Track motion for analysis
        self._track_motion_points(dt)
        
        # Update analysis overlay
        if self.analysis_overlay:
            self.analysis_overlay.update()
    
    def _track_motion_points(self, dt: float):
        """Track mechanism motion points for analysis."""
        if not self.current_mechanism or not hasattr(self.current_mechanism, 'points'):
            return
        
        current_positions = {}
        
        # Track key points (typically the end effector and joints)
        for i, point in enumerate(self.current_mechanism.points):
            point_id = f"point_{i}"
            current_pos = QPointF(point.x, point.y)
            current_positions[point_id] = current_pos
            
            # Calculate velocity and acceleration if we have previous data
            if point_id in self.previous_positions:
                prev_data = self.previous_positions[point_id]
                prev_pos = prev_data['position']
                prev_vel = prev_data.get('velocity', QPointF(0, 0))
                
                # Calculate velocity (change in position / time)
                velocity = QPointF(
                    (current_pos.x() - prev_pos.x()) / dt,
                    (current_pos.y() - prev_pos.y()) / dt
                )
                
                # Calculate acceleration (change in velocity / time)
                acceleration = QPointF(
                    (velocity.x() - prev_vel.x()) / dt,
                    (velocity.y() - prev_vel.y()) / dt
                )
                
                # Add motion point to analysis manager
                self.motion_analysis_manager.add_motion_point(
                    position=current_pos,
                    velocity=velocity,
                    acceleration=acceleration,
                    time=self.animation_time
                )
                
                # Store current data for next iteration
                self.previous_positions[point_id] = {
                    'position': current_pos,
                    'velocity': velocity,
                    'time': self.animation_time
                }
            else:
                # First iteration - no velocity/acceleration data yet
                self.previous_positions[point_id] = {
                    'position': current_pos,
                    'velocity': QPointF(0, 0),
                    'time': self.animation_time
                }
    
    def _on_mechanism_changed(self, mechanism_id: str):
        """Handle mechanism change from state manager."""
        if self.state_manager:
            mechanism = self.state_manager.get_current_mechanism_instance()
            if mechanism:
                self.load_mechanism(mechanism)
            else:
                logger.warning(f"State manager returned None mechanism for ID: {mechanism_id}")
                self.clear_mechanism()
    
    def _on_animation_state_changed(self, is_animating: bool):
        """Handle animation state change from state manager."""
        if is_animating:
            self.start_animation()
        else:
            self.stop_animation()
    
    def _on_path_trace_toggled(self, enabled: bool):
        """Handle path trace toggle."""
        if self.mechanism_item:
            self.mechanism_item.set_path_trace_visible(enabled)
    
    def _on_speed_changed(self, speed: float):
        """Handle animation speed change."""
        self.animation_speed = speed
        if self.state_manager:
            self.state_manager.set_animation_speed(speed)
    
    def _on_zoom_changed(self, zoom: float):
        """Handle zoom change."""
        transform = self.graphics_view.transform()
        self.graphics_view.setTransform(transform.scale(zoom/transform.m11(), zoom/transform.m22()))
    
    def _reset_view(self):
        """Reset view to fit mechanism."""
        if self.mechanism_item:
            self.graphics_view.fitInView(self.mechanism_item.boundingRect(), Qt.AspectRatioMode.KeepAspectRatio)
            # Add some margin
            self.graphics_view.scale(0.8, 0.8)
        else:
            self.graphics_view.resetTransform()
        
        # Reset zoom slider
        self.toolbar.zoom_slider.setValue(100)
        self.toolbar.zoom_label.setText("100%")
    
    def take_snapshot(self) -> QPixmap:
        """Take a snapshot of the current view."""
        return self.graphics_view.grab()
    
    def export_animation(self) -> List[QPixmap]:
        """Export animation frames (placeholder for future implementation)."""
        frames = []
        # Could implement frame-by-frame export here
        return frames
    
    def _load_interaction_controls(self):
        """Load mechanism-specific interaction controls."""
        if not self.interaction_handler or not self.current_mechanism:
            return
        
        # Clear existing controls
        self._clear_interaction_controls()
        
        # Add mechanism type header
        mechanism_type = self.current_mechanism.get_mechanism_type() if self.current_mechanism else "Unknown"
        type_label = QLabel(f"Mechanism: {mechanism_type.replace('_', ' ').title()}")
        type_label.setFont(QFont(ModernStyling.TYPOGRAPHY['font_family'], 
                                ModernStyling.TYPOGRAPHY['font_size_h3'], QFont.Weight.Bold))
        type_label.setStyleSheet(f"color: {ModernStyling.COLORS['primary']}; margin-bottom: 8px;")
        self.interaction_layout.addWidget(type_label)
        
        # Add interaction controls widget
        controls_widget = self.interaction_handler.create_interaction_controls()
        if controls_widget:
            self.interaction_layout.addWidget(controls_widget)
        
        # Add drag instructions
        instructions_label = QLabel("💡 Drag the blue handles in the viewport to adjust parameters in real-time")
        instructions_label.setWordWrap(True)
        instructions_label.setStyleSheet(f"""
            color: {ModernStyling.COLORS['on_surface_variant']};
            font-size: {ModernStyling.TYPOGRAPHY['font_size_caption']}px;
            background-color: {ModernStyling.COLORS['surface_variant']};
            padding: 8px;
            border-radius: 4px;
            margin-top: 8px;
        """)
        self.interaction_layout.addWidget(instructions_label)
        
        self.interaction_layout.addStretch()
    
    def _clear_interaction_controls(self):
        """Clear all interaction control widgets."""
        while self.interaction_layout.count():
            child = self.interaction_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Add default "no mechanism" message
        no_mechanism_label = QLabel("Select a mechanism to see interaction controls")
        no_mechanism_label.setStyleSheet(f"""
            color: {ModernStyling.COLORS['on_surface_variant']};
            font-style: italic;
            padding: 16px;
        """)
        no_mechanism_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.interaction_layout.addWidget(no_mechanism_label)
        self.interaction_layout.addStretch()
    
    def _on_parameter_changed(self, parameter_name: str, value):
        """Handle parameter changes from interaction handlers."""
        if self.current_mechanism:
            # Update mechanism parameter
            self.current_mechanism.set_parameter(parameter_name, value)
            
            # Update visualization
            if self.interaction_handler:
                self.interaction_handler.update_visualization()
            
            # Propagate to state manager
            if self.state_manager:
                self.state_manager.set_mechanism_parameter(parameter_name, value)
            
            logger.debug(f"Parameter {parameter_name} changed to {value}")
    
    def _on_analysis_updated(self, analysis_data: Dict):
        """Handle analysis updates from interaction handlers."""
        # Could display analysis data in a separate panel or tooltip
        # For now, just log the analysis
        logger.debug(f"Analysis updated: {analysis_data}")
        
        # Future: Could emit signal to update analysis display
        # self.analysis_updated.emit(analysis_data)
    
    def _on_analysis_layer_visibility_changed(self, layer_name: str, visible: bool):
        """Handle analysis layer visibility changes."""
        if self.analysis_overlay:
            self.analysis_overlay.set_layer_visibility(layer_name, visible)
        logger.debug(f"Analysis layer {layer_name} visibility: {visible}")
    
    def _on_analysis_parameter_changed(self, strategy_name: str, parameter_name: str, value):
        """Handle analysis parameter changes."""
        self.motion_analysis_manager.set_strategy_parameter(strategy_name, parameter_name, value)
        logger.debug(f"Analysis parameter {strategy_name}.{parameter_name} = {value}")
    
    def _on_analysis_export_requested(self):
        """Handle analysis data export request."""
        try:
            export_data = self.motion_analysis_manager.export_analysis_data()
            
            # In a real implementation, this would show a file dialog
            # For now, just log the export data
            logger.info("Analysis data export requested")
            logger.debug(f"Export data: {export_data}")
            
            # Future: Could implement CSV/JSON export to file
            # import json
            # with open("motion_analysis_export.json", "w") as f:
            #     json.dump(export_data, f, indent=2)
            
        except Exception as e:
            logger.error(f"Failed to export analysis data: {e}")