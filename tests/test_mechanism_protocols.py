"""
Tests for mechanism protocols.

Note: MechanismRenderer is a concrete class in presentation layer, not a Protocol.
Protocol tests only apply to Mechanism which is defined in domain.mechanisms.core.protocols.
"""

import pytest
from automataii.domain.mechanisms.core.protocols import Mechanism
from automataii.domain.mechanisms.core.state import MechanismState, RenderConfig


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


class TestMechanismRendererClass:
    """
    MechanismRenderer is a concrete class in the presentation layer.
    These tests verify its basic functionality rather than Protocol behavior.
    """

    def test_renderer_import(self):
        """Verify MechanismRenderer can be imported from presentation layer."""
        from automataii.presentation.qt.tabs.mechanism_foundry.components.mechanism_renderer import (
            MechanismRenderer,
        )
        assert MechanismRenderer is not None

    def test_renderer_has_render_method(self):
        """Verify MechanismRenderer class has render_mechanism method."""
        from automataii.presentation.qt.tabs.mechanism_foundry.components.mechanism_renderer import (
            MechanismRenderer,
        )
        assert hasattr(MechanismRenderer, "render_mechanism")
        assert callable(getattr(MechanismRenderer, "render_mechanism", None))
