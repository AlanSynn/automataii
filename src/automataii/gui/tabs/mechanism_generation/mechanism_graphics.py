"""Graphics items for mechanism visualization with enhanced interactivity."""

import math
from typing import Optional, List, Tuple, Dict
from enum import Enum

from PyQt6.QtCore import (
    Qt, QPointF, QRectF, QLineF, pyqtSignal, QObject,
    QPropertyAnimation, QEasingCurve, pyqtProperty, QTimer
)
from PyQt6.QtWidgets import (
    QGraphicsItem, QGraphicsObject, QGraphicsEllipseItem,
    QGraphicsLineItem, QGraphicsPathItem, QGraphicsPolygonItem,
    QGraphicsSceneMouseEvent, QGraphicsTextItem, QStyleOptionGraphicsItem,
    QGraphicsRectItem, QGraphicsItemGroup
)
from PyQt6.QtGui import (
    QPen, QBrush, QColor, QPainterPath, QPainter, 
    QFont, QPolygonF, QTransform, QRadialGradient
)


class MechanismColors:
    """Color scheme for mechanism visualization."""
    # Base colors
    GROUND = QColor(100, 100, 100)
    LINK = QColor(60, 60, 60)
    JOINT = QColor(80, 120, 200)
    FIXED_JOINT = QColor(200, 80, 80)
    
    # Interactive colors
    HOVER = QColor(100, 150, 255)
    SELECTED = QColor(255, 150, 100)
    DRAGGING = QColor(255, 200, 100)
    
    # Cam colors
    CAM_PROFILE = QColor(100, 100, 200)
    CAM_FILL = QColor(150, 150, 255, 50)
    FOLLOWER = QColor(200, 100, 100)
    
    # Gear colors
    GEAR_TEETH = QColor(120, 120, 120)
    GEAR_BODY = QColor(180, 180, 180)
    
    # Animation colors
    MOTION_PATH = QColor(100, 200, 100, 128)
    TRACE = QColor(255, 100, 100, 200)


class AnimatedFourBarLinkage(QGraphicsObject):
    """Animated four-bar linkage visualization."""
    
    def __init__(self, mechanism_data: Dict, parent=None):
        super().__init__(parent)
        
        self.mechanism_data = mechanism_data
        self._angle = 0.0
        self._is_animating = False
        
        # Extract data
        self.pivot_a = mechanism_data.get("pivot_a", QPointF(0, 0))
        self.pivot_d = mechanism_data.get("pivot_d", QPointF(100, 0))
        self.joint_b = mechanism_data.get("joint_b", QPointF(50, 50))
        self.joint_c = mechanism_data.get("joint_c", QPointF(80, 50))
        
        # Calculate link lengths
        self.link_ab = self._distance(self.pivot_a, self.joint_b)
        self.link_bc = self._distance(self.joint_b, self.joint_c)
        self.link_cd = self._distance(self.joint_c, self.pivot_d)
        self.link_ad = self._distance(self.pivot_a, self.pivot_d)
        
        # Visual elements
        self.links: List[QGraphicsLineItem] = []
        self.joints: List[QGraphicsEllipseItem] = []
        self.trace_path = QPainterPath()
        self.trace_points: List[QPointF] = []
        
        # Animation
        self.animation = QPropertyAnimation(self, b"angle")
        self.animation.setDuration(4000)
        self.animation.setStartValue(0)
        self.animation.setEndValue(360)
        self.animation.setLoopCount(-1)  # Infinite loop
        
        self._create_visuals()
        
    def _distance(self, p1: QPointF, p2: QPointF) -> float:
        """Calculate distance between two points."""
        return math.sqrt((p2.x() - p1.x())**2 + (p2.y() - p1.y())**2)
        
    def _create_visuals(self):
        """Create visual elements."""
        # Ground link (fixed)
        ground_pen = QPen(MechanismColors.GROUND, 6)
        ground_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        ground_link = QGraphicsLineItem(
            self.pivot_a.x(), self.pivot_a.y(),
            self.pivot_d.x(), self.pivot_d.y(),
            self
        )
        ground_link.setPen(ground_pen)
        ground_link.setZValue(0)
        
        # Create pattern for ground
        ground_pattern = QGraphicsPathItem(self)
        pattern_path = QPainterPath()
        step = 10
        y_offset = 5
        for x in range(int(self.pivot_a.x()), int(self.pivot_d.x()), step):
            pattern_path.moveTo(x, self.pivot_a.y())
            pattern_path.lineTo(x - step/2, self.pivot_a.y() + y_offset)
        ground_pattern.setPath(pattern_path)
        ground_pattern.setPen(QPen(MechanismColors.GROUND, 2))
        ground_pattern.setZValue(-1)
        
        # Moving links
        link_pen = QPen(MechanismColors.LINK, 4)
        link_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        
        for _ in range(3):  # AB, BC, CD
            link = QGraphicsLineItem(self)
            link.setPen(link_pen)
            link.setZValue(1)
            self.links.append(link)
            
        # Joints
        joint_radius = 8
        
        # Fixed pivots
        for pos, is_fixed in [(self.pivot_a, True), (self.pivot_d, True)]:
            joint = QGraphicsEllipseItem(
                pos.x() - joint_radius, pos.y() - joint_radius,
                joint_radius * 2, joint_radius * 2,
                self
            )
            joint.setPen(QPen(Qt.GlobalColor.black, 2))
            color = MechanismColors.FIXED_JOINT if is_fixed else MechanismColors.JOINT
            joint.setBrush(QBrush(color))
            joint.setZValue(2)
            self.joints.append(joint)
            
        # Moving joints
        for _ in range(2):  # B and C
            joint = QGraphicsEllipseItem(
                -joint_radius, -joint_radius,
                joint_radius * 2, joint_radius * 2,
                self
            )
            joint.setPen(QPen(Qt.GlobalColor.black, 2))
            joint.setBrush(QBrush(MechanismColors.JOINT))
            joint.setZValue(2)
            self.joints.append(joint)
            
        # Update initial positions
        self._update_linkage(0)
        
    def _update_linkage(self, angle_deg: float):
        """Update linkage positions for given input angle."""
        # Convert to radians
        angle_rad = math.radians(angle_deg)
        
        # Calculate new position of joint B (on circle around A)
        b_x = self.pivot_a.x() + self.link_ab * math.cos(angle_rad)
        b_y = self.pivot_a.y() + self.link_ab * math.sin(angle_rad)
        new_b = QPointF(b_x, b_y)
        
        # Find joint C using circle intersection
        # C is on circle around B with radius BC and circle around D with radius CD
        c_positions = self._circle_intersection(
            new_b, self.link_bc,
            self.pivot_d, self.link_cd
        )
        
        if c_positions:
            # Choose the configuration (could be made configurable)
            new_c = c_positions[0]  # or c_positions[1] for other configuration
            
            # Update link positions
            self.links[0].setLine(self.pivot_a.x(), self.pivot_a.y(), b_x, b_y)
            self.links[1].setLine(b_x, b_y, new_c.x(), new_c.y())
            self.links[2].setLine(new_c.x(), new_c.y(), self.pivot_d.x(), self.pivot_d.y())
            
            # Update joint positions
            joint_radius = 8
            self.joints[2].setPos(b_x - joint_radius, b_y - joint_radius)
            self.joints[3].setPos(new_c.x() - joint_radius, new_c.y() - joint_radius)
            
            # Add to trace
            if self._is_animating:
                # Can trace any point - let's trace joint C
                self.trace_points.append(new_c)
                if len(self.trace_points) > 200:  # Limit trace length
                    self.trace_points.pop(0)
                self.update()  # Trigger repaint for trace
                
    def _circle_intersection(self, c1: QPointF, r1: float, 
                           c2: QPointF, r2: float) -> Optional[List[QPointF]]:
        """Find intersection points of two circles."""
        d = self._distance(c1, c2)
        
        # Check if circles intersect
        if d > r1 + r2 or d < abs(r1 - r2) or d == 0:
            return None
            
        # Calculate intersection points
        a = (r1**2 - r2**2 + d**2) / (2 * d)
        h = math.sqrt(r1**2 - a**2)
        
        # Point on line between centers
        px = c1.x() + a * (c2.x() - c1.x()) / d
        py = c1.y() + a * (c2.y() - c1.y()) / d
        
        # Intersection points
        p1 = QPointF(
            px + h * (c2.y() - c1.y()) / d,
            py - h * (c2.x() - c1.x()) / d
        )
        p2 = QPointF(
            px - h * (c2.y() - c1.y()) / d,
            py + h * (c2.x() - c1.x()) / d
        )
        
        return [p1, p2]
        
    @pyqtProperty(float)
    def angle(self):
        """Get current angle."""
        return self._angle
        
    @angle.setter
    def angle(self, value):
        """Set current angle and update linkage."""
        self._angle = value
        self._update_linkage(value)
        
    def start_animation(self):
        """Start the animation."""
        self._is_animating = True
        self.trace_points.clear()
        self.animation.start()
        
    def stop_animation(self):
        """Stop the animation."""
        self._is_animating = False
        self.animation.stop()
        
    def reset_animation(self):
        """Reset to initial position."""
        self.stop_animation()
        self.trace_points.clear()
        self.angle = 0
        self.update()
        
    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget=None):
        """Paint the trace path."""
        if self.trace_points and len(self.trace_points) > 1:
            # Draw trace with gradient
            pen = QPen(MechanismColors.TRACE, 2)
            pen.setStyle(Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            
            # Create path from trace points
            trace_path = QPainterPath()
            trace_path.moveTo(self.trace_points[0])
            for point in self.trace_points[1:]:
                trace_path.lineTo(point)
                
            painter.drawPath(trace_path)
            
    def boundingRect(self) -> QRectF:
        """Return bounding rectangle."""
        # Calculate bounds including all possible positions
        margin = 50
        all_points = [self.pivot_a, self.pivot_d, self.joint_b, self.joint_c]
        
        min_x = min(p.x() for p in all_points) - self.link_ab - margin
        min_y = min(p.y() for p in all_points) - self.link_ab - margin
        max_x = max(p.x() for p in all_points) + self.link_ab + margin
        max_y = max(p.y() for p in all_points) + self.link_ab + margin
        
        return QRectF(min_x, min_y, max_x - min_x, max_y - min_y)


class AnimatedCamFollower(QGraphicsObject):
    """Animated cam and follower mechanism."""
    
    def __init__(self, mechanism_data: Dict, parent=None):
        super().__init__(parent)
        
        self.mechanism_data = mechanism_data
        self._rotation = 0.0
        
        # Extract data
        self.cam_center = mechanism_data.get("cam_center", QPointF(0, 0))
        self.cam_profile = mechanism_data.get("cam_profile", [])
        self.follower_type = mechanism_data.get("follower_type", "roller")
        
        # Visual elements
        self.cam_item: Optional[QGraphicsPathItem] = None
        self.follower_item: Optional[QGraphicsItem] = None
        self.center_marker: Optional[QGraphicsEllipseItem] = None
        
        # Animation
        self.animation = QPropertyAnimation(self, b"rotation")
        self.animation.setDuration(4000)
        self.animation.setStartValue(0)
        self.animation.setEndValue(360)
        self.animation.setLoopCount(-1)
        
        self._create_visuals()
        
    def _create_visuals(self):
        """Create visual elements."""
        # Cam profile
        if self.cam_profile:
            cam_path = QPainterPath()
            cam_path.moveTo(self.cam_profile[0])
            for point in self.cam_profile[1:]:
                cam_path.lineTo(point)
            cam_path.closeSubpath()
            
            self.cam_item = QGraphicsPathItem(cam_path, self)
            self.cam_item.setPen(QPen(MechanismColors.CAM_PROFILE, 3))
            
            # Gradient fill
            gradient = QRadialGradient(self.cam_center, 50)
            gradient.setColorAt(0, QColor(180, 180, 255))
            gradient.setColorAt(1, MechanismColors.CAM_FILL)
            self.cam_item.setBrush(QBrush(gradient))
            self.cam_item.setTransformOriginPoint(self.cam_center)
            
        # Center marker
        marker_radius = 6
        self.center_marker = QGraphicsEllipseItem(
            self.cam_center.x() - marker_radius,
            self.cam_center.y() - marker_radius,
            marker_radius * 2,
            marker_radius * 2,
            self
        )
        self.center_marker.setPen(QPen(Qt.GlobalColor.black, 2))
        self.center_marker.setBrush(QBrush(MechanismColors.FIXED_JOINT))
        self.center_marker.setZValue(10)
        
        # Follower
        self._create_follower()
        
    def _create_follower(self):
        """Create follower based on type."""
        if self.follower_type == "roller":
            # Roller follower
            roller_radius = 15
            follower_pos = self._get_follower_position(0)
            
            self.follower_item = QGraphicsEllipseItem(
                follower_pos.x() - roller_radius,
                follower_pos.y() - roller_radius,
                roller_radius * 2,
                roller_radius * 2,
                self
            )
            self.follower_item.setPen(QPen(MechanismColors.FOLLOWER, 3))
            self.follower_item.setBrush(QBrush(QColor(255, 200, 200, 100)))
            
        elif self.follower_type == "flat":
            # Flat follower
            width = 40
            height = 10
            follower_pos = self._get_follower_position(0)
            
            self.follower_item = QGraphicsRectItem(
                follower_pos.x() - width/2,
                follower_pos.y() - height/2,
                width,
                height,
                self
            )
            self.follower_item.setPen(QPen(MechanismColors.FOLLOWER, 3))
            self.follower_item.setBrush(QBrush(QColor(255, 200, 200, 100)))
            
    def _get_follower_position(self, angle_deg: float) -> QPointF:
        """Calculate follower position for given cam angle."""
        if not self.cam_profile:
            return self.cam_center
            
        # Simple approach: find cam profile point at angle
        angle_rad = math.radians(angle_deg)
        
        # For now, just place follower at top of cam
        # In reality, this would involve contact point calculation
        max_radius = max(self._distance(self.cam_center, p) for p in self.cam_profile)
        return QPointF(
            self.cam_center.x(),
            self.cam_center.y() - max_radius - 20
        )
        
    def _distance(self, p1: QPointF, p2: QPointF) -> float:
        """Calculate distance between two points."""
        return math.sqrt((p2.x() - p1.x())**2 + (p2.y() - p1.y())**2)
        
    @pyqtProperty(float)
    def rotation(self):
        """Get current rotation."""
        return self._rotation
        
    @rotation.setter
    def rotation(self, value):
        """Set rotation and update visuals."""
        self._rotation = value
        if self.cam_item:
            self.cam_item.setRotation(value)
            
        # Update follower position
        follower_pos = self._get_follower_position(value)
        if self.follower_item:
            if self.follower_type == "roller":
                radius = 15
                self.follower_item.setPos(
                    follower_pos.x() - radius,
                    follower_pos.y() - radius
                )
                
    def start_animation(self):
        """Start the animation."""
        self.animation.start()
        
    def stop_animation(self):
        """Stop the animation."""
        self.animation.stop()
        
    def reset_animation(self):
        """Reset to initial position."""
        self.stop_animation()
        self.rotation = 0
        
    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget=None):
        """Paint method (required for QGraphicsObject)."""
        pass
        
    def boundingRect(self) -> QRectF:
        """Return bounding rectangle."""
        if self.cam_profile:
            # Calculate bounds from cam profile
            xs = [p.x() for p in self.cam_profile]
            ys = [p.y() for p in self.cam_profile]
            margin = 50
            return QRectF(
                min(xs) - margin, min(ys) - margin,
                max(xs) - min(xs) + 2*margin,
                max(ys) - min(ys) + 2*margin
            )
        return QRectF(-100, -100, 200, 200)


class AnimatedGearTrain(QGraphicsObject):
    """Animated gear train visualization."""
    
    def __init__(self, mechanism_data: Dict, parent=None):
        super().__init__(parent)
        
        self.mechanism_data = mechanism_data
        self._base_rotation = 0.0
        
        # Extract data
        self.gears = mechanism_data.get("gears", [])
        
        # Visual elements
        self.gear_items: List[QGraphicsItem] = []
        
        # Animation
        self.animation = QPropertyAnimation(self, b"baseRotation")
        self.animation.setDuration(8000)
        self.animation.setStartValue(0)
        self.animation.setEndValue(360)
        self.animation.setLoopCount(-1)
        
        self._create_visuals()
        
    def _create_visuals(self):
        """Create gear visuals."""
        for i, gear_data in enumerate(self.gears):
            center = gear_data.get("center", QPointF(i * 100, 0))
            radius = gear_data.get("radius", 40)
            teeth = gear_data.get("teeth", 20)
            
            # Create gear group
            gear_group = QGraphicsItemGroup(self)
            
            # Gear body
            body = QGraphicsEllipseItem(
                center.x() - radius,
                center.y() - radius,
                radius * 2,
                radius * 2
            )
            body.setPen(QPen(MechanismColors.GEAR_TEETH, 2))
            body.setBrush(QBrush(MechanismColors.GEAR_BODY))
            gear_group.addToGroup(body)
            
            # Simplified teeth (just markers)
            for j in range(teeth):
                angle = j * 360 / teeth
                angle_rad = math.radians(angle)
                
                tooth_inner = radius - 5
                tooth_outer = radius + 5
                
                tooth_line = QGraphicsLineItem(
                    center.x() + tooth_inner * math.cos(angle_rad),
                    center.y() + tooth_inner * math.sin(angle_rad),
                    center.x() + tooth_outer * math.cos(angle_rad),
                    center.y() + tooth_outer * math.sin(angle_rad)
                )
                tooth_line.setPen(QPen(MechanismColors.GEAR_TEETH, 3))
                gear_group.addToGroup(tooth_line)
                
            # Center hole
            hole_radius = 5
            hole = QGraphicsEllipseItem(
                center.x() - hole_radius,
                center.y() - hole_radius,
                hole_radius * 2,
                hole_radius * 2
            )
            hole.setPen(QPen(Qt.GlobalColor.black, 2))
            hole.setBrush(QBrush(Qt.GlobalColor.white))
            gear_group.addToGroup(hole)
            
            gear_group.setTransformOriginPoint(center)
            self.gear_items.append(gear_group)
            
    @pyqtProperty(float)
    def baseRotation(self):
        """Get base rotation."""
        return self._base_rotation
        
    @baseRotation.setter
    def baseRotation(self, value):
        """Set rotation for all gears."""
        self._base_rotation = value
        
        # Update each gear rotation based on gear ratios
        for i, (gear_item, gear_data) in enumerate(zip(self.gear_items, self.gears)):
            # First gear rotates at base speed
            if i == 0:
                gear_item.setRotation(value)
            else:
                # Others rotate based on gear ratio
                prev_teeth = self.gears[i-1].get("teeth", 20)
                curr_teeth = gear_data.get("teeth", 20)
                ratio = prev_teeth / curr_teeth
                
                # Alternate direction for meshing gears
                direction = -1 if i % 2 == 1 else 1
                gear_item.setRotation(value * ratio * direction)
                
    def start_animation(self):
        """Start the animation."""
        self.animation.start()
        
    def stop_animation(self):
        """Stop the animation."""
        self.animation.stop()
        
    def reset_animation(self):
        """Reset to initial position."""
        self.stop_animation()
        self.baseRotation = 0
        
    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget=None):
        """Paint method (required for QGraphicsObject)."""
        pass
        
    def boundingRect(self) -> QRectF:
        """Return bounding rectangle."""
        if self.gears:
            margin = 50
            min_x = min(g.get("center", QPointF()).x() - g.get("radius", 40) for g in self.gears) - margin
            max_x = max(g.get("center", QPointF()).x() + g.get("radius", 40) for g in self.gears) + margin
            min_y = min(g.get("center", QPointF()).y() - g.get("radius", 40) for g in self.gears) - margin
            max_y = max(g.get("center", QPointF()).y() + g.get("radius", 40) for g in self.gears) + margin
            return QRectF(min_x, min_y, max_x - min_x, max_y - min_y)
        return QRectF(-200, -200, 400, 400)