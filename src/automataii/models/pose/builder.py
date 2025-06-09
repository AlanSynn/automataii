"""Configuration builder for pose detection models."""

from typing import Dict, Any, Optional
from pathlib import Path

from .base import BaseConfig, EvaluationConfig, DataConfig, ChannelConfig
from .dataset import CocoDatasetConfig
from .model import ModelConfig, get_default_model_config
from .pipeline import PipelineConfig, DataLoaderConfig
from .training import TrainingConfig, get_default_training_config


class PoseConfigBuilder:
    """Builder class to construct complete pose detection configuration."""
    
    def __init__(self):
        """Initialize with default configurations."""
        self.base_config = BaseConfig()
        self.eval_config = EvaluationConfig()
        self.data_config = DataConfig()
        self.channel_config = ChannelConfig()
        self.model_config = get_default_model_config()
        self.training_config = get_default_training_config()
        self.dataloader_config = DataLoaderConfig()
        
    def set_work_dir(self, work_dir: str) -> "PoseConfigBuilder":
        """Set working directory."""
        self.base_config.work_dir = work_dir
        return self
    
    def set_annotation_files(
        self,
        train_ann_file: str,
        val_ann_file: str,
        test_ann_file: Optional[str] = None
    ) -> "PoseConfigBuilder":
        """Set annotation file paths."""
        self.train_ann_file = train_ann_file
        self.val_ann_file = val_ann_file
        self.test_ann_file = test_ann_file or val_ann_file
        return self
    
    def set_bbox_file(self, bbox_file: str) -> "PoseConfigBuilder":
        """Set bounding box file path."""
        self.data_config.bbox_file = bbox_file
        return self
    
    def build(self) -> Dict[str, Any]:
        """Build the complete configuration dictionary."""
        # Get dataset info
        dataset_info = CocoDatasetConfig.get_dataset_info()
        
        # Build data configuration
        data_cfg = {
            "image_size": self.data_config.image_size,
            "heatmap_size": self.data_config.heatmap_size,
            "num_output_channels": self.data_config.num_output_channels,
            "num_joints": self.data_config.num_joints,
            "dataset_channel": self.data_config.dataset_channel,
            "inference_channel": self.data_config.inference_channel,
            "soft_nms": self.data_config.soft_nms,
            "nms_thr": self.data_config.nms_thr,
            "oks_thr": self.data_config.oks_thr,
            "vis_thr": self.data_config.vis_thr,
            "use_gt_bbox": self.data_config.use_gt_bbox,
            "det_bbox_thr": self.data_config.det_bbox_thr,
            "bbox_file": self.data_config.bbox_file,
        }
        
        # Build complete configuration
        config = {
            # Base configuration
            "checkpoint_config": {"interval": self.base_config.checkpoint_interval},
            "log_config": {
                "interval": self.base_config.log_interval,
                "hooks": self.base_config.log_hooks
            },
            "log_level": self.base_config.log_level,
            "load_from": self.base_config.load_from,
            "resume_from": self.base_config.resume_from,
            "dist_params": {"backend": self.base_config.dist_backend},
            "workflow": self.base_config.workflow,
            "opencv_num_threads": self.base_config.opencv_num_threads,
            "mp_start_method": self.base_config.mp_start_method,
            
            # Dataset info
            "dataset_info": dataset_info,
            
            # Evaluation
            "evaluation": {
                "interval": self.eval_config.interval,
                "metric": self.eval_config.metric,
                "save_best": self.eval_config.save_best
            },
            
            # Training configuration
            **self.training_config.to_dict(),
            
            # Channel configuration
            "channel_cfg": {
                "num_output_channels": self.channel_config.num_output_channels,
                "dataset_joints": self.channel_config.dataset_joints,
                "dataset_channel": self.channel_config.dataset_channel,
                "inference_channel": self.channel_config.inference_channel,
            },
            
            # Model
            "model": self.model_config,
            
            # Data configuration
            "data_cfg": data_cfg,
            
            # Pipelines
            "train_pipeline": PipelineConfig.get_train_pipeline(),
            "val_pipeline": PipelineConfig.get_val_pipeline(),
            "test_pipeline": PipelineConfig.get_test_pipeline(),
            
            # Data loaders
            "data": {
                **self.dataloader_config.to_dict(),
                "train": self._build_dataset_config("train", self.train_ann_file, data_cfg),
                "val": self._build_dataset_config("val", self.val_ann_file, data_cfg),
                "test": self._build_dataset_config("test", self.test_ann_file, data_cfg),
            },
            
            # Work directory
            "work_dir": self.base_config.work_dir,
        }
        
        return config
    
    def _build_dataset_config(
        self,
        split: str,
        ann_file: str,
        data_cfg: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build dataset configuration for a specific split."""
        pipeline = {
            "train": PipelineConfig.get_train_pipeline(),
            "val": PipelineConfig.get_val_pipeline(),
            "test": PipelineConfig.get_test_pipeline(),
        }[split]
        
        return {
            "type": "TopDownCocoDataset",
            "img_prefix": "",
            "data_cfg": data_cfg,
            "pipeline": pipeline,
            "dataset_info": CocoDatasetConfig.get_dataset_info(),
            "ann_file": ann_file,
        }