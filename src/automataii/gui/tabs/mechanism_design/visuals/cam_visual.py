# src/automataii/gui/tabs/mechanism_design/visuals/cam_visual.py
from PyQt6.QtWidgets import QGraphicsEllipseItem, QGraphicsLineItem
from PyQt6.QtGui import QPen, QColor, QBrush
from PyQt6.QtCore import QRectF, QPointF
import numpy as np

def create(layer_data, scene_manager, transform, is_preview=False):
    """(Strategy) Creates visuals for a cam mechanism."""
    items = []
    debug_items = []
    color = QColor("#3498db") if is_preview else QColor("#9b59b6")
    
    cam_profile = QGraphicsEllipseItem() # Placeholder
    cam_profile.setPen(QPen(color, 3))
    cam_profile.setBrush(QBrush(color.lighter(150)))
    scene_manager.scene.addItem(cam_profile)
    items.append(cam_profile)

    follower = QGraphicsLineItem()
    follower.setPen(QPen(QColor("#34495e"), 3))
    scene_manager.scene.addItem(follower)
    items.append(follower)
    
    return items, debug_items

def update(layer_data, time, visual_items, transform):
    """(Strategy) Updates visuals for a cam mechanism."""
    # This is a simplified placeholder update logic
    if len(visual_items) != 2: return None
    
    cam_profile, follower = visual_items
    key_points = layer_data.get("key_points", {})
    cam_center = transform(key_points.get("cam_center", [0,0]))
    
    # Simple circular motion for preview
    radius = 50
    angle = time
    pos_x = cam_center.x() + radius * 0.5 * (1 + np.cos(angle))
    pos_y = cam_center.y()
    
    cam_profile.setRect(QRectF(cam_center.x() - radius, cam_center.y() - radius, 2 * radius, 2 * radius))
    follower.setLine(pos_x - 20, pos_y, pos_x + 20, pos_y)
    
    return follower.line().p1()

def get_initial_output(layer_data, transform):
    """(Strategy) Calculates the initial output position for a cam mechanism."""
    key_points = layer_data.get("key_points", {})
    cam_center = transform(key_points.get("cam_center", [0,0]))
    
    # This should match the initial state in the update function
    radius = 50
    angle = 0
    pos_x = cam_center.x() + radius * 0.5 * (1 + np.cos(angle))
    pos_y = cam_center.y()
    
    return QPointF(pos_x, pos_y)
