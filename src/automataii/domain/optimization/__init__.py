"""
Optimization Pipeline and Components

Implements the optimization system from PAPER_IMPL.md for mechanism parameter optimization
and gear train design.
"""

from .pipeline import OptimizationPipeline
from .gear_train_optimizer import GearTrainOptimizer

__all__ = ['OptimizationPipeline', 'GearTrainOptimizer']