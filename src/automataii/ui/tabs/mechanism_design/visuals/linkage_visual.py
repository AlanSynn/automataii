# src/automataii/gui/tabs/mechanism_design/visuals/linkage_visual.py
import logging
import numpy as np
from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QBrush, QColor, QPen, QPolygonF
from PyQt6.QtWidgets import QGraphicsEllipseItem, QGraphicsLineItem, QGraphicsPolygonItem

from automataii.config.z_indices import Z_MECHANISM_PIVOT

logger = logging.getLogger(__name__)


def create(layer_data, scene_manager, transform, is_preview=False):
    """(Strategy) Creates visuals for a 4-bar linkage with enhanced graphics."""
    logger.info(f"LinkageVisual: Creating 4-bar linkage visuals (preview={is_preview})")
    logger.info(f"LinkageVisual: Layer data type: {layer_data.get('type')}, original_json_type: {layer_data.get('original_json_type')}")
    logger.info(f"LinkageVisual: Scene bounds: {scene_manager.scene.sceneRect()}")
    items = []
    debug_items = []

    # Colors exactly matching recommendation dialog
    driver_color = QColor("#e74c3c")  # Red for driver link
    coupler_color = QColor("#2ecc71")  # Green for coupler link
    rocker_color = QColor("#f39c12")  # Orange for rocker link

    line_width = 4  # Same as dialog
    z_value = Z_MECHANISM_PIVOT + 10  # High Z-index to ensure visibility

    # Create links with different colors
    driver_link = QGraphicsLineItem()
    driver_link.setPen(
        QPen(driver_color, line_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    )
    driver_link.setZValue(z_value)
    scene_manager.scene.addItem(driver_link)
    items.append(driver_link)
    logger.info(f"LinkageVisual: Created driver link with Z-value {z_value}, scene={driver_link.scene() is not None}")

    coupler_link = QGraphicsPolygonItem()  # Use polygon for triangular coupler
    coupler_link.setPen(QPen(coupler_color, 2))  # Same pen width as dialog
    coupler_link.setBrush(QBrush(coupler_color.lighter(160)))  # Same brush as dialog
    coupler_link.setZValue(z_value)
    scene_manager.scene.addItem(coupler_link)
    items.append(coupler_link)
    logger.info(f"LinkageVisual: Created coupler link with Z-value {z_value}")

    rocker_link = QGraphicsLineItem()
    rocker_link.setPen(
        QPen(rocker_color, line_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    )
    rocker_link.setZValue(z_value)
    scene_manager.scene.addItem(rocker_link)
    items.append(rocker_link)
    logger.info(f"LinkageVisual: Created rocker link with Z-value {z_value}")

    # Don't draw pivot points - recommendation dialog doesn't show them
    # Only log key points for debugging
    key_points = layer_data.get("key_points", {})
    logger.info(f"LinkageVisual: Key points available: {list(key_points.keys())}")

    if key_points:
        for key, point in key_points.items():
            if point:
                pos = transform(point)
                logger.info(f"LinkageVisual: {key} at original coords {point} transformed to scene coords ({pos.x():.1f}, {pos.y():.1f})")

    # Create coupler point marker (red dot) - same size as dialog (6x6)
    coupler_marker = QGraphicsEllipseItem(-3, -3, 6, 6)  # Same size as dialog
    coupler_marker.setBrush(QBrush(QColor("#ff0000")))  # Same color as dialog
    coupler_marker.setPen(QPen(QColor("#ff0000")))  # Same pen as dialog
    coupler_marker.setZValue(z_value + 10)  # Highest Z-value
    scene_manager.scene.addItem(coupler_marker)
    items.append(coupler_marker)
    logger.info(f"LinkageVisual: Created coupler marker with Z-value {z_value + 10}")

    # Set initial positions using EXACT same logic as recommendation dialog
    # Use the first frame from simulation data if available, otherwise use key_points
    full_sim_data = layer_data.get("full_simulation_data", {})
    if full_sim_data and "joint_positions" in full_sim_data:
        # EXACT same logic as dialog: use frame 0 from simulation
        joint_pos = full_sim_data["joint_positions"]
        frame_idx = 0

        if (joint_pos.get("p1_positions") and
            joint_pos.get("p2_positions") and
            joint_pos.get("p3_positions") and
            joint_pos.get("p4_positions")):

            p1 = transform(joint_pos["p1_positions"][frame_idx])
            p2 = transform(joint_pos["p2_positions"][frame_idx])
            p3 = transform(joint_pos["p3_positions"][frame_idx])
            p4 = transform(joint_pos["p4_positions"][frame_idx])

            # Set initial positions exactly like dialog
            driver_link.setLine(p1.x(), p1.y(), p3.x(), p3.y())
            rocker_link.setLine(p4.x(), p4.y(), p2.x(), p2.y())

            # Calculate initial coupler and marker positions - same as dialog
            params = layer_data.get("parameters", {})
            coupler_point_x = params.get("p_x", 0.0)
            coupler_point_y = params.get("p_y", 0.0)

            p3_pos = np.array([p3.x(), p3.y()])
            p4_pos = np.array([p4.x(), p4.y()])
            coupler_vec = p4_pos - p3_pos

            if np.linalg.norm(coupler_vec) > 0:
                coupler_unit = coupler_vec / np.linalg.norm(coupler_vec)
                coupler_normal = np.array([-coupler_unit[1], coupler_unit[0]])
                p_coupler_pos = p3_pos + coupler_point_x * coupler_unit + coupler_point_y * coupler_normal
                p_coupler = QPointF(p_coupler_pos[0], p_coupler_pos[1])
            else:
                p_coupler = p3

            # Set initial triangle - same area check as dialog
            p3_np = np.array([p3.x(), p3.y()])
            p4_np = np.array([p4.x(), p4.y()])
            p_coupler_np = np.array([p_coupler.x(), p_coupler.y()])

            area = (
                abs(
                    p3_np[0] * (p4_np[1] - p_coupler_np[1])
                    + p4_np[0] * (p_coupler_np[1] - p3_np[1])
                    + p_coupler_np[0] * (p3_np[1] - p4_np[1])
                )
                / 2
            )

            if area < 1e-3:
                # Degenerate triangle, draw as line - same as dialog
                coupler_link.setPolygon(QPolygonF([p3, p4]))
            else:
                # Full triangle - same as dialog
                triangle_polygon = QPolygonF([p3, p4, p_coupler])
                coupler_link.setPolygon(triangle_polygon)

            # Set marker position - same size as dialog (6x6)
            coupler_marker.setRect(p_coupler.x() - 3, p_coupler.y() - 3, 6, 6)

            logger.info(f"LinkageVisual: Set initial positions from sim data - P1:({p1.x():.1f},{p1.y():.1f}) P2:({p2.x():.1f},{p2.y():.1f}) P3:({p3.x():.1f},{p3.y():.1f}) P4:({p4.x():.1f},{p4.y():.1f})")
    else:
        # Fallback to key_points if no simulation data
        key_points = layer_data.get("key_points", {})
        if key_points:
            ground_pivot_1 = key_points.get("ground_pivot_1")
            ground_pivot_2 = key_points.get("ground_pivot_2")
            if ground_pivot_1 and ground_pivot_2:
                p1 = transform(ground_pivot_1)
                p2 = transform(ground_pivot_2)
                # Set initial line positions to make them visible
                driver_link.setLine(p1.x(), p1.y(), p1.x() + 50, p1.y() - 50)
                rocker_link.setLine(p2.x(), p2.y(), p2.x() - 50, p2.y() - 50)
                logger.info(f"LinkageVisual: Set initial positions from key points - Driver: ({p1.x():.1f},{p1.y():.1f}), Rocker: ({p2.x():.1f},{p2.y():.1f})")

    logger.info(f"LinkageVisual: Created {len(items)} main items and {len(debug_items)} debug items")

    # Verify all items are in scene
    for i, item in enumerate(items):
        logger.info(f"LinkageVisual: Item {i} ({type(item).__name__}) in scene: {item.scene() is not None}, visible: {item.isVisible()}")

    return items, debug_items


def update(layer_data, time, visual_items, transform):
    """(Strategy) Updates visuals for a 4-bar linkage with enhanced triangular coupler using EXACT dialog alignment."""
    if len(visual_items) != 4:
        logger.warning(f"LinkageVisual: Expected 4 visual items, got {len(visual_items)}")
        return None

    driver, coupler_poly, rocker, coupler_marker = visual_items
    sim_data = layer_data.get("full_simulation_data", {})

    # Use dialog-aligned data for exact consistency if available
    is_dialog_aligned = layer_data.get("dialog_aligned", False)
    user_path_aligned = layer_data.get("user_path_aligned_np")
    mech_path_aligned = layer_data.get("mech_path_aligned_np")

    if not sim_data:
        logger.warning("LinkageVisual: No simulation data available")
        # Try to use key_points for static display
        key_points = layer_data.get("key_points", {})
        if key_points:
            logger.info("LinkageVisual: Using key_points for static display")
            p1 = transform(key_points.get("ground_pivot_1", [0, 0]))
            p2 = transform(key_points.get("ground_pivot_2", [0, 0]))
            p3 = transform(key_points.get("crank_end", [0, 0]))
            p4 = transform(key_points.get("rocker_end", [0, 0]))

            driver.setLine(p1.x(), p1.y(), p3.x(), p3.y())
            rocker.setLine(p2.x(), p2.y(), p4.x(), p4.y())

            # Simple triangle for coupler
            triangle = QPolygonF([p3, p4, QPointF((p3.x() + p4.x())/2, (p3.y() + p4.y())/2 - 30)])
            coupler_poly.setPolygon(triangle)

            # Place marker at coupler point
            coupler_marker.setRect((p3.x() + p4.x())/2 - 3, (p3.y() + p4.y())/2 - 30 - 3, 6, 6)
        return None

    num_frames = len(sim_data.get("coupler_path", []))
    if num_frames == 0:
        logger.warning("LinkageVisual: No coupler path frames available")
        return None

    frame_index = int((time % (2 * np.pi)) / (2 * np.pi) * num_frames) % num_frames
    logger.debug(f"LinkageVisual: Updating frame {frame_index}/{num_frames} at time {time:.2f}")

    if is_dialog_aligned and "joint_positions" in sim_data:
        # Use EXACT simulation data from the dialog for perfect consistency
        joint_pos = sim_data["joint_positions"]

        # Use exact positions as they appear in the dialog
        def get_dialog_pos(key, frame):
            path = joint_pos.get(key, [])
            if path and frame < len(path):
                return transform(path[frame])
            return transform([0, 0])

        p1 = get_dialog_pos("p1_positions", frame_index)
        p2 = get_dialog_pos("p2_positions", frame_index)
        p3 = get_dialog_pos("p3_positions", frame_index)
        p4 = get_dialog_pos("p4_positions", frame_index)
    else:
        # Fallback to original logic
        def get_pos(key, frame):
            # Check in joint_positions first
            joint_positions = sim_data.get("joint_positions", {})
            path = joint_positions.get(key, [])
            if path and frame < len(path):
                return transform(path[frame])

            # Fallback to direct sim_data
            path = sim_data.get(key, [])
            if path and frame < len(path):
                return transform(path[frame])

            # Fallback to key_points if available
            kp = layer_data.get("key_points", {}).get(key.replace("_positions", ""))
            return transform(kp) if kp else transform([0, 0])

        p1 = get_pos("p1_positions", frame_index)
        p2 = get_pos("p2_positions", frame_index)
        p3 = get_pos("p3_positions", frame_index)
        p4 = get_pos("p4_positions", frame_index)

    logger.debug(f"LinkageVisual: Joint positions - P1:({p1.x():.1f},{p1.y():.1f}) P2:({p2.x():.1f},{p2.y():.1f}) P3:({p3.x():.1f},{p3.y():.1f}) P4:({p4.x():.1f},{p4.y():.1f})")

    # Update driver and rocker as lines - EXACT same as dialog
    driver.setLine(p1.x(), p1.y(), p3.x(), p3.y())
    rocker.setLine(p4.x(), p4.y(), p2.x(), p2.y())

    # Calculate coupler point for triangular coupler - EXACT same logic as dialog
    params = layer_data.get("parameters", {})
    coupler_point_x = params.get("p_x", 0.0)
    coupler_point_y = params.get("p_y", 0.0)

    # Calculate coupler point position using EXACT same method as dialog
    p3_pos = np.array([p3.x(), p3.y()])
    p4_pos = np.array([p4.x(), p4.y()])
    coupler_vec = p4_pos - p3_pos

    if np.linalg.norm(coupler_vec) > 0:
        coupler_unit = coupler_vec / np.linalg.norm(coupler_vec)
        coupler_normal = np.array([-coupler_unit[1], coupler_unit[0]])
        p_coupler_pos = p3_pos + coupler_point_x * coupler_unit + coupler_point_y * coupler_normal
        p_coupler = QPointF(p_coupler_pos[0], p_coupler_pos[1])
    else:
        p_coupler = p3

    # Create triangular coupler polygon - EXACT same logic as recommendation dialog
    # Calculate triangle area using the EXACT same formula as dialog
    p3_np = np.array([p3.x(), p3.y()])
    p4_np = np.array([p4.x(), p4.y()])
    p_coupler_np = np.array([p_coupler.x(), p_coupler.y()])

    area = (
        abs(
            p3_np[0] * (p4_np[1] - p_coupler_np[1])
            + p4_np[0] * (p_coupler_np[1] - p3_np[1])
            + p_coupler_np[0] * (p3_np[1] - p4_np[1])
        )
        / 2
    )

    if area < 1e-3:
        # Degenerate triangle, draw as line - EXACT same threshold and behavior as dialog
        logger.debug(f"LinkageVisual: Degenerate triangle (area={area:.6f}), drawing as line")
        coupler_poly.setPolygon(QPolygonF([p3, p4]))
    else:
        # Full triangle - EXACT same as dialog
        logger.debug(f"LinkageVisual: Drawing full triangle (area={area:.2f})")
        triangle_polygon = QPolygonF([p3, p4, p_coupler])
        coupler_poly.setPolygon(triangle_polygon)

    # Update coupler point marker position - EXACT same size (6x6) and positioning as dialog
    coupler_marker.setRect(p_coupler.x() - 3, p_coupler.y() - 3, 6, 6)

    return p_coupler


def get_initial_output(layer_data, transform):
    """(Strategy) Calculates the initial output position for a 4-bar linkage."""
    sim_data = layer_data.get("full_simulation_data", {})
    if not sim_data:
        return None

    coupler_path = sim_data.get("coupler_path", [])
    if not coupler_path:
        return None

    return transform(coupler_path[0])
