"""
Tests for mechanism registry.
"""

import pytest
from automataii.domain.mechanisms.core.protocols import Mechanism
from automataii.domain.mechanisms.core.state import MechanismState
from automataii.domain.mechanisms.catalog.registry import (
    MechanismRegistry,
    MechanismNotFoundError,
    get_mechanism,
    list_mechanism_types,
)


class MockMechanism:
    """Mock mechanism for testing."""

    @property
    def mechanism_type(self) -> str:
        return "mock"

    @property
    def required_parameters(self) -> frozenset[str]:
        return frozenset({"param1", "param2"})

    def compute_state(self, parameters: dict[str, float], input_angle: float) -> MechanismState:
        return MechanismState(
            positions={"joint_1": (0.0, 0.0)},
            velocities={"joint_1": (0.0, 0.0)},
        )

    def validate_parameters(self, parameters: dict[str, float]) -> None:
        missing = self.required_parameters - parameters.keys()
        if missing:
            raise ValueError(f"Missing parameters: {missing}")


class AnotherMockMechanism:
    """Another mock mechanism for testing."""

    @property
    def mechanism_type(self) -> str:
        return "another_mock"

    @property
    def required_parameters(self) -> frozenset[str]:
        return frozenset({"param_x"})

    def compute_state(self, parameters: dict[str, float], input_angle: float) -> MechanismState:
        return MechanismState(
            positions={"joint_1": (1.0, 1.0)},
            velocities={"joint_1": (1.0, 1.0)},
        )

    def validate_parameters(self, parameters: dict[str, float]) -> None:
        pass


class TestMechanismRegistry:
    def setup_method(self):
        self.registry = MechanismRegistry.get_instance()
        self.registry._mechanisms.clear()

    def test_singleton_pattern(self):
        registry1 = MechanismRegistry.get_instance()
        registry2 = MechanismRegistry.get_instance()
        assert registry1 is registry2

    def test_register_and_get(self):
        self.registry.register("mock", MockMechanism)
        mechanism = self.registry.get("mock")
        assert isinstance(mechanism, MockMechanism)
        assert mechanism.mechanism_type == "mock"

    def test_register_multiple(self):
        self.registry.register("mock", MockMechanism)
        self.registry.register("another_mock", AnotherMockMechanism)

        mock1 = self.registry.get("mock")
        mock2 = self.registry.get("another_mock")

        assert isinstance(mock1, MockMechanism)
        assert isinstance(mock2, AnotherMockMechanism)

    def test_get_nonexistent_raises_error(self):
        with pytest.raises(MechanismNotFoundError) as exc_info:
            self.registry.get("nonexistent")

        assert "nonexistent" in str(exc_info.value)
        assert "Available types" in str(exc_info.value)

    def test_list_types_empty(self):
        types = self.registry.list_types()
        assert types == []

    def test_list_types_with_mechanisms(self):
        self.registry.register("mock", MockMechanism)
        self.registry.register("another_mock", AnotherMockMechanism)

        types = self.registry.list_types()
        assert set(types) == {"mock", "another_mock"}

    def test_is_registered_true(self):
        self.registry.register("mock", MockMechanism)
        assert self.registry.is_registered("mock") is True

    def test_is_registered_false(self):
        assert self.registry.is_registered("nonexistent") is False

    def test_register_overwrites_with_warning(self, caplog):
        self.registry.register("mock", MockMechanism)
        self.registry.register("mock", AnotherMockMechanism)

        mechanism = self.registry.get("mock")
        assert isinstance(mechanism, AnotherMockMechanism)

        assert any("already registered" in record.message for record in caplog.records)

    def test_get_instantiates_new_object(self):
        self.registry.register("mock", MockMechanism)

        mechanism1 = self.registry.get("mock")
        mechanism2 = self.registry.get("mock")

        assert mechanism1 is not mechanism2
        assert isinstance(mechanism1, MockMechanism)
        assert isinstance(mechanism2, MockMechanism)


class TestConvenienceFunctions:
    def setup_method(self):
        registry = MechanismRegistry.get_instance()
        registry._mechanisms.clear()
        registry.register("mock", MockMechanism)
        registry.register("another_mock", AnotherMockMechanism)

    def test_get_mechanism(self):
        mechanism = get_mechanism("mock")
        assert isinstance(mechanism, MockMechanism)

    def test_get_mechanism_not_found(self):
        with pytest.raises(MechanismNotFoundError):
            get_mechanism("nonexistent")

    def test_list_mechanism_types(self):
        types = list_mechanism_types()
        assert set(types) == {"mock", "another_mock"}
