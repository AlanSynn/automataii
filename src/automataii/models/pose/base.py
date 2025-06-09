"""Base configuration classes for pose detection."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class BaseConfig:
    """Base configuration class with common functionality."""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        result = {}
        for key, value in self.__dict__.items():
            if isinstance(value, BaseConfig):
                result[key] = value.to_dict()
            elif isinstance(value, list):
                result[key] = [
                    item.to_dict() if isinstance(item, BaseConfig) else item
                    for item in value
                ]
            else:
                result[key] = value
        return result


@dataclass
class RuntimeConfig(BaseConfig):
    """Runtime configuration settings."""
    checkpoint_interval: int = 10
    log_interval: int = 50
    log_level: str = "INFO"
    load_from: Optional[str] = None
    resume_from: Optional[str] = None
    opencv_num_threads: int = 0
    mp_start_method: str = "fork"
    work_dir: Optional[str] = None


@dataclass
class DistributedConfig(BaseConfig):
    """Distributed training configuration."""
    backend: str = "nccl"


@dataclass
class PoseConfig(BaseConfig):
    """Main pose detection configuration."""
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)
    distributed: DistributedConfig = field(default_factory=DistributedConfig)
    workflow: List[tuple] = field(default_factory=lambda: [("train", 1)])
    
    # These will be populated by specific config files
    model: Optional[Dict[str, Any]] = None
    training: Optional[Dict[str, Any]] = None
    data: Optional[Dict[str, Any]] = None
    dataset_info: Optional[Dict[str, Any]] = None