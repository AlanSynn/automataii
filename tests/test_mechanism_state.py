"""
Tests for mechanism state dataclasses.

Note: The domain layer uses pure Python types (tuples) instead of Qt types
to maintain architectural purity and avoid Qt dependencies in the domain.
"""

import math

import pytest

from automataii.domain.mechanisms.core.state import (
    ForceType,
    ForceVector,
    MechanismState,
    RenderConfig,
    SafetyLevel,
    SafetyStatus,
)


class TestSafetyStatus:
    def test_creation(self):
        status = SafetyStatus(
            level=SafetyLevel.WARNING,
            message="High stress detected",
            details={"affected_components": ["linkage_1"]},
        )
        assert status.level == SafetyLevel.WARNING
        assert status.message == "High stress detected"
        assert status.details == {"affected_components": ["linkage_1"]}

    def test_immutability(self):
        status = SafetyStatus(level=SafetyLevel.SAFE)
        with pytest.raises(AttributeError):
            status.level = SafetyLevel.DANGER

    def test_default_message(self):
        status = SafetyStatus(level=SafetyLevel.SAFE)
        assert status.message == ""

    def test_default_details(self):
        status = SafetyStatus(level=SafetyLevel.SAFE)
        assert status.details == {}


class TestForceVector:
    def test_creation(self):
        force = ForceVector(
            position=(10.0, 20.0),
            magnitude=100.0,
            angle=45.0,
            force_type=ForceType.APPLIED,
            color=(255, 0, 0, 255),
        )
        assert force.position == (10.0, 20.0)
        assert force.magnitude == 100.0
        assert force.angle == 45.0
        assert force.force_type == ForceType.APPLIED
        assert force.color == (255, 0, 0, 255)

    def test_immutability(self):
        force = ForceVector(
            position=(0.0, 0.0),
            magnitude=50.0,
            angle=0.0,
            force_type=ForceType.REACTION,
        )
        with pytest.raises(AttributeError):
            force.magnitude = 100.0

    def test_default_color_reaction(self):
        force = ForceVector(
            position=(0.0, 0.0),
            magnitude=50.0,
            angle=0.0,
            force_type=ForceType.REACTION,
        )
        assert force.color == (255, 69, 0, 200)

    def test_default_color_applied(self):
        force = ForceVector(
            position=(0.0, 0.0),
            magnitude=50.0,
            angle=0.0,
            force_type=ForceType.APPLIED,
        )
        assert force.color == (0, 123, 255, 200)

    def test_default_color_constraint(self):
        force = ForceVector(
            position=(0.0, 0.0),
            magnitude=50.0,
            angle=0.0,
            force_type=ForceType.CONSTRAINT,
        )
        assert force.color == (255, 140, 0, 200)

    def test_default_color_friction(self):
        force = ForceVector(
            position=(0.0, 0.0),
            magnitude=50.0,
            angle=0.0,
            force_type=ForceType.FRICTION,
        )
        assert force.color == (128, 128, 128, 200)

    def test_default_color_gravity(self):
        force = ForceVector(
            position=(0.0, 0.0),
            magnitude=50.0,
            angle=0.0,
            force_type=ForceType.GRAVITY,
        )
        assert force.color == (139, 69, 19, 200)

    def test_to_components_zero_angle(self):
        force = ForceVector(
            position=(0.0, 0.0),
            magnitude=100.0,
            angle=0.0,
            force_type=ForceType.APPLIED,
        )
        fx, fy = force.to_components()
        assert math.isclose(fx, 100.0, abs_tol=1e-9)
        assert math.isclose(fy, 0.0, abs_tol=1e-9)

    def test_to_components_90_degrees(self):
        force = ForceVector(
            position=(0.0, 0.0),
            magnitude=100.0,
            angle=90.0,
            force_type=ForceType.APPLIED,
        )
        fx, fy = force.to_components()
        assert math.isclose(fx, 0.0, abs_tol=1e-9)
        assert math.isclose(fy, 100.0, abs_tol=1e-9)

    def test_to_components_45_degrees(self):
        force = ForceVector(
            position=(0.0, 0.0),
            magnitude=100.0,
            angle=45.0,
            force_type=ForceType.APPLIED,
        )
        fx, fy = force.to_components()
        expected = 100.0 / math.sqrt(2)
        assert math.isclose(fx, expected, abs_tol=1e-9)
        assert math.isclose(fy, expected, abs_tol=1e-9)

    def test_to_components_180_degrees(self):
        force = ForceVector(
            position=(0.0, 0.0),
            magnitude=100.0,
            angle=180.0,
            force_type=ForceType.APPLIED,
        )
        fx, fy = force.to_components()
        assert math.isclose(fx, -100.0, abs_tol=1e-9)
        assert math.isclose(fy, 0.0, abs_tol=1e-9)

    def test_to_components_270_degrees(self):
        force = ForceVector(
            position=(0.0, 0.0),
            magnitude=100.0,
            angle=270.0,
            force_type=ForceType.APPLIED,
        )
        fx, fy = force.to_components()
        assert math.isclose(fx, 0.0, abs_tol=1e-9)
        assert math.isclose(fy, -100.0, abs_tol=1e-9)


class TestMechanismState:
    def test_creation_minimal(self):
        state = MechanismState(
            positions={"joint_1": (0.0, 0.0)},
            velocities={"joint_1": (1.0, 0.0)},
        )
        assert state.positions == {"joint_1": (0.0, 0.0)}
        assert state.velocities == {"joint_1": (1.0, 0.0)}
        assert state.forces is None
        assert state.safety_status.level == SafetyLevel.SAFE
        assert state.metadata == {}

    def test_creation_full(self):
        force = ForceVector(
            position=(0.0, 0.0),
            magnitude=50.0,
            angle=0.0,
            force_type=ForceType.APPLIED,
        )
        safety = SafetyStatus(level=SafetyLevel.WARNING, message="Test")
        state = MechanismState(
            positions={"joint_1": (0.0, 0.0)},
            velocities={"joint_1": (1.0, 0.0)},
            forces={"force_1": force},
            safety_status=safety,
            metadata={"test_key": "test_value"},
        )
        assert state.forces == {"force_1": force}
        assert state.safety_status == safety
        assert state.metadata == {"test_key": "test_value"}

    def test_immutability(self):
        state = MechanismState(
            positions={"joint_1": (0.0, 0.0)},
            velocities={"joint_1": (1.0, 0.0)},
        )
        with pytest.raises(AttributeError):
            state.positions = {}

    def test_default_safety_status(self):
        state = MechanismState(
            positions={"joint_1": (0.0, 0.0)},
            velocities={"joint_1": (1.0, 0.0)},
        )
        assert isinstance(state.safety_status, SafetyStatus)
        assert state.safety_status.level == SafetyLevel.SAFE


class TestRenderConfig:
    def test_creation_defaults(self):
        config = RenderConfig()
        assert config.show_forces is True
        assert config.show_safety_zones is True
        assert config.show_labels is True
        assert config.show_trails is False
        assert config.color_scheme == "default"
        assert config.scale == 1.0

    def test_creation_custom(self):
        config = RenderConfig(
            show_forces=False,
            show_safety_zones=True,
            show_labels=False,
            show_trails=True,
            color_scheme="dark",
            scale=2.0,
        )
        assert config.show_forces is False
        assert config.show_safety_zones is True
        assert config.show_labels is False
        assert config.show_trails is True
        assert config.color_scheme == "dark"
        assert config.scale == 2.0

    def test_immutability(self):
        config = RenderConfig()
        with pytest.raises(AttributeError):
            config.scale = 2.0
