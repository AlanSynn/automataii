"""
Tests for mechanism protocols.
"""

import pytest
from automataii.mechanisms.core.protocols import Mechanism, MechanismRenderer
from automataii.mechanisms.core.state import MechanismState, RenderConfig


class TestMechanismProtocol:
    def test_protocol_is_runtime_checkable(self):
        # Verify @runtime_checkable decorator works by testing isinstance check
        class MinimalImplementation:
            @property
            def mechanism_type(self) -> str:
                return "test"

            @property
            def required_parameters(self) -> frozenset[str]:
                return frozenset()

            def compute_state(self, parameters, input_angle):
                return MechanismState(positions={})

            def validate_parameters(self, parameters):
                pass

        assert isinstance(MinimalImplementation(), Mechanism)

    def test_valid_implementation(self):
        class ValidMechanism:
            @property
            def mechanism_type(self) -> str:
                return "valid"

            @property
            def required_parameters(self) -> frozenset[str]:
                return frozenset({"param1"})

            def compute_state(
                self, parameters: dict[str, float], input_angle: float
            ) -> MechanismState:
                return MechanismState(
                    positions={"joint": (0.0, 0.0)},
                    velocities={"joint": (0.0, 0.0)},
                )

            def validate_parameters(self, parameters: dict[str, float]) -> None:
                pass

        instance = ValidMechanism()
        assert isinstance(instance, Mechanism)

    def test_missing_mechanism_type(self):
        class InvalidMechanism:
            @property
            def required_parameters(self) -> frozenset[str]:
                return frozenset()

            def compute_state(
                self, parameters: dict[str, float], input_angle: float
            ) -> MechanismState:
                return MechanismState(positions={}, velocities={})

            def validate_parameters(self, parameters: dict[str, float]) -> None:
                pass

        instance = InvalidMechanism()
        assert not isinstance(instance, Mechanism)

    def test_missing_required_parameters(self):
        class InvalidMechanism:
            @property
            def mechanism_type(self) -> str:
                return "invalid"

            def compute_state(
                self, parameters: dict[str, float], input_angle: float
            ) -> MechanismState:
                return MechanismState(positions={}, velocities={})

            def validate_parameters(self, parameters: dict[str, float]) -> None:
                pass

        instance = InvalidMechanism()
        assert not isinstance(instance, Mechanism)

    def test_missing_compute_state(self):
        class InvalidMechanism:
            @property
            def mechanism_type(self) -> str:
                return "invalid"

            @property
            def required_parameters(self) -> frozenset[str]:
                return frozenset()

            def validate_parameters(self, parameters: dict[str, float]) -> None:
                pass

        instance = InvalidMechanism()
        assert not isinstance(instance, Mechanism)

    def test_missing_validate_parameters(self):
        class InvalidMechanism:
            @property
            def mechanism_type(self) -> str:
                return "invalid"

            @property
            def required_parameters(self) -> frozenset[str]:
                return frozenset()

            def compute_state(
                self, parameters: dict[str, float], input_angle: float
            ) -> MechanismState:
                return MechanismState(positions={}, velocities={})

        instance = InvalidMechanism()
        assert not isinstance(instance, Mechanism)


class TestMechanismRendererProtocol:
    def test_protocol_is_runtime_checkable(self):
        # Verify @runtime_checkable decorator works by testing isinstance check
        class MinimalRenderer:
            def render(self, state, scene, config):
                return []

        assert isinstance(MinimalRenderer(), MechanismRenderer)

    def test_valid_implementation(self):
        class ValidRenderer:
            def render(self, state: MechanismState, scene, config: RenderConfig) -> list:
                return []

        instance = ValidRenderer()
        assert isinstance(instance, MechanismRenderer)

    def test_missing_render_method(self):
        class InvalidRenderer:
            pass

        instance = InvalidRenderer()
        assert not isinstance(instance, MechanismRenderer)

    def test_wrong_render_signature(self):
        class InvalidRenderer:
            def render(self) -> list:
                return []

        instance = InvalidRenderer()
        assert isinstance(instance, MechanismRenderer)
