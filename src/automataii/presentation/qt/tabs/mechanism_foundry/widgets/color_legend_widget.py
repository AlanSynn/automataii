from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTextEdit, QVBoxLayout, QWidget

from automataii.domain.mechanisms.linkages.config import LinkRole
from automataii.presentation.qt.mechanisms.linkage_colors import LINK_COLORS


class ColorLegendWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._display = QTextEdit()
        self._display.setReadOnly(True)
        self._display.setFrameShape(QTextEdit.Shape.NoFrame)
        self._display.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self._display.setMaximumHeight(200)

        html = self._build_html()
        self._display.setHtml(html)

        layout.addWidget(self._display)

    def _build_html(self) -> str:
        roles = [LinkRole.GROUND, LinkRole.DRIVER, LinkRole.COUPLER, LinkRole.FOLLOWER]

        legend_rows = ""
        for role in roles:
            color = LINK_COLORS[role]
            name = role.value.title()
            legend_rows += f"""
            <div class="legend-row">
                <div class="color-swatch" style="background: {color};"></div>
                <span class="legend-label">{name}</span>
            </div>
            """

        style = """
        <style>
        body {
            font-family: 'Helvetica Neue', Arial;
            font-size: 13px;
            line-height: 1.6;
            color: #2c3e50;
            margin: 0;
            padding: 0;
        }
        .card {
            background: #ffffff;
            border: 1px solid #e1e8ed;
            border-radius: 6px;
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 10px 12px;
            font-size: 13px;
            font-weight: 600;
            letter-spacing: 0.5px;
        }
        .content {
            padding: 12px;
        }
        .legend-row {
            display: flex;
            align-items: center;
            margin: 10px 0;
        }
        .color-swatch {
            width: 24px;
            height: 24px;
            border-radius: 4px;
            border: 2px solid #e1e8ed;
            margin-right: 12px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        .legend-label {
            color: #2c3e50;
            font-weight: 500;
            font-size: 13px;
        }
        </style>
        """

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>{style}</head>
        <body>
            <div class="card">
                <div class="header">🎨 LINK COLORS</div>
                <div class="content">
                    {legend_rows}
                </div>
            </div>
        </body>
        </html>
        """
        return html
