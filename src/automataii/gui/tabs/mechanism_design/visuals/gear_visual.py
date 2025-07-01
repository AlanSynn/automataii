# src/automataii/gui/tabs/mechanism_design/visuals/gear_visual.py
from PyQt6.QtWidgets import QGraphicsEllipseItem
from PyQt6.QtGui import QPen, QColor, QBrush
from PyQt6.QtCore import QRectF, QPointF
import numpy as np

def create(layer_data, scene_manager, transform, is_preview=False):
    """(Strategy) Creates visuals for a gear mechanism."""
    items = []
    debug_items = []
    color = QColor("#3498db") if is_preview else QColor("#1abc9c")
    
    # Sun gear
    sun_gear = QGraphicsEllipseItem()
    sun_gear.setPen(QPen(color, 2))
    sun_gear.setBrush(QBrush(color.lighter(150)))
    scene_manager.scene.addItem(sun_gear)
    items.append(sun_gear)

    # Planet gear
    planet_gear = QGraphicsEllipseItem()
    planet_gear.setPen(QPen(color.darker(120), 2))
    planet_gear.setBrush(QBrush(color.darker(120).lighter(150)))
    scene_manager.scene.addItem(planet_gear)
    items.append(planet_gear)
    
    return items, debug_items

def update(layer_data, time, visual_items, transform):
    """(Strategy) Updates visuals for a gear mechanism."""
    if len(visual_items) != 2: return None

    sun_gear, planet_gear = visual_items
    params = layer_data.get("params", {})
    sun_radius = params.get("sun_radius", 50)
    planet_radius = params.get("planet_radius", 25)
    
    sun_center = transform(layer_data.get("key_points", {}).get("sun_center", [0,0]))
    
    sun_gear.setRect(QRectF(sun_center.x() - sun_radius, sun_center.y() - sun_radius, 2 * sun_radius, 2 * sun_radius))
    
    # Planet orbits the sun
    orbit_radius = sun_radius + planet_radius
    angle = time
    planet_x = sun_center.x() + orbit_radius * np.cos(angle)
    planet_y = sun_center.y() + orbit_radius * np.sin(angle)
    
    planet_gear.setRect(QRectF(planet_x - planet_radius, planet_y - planet_radius, 2 * planet_radius, 2 * planet_radius))
    
    # For gears, the "output" could be the planet center
    return planet_gear.rect().center()

def get_initial_output(layer_data, transform):
    """(Strategy) Calculates the initial output position for a gear mechanism."""
    params = layer_data.get("params", {})
    sun_radius = params.get("sun_radius", 50)
    planet_radius = params.get("planet_radius", 25)
    
    sun_center = transform(layer_data.get("key_points", {}).get("sun_center", [0,0]))
    
    # This should match the initial state in the update function
    orbit_radius = sun_radius + planet_radius
    angle = 0
    planet_x = sun_center.x() + orbit_radius * np.cos(angle)
    planet_y = sun_center.y() + orbit_radius * np.sin(angle)
    
    return QPointF(planet_x, planet_y)
