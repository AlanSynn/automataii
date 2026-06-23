"""
Smart Layout Manager for blueprint layout optimization.

Implements intelligent layout using bin-packing algorithms.
Pure Python implementation - NO Qt or SVG dependencies.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass


@dataclass
class ScaledBounds:
    """
    Represents scaled bounding box in real-world units (mm).

    Used for layout and SVG generation to define areas for rendering.

    Attributes:
        x: Left edge position in mm
        y: Top edge position in mm
        width: Width in mm
        height: Height in mm
    """

    x: float
    y: float
    width: float
    height: float

    def area(self) -> float:
        """Calculate area of bounds."""
        return self.width * self.height

    def center(self) -> tuple[float, float]:
        """Calculate the center point of the bounds."""
        return (self.x + self.width / 2, self.y + self.height / 2)

    def overlaps_with(self, other: ScaledBounds, padding: float = 0.0) -> bool:
        """Check if this bounds overlaps with another (with margin)."""
        return not (
            self.x + self.width + padding <= other.x
            or other.x + other.width + padding <= self.x
            or self.y + self.height + padding <= other.y
            or other.y + other.height + padding <= self.y
        )


@dataclass
class LayoutItem:
    """Represents an item to be laid out in the blueprint."""

    name: str
    bounds: ScaledBounds
    svg_content: str
    item_type: str  # 'part', 'mechanism', 'annotation'
    priority: int = 1  # Higher priority items get better placement
    group: str | None = None


class SmartLayoutManager:
    """
    Intelligent layout manager for non-overlapping blueprint placement.
    Uses modified bin packing algorithm for optimal layout.
    """

    def __init__(self, page_width_mm: float = 600.0, padding_mm: float = 15.0):
        """
        Initialize layout manager.

        Args:
            page_width_mm: Target page width
            padding_mm: Minimum padding between items
        """
        self.page_width_mm = page_width_mm
        self.padding_mm = padding_mm
        self.logger = logging.getLogger(__name__)

    def calculate_optimal_layout(self, items: list[LayoutItem]) -> list[LayoutItem]:
        """
        Calculate optimal non-overlapping layout for all items.

        Args:
            items: List of items to lay out

        Returns:
            List of items with updated positions
        """
        if not items:
            return items

        # Sort items by priority and size (larger, higher priority first)
        sorted_items = sorted(items, key=lambda item: (-item.priority, -item.bounds.area()))

        # Place items using modified bin packing algorithm
        placed_items: list[LayoutItem] = []
        current_y = self.padding_mm
        row_height = 0.0
        current_x = self.padding_mm

        for item in sorted_items:
            # Check if item fits in current row
            if current_x + item.bounds.width <= self.page_width_mm - self.padding_mm:
                # Place in current row
                new_bounds = ScaledBounds(
                    x=current_x,
                    y=current_y,
                    width=item.bounds.width,
                    height=item.bounds.height,
                )

                # Check for overlaps with already placed items
                if not self._has_overlaps(new_bounds, placed_items):
                    item.bounds = new_bounds
                    placed_items.append(item)

                    current_x += item.bounds.width + self.padding_mm
                    row_height = max(row_height, item.bounds.height)
                    continue

            # Move to next row
            current_y += row_height + self.padding_mm
            current_x = self.padding_mm
            row_height = item.bounds.height

            # Place item at start of new row
            item.bounds = ScaledBounds(
                x=current_x,
                y=current_y,
                width=item.bounds.width,
                height=item.bounds.height,
            )
            placed_items.append(item)

            current_x += item.bounds.width + self.padding_mm

        self.logger.info(f"Successfully laid out {len(placed_items)} items")
        return placed_items

    def _has_overlaps(self, bounds: ScaledBounds, placed_items: list[LayoutItem]) -> bool:
        """Check if bounds overlap with any placed items."""
        for item in placed_items:
            if bounds.overlaps_with(item.bounds, self.padding_mm):
                return True
        return False

    def calculate_total_dimensions(self, items: list[LayoutItem]) -> tuple[float, float]:
        """Calculate total blueprint dimensions from placed items."""
        if not items:
            return (self.page_width_mm, 400.0)  # Default size

        max_x = max(item.bounds.x + item.bounds.width for item in items)
        max_y = max(item.bounds.y + item.bounds.height for item in items)

        total_width = max_x + self.padding_mm
        total_height = max_y + self.padding_mm

        return (total_width, total_height)

    def optimize_layout(
        self,
        items: list[LayoutItem],
        target_page_width_mm: float,
        target_page_height_mm: float,
    ) -> tuple[list[LayoutItem], float, float]:
        """
        Optimize layout of items and return positioned items with total dimensions.

        Args:
            items: List of items to lay out
            target_page_width_mm: Target page width in mm
            target_page_height_mm: Target page height in mm

        Returns:
            Tuple of (positioned_items, total_width_mm, total_height_mm)
        """
        # Update page width if different from default
        self.page_width_mm = target_page_width_mm

        # Calculate optimal layout
        positioned_items = self.calculate_optimal_layout(items)

        # Calculate total dimensions
        total_width, total_height = self.calculate_total_dimensions(positioned_items)

        # Ensure minimum dimensions
        total_width = max(total_width, target_page_width_mm)
        total_height = max(total_height, target_page_height_mm)

        return positioned_items, total_width, total_height
