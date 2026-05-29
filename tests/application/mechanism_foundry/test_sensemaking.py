import math

from automataii.application.mechanism_foundry import (
    FoundrySensemakingEvent,
    SensemakingParameterChange,
    SensemakingPreviewSnapshot,
    SensemakingService,
)
from automataii.application.mechanism_foundry.controller import MECHANISM_CONFIGS


def test_four_bar_input_rule_explains_one_part_one_consequence():
    service = SensemakingService()

    rule = service.rule_for("fourbar", "input_link")

    assert rule.mechanism_type == "four_bar"
    assert "input crank" in rule.role.lower()
    assert "Joint A" in rule.effect_label
    assert "hole" in rule.build_hint


def test_unknown_rule_uses_safe_teachable_fallback():
    service = SensemakingService()

    rule = service.rule_for("unknown", "mystery")

    assert rule.confidence == "unknown"
    assert "one change" in rule.build_hint.lower()
    assert "which point" in rule.prompt.lower()


def test_every_visible_foundry_parameter_has_specific_rule():
    service = SensemakingService()

    missing = [
        (mechanism_type, spec.key)
        for mechanism_type, config in MECHANISM_CONFIGS.items()
        for spec in config.parameter_specs
        if service.rule_for(mechanism_type, spec.key).confidence == "unknown"
    ]

    assert missing == []


def test_build_context_creates_baseline_for_students_and_teachers():
    context = SensemakingService.build_context(
        "four_bar",
        selected_motion_point_key="joint_b",
        current_positions={"A": (10.0, 20.0), "B": (30.0, 40.0)},
    )

    assert context.change is None
    assert context.change_line.startswith("Pick one slider")
    assert "Joint B" in context.watch_line
    assert "Joint A" in context.evidence_line
    assert "Ask:" in context.teacher_prompt


def test_build_context_uses_previous_and_current_point_snapshots():
    change = SensemakingParameterChange(
        parameter_key="input_link",
        parameter_label="Input link",
        before_value="40 mm",
        after_value="65 mm",
    )

    context = SensemakingService.build_context(
        "four_bar",
        selected_motion_point_key="joint_b",
        parameter_change=change,
        current_positions={"A": (0.0, 0.0), "B": (30.0, 40.0)},
        previous_positions={"A": (0.0, 0.0), "B": (0.0, 0.0)},
    )

    assert context.change_line == "Input link: 40 mm → 65 mm"
    assert "Joint B moved about 50 mm" in context.evidence_line
    assert "larger or smaller circle" in context.effect_line


def test_pending_preview_snapshot_does_not_report_stale_movement():
    change = SensemakingParameterChange(
        parameter_key="input_link",
        parameter_label="Input link",
        before_value="40 mm",
        after_value="65 mm",
    )

    context = SensemakingService.build_context(
        "four_bar",
        selected_motion_point_key="joint_b",
        parameter_change=change,
        preview_snapshot=SensemakingPreviewSnapshot(
            current_parameters={"input_link": 65.0},
            current_positions={"A": (0.0, 0.0), "B": (30.0, 40.0)},
            previous_positions={"A": (0.0, 0.0), "B": (0.0, 0.0)},
            geometry_pending=True,
        ),
    )

    assert context.evidence_pending is True
    assert "updating" in context.evidence_line
    assert "moved about" not in context.evidence_line


def test_motion_point_snapshots_share_selector_metadata_source():
    options = SensemakingService.motion_point_options_for("four_bar")

    context = SensemakingService.build_context(
        "four_bar",
        selected_motion_point_key="joint_b",
        current_positions={"A": (10.0, 20.0), "B": (30.0, 40.0)},
    )

    assert {snapshot.key for snapshot in context.point_snapshots} == {
        option.state_key for option in options
    }
    assert "Joint B" in context.evidence_line


def test_build_context_moves_gear_and_slider_evidence_out_of_view():
    gear_context = SensemakingService.build_context(
        "gear_train",
        current_parameters={"gear1_teeth": 12.0, "gear2_teeth": 24.0},
    )
    slider_context = SensemakingService.build_context(
        "slider_crank",
        current_parameters={"crank_length": 80.0, "rod_length": 140.0},
    )

    assert "Ratio 12:24" in gear_context.evidence_line
    assert "driven gear" in gear_context.watch_line
    assert "Estimated stroke" in slider_context.evidence_line


def test_value_formatting_keeps_panel_learner_friendly():
    service = SensemakingService()

    assert service.format_value(40.0, "mm") == "40 mm"
    assert service.format_value(40.25, "mm") == "40.2 mm"
    assert service.format_value(math.nan, "mm") == "—"
    assert service.format_value("joint_b") == "joint_b"


def test_describe_change_combines_before_after_and_motion_effect():
    service = SensemakingService()
    rule = service.rule_for("four_bar", "input_link")
    event = FoundrySensemakingEvent(
        mechanism_type="four_bar",
        parameter_key="input_link",
        parameter_label="Input link",
        before_value="40 mm",
        after_value="60 mm",
        selected_motion_point="Joint B (Output)",
        evidence_summary="Joint B trace widened.",
    )

    text = service.describe_change(rule, event)

    assert "Input link: 40 mm → 60 mm" in text
    assert "Joint A" in text
