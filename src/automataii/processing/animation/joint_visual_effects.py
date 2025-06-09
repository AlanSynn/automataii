"""
Visual effects for enhancing joint connections in animated parts.
"""

import numpy as np
import cv2
from typing import Tuple, Optional, List
from enum import Enum

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QPainter, QBrush, QPen, QColor, QRadialGradient, QLinearGradient, QPixmap, QImage


class EffectType(Enum):
    """Types of visual effects for joints."""
    GLOW = "glow"
    SHADOW = "shadow"
    BLUR = "blur"
    OUTLINE = "outline"


class JointVisualEffects:
    """Creates visual effects to enhance joint connections."""
    
    @staticmethod
    def create_glow_effect(center: QPointF, radius: float, color: QColor, 
                          intensity: float = 0.8) -> QPixmap:
        """Create a glow effect around a joint.
        
        Args:
            center: Center point of the glow
            radius: Radius of the glow effect
            color: Glow color
            intensity: Glow intensity (0.0 to 1.0)
            
        Returns:
            QPixmap with glow effect
        """
        # Create pixmap with margin for glow
        size = int(radius * 4)
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Create radial gradient for glow
        gradient = QRadialGradient(size/2, size/2, radius * 2)
        
        # Set gradient colors with varying alpha
        glow_color = QColor(color)
        glow_color.setAlphaF(intensity)
        gradient.setColorAt(0.0, glow_color)
        
        glow_color.setAlphaF(intensity * 0.5)
        gradient.setColorAt(0.3, glow_color)
        
        glow_color.setAlphaF(intensity * 0.2)
        gradient.setColorAt(0.6, glow_color)
        
        glow_color.setAlphaF(0.0)
        gradient.setColorAt(1.0, glow_color)
        
        # Draw glow
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(size/2, size/2), radius * 2, radius * 2)
        
        painter.end()
        return pixmap
    
    @staticmethod
    def create_soft_shadow(size: QRectF, offset: QPointF = QPointF(2, 2),
                          blur_radius: float = 5.0, opacity: float = 0.3) -> QPixmap:
        """Create a soft shadow effect.
        
        Args:
            size: Size of the shadow area
            offset: Shadow offset from origin
            blur_radius: Blur radius for soft edge
            opacity: Shadow opacity
            
        Returns:
            QPixmap with shadow effect
        """
        # Create pixmap with margin for blur
        margin = int(blur_radius * 2)
        width = int(size.width() + margin * 2)
        height = int(size.height() + margin * 2)
        
        pixmap = QPixmap(width, height)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        # Convert to numpy for blur operation
        qimage = pixmap.toImage()
        qimage = qimage.convertToFormat(QImage.Format.Format_RGBA8888)
        
        width = qimage.width()
        height = qimage.height()
        ptr = qimage.bits()
        ptr.setsize(height * width * 4)
        arr = np.frombuffer(ptr, np.uint8).reshape((height, width, 4))
        
        # Create shadow shape
        shadow_color = int(255 * opacity)
        cv2.rectangle(arr, 
                     (margin, margin), 
                     (width - margin, height - margin),
                     (0, 0, 0, shadow_color), 
                     -1)
        
        # Apply Gaussian blur
        if blur_radius > 0:
            kernel_size = int(blur_radius * 2 + 1)
            arr[:, :, 3] = cv2.GaussianBlur(arr[:, :, 3], (kernel_size, kernel_size), blur_radius)
        
        # Convert back to QPixmap
        result_image = QImage(arr.data, width, height, width * 4, QImage.Format.Format_RGBA8888)
        result_pixmap = QPixmap.fromImage(result_image)
        
        return result_pixmap
    
    @staticmethod
    def apply_edge_softening(image: np.ndarray, edge_width: int = 10,
                           softness: float = 0.5) -> np.ndarray:
        """Soften edges of an image for smoother blending.
        
        Args:
            image: Input image (RGBA)
            edge_width: Width of edge to soften
            softness: Amount of softening (0.0 to 1.0)
            
        Returns:
            Image with softened edges
        """
        if image.shape[2] != 4:
            return image  # Need alpha channel
            
        h, w = image.shape[:2]
        result = image.copy()
        
        # Create distance transform from edges
        alpha = image[:, :, 3]
        dist_transform = cv2.distanceTransform(alpha, cv2.DIST_L2, 5)
        
        # Normalize distance transform
        max_dist = np.max(dist_transform)
        if max_dist > 0:
            dist_transform = dist_transform / max_dist
        
        # Apply softening to alpha channel
        edge_mask = dist_transform < (edge_width / max_dist) if max_dist > 0 else np.zeros_like(dist_transform)
        softened_alpha = alpha.copy()
        
        # Gradual fade at edges
        fade_factor = dist_transform * (1.0 / (edge_width / max_dist))
        fade_factor = np.clip(fade_factor, 0, 1)
        fade_factor = fade_factor ** (1.0 / softness)  # Power curve for smoothness
        
        softened_alpha[edge_mask] = (alpha[edge_mask] * fade_factor[edge_mask]).astype(np.uint8)
        result[:, :, 3] = softened_alpha
        
        return result
    
    @staticmethod
    def create_connection_bridge(point1: QPointF, point2: QPointF,
                               width: float = 20.0, color: QColor = QColor(255, 255, 255, 128)) -> QPixmap:
        """Create a visual bridge between two connection points.
        
        Args:
            point1: First connection point
            point2: Second connection point
            width: Width of the bridge
            color: Bridge color
            
        Returns:
            QPixmap with connection bridge
        """
        # Calculate bounding rect
        x1, y1 = point1.x(), point1.y()
        x2, y2 = point2.x(), point2.y()
        
        min_x = min(x1, x2) - width
        min_y = min(y1, y2) - width
        max_x = max(x1, x2) + width
        max_y = max(y1, y2) + width
        
        pixmap_width = int(max_x - min_x)
        pixmap_height = int(max_y - min_y)
        
        pixmap = QPixmap(pixmap_width, pixmap_height)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Translate to local coordinates
        painter.translate(-min_x, -min_y)
        
        # Create gradient along the connection
        gradient = QLinearGradient(point1, point2)
        gradient_color = QColor(color)
        
        gradient_color.setAlphaF(0.0)
        gradient.setColorAt(0.0, gradient_color)
        
        gradient_color.setAlphaF(color.alphaF())
        gradient.setColorAt(0.3, gradient_color)
        gradient.setColorAt(0.7, gradient_color)
        
        gradient_color.setAlphaF(0.0)
        gradient.setColorAt(1.0, gradient_color)
        
        # Draw connection with rounded caps
        pen = QPen(QBrush(gradient), width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(point1, point2)
        
        painter.end()
        return pixmap
    
    @staticmethod
    def apply_motion_blur(image: np.ndarray, angle: float, length: int = 10) -> np.ndarray:
        """Apply motion blur effect to simulate movement.
        
        Args:
            image: Input image
            angle: Angle of motion in degrees
            length: Length of motion blur
            
        Returns:
            Image with motion blur applied
        """
        if length <= 0:
            return image
            
        # Create motion blur kernel
        angle_rad = np.deg2rad(angle)
        kernel = np.zeros((length, length))
        
        # Calculate kernel center
        center = length // 2
        
        # Create line kernel for motion blur
        for i in range(length):
            offset = i - center
            x = int(center + offset * np.cos(angle_rad))
            y = int(center + offset * np.sin(angle_rad))
            
            if 0 <= x < length and 0 <= y < length:
                kernel[y, x] = 1.0
                
        # Normalize kernel
        kernel = kernel / np.sum(kernel)
        
        # Apply motion blur to each channel
        result = image.copy()
        for i in range(image.shape[2]):
            result[:, :, i] = cv2.filter2D(image[:, :, i], -1, kernel)
            
        return result
    
    @staticmethod
    def create_joint_highlight(joint_type: str, size: float = 30.0) -> QPixmap:
        """Create a highlight effect specific to joint type.
        
        Args:
            joint_type: Type of joint (e.g., 'shoulder', 'elbow', 'hip')
            size: Size of the highlight
            
        Returns:
            QPixmap with joint-specific highlight
        """
        pixmap = QPixmap(int(size * 2), int(size * 2))
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        center = QPointF(size, size)
        
        # Different styles for different joint types
        if joint_type in ['shoulder', 'hip']:
            # Ball joint style - circular with inner ring
            gradient = QRadialGradient(center, size)
            gradient.setColorAt(0.0, QColor(255, 255, 255, 200))
            gradient.setColorAt(0.3, QColor(200, 200, 255, 150))
            gradient.setColorAt(0.6, QColor(150, 150, 255, 100))
            gradient.setColorAt(1.0, QColor(100, 100, 255, 0))
            
            painter.setBrush(QBrush(gradient))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(center, size, size)
            
            # Inner ring
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(255, 255, 255, 150), 2))
            painter.drawEllipse(center, size * 0.4, size * 0.4)
            
        elif joint_type in ['elbow', 'knee']:
            # Hinge joint style - elliptical with axis line
            gradient = QRadialGradient(center, size)
            gradient.setColorAt(0.0, QColor(255, 200, 200, 200))
            gradient.setColorAt(0.4, QColor(255, 150, 150, 150))
            gradient.setColorAt(0.8, QColor(255, 100, 100, 50))
            gradient.setColorAt(1.0, QColor(255, 50, 50, 0))
            
            painter.setBrush(QBrush(gradient))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(center, size * 0.8, size)
            
            # Axis line
            painter.setPen(QPen(QColor(255, 255, 255, 100), 3))
            painter.drawLine(center.x() - size * 0.6, center.y(),
                           center.x() + size * 0.6, center.y())
            
        else:
            # Default style - simple glow
            gradient = QRadialGradient(center, size)
            gradient.setColorAt(0.0, QColor(255, 255, 200, 180))
            gradient.setColorAt(0.5, QColor(255, 255, 150, 100))
            gradient.setColorAt(1.0, QColor(255, 255, 100, 0))
            
            painter.setBrush(QBrush(gradient))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(center, size, size)
        
        painter.end()
        return pixmap