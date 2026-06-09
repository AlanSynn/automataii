from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from automataii.domain.mechanisms.linkages.config import LinkageConfig, LinkageType, LinkRole
from automataii.presentation.qt.tabs.mechanism_foundry.widgets.grashof_display import (
    GrashofAnalysis,
)


class EnhancedInfoPanel(QWidget):
    """Compact “Mechanism Basics” card shown on the right-hand side."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(240)
        self.setMaximumWidth(320)

        self._build_ui()
        self.clear()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        card = QFrame(self)
        card.setObjectName("mechanismBasicsCard")
        card.setStyleSheet(
            """
            QFrame#mechanismBasicsCard {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 12px;
            }
            """
        )

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(10)

        self._title_label = QLabel("Mechanism Basics", card)
        self._title_label.setStyleSheet("font-size: 16px; font-weight: 700; color: #1f2937;")
        card_layout.addWidget(self._title_label)

        self._summary_label = QLabel(card)
        self._summary_label.setWordWrap(True)
        self._summary_label.setStyleSheet("color: #334155; font-size: 12px;")
        card_layout.addWidget(self._summary_label)

        roles_header = QLabel("Link Roles", card)
        roles_header.setStyleSheet("color: #64748b; font-size: 12px; font-weight: 600;")
        card_layout.addWidget(roles_header)

        self._roles_label = QLabel(card)
        self._roles_label.setWordWrap(True)
        self._roles_label.setStyleSheet("color: #0f172a; font-size: 12px;")
        card_layout.addWidget(self._roles_label)

        badge_row = QHBoxLayout()
        badge_row.setSpacing(8)
        badge_row.setContentsMargins(0, 4, 0, 0)

        badge_caption = QLabel("Grashof:")
        badge_caption.setStyleSheet("color:#64748b; font-weight:600; font-size:12px;")
        badge_row.addWidget(badge_caption)

        self._grashof_badge = QLabel(card)
        self._grashof_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._grashof_badge.setFixedHeight(22)
        self._set_grashof_badge("n/a", "#cbd5f5", "#1d4ed8")
        badge_row.addWidget(self._grashof_badge)
        badge_row.addStretch()

        card_layout.addLayout(badge_row)

        self._notes_label = QLabel(card)
        self._notes_label.setWordWrap(True)
        self._notes_label.setStyleSheet("color:#475569; font-size:12px;")
        card_layout.addWidget(self._notes_label)

        card_layout.addStretch()

        main_layout.addWidget(card)
        main_layout.addStretch()

    def update_mechanism(self, config: LinkageConfig) -> None:
        link_count = len(config.link_lengths)
        mechanism_name = self._friendly_name(config.type, link_count)
        config.get_link_role(config.driver_index).value.title()
        follower_role = self._find_role(config, LinkRole.FOLLOWER)

        summary_parts = [
            f"{link_count} links",
            f"driver: Link {config.driver_index}",
        ]
        if follower_role:
            summary_parts.append(f"follower: {follower_role}")

        lengths_text = ", ".join(f"{length:.0f}mm" for length in config.link_lengths)
        summary_parts.append(f"lengths: {lengths_text}")

        role_lines = [f"Link {idx}: {role.value.title()}" for idx, role in enumerate(config.roles)]

        self.update_summary(
            title=mechanism_name,
            summary_lines=summary_parts,
            roles=role_lines,
            badge={
                "text": f"{GrashofAnalysis.from_config(config).classification.value} ({'Pass' if GrashofAnalysis.from_config(config).passes else 'Fail'})"
                if config.type == LinkageType.FOUR_BAR
                else "N/A",
                "bg": "#dcfce7"
                if config.type == LinkageType.FOUR_BAR
                and GrashofAnalysis.from_config(config).passes
                else "#fee2e2"
                if config.type == LinkageType.FOUR_BAR
                else "#e2e8f0",
                "fg": "#166534"
                if config.type == LinkageType.FOUR_BAR
                and GrashofAnalysis.from_config(config).passes
                else "#b91c1c"
                if config.type == LinkageType.FOUR_BAR
                else "#475569",
            },
            note="Tip: Watch how the driver pulls the coupler—try changing the driven link or bar count to see different motions.",
        )

    def update_summary(
        self,
        title: str,
        summary_lines: list[str],
        roles: list[str],
        badge: dict[str, str] | None = None,
        note: str | None = None,
    ) -> None:
        self._title_label.setText(title)
        self._summary_label.setText(" • ".join(summary_lines))
        self._roles_label.setText("\n".join(roles))

        if badge:
            self._set_grashof_badge(
                badge.get("text", "N/A"), badge.get("bg", "#e2e8f0"), badge.get("fg", "#475569")
            )
        else:
            self._set_grashof_badge("N/A", "#e2e8f0", "#475569")

        if note:
            self._notes_label.setText(note)
        else:
            self._notes_label.setText("")

    def clear(self) -> None:
        self.update_summary(
            title="Mechanism Basics",
            summary_lines=["Select a mechanism to review its core traits."],
            roles=["Link roles will appear here once a mechanism is active."],
            badge=None,
            note="Tip: Use the gallery to pick a mechanism and explore how each link contributes.",
        )

    @staticmethod
    def _friendly_name(linkage_type: LinkageType, link_count: int) -> str:
        if linkage_type == LinkageType.THREE_BAR:
            return "Three-Bar Linkage"
        if linkage_type == LinkageType.FIVE_BAR:
            return "Five-Bar Linkage"
        if linkage_type == LinkageType.SIX_BAR:
            return "Six-Bar Linkage"
        if linkage_type == LinkageType.FOUR_BAR:
            return "Four-Bar Linkage"
        return f"{link_count}-Link Mechanism"

    @staticmethod
    def _find_role(config: LinkageConfig, role: LinkRole) -> str | None:
        for idx, link_role in enumerate(config.roles):
            if link_role == role:
                return f"Link {idx}"
        return None

    def _set_grashof_badge(self, text: str, background: str, foreground: str) -> None:
        self._grashof_badge.setText(text)
        self._grashof_badge.setStyleSheet(
            f"padding: 2px 10px; border-radius: 10px; font-size: 11px; "
            f"font-weight: 600; background: {background}; color: {foreground};"
        )
