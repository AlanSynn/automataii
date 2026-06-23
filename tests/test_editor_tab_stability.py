from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock

from PyQt6.QtCore import QEvent, QPointF, Qt
from PyQt6.QtGui import QMouseEvent, QPainterPath, QPixmap
from PyQt6.QtWidgets import QApplication, QGraphicsScene

from automataii.domain.project.models import PartInfoModel
from automataii.presentation.qt.graphics_items.part_item import CharacterPartItem
from automataii.presentation.qt.models import PartInfo
from automataii.presentation.qt.tabs.editor.components.motion_path_manager import MotionPathManager
from automataii.presentation.qt.tabs.editor.components.skeleton_ik_handler import SkeletonIKHandler
from automataii.presentation.qt.tabs.editor.tab import EditorTab

_APP: QApplication | None = None


def _get_app() -> QApplication:
    global _APP
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    app = cast(QApplication, app)
    _APP = app
    return app


class _NoStatusMainWindow:
    def __init__(self, project_dir: Path, parts: dict | None = None) -> None:
        self.debug_mode = False
        self.project_data_manager = SimpleNamespace(project_dir=project_dir, parts=parts or {})
        self.project_state_manager = None
        self.mechanism_design_tab = None
        self.editor_tab = None

    @staticmethod
    def statusBar() -> None:
        # Real teardown or tests can temporarily leave no status bar object.
        return None


class _DummyEditorView:
    def __init__(self) -> None:
        self.set_joint_map = MagicMock()
        self.visualize_skeleton = MagicMock()


class _PathItem:
    def __init__(self, path: QPainterPath) -> None:
        self._path = path

    def path(self) -> QPainterPath:
        return self._path

    def setPath(self, path: QPainterPath) -> None:
        self._path = path


class _ReachEditorView(_DummyEditorView):
    def __init__(self, path: QPainterPath | None = None) -> None:
        super().__init__()
        self.final_paths_map = {"hand": _PathItem(path or QPainterPath())}
        self.started_vertex_editing: list[tuple[str, QPainterPath, bool]] = []
        self.corrected_overlay: QPainterPath | None = None

    def start_vertex_editing(self, part_name: str, path: QPainterPath, is_closed: bool) -> bool:
        self.started_vertex_editing.append((part_name, path, is_closed))
        return True

    def set_corrected_overlay_path(self, _part_name: str, path: QPainterPath) -> None:
        self.corrected_overlay = path


class _MotionPart:
    def __init__(self) -> None:
        self.motion_path: QPainterPath | None = None

    def set_motion_path(self, path: QPainterPath) -> None:
        self.motion_path = path


def _reach_constrained_manager(view: _ReachEditorView, part: _MotionPart) -> MotionPathManager:
    manager = MotionPathManager(view, QGraphicsScene())  # type: ignore[arg-type]
    project_part = SimpleNamespace(motion_path=None)
    manager.configure_callbacks(
        get_selected_part=lambda: "hand",
        get_editor_items=lambda: {"hand": part},  # type: ignore[return-value]
        get_parts_info=lambda: {},
        get_main_window=lambda: SimpleNamespace(
            project_data_manager=SimpleNamespace(parts={"hand": project_part}),
            ik_manager=SimpleNamespace(
                sim_selectable_components=[{"partName": "hand", "targetJointId": "eff"}],
                sim_limb_configs={
                    "eff": {"parentAnchor": "mid"},
                    "mid": {"parentAnchor": "root"},
                },
                sim_joints_config={
                    "root": {"position": QPointF(0, 0)},
                    "mid": {"position": QPointF(10, 0)},
                    "eff": {"position": QPointF(20, 0)},
                },
                _get_standardized_joint_id=lambda name: name,
            ),
            statusBar=lambda: None,
        ),
        update_button_states=lambda: None,
        has_motion_path=lambda _part: True,
        emit_path_data=lambda: None,
    )
    return manager


def _make_part(tmp_path: Path, name: str = "head") -> PartInfo:
    image_path = tmp_path / f"{name}.png"
    pixmap = QPixmap(20, 20)
    pixmap.fill()
    assert pixmap.save(str(image_path))
    return PartInfo.from_pydantic(
        PartInfoModel(
            name=name,
            roi=[0.0, 0.0, 20.0, 20.0],
            image_path=image_path.name,
            local_pivot_offset=[10.0, 10.0],
        ),
        project_dir=tmp_path,
    )


def _mouse_event(
    event_type: QEvent.Type,
    x: float,
    y: float,
    button: Qt.MouseButton,
    buttons: Qt.MouseButton | Qt.MouseButton = Qt.MouseButton.NoButton,
    modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier,
) -> QMouseEvent:
    if buttons == Qt.MouseButton.NoButton and button != Qt.MouseButton.NoButton:
        buttons = button
    pos = QPointF(x, y)
    return QMouseEvent(event_type, pos, pos, button, buttons, modifiers)


def _loaded_editor_tab(tmp_path: Path) -> EditorTab:
    _ = _get_app()
    part = _make_part(tmp_path)
    main_window = _NoStatusMainWindow(tmp_path, parts={"head": part})
    tab = EditorTab(main_window)
    main_window.editor_tab = tab
    tab.set_parts_data({"head": part})
    tab.parts_list.setCurrentRow(0)
    assert tab.selected_part_name == "head"
    return tab


def test_start_drawing_tolerates_partial_project_data_manager(tmp_path: Path) -> None:
    tab = _loaded_editor_tab(tmp_path)

    # Regression: partial project_data_manager objects used during tests/startup have a
    # parts dict but no get_current_parts_data(). Start Drawing must not crash.
    tab.define_motion_path_btn.setChecked(True)

    assert tab.editor_view.current_mode == "define_motion_path"
    assert tab.define_motion_path_btn.isChecked()


def test_editor_skeleton_handler_deep_copies_rest_pose() -> None:
    _ = _get_app()
    handler = SkeletonIKHandler(_DummyEditorView(), QGraphicsScene())
    skeleton = {
        "joint_map": {"head": "joint-head"},
        "joints": {"joint-head": {"position": [10.0, 20.0]}},
    }

    handler.cache_initial_skeleton(skeleton)
    skeleton["joints"]["joint-head"]["position"][1] = 999.0

    assert handler._initial_skeleton_cache == {  # type: ignore[attr-defined]
        "joint_map": {"head": "joint-head"},
        "joints": {"joint-head": {"position": [10.0, 20.0]}},
    }


def test_freehand_path_completion_tolerates_missing_status_bar_and_records_timing(
    tmp_path: Path,
) -> None:
    tab = _loaded_editor_tab(tmp_path)
    tab.define_motion_path_btn.setChecked(True)
    view = tab.editor_view

    view.mousePressEvent(
        _mouse_event(QEvent.Type.MouseButtonPress, 20, 20, Qt.MouseButton.LeftButton)
    )
    view.mouseMoveEvent(
        _mouse_event(
            QEvent.Type.MouseMove,
            80,
            30,
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
        )
    )
    view.mouseMoveEvent(
        _mouse_event(
            QEvent.Type.MouseMove,
            120,
            90,
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
        )
    )
    view.mouseReleaseEvent(
        _mouse_event(QEvent.Type.MouseButtonRelease, 160, 120, Qt.MouseButton.LeftButton)
    )

    item = tab.current_editor_items["head"]
    assert item.motion_path is not None
    assert isinstance(item.motion_path, QPainterPath)
    assert not item.motion_path.isEmpty()
    assert len(item.timed_path_points) >= 3
    assert item.path_duration >= 0.0
    assert tab.editor_view.current_mode in {"select", "edit_vertices"}
    assert not tab.define_motion_path_btn.isChecked()


def test_completed_paths_do_not_block_parts_and_clear_with_editor_content(
    tmp_path: Path,
) -> None:
    tab = _loaded_editor_tab(tmp_path)
    tab.define_motion_path_btn.setChecked(True)
    view = tab.editor_view

    view.mousePressEvent(
        _mouse_event(QEvent.Type.MouseButtonPress, 20, 20, Qt.MouseButton.LeftButton)
    )
    view.mouseMoveEvent(
        _mouse_event(
            QEvent.Type.MouseMove,
            80,
            30,
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
        )
    )
    view.mouseMoveEvent(
        _mouse_event(
            QEvent.Type.MouseMove,
            120,
            90,
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
        )
    )
    view.mouseReleaseEvent(
        _mouse_event(QEvent.Type.MouseButtonRelease, 160, 120, Qt.MouseButton.LeftButton)
    )

    path_item = view.final_paths_map["head"]
    assert path_item.acceptedMouseButtons() == Qt.MouseButton.NoButton

    clicked_parts: list[str] = []
    view.part_item_clicked.connect(lambda item: clicked_parts.append(item.name()))
    view.set_mode("select")
    part_item = tab.current_editor_items["head"]
    part_center = view.mapFromScene(part_item.sceneBoundingRect().center())
    view.mousePressEvent(
        _mouse_event(
            QEvent.Type.MouseButtonPress,
            part_center.x(),
            part_center.y(),
            Qt.MouseButton.LeftButton,
        )
    )

    assert clicked_parts == ["head"]
    assert part_item.isSelected()

    tab._motion_path_manager.corrected_paths["head"] = QPainterPath(path_item.path())
    tab.clear_editor_content()

    assert view.final_paths_map == {}
    assert tab._motion_path_manager.corrected_paths == {}
    assert path_item.scene() is None


def test_feasibility_snapping_preserves_open_path_intent() -> None:
    _ = _get_app()
    manager = MotionPathManager(_DummyEditorView(), QGraphicsScene())  # type: ignore[arg-type]
    manager._get_main_window = lambda: SimpleNamespace(  # type: ignore[attr-defined]
        ik_manager=SimpleNamespace(
            sim_selectable_components=[{"partName": "hand", "targetJointId": "eff"}],
            sim_limb_configs={
                "eff": {"parentAnchor": "mid"},
                "mid": {"parentAnchor": "root"},
            },
            sim_joints_config={
                "root": {"position": QPointF(0, 0)},
                "mid": {"position": QPointF(10, 0)},
                "eff": {"position": QPointF(20, 0)},
            },
            _get_standardized_joint_id=lambda name: name,
        )
    )
    path = QPainterPath(QPointF(30, 0))
    path.lineTo(QPointF(30, 10))

    corrected = manager._apply_feasibility_snapping("hand", path, is_closed=False)  # type: ignore[attr-defined]

    assert corrected is not None
    assert corrected.currentPosition() != corrected.pointAtPercent(0.0)


def test_freehand_completion_snaps_path_before_mechanism_handoff() -> None:
    _ = _get_app()
    raw_path = QPainterPath(QPointF(140, 0))
    raw_path.lineTo(QPointF(140, 20))
    view = _ReachEditorView(raw_path)
    part = _MotionPart()
    manager = _reach_constrained_manager(view, part)

    manager.handle_freehand_path_completed(
        [QPointF(140, 0), QPointF(140, 20)],
        [],
        0.0,
    )

    assert part.motion_path is not None
    assert part.motion_path.pointAtPercent(0.0).x() <= 21.1
    assert view.final_paths_map["hand"].path().pointAtPercent(0.0).x() <= 21.1
    assert view.started_vertex_editing[-1][1].pointAtPercent(0.0).x() <= 21.1


def test_vertex_edit_finish_snaps_path_before_storage() -> None:
    _ = _get_app()
    raw_path = QPainterPath(QPointF(120, 0))
    raw_path.lineTo(QPointF(120, 10))
    view = _ReachEditorView(raw_path)
    part = _MotionPart()
    manager = _reach_constrained_manager(view, part)
    manager._path_closed_intent["hand"] = False  # type: ignore[attr-defined]

    manager.on_vertex_editing_finished("hand", raw_path)

    assert part.motion_path is not None
    assert part.motion_path.pointAtPercent(0.0).x() <= 21.1
    assert part.motion_path.currentPosition() != part.motion_path.pointAtPercent(0.0)


def test_skeleton_connected_joints_validate_anchor_length_change() -> None:
    _ = _get_app()
    handler = SkeletonIKHandler(_DummyEditorView(), QGraphicsScene())  # type: ignore[arg-type]
    part = SimpleNamespace(anchor_joint_id="mid")
    joints = {
        "root": {"position": [0.0, 0.0]},
        "mid": {"position": [10.0, 0.0], "parent_id": "root", "length": 10.0},
        "eff": {"position": [20.0, 0.0], "parent_id": "mid", "length": 10.0},
    }

    assert handler._get_connected_joints_for_part(part, joints) == [  # type: ignore[arg-type]
        ("root", "mid", 10.0),
        ("mid", "eff", 10.0),
    ]
    assert handler._validate_skeleton_length_preservation(  # type: ignore[arg-type]
        part,
        QPointF(10.0, 0.0),
        joints,
    )
    assert not handler._validate_skeleton_length_preservation(  # type: ignore[arg-type]
        part,
        QPointF(40.0, 0.0),
        joints,
    )


def test_character_parts_are_locked_against_direct_dragging(tmp_path: Path) -> None:
    tab = _loaded_editor_tab(tmp_path)

    item = tab.current_editor_items["head"]

    assert not item.is_user_movable()


def test_part_anchor_positioning_respects_current_rotation(tmp_path: Path) -> None:
    _ = _get_app()
    part = _make_part(tmp_path)
    scene = QGraphicsScene()
    item = CharacterPartItem(part, tmp_path)
    scene.addItem(item)
    target = QPointF(123.0, 45.0)

    item.setRotation(90.0)
    item.set_scene_position_from_anchor(target, bypass_validation=True)

    actual = item.get_anchor_point_scene_pos()
    assert abs(actual.x() - target.x()) < 1e-6
    assert abs(actual.y() - target.y()) < 1e-6


def test_character_part_item_falls_back_to_body_part_anchor(tmp_path: Path) -> None:
    _ = _get_app()
    part = _make_part(tmp_path, name="left_arm_upper")

    item = CharacterPartItem(part, tmp_path)

    assert item.anchor_joint_id == "left_shoulder"


def test_right_click_cancels_motion_path_instead_of_starting_pan(tmp_path: Path) -> None:
    tab = _loaded_editor_tab(tmp_path)
    tab.define_motion_path_btn.setChecked(True)
    view = tab.editor_view

    view.mousePressEvent(
        _mouse_event(QEvent.Type.MouseButtonPress, 30, 30, Qt.MouseButton.RightButton)
    )

    assert view.current_mode == "select"
    assert not view._panning
    assert not tab.define_motion_path_btn.isChecked()


def test_malformed_joint_definition_tolerates_missing_status_bar(tmp_path: Path) -> None:
    tab = _loaded_editor_tab(tmp_path)

    # Regression: malformed/legacy joint payloads should not raise inside a Qt slot.
    tab.handle_joint_defined({"unexpected": "payload"})

    assert tab.joints[-1] == {"unexpected": "payload"}


def test_motion_path_update_helpers_tolerate_partial_project_data_manager(
    tmp_path: Path,
) -> None:
    tab = _loaded_editor_tab(tmp_path)
    path = QPainterPath()
    path.moveTo(0, 0)
    path.lineTo(10, 10)
    path.lineTo(20, 0)

    # Regression: smoothing/vertex-edit paths use private update helpers that may
    # run while the parent project data object only has a parts dict.
    tab._update_part_path("head", path)
    tab._motion_path_manager._update_part_path("head", path)

    assert tab.main_window.project_data_manager.parts["head"].motion_path is path
