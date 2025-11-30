"""
IK Visual Updater - Updates character part visuals from IK state.

Extracted from IKManager. Handles calculation of visual transforms
based on joint positions and angles.

Design Pattern: Updater (compute visual state from IK state)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable

from PyQt6.QtCore import QPointF


@dataclass
class VisualUpdate:
    """Visual update data for a joint/part."""

    scene_position: QPointF
    world_rotation_degrees: float


class IKVisualUpdater:
    """
    Computes visual updates for character parts from IK state.

    Responsibilities:
    - Calculate world rotations from joint angles
    - Compute position/rotation deltas from initial pose
    - Generate visual update dictionaries

    Time Complexity: O(n) where n = number of limbs/components
    """

    def __init__(self) -> None:
        """Initialize the visual updater."""
        self._initial_snapshot: dict[str, dict[str, Any]] = {}

    def set_initial_snapshot(self, snapshot: dict[str, dict[str, Any]]) -> None:
        """Set the initial pose snapshot for delta calculations."""
        self._initial_snapshot = snapshot

    def compute_visual_updates(
        self,
        joints_config: dict[str, dict[str, Any]],
        limb_configs: dict[str, dict[str, Any]],
        selectable_components: list[dict[str, Any]],
        get_standardized_joint_id: Callable[[str], str | None],
    ) -> dict[str, dict[str, Any]]:
        """
        Compute visual updates for all joints and components.

        Args:
            joints_config: Current joint positions and angles
            limb_configs: Limb configuration data
            selectable_components: List of selectable component configs
            get_standardized_joint_id: Function to standardize joint IDs

        Returns:
            Dictionary of visual updates keyed by joint ID
        """
        updated: dict[str, dict[str, Any]] = {}
        processed_parts: set[str] = set()

        def pos(jid: str) -> QPointF | None:
            return joints_config.get(jid, {}).get("position")

        # Process limb chains
        for eff_abs, limb in limb_configs.items():
            part_name = limb.get("label")
            parent_id = get_standardized_joint_id(limb.get("parentAnchor", ""))
            child_id = get_standardized_joint_id(eff_abs)

            if not (part_name and parent_id and child_id):
                continue

            p_parent, p_child = pos(parent_id), pos(child_id)
            if not (p_parent and p_child):
                continue

            updates = self._compute_limb_visual_update(
                parent_id,
                child_id,
                p_parent,
                p_child,
                joints_config,
            )

            updated.update(updates)
            processed_parts.add(part_name)

        # Process remaining selectable components
        for comp in selectable_components:
            part_name = comp.get("partName")
            if not part_name or part_name in processed_parts:
                continue

            jid = get_standardized_joint_id(comp.get("targetJointId", ""))
            pj = pos(jid) if jid else None
            if not (jid and pj):
                continue

            update = self._compute_component_visual_update(
                jid, pj, joints_config, pos
            )

            if update:
                updated[jid] = update
                processed_parts.add(part_name)

        return updated

    def _compute_limb_visual_update(
        self,
        parent_id: str,
        child_id: str,
        p_parent: QPointF,
        p_child: QPointF,
        joints_config: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        """Compute visual updates for a limb chain."""
        updates: dict[str, dict[str, Any]] = {}

        current_angle = self._angle_between(p_parent, p_child)

        # Get initial positions for delta calculation
        initial_parent_pos = None
        initial_child_pos = None
        if self._initial_snapshot:
            if parent_id in self._initial_snapshot:
                initial_parent_pos = self._initial_snapshot[parent_id].get("position")
            if child_id in self._initial_snapshot:
                initial_child_pos = self._initial_snapshot[child_id].get("position")

        initial_angle = 0.0
        if initial_parent_pos and initial_child_pos:
            initial_angle = self._angle_between(initial_parent_pos, initial_child_pos)

        joint_angle_delta = current_angle - initial_angle
        part_world_rotation = joint_angle_delta

        updates[parent_id] = {
            "scene_position": p_parent,
            "world_rotation_degrees": part_world_rotation,
        }

        # Child rotation
        child_current_angle = joints_config.get(child_id, {}).get("angle", 0.0)
        child_initial_angle = self._get_initial_angle(child_id)
        child_rotation_delta = child_current_angle - child_initial_angle

        updates[child_id] = {
            "scene_position": p_child,
            "world_rotation_degrees": child_rotation_delta,
        }

        return updates

    def _compute_component_visual_update(
        self,
        jid: str,
        pj: QPointF,
        joints_config: dict[str, dict[str, Any]],
        pos_fn: Callable[[str], QPointF | None],
    ) -> dict[str, Any] | None:
        """Compute visual update for a single component."""
        current_angle = joints_config.get(jid, {}).get("angle", 0.0)
        parent_id = joints_config.get(jid, {}).get("parent")

        if parent_id:
            parent_pos = pos_fn(parent_id)
            if parent_pos:
                current_angle = self._angle_between(parent_pos, pj)

        initial_joint_angle = self._get_initial_angle(jid)
        joint_angle_delta = current_angle - initial_joint_angle
        part_world_rotation = joint_angle_delta

        return {
            "scene_position": pj,
            "world_rotation_degrees": part_world_rotation,
        }

    def _angle_between(self, a: QPointF, b: QPointF) -> float:
        """Calculate angle between two points in degrees."""
        return math.degrees(math.atan2(b.y() - a.y(), b.x() - a.x()))

    def _get_initial_angle(self, jid: str) -> float:
        """Get the initial angle for a joint from the initial snapshot."""
        if self._initial_snapshot and jid in self._initial_snapshot:
            return self._initial_snapshot[jid].get("angle", 0.0)
        return 0.0
