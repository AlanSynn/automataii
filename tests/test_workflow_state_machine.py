from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QSettings

from automataii.presentation.qt.windows.components.workflow_state_machine import (
    WorkflowStateMachine,
)


def _settings_for_test(tmp_path: Path, name: str) -> QSettings:
    settings_path = tmp_path / f"{name}.ini"
    return QSettings(str(settings_path), QSettings.Format.IniFormat)


def test_flexible_workflow_recommends_first_incomplete_stage(tmp_path: Path) -> None:
    machine = WorkflowStateMachine(
        default_sequence=["welcome", "character", "design"],
        settings=_settings_for_test(tmp_path, "flexible_recommend"),
    )

    assert machine.recommended_next_tab() == "welcome"

    machine.mark_stage_complete("welcome")
    assert machine.recommended_next_tab() == "character"


def test_guided_workflow_reports_missing_prerequisites(tmp_path: Path) -> None:
    machine = WorkflowStateMachine(
        default_sequence=["welcome", "character", "design"],
        settings=_settings_for_test(tmp_path, "guided_checks"),
    )
    machine.set_mode("guided")

    assert machine.can_navigate("design") is False

    machine.mark_stage_complete("welcome")
    assert machine.can_navigate("design") is False

    machine.mark_stage_complete("character")
    assert machine.can_navigate("design") is True


def test_capture_and_reset_sequence(tmp_path: Path) -> None:
    machine = WorkflowStateMachine(
        default_sequence=["welcome", "character", "design"],
        settings=_settings_for_test(tmp_path, "capture_sequence"),
    )

    machine.capture_sequence(["design", "welcome", "design", "character"])
    assert machine.sequence == ["design", "welcome", "character"]

    machine.reset_sequence()
    assert machine.sequence == ["welcome", "character", "design"]


def test_status_message_uses_label_lookup(tmp_path: Path) -> None:
    machine = WorkflowStateMachine(
        default_sequence=["welcome", "character"],
        settings=_settings_for_test(tmp_path, "status_message"),
    )

    message = machine.build_status_message(
        {"welcome": "Welcome", "character": "Character Selection"}
    )
    assert "Flexible workflow" in message
    assert "Suggested: Welcome" in message
