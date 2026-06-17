from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import TypeVar

from automataii.application.mechanism_transfer import (
    MechanismTransferPackage,
    MechanismTransferService,
    TransferValidationError,
)
from automataii.shared.physical_kit import (
    DEFAULT_GRID_CELL_CM,
    DEFAULT_PHYSICAL_KIT_PROFILE,
    PhysicalKitProfile,
    allowed_linkage_lengths_mm,
)

from .catalog import MechanismEntry, MechanismParameter
from .mechanism_types import canonical_mechanism_type, is_visible_foundry_mechanism_type
from .service import MechanismCatalogService

T = TypeVar("T")


@dataclass(frozen=True)
class MechanismItem:
    category_key: str
    mechanism_key: str
    display_name: str
    entry: MechanismEntry
    mechanism_type: str


@dataclass(frozen=True)
class ParameterSpec:
    key: str
    label: str
    min_value: float
    max_value: float
    default_value: float
    value_type: str = "float"
    unit: str | None = None
    step: float = 1.0

    @property
    def is_integer(self) -> bool:
        return self.value_type in {"int", "integer"}


@dataclass(frozen=True)
class MechanismConfiguration:
    mechanism_type: str
    parameter_specs: Sequence[ParameterSpec]
    extra_defaults: Mapping[str, float] = field(default_factory=dict)

    def initial_parameters(self) -> dict[str, float]:
        values = {spec.key: spec.default_value for spec in self.parameter_specs}
        values.update(self.extra_defaults)
        return values


def build_mechanism_configs(
    profile: PhysicalKitProfile = DEFAULT_PHYSICAL_KIT_PROFILE,
    grid_cell_cm: float = DEFAULT_GRID_CELL_CM,
) -> dict[str, MechanismConfiguration]:
    """Build Foundry defaults from the active physical-kit profile."""

    linkage_lengths_mm = allowed_linkage_lengths_mm(grid_cell_cm, profile=profile)
    if not linkage_lengths_mm:
        raise ValueError("PhysicalKitProfile must define at least one linkage length cell")
    if not profile.gear_presets:
        raise ValueError("PhysicalKitProfile must define at least one gear preset")
    if not profile.cam_presets:
        raise ValueError("PhysicalKitProfile must define at least one cam preset")

    def _at(values: Sequence[T], index: int) -> T:
        return values[min(index, len(values) - 1)]

    min_linkage_mm = min(linkage_lengths_mm)
    max_linkage_mm = max(linkage_lengths_mm)
    gear_teeth = tuple(preset.teeth for preset in profile.gear_presets)
    min_gear_teeth = min(gear_teeth)
    max_gear_teeth = max(gear_teeth)
    default_cam = _at(profile.cam_presets, 1).params_mm(grid_cell_cm)

    return {
        "four_bar": MechanismConfiguration(
            mechanism_type="four_bar",
            parameter_specs=(
                ParameterSpec(
                    "ground_link",
                    "Ground Link (mm)",
                    min_linkage_mm,
                    max_linkage_mm,
                    _at(linkage_lengths_mm, 3),
                    "float",
                    "mm",
                    step=1.0,
                ),
                ParameterSpec(
                    "input_link",
                    "Input Link (mm)",
                    min_linkage_mm,
                    max_linkage_mm,
                    _at(linkage_lengths_mm, 0),
                    "float",
                    "mm",
                    step=1.0,
                ),
                ParameterSpec(
                    "coupler_link",
                    "Coupler Link (mm)",
                    min_linkage_mm,
                    max_linkage_mm,
                    _at(linkage_lengths_mm, 2),
                    "float",
                    "mm",
                    step=1.0,
                ),
                ParameterSpec(
                    "output_link",
                    "Output Link (mm)",
                    min_linkage_mm,
                    max_linkage_mm,
                    _at(linkage_lengths_mm, 2),
                    "float",
                    "mm",
                    step=1.0,
                ),
            ),
            extra_defaults={"input_angle": 30.0},
        ),
        "slider_crank": MechanismConfiguration(
            mechanism_type="slider_crank",
            parameter_specs=(
                ParameterSpec(
                    "crank_length",
                    "Crank Length (mm)",
                    min_linkage_mm,
                    max_linkage_mm,
                    _at(linkage_lengths_mm, 1),
                    "float",
                    "mm",
                    step=1.0,
                ),
                ParameterSpec(
                    "rod_length",
                    "Rod Length (mm)",
                    min_linkage_mm,
                    max_linkage_mm,
                    _at(linkage_lengths_mm, 3),
                    "float",
                    "mm",
                    step=1.0,
                ),
                ParameterSpec(
                    "gas_pressure",
                    "Gas Pressure (kPa)",
                    50.0,
                    2000.0,
                    500.0,
                    "float",
                    "kPa",
                    step=10.0,
                ),
            ),
            extra_defaults={"input_angle": 30.0},
        ),
        "cam_follower": MechanismConfiguration(
            mechanism_type="cam_follower",
            parameter_specs=(
                ParameterSpec(
                    "cam_radius",
                    "Cam Radius (mm)",
                    _at(linkage_lengths_mm, 0),
                    _at(linkage_lengths_mm, 3),
                    default_cam["base_radius"],
                    "float",
                    "mm",
                    step=1.0,
                ),
                ParameterSpec(
                    "cam_offset",
                    "Cam Offset (mm)",
                    0.0,
                    _at(linkage_lengths_mm, 1),
                    default_cam["eccentricity"],
                    "float",
                    "mm",
                    step=1.0,
                ),
                ParameterSpec(
                    "follower_length",
                    "Follower Length (mm)",
                    min_linkage_mm,
                    max_linkage_mm,
                    _at(linkage_lengths_mm, 3),
                    "float",
                    "mm",
                    step=1.0,
                ),
                ParameterSpec("cam_lobes", "Cam Lobes", 1, 4, 1, "int", "lobes", step=1.0),
                ParameterSpec(
                    "profile_harmonic",
                    "Profile Variation",
                    0.0,
                    0.8,
                    default_cam["profile_harmonic"],
                    "float",
                    "ratio",
                    step=0.05,
                ),
            ),
            extra_defaults={"input_angle": 30.0},
        ),
        "gear_train": MechanismConfiguration(
            mechanism_type="gear_train",
            parameter_specs=(
                ParameterSpec(
                    "gear1_teeth",
                    "Drive Gear Teeth",
                    min_gear_teeth,
                    max_gear_teeth,
                    _at(profile.gear_presets, 0).teeth,
                    "int",
                    "teeth",
                    step=1.0,
                ),
                ParameterSpec(
                    "gear2_teeth",
                    "Driven Gear Teeth",
                    min_gear_teeth,
                    max_gear_teeth,
                    _at(profile.gear_presets, 2).teeth,
                    "int",
                    "teeth",
                    step=1.0,
                ),
                ParameterSpec(
                    "input_torque",
                    "Input Torque (Nm)",
                    10.0,
                    1000.0,
                    200.0,
                    "float",
                    "Nm",
                    step=10.0,
                ),
            ),
            extra_defaults={"input_angle": 30.0},
        ),
        "gear_linkage": MechanismConfiguration(
            mechanism_type="gear_linkage",
            parameter_specs=(
                ParameterSpec(
                    "gear1_teeth",
                    "Drive Gear Teeth",
                    min_gear_teeth,
                    max_gear_teeth,
                    _at(profile.gear_presets, 0).teeth,
                    "int",
                    "teeth",
                    step=1.0,
                ),
                ParameterSpec(
                    "gear2_teeth",
                    "Driven Gear Teeth",
                    min_gear_teeth,
                    max_gear_teeth,
                    _at(profile.gear_presets, 1).teeth,
                    "int",
                    "teeth",
                    step=1.0,
                ),
                ParameterSpec(
                    "linkage_pin_radius",
                    "Linkage Pin Radius (mm)",
                    profile.hole_diameter_mm,
                    _at(linkage_lengths_mm, 1),
                    grid_cell_cm * 10.0,
                    "float",
                    "mm",
                    step=1.0,
                ),
                ParameterSpec(
                    "linkage_arm_length",
                    "Linkage Arm Length (mm)",
                    min_linkage_mm,
                    max_linkage_mm,
                    _at(linkage_lengths_mm, 1),
                    "float",
                    "mm",
                    step=1.0,
                ),
            ),
            extra_defaults={"input_angle": 30.0, "gear_linkage_enabled": 1.0},
        ),
    }


# Compatibility defaults for tests/legacy callers only. Runtime Foundry views
# use instance-level configs built from the app-owned physical context.
MECHANISM_CONFIGS: dict[str, MechanismConfiguration] = build_mechanism_configs()


def _build_entry_from_config(
    key: str,
    display_name: str,
    description: str,
    mech_type: str,
    config: MechanismConfiguration,
) -> MechanismEntry:
    parameters = {
        spec.key: MechanismParameter(
            key=spec.key,
            name=spec.label,
            type="int" if spec.is_integer else "float",
            default=spec.default_value,
            min=spec.min_value,
            max=spec.max_value,
            unit=spec.unit,
            description=None,
        )
        for spec in config.parameter_specs
    }
    return MechanismEntry(
        key=key,
        name=display_name,
        description=description,
        mech_type=mech_type,
        class_name="",
        tags=(),
        complexity="beginner",
        parameters=parameters,
        preview_size=None,
        animation_duration=None,
    )


def build_fallback_items(
    configs: Mapping[str, MechanismConfiguration],
) -> Sequence[MechanismItem]:
    return (
        MechanismItem(
            category_key="__fallback__",
            mechanism_key="four_bar",
            display_name="Four-Bar Linkage",
            entry=_build_entry_from_config(
                key="four_bar",
                display_name="Four-Bar Linkage",
                description="Classic four-bar mechanism for converting rotary to oscillating motion.",
                mech_type="four_bar_linkage",
                config=configs["four_bar"],
            ),
            mechanism_type="four_bar",
        ),
        MechanismItem(
            category_key="__fallback__",
            mechanism_key="slider_crank",
            display_name="Slider-Crank",
            entry=_build_entry_from_config(
                key="slider_crank",
                display_name="Slider-Crank",
                description="Converts rotary motion into reciprocating motion with a piston.",
                mech_type="slider_crank",
                config=configs["slider_crank"],
            ),
            mechanism_type="slider_crank",
        ),
        MechanismItem(
            category_key="__fallback__",
            mechanism_key="cam_follower",
            display_name="Cam-Follower",
            entry=_build_entry_from_config(
                key="cam_follower",
                display_name="Cam-Follower",
                description="Basic cam mechanism with follower for motion control.",
                mech_type="cam_follower",
                config=configs["cam_follower"],
            ),
            mechanism_type="cam_follower",
        ),
        MechanismItem(
            category_key="__fallback__",
            mechanism_key="gear_train",
            display_name="Gear Train",
            entry=_build_entry_from_config(
                key="gear_train",
                display_name="Gear Train",
                description="Two meshing gears for speed and torque conversion.",
                mech_type="gear_train",
                config=configs["gear_train"],
            ),
            mechanism_type="gear_train",
        ),
        MechanismItem(
            category_key="__fallback__",
            mechanism_key="gear_linkage",
            display_name="Gear + Linkage",
            entry=_build_entry_from_config(
                key="gear_linkage",
                display_name="Gear + Linkage",
                description=("Meshing gears with an off-center crank hole driving a linkage arm."),
                mech_type="gear_linkage",
                config=configs["gear_linkage"],
            ),
            mechanism_type="gear_linkage",
        ),
    )


class MechanismFoundryController:
    """Controller coordinating catalog and configuration data for the Foundry tab."""

    def __init__(
        self,
        service: MechanismCatalogService | None = None,
        *,
        physical_profile: PhysicalKitProfile = DEFAULT_PHYSICAL_KIT_PROFILE,
        grid_cell_cm: float = DEFAULT_GRID_CELL_CM,
    ) -> None:
        self._service = service or MechanismCatalogService()
        self._configs = build_mechanism_configs(physical_profile, grid_cell_cm)
        self._fallback_items = build_fallback_items(self._configs)
        self._mechanisms: list[MechanismItem] = []
        self._load_catalog_items()
        self._ensure_fallback_items()
        order = {"four_bar": 0, "cam_follower": 1, "gear_train": 2, "gear_linkage": 3}
        self._mechanisms.sort(
            key=lambda item: (order.get(item.mechanism_type, 99), item.display_name)
        )
        self._selection: MechanismItem | None = self._mechanisms[0] if self._mechanisms else None

    @property
    def service(self) -> MechanismCatalogService:
        return self._service

    def list_mechanisms(self) -> Iterable[MechanismItem]:
        return [
            item
            for item in self._mechanisms
            if is_visible_foundry_mechanism_type(item.mechanism_type)
        ]

    def select_mechanism(self, category_key: str, mechanism_key: str) -> MechanismEntry | None:
        for item in self._mechanisms:
            if item.category_key == category_key and item.mechanism_key == mechanism_key:
                self._selection = item
                return item.entry
        return None

    @property
    def selected_entry(self) -> MechanismEntry | None:
        return self._selection.entry if self._selection else None

    @property
    def selected_configuration(self) -> MechanismConfiguration | None:
        return self.get_configuration()

    def get_configuration(self, mechanism_type: str | None = None) -> MechanismConfiguration | None:
        target = mechanism_type or (self._selection.mechanism_type if self._selection else None)
        if target is None:
            return None
        canonical_type = self._map_catalog_type(target)
        return self._configs.get(canonical_type or target)

    def initial_parameters(self, mechanism_type: str | None = None) -> dict[str, float]:
        config = self.get_configuration(mechanism_type)
        return config.initial_parameters() if config else {}

    @staticmethod
    def default_configuration(mechanism_type: str | None) -> MechanismConfiguration | None:
        """Return the default-kit configuration for legacy/static callers.

        New runtime code should use an instance created with the active
        ``PhysicalKitProfile``/grid pitch and call ``get_configuration``.
        """
        if mechanism_type is None:
            return None
        canonical_type = MechanismFoundryController._map_catalog_type(mechanism_type)
        return build_mechanism_configs().get(canonical_type or mechanism_type)

    @staticmethod
    def fallback_items() -> Sequence[MechanismItem]:
        """Return default-kit fallback items for legacy/static callers."""
        return build_fallback_items(build_mechanism_configs())

    def _load_catalog_items(self) -> None:
        try:
            categories = list(self._service.list_categories())
        except Exception:
            return
        for category in categories:
            for entry_key, entry in category.mechanisms.items():
                mechanism_type = self._map_catalog_type(entry.mech_type)
                if mechanism_type not in self._configs:
                    continue
                if not is_visible_foundry_mechanism_type(mechanism_type):
                    continue
                self._mechanisms.append(
                    MechanismItem(
                        category_key=category.key,
                        mechanism_key=entry_key,
                        display_name=entry.name,
                        entry=entry,
                        mechanism_type=mechanism_type,
                    )
                )

    def _ensure_fallback_items(self) -> None:
        existing_types = {item.mechanism_type for item in self._mechanisms}
        for fallback in self._fallback_items:
            if not is_visible_foundry_mechanism_type(fallback.mechanism_type):
                continue
            if fallback.mechanism_type not in existing_types:
                self._mechanisms.append(fallback)

    @staticmethod
    def _map_catalog_type(mech_type: str | None) -> str | None:
        if mech_type is None:
            return None
        return canonical_mechanism_type(mech_type)

    def export_mechanism_to_design(
        self,
        parameters: Mapping[str, float],
        pivot_point: tuple[float, float],
    ) -> MechanismTransferPackage:
        if not self._selection:
            raise TransferValidationError("No mechanism selected for export")

        transfer_service = MechanismTransferService()
        return transfer_service.create_export_package(
            mechanism_type=self._selection.mechanism_type,
            parameters=parameters,
            pivot_point=pivot_point,
        )
