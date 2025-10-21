from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QScrollArea, QTextEdit, QVBoxLayout, QWidget

from automataii.application.mechanism_foundry import MechanismContent


class EducationalInfoPanel(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._content: MechanismContent | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._text_display = QTextEdit()
        self._text_display.setReadOnly(True)
        self._text_display.setFrameShape(QTextEdit.Shape.NoFrame)

        scroll = QScrollArea()
        scroll.setWidget(self._text_display)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        layout.addWidget(scroll)

    def set_content(self, content: MechanismContent) -> None:
        self._content = content
        self._render_content()

    def clear(self) -> None:
        self._content = None
        self._text_display.clear()

    def _render_content(self) -> None:
        if self._content is None:
            self._text_display.clear()
            return

        html = self._build_html()
        self._text_display.setHtml(html)

    def _build_html(self) -> str:
        if self._content is None:
            return ""

        c = self._content

        style = """
        <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            font-size: 13px;
            line-height: 1.6;
            color: #2c3e50;
            padding: 16px;
            margin: 0;
        }
        h1 {
            font-size: 20px;
            font-weight: 600;
            color: #1a202c;
            margin: 0 0 12px 0;
            padding-bottom: 8px;
            border-bottom: 2px solid #3498db;
        }
        h2 {
            font-size: 14px;
            font-weight: 600;
            color: #34495e;
            margin: 16px 0 8px 0;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .goal {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 12px;
            border-radius: 6px;
            margin-bottom: 16px;
            font-size: 13px;
            line-height: 1.7;
        }
        .section {
            margin-bottom: 16px;
        }
        ul {
            margin: 4px 0;
            padding-left: 20px;
        }
        li {
            margin: 6px 0;
            line-height: 1.5;
        }
        .advantages li::marker {
            content: "✓ ";
            color: #27ae60;
            font-weight: bold;
        }
        .disadvantages li::marker {
            content: "⚠ ";
            color: #e67e22;
            font-weight: bold;
        }
        .parts li::marker {
            content: "⚙ ";
            color: #3498db;
        }
        .materials li::marker {
            content: "■ ";
            color: #95a5a6;
        }
        .cautions {
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 12px;
            border-radius: 4px;
            margin-top: 8px;
        }
        .cautions h2 {
            margin-top: 0;
            color: #856404;
        }
        .cautions ul {
            margin-bottom: 0;
        }
        .cautions li {
            color: #856404;
        }
        .cautions li::marker {
            content: "⚠️ ";
        }
        </style>
        """

        parts_html = ""
        if c.parts:
            parts_html = f"""
            <div class="section parts">
                <h2>Components</h2>
                <ul>
                    {"".join(f"<li>{part}</li>" for part in c.parts)}
                </ul>
            </div>
            """

        advantages_html = ""
        if c.advantages:
            advantages_html = f"""
            <div class="section advantages">
                <h2>Advantages</h2>
                <ul>
                    {"".join(f"<li>{adv}</li>" for adv in c.advantages)}
                </ul>
            </div>
            """

        disadvantages_html = ""
        if c.disadvantages:
            disadvantages_html = f"""
            <div class="section disadvantages">
                <h2>Limitations</h2>
                <ul>
                    {"".join(f"<li>{dis}</li>" for dis in c.disadvantages)}
                </ul>
            </div>
            """

        materials_html = ""
        if c.materials:
            materials_html = f"""
            <div class="section materials">
                <h2>Materials</h2>
                <ul>
                    {"".join(f"<li>{mat}</li>" for mat in c.materials)}
                </ul>
            </div>
            """

        cautions_html = ""
        if c.cautions:
            cautions_html = f"""
            <div class="cautions">
                <h2>⚠️ Important Considerations</h2>
                <ul>
                    {"".join(f"<li>{cau}</li>" for cau in c.cautions)}
                </ul>
            </div>
            """

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            {style}
        </head>
        <body>
            <h1>{c.title}</h1>
            <div class="goal">{c.goal}</div>
            {parts_html}
            {advantages_html}
            {disadvantages_html}
            {materials_html}
            {cautions_html}
        </body>
        </html>
        """

        return html
