from __future__ import annotations

import html
import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import Enum
from typing import SupportsFloat, SupportsIndex, cast

from PyQt6.QtCore import QSettings, Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpacerItem,
    QTextBrowser,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from automataii.application.mechanism_foundry import MechanismContent, ParameterSpec
from automataii.presentation.qt.shared import blocked_signals, clear_layout

MM_PER_INCH = 25.4
MAX_SLIDER_STEPS = 10_000
_FloatPayload = str | bytes | bytearray | SupportsFloat | SupportsIndex


def _finite_float(value: object, default: float) -> float:
    try:
        result = float(cast(_FloatPayload, value))
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _positive_finite_float(value: object, default: float) -> float:
    result = _finite_float(value, default)
    return result if result > 0.0 else default


def _finite_range(min_value: object, max_value: object, default_min: float, default_max: float) -> tuple[float, float]:
    low = _finite_float(min_value, default_min)
    high = _finite_float(max_value, default_max)
    if low == high:
        high = low + 1.0
    if low > high:
        low, high = high, low
    return low, high


def _bounded_step(min_unit: float, max_unit: float, requested_step: object) -> tuple[float, int]:
    span = max(0.0, max_unit - min_unit)
    step = _positive_finite_float(requested_step, 1.0)
    if span <= 0.0:
        return 1.0, 1
    total_steps = max(1, int(round(span / step)))
    if total_steps > MAX_SLIDER_STEPS:
        total_steps = MAX_SLIDER_STEPS
        step = span / total_steps
    return step, total_steps


def _slider_index(value: object, default: int = 0) -> int:
    try:
        return int(cast(SupportsIndex, value))
    except (TypeError, ValueError, OverflowError):
        return default


class UnitSystem(str, Enum):
    MILLIMETER = "mm"
    INCH = "inch"


def _mm_to_unit(value_mm: float, unit: UnitSystem) -> float:
    value_mm = _finite_float(value_mm, 0.0)
    if unit == UnitSystem.MILLIMETER:
        return value_mm
    return value_mm / MM_PER_INCH


def _unit_to_mm(value_unit: float, unit: UnitSystem) -> float:
    value_unit = _finite_float(value_unit, 0.0)
    if unit == UnitSystem.MILLIMETER:
        return value_unit
    return value_unit * MM_PER_INCH


class CollapsibleSection(QWidget):
    toggled = pyqtSignal(bool)

    def __init__(self, title: str, settings: QSettings, settings_key: str, parent: QWidget | None = None):
        super().__init__(parent)
        self._settings = settings
        self._settings_key = settings_key

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._toggle_btn = QToolButton(self)
        self._toggle_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._toggle_btn.setArrowType(Qt.ArrowType.DownArrow)
        self._toggle_btn.setText(title)
        self._toggle_btn.setCheckable(True)
        self._toggle_btn.setChecked(True)
        self._toggle_btn.clicked.connect(self._on_toggled)
        self._toggle_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.setStyleSheet(
            """
            QToolButton {
                border: none;
                font-size: 15px;
                font-weight: 600;
                padding: 6px 4px;
                text-align: left;
            }
            """
        )
        layout.addWidget(self._toggle_btn)

        divider = QFrame(self)
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(divider)

        self._content = QWidget(self)
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 8, 0, 8)
        self._content_layout.setSpacing(12)
        layout.addWidget(self._content)

        collapsed = self._settings.value(self._settings_key, False, type=bool)
        self.set_collapsed(bool(collapsed))

    def content_layout(self) -> QVBoxLayout:
        return self._content_layout

    def set_collapsed(self, collapsed: bool) -> None:
        with blocked_signals(self._toggle_btn):
            self._toggle_btn.setChecked(not collapsed)
        self._content.setVisible(not collapsed)
        self._toggle_btn.setArrowType(
            Qt.ArrowType.RightArrow if collapsed else Qt.ArrowType.DownArrow
        )
        self._settings.setValue(self._settings_key, collapsed)
        self.toggled.emit(not collapsed)

    def _on_toggled(self) -> None:
        collapsed = not self._toggle_btn.isChecked()
        self.set_collapsed(collapsed)


@dataclass(slots=True)
class _DimensionControl:
    spec: ParameterSpec
    slider: QSlider
    spinbox: QDoubleSpinBox
    label: QLabel
    min_unit: float
    max_unit: float
    step_unit: float
    current_unit: UnitSystem
    value_mm: float
    is_length: bool
    on_value_changed: Callable[[str, float], None]

    def configure_unit(self, unit: UnitSystem) -> None:
        self.current_unit = unit
        if not self.is_length:
            self.min_unit, self.max_unit = _finite_range(
                self.spec.min_value,
                self.spec.max_value,
                0.0,
                1.0,
            )
            self.step_unit, total_steps = _bounded_step(
                self.min_unit,
                self.max_unit,
                self.spec.step,
            )
            decimals = 0 if self.spec.is_integer else 2
            suffix = f" {self.spec.unit}" if self.spec.unit else ""

            with blocked_signals(self.spinbox):
                self.spinbox.setDecimals(decimals)
                self.spinbox.setSuffix(suffix)
                self.spinbox.setRange(self.min_unit, self.max_unit)
                self.spinbox.setSingleStep(self.step_unit)

            with blocked_signals(self.slider):
                self.slider.setMinimum(0)
                self.slider.setMaximum(total_steps)
            self.set_value_mm(self.value_mm, emit=False)
            return

        self.current_unit = unit
        min_mm, max_mm = _finite_range(self.spec.min_value, self.spec.max_value, 0.0, 1.0)
        self.min_unit = _mm_to_unit(min_mm, unit)
        self.max_unit = _mm_to_unit(max_mm, unit)
        raw_step = _positive_finite_float(self.spec.step, 1.0)
        step_unit = _mm_to_unit(raw_step, unit)
        self.step_unit, total_steps = _bounded_step(
            self.min_unit,
            self.max_unit,
            step_unit,
        )

        decimals = 0 if self.spec.is_integer else (2 if unit == UnitSystem.MILLIMETER else 3)
        suffix = f" {unit.value}"

        with blocked_signals(self.spinbox):
            self.spinbox.setDecimals(decimals)
            self.spinbox.setSuffix(suffix)
            self.spinbox.setRange(self.min_unit, self.max_unit)
            self.spinbox.setSingleStep(self.step_unit)

        with blocked_signals(self.slider):
            self.slider.setMinimum(0)
            self.slider.setMaximum(total_steps)
        self.set_value_mm(self.value_mm, emit=False)

    def set_value_mm(self, value_mm: float, emit: bool = False) -> None:
        min_mm, max_mm = _finite_range(self.spec.min_value, self.spec.max_value, 0.0, 1.0)
        value_mm = _finite_float(value_mm, self.value_mm)
        clamped = max(min_mm, min(max_mm, value_mm))
        self.value_mm = clamped

        if self.is_length:
            unit_value = _mm_to_unit(clamped, self.current_unit)
        else:
            unit_value = clamped

        if self.step_unit <= 0 or not math.isfinite(self.step_unit):
            slider_value = 0
        else:
            slider_value = int(round((unit_value - self.min_unit) / self.step_unit))
        slider_value = max(self.slider.minimum(), min(self.slider.maximum(), slider_value))

        unit_value = self.min_unit + slider_value * self.step_unit
        if self.is_length:
            value_mm = _unit_to_mm(unit_value, self.current_unit)
            self.value_mm = value_mm
        else:
            self.value_mm = unit_value

        with blocked_signals(self.slider):
            self.slider.setValue(slider_value)

        with blocked_signals(self.spinbox):
            self.spinbox.setValue(unit_value)

        if emit:
            self.on_value_changed(self.spec.key, self.value_mm)

    def handle_slider_change(self, slider_value: int) -> None:
        slider_value = _slider_index(slider_value, self.slider.value())
        slider_value = max(self.slider.minimum(), min(self.slider.maximum(), slider_value))
        unit_value = self.min_unit + slider_value * self.step_unit
        if self.is_length:
            value_mm = _unit_to_mm(unit_value, self.current_unit)
        else:
            value_mm = unit_value
        self.set_value_mm(value_mm, emit=True)

    def handle_spinbox_change(self, unit_value: float) -> None:
        unit_value = _finite_float(unit_value, self.min_unit)
        if self.is_length:
            value_mm = _unit_to_mm(unit_value, self.current_unit)
        else:
            value_mm = unit_value
        self.set_value_mm(value_mm, emit=True)


class MechanismParameterPanel(QWidget):
    parameter_changed = pyqtSignal(str, float)
    unit_changed = pyqtSignal(str)
    linkage_type_changed = pyqtSignal(int)
    driver_index_changed = pyqtSignal(int)
    coupler_point_changed = pyqtSignal(str)
    follower_position_changed = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(320)
        self.setMaximumWidth(360)

        self._settings = QSettings("MotionSmith", "MechanismFoundry")

        self._unit_system = UnitSystem.MILLIMETER
        self._dimension_controls: dict[str, _DimensionControl] = {}

        self._linkage_buttons: dict[int, QPushButton] = {}
        self._linkage_group = QButtonGroup(self)
        self._linkage_group.setExclusive(True)

        self._driver_buttons: dict[int, QRadioButton] = {}
        self._driver_group = QButtonGroup(self)
        self._driver_group.setExclusive(True)

        self._hints_browser: QTextBrowser | None = None
        self._status_label: QLabel | None = None

        self._build_layout()

    def _build_layout(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        scroll_widget = QWidget()
        content_layout = QVBoxLayout(scroll_widget)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(16)

        self._dimensions_section = CollapsibleSection(
            "Dimensions", self._settings, "panel_section_dimensions", self
        )
        content_layout.addWidget(self._dimensions_section)

        self._configuration_section = CollapsibleSection(
            "Configuration", self._settings, "panel_section_configuration", self
        )
        content_layout.addWidget(self._configuration_section)

        self._guidance_section = CollapsibleSection(
            "Learning Hints", self._settings, "panel_section_guidance", self
        )
        content_layout.addWidget(self._guidance_section)

        content_layout.addStretch()

        scroll_area.setWidget(scroll_widget)
        outer_layout.addWidget(scroll_area)

        status_frame = QFrame()
        status_frame.setFrameShape(QFrame.Shape.NoFrame)
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(16, 8, 16, 12)
        status_layout.setSpacing(8)

        caption = QLabel("Status:")
        caption.setStyleSheet("color:#6b7280; font-weight:600;")
        status_layout.addWidget(caption)

        self._status_label = QLabel("Ready")
        self._status_label.setStyleSheet("color:#1f2937; font-weight:600;")
        status_layout.addWidget(self._status_label, stretch=1)

        outer_layout.addWidget(status_frame)

        self._build_dimensions_section()
        self._build_configuration_section()
        self._build_guidance_section()

    def _build_dimensions_section(self) -> None:
        container = self._dimensions_section.content_layout()
        container.setSpacing(10)

        unit_row = QHBoxLayout()
        unit_row.addWidget(QLabel("Units:"))

        self._mm_button = QRadioButton("mm")
        self._inch_button = QRadioButton("inch")
        self._mm_button.setChecked(True)
        self._mm_button.toggled.connect(lambda checked: checked and self._set_unit(UnitSystem.MILLIMETER))
        self._inch_button.toggled.connect(lambda checked: checked and self._set_unit(UnitSystem.INCH))

        unit_group = QButtonGroup(self)
        unit_group.addButton(self._mm_button)
        unit_group.addButton(self._inch_button)

        unit_row.addWidget(self._mm_button)
        unit_row.addWidget(self._inch_button)
        unit_row.addStretch()
        container.addLayout(unit_row)

        self._dimensions_placeholder = QWidget()
        self._dimensions_placeholder_layout = QVBoxLayout(self._dimensions_placeholder)
        self._dimensions_placeholder_layout.setContentsMargins(0, 0, 0, 0)
        self._dimensions_placeholder_layout.setSpacing(10)
        container.addWidget(self._dimensions_placeholder)

    def _build_configuration_section(self) -> None:
        layout = self._configuration_section.content_layout()
        layout.setSpacing(10)

        linkage_label = QLabel("Linkage Type:")
        layout.addWidget(linkage_label)

        linkage_row = QHBoxLayout()
        linkage_row.setSpacing(6)
        for idx, label in enumerate(["3-Bar", "4-Bar", "5-Bar", "6-Bar"], start=3):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            self._linkage_group.addButton(button, idx)
            linkage_row.addWidget(button)
            self._linkage_buttons[idx] = button
        linkage_row.addStretch()
        layout.addLayout(linkage_row)
        self._linkage_group.idClicked.connect(self._on_linkage_type_changed)

        driver_label = QLabel("Which link is driven?")
        layout.addWidget(driver_label)

        self._driver_container = QVBoxLayout()
        layout.addLayout(self._driver_container)

        coupler_row = QHBoxLayout()
        coupler_row.addWidget(QLabel("Coupler Point Path:"))
        self._coupler_combo = QComboBox()
        coupler_row.addWidget(self._coupler_combo)
        layout.addLayout(coupler_row)
        self._coupler_combo.currentTextChanged.connect(self._on_coupler_point_changed)

        follower_row = QHBoxLayout()
        follower_row.addWidget(QLabel("Follower Position:"))
        self._follower_combo = QComboBox()
        follower_row.addWidget(self._follower_combo)
        layout.addLayout(follower_row)
        self._follower_combo.currentTextChanged.connect(self._on_follower_position_changed)

        hints_label = QLabel("Educational hints")
        hints_label.setFont(QFont(hints_label.font().family(), 11, QFont.Weight.Medium))

        layout.addWidget(hints_label)
        self._hints_browser = QTextBrowser()
        self._hints_browser.setFrameShape(QFrame.Shape.NoFrame)
        self._hints_browser.setOpenExternalLinks(False)
        self._hints_browser.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._hints_browser.setMaximumHeight(120)
        self._hints_browser.setStyleSheet(
            """
            QTextBrowser {
                background: #f7f9fc;
                border-radius: 6px;
                padding: 8px;
                font-size: 12px;
            }
            """
        )
        layout.addWidget(self._hints_browser)

    def _build_guidance_section(self) -> None:
        layout = self._guidance_section.content_layout()
        layout.setSpacing(6)

        intro = QLabel(
            "Use these controls to explore how link lengths and driver selection change the motion. "
            "Hover over hints for quick intuition, or open the info panel for deeper dives."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color:#4b5563; font-size:12px;")
        layout.addWidget(intro)

        self._hints_browser = QTextBrowser()
        self._hints_browser.setFrameShape(QFrame.Shape.NoFrame)
        self._hints_browser.setOpenExternalLinks(False)
        self._hints_browser.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._hints_browser.setMaximumHeight(140)
        self._hints_browser.setStyleSheet(
            """
            QTextBrowser {
                background: #f8fafc;
                border-radius: 8px;
                padding: 10px;
                font-size: 12px;
                color: #1f2937;
            }
            """
        )
        layout.addWidget(self._hints_browser)

    def set_parameter_specs(
        self,
        mechanism_type: str,
        specs: Iterable[ParameterSpec],
        values: dict[str, float],
    ) -> None:
        for ctrl in self._dimension_controls.values():
            ctrl.slider.deleteLater()
            ctrl.spinbox.deleteLater()
            ctrl.label.deleteLater()
        self._dimension_controls.clear()
        clear_layout(self._dimensions_placeholder_layout)

        for spec in specs:
            min_value, max_value = _finite_range(spec.min_value, spec.max_value, 0.0, 1.0)
            default_value = max(min_value, min(max_value, _finite_float(spec.default_value, min_value)))
            initial_value = max(
                min_value,
                min(max_value, _finite_float(values.get(spec.key, default_value), default_value)),
            )
            widget = QWidget()
            widget_layout = QVBoxLayout(widget)
            widget_layout.setContentsMargins(0, 0, 0, 0)
            widget_layout.setSpacing(4)

            header_row = QHBoxLayout()
            label = QLabel(spec.label)
            label.setWordWrap(True)
            header_row.addWidget(label)

            value_spin = QDoubleSpinBox()
            value_spin.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
            value_spin.setKeyboardTracking(False)
            header_row.addWidget(value_spin)
            widget_layout.addLayout(header_row)

            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setCursor(Qt.CursorShape.PointingHandCursor)
            widget_layout.addWidget(slider)

            unit_lower = (spec.unit or "").lower()
            is_length = unit_lower in {"mm", "millimeter", "millimeters", "inch", "inches"}

            control = _DimensionControl(
                spec=spec,
                slider=slider,
                spinbox=value_spin,
                label=label,
                min_unit=spec.min_value,
                max_unit=spec.max_value,
                step_unit=spec.step if spec.step > 0 else 1.0,
                current_unit=self._unit_system,
                value_mm=initial_value,
                is_length=is_length,
                on_value_changed=self._emit_dimension_change,
            )
            control.configure_unit(self._unit_system)
            control.set_value_mm(initial_value)
            slider.valueChanged.connect(
                lambda value, ctl=control: ctl.handle_slider_change(value)
            )
            value_spin.valueChanged.connect(
                lambda value, ctl=control: ctl.handle_spinbox_change(value)
            )

            self._dimension_controls[spec.key] = control
            self._dimensions_placeholder_layout.addWidget(widget)

        self._dimensions_placeholder_layout.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

    def set_driver_options(self, options: Iterable[str], selected_index: int = 0) -> None:
        clear_layout(self._driver_container)
        self._driver_buttons.clear()
        self._driver_group.deleteLater()
        self._driver_group = QButtonGroup(self)
        self._driver_group.setExclusive(True)
        for label in options:
            if label is None:
                continue
            label_text = str(label).strip()
            if not label_text:
                continue
            idx = len(self._driver_buttons)
            radio = QRadioButton(label_text)
            radio.setCursor(Qt.CursorShape.PointingHandCursor)
            self._driver_group.addButton(radio, idx)
            self._driver_container.addWidget(radio)
            self._driver_buttons[idx] = radio
        if selected_index in self._driver_buttons:
            self._driver_buttons[selected_index].setChecked(True)

        self._driver_group.idClicked.connect(self._on_driver_changed)

    def set_linkage_type(self, link_count: int) -> None:
        if button := self._linkage_buttons.get(link_count):
            button.setChecked(True)

    def set_coupler_options(self, options: Iterable[str], current: str | None = None) -> None:
        if self._coupler_combo is None:
            return
        with blocked_signals(self._coupler_combo):
            self._coupler_combo.clear()
            for option in options:
                if option is None:
                    continue
                option_text = str(option).strip()
                if option_text:
                    self._coupler_combo.addItem(option_text)
            if current:
                index = self._coupler_combo.findText(current)
                if index >= 0:
                    self._coupler_combo.setCurrentIndex(index)

    def set_follower_positions(self, options: Iterable[str], current: str | None = None) -> None:
        if self._follower_combo is None:
            return
        with blocked_signals(self._follower_combo):
            self._follower_combo.clear()
            for option in options:
                if option is None:
                    continue
                option_text = str(option).strip()
                if option_text:
                    self._follower_combo.addItem(option_text)
            if current:
                index = self._follower_combo.findText(current)
                if index >= 0:
                    self._follower_combo.setCurrentIndex(index)

    def set_hints(self, hints: Iterable[str]) -> None:
        if self._hints_browser is None:
            return
        limited = list(hints)[:2]
        if not limited:
            self._hints_browser.setHtml("<p style='color:#6b7280;'>Hints appear here based on selected mechanism.</p>")
            return
        bullets = "".join(f"<li>{html.escape(str(hint))}</li>" for hint in limited)
        html_content = f"""
        <ul style="margin:0; padding-left:16px; color:#1f2937;">
            {bullets}
        </ul>
        <p style="margin-top:8px; color:#2563eb; font-size:11px;">Open the info panel for full context →</p>
        """
        self._hints_browser.setHtml(html_content)

    def apply_content(self, content: MechanismContent | None) -> None:
        if content is None:
            self.set_hints([])
            return
        hints: list[str] = []
        if content.goal:
            hints.append(content.goal)
        if content.advantages:
            hints.append(f"Advantage: {content.advantages[0]}")
        if content.cautions:
            hints.append(f"Caution: {content.cautions[0]}")
        self.set_hints(hints)

    def set_status_text(self, text: str, color: str) -> None:
        if not self._status_label:
            return
        self._status_label.setText(text)
        self._status_label.setStyleSheet(f"color: {color}; font-weight: 600;")

    def current_unit(self) -> UnitSystem:
        return self._unit_system

    def _set_unit(self, unit: UnitSystem) -> None:
        if unit == self._unit_system:
            return
        self._unit_system = unit
        for control in self._dimension_controls.values():
            control.configure_unit(unit)
        self.unit_changed.emit(unit.value)

    def _emit_dimension_change(self, key: str, value_mm: float) -> None:
        self.parameter_changed.emit(key, value_mm)

    def _on_linkage_type_changed(self, value: int) -> None:
        self.linkage_type_changed.emit(value)

    def _on_driver_changed(self, index: int) -> None:
        self.driver_index_changed.emit(index)

    def _on_coupler_point_changed(self, text: str) -> None:
        self.coupler_point_changed.emit(text)

    def _on_follower_position_changed(self, text: str) -> None:
        self.follower_position_changed.emit(text)
