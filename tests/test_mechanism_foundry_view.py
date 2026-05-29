import pytest
from PyQt6.QtCore import QPointF
from PyQt6.QtWidgets import QApplication, QLabel, QToolBar


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


def _foundry_label_text(view, object_name: str) -> str:
    label = view.info_panel.findChild(QLabel, object_name)
    assert label is not None
    return label.text()


def test_foundry_uses_sensemaking_panel_with_legacy_text(qapp):
    from automataii.presentation.qt.tabs.mechanism_foundry.foundry_view import MechanismFoundryView
    from automataii.presentation.qt.tabs.mechanism_foundry.sensemaking_panel import (
        MechanismSensemakingPanel,
    )

    view = MechanismFoundryView()
    idx = view.mechanism_selector.findData("four_bar")
    assert idx >= 0
    view.mechanism_selector.setCurrentIndex(idx)
    view._on_mechanism_changed(idx)

    assert isinstance(view.info_panel, MechanismSensemakingPanel)
    assert view.info_text is not None
    assert "Four" in _foundry_label_text(view, "sensemakingTitleLabel")
    assert "Pick one slider" in _foundry_label_text(view, "changeValueLabel")


def test_foundry_sensemaking_updates_immediately_on_parameter_change(qapp):
    from automataii.presentation.qt.tabs.mechanism_foundry.foundry_view import MechanismFoundryView

    view = MechanismFoundryView()
    idx = view.mechanism_selector.findData("four_bar")
    assert idx >= 0
    view.mechanism_selector.setCurrentIndex(idx)
    view._on_mechanism_changed(idx)
    view.set_grid_system(False, 2.5)

    _, label = view.parameter_sliders["input_link"]
    view._on_parameter_changed("input_link", 65.0, label, False)

    assert "Input Link" in label.text() or label.text() == "65.0"
    assert "Input link:" in _foundry_label_text(view, "changeValueLabel")
    assert "65 mm" in _foundry_label_text(view, "changeValueLabel")
    assert "hole" in _foundry_label_text(view, "buildHintLabel").lower()
    assert view._last_sensemaking_context is not None
    assert view._last_sensemaking_context.change is not None
    assert view._last_sensemaking_context.evidence_pending is True
    assert "updating" in _foundry_label_text(view, "evidenceLabel")

    view._apply_pending_parameter()

    assert view._last_sensemaking_context is not None
    assert view._last_sensemaking_context.evidence_pending is False
    assert "updating" not in _foundry_label_text(view, "evidenceLabel")


def test_foundry_sensemaking_clears_stale_change_on_mechanism_switch(qapp):
    from automataii.presentation.qt.tabs.mechanism_foundry.foundry_view import MechanismFoundryView

    view = MechanismFoundryView()
    four_bar_idx = view.mechanism_selector.findData("four_bar")
    assert four_bar_idx >= 0
    view.mechanism_selector.setCurrentIndex(four_bar_idx)
    view._on_mechanism_changed(four_bar_idx)
    view.set_grid_system(False, 2.5)
    _, label = view.parameter_sliders["input_link"]
    view._on_parameter_changed("input_link", 65.0, label, False)
    assert "Input link:" in _foundry_label_text(view, "changeValueLabel")

    idx = view.mechanism_selector.findData("cam_follower")
    assert idx >= 0
    view.mechanism_selector.setCurrentIndex(idx)
    view._on_mechanism_changed(idx)

    assert "Input link:" not in _foundry_label_text(view, "changeValueLabel")
    assert "Pick one slider" in _foundry_label_text(view, "changeValueLabel")
    assert "cam" in _foundry_label_text(view, "sensemakingChainLabel").lower()


def test_foundry_sensemaking_resets_motion_point_when_selector_hidden(qapp):
    from automataii.presentation.qt.tabs.mechanism_foundry.foundry_view import MechanismFoundryView

    view = MechanismFoundryView()
    four_bar_idx = view.mechanism_selector.findData("four_bar")
    assert four_bar_idx >= 0
    view.mechanism_selector.setCurrentIndex(four_bar_idx)
    view._on_mechanism_changed(four_bar_idx)
    assert "Joint B" in _foundry_label_text(view, "evidenceLabel")

    gear_idx = view.mechanism_selector.findData("gear_train")
    assert gear_idx < 0
    view._load_mechanism("gear_train")

    evidence = _foundry_label_text(view, "evidenceLabel")
    assert "Ratio" in evidence
    assert "Joint B" not in evidence


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


def test_foundry_toolbar_does_not_expose_assign_character_action(qapp):
    from automataii.presentation.qt.tabs.mechanism_foundry.foundry_view import MechanismFoundryView

    view = MechanismFoundryView()
    toolbars = view.findChildren(QToolBar)
    action_texts = [action.text().lower() for toolbar in toolbars for action in toolbar.actions()]
    assert all("assign character" not in text for text in action_texts)


def test_foundry_right_sensemaking_pane_is_collapsed_by_default_and_toggleable(qapp):
    from automataii.presentation.qt.tabs.mechanism_foundry.foundry_view import MechanismFoundryView

    view = MechanismFoundryView()

    assert view.info_panel_container is not None
    assert view.info_panel_action is not None
    assert view.info_panel_collapsed is True
    assert view.info_panel_container.isHidden()
    assert not view.info_panel_action.isChecked()
    assert "Show Sensemaking" in view.info_panel_action.text()

    view._set_info_panel_collapsed(False)

    assert view.info_panel_collapsed is False
    assert not view.info_panel_container.isHidden()
    assert view.info_panel_action.isChecked()
    assert "Hide Sensemaking" in view.info_panel_action.text()

    view._set_info_panel_collapsed(True)

    assert view.info_panel_collapsed is True
    assert view.info_panel_container.isHidden()
    assert not view.info_panel_action.isChecked()


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


def test_forces_toggle_hides_and_restores_force_items(qapp):
    from automataii.presentation.qt.tabs.mechanism_foundry.foundry_view import MechanismFoundryView

    view = MechanismFoundryView()
    idx = view.mechanism_selector.findData("four_bar")
    assert idx >= 0
    view.mechanism_selector.setCurrentIndex(idx)
    view._on_mechanism_changed(idx)
    view._render_mechanism()

    force_keys = [key for key in view.visual_items_cache if key.startswith("force_")]
    assert force_keys

    view.forces_action.setChecked(False)
    view._toggle_forces()
    assert not [key for key in view.visual_items_cache if key.startswith("force_")]

    view.forces_action.setChecked(True)
    view._toggle_forces()
    assert [key for key in view.visual_items_cache if key.startswith("force_")]


def test_path_preview_toggle_off_on_applies_immediately(qapp):
    from automataii.presentation.qt.tabs.mechanism_foundry.foundry_view import MechanismFoundryView

    view = MechanismFoundryView()
    idx = view.mechanism_selector.findData("four_bar")
    assert idx >= 0
    view.mechanism_selector.setCurrentIndex(idx)
    view._on_mechanism_changed(idx)
    view._render_mechanism()

    assert view.path_preview_overlay.enabled is True
    assert view.path_preview_overlay._items

    view.path_preview_action.setChecked(False)
    view._toggle_path_preview()
    assert view.path_preview_overlay.enabled is False
    assert not view.path_preview_overlay._items

    view.path_preview_action.setChecked(True)
    view._toggle_path_preview()
    assert view.path_preview_overlay.enabled is True
    assert view.path_preview_overlay._items


def test_path_preview_refreshes_on_parameter_rerender(qapp):
    from automataii.presentation.qt.tabs.mechanism_foundry.foundry_view import MechanismFoundryView

    view = MechanismFoundryView()
    idx = view.mechanism_selector.findData("four_bar")
    assert idx >= 0
    view.mechanism_selector.setCurrentIndex(idx)
    view._on_mechanism_changed(idx)
    view._render_mechanism()

    assert "A" in view.path_preview_overlay._items
    first_items = list(view.path_preview_overlay._items["A"])

    view.current_parameters["input_link"] += 10.0
    view._state_cache_valid = False
    view._render_mechanism()

    second_items = list(view.path_preview_overlay._items["A"])
    assert second_items != first_items
    assert all(item.scene() is None for item in first_items)


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

    view._on_gallery_mechanism_selected("cam_follower")
    assert view.mechanism_selector.currentData() == "cam_follower"

    view._on_export_to_design()
    assert captured
    assert captured[0][0] == "cam_follower"
    assert captured[0][1]["grid_system_enabled"] is True
    assert captured[0][1]["grid_cell_cm"] == 2.5
    assert "__foundry_snapshot__" in captured[0][1]
    snapshot = captured[0][1]["__foundry_snapshot__"]
    assert isinstance(snapshot, dict)
    assert "positions" in snapshot


def test_foundry_selector_hides_deferred_mechanisms(qapp):
    from automataii.presentation.qt.tabs.mechanism_foundry.foundry_view import MechanismFoundryView

    view = MechanismFoundryView()
    visible_types = {
        view.mechanism_selector.itemData(i) for i in range(view.mechanism_selector.count())
    }

    assert visible_types == {"four_bar", "cam_follower"}
    assert view.mechanism_selector.findData("gear_train") < 0
    assert view.mechanism_selector.findData("planetary_gear") < 0
    assert view.mechanism_selector.findData("slider_crank") < 0


def test_foundry_view_type_aliases_ignore_case_and_whitespace(qapp):
    from automataii.application.mechanism_foundry import canonical_mechanism_type
    from automataii.presentation.qt.tabs.mechanism_foundry.foundry_view import MechanismFoundryView

    view = MechanismFoundryView()

    assert canonical_mechanism_type(" Four_Bar_Linkage ") == "four_bar"
    assert view._to_controller_mechanism_type(" Gear ") == "gear_train"
    assert view._to_controller_mechanism_type(" Four_Bar_Linkage ") == "four_bar"

    mapped = view._map_design_params_to_foundry(
        " Four_Bar_Linkage ",
        {"L1": 150.0, "L2": 45.0, "L3": 120.0, "L4": 130.0},
    )

    assert mapped["ground_link"] == 150.0
    assert mapped["input_link"] == 45.0
    assert mapped["coupler_link"] == 120.0
    assert mapped["output_link"] == 130.0


def test_set_synced_mechanism_normalizes_case_and_whitespace(qapp):
    from automataii.presentation.qt.tabs.mechanism_foundry.foundry_view import MechanismFoundryView

    view = MechanismFoundryView()

    view.set_synced_mechanism("sync_cam", " CAM ")

    assert view.synced_mechanism_id == "sync_cam"
    assert view.current_mechanism is not None
    assert view.current_mechanism.mechanism_type == "cam_follower"

    view.set_synced_mechanism("sync_gear", " Planetary_Gear ")

    assert view.synced_mechanism_id == "sync_gear"
    assert view.current_mechanism is not None
    assert view.current_mechanism.mechanism_type == "gear_train"


def test_fourbar_preview_renders_coupler_triangle_and_point(qapp):
    from automataii.presentation.qt.tabs.mechanism_foundry.foundry_view import MechanismFoundryView

    view = MechanismFoundryView()
    idx = view.mechanism_selector.findData("four_bar")
    assert idx >= 0
    view.mechanism_selector.setCurrentIndex(idx)
    view._on_mechanism_changed(idx)

    view.current_parameters["coupler_point_x"] = 60.0
    view.current_parameters["coupler_point_y"] = 30.0
    view._render_mechanism()

    assert "fourbar_coupler_triangle" in view.visual_items_cache
    assert "fourbar_coupler_point" in view.visual_items_cache


def test_fourbar_export_snapshot_includes_coupler_point(qapp):
    from automataii.presentation.qt.tabs.mechanism_foundry.foundry_view import MechanismFoundryView

    view = MechanismFoundryView()
    idx = view.mechanism_selector.findData("four_bar")
    assert idx >= 0
    view.mechanism_selector.setCurrentIndex(idx)
    view._on_mechanism_changed(idx)

    snapshot = view._capture_export_snapshot()
    assert snapshot is not None
    assert "positions" in snapshot
    assert "coupler_point" in snapshot["positions"]


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


def test_length_parameter_half_grid_stays_on_positive_grid_cell(qapp):
    from automataii.presentation.qt.tabs.mechanism_foundry.foundry_view import MechanismFoundryView

    view = MechanismFoundryView()
    idx = view.mechanism_selector.findData("cam_follower")
    assert idx >= 0
    view.mechanism_selector.setCurrentIndex(idx)
    view._on_mechanism_changed(idx)

    _, label = view.parameter_sliders["cam_offset"]

    view.set_grid_system(True, 2.5)
    view._on_parameter_changed("cam_offset", 12.5, label, False)

    assert view.current_parameters["cam_offset"] == 25.0


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


def test_map_design_params_to_foundry_gear_keeps_radii_when_output_mode_present(qapp):
    from automataii.presentation.qt.tabs.mechanism_foundry.foundry_view import MechanismFoundryView

    view = MechanismFoundryView()
    mapped = view._map_design_params_to_foundry(
        "gear_train",
        {
            "gear1_radius": 45.0,
            "gear2_radius": 75.0,
            "output_point_mode": "contact_point",
        },
    )

    assert mapped["gear1_teeth"] == 15.0
    assert mapped["gear2_teeth"] == 25.0
    assert mapped["output_point_mode"] == "contact_point"


def test_map_design_params_to_foundry_skips_invalid_preferred_values(qapp):
    from automataii.presentation.qt.tabs.mechanism_foundry.foundry_view import MechanismFoundryView

    view = MechanismFoundryView()
    gear = view._map_design_params_to_foundry(
        "gear_train",
        {
            "gear1_radius": "bad-radius",
            "gear1_teeth": 12.0,
            "gear2_radius": 75.0,
        },
    )
    cam = view._map_design_params_to_foundry(
        "cam_follower",
        {
            "base_radius": "bad-radius",
            "eccentricity": 20.0,
            "follower_rod_length": 100.0,
        },
    )

    assert gear["gear1_teeth"] == 12.0
    assert gear["gear2_teeth"] == 25.0
    assert "cam_radius" not in cam
    assert cam["cam_offset"] == 20.0
    assert cam["follower_length"] == 100.0


def test_cam_motion_point_selector_uses_follower_base_and_contact_point(qapp):
    from automataii.presentation.qt.tabs.mechanism_foundry.foundry_view import MechanismFoundryView

    view = MechanismFoundryView()
    idx = view.mechanism_selector.findData("cam_follower")
    assert idx >= 0
    view.mechanism_selector.setCurrentIndex(idx)
    view._on_mechanism_changed(idx)

    assert view.output_point_selector is not None
    options = [
        view.output_point_selector.itemData(i) for i in range(view.output_point_selector.count())
    ]
    assert options == ["follower_base", "contact_point"]
    assert view.current_parameters["output_point_mode"] == "follower_base"


def test_export_payload_includes_selected_output_point_mode(qapp):
    from automataii.presentation.qt.tabs.mechanism_foundry.foundry_view import MechanismFoundryView

    view = MechanismFoundryView()
    idx = view.mechanism_selector.findData("four_bar")
    assert idx >= 0
    view.mechanism_selector.setCurrentIndex(idx)
    view._on_mechanism_changed(idx)

    captured: list[dict[str, object]] = []
    view.export_to_design_requested.connect(
        lambda _mid, _mtype, params, _pivot: captured.append(params)
    )

    assert view.output_point_selector is not None
    mode_index = view.output_point_selector.findData("joint_a")
    assert mode_index >= 0
    view.output_point_selector.setCurrentIndex(mode_index)
    view._on_motion_point_mode_changed(mode_index)
    view._on_export_to_design()

    assert captured
    assert captured[-1]["output_point_mode"] == "joint_a"


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


def test_map_design_params_to_foundry_normalizes_cam_follower_end_mode(qapp):
    from automataii.presentation.qt.tabs.mechanism_foundry.foundry_view import MechanismFoundryView

    view = MechanismFoundryView()
    mapped = view._map_design_params_to_foundry(
        "cam_follower",
        {"output_point_mode": "follower_end"},
    )

    assert mapped["output_point_mode"] == "follower_base"


def test_foundry_preview_mechanisms_sanitize_nonfinite_inputs(qapp):
    import math

    from automataii.presentation.qt.tabs.mechanism_foundry.foundry_view import (
        _GearTrainPreviewMechanism,
        _SliderCrankPreviewMechanism,
    )

    gear_state = _GearTrainPreviewMechanism().compute_state(
        {"gear1_teeth": math.nan, "gear2_teeth": math.inf},
        math.nan,
    )
    slider_state = _SliderCrankPreviewMechanism().compute_state(
        {"crank_length": math.nan, "rod_length": -1.0},
        math.inf,
    )

    all_values = [
        value
        for state in (gear_state, slider_state)
        for position in state.positions.values()
        for value in position
    ]
    assert all(math.isfinite(value) for value in all_values)
    assert gear_state.metadata["r1"] == 36.0
    assert slider_state.metadata["rod_length"] > slider_state.metadata["crank_length"]


def test_foundry_mapping_and_sync_skip_nonfinite_design_values(qapp):
    import math

    from automataii.presentation.qt.tabs.mechanism_foundry.foundry_view import MechanismFoundryView

    view = MechanismFoundryView()
    mapped = view._map_design_params_to_foundry(
        "gear_train",
        {
            "gear1_radius": math.nan,
            "gear1_teeth": 12.0,
            "gear2_radius": math.inf,
            "gear2_teeth": 18.0,
            "input_angle": math.nan,
        },
    )

    assert mapped == {"gear1_teeth": 12.0, "gear2_teeth": 18.0}

    view.set_synced_mechanism("sync_gear", "gear_train")
    previous_angle = view.current_angle
    view.update_from_design_tab("sync_gear", {"input_angle": "bad-angle", "gear1_radius": math.nan})

    assert view.current_angle == previous_angle
    assert math.isfinite(view._grid_step_mm)


def test_foundry_grid_snap_handles_bad_cell_and_value(qapp):
    import math

    from automataii.presentation.qt.tabs.mechanism_foundry.foundry_view import MechanismFoundryView

    view = MechanismFoundryView()
    idx = view.mechanism_selector.findData("four_bar")
    assert idx >= 0
    view.mechanism_selector.setCurrentIndex(idx)
    view._on_mechanism_changed(idx)

    _, label = view.parameter_sliders["input_link"]
    view.set_grid_system(True, "bad-cell")
    view._on_parameter_changed("input_link", math.nan, label, False)

    assert view._grid_cell_cm == 0.1
    assert math.isfinite(view.current_parameters["input_link"])


def test_gallery_thumbnail_uses_plain_text_for_catalog_content(qapp):
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QLabel

    from automataii.presentation.qt.tabs.mechanism_foundry.gallery_thumbnail import (
        GalleryThumbnail,
    )

    thumbnail = GalleryThumbnail(
        "four_bar",
        "<b>Four Bar</b>",
        "<i>Long catalog description</i> " * 40,
        motion_summary="<u>Oscillatory</u> " * 30,
    )
    try:
        assert not thumbnail.animation_timer.isActive()
        thumbnail.show()
        qapp.processEvents()
        assert thumbnail.animation_timer.isActive()
        thumbnail.hide()
        qapp.processEvents()
        assert not thumbnail.animation_timer.isActive()
        labels = thumbnail.findChildren(QLabel)
        assert labels
        assert all(label.textFormat() == Qt.TextFormat.PlainText for label in labels)
        assert thumbnail.display_name == "<b>Four Bar</b>"
        assert len(thumbnail.description) <= 320
        assert len(thumbnail.motion_summary) <= 160
    finally:
        thumbnail.animation_timer.stop()
        thumbnail.close()


def test_foundry_sync_payload_filters_nonfinite_and_preserves_output_mode(qapp):
    import math

    from automataii.presentation.qt.tabs.mechanism_foundry.foundry_view import MechanismFoundryView

    view = MechanismFoundryView()
    view.current_parameters = {
        "good": 12.0,
        "bad_nan": math.nan,
        "bad_inf": math.inf,
        "bool_value": True,
        "text_value": "not-a-number",
        view.OUTPUT_POINT_MODE_KEY: "joint_b",
    }
    view.current_angle = math.inf
    view._grid_cell_cm = math.inf

    payload = view._build_sync_payload_parameters()

    assert payload["good"] == 12.0
    assert payload[view.OUTPUT_POINT_MODE_KEY] == "joint_b"
    assert payload["input_angle"] == 0.0
    assert payload["grid_cell_cm"] == 0.1
    assert "bad_nan" not in payload
    assert "bad_inf" not in payload
    assert "bool_value" not in payload
    assert "text_value" not in payload


def test_export_snapshot_filters_nonfinite_geometry(qapp):
    import math

    from automataii.domain.mechanisms.core.state import (
        MechanismState,
        SafetyLevel,
        SafetyStatus,
    )
    from automataii.presentation.qt.tabs.mechanism_foundry.foundry_view import MechanismFoundryView

    class FakeMechanism:
        mechanism_type = "gear_train"

        def compute_state(self, _params, _angle):
            return MechanismState(
                positions={
                    "ok": (1.0, 2.0),
                    "bad_nan": (math.nan, 1.0),
                    "bad_inf": (1.0, math.inf),
                    "bad_short": (1.0,),
                    "": (3.0, 4.0),
                },
                safety_status=SafetyStatus(SafetyLevel.SAFE, "ok"),
            )

    view = MechanismFoundryView()
    view.current_mechanism = FakeMechanism()
    view.current_parameters = {}
    view.current_angle = math.nan
    view._last_rendered_state = None
    view._last_rendered_mechanism = None
    view._state_cache_valid = False

    snapshot = view._capture_export_snapshot()

    assert snapshot is not None
    assert snapshot["positions"] == {"ok": [1.0, 2.0]}


def test_motion_modes_label_is_plain_text_and_bounded(qapp):
    from PyQt6.QtCore import Qt

    from automataii.application.mechanism_foundry import MechanismContent
    from automataii.presentation.qt.tabs.mechanism_foundry.foundry_view import MechanismFoundryView

    view = MechanismFoundryView()
    content = MechanismContent(
        title="Unsafe rich title",
        goal="",
        parts=(),
        advantages=(),
        disadvantages=(),
        materials=(),
        cautions=(),
        parameter_options={},
        diagram_path=None,
        tags=(),
        motions=("<b>Oscillatory</b>",) * 20,
    )

    view._update_motion_modes(content)

    assert view.motion_modes_label is not None
    assert view.motion_modes_label.textFormat() == Qt.TextFormat.PlainText
    assert "<b>Oscillatory</b>" in view.motion_modes_label.text()
    assert len(view.motion_modes_label.text()) <= 240
