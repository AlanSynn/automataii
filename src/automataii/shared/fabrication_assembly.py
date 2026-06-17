"""Semantic board-assembly recipes for the physical fabrication kit.

This module is intentionally Qt-free. It is the source-of-truth layer between
physical fabricated parts, generated instruction SVGs, and future app-level
visual step guides.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from automataii.shared.physical_kit import (
    DEFAULT_BOARD_COLUMNS,
    DEFAULT_BOARD_ROWS,
    DEFAULT_PHYSICAL_KIT_PROFILE,
    PhysicalKitProfile,
    finite_float,
    gear_center_distance,
)

ASSEMBLY_SCHEMA_VERSION = "automataii.fabrication.assembly.v1"
BOARD_ROWS: tuple[str, ...] = tuple(chr(ord("A") + idx) for idx in range(DEFAULT_BOARD_ROWS))
BOARD_COLUMNS: tuple[int, ...] = tuple(range(1, DEFAULT_BOARD_COLUMNS + 1))
PAPER_FASTENER_KEY = "paper-fastener"
DEFAULT_FASTENER_MAX_LENGTH = "2in"


class AssemblyValidationError(ValueError):
    """Raised when a semantic board-assembly package is not self-consistent."""


@dataclass(frozen=True, slots=True)
class BoardCoord:
    row: str
    column: int

    @classmethod
    def from_label(cls, label: str) -> BoardCoord:
        normalized = label.strip().upper()
        if len(normalized) < 2:
            raise AssemblyValidationError(f"Invalid board coordinate: {label!r}")
        row = normalized[0]
        try:
            column = int(normalized[1:])
        except ValueError as exc:
            raise AssemblyValidationError(f"Invalid board coordinate: {label!r}") from exc
        coord = cls(row, column)
        coord.validate()
        return coord

    @property
    def label(self) -> str:
        return f"{self.row}{self.column}"

    def validate(self) -> None:
        if self.row not in BOARD_ROWS or self.column not in BOARD_COLUMNS:
            raise AssemblyValidationError(f"Coordinate outside 15x15 board: {self.label}")

    def distance_cells(self, other: BoardCoord) -> float:
        return math.hypot(
            BOARD_ROWS.index(self.row) - BOARD_ROWS.index(other.row), self.column - other.column
        )


@dataclass(frozen=True, slots=True)
class PartRef:
    category: str
    key: str
    label: str
    count: int = 1

    @property
    def part_id(self) -> str:
        return f"{self.category}:{self.key}"

    def to_dict(self) -> dict[str, object]:
        return {
            "part": self.part_id,
            "category": self.category,
            "key": self.key,
            "label": self.label,
            "count": self.count,
        }


@dataclass(frozen=True, slots=True)
class StackLayer:
    order: int
    role: str
    label: str
    part: PartRef | None = None

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "order": self.order,
            "role": self.role,
            "label": self.label,
        }
        if self.part is not None:
            result["part"] = self.part.part_id
        return result


@dataclass(frozen=True, slots=True)
class VisualState:
    active_parts: tuple[str, ...]
    ghost_parts: tuple[str, ...] = ()
    highlight_coords: tuple[BoardCoord, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "active_parts": list(self.active_parts),
            "ghost_parts": list(self.ghost_parts),
            "highlight_coords": [coord.label for coord in self.highlight_coords],
        }


@dataclass(frozen=True, slots=True)
class AppMapping:
    mechanism_type: str
    component_role: str
    highlight_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "mechanism_type": self.mechanism_type,
            "component_role": self.component_role,
            "highlight_ids": list(self.highlight_ids),
        }


@dataclass(frozen=True, slots=True)
class AssemblyStep:
    n: int
    action: str
    title: str
    instruction: str
    coords: tuple[BoardCoord, ...]
    coord_roles: tuple[str, ...]
    parts: tuple[PartRef, ...]
    stack: tuple[StackLayer, ...]
    visual_state: VisualState
    app_mapping: AppMapping
    check: str

    def to_dict(self) -> dict[str, object]:
        return {
            "n": self.n,
            "action": self.action,
            "title": self.title,
            "instruction": self.instruction,
            "coords": [coord.label for coord in self.coords],
            "coord_roles": list(self.coord_roles),
            "parts": [part.to_dict() for part in self.parts],
            "stack": [layer.to_dict() for layer in self.stack],
            "visual_state": self.visual_state.to_dict(),
            "app_mapping": self.app_mapping.to_dict(),
            "check": self.check,
        }


@dataclass(frozen=True, slots=True)
class GearCompatibility:
    first_part: str
    second_part: str
    first_coord: BoardCoord
    second_coord: BoardCoord
    board_distance_cells: float
    board_distance_mm: float
    required_center_distance_mm: float
    tolerance_mm: float
    first_coord_role: str = "board_axle"
    second_coord_role: str = "board_axle"

    @property
    def error_mm(self) -> float:
        return self.board_distance_mm - self.required_center_distance_mm

    @property
    def compatible(self) -> bool:
        return abs(self.error_mm) <= self.tolerance_mm

    def to_dict(self) -> dict[str, object]:
        return {
            "first_part": self.first_part,
            "second_part": self.second_part,
            "first_coord": self.first_coord.label,
            "second_coord": self.second_coord.label,
            "first_coord_role": self.first_coord_role,
            "second_coord_role": self.second_coord_role,
            "board_distance_cells": round(self.board_distance_cells, 3),
            "board_distance_mm": round(self.board_distance_mm, 3),
            "required_center_distance_mm": round(self.required_center_distance_mm, 3),
            "error_mm": round(self.error_mm, 3),
            "tolerance_mm": round(self.tolerance_mm, 3),
            "compatible": self.compatible,
        }


@dataclass(frozen=True, slots=True)
class AssemblyRecipe:
    key: str
    title: str
    mechanism_type: str
    guide_svg: str
    parts: tuple[PartRef, ...]
    steps: tuple[AssemblyStep, ...]
    app_mapping: AppMapping
    compatibility: tuple[GearCompatibility, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "title": self.title,
            "mechanism_type": self.mechanism_type,
            "guide_svg": self.guide_svg,
            "parts": [part.to_dict() for part in self.parts],
            "steps": [step.to_dict() for step in self.steps],
            "app_mapping": self.app_mapping.to_dict(),
            "compatibility": [entry.to_dict() for entry in self.compatibility],
        }


def part_id(category: str, key: str) -> str:
    return f"{category}:{key}"


def _coord(label: str) -> BoardCoord:
    return BoardCoord.from_label(label)


def _part(category: str, key: str, label: str, count: int = 1) -> PartRef:
    return PartRef(category, key, label, count)


def _part_short_label(part: PartRef) -> str:
    if part.category == "gears" and part.key.startswith("g") and part.key[1:].isdigit():
        return f"G{part.key[1:]}"
    return part.label


def _stack(coord: BoardCoord, moving_part: PartRef, spacer: PartRef) -> tuple[StackLayer, ...]:
    return (
        StackLayer(1, "board", f"Board hole {coord.label}"),
        StackLayer(2, "paper-fastener", "Paper fastener"),
        StackLayer(3, "spacer", spacer.label, spacer),
        StackLayer(4, "moving-part", moving_part.label, moving_part),
        StackLayer(5, "top-spacer", spacer.label, spacer),
        StackLayer(6, "fastener-tabs", "Open tabs loosely"),
    )


def _fixed_part_stack(coord: BoardCoord, fixed_part: PartRef, spacer: PartRef) -> tuple[StackLayer, ...]:
    """Stack for a part that is fixed to the board rather than free-running."""

    return (
        StackLayer(1, "board", f"Board hole {coord.label}"),
        StackLayer(2, "paper-fastener", "Paper fastener"),
        StackLayer(3, "spacer", spacer.label, spacer),
        StackLayer(4, "fixed-part", fixed_part.label, fixed_part),
        StackLayer(5, "fastener-tabs", "Open tabs behind board"),
    )


def _carrier_pivot_stack(
    reference_coord: BoardCoord, moving_part: PartRef, spacer: PartRef
) -> tuple[StackLayer, ...]:
    """Stack for a planet axle that rides on a carrier, not through the board.

    The board coordinate is still useful as an assembly reference because the
    carrier hole should be aligned near that pegboard location, but this stack
    must not claim a second fixed board axle. A fixed planet axle would lock the
    carrier and mis-teach the physical planetary mechanism.
    """

    return (
        StackLayer(1, "carrier-hole", f"Carrier hole near {reference_coord.label}"),
        StackLayer(2, "paper-fastener", "Paper fastener"),
        StackLayer(3, "spacer", spacer.label, spacer),
        StackLayer(4, "moving-part", moving_part.label, moving_part),
        StackLayer(5, "top-spacer", spacer.label, spacer),
        StackLayer(6, "fastener-tabs", "Open tabs loosely"),
    )


def _gear_handle_stack(
    reference_coord: BoardCoord,
    moving_part: PartRef,
    spacer: PartRef,
    gear_part: PartRef,
) -> tuple[StackLayer, ...]:
    """Stack for a linkage joint mounted on an off-center gear handle hole."""

    return (
        StackLayer(1, "gear-handle-hole", f"{_part_short_label(gear_part)} handle hole near {reference_coord.label}"),
        StackLayer(2, "paper-fastener", "Paper fastener"),
        StackLayer(3, "spacer", spacer.label, spacer),
        StackLayer(4, "moving-part", moving_part.label, moving_part),
        StackLayer(5, "top-spacer", spacer.label, spacer),
        StackLayer(6, "fastener-tabs", "Open tabs loosely"),
    )


def _link_end_stack(
    reference_coord: BoardCoord, moving_part: PartRef, spacer: PartRef
) -> tuple[StackLayer, ...]:
    """Stack for a moving output connector attached to a linkage end."""

    return (
        StackLayer(1, "link-end-hole", f"Link output hole near {reference_coord.label}"),
        StackLayer(2, "paper-fastener", "Paper fastener"),
        StackLayer(3, "spacer", spacer.label, spacer),
        StackLayer(4, "moving-part", moving_part.label, moving_part),
        StackLayer(5, "top-spacer", spacer.label, spacer),
        StackLayer(6, "fastener-tabs", "Open tabs loosely"),
    )


def _link_joint_stack(
    reference_coord: BoardCoord, moving_part: PartRef, spacer: PartRef
) -> tuple[StackLayer, ...]:
    """Stack for a free linkage-to-linkage joint, not a board pivot."""

    return (
        StackLayer(1, "link-joint-hole", f"Moving joint near {reference_coord.label}"),
        StackLayer(2, "paper-fastener", "Paper fastener"),
        StackLayer(3, "spacer", spacer.label, spacer),
        StackLayer(4, "moving-part", moving_part.label, moving_part),
        StackLayer(5, "top-spacer", spacer.label, spacer),
        StackLayer(6, "fastener-tabs", "Open tabs loosely"),
    )


def _fixed_stack(coord: BoardCoord) -> tuple[StackLayer, ...]:
    return (
        StackLayer(1, "board", f"Board hole {coord.label}"),
        StackLayer(2, "paper-fastener", "Paper fastener"),
        StackLayer(3, "fastener-tabs", "Open tabs behind board"),
    )


def _step(
    n: int,
    action: str,
    title: str,
    instruction: str,
    coords: Sequence[str],
    parts: Sequence[PartRef],
    stack: Sequence[StackLayer],
    mechanism_type: str,
    component_role: str,
    check: str,
    *,
    ghosts: Sequence[str] = (),
    coord_roles: Sequence[str] | None = None,
) -> AssemblyStep:
    board_coords = tuple(_coord(coord) for coord in coords)
    roles = tuple(coord_roles or ("board",) * len(board_coords))
    if len(roles) != len(board_coords):
        raise AssemblyValidationError("Step coordinate roles must match coordinates")
    part_ids = tuple(part.part_id for part in parts)
    return AssemblyStep(
        n=n,
        action=action,
        title=title,
        instruction=instruction,
        coords=board_coords,
        coord_roles=roles,
        parts=tuple(parts),
        stack=tuple(stack),
        visual_state=VisualState(part_ids, tuple(ghosts), board_coords),
        app_mapping=AppMapping(mechanism_type, component_role, part_ids),
        check=check,
    )


def _gear_compatibility(
    first: PartRef,
    second: PartRef,
    first_coord: str,
    second_coord: str,
    pitch_mm: float,
    manifest_index: Mapping[str, Mapping[str, object]],
    profile: PhysicalKitProfile,
) -> GearCompatibility:
    a = _coord(first_coord)
    b = _coord(second_coord)
    first_meta = manifest_index[first.part_id]
    second_meta = manifest_index[second.part_id]
    r1 = finite_float(first_meta.get("pitch_radius_mm"), 0.0)
    r2 = finite_float(second_meta.get("pitch_radius_mm"), 0.0)
    board_distance_cells = a.distance_cells(b)
    board_distance_mm = board_distance_cells * pitch_mm
    required = gear_center_distance(r1, r2, profile.default_gear_clearance_mm, profile=profile)
    return GearCompatibility(
        first.part_id,
        second.part_id,
        a,
        b,
        board_distance_cells,
        board_distance_mm,
        required,
        tolerance_mm=max(1.0, pitch_mm * 0.075),
    )


def _offset_coord(anchor: BoardCoord, row_delta: int, column_delta: int) -> BoardCoord:
    row_index = BOARD_ROWS.index(anchor.row) + row_delta
    column = anchor.column + column_delta
    if row_index < 0 or row_index >= len(BOARD_ROWS):
        raise AssemblyValidationError("Gear offset row outside board")
    return BoardCoord(BOARD_ROWS[row_index], column)


def _best_gear_pair(
    anchor_label: str,
    pitch_mm: float,
    manifest_index: Mapping[str, Mapping[str, object]],
    profile: PhysicalKitProfile,
) -> tuple[PartRef, PartRef, BoardCoord, BoardCoord, GearCompatibility]:
    anchor = _coord(anchor_label)
    offsets = ((0, 2), (1, 1), (0, 1), (1, 2), (2, 1), (0, 3))
    candidates: list[tuple[float, PartRef, PartRef, BoardCoord, BoardCoord, GearCompatibility]] = []
    gear_refs = tuple(
        _part("gears", preset.key, f"G{preset.teeth} gear") for preset in profile.gear_presets
    )
    for first in gear_refs:
        for second in gear_refs:
            if first.part_id not in manifest_index or second.part_id not in manifest_index:
                continue
            for row_delta, column_delta in offsets:
                try:
                    other = _offset_coord(anchor, row_delta, column_delta)
                    compat = _gear_compatibility(
                        first,
                        second,
                        anchor.label,
                        other.label,
                        pitch_mm,
                        manifest_index,
                        profile,
                    )
                except AssemblyValidationError:
                    continue
                candidates.append((abs(compat.error_mm), first, second, anchor, other, compat))
    if not candidates:
        raise AssemblyValidationError("No gear pairs available in fabrication manifest")
    _, first, second, first_coord, second_coord, compat = min(
        candidates,
        key=lambda item: (
            item[0],
            item[1].key,
            item[2].key,
            item[4].row,
            item[4].column,
        ),
    )
    # Small paper-fastener gears tolerate loose educational mesh. The value is
    # still recorded so tests and app previews can show the actual delta.
    compat = GearCompatibility(
        compat.first_part,
        compat.second_part,
        compat.first_coord,
        compat.second_coord,
        compat.board_distance_cells,
        compat.board_distance_mm,
        compat.required_center_distance_mm,
        tolerance_mm=max(1.5, pitch_mm * 0.18),
    )
    return first, second, first_coord, second_coord, compat


def manifest_part_index(manifest: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    parts = manifest.get("parts")
    if not isinstance(parts, Mapping):
        return {}
    index: dict[str, Mapping[str, object]] = {}
    for category, raw_items in parts.items():
        if not isinstance(category, str) or not isinstance(raw_items, Sequence):
            continue
        for item in raw_items:
            if not isinstance(item, Mapping):
                continue
            raw_key = item.get("key")
            if raw_key is None:
                raw_path = str(item.get("path", "")).strip()
                raw_key = raw_path.rsplit("/", 1)[-1].removesuffix(".svg")
            key = str(raw_key).strip()
            if key:
                index[part_id(category, key)] = item
    return index


def build_default_assembly_package(
    manifest: Mapping[str, object],
    *,
    profile: PhysicalKitProfile = DEFAULT_PHYSICAL_KIT_PROFILE,
) -> dict[str, object]:
    index = manifest_part_index(manifest)
    pitch_mm = finite_float(manifest.get("grid_pitch_mm"), profile.default_pitch_mm)
    hole_diameter_mm = finite_float(manifest.get("hole_diameter_mm"), profile.hole_diameter_mm)

    cam = _part("cams", "eccentric", "Eccentric cam")
    follower = _part("followers", "f3-round", "Round follower")
    link2 = _part("linkages", "linkage-2-cell", "L2 linkage")
    link4 = _part("linkages", "linkage-4-cell", "L4 linkage")
    link6 = _part("linkages", "linkage-6-cell", "L6 linkage")
    bracket2 = _part("brackets", "2-hole-straight", "2-hole bracket")
    bracket3 = _part("brackets", "3-hole-straight", "3-hole bracket")
    spacer = _part("spacers", "s8", "S8 spacer", count=8)
    spacer_tall = _part("spacers", "s12", "S12 spacer", count=2)

    drive_gear, driven_gear, drive_coord, driven_coord, gear_compat = _best_gear_pair(
        "H6", pitch_mm, index, profile
    )
    crank_drive_gear, crank_driven_gear, crank_drive_coord, crank_driven_coord, gear_link_compat = (
        _best_gear_pair("I6", pitch_mm, index, profile)
    )
    sun_coord = _coord("H8")
    planet_coord = _coord("H10")
    if len(profile.gear_presets) < 2:
        raise AssemblyValidationError("Planetary recipe requires at least two gear presets")
    sun_preset = profile.gear_presets[0]
    planet_preset = profile.gear_presets[1]
    sun_gear = _part("gears", sun_preset.key, f"G{sun_preset.teeth} gear")
    planet_gear = _part("gears", planet_preset.key, f"G{planet_preset.teeth} gear")
    if sun_gear.part_id not in index or planet_gear.part_id not in index:
        raise AssemblyValidationError("Planetary gear pair missing from fabrication manifest")
    planetary_compat_raw = _gear_compatibility(
        sun_gear,
        planet_gear,
        sun_coord.label,
        planet_coord.label,
        pitch_mm,
        index,
        profile,
    )
    ring_key = f"ring-{sun_preset.key}-{planet_preset.key}"
    ring_teeth = sun_preset.teeth + planet_preset.teeth * 2
    ring_gear = _part("ring_gears", ring_key, f"R{ring_teeth} internal ring gear")
    if ring_gear.part_id not in index:
        raise AssemblyValidationError("Planetary ring gear missing from fabrication manifest")
    planetary_compat = GearCompatibility(
        planetary_compat_raw.first_part,
        planetary_compat_raw.second_part,
        planetary_compat_raw.first_coord,
        planetary_compat_raw.second_coord,
        planetary_compat_raw.board_distance_cells,
        planetary_compat_raw.board_distance_mm,
        planetary_compat_raw.required_center_distance_mm,
        tolerance_mm=max(1.5, pitch_mm * 0.18, abs(planetary_compat_raw.error_mm) + 0.001),
        first_coord_role="board_axle",
        second_coord_role="carrier_reference",
    )
    gear_parts = (
        (PartRef(drive_gear.category, drive_gear.key, drive_gear.label, count=2),)
        if drive_gear.part_id == driven_gear.part_id
        else (drive_gear, driven_gear)
    )
    crank_gear_parts = (
        (
            PartRef(
                crank_drive_gear.category,
                crank_drive_gear.key,
                crank_drive_gear.label,
                count=2,
            ),
        )
        if crank_drive_gear.part_id == crank_driven_gear.part_id
        else (crank_drive_gear, crank_driven_gear)
    )
    planetary_gear_parts = (ring_gear, sun_gear, planet_gear)
    four_bar_link2_pair = PartRef(link2.category, link2.key, link2.label, count=2)

    recipes = (
        AssemblyRecipe(
            "gear-train-basic",
            "Two-gear crank",
            "gear_train",
            "assembly/01-gear-train-basic.svg",
            (*gear_parts, spacer),
            (
                _step(
                    1,
                    "place-fastener",
                    f"Start at {drive_coord.label}",
                    f"Place a paper fastener at {drive_coord.label}.",
                    (drive_coord.label,),
                    (),
                    _fixed_stack(drive_coord),
                    "gear_train",
                    "drive-axle",
                    "The fastener turns freely.",
                ),
                _step(
                    2,
                    "add-part",
                    f"Add {_part_short_label(drive_gear)} drive gear",
                    f"Add one S8 spacer, then place {_part_short_label(drive_gear)} on {drive_coord.label}.",
                    (drive_coord.label,),
                    (spacer, drive_gear),
                    _stack(drive_coord, drive_gear, spacer),
                    "gear_train",
                    "drive-gear",
                    f"{_part_short_label(drive_gear)} spins without rubbing.",
                    ghosts=(drive_gear.part_id,),
                ),
                _step(
                    3,
                    "add-part",
                    f"Add {_part_short_label(driven_gear)} output gear",
                    f"Place {_part_short_label(driven_gear)} at {driven_coord.label} so the two gears touch lightly.",
                    (driven_coord.label,),
                    (spacer, driven_gear),
                    _stack(driven_coord, driven_gear, spacer),
                    "gear_train",
                    "driven-gear",
                    f"Both gears turn when {_part_short_label(drive_gear)} turns.",
                    ghosts=(drive_gear.part_id,),
                ),
                _step(
                    4,
                    "test-motion",
                    "Turn the handle hole",
                    f"Use a handle hole on {_part_short_label(drive_gear)} and rotate slowly.",
                    (drive_coord.label, driven_coord.label),
                    (drive_gear, driven_gear),
                    _stack(drive_coord, drive_gear, spacer),
                    "gear_train",
                    "motion-check",
                    "If the mesh binds, loosen both fasteners.",
                    ghosts=(drive_gear.part_id, driven_gear.part_id),
                ),
            ),
            AppMapping("gear_train", "recipe", (drive_gear.part_id, driven_gear.part_id)),
            (gear_compat,),
        ),
        AssemblyRecipe(
            "cam-follower-basic",
            "Cam and follower lift",
            "cam_follower",
            "assembly/02-cam-follower-basic.svg",
            (cam, follower, bracket2, spacer, spacer_tall),
            (
                _step(
                    1,
                    "place-fastener",
                    "Mount cam axle",
                    "Place a paper fastener at J7.",
                    ("J7",),
                    (),
                    _fixed_stack(_coord("J7")),
                    "cam_follower",
                    "cam-axle",
                    "The axle is loose enough to rotate.",
                ),
                _step(
                    2,
                    "add-part",
                    "Add eccentric cam",
                    "Add S8 spacer, then place the eccentric cam at J7.",
                    ("J7",),
                    (spacer, cam),
                    _stack(_coord("J7"), cam, spacer),
                    "cam_follower",
                    "cam",
                    "The cam turns cleanly.",
                    ghosts=(cam.part_id,),
                ),
                _step(
                    3,
                    "add-guide",
                    "Add follower guide",
                    "Pin the follower guide slot at G7 with a loose spacer stack.",
                    ("G7",),
                    (spacer_tall, follower),
                    _stack(_coord("G7"), follower, spacer_tall),
                    "cam_follower",
                    "follower-guide",
                    "The follower can slide up and down.",
                    ghosts=(cam.part_id,),
                ),
                _step(
                    4,
                    "test-motion",
                    "Check lift",
                    "Turn the cam and watch the follower rise.",
                    ("J7", "G7"),
                    (cam, follower),
                    _stack(_coord("G7"), follower, spacer_tall),
                    "cam_follower",
                    "lift-check",
                    "Loosen the guide if it sticks.",
                    ghosts=(cam.part_id, follower.part_id),
                ),
            ),
            AppMapping("cam_follower", "recipe", (cam.part_id, follower.part_id)),
        ),
        AssemblyRecipe(
            "four-bar-basic",
            "Four-bar linkage",
            "four_bar",
            "assembly/03-four-bar-basic.svg",
            (four_bar_link2_pair, link4, spacer),
            (
                _step(
                    1,
                    "place-ground",
                    "Set ground pivots",
                    "Pin ground pivots at I5 and I9.",
                    ("I5", "I9"),
                    (),
                    _fixed_stack(_coord("I5")),
                    "four_bar",
                    "ground",
                    "Both ground pivots are fixed.",
                ),
                _step(
                    2,
                    "add-linkage",
                    "Add input link",
                    "Place L2 from I5 toward G6 with spacers.",
                    ("I5", "G6"),
                    (spacer, link2),
                    _stack(_coord("I5"), link2, spacer),
                    "four_bar",
                    "input-link",
                    "The input link swings freely.",
                    coord_roles=("board", "link_end_reference"),
                ),
                _step(
                    3,
                    "add-linkage",
                    "Add coupler",
                    "Join L4 to the free input-link hole near G6, then point the other end toward G10.",
                    ("G6", "G10"),
                    (spacer, link4),
                    _link_joint_stack(_coord("G6"), link4, spacer),
                    "four_bar",
                    "coupler",
                    "The coupler moves without scraping.",
                    ghosts=(link2.part_id,),
                    coord_roles=("link_joint_reference", "link_end_reference"),
                ),
                _step(
                    4,
                    "add-linkage",
                    "Close output link",
                    "Place L2 from G10 back to I9.",
                    ("G10", "I9"),
                    (spacer, link2),
                    _stack(_coord("I9"), link2, spacer),
                    "four_bar",
                    "output-link",
                    "All pivots move when the input link turns.",
                    ghosts=(link2.part_id, link4.part_id),
                    coord_roles=("link_joint_reference", "board"),
                ),
                _step(
                    5,
                    "add-linkage",
                    "Join output to coupler",
                    "Fasten the L4 coupler to the free output-link hole near G10 only (not the board).",
                    ("G10",),
                    (spacer, link4),
                    _link_joint_stack(_coord("G10"), link4, spacer),
                    "four_bar",
                    "coupler-output-joint",
                    "The G10 joint floats with the links and is not pinned to the board.",
                    ghosts=(link2.part_id, link4.part_id),
                    coord_roles=("link_joint_reference",),
                ),
            ),
            AppMapping("four_bar", "recipe", (link2.part_id, link4.part_id)),
        ),
        AssemblyRecipe(
            "gear-linkage-crank",
            "Gear crank linkage",
            "gear_linkage",
            "assembly/04-gear-linkage-crank.svg",
            (*crank_gear_parts, link4, bracket2, spacer),
            (
                _step(
                    1,
                    "place-fastener",
                    "Mount drive gear",
                    f"Place the drive gear fastener at {crank_drive_coord.label}.",
                    (crank_drive_coord.label,),
                    (),
                    _fixed_stack(crank_drive_coord),
                    "gear_linkage",
                    "drive-axle",
                    "The axle is straight.",
                ),
                _step(
                    2,
                    "add-part",
                    f"Add {_part_short_label(crank_drive_gear)} gear",
                    f"Add S8 spacer, then place {_part_short_label(crank_drive_gear)} at {crank_drive_coord.label}.",
                    (crank_drive_coord.label,),
                    (spacer, crank_drive_gear),
                    _stack(crank_drive_coord, crank_drive_gear, spacer),
                    "gear_linkage",
                    "drive-gear",
                    f"{_part_short_label(crank_drive_gear)} rotates freely.",
                    ghosts=(crank_drive_gear.part_id,),
                ),
                _step(
                    3,
                    "add-part",
                    f"Mesh {_part_short_label(crank_driven_gear)} gear",
                    f"Place {_part_short_label(crank_driven_gear)} at {crank_driven_coord.label} and mesh it with {_part_short_label(crank_drive_gear)}.",
                    (crank_driven_coord.label,),
                    (spacer, crank_driven_gear),
                    _stack(crank_driven_coord, crank_driven_gear, spacer),
                    "gear_linkage",
                    "driven-gear",
                    "The gears move together.",
                    ghosts=(crank_drive_gear.part_id,),
                ),
                _step(
                    4,
                    "add-linkage",
                    "Add linkage output",
                    (
                        f"Fasten L4 through an off-center {_part_short_label(crank_driven_gear)} "
                        "handle hole only (not the board), then point the free end toward I12."
                    ),
                    (crank_driven_coord.label, "I12"),
                    (spacer, link4),
                    _gear_handle_stack(crank_driven_coord, link4, spacer, crank_driven_gear),
                    "gear_linkage",
                    "output-link",
                    "The linkage rides around the gear center instead of locking to the board.",
                    ghosts=(crank_drive_gear.part_id, crank_driven_gear.part_id),
                    coord_roles=("gear_handle_reference", "link_end_reference"),
                ),
                _step(
                    5,
                    "add-bracket",
                    "Add output connector",
                    "Fasten the 2-hole bracket to the free L4 end near I12 as a moving handle.",
                    ("I12",),
                    (spacer, bracket2),
                    _link_end_stack(_coord("I12"), bracket2, spacer),
                    "gear_linkage",
                    "output-connector",
                    "The bracket follows the linkage end and is not pinned to the board.",
                    ghosts=(crank_drive_gear.part_id, crank_driven_gear.part_id, link4.part_id),
                    coord_roles=("link_end_reference",),
                ),
            ),
            AppMapping(
                "gear_linkage",
                "recipe",
                (crank_drive_gear.part_id, crank_driven_gear.part_id, link4.part_id),
            ),
            (gear_link_compat,),
        ),
        AssemblyRecipe(
            "planetary-gear-basic",
            "Planetary ring gear",
            "planetary_gear",
            "assembly/05-planetary-gear-basic.svg",
            (*planetary_gear_parts, link2, spacer),
            (
                _step(
                    1,
                    "place-fastener",
                    "Pin the sun axle",
                    f"Place the sun gear fastener at {sun_coord.label}.",
                    (sun_coord.label,),
                    (),
                    _fixed_stack(sun_coord),
                    "planetary_gear",
                    "sun-axle",
                    "The center axle is straight and fixed.",
                ),
                _step(
                    2,
                    "add-ring",
                    f"Mount {_part_short_label(ring_gear)}",
                    (
                        f"Center {_part_short_label(ring_gear)} around H8 and fasten its outer "
                        "mount holes at D8, H4, H12, and L8."
                    ),
                    ("D8", "H4", "H12", "L8"),
                    (spacer, ring_gear),
                    _fixed_part_stack(_coord("D8"), ring_gear, spacer),
                    "planetary_gear",
                    "ring-gear",
                    "The ring gear is fixed to the board and does not rotate.",
                ),
                _step(
                    3,
                    "add-part",
                    f"Add {_part_short_label(sun_gear)} sun gear",
                    f"Add S8 spacer, then place {_part_short_label(sun_gear)} on {sun_coord.label}.",
                    (sun_coord.label,),
                    (spacer, sun_gear),
                    _stack(sun_coord, sun_gear, spacer),
                    "planetary_gear",
                    "sun-gear",
                    f"{_part_short_label(sun_gear)} spins cleanly before the carrier is added.",
                    ghosts=(ring_gear.part_id,),
                ),
                _step(
                    4,
                    "add-linkage",
                    "Add carrier link",
                    f"Place L2 from {sun_coord.label} toward {planet_coord.label} as the carrier.",
                    (sun_coord.label, planet_coord.label),
                    (spacer, link2),
                    _stack(sun_coord, link2, spacer),
                    "planetary_gear",
                    "carrier",
                    "The carrier swings loosely around the sun axle.",
                    ghosts=(ring_gear.part_id, sun_gear.part_id),
                    coord_roles=("board", "carrier_reference"),
                ),
                _step(
                    5,
                    "add-part",
                    f"Add {_part_short_label(planet_gear)} moving planet gear",
                    (
                        f"Align the free carrier hole near {planet_coord.label}, then fasten "
                        f"{_part_short_label(planet_gear)} through the carrier hole only "
                        f"(not the board) so it meshes with both {_part_short_label(sun_gear)} "
                        f"and {_part_short_label(ring_gear)}."
                    ),
                    (planet_coord.label,),
                    (spacer, planet_gear),
                    _carrier_pivot_stack(planet_coord, planet_gear, spacer),
                    "planetary_gear",
                    "planet-gear",
                    "The planet axle travels with the carrier and rolls between sun and ring.",
                    ghosts=(ring_gear.part_id, sun_gear.part_id, link2.part_id),
                    coord_roles=("carrier_reference",),
                ),
                _step(
                    6,
                    "test-motion",
                    "Rotate the carrier",
                    "Hold the ring fixed and use the carrier end/handle hole to orbit the planet around H8.",
                    (sun_coord.label, planet_coord.label),
                    (sun_gear, planet_gear, link2),
                    _carrier_pivot_stack(planet_coord, planet_gear, spacer),
                    "planetary_gear",
                    "carrier-check",
                    "If the orbit binds, loosen the planet fastener and spacer stack.",
                    ghosts=(ring_gear.part_id, sun_gear.part_id, planet_gear.part_id, link2.part_id),
                    coord_roles=("board", "carrier_reference"),
                ),
            ),
            AppMapping(
                "planetary_gear",
                "recipe",
                (ring_gear.part_id, sun_gear.part_id, planet_gear.part_id, link2.part_id),
            ),
            (planetary_compat,),
        ),
        AssemblyRecipe(
            "slider-crank-basic",
            "Slider-crank linkage",
            "slider_crank",
            "assembly/06-slider-crank-basic.svg",
            (link2, link6, bracket2, bracket3, spacer),
            (
                _step(
                    1,
                    "place-fastener",
                    "Pin crank axle",
                    "Place the crank axle fastener at I5.",
                    ("I5",),
                    (),
                    _fixed_stack(_coord("I5")),
                    "slider_crank",
                    "crank-axle",
                    "The crank axle is fixed to the board.",
                ),
                _step(
                    2,
                    "add-linkage",
                    "Add crank link",
                    "Place L2 on I5 with its free hole near G6.",
                    ("I5", "G6"),
                    (spacer, link2),
                    _stack(_coord("I5"), link2, spacer),
                    "slider_crank",
                    "crank-link",
                    "The crank rotates without scraping.",
                    coord_roles=("board", "link_end_reference"),
                ),
                _step(
                    3,
                    "add-linkage",
                    "Add connecting rod",
                    "Fasten L6 to the crank free hole near G6, then point it toward G12.",
                    ("G6", "G12"),
                    (spacer, link6),
                    _link_joint_stack(_coord("G6"), link6, spacer),
                    "slider_crank",
                    "connecting-rod",
                    "The rod joint is moving and is not pinned to the board.",
                    ghosts=(link2.part_id,),
                    coord_roles=("link_joint_reference", "slider_reference"),
                ),
                _step(
                    4,
                    "add-guide",
                    "Fix slider guide",
                    "Fasten the 3-hole bracket along G11, G12, and G13 as the straight guide.",
                    ("G11", "G12", "G13"),
                    (spacer, bracket3),
                    _fixed_part_stack(_coord("G11"), bracket3, spacer),
                    "slider_crank",
                    "slider-guide",
                    "The guide is fixed; only the slider block should move.",
                    ghosts=(link2.part_id, link6.part_id),
                ),
                _step(
                    5,
                    "add-bracket",
                    "Add slider block",
                    "Fasten the 2-hole bracket to the free L6 end near G12 only (not the board).",
                    ("G12",),
                    (spacer, bracket2),
                    _link_end_stack(_coord("G12"), bracket2, spacer),
                    "slider_crank",
                    "slider-block",
                    "The block travels along the guide as the crank turns.",
                    ghosts=(link2.part_id, link6.part_id, bracket3.part_id),
                    coord_roles=("slider_reference",),
                ),
                _step(
                    6,
                    "test-motion",
                    "Turn crank and check slide",
                    "Rotate the L2 crank slowly; the slider block should move left-right along G11-G13.",
                    ("I5", "G12"),
                    (link2, link6, bracket2),
                    _link_end_stack(_coord("G12"), bracket2, spacer),
                    "slider_crank",
                    "motion-check",
                    "If it binds, loosen the G6 and G12 moving joints.",
                    ghosts=(link2.part_id, link6.part_id, bracket2.part_id, bracket3.part_id),
                    coord_roles=("board", "slider_reference"),
                ),
            ),
            AppMapping(
                "slider_crank",
                "recipe",
                (link2.part_id, link6.part_id, bracket2.part_id, bracket3.part_id),
            ),
        ),
    )

    package: dict[str, object] = {
        "schema_version": ASSEMBLY_SCHEMA_VERSION,
        "board": {
            "rows": len(BOARD_ROWS),
            "columns": len(BOARD_COLUMNS),
            "row_labels": list(BOARD_ROWS),
            "column_labels": [str(column) for column in BOARD_COLUMNS],
            "origin": "top-left",
        },
        "hardware": {
            "fastener": PAPER_FASTENER_KEY,
            "fastener_max_length": DEFAULT_FASTENER_MAX_LENGTH,
            "part_hole_diameter_mm": hole_diameter_mm,
            "board_pitch_mm": pitch_mm,
        },
        "recipes": [recipe.to_dict() for recipe in recipes],
    }
    validate_assembly_package(package, manifest, profile=profile)
    return package


def _iter_step_part_ids(step: Mapping[str, object]) -> Iterable[str]:
    raw_parts = step.get("parts", ())
    if isinstance(raw_parts, Sequence) and not isinstance(raw_parts, str):
        for raw_part in raw_parts:
            if isinstance(raw_part, Mapping):
                value = raw_part.get("part")
                if isinstance(value, str):
                    yield value
    raw_stack = step.get("stack", ())
    if isinstance(raw_stack, Sequence) and not isinstance(raw_stack, str):
        for raw_layer in raw_stack:
            if isinstance(raw_layer, Mapping):
                value = raw_layer.get("part")
                if isinstance(value, str):
                    yield value


def validate_assembly_package(
    package: Mapping[str, object],
    manifest: Mapping[str, object],
    *,
    profile: PhysicalKitProfile = DEFAULT_PHYSICAL_KIT_PROFILE,
) -> None:
    if package.get("schema_version") != ASSEMBLY_SCHEMA_VERSION:
        raise AssemblyValidationError("Unsupported assembly schema version")
    index = manifest_part_index(manifest)
    board = package.get("board")
    if not isinstance(board, Mapping):
        raise AssemblyValidationError("Missing board contract")
    expected_rows = profile.board_rows
    expected_columns = profile.board_columns
    if board.get("rows") != expected_rows or board.get("columns") != expected_columns:
        raise AssemblyValidationError(
            f"Assembly guides require a {expected_rows}x{expected_columns} board"
        )
    manifest_rows = manifest.get("board_rows", expected_rows)
    manifest_columns = manifest.get("board_columns", expected_columns)
    if manifest_rows != expected_rows or manifest_columns != expected_columns:
        raise AssemblyValidationError("Assembly manifest board size does not match profile")
    recipes = package.get("recipes")
    if not isinstance(recipes, Sequence) or not recipes:
        raise AssemblyValidationError("Assembly package has no recipes")
    for recipe in recipes:
        if not isinstance(recipe, Mapping):
            raise AssemblyValidationError("Invalid recipe entry")
        steps = recipe.get("steps")
        if not isinstance(steps, Sequence) or not steps:
            raise AssemblyValidationError(f"Recipe {recipe.get('key')} has no steps")
        expected_numbers = list(range(1, len(steps) + 1))
        actual_numbers: list[int] = []
        for step in steps:
            if not isinstance(step, Mapping):
                raise AssemblyValidationError("Invalid step entry")
            raw_n = step.get("n")
            if not isinstance(raw_n, int):
                raise AssemblyValidationError("Step number must be an integer")
            actual_numbers.append(raw_n)
            raw_coords = step.get("coords")
            if not isinstance(raw_coords, Sequence) or isinstance(raw_coords, str):
                raise AssemblyValidationError(f"Step {raw_n} has no board coordinates")
            raw_coord_roles = step.get("coord_roles")
            if not isinstance(raw_coord_roles, Sequence) or isinstance(raw_coord_roles, str):
                raise AssemblyValidationError(f"Step {raw_n} has no coordinate roles")
            if len(raw_coord_roles) != len(raw_coords):
                raise AssemblyValidationError(
                    f"Step {raw_n} coordinate roles do not match coordinates"
                )
            for label in raw_coords:
                if not isinstance(label, str):
                    raise AssemblyValidationError(f"Step {raw_n} has invalid coordinate")
                BoardCoord.from_label(label)
            for part in _iter_step_part_ids(step):
                if part not in index:
                    raise AssemblyValidationError(f"Unknown assembly part reference: {part}")
            stack = step.get("stack")
            if not isinstance(stack, Sequence):
                raise AssemblyValidationError(f"Step {raw_n} has invalid stack")
            action = str(step.get("action", ""))
            if action in {"add-part", "add-linkage", "add-guide", "test-motion"}:
                roles = {
                    str(layer.get("role"))
                    for layer in stack
                    if isinstance(layer, Mapping) and layer.get("role") is not None
                }
                if "paper-fastener" not in roles or not ({"spacer", "top-spacer"} & roles):
                    raise AssemblyValidationError(
                        f"Moving step {raw_n} missing fastener/spacer stack"
                    )
            visual = step.get("visual_state")
            mapping = step.get("app_mapping")
            if not isinstance(visual, Mapping) or not isinstance(mapping, Mapping):
                raise AssemblyValidationError(
                    f"Step {raw_n} missing bidirectional visual/app mapping"
                )
            raw_active_parts = visual.get("active_parts", ())
            active_parts = (
                tuple(str(part) for part in raw_active_parts if isinstance(part, str))
                if isinstance(raw_active_parts, Sequence) and not isinstance(raw_active_parts, str)
                else ()
            )
            raw_highlight_ids = mapping.get("highlight_ids", ())
            highlight_ids = (
                tuple(str(part) for part in raw_highlight_ids if isinstance(part, str))
                if isinstance(raw_highlight_ids, Sequence)
                and not isinstance(raw_highlight_ids, str)
                else ()
            )
            step_parts = tuple(_iter_step_part_ids(step))
            for active in active_parts + highlight_ids:
                if active not in step_parts:
                    raise AssemblyValidationError(
                        f"Step {raw_n} app/visual part not in physical step: {active}"
                    )
        if actual_numbers != expected_numbers:
            raise AssemblyValidationError(f"Recipe {recipe.get('key')} has non-contiguous steps")
        raw_compatibility = recipe.get("compatibility", ())
        if isinstance(raw_compatibility, Sequence) and not isinstance(raw_compatibility, str):
            for raw_compat in raw_compatibility:
                if not isinstance(raw_compat, Mapping):
                    continue
                if raw_compat.get("compatible") is not True:
                    raise AssemblyValidationError(
                        f"Recipe {recipe.get('key')} has incompatible gear pair"
                    )
                for compat_part in (
                    raw_compat.get("first_part"),
                    raw_compat.get("second_part"),
                ):
                    if isinstance(compat_part, str) and compat_part not in index:
                        raise AssemblyValidationError(
                            f"Unknown gear compatibility part: {compat_part}"
                        )
    hole = finite_float(manifest.get("hole_diameter_mm"), profile.hole_diameter_mm)
    hardware = package.get("hardware")
    if (
        not isinstance(hardware, Mapping)
        or finite_float(hardware.get("part_hole_diameter_mm"), 0.0) != hole
    ):
        raise AssemblyValidationError("Assembly hardware hole diameter must match manifest")
