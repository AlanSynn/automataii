from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTextEdit, QVBoxLayout, QWidget

from automataii.mechanisms.linkage.config import LinkageConfig, LinkageType


class MechanismInfoWidget(QWidget):
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
        self._display.setMaximumHeight(150)

        layout.addWidget(self._display)
        self.clear()

    def update_config(self, config: LinkageConfig) -> None:
        type_name = self._get_type_name(config.type)
        link_count = len(config.link_lengths)
        driver_role = config.get_link_role(config.driver_index)
        driver_text = f"Link {config.driver_index} ({driver_role.value.title()})"

        html = self._build_html(type_name, link_count, driver_text)
        self._display.setHtml(html)

    def clear(self) -> None:
        html = self._build_html("--", "--", "--")
        self._display.setHtml(html)

    def _get_type_name(self, linkage_type: LinkageType) -> str:
        if linkage_type == LinkageType.FOUR_BAR:
            return "Four-Bar"
        return linkage_type.name.replace("_", "-").title()

    def _build_html(self, type_name: str, link_count: int | str, driver_text: str) -> str:
        style = """
        <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
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
        .info-row {
            display: flex;
            margin: 8px 0;
            line-height: 1.5;
        }
        .info-label {
            color: #7f8c8d;
            font-weight: 500;
            min-width: 60px;
        }
        .info-value {
            color: #2c3e50;
            font-weight: 600;
        }
        .icon {
            margin-right: 6px;
        }
        </style>
        """

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>{style}</head>
        <body>
            <div class="card">
                <div class="header">⚙️ MECHANISM INFO</div>
                <div class="content">
                    <div class="info-row">
                        <span class="info-label">Type:</span>
                        <span class="info-value">{type_name}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Links:</span>
                        <span class="info-value">{link_count}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Driver:</span>
                        <span class="info-value">↻ {driver_text}</span>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        return html
