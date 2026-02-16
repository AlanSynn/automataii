"""
Workflow state machine for non-linear tab workflows.

Design goals:
- Keep navigation non-blocking (users can jump across tabs freely)
- Offer optional guided recommendations
- Persist workflow mode/sequence/completion state
"""

from __future__ import annotations

from enum import Enum

from PyQt6.QtCore import QObject, QSettings, pyqtSignal


class WorkflowMode(str, Enum):
    FLEXIBLE = "flexible"
    GUIDED = "guided"


class WorkflowStateMachine(QObject):
    """Tracks workflow progress and recommends next tab/stage."""

    mode_changed = pyqtSignal(str)
    sequence_changed = pyqtSignal(list)
    recommendation_changed = pyqtSignal(str)

    def __init__(
        self,
        default_sequence: list[str],
        settings: QSettings | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings or QSettings("Automataii", "WorkflowState")
        self._default_sequence = self._dedupe_sequence(default_sequence)
        self._sequence = list(self._default_sequence)
        self._mode: WorkflowMode = WorkflowMode.FLEXIBLE
        self._visited: set[str] = set()
        self._completed: set[str] = set()
        self._current_tab_id: str | None = None
        self._load_state()

    @property
    def mode(self) -> WorkflowMode:
        return self._mode

    @property
    def sequence(self) -> list[str]:
        return list(self._sequence)

    def set_mode(self, mode: str | WorkflowMode) -> None:
        normalized = WorkflowMode.GUIDED if str(mode) == WorkflowMode.GUIDED.value else WorkflowMode.FLEXIBLE
        if normalized == self._mode:
            return
        self._mode = normalized
        self._persist_state()
        self.mode_changed.emit(self._mode.value)
        self._emit_recommendation()

    def capture_sequence(self, sequence: list[str]) -> None:
        deduped = self._dedupe_sequence(sequence)
        if not deduped:
            return
        self._sequence = deduped
        self._persist_state()
        self.sequence_changed.emit(list(self._sequence))
        self._emit_recommendation()

    def reset_sequence(self) -> None:
        self._sequence = list(self._default_sequence)
        self._persist_state()
        self.sequence_changed.emit(list(self._sequence))
        self._emit_recommendation()

    def on_tab_activated(self, tab_id: str | None) -> None:
        if not tab_id:
            return
        self._current_tab_id = tab_id
        self._visited.add(tab_id)
        self._persist_state()
        self._emit_recommendation()

    def mark_stage_complete(self, tab_id: str | None) -> None:
        if not tab_id:
            return
        self._completed.add(tab_id)
        self._visited.add(tab_id)
        self._persist_state()
        self._emit_recommendation()

    def can_navigate(self, tab_id: str | None) -> bool:
        if not tab_id or self._mode == WorkflowMode.FLEXIBLE:
            return True
        if tab_id not in self._sequence:
            return True
        target_index = self._sequence.index(tab_id)
        prerequisites = self._sequence[:target_index]
        return all(stage in self._completed for stage in prerequisites)

    def recommended_next_tab(self) -> str | None:
        if not self._sequence:
            return self._current_tab_id

        if self._mode == WorkflowMode.FLEXIBLE:
            for tab_id in self._sequence:
                if tab_id not in self._completed:
                    return tab_id
            return self._current_tab_id or self._sequence[0]

        if self._current_tab_id and self._current_tab_id in self._sequence:
            current_index = self._sequence.index(self._current_tab_id)
        else:
            current_index = 0

        for tab_id in self._sequence:
            if tab_id not in self._completed:
                return tab_id

        next_index = min(current_index + 1, len(self._sequence) - 1)
        return self._sequence[next_index]

    def build_status_message(self, label_lookup: dict[str, str] | None = None) -> str:
        if not self._sequence:
            return "Workflow: ready."
        suggested = self.recommended_next_tab()
        suggested_label = self._lookup_label(suggested, label_lookup)
        mode_label = "Flexible" if self._mode == WorkflowMode.FLEXIBLE else "Guided"
        return (
            f"{mode_label} workflow: {len(self._completed)}/{len(self._sequence)} complete"
            + (f" | Suggested: {suggested_label}" if suggested_label else "")
        )

    def _emit_recommendation(self) -> None:
        recommended = self.recommended_next_tab()
        self.recommendation_changed.emit(recommended or "")

    def _lookup_label(self, tab_id: str | None, label_lookup: dict[str, str] | None) -> str:
        if not tab_id:
            return ""
        if label_lookup and tab_id in label_lookup:
            return label_lookup[tab_id]
        return tab_id

    def _dedupe_sequence(self, sequence: list[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for item in sequence:
            if not item or item in seen:
                continue
            seen.add(item)
            ordered.append(item)
        return ordered

    def _load_state(self) -> None:
        mode_value = self._settings.value("workflow/mode", WorkflowMode.FLEXIBLE.value)
        self._mode = WorkflowMode.GUIDED if str(mode_value) == WorkflowMode.GUIDED.value else WorkflowMode.FLEXIBLE

        stored_sequence = self._coerce_string_list(self._settings.value("workflow/sequence", []))
        if stored_sequence:
            self._sequence = self._dedupe_sequence(stored_sequence)

        self._visited = set(self._coerce_string_list(self._settings.value("workflow/visited", [])))
        self._completed = set(self._coerce_string_list(self._settings.value("workflow/completed", [])))

        current_tab_id = self._settings.value("workflow/current_tab_id")
        if isinstance(current_tab_id, str) and current_tab_id:
            self._current_tab_id = current_tab_id

    def _persist_state(self) -> None:
        self._settings.setValue("workflow/mode", self._mode.value)
        self._settings.setValue("workflow/sequence", list(self._sequence))
        self._settings.setValue("workflow/visited", sorted(self._visited))
        self._settings.setValue("workflow/completed", sorted(self._completed))
        self._settings.setValue("workflow/current_tab_id", self._current_tab_id or "")
        self._settings.sync()

    def _coerce_string_list(self, value: object) -> list[str]:
        if isinstance(value, str):
            return [value] if value else []
        if isinstance(value, list):
            return [item for item in value if isinstance(item, str) and item]
        if isinstance(value, tuple):
            return [item for item in value if isinstance(item, str) and item]
        return []
