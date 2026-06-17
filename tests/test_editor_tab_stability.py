from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import cast

from PyQt6.QtCore import QEvent, QPointF, Qt
from PyQt6.QtGui import QMouseEvent, QPainterPath, QPixmap
from PyQt6.QtWidgets import QApplication

from automataii.domain.project.models import PartInfoModel
from automataii.presentation.qt.models import PartInfo
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
