"""Model architecture configuration for pose detection."""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional

from .base import BaseConfig


@dataclass
class BackboneConfig(BaseConfig):
    """Backbone network configuration."""
    type: str = "ResNet"
    depth: int = 50


@dataclass
class LossConfig(BaseConfig):
    """Loss function configuration."""
    type: str = "JointsMSELoss"
    use_target_weight: bool = True


@dataclass
class KeypointHeadConfig(BaseConfig):
    """Keypoint detection head configuration."""
    type: str = "TopdownHeatmapSimpleHead"
    in_channels: int = 2048
    out_channels: int = 17
    loss_keypoint: LossConfig = field(default_factory=LossConfig)


@dataclass
class TestConfig(BaseConfig):
    """Test/inference configuration."""
    flip_test: bool = True
    post_process: str = "default"
    shift_heatmap: bool = True
    modulate_kernel: int = 11


@dataclass
class ModelConfig(BaseConfig):
    """Complete model configuration."""
    type: str = "TopDown"
    pretrained: str = "torchvision://resnet50"
    backbone: BackboneConfig = field(default_factory=BackboneConfig)
    keypoint_head: KeypointHeadConfig = field(default_factory=KeypointHeadConfig)
    train_cfg: Dict[str, Any] = field(default_factory=dict)
    test_cfg: TestConfig = field(default_factory=TestConfig)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format expected by MMPose."""
        return {
            "type": self.type,
            "pretrained": self.pretrained,
            "backbone": dict(type=self.backbone.type, depth=self.backbone.depth),
            "keypoint_head": dict(
                type=self.keypoint_head.type,
                in_channels=self.keypoint_head.in_channels,
                out_channels=self.keypoint_head.out_channels,
                loss_keypoint=dict(
                    type=self.keypoint_head.loss_keypoint.type,
                    use_target_weight=self.keypoint_head.loss_keypoint.use_target_weight
                )
            ),
            "train_cfg": self.train_cfg,
            "test_cfg": dict(
                flip_test=self.test_cfg.flip_test,
                post_process=self.test_cfg.post_process,
                shift_heatmap=self.test_cfg.shift_heatmap,
                modulate_kernel=self.test_cfg.modulate_kernel
            )
        }