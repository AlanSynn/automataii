"""Unified linkage mechanism with modular strategy and validator pattern.
"""

from __future__ import annotations

from automataii.domain.mechanisms.core.protocols import Mechanism
from automataii.domain.mechanisms.core.state import MechanismState
from automataii.domain.mechanisms.linkages.config import LinkageConfig, LinkageType
from automataii.domain.mechanisms.linkages.strategies.base import LinkageStrategy
from automataii.domain.mechanisms.linkages.strategies.fourbar import FourBarStrategy
from automataii.domain.mechanisms.linkages.strategies.fivebar import FiveBarStrategy
from automataii.domain.mechanisms.linkages.strategies.sixbar import SixBarStrategy
from automataii.domain.mechanisms.linkages.validators.base import LinkageValidator
from automataii.domain.mechanisms.linkages.validators.fourbar import FourBarValidator
from automataii.domain.mechanisms.linkages.validators.fivebar import FiveBarValidator
from automataii.domain.mechanisms.linkages.validators.sixbar import SixBarValidator


class UnifiedLinkageMechanism(Mechanism):
    """Unified linkage mechanism supporting 4/5/6-bar configurations.

    Uses Strategy pattern to dispatch computation based on bar_count parameter.
    Uses Validator pattern for type-specific safety/quality checks.

    Example:
        params = {"bar_count": 4, "ground_link": 100, "input_link": 50, ...}
        mech = UnifiedLinkageMechanism(params)
        state = mech.compute_state(params, input_angle=45.0)
    """

    # Strategy and Validator registries
    _STRATEGIES: dict[int, type[LinkageStrategy]] = {
        4: FourBarStrategy,
        5: FiveBarStrategy,
        6: SixBarStrategy,
    }

    _VALIDATORS: dict[int, type[LinkageValidator]] = {
        4: FourBarValidator,
        5: FiveBarValidator,
        6: SixBarValidator,
    }

    def __init__(self, parameters: dict[str, float] | None = None) -> None:
        """Initialize with bar_count-specific strategy and validator.

        Args:
            parameters: Must include "bar_count" (4, 5, or 6) plus type-specific params

        Raises:
            ValueError: If bar_count is invalid or missing
        """
        params = parameters or {}
        self._bar_count = int(params.get("bar_count", 4))

        if self._bar_count not in self._STRATEGIES:
            raise ValueError(
                f"Unsupported bar_count={self._bar_count}. "
                f"Supported: {sorted(self._STRATEGIES.keys())}"
            )

        # Instantiate strategy and validator
        self._strategy: LinkageStrategy = self._STRATEGIES[self._bar_count]()
        self._validator: LinkageValidator = self._VALIDATORS[self._bar_count]()

    @property
    def mechanism_type(self) -> str:
        """Returns 'linkages' (unified type for all bar counts)."""
        return "linkages"

    @property
    def required_parameters(self) -> frozenset[str]:
        """Dynamic required parameters based on bar_count.

        Returns:
            Union of {bar_count} and strategy-specific parameters
        """
        return frozenset(["bar_count"]) | self._strategy.required_parameters()

    def validate_parameters(self, parameters: dict[str, float]) -> None:
        """Validate required parameters are present and positive.

        Args:
            parameters: Parameter dictionary

        Raises:
            ValueError: If required parameters are missing or invalid
        """
        required = self.required_parameters
        missing = required - parameters.keys()
        if missing:
            raise ValueError(f"Missing required parameters: {missing}")

        # Validate positivity (except bar_count)
        for param in required:
            if param == "bar_count":
                continue
            if parameters[param] <= 0:
                raise ValueError(f"Parameter {param} must be positive, got {parameters[param]}")

    def compute_state(
        self,
        parameters: dict[str, float],
        input_angle: float,
    ) -> MechanismState:
        """Compute linkage state using bar_count-specific strategy.

        Args:
            parameters: Mechanism parameters (must include bar_count)
            input_angle: Input angle in degrees

        Returns:
            MechanismState with positions, forces, safety status, and metadata
        """
        # Compute positions using strategy
        positions = self._strategy.compute_positions(parameters, input_angle)

        # Compute forces (may be None for some strategies)
        forces = self._strategy.compute_forces(positions, parameters, input_angle)

        # Validate safety using validator
        safety = self._validator.validate_safety(parameters, positions, input_angle)

        # Build metadata (linkage config, parameters, etc.)
        metadata = self._build_metadata(parameters, positions, input_angle)

        return MechanismState(
            positions=positions,
            forces=forces,
            safety_status=safety,
            metadata=metadata,
        )

    def _build_metadata(
        self,
        parameters: dict[str, float],
        positions: dict[str, tuple[float, float]],
        input_angle: float,
    ) -> dict[str, object]:
        """Build metadata dictionary for mechanism state.

        Args:
            parameters: Mechanism parameters
            positions: Joint positions
            input_angle: Current input angle

        Returns:
            Metadata dict with linkage_config, bar_count, parameters, etc.
        """
        bar_count = self._bar_count

        # Build LinkageConfig
        link_lengths = self._extract_link_lengths(parameters, bar_count)
        linkage_config = LinkageConfig(
            type=LinkageType(bar_count),
            link_lengths=link_lengths,
            driver_index=1,
        )

        metadata: dict[str, object] = {
            "bar_count": bar_count,
            "input_angle": input_angle,
            "linkage_config": linkage_config,
        }

        # Add strategy-specific metadata
        for key, value in parameters.items():
            if key != "bar_count":
                metadata[key] = value

        return metadata

    @staticmethod
    def _extract_link_lengths(
        parameters: dict[str, float],
        bar_count: int,
    ) -> tuple[float, ...]:
        """Extract link lengths tuple from parameters.

        Args:
            parameters: Parameter dict
            bar_count: Number of bars (4, 5, or 6)

        Returns:
            Tuple of link lengths in mechanism order
        """
        if bar_count == 4:
            return (
                parameters["ground_link"],
                parameters["input_link"],
                parameters["coupler_link"],
                parameters["output_link"],
            )
        elif bar_count == 5:
            return (
                parameters["ground_link"],
                parameters["input_link"],
                parameters["coupler_link"],
                parameters["coupler_link"],  # Floating segments (symmetric)
                parameters["output_link"],
            )
        elif bar_count == 6:
            return (
                parameters["ground_link"],
                parameters["input_link"],
                parameters["coupler_link"],
                parameters["coupler_link"],  # Floating segments
                parameters["output_link"],
                parameters.get("pivot_height", 100.0),  # Rocker (height proxy)
            )
        else:
            return ()
