"""Compatibility module for legacy pose_config.py format."""

from typing import Dict, Any

from .config_builder import PoseConfigBuilder
from .dataset import DataConfig, CocoDatasetInfo
from .pipeline import PipelineConfig


def get_legacy_config() -> Dict[str, Any]:
    """Get configuration in legacy format for backward compatibility."""
    builder = PoseConfigBuilder()
    config = builder.build_default_config()
    
    # Add specific paths from original config
    config["data"]["train"] = builder.build_dataset_config(
        ann_file="/private/home/hjessmith/AD_Consent_Data_workspace/mmpose-180k-workspace/train_size-180000_dev.json"
    )
    config["data"]["val"] = builder.build_dataset_config(
        ann_file="/private/home/hjessmith/AD_Consent_Data_workspace/mmpose-dataset-size_workspace/run_2022-06-09_16:19:59.526334/coco_annos/val0.json",
        pipeline=PipelineConfig.create_val_pipeline()  # Use val pipeline
    )
    config["data"]["test"] = builder.build_dataset_config(
        ann_file="/private/home/hjessmith/AD_Consent_Data_workspace/mmpose-dataset-size_workspace/run_2022-06-09_16:19:59.526334/coco_annos/val0.json",
        pipeline=PipelineConfig.create_test_pipeline()  # Use test pipeline
    )
    
    # Set work_dir
    config["work_dir"] = "/private/home/hjessmith/AD_Consent_Data_workspace/mmpose-180k-workspace/workdir"
    
    # Update bbox_file in data_cfg
    config["data_cfg"]["bbox_file"] = "/private/home/hjessmith/AD_Consent_Data_workspace/mmpose-180k-workspace/train_size-180000_detections.json"
    
    return config


# Export all the variables that were in the original file for compatibility
_config = get_legacy_config()

# Export individual variables
checkpoint_config = _config["checkpoint_config"]
log_config = _config["log_config"]
log_level = _config["log_level"]
load_from = _config["load_from"]
resume_from = _config["resume_from"]
dist_params = _config["dist_params"]
workflow = _config["workflow"]
opencv_num_threads = _config["opencv_num_threads"]
mp_start_method = _config["mp_start_method"]

dataset_info = _config["dataset_info"]
evaluation = _config["evaluation"]
optimizer = _config["optimizer"]
optimizer_config = _config["optimizer_config"]
lr_config = _config["lr_config"]
total_epochs = _config["total_epochs"]
channel_cfg = _config["channel_cfg"]
model = _config["model"]
data_cfg = _config["data_cfg"]
train_pipeline = _config["train_pipeline"]
val_pipeline = _config["val_pipeline"]
test_pipeline = _config["test_pipeline"]
data = _config["data"]
work_dir = _config["work_dir"]