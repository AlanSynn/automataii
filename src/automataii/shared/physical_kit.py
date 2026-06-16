"""Shared physical pegboard-kit constraints.

This module is intentionally pure Python and Qt-free because presentation,
application, and infrastructure code all need the same physical contract.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import SupportsFloat, SupportsIndex

DEFAULT_GRID_PITCH_MM = 20.0
DEFAULT_GRID_CELL_CM = DEFAULT_GRID_PITCH_MM / 10.0
DEFAULT_HOLE_DIAMETER_MM = 4.0
GEAR_RADIUS_PER_TOOTH_MM = 1.5
DEFAULT_GEAR_CLEARANCE_MM = 2.0
LINKAGE_LENGTH_CELLS: tuple[int, ...] = (2, 4, 6, 8)
_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class GridPitchChoice:
    key: str
    label: str
    pitch_mm: float

    @property
    def pitch_cm(self) -> float:
        return self.pitch_mm / 10.0


@dataclass(frozen=True, slots=True)
class GearPreset:
    key: str
    label: str
    teeth: int

    @property
    def radius_mm(self) -> float:
        return gear_radius_for_teeth(self.teeth)


@dataclass(frozen=True, slots=True)
class CamPreset:
    key: str
    label: str
    base_radius_cells: float
    eccentricity_cells: float
    lobes: int
    profile_harmonic: float
    rise_deg: float
    high_dwell_deg: float
    return_deg: float

    def params_mm(self, grid_cell_cm: float = DEFAULT_GRID_CELL_CM) -> dict[str, float]:
        step_mm = grid_step_mm(grid_cell_cm)
        return {
            "base_radius": self.base_radius_cells * step_mm,
            "eccentricity": self.eccentricity_cells * step_mm,
            "cam_lobes": float(self.lobes),
            "profile_harmonic": self.profile_harmonic,
            "rise_deg": self.rise_deg,
            "high_dwell_deg": self.high_dwell_deg,
            "return_deg": self.return_deg,
        }


@dataclass(frozen=True, slots=True)
class FollowerPreset:
    key: str
    label: str
    contact_style: str
    body_cells: int
    guide_slot_travel_cells: float
    output_hole_count: int
    foot_width_cells: float
    roller_axle: bool = False


@dataclass(frozen=True, slots=True)
class PhysicalKitProfile:
    """Named, explicit contract for the supported physical pegboard kit.

    The profile keeps long-lived physical assumptions discoverable in one value
    while the module-level helpers provide the lightweight API used by Qt,
    application, and generation layers.
    """

    key: str
    label: str
    default_pitch_mm: float
    grid_pitch_choices: tuple[GridPitchChoice, ...]
    linkage_length_cells: tuple[int, ...]
    gear_presets: tuple[GearPreset, ...]
    cam_presets: tuple[CamPreset, ...]
    gear_radius_per_tooth_mm: float
    default_gear_clearance_mm: float
    hole_diameter_mm: float = DEFAULT_HOLE_DIAMETER_MM
    follower_presets: tuple[FollowerPreset, ...] = ()


@dataclass(frozen=True, slots=True)
class PhysicalKitContext:
    """Runtime physical-kit selection propagated through UI/workflow layers."""

    enabled: bool
    grid_cell_cm: float
    grid_pitch_choice: str
    profile: PhysicalKitProfile

    def as_params(self) -> dict[str, object]:
        return {
            "grid_system_enabled": self.enabled,
            "grid_cell_cm": self.grid_cell_cm,
            "grid_pitch_choice": self.grid_pitch_choice,
            "physical_profile_key": self.profile.key,
            "hole_diameter_mm": self.profile.hole_diameter_mm,
        }


GRID_PITCH_CHOICES: tuple[GridPitchChoice, ...] = (
    GridPitchChoice("2cm", "2.0 cm board", DEFAULT_GRID_PITCH_MM),
    GridPitchChoice("ms4n", "Legacy MS4N kit — 2.04 cm", 20.4),
    GridPitchChoice("2_5cm", "2.5 cm board", 25.0),
)

GEAR_PRESETS: tuple[GearPreset, ...] = (
    GearPreset("g12", "G12 micro", 12),
    GearPreset("g14", "G14 compact", 14),
    GearPreset("g16", "G16 small", 16),
    GearPreset("g18", "G18 medium", 18),
)

CAM_PRESETS: tuple[CamPreset, ...] = (
    CamPreset("circle", "Circle / steady", 0.75, 0.0, 1, 0.0, 45.0, 270.0, 45.0),
    CamPreset("eccentric", "Eccentric / bounce", 0.75, 0.25, 1, 0.0, 90.0, 60.0, 90.0),
    CamPreset("oval", "Oval / smooth rise", 0.8, 0.3, 2, 0.2, 120.0, 30.0, 120.0),
    CamPreset("pear", "Pear / slow-fast", 0.9, 0.45, 1, 0.35, 150.0, 45.0, 75.0),
)

FOLLOWER_PRESETS: tuple[FollowerPreset, ...] = (
    FollowerPreset("f3-round", "3-cell round-nose follower", "round_nose", 3, 1.0, 1, 0.9),
    FollowerPreset("f4-roller", "4-cell roller-pin follower", "roller_pin", 4, 1.0, 1, 0.9, True),
    FollowerPreset("f5-flat", "5-cell flat-shoe follower", "flat_shoe", 5, 1.25, 2, 1.0),
    FollowerPreset(
        "f6-linkage-output",
        "6-cell linkage-output follower",
        "linkage_output",
        6,
        1.5,
        3,
        0.9,
    ),
)

DEFAULT_PHYSICAL_KIT_PROFILE = PhysicalKitProfile(
    key="motionsmith-ms4n",
    label="MotionSmith 2cm pegboard kit (legacy MS4N pitch available)",
    default_pitch_mm=DEFAULT_GRID_PITCH_MM,
    grid_pitch_choices=GRID_PITCH_CHOICES,
    linkage_length_cells=LINKAGE_LENGTH_CELLS,
    gear_presets=GEAR_PRESETS,
    cam_presets=CAM_PRESETS,
    gear_radius_per_tooth_mm=GEAR_RADIUS_PER_TOOTH_MM,
    default_gear_clearance_mm=DEFAULT_GEAR_CLEARANCE_MM,
    follower_presets=FOLLOWER_PRESETS,
)

PHYSICAL_KIT_PROFILES: tuple[PhysicalKitProfile, ...] = (DEFAULT_PHYSICAL_KIT_PROFILE,)

LINKAGE_PARAM_KEYS: frozenset[str] = frozenset(
    {
        "l1",
        "l2",
        "l3",
        "l4",
        "L1",
        "L2",
        "L3",
        "L4",
        "ground_link",
        "input_link",
        "coupler_link",
        "output_link",
        "crank_length",
        "rod_length",
    }
)


def _gear_presets_for(profile: PhysicalKitProfile) -> tuple[GearPreset, ...]:
    """Return the profile's gear presets, falling back only for invalid custom profiles."""
    return profile.gear_presets or DEFAULT_PHYSICAL_KIT_PROFILE.gear_presets


def _gear_preset_at(profile: PhysicalKitProfile, index: int) -> GearPreset:
    presets = _gear_presets_for(profile)
    return presets[min(max(index, 0), len(presets) - 1)]


def grid_step_mm(grid_cell_cm: object = DEFAULT_GRID_CELL_CM) -> float:
    return max(1.0, finite_float(grid_cell_cm, DEFAULT_GRID_CELL_CM) * 10.0)


def pitch_cm_to_mm(grid_cell_cm: object = DEFAULT_GRID_CELL_CM) -> float:
    return grid_step_mm(grid_cell_cm)


def pitch_mm_to_cm(pitch_mm: object = DEFAULT_GRID_PITCH_MM) -> float:
    return finite_float(pitch_mm, DEFAULT_GRID_PITCH_MM) / 10.0


def nearest_pitch_choice(
    value_cm: object,
    *,
    profile: PhysicalKitProfile = DEFAULT_PHYSICAL_KIT_PROFILE,
) -> GridPitchChoice:
    value_mm = pitch_cm_to_mm(value_cm)
    return min(
        profile.grid_pitch_choices,
        key=lambda choice: (abs(choice.pitch_mm - value_mm), choice.key),
    )


def physical_profile_from_key(profile_key: object) -> PhysicalKitProfile:
    key = str(profile_key or "").strip()
    if key:
        for profile in PHYSICAL_KIT_PROFILES:
            if profile.key == key:
                return profile
        _LOGGER.warning(
            "Unknown physical kit profile key %r; using default %s",
            key,
            DEFAULT_PHYSICAL_KIT_PROFILE.key,
        )
    return DEFAULT_PHYSICAL_KIT_PROFILE


def physical_profile_from_params(params: Mapping[str, object]) -> PhysicalKitProfile:
    return physical_profile_from_key(params.get("physical_profile_key"))


def grid_pitch_choice_by_key(
    key: object,
    *,
    profile: PhysicalKitProfile = DEFAULT_PHYSICAL_KIT_PROFILE,
) -> GridPitchChoice | None:
    normalized = str(key or "").strip()
    return next(
        (choice for choice in profile.grid_pitch_choices if choice.key == normalized),
        None,
    )


def grid_cell_cm_for_pitch_choice(
    key: object,
    fallback_cm: object = DEFAULT_GRID_CELL_CM,
    *,
    profile: PhysicalKitProfile = DEFAULT_PHYSICAL_KIT_PROFILE,
) -> float:
    choice = grid_pitch_choice_by_key(key, profile=profile)
    if choice is not None:
        return choice.pitch_cm
    return nearest_pitch_choice(fallback_cm, profile=profile).pitch_cm


def physical_context_from_settings(
    enabled: object = True,
    grid_cell_cm: object = DEFAULT_GRID_CELL_CM,
    grid_pitch_choice: object | None = None,
    *,
    profile: PhysicalKitProfile = DEFAULT_PHYSICAL_KIT_PROFILE,
) -> PhysicalKitContext:
    enabled_value = grid_enabled_from_value(enabled, default=True)
    if grid_pitch_choice is not None:
        choice = grid_pitch_choice_by_key(grid_pitch_choice, profile=profile)
    else:
        choice = None
    if choice is None:
        choice = nearest_pitch_choice(grid_cell_cm, profile=profile)
    cell_cm = (
        choice.pitch_cm if enabled_value else max(0.1, finite_float(grid_cell_cm, choice.pitch_cm))
    )
    return PhysicalKitContext(
        enabled=enabled_value,
        grid_cell_cm=cell_cm,
        grid_pitch_choice=choice.key,
        profile=profile,
    )


def physical_context_from_params(
    params: Mapping[str, object],
    *,
    default_enabled: bool = True,
    default_grid_cell_cm: float = DEFAULT_GRID_CELL_CM,
) -> PhysicalKitContext:
    profile = physical_profile_from_params(params)
    return physical_context_from_settings(
        params.get("grid_system_enabled", default_enabled),
        params.get("grid_cell_cm", default_grid_cell_cm),
        params.get("grid_pitch_choice"),
        profile=profile,
    )


def allowed_linkage_lengths_mm(
    grid_cell_cm: object = DEFAULT_GRID_CELL_CM,
    *,
    profile: PhysicalKitProfile = DEFAULT_PHYSICAL_KIT_PROFILE,
) -> tuple[float, ...]:
    step_mm = grid_step_mm(grid_cell_cm)
    return tuple(float(cells) * step_mm for cells in profile.linkage_length_cells)


def nearest_linkage_length_mm(
    value: object,
    grid_cell_cm: object = DEFAULT_GRID_CELL_CM,
    *,
    profile: PhysicalKitProfile = DEFAULT_PHYSICAL_KIT_PROFILE,
) -> float:
    choices = allowed_linkage_lengths_mm(grid_cell_cm, profile=profile)
    return nearest_float(finite_float(value, choices[0]), choices)


def allowed_gear_teeth(
    *,
    profile: PhysicalKitProfile = DEFAULT_PHYSICAL_KIT_PROFILE,
) -> tuple[int, ...]:
    return tuple(preset.teeth for preset in _gear_presets_for(profile))


def allowed_gear_radii_mm(
    *,
    profile: PhysicalKitProfile = DEFAULT_PHYSICAL_KIT_PROFILE,
) -> tuple[float, ...]:
    return tuple(
        float(preset.teeth) * profile.gear_radius_per_tooth_mm
        for preset in _gear_presets_for(profile)
    )


def gear_radius_for_teeth(
    teeth: object,
    *,
    profile: PhysicalKitProfile = DEFAULT_PHYSICAL_KIT_PROFILE,
) -> float:
    return float(nearest_gear_teeth(teeth, profile=profile)) * profile.gear_radius_per_tooth_mm


def freeform_gear_radius_for_teeth(
    teeth: object,
    default_teeth: int = 16,
    *,
    profile: PhysicalKitProfile = DEFAULT_PHYSICAL_KIT_PROFILE,
) -> float:
    parsed = max(1, int(round(finite_float(teeth, float(default_teeth)))))
    return float(parsed) * profile.gear_radius_per_tooth_mm


def gear_teeth_for_radius(
    radius_mm: object,
    *,
    profile: PhysicalKitProfile = DEFAULT_PHYSICAL_KIT_PROFILE,
) -> int:
    return nearest_gear_preset_for_radius(radius_mm, profile=profile).teeth


def freeform_gear_teeth_for_radius(
    radius_mm: object,
    default_teeth: int = 16,
    *,
    profile: PhysicalKitProfile = DEFAULT_PHYSICAL_KIT_PROFILE,
) -> int:
    default_radius = freeform_gear_radius_for_teeth(default_teeth, profile=profile)
    radius = max(1.0, finite_float(radius_mm, default_radius))
    return max(1, int(round(radius / profile.gear_radius_per_tooth_mm)))


def gear_teeth_from_params(
    params: Mapping[str, object],
    teeth_keys: Sequence[str],
    radius_keys: Sequence[str],
    default_teeth: int,
    *,
    enabled: bool = True,
    profile: PhysicalKitProfile = DEFAULT_PHYSICAL_KIT_PROFILE,
) -> int:
    for key in teeth_keys:
        if key in params:
            return (
                nearest_gear_teeth(params[key], profile=profile)
                if enabled
                else max(1, int(round(finite_float(params[key], float(default_teeth)))))
            )
    for key in radius_keys:
        if key in params:
            return (
                gear_teeth_for_radius(params[key], profile=profile)
                if enabled
                else freeform_gear_teeth_for_radius(params[key], default_teeth, profile=profile)
            )
    return (
        nearest_gear_teeth(default_teeth, profile=profile)
        if enabled
        else max(1, int(default_teeth))
    )


def nearest_gear_teeth(
    value: object,
    *,
    profile: PhysicalKitProfile = DEFAULT_PHYSICAL_KIT_PROFILE,
) -> int:
    choices = allowed_gear_teeth(profile=profile)
    parsed = int(round(finite_float(value, float(choices[0]))))
    return min(choices, key=lambda choice: (abs(choice - parsed), -choice))


def nearest_gear_radius_mm(
    value: object,
    *,
    profile: PhysicalKitProfile = DEFAULT_PHYSICAL_KIT_PROFILE,
) -> float:
    preset = nearest_gear_preset_for_radius(value, profile=profile)
    return float(preset.teeth) * profile.gear_radius_per_tooth_mm


def nearest_gear_preset_for_radius(
    value: object,
    *,
    profile: PhysicalKitProfile = DEFAULT_PHYSICAL_KIT_PROFILE,
) -> GearPreset:
    presets = _gear_presets_for(profile)
    first_radius = float(presets[0].teeth) * profile.gear_radius_per_tooth_mm
    parsed = finite_float(value, first_radius)
    return min(
        presets,
        key=lambda preset: (
            abs(float(preset.teeth) * profile.gear_radius_per_tooth_mm - parsed),
            -preset.teeth,
        ),
    )


def gear_pair_from_params(
    params: Mapping[str, object],
    *,
    profile: PhysicalKitProfile = DEFAULT_PHYSICAL_KIT_PROFILE,
) -> tuple[int, float, int, float]:
    gear1_teeth = (
        nearest_gear_teeth(params["gear1_teeth"], profile=profile)
        if "gear1_teeth" in params
        else gear_teeth_for_radius(_first(params, "gear1_radius", "r1"), profile=profile)
    )
    gear2_teeth = (
        nearest_gear_teeth(params["gear2_teeth"], profile=profile)
        if "gear2_teeth" in params
        else gear_teeth_for_radius(_first(params, "gear2_radius", "r2"), profile=profile)
    )
    return (
        gear1_teeth,
        gear_radius_for_teeth(gear1_teeth, profile=profile),
        gear2_teeth,
        gear_radius_for_teeth(gear2_teeth, profile=profile),
    )


def gear_center_distance(
    radius_1: object,
    radius_2: object,
    clearance: object = None,
    *,
    profile: PhysicalKitProfile = DEFAULT_PHYSICAL_KIT_PROFILE,
) -> float:
    first_radius = float(_gear_preset_at(profile, 0).teeth) * profile.gear_radius_per_tooth_mm
    second_radius = float(_gear_preset_at(profile, 1).teeth) * profile.gear_radius_per_tooth_mm
    r1 = max(1.0, finite_float(radius_1, first_radius))
    r2 = max(1.0, finite_float(radius_2, second_radius))
    gap = max(0.0, finite_float(clearance, profile.default_gear_clearance_mm))
    return r1 + r2 + gap


def gear_clearance_from_params(
    params: Mapping[str, object],
    *,
    profile: PhysicalKitProfile = DEFAULT_PHYSICAL_KIT_PROFILE,
) -> float:
    clearance = _first(params, "gear_clearance", "mesh_clearance", "clearance")
    return max(0.0, finite_float(clearance, profile.default_gear_clearance_mm))


def snap_gear_params(
    params: Mapping[str, object],
    *,
    profile: PhysicalKitProfile = DEFAULT_PHYSICAL_KIT_PROFILE,
) -> dict[str, object]:
    snapped = dict(params)
    teeth1, r1, teeth2, r2 = gear_pair_from_params(snapped, profile=profile)
    snapped["gear1_teeth"] = teeth1
    snapped["gear2_teeth"] = teeth2
    snapped["gear1_radius"] = r1
    snapped["gear2_radius"] = r2
    snapped["r1"] = r1
    snapped["r2"] = r2
    snapped.setdefault("gear_clearance", profile.default_gear_clearance_mm)
    snapped.setdefault("mesh_clearance", snapped["gear_clearance"])
    return snapped


def nearest_cam_preset(
    params: Mapping[str, object],
    grid_cell_cm: object = DEFAULT_GRID_CELL_CM,
    *,
    profile: PhysicalKitProfile = DEFAULT_PHYSICAL_KIT_PROFILE,
) -> CamPreset:
    step_mm = grid_step_mm(grid_cell_cm)
    normalized_grid_cell_cm = step_mm / 10.0
    base = finite_float(_first(params, "base_radius", "cam_radius"), 2.0 * step_mm)
    eccentricity = finite_float(_first(params, "eccentricity", "cam_offset"), 0.0)
    lobes = int(round(finite_float(params.get("cam_lobes"), 1.0)))
    harmonic = finite_float(params.get("profile_harmonic"), 0.0)

    def score(preset: CamPreset) -> tuple[float, str]:
        preset_params = preset.params_mm(normalized_grid_cell_cm)
        base_score = abs(base - preset_params["base_radius"]) / step_mm
        ecc_score = abs(eccentricity - preset_params["eccentricity"]) / step_mm
        lobe_score = abs(lobes - int(preset_params["cam_lobes"])) * 0.5
        harmonic_score = abs(harmonic - preset_params["profile_harmonic"])
        return (base_score + ecc_score + lobe_score + harmonic_score, preset.key)

    return min(profile.cam_presets, key=score)


def snap_cam_params(
    params: Mapping[str, object],
    grid_cell_cm: object = DEFAULT_GRID_CELL_CM,
    *,
    profile: PhysicalKitProfile = DEFAULT_PHYSICAL_KIT_PROFILE,
) -> dict[str, object]:
    snapped = dict(params)
    normalized_grid_cell_cm = grid_step_mm(grid_cell_cm) / 10.0
    preset = nearest_cam_preset(snapped, normalized_grid_cell_cm, profile=profile)
    preset_params = preset.params_mm(normalized_grid_cell_cm)
    if "cam_radius" in snapped:
        snapped["cam_radius"] = preset_params["base_radius"]
    snapped["base_radius"] = preset_params["base_radius"]
    if "cam_offset" in snapped:
        snapped["cam_offset"] = preset_params["eccentricity"]
    snapped["eccentricity"] = preset_params["eccentricity"]
    snapped["cam_lobes"] = int(preset_params["cam_lobes"])
    snapped["profile_harmonic"] = preset_params["profile_harmonic"]
    snapped["physical_cam_preset"] = preset.key
    for key in ("rise_deg", "high_dwell_deg", "return_deg"):
        snapped[key] = preset_params[key]
    return snapped


def snap_linkage_params(
    params: Mapping[str, object],
    grid_cell_cm: object = DEFAULT_GRID_CELL_CM,
    *,
    profile: PhysicalKitProfile = DEFAULT_PHYSICAL_KIT_PROFILE,
) -> dict[str, object]:
    snapped = dict(params)
    for key in LINKAGE_PARAM_KEYS:
        if key in snapped:
            snapped[key] = nearest_linkage_length_mm(snapped[key], grid_cell_cm, profile=profile)
    for lower_key, upper_key in (("l1", "L1"), ("l2", "L2"), ("l3", "L3"), ("l4", "L4")):
        if lower_key in snapped and upper_key in snapped:
            snapped[upper_key] = finite_float(snapped[lower_key], 0.0)
        elif lower_key in snapped:
            snapped[upper_key] = finite_float(snapped[lower_key], 0.0)
        elif upper_key in snapped:
            snapped[lower_key] = finite_float(snapped[upper_key], 0.0)
    return snapped


def snap_physical_params(
    mechanism_type: str,
    params: Mapping[str, object],
    grid_cell_cm: object = DEFAULT_GRID_CELL_CM,
    *,
    enabled: bool = True,
    profile: PhysicalKitProfile = DEFAULT_PHYSICAL_KIT_PROFILE,
) -> dict[str, object]:
    snapped = dict(params)
    if not enabled:
        return snapped
    normalized = normalize_mechanism_type(mechanism_type)
    if normalized in {"four_bar", "slider_crank"}:
        return snap_linkage_params(snapped, grid_cell_cm, profile=profile)
    if normalized == "gear_train":
        return snap_gear_params(snapped, profile=profile)
    if normalized == "cam_follower":
        return snap_cam_params(snapped, grid_cell_cm, profile=profile)
    return snapped


def snap_parameter_value(
    mechanism_type: str,
    param_key: str,
    value: object,
    grid_cell_cm: object = DEFAULT_GRID_CELL_CM,
    *,
    profile: PhysicalKitProfile = DEFAULT_PHYSICAL_KIT_PROFILE,
) -> float:
    normalized = normalize_mechanism_type(mechanism_type)
    key = str(param_key)
    normalized_grid_cell_cm = grid_step_mm(grid_cell_cm) / 10.0
    if normalized in {"four_bar", "slider_crank"} and key in LINKAGE_PARAM_KEYS:
        return nearest_linkage_length_mm(value, normalized_grid_cell_cm, profile=profile)
    if normalized == "gear_train" and key in {"gear1_teeth", "gear2_teeth"}:
        return float(nearest_gear_teeth(value, profile=profile))
    if normalized == "gear_train" and key in {"gear1_radius", "gear2_radius", "r1", "r2"}:
        return nearest_gear_radius_mm(value, profile=profile)
    if normalized == "cam_follower":
        if key in {"cam_radius", "base_radius"}:
            presets = (preset.params_mm(normalized_grid_cell_cm) for preset in profile.cam_presets)
            return nearest_float(finite_float(value, 0.0), tuple(p["base_radius"] for p in presets))
        if key in {"cam_offset", "eccentricity"}:
            presets = (preset.params_mm(normalized_grid_cell_cm) for preset in profile.cam_presets)
            return nearest_float(
                finite_float(value, 0.0),
                tuple(p["eccentricity"] for p in presets),
            )
        if key == "cam_lobes":
            return float(
                min(
                    profile.cam_presets, key=lambda p: abs(p.lobes - finite_float(value, 1.0))
                ).lobes
            )
        if key == "profile_harmonic":
            return nearest_float(
                finite_float(value, 0.0),
                tuple(preset.profile_harmonic for preset in profile.cam_presets),
            )
    return finite_float(value, 0.0)


def normalize_mechanism_type(mechanism_type: object) -> str:
    key = str(mechanism_type or "").strip().lower().replace("-", "_").replace(" ", "_")
    mapping = {
        "fourbar": "four_bar",
        "four_bar": "four_bar",
        "four_bar_linkage": "four_bar",
        "4_bar_linkage": "four_bar",
        "slidercrank": "slider_crank",
        "slider_crank": "slider_crank",
        "cam": "cam_follower",
        "cam_profile": "cam_follower",
        "cam_follower": "cam_follower",
        "gear": "gear_train",
        "gears": "gear_train",
        "gear_train": "gear_train",
        "planetary_gear": "gear_train",
    }
    return mapping.get(key, key)


def finite_float(value: object, default: float) -> float:
    if not isinstance(value, str | bytes | bytearray | SupportsFloat | SupportsIndex):
        return default
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def grid_enabled_from_params(
    params: Mapping[str, object],
    default: bool = True,
) -> bool:
    return grid_enabled_from_value(params.get("grid_system_enabled", default), default=default)


def grid_enabled_from_value(raw_value: object, default: bool = True) -> bool:
    if isinstance(raw_value, bool):
        return raw_value
    if isinstance(raw_value, str):
        normalized = raw_value.strip().lower()
        if normalized in {"0", "false", "no", "off", ""}:
            return False
        if normalized in {"1", "true", "yes", "on"}:
            return True
        return default
    if isinstance(raw_value, int | float) and not isinstance(raw_value, bool):
        return math.isfinite(float(raw_value)) and bool(raw_value)
    return default


def grid_cell_cm_from_params(
    params: Mapping[str, object],
    default: float = DEFAULT_GRID_CELL_CM,
) -> float:
    context = physical_context_from_params(
        params,
        default_enabled=True,
        default_grid_cell_cm=default,
    )
    return context.grid_cell_cm


def nearest_float(value: float, choices: Sequence[float]) -> float:
    return float(min(choices, key=lambda choice: (abs(choice - value), choice)))


def _first(params: Mapping[str, object], *keys: str) -> object | None:
    for key in keys:
        if key in params:
            return params[key]
    return None
