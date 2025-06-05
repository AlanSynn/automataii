import math
import logging
from PyQt6.QtCore import QPointF, QLineF
from PyQt6.QtGui import QTransform

def get_world_rotation(item):
    """아이템의 월드 좌표계 기준 회전각을 구합니다."""
    transform = item.sceneTransform()
    # QTransform에서 회전각 추출
    # m11 = cos(angle), m12 = -sin(angle)
    # m21 = sin(angle), m22 = cos(angle)
    angle_rad = math.atan2(transform.m21(), transform.m11())
    return math.degrees(angle_rad)

def solve_ik_ccd(chain, target_pos, iterations=10, tolerance=1.0):
    """Solve inverse kinematics using Cyclic Coordinate Descent algorithm with FABRIK-style constraints.

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

    if len(chain) < 2:
        logging.warning("IK solver requires at least 2 items in chain.")
        return

    # Store original bone lengths to maintain skeleton structure
    bone_lengths = []
    original_positions = []
    
    for i in range(len(chain)):
        item = chain[i]
        pos = item.mapToScene(item.anchor_offset)
        original_positions.append(pos)
        
        if i > 0:
            prev_pos = original_positions[i-1]
            length = QLineF(prev_pos, pos).length()
            bone_lengths.append(length)
            logging.debug(f"IK: Bone length between {chain[i-1].part_info.name} and {item.part_info.name}: {length:.2f}")

    # Check if the target is reachable
    total_length = sum(bone_lengths)
    base_pos = original_positions[0]
    target_distance = QLineF(base_pos, target_pos).length()
    
    if target_distance > total_length:
        logging.debug(f"IK: Target unreachable. Distance: {target_distance:.2f}, Total length: {total_length:.2f}")
        # Stretch the chain towards target
        _stretch_chain_to_target(chain, bone_lengths, base_pos, target_pos)
        return

    # Use FABRIK solver which better maintains bone lengths
    _solve_ik_fabrik(chain, bone_lengths, target_pos, iterations, tolerance)
    return
    
    # Original CCD implementation below (kept for reference but not used)
    end_effector_item = chain[-1]
    if end_effector_item.end_effector_offset:
        end_effector_local_pos = end_effector_item.end_effector_offset
    else:
        end_effector_local_pos = end_effector_item.boundingRect().center()

    if len(chain) == 1:
        logging.warning(f"IK solver: Single item chain for {end_effector_item.part_info.name}. CCD requires at least 2 links.")
        return

    for iteration in range(iterations):
        if not end_effector_item.scene():
            logging.warning(f"End effector item {end_effector_item.part_info.name} not in scene at start of IK iteration.")
            return
        current_ee_scene_pos = end_effector_item.mapToScene(end_effector_local_pos)
        error = QLineF(current_ee_scene_pos, target_pos).length()

        logging.debug(f"IK Iteration {iteration+1}/{iterations}: Current EE Pos={current_ee_scene_pos}, Target={target_pos}, Error={error:.2f}")

        if error < tolerance:
            logging.debug(f"IK solved in {iteration+1} iterations, error: {error:.2f}")
            return

        # Iterate from the item just before the end-effector, down to the base item.
        # chain[j] is the item whose rotation we are adjusting.
        # Its anchor point (transformOriginPoint) is the pivot for this adjustment.

        # For a 2-link chain [Base, EndEffector], if Base is fixed, only EndEffector should rotate.
        # The standard loop range (len(chain) - 2 down to 0) would only process Base.
        # So, we adjust the starting point for the loop if it's a 2-link chain.

        start_index_j = len(chain) - 2 # Default for chains >= 3 links
        if len(chain) == 2:
            # For [Base, EndEffector], we want to process j=0 (Base) if movable,
            # but the primary goal is to rotate EndEffector (chain[1]) around its joint with Base.
            # The current CCD loop structure rotates chain[j] around its *own* anchor.
            # Let's adjust to directly rotate chain[1] if chain[0] is fixed.
            if chain[0].is_fixed:
                # Directly attempt to rotate chain[1] (the end effector)
                # This is a simplification for 2-link fixed-base chains.
                item_to_rotate = chain[1]
                logging.debug(f"  IK 2-Link Special: Handling '{item_to_rotate.part_info.name}'")
                logging.debug(f"    Anchor Offset (local pivot on item): {item_to_rotate.anchor_offset}")
                logging.debug(f"    EndEffector Offset (local target point on item): {end_effector_local_pos}")

                # Pivot is chain[1]'s anchor (its connection to chain[0])
                pivot_scene_pos_special = item_to_rotate.mapToScene(item_to_rotate.anchor_offset)
                current_ee_scene_pos_special = item_to_rotate.mapToScene(end_effector_local_pos) # end_effector_local_pos is for chain[-1]

                logging.debug(f"    Pivot Scene Pos (item's anchor in scene): {pivot_scene_pos_special}")
                logging.debug(f"    Current EE Scene Pos (item's EE point in scene): {current_ee_scene_pos_special}")
                logging.debug(f"    Target Scene Pos (from path): {target_pos}")

                # Check for coincident pivot and EE point for the item_to_rotate
                if QLineF(pivot_scene_pos_special, current_ee_scene_pos_special).length() < 1.0:
                    logging.warning(f"  IK 2-Link Special for '{item_to_rotate.part_info.name}': Pivot and End-Effector points are coincident ({pivot_scene_pos_special}). Skipping rotation this iteration.")
                    # This will effectively stall the 2-link IK if points remain coincident.
                    # The issue is likely that anchor_offset and end_effector_offset are the same on the item.
                    continue # Skip to next IK iteration, or effectively end if error doesn't decrease.

                vec_pivot_to_ee_special = QLineF(pivot_scene_pos_special, current_ee_scene_pos_special)
                vec_pivot_to_target_special = QLineF(pivot_scene_pos_special, target_pos)

                line_pivot_to_ee_special = QLineF(pivot_scene_pos_special, current_ee_scene_pos_special)
                line_pivot_to_target_special = QLineF(pivot_scene_pos_special, target_pos)

                if line_pivot_to_ee_special.length() > 1e-6 and line_pivot_to_target_special.length() > 1e-6:
                    angle_to_ee_deg_special = line_pivot_to_ee_special.angle()
                    angle_to_target_deg_special = line_pivot_to_target_special.angle()
                    angle_diff_deg_special = angle_to_target_deg_special - angle_to_ee_deg_special
                    while angle_diff_deg_special > 180: angle_diff_deg_special -= 360
                    while angle_diff_deg_special < -180: angle_diff_deg_special += 360

                    old_rot_special = item_to_rotate.rotation()
                    new_rot_special = old_rot_special + angle_diff_deg_special
                    logging.debug(f"  IK 2-Link Special: Rotating '{item_to_rotate.part_info.name}': Old={old_rot_special:.2f}, Diff={angle_diff_deg_special:.2f}, New={new_rot_special:.2f}")
                    item_to_rotate.setRotation(new_rot_special)
                # After rotating the end-effector, recalculate error and check for early exit
                current_ee_scene_pos = end_effector_item.mapToScene(end_effector_local_pos)
                error = QLineF(current_ee_scene_pos, target_pos).length()
                if error < tolerance:
                    logging.debug(f"IK (2-link special) solved in {iteration+1} iterations, error: {error:.2f}")
                    return
                continue # Skip the main loop for this iteration as we handled the 2-link case

            # Special handling for 2-link chains where chain[0] is fixed (e.g., torso -> head)
            # In this case, chain is [fixed_base, end_effector_item_actual]
            # We are in the loop j = len(chain) - 2, which is j = 0.
            # So current_item_to_rotate is chain[0] (fixed_base).
            # This original CCD logic would try to rotate chain[0], which is wrong if it's fixed.

            # The "IK 2-Link Special" logging suggests we are trying to rotate chain[1] (item_to_rotate from outer scope)
            # Let's ensure the logic here correctly identifies the item to rotate.
            # For a 2-link fixed chain [fixed_base, actual_ee], we only rotate actual_ee.

            # The iteration is from N-2 down to 0. For a 2-link chain [A,B], N=2. Loop is for j=0. chain[j] = A.
            # This means current_item_to_rotate in the main loop is the fixed base.
            # The "2-link special" logic was outside this loop, which is confusing.
            # Let's assume the 2-link special block *replaces* the general CCD step for that one link.

            # Re-evaluating the 2-link scenario based on logs:
            # The chain is [torso, head]. torso is fixed. head is end_effector_item.
            # solve_ik_ccd is called. iteration loop begins.
            # The 'IK 2-Link Special' log appears, then seems to iterate.
            # This suggests the 2-link logic is hit *instead* of the j-loop for chain[0] if chain[0] is fixed.

            if chain[0].is_fixed and len(chain) == 2: # Explicit 2-link fixed base
                item_to_rotate = chain[1] # This is the actual end effector
                logging.debug(f"  IK CCD: Applying 2-Link Special Logic for {item_to_rotate.part_info.name} parented to fixed {chain[0].part_info.name}")

                pivot_scene_pos = item_to_rotate.mapToScene(item_to_rotate.anchor_offset)
                current_ee_on_item_scene_pos = item_to_rotate.mapToScene(end_effector_local_pos) # end_effector_local_pos is for chain[1]

                # Detailed logging as per previous steps
                logging.debug(f"    2-Link Pivot (anchor of {item_to_rotate.part_info.name}): {pivot_scene_pos}")
                logging.debug(f"    2-Link EE point on {item_to_rotate.part_info.name} (local: {end_effector_local_pos}): {current_ee_on_item_scene_pos}")
                logging.debug(f"    2-Link Target Pos: {target_pos}")

                vec_pivot_to_current_ee = current_ee_on_item_scene_pos - pivot_scene_pos
                vec_pivot_to_target = target_pos - pivot_scene_pos

                if vec_pivot_to_current_ee.lengthSquared() < 1e-6: # Use a small tolerance for coincident points
                    logging.warning(
                        f"IK 2-Link Special for '{item_to_rotate.part_info.name}': "
                        f"The local end-effector point {end_effector_local_pos} and "
                        f"the anchor point {item_to_rotate.anchor_offset} are effectively coincident. "
                        f"(Scene Pivot: {pivot_scene_pos}, Scene EE on item: {current_ee_on_item_scene_pos}). "
                        f"Cannot determine a unique orientation vector to align. Skipping rotation adjustment for this item."
                    )
                    # Check if the pivot itself is close enough to the target, as rotating this item won't help.
                    error_pivot_to_target = QLineF(pivot_scene_pos, target_pos).length()
                    if error_pivot_to_target < tolerance:
                        logging.debug(f"IK 2-Link Special: Pivot for {item_to_rotate.part_info.name} is already at target (error: {error_pivot_to_target:.2f}). Considering solved.")
                        return # Solved
                    # Otherwise, this link cannot contribute. Since it's the only mobile link, we can't solve further.
                    logging.debug(f"IK 2-Link Special: Pivot for {item_to_rotate.part_info.name} not at target (error: {error_pivot_to_target:.2f}), and EE point is coincident. Cannot solve further for this chain.")
                    return # Cannot improve

                # Angle calculation
                angle_rad = math.atan2(vec_pivot_to_target.y(), vec_pivot_to_target.x()) - \
                            math.atan2(vec_pivot_to_current_ee.y(), vec_pivot_to_current_ee.x())

                delta_angle_deg = math.degrees(angle_rad)
                current_rotation = item_to_rotate.rotation()

                # Clamp rotation for this link
                # (Consider adding min/max rotation constraints from PartInfo if available)
                # For now, simple clamping to avoid excessive rotation in one step
                max_angle_deg = 30.0
                clamped_delta_angle_deg = max(-max_angle_deg, min(max_angle_deg, delta_angle_deg))

                if abs(clamped_delta_angle_deg) > 1e-3: # Only rotate if angle is significant
                    # 초기 월드 각도(0)에서부터의 누적 회전 계산
                    current_world_rotation = get_world_rotation(item_to_rotate)
                    # 목표 월드 회전 = 0 + 누적된 델타
                    # 현재 상황에서 필요한 추가 회전
                    target_world_rotation = current_world_rotation + clamped_delta_angle_deg

                    # 로컬 회전 업데이트
                    current_local_rotation = item_to_rotate.rotation()
                    new_local_rotation = current_local_rotation + clamped_delta_angle_deg

                    logging.debug(f"    2-Link Special '{item_to_rotate.part_info.name}': InitialWorld=0.0, CurrentWorld={current_world_rotation:.2f}, TargetWorld={target_world_rotation:.2f}, Delta={clamped_delta_angle_deg:.2f}, NewLocal={new_local_rotation:.2f}")
                    item_to_rotate.setRotation(new_local_rotation)
                    
                    # Enforce bone length constraint for 2-link chain
                    if len(bone_lengths) > 0:
                        _enforce_bone_length_constraints(chain, bone_lengths, 0)
                else:
                    logging.debug(f"    2-Link Special '{item_to_rotate.part_info.name}': Delta angle {clamped_delta_angle_deg:.2f} too small, no rotation applied.")

                # After rotating chain[1], the IK for this 2-link chain is effectively done for this iteration.
                # We need to recalculate the EE position and error.
                current_ee_scene_pos = end_effector_item.mapToScene(end_effector_local_pos) # Recalculate global EE position
                error = QLineF(current_ee_scene_pos, target_pos).length()
                logging.debug(f"IK Iteration {iteration+1}/{iterations} (after 2-link adj): New EE Pos={current_ee_scene_pos}, Target={target_pos}, Error={error:.2f}")
                if error < tolerance:
                    logging.debug(f"IK solved in {iteration+1} iterations (2-link path), error: {error:.2f}")
                    return
                continue # To the next iteration, or break if max iterations reached by the loop condition

        # Original CCD Loop for chains with >= 3 links or 2-link with movable base
        for j in range(start_index_j, -1, -1):
            current_item_to_rotate = chain[j]

            # If the current item is fixed (e.g., torso), skip its rotation.
            if current_item_to_rotate.is_fixed:
                logging.debug(f"IK Solver: Skipping rotation for fixed item: {current_item_to_rotate.part_info.name} at index {j}")
                # If this fixed item is the base of the chain (j==0),
                # no further items in this chain should be rotated by this IK pass from this point up.
                # However, CCD works from end-effector up to this point.
                # So, if chain[0] is fixed, it simply won't be rotated, which is correct.
                continue

            logging.debug(f"  IK Inner Loop: Processing '{current_item_to_rotate.part_info.name}' (index {j})")
            # The pivot for rotation is the anchor point of current_item_to_rotate.
            # In local coords of current_item_to_rotate, this is current_item_to_rotate.anchor_offset
            # In scene coords, this is current_item_to_rotate.mapToScene(current_item_to_rotate.anchor_offset)
            pivot_scene_pos = current_item_to_rotate.mapToScene(current_item_to_rotate.anchor_offset)
            logging.debug(f"    Pivot Scene Pos: {pivot_scene_pos}, (Anchor Offset: {current_item_to_rotate.anchor_offset})")

            # Current end effector position in scene coordinates
            # This needs to be recalculated inside the loop as previous rotations affect it.
            if not end_effector_item.scene():
                logging.warning(f"End effector item {end_effector_item.part_info.name} not in scene during IK inner loop.")
                break
            current_ee_scene_pos = end_effector_item.mapToScene(end_effector_local_pos)

            vec_pivot_to_ee = current_ee_scene_pos - pivot_scene_pos
            vec_pivot_to_target = target_pos - pivot_scene_pos

            logging.debug(f"    Vec Pivot->EE: {vec_pivot_to_ee}, Vec Pivot->Target: {vec_pivot_to_target}")

            # Calculate angle between an_to_ef and an_to_target
            # Using QLineF for angle calculation for simplicity and robustness
            line_pivot_to_ee = QLineF(pivot_scene_pos, current_ee_scene_pos)
            line_pivot_to_target = QLineF(pivot_scene_pos, target_pos)

            if line_pivot_to_ee.length() < 1e-6 or line_pivot_to_target.length() < 1e-6:
                continue # Avoid division by zero or unstable calculations

            angle_to_ee_deg = line_pivot_to_ee.angle()
            angle_to_target_deg = line_pivot_to_target.angle()

            logging.debug(f"    Angle EE_Line: {angle_to_ee_deg:.2f}, Angle Target_Line: {angle_to_target_deg:.2f}, Initial Diff: {angle_to_target_deg - angle_to_ee_deg:.2f}")

            # angleTo() gives angle in degrees, 0-360. We need the signed shortest angle.
            angle_diff_deg = angle_to_target_deg - angle_to_ee_deg

            # Normalize angle_diff_deg to be between -180 and 180
            while angle_diff_deg > 180:
                angle_diff_deg -= 360
            while angle_diff_deg < -180:
                angle_diff_deg += 360

            logging.debug(f"    Normalized Angle Diff: {angle_diff_deg:.2f}")

            # Clamp rotation to avoid overshooting, e.g. max 30 degrees per step
            # max_rot_step = 30.0
            # angle_diff_deg = max(-max_rot_step, min(max_rot_step, angle_diff_deg))

            # Apply rotation to current_item_to_rotate around its anchor_offset
            # The CharacterPartItem.setRotation() handles rotation around its transformOriginPoint (anchor_offset)
            old_rotation = current_item_to_rotate.rotation()

            # 초기 월드 각도(0)에서부터의 회전 계산
            current_world_rotation = get_world_rotation(current_item_to_rotate)

            # 현재 상황에서 필요한 추가 회전을 적용
            new_rotation = old_rotation + angle_diff_deg

            logging.debug(f"    Applying Rotation to '{current_item_to_rotate.part_info.name}': InitialWorld=0.0, CurrentWorld={current_world_rotation:.2f}, Delta={angle_diff_deg:.2f}, OldLocal={old_rotation:.2f}, NewLocal={new_rotation:.2f}")
            # TODO: Apply joint angle limits here by clamping new_rotation if necessary
            # based on parent/child joint constraints if they exist.
            current_item_to_rotate.setRotation(new_rotation)
            
            # Enforce bone length constraints to maintain skeleton structure
            _enforce_bone_length_constraints(chain, bone_lengths, j)

    # After all iterations, check final error
    if end_effector_item.scene():
        final_pos = end_effector_item.mapToScene(end_effector_local_pos)
        final_error = QLineF(final_pos, target_pos).length()
        logging.debug(f"IK finished after {iterations} iterations, final error: {final_error:.2f}")
    else:
        logging.warning("IK finished, but end effector item was no longer in scene.")

def _enforce_bone_length_constraints(chain, bone_lengths, rotated_joint_index):
    """Enforces bone length constraints after rotating a joint.
    
    Args:
        chain: The IK chain of CharacterPartItems
        bone_lengths: Original bone lengths to maintain
        rotated_joint_index: Index of the joint that was just rotated
    """
    # After rotating joint j, we need to update positions of all children
    # to maintain bone lengths
    for i in range(rotated_joint_index + 1, len(chain)):
        parent_item = chain[i - 1]
        child_item = chain[i]
        target_length = bone_lengths[i - 1]
        
        # Get current positions
        parent_anchor_scene = parent_item.mapToScene(parent_item.anchor_offset)
        child_anchor_scene = child_item.mapToScene(child_item.anchor_offset)
        
        # Calculate current direction from parent to child
        direction = child_anchor_scene - parent_anchor_scene
        current_length = QLineF(parent_anchor_scene, child_anchor_scene).length()
        
        if current_length < 0.1:  # Avoid division by zero
            # If joints are coincident, use a default direction
            direction = QPointF(target_length, 0)
            current_length = target_length
        
        # Normalize direction and scale to target length
        direction_normalized = direction / current_length
        new_child_pos = parent_anchor_scene + direction_normalized * target_length
        
        # Update child position to maintain bone length
        child_item.set_scene_position_from_anchor(new_child_pos)
        
        logging.debug(f"    Enforced bone length {target_length:.2f} between {parent_item.part_info.name} and {child_item.part_info.name}")

def _stretch_chain_to_target(chain, bone_lengths, base_pos, target_pos):
    """Stretches the chain towards an unreachable target while maintaining bone lengths."""
    direction = target_pos - base_pos
    total_length = QLineF(base_pos, target_pos).length()
    if total_length < 0.1:
        return
    
    direction_normalized = direction / total_length
    
    # Position each joint along the line from base to target
    current_pos = base_pos
    for i in range(1, len(chain)):
        bone_length = bone_lengths[i-1]
        current_pos = current_pos + direction_normalized * bone_length
        chain[i].set_scene_position_from_anchor(current_pos)
        
        # Update rotation to point to next joint
        if i > 0:
            prev_item = chain[i-1]
            angle_rad = math.atan2(direction_normalized.y(), direction_normalized.x())
            prev_item.setRotation(math.degrees(angle_rad))

def _solve_ik_fabrik(chain, bone_lengths, target_pos, iterations=10, tolerance=1.0):
    """Solves IK using FABRIK (Forward And Backward Reaching Inverse Kinematics)."""
    if len(chain) < 2:
        return
    
    # Get current joint positions
    joint_positions = []
    for item in chain:
        pos = item.mapToScene(item.anchor_offset)
        joint_positions.append(QPointF(pos))
    
    base_pos = joint_positions[0]
    
    for iteration in range(iterations):
        # Forward pass: start from end effector and work towards base
        joint_positions[-1] = QPointF(target_pos)
        
        for i in range(len(chain) - 2, -1, -1):
            current_pos = joint_positions[i]
            next_pos = joint_positions[i + 1]
            bone_length = bone_lengths[i]
            
            direction = current_pos - next_pos
            distance = QLineF(current_pos, next_pos).length()
            
            if distance < 0.1:
                direction = QPointF(bone_length, 0)
                distance = bone_length
            
            direction_normalized = direction / distance
            joint_positions[i] = next_pos + direction_normalized * bone_length
        
        # Backward pass: start from base and work towards end effector
        joint_positions[0] = QPointF(base_pos)  # Fix base position
        
        for i in range(1, len(chain)):
            prev_pos = joint_positions[i - 1]
            current_pos = joint_positions[i]
            bone_length = bone_lengths[i - 1]
            
            direction = current_pos - prev_pos
            distance = QLineF(prev_pos, current_pos).length()
            
            if distance < 0.1:
                direction = QPointF(bone_length, 0)
                distance = bone_length
            
            direction_normalized = direction / distance
            joint_positions[i] = prev_pos + direction_normalized * bone_length
        
        # Check convergence
        end_pos = joint_positions[-1]
        error = QLineF(end_pos, target_pos).length()
        if error < tolerance:
            logging.debug(f"FABRIK converged in {iteration + 1} iterations, error: {error:.2f}")
            break
    
    # Apply final positions and rotations to chain items
    for i in range(len(chain)):
        item = chain[i]
        new_pos = joint_positions[i]
        item.set_scene_position_from_anchor(new_pos)
        
        # Calculate rotation to point to next joint
        if i < len(chain) - 1:
            next_pos = joint_positions[i + 1]
            angle_rad = math.atan2(next_pos.y() - new_pos.y(), next_pos.x() - new_pos.x())
            item.setRotation(math.degrees(angle_rad))

# Helper function (if needed for manual transform updates)
# def update_transform_based_on_parent(item, parent_item):
#     # Implementation depends on how joints and transforms are managed
#     pass