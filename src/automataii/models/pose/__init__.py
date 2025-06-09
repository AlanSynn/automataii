"""Pose detection configuration module."""

from .base import PoseConfig
from .dataset import CocoDatasetInfo, DataConfig
from .model import ModelConfig
from .pipeline import PipelineConfig
from .training import TrainingConfig

__all__ = [
    "PoseConfig",
    "CocoDatasetInfo",
    "DataConfig",
    "ModelConfig",
    "PipelineConfig",
    "TrainingConfig",
]