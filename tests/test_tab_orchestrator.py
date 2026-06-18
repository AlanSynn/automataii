from __future__ import annotations

import sys
from typing import cast

from PyQt6.QtWidgets import QApplication, QTabWidget, QWidget

from automataii.presentation.qt.windows.components.tab_orchestrator import TabOrchestrator

_APP: QApplication | None = None


def _get_app() -> QApplication:
    global _APP
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    app = cast(QApplication, app)
    _APP = app
    return app


class _MechanismTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._initial_skeleton_data_cache = None
        self.events: list[str] = []

    def cache_initial_skeleton(self, data: dict[str, object]) -> None:
        self._initial_skeleton_data_cache = data
        self.events.append("cache")

    def activate_tab(self) -> None:
        self.events.append(
            "activate_with_cache" if self._initial_skeleton_data_cache else "activate_empty"
        )


def test_tab_orchestrator_syncs_skeleton_before_mechanism_activation() -> None:
    _ = _get_app()
    tabs = QTabWidget()
    previous = QWidget()
    current = _MechanismTab()
    tabs.addTab(previous, "Editor")
    tabs.addTab(current, "Mechanism")
    orchestrator = TabOrchestrator(tabs)
    orchestrator.configure_callbacks(
        get_status_bar=lambda: None,
        get_skeleton_manager=lambda: type(
            "SkeletonManager",
            (),
            {"get_current_skeleton_data": lambda self: {"joints": {"root": {}}}},
        )(),
    )

    orchestrator._on_tab_changed(1)  # type: ignore[attr-defined]

    assert current.events == ["cache", "activate_with_cache"]
