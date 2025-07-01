# src/automataii/gui/tabs/mechanism_design/visuals/linkage_visual.py
from PyQt6.QtWidgets import QGraphicsLineItem, QGraphicsEllipseItem
from PyQt6.QtGui import QPen, QColor
from PyQt6.QtCore import Qt, QPointF
import numpy as np

def create(layer_data, scene_manager, transform, is_preview=False):
    """(Strategy) Creates visuals for a 4-bar linkage."""
    items = []
    debug_items = []
    color = QColor("#3498db") if is_preview else QColor("#e74c3c")
    pen = QPen(color, 3)
    
    for _ in range(3): # driver, coupler, rocker
        link = QGraphicsLineItem()
        link.setPen(pen)
        scene_manager.scene.addItem(link)
        items.append(link)

    # Create debug visuals for pivots
    key_points = layer_data.get("key_points", {})
    pivots = [
        key_points.get("ground_pivot_1"),
        key_points.get("ground_pivot_2"),
        key_points.get("crank_end"),
        key_points.get("rocker_end"),
    ]
    for pivot in pivots:
        if pivot:
            pos = transform(pivot)
            dot = QGraphicsEllipseItem(pos.x() - 3, pos.y() - 3, 6, 6)
            dot.setBrush(QColor("red"))
            dot.setPen(QPen(Qt.PenStyle.NoPen))
            debug_items.append(dot)

    return items, debug_items

def update(layer_data, time, visual_items, transform):
    """(Strategy) Updates visuals for a 4-bar linkage."""
    if len(visual_items) != 3: return None

    driver, coupler, rocker = visual_items
    sim_data = layer_data.get("full_simulation_data", {})
    if not sim_data: return None

    num_frames = len(sim_data.get("coupler_path", []))
    if num_frames == 0: return None
        
    frame_index = int((time % (2 * np.pi)) / (2 * np.pi) * num_frames) % num_frames

    def get_pos(key, frame):
        path = sim_data.get(key, [])
        if path and frame < len(path):
            return transform(path[frame])
        # Fallback to key_points if available
        kp = layer_data.get("key_points", {}).get(key.replace("_positions", ""))
        return transform(kp) if kp else transform([0,0])

    p1 = get_pos("p1_positions", frame_index)
    p2 = get_pos("p2_positions", frame_index)
    p3 = get_pos("p3_positions", frame_index)
    p4 = get_pos("p4_positions", frame_index)

    driver.setLine(p1.x(), p1.y(), p3.x(), p3.y())
    coupler.setLine(p3.x(), p3.y(), p4.x(), p4.y())
    rocker.setLine(p4.x(), p4.y(), p2.x(), p2.y())

    return get_pos("coupler_path", frame_index)

def get_initial_output(layer_data, transform):
    """(Strategy) Calculates the initial output position for a 4-bar linkage."""
    sim_data = layer_data.get("full_simulation_data", {})
    if not sim_data: return None

    coupler_path = sim_data.get("coupler_path", [])
    if not coupler_path: return None

    return transform(coupler_path[0])
