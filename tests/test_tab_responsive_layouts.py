import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
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
    skeleton_manager = None

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


def test_foundry_editor_splitter_allows_side_panel_collapse() -> None:
    _ = _get_app()

    view = MechanismFoundryView()
    splitter = view.findChild(QSplitter)
    assert splitter is not None
    assert splitter.childrenCollapsible()
    assert splitter.isCollapsible(0)
    assert splitter.isCollapsible(2)
    assert isinstance(splitter.widget(0), QScrollArea)
