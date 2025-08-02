# src/automataii/gui/tabs/mechanism_design/visuals/visual_factory.py
from ..utils import get_scene_transform_function
from . import belt_visual, cam_visual, gear_visual, linkage_visual, spring_visual


def create(layer_data, scene_manager, is_preview=False):
    """
    (Factory/Strategy) Creates visualization for a mechanism.
    Returns a tuple of (visual_items, debug_items).
    """
    mech_type = layer_data.get("type")
    original_json_type = layer_data.get("original_json_type", mech_type)
    transform = get_scene_transform_function(layer_data)

    visual_items, debug_items = [], []

    # Map recommendation dialog types to visual implementations
    if mech_type in ["4-Bar Linkage", "4_bar_linkage"] or original_json_type == "4-bar Coupler":
        visual_items, debug_items = linkage_visual.create(
            layer_data, scene_manager, transform, is_preview
        )
    elif mech_type in ["Cam & Follower", "cam"] or original_json_type in [
        "Cam-Follower",
        "Cam Follower",
    ]:
        visual_items, debug_items = cam_visual.create(
            layer_data, scene_manager, transform, is_preview
        )
    elif mech_type in [
        "Gears (Simple Pair)",
        "Planetary Gear",
        "gear",
        "planetary_gear",
    ] or original_json_type in ["Simple Gear", "Gear Contact", "Planetary Gear"]:
        visual_items, debug_items = gear_visual.create(
            layer_data, scene_manager, transform, is_preview
        )
    elif mech_type in ["Belt", "belt", "belt_pulley"] or original_json_type in [
        "Belt System",
        "Pulley System",
    ]:
        visual_items, debug_items = belt_visual.create(
            layer_data, scene_manager, transform, is_preview
        )
    elif mech_type in ["Spring", "spring", "spring_damper"] or original_json_type in [
        "Spring System",
        "Damper System",
    ]:
        visual_items, debug_items = spring_visual.create(
            layer_data, scene_manager, transform, is_preview
        )

    return visual_items, debug_items


def update(mechanism_id, layer_data, time, visual_items):
    """
    (Factory/Strategy) Updates visualization for a mechanism.
    """
    mech_type = layer_data.get("type")
    original_json_type = layer_data.get("original_json_type", mech_type)
    transform = get_scene_transform_function(layer_data)

    # Map recommendation dialog types to visual implementations
    if mech_type in ["4-Bar Linkage", "4_bar_linkage"] or original_json_type == "4-bar Coupler":
        return linkage_visual.update(layer_data, time, visual_items, transform)
    elif mech_type in ["Cam & Follower", "cam"] or original_json_type in [
        "Cam-Follower",
        "Cam Follower",
    ]:
        return cam_visual.update(layer_data, time, visual_items, transform)
    elif mech_type in [
        "Gears (Simple Pair)",
        "Planetary Gear",
        "gear",
        "planetary_gear",
    ] or original_json_type in ["Simple Gear", "Gear Contact", "Planetary Gear"]:
        return gear_visual.update(layer_data, time, visual_items, transform)
    elif mech_type in ["Belt", "belt", "belt_pulley"] or original_json_type in [
        "Belt System",
        "Pulley System",
    ]:
        return belt_visual.update(layer_data, time, visual_items, transform)
    elif mech_type in ["Spring", "spring", "spring_damper"] or original_json_type in [
        "Spring System",
        "Damper System",
    ]:
        return spring_visual.update(layer_data, time, visual_items, transform)

    return None


def get_initial_output(layer_data):
    """
    (Factory/Strategy) Calculates the initial output position of a mechanism.
    This is used to align the mechanism with the skeleton.
    """
    mech_type = layer_data.get("type")
    original_json_type = layer_data.get("original_json_type", mech_type)
    transform = get_scene_transform_function(layer_data)

    # Map recommendation dialog types to visual implementations
    if mech_type in ["4-Bar Linkage", "4_bar_linkage"] or original_json_type == "4-bar Coupler":
        return linkage_visual.get_initial_output(layer_data, transform)
    elif mech_type in ["Cam & Follower", "cam"] or original_json_type in [
        "Cam-Follower",
        "Cam Follower",
    ]:
        return cam_visual.get_initial_output(layer_data, transform)
    elif mech_type in [
        "Gears (Simple Pair)",
        "Planetary Gear",
        "gear",
        "planetary_gear",
    ] or original_json_type in ["Simple Gear", "Gear Contact", "Planetary Gear"]:
        return gear_visual.get_initial_output(layer_data, transform)
    elif mech_type in ["Belt", "belt", "belt_pulley"] or original_json_type in [
        "Belt System",
        "Pulley System",
    ]:
        return belt_visual.get_initial_output(layer_data, transform)
    elif mech_type in ["Spring", "spring", "spring_damper"] or original_json_type in [
        "Spring System",
        "Damper System",
    ]:
        return spring_visual.get_initial_output(layer_data, transform)

    return None
