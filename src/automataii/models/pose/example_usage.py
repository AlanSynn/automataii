"""Example usage of the modular pose configuration system."""

from automataii.models.pose import (
    PoseConfig,
    ModelConfig,
    TrainingConfig,
    CocoDatasetInfo,
    DataConfig,
    PipelineConfig
)
from automataii.models.pose.config_builder import PoseConfigBuilder


def example_create_custom_config():
    """Example of creating a custom pose detection configuration."""
    # Create a custom model configuration
    model_config = ModelConfig(
        type="TopDown",
        pretrained="torchvision://resnet101",  # Using ResNet-101 instead of ResNet-50
        backbone=dict(type="ResNet", depth=101),
        keypoint_head=dict(
            type="TopdownHeatmapSimpleHead",
            in_channels=2048,
            out_channels=17,
            loss_keypoint=dict(type="JointsMSELoss", use_target_weight=True)
        )
    )
    
    # Create custom training configuration
    training_config = TrainingConfig(
        total_epochs=500,  # Fewer epochs
        optimizer=dict(type="AdamW", lr=0.001),  # Different optimizer
        lr_config=dict(
            policy="step",
            warmup="linear",
            warmup_iters=1000,
            warmup_ratio=0.001,
            step=[100, 300, 450]
        )
    )
    
    # Create custom data configuration
    data_config = DataConfig(
        image_size=[256, 256],  # Square images
        heatmap_size=[64, 64],
        num_output_channels=17,
        num_joints=17
    )
    
    # Build complete configuration
    config = {
        "model": model_config.to_dict(),
        "training": training_config.to_dict(),
        "data_cfg": data_config.to_dict(),
        # ... other configurations
    }
    
    return config


def example_modify_default_config():
    """Example of modifying the default configuration."""
    # Get default configuration
    config = PoseConfigBuilder.build_default_config()
    
    # Modify specific parts
    config["model"]["backbone"]["depth"] = 101
    config["optimizer"]["lr"] = 0.001
    config["total_epochs"] = 500
    
    # Change image size
    config["data_cfg"]["image_size"] = [256, 256]
    config["data_cfg"]["heatmap_size"] = [64, 64]
    
    return config


def example_create_inference_config():
    """Example of creating an inference-only configuration."""
    model = ModelConfig()
    data_cfg = DataConfig()
    test_pipeline = PipelineConfig.create_test_pipeline()
    
    inference_config = {
        "model": model.to_dict(),
        "data_cfg": data_cfg.to_dict(),
        "test_pipeline": test_pipeline.to_list(),
        "test_cfg": {
            "flip_test": True,
            "post_process": "default",
            "shift_heatmap": True,
            "modulate_kernel": 11
        }
    }
    
    return inference_config


if __name__ == "__main__":
    # Example 1: Create custom config
    custom_config = example_create_custom_config()
    print("Custom config created")
    
    # Example 2: Modify default config
    modified_config = example_modify_default_config()
    print("Modified default config")
    
    # Example 3: Create inference config
    inference_config = example_create_inference_config()
    print("Inference config created")