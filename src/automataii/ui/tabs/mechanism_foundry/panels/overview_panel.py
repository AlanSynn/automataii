"""
Overview Panel - Educational content and conceptual understanding

Provides comprehensive learning materials for mechanism understanding:
- Animated mechanism visualization
- Educational content with definitions and key terms
- Real-world applications and context
- Interactive tutorial integration
"""

from typing import Optional, Dict
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QSplitter,
    QLabel, QTextEdit, QGroupBox, QFrame
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QPainter, QPen, QBrush, QColor, QRadialGradient
import math


class AnimatedMechanismView(QFrame):
    """Animated visualization of the mechanism"""
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.mechanism_data = None
        self.animation_time = 0.0
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.update_animation)
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the visualization widget"""
        self.setMinimumSize(500, 400)
        self.setStyleSheet("""
            QFrame {
                border: 2px solid #0d6efd;
                border-radius: 12px;
                background: qradialgradient(cx:0.5, cy:0.5, radius:0.8,
                    fx:0.3, fy:0.3, stop:0 #2c3e50, stop:1 #34495e);
            }
        """)
        
    def set_mechanism(self, mechanism_data: Dict):
        """Set the mechanism to visualize"""
        self.mechanism_data = mechanism_data
        
        # Start animation
        self.animation_timer.start(50)  # 20 FPS
        self.update()
        
    def update_animation(self):
        """Update animation frame"""
        self.animation_time += 0.1
        self.update()
        
    def paintEvent(self, event):
        """Draw the animated mechanism"""
        super().paintEvent(event)
        
        if not self.mechanism_data:
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Setup drawing parameters
        width = self.width() - 40
        height = self.height() - 40
        center_x = self.width() // 2
        center_y = self.height() // 2
        
        mechanism_name = self.mechanism_data.get('name', '').lower()
        
        # Draw mechanism based on type
        if 'four-bar' in mechanism_name or 'linkage' in mechanism_name:
            self.draw_animated_linkage(painter, center_x, center_y, width, height)
        elif 'gear' in mechanism_name:
            self.draw_animated_gears(painter, center_x, center_y, width, height)
        elif 'cam' in mechanism_name:
            self.draw_animated_cam(painter, center_x, center_y, width, height)
        elif 'spring' in mechanism_name:
            self.draw_animated_spring(painter, center_x, center_y, width, height)
        else:
            self.draw_generic_mechanism(painter, center_x, center_y, width, height)
            
    def draw_animated_linkage(self, painter: QPainter, cx: int, cy: int, w: int, h: int):
        """Draw animated four-bar linkage"""
        # Link lengths (scaled for display)
        l1 = 80  # Ground link
        l2 = 50  # Input link
        l3 = 70  # Coupler link
        l4 = 60  # Output link
        
        # Input angle (rotating)
        theta2 = self.animation_time
        
        # Calculate joint positions
        A = (cx - l1//2, cy)  # Ground joint A
        B = (cx + l1//2, cy)  # Ground joint B
        
        # Input link endpoint
        C = (A[0] + l2 * math.cos(theta2), A[1] + l2 * math.sin(theta2))
        
        # Solve for output link angle (simplified)
        try:
            # Distance from C to B
            cb_dist = math.sqrt((B[0] - C[0])**2 + (B[1] - C[1])**2)
            
            # Use cosine rule to find output angle
            cos_theta4 = (l4**2 + l1**2 - (cb_dist**2 - l3**2 + l4**2)) / (2 * l4 * l1)
            cos_theta4 = max(-1, min(1, cos_theta4))  # Clamp to valid range
            theta4 = math.acos(cos_theta4)
            
            # Output link endpoint
            D = (B[0] + l4 * math.cos(math.pi - theta4), B[1] + l4 * math.sin(math.pi - theta4))
        except:
            # Fallback if calculation fails
            D = (B[0] - l4 * 0.7, B[1] - l4 * 0.3)
        
        # Set drawing style with glow effect
        painter.setPen(QPen(QColor('#3498db'), 4))
        painter.setBrush(QBrush(QColor('#2980b9')))
        
        # Draw links
        painter.drawLine(int(A[0]), int(A[1]), int(C[0]), int(C[1]))  # Input link
        painter.drawLine(int(C[0]), int(C[1]), int(D[0]), int(D[1]))  # Coupler link
        painter.drawLine(int(D[0]), int(D[1]), int(B[0]), int(B[1]))  # Output link
        painter.drawLine(int(A[0]), int(A[1]), int(B[0]), int(B[1]))  # Ground link
        
        # Draw joints with gradient effect
        joint_radius = 8
        for i, point in enumerate([A, B, C, D]):
            # Create radial gradient for each joint
            gradient = QRadialGradient(point[0], point[1], joint_radius)
            if i < 2:  # Ground joints
                gradient.setColorAt(0, QColor('#95a5a6'))
                gradient.setColorAt(1, QColor('#7f8c8d'))
            else:  # Moving joints
                gradient.setColorAt(0, QColor('#e74c3c'))
                gradient.setColorAt(1, QColor('#c0392b'))
            
            painter.setBrush(QBrush(gradient))
            painter.setPen(QPen(QColor('#2c3e50'), 2))
            painter.drawEllipse(int(point[0] - joint_radius), int(point[1] - joint_radius), 
                              2 * joint_radius, 2 * joint_radius)
            
        # Draw coupler curve with glowing effect
        coupler_point = ((C[0] + D[0]) / 2, (C[1] + D[1]) / 2)
        
        # Draw glow effect
        for radius in range(8, 3, -1):
            alpha = int(100 * (1 - (radius - 3) / 5))
            glow_color = QColor('#f39c12')
            glow_color.setAlpha(alpha)
            painter.setBrush(QBrush(glow_color))
            painter.setPen(QPen(glow_color, 1))
            painter.drawEllipse(int(coupler_point[0] - radius), int(coupler_point[1] - radius), 
                              2 * radius, 2 * radius)
        
        # Draw central point
        painter.setBrush(QBrush(QColor('#f39c12')))
        painter.setPen(QPen(QColor('#e67e22'), 2))
        painter.drawEllipse(int(coupler_point[0] - 4), int(coupler_point[1] - 4), 8, 8)
        
    def draw_animated_gears(self, painter: QPainter, cx: int, cy: int, w: int, h: int):
        """Draw animated gear pair"""
        # Gear parameters
        r1 = 40  # First gear radius
        r2 = 60  # Second gear radius
        
        # Gear centers
        c1 = (cx - 50, cy)
        c2 = (cx + 50, cy)
        
        # Rotation angles
        theta1 = self.animation_time
        theta2 = -theta1 * r1 / r2  # Inverse ratio
        
        # Draw gear bodies with metallic gradient
        for i, (center, radius) in enumerate([(c1, r1), (c2, r2)]):
            gradient = QRadialGradient(center[0], center[1], radius)
            if i == 0:
                gradient.setColorAt(0, QColor('#3498db'))
                gradient.setColorAt(0.7, QColor('#2980b9'))
                gradient.setColorAt(1, QColor('#1f4e79'))
            else:
                gradient.setColorAt(0, QColor('#e74c3c'))
                gradient.setColorAt(0.7, QColor('#c0392b'))
                gradient.setColorAt(1, QColor('#8b2635'))
            
            painter.setBrush(QBrush(gradient))
            painter.setPen(QPen(QColor('#2c3e50'), 3))
            painter.drawEllipse(center[0] - radius, center[1] - radius, 2 * radius, 2 * radius)
        
        # Draw teeth (simplified)
        painter.setPen(QPen(QColor('#495057'), 1))
        teeth1 = 12
        teeth2 = 18
        
        for i in range(teeth1):
            angle = theta1 + i * 2 * math.pi / teeth1
            x = c1[0] + (r1 + 5) * math.cos(angle)
            y = c1[1] + (r1 + 5) * math.sin(angle)
            painter.drawRect(int(x - 2), int(y - 2), 4, 4)
            
        for i in range(teeth2):
            angle = theta2 + i * 2 * math.pi / teeth2
            x = c2[0] + (r2 + 5) * math.cos(angle)
            y = c2[1] + (r2 + 5) * math.sin(angle)
            painter.drawRect(int(x - 2), int(y - 2), 4, 4)
            
    def draw_animated_cam(self, painter: QPainter, cx: int, cy: int, w: int, h: int):
        """Draw animated cam mechanism"""
        # Cam parameters
        base_radius = 30
        lift_height = 20
        
        # Cam rotation
        cam_angle = self.animation_time
        
        painter.setPen(QPen(QColor('#0d6efd'), 2))
        painter.setBrush(QBrush(QColor('#e7f3ff')))
        
        # Draw cam profile (simplified ellipse with varying radius)
        cam_radius = base_radius + lift_height * (1 + math.sin(2 * cam_angle)) / 2
        painter.drawEllipse(cx - int(cam_radius), cy - int(cam_radius), 
                          int(2 * cam_radius), int(2 * cam_radius))
        
        # Draw follower
        follower_y = cy - base_radius - lift_height * (1 + math.sin(2 * cam_angle)) / 2
        painter.drawRect(cx + 40, int(follower_y - 10), 8, 60)
        
        # Draw follower guide
        painter.setPen(QPen(QColor('#6c757d'), 1))
        painter.drawLine(cx + 35, cy - 60, cx + 35, cy + 20)
        painter.drawLine(cx + 55, cy - 60, cx + 55, cy + 20)
        
    def draw_animated_spring(self, painter: QPainter, cx: int, cy: int, w: int, h: int):
        """Draw animated spring mechanism"""
        # Spring parameters
        compression = 10 * (1 + math.sin(self.animation_time)) / 2
        
        painter.setPen(QPen(QColor('#0d6efd'), 2))
        
        # Draw spring coils
        coil_count = 8
        spring_length = 100 - compression
        coil_spacing = spring_length / coil_count
        
        start_y = cy - spring_length // 2
        
        for i in range(coil_count):
            y = start_y + i * coil_spacing
            if i % 2 == 0:
                painter.drawLine(cx - 15, int(y), cx + 15, int(y + coil_spacing))
            else:
                painter.drawLine(cx + 15, int(y), cx - 15, int(y + coil_spacing))
                
        # Draw end plates
        painter.setPen(QPen(QColor('#495057'), 3))
        painter.drawLine(cx - 20, int(start_y), cx + 20, int(start_y))
        painter.drawLine(cx - 20, int(start_y + spring_length), cx + 20, int(start_y + spring_length))
        
    def draw_generic_mechanism(self, painter: QPainter, cx: int, cy: int, w: int, h: int):
        """Draw generic mechanism placeholder"""
        painter.setPen(QPen(QColor('#6c757d'), 2))
        painter.setBrush(QBrush(QColor('#f8f9fa')))
        
        # Draw rotating element
        angle = self.animation_time
        radius = 50
        
        # Draw base
        painter.drawRect(cx - 60, cy - 10, 120, 20)
        
        # Draw rotating arm
        end_x = cx + radius * math.cos(angle)
        end_y = cy + radius * math.sin(angle)
        painter.drawLine(cx, cy, int(end_x), int(end_y))
        
        # Draw joint
        painter.drawEllipse(cx - 5, cy - 5, 10, 10)


class EducationalContent(QScrollArea):
    """Educational content display"""
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.mechanism_data = None
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the content area"""
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # Content widget
        content_widget = QWidget()
        self.content_layout = QVBoxLayout(content_widget)
        self.content_layout.setContentsMargins(16, 16, 16, 16)
        self.content_layout.setSpacing(16)
        
        self.setWidget(content_widget)
        
    def set_mechanism(self, mechanism_data: Dict):
        """Set mechanism and update content"""
        self.mechanism_data = mechanism_data
        self.update_content()
        
    def update_content(self):
        """Update the educational content"""
        if not self.mechanism_data:
            return
            
        # Clear existing content
        for i in reversed(range(self.content_layout.count())):
            child = self.content_layout.itemAt(i).widget()
            if child:
                child.setParent(None)
                
        # Add content sections
        self.add_definition_section()
        self.add_key_concepts_section()
        self.add_applications_section()
        self.add_learning_objectives_section()
        
        # Add stretch at the end
        self.content_layout.addStretch()
        
    def add_definition_section(self):
        """Add mechanism definition section"""
        group = QGroupBox("Definition & Description")
        group.setStyleSheet("""
            QGroupBox {
                font-size: 16px;
                font-weight: bold;
                color: #495057;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px 0 8px;
                background-color: white;
            }
        """)
        
        layout = QVBoxLayout(group)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # Description
        description = QLabel(self.mechanism_data.get('description', ''))
        description.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #212529;
                line-height: 1.5;
                padding: 8px 0;
            }
        """)
        description.setWordWrap(True)
        layout.addWidget(description)
        
        self.content_layout.addWidget(group)
        
    def add_key_concepts_section(self):
        """Add key concepts section"""
        concepts = self.mechanism_data.get('key_concepts', [])
        if not concepts:
            return
            
        group = QGroupBox("Key Concepts")
        group.setStyleSheet("""
            QGroupBox {
                font-size: 16px;
                font-weight: bold;
                color: #495057;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px 0 8px;
                background-color: white;
            }
        """)
        
        layout = QVBoxLayout(group)
        layout.setContentsMargins(16, 16, 16, 16)
        
        for concept in concepts:
            concept_label = QLabel(f"• {concept}")
            concept_label.setStyleSheet("""
                QLabel {
                    font-size: 14px;
                    color: #0d6efd;
                    font-weight: 500;
                    padding: 4px 0;
                }
            """)
            concept_label.setWordWrap(True)
            layout.addWidget(concept_label)
            
            # Add detailed explanation (placeholder)
            explanation = self.get_concept_explanation(concept)
            if explanation:
                exp_label = QLabel(explanation)
                exp_label.setStyleSheet("""
                    QLabel {
                        font-size: 13px;
                        color: #6c757d;
                        margin-left: 16px;
                        margin-bottom: 8px;
                        line-height: 1.4;
                    }
                """)
                exp_label.setWordWrap(True)
                layout.addWidget(exp_label)
        
        self.content_layout.addWidget(group)
        
    def add_applications_section(self):
        """Add real-world applications section"""
        applications = self.mechanism_data.get('applications', [])
        if not applications:
            return
            
        group = QGroupBox("Real-World Applications")
        group.setStyleSheet("""
            QGroupBox {
                font-size: 16px;
                font-weight: bold;
                color: #495057;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px 0 8px;
                background-color: white;
            }
        """)
        
        layout = QVBoxLayout(group)
        layout.setContentsMargins(16, 16, 16, 16)
        
        for app in applications:
            app_label = QLabel(f"🔧 {app}")
            app_label.setStyleSheet("""
                QLabel {
                    font-size: 14px;
                    color: #198754;
                    font-weight: 500;
                    padding: 4px 0;
                }
            """)
            layout.addWidget(app_label)
        
        self.content_layout.addWidget(group)
        
    def add_learning_objectives_section(self):
        """Add learning objectives section"""
        group = QGroupBox("Learning Objectives")
        group.setStyleSheet("""
            QGroupBox {
                font-size: 16px;
                font-weight: bold;
                color: #495057;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px 0 8px;
                background-color: white;
            }
        """)
        
        layout = QVBoxLayout(group)
        layout.setContentsMargins(16, 16, 16, 16)
        
        objectives = self.get_learning_objectives()
        for objective in objectives:
            obj_label = QLabel(f"📚 {objective}")
            obj_label.setStyleSheet("""
                QLabel {
                    font-size: 14px;
                    color: #fd7e14;
                    font-weight: 500;
                    padding: 4px 0;
                }
            """)
            obj_label.setWordWrap(True)
            layout.addWidget(obj_label)
        
        self.content_layout.addWidget(group)
        
    def get_concept_explanation(self, concept: str) -> str:
        """Get detailed explanation for a concept"""
        explanations = {
            "Grashof condition": "Determines if a four-bar linkage has continuous rotation by comparing link lengths.",
            "Coupler curves": "The path traced by any point on the coupler link during mechanism motion.",
            "Transmission angle": "The angle between coupler and follower links, affecting force transmission efficiency.",
            "Gear ratio": "The ratio of angular velocities between input and output gears.",
            "Module": "The ratio of pitch diameter to number of teeth, determining gear size.",
            "Pressure angle": "The angle between the line of action and the common tangent to pitch circles.",
            "Cam profile": "The shape of the cam that determines the motion of the follower.",
            "Follower motion": "The prescribed movement pattern of the cam follower.",
            "Spring constant": "The resistance of a spring to deformation, measured in force per unit length.",
            "Deflection": "The displacement of a spring from its natural length when loaded."
        }
        return explanations.get(concept, "")
        
    def get_learning_objectives(self) -> list:
        """Get learning objectives based on mechanism type"""
        mechanism_name = self.mechanism_data.get('name', '').lower()
        
        if 'linkage' in mechanism_name:
            return [
                "Understand the relationship between link lengths and motion type",
                "Apply the Grashof condition to classify linkage behavior",
                "Analyze coupler curves and their practical applications",
                "Calculate transmission angles and their impact on performance"
            ]
        elif 'gear' in mechanism_name:
            return [
                "Calculate gear ratios and their effect on speed and torque",
                "Understand gear geometry and manufacturing parameters",
                "Analyze gear train efficiency and power transmission",
                "Design gear systems for specific applications"
            ]
        elif 'cam' in mechanism_name:
            return [
                "Design cam profiles for desired follower motion",
                "Understand the relationship between cam geometry and follower displacement",
                "Analyze cam-follower contact forces and stresses",
                "Select appropriate cam-follower combinations for applications"
            ]
        else:
            return [
                "Understand the fundamental operating principles",
                "Analyze motion and force relationships",
                "Identify key design parameters and their effects",
                "Apply knowledge to practical engineering problems"
            ]


class OverviewPanel(QWidget):
    """
    Overview panel providing educational content and conceptual understanding.
    
    Features:
    - Animated mechanism visualization
    - Comprehensive educational content
    - Key concepts with detailed explanations
    - Real-world applications and context
    - Structured learning objectives
    """
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.mechanism_data = None
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the overview panel UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Create splitter for visualization and content
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left side: Animated visualization
        self.visualization = AnimatedMechanismView()
        splitter.addWidget(self.visualization)
        
        # Right side: Educational content
        self.content = EducationalContent()
        splitter.addWidget(self.content)
        
        # Set initial splitter proportions
        splitter.setSizes([400, 500])  # Roughly 40% visualization, 60% content
        
        layout.addWidget(splitter)
        
    def set_mechanism(self, mechanism_data: Dict):
        """Set the mechanism for display"""
        self.mechanism_data = mechanism_data
        
        # Update both visualization and content
        self.visualization.set_mechanism(mechanism_data)
        self.content.set_mechanism(mechanism_data)
        
    def on_tab_activated(self):
        """Called when this tab becomes active"""
        # Resume animation if it was paused
        if self.visualization.mechanism_data:
            self.visualization.animation_timer.start(50)