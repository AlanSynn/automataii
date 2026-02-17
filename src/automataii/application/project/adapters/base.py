"""
Base Tab Adapter.

Provides common interface for all tab adapters.

Architecture: Application Layer (Hexagonal)
Pattern: Template Method
"""
from __future__ import annotations

import logging
from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject

if TYPE_CHECKING:
    from automataii.application.project import ProjectStateManager

logger = logging.getLogger(__name__)


class QObjectABCMeta(type(QObject), ABCMeta):
    """Combined metaclass for QObject and ABC."""
    pass


class TabAdapter(QObject, metaclass=QObjectABCMeta):
    """
    Base adapter for bridging tabs to ProjectStateManager.

    Responsibilities:
    - Connect to tab signals (production)
    - Subscribe to state changes (consumption)
    - Transform data between tab format and domain models

    Subclasses implement:
    - _connect_tab_signals(): Connect to tab's pyqtSignals
    - _subscribe_to_state(): Subscribe to relevant state changes
    - Data transformation methods
    """

    def __init__(
        self,
        state_manager: ProjectStateManager,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._state_manager = state_manager
        self._tab = None
        self._connected = False

    @property
    def state_manager(self) -> ProjectStateManager:
        return self._state_manager

    @property
    def tab(self):
        return self._tab

    @property
    def is_connected(self) -> bool:
        return self._connected

    def attach(self, tab) -> None:
        """
        Attach adapter to a tab instance.

        Args:
            tab: The tab widget to adapt
        """
        if self._connected:
            logger.warning(f"{self.__class__.__name__} already connected")
            return

        self._tab = tab
        self._connect_tab_signals()
        self._subscribe_to_state()
        self._connected = True
        logger.info(f"{self.__class__.__name__} attached to {tab.__class__.__name__}")

    def detach(self) -> None:
        """Detach adapter from tab."""
        if not self._connected:
            return

        self._disconnect_tab_signals()
        self._unsubscribe_from_state()
        self._tab = None
        self._connected = False
        logger.info(f"{self.__class__.__name__} detached")

    @abstractmethod
    def _connect_tab_signals(self) -> None:
        """Connect to tab's output signals."""
        ...

    @abstractmethod
    def _subscribe_to_state(self) -> None:
        """Subscribe to relevant state manager signals."""
        ...

    def _disconnect_tab_signals(self) -> None:
        """Disconnect from tab's signals. Override if needed."""
        pass

    def _unsubscribe_from_state(self) -> None:
        """Unsubscribe from state manager. Override if needed."""
        pass

    def _is_runtime_to_ssot_sync_in_progress(self) -> bool:
        """Return True when MainWindow is mirroring runtime state into SSOT."""
        parent = self.parent()
        if parent is None:
            return False
        return bool(getattr(parent, "_runtime_to_ssot_sync_in_progress", False))
