import pytest
from PyQt6.QtCore import QPointF
from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    import sys
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


def test_view_instantiation(qapp):
    from automataii.presentation.qt.tabs.mechanism_foundry.foundry_view import MechanismFoundryView

    view = MechanismFoundryView()

    assert view.current_mechanism is not None
    assert view.mechanism_selector is not None
    assert view.mechanism_selector.count() > 0


def test_view_initial_four_bar_loaded(qapp):
    from automataii.presentation.qt.tabs.mechanism_foundry.foundry_view import MechanismFoundryView

    view = MechanismFoundryView()
    idx = view.mechanism_selector.findData("four_bar")
    assert idx >= 0
    view.mechanism_selector.setCurrentIndex(idx)
    view._on_mechanism_changed(idx)

    assert view.current_mechanism.mechanism_type == "fourbar"
    assert len(view.parameter_sliders) == 4
    assert "ground_link" in view.current_parameters
    assert "input_link" in view.current_parameters


def test_view_mechanism_switching(qapp):
    from automataii.presentation.qt.tabs.mechanism_foundry.foundry_view import MechanismFoundryView

    view = MechanismFoundryView()
    idx = view.mechanism_selector.findData("cam_follower")
    assert idx >= 0

    view.mechanism_selector.setCurrentIndex(idx)
    view._on_mechanism_changed(idx)

    assert view.current_mechanism.mechanism_type == "cam_follower"
    assert "cam_radius" in view.current_parameters


def test_view_animation_tick(qapp):
    from automataii.presentation.qt.tabs.mechanism_foundry.foundry_view import MechanismFoundryView

    view = MechanismFoundryView()
    initial_angle = view.current_angle

    view._on_animation_tick()

    assert view.current_angle == (initial_angle + 4.0) % 360.0


def test_view_rendering_creates_scene_items(qapp):
    """
    Test that rendering creates scene items.

    Note: The mechanism renderer uses callbacks to get state. During initialization,
    the scene may contain grid/background items but mechanism items are created
    on-demand during animation ticks or explicit rendering calls.
    """
    from automataii.presentation.qt.tabs.mechanism_foundry.foundry_view import MechanismFoundryView

    view = MechanismFoundryView()

    # Trigger an animation tick to force rendering
    view._on_animation_tick()

    # After an animation tick, there should be items in the scene
    # (could be grid items, mechanism items, or other visual elements)
    assert len(view.scene.items()) > 0


def test_hover_hit_test_reuses_cached_state(qapp, monkeypatch):
    from automataii.presentation.qt.tabs.mechanism_foundry.foundry_view import MechanismFoundryView

    view = MechanismFoundryView()
    idx = view.mechanism_selector.findData("four_bar")
    assert idx >= 0
    view.mechanism_selector.setCurrentIndex(idx)
    view._on_mechanism_changed(idx)
    assert view.current_mechanism is not None

    original_compute = view.current_mechanism.compute_state
    state = original_compute(view.current_parameters, view.current_angle)
    view._last_rendered_state = state
    view._last_rendered_mechanism = view.current_mechanism
    view._state_cache_valid = True

    call_count = {"count": 0}

    def wrapped_compute(params, angle):
        call_count["count"] += 1
        return original_compute(params, angle)

    monkeypatch.setattr(view.current_mechanism, "compute_state", wrapped_compute)
    point = state.positions.get("A")
    assert point is not None

    view_pos = view.graphics_view.mapFromScene(QPointF(point[0], point[1]))
    hovered = view._get_hovered_point_name(view_pos)

    assert hovered in {"A", "B"}
    assert call_count["count"] == 0


def test_gallery_selection_syncs_selector_and_export_type(qapp):
    from automataii.presentation.qt.tabs.mechanism_foundry.foundry_view import MechanismFoundryView

    view = MechanismFoundryView()
    captured: list[tuple[str, dict]] = []
    view.export_to_design_requested.connect(
        lambda _mid, mtype, params, _pivot: captured.append((mtype, params))
    )

    view._on_gallery_mechanism_selected("slider_crank")
    assert view.mechanism_selector.currentData() == "slider_crank"

    view._on_export_to_design()
    assert captured
    assert captured[0][0] == "slider_crank"
    assert captured[0][1]["grid_system_enabled"] is True
    assert captured[0][1]["grid_cell_cm"] == 2.5


def test_length_parameter_snaps_to_2_5cm_grid_when_enabled(qapp):
    from automataii.presentation.qt.tabs.mechanism_foundry.foundry_view import MechanismFoundryView

    view = MechanismFoundryView()
    idx = view.mechanism_selector.findData("four_bar")
    assert idx >= 0
    view.mechanism_selector.setCurrentIndex(idx)
    view._on_mechanism_changed(idx)

    _, label = view.parameter_sliders["input_link"]

    view.set_grid_system(True, 2.5)
    view._on_parameter_changed("input_link", 41.0, label, False)
    assert view.current_parameters["input_link"] == 50.0

    view.set_grid_system(False, 2.5)
    view._on_parameter_changed("input_link", 41.0, label, False)
    assert view.current_parameters["input_link"] == 41.0


def test_motion_modes_label_populates_for_four_bar(qapp):
    from automataii.presentation.qt.tabs.mechanism_foundry.foundry_view import MechanismFoundryView

    view = MechanismFoundryView()
    assert view.motion_modes_label is not None
    text = view.motion_modes_label.text()

    assert "Motions:" in text
    assert "Circular" in text
    assert "Oscillatory" in text


def test_map_design_params_to_foundry_gear_prefers_live_radii(qapp):
    from automataii.presentation.qt.tabs.mechanism_foundry.foundry_view import MechanismFoundryView

    view = MechanismFoundryView()
    mapped = view._map_design_params_to_foundry(
        "gear_train",
        {
            "gear1_teeth": 12.0,
            "gear2_teeth": 18.0,
            "gear1_radius": 45.0,
            "gear2_radius": 75.0,
        },
    )

    assert mapped["gear1_teeth"] == 15.0
    assert mapped["gear2_teeth"] == 25.0


def test_map_design_params_to_foundry_slider_crank_from_4bar_values(qapp):
    from automataii.presentation.qt.tabs.mechanism_foundry.foundry_view import MechanismFoundryView

    view = MechanismFoundryView()
    mapped = view._map_design_params_to_foundry(
        "slider_crank",
        {
            "l2": 90.0,
            "l3": 145.0,
            "crank_angle": 33.0,
        },
    )

    assert mapped["crank_length"] == 90.0
    assert mapped["rod_length"] == 145.0
    assert mapped["input_angle"] == 33.0


def test_map_design_params_to_foundry_fourbar_supports_uppercase_aliases(qapp):
    from automataii.presentation.qt.tabs.mechanism_foundry.foundry_view import MechanismFoundryView

    view = MechanismFoundryView()
    mapped = view._map_design_params_to_foundry(
        "4_bar_linkage",
        {
            "L1": 150.0,
            "L2": 41.0,
            "L3": 122.0,
            "L4": 133.0,
            "crank_angle": 27.0,
        },
    )

    assert mapped["ground_link"] == 150.0
    assert mapped["input_link"] == 41.0
    assert mapped["coupler_link"] == 122.0
    assert mapped["output_link"] == 133.0
    assert mapped["input_angle"] == 27.0
