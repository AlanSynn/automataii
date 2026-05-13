from __future__ import annotations

import math
import sys

import pytest
from PyQt6.QtWidgets import QApplication

from automataii.application.mechanism_foundry import ParameterSpec
from automataii.presentation.qt.tabs.mechanism_foundry.parameter_panel import (
    MAX_SLIDER_STEPS,
    MechanismParameterPanel,
    UnitSystem,
)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


def test_parameter_panel_sanitizes_bad_dimension_spec_and_value(qapp) -> None:
    panel = MechanismParameterPanel()
    spec = ParameterSpec("bad", "Bad", math.inf, math.nan, math.nan, "float", "mm", step=1e-12)

    panel.set_parameter_specs("four_bar", [spec], {"bad": math.inf})

    control = panel._dimension_controls["bad"]
    assert control.min_unit == 0.0
    assert control.max_unit == 1.0
    assert control.step_unit > 0.0
    assert control.slider.maximum() <= MAX_SLIDER_STEPS
    assert math.isfinite(control.value_mm)


def test_dimension_control_reversed_range_zero_step_and_bad_events(qapp) -> None:
    panel = MechanismParameterPanel()
    spec = ParameterSpec("rev", "Reversed", 100.0, 0.0, 50.0, "float", "ratio", step=0.0)
    seen: list[tuple[str, float]] = []
    panel.parameter_changed.connect(lambda key, value: seen.append((key, value)))

    panel.set_parameter_specs("gear_train", [spec], {"rev": math.nan})
    control = panel._dimension_controls["rev"]

    assert control.min_unit == 0.0
    assert control.max_unit == 100.0
    assert control.step_unit > 0.0
    control.handle_spinbox_change(math.nan)
    control.handle_slider_change(math.nan)  # type: ignore[arg-type]
    control.handle_slider_change(999_999)

    assert seen[-1][0] == "rev"
    assert 0.0 <= seen[-1][1] <= 100.0


def test_parameter_panel_unit_switch_caps_slider_steps_and_filters_options(qapp) -> None:
    panel = MechanismParameterPanel()
    spec = ParameterSpec("long", "Long", 0.0, 1_000_000.0, 10.0, "float", "mm", step=1e-9)

    panel.set_parameter_specs("four_bar", [spec], {"long": 500_000.0})
    panel._set_unit(UnitSystem.INCH)
    control = panel._dimension_controls["long"]

    assert control.slider.maximum() == MAX_SLIDER_STEPS
    assert control.step_unit > 0.0

    panel.set_driver_options(["", " Driver A ", 3])
    assert sorted(panel._driver_buttons) == [0, 1]
    assert panel._driver_buttons[0].text() == "Driver A"
    assert panel._driver_buttons[1].text() == "3"


def test_parameter_panel_escapes_hints_and_filters_combo_options(qapp) -> None:
    panel = MechanismParameterPanel()

    panel.set_coupler_options(["", "joint_a", 4], current="joint_a")
    panel.set_follower_positions([None, " follower "], current="follower")  # type: ignore[list-item]
    panel.set_hints(["<b>unsafe</b>"])

    assert panel._coupler_combo.count() == 2
    assert panel._coupler_combo.itemText(0) == "joint_a"
    assert panel._follower_combo.count() == 1
    assert "&lt;b&gt;unsafe&lt;/b&gt;" in panel._hints_browser.toHtml()
