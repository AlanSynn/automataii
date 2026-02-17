import sys
from pathlib import Path
from types import SimpleNamespace

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
    tab._assign_character_from_image = _fake_assign_character
    tab.load_input_image()

    assert called["assign"] == 0
    assert tab.input_image_path == "/tmp/mock.png"


def test_image_processing_assign_character_button_runs_pipeline() -> None:
    _ = _get_app()

    tab = ImageProcessingTab(_DummyMainWindow())
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

    def _fake_create_parts() -> None:
        called["create"] += 1

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


def test_image_processing_replace_button_loads_image_when_missing() -> None:
    _ = _get_app()

    tab = ImageProcessingTab(_DummyMainWindow())
    tab._is_dummy_mechanism_design_session = lambda: True
    tab.update_button_states()

    called = {"load": 0, "process": 0, "create": 0}

    def _fake_load_input() -> None:
        called["load"] += 1
        tab.input_image_path = "/tmp/mock.png"

    def _fake_process_image() -> None:
        called["process"] += 1
        tab.current_annotation_results = {"char_cfg_path": "/tmp/char_cfg.yaml"}
        tab.current_temp_char_dir = "/tmp/mock"
        tab.skeleton_data = {"skeleton": []}

    def _fake_create_parts() -> None:
        called["create"] += 1

    tab.load_input_image = _fake_load_input
    tab.process_image = _fake_process_image
    tab.create_parts_from_skeleton = _fake_create_parts

    assert tab.assign_character_btn is not None
    tab.assign_character_btn.click()

    assert called["load"] == 1
    assert called["process"] == 1
    assert called["create"] == 1


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
