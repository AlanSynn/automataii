"""
CAM mechanism visualizer implementation.
"""

import logging
from typing import Any

import numpy as np
from PyQt6.QtCore import QLineF, QPointF, Qt
from PyQt6.QtGui import QBrush, QColor, QPainterPath, QPen, QPolygonF
from PyQt6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsPathItem,
    QGraphicsPolygonItem,
    QGraphicsRectItem
)

from ..base import MechanismVisualizer


class CamVisualizer(MechanismVisualizer):
    """Visualizer for CAM and follower mechanisms."""
    
    CAM_COLOR = QColor(100, 150, 100)
    FOLLOWER_COLOR = QColor(150, 100, 100)
    ROD_COLOR = QColor(80, 80, 80)
    
    def create_visuals(self, mechanism_data: dict[str, Any]) -> list[QGraphicsItem]:
        """Create visual representation of CAM mechanism."""
        visual_items = []
        params = self.extract_params(mechanism_data)
        
        if not params:
            return visual_items
        
        # Extract CAM parameters with smaller default sizes
        base_radius = params.get("base_radius", 15.0)  # Reduced from 25
        eccentricity = params.get("eccentricity", 5.0)  # Reduced from 10
        follower_rod_length = params.get("follower_rod_length", 25.0)  # Reduced from 40
        
        # Apply scaling factors if available
        cam_scale_factor = mechanism_data.get('cam_scale_factor', 0.6)  # Smaller default scale
        rod_length_multiplier = mechanism_data.get('rod_length_multiplier', 0.8)
        
        # Apply scaling
        scaled_base_radius = base_radius * cam_scale_factor
        scaled_eccentricity = eccentricity * cam_scale_factor
        scaled_rod_length = follower_rod_length * rod_length_multiplier
        
        # Get CAM position - prioritize params over cam_position
        if "center_x" in params and "center_y" in params:
            cam_center = np.array([params["center_x"], params["center_y"]])
        elif 'cam_position' in mechanism_data and len(mechanism_data['cam_position']) >= 2:
            cam_center = np.array([mechanism_data['cam_position'][0], mechanism_data['cam_position'][1]])
        else:
            cam_center = np.array([400, 300])  # Default position
        
        # Create egg-shaped CAM profile with scaled dimensions
        cam_profile = self._create_egg_shape_profile(scaled_base_radius, scaled_eccentricity)
        
        # Transform to scene coordinates if transform function provided
        if self.config.transform_function:
            cam_center_scene = self.config.transform_function(cam_center)
        else:
            cam_center_scene = QPointF(cam_center[0], cam_center[1])
        
        # Create CAM polygon
        cam_polygon_points = []
        for point in cam_profile:
            point_offset = np.array(point) + cam_center
            if self.config.transform_function:
                scene_point = self.config.transform_function(point_offset)
            else:
                scene_point = QPointF(point_offset[0], point_offset[1])
            cam_polygon_points.append(scene_point)
        
        # Create CAM visual
        cam_polygon = QPolygonF(cam_polygon_points)
        cam_item = QGraphicsPolygonItem(cam_polygon)
        cam_item.setPen(QPen(self.CAM_COLOR.darker(150), 2))
        cam_item.setBrush(QBrush(self.CAM_COLOR))
        cam_item.setZValue(self.config.z_index_base)
        visual_items.append(cam_item)
        
        # Create follower - positioned above CAM
        follower_y = cam_center[1] - (scaled_base_radius + scaled_rod_length)
        follower_pos = np.array([cam_center[0], follower_y])
        
        if self.config.transform_function:
            follower_scene = self.config.transform_function(follower_pos)
        else:
            follower_scene = QPointF(follower_pos[0], follower_pos[1])
        
        # Follower rod
        rod = QGraphicsLineItem(QLineF(cam_center_scene, follower_scene))
        rod.setPen(QPen(self.ROD_COLOR, 3))
        rod.setZValue(self.config.z_index_base + 1)
        visual_items.append(rod)
        
        # Follower head (smaller size)
        follower_rect = QGraphicsRectItem(
            follower_scene.x() - 10, follower_scene.y() - 7, 20, 14  # Reduced size
        )
        follower_rect.setPen(QPen(self.FOLLOWER_COLOR.darker(150), 2))
        follower_rect.setBrush(QBrush(self.FOLLOWER_COLOR))
        follower_rect.setZValue(self.config.z_index_base + 2)
        visual_items.append(follower_rect)
        
        # CAM center pivot (smaller)
        pivot = QGraphicsEllipseItem(
            cam_center_scene.x() - 3, cam_center_scene.y() - 3, 6, 6  # Reduced size
        )
        pivot.setPen(QPen(QColor(255, 0, 0), 2))
        pivot.setBrush(QBrush(QColor(255, 0, 0)))
        pivot.setZValue(self.config.z_index_pivot)
        visual_items.append(pivot)
        
        return visual_items
    
    def update_visuals(self, visual_items: list[QGraphicsItem], 
                      mechanism_data: dict[str, Any]) -> None:
        """Update existing CAM visuals with new position and parameters."""
        if len(visual_items) < 4:
            return  # Not enough items to update
        
        params = self.extract_params(mechanism_data)
        if not params:
            return
        
        # Extract CAM parameters
        base_radius = params.get("base_radius", 15.0)
        eccentricity = params.get("eccentricity", 5.0)
        follower_rod_length = params.get("follower_rod_length", 25.0)
        
        # Apply scaling factors
        cam_scale_factor = mechanism_data.get('cam_scale_factor', 0.6)
        rod_length_multiplier = mechanism_data.get('rod_length_multiplier', 0.8)
        
        scaled_base_radius = base_radius * cam_scale_factor
        scaled_eccentricity = eccentricity * cam_scale_factor
        scaled_rod_length = follower_rod_length * rod_length_multiplier
        
        # Get CAM position - prioritize params over cam_position
        if "center_x" in params and "center_y" in params:
            cam_center = np.array([params["center_x"], params["center_y"]])
        elif 'cam_position' in mechanism_data and len(mechanism_data['cam_position']) >= 2:
            cam_center = np.array([mechanism_data['cam_position'][0], mechanism_data['cam_position'][1]])
        else:
            return  # Can't update without position
        
        # Transform center to scene coordinates
        if self.config.transform_function:
            cam_center_scene = self.config.transform_function(cam_center)
        else:
            cam_center_scene = QPointF(cam_center[0], cam_center[1])
        
        # Update CAM polygon (item 0)
        if isinstance(visual_items[0], QGraphicsPolygonItem):
            cam_profile = self._create_egg_shape_profile(scaled_base_radius, scaled_eccentricity)
            cam_polygon_points = []
            for point in cam_profile:
                point_offset = np.array(point) + cam_center
                if self.config.transform_function:
                    scene_point = self.config.transform_function(point_offset)
                else:
                    scene_point = QPointF(point_offset[0], point_offset[1])
                cam_polygon_points.append(scene_point)
            visual_items[0].setPolygon(QPolygonF(cam_polygon_points))
        
        # Update follower position
        follower_y = cam_center[1] - (scaled_base_radius + scaled_rod_length)
        follower_pos = np.array([cam_center[0], follower_y])
        
        if self.config.transform_function:
            follower_scene = self.config.transform_function(follower_pos)
        else:
            follower_scene = QPointF(follower_pos[0], follower_pos[1])
        
        # Update rod (item 1)
        if isinstance(visual_items[1], QGraphicsLineItem):
            visual_items[1].setLine(QLineF(cam_center_scene, follower_scene))
        
        # Update follower rectangle (item 2)
        if isinstance(visual_items[2], QGraphicsRectItem):
            visual_items[2].setRect(
                follower_scene.x() - 10, follower_scene.y() - 7, 20, 14
            )
        
        # Update pivot (item 3)
        if isinstance(visual_items[3], QGraphicsEllipseItem):
            visual_items[3].setRect(
                cam_center_scene.x() - 3, cam_center_scene.y() - 3, 6, 6
            )
    
    def _create_egg_shape_profile(self, base_radius: float, 
                                 eccentricity: float) -> list[list[float]]:
        """Create an egg-shaped cam profile."""
        points = []
        num_points = 100
        
        for i in range(num_points):
            theta = (i / num_points) * 2 * np.pi
            
            # Create egg shape
            lift = eccentricity * (1 + np.cos(theta)) / 2
            r = base_radius + lift
            
            # Convert to Cartesian
            x = r * np.cos(theta)
            y = r * np.sin(theta)
            
            points.append([x, y])
        
        return points