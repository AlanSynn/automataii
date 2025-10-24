from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional, Sequence

from automataii.application.mechanism_transfer import (
    MechanismTransferPackage,
    MechanismTransferService,
    TransferValidationError,
)

from .catalog import MechanismEntry, MechanismParameter
from .service import MechanismCatalogService


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


MECHANISM_CONFIGS: Dict[str, MechanismConfiguration] = {
    "four_bar": MechanismConfiguration(
        mechanism_type="four_bar",
        parameter_specs=(
            ParameterSpec(
                "ground_link", "Ground Link (mm)", 30.0, 300.0, 150.0, "float", "mm", step=1.0
            ),
            ParameterSpec(
                "input_link", "Input Link (mm)", 10.0, 150.0, 40.0, "float", "mm", step=1.0
            ),
            ParameterSpec(
                "coupler_link", "Coupler Link (mm)", 20.0, 250.0, 120.0, "float", "mm", step=1.0
            ),
            ParameterSpec(
                "output_link", "Output Link (mm)", 20.0, 250.0, 130.0, "float", "mm", step=1.0
            ),
        ),
        extra_defaults={"input_angle": 30.0},
    ),
    "slider_crank": MechanismConfiguration(
        mechanism_type="slider_crank",
        parameter_specs=(
            ParameterSpec(
                "crank_length", "Crank Length (mm)", 40.0, 160.0, 80.0, "float", "mm", step=1.0
            ),
            ParameterSpec(
                "rod_length", "Rod Length (mm)", 50.0, 220.0, 140.0, "float", "mm", step=1.0
            ),
            ParameterSpec(
                "gas_pressure", "Gas Pressure (kPa)", 50.0, 2000.0, 500.0, "float", "kPa", step=10.0
            ),
        ),
        extra_defaults={"input_angle": 30.0},
    ),
    "cam_follower": MechanismConfiguration(
        mechanism_type="cam_follower",
        parameter_specs=(
            ParameterSpec(
                "cam_radius", "Cam Radius (mm)", 20.0, 150.0, 60.0, "float", "mm", step=1.0
            ),
            ParameterSpec(
                "cam_offset", "Cam Offset (mm)", 5.0, 60.0, 20.0, "float", "mm", step=1.0
            ),
            ParameterSpec(
                "follower_length",
                "Follower Length (mm)",
                30.0,
                200.0,
                100.0,
                "float",
                "mm",
                step=1.0,
            ),
            ParameterSpec("cam_lobes", "Cam Lobes", 1, 4, 1, "int", "lobes", step=1.0),
            ParameterSpec(
                "profile_harmonic", "Profile Variation", 0.0, 0.8, 0.3, "float", "ratio", step=0.05
            ),
        ),
        extra_defaults={"input_angle": 30.0},
    ),
    "gear_train": MechanismConfiguration(
        mechanism_type="gear_train",
        parameter_specs=(
            ParameterSpec("gear1_teeth", "Drive Gear Teeth", 8, 24, 12, "int", "teeth", step=1.0),
            ParameterSpec("gear2_teeth", "Driven Gear Teeth", 8, 24, 18, "int", "teeth", step=1.0),
            ParameterSpec(
                "input_torque", "Input Torque (Nm)", 10.0, 1000.0, 200.0, "float", "Nm", step=10.0
            ),
        ),
        extra_defaults={"input_angle": 30.0},
    ),
}

CATALOG_TYPE_TO_MECHANISM_TYPE: Dict[str, str] = {
    "four_bar_linkage": "four_bar",
    "cam_follower": "cam_follower",
    "gear_train": "gear_train",
}


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


_FALLBACK_ITEMS: Sequence[MechanismItem] = (
    MechanismItem(
        category_key="__fallback__",
        mechanism_key="four_bar",
        display_name="Four-Bar Linkage",
        entry=_build_entry_from_config(
            key="four_bar",
            display_name="Four-Bar Linkage",
            description="Classic four-bar mechanism for converting rotary to oscillating motion.",
            mech_type="four_bar_linkage",
            config=MECHANISM_CONFIGS["four_bar"],
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
            config=MECHANISM_CONFIGS["slider_crank"],
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
            config=MECHANISM_CONFIGS["cam_follower"],
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
            config=MECHANISM_CONFIGS["gear_train"],
        ),
        mechanism_type="gear_train",
    ),
)


class MechanismFoundryController:
    """Controller coordinating catalog and configuration data for the Foundry tab."""

    def __init__(self, service: MechanismCatalogService | None = None) -> None:
        self._service = service or MechanismCatalogService()
        self._mechanisms: List[MechanismItem] = []
        self._load_catalog_items()
        self._ensure_fallback_items()
        self._mechanisms.sort(key=lambda item: item.display_name)
        self._selection: MechanismItem | None = self._mechanisms[0] if self._mechanisms else None

    @property
    def service(self) -> MechanismCatalogService:
        return self._service

    def list_mechanisms(self) -> Iterable[MechanismItem]:
        return list(self._mechanisms)

    def select_mechanism(self, category_key: str, mechanism_key: str) -> Optional[MechanismEntry]:
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
        return self.default_configuration(target)

    def initial_parameters(self, mechanism_type: str | None = None) -> dict[str, float]:
        config = self.get_configuration(mechanism_type)
        return config.initial_parameters() if config else {}

    @staticmethod
    def default_configuration(mechanism_type: str | None) -> MechanismConfiguration | None:
        if mechanism_type is None:
            return None
        return MECHANISM_CONFIGS.get(mechanism_type)

    @staticmethod
    def fallback_items() -> Sequence[MechanismItem]:
        return _FALLBACK_ITEMS

    def _load_catalog_items(self) -> None:
        try:
            categories = list(self._service.list_categories())
        except Exception:
            return
        for category in categories:
            for entry_key, entry in category.mechanisms.items():
                mechanism_type = self._map_catalog_type(entry.mech_type)
                if mechanism_type not in MECHANISM_CONFIGS:
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
        for fallback in _FALLBACK_ITEMS:
            if fallback.mechanism_type not in existing_types:
                self._mechanisms.append(fallback)

    @staticmethod
    def _map_catalog_type(mech_type: str | None) -> str | None:
        if mech_type is None:
            return None
        return CATALOG_TYPE_TO_MECHANISM_TYPE.get(mech_type)

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
