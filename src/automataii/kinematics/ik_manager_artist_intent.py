# ARTIST INTENT RESPECTING BEND DIRECTION CALCULATION
# 사용자 제안 - 아티스트의 그림을 신뢰하는 방식

def calculate_bend_directions_artist_intent(self):
    """Calculate bend directions based on artist's initial pose, not rigid anatomical rules."""
    
    self.sim_joint_bend_directions = {}
    middle_joints_to_process = [
        "left_elbow",
        "right_elbow", 
        "left_knee",
        "right_knee",
    ]

    for middle_joint_abstract_name in middle_joints_to_process:
        # Find P0 (root), P1 (middle), P2 (effector)
        p1_std_id = self._get_standardized_joint_id(middle_joint_abstract_name)
        if not p1_std_id or p1_std_id not in self.sim_joints_config:
            continue

        p1_pos = self.sim_joints_config[p1_std_id]["position"]

        # Find P0 (parent of P1)
        middle_joint_limb_config = self.sim_limb_configs.get(middle_joint_abstract_name)
        if not middle_joint_limb_config:
            continue
        p0_abstract_name = middle_joint_limb_config.get("parentAnchor")
        if not p0_abstract_name:
            continue
        p0_std_id = self._get_standardized_joint_id(p0_abstract_name)
        if not p0_std_id or p0_std_id not in self.sim_joints_config:
            continue
        p0_pos = self.sim_joints_config[p0_std_id]["position"]

        # Find P2 (child of P1)
        p2_std_id = None
        for effector_abs_name, config_data in self.sim_limb_configs.items():
            if config_data.get("parentAnchor") == middle_joint_abstract_name:
                p2_std_id = self._get_standardized_joint_id(effector_abs_name)
                break

        if not p2_std_id or p2_std_id not in self.sim_joints_config:
            continue
        p2_pos = self.sim_joints_config[p2_std_id]["position"]

        # --- ROBUST BEND DIRECTION INFERENCE ---
        # This logic infers the bend direction from the initial drawing,
        # respecting the artist's intent rather than a rigid anatomical model.

        # Vector from the middle joint (e.g., elbow) to the root (e.g., shoulder)
        vec_to_root = p0_pos - p1_pos
        # Vector from the middle joint to the end effector (e.g., wrist)
        vec_to_end = p2_pos - p1_pos

        # The 2D cross-product of these vectors determines the bend direction.
        # (v1.x * v2.y) - (v1.y * v2.x)
        # A positive result means vec_to_end is "to the left" of vec_to_root (CCW).
        # A negative result means it's "to the right" (CW).
        cross_product = (vec_to_root.x() * vec_to_end.y()) - (vec_to_root.y() * vec_to_end.x())

        # Use a small tolerance to handle nearly straight limbs.
        if abs(cross_product) < 1e-4:
            # The limb is almost perfectly straight. Fall back to a simple default.
            direction = 1 if "left" in middle_joint_abstract_name else -1
            logging.warning(f"IKManager: Limb '{middle_joint_abstract_name}' is nearly straight (cross_product: {cross_product:.2e}). Using anatomical default bend direction: {direction}")
        else:
            # The initial pose has a clear bend. Trust the artist.
            direction = 1 if cross_product > 0 else -1
            logging.info(f"IKManager: Inferred bend direction for '{middle_joint_abstract_name}' from initial pose: {direction} (cross_product: {cross_product:.2f})")

        self.sim_joint_bend_directions[middle_joint_abstract_name] = direction

    logging.info(f"🎯 Artist-Intent Bend directions: {self.sim_joint_bend_directions}")