"""Test script to verify all imports work correctly."""

def test_imports():
    """Test that all modules can be imported."""
    try:
        # Test individual module imports
        from . import models
        from . import preprocessing
        from . import joint_mapper
        from . import segmentation
        from . import part_extractor
        from . import visualization
        from . import file_io
        from . import animation_handler
        from . import extractor
        
        # Test main exports
        from . import BodyPartsExtractor, PartInfo, ExtractionResult
        
        print("✓ All imports successful")
        return True
        
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False


if __name__ == "__main__":
    test_imports()