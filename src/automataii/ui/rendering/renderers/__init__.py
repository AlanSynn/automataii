"""Concrete visual renderers for different mechanism types.

These renderers implement the Strategy Pattern to eliminate dispatch tables.
They act as Adapters to the existing MechanismVisualsFactory implementation.
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtWidgets import QGraphicsItem

from ..protocol import MechanismVisualRendererProtocol, RenderConfig

__all__ = [
    "FourBarVisualRenderer",
    "FiveBarVisualRenderer",
    "SixBarVisualRenderer",
    "CamVisualRenderer",
    "GearVisualRenderer",
    "PlanetaryGearVisualRenderer",
]


class FourBarVisualRenderer:
    """Visual renderer for 4-bar linkage mechanisms.

    Adapter Pattern: Wraps MechanismVisualsFactory.create_4bar_linkage_visuals()
    to conform to MechanismVisualRendererProtocol.

    Attributes:
        visuals_factory: Legacy factory containing rendering logic
    """

    def __init__(self, visuals_factory: Any) -> None:
        """Initialize renderer with legacy factory.

        Args:
            visuals_factory: Instance of MechanismVisualsFactory
        """
        self.visuals_factory = visuals_factory

    def render(
        self,
        graphics_data: dict[str, Any],
        config: RenderConfig,
    ) -> list[QGraphicsItem]:
        """Render 4-bar linkage visual items.

        Args:
            graphics_data: Mechanism graphics data containing:
                - params: linkage parameters (l1, l2, l3, l4, coupler_point_x/y)
                - full_simulation_data: joint positions
                - transform_params: coordinate transformation function
            config: Rendering configuration (currently unused, for future extensibility)

        Returns:
            List of QGraphicsItem objects (links, joints, pivots, coupler triangle)

        Complexity: O(1) - creates fixed number of visual elements
        """
        transform_func = graphics_data.get("transform_function")
        return self.visuals_factory.create_4bar_linkage_visuals(graphics_data, transform_func)


class FiveBarVisualRenderer:
    """Visual renderer for 5-bar linkage mechanisms.

    Adapter Pattern: Wraps MechanismVisualsFactory.create_5bar_linkage_visuals()
    """

    def __init__(self, visuals_factory: Any) -> None:
        self.visuals_factory = visuals_factory

    def render(
        self,
        graphics_data: dict[str, Any],
        config: RenderConfig,
    ) -> list[QGraphicsItem]:
        """Render 5-bar linkage visual items.

        Args:
            graphics_data: Mechanism graphics data
            config: Rendering configuration

        Returns:
            List of QGraphicsItem objects

        Complexity: O(1)
        """
        transform_func = graphics_data.get("transform_function")
        return self.visuals_factory.create_5bar_linkage_visuals(graphics_data, transform_func)


class SixBarVisualRenderer:
    """Visual renderer for 6-bar linkage mechanisms.

    Adapter Pattern: Wraps MechanismVisualsFactory.create_6bar_linkage_visuals()
    """

    def __init__(self, visuals_factory: Any) -> None:
        self.visuals_factory = visuals_factory

    def render(
        self,
        graphics_data: dict[str, Any],
        config: RenderConfig,
    ) -> list[QGraphicsItem]:
        """Render 6-bar linkage visual items.

        Args:
            graphics_data: Mechanism graphics data
            config: Rendering configuration

        Returns:
            List of QGraphicsItem objects

        Complexity: O(1)
        """
        transform_func = graphics_data.get("transform_function")
        return self.visuals_factory.create_6bar_linkage_visuals(graphics_data, transform_func)


class CamVisualRenderer:
    """Visual renderer for cam-follower mechanisms.

    Adapter Pattern: Wraps MechanismVisualsFactory.create_cam_visuals()
    """

    def __init__(self, visuals_factory: Any) -> None:
        self.visuals_factory = visuals_factory

    def render(
        self,
        graphics_data: dict[str, Any],
        config: RenderConfig,
    ) -> list[QGraphicsItem]:
        """Render cam-follower visual items.

        Args:
            graphics_data: Mechanism graphics data containing:
                - cam_profile_local_points: cam contour in local coords
                - follower position and rod length
                - transform_params: coordinate transformation function
            config: Rendering configuration

        Returns:
            List of QGraphicsItem objects (cam profile, follower, rod)

        Complexity: O(N) where N = number of cam profile points
        """
        transform_func = graphics_data.get("transform_function")
        character_position = graphics_data.get("character_position")
        return self.visuals_factory.create_cam_visuals(
            graphics_data, transform_func, character_position
        )


class GearVisualRenderer:
    """Visual renderer for simple gear pair mechanisms.

    Adapter Pattern: Wraps MechanismVisualsFactory.create_gear_visuals()
    """

    def __init__(self, visuals_factory: Any) -> None:
        self.visuals_factory = visuals_factory

    def render(
        self,
        graphics_data: dict[str, Any],
        config: RenderConfig,
    ) -> list[QGraphicsItem]:
        """Render gear pair visual items.

        Args:
            graphics_data: Mechanism graphics data containing:
                - gear radii, positions
                - tooth count
                - transform_params: coordinate transformation function
            config: Rendering configuration

        Returns:
            List of QGraphicsItem objects (gear circles, teeth, center markers)

        Complexity: O(N) where N = total tooth count
        """
        transform_func = graphics_data.get("transform_function")
        return self.visuals_factory.create_gear_visuals(graphics_data, transform_func)


class PlanetaryGearVisualRenderer:
    """Visual renderer for planetary gear mechanisms.

    Adapter Pattern: Wraps MechanismVisualsFactory.create_planetary_gear_visuals()
    """

    def __init__(self, visuals_factory: Any) -> None:
        self.visuals_factory = visuals_factory

    def render(
        self,
        graphics_data: dict[str, Any],
        config: RenderConfig,
    ) -> list[QGraphicsItem]:
        """Render planetary gear visual items.

        Args:
            graphics_data: Mechanism graphics data containing:
                - sun, planet, ring gear parameters
                - planet count and positions
                - transform_params: coordinate transformation function
            config: Rendering configuration

        Returns:
            List of QGraphicsItem objects (sun, planets, ring, carrier)

        Complexity: O(N*M) where N = planet count, M = teeth per planet
        """
        transform_func = graphics_data.get("transform_function")
        return self.visuals_factory.create_planetary_gear_visuals(graphics_data, transform_func)
