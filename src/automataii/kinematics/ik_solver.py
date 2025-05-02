import math
import logging
from PyQt6.QtCore import QPointF, QLineF
from PyQt6.QtGui import QTransform

def solve_ik_ccd(chain, target_pos, iterations=10, tolerance=1.0):
    """Solve inverse kinematics using Cyclic Coordinate Descent algorithm.

    Args:
        chain (list): List of CharacterPartItem objects forming the kinematic chain,
                      ordered from base to end effector.
        target_pos (QPointF): The target position in scene coordinates.
        iterations (int): Maximum number of iterations.
        tolerance (float): Position error tolerance to stop early.
    """
    if not chain:
        logging.warning("IK solver called with empty chain.")
        return

    end_effector_item = chain[-1]
    # end_effector_offset is the pivot point of the end effector part itself.
    # For IK, the target is usually the tip/edge of the end effector, not its pivot.
    # Let's assume end_effector_offset is the point on the end_effector we want to reach target_pos.
    # If end_effector_offset is None, we can default to its center or a predefined point.
    if end_effector_item.end_effector_offset:
        end_effector_local_pos = end_effector_item.end_effector_offset
    else:
        # Default to the center of the end effector item if no specific offset is set.
        # This might not be ideal for all parts, but provides a fallback.
        end_effector_local_pos = end_effector_item.boundingRect().center()
        # logging.warning(f"End effector item {end_effector_item.part_info.name} has no end_effector_offset. Using boundingRec.center() as IK target point on item.")

    # The number of movable joints is len(chain) - 1.
    # The items in the chain are indexed 0 (base) to N-1 (end_effector).
    # The joints are between item[j] and item[j+1].
    # We iterate from the joint closest to the end effector (N-2 -> N-1)
    # down to the joint closest to the base (0 -> 1).
    # So, the parent item whose rotation we modify is chain[j].

    for iteration in range(iterations):
        if not end_effector_item.scene():
            logging.warning(f"End effector item {end_effector_item.part_info.name} not in scene at start of IK iteration.")
            return
        current_ee_scene_pos = end_effector_item.mapToScene(end_effector_local_pos)
        error = QLineF(current_ee_scene_pos, target_pos).length()

        if error < tolerance:
            logging.debug(f"IK solved in {iteration+1} iterations, error: {error:.2f}")
            return

        # Iterate from the item just before the end-effector, down to the base item.
        # chain[j] is the item whose rotation we are adjusting.
        # Its anchor point (transformOriginPoint) is the pivot for this adjustment.
        for j in range(len(chain) - 2, -1, -1): # Iterate from N-2 down to 0
            current_item_to_rotate = chain[j]

            # If the current item is fixed (e.g., torso), skip its rotation.
            if current_item_to_rotate.is_fixed:
                logging.debug(f"Skipping rotation for fixed item: {current_item_to_rotate.part_info.name}")
                continue

            # The pivot for rotation is the anchor point of current_item_to_rotate.
            # In local coords of current_item_to_rotate, this is current_item_to_rotate.anchor_offset
            # In scene coords, this is current_item_to_rotate.mapToScene(current_item_to_rotate.anchor_offset)
            pivot_scene_pos = current_item_to_rotate.mapToScene(current_item_to_rotate.anchor_offset)

            # Current end effector position in scene coordinates
            # This needs to be recalculated inside the loop as previous rotations affect it.
            if not end_effector_item.scene():
                logging.warning(f"End effector item {end_effector_item.part_info.name} not in scene during IK inner loop.")
                break
            current_ee_scene_pos = end_effector_item.mapToScene(end_effector_local_pos)

            vec_pivot_to_ee = current_ee_scene_pos - pivot_scene_pos
            vec_pivot_to_target = target_pos - pivot_scene_pos

            # Calculate angle between an_to_ef and an_to_target
            # Using QLineF for angle calculation for simplicity and robustness
            line_pivot_to_ee = QLineF(pivot_scene_pos, current_ee_scene_pos)
            line_pivot_to_target = QLineF(pivot_scene_pos, target_pos)

            if line_pivot_to_ee.length() < 1e-6 or line_pivot_to_target.length() < 1e-6:
                continue # Avoid division by zero or unstable calculations

            angle_to_ee_deg = line_pivot_to_ee.angle()
            angle_to_target_deg = line_pivot_to_target.angle()

            # angleTo() gives angle in degrees, 0-360. We need the signed shortest angle.
            angle_diff_deg = angle_to_target_deg - angle_to_ee_deg

            # Normalize angle_diff_deg to be between -180 and 180
            while angle_diff_deg > 180:
                angle_diff_deg -= 360
            while angle_diff_deg < -180:
                angle_diff_deg += 360

            # Clamp rotation to avoid overshooting, e.g. max 30 degrees per step
            # max_rot_step = 30.0
            # angle_diff_deg = max(-max_rot_step, min(max_rot_step, angle_diff_deg))

            # Apply rotation to current_item_to_rotate around its anchor_offset
            # The CharacterPartItem.setRotation() handles rotation around its transformOriginPoint (anchor_offset)
            new_rotation = current_item_to_rotate.rotation() + angle_diff_deg
            # TODO: Apply joint angle limits here by clamping new_rotation if necessary
            # based on parent/child joint constraints if they exist.
            current_item_to_rotate.setRotation(new_rotation)

    # After all iterations, check final error
    if end_effector_item.scene():
        final_pos = end_effector_item.mapToScene(end_effector_local_pos)
        final_error = QLineF(final_pos, target_pos).length()
        logging.debug(f"IK finished after {iterations} iterations, final error: {final_error:.2f}")
    else:
        logging.warning("IK finished, but end effector item was no longer in scene.")

# Helper function (if needed for manual transform updates)
# def update_transform_based_on_parent(item, parent_item):
#     # Implementation depends on how joints and transforms are managed
#     pass