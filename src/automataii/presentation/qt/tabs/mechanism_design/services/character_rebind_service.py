"""
Character rebind service for mechanism layers.

Handles mechanism-to-part reassignment and type-specific readjustment when
character parts/skeleton are replaced after mechanisms were already created.
"""
from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .character_rebind_matcher import resolve_part_scene_fallback, resolve_target_part_name

SceneToMechFn = Callable[[dict[str, Any], tuple[float, float]], tuple[float, float] | None]


@dataclass(frozen=True)
class _AnchorTarget:
    part_name: str
    anchor_joint_id: str | None
    scene_position: tuple[float, float]
    part_extent_scene: float | None = None


@dataclass
class RebindResult:
    changed_ids: list[str] = field(default_factory=list)
    failed_ids: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class MechanismCharacterRebindService:
    """
    Rebind mechanisms to newly loaded character parts and skeleton.

    Policy:
    - Part mapping: name-match-first, fallback to torso, then first part.
    - Readjustment: linkage/cam are refit to the new skeleton anchor.
    """

    def __init__(self, scene_to_mech: SceneToMechFn | None = None) -> None:
        self._scene_to_mech = scene_to_mech

    def rebind_all(
        self,
        mechanism_layers: dict[str, dict[str, Any]],
        parts_data: dict[str, Any],
        skeleton_cache: dict[str, Any] | None,
        *,
        force_readjust: bool = True,
    ) -> RebindResult:
        result = RebindResult()
        if not mechanism_layers or not parts_data:
            return result

        for mechanism_id, layer_data in mechanism_layers.items():
            try:
                target = self._resolve_target(
                    mechanism_id=mechanism_id,
                    layer_data=layer_data,
                    parts_data=parts_data,
                    skeleton_cache=skeleton_cache,
                )
                if target is None:
                    result.failed_ids.append(str(mechanism_id))
                    result.warnings.append(
                        f"Unable to resolve target part for mechanism '{mechanism_id}'"
                    )
                    continue

                changed = False
                current_part = str(layer_data.get("part_name") or "")
                if current_part != target.part_name:
                    layer_data["part_name"] = target.part_name
                    changed = True

                mech_type = str(layer_data.get("type") or "")
                if mech_type == "4_bar_linkage" and (force_readjust or changed):
                    changed = self._readjust_4bar(layer_data, target) or changed
                elif mech_type == "cam" and (force_readjust or changed):
                    changed = self._readjust_cam(layer_data, target) or changed

                if changed:
                    result.changed_ids.append(str(mechanism_id))

            except Exception as exc:  # pragma: no cover - defensive
                result.failed_ids.append(str(mechanism_id))
                result.warnings.append(f"Rebind failed for '{mechanism_id}': {exc}")

        return result

    def _resolve_target(
        self,
        mechanism_id: str,
        layer_data: dict[str, Any],
        parts_data: dict[str, Any],
        skeleton_cache: dict[str, Any] | None,
    ) -> _AnchorTarget | None:
        if not parts_data:
            return None

        target_part_name = resolve_target_part_name(mechanism_id, layer_data, parts_data)

        part_info = parts_data.get(target_part_name)
        anchor_joint_id = getattr(part_info, "anchor_joint_id", None)

        scene_pos = self._resolve_joint_scene_position(anchor_joint_id, skeleton_cache)
        if scene_pos is None:
            scene_pos = resolve_part_scene_fallback(part_info)

        return _AnchorTarget(
            part_name=target_part_name,
            anchor_joint_id=str(anchor_joint_id) if anchor_joint_id else None,
            scene_position=scene_pos,
            part_extent_scene=self._extract_part_extent_scene(part_info),
        )

    @staticmethod
    def _extract_part_extent_scene(part_info: Any) -> float | None:
        roi = getattr(part_info, "roi", None)
        if not isinstance(roi, list | tuple) or len(roi) < 4:
            return None
        try:
            width = float(roi[2])
            height = float(roi[3])
        except (TypeError, ValueError):
            return None
        extent = min(abs(width), abs(height))
        if extent <= 0.0:
            return None
        return extent

    def _resolve_joint_scene_position(
        self,
        anchor_joint_id: str | None,
        skeleton_cache: dict[str, Any] | None,
    ) -> tuple[float, float] | None:
        if not anchor_joint_id or not skeleton_cache:
            return None

        joints = skeleton_cache.get("joints", {})
        if not isinstance(joints, dict) or not joints:
            return None

        joint_data = joints.get(anchor_joint_id)
        if joint_data is None:
            # Prefix matching for IDs like "left_hand_9".
            for joint_id, candidate in joints.items():
                if not isinstance(joint_id, str):
                    continue
                if joint_id.startswith(anchor_joint_id + "_"):
                    joint_data = candidate
                    break
                if joint_id.startswith(anchor_joint_id) and len(joint_id) > len(anchor_joint_id):
                    suffix = joint_id[len(anchor_joint_id):]
                    if suffix.startswith("_"):
                        joint_data = candidate
                        break

        if isinstance(joint_data, dict):
            position = joint_data.get("position") or joint_data.get("scene_position")
            if isinstance(position, list | tuple) and len(position) >= 2:
                try:
                    return (float(position[0]), float(position[1]))
                except (TypeError, ValueError):
                    return None

        return None

    def _scene_to_mechanism(
        self,
        layer_data: dict[str, Any],
        scene_position: tuple[float, float],
    ) -> tuple[float, float]:
        if self._scene_to_mech:
            converted = self._scene_to_mech(layer_data, scene_position)
            if converted is not None:
                return (float(converted[0]), float(converted[1]))
        # Fallback transform used by TransformService when generated_path is missing.
        return ((scene_position[0] - 400.0) / 2.0, (scene_position[1] - 300.0) / 2.0)

    def _scene_span_to_mechanism_length(
        self,
        layer_data: dict[str, Any],
        center_scene: tuple[float, float],
        scene_span: float,
    ) -> float | None:
        if scene_span <= 0.0:
            return None
        try:
            p0 = self._scene_to_mechanism(layer_data, center_scene)
            p1 = self._scene_to_mechanism(
                layer_data,
                (center_scene[0] + float(scene_span), center_scene[1]),
            )
            return max(0.0, math.hypot(p1[0] - p0[0], p1[1] - p0[1]))
        except Exception:  # pragma: no cover - defensive fallback
            return None

    @staticmethod
    def _point(
        value: Any,
        default: tuple[float, float],
    ) -> tuple[float, float]:
        if isinstance(value, list | tuple) and len(value) >= 2:
            try:
                return (float(value[0]), float(value[1]))
            except (TypeError, ValueError):
                return default
        return default

    @staticmethod
    def _float(value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _readjust_4bar(self, layer_data: dict[str, Any], target: _AnchorTarget) -> bool:
        params = layer_data.setdefault("params", {})
        key_points = layer_data.setdefault("key_points", {})

        l1 = max(1.0, min(5000.0, self._float(params.get("l1", params.get("L1", 150.0)), 150.0)))
        p1 = self._point(
            params.get("ground_pivot_1", key_points.get("ground_pivot_1")),
            (0.0, 0.0),
        )
        p2 = self._point(
            params.get("ground_pivot_2", key_points.get("ground_pivot_2")),
            (p1[0] + l1, p1[1]),
        )

        desired_mid = self._scene_to_mechanism(layer_data, target.scene_position)
        current_mid = ((p1[0] + p2[0]) * 0.5, (p1[1] + p2[1]) * 0.5)
        dx = desired_mid[0] - current_mid[0]
        dy = desired_mid[1] - current_mid[1]

        p1_new = (p1[0] + dx, p1[1] + dy)
        p2_new = (p2[0] + dx, p2[1] + dy)
        l1_new = max(1.0, min(5000.0, math.hypot(p2_new[0] - p1_new[0], p2_new[1] - p1_new[1])))
        scale_factor = 1.0

        # Scale linkage to a usable size for the new part if previous size is far off.
        # Keeps behavior stable while preventing tiny/oversized mechanisms after character swap.
        if target.part_extent_scene:
            desired_scene_span = max(140.0, min(420.0, target.part_extent_scene * 1.25))
            desired_mech_span = self._scene_span_to_mechanism_length(
                layer_data, target.scene_position, desired_scene_span
            )
            if desired_mech_span and l1_new > 0.0:
                min_allowed = desired_mech_span * 0.75
                max_allowed = desired_mech_span * 1.35
                clamped_l1 = min(max(l1_new, min_allowed), max_allowed)
                scale_factor = clamped_l1 / l1_new
                if abs(scale_factor - 1.0) > 0.01:
                    p1_new = (
                        desired_mid[0] + (p1_new[0] - desired_mid[0]) * scale_factor,
                        desired_mid[1] + (p1_new[1] - desired_mid[1]) * scale_factor,
                    )
                    p2_new = (
                        desired_mid[0] + (p2_new[0] - desired_mid[0]) * scale_factor,
                        desired_mid[1] + (p2_new[1] - desired_mid[1]) * scale_factor,
                    )
                    l1_new = max(
                        1.0,
                        min(
                            5000.0,
                            math.hypot(
                                p2_new[0] - p1_new[0],
                                p2_new[1] - p1_new[1],
                            ),
                        ),
                    )

        params["ground_pivot_1"] = [p1_new[0], p1_new[1]]
        params["ground_pivot_2"] = [p2_new[0], p2_new[1]]
        params["l1"] = l1_new
        params["L1"] = l1_new

        for low_key, high_key, default in (
            ("l2", "L2", 40.0),
            ("l3", "L3", 120.0),
            ("l4", "L4", 130.0),
        ):
            val = max(
                1.0,
                min(5000.0, self._float(params.get(low_key, params.get(high_key, default)), default)),
            )
            val = max(1.0, min(5000.0, val * scale_factor))
            params[low_key] = val
            params[high_key] = val

        input_angle = self._float(
            params.get("input_angle", params.get("crank_angle", 0.0)),
            0.0,
        )
        params["input_angle"] = input_angle
        params["crank_angle"] = input_angle

        crank_src = key_points.get("crank_end")
        rocker_src = key_points.get("rocker_end")

        if crank_src is not None:
            crank = self._point(crank_src, (p1_new[0], p1_new[1] - params["l2"]))
            crank = (
                desired_mid[0] + ((crank[0] + dx) - desired_mid[0]) * scale_factor,
                desired_mid[1] + ((crank[1] + dy) - desired_mid[1]) * scale_factor,
            )
        else:
            crank = (p1_new[0], p1_new[1] - params["l2"])

        if rocker_src is not None:
            rocker = self._point(rocker_src, (p2_new[0], p2_new[1] - params["l4"]))
            rocker = (
                desired_mid[0] + ((rocker[0] + dx) - desired_mid[0]) * scale_factor,
                desired_mid[1] + ((rocker[1] + dy) - desired_mid[1]) * scale_factor,
            )
        else:
            rocker = (p2_new[0], p2_new[1] - params["l4"])

        key_points["ground_pivot_1"] = [p1_new[0], p1_new[1]]
        key_points["ground_pivot_2"] = [p2_new[0], p2_new[1]]
        key_points["crank_end"] = [crank[0], crank[1]]
        key_points["rocker_end"] = [rocker[0], rocker[1]]
        return True

    def _readjust_cam(self, layer_data: dict[str, Any], target: _AnchorTarget) -> bool:
        params = layer_data.setdefault("params", {})
        key_points = layer_data.setdefault("key_points", {})

        base_radius = max(5.0, min(2000.0, self._float(params.get("base_radius", 25.0), 25.0)))
        eccentricity = max(0.0, min(1500.0, self._float(params.get("eccentricity", 10.0), 10.0)))
        rod_length = max(
            15.0,
            min(4000.0, self._float(params.get("follower_rod_length", 40.0), 40.0)),
        )
        cam_lobes = max(1, min(12, int(self._float(params.get("cam_lobes", 1), 1))))
        profile_harmonic = self._float(params.get("profile_harmonic", 0.3), 0.3)
        profile_harmonic = max(0.0, min(profile_harmonic, 1.0))

        params["base_radius"] = base_radius
        params["eccentricity"] = eccentricity
        params["follower_rod_length"] = rod_length
        params["cam_lobes"] = cam_lobes
        params["profile_harmonic"] = profile_harmonic

        scene_x, scene_y = target.scene_position
        params["center_x"] = float(scene_x)
        params["center_y"] = float(scene_y)
        layer_data["cam_position"] = [float(scene_x), float(scene_y)]

        if target.part_extent_scene:
            desired_scene_radius = max(35.0, min(150.0, target.part_extent_scene * 0.35))
            desired_scene_rod = max(60.0, min(260.0, target.part_extent_scene * 0.9))
            desired_mech_radius = self._scene_span_to_mechanism_length(
                layer_data, target.scene_position, desired_scene_radius
            )
            desired_mech_rod = self._scene_span_to_mechanism_length(
                layer_data, target.scene_position, desired_scene_rod
            )
            if desired_mech_radius:
                min_radius = desired_mech_radius * 0.7
                max_radius = desired_mech_radius * 1.4
                params["base_radius"] = min(max(params["base_radius"], min_radius), max_radius)
            if desired_mech_rod:
                min_rod = desired_mech_rod * 0.65
                max_rod = desired_mech_rod * 1.6
                params["follower_rod_length"] = min(
                    max(params["follower_rod_length"], min_rod),
                    max_rod,
                )

        layer_data["cam_scale_factor"] = max(
            0.1,
            self._float(layer_data.get("cam_scale_factor", 1.0), 1.0),
        )
        layer_data["rod_length_multiplier"] = max(
            0.1,
            self._float(layer_data.get("rod_length_multiplier", 1.0), 1.0),
        )

        center_mech = self._scene_to_mechanism(layer_data, target.scene_position)
        key_points["cam_center"] = [center_mech[0], center_mech[1]]
        key_points["follower_base"] = [center_mech[0], center_mech[1] - (base_radius + rod_length)]
        return True
