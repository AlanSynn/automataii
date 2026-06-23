import sys
from types import SimpleNamespace

from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QColor, QPixmap
from PyQt6.QtWidgets import QApplication, QGraphicsScene

from automataii.presentation.qt.graphics_items.skeleton_item import SkeletonGraphicsItem
from automataii.presentation.qt.image_view import ImageProcessingView
from automataii.presentation.qt.tabs.image_processing_tab import ImageProcessingTab


def _get_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_image_processing_view_loads_editable_skeleton_handles(tmp_path) -> None:
    _ = _get_app()
    image_path = tmp_path / "character.png"
    pixmap = QPixmap(100, 100)
    pixmap.fill(QColor("white"))
    assert pixmap.save(str(image_path))

    scene = QGraphicsScene()
    view = ImageProcessingView(scene)
    assert view.load_image(str(image_path))

    assert view.load_skeleton(
        {
            "skeleton": [
                {"name": "neck", "parent": None, "loc": [50, 20]},
                {"name": "left_shoulder", "parent": "neck", "loc": [30, 35]},
            ]
        }
    )

    assert set(view.joints) == {"neck", "left_shoulder"}
    assert len(view.lines) == 1

    view.set_edit_mode(True)
    view.joints["left_shoulder"].setPos(QPointF(32, 37))

    saved = view.get_skeleton_data()
    assert saved["skeleton"][1]["loc"] == [32, 37]


def test_skeleton_direction_arrows_cover_parent_joints() -> None:
    _ = _get_app()
    item = SkeletonGraphicsItem(
        skeleton_data=[
            {"id": "shoulder", "position": [0, 0], "parent": None},
            {"id": "elbow", "position": [20, 0], "parent": "shoulder"},
            {"id": "wrist", "position": [40, 0], "parent": "elbow"},
        ],
        hierarchy={"shoulder": ["elbow"], "elbow": ["wrist"]},
    )

    assert "shoulder" in item._bend_arrows
    assert "elbow" in item._bend_arrows


def test_character_recognition_manual_editor_is_visible_without_debug_mode() -> None:
    _ = _get_app()
    status_bar = SimpleNamespace(showMessage=lambda *_args, **_kwargs: None)
    main_window = SimpleNamespace(skeleton_manager=None, statusBar=lambda: status_bar)

    tab = ImageProcessingTab(main_window, editing_mode=False)

    assert tab.manual_segmentation_btn.text() == "Edit Parts / Skeleton / Boxes"
    assert tab.manual_segmentation_btn.isEnabled() is False
    assert tab.edit_skeleton_btn.text() == "Edit Skeleton Joints"
    assert tab.save_skeleton_btn.text() == "Save Skeleton"


def test_image_processing_tab_clear_display_forgets_loaded_image(tmp_path) -> None:
    _ = _get_app()
    status_bar = SimpleNamespace(showMessage=lambda *_args, **_kwargs: None)
    main_window = SimpleNamespace(skeleton_manager=None, statusBar=lambda: status_bar)
    image_path = tmp_path / "character.png"
    pixmap = QPixmap(100, 100)
    pixmap.fill(QColor("white"))
    assert pixmap.save(str(image_path))

    tab = ImageProcessingTab(main_window, editing_mode=False)
    assert tab.image_proc_view.load_image(str(image_path))
    tab.input_image_path = str(image_path)
    assert tab._has_loaded_preview_image()

    tab.clear_display_and_data()

    assert tab.input_image_path is None
    assert tab.image_proc_view.image_item is None
    assert not tab._has_loaded_preview_image()
    assert tab.image_proc_scene.items() == []
