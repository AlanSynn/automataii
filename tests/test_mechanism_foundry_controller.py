from __future__ import annotations

from automataii.application.mechanism_foundry import (
    MechanismFoundryController,
    ParameterSpec,
)


def test_list_mechanisms_returns_items():
    controller = MechanismFoundryController()
    items = list(controller.list_mechanisms())
    assert items, "Expected at least one mechanism entry"
    assert all(item.display_name for item in items)
    assert all(item.mechanism_type for item in items)


def test_select_mechanism_updates_selection():
    controller = MechanismFoundryController()
    item = next(iter(controller.list_mechanisms()))
    entry = controller.select_mechanism(item.category_key, item.mechanism_key)
    assert entry is not None
    assert controller.selected_entry == entry
    config = controller.get_configuration(item.mechanism_type)
    assert config is not None
    assert isinstance(config.parameter_specs[0], ParameterSpec)


def test_configuration_defaults_present():
    controller = MechanismFoundryController()
    item = next(iter(controller.list_mechanisms()))
    config = controller.get_configuration(item.mechanism_type)
    assert config is not None
    defaults = controller.initial_parameters(item.mechanism_type)
    for spec in config.parameter_specs:
        assert spec.key in defaults


def test_physical_kit_mechanisms_visible_and_deferred_mechanisms_hidden():
    controller = MechanismFoundryController()
    mechanism_types = {item.mechanism_type for item in controller.list_mechanisms()}
    assert mechanism_types == {"four_bar", "cam_follower", "gear_train"}
    assert "slider_crank" not in mechanism_types
