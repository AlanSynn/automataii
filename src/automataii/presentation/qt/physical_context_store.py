"""Qt runtime owner for the physical pegboard-kit context."""

from __future__ import annotations

from typing import Final

from PyQt6.QtCore import QObject, pyqtSignal

from automataii.shared.physical_kit import (
    DEFAULT_GRID_CELL_CM,
    DEFAULT_PHYSICAL_KIT_PROFILE,
    PhysicalKitContext,
    PhysicalKitProfile,
    physical_context_from_settings,
)

_UNSET: Final = object()


class PhysicalKitContextStore(QObject):
    """Single Qt-level owner for runtime physical-kit settings.

    The shared ``PhysicalKitContext`` remains Qt-free and serializable; this
    QObject only owns mutation and notification for live presentation widgets.
    Tabs may keep local render caches, but user/settings mutations flow through
    this store first.
    """

    context_changed = pyqtSignal(object)

    def __init__(
        self,
        context: PhysicalKitContext | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._context = context or physical_context_from_settings(
            True,
            DEFAULT_GRID_CELL_CM,
            profile=DEFAULT_PHYSICAL_KIT_PROFILE,
        )

    @property
    def context(self) -> PhysicalKitContext:
        return self._context

    def set_context(
        self, context: PhysicalKitContext, *, force: bool = False
    ) -> PhysicalKitContext:
        """Replace the context and notify subscribers when it changes."""
        if not force and context == self._context:
            return self._context
        self._context = context
        self.context_changed.emit(context)
        return self._context

    def update_from_settings(
        self,
        *,
        enabled: object = _UNSET,
        grid_cell_cm: object = _UNSET,
        grid_pitch_choice: object = _UNSET,
        profile: PhysicalKitProfile | object = _UNSET,
    ) -> PhysicalKitContext:
        """Normalize partial UI settings into one authoritative context."""
        current = self._context
        next_enabled = current.enabled if enabled is _UNSET else enabled
        next_grid_cell_cm = current.grid_cell_cm if grid_cell_cm is _UNSET else grid_cell_cm
        next_grid_pitch_choice = (
            current.grid_pitch_choice if grid_pitch_choice is _UNSET else grid_pitch_choice
        )
        if grid_cell_cm is not _UNSET and grid_pitch_choice is _UNSET:
            next_grid_pitch_choice = None
        next_profile = current.profile if profile is _UNSET else profile
        if not isinstance(next_profile, PhysicalKitProfile):
            next_profile = DEFAULT_PHYSICAL_KIT_PROFILE

        context = physical_context_from_settings(
            next_enabled,
            next_grid_cell_cm,
            next_grid_pitch_choice,
            profile=next_profile,
        )
        return self.set_context(context)
