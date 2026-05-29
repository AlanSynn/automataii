"""Bounded P0 coding vocabulary for Lab/MS4N repair episodes."""

from __future__ import annotations

from collections.abc import Iterable


class TaxonomyValidationError(ValueError):
    """Raised when a Lab/MS4N coding value is outside the bounded vocabulary."""


SYMPTOM_CODES: tuple[str, ...] = (
    "jam",
    "no_motion",
    "unexpected_motion",
    "overshoot",
    "undershoot",
    "wobble",
    "collision",
    "slip",
    "misalignment",
)

SUSPECTED_CAUSE_CODES: tuple[str, ...] = (
    "pivot_spacing",
    "link_length",
    "hole_position",
    "cam_profile",
    "follower_alignment",
    "spacer_height",
    "material_flex",
    "friction",
    "assembly_order",
    "gear_mesh",
)

CHANGE_CODES: tuple[str, ...] = (
    "move_pivot",
    "change_link_length",
    "swap_hole",
    "change_cam_profile",
    "change_spacer_height",
    "realign_part",
    "change_character_connection",
)

REPAIR_ACTION_CODES: tuple[str, ...] = (
    "move_pivot",
    "change_link_length",
    "swap_hole",
    "change_cam_profile",
    "add_spacer",
    "reduce_friction",
    "realign_part",
    "tighten_connection",
    "simplify_mechanism",
)

FACILITATOR_MOVE_CODES: tuple[str, ...] = (
    "predict_observe_explain",
    "trace_comparison",
    "ask_why_changed",
    "isolate_one_change",
    "physical_check",
    "fabrication_check",
    "connect_to_character_action",
    "debug_jam",
)

STATUS_CODES: tuple[str, ...] = ("open", "repaired", "unresolved", "abandoned")


def validate_code(code: str, allowed: Iterable[str], field_name: str) -> str:
    """Validate an exact taxonomy code without silent normalization."""
    allowed_tuple = tuple(allowed)
    if code not in allowed_tuple:
        allowed_text = ", ".join(allowed_tuple)
        raise TaxonomyValidationError(
            f"Unknown {field_name} code {code!r}; expected one of: {allowed_text}"
        )
    return code


def validate_symptom(code: str) -> str:
    return validate_code(code, SYMPTOM_CODES, "symptom")


def validate_suspected_cause(code: str) -> str:
    return validate_code(code, SUSPECTED_CAUSE_CODES, "suspected_cause")


def validate_change(code: str) -> str:
    return validate_code(code, CHANGE_CODES, "change")


def validate_repair_action(code: str) -> str:
    return validate_code(code, REPAIR_ACTION_CODES, "repair_action")


def validate_facilitator_move(code: str) -> str:
    return validate_code(code, FACILITATOR_MOVE_CODES, "facilitator_move")


def validate_status(code: str) -> str:
    return validate_code(code, STATUS_CODES, "status")
