"""Right-side sensemaking panel for Mechanism Foundry."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from automataii.application.mechanism_foundry import (
    FoundrySensemakingEvent,
    MechanismContent,
    SensemakingContext,
    SensemakingService,
)


class MechanismSensemakingPanel(QWidget):
    """Beautiful, compact inspector for novice mechanism-motion reasoning."""

    def __init__(
        self,
        sensemaking_service: SensemakingService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = sensemaking_service or SensemakingService()
        self._content: MechanismContent | None = None
        self._mechanism_type = "unknown"
        self._context: SensemakingContext | None = None
        self._selected_motion_point = "default motion point"

        # Back-compat with tests that historically used FoundryView.info_text.
        self._text_display = QTextEdit(self)
        self._text_display.setObjectName("legacyInfoTextDisplay")
        self._text_display.setVisible(False)

        self.setObjectName("MechanismSensemakingPanel")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.setStyleSheet(self._style_sheet())

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea(self)
        scroll.setObjectName("sensemakingScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(scroll)

        surface = QWidget(scroll)
        surface.setObjectName("sensemakingSurface")
        layout = QVBoxLayout(surface)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        header = self._make_card("sensemakingHeaderCard")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(14, 12, 14, 12)
        header_layout.setSpacing(8)

        top_row = QHBoxLayout()
        self._badge_label = self._make_label(
            "Mechanism Sensemaking",
            "sensemakingBadgeLabel",
            css_class="BadgeLabel",
        )
        self.safetyBadgeLabel = self._make_label("Status: waiting", "safetyBadgeLabel")
        self.safetyBadgeLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_row.addWidget(self._badge_label)
        top_row.addStretch()
        top_row.addWidget(self.safetyBadgeLabel)
        header_layout.addLayout(top_row)

        self.sensemakingTitleLabel = self._make_label(
            "Select a mechanism",
            "sensemakingTitleLabel",
            css_class="TitleLabel",
        )
        header_layout.addWidget(self.sensemakingTitleLabel)

        self.sensemakingGoalLabel = self._make_label(
            "Change one part, predict the motion, then test it in the kit.",
            "sensemakingGoalLabel",
            css_class="GoalLabel",
        )
        header_layout.addWidget(self.sensemakingGoalLabel)

        self.sensemakingChainLabel = self._make_label(
            "part geometry → motion path → character action",
            "sensemakingChainLabel",
            css_class="ChainLabel",
        )
        header_layout.addWidget(self.sensemakingChainLabel)
        layout.addWidget(header)

        insight_card = self._make_card("sensemakingInsightCard")
        insight_layout = QVBoxLayout(insight_card)
        insight_layout.setContentsMargins(14, 12, 14, 12)
        insight_layout.setSpacing(8)
        insight_layout.addWidget(
            self._make_label("1 · You changed", "changeHeaderLabel", css_class="SectionLabel")
        )
        self.changeValueLabel = self._make_label(
            "Pick one slider. Predict first, then compare the trace.",
            "changeValueLabel",
            css_class="ValueLabel",
        )
        insight_layout.addWidget(self.changeValueLabel)
        self.consequenceLabel = self._make_label(
            "The panel will connect that part edit to the visible motion consequence.",
            "consequenceLabel",
        )
        insight_layout.addWidget(self.consequenceLabel)
        layout.addWidget(insight_card)

        principle_card = self._make_card("sensemakingPrincipleCard")
        principle_layout = QVBoxLayout(principle_card)
        principle_layout.setContentsMargins(14, 12, 14, 12)
        principle_layout.setSpacing(8)
        principle_layout.addWidget(
            self._make_label("2 · Watch this", "principleHeaderLabel", css_class="SectionLabel")
        )
        self.principleLabel = self._make_label(
            "Mechanisms turn part geometry into constrained motion.",
            "principleLabel",
        )
        principle_layout.addWidget(self.principleLabel)
        self.evidenceLabel = self._make_label(
            "Evidence: preview paths and selected motion point will appear here.",
            "evidenceLabel",
            css_class="EvidenceLabel",
        )
        principle_layout.addWidget(self.evidenceLabel)
        layout.addWidget(principle_card)

        kit_card = self._make_card("sensemakingKitCard")
        kit_layout = QVBoxLayout(kit_card)
        kit_layout.setContentsMargins(14, 12, 14, 12)
        kit_layout.setSpacing(8)
        kit_layout.addWidget(
            self._make_label("3 · Build + explain", "buildHeaderLabel", css_class="SectionLabel")
        )
        self.buildHintLabel = self._make_label(
            "Build the smallest comparable version before decorating the automaton.",
            "buildHintLabel",
        )
        kit_layout.addWidget(self.buildHintLabel)
        self.promptLabel = self._make_label(
            "Prompt: Which point moved differently after one edit?",
            "promptLabel",
            css_class="PromptLabel",
        )
        kit_layout.addWidget(self.promptLabel)
        layout.addWidget(kit_card)

        layout.addStretch()
        scroll.setWidget(surface)
        self._render_baseline()

    @property
    def legacy_text_display(self) -> QTextEdit:
        """Expose the hidden legacy QTextEdit used by old tests."""
        return self._text_display

    def set_content(
        self,
        content: MechanismContent,
        mechanism_type: str,
        reset_change: bool = False,
    ) -> None:
        """Load mechanism educational content and optionally clear stale edits."""
        self._content = content
        self._mechanism_type = mechanism_type
        if reset_change:
            self._context = None
        self._text_display.setPlainText(self._legacy_text(content))

        context = self._context or self._service.build_context(
            mechanism_type,
            selected_motion_point_label=self._selected_motion_point,
        )
        story = context.story
        title = content.title.strip() or story.title
        goal = content.gallery_summary or story.focus or content.goal
        motions = " / ".join(content.motions[:4]) if content.motions else "preview motion"
        self.sensemakingTitleLabel.setText(title)
        self.sensemakingGoalLabel.setText(goal)
        self.sensemakingChainLabel.setText(f"Cause → motion: {story.chain} · {motions}")
        self._render_context(context)

    def set_context(self, context: SensemakingContext) -> None:
        """Render the application-owned sensemaking context."""
        self._context = context
        self._mechanism_type = context.mechanism_type
        self._selected_motion_point = context.selected_motion_point_label

        title = context.story.title
        goal = context.story.focus
        if self._content is not None and self._content.title.strip():
            title = self._content.title.strip()
            goal = self._content.gallery_summary or context.story.focus

        self.sensemakingTitleLabel.setText(title)
        self.sensemakingGoalLabel.setText(goal)
        self.sensemakingChainLabel.setText(f"Cause → motion: {context.story.chain}")
        self._render_context(context)

    def set_change_event(self, event: FoundrySensemakingEvent) -> None:
        """Show the latest cause-effect edit from the legacy event shape."""
        self.set_context(self._service.context_from_event(event))

    def set_motion_point(self, point_label: str | None) -> None:
        """Reflect the currently tracked path point without inventing a new explanation."""
        clean = str(point_label or "").strip()
        if clean:
            self._selected_motion_point = clean
        if self._context is None:
            context = self._service.build_context(
                self._mechanism_type,
                selected_motion_point_label=self._selected_motion_point,
            )
            self._render_context(context)

    def set_safety_status(self, message: str, level: str) -> None:
        """Mirror mechanism safety in a compact badge."""
        clean_level = str(level or "unknown").strip().lower()
        clean_message = str(message or "Status: unknown").strip()
        self.safetyBadgeLabel.setText(clean_message)
        self.safetyBadgeLabel.setProperty("safetyLevel", clean_level)
        style = self.safetyBadgeLabel.style()
        if style is not None:
            style.unpolish(self.safetyBadgeLabel)
            style.polish(self.safetyBadgeLabel)

    def _render_baseline(self) -> None:
        context = self._service.build_context(
            self._mechanism_type,
            selected_motion_point_label=self._selected_motion_point,
        )
        self._render_context(context)

    def _render_context(self, context: SensemakingContext) -> None:
        self.changeValueLabel.setText(context.change_line)
        self.consequenceLabel.setText(f"Effect: {context.effect_line}")
        self.principleLabel.setText(f"Why: {context.principle_line}")
        self.evidenceLabel.setText(f"{context.watch_line}\nEvidence: {context.evidence_line}")
        self.buildHintLabel.setText(f"Build check: {context.build_check}")
        self.promptLabel.setText(f"Teacher prompt: {context.teacher_prompt}")

    @staticmethod
    def _legacy_text(content: MechanismContent) -> str:
        lines = [content.title, "", content.goal]
        sections = (
            ("Parts", content.parts),
            ("Motions", content.motions),
            ("Advantages", content.advantages),
            ("Limitations", content.disadvantages),
            ("Materials", content.materials),
            ("Build cautions", content.cautions),
        )
        for heading, items in sections:
            if items:
                lines.extend(["", f"{heading}:", *[f"- {item}" for item in items]])
        return "\n".join(lines).strip()

    @staticmethod
    def _make_card(object_name: str) -> QFrame:
        card = QFrame()
        card.setObjectName(object_name)
        card.setFrameShape(QFrame.Shape.NoFrame)
        return card

    @staticmethod
    def _make_label(text: str, object_name: str, css_class: str | None = None) -> QLabel:
        label = QLabel(text)
        label.setObjectName(object_name)
        label.setWordWrap(True)
        label.setTextFormat(Qt.TextFormat.PlainText)
        if css_class:
            label.setProperty("cssClass", css_class)
        return label

    @staticmethod
    def _style_sheet() -> str:
        return """
        #MechanismSensemakingPanel {
            background: #f7f3ea;
            color: #1f2937;
        }
        #sensemakingScrollArea {
            background: transparent;
            border: 0;
        }
        #sensemakingSurface {
            background: #f7f3ea;
        }
        QFrame#sensemakingHeaderCard,
        QFrame#sensemakingInsightCard,
        QFrame#sensemakingPrincipleCard,
        QFrame#sensemakingKitCard {
            background: #fffdf7;
            border: 1px solid #eadfca;
            border-radius: 18px;
        }
        QLabel {
            color: #374151;
            font-size: 12px;
            line-height: 1.35;
        }
        QLabel[cssClass="BadgeLabel"] {
            color: #4338ca;
            background: #eef2ff;
            border: 1px solid #c7d2fe;
            border-radius: 10px;
            padding: 4px 8px;
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 0.4px;
        }
        QLabel#safetyBadgeLabel {
            color: #047857;
            background: #ecfdf5;
            border: 1px solid #a7f3d0;
            border-radius: 10px;
            padding: 4px 8px;
            font-size: 10px;
            font-weight: 700;
        }
        QLabel#safetyBadgeLabel[safetyLevel="warning"] {
            color: #92400e;
            background: #fffbeb;
            border-color: #fde68a;
        }
        QLabel#safetyBadgeLabel[safetyLevel="unsafe"],
        QLabel#safetyBadgeLabel[safetyLevel="danger"],
        QLabel#safetyBadgeLabel[safetyLevel="error"] {
            color: #991b1b;
            background: #fef2f2;
            border-color: #fecaca;
        }
        QLabel[cssClass="TitleLabel"] {
            color: #111827;
            font-size: 22px;
            font-weight: 800;
        }
        QLabel[cssClass="GoalLabel"] {
            color: #4b5563;
            font-size: 12px;
        }
        QLabel[cssClass="ChainLabel"] {
            color: #075985;
            background: #ecfeff;
            border: 1px solid #bae6fd;
            border-radius: 12px;
            padding: 7px 9px;
            font-weight: 700;
        }
        QLabel[cssClass="SectionLabel"] {
            color: #6b7280;
            font-size: 10px;
            font-weight: 800;
            letter-spacing: 0.7px;
            text-transform: uppercase;
        }
        QLabel[cssClass="ValueLabel"] {
            color: #111827;
            font-size: 14px;
            font-weight: 800;
        }
        QLabel[cssClass="EvidenceLabel"] {
            color: #155e75;
            background: #f0fdfa;
            border: 1px solid #99f6e4;
            border-radius: 12px;
            padding: 8px;
            font-weight: 650;
        }
        QLabel[cssClass="PromptLabel"] {
            color: #6d28d9;
            background: #f5f3ff;
            border: 1px solid #ddd6fe;
            border-radius: 12px;
            padding: 8px;
            font-weight: 700;
        }
        """
