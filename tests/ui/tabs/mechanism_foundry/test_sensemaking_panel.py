import sys

import pytest
from PyQt6.QtWidgets import QApplication, QLabel

from automataii.application.mechanism_foundry import (
    ContentLoader,
    FoundrySensemakingEvent,
    SensemakingParameterChange,
    SensemakingService,
)
from automataii.presentation.qt.tabs.mechanism_foundry.sensemaking_panel import (
    MechanismSensemakingPanel,
)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


def _label_text(panel: MechanismSensemakingPanel, object_name: str) -> str:
    label = panel.findChild(QLabel, object_name)
    assert label is not None
    return label.text()


def test_panel_loads_mechanism_story_and_legacy_text(qapp):
    content = ContentLoader().load_content("four_bar")
    panel = MechanismSensemakingPanel()

    panel.set_content(content, "four_bar", reset_change=True)

    assert "Four" in _label_text(panel, "sensemakingTitleLabel")
    assert "input crank" in _label_text(panel, "sensemakingChainLabel").lower()
    assert "1 · You changed" in _label_text(panel, "changeHeaderLabel")
    legacy_text = panel.legacy_text_display.toPlainText()
    assert "Parts:" in legacy_text
    assert "Motions:" in legacy_text
    assert "Advantages:" in legacy_text
    assert "Limitations:" in legacy_text
    assert "Materials:" in legacy_text
    assert "Build cautions:" in legacy_text


def test_panel_renders_application_context_for_student_and_teacher(qapp):
    panel = MechanismSensemakingPanel()
    context = SensemakingService.build_context(
        "four_bar",
        selected_motion_point_key="joint_b",
        parameter_change=SensemakingParameterChange(
            parameter_key="input_link",
            parameter_label="Input link",
            before_value="40 mm",
            after_value="65 mm",
        ),
        current_positions={"A": (0.0, 0.0), "B": (30.0, 40.0)},
        previous_positions={"A": (0.0, 0.0), "B": (0.0, 0.0)},
    )

    panel.set_context(context)

    assert "Input link: 40 mm → 65 mm" in _label_text(panel, "changeValueLabel")
    assert "Effect:" in _label_text(panel, "consequenceLabel")
    assert "Why:" in _label_text(panel, "principleLabel")
    assert "Joint B moved about 1.97 in" in _label_text(panel, "evidenceLabel")
    assert "2.5 board spaces" in _label_text(panel, "evidenceLabel")
    assert "Teacher prompt:" in _label_text(panel, "promptLabel")


def test_panel_renders_parameter_cause_effect_event(qapp):
    panel = MechanismSensemakingPanel()
    panel.set_content(ContentLoader().load_content("four_bar"), "four_bar", reset_change=True)

    panel.set_change_event(
        FoundrySensemakingEvent(
            mechanism_type="four_bar",
            parameter_key="input_link",
            parameter_label="Input link",
            before_value="40 mm",
            after_value="65 mm",
            selected_motion_point="Joint B (Output)",
            evidence_summary="Joint B trace expanded.",
        )
    )

    assert "Input link: 40 mm → 65 mm" in _label_text(panel, "changeValueLabel")
    assert "input crank" in _label_text(panel, "principleLabel").lower()
    assert "Joint B trace expanded" in _label_text(panel, "evidenceLabel")
    assert "Teacher prompt:" in _label_text(panel, "promptLabel")


def test_panel_resets_stale_change_on_mechanism_switch(qapp):
    panel = MechanismSensemakingPanel()
    panel.set_content(ContentLoader().load_content("four_bar"), "four_bar", reset_change=True)
    panel.set_change_event(
        FoundrySensemakingEvent(
            mechanism_type="four_bar",
            parameter_key="input_link",
            parameter_label="Input link",
            before_value="40 mm",
            after_value="65 mm",
            selected_motion_point="Joint B (Output)",
            evidence_summary="Joint B trace expanded.",
        )
    )

    panel.set_content(
        ContentLoader().load_content("cam_follower"), "cam_follower", reset_change=True
    )

    assert "Input link" not in _label_text(panel, "changeValueLabel")
    assert "Pick one slider" in _label_text(panel, "changeValueLabel")
    assert "cam" in _label_text(panel, "sensemakingChainLabel").lower()
