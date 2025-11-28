"""
Mechanism Generation Service - Application Layer

Orchestrates mechanism generation from candidates, handling the coordination
between domain services without UI concerns.

Design Pattern: Application Service (DDD)
Architecture: Hexagonal - Application Layer
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from PyQt6.QtGui import QPainterPath


@dataclass
class MechanismGenerationResult:
    """Result of mechanism generation operation."""

    success: bool
    mechanism_id: str | None = None
    layer_data: dict[str, Any] | None = None
    error_message: str | None = None


@dataclass
class MechanismGenerationContext:
    """Context for mechanism generation."""

    selected_part_name: str
    target_path: "QPainterPath | None"
    candidate_data: dict[str, Any]
    parts_data: dict[str, Any] = field(default_factory=dict)
    skeleton_cache: dict[str, Any] | None = None


class MechanismGenerationService:
    """
    Orchestrates mechanism generation from candidates.

    This is an APPLICATION layer service that coordinates:
    - Layer data creation from candidates
    - Coupler joint verification and adjustment
    - Mechanism instantiation

    Does NOT contain:
    - Qt/UI code (presentation layer)
    - Direct mechanism computation (domain layer)
    - Visual item management (presentation layer)
    """

    def __init__(self) -> None:
        """Initialize service."""
        # Callbacks for domain/infrastructure operations (injected)
        self._create_layer_data_fn: Callable[..., dict] | None = None
        self._verify_coupler_fn: Callable[[dict, dict, dict | None], bool] | None = None
        self._adjust_mechanism_fn: Callable[[dict, dict, dict | None], bool] | None = None
        self._extract_key_points_fn: Callable[[dict, str], dict] | None = None
        self._convert_params_fn: Callable[[dict, str], dict] | None = None

    def configure_callbacks(
        self,
        *,
        create_layer_data: Callable[..., dict],
        verify_coupler: Callable[[dict, dict, dict | None], bool] | None = None,
        adjust_mechanism: Callable[[dict, dict, dict | None], bool] | None = None,
        extract_key_points: Callable[[dict, str], dict] | None = None,
        convert_params: Callable[[dict, str], dict] | None = None,
    ) -> None:
        """
        Configure callbacks for domain operations.

        Args:
            create_layer_data: Function to create layer data from candidate
            verify_coupler: Function to verify coupler joint connection
            adjust_mechanism: Function to adjust mechanism to target joint
            extract_key_points: Function to extract key points from simulation
            convert_params: Function to convert JSON params to internal format
        """
        self._create_layer_data_fn = create_layer_data
        self._verify_coupler_fn = verify_coupler
        self._adjust_mechanism_fn = adjust_mechanism
        self._extract_key_points_fn = extract_key_points
        self._convert_params_fn = convert_params

    def generate_mechanism(
        self,
        context: MechanismGenerationContext,
    ) -> MechanismGenerationResult:
        """
        Generate a mechanism from candidate data.

        Args:
            context: Generation context with candidate and part info

        Returns:
            MechanismGenerationResult with layer data or error
        """
        if not self._create_layer_data_fn:
            return MechanismGenerationResult(
                success=False,
                error_message="Layer data creation not configured"
            )

        try:
            # Create layer data via instantiation service
            layer_data = self._create_layer_data_fn(
                candidate_data=context.candidate_data,
                selected_part_name=context.selected_part_name,
                target_path=context.target_path,
                convert_params_fn=self._convert_params_fn,
                extract_key_points_fn=self._extract_key_points_fn,
            )

            if not layer_data:
                return MechanismGenerationResult(
                    success=False,
                    error_message="Failed to create layer data"
                )

            # Verify coupler joint connection
            if self._verify_coupler_fn and context.skeleton_cache:
                self._verify_coupler_fn(
                    layer_data,
                    context.parts_data,
                    context.skeleton_cache,
                )

            # Adjust mechanism to target joint
            if self._adjust_mechanism_fn and context.skeleton_cache:
                self._adjust_mechanism_fn(
                    layer_data,
                    context.parts_data,
                    context.skeleton_cache,
                )

            return MechanismGenerationResult(
                success=True,
                mechanism_id=layer_data.get("id"),
                layer_data=layer_data,
            )

        except Exception as e:
            return MechanismGenerationResult(
                success=False,
                error_message=str(e)
            )

    def prepare_mechanism_visuals(
        self,
        layer_data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Prepare mechanism data for visual generation.

        Args:
            layer_data: Layer data from generation

        Returns:
            Graphics data dict ready for visual factory
        """
        return {
            "mechanism_id": layer_data.get("id"),
            "mechanism_type": layer_data.get("type"),
            **layer_data,
        }
