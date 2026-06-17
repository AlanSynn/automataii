"""Contract tests for mechanism factory-origin add flows.

These tests intentionally exercise the bottom-up path that starts with Foundry/factory
mechanism type strings and ends in Design-tab layer/render dispatch types.
"""

from __future__ import annotations

import logging
import math
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from automataii.application.mechanism_foundry import MechanismFoundryController, MechanismItem
from automataii.application.mechanism_transfer import (
    MechanismTransferService,
    TransferValidationError,
)
from automataii.application.mechanism_transfer.contract import SUPPORTED_EXPORT_TYPES
from automataii.application.mechanism_transfer.spec import (
    validate_export_type as spec_validate_export_type,
)
from automataii.presentation.qt.tabs.mechanism_design.presenter import MechanismDesignPresenter
from automataii.presentation.qt.tabs.mechanism_design.services.mechanism_instantiation_service import (
    MechanismInstantiationService,
    UnsupportedMechanismTypeError,
)

EXPECTED_FOUNDRY_TO_DESIGN_TYPES = {
    "four_bar": "4_bar_linkage",
    "cam_follower": "cam",
    "gear_train": "gear",
    "gear_linkage": "gear",
    "planetary_gear": "planetary_gear",
    "slider_crank": "4_bar_linkage",
}

VISIBLE_FOUNDRY_TYPES = {
    "four_bar",
    "cam_follower",
    "gear_train",
    "gear_linkage",
    "planetary_gear",
}

RENDERABLE_DESIGN_TYPES = {"4_bar_linkage", "cam", "gear", "planetary_gear"}


def _controller_items_by_type() -> dict[str, MechanismItem]:
    controller = MechanismFoundryController()
    return {item.mechanism_type: item for item in controller.list_mechanisms()}


@pytest.mark.parametrize(
    "foundry_type,design_type", sorted(EXPECTED_FOUNDRY_TO_DESIGN_TYPES.items())
)
def test_foundry_factory_creates_renderable_design_layer(
    foundry_type: str, design_type: str
) -> None:
    """Every Foundry-exposed type should map to an explicit renderable Design type."""
    controller = MechanismFoundryController()
    defaults = controller.initial_parameters(foundry_type)
    assert defaults, f"Missing default parameters for Foundry type {foundry_type!r}"

    service = MechanismInstantiationService()
    layer_data = service.create_layer_data_from_foundry(
        mechanism_type=foundry_type,
        parameters=defaults,
        pivot_point=(0.0, 0.0),
        part_name="torso",
        scene_position=(400.0, 300.0),
    )

    assert layer_data["type"] == design_type
    assert layer_data["type"] in RENDERABLE_DESIGN_TYPES
    assert layer_data["id"]
    assert layer_data["params"]
    assert layer_data["visual_items"] == []
    assert layer_data["source"] == "foundry"
    assert layer_data["source_type"] == foundry_type

    if foundry_type == "four_bar":
        assert {"l1", "l2", "l3", "l4"}.issubset(layer_data["params"])
        assert {"ground_pivot_1", "ground_pivot_2"}.issubset(layer_data["key_points"])
    elif foundry_type == "cam_follower":
        assert {"base_radius", "eccentricity", "center_x", "center_y"}.issubset(
            layer_data["params"]
        )
        assert "cam_position" in layer_data
    elif foundry_type == "gear_train":
        assert {"gear1_center", "gear2_center"}.issubset(layer_data["key_points"])
    elif foundry_type == "planetary_gear":
        assert layer_data["type"] == "planetary_gear"
        assert {"sun_teeth", "planet_teeth", "r_sun", "r_planet"}.issubset(layer_data["params"])
    elif foundry_type == "slider_crank":
        assert layer_data["approximated_as"] == "4_bar_linkage"
        assert layer_data["params"]["l1"] > 0.0


def test_controller_exposed_types_have_factory_contract_coverage() -> None:
    """Adding a Foundry type must force an explicit factory contract decision."""
    exposed_types = set(_controller_items_by_type())
    assert exposed_types == VISIBLE_FOUNDRY_TYPES
    assert exposed_types.issubset(EXPECTED_FOUNDRY_TO_DESIGN_TYPES)


@pytest.mark.parametrize(
    "catalog_type,foundry_type",
    [
        ("four_bar", "four_bar"),
        ("four_bar_linkage", "four_bar"),
        ("4_bar_linkage", "four_bar"),
        ("cam", "cam_follower"),
        ("cam_follower", "cam_follower"),
        ("gear", "gear_train"),
        ("gear_train", "gear_train"),
        ("planetary_gear", "planetary_gear"),
        ("slider_crank", "slider_crank"),
        ("slider-crank", "slider_crank"),
        ("slidercrank", "slider_crank"),
    ],
)
def test_catalog_type_aliases_map_to_foundry_types(catalog_type: str, foundry_type: str) -> None:
    """Catalog aliases should not disappear from Foundry just because naming drifted."""
    assert MechanismFoundryController._map_catalog_type(catalog_type) == foundry_type


@pytest.mark.parametrize(
    "catalog_type,foundry_type",
    [
        (" Four_Bar ", "four_bar"),
        ("CAM", "cam_follower"),
        (" Gear ", "gear_train"),
        (" Slider-Crank ", "slider_crank"),
    ],
)
def test_catalog_type_aliases_ignore_case_and_whitespace(
    catalog_type: str,
    foundry_type: str,
) -> None:
    """Catalog metadata often comes from files; case/space drift should not hide entries."""
    assert MechanismFoundryController._map_catalog_type(catalog_type) == foundry_type
    assert MechanismFoundryController.default_configuration(catalog_type) is not None


@pytest.mark.parametrize("foundry_type", sorted(EXPECTED_FOUNDRY_TO_DESIGN_TYPES))
def test_legacy_transfer_spec_accepts_foundry_export_contract(foundry_type: str) -> None:
    """The older spec module must not drift behind the Foundry export contract."""
    assert foundry_type in SUPPORTED_EXPORT_TYPES
    assert spec_validate_export_type(foundry_type)


@pytest.mark.parametrize("unsupported_type", ["six_bar_linkage", "unknown_custom"])
def test_foundry_factory_rejects_unsupported_types_without_4bar_fallback(
    unsupported_type: str,
) -> None:
    """Unsupported types must not silently become 4-bar linkages."""
    service = MechanismInstantiationService()

    with pytest.raises(UnsupportedMechanismTypeError, match=unsupported_type):
        service.create_layer_data_from_foundry(
            mechanism_type=unsupported_type,
            parameters={},
            pivot_point=(0.0, 0.0),
            scene_position=(400.0, 300.0),
        )


@pytest.mark.parametrize("display_type", ["Unknown Mechanism", "six_bar_linkage", "planetary_gear"])
def test_recommendation_factory_rejects_unknown_display_types(display_type: str) -> None:
    service = MechanismInstantiationService()

    with pytest.raises(UnsupportedMechanismTypeError, match=display_type):
        service.map_mechanism_type(display_type)


@pytest.mark.parametrize("foundry_type", sorted(VISIBLE_FOUNDRY_TYPES))
def test_controller_export_supports_every_exposed_foundry_type(foundry_type: str) -> None:
    """The public controller export route should not reject a visible Foundry type."""
    controller = MechanismFoundryController()
    item = _controller_items_by_type()[foundry_type]
    controller.select_mechanism(item.category_key, item.mechanism_key)
    defaults = controller.initial_parameters(foundry_type)

    try:
        package = controller.export_mechanism_to_design(defaults, pivot_point=(400.0, 300.0))
    except TransferValidationError as exc:  # pragma: no cover - assertion rewrites message below
        pytest.fail(f"{foundry_type!r} is exposed by Foundry but rejected for export: {exc}")

    assert package.export_data.mechanism_type == foundry_type
    assert foundry_type in SUPPORTED_EXPORT_TYPES


@pytest.mark.parametrize(
    "bad_value,match",
    [
        (True, "must be numeric"),
        (float("nan"), "must be finite"),
        (float("inf"), "must be finite"),
    ],
)
def test_transfer_export_rejects_bool_and_non_finite_parameters(
    bad_value: float | bool,
    match: str,
) -> None:
    service = MechanismTransferService()
    params = {
        "ground_link": 150.0,
        "input_link": bad_value,
        "coupler_link": 120.0,
        "output_link": 130.0,
        "input_angle": 30.0,
    }

    with pytest.raises(TransferValidationError, match=match):
        service.create_export_package(
            mechanism_type="four_bar",
            parameters=params,
            pivot_point=(0.0, 0.0),
        )


@pytest.mark.parametrize(
    "kwargs,match",
    [
        ({"pivot_point": (0.0, math.nan)}, "pivot_point"),
        ({"scale": 0.0}, "scale"),
        ({"scale": math.inf}, "scale"),
        ({"cycle_duration_ms": 0}, "cycle_duration_ms"),
        ({"steps_per_cycle": 0}, "steps_per_cycle"),
    ],
)
def test_transfer_export_rejects_invalid_visual_and_animation_config(
    kwargs: dict[str, object],
    match: str,
) -> None:
    service = MechanismTransferService()
    params = {
        "ground_link": 150.0,
        "input_link": 40.0,
        "coupler_link": 120.0,
        "output_link": 130.0,
        "input_angle": 30.0,
    }
    call_kwargs = {"pivot_point": (0.0, 0.0), **kwargs}

    with pytest.raises(TransferValidationError, match=match):
        service.create_export_package(
            mechanism_type="four_bar",
            parameters=params,
            **call_kwargs,
        )


def test_transfer_export_normalizes_visual_config_payload_types() -> None:
    """Validated transfer packages should carry canonical tuple/float visual values."""
    service = MechanismTransferService()
    package = service.create_export_package(
        mechanism_type="four_bar",
        parameters={
            "ground_link": 150.0,
            "input_link": 40.0,
            "coupler_link": 120.0,
            "output_link": 130.0,
            "input_angle": 30.0,
        },
        pivot_point=[400, 300],  # type: ignore[arg-type]
        scale=2,
    )

    assert package.export_data.visual_config.pivot_point == (400.0, 300.0)
    assert package.export_data.visual_config.scale == 2.0


def test_transfer_import_validation_rejects_tampered_visual_and_animation_config() -> None:
    """Import validation must re-check visual/animation config, not only parameters."""
    service = MechanismTransferService()
    package = service.create_export_package(
        mechanism_type="four_bar",
        parameters={
            "ground_link": 150.0,
            "input_link": 40.0,
            "coupler_link": 120.0,
            "output_link": 130.0,
            "input_angle": 30.0,
        },
        pivot_point=(0.0, 0.0),
    )

    bad_visual = replace(
        package,
        export_data=replace(
            package.export_data,
            visual_config=replace(package.export_data.visual_config, scale=0.0),
        ),
    )
    bad_animation = replace(
        package,
        animation_config=replace(package.animation_config, steps_per_cycle=0),
    )

    assert service.validate_import_package(bad_visual) is False
    assert service.validate_import_package(bad_animation) is False


def test_catalog_unsupported_mechanisms_are_hidden_from_foundry_controller() -> None:
    """Catalog entries without Design support should be hidden, not half-importable."""
    exposed_types = set(_controller_items_by_type())
    assert "six_bar_linkage" not in exposed_types
    assert "planetary_gear" in exposed_types


@pytest.mark.parametrize(
    "mechanism_type,method_name",
    [
        ("4_bar_linkage", "create_4bar_linkage_visuals"),
        ("cam", "create_cam_visuals"),
        ("gear", "create_gear_visuals"),
        ("planetary_gear", "create_planetary_gear_visuals"),
    ],
)
def test_design_render_dispatch_has_factory_method(mechanism_type: str, method_name: str) -> None:
    """Layer creation is insufficient unless the resulting type reaches a renderer."""
    presenter = MechanismDesignPresenter.__new__(MechanismDesignPresenter)
    factory = SimpleNamespace(
        create_4bar_linkage_visuals=MagicMock(return_value=["4bar-item"]),
        create_cam_visuals=MagicMock(return_value=["cam-item"]),
        create_gear_visuals=MagicMock(return_value=["gear-item"]),
        create_planetary_gear_visuals=MagicMock(return_value=["planetary-item"]),
    )
    presenter._tab = SimpleNamespace(visuals_factory=factory)
    presenter._get_character_position = lambda: [0.0, 0.0]

    items = presenter._create_mechanism_visuals(mechanism_type, {"params": {}}, transform_func=None)

    getattr(factory, method_name).assert_called_once()
    assert items


def test_design_render_dispatch_warns_on_unknown_type(caplog: pytest.LogCaptureFixture) -> None:
    """Unknown internal types should be visible in logs, not silently ignored."""
    presenter = MechanismDesignPresenter.__new__(MechanismDesignPresenter)
    factory = SimpleNamespace(
        create_4bar_linkage_visuals=MagicMock(return_value=["4bar-item"]),
        create_cam_visuals=MagicMock(return_value=["cam-item"]),
        create_gear_visuals=MagicMock(return_value=["gear-item"]),
        create_planetary_gear_visuals=MagicMock(return_value=["planetary-item"]),
    )
    presenter._tab = SimpleNamespace(visuals_factory=factory)
    presenter._get_character_position = lambda: [0.0, 0.0]

    with caplog.at_level(logging.WARNING):
        items = presenter._create_mechanism_visuals("unknown_type", {"params": {}}, None)

    assert items == []
    assert "No visual factory registered for mechanism type: unknown_type" in caplog.text
    factory.create_4bar_linkage_visuals.assert_not_called()
    factory.create_cam_visuals.assert_not_called()
    factory.create_gear_visuals.assert_not_called()
    factory.create_planetary_gear_visuals.assert_not_called()
