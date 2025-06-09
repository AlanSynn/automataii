"""Configuration builder for creating complete pose detection configs."""

from typing import Dict, Any, Optional

from .base import PoseConfig, RuntimeConfig, DistributedConfig
from .dataset import CocoDatasetInfo, DataConfig, ChannelConfig
from .model import ModelConfig
from .pipeline import PipelineConfig
from .training import TrainingConfig


class PoseConfigBuilder:
    """Builder for creating complete pose detection configurations."""
    
    @staticmethod
    def build_default_config() -> Dict[str, Any]:
        """Build default pose detection configuration."""
        # Create components
        runtime = RuntimeConfig()
        distributed = DistributedConfig()
        model = ModelConfig()
        training = TrainingConfig()
        dataset_info = CocoDatasetInfo()
        data_cfg = DataConfig()
        channel_cfg = ChannelConfig()
        
        # Build pipelines
        train_pipeline = PipelineConfig.create_train_pipeline()
        val_pipeline = PipelineConfig.create_val_pipeline()
        test_pipeline = PipelineConfig.create_test_pipeline()
        
        # Construct complete configuration dictionary
        config = {
            # Runtime settings
            "checkpoint_config": dict(interval=runtime.checkpoint_interval),
            "log_config": dict(
                interval=runtime.log_interval,
                hooks=[dict(type="TextLoggerHook")]
            ),
            "log_level": runtime.log_level,
            "load_from": runtime.load_from,
            "resume_from": runtime.resume_from,
            "dist_params": dict(backend=distributed.backend),
            "workflow": [("train", 1)],
            "opencv_num_threads": runtime.opencv_num_threads,
            "mp_start_method": runtime.mp_start_method,
            
            # Model
            "model": model.to_dict(),
            
            # Training
            "optimizer": training.optimizer.to_dict(),
            "optimizer_config": dict(grad_clip=training.optimizer_config.grad_clip),
            "lr_config": training.lr_config.to_dict(),
            "total_epochs": training.total_epochs,
            
            # Evaluation
            "evaluation": training.evaluation.to_dict(),
            
            # Dataset info
            "dataset_info": dataset_info.to_dict(),
            
            # Data configuration
            "data_cfg": data_cfg.to_dict(),
            "channel_cfg": channel_cfg.to_dict(),
            
            # Pipelines
            "train_pipeline": train_pipeline.to_list(),
            "val_pipeline": val_pipeline.to_list(),
            "test_pipeline": test_pipeline.to_list(),
            
            # Data loaders
            "data": {
                "samples_per_gpu": training.data_loader.samples_per_gpu,
                "workers_per_gpu": training.data_loader.workers_per_gpu,
                "val_dataloader": dict(samples_per_gpu=training.data_loader.val_samples_per_gpu),
                "test_dataloader": dict(samples_per_gpu=training.data_loader.test_samples_per_gpu),
            }
        }
        
        return config
    
    @staticmethod
    def build_dataset_config(
        dataset_type: str = "TopDownCocoDataset",
        img_prefix: str = "",
        ann_file: str = "",
        data_cfg: Optional[DataConfig] = None,
        dataset_info: Optional[CocoDatasetInfo] = None,
        pipeline: Optional[PipelineConfig] = None
    ) -> Dict[str, Any]:
        """Build dataset configuration."""
        if data_cfg is None:
            data_cfg = DataConfig()
        if dataset_info is None:
            dataset_info = CocoDatasetInfo()
        if pipeline is None:
            pipeline = PipelineConfig.create_train_pipeline()
        
        return {
            "type": dataset_type,
            "img_prefix": img_prefix,
            "ann_file": ann_file,
            "data_cfg": data_cfg.to_dict(),
            "dataset_info": dataset_info.to_dict(),
            "pipeline": pipeline.to_list()
        }