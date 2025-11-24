from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QSlider,
    QVBoxLayout,
)


class CustomCouplerPointDialog(QDialog):
    """Dialog that lets the user select a custom tracking point along the coupler link."""

    def __init__(
        self,
        parent=None,
        initial_fraction: float = 0.5,
        coupler_length_mm: float = 120.0,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Custom Coupler Path")
        self.setModal(True)
        self._coupler_length_mm = max(coupler_length_mm, 1.0)
        self._fraction = max(0.0, min(1.0, initial_fraction))
        self._build_ui()

    def selected_fraction(self) -> float:
        """Return the normalised position along the coupler (0.0 = at joint A, 1.0 = at joint B)."""
        return self._fraction

    # --------------------------------------------------------------------- #
    # UI construction helpers
    # --------------------------------------------------------------------- #
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        description = QLabel(
            "Select a point along the coupler link to track in the path preview.\n"
            "0.0 locks to joint A, 1.0 locks to joint B. The selection adapts as the linkage moves."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        self._value_label = QLabel()
        layout.addWidget(self._value_label)

        control_row = QHBoxLayout()
        control_row.setSpacing(12)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 100)
        self._slider.setValue(int(round(self._fraction * 100)))
        self._slider.valueChanged.connect(self._on_slider_changed)

        self._spin = QDoubleSpinBox()
        self._spin.setRange(0.0, 1.0)
        self._spin.setSingleStep(0.01)
        self._spin.setDecimals(2)
        self._spin.setValue(self._fraction)
        self._spin.valueChanged.connect(self._on_spin_changed)

        control_row.addWidget(QLabel("Fraction:"))
        control_row.addWidget(self._spin)
        control_row.addWidget(self._slider, stretch=1)
        layout.addLayout(control_row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._update_label()

    def _on_slider_changed(self, value: int) -> None:
        fraction = max(0.0, min(1.0, value / 100.0))
        if abs(fraction - self._fraction) < 1e-6:
            return
        self._fraction = fraction
        self._spin.blockSignals(True)
        self._spin.setValue(fraction)
        self._spin.blockSignals(False)
        self._update_label()

    def _on_spin_changed(self, value: float) -> None:
        fraction = max(0.0, min(1.0, value))
        if abs(fraction - self._fraction) < 1e-6:
            return
        self._fraction = fraction
        self._slider.blockSignals(True)
        self._slider.setValue(int(round(fraction * 100)))
        self._slider.blockSignals(False)
        self._update_label()

    def _update_label(self) -> None:
        distance = self._fraction * self._coupler_length_mm
        self._value_label.setText(
            f"Tracking point at {self._fraction:.2f} × coupler length (~{distance:.1f} mm from joint A)."
        )
