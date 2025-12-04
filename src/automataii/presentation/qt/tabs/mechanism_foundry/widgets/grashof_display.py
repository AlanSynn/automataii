from dataclasses import dataclass
from enum import Enum

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTextEdit, QVBoxLayout, QWidget

from automataii.domain.mechanisms.linkages.config import LinkageConfig, LinkageType


class GrashofClassification(Enum):
    CRANK_ROCKER = "Crank-Rocker"
    DOUBLE_CRANK = "Double-Crank"
    DOUBLE_ROCKER = "Double-Rocker"
    NON_GRASHOF = "Non-Grashof"
    UNSUPPORTED = "Unsupported"


@dataclass(frozen=True)
class GrashofAnalysis:
    ratio: float
    passes: bool
    classification: GrashofClassification

    @classmethod
    def from_config(cls, config: LinkageConfig) -> "GrashofAnalysis":
        if config.type != LinkageType.FOUR_BAR:
            return cls(
                ratio=float("nan"),
                passes=False,
                classification=GrashofClassification.UNSUPPORTED,
            )

        ratio = config.grashof_ratio
        passes = config.validate_grashof()

        if not passes:
            classification = GrashofClassification.NON_GRASHOF
        else:
            sorted_lengths = sorted(config.link_lengths)
            s = sorted_lengths[0]
            ground_idx = 0
            driver_idx = config.driver_index

            shortest_idx = config.link_lengths.index(s)

            if shortest_idx == ground_idx:
                classification = GrashofClassification.DOUBLE_CRANK
            elif shortest_idx == driver_idx:
                classification = GrashofClassification.CRANK_ROCKER
            else:
                classification = GrashofClassification.DOUBLE_ROCKER

        return cls(ratio=ratio, passes=passes, classification=classification)


class GrashofDisplay(QWidget):
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
        self._display.setMaximumHeight(180)

        layout.addWidget(self._display)
        self.clear()

    def update_analysis(self, analysis: GrashofAnalysis) -> None:
        try:
            ratio_value = float(analysis.ratio)
            ratio_str = f"{ratio_value:.3f}"
        except (TypeError, ValueError):
            ratio_value = float("nan")
            ratio_str = "n/a"

        if ratio_value != ratio_value:  # NaN check
            ratio_str = "n/a"

        passes_value = analysis.passes if analysis.passes else False
        classification_value = analysis.classification.value

        if ratio_str == "n/a":
            passes_value = None

        html = self._build_html(
            ratio=ratio_str,
            passes=passes_value,
            classification=classification_value,
        )
        self._display.setHtml(html)

    def clear(self) -> None:
        html = self._build_html(ratio="--", passes=None, classification="--")
        self._display.setHtml(html)

    def _build_html(self, ratio: str, passes: bool | None, classification: str) -> str:
        # Color-code status
        if passes is None:
            status_color = "#95a5a6"
            status_text = "--"
            status_icon = "○"
        elif passes:
            status_color = "#27ae60"
            status_text = "Pass"
            status_icon = "✓"
        else:
            status_color = "#e74c3c"
            status_text = "Fail"
            status_icon = "✗"

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
            min-width: 100px;
        }
        .info-value {
            color: #2c3e50;
            font-weight: 600;
        }
        .status-badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-weight: 600;
            font-size: 12px;
        }
        </style>
        """

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>{style}</head>
        <body>
            <div class="card">
                <div class="header">📐 GRASHOF ANALYSIS</div>
                <div class="content">
                    <div class="info-row">
                        <span class="info-label">Ratio:</span>
                        <span class="info-value">{ratio}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Status:</span>
                        <span class="status-badge" style="background: {status_color}; color: white;">
                            {status_icon} {status_text}
                        </span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Classification:</span>
                        <span class="info-value">{classification}</span>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        return html
