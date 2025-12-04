"""
Widget utilities for safe signal-blocking value updates.

This module provides utilities to update widget values without
triggering signals, preventing infinite loops in connected widgets.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from PyQt6.QtWidgets import QComboBox, QDoubleSpinBox, QSlider, QSpinBox, QWidget


T = TypeVar("T", bound="QWidget")


@contextmanager
def blocked_signals(widget: T) -> Iterator[T]:
    """Context manager to temporarily block signals on a widget.

    Usage:
        with blocked_signals(slider):
            slider.setValue(50)

    Args:
        widget: Any QWidget subclass

    Yields:
        The same widget with signals blocked
    """
    widget.blockSignals(True)
    try:
        yield widget
    finally:
        widget.blockSignals(False)


def set_value_silently(
    widget: QSlider | QSpinBox | QDoubleSpinBox,
    value: int | float
) -> None:
    """Set widget value without triggering signals.

    Works with QSlider, QSpinBox, and QDoubleSpinBox.

    Args:
        widget: The widget to update
        value: The value to set
    """
    with blocked_signals(widget):
        widget.setValue(int(value) if isinstance(widget.value(), int) else value)


def set_combo_silently(
    combo: QComboBox,
    items: list[str] | None = None,
    current_text: str | None = None,
    current_index: int | None = None
) -> None:
    """Set combo box contents and/or selection without triggering signals.

    Args:
        combo: The combo box to update
        items: Optional list of items to populate (clears existing)
        current_text: Optional text to select by matching
        current_index: Optional index to select directly
    """
    with blocked_signals(combo):
        if items is not None:
            combo.clear()
            for item in items:
                combo.addItem(item)

        if current_text is not None:
            index = combo.findText(current_text)
            if index >= 0:
                combo.setCurrentIndex(index)
        elif current_index is not None:
            combo.setCurrentIndex(current_index)


class SliderSpinboxSync:
    """Synchronizes a slider and spinbox pair with proper signal blocking.

    This class encapsulates the common pattern of keeping a slider and
    spinbox in sync, handling the conversion between slider steps and
    spinbox values, and preventing infinite signal loops.

    Usage:
        sync = SliderSpinboxSync(
            slider=self.my_slider,
            spinbox=self.my_spinbox,
            min_value=0.0,
            max_value=100.0,
            step=0.1
        )

        # Connect signals
        self.my_slider.valueChanged.connect(sync.on_slider_changed)
        self.my_spinbox.valueChanged.connect(sync.on_spinbox_changed)

        # Set value programmatically
        sync.set_value(50.0)

        # Get current value
        value = sync.value
    """

    def __init__(
        self,
        slider: QSlider,
        spinbox: QSpinBox | QDoubleSpinBox,
        min_value: float,
        max_value: float,
        step: float = 1.0,
        on_value_changed: Callable[[float], None] | None = None
    ):
        """Initialize slider-spinbox synchronization.

        Args:
            slider: The QSlider widget
            spinbox: The QSpinBox or QDoubleSpinBox widget
            min_value: Minimum value in spinbox units
            max_value: Maximum value in spinbox units
            step: Step size in spinbox units
            on_value_changed: Optional callback when value changes
        """
        self._slider = slider
        self._spinbox = spinbox
        self._min_value = min_value
        self._max_value = max_value
        self._step = step if step > 0 else 1.0
        self._on_value_changed = on_value_changed
        self._value = min_value

        # Calculate total steps for slider
        self._total_steps = max(1, int(round((max_value - min_value) / self._step)))

        # Configure widgets
        self._configure_widgets()

    def _configure_widgets(self) -> None:
        """Configure slider and spinbox ranges."""
        with blocked_signals(self._slider):
            self._slider.setMinimum(0)
            self._slider.setMaximum(self._total_steps)

        with blocked_signals(self._spinbox):
            self._spinbox.setRange(self._min_value, self._max_value)
            self._spinbox.setSingleStep(self._step)

    @property
    def value(self) -> float:
        """Get current synchronized value."""
        return self._value

    def set_value(self, value: float, emit: bool = True) -> None:
        """Set value and update both widgets.

        Args:
            value: The value to set
            emit: Whether to trigger the on_value_changed callback
        """
        clamped = max(self._min_value, min(self._max_value, value))
        self._value = clamped

        # Calculate slider position
        slider_value = int(round((clamped - self._min_value) / self._step))
        slider_value = max(0, min(self._total_steps, slider_value))

        # Update widgets
        with blocked_signals(self._slider):
            self._slider.setValue(slider_value)

        with blocked_signals(self._spinbox):
            self._spinbox.setValue(clamped)

        if emit and self._on_value_changed:
            self._on_value_changed(clamped)

    def on_slider_changed(self, slider_value: int) -> None:
        """Handle slider value change. Connect to slider.valueChanged."""
        # Convert slider steps to value
        value = self._min_value + slider_value * self._step
        value = max(self._min_value, min(self._max_value, value))
        self._value = value

        # Sync spinbox
        with blocked_signals(self._spinbox):
            self._spinbox.setValue(value)

        if self._on_value_changed:
            self._on_value_changed(value)

    def on_spinbox_changed(self, spinbox_value: float) -> None:
        """Handle spinbox value change. Connect to spinbox.valueChanged."""
        value = max(self._min_value, min(self._max_value, spinbox_value))
        self._value = value

        # Calculate slider position
        slider_value = int(round((value - self._min_value) / self._step))
        slider_value = max(0, min(self._total_steps, slider_value))

        # Sync slider
        with blocked_signals(self._slider):
            self._slider.setValue(slider_value)

        if self._on_value_changed:
            self._on_value_changed(value)

    def update_range(
        self,
        min_value: float | None = None,
        max_value: float | None = None,
        step: float | None = None
    ) -> None:
        """Update the synchronization range.

        Args:
            min_value: New minimum value (optional)
            max_value: New maximum value (optional)
            step: New step size (optional)
        """
        if min_value is not None:
            self._min_value = min_value
        if max_value is not None:
            self._max_value = max_value
        if step is not None and step > 0:
            self._step = step

        self._total_steps = max(1, int(round((self._max_value - self._min_value) / self._step)))
        self._configure_widgets()

        # Re-apply current value to ensure it's within new range
        self.set_value(self._value, emit=False)
