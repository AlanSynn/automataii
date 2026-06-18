from __future__ import annotations

from automataii.domain.generation.layout import ScaleNormalizer
from automataii.infrastructure.generation.svg.optimizer import EnhancedMechanismProcessor


def _processor() -> EnhancedMechanismProcessor:
    return EnhancedMechanismProcessor(ScaleNormalizer())


def test_blueprint_optimizer_routes_gear_train_alias_to_real_gear_generator() -> None:
    item = _processor().process_mechanism(
        "gear-train",
        {
            "type": "gear_train",
            "params": {
                "gear1_radius": 18.0,
                "gear2_radius": 21.0,
                "gear1_teeth": 12,
                "gear2_teeth": 14,
            },
            "total_scale_factor": 1.0,
            "real_world_params": {"scale_factor_used": 1.0},
        },
    )

    assert item is not None
    assert "Center:" in item.svg_content
    assert "Standard Gear" not in item.svg_content


def test_blueprint_optimizer_sizes_gear_linkage_from_gear_and_arm_params() -> None:
    width, height = _processor()._calculate_mechanism_dimensions_from_params(  # type: ignore[attr-defined]
        {"gear1_radius": 18.0, "gear2_radius": 21.0, "linkage_arm_length": 80.0},
        "gear_linkage",
    )

    assert width >= 140.0
    assert height >= 64.0


def test_blueprint_optimizer_renders_gear_linkage_cuttable_arm() -> None:
    item = _processor().process_mechanism(
        "gear-linkage",
        {
            "type": "gear_linkage",
            "params": {
                "gear1_radius": 18.0,
                "gear2_radius": 21.0,
                "gear1_teeth": 12,
                "gear2_teeth": 14,
                "linkage_arm_length": 80.0,
            },
            "total_scale_factor": 1.0,
            "real_world_params": {"scale_factor_used": 1.0},
        },
    )

    assert item is not None
    assert "Center:" in item.svg_content
    assert 'data-part-kind="gear-linkage-arm"' in item.svg_content
    assert "Linkage arm: 80.0mm" in item.svg_content
