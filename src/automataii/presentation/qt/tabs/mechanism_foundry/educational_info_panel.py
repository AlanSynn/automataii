from html import escape

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
            font-family: 'Helvetica Neue', Arial;
            font-size: 13px;
            line-height: 1.55;
            color: #243447;
            padding: 14px 14px 18px 14px;
            margin: 0;
            background: #f7fafc;
        }
        h1 {
            font-size: 24px;
            font-weight: 800;
            color: #172b4d;
            margin: 0 0 12px 0;
            letter-spacing: -0.3px;
        }
        .section {
            margin: 0 0 12px 0;
            background: #ffffff;
            border: 1px solid #e5eaf1;
            border-radius: 12px;
            padding: 12px 12px 10px 12px;
        }
        .section-title {
            font-size: 12px;
            font-weight: 700;
            color: #49607a;
            letter-spacing: 0.45px;
            text-transform: uppercase;
            margin-bottom: 8px;
        }
        .goal-card {
            background: linear-gradient(140deg, #2f80ed 0%, #4f46e5 100%);
            color: #ffffff;
            padding: 12px;
            border-radius: 10px;
            font-size: 13px;
            line-height: 1.6;
            margin-bottom: 12px;
        }
        .chip-row {
            display: block;
            margin-bottom: 4px;
        }
        .chip {
            display: inline-block;
            margin: 0 6px 6px 0;
            padding: 3px 10px;
            border-radius: 999px;
            border: 1px solid #c9d8f7;
            background: #eef4ff;
            color: #2a4f9b;
            font-size: 12px;
            font-weight: 600;
        }
        ul {
            margin: 6px 0 4px 0;
            padding-left: 18px;
        }
        li {
            margin: 6px 0;
        }
        .components li::marker {
            color: #2f80ed;
        }
        .features li::marker {
            color: #16a34a;
        }
        .tradeoffs li::marker {
            color: #d97706;
        }
        .materials li::marker {
            color: #64748b;
        }
        .warning-card {
            background: #fff7e6;
            border: 1px solid #f4d08d;
            border-left: 4px solid #e8a627;
            padding: 12px;
            border-radius: 10px;
            margin-top: 10px;
        }
        .warning-title {
            font-size: 12px;
            font-weight: 800;
            letter-spacing: 0.4px;
            text-transform: uppercase;
            margin-bottom: 6px;
            margin-top: 0;
            color: #8a5a00;
        }
        .warning-card ul {
            margin-bottom: 0;
            color: #7a5100;
        }
        </style>
        """

        motions = self._render_motion_chips(c.motions)
        components = self._render_section("Components", c.parts, "components")
        features = self._render_section("Feature Highlights", c.advantages, "features")
        tradeoffs = self._render_section("Design Trade-offs", c.disadvantages, "tradeoffs")
        materials = self._render_section("Build & Materials", c.materials, "materials")
        cautions = self._render_warning(c.cautions)

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            {style}
        </head>
        <body>
            <h1>{escape(c.title)}</h1>
            <div class="goal-card">{escape(c.goal)}</div>
            {motions}
            {components}
            {features}
            {tradeoffs}
            {materials}
            {cautions}
        </body>
        </html>
        """

        return html

    @staticmethod
    def _render_motion_chips(motions: tuple[str, ...]) -> str:
        if not motions:
            return ""
        chips = "".join(f'<span class="chip">{escape(str(m))}</span>' for m in motions)
        return f"""
        <div class="section">
            <div class="section-title">Motions</div>
            <div class="chip-row">{chips}</div>
        </div>
        """

    @staticmethod
    def _render_section(title: str, items: tuple[str, ...], class_name: str) -> str:
        if not items:
            return ""
        rendered_items = "".join(f"<li>{escape(str(item))}</li>" for item in items)
        return f"""
        <div class="section {class_name}">
            <div class="section-title">{escape(title)}</div>
            <ul>{rendered_items}</ul>
        </div>
        """

    @staticmethod
    def _render_warning(items: tuple[str, ...]) -> str:
        if not items:
            return ""
        rendered_items = "".join(f"<li>{escape(str(item))}</li>" for item in items)
        return f"""
        <div class="warning-card">
            <div class="warning-title">Important Considerations</div>
            <ul>{rendered_items}</ul>
        </div>
        """
