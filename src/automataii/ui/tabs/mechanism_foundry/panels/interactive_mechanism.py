"""
Interactive Mechanism Visualization - Amazing interactive mechanism rendering

Features:
- Real-time physics simulation
- Smooth animations with easing
- Interactive drag handles
- Force visualization
- Motion trails
- Dynamic lighting effects
- Realistic mechanical constraints
"""

import math
import time
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF, pyqtSignal
from PyQt6.QtGui import (
    QPainter, QPen, QBrush, QColor, QLinearGradient, QRadialGradient,
    QPainterPath, QTransform, QPolygonF, QFont, QFontMetrics
)

from .unified_visualization import UnifiedMechanismRenderer, RenderSettings, GridSettings


@dataclass
class Joint:
    """Represents a mechanical joint"""
    x: float
    y: float
    fixed: bool = False
    radius: float = 8.0
    velocity_x: float = 0.0
    velocity_y: float = 0.0
    force_x: float = 0.0
    force_y: float = 0.0
    
    def __post_init__(self):
        if not hasattr(self, 'color'):
            self.color = QColor('#0d6efd')


@dataclass
class Link:
    """Represents a mechanical link"""
    joint1_idx: int
    joint2_idx: int
    length: float
    width: float = 6.0
    force: float = 0.0
    stress: float = 0.0
    
    def __post_init__(self):
        if not hasattr(self, 'color'):
            self.color = QColor('#495057')


@dataclass
class MotionTrail:
    """Represents a motion trail point"""
    x: float
    y: float
    timestamp: float
    alpha: float = 1.0


class PhysicsEngine:
    """Simple physics engine for mechanism simulation"""
    
    def __init__(self):
        self.gravity = 0.0  # No gravity for mechanisms
        self.damping = 0.95
        self.constraint_iterations = 3
        
    def update_kinematics(self, joints: List[Joint], links: List[Link], dt: float):
        """Update joint positions based on constraints"""
        # Apply constraint forces
        for _ in range(self.constraint_iterations):
            for link in links:
                j1 = joints[link.joint1_idx]
                j2 = joints[link.joint2_idx]
                
                if j1.fixed and j2.fixed:
                    continue
                    
                # Calculate current distance
                dx = j2.x - j1.x
                dy = j2.y - j1.y
                current_dist = math.sqrt(dx*dx + dy*dy)
                
                if current_dist == 0:
                    continue
                    
                # Calculate constraint force
                error = current_dist - link.length
                correction = error * 0.5
                
                # Normalize direction
                nx = dx / current_dist
                ny = dy / current_dist
                
                # Apply corrections
                if not j1.fixed and not j2.fixed:
                    # Both joints can move
                    j1.x += nx * correction
                    j1.y += ny * correction
                    j2.x -= nx * correction
                    j2.y -= ny * correction
                elif j1.fixed:
                    # Only j2 can move
                    j2.x -= nx * error
                    j2.y -= ny * error
                elif j2.fixed:
                    # Only j1 can move
                    j1.x += nx * error
                    j1.y += ny * error
                    
                # Update link force
                link.force = abs(error) * 100  # Arbitrary force scale
        
        # Apply damping
        for joint in joints:
            if not joint.fixed:
                joint.velocity_x *= self.damping
                joint.velocity_y *= self.damping


class InteractiveMechanismRenderer(QWidget):
    """
    Amazing interactive mechanism renderer with physics simulation.
    
    Features:
    - Real-time physics simulation
    - Interactive drag handles
    - Smooth animations with easing
    - Force visualization
    - Motion trails
    - Dynamic lighting effects
    """
    
    parameterChanged = pyqtSignal(str, float)  # parameter_name, new_value
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.mechanism_data = None
        self.parameters = {}
        
        # Animation system
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.update_animation)
        self.animation_time = 0.0
        self.last_update_time = time.time()
        
        # Physics system
        self.physics = PhysicsEngine()
        self.joints: List[Joint] = []
        self.links: List[Link] = []
        
        # Interaction system
        self.dragging_joint = None
        self.drag_offset = QPointF(0, 0)
        self.hover_joint = None
        
        # Visual effects
        self.motion_trails: Dict[int, List[MotionTrail]] = {}
        self.show_forces = True
        self.show_trails = True
        self.show_labels = True
        self.show_grid = True  # Enable grid by default for macanism style
        
        # Animation parameters
        self.input_speed = 60.0  # RPM
        self.input_angle = 0.0
        
        # Unified renderer for macanism-style visualization
        self.setup_unified_renderer()
        
        self.setup_ui()
        
    def setup_unified_renderer(self):
        """Setup the unified macanism-style renderer"""
        # Configure professional engineering drawing style
        grid_settings = GridSettings(
            show_grid=True,
            grid_size=20.0,
            major_grid_size=100.0,
            grid_color=QColor(200, 200, 200, 100),
            major_grid_color=QColor(150, 150, 150, 150),
            axis_color=QColor(100, 100, 100, 200),
            show_measurements=True,
            show_origin=True
        )
        
        render_settings = RenderSettings(
            background_color=QColor(250, 250, 250),  # Clean white background
            grid=grid_settings,
            link_color=QColor(70, 130, 180),
            joint_color=QColor(220, 20, 60),
            ground_joint_color=QColor(105, 105, 105),
            highlight_color=QColor(255, 140, 0),
            force_color=QColor(255, 69, 0, 200),
            velocity_color=QColor(50, 205, 50, 200),
            motion_trail_color=QColor(255, 215, 0, 150),
            text_color=QColor(60, 60, 60),
            dimension_color=QColor(100, 100, 100)
        )
        
        self.unified_renderer = UnifiedMechanismRenderer(render_settings)
        
    def setup_ui(self):
        """Setup the renderer"""
        self.setMinimumSize(800, 600)
        self.setMouseTracking(True)  # Enable hover detection
        # Clean professional styling matching macanism
        self.setStyleSheet("""
            QWidget {
                background-color: #fafafa;
                border: 2px solid #0d6efd;
                border-radius: 12px;
            }
        """)
        
    def set_mechanism(self, mechanism_data: Dict):
        """Set the mechanism to render"""
        self.mechanism_data = mechanism_data
        self.setup_mechanism()
        self.start_animation()
        
    def setup_mechanism(self):
        """Setup mechanism geometry based on type"""
        if not self.mechanism_data:
            return
            
        mechanism_name = self.mechanism_data.get('name', '').lower()
        
        # Clear existing data
        self.joints.clear()
        self.links.clear()
        self.motion_trails.clear()
        
        # Setup based on mechanism type
        if 'four-bar' in mechanism_name or 'linkage' in mechanism_name:
            self.setup_fourbar_linkage()
        elif 'gear' in mechanism_name:
            self.setup_gear_mechanism()
        elif 'cam' in mechanism_name:
            self.setup_cam_mechanism()
        elif 'spring' in mechanism_name:
            self.setup_spring_mechanism()
        else:
            self.setup_generic_mechanism()
            
    def setup_fourbar_linkage(self):
        """Setup four-bar linkage with realistic proportions - centered at origin"""
        # Get parameters or use defaults
        l1 = self.parameters.get('Link Lengths.Link 1 (Ground)', 120.0)
        l2 = self.parameters.get('Link Lengths.Link 2 (Input)', 60.0)
        l3 = self.parameters.get('Link Lengths.Link 3 (Coupler)', 100.0)
        l4 = self.parameters.get('Link Lengths.Link 4 (Output)', 80.0)
        
        # Create joints - centered at origin (0,0)
        self.joints = [
            Joint(-l1/2, 0, fixed=True),  # Ground joint A
            Joint(l1/2, 0, fixed=True),  # Ground joint B
            Joint(-l1/2 + l2, -20, fixed=False),  # Moving joint C
            Joint(l1/2 - l4, -30, fixed=False),  # Moving joint D
        ]
        
        # Create links with beautiful colors
        self.links = [
            Link(0, 2, l2, 8.0, QColor('#e74c3c')),  # Input link (red)
            Link(2, 3, l3, 6.0, QColor('#3498db')),  # Coupler link (blue)
            Link(3, 1, l4, 8.0, QColor('#2ecc71')),  # Output link (green)
            Link(0, 1, l1, 10.0, QColor('#95a5a6')), # Ground link (gray)
        ]
        
        # Initialize motion trails
        for i in range(len(self.joints)):
            self.motion_trails[i] = []
            
    def setup_gear_mechanism(self):
        """Setup gear mechanism with realistic teeth - centered at origin"""
        # Get parameters
        teeth1 = int(self.parameters.get('Gear 1.Teeth Count', 24))
        teeth2 = int(self.parameters.get('Gear 2.Teeth Count', 36))
        module = self.parameters.get('Gear 1.Module', 2.0)
        
        # Calculate gear radii
        r1 = teeth1 * module / 2
        r2 = teeth2 * module / 2
        
        # Position gears so they mesh
        distance = r1 + r2
        
        # Create gear centers as joints - centered at origin
        self.joints = [
            Joint(-distance/2, 0, fixed=True, radius=r1, color=QColor('#e74c3c')),
            Joint(distance/2, 0, fixed=True, radius=r2, color=QColor('#3498db')),
        ]
        
        # Store gear-specific data
        self.gear_data = {
            'teeth1': teeth1,
            'teeth2': teeth2,
            'radius1': r1,
            'radius2': r2,
            'angle1': 0.0,
            'angle2': 0.0,
        }
        
    def setup_cam_mechanism(self):
        """Setup cam mechanism with follower - centered at origin"""
        # Get parameters
        base_radius = self.parameters.get('Cam Profile.Base Radius', 40.0)
        lift_height = self.parameters.get('Cam Profile.Lift Height', 20.0)
        
        # Create cam center and follower - centered at origin
        self.joints = [
            Joint(0, 0, fixed=True, radius=base_radius, color=QColor('#e74c3c')),
            Joint(base_radius + 60, 0, fixed=False, radius=6.0, color=QColor('#3498db')),
        ]
        
        # Store cam-specific data
        self.cam_data = {
            'base_radius': base_radius,
            'lift_height': lift_height,
            'angle': 0.0,
        }
        
    def setup_spring_mechanism(self):
        """Setup spring mechanism - enhanced for macanism-style visualization - centered at origin"""
        # Get parameters with more descriptive names
        free_length = self.parameters.get('Parameters.Natural Length', 150.0)
        force = self.parameters.get('Parameters.Applied Force', 20.0)
        k = self.parameters.get('Parameters.Spring Constant', 200.0)
        mass = self.parameters.get('Parameters.Mass', 2.0)
        
        # Calculate static deflection using Hooke's law
        static_deflection = force / k if k > 0 else 0
        current_length = free_length + static_deflection  # Spring extends under load
        
        # Create spring system with proper anchor and mass - centered at origin
        self.joints = [
            Joint(0, -free_length/2, fixed=True, color=QColor('#34495e')),  # Fixed anchor
            Joint(0, -free_length/2 + current_length, fixed=False, color=QColor('#e74c3c')),  # Moving mass
        ]
        
        # Create spring link
        self.links = [
            Link(0, 1, current_length)
        ]
        
        # Store spring analysis data for educational display
        natural_freq = math.sqrt(k / mass) / (2 * math.pi) if mass > 0 else 0
        self.spring_data = {
            'free_length': free_length,
            'current_length': current_length,
            'static_deflection': static_deflection,
            'force': force,
            'spring_constant': k,
            'mass': mass,
            'natural_frequency': natural_freq,
        }
        
    def setup_generic_mechanism(self):
        """Setup generic rotating mechanism - centered at origin"""
        # Simple rotating arm
        arm_length = 80.0
        
        self.joints = [
            Joint(0, 0, fixed=True, color=QColor('#95a5a6')),
            Joint(arm_length, 0, fixed=False, color=QColor('#e74c3c')),
        ]
        
        self.links = [
            Link(0, 1, arm_length, 6.0, QColor('#3498db')),
        ]
        
    def start_animation(self):
        """Start the animation loop"""
        self.animation_timer.start(16)  # ~60 FPS
        
    def stop_animation(self):
        """Stop the animation loop"""
        self.animation_timer.stop()
        
    def update_animation(self):
        """Update animation frame"""
        current_time = time.time()
        dt = current_time - self.last_update_time
        self.last_update_time = current_time
        
        # Update animation time
        self.animation_time += dt
        
        # Update input motion
        self.input_angle = (self.input_speed / 60.0) * 2 * math.pi * self.animation_time
        
        # Update mechanism based on type
        if self.mechanism_data:
            mechanism_name = self.mechanism_data.get('name', '').lower()
            
            if 'four-bar' in mechanism_name or 'linkage' in mechanism_name:
                self.update_fourbar_animation(dt)
            elif 'gear' in mechanism_name:
                self.update_gear_animation(dt)
            elif 'cam' in mechanism_name:
                self.update_cam_animation(dt)
            elif 'spring' in mechanism_name:
                self.update_spring_animation(dt)
            else:
                self.update_generic_animation(dt)
        
        # Update motion trails
        self.update_motion_trails()
        
        # Trigger repaint
        self.update()
        
    def update_fourbar_animation(self, dt: float):
        """Update four-bar linkage animation"""
        if len(self.joints) < 4:
            return
            
        # Update input joint position
        l2 = self.links[0].length if self.links else 60.0
        base_joint = self.joints[0]
        
        # Calculate new position for input joint
        new_x = base_joint.x + l2 * math.cos(self.input_angle)
        new_y = base_joint.y + l2 * math.sin(self.input_angle)
        
        self.joints[2].x = new_x
        self.joints[2].y = new_y
        
        # Apply physics constraints
        self.physics.update_kinematics(self.joints, self.links, dt)
        
    def update_gear_animation(self, dt: float):
        """Update gear mechanism animation"""
        if not hasattr(self, 'gear_data'):
            return
            
        # Update gear angles
        self.gear_data['angle1'] = self.input_angle
        self.gear_data['angle2'] = -self.input_angle * (self.gear_data['teeth1'] / self.gear_data['teeth2'])
        
    def update_cam_animation(self, dt: float):
        """Update cam mechanism animation"""
        if not hasattr(self, 'cam_data'):
            return
            
        # Update cam angle
        self.cam_data['angle'] = self.input_angle
        
        # Calculate follower position
        base_radius = self.cam_data['base_radius']
        lift_height = self.cam_data['lift_height']
        
        # Simple cam profile (sinusoidal)
        profile_radius = base_radius + lift_height * (1 + math.sin(2 * self.input_angle)) / 2
        
        # Update follower position
        cam_center = self.joints[0]
        follower = self.joints[1]
        
        follower.x = cam_center.x + profile_radius + 20
        
    def update_spring_animation(self, dt: float):
        """Update spring mechanism animation"""
        if not hasattr(self, 'spring_data'):
            return
            
        # Animate compression (simple harmonic motion)
        base_compression = self.spring_data['compression']
        oscillation = 10 * math.sin(self.input_angle * 2)
        
        current_length = self.spring_data['free_length'] - base_compression - oscillation
        
        # Update spring endpoint
        center_y = self.height() / 2
        self.joints[1].y = center_y + current_length / 2
        
    def update_generic_animation(self, dt: float):
        """Update generic mechanism animation"""
        if len(self.joints) < 2:
            return
            
        # Simple rotation
        center = self.joints[0]
        end = self.joints[1]
        
        if self.links:
            radius = self.links[0].length
        else:
            radius = 80.0
            
        end.x = center.x + radius * math.cos(self.input_angle)
        end.y = center.y + radius * math.sin(self.input_angle)
        
    def update_motion_trails(self):
        """Update motion trails for all joints"""
        current_time = time.time()
        trail_lifetime = 3.0  # 3 seconds
        
        for joint_idx, joint in enumerate(self.joints):
            if joint.fixed:
                continue
                
            # Add new trail point
            if joint_idx not in self.motion_trails:
                self.motion_trails[joint_idx] = []
                
            trails = self.motion_trails[joint_idx]
            trails.append(MotionTrail(joint.x, joint.y, current_time))
            
            # Remove old trail points and update alpha
            trails[:] = [
                trail for trail in trails 
                if current_time - trail.timestamp < trail_lifetime
            ]
            
            # Update alpha based on age
            for trail in trails:
                age = current_time - trail.timestamp
                trail.alpha = max(0, 1 - age / trail_lifetime)
                
    def update_parameters(self, parameters: Dict[str, float]):
        """Update mechanism parameters"""
        self.parameters = parameters
        
        # Update input speed if available
        if 'Motion.Input Speed' in parameters:
            self.input_speed = parameters['Motion.Input Speed']
        elif 'Motion.Speed' in parameters:
            self.input_speed = parameters['Motion.Speed']
            
        # Recreate mechanism with new parameters
        self.setup_mechanism()
    
    def update_from_mechanism_state(self, state_data: Dict):
        """
        Update visualization from mechanism state data.
        
        Args:
            state_data: State data from domain mechanism
        """
        if not state_data:
            return
        
        # Update joints from state data
        joints_data = state_data.get('joints', {})
        self.joints.clear()
        
        for joint_id, joint_info in joints_data.items():
            joint = Joint(
                x=joint_info['x'],
                y=joint_info['y'],
                fixed=joint_info.get('fixed', False)
            )
            self.joints.append(joint)
        
        # Update links from state data
        links_data = state_data.get('links', {})
        self.links.clear()
        
        # Create a mapping from joint IDs to indices
        joint_id_to_index = {joint_id: idx for idx, joint_id in enumerate(joints_data.keys())}
        
        for link_id, link_info in links_data.items():
            joint_a_id = link_info.get('joint_a')
            joint_b_id = link_info.get('joint_b')
            
            if joint_a_id in joint_id_to_index and joint_b_id in joint_id_to_index:
                link = Link(
                    joint1_idx=joint_id_to_index[joint_a_id],
                    joint2_idx=joint_id_to_index[joint_b_id],
                    length=link_info.get('length', 0.0)
                )
                self.links.append(link)
        
        # Update forces if available
        forces_data = state_data.get('forces', {})
        for joint_idx, joint in enumerate(self.joints):
            joint_id = list(joints_data.keys())[joint_idx]
            if joint_id in forces_data:
                force_x, force_y = forces_data[joint_id]
                joint.force_x = force_x
                joint.force_y = force_y
        
        # Update velocities if available
        velocities_data = state_data.get('velocities', {})
        for joint_idx, joint in enumerate(self.joints):
            joint_id = list(joints_data.keys())[joint_idx]
            if joint_id in velocities_data:
                vel_x, vel_y = velocities_data[joint_id]
                joint.velocity_x = vel_x
                joint.velocity_y = vel_y
        
        # Update input angle
        self.input_angle = state_data.get('input_angle', 0.0)
        
        # Store mechanism type for specialized rendering
        self.mechanism_type = state_data.get('mechanism_type', 'generic')
        
        # Trigger repaint
        self.update()
        
    def paintEvent(self, event):
        """Render the amazing interactive mechanism with macanism-style unified rendering"""
        super().paintEvent(event)
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Transform coordinate system to center (0,0) at center of widget
        painter.translate(self.width() / 2, self.height() / 2)
        
        # Setup unified renderer viewport with centered coordinates
        viewport_rect = QRectF(-self.width()/2, -self.height()/2, self.width(), self.height())
        self.unified_renderer.set_viewport(viewport_rect)
        
        # Begin professional rendering
        self.unified_renderer.begin_render(painter)
        
        # Draw professional grid
        if self.show_grid:
            self.unified_renderer.draw_grid(painter)
            
        # Draw motion trails with unified style
        if self.show_trails:
            self.draw_unified_motion_trails(painter)
            
        # Draw mechanism with unified professional styling
        if self.mechanism_data:
            mechanism_name = self.mechanism_data.get('name', '').lower()
            
            if 'gear' in mechanism_name:
                self.draw_unified_gears(painter)
            elif 'cam' in mechanism_name:
                self.draw_unified_cam(painter)
            elif 'spring' in mechanism_name:
                self.draw_unified_spring(painter)
            else:
                self.draw_unified_linkage(painter)
        elif self.joints:
            # Draw any joints/links that exist even without mechanism_data
            self.draw_unified_linkage(painter)
        else:
            # Draw placeholder when no mechanism is loaded
            self.draw_placeholder(painter)
        
        # Draw force vectors with professional styling
        if self.show_forces:
            self.draw_unified_forces(painter)
            
        # Draw professional labels and info
        if self.show_labels:
            self.draw_unified_labels(painter)
            
        # Draw hover effects with professional styling
        self.draw_unified_hover_effects(painter)
        
    def draw_unified_motion_trails(self, painter: QPainter):
        """Draw motion trails using unified renderer"""
        for joint_idx, trails in self.motion_trails.items():
            if len(trails) < 2:
                continue
                
            # Convert trails to QPointF list
            trail_points = [QPointF(trail.x, trail.y) for trail in trails]
            
            # Use unified renderer for consistent styling
            self.unified_renderer.draw_motion_trail(painter, trail_points, alpha_fade=True)
        
    def draw_unified_linkage(self, painter: QPainter):
        """Draw linkage mechanism with unified professional styling"""
        # Update physics data for unified renderer
        forces = {}
        velocities = {}
        
        # Prepare physics data
        for i, joint in enumerate(self.joints):
            if joint.force_x != 0 or joint.force_y != 0:
                forces[i] = (joint.force_x, joint.force_y)
            if joint.velocity_x != 0 or joint.velocity_y != 0:
                velocities[i] = (joint.velocity_x, joint.velocity_y)
                
        self.unified_renderer.update_physics_data(forces, velocities)
        
        # Set selection state
        selected_elements = set()
        if self.hover_joint is not None:
            selected_elements.add(f"joint_{self.hover_joint}")
        self.unified_renderer.set_selection(selected_elements)
        
        # Draw links with professional styling
        for link in self.links:
            if link.joint1_idx >= len(self.joints) or link.joint2_idx >= len(self.joints):
                continue
                
            j1 = self.joints[link.joint1_idx]
            j2 = self.joints[link.joint2_idx]
            
            start_pos = QPointF(j1.x, j1.y)
            end_pos = QPointF(j2.x, j2.y)
            
            # Draw with unified renderer for consistent styling
            self.unified_renderer.draw_mechanism_link(
                painter, start_pos, end_pos, 
                width=link.width, force=link.force, 
                selected=False
            )
            
        # Draw joints with professional styling
        for i, joint in enumerate(self.joints):
            position = QPointF(joint.x, joint.y)
            selected = (i == self.hover_joint)
            joint_id = f"J{i+1}" if self.show_labels else ""
            
            self.unified_renderer.draw_mechanism_joint(
                painter, position, radius=joint.radius,
                fixed=joint.fixed, selected=selected,
                joint_id=joint_id
            )
            
    def draw_unified_gears(self, painter: QPainter):
        """Draw gear mechanism with unified professional styling"""
        if not hasattr(self, 'gear_data'):
            return
            
        for i, joint in enumerate(self.joints):
            position = QPointF(joint.x, joint.y)
            selected = (i == self.hover_joint)
            
            # Use unified renderer for consistent joint styling
            self.unified_renderer.draw_mechanism_joint(
                painter, position, radius=joint.radius,
                fixed=joint.fixed, selected=selected,
                joint_id=f"G{i+1}" if self.show_labels else ""
            )
            
            # Draw gear teeth with professional styling
            self.draw_professional_gear_teeth(painter, joint, i)
            
    def draw_professional_gear_teeth(self, painter: QPainter, joint: Joint, gear_index: int):
        """Draw gear teeth with professional engineering style"""
        radius = joint.radius
        teeth = self.gear_data['teeth1'] if gear_index == 0 else self.gear_data['teeth2']
        angle = self.gear_data['angle1'] if gear_index == 0 else self.gear_data['angle2']
        
        # Professional gear tooth styling
        painter.setPen(QPen(QColor(100, 100, 100), 1.5))
        painter.setBrush(QBrush(joint.color.lighter(120)))
        
        for tooth in range(teeth):
            tooth_angle = angle + (tooth * 2 * math.pi / teeth)
            
            # Calculate tooth geometry
            inner_radius = radius - 3
            outer_radius = radius + 6
            
            # Draw simplified tooth outline
            base_angle1 = tooth_angle - math.pi / teeth * 0.3
            base_angle2 = tooth_angle + math.pi / teeth * 0.3
            
            # Tooth points
            points = [
                QPointF(joint.x + inner_radius * math.cos(base_angle1),
                       joint.y + inner_radius * math.sin(base_angle1)),
                QPointF(joint.x + outer_radius * math.cos(tooth_angle - math.pi / teeth * 0.15),
                       joint.y + outer_radius * math.sin(tooth_angle - math.pi / teeth * 0.15)),
                QPointF(joint.x + outer_radius * math.cos(tooth_angle + math.pi / teeth * 0.15),
                       joint.y + outer_radius * math.sin(tooth_angle + math.pi / teeth * 0.15)),
                QPointF(joint.x + inner_radius * math.cos(base_angle2),
                       joint.y + inner_radius * math.sin(base_angle2))
            ]
            
            tooth_polygon = QPolygonF(points)
            painter.drawPolygon(tooth_polygon)
                               
    def draw_unified_cam(self, painter: QPainter):
        """Draw cam mechanism with unified professional styling"""
        if not hasattr(self, 'cam_data') or len(self.joints) < 2:
            return
            
        cam_joint = self.joints[0]
        follower_joint = self.joints[1]
        
        # Draw cam center as fixed joint
        cam_pos = QPointF(cam_joint.x, cam_joint.y)
        self.unified_renderer.draw_mechanism_joint(
            painter, cam_pos, radius=8.0, fixed=True,
            selected=(0 == self.hover_joint), joint_id="Cam" if self.show_labels else ""
        )
        
        # Draw follower as moving joint
        follower_pos = QPointF(follower_joint.x, follower_joint.y)
        self.unified_renderer.draw_mechanism_joint(
            painter, follower_pos, radius=6.0, fixed=False,
            selected=(1 == self.hover_joint), joint_id="Follower" if self.show_labels else ""
        )
        
        # Draw cam profile with professional styling
        self.draw_professional_cam_profile(painter, cam_joint)
        
        # Draw follower guide with professional styling
        painter.setPen(QPen(QColor(100, 100, 100), 2.0, Qt.PenStyle.DashLine))
        guide_x = follower_joint.x + 30
        painter.drawLine(guide_x, cam_joint.y - 100, guide_x, cam_joint.y + 100)
        
    def draw_professional_cam_profile(self, painter: QPainter, cam_joint: Joint):
        """Draw cam profile with professional engineering style"""
        base_radius = self.cam_data['base_radius']
        lift_height = self.cam_data['lift_height']
        angle = self.cam_data['angle']
        
        # Professional cam profile styling
        painter.setPen(QPen(QColor(70, 130, 180), 2.0))
        painter.setBrush(QBrush(QColor(70, 130, 180, 100)))
        
        # Create smooth cam profile
        cam_path = QPainterPath()
        segments = 64
        
        for i in range(segments + 1):
            theta = i * 2 * math.pi / segments
            profile_radius = base_radius + lift_height * (1 + math.sin(2 * (theta - angle))) / 2
            
            x = cam_joint.x + profile_radius * math.cos(theta)
            y = cam_joint.y + profile_radius * math.sin(theta)
            
            if i == 0:
                cam_path.moveTo(x, y)
            else:
                cam_path.lineTo(x, y)
                
        cam_path.closeSubpath()
        painter.drawPath(cam_path)
            
    def draw_unified_spring(self, painter: QPainter):
        """Draw spring mechanism with unified professional styling"""
        if not hasattr(self, 'spring_data') or len(self.joints) < 2:
            return
            
        start_joint = self.joints[0]
        end_joint = self.joints[1]
        
        # Draw spring endpoints as joints
        start_pos = QPointF(start_joint.x, start_joint.y)
        end_pos = QPointF(end_joint.x, end_joint.y)
        
        self.unified_renderer.draw_mechanism_joint(
            painter, start_pos, radius=8.0, fixed=start_joint.fixed,
            selected=(0 == self.hover_joint), joint_id="Fixed" if self.show_labels else ""
        )
        
        self.unified_renderer.draw_mechanism_joint(
            painter, end_pos, radius=8.0, fixed=end_joint.fixed,
            selected=(1 == self.hover_joint), joint_id="Load" if self.show_labels else ""
        )
        
        # Draw spring coils with professional styling
        self.draw_professional_spring_coils(painter, start_joint, end_joint)
        
        # Show compression force if applicable
        if self.spring_data['compression'] > 0:
            force_magnitude = self.spring_data['force']
            self.unified_renderer.draw_force_vector(
                painter, end_pos, (0, -force_magnitude), scale=0.5
            )
            
    def draw_professional_spring_coils(self, painter: QPainter, start_joint: Joint, end_joint: Joint):
        """Draw spring coils with professional engineering style"""
        current_length = abs(end_joint.y - start_joint.y) - 20
        coil_count = 10
        coil_width = 15
        coil_spacing = current_length / coil_count
        
        # Professional spring styling
        painter.setPen(QPen(QColor(70, 130, 180), 2.5))
        
        spring_path = QPainterPath()
        spring_path.moveTo(start_joint.x, start_joint.y + 10)
        
        for i in range(coil_count):
            y = start_joint.y + 10 + i * coil_spacing
            
            if i % 2 == 0:
                spring_path.lineTo(start_joint.x - coil_width/2, y + coil_spacing/3)
                spring_path.lineTo(start_joint.x + coil_width/2, y + 2*coil_spacing/3)
            else:
                spring_path.lineTo(start_joint.x + coil_width/2, y + coil_spacing/3)
                spring_path.lineTo(start_joint.x - coil_width/2, y + 2*coil_spacing/3)
                
        spring_path.lineTo(end_joint.x, end_joint.y - 10)
        painter.drawPath(spring_path)
        
        # Draw end plates with professional styling
        painter.setPen(QPen(QColor(105, 105, 105), 4.0))
        painter.drawLine(start_joint.x - 20, start_joint.y, start_joint.x + 20, start_joint.y)
        painter.drawLine(end_joint.x - 20, end_joint.y, end_joint.x + 20, end_joint.y)
            
    def draw_unified_forces(self, painter: QPainter):
        """Draw force vectors using unified renderer"""
        for i, joint in enumerate(self.joints):
            if joint.force_x == 0 and joint.force_y == 0:
                continue
                
            position = QPointF(joint.x, joint.y)
            force = (joint.force_x, joint.force_y)
            
            # Use unified renderer for consistent force visualization
            self.unified_renderer.draw_force_vector(painter, position, force, scale=1.0)
        
    def draw_unified_labels(self, painter: QPainter):
        """Draw professional labels using unified renderer"""
        if not self.mechanism_data:
            return
            
        # Prepare mechanism info for professional display
        info = {
            "Mechanism": self.mechanism_data.get('name', 'Unknown'),
            "Speed": f"{self.input_speed:.1f} RPM",
            "Angle": f"{math.degrees(self.input_angle) % 360:.1f}°"
        }
        
        # Add mechanism-specific information
        if hasattr(self, 'spring_data'):
            info["Compression"] = f"{self.spring_data['compression']:.1f} mm"
            info["Force"] = f"{self.spring_data['force']:.1f} N"
        elif hasattr(self, 'gear_data'):
            info["Gear Ratio"] = f"{self.gear_data['teeth2']/self.gear_data['teeth1']:.2f}:1"
        
        # Use unified renderer for consistent info panel styling
        self.unified_renderer.draw_info_panel(painter, info, QPointF(10, 10))
        
    def draw_unified_hover_effects(self, painter: QPainter):
        """Draw professional hover effects"""
        if self.hover_joint is not None and self.hover_joint < len(self.joints):
            joint = self.joints[self.hover_joint]
            position = QPointF(joint.x, joint.y)
            
            # Professional glow effect using unified renderer colors
            painter.setBrush(QBrush(Qt.BrushStyle.NoBrush))
            
            # Subtle professional highlight rings
            for radius in range(int(joint.radius + 3), int(joint.radius + 12), 3):
                alpha = int(80 * (1 - (radius - joint.radius - 3) / 9))
                color = self.unified_renderer.settings.highlight_color
                color.setAlpha(alpha)
                painter.setPen(QPen(color, 1.5))
                painter.drawEllipse(position, radius, radius)
            
    def draw_placeholder(self, painter: QPainter):
        """Draw placeholder content when no mechanism is loaded - using centered coordinates"""
        # Draw placeholder message at origin (already translated to center)
        painter.setPen(QPen(QColor('#6c757d'), 1))
        font = QFont("system-ui", 16)
        painter.setFont(font)
        
        text = "🔧 Select a mechanism to start exploring"
        text_rect = painter.fontMetrics().boundingRect(text)
        text_x = -text_rect.width() / 2
        text_y = -text_rect.height() / 2
        
        painter.drawText(int(text_x), int(text_y), text)
        
        # Draw some decorative elements
        painter.setPen(QPen(QColor('#dee2e6'), 2))
        
        # Draw a simple gear icon - using centered coordinates
        gear_radius = 40
        gear_center = QPointF(0, 60)  # 60 pixels below center
        
        # Outer circle of gear
        painter.drawEllipse(gear_center, gear_radius, gear_radius)
        
        # Inner circle
        painter.drawEllipse(gear_center, gear_radius * 0.4, gear_radius * 0.4)
        
        # Gear teeth (simplified)
        for i in range(8):
            angle = i * 45 * math.pi / 180
            x1 = gear_center.x() + gear_radius * 0.9 * math.cos(angle)
            y1 = gear_center.y() + gear_radius * 0.9 * math.sin(angle)
            x2 = gear_center.x() + gear_radius * 1.1 * math.cos(angle)
            y2 = gear_center.y() + gear_radius * 1.1 * math.sin(angle)
            painter.drawLine(QPointF(float(x1), float(y1)), QPointF(float(x2), float(y2)))

    def resizeEvent(self, event):
        """Handle resize event to update unified renderer viewport"""
        super().resizeEvent(event)
        if hasattr(self, 'unified_renderer'):
            self.unified_renderer.set_viewport(QRectF(self.rect()))
            
    def update_unified_renderer_settings(self):
        """Update unified renderer based on current display options"""
        if hasattr(self, 'unified_renderer'):
            # Update grid settings
            if hasattr(self.unified_renderer.settings, 'grid'):
                self.unified_renderer.settings.grid.show_grid = self.show_grid
                
            # Force update
            self.update()
                
    # Mouse interaction methods
    def mousePressEvent(self, event):
        """Handle mouse press for interaction"""
        if event.button() == Qt.MouseButton.LeftButton:
            # Check if clicking on a joint
            for i, joint in enumerate(self.joints):
                distance = math.sqrt((event.pos().x() - joint.x)**2 + (event.pos().y() - joint.y)**2)
                if distance <= joint.radius + 5:
                    if not joint.fixed:
                        self.dragging_joint = i
                        self.drag_offset = QPointF(joint.x - event.pos().x(), joint.y - event.pos().y())
                        self.setCursor(Qt.CursorShape.ClosedHandCursor)
                    break
                    
    def mouseMoveEvent(self, event):
        """Handle mouse move for dragging and hover"""
        if self.dragging_joint is not None:
            # Update joint position
            joint = self.joints[self.dragging_joint]
            joint.x = event.pos().x() + self.drag_offset.x()
            joint.y = event.pos().y() + self.drag_offset.y()
            
            # Emit parameter change signal if needed
            self.parameterChanged.emit("manual_drag", 0.0)
            
        else:
            # Check for hover effects
            old_hover = self.hover_joint
            self.hover_joint = None
            
            for i, joint in enumerate(self.joints):
                distance = math.sqrt((event.pos().x() - joint.x)**2 + (event.pos().y() - joint.y)**2)
                if distance <= joint.radius + 5:
                    self.hover_joint = i
                    if not joint.fixed:
                        self.setCursor(Qt.CursorShape.OpenHandCursor)
                    else:
                        self.setCursor(Qt.CursorShape.ArrowCursor)
                    break
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
                
            # Update if hover changed
            if old_hover != self.hover_joint:
                self.update()
                
    def mouseReleaseEvent(self, event):
        """Handle mouse release"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging_joint = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            
    def leaveEvent(self, event):
        """Handle mouse leave"""
        self.hover_joint = None
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update()
        
    # Control methods
    def set_show_forces(self, show: bool):
        """Toggle force visualization"""
        self.show_forces = show
        self.update()
        
    def set_show_trails(self, show: bool):
        """Toggle motion trails"""
        self.show_trails = show
        if not show:
            self.motion_trails.clear()
        self.update()
        
    def set_show_labels(self, show: bool):
        """Toggle labels"""
        self.show_labels = show
        self.update()
        
    def set_show_grid(self, show: bool):
        """Toggle grid with unified renderer"""
        self.show_grid = show
        if hasattr(self, 'unified_renderer'):
            self.unified_renderer.settings.grid.show_grid = show
        self.update()
        
    def clear_trails(self):
        """Clear all motion trails"""
        self.motion_trails.clear()
        self.update()