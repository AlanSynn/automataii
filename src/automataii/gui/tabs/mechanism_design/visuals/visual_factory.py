# src/automataii/gui/tabs/mechanism_design/visuals/visual_factory.py
from . import linkage_visual, cam_visual, gear_visual
from ..utils import get_scene_transform_function

def create(layer_data, scene_manager, is_preview=False):
    """
    (Factory/Strategy) Creates visualization for a mechanism.
    Returns a tuple of (visual_items, debug_items).
    """
    mech_type = layer_data.get("type")
    transform = get_scene_transform_function(layer_data)
    
    visual_items, debug_items = [], []

    if mech_type == "4_bar_linkage":
        visual_items, debug_items = linkage_visual.create(layer_data, scene_manager, transform, is_preview)
    elif mech_type == "cam":
        visual_items, debug_items = cam_visual.create(layer_data, scene_manager, transform, is_preview)
    elif mech_type in ["gear", "planetary_gear"]:
        visual_items, debug_items = gear_visual.create(layer_data, scene_manager, transform, is_preview)
    
    return visual_items, debug_items

def update(mechanism_id, layer_data, time, visual_items):
    """
    (Factory/Strategy) Updates visualization for a mechanism.
    """
    mech_type = layer_data.get("type")
    transform = get_scene_transform_function(layer_data)

    if mech_type == "4_bar_linkage":
        return linkage_visual.update(layer_data, time, visual_items, transform)
    elif mech_type == "cam":
        return cam_visual.update(layer_data, time, visual_items, transform)
    elif mech_type in ["gear", "planetary_gear"]:
        return gear_visual.update(layer_data, time, visual_items, transform)
    
    return None

def get_initial_output(layer_data):
    """
    (Factory/Strategy) Calculates the initial output position of a mechanism.
    This is used to align the mechanism with the skeleton.
    """
    mech_type = layer_data.get("type")
    transform = get_scene_transform_function(layer_data)

    if mech_type == "4_bar_linkage":
        return linkage_visual.get_initial_output(layer_data, transform)
    elif mech_type == "cam":
        return cam_visual.get_initial_output(layer_data, transform)
    elif mech_type in ["gear", "planetary_gear"]:
        return gear_visual.get_initial_output(layer_data, transform)
        
    return None
