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
    if not end_effector_item.end_effector_offset:
        logging.warning(f"End effector item {end_effector_item.part_info.name} has no end_effector_offset defined.")
        return

    end_effector_local_pos = end_effector_item.end_effector_offset
    num_joints = len(chain) - 1

    for iteration in range(iterations):
        # Get current global position of end effector
        # Check if item is still in a scene before mapping
        if not end_effector_item.scene():
            logging.warning(f"End effector item {end_effector_item.part_info.name} not in scene during IK solve.")
            return
        current_pos = end_effector_item.mapToScene(end_effector_local_pos)
        error = QLineF(current_pos, target_pos).length()

        if error < tolerance:
            logging.debug(f"IK solved in {iteration+1} iterations, error: {error:.2f}")
            return

        # Iterate through chain from end to root (item closest to end effector first)
        for i in range(num_joints - 1, -1, -1):
            # The item controlling the joint is chain[i]
            # The joint connects chain[i] (parent) to chain[i+1] (child)
            parent_item = chain[i]
            child_item = chain[i+1]

            # Find the correct joint connecting parent to child
            joint = None
            for j in parent_item.child_joints:
                if j.child_item == child_item:
                    joint = j
                    break

            if not joint:
                logging.warning(f"Could not find joint between {parent_item.part_info.name} and {child_item.part_info.name} in chain.")
                continue

            # Get global joint position
            # Check if parent item is still in scene
            if not parent_item.scene():
                 logging.warning(f"Parent item {parent_item.part_info.name} not in scene during IK joint calculation.")
                 continue
            joint_global_pos = joint.get_global_pos()

            # Recalculate current end effector position (it might have changed)
            if not end_effector_item.scene():
                logging.warning(f"End effector item {end_effector_item.part_info.name} not in scene during IK inner loop.")
                break # Exit inner loop if end effector removed
            current_pos = end_effector_item.mapToScene(end_effector_local_pos)

            # Vector from joint to current end effector
            vec_to_current = current_pos - joint_global_pos
            # Vector from joint to target
            vec_to_target = target_pos - joint_global_pos

            len_current = vec_to_current.manhattanLength() # Use manhattanLength for efficiency?
            len_target = vec_to_target.manhattanLength()

            # Calculate angle difference only if vectors are non-zero
            if len_current > 1e-6 and len_target > 1e-6:
                # Normalize vectors
                norm_current = vec_to_current / math.sqrt(QPointF.dotProduct(vec_to_current, vec_to_current))
                norm_target = vec_to_target / math.sqrt(QPointF.dotProduct(vec_to_target, vec_to_target))

                dot_product = QPointF.dotProduct(norm_current, norm_target)
                dot_product = max(-1.0, min(1.0, dot_product)) # Clamp for acos stability

                angle_diff_rad = math.acos(dot_product)

                # Determine rotation direction (using cross product Z in 2D)
                cross_product_z = norm_current.x() * norm_target.y() - norm_current.y() * norm_target.x()
                if cross_product_z < 0:
                    angle_diff_rad = -angle_diff_rad # Clockwise rotation

                angle_diff_deg = math.degrees(angle_diff_rad)

                # --- Apply Rotation around Joint using QTransform --- #
                # Get the joint position in the parent's local coordinates
                joint_local_pos = joint.parent_pos

                # Get the current transform of the parent item
                current_transform = parent_item.transform()

                # Create a new transform that applies the rotation around the local joint point
                # 1. Translate origin to joint position
                # 2. Rotate
                # 3. Translate origin back
                new_transform = QTransform().translate(joint_local_pos.x(), joint_local_pos.y())\
                                          .rotate(angle_diff_deg)\
                                          .translate(-joint_local_pos.x(), -joint_local_pos.y()) \
                                          * current_transform # Apply rotation ON TOP of current transform

                # TODO: Apply joint angle limits by clamping angle_diff_deg if needed

                # --- Apply Transform only if parent is not the fixed base --- #
                if i > 0: # chain[0] is the fixed base, don't rotate it
                    parent_item.setTransform(new_transform)
                elif i == 0: # Special case for the joint connected to the fixed base
                    # Apply the rotation to the child item (chain[1]) instead
                    # We need the transform relative to the child's coordinate system
                    # This requires careful recalculation or assumptions.
                    # --- SIMPLIFICATION ATTEMPT: Apply world rotation to child ---
                    # This is likely NOT mathematically correct for nested rotations,
                    # but might visually work for a 2-link chain like torso-head.
                    # Get the joint position in the CHILD's local coordinates
                    child_joint_local_pos = joint.child_pos
                    child_current_transform = child_item.transform()
                    # Transform to apply rotation around child's joint pos
                    child_new_transform = QTransform().translate(child_joint_local_pos.x(), child_joint_local_pos.y())\
                                                    .rotate(angle_diff_deg)\
                                                    .translate(-child_joint_local_pos.x(), -child_joint_local_pos.y()) \
                                                    * child_current_transform
                    child_item.setTransform(child_new_transform)
                    logging.debug(f"Applied rotation to child ({child_item.part_info.name}) for base joint.")
                # --- End QTransform Rotation --- #

                # --- Important: Update transforms for all items affected by this rotation ---
                # This requires knowing the hierarchy. If items are parented correctly
                # in the QGraphicsScene, setting rotation on the parent *should*
                # automatically update children's scene positions.
                # If not using scene parenting for kinematics, manual update is needed.
                # Example (if manual update needed):
                # for k in range(i + 1, len(chain)):
                #     chain[k].update_transform_based_on_parent(chain[k-1])

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