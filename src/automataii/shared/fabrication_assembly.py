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
    DEFAULT_PHYSICAL_KIT_PROFILE,
    PhysicalKitProfile,
    finite_float,
    gear_center_distance,
)

ASSEMBLY_SCHEMA_VERSION = "automataii.fabrication.assembly.v1"
BOARD_ROWS: tuple[str, ...] = tuple(chr(ord("A") + idx) for idx in range(15))
BOARD_COLUMNS: tuple[int, ...] = tuple(range(1, 16))
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
) -> AssemblyStep:
    board_coords = tuple(_coord(coord) for coord in coords)
    part_ids = tuple(part.part_id for part in parts)
    return AssemblyStep(
        n=n,
        action=action,
        title=title,
        instruction=instruction,
        coords=board_coords,
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
    bracket2 = _part("brackets", "2-hole-straight", "2-hole bracket")
    bracket_l = _part("brackets", "l-3-hole", "L bracket")
    spacer = _part("spacers", "s8", "S8 spacer", count=8)
    spacer_tall = _part("spacers", "s12", "S12 spacer", count=2)

    drive_gear, driven_gear, drive_coord, driven_coord, gear_compat = _best_gear_pair(
        "H6", pitch_mm, index, profile
    )
    crank_drive_gear, crank_driven_gear, crank_drive_coord, crank_driven_coord, gear_link_compat = (
        _best_gear_pair("I6", pitch_mm, index, profile)
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
            (link2, link4, bracket_l, spacer),
            (
                _step(
                    1,
                    "place-ground",
                    "Set ground pivots",
                    "Pin ground pivots at I5 and I9.",
                    ("I5", "I9"),
                    (bracket_l,),
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
                    ghosts=(bracket_l.part_id,),
                ),
                _step(
                    3,
                    "add-linkage",
                    "Add coupler",
                    "Join L4 between G6 and G10.",
                    ("G6", "G10"),
                    (spacer, link4),
                    _stack(_coord("G6"), link4, spacer),
                    "four_bar",
                    "coupler",
                    "The coupler moves without scraping.",
                    ghosts=(bracket_l.part_id, link2.part_id),
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
                    ghosts=(bracket_l.part_id, link2.part_id, link4.part_id),
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
                    f"Attach L4 from a {_part_short_label(crank_driven_gear)} handle hole toward I12.",
                    (crank_driven_coord.label, "I12"),
                    (spacer, link4),
                    _stack(crank_driven_coord, link4, spacer),
                    "gear_linkage",
                    "output-link",
                    f"The linkage pushes and pulls as {_part_short_label(crank_driven_gear)} turns.",
                    ghosts=(crank_drive_gear.part_id, crank_driven_gear.part_id),
                ),
            ),
            AppMapping(
                "gear_linkage",
                "recipe",
                (crank_drive_gear.part_id, crank_driven_gear.part_id, link4.part_id),
            ),
            (gear_link_compat,),
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
    if board.get("rows") != 15 or board.get("columns") != 15:
        raise AssemblyValidationError("Assembly guides require a 15x15 board")
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
