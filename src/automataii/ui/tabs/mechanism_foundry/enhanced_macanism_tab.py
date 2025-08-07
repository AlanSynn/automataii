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
        self.animation_angle = 0.0
        self.animation_speed = 3.0  # Increased speed for better visual

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

        # Draw forces if enabled (skip every 3rd frame for performance)
        if self.show_forces and not self.skip_expensive_operations:
            self._draw_force_vectors_optimized()

        # Draw motion trail if enabled (simplified)
        if self.show_motion_trail:
            self._draw_motion_trail_optimized()

    def _clear_mechanism_items(self):
        """Clear only mechanism-related items, keeping grid and safety zones"""
        # Remove old mechanism items
        for items_list in [self.mechanism_items.values(), self.force_items, self.trail_items]:
            for item in items_list:
                if hasattr(item, '__iter__') and not isinstance(item, str):
                    for sub_item in item:
                        if sub_item.scene():
                            self.scene.removeItem(sub_item)
                else:
                    if item.scene():
                        self.scene.removeItem(item)
        
        self.mechanism_items.clear()
        self.force_items.clear()
        self.trail_items.clear()

    def _draw_four_bar_mechanism_optimized(self):
        """Optimized four-bar linkage drawing"""
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

        # Calculate joint B position using simplified kinematics for performance
        output_angle = self._solve_four_bar_output_angle_fast(
            ground_link, input_link, coupler_link, output_link, input_angle
        )

        B = QPointF(
            O4.x() + output_link * math.cos(output_angle),
            O4.y() + output_link * math.sin(output_angle),
        )

        # Simplified stress calculation
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

        # Calculate forces less frequently
        if not self.skip_expensive_operations:
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
        """Optimized slider-crank mechanism"""
        # Simplified parameters
        crank_length = 80
        connecting_rod_length = 140
        
        O1 = QPointF(-50, 0)
        crank_angle = math.radians(self.animation_angle)
        
        # Crank end position
        A = QPointF(
            O1.x() + crank_length * math.cos(crank_angle),
            O1.y() + crank_length * math.sin(crank_angle)
        )
        
        # Simplified slider position calculation
        slider_x = O1.x() + crank_length * math.cos(crank_angle) + \
                  math.sqrt(max(0, connecting_rod_length**2 - (crank_length * math.sin(crank_angle))**2))
        B = QPointF(slider_x, 0)
        
        # Simplified drawing
        self._draw_link_optimized(O1, A, "crank", stress=0.5)
        self._draw_link_optimized(A, B, "rod", stress=-0.3)
        
        # Simplified slider block
        slider_rect = self.scene.addRect(B.x() - 10, B.y() - 10, 20, 20, 
                                       QPen(QColor(100, 200, 100), 2), 
                                       QBrush(QColor(100, 200, 100)))
        self.mechanism_items["slider"] = slider_rect
        
        # Joints
        self._draw_joint_optimized(O1, "O", is_fixed=True)
        self._draw_joint_optimized(A, "A", is_fixed=False)
        self._draw_joint_optimized(B, "B", is_fixed=False)

    def _draw_cam_follower_mechanism_optimized(self):
        """Optimized cam-follower mechanism"""
        cam_radius = 60
        cam_offset = 20
        follower_length = 100
        
        cam_center = QPointF(0, 0)
        cam_angle = math.radians(self.animation_angle)
        
        # Simplified cam (just main circle)
        cam_circle = self.scene.addEllipse(
            cam_center.x() - cam_radius, cam_center.y() - cam_radius,
            cam_radius * 2, cam_radius * 2,
            QPen(QColor(150, 150, 150), 2),
            QBrush(QColor(200, 200, 200))
        )
        self.mechanism_items["cam"] = cam_circle
        
        # Follower position
        follower_displacement = cam_offset * math.cos(cam_angle)
        follower_base = QPointF(cam_radius + 40, follower_displacement)
        follower_end = QPointF(follower_base.x() + follower_length, follower_base.y())
        
        # Draw follower
        self._draw_link_optimized(follower_base, follower_end, "follower", stress=-0.4)
        
        # Joints
        self._draw_joint_optimized(cam_center, "C", is_fixed=True)
        self._draw_joint_optimized(follower_base, "F", is_fixed=False)

    def _draw_gear_train_mechanism_optimized(self):
        """Optimized gear train - simplified gear representation"""
        # Simplified gear parameters
        gear1_radius = 50
        gear2_radius = 80
        gear3_radius = 35
        
        # Gear centers
        gear1_center = QPointF(-100, 0)
        gear2_center = QPointF(0, 0)
        gear3_center = QPointF(gear2_radius + gear3_radius + 10, 0)
        
        # Simplified gear ratios
        input_angle = math.radians(self.animation_angle)
        gear1_angle = input_angle
        gear2_angle = -input_angle * (20 / 32)  # Simplified gear ratio
        gear3_angle = gear2_angle * (32 / 14)
        
        # Draw simplified gears (just circles with rotation indicators)
        self._draw_gear_optimized(gear1_center, gear1_radius, gear1_angle, QColor(200, 100, 100))
        self._draw_gear_optimized(gear2_center, gear2_radius, gear2_angle, QColor(100, 200, 100))
        self._draw_gear_optimized(gear3_center, gear3_radius, gear3_angle, QColor(100, 100, 200))
        
        # Joints
        self._draw_joint_optimized(gear1_center, "G1", is_fixed=True)
        self._draw_joint_optimized(gear2_center, "G2", is_fixed=True)
        self._draw_joint_optimized(gear3_center, "G3", is_fixed=True)

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
        """Optimized scotch yoke mechanism"""
        crank_radius = 60
        yoke_width = 120
        yoke_height = 30
        
        crank_center = QPointF(-80, 0)
        crank_angle = math.radians(self.animation_angle)
        
        # Pin position
        pin_position = QPointF(
            crank_center.x() + crank_radius * math.cos(crank_angle),
            crank_center.y() + crank_radius * math.sin(crank_angle)
        )
        
        # Yoke position
        yoke_center = QPointF(pin_position.x(), 0)
        
        # Draw crank
        self._draw_link_optimized(crank_center, pin_position, "crank", stress=0.6)
        
        # Draw simplified yoke
        yoke_rect = self.scene.addRect(
            yoke_center.x() - yoke_width/2, yoke_center.y() - yoke_height/2,
            yoke_width, yoke_height,
            QPen(QColor(100, 200, 100), 2),
            QBrush(QColor(150, 250, 150))
        )
        self.mechanism_items["yoke"] = yoke_rect
        
        # Joints
        self._draw_joint_optimized(crank_center, "O", is_fixed=True)
        self._draw_joint_optimized(pin_position, "P", is_fixed=False)
        self._draw_joint_optimized(yoke_center, "Y", is_fixed=False)

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
        """Optimized force vector drawing"""
        for force in self.forces:
            self._draw_force_vector_simple(force)

    def _draw_force_vector_simple(self, force: ForceVector):
        """Simple force vector drawing for performance"""
        # Scale factor
        scale = 1.0
        
        # Calculate end point
        fx, fy = force.to_components()
        end_point = QPointF(force.position.x() + fx * scale, force.position.y() + fy * scale)
        
        # Simple line with arrowhead
        pen = QPen(force.color, 2)
        line = self.scene.addLine(
            force.position.x(), force.position.y(), end_point.x(), end_point.y(), pen
        )
        line.setZValue(20)
        self.force_items.append(line)
        
        # Simplified arrowhead (just a small triangle)
        arrow_size = 8
        arrow_angle = 0.4
        
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
        """Animation update with safety zone visualization"""
        # Always continue animation - never stop for educational purposes
        
        # Update angle
        self.animation_angle += self.animation_speed
        if self.animation_angle >= 360:
            self.animation_angle -= 360

        self.mechanism_params["input_angle"] = self.animation_angle
        
        # Evaluate safety status
        self.safety_status, self.safety_message = self._evaluate_mechanism_safety()
        
        # Draw mechanism and safety zones
        self.draw_mechanism()
        
        # Update safety status display
        self._update_safety_status_display()

    def start_animation(self):
        """Start mechanism animation at optimized 45 FPS for performance/quality balance"""
        self.animation_timer.start(22)  # ~45 FPS (22ms) - balance between performance and smoothness  # ~60 FPS (16.67ms)

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
        """Get educational content for a specific mechanism type"""
        educational_content = {
            "four_bar": {
                "title": "Four-Bar Linkage",
                "description": "A fundamental mechanism consisting of four rigid links connected by revolute joints. It converts rotary motion to complex curvilinear motion.",
                "applications": [
                    "Automobile suspension systems",
                    "Industrial robot arms", 
                    "Windshield wiper mechanisms",
                    "Exercise equipment"
                ],
                "key_concepts": [
                    "Grashof's criterion determines motion characteristics",
                    "Input-output relationship is non-linear",
                    "Can generate complex trajectories with simple input",
                    "Dead positions occur when links become collinear"
                ],
                "forces_explained": {
                    "Input Force": "Applied torque converted to tangential force on input link",
                    "Constraint Forces": "Internal forces that maintain joint connections", 
                    "Reaction Forces": "Support forces at fixed pivots that balance applied loads"
                }
            },
            "slider_crank": {
                "title": "Slider-Crank Mechanism",
                "description": "Converts rotational motion to linear reciprocating motion or vice versa. Essential in internal combustion engines and reciprocating pumps.",
                "applications": [
                    "Internal combustion engine pistons",
                    "Reciprocating pumps and compressors",
                    "Steam engines",
                    "Reciprocating saws"
                ]
            },
            "cam_follower": {
                "title": "Cam-Follower Mechanism", 
                "description": "Provides precise motion control through a specially shaped cam profile. Widely used for timing and automation applications.",
                "applications": [
                    "Engine valve timing systems",
                    "Automated manufacturing machinery",
                    "Textile machinery",
                    "Packaging equipment"
                ]
            },
            "gear_train": {
                "title": "Gear Train System",
                "description": "Transmits motion and force between rotating shafts through meshing gear teeth. Provides speed reduction/increase and torque multiplication.",
                "applications": [
                    "Automotive transmissions",
                    "Industrial gearboxes",
                    "Clock mechanisms",
                    "Power tools"
                ]
            },
            "scotch_yoke": {
                "title": "Scotch Yoke Mechanism",
                "description": "Converts rotational motion to pure harmonic linear motion. Provides sinusoidal displacement with simple harmonic motion characteristics.",
                "applications": [
                    "Steam engine crossheads",
                    "Control valve actuators",
                    "Testing machines",
                    "Mechanical calculators"
                ]
            }
        }
        
        return educational_content.get(mechanism_type, {
            "title": "Unknown Mechanism",
            "description": "No educational content available for this mechanism type.",
            "applications": [],
            "key_concepts": [],
            "forces_explained": {}
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

        # Set splitter sizes (prevent clipping)
        splitter.setSizes([250, 600, 250])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)

        layout.addWidget(splitter)

        # Initial draw
        if self.mechanism_widget:
            print("Drawing initial mechanism...")
            self.mechanism_widget.draw_mechanism()
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
        """Create parameter control panel"""
        panel = QGroupBox("Parameters")
        layout = QVBoxLayout(panel)

        # Mechanism type selector
        type_label = QLabel("Mechanism Type:")
        layout.addWidget(type_label)

        type_combo = QComboBox()
        type_combo.addItems(["Four-Bar Linkage", "Slider-Crank", "Cam-Follower"])
        type_combo.currentTextChanged.connect(self._on_mechanism_changed)
        layout.addWidget(type_combo)

        layout.addSpacing(20)

        # Parameter sliders
        params_label = QLabel("Link Lengths:")
        params_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(params_label)

        # Ground link
        self._add_parameter_slider(layout, "Ground Link", 50, 200, 150)

        # Input link
        self._add_parameter_slider(layout, "Input Link", 30, 120, 80)

        # Coupler link
        self._add_parameter_slider(layout, "Coupler Link", 50, 150, 120)

        # Output link
        self._add_parameter_slider(layout, "Output Link", 40, 130, 100)

        layout.addSpacing(20)

        # Animation speed
        speed_label = QLabel("Animation Speed:")
        layout.addWidget(speed_label)

        speed_slider = QSlider(Qt.Orientation.Horizontal)
        speed_slider.setRange(1, 10)
        speed_slider.setValue(2)
        speed_slider.valueChanged.connect(self._on_speed_changed)
        layout.addWidget(speed_slider)

        layout.addStretch()

        return panel

    def _add_parameter_slider(self, layout, label: str, min_val: int, max_val: int, default: int):
        """Add a parameter slider with label and value display"""
        param_layout = QHBoxLayout()

        label_widget = QLabel(f"{label}:")
        label_widget.setMinimumWidth(80)
        param_layout.addWidget(label_widget)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_val, max_val)
        slider.setValue(default)
        slider.setObjectName(label.lower().replace(" ", "_"))
        param_layout.addWidget(slider)

        value_label = QLabel(str(default))
        value_label.setMinimumWidth(30)
        param_layout.addWidget(value_label)

        # Connect slider
        slider.valueChanged.connect(lambda v: value_label.setText(str(v)))
        slider.valueChanged.connect(lambda v: self._on_parameter_changed(label, v))

        layout.addLayout(param_layout)

    def _create_info_panel(self) -> QWidget:
        """Create information panel for force display and educational content"""
        panel = QGroupBox("Analysis & Education")
        layout = QVBoxLayout(panel)

        # Mechanism info header
        self.mechanism_title = QLabel("Four-Bar Linkage")
        self.mechanism_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #0066cc;")
        layout.addWidget(self.mechanism_title)
    
        # Short description
        self.mechanism_desc = QLabel("Converts rotary motion to complex curvilinear motion")
        self.mechanism_desc.setWordWrap(True)
        self.mechanism_desc.setStyleSheet("color: #666; font-size: 11px; margin-bottom: 10px;")
        layout.addWidget(self.mechanism_desc)

        # Force display
        forces_label = QLabel("Real-time Forces:")
        forces_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(forces_label)

        self.force_display = QLabel("No forces calculated")
        self.force_display.setWordWrap(True)
        self.force_display.setStyleSheet(
            "background-color: #f0f0f0; padding: 5px; border-radius: 3px; font-size: 10px;"
        )
        layout.addWidget(self.force_display)

        layout.addSpacing(10)

        # Mechanical advantage
        ma_label = QLabel("Mechanical Advantage:")
        ma_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(ma_label)

        self.ma_display = QLabel("N/A")
        self.ma_display.setStyleSheet("font-size: 16px; color: #0066cc;")
        layout.addWidget(self.ma_display)

        layout.addSpacing(10)

        # Key applications
        apps_label = QLabel("Key Applications:")
        apps_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(apps_label)
        
        self.applications_display = QLabel("• Automobile suspension\n• Robot arms\n• Windshield wipers")
        self.applications_display.setStyleSheet("color: #666; font-size: 10px;")
        self.applications_display.setWordWrap(True)
        layout.addWidget(self.applications_display)

        layout.addSpacing(10)

        # Educational tips
        tips_label = QLabel("Visual Guide:")
        tips_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(tips_label)

        tips_text = QLabel(
            "🔴 Red = Compression forces\n"
            "🔵 Blue = Tension forces\n"
            "🟡 Yellow = Motion trail\n"
            "🟠 Orange = Applied forces"
        )
        tips_text.setWordWrap(True)
        tips_text.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(tips_text)
        
        layout.addSpacing(10)

        # Educational detail button
        self.detail_button = QPushButton("📖 Detailed Analysis")
        self.detail_button.setStyleSheet("""
            QPushButton {
                background-color: #0066cc;
                color: white;
                border: none;
                padding: 5px;
                border-radius: 3px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #0052a3;
            }
        """)
        self.detail_button.clicked.connect(self._show_detailed_analysis)
        layout.addWidget(self.detail_button)

        layout.addStretch()

        return panel

    def _connect_signals(self):
        """Connect widget signals"""
        # Connect mechanism widget signals
        if self.mechanism_widget:
            self.mechanism_widget.force_calculated.connect(self._update_force_display)
            self.mechanism_widget.force_calculated.connect(self._update_mechanical_advantage_display)
    
    def _update_mechanical_advantage_display(self):
        """Update mechanical advantage display"""
        if hasattr(self, 'ma_display') and self.mechanism_widget:
            ma_value = self._calculate_mechanical_advantage(self.mechanism_widget.mechanism_type)
            self.ma_display.setText(ma_value)
        if self.mechanism_widget:
            self.mechanism_widget.force_calculated.connect(self._update_force_display)
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
        """Handle mechanism type change"""
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
        self.mechanism_widget.mechanism_type = type_map.get(mechanism_type, "four_bar")
        
        # Update educational content
        self._update_educational_content(self.mechanism_widget.mechanism_type)
        self.mechanism_widget.motion_trail.clear()
        self.mechanism_widget.draw_mechanism()

    def _on_parameter_changed(self, param_name: str, value: int):
        """Handle parameter slider change"""
        if not self.mechanism_widget:
            print("Warning: mechanism_widget is None in _on_parameter_changed")
            return
            
        param_map = {
            "Ground Link": "ground_link",
            "Input Link": "input_link",
            "Coupler Link": "coupler_link",
            "Output Link": "output_link",
        }

        param_key = param_map.get(param_name)
        if param_key:
            self.mechanism_widget.mechanism_params[param_key] = value
            self.mechanism_widget.draw_mechanism()

    def _on_speed_changed(self, value: int):
        """Handle animation speed change"""
        if not self.mechanism_widget:
            print("Warning: mechanism_widget is None in _on_speed_changed")
            return
            
        self.mechanism_widget.animation_speed = value

    def _update_force_display(self, force_data: dict):
        """Update force display panel"""
        force_text = ""
        for name, value in force_data.items():
            force_text += f"{name}: {value:.1f} N\n"

        self.force_display.setText(force_text)

        # Calculate mechanical advantage (simplified)
        if "input_force" in force_data and "reaction_O4" in force_data:
            ma = force_data["reaction_O4"] / force_data["input_force"]
            self.ma_display.setText(f"{ma:.2f}")

    def _on_component_selected(self, component_id: str):
        """Handle component selection"""
        # Could highlight the component or show detailed info
        pass
    
    def _show_detailed_analysis(self):
        """Show detailed educational analysis in a popup window"""
        try:
            from PyQt6.QtWidgets import QDialog, QTextBrowser, QVBoxLayout
            
            dialog = QDialog(self)
            dialog.setWindowTitle(f"Educational Analysis - {self.mechanism_widget.mechanism_type.replace('_', ' ').title()}")
            dialog.setModal(True)
            dialog.resize(600, 500)
            
            layout = QVBoxLayout(dialog)
            
            # Text browser for rich content
            browser = QTextBrowser()
            analysis_text = self.mechanism_widget.get_force_analysis_text(self.mechanism_widget.mechanism_type)
            browser.setHtml(analysis_text)
            
            layout.addWidget(browser)
            
            # Close button
            close_button = QPushButton("Close")
            close_button.clicked.connect(dialog.close)
            layout.addWidget(close_button)
            
            dialog.exec()
            
        except Exception as e:
            print(f"Error showing detailed analysis: {e}")
    
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

