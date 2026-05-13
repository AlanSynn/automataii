from __future__ import annotations

from automataii.application.editor import EditorViewStateStore


def test_state_store_notifies_listeners():
    store = EditorViewStateStore()
    seen = []
    store.add_listener(lambda state: seen.append(state.mode))
    store.set_mode("draw")
    assert seen == ["draw"]


def test_start_and_finish_path():
    store = EditorViewStateStore()
    store.start_path([(0, 0)])
    assert store.state.drawing_path is True
    assert store.state.path_points == ((0.0, 0.0),)
    store.append_path_point((1, 1))
    assert store.state.path_points[-1] == (1.0, 1.0)
    store.finish_path(True)
    assert store.state.drawing_path is False
    assert store.state.path_closed is True


def test_cancel_path_resets_points():
    store = EditorViewStateStore()
    store.start_path([(0, 0), (1, 1)])
    store.cancel_path()
    assert store.state.drawing_path is False
    assert store.state.path_points == ()


def test_update_paths_converts_points():
    store = EditorViewStateStore()
    store.update_paths({"hand": [(0, 0), (1, 2)]}, {"hand": [(0, 0), (1, 2)]})
    assert store.state.raw_paths["hand"][1] == (1.0, 2.0)


def test_animation_state_update():
    store = EditorViewStateStore()
    store.set_animation(True, time=0.5)
    assert store.state.animation_running is True
    assert store.state.animation_time == 0.5


def test_editor_state_filters_nonfinite_path_and_view_values():
    import math

    store = EditorViewStateStore()
    store.start_path([(0, 0), (math.nan, 2), (3, math.inf)])
    assert store.state.path_points == ((0.0, 0.0),)

    store.set_zoom(math.nan)
    assert store.state.zoom_level == 1.0
    store.set_pan_offset((math.inf, 4.0))
    assert store.state.pan_offset == (0.0, 0.0)
    store.set_animation(True, time=math.nan)
    assert store.state.animation_time == 0.0

    store.update_paths({"hand": [(0, 0), (math.nan, 1)]}, {"hand": [(math.inf, 2), (3, 4)]})
    assert store.state.raw_paths["hand"] == ((0.0, 0.0),)
    assert store.state.corrected_paths["hand"] == ((3.0, 4.0),)


def test_append_path_point_rejects_nonfinite_point():
    import math

    store = EditorViewStateStore()
    store.start_path([(0, 0)])

    import pytest

    with pytest.raises(ValueError):
        store.append_path_point((math.nan, 1.0))
