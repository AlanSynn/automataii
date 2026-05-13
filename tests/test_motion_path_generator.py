import math

from PyQt6.QtCore import QPointF

from automataii.domain.kinematics.motion_path_generator import MotionPathGenerator


def _constant_output(_mech_type, _params, angle, _layer_data):
    return QPointF(float(angle), float(angle))


def test_motion_path_generator_defaults_invalid_resolution_values():
    generator = MotionPathGenerator(resolution="bad")  # type: ignore[arg-type]

    assert generator._resolution == MotionPathGenerator.DEFAULT_RESOLUTION


def test_generate_sampled_positions_defaults_invalid_num_samples():
    generator = MotionPathGenerator(resolution=3)

    positions = generator.generate_sampled_positions(
        {"type": "4_bar_linkage", "params": {}},
        _constant_output,
        num_samples="bad",  # type: ignore[arg-type]
    )

    assert len(positions) == 3


def test_generate_sampled_positions_rejects_non_finite_points():
    generator = MotionPathGenerator(resolution=3)

    positions = generator.generate_sampled_positions(
        {"type": "4_bar_linkage", "params": {}},
        lambda *_args: QPointF(float("nan"), 0.0),
    )

    assert positions == []


def test_generate_joint_motion_path_rejects_non_finite_points():
    generator = MotionPathGenerator(resolution=3)

    path = generator.generate_joint_motion_path(
        {"type": "4_bar_linkage", "params": {}},
        "joint",
        lambda *_args: QPointF(math.inf, 0.0),
    )

    assert path is None
