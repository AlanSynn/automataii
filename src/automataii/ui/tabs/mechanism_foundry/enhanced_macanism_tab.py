"""
Enhanced Macanism Tab - Interactive Mechanism Visualization with Force Display

This module provides an intuitive, interactive mechanism visualization system inspired by
github.com/AlanSynn/macanism with force visualization, physics simulation, and educational features.

Key Features:
- Real-time force visualization with color-coded stress display
- Interactive drag-and-drop parameter manipulation
- Live physics simulation with motion trails
- Educational tooltips and measurement displays
- Simplified, intuitive UI with no clipping issues
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Sequence

from PyQt6.QtCore import (
    QCoreApplication,
    QPointF,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
    QTransform,
)
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QGraphicsEllipseItem,
    QGraphicsScene,
    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSlider,
    QSplitter,
    QToolBar,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from automataii.application.mechanism_foundry import (
    MechanismCatalogService,
    MechanismFoundryController,
    MechanismItem,
    ParameterSpec,
)


class ForceType(Enum):
    """Types of forces to visualize"""

    REACTION = "reaction"
    APPLIED = "applied"
    CONSTRAINT = "constraint"
    FRICTION = "friction"
    GRAVITY = "gravity"


@dataclass
class ForceVector:
    """Represents a force vector for visualization"""

    position: QPointF
    magnitude: float
    angle: float  # radians
    force_type: ForceType
    label: str = ""
    color: QColor = None

    def __post_init__(self):
        if self.color is None:
            colors = {
                ForceType.REACTION: QColor(255, 69, 0, 200),
                ForceType.APPLIED: QColor(0, 123, 255, 200),
                ForceType.CONSTRAINT: QColor(255, 140, 0, 200),
                ForceType.FRICTION: QColor(128, 128, 128, 200),
                ForceType.GRAVITY: QColor(139, 69, 19, 200),
            }
            self.color = colors.get(self.force_type, QColor(100, 100, 100, 200))

    def to_components(self) -> tuple[float, float]:
        """Convert to x, y components"""
        return (self.magnitude * math.cos(self.angle), self.magnitude * math.sin(self.angle))


class DraggablePointHandle(QGraphicsEllipseItem):
    """Minimal draggable handle for parametric editing."""

    def __init__(self, center: QPointF, radius: float, item_id: str,
                 on_move=None, on_release=None, parent=None):
        super().__init__(-radius, -radius, radius * 2, radius * 2, parent)
        self.setBrush(QBrush(QColor(255, 0, 0, 180)))
        self.setPen(QPen(QColor(200, 0, 0), 1.5))
        self.setZValue(10_000)
        self.setFlag(QGraphicsEllipseItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsEllipseItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self.setPos(center)
        self._dragging = False
        self._on_move = on_move
        self._on_release = on_release
        self._id = item_id

    def id(self) -> str:
        return self._id

    def mousePressEvent(self, event):
        self._dragging = True
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        if self._dragging and self._on_move:
            self._on_move(self, self.pos())

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self._dragging = False
        if self._on_release:
            self._on_release(self, self.pos())


class InteractiveMechanismWidget(QGraphicsView):
    """
    Interactive mechanism visualization widget with force display - OPTIMIZED VERSION

    Features:
    - Real-time force visualization with optimized rendering
    - Interactive parameter manipulation via drag handles
    - Motion trails and velocity vectors
    - Stress/strain color coding
    - Educational annotations
    - Performance optimizations for smooth 60fps animation
    """

    # Signals
    parameter_changed = pyqtSignal(str, float)  # param_name, value
    component_selected = pyqtSignal(str)  # component_id
    force_calculated = pyqtSignal(dict)  # force_data

    def __init__(self, parent=None):
        super().__init__(parent)

        # Scene setup
        self.scene = QGraphicsScene()
        self.setScene(self.scene)

        # Performance optimizations
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.SmartViewportUpdate)
        self.setCacheMode(QGraphicsView.CacheModeFlag.CacheBackground)
        self.setOptimizationFlags(
            QGraphicsView.OptimizationFlag.DontAdjustForAntialiasing |
            QGraphicsView.OptimizationFlag.DontSavePainterState
        )

        # Rendering settings - simplified for performance
        self.show_forces = True
        self.show_velocities = False
        self.show_accelerations = False
        self.show_motion_trail = True
        self.show_measurements = False  # Disable measurements for performance
        self.show_stress = True

        # Mechanism data
        self.mechanism_type = "four_bar"
        self.mechanism_params = {}
        self.forces: list[ForceVector] = []
        self.motion_trail: list[QPointF] = []
        self.max_trail_points = 30  # Reduced from 50 for performance

        # Interaction state
        self.dragging_handle = None
        self.hover_component = None
        self.selected_components = set()

        # Parametric handles
        self.parametric_handles: dict[str, DraggablePointHandle] = {}
        self.show_parametric_handles = True

        # Animation - optimized to 45 FPS
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.update_animation)
        self.animation_angle = 30.0  # Start at 30 degrees - safe position for four-bar mechanisms
        self.animation_speed = 4.0  # Faster animation speed (4 degrees per frame)

        # Safety zone system (replacing physics violation system)
        self.safety_status = "safe"  # "safe", "warning", "danger"
        self.safety_message = ""
        self.show_safety_zones = True
        self.physics_tolerance = 0.001

        # Safety zone visual elements
        self.safety_zone_items = []
        self.safety_status_text = None

        # Performance tracking
        self.frame_count = 0
        self.skip_expensive_operations = False

        # Cached graphics items for reuse
        self.grid_items = []
        self.mechanism_items = {}
        self.force_items = []
        self.trail_items = []

        self._setup_ui()
        self._setup_interactions()
        self._create_static_grid()  # Create grid once instead of every frame  # Create grid once instead of every frame  # Create grid once instead of every frame

    def _setup_ui(self):
        """Setup the view UI with performance optimizations"""
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Set scene rect
        self.scene.setSceneRect(-400, -300, 800, 600)

        # Background
        self.scene.setBackgroundBrush(QBrush(QColor(250, 250, 250)))

        # Enable keyboard input
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocus()

    def _setup_interactions(self):
        """Setup mouse interactions"""
        self.setMouseTracking(True)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)

    def _create_static_grid(self):
        """Create optimized grid once and cache it for performance"""
        if self.grid_items:  # Already created
            return

        grid_size = 50  # Larger grid for fewer lines
        major_grid_size = 100

        # Grid colors
        minor_color = QColor(200, 200, 200, 60)
        major_color = QColor(150, 150, 150, 120)
        axis_color = QColor(100, 100, 100, 200)

        rect = self.scene.sceneRect()

        # Major grid only - skip minor grid for better performance
        pen = QPen(major_color, 1, Qt.PenStyle.SolidLine)
        for x in range(int(rect.left()), int(rect.right()), major_grid_size):
            line = self.scene.addLine(x, rect.top(), x, rect.bottom(), pen)
            line.setZValue(-99)
            self.grid_items.append(line)

        for y in range(int(rect.top()), int(rect.bottom()), major_grid_size):
            line = self.scene.addLine(rect.left(), y, rect.right(), y, pen)
            line.setZValue(-99)
            self.grid_items.append(line)

        # Axes
        pen = QPen(axis_color, 2, Qt.PenStyle.SolidLine)
        x_axis = self.scene.addLine(rect.left(), 0, rect.right(), 0, pen)
        y_axis = self.scene.addLine(0, rect.top(), 0, rect.bottom(), pen)
        x_axis.setZValue(-98)
        y_axis.setZValue(-98)
        self.grid_items.extend([x_axis, y_axis])

        # Origin
        origin = self.scene.addEllipse(-3, -3, 6, 6, pen, QBrush(axis_color))
        origin.setZValue(-97)
        self.grid_items.append(origin)

    def draw_mechanism(self):
        """Draw the current mechanism with performance optimizations and safety zones"""
        # Ensure valid starting position on first draw
        if self.frame_count == 0:
            self._ensure_valid_starting_position()

        # Performance tracking
        self.frame_count += 1

        # Skip expensive operations occasionally for performance
        self.skip_expensive_operations = (self.frame_count % 3 != 0)

        # Only clear mechanism items, not grid
        self._clear_mechanism_items()

        # Draw safety zones first (educational overlay)
        if not self.skip_expensive_operations:
            self._draw_safety_zones()

        # Draw mechanism based on type
        print(f"DEBUG: Drawing mechanism type: {self.mechanism_type}")
        if self.mechanism_type == "four_bar":
            self._draw_four_bar_mechanism_optimized()
        elif self.mechanism_type == "slider_crank":
            self._draw_slider_crank_mechanism_optimized()
        elif self.mechanism_type == "cam_follower":
            self._draw_cam_follower_mechanism_optimized()
        elif self.mechanism_type == "gear_train":
            print("DEBUG: About to draw gear train...")
            self._draw_gear_train_mechanism_optimized()
            print("DEBUG: Gear train drawn")


        # Draw forces if enabled (persistent vectors - no more blinking!)
        if self.show_forces:
            self._draw_force_vectors_optimized()

        # Draw motion trail if enabled (simplified)
        if self.show_motion_trail:
            self._draw_motion_trail_optimized()

        # Update or create parametric handles after drawing
        self._ensure_parametric_handles()

    def _clear_mechanism_items(self):
        """Clear only mechanism-related items, keeping persistent force vectors"""
        # Remove old mechanism items (links, joints, etc.)
        for key, item in list(self.mechanism_items.items()):
            try:
                if hasattr(item, '__iter__') and not isinstance(item, str):
                    # Handle lists/collections of items
                    for sub_item in item:
                        if sub_item and hasattr(sub_item, 'scene') and sub_item.scene():
                            self.scene.removeItem(sub_item)
                else:
                    # Handle single items
                    if item and hasattr(item, 'scene') and item.scene():
                        self.scene.removeItem(item)
            except RuntimeError:
                # Item might have been deleted already
                pass

        # Clear old force items (but preserve persistent force vectors)
        for item in list(self.force_items):
            try:
                if item and hasattr(item, 'scene') and item.scene():
                    self.scene.removeItem(item)
            except RuntimeError:
                # Item might have been deleted already
                pass

        # Remove trail items
        for item in list(self.trail_items):
            try:
                if item and hasattr(item, 'scene') and item.scene():
                    self.scene.removeItem(item)
            except RuntimeError:
                # Item might have been deleted already
                pass

        # Clear the collections
        self.mechanism_items.clear()
        self.force_items.clear()  # This is OK since we use persistent_force_vectors now
        self.trail_items.clear()

        # Note: persistent_force_vectors are NOT cleared - they update smoothly!

    def _draw_four_bar_mechanism_optimized(self):
        """Optimized four-bar linkage drawing with proper force calculation"""
        print(f"DEBUG: _draw_four_bar_mechanism_optimized called! mechanism_type={self.mechanism_type}")
        # Updated default parameters to match image settings
        if not self.mechanism_params:
            self.mechanism_params = {
                "ground_link": 150,      # Ground Link: 150
                "input_link": 40,        # Input Link: 40
                "coupler_link": 120,     # Coupler Link: 120
                "output_link": 130,      # Output Link: 130
                "input_angle": self.animation_angle,
            }

        # Calculate positions
        input_link = self.mechanism_params["input_link"]
        coupler_link = self.mechanism_params["coupler_link"]
        output_link = self.mechanism_params["output_link"]
        input_angle = math.radians(self.mechanism_params["input_angle"])

        # Joint positions with optional custom anchors
        if "ground_pivot1" in self.mechanism_params and "ground_pivot2" in self.mechanism_params:
            gp1 = self.mechanism_params["ground_pivot1"]
            gp2 = self.mechanism_params["ground_pivot2"]
            O1 = gp1 if isinstance(gp1, QPointF) else QPointF(gp1[0], gp1[1])
            O4 = gp2 if isinstance(gp2, QPointF) else QPointF(gp2[0], gp2[1])
            ground_link = math.hypot(O4.x() - O1.x(), O4.y() - O1.y())
            self.mechanism_params["ground_link"] = ground_link
        else:
            ground_link = self.mechanism_params["ground_link"]
            O1 = QPointF(-ground_link / 2, 0)
            O4 = QPointF(ground_link / 2, 0)

        # Moving joint A (input link endpoint)
        A = QPointF(
            O1.x() + input_link * math.cos(input_angle),
            O1.y() + input_link * math.sin(input_angle)
        )

        # Calculate joint B position using accurate kinematics
        output_angle = self._solve_four_bar_output_angle_fast(
            ground_link, input_link, coupler_link, output_link, input_angle
        )

        B = QPointF(
            O4.x() + output_link * math.cos(output_angle),
            O4.y() + output_link * math.sin(output_angle),
        )

        # Calculate stress levels for coloring
        input_stress = 0.3 * math.sin(input_angle * 2)
        coupler_stress = -0.4 * math.cos(input_angle)
        output_stress = 0.2 * math.sin(output_angle * 1.5)

        # Draw links with optimized rendering
        self._draw_link_optimized(O1, A, "link_O1A", stress=input_stress)
        self._draw_link_optimized(A, B, "link_AB", stress=coupler_stress)
        self._draw_link_optimized(B, O4, "link_BO4", stress=output_stress)

        # Draw joints with simplified representation
        self._draw_joint_optimized(O1, "O1", is_fixed=True)
        self._draw_joint_optimized(O4, "O4", is_fixed=True)
        self._draw_joint_optimized(A, "A", is_fixed=False)
        self._draw_joint_optimized(B, "B", is_fixed=False)

        # Store joint positions for animation updates
        self.mechanism_items["joint_A"] = A
        self.mechanism_items["joint_B"] = B

        # Calculate forces for four-bar mechanism
        self._calculate_four_bar_forces_optimized(O1, A, B, O4)

        # Add to motion trail (simplified)
        if self.show_motion_trail:
            self.motion_trail.append(B)
            if len(self.motion_trail) > self.max_trail_points:
                self.motion_trail.pop(0)

    def _draw_link_optimized(self, start: QPointF, end: QPointF, link_id: str, stress: float = 0.0):
        """Optimized link drawing with proper visual representation"""
        # Base color
        base_color = QColor(70, 130, 180)

        # Stress coloring - keep the original visual quality
        if self.show_stress and stress != 0:
            if stress > 0:  # Compression - red
                intensity = min(abs(stress), 1.0)
                color = QColor(
                    int(255 * intensity + base_color.red() * (1 - intensity)),
                    int(base_color.green() * (1 - intensity)),
                    int(base_color.blue() * (1 - intensity)),
                )
            else:  # Tension - blue
                intensity = min(abs(stress), 1.0)
                color = QColor(
                    int(base_color.red() * (1 - intensity)),
                    int(base_color.green() * (1 - intensity)),
                    int(255 * intensity + base_color.blue() * (1 - intensity)),
                )
        else:
            color = base_color

        # Draw link body (wider representation) - restore visual quality
        angle = math.atan2(end.y() - start.y(), end.x() - start.x())
        width = 8

        # Calculate perpendicular offset
        perp_x = -math.sin(angle) * width / 2
        perp_y = math.cos(angle) * width / 2

        # Create polygon for link body
        polygon = QPolygonF([
            QPointF(start.x() + perp_x, start.y() + perp_y),
            QPointF(start.x() - perp_x, start.y() - perp_y),
            QPointF(end.x() - perp_x, end.y() - perp_y),
            QPointF(end.x() + perp_x, end.y() + perp_y),
        ])

        brush = QBrush(color.lighter(150))
        pen = QPen(color, 1)
        poly_item = self.scene.addPolygon(polygon, pen, brush)
        poly_item.setData(0, link_id)
        poly_item.setOpacity(0.7)

        # Main line for structure
        main_pen = QPen(color.darker(120), 3)
        line = self.scene.addLine(start.x(), start.y(), end.x(), end.y(), main_pen)
        line.setData(0, link_id + "_main")

        # Store both items
        self.mechanism_items[link_id] = [poly_item, line]

    def _draw_joint_optimized(self, position: QPointF, joint_id: str, is_fixed: bool = False):
        """Optimized joint drawing with proper visual representation"""
        if is_fixed:
            # Fixed joint (ground) - restore hatching for visual clarity
            size = 16
            color = QColor(105, 105, 105)

            # Draw hatch pattern for ground - simplified but visible
            hatch_lines = []
            for i in range(3):  # Reduced from 5 to 3 for performance
                x_offset = -15 + i * 7
                line = self.scene.addLine(
                    position.x() + x_offset,
                    position.y(),
                    position.x() + x_offset - 8,
                    position.y() + 8,
                    QPen(color, 1),
                )
                hatch_lines.append(line)

            # Store hatch lines
            self.mechanism_items[joint_id + "_hatch"] = hatch_lines
        else:
            # Moving joint
            size = 12
            color = QColor(220, 20, 60)

        # Draw joint circle
        joint = self.scene.addEllipse(
            position.x() - size / 2,
            position.y() - size / 2,
            size,
            size,
            QPen(color.darker(120), 2),
            QBrush(color),
        )
        joint.setData(0, joint_id)
        joint.setZValue(10)

        # Inner circle for visual effect - keep for quality
        inner_size = size * 0.4
        inner = self.scene.addEllipse(
            position.x() - inner_size / 2,
            position.y() - inner_size / 2,
            inner_size,
            inner_size,
            QPen(Qt.PenStyle.NoPen),
            QBrush(QColor(255, 255, 255, 150)),
        )
        inner.setZValue(11)

        # Store joint items
        self.mechanism_items[joint_id] = [joint, inner]

        # Label - only show occasionally for performance
        if not self.skip_expensive_operations:
            text = self.scene.addText(joint_id, QFont("Arial", 8))
            text.setPos(position.x() + size / 2 + 5, position.y() - 10)
            text.setDefaultTextColor(QColor(60, 60, 60))
            self.mechanism_items[joint_id + "_label"] = text

    def _solve_four_bar_output_angle_fast(self, ground, input_l, coupler, output, input_angle):
        """Accurate and robust four-bar kinematics with improved branch selection"""
        try:
            # Link lengths
            r1 = ground  # ground link
            r2 = input_l  # input (crank) link
            r3 = coupler  # coupler link
            r4 = output   # output (rocker) link

            # Input angle (theta2)
            theta2 = input_angle

            # Position of point A (end of input link)
            Ax = r2 * math.cos(theta2)
            Ay = r2 * math.sin(theta2)

            # Position of ground joint O4
            O4x = r1
            O4y =0

            # Distance from A to O4
            L = math.sqrt((O4x - Ax)**2 + (O4y - Ay)**2)

            # Check if configuration is geometrically possible (Grashof condition)
            if L > (r3 + r4) or L < abs(r3 - r4):
                # Return last valid angle if configuration is impossible
                if hasattr(self, '_last_output_angle'):
                    return self._last_output_angle
                else:
                    # Fallback for first calculation
                    return -input_angle * 0.3

            # Calculate output angle using vector approach
            # Vector from O4 to A
            vec_O4A_x = Ax - O4x
            vec_O4A_y = Ay - O4y

            # Angle from O4 to A
            alpha = math.atan2(vec_O4A_y, vec_O4A_x)

            # Use cosine rule to find angle at joint B
            try:
                cos_gamma = (r3*r3 + r4*r4 - L*L) / (2*r3*r4)
                cos_gamma = max(-1.0, min(1.0, cos_gamma))  # Clamp to valid range
                gamma = math.acos(cos_gamma)
            except (ValueError, ZeroDivisionError):
                gamma = 0

            # Use cosine rule to find angle from O4-A line to O4-B line
            try:
                cos_beta = (r4*r4 + L*L - r3*r3) / (2*r4*L)
                cos_beta = max(-1.0, min(1.0, cos_beta))  # Clamp to valid range
                beta = math.acos(cos_beta)
            except (ValueError, ZeroDivisionError):
                beta = 0

            # Two possible solutions for the output angle
            theta4_1 = alpha + beta  # "Open" configuration
            theta4_2 = alpha - beta  # "Closed" configuration

            # Initialize branch selection for first calculation
            if not hasattr(self, '_assembly_mode'):
                # Choose initial assembly mode based on mechanism geometry
                # For typical four-bar linkages, prefer the configuration that keeps
                # the output link in the lower half-plane initially
                test_B1_y = O4y + r4 * math.sin(theta4_1)
                test_B2_y = O4y + r4 * math.sin(theta4_2)

                # Choose the solution that starts with output link pointing down or right
                if abs(theta4_1) < abs(theta4_2):
                    self._assembly_mode = 1  # Use theta4_1 (open)
                    theta4 = theta4_1
                else:
                    self._assembly_mode = 2  # Use theta4_2 (closed)
                    theta4 = theta4_2

                print(f"Four-bar mechanism initialized in assembly mode {self._assembly_mode}")
            else:
                # Use consistent assembly mode
                if self._assembly_mode == 1:
                    theta4 = theta4_1
                else:
                    theta4 = theta4_2

                # Check for branch switching - only switch if absolutely necessary
                if hasattr(self, '_last_output_angle'):
                    current_diff = abs(theta4 - self._last_output_angle)

                    # Normalize the difference to handle angle wrapping
                    while current_diff > math.pi:
                        current_diff -= 2*math.pi
                    current_diff = abs(current_diff)

                    # If current branch gives a huge jump, try the other branch
                    if current_diff > math.pi/3:  # 60 degrees threshold
                        # Try the other branch
                        alternative_theta4 = theta4_2 if self._assembly_mode == 1 else theta4_1
                        alternative_diff = abs(alternative_theta4 - self._last_output_angle)

                        # Normalize alternative difference
                        while alternative_diff > math.pi:
                            alternative_diff -= 2*math.pi
                        alternative_diff = abs(alternative_diff)

                        # Switch branch only if alternative is significantly better
                        if alternative_diff < current_diff / 2:
                            self._assembly_mode = 2 if self._assembly_mode == 1 else 1
                            theta4 = alternative_theta4
                            print(f"Four-bar mechanism switched to assembly mode {self._assembly_mode}")

            # Additional smoothing for very large jumps
            if hasattr(self, '_last_output_angle'):
                angular_change = theta4 - self._last_output_angle

                # Normalize to [-π, π]
                while angular_change > math.pi:
                    angular_change -= 2*math.pi
                while angular_change < -math.pi:
                    angular_change += 2*math.pi

                # Limit the maximum change per frame to prevent jumps
                max_change = math.pi / 8  # 22.5 degrees max per frame
                if abs(angular_change) > max_change:
                    if angular_change > 0:
                        theta4 = self._last_output_angle + max_change
                    else:
                        theta4 = self._last_output_angle - max_change

            # Store for next iteration
            self._last_output_angle = theta4

            # Validate the result
            if math.isnan(theta4) or math.isinf(theta4):
                print("Warning: Invalid angle calculated, using fallback")
                return getattr(self, '_last_output_angle', 0)

            return theta4

        except Exception as e:
            print(f"Error in four-bar calculation: {e}")
            # Return last known good value
            return getattr(self, '_last_output_angle', 0)




    def _evaluate_four_bar_safety(self, ground, input_l, coupler, output, input_angle):
        """Comprehensive four-bar mechanism safety evaluation using mechanical engineering principles"""
        try:
            # Link identification for Grashof analysis
            links = [(ground, 'ground'), (input_l, 'input'), (coupler, 'coupler'), (output, 'output')]
            link_lengths = [ground, input_l, coupler, output]
            sorted_links = sorted(link_lengths)
            s, p, q, l = sorted_links  # shortest, intermediate, intermediate, longest

            # Grashof criterion: s + l ≤ p + q
            grashof_sum = s + l
            middle_sum = p + q
            grashof_condition = grashof_sum <= middle_sum
            grashof_ratio = grashof_sum / middle_sum if middle_sum > 0 else float('inf')

            # Identify mechanism type based on which link is shortest
            shortest_link = min(links, key=lambda x: x[0])
            mechanism_class = "Unknown"

            if grashof_condition:
                if shortest_link[1] == 'ground':
                    mechanism_class = "Double-Crank (Class III)"
                    motion_type = "Both input and output can rotate 360°"
                elif shortest_link[1] in ['input', 'output']:
                    mechanism_class = "Crank-Rocker (Class I)"
                    motion_type = "Input rotates 360°, output rocks"
                else:  # coupler is shortest
                    mechanism_class = "Double-Rocker (Class II)"
                    motion_type = "Both input and output rock"
            else:
                mechanism_class = "Triple-Rocker (Class IV)"
                motion_type = "All links rock, no continuous rotation"

            # Current position analysis
            O1 = (-ground/2, 0)
            O4 = (ground/2, 0)
            A = (O1[0] + input_l * math.cos(input_angle), O1[1] + input_l * math.sin(input_angle))

            # Distance from A to O4
            distance_AO4 = math.sqrt((A[0] - O4[0])**2 + (A[1] - O4[1])**2)

            # Triangle feasibility check
            max_reach_AB = coupler + output  # Maximum distance between A and B
            min_reach_AB = abs(coupler - output)  # Minimum distance between A and B

            # Transmission angle calculation (angle between coupler and output links)
            if distance_AO4 <= max_reach_AB and distance_AO4 >= min_reach_AB:
                # Calculate output angle
                try:
                    cos_beta = (output*output + distance_AO4*distance_AO4 - coupler*coupler) / (2*output*distance_AO4)
                    cos_beta = max(-1.0, min(1.0, cos_beta))

                    cos_gamma = (coupler*coupler + output*output - distance_AO4*distance_AO4) / (2*coupler*output)
                    cos_gamma = max(-1.0, min(1.0, cos_gamma))

                    transmission_angle = math.degrees(math.acos(abs(cos_gamma)))
                    transmission_quality = "excellent" if 40 <= transmission_angle <= 140 else \
                                         "good" if 30 <= transmission_angle <= 150 else \
                                         "poor" if 20 <= transmission_angle <= 160 else "critical"
                except:
                    transmission_angle = 90
                    transmission_quality = "unknown"
            else:
                transmission_angle = 0
                transmission_quality = "impossible"

            # Design quality assessment
            link_ratio_quality = "excellent"
            quality_messages = []

            # Check for extreme link ratios (poor design practice)
            max_ratio = max(link_lengths) / min(link_lengths) if min(link_lengths) > 0 else float('inf')
            if max_ratio > 10:
                link_ratio_quality = "poor"
                quality_messages.append(f"Extreme link ratio: {max_ratio:.1f}:1")
            elif max_ratio > 6:
                link_ratio_quality = "fair"
                quality_messages.append(f"High link ratio: {max_ratio:.1f}:1")

            # Check for very small input link (difficult to manufacture/control)
            if input_l < ground * 0.1:
                quality_messages.append("Very small input link")
                if link_ratio_quality == "excellent":
                    link_ratio_quality = "fair"

            # Overall safety evaluation
            safety_status = "safe"
            safety_message = f"{mechanism_class}"

            if not grashof_condition:
                if grashof_ratio > 1.1:
                    safety_status = "danger"
                    safety_message = f"No continuous rotation possible (Grashof ratio: {grashof_ratio:.2f})"
                else:
                    safety_status = "warning"
                    safety_message = f"Limited motion, no continuous rotation (Grashof ratio: {grashof_ratio:.2f})"

            elif distance_AO4 > max_reach_AB:
                safety_status = "danger"
                safety_message = f"Links cannot reach current position (distance: {distance_AO4:.1f} > max: {max_reach_AB:.1f})"

            elif distance_AO4 < min_reach_AB:
                safety_status = "danger"
                safety_message = f"Links interference (distance: {distance_AO4:.1f} < min: {min_reach_AB:.1f})"

            elif transmission_quality == "critical":
                safety_status = "danger"
                safety_message = f"Critical transmission angle: {transmission_angle:.1f}° (force transmission very poor)"

            elif transmission_quality == "poor":
                safety_status = "warning"
                safety_message = f"Poor transmission angle: {transmission_angle:.1f}° (low force efficiency)"

            elif distance_AO4 > max_reach_AB * 0.95:
                safety_status = "warning"
                safety_message = "Near reach limit - approaching singular position"

            elif distance_AO4 < min_reach_AB * 1.05:
                safety_status = "warning"
                safety_message = "Near interference - approaching singular position"

            elif link_ratio_quality == "poor":
                safety_status = "warning"
                safety_message = f"{mechanism_class} - Design quality: {link_ratio_quality}"

            else:
                # Excellent condition
                if transmission_quality == "excellent":
                    safety_message = f"{mechanism_class} - Optimal design (T.A.: {transmission_angle:.1f}°)"
                else:
                    safety_message = f"{mechanism_class} - Good design (T.A.: {transmission_angle:.1f}°)"

            # Add quality notes if any
            if quality_messages and safety_status == "safe":
                safety_message += f" - Note: {', '.join(quality_messages)}"

            return safety_status, safety_message

        except Exception as e:
            return "danger", f"Safety evaluation error: {str(e)}"

    def _evaluate_slider_crank_safety(self, crank_length, rod_length, crank_angle):
        """Evaluate slider-crank mechanism safety"""
        crank_y_displacement = crank_length * abs(math.sin(crank_angle))
        reach_ratio = crank_y_displacement / rod_length

        if reach_ratio > 1.0:
            return "danger", f"Rod too short: needs {crank_y_displacement:.1f}, has {rod_length:.1f}"
        elif reach_ratio > 0.95:
            return "warning", f"Near rod limit: using {reach_ratio*100:.1f}% of rod length"
        elif abs(math.cos(crank_angle)) < 0.1:  # Near dead center
            return "warning", f"Approaching dead center (cos = {math.cos(crank_angle):.3f})"
        else:
            return "safe", f"Normal operation (rod usage: {reach_ratio*100:.1f}%)"

    def _draw_safety_zones(self):
        """Draw visual safety zones for educational understanding"""
        if not self.show_safety_zones:
            return

        # Clear old safety zone items
        for item in self.safety_zone_items:
            if item.scene():
                self.scene.removeItem(item)
        self.safety_zone_items.clear()

        if self.mechanism_type == "four_bar":
            self._draw_four_bar_safety_zones()
        elif self.mechanism_type == "slider_crank":
            self._draw_slider_crank_safety_zones()
        # No safety zones for gear_train or cam_follower

    def _draw_four_bar_safety_zones(self):
        """Draw comprehensive safety zones for four-bar mechanism based on mechanical engineering principles"""
        if not self.mechanism_params:
            return

        ground_link = self.mechanism_params.get("ground_link", 150)
        input_link = self.mechanism_params.get("input_link", 40)
        coupler_link = self.mechanism_params.get("coupler_link", 120)
        output_link = self.mechanism_params.get("output_link", 130)

        # Fixed joint positions
        O1 = QPointF(-ground_link / 2, 0)
        O4 = QPointF(ground_link / 2, 0)

        # Calculate reachability limits
        max_reach = coupler_link + output_link  # Maximum distance between A and B
        min_reach = abs(coupler_link - output_link)  # Minimum distance between A and B

        # Input link creates a circle of possible positions for point A
        input_circle_radius = input_link

        # For each point on the input circle, check if mechanism can be assembled
        # SAFE ZONE: Positions where transmission angle is optimal (40° ≤ T.A. ≤ 140°)
        # CAUTION ZONE: Acceptable transmission angles (20° ≤ T.A. ≤ 160°)
        # UNREACHABLE ZONE: Geometrically impossible or very poor transmission angles

        # Draw SAFE ZONE (green) - optimal operation region
        safe_inner_radius = min_reach * 1.1  # Avoid interference region
        safe_outer_radius = max_reach * 0.85  # Stay away from extreme reach

        safe_pen = QPen(QColor(0, 180, 0, 120), 3, Qt.PenStyle.DashLine)
        safe_brush = QBrush(QColor(50, 255, 50, 30))

        # Draw safe zone as ring around O4
        safe_outer = self.scene.addEllipse(
            O4.x() - safe_outer_radius, O4.y() - safe_outer_radius,
            safe_outer_radius * 2, safe_outer_radius * 2,
            safe_pen, safe_brush
        )
        safe_outer.setZValue(-52)
        self.safety_zone_items.append(safe_outer)

        # Remove inner part of safe zone if there's a minimum reach
        if min_reach > 10:  # Only if there's significant minimum reach
            safe_inner = self.scene.addEllipse(
                O4.x() - safe_inner_radius, O4.y() - safe_inner_radius,
                safe_inner_radius * 2, safe_inner_radius * 2,
                QPen(Qt.PenStyle.NoPen), QBrush(QColor(255, 255, 255, 100))
            )
            safe_inner.setZValue(-51)
            self.safety_zone_items.append(safe_inner)

        # Draw CAUTION ZONE (yellow) - acceptable operation
        caution_pen = QPen(QColor(255, 180, 0, 150), 2, Qt.PenStyle.DashLine)
        caution_brush = QBrush(QColor(255, 255, 0, 25))

        # Outer caution zone
        caution_outer = self.scene.addEllipse(
            O4.x() - max_reach * 0.98, O4.y() - max_reach * 0.98,
            max_reach * 0.98 * 2, max_reach * 0.98 * 2,
            caution_pen, caution_brush
        )
        caution_outer.setZValue(-53)
        self.safety_zone_items.append(caution_outer)

        # Inner caution zone (near interference)
        if min_reach > 5:
            caution_inner = self.scene.addEllipse(
                O4.x() - min_reach * 1.05, O4.y() - min_reach * 1.05,
                min_reach * 1.05 * 2, min_reach * 1.05 * 2,
                caution_pen, caution_brush
            )
            caution_inner.setZValue(-53)
            self.safety_zone_items.append(caution_inner)

        # Draw UNREACHABLE ZONE markers (red)
        unreachable_pen = QPen(QColor(220, 20, 20, 180), 3, Qt.PenStyle.SolidLine)
        unreachable_brush = QBrush(QColor(255, 0, 0, 40))

        # Outer unreachable zone
        unreachable_outer = self.scene.addEllipse(
            O4.x() - max_reach * 1.15, O4.y() - max_reach * 1.15,
            max_reach * 1.15 * 2, max_reach * 1.15 * 2,
            unreachable_pen, QBrush(Qt.BrushStyle.NoBrush)
        )
        unreachable_outer.setZValue(-54)
        self.safety_zone_items.append(unreachable_outer)

        # Add "UNREACHABLE" markers around the outer boundary
        for angle in range(0, 360, 60):
            rad = math.radians(angle)
            x = O4.x() + max_reach * 1.25 * math.cos(rad)
            y = O4.y() + max_reach * 1.25 * math.sin(rad)

            marker = self.scene.addEllipse(
                x - 8, y - 8, 16, 16,
                QPen(QColor(200, 0, 0), 2),
                QBrush(QColor(255, 100, 100, 150))
            )
            marker.setZValue(-48)
            self.safety_zone_items.append(marker)

        # Draw current mechanism position indicator
        current_angle = math.radians(self.animation_angle)
        current_A = QPointF(
            O1.x() + input_link * math.cos(current_angle),
            O1.y() + input_link * math.sin(current_angle)
        )

        # Calculate current output position
        try:
            output_angle = self._solve_four_bar_output_angle_fast(
                ground_link, input_link, coupler_link, output_link, current_angle
            )
            current_B = QPointF(
                O4.x() + output_link * math.cos(output_angle),
                O4.y() + output_link * math.sin(output_angle)
            )

            # Draw current coupler line (shows current reach)
            coupler_line = self.scene.addLine(
                current_A.x(), current_A.y(), current_B.x(), current_B.y(),
                QPen(QColor(100, 100, 255, 200), 3, Qt.PenStyle.SolidLine)
            )
            coupler_line.setZValue(-47)
            self.safety_zone_items.append(coupler_line)

        except:
            # If calculation fails, just show the reach requirement
            reach_line = self.scene.addLine(
                current_A.x(), current_A.y(), O4.x(), O4.y(),
                QPen(QColor(150, 150, 150, 150), 2, Qt.PenStyle.DotLine)
            )
            reach_line.setZValue(-48)
            self.safety_zone_items.append(reach_line)

        # Add zone labels with improved descriptions
        self._add_safety_zone_labels()

    def _draw_slider_crank_safety_zones(self):
        """Draw safety zones for slider-crank mechanism"""
        crank_length = 80
        rod_length = 140

        O1 = QPointF(-50, 0)

        # Draw maximum stroke limits
        max_stroke_left = O1.x() - crank_length - rod_length
        max_stroke_right = O1.x() + crank_length + rod_length

        # Safe operation zone (green)
        safe_pen = QPen(QColor(0, 200, 0, 120), 3)
        safe_zone = self.scene.addLine(
            max_stroke_left + crank_length * 0.1, -5,
            max_stroke_right - crank_length * 0.1, -5,
            safe_pen
        )
        safe_zone.setZValue(-50)
        self.safety_zone_items.append(safe_zone)

        # Warning zones (yellow) - near dead centers
        warning_pen = QPen(QColor(255, 165, 0, 120), 3)
        warning_left = self.scene.addLine(
            max_stroke_left, -5,
            max_stroke_left + crank_length * 0.1, -5,
            warning_pen
        )
        warning_right = self.scene.addLine(
            max_stroke_right - crank_length * 0.1, -5,
            max_stroke_right, -5,
            warning_pen
        )
        self.safety_zone_items.extend([warning_left, warning_right])

        # Current crank position
        current_angle = math.radians(self.animation_angle)
        current_A = QPointF(
            O1.x() + crank_length * math.cos(current_angle),
            O1.y() + crank_length * math.sin(current_angle)
        )

        # Show rod stress level
        rod_stress = abs(math.sin(current_angle))
        stress_color = QColor(int(255 * rod_stress), int(255 * (1 - rod_stress)), 0, 150)
        stress_indicator = self.scene.addEllipse(
            current_A.x() - 8, current_A.y() - 8, 16, 16,
            QPen(stress_color, 2), QBrush(stress_color)
        )
        stress_indicator.setZValue(-48)
        self.safety_zone_items.append(stress_indicator)

    def _add_safety_zone_labels(self):
        """Add educational labels to safety zones with mechanical engineering context"""
        # Safe zone label - optimal transmission angle region
        safe_label = self.scene.addText("SAFE ZONE", QFont("Arial", 11, QFont.Weight.Bold))
        safe_label.setDefaultTextColor(QColor(0, 150, 0, 200))
        safe_label.setPos(40, -100)
        safe_label.setZValue(-45)
        self.safety_zone_items.append(safe_label)

        safe_desc = self.scene.addText("Optimal transmission angles\n40° ≤ T.A. ≤ 140°", QFont("Arial", 8))
        safe_desc.setDefaultTextColor(QColor(0, 120, 0, 180))
        safe_desc.setPos(45, -80)
        safe_desc.setZValue(-45)
        self.safety_zone_items.append(safe_desc)

        # Caution zone label - acceptable but suboptimal
        caution_label = self.scene.addText("CAUTION", QFont("Arial", 10, QFont.Weight.Bold))
        caution_label.setDefaultTextColor(QColor(255, 140, 0, 200))
        caution_label.setPos(100, -60)
        caution_label.setZValue(-45)
        self.safety_zone_items.append(caution_label)

        caution_desc = self.scene.addText("Acceptable transmission\nApproaching limits", QFont("Arial", 8))
        caution_desc.setDefaultTextColor(QColor(200, 120, 0, 180))
        caution_desc.setPos(100, -45)
        caution_desc.setZValue(-45)
        self.safety_zone_items.append(caution_desc)

        # Unreachable zone label
        unreachable_label = self.scene.addText("UNREACHABLE", QFont("Arial", 10, QFont.Weight.Bold))
        unreachable_label.setDefaultTextColor(QColor(200, 0, 0, 200))
        unreachable_label.setPos(140, -25)
        unreachable_label.setZValue(-45)
        self.safety_zone_items.append(unreachable_label)

        unreachable_desc = self.scene.addText("Geometric impossibility\nPoor force transmission", QFont("Arial", 8))
        unreachable_desc.setDefaultTextColor(QColor(180, 0, 0, 180))
        unreachable_desc.setPos(140, -10)
        unreachable_desc.setZValue(-45)
        self.safety_zone_items.append(unreachable_desc)



    def _show_physics_status(self, message, color):
        """Show physics status message on screen"""
        # Remove old status text
        if self.physics_status_text and self.physics_status_text.scene():
            self.scene.removeItem(self.physics_status_text)

        # Add new status text
        font = QFont("Arial", 12, QFont.Weight.Bold)
        self.physics_status_text = self.scene.addText(message, font)
        self.physics_status_text.setDefaultTextColor(color)
        self.physics_status_text.setPos(-200, -280)  # Top of screen
        self.physics_status_text.setZValue(100)  # On top of everything

    def _show_physics_diagnostic(self, error_message):
        """Show detailed physics diagnostic with solutions"""
        # Clear old items first
        if self.physics_status_text and self.physics_status_text.scene():
            self.scene.removeItem(self.physics_status_text)

        # Create diagnostic panel
        panel_width = 400
        panel_height = 220
        panel_x = -panel_width // 2
        panel_y = -50

        # Background panel
        panel_rect = self.scene.addRect(
            panel_x, panel_y, panel_width, panel_height,
            QPen(QColor(200, 0, 0), 2),
            QBrush(QColor(255, 240, 240, 230))
        )
        panel_rect.setZValue(90)

        # Title
        title_font = QFont("Arial", 14, QFont.Weight.Bold)
        title_text = self.scene.addText("❌ Physics Violation - Animation Stopped", title_font)
        title_text.setDefaultTextColor(QColor(200, 0, 0))
        title_text.setPos(panel_x + 10, panel_y + 5)
        title_text.setZValue(91)

        # Error details
        details_font = QFont("Arial", 10)
        details_text = f"Error: {error_message}"
        details = self.scene.addText(details_text, details_font)
        details.setDefaultTextColor(QColor(100, 0, 0))
        details.setPos(panel_x + 10, panel_y + 35)
        details.setZValue(91)

        # Solutions based on mechanism type
        solutions = self._get_physics_solutions(error_message)
        solution_text = "Solutions:\n"
        for i, solution in enumerate(solutions, 1):
            solution_text += f"{i}. {solution}\n"

        solution_display = self.scene.addText(solution_text, details_font)
        solution_display.setDefaultTextColor(QColor(0, 100, 0))
        solution_display.setPos(panel_x + 10, panel_y + 60)
        solution_display.setZValue(91)

        # Controls hint
        controls_text = "🔄 R: Reset & Restart | 🏠 H: Safe Position | Space: Pause/Resume"
        controls = self.scene.addText(controls_text, QFont("Arial", 9))
        controls.setDefaultTextColor(QColor(0, 0, 150))
        controls.setPos(panel_x + 10, panel_y + 190)
        controls.setZValue(91)

        # Store all diagnostic items for cleanup
        self.diagnostic_items = [panel_rect, title_text, details, solution_display, controls]

    def _get_physics_solutions(self, error_message):
        """Get specific solutions based on the error type"""
        solutions = []

        if "Grashof criterion violated" in error_message:
            solutions.extend([
                "Make the Input Link shorter",
                "Adjust the Coupler Link length",
                "Adjust the Output Link length",
                "Grashof rule: Shortest + Longest ≤ Sum of other two links"
            ])
        elif "Links too short to reach" in error_message:
            solutions.extend([
                "Increase the Coupler Link length",
                "Increase the Output Link length",
                "Decrease the Input Link length"
            ])
        elif "Links cannot connect" in error_message:
            solutions.extend([
                "Adjust link length ratios",
                "Reduce difference between Coupler and Output links"
            ])
        elif "singular position" in error_message:
            solutions.extend([
                "Current position is a singularity",
                "Adjust link lengths to avoid singular positions",
                "Try a different starting angle"
            ])
        elif "Connecting rod too short" in error_message:
            solutions.extend([
                "Increase Connecting Rod length",
                "Reduce Crank radius"
            ])
        elif "dead center" in error_message:
            solutions.extend([
                "Currently at dead center position",
                "Rotate crank slightly to escape dead center"
            ])
        else:
            solutions.extend([
                "Try adjusting mechanism parameters",
                "Try a different mechanism type",
                "Reset to default settings"
            ])

        # Add current mechanism parameters for reference
        if self.mechanism_type == "four_bar" and self.mechanism_params:
            solutions.append("Current settings:")
            solutions.append(f"  • Ground Link: {self.mechanism_params.get('ground_link', 0):.0f}")
            solutions.append(f"  • Input Link: {self.mechanism_params.get('input_link', 0):.0f}")
            solutions.append(f"  • Coupler Link: {self.mechanism_params.get('coupler_link', 0):.0f}")
            solutions.append(f"  • Output Link: {self.mechanism_params.get('output_link', 0):.0f}")

        return solutions

    def clear_physics_diagnostic(self):
        """Clear physics diagnostic display"""
        if hasattr(self, 'diagnostic_items'):
            for item in self.diagnostic_items:
                if item.scene():
                    self.scene.removeItem(item)
            delattr(self, 'diagnostic_items')

        if self.physics_status_text and self.physics_status_text.scene():
            self.scene.removeItem(self.physics_status_text)
            self.physics_status_text = None

    def _draw_slider_crank_mechanism_optimized(self):
        """Accurate slider-crank mechanism with proper physics"""
        # Get parameters from mechanism params or use defaults
        crank_length = self.mechanism_params.get("crank_length", 80)
        connecting_rod_length = self.mechanism_params.get("rod_length", 140)

        O1 = QPointF(-50, 0)  # Fixed pivot
        crank_angle = math.radians(self.animation_angle)

        # Crank end position (accurate)
        A = QPointF(
            O1.x() + crank_length * math.cos(crank_angle),
            O1.y() + crank_length * math.sin(crank_angle)
        )

        # Accurate slider position using proper kinematics
        # The slider moves along horizontal line through O1
        crank_x = crank_length * math.cos(crank_angle)
        crank_y = crank_length * math.sin(crank_angle)

        # Calculate slider position using law of cosines
        # rod² = (slider_x - crank_x)² + crank_y²
        # solving for slider_x:
        discriminant = connecting_rod_length**2 - crank_y**2

        if discriminant >= 0:
            # Two solutions - pick the one that gives continuous motion
            slider_offset = math.sqrt(discriminant)
            slider_x = O1.x() + crank_x + slider_offset
        else:
            # Rod too short - clamp to maximum extension
            slider_x = O1.x() + crank_x + connecting_rod_length

        B = QPointF(slider_x, 0)  # Slider moves only horizontally

        # Calculate velocities for more accurate physics
        crank_omega = math.radians(self.animation_speed)  # rad/s

        # Crank tip velocity
        crank_velocity = QPointF(
            -crank_length * crank_omega * math.sin(crank_angle),
            crank_length * crank_omega * math.cos(crank_angle)
        )

        # Slider velocity (horizontal component only)
        if discriminant > 0:
            # d(slider_x)/dt calculation
            slider_velocity = (crank_length * crank_omega *
                              (math.cos(crank_angle) - crank_y * math.sin(crank_angle) / math.sqrt(discriminant)))
        else:
            slider_velocity = crank_length * crank_omega * math.cos(crank_angle)

        # Calculate stress levels based on forces and geometry
        compression_ratio = abs(crank_y) / crank_length  # 0 to 1
        rod_tension = abs(slider_velocity) / (crank_length * crank_omega) if crank_omega > 0 else 0

        # Draw crank with compression stress coloring
        crank_stress = compression_ratio * 0.8
        self._draw_link_optimized(O1, A, "crank", stress=crank_stress)

        # Draw connecting rod with tension stress
        rod_stress = -rod_tension * 0.6  # Negative for tension
        self._draw_link_optimized(A, B, "rod", stress=rod_stress)

        # Draw slider block with proper dimensions
        slider_width = 20
        slider_height = 16
        slider_rect = self.scene.addRect(
            B.x() - slider_width/2, B.y() - slider_height/2,
            slider_width, slider_height,
            QPen(QColor(100, 200, 100), 2),
            QBrush(QColor(150, 220, 150))
        )
        self.mechanism_items["slider"] = slider_rect

        # Draw slider guide rails with proper engineering appearance
        guide_length = 300
        guide_pen = QPen(QColor(120, 120, 120), 4)

        # Upper rail
        upper_rail = self.scene.addLine(-guide_length/2, -8, guide_length/2, -8, guide_pen)
        self.mechanism_items["upper_rail"] = upper_rail

        # Lower rail
        lower_rail = self.scene.addLine(-guide_length/2, 8, guide_length/2, 8, guide_pen)
        self.mechanism_items["lower_rail"] = lower_rail

        # Draw joints with appropriate sizes
        self._draw_joint_optimized(O1, "O", is_fixed=True)  # Fixed pivot
        self._draw_joint_optimized(A, "A", is_fixed=False)  # Pin joint
        self._draw_joint_optimized(B, "B", is_fixed=False)  # Slider joint

        # Calculate and store accurate forces
        self._calculate_slider_crank_forces_accurate(O1, A, B, crank_angle, crank_omega)

    def _draw_cam_follower_mechanism_optimized(self):
        """Accurate cam-follower mechanism with proper egg-shaped cam"""
        # Get parameters
        cam_radius = self.mechanism_params.get("cam_radius", 60)
        cam_offset = self.mechanism_params.get("cam_offset", 20)
        follower_length = self.mechanism_params.get("follower_length", 100)

        cam_center = QPointF(0, 0)
        cam_angle = math.radians(self.animation_angle)

        # Create egg-shaped cam profile using proper mathematical formula
        # Egg shape: radius varies as r = a + b*cos(θ) + c*cos(2θ)
        egg_profile_points = []
        contact_radii = []

        num_points = 72  # 5-degree increments for smooth curve
        for i in range(num_points):
            theta = (i * 2 * math.pi) / num_points

            # Egg-shaped profile equation
            # This creates an asymmetric oval (wider at one end)
            base_radius = cam_radius
            primary_variation = cam_offset * math.cos(theta)
            secondary_variation = (cam_offset * 0.3) * math.cos(2 * theta)

            # Radius at this angle
            radius = base_radius + primary_variation + secondary_variation
            contact_radii.append(radius)

            # Point on cam perimeter
            x = radius * math.cos(theta)
            y = radius * math.sin(theta)
            egg_profile_points.append(QPointF(x, y))

        # Draw main cam disk (structural base)
        cam_base_circle = self.scene.addEllipse(
            cam_center.x() - cam_radius*0.8, cam_center.y() - cam_radius*0.8,
            cam_radius*1.6, cam_radius*1.6,
            QPen(QColor(120, 120, 120), 2),
            QBrush(QColor(180, 180, 180))
        )
        self.mechanism_items["cam_base"] = cam_base_circle

        # Draw the egg-shaped cam profile
        egg_path = QPainterPath()
        if egg_profile_points:
            egg_path.moveTo(egg_profile_points[0])
            for point in egg_profile_points[1:]:
                egg_path.lineTo(point)
            egg_path.closeSubpath()

        # Rotate the entire cam profile
        transform = QTransform()
        transform.translate(cam_center.x(), cam_center.y())
        transform.rotate(math.degrees(cam_angle))
        transform.translate(-cam_center.x(), -cam_center.y())

        egg_path_item = self.scene.addPath(
            egg_path,
            QPen(QColor(160, 120, 80), 3),
            QBrush(QColor(200, 150, 100))
        )
        egg_path_item.setTransform(transform)
        self.mechanism_items["cam_profile"] = egg_path_item

        # Calculate actual follower position based on egg cam
        # Find the contact point at the current cam angle
        contact_angle_index = int((cam_angle * num_points) / (2 * math.pi)) % num_points
        contact_radius = contact_radii[contact_angle_index]

        # The follower contacts the cam at the rightmost point
        follower_contact_angle = 0  # Right side of cam
        rotated_contact_angle = follower_contact_angle + cam_angle

        # Contact point on rotating cam
        contact_x = contact_radius * math.cos(rotated_contact_angle)
        contact_y = contact_radius * math.sin(rotated_contact_angle)
        contact_point = QPointF(contact_x, contact_y)

        # Follower base position (horizontal displacement due to cam profile)
        follower_base_x = cam_radius + 40 + (contact_radius - cam_radius)
        follower_base_y = contact_y  # Vertical position follows cam
        follower_base = QPointF(follower_base_x, follower_base_y)

        # Follower rod extends horizontally
        follower_end = QPointF(follower_base.x() + follower_length, follower_base.y())

        # Calculate stress based on cam curvature and acceleration
        displacement_amplitude = contact_radius - cam_radius
        follower_stress = abs(displacement_amplitude) / cam_offset if cam_offset > 0 else 0

        # Draw follower rod with stress coloring
        self._draw_link_optimized(follower_base, follower_end, "follower", stress=-follower_stress*0.6)

        # Draw follower guide housing (vertical slider that constrains follower motion)
        guide_height = cam_radius * 2.5
        guide_width = 12

        # Left guide rail
        left_guide = self.scene.addRect(
            follower_base_x - 15, -guide_height/2,
            guide_width, guide_height,
            QPen(QColor(100, 100, 100), 2),
            QBrush(QColor(160, 160, 160))
        )
        self.mechanism_items["left_guide"] = left_guide

        # Right guide rail
        right_guide = self.scene.addRect(
            follower_base_x + 5, -guide_height/2,
            guide_width, guide_height,
            QPen(QColor(100, 100, 100), 2),
            QBrush(QColor(160, 160, 160))
        )
        self.mechanism_items["right_guide"] = right_guide

        # Draw follower contact point
        contact_circle = self.scene.addEllipse(
            contact_point.x() - 4, contact_point.y() - 4, 8, 8,
            QPen(QColor(255, 100, 100), 2),
            QBrush(QColor(255, 150, 150))
        )
        self.mechanism_items["contact_point"] = contact_circle

        # Draw follower tip/roller
        follower_tip = self.scene.addEllipse(
            follower_base.x() - 8, follower_base.y() - 8, 16, 16,
            QPen(QColor(200, 100, 100), 2),
            QBrush(QColor(220, 150, 150))
        )
        self.mechanism_items["follower_tip"] = follower_tip

        # Draw return spring (zigzag pattern)
        spring_start = follower_end
        spring_end = QPointF(follower_end.x() + 50, follower_end.y())

        spring_path = QPainterPath()
        spring_path.moveTo(spring_start)

        # Create realistic spring coils
        coil_count = 10
        coil_amplitude = 6
        spring_length = 50

        for i in range(coil_count * 2):
            t = i / (coil_count * 2)
            x = spring_start.x() + t * spring_length
            y_offset = coil_amplitude * math.sin(i * math.pi)
            y = spring_start.y() + y_offset
            spring_path.lineTo(x, y)

        spring_path.lineTo(spring_end)

        spring_item = self.scene.addPath(
            spring_path,
            QPen(QColor(200, 100, 50), 2)
        )
        self.mechanism_items["spring"] = spring_item

        # Draw cam center axis
        axis_circle = self.scene.addEllipse(
            cam_center.x() - 6, cam_center.y() - 6, 12, 12,
            QPen(QColor(80, 80, 80), 2),
            QBrush(QColor(120, 120, 120))
        )
        self.mechanism_items["cam_axis"] = axis_circle

        # Draw joints
        self._draw_joint_optimized(cam_center, "C", is_fixed=True)  # Cam center
        self._draw_joint_optimized(follower_base, "F", is_fixed=False)  # Follower

        # Calculate and store forces
        self._calculate_cam_follower_forces_accurate(
            cam_center, contact_point, follower_end,
            cam_angle, contact_radius, follower_stress
        )

    def _find_safe_four_bar_position(self) -> float:
        """Find a safe starting position for four-bar mechanism using Grashof criterion"""
        # Get current parameters
        a = self.mechanism_params.get("ground_link", 150)  # Ground link
        b = self.mechanism_params.get("input_link", 80)    # Input link
        c = self.mechanism_params.get("coupler_link", 120) # Coupler link
        d = self.mechanism_params.get("output_link", 100)  # Output link

        # Check Grashof condition for valid four-bar linkage
        lengths = [a, b, c, d]
        lengths.sort()
        s, p, q, r = lengths  # s=shortest, r=longest

        # Grashof condition: s + r <= p + q (for continuous rotation)
        grashof_satisfied = (s + r) <= (p + q + 1)  # +1 for tolerance

        if not grashof_satisfied:
            print(f"Warning: Four-bar may have limited motion. Grashof: {s+r} vs {p+q}")

        # Test different starting positions to find a feasible one
        test_angles = [30, 45, 60, 90, 0, 15, 75]  # Priority order

        for angle in test_angles:
            if self._is_four_bar_position_valid(a, b, c, d, angle):
                print(f"Found safe four-bar position: {angle} degrees")
                return angle

        # If no safe position found, return default
        print("Warning: No completely safe position found, using 30 degrees")
        return 30.0

    def _is_four_bar_position_valid(self, a: float, b: float, c: float, d: float, input_angle: float) -> bool:
        """Check if a four-bar position is geometrically valid"""
        try:
            # Try to solve for output angle
            output_angle = self._solve_four_bar_output_angle_fast(a, b, c, d, math.radians(input_angle))

            # If we get a valid solution, check if triangle inequalities are satisfied
            O1 = QPointF(-a/2, 0)
            O4 = QPointF(a/2, 0)
            A = QPointF(O1.x() + b * math.cos(math.radians(input_angle)),
                        O1.y() + b * math.sin(math.radians(input_angle)))
            B = QPointF(O4.x() + d * math.cos(output_angle),
                        O4.y() + d * math.sin(output_angle))

            # Distance between A and B should equal coupler length
            AB_distance = math.sqrt((B.x() - A.x())**2 + (B.y() - A.y())**2)
            error = abs(AB_distance - c)

            return error < 1.0  # Accept small numerical errors

        except:
            return False

    def _ensure_valid_starting_position(self):
        """Ensure the mechanism starts in a valid position"""
        if self.mechanism_type == "four_bar":
            safe_angle = self._find_safe_four_bar_position()
            if abs(self.animation_angle - safe_angle) > 5:  # If current position is not safe
                print(f"Adjusting four-bar from {self.animation_angle}° to safe position {safe_angle}°")
                self.animation_angle = safe_angle
                self.mechanism_params["input_angle"] = safe_angle

    def _calculate_slider_crank_forces_accurate(self, O1, A, B, crank_angle, crank_omega):
        """Calculate accurate forces for slider-crank mechanism"""
        # Physical parameters
        crank_length = self.mechanism_params.get("crank_length", 80) / 1000.0  # Convert to meters
        rod_length = self.mechanism_params.get("rod_length", 140) / 1000.0
        gas_pressure = self.mechanism_params.get("gas_pressure", 500)  # kPa
        piston_area = 0.01  # m² (100 cm²)

        # Calculate gas force on piston
        gas_force = gas_pressure * piston_area  # N

        # Calculate connecting rod angle
        crank_x = crank_length * math.cos(crank_angle)
        crank_y = crank_length * math.sin(crank_angle)

        discriminant = rod_length**2 - crank_y**2
        if discriminant > 0:
            rod_horizontal = math.sqrt(discriminant)
            rod_angle = math.atan2(crank_y, rod_horizontal) if rod_horizontal > 0 else 0
        else:
            rod_angle = math.pi / 2

        # Force analysis
        # Gas force acts horizontally on piston
        piston_force = QPointF(gas_force, 0)

        # Rod force (compression/tension)
        rod_force_magnitude = gas_force / math.cos(rod_angle) if abs(math.cos(rod_angle)) > 0.01 else gas_force
        rod_force = QPointF(
            rod_force_magnitude * math.cos(rod_angle),
            rod_force_magnitude * math.sin(rod_angle)
        )

        # Crank torque
        crank_torque = crank_length * rod_force_magnitude * math.sin(crank_angle - rod_angle)

        # Store forces for display
        self.current_forces = {
            "piston": {"position": B, "force": piston_force, "label": f"Gas: {gas_force:.0f}N"},
            "rod": {"position": QPointF((A.x() + B.x()) / 2, (A.y() + B.y()) / 2),
                   "force": QPointF(rod_force.x() * 0.1, rod_force.y() * 0.1),
                   "label": f"Rod: {rod_force_magnitude:.0f}N"},
            "crank": {"position": QPointF((O1.x() + A.x()) / 2, (O1.y() + A.y()) / 2),
                     "force": QPointF(crank_torque * 0.01, 0),
                     "label": f"Torque: {crank_torque:.1f}Nm"}
        }

    def _calculate_cam_follower_forces_accurate(self, cam_center, contact_point, follower_end,
                                               cam_angle, cam_radius, follower_stress):
        """Calculate accurate forces for cam-follower mechanism"""
        # Physical parameters
        spring_constant = self.mechanism_params.get("spring_constant", 300)  # N/m
        follower_mass = 0.5  # kg
        cam_radius_m = self.mechanism_params.get("cam_radius", 60) / 1000.0  # Convert to meters
        cam_offset_m = self.mechanism_params.get("cam_offset", 20) / 1000.0

        # Calculate follower displacement and velocity
        displacement = cam_offset_m * math.cos(cam_angle)
        velocity = -cam_offset_m * math.radians(self.animation_speed) * math.sin(cam_angle)
        acceleration = -cam_offset_m * (math.radians(self.animation_speed))**2 * math.cos(cam_angle)

        # Forces
        spring_force = spring_constant * displacement  # Spring force
        inertia_force = follower_mass * acceleration   # ma
        contact_force = spring_force + inertia_force   # Contact force on cam

        # Contact normal direction
        normal_angle = cam_angle + math.pi / 2  # Normal to cam surface
        contact_force_vector = QPointF(
            contact_force * math.cos(normal_angle) * 0.01,  # Scale for display
            contact_force * math.sin(normal_angle) * 0.01
        )

        # Spring force vector
        spring_direction = math.atan2(follower_end.y() - contact_point.y(),
                                     follower_end.x() - contact_point.x())
        spring_force_vector = QPointF(
            -spring_force * math.cos(spring_direction) * 0.01,
            -spring_force * math.sin(spring_direction) * 0.01
        )

        # Store forces for display
        self.current_forces = {
            "contact": {
                "position": contact_point,
                "force": contact_force_vector,
                "label": f"Contact: {abs(contact_force):.0f}N"
            },
            "spring": {
                "position": follower_end,
                "force": spring_force_vector,
                "label": f"Spring: {abs(spring_force):.0f}N"
            },
            "inertia": {
                "position": QPointF((contact_point.x() + follower_end.x()) / 2,
                                   (contact_point.y() + follower_end.y()) / 2),
                "force": QPointF(-inertia_force * 0.01 * math.cos(spring_direction),
                                -inertia_force * 0.01 * math.sin(spring_direction)),
                "label": f"Inertia: {abs(inertia_force):.1f}N"
            }
        }

    def _draw_gear_train_mechanism_optimized(self):
        """Gear train with physically plausible pitch meshing and rotation."""
        print(f"DEBUG: _draw_gear_train_mechanism_optimized called! mechanism_type={self.mechanism_type}")

        # Teeth and pitch parameters
        z1 = int(self.mechanism_params.get("gear1_teeth", 24))
        z2 = int(self.mechanism_params.get("gear2_teeth", 36))
        circular_pitch = float(self.mechanism_params.get("tooth_pitch", 8.0))  # length per tooth
        module = circular_pitch / math.pi  # m = p/π

        # Pitch radii
        r1 = 0.5 * module * z1
        r2 = 0.5 * module * z2

        # Centers: respect stored centers if present, but enforce correct distance (r1+r2)
        c1 = self.mechanism_params.get("gear1_center")
        c2 = self.mechanism_params.get("gear2_center")
        if c1 is None or c2 is None:
            gear1_center = QPointF(-r1, 0)
            gear2_center = QPointF(+r2, 0)
        else:
            gear1_center = c1 if isinstance(c1, QPointF) else QPointF(c1[0], c1[1])
            gear2_center = c2 if isinstance(c2, QPointF) else QPointF(c2[0], c2[1])
            vx, vy = gear2_center.x() - gear1_center.x(), gear2_center.y() - gear1_center.y()
            dist = math.hypot(vx, vy)
            target = r1 + r2
            if dist < 1e-6:
                gear2_center = QPointF(gear1_center.x() + target, gear1_center.y())
            else:
                s = target / dist
                gear2_center = QPointF(gear1_center.x() + vx * s, gear1_center.y() + vy * s)

        # Rotation relationship
        gear1_angle = math.radians(self.animation_angle)
        ratio = z1 / z2
        gear2_angle = -gear1_angle * ratio

        # Draw gears using pitch radii and module-based tooth geometry
        self._draw_simple_gear_with_teeth(gear1_center, r1, z1, gear1_angle, True, "DRIVE")
        self._draw_simple_gear_with_teeth(gear2_center, r2, z2, gear2_angle, False, "DRIVEN")

        # Meshing point on pitch circles along line of centers
        vx, vy = gear2_center.x() - gear1_center.x(), gear2_center.y() - gear1_center.y()
        dist = math.hypot(vx, vy) or 1.0
        ux, uy = vx / dist, vy / dist
        mesh_x = gear1_center.x() + ux * r1
        mesh_y = gear1_center.y() + uy * r1

        mesh_point = self.scene.addEllipse(
            mesh_x - 6, mesh_y - 6, 12, 12,
            QPen(QColor(255, 50, 50), 3),
            QBrush(QColor(255, 100, 100))
        )
        mesh_point.setZValue(10)
        self.mechanism_items["mesh_point"] = mesh_point

        mesh_label = self.scene.addText("MESH", QFont("Arial", 10, QFont.Weight.Bold))
        mesh_label.setPos(mesh_x - 15, mesh_y - 30)
        mesh_label.setDefaultTextColor(QColor(255, 0, 0))
        self.mechanism_items["mesh_label"] = mesh_label

        # Rotation arrows (use pitch radii for placement)
        self._draw_simple_rotation_arrow(gear1_center, r1, gear1_angle, QColor(0, 100, 200), "INPUT", True)
        self._draw_simple_rotation_arrow(gear2_center, r2, gear2_angle, QColor(200, 100, 0), "OUTPUT", False)

        # Info text
        info = self.scene.addText(f"RATIO {z1}:{z2} = {ratio:.2f}:1")
        info.setPos(-100, 150)
        info.setDefaultTextColor(QColor(100, 100, 100))
        self.mechanism_items["info"] = info

        # Persist for later interactions
        self.mechanism_params["gear1_center"] = gear1_center
        self.mechanism_params["gear2_center"] = gear2_center
        self.mechanism_params["gear1_pitch_radius"] = r1
        self.mechanism_params["gear2_pitch_radius"] = r2

    def _ensure_parametric_handles(self):
        """Create/update parametric handles for current mechanism."""
        # Toggle visibility quickly
        if hasattr(self, "parametric_handles"):
            for h in self.parametric_handles.values():
                h.setVisible(self.show_parametric_handles)

        if not getattr(self, "show_parametric_handles", True):
            return

        if self.mechanism_type == "four_bar":
            self._ensure_four_bar_handles()
        elif self.mechanism_type == "gear_train":
            self._ensure_gear_handles()
        elif self.mechanism_type == "slider_crank":
            self._ensure_slider_crank_handles()
        elif self.mechanism_type == "cam_follower":
            self._ensure_cam_follower_handles()


    def _ensure_four_bar_handles(self):
        # Current anchors
        if "ground_pivot1" in self.mechanism_params and "ground_pivot2" in self.mechanism_params:
            gp1 = self.mechanism_params["ground_pivot1"]
            gp2 = self.mechanism_params["ground_pivot2"]
            O1 = gp1 if isinstance(gp1, QPointF) else QPointF(gp1[0], gp1[1])
            O4 = gp2 if isinstance(gp2, QPointF) else QPointF(gp2[0], gp2[1])
        else:
            gl = self.mechanism_params.get("ground_link", 150)
            O1 = QPointF(-gl / 2, 0)
            O4 = QPointF(gl / 2, 0)

        def on_move_o1(_, pos: QPointF):
            self.mechanism_params["ground_pivot1"] = QPointF(pos.x(), pos.y())
            gp2 = self.mechanism_params.get("ground_pivot2", O4)
            gp2 = gp2 if isinstance(gp2, QPointF) else QPointF(gp2[0], gp2[1])
            self.mechanism_params["ground_link"] = math.hypot(gp2.x() - pos.x(), gp2.y() - pos.y())
            self.draw_mechanism()

        def on_move_o4(_, pos: QPointF):
            self.mechanism_params["ground_pivot2"] = QPointF(pos.x(), pos.y())
            gp1 = self.mechanism_params.get("ground_pivot1", O1)
            gp1 = gp1 if isinstance(gp1, QPointF) else QPointF(gp1[0], gp1[1])
            self.mechanism_params["ground_link"] = math.hypot(pos.x() - gp1.x(), pos.y() - gp1.y())
            self.draw_mechanism()

        if "anchor_O1" not in self.parametric_handles:
            h = DraggablePointHandle(O1, 6, "anchor_O1", on_move=on_move_o1)
            self.parametric_handles["anchor_O1"] = h
            self.scene.addItem(h)
        if "anchor_O4" not in self.parametric_handles:
            h = DraggablePointHandle(O4, 6, "anchor_O4", on_move=on_move_o4)
            self.parametric_handles["anchor_O4"] = h
            self.scene.addItem(h)

        if not self.parametric_handles["anchor_O1"].isSelected():
            self.parametric_handles["anchor_O1"].setPos(O1)
        if not self.parametric_handles["anchor_O4"].isSelected():
            self.parametric_handles["anchor_O4"].setPos(O4)

    def _ensure_gear_handles(self):
        g1 = self.mechanism_params.get("gear1_center")
        g2 = self.mechanism_params.get("gear2_center")
        if g1 is None or g2 is None:
            t1 = self.mechanism_params.get("gear1_teeth", 24)
            t2 = self.mechanism_params.get("gear2_teeth", 36)
            pitch = self.mechanism_params.get("tooth_pitch", 8.0)
            r1 = (t1 * pitch) / (2 * math.pi)
            r2 = (t2 * pitch) / (2 * math.pi)
            d = r1 + r2
            # Place so pitch point is near origin, preserving asymmetry if radii differ
            g1 = QPointF(-r1, 0)
            g2 = QPointF(+r2, 0)
        else:
            g1 = g1 if isinstance(g1, QPointF) else QPointF(g1[0], g1[1])
            g2 = g2 if isinstance(g2, QPointF) else QPointF(g2[0], g2[1])

        t1 = self.mechanism_params.get("gear1_teeth", 24)
        t2 = self.mechanism_params.get("gear2_teeth", 36)
        pitch = self.mechanism_params.get("tooth_pitch", 8.0)
        r1 = (t1 * pitch) / (2 * math.pi)
        r2 = (t2 * pitch) / (2 * math.pi)
        target_dist = r1 + r2

        def on_move_g1(_, pos: QPointF):
            prev = self.mechanism_params.get("gear1_center", g1)
            prev = prev if isinstance(prev, QPointF) else QPointF(prev[0], prev[1])
            dx, dy = pos.x() - prev.x(), pos.y() - prev.y()
            new_g1 = QPointF(pos.x(), pos.y())
            cur_g2 = self.mechanism_params.get("gear2_center", g2)
            cur_g2 = cur_g2 if isinstance(cur_g2, QPointF) else QPointF(cur_g2[0], cur_g2[1])
            new_g2 = QPointF(cur_g2.x() + dx, cur_g2.y() + dy)
            self.mechanism_params["gear1_center"] = new_g1
            self.mechanism_params["gear2_center"] = new_g2
            self.draw_mechanism()

        def on_move_g2(_, pos: QPointF):
            cur_g1 = self.mechanism_params.get("gear1_center", g1)
            cur_g1 = cur_g1 if isinstance(cur_g1, QPointF) else QPointF(cur_g1[0], cur_g1[1])
            vx, vy = pos.x() - cur_g1.x(), pos.y() - cur_g1.y()
            dist = math.hypot(vx, vy)
            if dist < 1e-6:
                vx, vy, dist = target_dist, 0.0, target_dist
            s = target_dist / dist
            new_g2 = QPointF(cur_g1.x() + vx * s, cur_g1.y() + vy * s)
            self.mechanism_params["gear2_center"] = new_g2
            self.draw_mechanism()

        if "gear1_handle" not in self.parametric_handles:
            h = DraggablePointHandle(g1, 6, "gear1_handle", on_move=on_move_g1)
            self.parametric_handles["gear1_handle"] = h
            self.scene.addItem(h)
        if "gear2_handle" not in self.parametric_handles:
            h = DraggablePointHandle(g2, 6, "gear2_handle", on_move=on_move_g2)
            self.parametric_handles["gear2_handle"] = h
            self.scene.addItem(h)

        if not self.parametric_handles["gear1_handle"].isSelected():
            self.parametric_handles["gear1_handle"].setPos(g1)
        if not self.parametric_handles["gear2_handle"].isSelected():
            self.parametric_handles["gear2_handle"].setPos(g2)

    def _ensure_slider_crank_handles(self):
        # Pivot handle O1
        pivot = self.mechanism_params.get("pivot")
        if pivot is None:
            pivot = QPointF(-50, 0)
        else:
            pivot = pivot if isinstance(pivot, QPointF) else QPointF(pivot[0], pivot[1])

        def on_move_pivot(_, pos: QPointF):
            self.mechanism_params["pivot"] = QPointF(pos.x(), pos.y())
            self.draw_mechanism()

        if "slider_pivot" not in self.parametric_handles:
            h = DraggablePointHandle(pivot, 6, "slider_pivot", on_move=on_move_pivot)
            self.parametric_handles["slider_pivot"] = h
            self.scene.addItem(h)
        if not self.parametric_handles["slider_pivot"].isSelected():
            self.parametric_handles["slider_pivot"].setPos(pivot)

    def _ensure_cam_follower_handles(self):
        cam_center = self.mechanism_params.get("cam_center")
        if cam_center is None:
            cam_center = QPointF(0, 0)
        else:
            cam_center = cam_center if isinstance(cam_center, QPointF) else QPointF(cam_center[0], cam_center[1])

        def on_move_cam(_, pos: QPointF):
            self.mechanism_params["cam_center"] = QPointF(pos.x(), pos.y())
            self.draw_mechanism()

        if "cam_center_handle" not in self.parametric_handles:
            h = DraggablePointHandle(cam_center, 6, "cam_center_handle", on_move=on_move_cam)
            self.parametric_handles["cam_center_handle"] = h
            self.scene.addItem(h)
        if not self.parametric_handles["cam_center_handle"].isSelected():
            self.parametric_handles["cam_center_handle"].setPos(cam_center)





    def _draw_simple_gear_with_teeth(self, center, pitch_radius, teeth, angle, is_drive, label):
        """Draw gear with realistic tooth proportions based on pitch radius."""
        # Gear colors
        if is_drive:
            gear_color = QColor(90, 90, 95)
            tooth_color = QColor(70, 70, 75)
        else:
            gear_color = QColor(130, 130, 135)
            tooth_color = QColor(110, 110, 115)

        # Use actual teeth count
        actual_teeth = teeth
        tooth_angle = 2 * math.pi / actual_teeth

        # Derive geometry from module
        circular_pitch = float(self.mechanism_params.get("tooth_pitch", 8.0))
        module = circular_pitch / math.pi
        addendum = module
        dedendum = 1.25 * module

        pr = float(pitch_radius)
        tip_radius = max(pr + addendum, pr + 1.0)
        root_radius = max(pr - dedendum, max(4.0, pr * 0.5))

        # Main gear body (root circle)
        gear_circle = self.scene.addEllipse(
            center.x() - root_radius, center.y() - root_radius,
            root_radius * 2, root_radius * 2,
            QPen(gear_color.darker(130), 2),
            QBrush(gear_color)
        )

        # Draw realistic trapezoid teeth
        teeth_path = QPainterPath()

        for i in range(actual_teeth):
            current_angle = angle + i * tooth_angle
            tooth_width_angle = tooth_angle * 0.4  # Tooth takes 40% of space

            # Create trapezoid tooth shape
            # Bottom left
            angle1 = current_angle - tooth_width_angle/2
            x1 = center.x() + root_radius * math.cos(angle1)
            y1 = center.y() + root_radius * math.sin(angle1)

            # Top left (narrower)
            angle2 = current_angle - tooth_width_angle/3
            x2 = center.x() + tip_radius * math.cos(angle2)
            y2 = center.y() + tip_radius * math.sin(angle2)

            # Top right (narrower)
            angle3 = current_angle + tooth_width_angle/3
            x3 = center.x() + tip_radius * math.cos(angle3)
            y3 = center.y() + tip_radius * math.sin(angle3)

            # Bottom right
            angle4 = current_angle + tooth_width_angle/2
            x4 = center.x() + root_radius * math.cos(angle4)
            y4 = center.y() + root_radius * math.sin(angle4)

            # Create trapezoid polygon for this tooth
            tooth_points = [
                QPointF(x1, y1),  # Bottom left
                QPointF(x2, y2),  # Top left
                QPointF(x3, y3),  # Top right
                QPointF(x4, y4)   # Bottom right
            ]

            tooth_polygon = QPolygonF(tooth_points)
            teeth_path.addPolygon(tooth_polygon)

        # Draw ALL teeth as single item for performance
        teeth_item = self.scene.addPath(
            teeth_path,
            QPen(tooth_color.darker(120), 1),
            QBrush(tooth_color.lighter(110))
        )

        # Pitch circle (reference line where gears mesh)
        pitch_circle = self.scene.addEllipse(
            center.x() - pr, center.y() - pr,
            pr * 2, pr * 2,
            QPen(QColor(200, 200, 200, 100), 1, Qt.PenStyle.DotLine),
            QBrush(Qt.BrushStyle.NoBrush)
        )

        # Center hub
        hub_radius = tip_radius * 0.2
        hub = self.scene.addEllipse(
            center.x() - hub_radius, center.y() - hub_radius,
            hub_radius * 2, hub_radius * 2,
            QPen(gear_color.darker(160), 2),
            QBrush(gear_color.darker(110))
        )

        # Center axis
        axis_radius = tip_radius * 0.05
        axis = self.scene.addEllipse(
            center.x() - axis_radius, center.y() - axis_radius,
            axis_radius * 2, axis_radius * 2,
            QPen(Qt.PenStyle.NoPen),
            QBrush(QColor(30, 30, 30))
        )

        # Gear label with tooth count
        text = self.scene.addText(f"{label}\n({teeth}T)", QFont("Arial", 11, QFont.Weight.Bold))
        text.setPos(center.x() - 25, center.y() - tip_radius - 50)
        text.setDefaultTextColor(QColor(80, 80, 80))

        # Store items
        gear_name = "gear1" if is_drive else "gear2"
        self.mechanism_items[f"{gear_name}"] = gear_circle
        self.mechanism_items[f"{gear_name}_teeth"] = teeth_item
        self.mechanism_items[f"{gear_name}_pitch"] = pitch_circle
        self.mechanism_items[f"{gear_name}_hub"] = hub
        self.mechanism_items[f"{gear_name}_axis"] = axis
        self.mechanism_items[f"{gear_name}_label"] = text

    def _draw_simple_rotation_arrow(self, center, radius, angle, color, _direction_label, clockwise):
        """Ultra-simple rotation arrow - just one line with arrowhead"""
        arrow_length = 40
        arrow_angle = angle + (math.pi/3 if clockwise else -math.pi/3)

        # Start and end points
        start_x = center.x() + (radius + 15) * math.cos(arrow_angle)
        start_y = center.y() + (radius + 15) * math.sin(arrow_angle)
        end_x = start_x + arrow_length * math.cos(arrow_angle)
        end_y = start_y + arrow_length * math.sin(arrow_angle)

        # Single arrow line
        arrow = self.scene.addLine(start_x, start_y, end_x, end_y, QPen(color, 3))

        # Simple arrowhead - just two short lines
        head_angle1 = arrow_angle + 2.8
        head_angle2 = arrow_angle - 2.8
        head_len = 8

        head1 = self.scene.addLine(
            end_x, end_y,
            end_x - head_len * math.cos(head_angle1),
            end_y - head_len * math.sin(head_angle1),
            QPen(color, 3)
        )
        head2 = self.scene.addLine(
            end_x, end_y,
            end_x - head_len * math.cos(head_angle2),
            end_y - head_len * math.sin(head_angle2),
            QPen(color, 3)
        )

        # Store minimal items
        arrow_name = "input_arrow" if clockwise else "output_arrow"
        self.mechanism_items[f"{arrow_name}"] = arrow
        self.mechanism_items[f"{arrow_name}_h1"] = head1
        self.mechanism_items[f"{arrow_name}_h2"] = head2




    def _calculate_four_bar_forces_optimized(self, O1: QPointF, A: QPointF, B: QPointF, O4: QPointF):
        """Simplified force calculation for performance"""
        self.forces.clear()

        angle = math.radians(self.animation_angle)

        # Simplified force vectors
        input_force = ForceVector(
            position=A,
            magnitude=40 + 10 * math.sin(angle),
            angle=angle + math.pi/2,
            force_type=ForceType.APPLIED,
            label="F_in"
        )
        self.forces.append(input_force)

        # Reaction forces
        reaction_O1 = ForceVector(
            position=O1,
            magnitude=30,
            angle=angle + math.pi,
            force_type=ForceType.REACTION,
            label="R_O1"
        )
        self.forces.append(reaction_O1)




    def _draw_force_vectors_optimized(self):
        """Optimized force vector drawing with persistent arrows"""
        # Initialize persistent force vectors if needed
        if not hasattr(self, 'persistent_force_vectors'):
            self.persistent_force_vectors = {}

        # Get current forces from mechanism calculations
        current_forces = getattr(self, 'current_forces', {})

        # Update or create force vectors
        for force_id, force_data in current_forces.items():
            if force_id not in self.persistent_force_vectors:
                # Create new persistent force vector
                self._create_persistent_force_vector(force_id, force_data)
            else:
                # Update existing force vector position and direction
                self._update_persistent_force_vector(force_id, force_data)

    def _create_persistent_force_vector(self, force_id: str, force_data: dict):
        """Create a persistent force vector that can be updated without redrawing"""
        position = force_data.get('position', QPointF(0, 0))
        force_vector = force_data.get('force', QPointF(10, 0))
        label_text = force_data.get('label', f'F{force_id}')

        # Calculate force properties
        magnitude = math.sqrt(force_vector.x()**2 + force_vector.y()**2)
        if magnitude < 0.1:  # Skip very small forces
            return

        angle = math.atan2(force_vector.y(), force_vector.x())

        # Choose color based on force type
        if 'gas' in label_text.lower() or 'pressure' in label_text.lower():
            color = QColor(255, 100, 100)  # Red for gas forces
        elif 'spring' in label_text.lower():
            color = QColor(100, 255, 100)  # Green for spring forces
        elif 'contact' in label_text.lower():
            color = QColor(100, 100, 255)  # Blue for contact forces
        elif 'torque' in label_text.lower():
            color = QColor(255, 150, 0)    # Orange for torques
        else:
            color = QColor(255, 200, 0)    # Yellow for other forces

        # Scale for visibility
        scale = min(2.0, max(0.5, magnitude / 100.0))  # Adaptive scaling
        end_point = QPointF(
            position.x() + force_vector.x() * scale,
            position.y() + force_vector.y() * scale
        )

        # Create vector line
        pen = QPen(color, 3)
        line = self.scene.addLine(position.x(), position.y(), end_point.x(), end_point.y(), pen)
        line.setZValue(20)

        # Create arrowhead
        arrow_size = 10
        arrow_angle = 0.4

        arrow_p1 = QPointF(
            end_point.x() - arrow_size * math.cos(angle - arrow_angle),
            end_point.y() - arrow_size * math.sin(angle - arrow_angle)
        )
        arrow_p2 = QPointF(
            end_point.x() - arrow_size * math.cos(angle + arrow_angle),
            end_point.y() - arrow_size * math.sin(angle + arrow_angle)
        )

        arrow_polygon = QPolygonF([end_point, arrow_p1, arrow_p2])
        arrow = self.scene.addPolygon(arrow_polygon, pen, QBrush(color))
        arrow.setZValue(21)

        # Create label
        label_font = QFont("Arial", 8, QFont.Weight.Bold)
        label = self.scene.addText(label_text, label_font)
        label.setDefaultTextColor(color.darker(120))

        # Position label
        label_x = end_point.x() + 10
        label_y = end_point.y() - 10
        label.setPos(label_x, label_y)
        label.setZValue(22)

        # Store persistent items
        self.persistent_force_vectors[force_id] = {
            'line': line,
            'arrow': arrow,
            'label': label,
            'color': color,
            'last_position': position,
            'last_force': force_vector,
            'last_magnitude': magnitude
        }

    def _update_persistent_force_vector(self, force_id: str, force_data: dict):
        """Update existing persistent force vector smoothly"""
        vector_items = self.persistent_force_vectors[force_id]

        position = force_data.get('position', QPointF(0, 0))
        force_vector = force_data.get('force', QPointF(10, 0))
        label_text = force_data.get('label', f'F{force_id}')

        # Calculate new properties
        magnitude = math.sqrt(force_vector.x()**2 + force_vector.y()**2)
        if magnitude < 0.1:  # Hide very small forces
            vector_items['line'].setVisible(False)
            vector_items['arrow'].setVisible(False)
            vector_items['label'].setVisible(False)
            return
        else:
            vector_items['line'].setVisible(True)
            vector_items['arrow'].setVisible(True)
            vector_items['label'].setVisible(True)

        # Check if significant change occurred (avoid unnecessary updates)
        pos_change = math.sqrt((position.x() - vector_items['last_position'].x())**2 +
                              (position.y() - vector_items['last_position'].y())**2)
        force_change = abs(magnitude - vector_items['last_magnitude'])

        if pos_change < 1.0 and force_change < 5.0:  # Skip minor changes
            return

        angle = math.atan2(force_vector.y(), force_vector.x())
        color = vector_items['color']

        # Scale for visibility
        scale = min(2.0, max(0.5, magnitude / 100.0))
        end_point = QPointF(
            position.x() + force_vector.x() * scale,
            position.y() + force_vector.y() * scale
        )

        # Update line position
        line = vector_items['line']
        line.setLine(position.x(), position.y(), end_point.x(), end_point.y())

        # Update arrowhead
        arrow_size = 10
        arrow_angle = 0.4

        arrow_p1 = QPointF(
            end_point.x() - arrow_size * math.cos(angle - arrow_angle),
            end_point.y() - arrow_size * math.sin(angle - arrow_angle)
        )
        arrow_p2 = QPointF(
            end_point.x() - arrow_size * math.cos(angle + arrow_angle),
            end_point.y() - arrow_size * math.sin(angle + arrow_angle)
        )

        arrow_polygon = QPolygonF([end_point, arrow_p1, arrow_p2])
        arrow = vector_items['arrow']
        arrow.setPolygon(arrow_polygon)

        # Update label position and text
        label = vector_items['label']
        label.setPlainText(label_text)
        label.setPos(end_point.x() + 10, end_point.y() - 10)

        # Update cached values
        vector_items['last_position'] = position
        vector_items['last_force'] = force_vector
        vector_items['last_magnitude'] = magnitude

    def clear_persistent_force_vectors(self):
        """Clear all persistent force vectors when mechanism changes"""
        if hasattr(self, 'persistent_force_vectors'):
            for force_id, vector_items in self.persistent_force_vectors.items():
                try:
                    if vector_items['line'] and vector_items['line'].scene():
                        self.scene.removeItem(vector_items['line'])
                    if vector_items['arrow'] and vector_items['arrow'].scene():
                        self.scene.removeItem(vector_items['arrow'])
                    if vector_items['label'] and vector_items['label'].scene():
                        self.scene.removeItem(vector_items['label'])
                except:
                    pass  # Item might already be removed

            self.persistent_force_vectors.clear()

    def clear_all_mechanism_graphics(self):
        """Comprehensive clearing of all mechanism-related graphics"""
        # Clear persistent force vectors first
        self.clear_persistent_force_vectors()

        # Clear current forces data
        if hasattr(self, 'current_forces'):
            self.current_forces.clear()

        # Clear mechanism items (this includes joints, links, labels)
        self._clear_mechanism_items()

        # Clear safety zone items
        if hasattr(self, 'safety_zone_items'):
            for item in self.safety_zone_items:
                if item and item.scene():
                    self.scene.removeItem(item)
            self.safety_zone_items.clear()

        # Clear diagnostic items
        if hasattr(self, 'diagnostic_items'):
            for item in self.diagnostic_items:
                if item and item.scene():
                    self.scene.removeItem(item)
            self.diagnostic_items.clear()

        # Clear parametric handles
        if hasattr(self, 'parametric_handles'):
            for handle in self.parametric_handles.values():
                if handle and handle.scene():
                    self.scene.removeItem(handle)
            self.parametric_handles.clear()

        # Clear safety status text
        if hasattr(self, 'safety_status_text') and self.safety_status_text:
            if self.safety_status_text.scene():
                self.scene.removeItem(self.safety_status_text)
            self.safety_status_text = None

        # Clear physics status text
        if hasattr(self, 'physics_status_text') and self.physics_status_text:
            if self.physics_status_text.scene():
                self.scene.removeItem(self.physics_status_text)
            self.physics_status_text = None

        # CRITICAL: Reset physics state to prevent solver issues
        if hasattr(self, '_last_output_angle'):
            delattr(self, '_last_output_angle')
        if hasattr(self, '_assembly_mode'):
            delattr(self, '_assembly_mode')

        # Clear motion trail
        self.motion_trail.clear()


    def _draw_motion_trail_optimized(self):
        """Optimized motion trail drawing"""
        if len(self.motion_trail) < 2:
            return

        # Draw trail with fewer segments for performance
        step = max(1, len(self.motion_trail) // 15)  # Max 15 trail segments

        for i in range(step, len(self.motion_trail), step):
            alpha = int(255 * (i / len(self.motion_trail)))
            color = QColor(255, 215, 0, alpha)
            pen = QPen(color, 2)

            line = self.scene.addLine(
                self.motion_trail[i - step].x(),
                self.motion_trail[i - step].y(),
                self.motion_trail[i].x(),
                self.motion_trail[i].y(),
                pen,
            )
            line.setZValue(-1)
            self.trail_items.append(line)

    def update_animation(self):
        """Ultra-optimized animation update for gear train"""
        # Update angle
        self.animation_angle += self.animation_speed
        if self.animation_angle >= 360:
            self.animation_angle -= 360

        self.mechanism_params["input_angle"] = self.animation_angle

        # PERFORMANCE: Skip heavy operations for gear train
        if self.mechanism_type == "gear_train":
            # Only redraw every 3rd frame for gears (they're circular, less noticeable)
            self.frame_count += 1
            if self.frame_count % 3 == 0:
                self.draw_mechanism()
        else:
            # Full redraw for other mechanisms that need precision
            self.draw_mechanism()



    def _update_four_bar_positions(self):
        """Update only four-bar linkage positions for smooth animation"""
        # Get current parameters
        ground_link = self.mechanism_params.get("ground_link", 150)
        input_link = self.mechanism_params.get("input_link", 80)
        coupler_link = self.mechanism_params.get("coupler_link", 120)
        output_link = self.mechanism_params.get("output_link", 100)

        # Fixed joint positions
        O1 = QPointF(-ground_link/2, 0)
        O4 = QPointF(ground_link/2, 0)

        # Calculate input link position
        input_angle = math.radians(self.animation_angle)
        A = QPointF(
            O1.x() + input_link * math.cos(input_angle),
            O1.y() + input_link * math.sin(input_angle)
        )

        # Solve for output angle using accurate vector loop method
        output_angle = self._solve_four_bar_output_angle_fast(
            ground_link, input_link, coupler_link, output_link, input_angle
        )
        B = QPointF(
            O4.x() + output_link * math.cos(output_angle),
            O4.y() + output_link * math.sin(output_angle)
        )

        # Update existing link line positions if they exist
        if "link_O1A" in self.mechanism_items and self.mechanism_items["link_O1A"]:
            try:
                # Update line positions for links
                if hasattr(self.mechanism_items["link_O1A"], 'setLine'):
                    self.mechanism_items["link_O1A"].setLine(O1.x(), O1.y(), A.x(), A.y())
                if "link_AB" in self.mechanism_items and hasattr(self.mechanism_items["link_AB"], 'setLine'):
                    self.mechanism_items["link_AB"].setLine(A.x(), A.y(), B.x(), B.y())
                if "link_BO4" in self.mechanism_items and hasattr(self.mechanism_items["link_BO4"], 'setLine'):
                    self.mechanism_items["link_BO4"].setLine(B.x(), B.y(), O4.x(), O4.y())
            except (KeyError, AttributeError) as e:
                # If items don't exist or don't have expected methods, redraw
                print(f"Error updating positions: {e}")
                self.draw_mechanism()
                return

        # Update joint visual positions
        if "A" in self.mechanism_items:
            joint_items = self.mechanism_items["A"]
            if isinstance(joint_items, list) and len(joint_items) > 0:
                # The first item is usually the main joint circle
                joint_items[0].setPos(A.x() - 6, A.y() - 6)
                # Update inner circle if it exists
                if len(joint_items) > 1:
                    joint_items[1].setPos(A.x() - 2.4, A.y() - 2.4)

        if "B" in self.mechanism_items:
            joint_items = self.mechanism_items["B"]
            if isinstance(joint_items, list) and len(joint_items) > 0:
                joint_items[0].setPos(B.x() - 6, B.y() - 6)
                if len(joint_items) > 1:
                    joint_items[1].setPos(B.x() - 2.4, B.y() - 2.4)

        # Update motion trail if enabled
        if self.show_motion_trail:
            self.motion_trail.append(B)
            if len(self.motion_trail) > self.max_trail_points:
                self.motion_trail.pop(0)
            # Redraw trail
            self._draw_motion_trail_optimized()

    def _update_slider_crank_positions(self):
        """Update only slider-crank positions"""
        crank_length = self.mechanism_params.get("input_link", 80)
        connecting_rod_length = self.mechanism_params.get("coupler_link", 140)

        O1 = QPointF(-50, 0)
        crank_angle = math.radians(self.animation_angle)

        # Crank end position
        A = QPointF(
            O1.x() + crank_length * math.cos(crank_angle),
            O1.y() + crank_length * math.sin(crank_angle)
        )

        # Accurate slider position
        crank_x = crank_length * math.cos(crank_angle)
        crank_y = crank_length * math.sin(crank_angle)

        discriminant = connecting_rod_length**2 - crank_y**2
        if discriminant >= 0:
            slider_x = O1.x() + crank_x + math.sqrt(discriminant)
        else:
            slider_x = O1.x() + crank_x + connecting_rod_length

        B = QPointF(slider_x, 0)

        # Update positions
        if "crank" in self.mechanism_items:
            self.mechanism_items["crank"].setLine(O1.x(), O1.y(), A.x(), A.y())
        if "rod" in self.mechanism_items:
            self.mechanism_items["rod"].setLine(A.x(), A.y(), B.x(), B.y())
        if "slider" in self.mechanism_items:
            slider_rect = self.mechanism_items["slider"]
            slider_rect.setRect(B.x() - 10, B.y() - 10, 20, 20)

    def _update_cam_follower_positions(self):
        """Update only cam-follower positions"""
        cam_radius = self.mechanism_params.get("cam_radius", 60)
        cam_offset = self.mechanism_params.get("cam_offset", 20)
        follower_length = self.mechanism_params.get("follower_length", 100)

        cam_center = QPointF(0, 0)
        cam_angle = math.radians(self.animation_angle)

        # Cam profile center (eccentric)
        cam_profile_center = QPointF(
            cam_offset * math.cos(cam_angle),
            cam_offset * math.sin(cam_angle)
        )

        # Proper follower displacement using cam profile
        follower_displacement = cam_offset * math.cos(cam_angle)
        follower_base = QPointF(cam_radius + 40, follower_displacement)
        follower_end = QPointF(follower_base.x() + follower_length, follower_base.y())

        # Update cam profile position
        if "cam_profile" in self.mechanism_items:
            profile = self.mechanism_items["cam_profile"]
            profile.setRect(cam_profile_center.x() - 8, cam_profile_center.y() - 8, 16, 16)

        # Update follower position
        if "follower" in self.mechanism_items:
            self.mechanism_items["follower"].setLine(
                follower_base.x(), follower_base.y(),
                follower_end.x(), follower_end.y()
            )

    def _update_gear_train_positions(self):
        """Update only gear train positions"""
        z1 = int(self.mechanism_params.get("gear1_teeth", 24))
        z2 = int(self.mechanism_params.get("gear2_teeth", 36))
        gear1_center = self.mechanism_params.get("gear1_center", QPointF(-60, 0))
        gear2_center = self.mechanism_params.get("gear2_center", QPointF(60, 0))
        gear1_center = gear1_center if isinstance(gear1_center, QPointF) else QPointF(gear1_center[0], gear1_center[1])
        gear2_center = gear2_center if isinstance(gear2_center, QPointF) else QPointF(gear2_center[0], gear2_center[1])

        # Gear rotation with proper speed ratio
        gear1_angle = math.radians(self.animation_angle)
        gear2_angle = -gear1_angle * (z1 / z2)

        # Update gear rotations (if we have rotation indicators)
        # For now, just update any rotating elements
        pass

    def start_animation(self):
        """Start mechanism animation at optimized frame rate"""
        if self.mechanism_type == "gear_train":
            # Slower frame rate for gear train to reduce graphics load
            self.animation_timer.start(33)  # 30 FPS for gears
        else:
            # Standard frame rate for other mechanisms
            self.animation_timer.start(22)  # 45 FPS for others  # ~60 FPS - smooth high-quality animation

    def stop_animation(self):
        """Stop mechanism animation"""
        self.animation_timer.stop()

    def reset_physics_validation(self):
        """Reset physics validation and allow animation to restart"""
        self.physics_valid = True
        self.physics_error_count = 0
        self.animation_angle = 0.0  # Reset to safe starting position
        self.last_valid_angle = 0.0

        # Clear any error messages and diagnostics
        self.clear_physics_diagnostic()

        # Clear mechanism state
        if hasattr(self, '_last_output_angle'):
            delattr(self, '_last_output_angle')

        # Update mechanism parameters
        if self.mechanism_params:
            self.mechanism_params["input_angle"] = 0.0

        # Show success message
        success_font = QFont("Arial", 12, QFont.Weight.Bold)
        success_text = self.scene.addText("✅ Physics Reset - Restarting from Safe Position", success_font)
        success_text.setDefaultTextColor(QColor(0, 150, 0))
        success_text.setPos(-170, -280)
        success_text.setZValue(100)

        # Auto-remove success message after 3 seconds
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(3000, lambda: self.scene.removeItem(success_text) if success_text.scene() else None)

        print("Physics validation reset - animation can restart from safe position")


    # Keep the rest of the methods for compatibility
    def get_mechanism_educational_content(self, mechanism_type: str) -> dict:
        """Get concise, impactful educational content for each mechanism"""
        educational_content = {
            "four_bar": {
                "title": "Four-Bar Linkage",
                "description": "Converts rotary motion to complex curvilinear motion using four rigid links and revolute joints.",
                "applications": [
                    "Automobile suspension systems",
                    "Industrial robot arms",
                    "Windshield wiper mechanisms"
                ]
            },
            "slider_crank": {
                "title": "Slider-Crank Mechanism",
                "description": "Converts rotational motion to linear reciprocating motion. The foundation of internal combustion engines.",
                "applications": [
                    "Car engine pistons",
                    "Reciprocating pumps",
                    "Steam engines"
                ]
            },
            "cam_follower": {
                "title": "Cam-Follower System",
                "description": "Provides precise, programmable motion control through custom cam profiles for automation applications.",
                "applications": [
                    "Engine valve timing",
                    "Manufacturing automation",
                    "Textile machinery"
                ]
            },
            "gear_train": {
                "title": "Gear Train System",
                "description": "Transmits motion and torque between rotating shafts with precise speed ratios and mechanical advantage.",
                "applications": [
                    "Automotive transmissions",
                    "Industrial gearboxes",
                    "Power tools"
                ]
            }
        }

        return educational_content.get(mechanism_type, {
            "title": "Unknown Mechanism",
            "description": "No educational content available for this mechanism type.",
            "applications": []
        })

    def mousePressEvent(self, event):
        """Handle mouse press for interaction"""
        super().mousePressEvent(event)

        # Check if clicking on a draggable handle
        scene_pos = self.mapToScene(event.pos())
        items = self.scene.items(scene_pos)

        for item in items:
            item_id = item.data(0)
            if item_id:
                self.component_selected.emit(str(item_id))
                break

    def mouseMoveEvent(self, event):
        """Handle mouse move for hover effects and dragging"""
        super().mouseMoveEvent(event)

        # Simplified hover handling for performance
        if not self.skip_expensive_operations:
            scene_pos = self.mapToScene(event.pos())
            items = self.scene.items(scene_pos)

            # Show tooltips for components
            for item in items:
                item_id = item.data(0)
                if item_id:
                    QToolTip.showText(event.globalPosition().toPoint(), f"Component: {item_id}")
                    break

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts for mechanism control"""
        from PyQt6.QtCore import Qt

        if event.key() == Qt.Key.Key_R:
            # R key: Reset to start position
            print("User requested reset - returning to start position")
            self.animation_angle = 0.0
            self.mechanism_params["input_angle"] = 0.0
            self.draw_mechanism()

        elif event.key() == Qt.Key.Key_H:
            # H key: Go to home/safe position (45 degrees - typically safe)
            print("User requested safe position")
            self.animation_angle = 45.0
            self.mechanism_params["input_angle"] = 45.0
            self.draw_mechanism()

        elif event.key() == Qt.Key.Key_Space:
            # Space: Toggle animation
            if self.animation_timer.isActive():
                print("Animation paused by user")
                self.stop_animation()
            else:
                print("Animation resumed by user")
                self.start_animation()

        elif event.key() == Qt.Key.Key_S:
            # S key: Toggle safety zones
            self.show_safety_zones = not self.show_safety_zones
            print(f"Safety zones: {'ON' if self.show_safety_zones else 'OFF'}")
            self.draw_mechanism()

        elif event.key() == Qt.Key.Key_A:
            # Toggle parametric handles
            self.show_parametric_handles = not self.show_parametric_handles
            for h in self.parametric_handles.values():
                h.setVisible(self.show_parametric_handles)

        elif event.key() == Qt.Key.Key_D:
            # D key: Move to danger zone (for educational purposes)
            if self.mechanism_type == "four_bar":
                # Move to a position that's likely to cause issues
                self.animation_angle = 180.0  # Often problematic for four-bar
                self.mechanism_params["input_angle"] = 180.0
                self.draw_mechanism()
                print("Moved to potential danger zone for educational demonstration")

        elif event.key() == Qt.Key.Key_1:
            # Number keys: Jump to specific angles for exploration
            self.animation_angle = 0.0
            self.mechanism_params["input_angle"] = 0.0
            self.draw_mechanism()

        elif event.key() == Qt.Key.Key_2:
            self.animation_angle = 90.0
            self.mechanism_params["input_angle"] = 90.0
            self.draw_mechanism()

        elif event.key() == Qt.Key.Key_3:
            self.animation_angle = 180.0
            self.mechanism_params["input_angle"] = 180.0
            self.draw_mechanism()

        elif event.key() == Qt.Key.Key_4:
            self.animation_angle = 270.0
            self.mechanism_params["input_angle"] = 270.0
            self.draw_mechanism()

        else:
            super().keyPressEvent(event)


class EnhancedMacanismTab(QWidget):
    """
    Enhanced mechanism tab with improved UX and force visualization

    Features:
    - Clean, intuitive interface without clipping
    - Real-time force visualization
    - Interactive parameter manipulation
    - Educational tooltips and guides
    - Smooth animations and transitions
    """

    def __init__(self, parent=None):
        # Initialize QWidget first, not the base class
        QWidget.__init__(self, parent)

        self.mechanism_widget = None
        self.control_panel = None
        self.info_panel = None
        self.catalog_controller = None
        self._parameter_specs: dict[str, ParameterSpec] = {}
        self._parameter_sliders: dict[str, QSlider] = {}
        self._parameter_value_labels: dict[str, QLabel] = {}
        self._parameter_scales: dict[str, int] = {}
        self.parameter_group: QGroupBox | None = None
        self.parameter_layout: QVBoxLayout | None = None

        try:
            service = MechanismCatalogService()
            self.catalog_controller = MechanismFoundryController(service)
        except Exception as exc:
            logging.warning("Failed to initialize mechanism catalog: %s", exc)
            self.catalog_controller = None

        # Setup our own UI directly
        self._setup_ui()
        self._connect_signals()

        # Initialize educational content for default mechanism
        if self.mechanism_widget:
            self._update_educational_content(self.mechanism_widget.mechanism_type)

        if self.mechanism_type_combo.count():
            self._apply_catalog_selection()

    def _apply_catalog_selection(self) -> bool:
        if not self.mechanism_widget:
            return False

        item = self.mechanism_type_combo.currentData()
        if not item or not hasattr(item, "mechanism_type"):
            return False

        entry = None
        config = None
        if self.catalog_controller:
            entry = self.catalog_controller.select_mechanism(item.category_key, item.mechanism_key)  # type: ignore[attr-defined]
            config = self.catalog_controller.get_configuration(item.mechanism_type)
        else:
            entry = getattr(item, "entry", None)
            config = MechanismFoundryController.default_configuration(getattr(item, "mechanism_type", None))

        if entry is None or config is None:
            logging.warning("Mechanism configuration unavailable for selection %s", getattr(item, "display_name", item))
            return False

        was_animating = self.mechanism_widget.animation_timer.isActive()
        if was_animating:
            self.mechanism_widget.stop_animation()

        self._parameter_specs = {spec.key: spec for spec in config.parameter_specs}
        self._parameter_sliders.clear()
        self._parameter_value_labels.clear()
        self._parameter_scales.clear()

        self._update_parameters_for_mechanism(config.mechanism_type, specs=config.parameter_specs)
        params = config.initial_parameters()

        if hasattr(self.mechanism_widget, "clear_all_mechanism_graphics"):
            self.mechanism_widget.clear_all_mechanism_graphics()
        self.mechanism_widget.physics_error_count = 0
        self.mechanism_widget.safety_status = "safe"
        self.mechanism_widget.safety_message = ""
        self.mechanism_widget.animation_angle = params.get("input_angle", 30.0)
        self.mechanism_widget.motion_trail.clear()

        params.setdefault("input_angle", self.mechanism_widget.animation_angle)
        self.mechanism_widget.mechanism_params = params
        self.mechanism_widget.mechanism_type = config.mechanism_type

        self._update_educational_from_entry(entry)

        try:
            self.mechanism_widget.draw_mechanism()
        except Exception as exc:
            logging.warning("Failed to draw mechanism %s: %s", entry.key, exc)

        self.mechanism_widget.scene.update()

        if was_animating:
            QTimer.singleShot(200, self.mechanism_widget.start_animation)

        return True

    def _update_educational_from_entry(self, entry):
        if hasattr(self, 'mechanism_title'):
            self.mechanism_title.setText(entry.name)
        if hasattr(self, 'mechanism_desc'):
            self.mechanism_desc.setText(entry.description)
        if hasattr(self, 'applications_display'):
            tags_text = "\n".join(f"• {tag}" for tag in entry.tags)
            self.applications_display.setText(tags_text or "")

        # Note: _setup_ui and _connect_signals are called by setup_tab_specific_ui
        # which is called by the base class

    def _setup_ui(self):
        """Setup the enhanced UI - direct independent layout"""
        print("Setting up Enhanced Mechanism Tab UI (independent)...")

        # Create our own layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Toolbar at top
        toolbar = self._create_toolbar()
        layout.addWidget(toolbar)

        # Main content with horizontal splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Control panel
        self.control_panel = self._create_control_panel()
        splitter.addWidget(self.control_panel)

        # Center: Mechanism visualization
        self.mechanism_widget = InteractiveMechanismWidget()
        print(f"Created mechanism_widget: {self.mechanism_widget}")
        splitter.addWidget(self.mechanism_widget)

        # Right: Information panel
        self.info_panel = self._create_info_panel()
        splitter.addWidget(self.info_panel)

        # Set splitter sizes (prevent text clipping with wider control panel)
        splitter.setSizes([300, 550, 250])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)

        layout.addWidget(splitter)

        # Initial draw and setup
        if self.mechanism_widget:
            print("Drawing initial mechanism...")
            self.mechanism_widget.draw_mechanism()

            # Start with animation paused for better control
            self.mechanism_widget.stop_animation()
            self.play_action.setChecked(False)
            self.play_action.setText("▶ Play")
        else:
            print("ERROR: mechanism_widget is None - cannot draw!")

    def _create_toolbar(self) -> QToolBar:
        """Create main toolbar with actions"""
        toolbar = QToolBar()
        toolbar.setMovable(False)

        # Play/Pause animation
        self.play_action = QAction("▶ Play", self)
        self.play_action.setCheckable(True)
        self.play_action.triggered.connect(self._toggle_animation)
        toolbar.addAction(self.play_action)

        toolbar.addSeparator()

        # Visualization toggles
        forces_action = QAction("🔧 Forces", self)
        forces_action.setCheckable(True)
        forces_action.setChecked(True)
        forces_action.triggered.connect(self._toggle_forces)
        toolbar.addAction(forces_action)

        velocity_action = QAction("➡ Velocity", self)
        velocity_action.setCheckable(True)
        velocity_action.triggered.connect(self._toggle_velocity)
        toolbar.addAction(velocity_action)

        trail_action = QAction("〰 Trail", self)
        trail_action.setCheckable(True)
        trail_action.setChecked(True)
        trail_action.triggered.connect(self._toggle_trail)
        toolbar.addAction(trail_action)

        toolbar.addSeparator()

        # Reset view
        reset_action = QAction("🔄 Reset", self)
        reset_action.triggered.connect(self._reset_view)
        toolbar.addAction(reset_action)

        return toolbar

    def _create_control_panel(self) -> QWidget:
        """Create parameter control panel with proper scrolling"""
        # Create main container
        main_container = QWidget()
        main_container.setFixedWidth(300)  # Increased from 250 to 300 for better text visibility

        # Create scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        # Create content widget for scrollable area
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(8)

        # Mechanism type selector
        type_group = QGroupBox("Mechanism Type")
        type_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 11px;
                color: #333;
                border: 2px solid #ddd;
                border-radius: 5px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px 0 4px;
            }
        """)
        type_layout = QVBoxLayout(type_group)
        type_layout.setContentsMargins(10, 10, 10, 8)

        type_combo = QComboBox()
        if self.catalog_controller:
            mechanism_items = list(self.catalog_controller.list_mechanisms())
        else:
            mechanism_items = list(MechanismFoundryController.fallback_items())
        if mechanism_items:
            for item in mechanism_items:
                type_combo.addItem(item.display_name, item)
        else:
            type_combo.addItem("No mechanisms available", None)
        type_combo.currentTextChanged.connect(self._on_mechanism_changed)
        type_layout.addWidget(type_combo)

        # Store reference for later use
        self.mechanism_type_combo = type_combo
        content_layout.addWidget(type_group)

        # Parameter controls group - START WITH UPDATED FOUR-BAR PARAMETERS (default)
        params_group = QGroupBox("Parameters")
        params_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 11px;
                color: #333;
                border: 2px solid #ddd;
                border-radius: 5px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px 0 4px;
            }
        """)
        # Create layout with updated four-bar parameters matching the image
        params_layout = QVBoxLayout(params_group)
        params_layout.setContentsMargins(10, 10, 10, 8)

        self.parameter_group = params_group
        self.parameter_layout = params_layout

        content_layout.addWidget(params_group)

        # Animation controls group
        anim_group = QGroupBox("Animation")
        anim_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 11px;
                color: #333;
                border: 2px solid #ddd;
                border-radius: 5px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px 0 4px;
            }
        """)
        anim_layout = QVBoxLayout(anim_group)
        anim_layout.setContentsMargins(10, 10, 10, 8)

        # Animation speed
        speed_label = QLabel("Speed:")
        anim_layout.addWidget(speed_label)

        speed_slider = QSlider(Qt.Orientation.Horizontal)
        speed_slider.setRange(1, 10)
        speed_slider.setValue(2)
        speed_slider.valueChanged.connect(self._on_speed_changed)
        anim_layout.addWidget(speed_slider)

        content_layout.addWidget(anim_group)

        # Add stretch to push content to top
        content_layout.addStretch()

        # Set up scroll area
        scroll_area.setWidget(content_widget)

        # Create main layout for container
        main_layout = QVBoxLayout(main_container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll_area)

        return main_container

    def _add_parameter_slider(
        self,
        layout: QVBoxLayout,
        spec: ParameterSpec,
        *,
        current_value: float | None = None,
    ) -> None:
        """Add a parameter slider with label and value display."""
        param_container = QVBoxLayout()

        label_widget = QLabel(f"{spec.label}:")
        label_widget.setWordWrap(True)
        label_widget.setStyleSheet("""
            QLabel {
                font-weight: bold;
                font-size: 11px;
                color: #333;
                margin-bottom: 3px;
            }
        """)
        param_container.addWidget(label_widget)

        slider_layout = QHBoxLayout()
        slider_layout.setContentsMargins(0, 0, 0, 5)

        scale = 1
        if spec.step < 1.0:
            scale = max(1, int(round(1 / spec.step)))

        min_tick = int(round(spec.min_value * scale))
        max_tick = int(round(spec.max_value * scale))
        value = current_value if current_value is not None else spec.default_value
        value_tick = int(round(value * scale))
        value_tick = max(min_tick, min(max_tick, value_tick))

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_tick, max_tick)
        slider.setValue(value_tick)
        slider.setSingleStep(max(1, int(round(spec.step * scale))))
        slider_layout.addWidget(slider)

        value_label = QLabel(self._format_parameter_value(spec, value))
        value_label.setMinimumWidth(60)
        value_label.setStyleSheet("""
            QLabel {
                font-weight: bold;
                font-size: 11px;
                color: #0066cc;
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 3px;
                padding: 2px 4px;
                text-align: center;
            }
        """)
        slider_layout.addWidget(value_label)

        param_container.addLayout(slider_layout)
        layout.addLayout(param_container)

        self._parameter_sliders[spec.key] = slider
        self._parameter_value_labels[spec.key] = value_label
        self._parameter_scales[spec.key] = scale

        slider.valueChanged.connect(lambda ticks, key=spec.key: self._on_parameter_changed(key, ticks))

    def _create_info_panel(self) -> QWidget:
        """Create information panel with enhanced visibility and concise content"""
        panel = QGroupBox("Analysis & Education")
        panel.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 12px;
                color: #333;
                border: 2px solid #ccc;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)

        layout = QVBoxLayout(panel)
        layout.setSpacing(8)

        # Mechanism title - larger and more visible
        self.mechanism_title = QLabel("Four-Bar Linkage")
        self.mechanism_title.setStyleSheet("""
            font-weight: bold;
            font-size: 16px;
            color: #0066cc;
            margin-bottom: 5px;
        """)
        layout.addWidget(self.mechanism_title)

        # Description - more readable
        self.mechanism_desc = QLabel("Converts rotary motion to complex curvilinear motion")
        self.mechanism_desc.setWordWrap(True)
        self.mechanism_desc.setStyleSheet("""
            color: #444;
            font-size: 12px;
            margin-bottom: 8px;
            line-height: 1.4;
        """)
        layout.addWidget(self.mechanism_desc)

        # Key applications - better formatted
        apps_label = QLabel("Key Applications:")
        apps_label.setStyleSheet("""
            font-weight: bold;
            font-size: 12px;
            color: #333;
            margin-top: 5px;
        """)
        layout.addWidget(apps_label)

        self.applications_display = QLabel("• Automobile suspension\n• Robot arms\n• Windshield wipers")
        self.applications_display.setStyleSheet("""
            color: #555;
            font-size: 11px;
            margin-left: 10px;
            line-height: 1.3;
        """)
        self.applications_display.setWordWrap(True)
        layout.addWidget(self.applications_display)

        # Visual guide with better colors and emojis
        tips_label = QLabel("Visual Guide:")
        tips_label.setStyleSheet("""
            font-weight: bold;
            font-size: 12px;
            color: #333;
            margin-top: 8px;
        """)
        layout.addWidget(tips_label)

        tips_text = QLabel(
            "🔴 Red = Compression forces\n"
            "🔵 Blue = Tension forces\n"
            "🟡 Yellow = Motion trail\n"
            "🟠 Orange = Applied forces"
        )
        tips_text.setWordWrap(True)
        tips_text.setStyleSheet("""
            color: #555;
            font-size: 11px;
            margin-left: 10px;
            line-height: 1.4;
        """)
        layout.addWidget(tips_text)

        layout.addStretch()
        return panel

    def _connect_signals(self):
        """Connect widget signals"""
        # Connect mechanism widget signals
        if self.mechanism_widget:

            self.mechanism_widget.force_calculated.connect(self._update_mechanical_advantage_display)

    def _update_mechanical_advantage_display(self):
        """Update mechanical advantage display"""

        if self.mechanism_widget:

            self.mechanism_widget.component_selected.connect(self._on_component_selected)

            # Force initial draw
            QTimer.singleShot(100, self.mechanism_widget.draw_mechanism)

    def _toggle_animation(self, checked: bool):
        """Toggle animation play/pause"""
        if not self.mechanism_widget:
            print("Warning: mechanism_widget is None")
            return

        if checked:
            self.play_action.setText("⏸ Pause")
            self.mechanism_widget.start_animation()
        else:
            self.play_action.setText("▶ Play")
            self.mechanism_widget.stop_animation()

    def _toggle_forces(self, checked: bool):
        """Toggle force visualization"""
        if not self.mechanism_widget:
            print("Warning: mechanism_widget is None in _toggle_forces")
            return

        self.mechanism_widget.show_forces = checked
        self.mechanism_widget.draw_mechanism()

    def _toggle_velocity(self, checked: bool):
        """Toggle velocity vectors"""
        if not self.mechanism_widget:
            print("Warning: mechanism_widget is None in _toggle_velocity")
            return

        self.mechanism_widget.show_velocities = checked
        self.mechanism_widget.draw_mechanism()

    def _toggle_trail(self, checked: bool):
        """Toggle motion trail"""
        if not self.mechanism_widget:
            print("Warning: mechanism_widget is None in _toggle_trail")
            return

        self.mechanism_widget.show_motion_trail = checked
        if not checked:
            self.mechanism_widget.motion_trail.clear()
        self.mechanism_widget.draw_mechanism()

    def _reset_view(self):
        """Reset view to default"""
        if not self.mechanism_widget:
            print("Warning: mechanism_widget is None in _reset_view")
            return

        self.mechanism_widget.animation_angle = 0
        self.mechanism_widget.motion_trail.clear()
        self.mechanism_widget.draw_mechanism()

    def _on_mechanism_changed(self, mechanism_type: str):
        """Handle mechanism type change with parameter updates"""
        if self._apply_catalog_selection():
            return

        logging.warning(
            "Mechanism catalog selection failed for '%s'; falling back to legacy controls",
            mechanism_type,
        )

        if not self.mechanism_widget:
            print("Warning: mechanism_widget is None in _on_mechanism_changed")
            return

        type_map = {
            "Four-Bar Linkage": "four_bar",
            "Slider-Crank": "slider_crank",
            "Cam-Follower": "cam_follower",
            "Gear Train": "gear_train",

        }

        mechanism_key = type_map.get(mechanism_type, "four_bar")
        print(f"DEBUG: Switching mechanism UI from {mechanism_type} to {mechanism_key}")
        print(f"DEBUG: Current mechanism_widget.mechanism_type = {self.mechanism_widget.mechanism_type}")

        # Stop animation during mechanism switch
        was_animating = self.mechanism_widget.animation_timer.isActive()
        if was_animating:
            self.mechanism_widget.stop_animation()

        # STEP 1: Clear parameters FIRST to avoid lingering UI
        print("DEBUG: Clearing old parameter UI...")
        config = MechanismFoundryController.default_configuration(mechanism_key)
        if config:
            self._parameter_specs = {spec.key: spec for spec in config.parameter_specs}
            self._update_parameters_for_mechanism(mechanism_key, specs=config.parameter_specs)
            params = config.initial_parameters()
        else:
            self._parameter_specs.clear()
            self._parameter_sliders.clear()
            self._parameter_value_labels.clear()
            self._parameter_scales.clear()
            params = {}

        # STEP 3: Clear all graphics
        print("DEBUG: Clearing mechanism graphics...")
        self.mechanism_widget.clear_all_mechanism_graphics()

        # STEP 4: Reset physics state
        self.mechanism_widget.physics_error_count = 0
        self.mechanism_widget.safety_status = "safe"
        self.mechanism_widget.safety_message = ""

        # STEP 5: Reset animation state
        self.mechanism_widget.animation_angle = 30.0  # Safe starting position

        # STEP 6: Clear any cached physics data
        if hasattr(self.mechanism_widget, '_last_output_angle'):
            delattr(self.mechanism_widget, '_last_output_angle')
        if hasattr(self.mechanism_widget, 'last_valid_angle'):
            self.mechanism_widget.last_valid_angle = None
        if hasattr(self.mechanism_widget, '_assembly_mode'):
            delattr(self.mechanism_widget, '_assembly_mode')

        # STEP 7: Set the new mechanism type
        old_type = self.mechanism_widget.mechanism_type
        self.mechanism_widget.mechanism_type = mechanism_key
        print(f"DEBUG: Set mechanism type to {mechanism_key}")

        # STEP 7.5: Initialize mechanism parameters for the new type
        if params:
            params.setdefault("input_angle", self.mechanism_widget.animation_angle)
            self.mechanism_widget.mechanism_params = params
        else:
            # Fallback hard-coded defaults if configuration unavailable.
            if mechanism_key == "gear_train":
                self.mechanism_widget.mechanism_params = {
                    "gear1_teeth": 12,
                    "gear2_teeth": 18,
                    "input_torque": 200,
                    "input_angle": self.mechanism_widget.animation_angle,
                }
                self.mechanism_widget.animation_speed = 5.0
            elif mechanism_key == "four_bar":
                self.mechanism_widget.mechanism_params = {
                    "ground_link": 150,
                    "input_link": 40,
                    "coupler_link": 120,
                    "output_link": 130,
                    "input_angle": self.mechanism_widget.animation_angle,
                }
            elif mechanism_key == "slider_crank":
                self.mechanism_widget.mechanism_params = {
                    "crank_length": 80,
                    "rod_length": 140,
                    "gas_pressure": 500,
                    "input_angle": self.mechanism_widget.animation_angle,
                }
            elif mechanism_key == "cam_follower":
                self.mechanism_widget.mechanism_params = {
                    "cam_radius": 60,
                    "cam_offset": 20,
                    "follower_length": 100,
                    "spring_constant": 300,
                    "input_angle": self.mechanism_widget.animation_angle,
                }

        # STEP 8: Update educational content
        self._update_educational_content(mechanism_key)

        # STEP 9: Redraw the mechanism with new parameters
        print("DEBUG: Drawing new mechanism...")
        try:
            self.mechanism_widget.draw_mechanism()
        except Exception as e:
            print(f"Error drawing new mechanism: {e}")
            print(f"ERROR: Failed to draw {mechanism_key}, keeping it anyway to avoid infinite loop")
            # Don't fallback - that causes more problems

        # STEP 10: Force scene update
        self.mechanism_widget.scene.update()

        # STEP 11: Restart animation if it was running
        if was_animating:
            # Use a timer to restart animation after a brief delay
            QTimer.singleShot(200, self.mechanism_widget.start_animation)

        print(f"DEBUG: Mechanism switch to {mechanism_key} completed successfully")

    def _update_parameters_for_mechanism(
        self,
        mechanism_type: str,
        *,
        specs: Sequence[ParameterSpec] | None = None,
        entry=None,
    ) -> None:
        """Update parameter controls for the active mechanism."""
        layout = self.parameter_layout
        params_group = self.parameter_group
        if layout is None or params_group is None:
            return

        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()

        self._parameter_value_labels.clear()
        self._parameter_sliders.clear()
        self._parameter_scales.clear()

        resolved_specs: list[ParameterSpec] = list(specs) if specs else []
        if not resolved_specs and entry is not None and entry.parameters:
            resolved_specs = [
                ParameterSpec(
                    key=param.key,
                    label=param.name,
                    min_value=float(param.min) if param.min is not None else 0.0,
                    max_value=float(param.max) if param.max is not None else float(param.default or 100.0),
                    default_value=float(param.default) if param.default is not None else 0.0,
                    value_type=(param.type or "float"),
                    unit=param.unit,
                )
                for param in entry.parameters.values()
            ]

        if not resolved_specs:
            config = MechanismFoundryController.default_configuration(mechanism_type)
            if config:
                resolved_specs = list(config.parameter_specs)

        if resolved_specs:
            self._parameter_specs = {spec.key: spec for spec in resolved_specs}
            for spec in resolved_specs:
                self._add_parameter_slider(layout, spec)
        else:
            placeholder = QLabel("No parameters available for this mechanism.")
            placeholder.setStyleSheet("color: #555; font-size: 11px;")
            layout.addWidget(placeholder)

        layout.addStretch()

        params_group.updateGeometry()
        params_group.update()
        params_group.repaint()
        self.control_panel.updateGeometry()
        self.control_panel.update()
        self.control_panel.repaint()
        QCoreApplication.processEvents()

    def _on_parameter_changed(self, param_key: str, tick_value: int):
        """Handle parameter slider change."""
        if not self.mechanism_widget:
            logging.warning("mechanism_widget is None in _on_parameter_changed")
            return

        spec = self._parameter_specs.get(param_key)
        if spec is None:
            logging.warning("Unknown parameter key '%s'", param_key)
            return

        scale = self._parameter_scales.get(param_key, 1)
        value = tick_value / scale
        if spec.is_integer:
            value = int(round(value))

        label = self._parameter_value_labels.get(param_key)
        if label:
            label.setText(self._format_parameter_value(spec, value))

        self.mechanism_widget.mechanism_params[param_key] = value
        self.mechanism_widget.draw_mechanism()

    @staticmethod
    def _format_parameter_value(spec: ParameterSpec, value: float) -> str:
        if spec.is_integer:
            return f"{int(round(value))}"
        if spec.step >= 1:
            return f"{value:.0f}"
        if spec.step >= 0.1:
            return f"{value:.1f}"
        return f"{value:.2f}"

    def _on_speed_changed(self, value: int):
        """Handle animation speed change - convert slider value to appropriate speed"""
        if not self.mechanism_widget:
            print("Warning: mechanism_widget is None in _on_speed_changed")
            return

        # Map slider value (1-10) to actual speed (0.1-2.0)
        # This gives us finer control over slow speeds
        speed_map = {
            1: 0.1,   # Very slow
            2: 0.2,   # Slow (default)
            3: 0.3,   #
            4: 0.5,   #
            5: 0.75,  # Medium
            6: 1.0,   #
            7: 1.25,  #
            8: 1.5,   #
            9: 1.75,  #
            10: 2.0   # Fast
        }

        actual_speed = speed_map.get(value, 0.75)  # Default to 0.75
        self.mechanism_widget.animation_speed = actual_speed
        print(f"Animation speed changed to {actual_speed} (slider: {value})")

    def _on_component_selected(self, _component_id: str):
        """Handle component selection"""
        # Could highlight the component or show detailed info
        pass

    def _update_educational_content(self, mechanism_type: str):
        """Update educational content based on current mechanism"""
        if self.catalog_controller and self.catalog_controller.selected_entry:
            self._update_educational_from_entry(self.catalog_controller.selected_entry)
            return

        content = self.mechanism_widget.get_mechanism_educational_content(mechanism_type)

        # Update title and description
        if hasattr(self, 'mechanism_title'):
            self.mechanism_title.setText(content['title'])
        if hasattr(self, 'mechanism_desc'):
            self.mechanism_desc.setText(content['description'])

        # Update applications
        if hasattr(self, 'applications_display') and content['applications']:
            apps_text = ""
            for i, app in enumerate(content['applications'][:3]):  # Show first 3
                apps_text += f"• {app}\n"
            self.applications_display.setText(apps_text.strip())
