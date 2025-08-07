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

import math
from dataclasses import dataclass
from enum import Enum

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QGroupBox,
    QLabel,
    QSlider,
    QComboBox,
    QToolTip,
    QGraphicsView,
    QGraphicsScene,
    QToolBar,
    QPushButton,
    QScrollArea,
    QFrame,
)
from PyQt6.QtCore import (
    Qt,
    QTimer,
    QPointF,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QPainter,
    QPen,
    QBrush,
    QColor,
    QPainterPath,
    QPolygonF,
    QFont,
    QAction,
    QTransform,
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

        # Animation - optimized to 45 FPS
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.update_animation)
        self.animation_angle = 30.0  # Start at 30 degrees - safe position for four-bar mechanisms
        self.animation_speed = 0.75  # Reduced to 1/4 speed for better control and visibility

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
        if self.mechanism_type == "four_bar":
            self._draw_four_bar_mechanism_optimized()
        elif self.mechanism_type == "slider_crank":
            self._draw_slider_crank_mechanism_optimized()
        elif self.mechanism_type == "cam_follower":
            self._draw_cam_follower_mechanism_optimized()
        elif self.mechanism_type == "gear_train":
            self._draw_gear_train_mechanism_optimized()
        elif self.mechanism_type == "scotch_yoke":
            self._draw_scotch_yoke_mechanism_optimized()

        # Draw forces if enabled (persistent vectors - no more blinking!)
        if self.show_forces:
            self._draw_force_vectors_optimized()

        # Draw motion trail if enabled (simplified)
        if self.show_motion_trail:
            self._draw_motion_trail_optimized()

    def _clear_mechanism_items(self):
        """Clear only mechanism-related items, keeping persistent force vectors"""
        # Remove old mechanism items (links, joints, etc.)
        for item in self.mechanism_items.values():
            if hasattr(item, '__iter__') and not isinstance(item, str):
                for sub_item in item:
                    if sub_item and sub_item.scene():
                        self.scene.removeItem(sub_item)
            else:
                if item and item.scene():
                    self.scene.removeItem(item)

        # Clear old force items (but preserve persistent force vectors)
        for item in self.force_items:
            if item and item.scene():
                self.scene.removeItem(item)

        # Remove trail items
        for item in self.trail_items:
            if item and item.scene():
                self.scene.removeItem(item)

        # Clear the collections
        self.mechanism_items.clear()
        self.force_items.clear()  # This is OK since we use persistent_force_vectors now
        self.trail_items.clear()

        # Note: persistent_force_vectors are NOT cleared - they update smoothly!

    def _draw_four_bar_mechanism_optimized(self):
        """Optimized four-bar linkage drawing with proper force calculation"""
        # Default parameters if not set
        if not self.mechanism_params:
            self.mechanism_params = {
                "ground_link": 150,
                "input_link": 80,
                "coupler_link": 120,
                "output_link": 100,
                "input_angle": self.animation_angle,
            }

        # Calculate positions
        ground_link = self.mechanism_params["ground_link"]
        input_link = self.mechanism_params["input_link"]
        coupler_link = self.mechanism_params["coupler_link"]
        output_link = self.mechanism_params["output_link"]
        input_angle = math.radians(self.mechanism_params["input_angle"])

        # Joint positions
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
        self._draw_link_optimized(O1, A, "input_link", stress=input_stress)
        self._draw_link_optimized(A, B, "coupler_link", stress=coupler_stress)
        self._draw_link_optimized(B, O4, "output_link", stress=output_stress)

        # Draw joints with simplified representation
        self._draw_joint_optimized(O1, "O1", is_fixed=True)
        self._draw_joint_optimized(O4, "O4", is_fixed=True)
        self._draw_joint_optimized(A, "A", is_fixed=False)
        self._draw_joint_optimized(B, "B", is_fixed=False)

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
        """Accurate and robust four-bar kinematics with error handling"""
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
            O4y = 0

            # Distance from A to O4
            L = math.sqrt((O4x - Ax)**2 + (O4y - Ay)**2)

            # Check if configuration is geometrically possible
            if L > (r3 + r4) or L < abs(r3 - r4):
                # Return last valid angle if configuration is impossible
                if hasattr(self, '_last_output_angle'):
                    return self._last_output_angle
                else:
                    # Fallback for first calculation
                    return -input_angle * 0.5

            # Calculate output angle using cosine rule
            cos_angle_B = (r3*r3 + r4*r4 - L*L) / (2*r3*r4)
            cos_angle_B = max(-1.0, min(1.0, cos_angle_B))  # Strict clamping

            # Angle from O4 to A
            alpha = math.atan2(Ay - O4y, Ax - O4x)

            # Angle from O4 to B (two possible solutions)
            try:
                beta_numerator = r4*r4 + L*L - r3*r3
                beta_denominator = 2*r4*L

                if abs(beta_denominator) < 1e-10:  # Avoid division by zero
                    beta = 0
                else:
                    cos_beta = beta_numerator / beta_denominator
                    cos_beta = max(-1.0, min(1.0, cos_beta))  # Clamp
                    beta = math.acos(cos_beta)

            except (ValueError, ZeroDivisionError):
                # Numerical issue - use fallback
                beta = 0

            # Two possible solutions
            theta4_1 = alpha + beta
            theta4_2 = alpha - beta

            # Choose solution based on continuity and mechanism type
            if hasattr(self, '_last_output_angle'):
                # Calculate differences, handling angle wrapping
                diff1 = theta4_1 - self._last_output_angle
                diff2 = theta4_2 - self._last_output_angle

                # Normalize differences to [-π, π]
                while diff1 > math.pi:
                    diff1 -= 2*math.pi
                while diff1 < -math.pi:
                    diff1 += 2*math.pi
                while diff2 > math.pi:
                    diff2 -= 2*math.pi
                while diff2 < -math.pi:
                    diff2 += 2*math.pi

                # Choose solution with smaller angular change
                theta4 = theta4_1 if abs(diff1) < abs(diff2) else theta4_2

                # Additional continuity check - if change is too large, mechanism might be in trouble
                if abs(theta4 - self._last_output_angle) > math.pi/2:
                    # Large jump detected - possible singular position
                    print(f"Warning: Large angular jump detected ({abs(theta4 - self._last_output_angle):.2f} rad)")
                    # Keep using the last valid angle to avoid jumps
                    theta4 = self._last_output_angle

            else:
                # First calculation - choose based on typical four-bar behavior
                # For most four-bar linkages, we want the solution that keeps the output link
                # in a reasonable range
                if abs(theta4_1) < abs(theta4_2):
                    theta4 = theta4_1
                else:
                    theta4 = theta4_2

            # Store for next iteration
            self._last_output_angle = theta4

            # Validate the result
            if math.isnan(theta4) or math.isinf(theta4):
                print("Warning: Invalid angle calculated, using fallback")
                return self._last_output_angle if hasattr(self, '_last_output_angle') else 0

            return theta4

        except Exception as e:
            print(f"Error in four-bar calculation: {e}")
            # Return last known good value
            return getattr(self, '_last_output_angle', 0)

    def _validate_four_bar_physics(self, ground, input_l, coupler, output, input_angle):
        """Validate if four-bar mechanism configuration is physically possible"""
        # Check Grashof criterion and geometric constraints
        links = [ground, input_l, coupler, output]
        links.sort()
        s, p, q, l = links  # shortest, two middle, longest

        # Grashof criterion: s + l <= p + q for continuous rotation
        grashof_satisfied = (s + l) <= (p + q + self.physics_tolerance)

        if not grashof_satisfied:
            return False, "Grashof criterion violated - mechanism cannot have continuous rotation"

        # Check if triangle inequality is satisfied (mechanism can be assembled)
        # Position of point A (end of input link)
        Ax = input_l * math.cos(input_angle)
        Ay = input_l * math.sin(input_angle)

        # Distance from A to O4
        L = math.sqrt((ground - Ax)**2 + (0 - Ay)**2)

        # Triangle inequality for coupler and output links
        if L > (coupler + output + self.physics_tolerance):
            return False, f"Links too short to reach - distance {L:.2f} > {coupler + output:.2f}"

        if L < abs(coupler - output) - self.physics_tolerance:
            return False, f"Links cannot connect - distance {L:.2f} < {abs(coupler - output):.2f}"

        # Check for singularities (dead positions)
        # This occurs when links become collinear
        cos_angle_B = (coupler*coupler + output*output - L*L) / (2*coupler*output)
        if abs(cos_angle_B) > (1.0 + self.physics_tolerance):
            return False, f"Invalid cosine value {cos_angle_B:.3f} - mechanism in singular position"

        return True, "Physics valid"

    def _validate_slider_crank_physics(self, crank_length, rod_length, crank_angle):
        """Validate slider-crank mechanism physics"""
        # Check if connecting rod is long enough
        crank_y_displacement = crank_length * abs(math.sin(crank_angle))

        if crank_y_displacement > (rod_length - self.physics_tolerance):
            return False, f"Connecting rod too short - needs {crank_y_displacement:.2f}, has {rod_length:.2f}"

        # Check for dead centers (extreme positions)
        if abs(crank_y_displacement) < self.physics_tolerance and abs(math.cos(crank_angle)) < self.physics_tolerance:
            return False, "Mechanism at dead center position"

        return True, "Physics valid"

    def _evaluate_mechanism_safety(self):
        """Evaluate mechanism safety and return status with educational info"""
        try:
            if self.mechanism_type == "four_bar":
                if not self.mechanism_params:
                    return "safe", "No parameters set"

                return self._evaluate_four_bar_safety(
                    self.mechanism_params.get("ground_link", 150),
                    self.mechanism_params.get("input_link", 80),
                    self.mechanism_params.get("coupler_link", 120),
                    self.mechanism_params.get("output_link", 100),
                    math.radians(self.animation_angle)
                )

            elif self.mechanism_type == "slider_crank":
                return self._evaluate_slider_crank_safety(
                    80,  # crank_length
                    140, # rod_length
                    math.radians(self.animation_angle)
                )

            # Other mechanisms are generally always safe for educational purposes
            elif self.mechanism_type in ["cam_follower", "gear_train", "scotch_yoke"]:
                return "safe", "Mechanism operating normally"

            return "safe", "Unknown mechanism type"

        except Exception as e:
            return "warning", f"Calculation error: {str(e)}"

    def _evaluate_four_bar_safety(self, ground, input_l, coupler, output, input_angle):
        """Evaluate four-bar mechanism safety with detailed feedback"""
        # Check Grashof criterion
        links = [ground, input_l, coupler, output]
        links.sort()
        s, p, q, l = links  # shortest, two middle, longest

        grashof_ratio = (s + l) / (p + q)

        # Position calculations for current angle
        Ax = input_l * math.cos(input_angle)
        Ay = input_l * math.sin(input_angle)
        L = math.sqrt((ground - Ax)**2 + (0 - Ay)**2)

        # Check triangle constraints
        max_reach = coupler + output
        min_reach = abs(coupler - output)
        reach_ratio = L / max_reach if max_reach > 0 else 0

        # Evaluate safety zones
        if grashof_ratio > 1.05:  # Clearly violates Grashof
            return "danger", f"Grashof violation: ratio {grashof_ratio:.2f} > 1.0 (no continuous rotation)"
        elif grashof_ratio > 1.02:  # Close to violation
            return "warning", f"Near Grashof limit: ratio {grashof_ratio:.2f} (may have dead positions)"
        elif L > max_reach:
            return "danger", f"Links cannot reach: distance {L:.1f} > max reach {max_reach:.1f}"
        elif L > max_reach * 0.95:  # Very close to limit
            return "warning", f"Near reach limit: distance {L:.1f}, max reach {max_reach:.1f}"
        elif L < min_reach:
            return "danger", f"Links too close: distance {L:.1f} < min reach {min_reach:.1f}"
        elif L < min_reach * 1.05:  # Close to minimum
            return "warning", f"Near minimum reach: distance {L:.1f}, min reach {min_reach:.1f}"
        else:
            # Check for approaching singular positions
            cos_angle_B = (coupler*coupler + output*output - L*L) / (2*coupler*output)
            if abs(cos_angle_B) > 0.98:  # Very close to ±1
                return "warning", f"Approaching singular position (cos = {cos_angle_B:.3f})"
            elif reach_ratio > 0.9:  # High stress region
                return "warning", f"High stress region (reach ratio: {reach_ratio:.2f})"
            else:
                return "safe", f"Optimal operation (Grashof: {grashof_ratio:.2f}, reach: {reach_ratio:.2f})"

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

    def _draw_four_bar_safety_zones(self):
        """Draw safety zones for four-bar mechanism"""
        if not self.mechanism_params:
            return

        ground_link = self.mechanism_params.get("ground_link", 150)
        input_link = self.mechanism_params.get("input_link", 80)
        coupler_link = self.mechanism_params.get("coupler_link", 120)
        output_link = self.mechanism_params.get("output_link", 100)

        # Draw reachable area (safe zone)
        O1 = QPointF(-ground_link / 2, 0)
        O4 = QPointF(ground_link / 2, 0)

        # Maximum and minimum reach circles from O4
        max_reach = coupler_link + output_link
        min_reach = abs(coupler_link - output_link)

        # Safe zone (green circle)
        safe_pen = QPen(QColor(0, 200, 0, 100), 2, Qt.PenStyle.DashLine)
        safe_brush = QBrush(QColor(0, 255, 0, 20))
        safe_circle = self.scene.addEllipse(
            O4.x() - max_reach * 0.9, O4.y() - max_reach * 0.9,
            max_reach * 0.9 * 2, max_reach * 0.9 * 2,
            safe_pen, safe_brush
        )
        safe_circle.setZValue(-50)
        self.safety_zone_items.append(safe_circle)

        # Warning zone (yellow ring)
        warning_pen = QPen(QColor(255, 165, 0, 120), 2, Qt.PenStyle.DashLine)
        warning_brush = QBrush(QColor(255, 255, 0, 20))
        warning_outer = self.scene.addEllipse(
            O4.x() - max_reach, O4.y() - max_reach,
            max_reach * 2, max_reach * 2,
            warning_pen, warning_brush
        )
        warning_outer.setZValue(-51)
        self.safety_zone_items.append(warning_outer)

        # Danger zone (red area - unreachable)
        danger_pen = QPen(QColor(255, 0, 0, 100), 2, Qt.PenStyle.SolidLine)
        # Draw danger indicators at the edge
        for angle in range(0, 360, 45):
            rad = math.radians(angle)
            x = O4.x() + max_reach * 1.2 * math.cos(rad)
            y = O4.y() + max_reach * 1.2 * math.sin(rad)
            danger_marker = self.scene.addEllipse(x-5, y-5, 10, 10, danger_pen, QBrush(QColor(255, 0, 0, 100)))
            danger_marker.setZValue(-49)
            self.safety_zone_items.append(danger_marker)

        # Current input link position indicator
        current_angle = math.radians(self.animation_angle)
        current_A = QPointF(
            O1.x() + input_link * math.cos(current_angle),
            O1.y() + input_link * math.sin(current_angle)
        )

        # Draw line from current position to O4 to show current reach requirement
        reach_line = self.scene.addLine(
            current_A.x(), current_A.y(), O4.x(), O4.y(),
            QPen(QColor(100, 100, 100, 150), 2, Qt.PenStyle.DotLine)
        )
        reach_line.setZValue(-48)
        self.safety_zone_items.append(reach_line)

        # Add zone labels
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
        """Add educational labels to safety zones"""
        # Safe zone label
        safe_label = self.scene.addText("SAFE ZONE", QFont("Arial", 10, QFont.Weight.Bold))
        safe_label.setDefaultTextColor(QColor(0, 150, 0, 180))
        safe_label.setPos(50, -120)
        safe_label.setZValue(-45)
        self.safety_zone_items.append(safe_label)

        # Warning zone label
        warning_label = self.scene.addText("CAUTION", QFont("Arial", 9))
        warning_label.setDefaultTextColor(QColor(255, 140, 0, 180))
        warning_label.setPos(120, -80)
        warning_label.setZValue(-45)
        self.safety_zone_items.append(warning_label)

        # Danger markers label
        danger_label = self.scene.addText("UNREACHABLE", QFont("Arial", 8))
        danger_label.setDefaultTextColor(QColor(200, 0, 0, 180))
        danger_label.setPos(150, -50)
        danger_label.setZValue(-45)
        self.safety_zone_items.append(danger_label)

    def _update_safety_status_display(self):
        """Update the safety status display"""
        # Remove old status
        if self.safety_status_text and self.safety_status_text.scene():
            self.scene.removeItem(self.safety_status_text)

        # Determine color and icon based on safety status
        if self.safety_status == "safe":
            color = QColor(0, 150, 0)
            icon = "✅"
            status_text = "SAFE OPERATION"
        elif self.safety_status == "warning":
            color = QColor(255, 140, 0)
            icon = "⚠️"
            status_text = "CAUTION ZONE"
        else:  # danger
            color = QColor(200, 0, 0)
            icon = "⚠️"
            status_text = "DANGER ZONE"

        # Create status display
        font = QFont("Arial", 12, QFont.Weight.Bold)
        display_text = f"{icon} {status_text}"
        self.safety_status_text = self.scene.addText(display_text, font)
        self.safety_status_text.setDefaultTextColor(color)
        self.safety_status_text.setPos(-200, 250)  # Bottom left
        self.safety_status_text.setZValue(100)

        # Add detailed message
        if self.safety_message:
            detail_font = QFont("Arial", 9)
            detail_text = self.scene.addText(self.safety_message, detail_font)
            detail_text.setDefaultTextColor(color.darker(120))
            detail_text.setPos(-200, 270)
            detail_text.setZValue(100)

            # Store detail text for cleanup
            if not hasattr(self, 'safety_detail_text'):
                self.safety_detail_text = detail_text
            else:
                if self.safety_detail_text and self.safety_detail_text.scene():
                    self.scene.removeItem(self.safety_detail_text)
                self.safety_detail_text = detail_text

    def _handle_physics_error(self, error_message):
        """Handle physics validation error with detailed user feedback"""
        self.physics_error_count += 1
        print(f"Physics error #{self.physics_error_count}: {error_message}")

        if self.physics_error_count >= self.max_physics_errors:
            print("Maximum physics errors reached - stopping animation")
            self.stop_animation()
            self.physics_valid = False
            self._show_physics_diagnostic(error_message)
        else:
            # Show warning but continue trying
            self._show_physics_status(f"⚠️ Physics Warning: {error_message} (Attempt {self.physics_error_count}/{self.max_physics_errors})", QColor(255, 165, 0))
            # Try to recover by reverting to last valid angle
            print(f"Attempting to recover... reverting to angle {self.last_valid_angle:.1f}°")
            self.animation_angle = self.last_valid_angle

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
        """Accurate gear train with proper gear ratios and tooth engagement"""
        # Get parameters
        gear1_teeth = self.mechanism_params.get("gear1_teeth", 24)
        gear2_teeth = self.mechanism_params.get("gear2_teeth", 36)

        # Calculate gear radii based on teeth (using standard tooth pitch)
        tooth_pitch = 8.0  # mm per tooth (standard)
        gear1_radius = (gear1_teeth * tooth_pitch) / (2 * math.pi)
        gear2_radius = (gear2_teeth * tooth_pitch) / (2 * math.pi)

        # Gear centers positioned for proper meshing
        center_distance = gear1_radius + gear2_radius + 2  # Small clearance
        gear1_center = QPointF(-center_distance / 2, 0)
        gear2_center = QPointF(center_distance / 2, 0)

        # Calculate gear rotations with accurate speed ratio
        gear_ratio = gear1_teeth / gear2_teeth  # Speed ratio (inverse of radius ratio)
        gear1_angle = math.radians(self.animation_angle)
        gear2_angle = -gear1_angle * gear_ratio  # Opposite direction, scaled speed

        # Draw gear 1 (drive gear)
        self._draw_accurate_gear(gear1_center, gear1_radius, gear1_teeth, gear1_angle, True)

        # Draw gear 2 (driven gear)
        self._draw_accurate_gear(gear2_center, gear2_radius, gear2_teeth, gear2_angle, False)

        # Draw gear engagement/contact point
        contact_point = QPointF(
            (gear1_center.x() + gear2_center.x()) / 2,
            0  # Contact along line of centers
        )

        # Small circle to show contact point
        contact_circle = self.scene.addEllipse(
            contact_point.x() - 3, contact_point.y() - 3, 6, 6,
            QPen(QColor(255, 100, 100), 2),
            QBrush(QColor(255, 150, 150))
        )
        self.mechanism_items["contact_point"] = contact_circle

        # Draw center lines
        center_line = self.scene.addLine(
            gear1_center.x(), gear1_center.y(),
            gear2_center.x(), gear2_center.y(),
            QPen(QColor(150, 150, 150), 1, Qt.PenStyle.DashLine)
        )
        self.mechanism_items["center_line"] = center_line

        # Draw joints
        self._draw_joint_optimized(gear1_center, "G1", is_fixed=True)
        self._draw_joint_optimized(gear2_center, "G2", is_fixed=True)

        # Calculate and store gear forces
        self._calculate_gear_train_forces_accurate(
            gear1_center, gear2_center, contact_point,
            gear1_radius, gear2_radius, gear_ratio
        )

    def _draw_accurate_gear(self, center, radius, teeth, angle, is_drive):
        """Draw a gear with accurate tooth profile"""
        # Main gear circle
        gear_color = QColor(180, 180, 180) if is_drive else QColor(160, 160, 160)
        gear_circle = self.scene.addEllipse(
            center.x() - radius, center.y() - radius,
            radius * 2, radius * 2,
            QPen(gear_color.darker(120), 2),
            QBrush(gear_color)
        )

        # Draw gear teeth (simplified as rectangles on circumference)
        tooth_angle = 2 * math.pi / teeth
        tooth_height = radius * 0.15  # Tooth height as fraction of radius

        for i in range(teeth):
            tooth_angle_pos = angle + i * tooth_angle

            # Tooth tip position
            tooth_tip_x = center.x() + (radius + tooth_height) * math.cos(tooth_angle_pos)
            tooth_tip_y = center.y() + (radius + tooth_height) * math.sin(tooth_angle_pos)

            # Draw tooth as small line
            tooth_base_x = center.x() + radius * math.cos(tooth_angle_pos)
            tooth_base_y = center.y() + radius * math.sin(tooth_angle_pos)

            tooth_line = self.scene.addLine(
                tooth_base_x, tooth_base_y,
                tooth_tip_x, tooth_tip_y,
                QPen(gear_color.darker(140), 1.5)
            )

        # Store gear items
        gear_name = "gear1" if is_drive else "gear2"
        self.mechanism_items[gear_name] = gear_circle

    def _calculate_gear_train_forces_accurate(self, gear1_center, gear2_center, contact_point,
                                             gear1_radius, gear2_radius, gear_ratio):
        """Calculate accurate forces for gear train"""
        # Physical parameters
        input_torque = self.mechanism_params.get("input_torque", 200)  # Nm
        efficiency = 0.95  # Gear efficiency

        # Calculate output torque
        output_torque = input_torque * gear_ratio * efficiency

        # Calculate contact force at gear interface
        # T = F * r, so F = T / r
        contact_force_magnitude = input_torque / (gear1_radius / 1000.0)  # Convert to meters

        # Contact force direction (perpendicular to line of centers)
        force_angle = math.atan2(gear2_center.y() - gear1_center.y(),
                                gear2_center.x() - gear1_center.x()) + math.pi / 2

        contact_force_vector = QPointF(
            contact_force_magnitude * math.cos(force_angle) * 0.001,  # Scale for display
            contact_force_magnitude * math.sin(force_angle) * 0.001
        )

        # Reaction forces at bearings
        bearing_force = contact_force_magnitude * 0.7  # Approximation

        # Store forces for display
        self.current_forces = {
            "contact": {
                "position": contact_point,
                "force": contact_force_vector,
                "label": f"Contact: {contact_force_magnitude:.0f}N"
            },
            "input_torque": {
                "position": gear1_center,
                "force": QPointF(input_torque * 0.01, 0),
                "label": f"T₁: {input_torque:.0f}Nm"
            },
            "output_torque": {
                "position": gear2_center,
                "force": QPointF(-output_torque * 0.01, 0),
                "label": f"T₂: {output_torque:.0f}Nm"
            }
        }

    def _draw_gear_optimized(self, center: QPointF, radius: float, angle: float, color: QColor):
        """Simplified gear drawing - just circle and rotation indicator"""
        # Main gear body (simple circle)
        gear_circle = self.scene.addEllipse(
            center.x() - radius, center.y() - radius,
            radius * 2, radius * 2,
            QPen(color, 2),
            QBrush(color.lighter(150))
        )

        # Rotation indicator
        indicator_length = radius * 0.8
        indicator_x = center.x() + indicator_length * math.cos(angle)
        indicator_y = center.y() + indicator_length * math.sin(angle)

        indicator_line = self.scene.addLine(
            center.x(), center.y(), indicator_x, indicator_y,
            QPen(color.darker(150), 3)
        )

        self.mechanism_items[f"gear_{center.x()}"] = [gear_circle, indicator_line]

    def _draw_scotch_yoke_mechanism_optimized(self):
        """Accurate scotch yoke mechanism with proper harmonic motion"""
        # Get parameters
        crank_radius = self.mechanism_params.get("crank_radius", 60)
        yoke_mass = self.mechanism_params.get("yoke_mass", 5)  # kg

        crank_center = QPointF(-100, 0)
        crank_angle = math.radians(self.animation_angle)

        # Crank pin position (rotates in circle)
        pin_position = QPointF(
            crank_center.x() + crank_radius * math.cos(crank_angle),
            crank_center.y() + crank_radius * math.sin(crank_angle)
        )

        # Draw crank arm
        crank_stress = abs(math.sin(crank_angle)) * 0.5
        self._draw_link_optimized(crank_center, pin_position, "crank_arm", stress=crank_stress)

        # Draw crank pin
        pin_circle = self.scene.addEllipse(
            pin_position.x() - 8, pin_position.y() - 8, 16, 16,
            QPen(QColor(200, 100, 100), 2),
            QBrush(QColor(220, 150, 150))
        )
        self.mechanism_items["crank_pin"] = pin_circle

        # Yoke position - pin moves in vertical slot, yoke moves horizontally
        # This is the key insight: scotch yoke converts rotation to pure harmonic motion
        yoke_displacement = crank_radius * math.cos(crank_angle)  # Harmonic displacement
        yoke_center = QPointF(50 + yoke_displacement, 0)

        # Draw yoke body (rectangular block)
        yoke_width = 60
        yoke_height = 30
        yoke_rect = self.scene.addRect(
            yoke_center.x() - yoke_width/2, yoke_center.y() - yoke_height/2,
            yoke_width, yoke_height,
            QPen(QColor(100, 150, 200), 2),
            QBrush(QColor(150, 180, 220))
        )
        self.mechanism_items["yoke"] = yoke_rect

        # Draw vertical slot in yoke where pin moves
        slot_width = 20
        slot_height = yoke_height + 10
        slot_rect = self.scene.addRect(
            yoke_center.x() - slot_width/2, yoke_center.y() - slot_height/2,
            slot_width, slot_height,
            QPen(QColor(80, 80, 80), 1),
            QBrush(QColor(240, 240, 240))  # Light background
        )
        self.mechanism_items["yoke_slot"] = slot_rect

        # Draw connecting rod from pin to yoke (vertical motion only)
        connecting_point = QPointF(yoke_center.x(), pin_position.y())

        # Horizontal connection from pin to yoke center line
        horizontal_connection = self.scene.addLine(
            pin_position.x(), pin_position.y(),
            yoke_center.x(), pin_position.y(),
            QPen(QColor(120, 120, 120), 3, Qt.PenStyle.DashLine)
        )
        self.mechanism_items["connection"] = horizontal_connection

        # Draw yoke guide rails
        rail_length = 200
        rail_y_offset = 40

        # Upper rail
        upper_rail = self.scene.addLine(
            -50, rail_y_offset, rail_length - 50, rail_y_offset,
            QPen(QColor(140, 140, 140), 4)
        )
        self.mechanism_items["upper_rail"] = upper_rail

        # Lower rail
        lower_rail = self.scene.addLine(
            -50, -rail_y_offset, rail_length - 50, -rail_y_offset,
            QPen(QColor(140, 140, 140), 4)
        )
        self.mechanism_items["lower_rail"] = lower_rail

        # Draw motion indicator arrow
        velocity = -crank_radius * math.radians(self.animation_speed) * math.sin(crank_angle)
        if abs(velocity) > 0.1:
            arrow_length = min(abs(velocity) * 2, 30)
            arrow_direction = 1 if velocity > 0 else -1

            arrow_end = QPointF(yoke_center.x() + arrow_direction * arrow_length, yoke_center.y())
            self._draw_velocity_arrow(yoke_center, arrow_end, f"v={abs(velocity):.1f}")

        # Draw joints
        self._draw_joint_optimized(crank_center, "O", is_fixed=True)
        self._draw_joint_optimized(pin_position, "P", is_fixed=False)

        # Calculate and store forces
        self._calculate_scotch_yoke_forces_accurate(
            crank_center, pin_position, yoke_center,
            crank_angle, crank_radius, yoke_mass
        )

    def _draw_velocity_arrow(self, start, end, label):
        """Draw velocity arrow with label"""
        # Arrow line
        arrow_line = self.scene.addLine(
            start.x(), start.y(), end.x(), end.y(),
            QPen(QColor(0, 150, 255), 3)
        )

        # Arrowhead
        arrow_length = 8
        angle = math.atan2(end.y() - start.y(), end.x() - start.x())

        # Arrow points
        arrow_p1 = QPointF(
            end.x() - arrow_length * math.cos(angle - math.pi/6),
            end.y() - arrow_length * math.sin(angle - math.pi/6)
        )
        arrow_p2 = QPointF(
            end.x() - arrow_length * math.cos(angle + math.pi/6),
            end.y() - arrow_length * math.sin(angle + math.pi/6)
        )

        arrow_head = QPolygonF([end, arrow_p1, arrow_p2])
        arrow_head_item = self.scene.addPolygon(
            arrow_head,
            QPen(QColor(0, 150, 255), 2),
            QBrush(QColor(0, 150, 255))
        )

        # Label
        text_item = self.scene.addText(label, QFont("Arial", 8))
        text_item.setPos(end.x() + 5, end.y() - 15)
        text_item.setDefaultTextColor(QColor(0, 120, 200))

        self.mechanism_items["velocity_arrow"] = arrow_line
        self.mechanism_items["velocity_head"] = arrow_head_item
        self.mechanism_items["velocity_label"] = text_item

    def _calculate_scotch_yoke_forces_accurate(self, crank_center, pin_position, yoke_center,
                                              crank_angle, crank_radius, yoke_mass):
        """Calculate accurate forces for scotch yoke mechanism"""
        # Kinematics
        omega = math.radians(self.animation_speed)  # rad/s

        # Position, velocity, acceleration (harmonic motion)
        displacement = crank_radius * math.cos(crank_angle)
        velocity = -crank_radius * omega * math.sin(crank_angle)
        acceleration = -crank_radius * omega**2 * math.cos(crank_angle)

        # Forces
        applied_force = self.mechanism_params.get("applied_force", 400)  # N
        inertia_force = yoke_mass * acceleration  # F = ma
        total_force = applied_force + inertia_force

        # Crank pin force (perpendicular to crank arm)
        pin_force_angle = crank_angle + math.pi / 2
        pin_force_magnitude = abs(total_force / math.sin(crank_angle)) if abs(math.sin(crank_angle)) > 0.1 else total_force

        pin_force_vector = QPointF(
            pin_force_magnitude * math.cos(pin_force_angle) * 0.01,  # Scale for display
            pin_force_magnitude * math.sin(pin_force_angle) * 0.01
        )

        # Store forces for display
        self.current_forces = {
            "applied": {
                "position": yoke_center,
                "force": QPointF(applied_force * 0.01, 0),
                "label": f"Applied: {applied_force:.0f}N"
            },
            "inertia": {
                "position": yoke_center,
                "force": QPointF(-inertia_force * 0.01, 0),
                "label": f"Inertia: {abs(inertia_force):.0f}N"
            },
            "pin": {
                "position": pin_position,
                "force": pin_force_vector,
                "label": f"Pin: {pin_force_magnitude:.0f}N"
            }
        }

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

    def _calculate_slider_crank_forces(self, O1: QPointF, A: QPointF, B: QPointF, crank_angle: float):
        """Calculate forces in slider-crank mechanism"""
        self.forces.clear()

        # Input torque force (tangential to crank)
        torque_magnitude = 40 + 15 * abs(math.sin(crank_angle * 2))  # Varying torque
        torque_force_angle = crank_angle + math.pi/2  # Perpendicular to crank
        input_force = ForceVector(
            position=A,
            magnitude=torque_magnitude,
            angle=torque_force_angle,
            force_type=ForceType.APPLIED,
            label="F_torque"
        )
        self.forces.append(input_force)

        # Gas pressure force on piston (horizontal)
        gas_pressure = 35 + 20 * math.cos(crank_angle)  # Simulates combustion cycle
        gas_force_direction = 0 if gas_pressure > 0 else math.pi  # Left or right
        gas_force = ForceVector(
            position=B,
            magnitude=abs(gas_pressure),
            angle=gas_force_direction,
            force_type=ForceType.APPLIED,
            label="F_gas"
        )
        self.forces.append(gas_force)

        # Connecting rod force (along the rod)
        rod_angle = math.atan2(B.y() - A.y(), B.x() - A.x())
        rod_force_magnitude = 25 + 10 * abs(math.sin(crank_angle))
        rod_force = ForceVector(
            position=A,
            magnitude=rod_force_magnitude,
            angle=rod_angle,
            force_type=ForceType.CONSTRAINT,
            label="F_rod"
        )
        self.forces.append(rod_force)

        # Reaction force at crank pivot
        reaction_magnitude = 30 + 15 * abs(math.cos(crank_angle))
        reaction_angle = crank_angle + math.pi + 0.2  # Slightly offset
        reaction_force = ForceVector(
            position=O1,
            magnitude=reaction_magnitude,
            angle=reaction_angle,
            force_type=ForceType.REACTION,
            label="R_O1"
        )
        self.forces.append(reaction_force)

        # Side force on piston (normal to slider motion)
        if abs(math.sin(crank_angle)) > 0.1:  # Avoid near-zero values
            side_force_magnitude = 15 * abs(math.sin(crank_angle))
            side_force_angle = math.pi/2 if math.sin(crank_angle) > 0 else -math.pi/2
            side_force = ForceVector(
                position=B,
                magnitude=side_force_magnitude,
                angle=side_force_angle,
                force_type=ForceType.CONSTRAINT,
                label="F_side"
            )
            self.forces.append(side_force)

        # Emit force data for the info panel
        force_data = {
            "torque_force": torque_magnitude,
            "gas_pressure": abs(gas_pressure),
            "rod_force": rod_force_magnitude,
            "reaction_force": reaction_magnitude,
            "side_force": 15 * abs(math.sin(crank_angle)) if abs(math.sin(crank_angle)) > 0.1 else 0
        }
        self.force_calculated.emit(force_data)

    def _calculate_cam_follower_forces(self, cam_center: QPointF, cam_profile: QPointF, follower_base: QPointF, follower_end: QPointF, cam_angle: float):
        """Calculate forces in cam-follower mechanism"""
        self.forces.clear()

        # Cam rotation torque
        torque_magnitude = 25 + 10 * abs(math.sin(cam_angle * 2))
        torque_angle = cam_angle + math.pi/2
        cam_torque = ForceVector(
            position=cam_profile,
            magnitude=torque_magnitude,
            angle=torque_angle,
            force_type=ForceType.APPLIED,
            label="F_cam"
        )
        self.forces.append(cam_torque)

        # Contact force between cam and follower
        contact_magnitude = 20 + 15 * abs(math.sin(cam_angle))
        contact_angle = math.atan2(follower_base.y() - cam_profile.y(), follower_base.x() - cam_profile.x())
        contact_force = ForceVector(
            position=cam_profile,
            magnitude=contact_magnitude,
            angle=contact_angle,
            force_type=ForceType.CONSTRAINT,
            label="F_contact"
        )
        self.forces.append(contact_force)

        # Follower inertia force (vertical motion)
        follower_acceleration = abs(math.sin(cam_angle)) * 20  # Approximate acceleration
        inertia_magnitude = follower_acceleration * 0.8  # Mass factor
        inertia_angle = math.pi/2 if math.sin(cam_angle) > 0 else -math.pi/2
        inertia_force = ForceVector(
            position=follower_base,
            magnitude=inertia_magnitude,
            angle=inertia_angle,
            force_type=ForceType.APPLIED,
            label="F_inertia"
        )
        self.forces.append(inertia_force)

        # Spring return force (if follower is displaced upward)
        displacement = follower_base.y()
        if abs(displacement) > 1:
            spring_magnitude = abs(displacement) * 0.5
            spring_angle = -math.pi/2 if displacement > 0 else math.pi/2
            spring_force = ForceVector(
                position=follower_end,
                magnitude=spring_magnitude,
                angle=spring_angle,
                force_type=ForceType.APPLIED,
                label="F_spring"
            )
            self.forces.append(spring_force)

        # Guide reaction force
        if abs(displacement) > 0.1:
            guide_magnitude = 12 + 8 * abs(displacement) / 20
            guide_angle = 0 if displacement > 0 else math.pi
            guide_force = ForceVector(
                position=follower_base,
                magnitude=guide_magnitude,
                angle=guide_angle,
                force_type=ForceType.REACTION,
                label="R_guide"
            )
            self.forces.append(guide_force)

        # Emit force data
        force_data = {
            "cam_torque": torque_magnitude,
            "contact_force": contact_magnitude,
            "inertia_force": inertia_magnitude,
            "spring_force": abs(displacement) * 0.5 if abs(displacement) > 1 else 0,
            "guide_reaction": 12 + 8 * abs(displacement) / 20 if abs(displacement) > 0.1 else 0
        }
        self.force_calculated.emit(force_data)

    def _calculate_gear_train_forces(self, g1_center: QPointF, g2_center: QPointF, g3_center: QPointF,
                                   mesh1_point: QPointF, mesh2_point: QPointF,
                                   g1_angle: float, g2_angle: float, g3_angle: float,
                                   teeth1: int, teeth2: int, teeth3: int):
        """Calculate forces in gear train mechanism"""
        self.forces.clear()

        # Input torque on gear 1
        input_torque = 35 + 10 * abs(math.sin(g1_angle * 2))
        input_torque_angle = g1_angle + math.pi/2
        # Convert torque to tangential force
        input_force_pos = QPointF(
            g1_center.x() + 25 * math.cos(input_torque_angle),
            g1_center.y() + 25 * math.sin(input_torque_angle)
        )
        input_force = ForceVector(
            position=input_force_pos,
            magnitude=input_torque,
            angle=input_torque_angle,
            force_type=ForceType.APPLIED,
            label="T_in"
        )
        self.forces.append(input_force)

        # Mesh force at gear 1-2 interface
        mesh1_magnitude = 25 + 8 * abs(math.cos(g1_angle))
        mesh1_angle = math.atan2(g2_center.y() - g1_center.y(), g2_center.x() - g1_center.x()) + math.pi/2
        mesh1_force = ForceVector(
            position=mesh1_point,
            magnitude=mesh1_magnitude,
            angle=mesh1_angle,
            force_type=ForceType.CONSTRAINT,
            label="F_mesh1"
        )
        self.forces.append(mesh1_force)

        # Mesh force at gear 2-3 interface
        mesh2_magnitude = 20 + 6 * abs(math.sin(g2_angle))
        mesh2_angle = math.atan2(g3_center.y() - g2_center.y(), g3_center.x() - g2_center.x()) + math.pi/2
        mesh2_force = ForceVector(
            position=mesh2_point,
            magnitude=mesh2_magnitude,
            angle=mesh2_angle,
            force_type=ForceType.CONSTRAINT,
            label="F_mesh2"
        )
        self.forces.append(mesh2_force)

        # Output torque on gear 3 (scaled by gear ratio)
        gear_ratio_total = (teeth1 / teeth2) * (teeth2 / teeth3)
        output_torque = input_torque * gear_ratio_total * 0.95  # 95% efficiency
        output_torque_angle = g3_angle + math.pi/2
        output_force_pos = QPointF(
            g3_center.x() + 20 * math.cos(output_torque_angle),
            g3_center.y() + 20 * math.sin(output_torque_angle)
        )
        output_force = ForceVector(
            position=output_force_pos,
            magnitude=output_torque * 0.7,  # Scale for visualization
            angle=output_torque_angle,
            force_type=ForceType.APPLIED,
            label="T_out"
        )
        self.forces.append(output_force)

        # Bearing reaction forces
        bearing1_magnitude = 18 + 5 * abs(math.sin(g1_angle))
        bearing1_force = ForceVector(
            position=g1_center,
            magnitude=bearing1_magnitude,
            angle=g1_angle + math.pi,
            force_type=ForceType.REACTION,
            label="R_1"
        )
        self.forces.append(bearing1_force)

        bearing2_magnitude = 22 + 7 * abs(math.cos(g2_angle))
        bearing2_force = ForceVector(
            position=g2_center,
            magnitude=bearing2_magnitude,
            angle=g2_angle + math.pi + 0.3,
            force_type=ForceType.REACTION,
            label="R_2"
        )
        self.forces.append(bearing2_force)

        # Emit force data
        force_data = {
            "input_torque": input_torque,
            "output_torque": output_torque,
            "mesh1_force": mesh1_magnitude,
            "mesh2_force": mesh2_magnitude,
            "gear_ratio": gear_ratio_total
        }
        self.force_calculated.emit(force_data)

    def _calculate_scotch_yoke_forces(self, crank_center: QPointF, pin_pos: QPointF, yoke_center: QPointF, rod_end: QPointF, crank_angle: float):
        """Calculate forces in scotch yoke mechanism"""
        self.forces.clear()

        # Input torque on crank
        torque_magnitude = 30 + 12 * abs(math.sin(crank_angle * 1.5))
        torque_angle = crank_angle + math.pi/2
        crank_torque = ForceVector(
            position=pin_pos,
            magnitude=torque_magnitude,
            angle=torque_angle,
            force_type=ForceType.APPLIED,
            label="T_crank"
        )
        self.forces.append(crank_torque)

        # Vertical constraint force from pin on yoke
        pin_vertical_force = abs(60 * math.sin(crank_angle))  # Harmonic force
        if abs(math.sin(crank_angle)) > 0.05:
            pin_force_angle = math.pi/2 if math.sin(crank_angle) > 0 else -math.pi/2
            pin_force = ForceVector(
                position=pin_pos,
                magnitude=pin_vertical_force,
                angle=pin_force_angle,
                force_type=ForceType.CONSTRAINT,
                label="F_pin"
            )
            self.forces.append(pin_force)

        # Horizontal output force
        horizontal_force = 40 * abs(math.cos(crank_angle))
        if abs(math.cos(crank_angle)) > 0.05:
            horizontal_angle = 0 if math.cos(crank_angle) > 0 else math.pi
            output_force = ForceVector(
                position=rod_end,
                magnitude=horizontal_force,
                angle=horizontal_angle,
                force_type=ForceType.APPLIED,
                label="F_output"
            )
            self.forces.append(output_force)

        # Inertia force on yoke (harmonic motion)
        yoke_velocity = 60 * math.cos(crank_angle)  # Velocity is derivative of position
        yoke_acceleration = -60 * math.sin(crank_angle)  # Acceleration is derivative of velocity
        inertia_magnitude = abs(yoke_acceleration) * 0.3  # Mass factor
        if inertia_magnitude > 1:
            inertia_angle = 0 if yoke_acceleration > 0 else math.pi
            inertia_force = ForceVector(
                position=yoke_center,
                magnitude=inertia_magnitude,
                angle=inertia_angle,
                force_type=ForceType.APPLIED,
                label="F_inertia"
            )
            self.forces.append(inertia_force)

        # Guide reaction forces (normal to motion)
        guide_reaction = 15 + 10 * abs(math.sin(crank_angle))
        if abs(pin_pos.y()) > 2:  # Only when there's significant vertical displacement
            guide_angle = -math.pi/2 if pin_pos.y() > 0 else math.pi/2
            guide_force_upper = ForceVector(
                position=QPointF(yoke_center.x(), yoke_center.y() + 15),
                magnitude=guide_reaction,
                angle=guide_angle,
                force_type=ForceType.REACTION,
                label="R_guide"
            )
            self.forces.append(guide_force_upper)

        # Bearing reaction at crank center
        bearing_magnitude = 25 + 8 * abs(math.cos(crank_angle))
        bearing_angle = crank_angle + math.pi + 0.2
        bearing_force = ForceVector(
            position=crank_center,
            magnitude=bearing_magnitude,
            angle=bearing_angle,
            force_type=ForceType.REACTION,
            label="R_bearing"
        )
        self.forces.append(bearing_force)

        # Emit force data
        force_data = {
            "crank_torque": torque_magnitude,
            "pin_force": pin_vertical_force,
            "output_force": horizontal_force if abs(math.cos(crank_angle)) > 0.05 else 0,
            "inertia_force": inertia_magnitude if inertia_magnitude > 1 else 0,
            "guide_reaction": guide_reaction if abs(pin_pos.y()) > 2 else 0
        }
        self.force_calculated.emit(force_data)

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
        # Clear persistent force vectors
        self.clear_persistent_force_vectors()

        # Clear current forces data
        if hasattr(self, 'current_forces'):
            self.current_forces.clear()

        # Clear mechanism items more thoroughly
        self._clear_mechanism_items()

        # Clear any remaining graphics by type
        all_items = self.scene.items()
        items_to_remove = []

        for item in all_items:
            # Skip grid items and background
            if hasattr(item, 'data') and item.data(0) == 'grid':
                continue
            if hasattr(item, 'data') and item.data(0) == 'background':
                continue

            # Remove mechanism-related items
            item_type = type(item).__name__
            if any(keyword in item_type.lower() for keyword in ['line', 'ellipse', 'polygon', 'text', 'path']):
                items_to_remove.append(item)

        # Remove collected items
        for item in items_to_remove:
            try:
                if item.scene():
                    self.scene.removeItem(item)
            except:
                pass

    def _draw_force_vector_simple(self, force: ForceVector):
        """Enhanced force vector drawing for better visibility"""
        # Scale factor for better visibility
        scale = 1.5  # Increased from 1.0

        # Calculate end point
        fx, fy = force.to_components()
        end_point = QPointF(force.position.x() + fx * scale, force.position.y() + fy * scale)

        # Use thicker, more visible lines
        pen = QPen(force.color, 3)  # Increased from 2
        line = self.scene.addLine(
            force.position.x(), force.position.y(), end_point.x(), end_point.y(), pen
        )
        line.setZValue(20)
        self.force_items.append(line)

        # Larger, more visible arrowhead
        arrow_size = 12  # Increased from 8
        arrow_angle = 0.5  # Slightly wider arrow

        arrow_p1 = QPointF(
            end_point.x() - arrow_size * math.cos(force.angle - arrow_angle),
            end_point.y() - arrow_size * math.sin(force.angle - arrow_angle),
        )
        arrow_p2 = QPointF(
            end_point.x() - arrow_size * math.cos(force.angle + arrow_angle),
            end_point.y() - arrow_size * math.sin(force.angle + arrow_angle),
        )

        arrow_polygon = QPolygonF([end_point, arrow_p1, arrow_p2])
        arrow = self.scene.addPolygon(arrow_polygon, pen, QBrush(force.color))
        arrow.setZValue(21)
        self.force_items.append(arrow)

        # Add force magnitude label for better understanding
        if force.label and not self.skip_expensive_operations:
            label_font = QFont("Arial", 9, QFont.Weight.Bold)
            label_text = f"{force.label}\n{force.magnitude:.0f}N"
            label = self.scene.addText(label_text, label_font)
            label.setDefaultTextColor(force.color.darker(120))

            # Position label away from the vector
            label_offset = 15
            label_x = (force.position.x() + end_point.x()) / 2 + label_offset
            label_y = (force.position.y() + end_point.y()) / 2 - label_offset
            label.setPos(label_x, label_y)
            label.setZValue(22)
            self.force_items.append(label)

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
        """Smooth animation update with reduced blinking"""
        # Update angle smoothly
        self.animation_angle += self.animation_speed
        if self.animation_angle >= 360:
            self.animation_angle -= 360

        self.mechanism_params["input_angle"] = self.animation_angle

        # Evaluate safety status
        self.safety_status, self.safety_message = self._evaluate_mechanism_safety()

        # Only redraw if parameters have changed or safety status changed
        # This reduces blinking significantly
        current_params_hash = hash(tuple(sorted(self.mechanism_params.items())))
        if (current_params_hash != getattr(self, '_last_params_hash', None) or
            self.safety_status != getattr(self, '_last_safety_status', None)):

            # Draw mechanism with optimized rendering
            self.draw_mechanism()

            # Update safety status display
            self._update_safety_status_display()

            # Cache current state
            self._last_params_hash = current_params_hash
            self._last_safety_status = self.safety_status
        else:
            # Just update positions without full redraw - smoother animation
            self._update_mechanism_positions_only()

    def _update_mechanism_positions_only(self):
        """Update only positions without full redraw to reduce blinking"""
        if self.mechanism_type == "four_bar":
            self._update_four_bar_positions()
        elif self.mechanism_type == "slider_crank":
            self._update_slider_crank_positions()
        elif self.mechanism_type == "cam_follower":
            self._update_cam_follower_positions()
        elif self.mechanism_type == "gear_train":
            self._update_gear_train_positions()
        elif self.mechanism_type == "scotch_yoke":
            self._update_scotch_yoke_positions()

    def _update_four_bar_positions(self):
        """Update only four-bar linkage positions"""
        # Get current parameters
        a = self.mechanism_params.get("ground_link", 150)
        b = self.mechanism_params.get("input_link", 80)
        c = self.mechanism_params.get("coupler_link", 120)
        d = self.mechanism_params.get("output_link", 100)

        # Joint positions
        O1 = QPointF(-a/2, 0)
        O4 = QPointF(a/2, 0)

        input_angle = math.radians(self.animation_angle)
        A = QPointF(O1.x() + b * math.cos(input_angle), O1.y() + b * math.sin(input_angle))

        # Solve for output angle using accurate vector loop method
        output_angle = self._solve_four_bar_output_angle_fast(a, b, c, d, input_angle)
        B = QPointF(O4.x() + d * math.cos(output_angle), O4.y() + d * math.sin(output_angle))

        # Update existing items positions if they exist
        if "link_O1A" in self.mechanism_items and self.mechanism_items["link_O1A"]:
            # Update line positions for links
            self.mechanism_items["link_O1A"].setLine(O1.x(), O1.y(), A.x(), A.y())
            self.mechanism_items["link_AB"].setLine(A.x(), A.y(), B.x(), B.y())
            self.mechanism_items["link_BO4"].setLine(B.x(), B.y(), O4.x(), O4.y())

            # Update joint positions
            if "joint_A" in self.mechanism_items:
                joint_A = self.mechanism_items["joint_A"]
                joint_A.setPos(A.x() - 6, A.y() - 6)
            if "joint_B" in self.mechanism_items:
                joint_B = self.mechanism_items["joint_B"]
                joint_B.setPos(B.x() - 6, B.y() - 6)

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
        gear1_radius = self.mechanism_params.get("gear1_radius", 50)
        gear2_radius = self.mechanism_params.get("gear2_radius", 30)

        gear1_center = QPointF(-60, 0)
        gear2_center = QPointF(60, 0)

        # Gear rotation with proper speed ratio
        gear_ratio = gear1_radius / gear2_radius
        gear1_angle = math.radians(self.animation_angle)
        gear2_angle = -gear1_angle * gear_ratio  # Opposite direction, scaled speed

        # Update gear rotations (if we have rotation indicators)
        # For now, just update any rotating elements
        pass

    def _update_scotch_yoke_positions(self):
        """Update only scotch yoke positions"""
        crank_radius = self.mechanism_params.get("crank_radius", 60)

        crank_center = QPointF(-100, 0)
        crank_angle = math.radians(self.animation_angle)

        # Crank pin position
        pin_position = QPointF(
            crank_center.x() + crank_radius * math.cos(crank_angle),
            crank_center.y() + crank_radius * math.sin(crank_angle)
        )

        # Yoke position (horizontal displacement only)
        yoke_center = QPointF(pin_position.x() + 100, 0)

        # Update positions
        if "crank_pin" in self.mechanism_items:
            pin = self.mechanism_items["crank_pin"]
            pin.setRect(pin_position.x() - 8, pin_position.y() - 8, 16, 16)

        if "yoke" in self.mechanism_items:
            yoke = self.mechanism_items["yoke"]
            yoke.setRect(yoke_center.x() - 30, yoke_center.y() - 15, 60, 30)

    def start_animation(self):
        """Start mechanism animation at optimized 45 FPS for performance/quality balance"""
        self.animation_timer.start(16)  # ~60 FPS - smooth high-quality animation

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

    def restart_animation(self):
        """Restart animation after physics reset"""
        self.reset_physics_validation()
        self.start_animation()

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
            },
            "scotch_yoke": {
                "title": "Scotch Yoke Mechanism",
                "description": "Converts rotational motion to perfect harmonic linear motion. Produces sinusoidal displacement patterns.",
                "applications": [
                    "Steam engine crossheads",
                    "Control valve actuators",
                    "Testing machines"
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

        # Setup our own UI directly
        self._setup_ui()
        self._connect_signals()

        # Initialize educational content for default mechanism
        if self.mechanism_widget:
            self._update_educational_content(self.mechanism_widget.mechanism_type)

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
        type_combo.addItems([
            "Four-Bar Linkage",
            "Slider-Crank",
            "Cam-Follower",
            "Gear Train",
            "Scotch Yoke"
        ])
        type_combo.currentTextChanged.connect(self._on_mechanism_changed)
        type_layout.addWidget(type_combo)
        content_layout.addWidget(type_group)

        # Parameter controls group
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
        params_layout = QVBoxLayout(params_group)
        params_layout.setContentsMargins(10, 10, 10, 8)

        # Ground link
        self._add_parameter_slider(params_layout, "Ground Link", 50, 200, 150)

        # Input link
        self._add_parameter_slider(params_layout, "Input Link", 30, 120, 80)

        # Coupler link
        self._add_parameter_slider(params_layout, "Coupler Link", 50, 150, 120)

        # Output link
        self._add_parameter_slider(params_layout, "Output Link", 40, 130, 100)

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

    def _add_parameter_slider(self, layout, label: str, min_val: int, max_val: int, default: int):
        """Add a parameter slider with label and value display - improved text visibility"""
        # Use vertical layout for better text visibility
        param_container = QVBoxLayout()

        # Parameter label on top
        label_widget = QLabel(f"{label}:")
        label_widget.setWordWrap(True)  # Allow text wrapping
        label_widget.setStyleSheet("""
            QLabel {
                font-weight: bold;
                font-size: 11px;
                color: #333;
                margin-bottom: 3px;
            }
        """)
        param_container.addWidget(label_widget)

        # Slider and value on same line
        slider_layout = QHBoxLayout()
        slider_layout.setContentsMargins(0, 0, 0, 5)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_val, max_val)
        slider.setValue(default)
        slider.setObjectName(label.lower().replace(" ", "_").replace("(", "").replace(")", ""))
        slider_layout.addWidget(slider)

        value_label = QLabel(str(default))
        value_label.setMinimumWidth(40)  # Slightly wider for larger numbers
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

        # Connect slider events
        slider.valueChanged.connect(lambda v: value_label.setText(str(v)))
        slider.valueChanged.connect(lambda v: self._on_parameter_changed(label, v))

        layout.addLayout(param_container)

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
        if not self.mechanism_widget:
            print("Warning: mechanism_widget is None in _on_mechanism_changed")
            return

        type_map = {
            "Four-Bar Linkage": "four_bar",
            "Slider-Crank": "slider_crank",
            "Cam-Follower": "cam_follower",
            "Gear Train": "gear_train",
            "Scotch Yoke": "scotch_yoke",
        }

        mechanism_key = type_map.get(mechanism_type, "four_bar")
        self.mechanism_widget.mechanism_type = mechanism_key

        # Update parameters based on mechanism type
        self._update_parameters_for_mechanism(mechanism_key)

        # Update educational content
        self._update_educational_content(mechanism_key)

        # Clear everything completely before switching mechanism
        self.mechanism_widget.motion_trail.clear()
        self.mechanism_widget.clear_all_mechanism_graphics()
        self.mechanism_widget.draw_mechanism()

    def _update_parameters_for_mechanism(self, mechanism_type: str):
        """Update parameter controls based on mechanism type"""
        # Find the parameters group box in the scrollable content
        params_group = None

        # Search more thoroughly for the Parameters group
        all_group_boxes = self.control_panel.findChildren(QGroupBox)
        for group_box in all_group_boxes:
            if group_box.title() == "Parameters":
                params_group = group_box
                break

        if not params_group:
            print(f"Warning: Could not find Parameters group box. Found groups: {[g.title() for g in all_group_boxes]}")
            return

        # Clear the existing layout
        layout = params_group.layout()
        if layout:
            # Remove all widgets from layout
            while layout.count():
                child = layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
        else:
            layout = QVBoxLayout(params_group)

        # Add mechanism-specific parameters with proper mapping
        if mechanism_type == "four_bar":
            self._add_parameter_slider(layout, "Ground Link", 50, 200, 150)
            self._add_parameter_slider(layout, "Input Link", 30, 120, 80)
            self._add_parameter_slider(layout, "Coupler Link", 50, 150, 120)
            self._add_parameter_slider(layout, "Output Link", 40, 130, 100)

        elif mechanism_type == "slider_crank":
            self._add_parameter_slider(layout, "Crank Length", 40, 120, 80)
            self._add_parameter_slider(layout, "Rod Length", 80, 200, 140)
            self._add_parameter_slider(layout, "Gas Pressure (kPa)", 100, 1000, 500)

        elif mechanism_type == "cam_follower":
            self._add_parameter_slider(layout, "Cam Radius", 30, 100, 60)
            self._add_parameter_slider(layout, "Cam Offset", 10, 40, 20)
            self._add_parameter_slider(layout, "Follower Length", 50, 150, 100)
            self._add_parameter_slider(layout, "Spring Force (N)", 100, 1000, 300)

        elif mechanism_type == "gear_train":
            self._add_parameter_slider(layout, "Drive Gear Teeth", 12, 60, 24)
            self._add_parameter_slider(layout, "Driven Gear Teeth", 12, 60, 36)
            self._add_parameter_slider(layout, "Input Torque (Nm)", 50, 500, 200)

        elif mechanism_type == "scotch_yoke":
            self._add_parameter_slider(layout, "Crank Radius", 30, 100, 60)
            self._add_parameter_slider(layout, "Yoke Mass (kg)", 1, 20, 5)
            self._add_parameter_slider(layout, "Applied Force (N)", 100, 1000, 400)

        # Force layout update
        params_group.updateGeometry()
        self.control_panel.update()

    def _on_parameter_changed(self, param_name: str, value: int):
        """Handle parameter slider change with comprehensive mapping"""
        if not self.mechanism_widget:
            print("Warning: mechanism_widget is None in _on_parameter_changed")
            return

        # Comprehensive parameter mapping for all mechanisms
        param_map = {
            # Four-bar linkage
            "Ground Link": "ground_link",
            "Input Link": "input_link",
            "Coupler Link": "coupler_link",
            "Output Link": "output_link",

            # Slider-crank
            "Crank Length": "crank_length",
            "Rod Length": "rod_length",
            "Gas Pressure (kPa)": "gas_pressure",

            # Cam-follower
            "Cam Radius": "cam_radius",
            "Cam Offset": "cam_offset",
            "Follower Length": "follower_length",
            "Spring Force (N)": "spring_constant",

            # Gear train
            "Drive Gear Teeth": "gear1_teeth",
            "Driven Gear Teeth": "gear2_teeth",
            "Input Torque (Nm)": "input_torque",

            # Scotch yoke
            "Crank Radius": "crank_radius",
            "Yoke Mass (kg)": "yoke_mass",
            "Applied Force (N)": "applied_force"
        }

        param_key = param_map.get(param_name)
        if param_key:
            self.mechanism_widget.mechanism_params[param_key] = value
            print(f"Updated {param_key} = {value}")
            self.mechanism_widget.draw_mechanism()
        else:
            print(f"Warning: Unknown parameter '{param_name}'")

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

    def _on_component_selected(self, component_id: str):
        """Handle component selection"""
        # Could highlight the component or show detailed info
        pass

    def _update_educational_content(self, mechanism_type: str):
        """Update educational content based on current mechanism"""
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

    def _calculate_mechanical_advantage(self, mechanism_type: str) -> str:
        """Calculate mechanical advantage for current mechanism"""
        if not self.mechanism_widget:
            return "N/A"

        try:
            angle = math.radians(self.mechanism_widget.animation_angle)

            if mechanism_type == "four_bar":
                # For four-bar, MA varies with position
                input_link = self.mechanism_widget.mechanism_params.get("input_link", 80)
                output_link = self.mechanism_widget.mechanism_params.get("output_link", 100)
                ma = (output_link / input_link) * abs(math.sin(angle))
                return f"{ma:.2f}"

            elif mechanism_type == "slider_crank":
                # For slider-crank, MA depends on crank angle
                ma = 1 / abs(math.cos(angle)) if abs(math.cos(angle)) > 0.1 else "∞"
                return f"{ma:.2f}" if ma != "∞" else ma

            elif mechanism_type == "gear_train":
                # For gears, MA is constant and equals gear ratio
                return "2.29"  # Based on our gear teeth ratios

            elif mechanism_type == "cam_follower":
                # For cam-follower, MA varies with cam profile
                return f"{1 + abs(math.sin(angle)):.2f}"

            elif mechanism_type == "scotch_yoke":
                # For scotch yoke, pure harmonic motion
                return f"{abs(math.cos(angle)):.2f}"

        except Exception as e:
            print(f"Error calculating MA: {e}")

        return "N/A"
