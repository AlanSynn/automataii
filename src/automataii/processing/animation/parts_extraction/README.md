# Body Parts Extraction Module

This module provides functionality for extracting body parts from character images using skeleton-driven segmentation.

## Architecture

The module is organized into several components, each handling a specific responsibility:

### Core Components

1. **models.py** (97 lines)
   - Data models for parts, joints, and extraction results
   - Provides type-safe data structures

2. **preprocessing.py** (138 lines)
   - Image preprocessing utilities
   - Handles scaling, masking, and bounding box extraction

3. **joint_mapper.py** (177 lines)
   - Converts between different skeleton data formats
   - Maps joint names and positions

4. **segmentation.py** (243 lines)
   - Core segmentation algorithm using skeleton-driven approach
   - Implements influence map-based part segmentation

5. **part_extractor.py** (166 lines)
   - Extracts individual body parts from segmented masks
   - Calculates pivot points for animation

6. **visualization.py** (182 lines)
   - Creates visual outputs (segmentation visualization, HTML viewer)
   - Handles rendering of results

7. **file_io.py** (121 lines)
   - File reading/writing operations
   - Handles JSON, YAML, and image I/O

8. **animation_handler.py** (115 lines)
   - Generates animations for body parts
   - Manages animation workflow

9. **extractor.py** (223 lines)
   - Main orchestrator class
   - Coordinates the entire extraction pipeline

## Usage

```python
from automataii.processing.animation.parts_extraction import BodyPartsExtractor

# Create extractor
extractor = BodyPartsExtractor(
    char_dir="path/to/character",
    output_dir="path/to/output",
    generate_animations=True,
    num_frames=30,
    fps=24
)

# Process character
result = extractor.process()

# Access extracted parts
if result:
    for part_name, part_info in result.character.parts.items():
        print(f"Part: {part_name}, ROI: {part_info.roi}")
```

## Key Features

- **Modular Design**: Each component has a single responsibility
- **Type Safety**: Uses dataclasses for structured data
- **Performance**: Vectorized operations for fast segmentation
- **Extensibility**: Easy to add new part definitions or processing steps
- **Backward Compatibility**: Original API preserved through wrapper

## File Structure

```
parts_extraction/
├── __init__.py          # Package initialization
├── models.py            # Data models
├── preprocessing.py     # Image preprocessing
├── joint_mapper.py      # Joint mapping utilities
├── segmentation.py      # Segmentation algorithm
├── part_extractor.py    # Part extraction logic
├── visualization.py     # Visualization utilities
├── file_io.py          # File I/O operations
├── animation_handler.py # Animation generation
├── extractor.py        # Main extractor class
└── README.md           # This file
```

## Dependencies

- OpenCV (cv2)
- NumPy
- SciPy
- PyYAML
- Pathlib (standard library)