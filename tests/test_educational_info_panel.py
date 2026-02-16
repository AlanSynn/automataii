import sys

from PyQt6.QtWidgets import QApplication

from automataii.application.mechanism_foundry.content_loader import ContentLoader
from automataii.presentation.qt.tabs.mechanism_foundry.educational_info_panel import (
    EducationalInfoPanel,
)


def _get_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_panel_renders_motion_and_warning_sections() -> None:
    _ = _get_app()
    panel = EducationalInfoPanel()

    content = ContentLoader().load_content("four_bar")
    panel.set_content(content)
    html = panel._build_html()

    assert "Motions" in html
    assert "Feature Highlights" in html
    assert "Important Considerations" in html
    assert "Circular" in html
