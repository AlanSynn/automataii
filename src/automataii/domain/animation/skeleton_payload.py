from __future__ import annotations

from collections.abc import Mapping

POSITION_KEYS = ("position", "loc", "coordinates")


def joint_name_from_payload(
    joint_id: object,
    joint_data: Mapping[str, object] | None = None,
) -> str:
    """Return a stable semantic joint name from a config payload.

    Generated configs can use ids like ``left_shoulder_0`` while storing the
    semantic name in ``name``. Other configs use semantic ids directly, e.g.
    ``left_shoulder``. Only strip a trailing numeric suffix when no explicit
    name is present.
    """
    raw_name = joint_data.get("name") if joint_data is not None else None
    if raw_name is not None and str(raw_name).strip():
        return str(raw_name).strip()

    joint_id_text = str(joint_id).strip()
    if not joint_id_text:
        return "joint"

    parts = joint_id_text.rsplit("_", 1)
    if len(parts) == 2 and parts[1].isdigit() and parts[0]:
        return parts[0]
    return joint_id_text


def joint_position_from_payload(
    joint_data: Mapping[str, object],
) -> tuple[float, float] | None:
    """Return a floating-point joint position from supported payload keys."""
    raw_pos: object | None = None
    for key in POSITION_KEYS:
        value = joint_data.get(key)
        if value is not None:
            raw_pos = value
            break

    if not isinstance(raw_pos, list | tuple) or len(raw_pos) < 2:
        return None

    try:
        return float(raw_pos[0]), float(raw_pos[1])
    except (TypeError, ValueError):
        return None


def joint_pixel_position_from_payload(
    joint_data: Mapping[str, object],
) -> tuple[int, int] | None:
    """Return an integer pixel position for segmentation maps."""
    pos = joint_position_from_payload(joint_data)
    if pos is None:
        return None
    return int(pos[0]), int(pos[1])


def normalized_joint_names_by_id(joints_data: Mapping[object, object]) -> dict[str, str]:
    """Build a lookup from raw joint ids to emitted semantic names."""
    normalized: dict[str, str] = {}
    for joint_id, joint_info in joints_data.items():
        joint_payload = joint_info if isinstance(joint_info, Mapping) else None
        normalized[str(joint_id)] = joint_name_from_payload(joint_id, joint_payload)
    return normalized


def normalized_parent_name(
    parent_ref: object,
    normalized_names: Mapping[str, str],
    valid_joint_names: set[str],
) -> str | None:
    """Normalize a parent reference and drop references to absent joints."""
    if parent_ref is None:
        return None

    parent_text = str(parent_ref).strip()
    if not parent_text:
        return None

    parent_name = normalized_names.get(parent_text)
    if parent_name is None:
        parent_name = joint_name_from_payload(parent_text)

    if parent_name not in valid_joint_names:
        return None
    return parent_name
