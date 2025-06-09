"""Training configuration for pose detection."""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

from .base import BaseConfig


@dataclass
class OptimizerConfig(BaseConfig):
    """Optimizer configuration."""
    type: str = "Adam"
    lr: float = 0.0005
    # Additional optimizer parameters
    params: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        result = {"type": self.type, "lr": self.lr}
        result.update(self.params)
        return result


@dataclass
class OptimizerClipConfig(BaseConfig):
    """Gradient clipping configuration."""
    grad_clip: Optional[Dict[str, Any]] = None


@dataclass
class LRSchedulerConfig(BaseConfig):
    """Learning rate scheduler configuration."""
    policy: str = "step"
    warmup: str = "linear"
    warmup_iters: int = 500
    warmup_ratio: float = 0.001
    step: List[int] = field(default_factory=lambda: [170, 500])
    # Additional scheduler parameters
    params: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        result = {
            "policy": self.policy,
            "warmup": self.warmup,
            "warmup_iters": self.warmup_iters,
            "warmup_ratio": self.warmup_ratio,
            "step": self.step
        }
        result.update(self.params)
        return result


@dataclass
class EvaluationConfig(BaseConfig):
    """Evaluation configuration."""
    interval: int = 1
    metric: str = "mAP"
    save_best: str = "AP"
    # Additional evaluation parameters
    params: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        result = {
            "interval": self.interval,
            "metric": self.metric,
            "save_best": self.save_best
        }
        result.update(self.params)
        return result


@dataclass
class DataLoaderConfig(BaseConfig):
    """Data loader configuration."""
    samples_per_gpu: int = 64
    workers_per_gpu: int = 2
    val_samples_per_gpu: int = 32
    test_samples_per_gpu: int = 32


@dataclass
class TrainingConfig(BaseConfig):
    """Complete training configuration."""
    total_epochs: int = 1000
    optimizer: OptimizerConfig = field(default_factory=OptimizerConfig)
    optimizer_config: OptimizerClipConfig = field(default_factory=OptimizerClipConfig)
    lr_config: LRSchedulerConfig = field(default_factory=LRSchedulerConfig)
    evaluation: EvaluationConfig = field(default_factory=EvaluationConfig)
    data_loader: DataLoaderConfig = field(default_factory=DataLoaderConfig)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format expected by MMPose."""
        return {
            "total_epochs": self.total_epochs,
            "optimizer": self.optimizer.to_dict(),
            "optimizer_config": dict(grad_clip=self.optimizer_config.grad_clip),
            "lr_config": self.lr_config.to_dict(),
            "evaluation": self.evaluation.to_dict(),
            "data": dict(
                samples_per_gpu=self.data_loader.samples_per_gpu,
                workers_per_gpu=self.data_loader.workers_per_gpu,
                val_dataloader=dict(samples_per_gpu=self.data_loader.val_samples_per_gpu),
                test_dataloader=dict(samples_per_gpu=self.data_loader.test_samples_per_gpu)
            )
        }