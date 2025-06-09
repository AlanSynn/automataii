# Pose Detection Configuration Module

This module provides a modular, type-safe configuration system for pose detection models.

## Structure

- `base.py` - Base configuration classes and runtime settings
- `dataset.py` - Dataset configurations (COCO keypoints, skeleton, data settings)
- `model.py` - Model architecture configurations
- `pipeline.py` - Data preprocessing pipeline configurations
- `training.py` - Training, optimization, and evaluation configurations
- `config_builder.py` - Builder for creating complete configurations
- `compat.py` - Backward compatibility with legacy pose_config.py format

## Usage

### Using the Legacy Format

For backward compatibility, you can still import from `pose_config.py`:

```python
from automataii.models import pose_config

# Access configurations as before
model = pose_config.model
data = pose_config.data
```

### Using the New Modular System

```python
from automataii.models.pose import ModelConfig, TrainingConfig, DataConfig
from automataii.models.pose.config_builder import PoseConfigBuilder

# Create configurations using dataclasses
model = ModelConfig(
    pretrained="torchvision://resnet101",
    backbone={"type": "ResNet", "depth": 101}
)

# Or use the builder for complete configs
config = PoseConfigBuilder.build_default_config()
```

### Creating Custom Configurations

```python
from automataii.models.pose import ModelConfig, TrainingConfig

# Create custom model
model = ModelConfig()
model.backbone.depth = 101  # ResNet-101 instead of ResNet-50

# Create custom training settings
training = TrainingConfig()
training.total_epochs = 500
training.optimizer.lr = 0.001
```

## Benefits

1. **Type Safety**: Dataclasses provide type hints and validation
2. **Modularity**: Each component is in its own file (<300 lines each)
3. **Reusability**: Easy to mix and match configurations
4. **Maintainability**: Clear separation of concerns
5. **Backward Compatibility**: Existing code continues to work

## Configuration Components

### Base Configuration
- Runtime settings (checkpoints, logging, distributed training)
- Base classes for other configurations

### Dataset Configuration
- COCO keypoint definitions
- Skeleton structure
- Data loading settings

### Model Configuration
- Backbone network (ResNet)
- Keypoint detection head
- Loss functions
- Test/inference settings

### Pipeline Configuration
- Data preprocessing steps
- Augmentation settings
- Normalization parameters

### Training Configuration
- Optimizer settings
- Learning rate scheduling
- Evaluation metrics
- Data loader settings