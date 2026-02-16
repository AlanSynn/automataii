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
