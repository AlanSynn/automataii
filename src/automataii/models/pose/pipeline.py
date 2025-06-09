"""Data pipeline configuration for pose detection."""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

from .base import BaseConfig


@dataclass
class PipelineStep(BaseConfig):
    """Single step in the data pipeline."""
    type: str
    # Additional parameters as needed
    params: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        result = {"type": self.type}
        result.update(self.params)
        return result


@dataclass
class PipelineConfig(BaseConfig):
    """Complete pipeline configuration."""
    steps: List[PipelineStep] = field(default_factory=list)
    
    @classmethod
    def create_train_pipeline(cls) -> "PipelineConfig":
        """Create default training pipeline."""
        return cls(steps=[
            PipelineStep("LoadImageFromFile"),
            PipelineStep("TopDownRandomFlip", {"flip_prob": 0.5}),
            PipelineStep("TopDownHalfBodyTransform", {
                "num_joints_half_body": 8,
                "prob_half_body": 0.3
            }),
            PipelineStep("TopDownGetRandomScaleRotation", {
                "rot_factor": 40,
                "scale_factor": 0.5
            }),
            PipelineStep("TopDownAffine"),
            PipelineStep("ToTensor"),
            PipelineStep("NormalizeTensor", {
                "mean": [0.485, 0.456, 0.406],
                "std": [0.229, 0.224, 0.225]
            }),
            PipelineStep("TopDownGenerateTarget", {"sigma": 2}),
            PipelineStep("Collect", {
                "keys": ["img", "target", "target_weight"],
                "meta_keys": [
                    "image_file", "joints_3d", "joints_3d_visible",
                    "center", "scale", "rotation", "bbox_score", "flip_pairs"
                ]
            })
        ])
    
    @classmethod
    def create_val_pipeline(cls) -> "PipelineConfig":
        """Create default validation pipeline."""
        return cls(steps=[
            PipelineStep("LoadImageFromFile"),
            PipelineStep("TopDownAffine"),
            PipelineStep("ToTensor"),
            PipelineStep("NormalizeTensor", {
                "mean": [0.485, 0.456, 0.406],
                "std": [0.229, 0.224, 0.225]
            }),
            PipelineStep("Collect", {
                "keys": ["img"],
                "meta_keys": [
                    "image_file", "center", "scale", "rotation",
                    "bbox_score", "flip_pairs"
                ]
            })
        ])
    
    @classmethod
    def create_test_pipeline(cls) -> "PipelineConfig":
        """Create default test pipeline."""
        # Test pipeline is same as validation pipeline
        return cls.create_val_pipeline()
    
    def to_list(self) -> List[Dict[str, Any]]:
        """Convert to list format expected by MMPose."""
        return [step.to_dict() for step in self.steps]


def create_pipeline_from_dict(pipeline_dict: List[Dict[str, Any]]) -> PipelineConfig:
    """Create PipelineConfig from dictionary representation."""
    steps = []
    for step_dict in pipeline_dict:
        type_name = step_dict.pop("type")
        steps.append(PipelineStep(type_name, step_dict))
    return PipelineConfig(steps=steps)