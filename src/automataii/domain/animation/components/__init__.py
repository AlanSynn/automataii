"""
Animation domain extracted components.

This package contains modules extracted from animation domain classes
using the LLM-native refactoring approach.

Extracted Modules:
- InfluenceMapGenerator: Vectorized influence map generation for segmentation
"""

from automataii.domain.animation.components.influence_map_generator import InfluenceMapGenerator

__all__ = [
    "InfluenceMapGenerator",
]
