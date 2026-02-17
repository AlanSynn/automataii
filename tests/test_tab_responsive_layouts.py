import sys
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import yaml
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGraphicsScene,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QWidget,
)

from automataii.presentation.qt.tabs.editor.components.ui_builder import EditorTabUIBuilder
from automataii.presentation.qt.tabs.image_processing_tab import ImageProcessingTab
from automataii.presentation.qt.tabs.mechanism_design.mechanism_design_tab_layout import (
    MechanismDesignTabLayout,
)
from automataii.presentation.qt.tabs.mechanism_foundry.foundry_view import (
    MechanismFoundryView,
)
from automataii.presentation.qt.views.editor_view import EditorView


def _get_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


class _DummyMainWindow:
    def __init__(self, project_dir: Path | None = None, parts: dict | None = None):
        self.skeleton_manager = None
        self.current_temp_char_dir = None
        self.project_data_manager = SimpleNamespace(
            project_dir=project_dir,
            parts=parts or {},
        )
        self.project_state_manager = None
        self.editor_tab = None
        self.mechanism_design_tab = None

    @staticmethod
    def statusBar():
        return None


def test_editor_tab_control_panel_is_resizable() -> None:
    _ = _get_app()

    host = QWidget()
    scene = QGraphicsScene(host)
    editor_view = EditorView(scene, host)

    builder = EditorTabUIBuilder(host, editor_view)
    builder.build()

    splitter = host.findChild(QSplitter)
    assert splitter is not None
    assert splitter.childrenCollapsible()
    assert splitter.isCollapsible(0)

    scroll_area = host.findChild(QScrollArea)
    assert scroll_area is not None
    assert scroll_area.minimumWidth() < scroll_area.maximumWidth()
    assert (
        scroll_area.sizePolicy().horizontalPolicy() != QSizePolicy.Policy.Fixed
    )


def test_mechanism_design_control_panel_is_resizable() -> None:
    _ = _get_app()

    host = QWidget()
    layout_manager = MechanismDesignTabLayout()
    layout_manager.setup_main_layout(host)

    splitter = host.findChild(QSplitter)
    assert splitter is not None
    assert splitter.childrenCollapsible()
    assert splitter.isCollapsible(0)

    scroll_area = host.findChild(QScrollArea)
    assert scroll_area is not None
    assert scroll_area.minimumWidth() < scroll_area.maximumWidth()
    assert (
        scroll_area.sizePolicy().horizontalPolicy() != QSizePolicy.Policy.Fixed
    )


def test_image_processing_uses_splitter_with_scrollable_controls() -> None:
    _ = _get_app()

    tab = ImageProcessingTab(_DummyMainWindow())
    splitter = tab.findChild(QSplitter)
    assert splitter is not None
    assert splitter.orientation() == Qt.Orientation.Horizontal
    assert splitter.childrenCollapsible()
    assert splitter.isCollapsible(0)

    left_widget = splitter.widget(0)
    assert isinstance(left_widget, QScrollArea)
    assert left_widget.minimumWidth() < left_widget.maximumWidth()
    assert left_widget.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded


def test_image_processing_load_image_does_not_auto_assign_character(monkeypatch) -> None:
    _ = _get_app()

    tab = ImageProcessingTab(_DummyMainWindow())
    called = {"assign": 0}

    def _fake_assign_character() -> None:
        called["assign"] += 1

    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *args, **kwargs: ("/tmp/mock.png", "Image Files (*.png)")),
    )
    tab.image_proc_view.load_image = lambda _path: True
    tab._auto_apply_loaded_image_to_editor = lambda: True
    tab._assign_character_from_image = _fake_assign_character
    tab.load_input_image()

    assert called["assign"] == 0
    assert tab.input_image_path == "/tmp/mock.png"


def test_image_processing_assign_character_button_runs_pipeline() -> None:
    _ = _get_app()

    tab = ImageProcessingTab(_DummyMainWindow())
    tab._is_dummy_mechanism_design_session = lambda: True
    tab.input_image_path = "/tmp/mock.png"
    tab.update_button_states()

    assert tab.assign_character_btn is not None
    assert tab.assign_character_btn.isEnabled()

    called = {"process": 0, "create": 0}

    def _fake_process_image() -> None:
        called["process"] += 1
        tab.current_annotation_results = {"char_cfg_path": "/tmp/char_cfg.yaml"}
        tab.current_temp_char_dir = "/tmp/mock"
        tab.skeleton_data = {"skeleton": []}

    def _fake_create_parts(*, show_success_dialog: bool = True) -> bool:
        called["create"] += 1
        return True

    tab.process_image = _fake_process_image
    tab.create_parts_from_skeleton = _fake_create_parts
    tab.assign_character_btn.click()

    assert called["process"] == 1
    assert called["create"] == 1


def test_image_processing_replace_button_enabled_for_dummy_mechanism_session() -> None:
    _ = _get_app()

    tab = ImageProcessingTab(_DummyMainWindow())
    tab._is_dummy_mechanism_design_session = lambda: True
    tab.update_button_states()

    assert tab.assign_character_btn is not None
    assert tab.assign_character_btn.isEnabled()


def test_image_processing_replace_button_disabled_without_dummy_session() -> None:
    _ = _get_app()

    tab = ImageProcessingTab(_DummyMainWindow())
    tab.input_image_path = "/tmp/mock.png"
    tab._is_dummy_mechanism_design_session = lambda: False
    tab.update_button_states()

    assert tab.assign_character_btn is not None
    assert not tab.assign_character_btn.isEnabled()


def test_image_processing_replace_button_loads_image_when_missing() -> None:
    _ = _get_app()

    tab = ImageProcessingTab(_DummyMainWindow())
    tab._is_dummy_mechanism_design_session = lambda: True
    tab.update_button_states()

    called = {"load": 0, "process": 0, "create": 0}

    def _fake_load_input(*, auto_apply: bool = True) -> None:
        called["load"] += 1
        tab.input_image_path = "/tmp/mock.png"

    def _fake_process_image() -> None:
        called["process"] += 1
        tab.current_annotation_results = {"char_cfg_path": "/tmp/char_cfg.yaml"}
        tab.current_temp_char_dir = "/tmp/mock"
        tab.skeleton_data = {"skeleton": []}

    def _fake_create_parts(*, show_success_dialog: bool = True) -> bool:
        called["create"] += 1
        return True

    tab.load_input_image = _fake_load_input
    tab.process_image = _fake_process_image
    tab.create_parts_from_skeleton = _fake_create_parts

    assert tab.assign_character_btn is not None
    tab.assign_character_btn.click()

    assert called["load"] == 1
    # load_input_image(auto_apply=True) handles full pipeline;
    # assign handler should not run process/create again.
    assert called["process"] == 0
    assert called["create"] == 0


def test_image_processing_load_image_auto_applies_pipeline(monkeypatch) -> None:
    _ = _get_app()

    tab = ImageProcessingTab(_DummyMainWindow())
    called = {"auto_apply": 0}

    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *args, **kwargs: ("/tmp/mock.png", "Image Files (*.png)")),
    )
    tab.image_proc_view.load_image = lambda _path: True
    tab._auto_apply_loaded_image_to_editor = lambda: called.__setitem__("auto_apply", called["auto_apply"] + 1) or True

    tab.load_input_image()

    assert called["auto_apply"] == 1
    assert tab.input_image_path == "/tmp/mock.png"


def test_image_processing_processing_steps_hidden_by_default_after_input_ready() -> None:
    _ = _get_app()
    tab = ImageProcessingTab(_DummyMainWindow())

    tab._on_input_ready("/tmp/mock.png", source="file", status_prefix="Loaded input image")

    assert not tab.processing_steps_group.isVisible()


def test_image_processing_external_skeleton_loads_project_preview(tmp_path) -> None:
    _ = _get_app()

    preview_path = tmp_path / "segmentation_vis.png"
    pixmap = QPixmap(32, 24)
    pixmap.fill()
    assert pixmap.save(str(preview_path))

    tab = ImageProcessingTab(_DummyMainWindow(project_dir=tmp_path))
    tab.on_skeleton_updated_externally(
        {"joints": {"root": {"position": [0.0, 0.0], "parent_id": None}}}
    )

    assert tab.image_proc_view.image_item is not None
    assert tab.skeleton_data is not None
    assert tab.input_image_path is None


def test_image_processing_external_preview_prefers_composited_parts_over_segmentation(tmp_path) -> None:
    _ = _get_app()

    segmentation_path = tmp_path / "segmentation_vis.png"
    segmentation = QPixmap(64, 64)
    segmentation.fill()
    assert segmentation.save(str(segmentation_path))

    part_path = tmp_path / "head.png"
    part = QPixmap(12, 10)
    part.fill()
    assert part.save(str(part_path))

    part_info = SimpleNamespace(
        roi=[0.0, 0.0, 12.0, 10.0],
        image_path="head.png",
        z_value=0.0,
    )
    tab = ImageProcessingTab(_DummyMainWindow(project_dir=tmp_path, parts={"head": part_info}))
    tab.on_parts_loaded_in_editor(True)

    assert tab.image_proc_view.image_item is not None
    preview_size = tab.image_proc_view.image_item.pixmap().size()
    assert preview_size.width() == 12
    assert preview_size.height() == 10


def test_foundry_editor_splitter_allows_side_panel_collapse() -> None:
    _ = _get_app()

    view = MechanismFoundryView()
    splitter = view.findChild(QSplitter)
    assert splitter is not None
    assert splitter.childrenCollapsible()
    assert splitter.isCollapsible(0)
    assert splitter.isCollapsible(2)
    assert isinstance(splitter.widget(0), QScrollArea)


def test_refresh_texture_from_input_skips_mismatched_dimensions(tmp_path: Path) -> None:
    _ = _get_app()

    tab = ImageProcessingTab(_DummyMainWindow())
    char_dir = tmp_path / "char"
    char_dir.mkdir()

    texture_path = char_dir / "texture.png"
    mask_path = char_dir / "mask.png"
    image_path = char_dir / "image.png"
    input_path = tmp_path / "input.png"

    original_texture = np.full((40, 32, 4), 17, dtype=np.uint8)
    assert cv2.imwrite(str(texture_path), original_texture)
    assert cv2.imwrite(str(mask_path), np.full((40, 32), 255, dtype=np.uint8))
    assert cv2.imwrite(str(image_path), np.full((40, 32, 3), 99, dtype=np.uint8))
    assert cv2.imwrite(str(input_path), np.full((80, 64, 3), 220, dtype=np.uint8))

    tab.input_image_path = str(input_path)
    replaced = tab._refresh_texture_from_input_if_compatible(char_dir)

    assert replaced is False
    texture_after = cv2.imread(str(texture_path), cv2.IMREAD_UNCHANGED)
    assert texture_after is not None
    assert texture_after.shape[:2] == (40, 32)
    assert int(texture_after[0, 0, 0]) == 17


def test_refresh_texture_from_input_replaces_when_dimensions_match(tmp_path: Path) -> None:
    _ = _get_app()

    tab = ImageProcessingTab(_DummyMainWindow())
    char_dir = tmp_path / "char"
    char_dir.mkdir()

    texture_path = char_dir / "texture.png"
    mask_path = char_dir / "mask.png"
    image_path = char_dir / "image.png"
    input_path = tmp_path / "input.png"

    assert cv2.imwrite(str(texture_path), np.full((40, 32, 4), 17, dtype=np.uint8))
    assert cv2.imwrite(str(mask_path), np.full((40, 32), 255, dtype=np.uint8))
    assert cv2.imwrite(str(image_path), np.full((40, 32, 3), 99, dtype=np.uint8))
    assert cv2.imwrite(str(input_path), np.full((40, 32, 3), 220, dtype=np.uint8))

    tab.input_image_path = str(input_path)
    replaced = tab._refresh_texture_from_input_if_compatible(char_dir)

    assert replaced is True
    texture_after = cv2.imread(str(texture_path), cv2.IMREAD_UNCHANGED)
    image_after = cv2.imread(str(image_path), cv2.IMREAD_UNCHANGED)
    assert texture_after is not None
    assert image_after is not None
    assert int(texture_after[0, 0, 0]) == 220
    assert int(image_after[0, 0, 0]) == 220


def test_load_skeleton_data_stays_local_by_default(tmp_path: Path) -> None:
    _ = _get_app()

    tab = ImageProcessingTab(_DummyMainWindow())
    tab.image_proc_view.load_skeleton = lambda _data: True

    emitted = {"count": 0}
    tab.skeleton_updated.connect(lambda _data: emitted.__setitem__("count", emitted["count"] + 1))

    char_cfg = {
        "skeleton": [
            {"name": "root", "parent": None, "loc": [10, 20]},
            {"name": "torso", "parent": "root", "loc": [10, 40]},
        ]
    }
    cfg_path = tmp_path / "char_cfg.yaml"
    with open(cfg_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(char_cfg, f)

    assert tab.load_skeleton_data_from_config(str(cfg_path)) is True
    assert emitted["count"] == 0


def test_load_skeleton_data_can_emit_when_requested(tmp_path: Path) -> None:
    _ = _get_app()

    tab = ImageProcessingTab(_DummyMainWindow())
    tab.image_proc_view.load_skeleton = lambda _data: True

    emitted = {"count": 0}
    tab.skeleton_updated.connect(lambda _data: emitted.__setitem__("count", emitted["count"] + 1))

    char_cfg = {"skeleton": [{"name": "root", "parent": None, "loc": [1, 2]}]}
    cfg_path = tmp_path / "char_cfg.yaml"
    with open(cfg_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(char_cfg, f)

    assert tab.load_skeleton_data_from_config(str(cfg_path), emit_signal=True) is True
    assert emitted["count"] == 1
