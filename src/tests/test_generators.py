"""
Test suite for all generator classes.

Tests the AxisGenerator, BodyCavityGenerator, StructuredGenerator, and
base generator functionality.
"""

import pytest
import numpy as np
from typing import Dict, Any

from automataii.generators import (
    BaseGenerator, GeneratorConfig, BaseType,
    AxisGenerator, BodyCavityGenerator, StructuredGenerator
)
from automataii.core.models import MountingPoint, MechanismType


class TestGeneratorConfig:
    """Test GeneratorConfig validation and behavior."""
    
    def test_valid_config(self):
        """Test creating valid generator configuration."""
        config = GeneratorConfig(
            scale=1.5,
            material_thickness=6.0,
            tolerance=0.2,
            units="mm"
        )
        config.validate()
        
        assert config.scale == 1.5
        assert config.material_thickness == 6.0
        assert config.tolerance == 0.2
        assert config.units == "mm"
    
    def test_invalid_scale(self):
        """Test validation rejects negative scale."""
        config = GeneratorConfig(scale=-1.0)
        with pytest.raises(ValueError, match="Scale must be positive"):
            config.validate()
    
    def test_invalid_thickness(self):
        """Test validation rejects negative thickness."""
        config = GeneratorConfig(material_thickness=-5.0)
        with pytest.raises(ValueError, match="Material thickness must be positive"):
            config.validate()
    
    def test_invalid_units(self):
        """Test validation rejects invalid units."""
        config = GeneratorConfig(units="invalid")
        with pytest.raises(ValueError, match="Unsupported units"):
            config.validate()


class TestBaseGenerator:
    """Test base generator functionality."""
    
    def test_transform_point(self):
        """Test point transformation."""
        config = GeneratorConfig()
        generator = ConcreteGenerator(config)
        
        # Test translation
        result = generator.transform_point((10, 20), offset=(5, -3))
        assert result == (15, 17)
        
        # Test rotation (90 degrees)
        result = generator.transform_point((10, 0), rotation=np.pi/2)
        assert np.isclose(result[0], 0, atol=1e-10)
        assert np.isclose(result[1], 10, atol=1e-10)
        
        # Test combined transform
        result = generator.transform_point(
            (10, 0), 
            offset=(5, 5), 
            rotation=np.pi/2
        )
        assert np.isclose(result[0], 5, atol=1e-10)
        assert np.isclose(result[1], 15, atol=1e-10)
    
    def test_scale_dimensions(self):
        """Test dimension scaling."""
        config = GeneratorConfig(scale=2.0)
        generator = ConcreteGenerator(config)
        
        dimensions = {"width": 100, "height": 50, "depth": 75}
        scaled = generator.scale_dimensions(dimensions)
        
        assert scaled["width"] == 200
        assert scaled["height"] == 100
        assert scaled["depth"] == 150
    
    def test_add_tolerance(self):
        """Test tolerance addition."""
        config = GeneratorConfig(tolerance=0.2)
        generator = ConcreteGenerator(config)
        
        # Test hole tolerance (makes larger)
        hole_dim = generator.add_tolerance(10.0, is_hole=True)
        assert hole_dim == 10.2
        
        # Test part tolerance (makes smaller)
        part_dim = generator.add_tolerance(10.0, is_hole=False)
        assert part_dim == 9.8


class TestAxisGenerator:
    """Test AxisGenerator class."""
    
    @pytest.fixture
    def axis_generator(self):
        """Create AxisGenerator instance."""
        config = GeneratorConfig(
            scale=1.0,
            material_thickness=5.0,
            tolerance=0.1
        )
        return AxisGenerator(config)
    
    def test_generate_basic(self, axis_generator):
        """Test basic axis generation."""
        result = axis_generator.generate(
            base_width=200,
            base_height=150,
            axis_height=100,
            num_supports=4
        )
        
        assert "base_plate" in result
        assert "axis_supports" in result
        assert "axis_shaft" in result
        assert len(result["axis_supports"]) == 4
    
    def test_calculate_mounting_points(self, axis_generator):
        """Test mounting point calculation."""
        axis_generator.generate(
            base_width=200,
            base_height=150,
            axis_height=100
        )
        
        mounting_points = axis_generator.calculate_mounting_points()
        
        # Should have center axis point and support points
        assert len(mounting_points) >= 1
        
        # Check center point
        center_point = next(
            (mp for mp in mounting_points if mp.id == "axis_center"),
            None
        )
        assert center_point is not None
        assert center_point.position == (100, 75)  # Center of 200x150
    
    def test_validate_input(self, axis_generator):
        """Test input validation."""
        # Valid input
        axis_generator.validate_input(
            base_width=200,
            base_height=150,
            axis_height=100
        )
        
        # Invalid width
        with pytest.raises(ValueError):
            axis_generator.validate_input(
                base_width=-10,
                base_height=150,
                axis_height=100
            )


class TestBodyCavityGenerator:
    """Test BodyCavityGenerator class."""
    
    @pytest.fixture
    def cavity_generator(self):
        """Create BodyCavityGenerator instance."""
        config = GeneratorConfig(
            scale=1.0,
            material_thickness=3.0
        )
        return BodyCavityGenerator(config)
    
    def test_generate_character_cavity(self, cavity_generator):
        """Test character body cavity generation."""
        # Simulate character outline
        character_outline = [
            (50, 100), (100, 150), (150, 100),
            (150, 50), (100, 0), (50, 50)
        ]
        
        result = cavity_generator.generate(
            character_outline=character_outline,
            cavity_depth=30,
            wall_thickness=5
        )
        
        assert "outer_wall" in result
        assert "inner_cavity" in result
        assert "mounting_tabs" in result
        assert result["cavity_depth"] == 30
    
    def test_multiple_cavities(self, cavity_generator):
        """Test generation of multiple cavities."""
        cavities = [
            {"outline": [(0, 0), (50, 0), (50, 50), (0, 50)], "depth": 20},
            {"outline": [(100, 0), (150, 0), (150, 50), (100, 50)], "depth": 25}
        ]
        
        result = cavity_generator.generate(
            cavities=cavities,
            wall_thickness=3
        )
        
        assert "cavities" in result
        assert len(result["cavities"]) == 2
        assert result["cavities"][0]["depth"] == 20
        assert result["cavities"][1]["depth"] == 25


class TestStructuredGenerator:
    """Test StructuredGenerator class."""
    
    @pytest.fixture
    def structured_generator(self):
        """Create StructuredGenerator instance."""
        config = GeneratorConfig(
            scale=1.0,
            material_thickness=6.0
        )
        return StructuredGenerator(config)
    
    def test_generate_box_structure(self, structured_generator):
        """Test box structure generation."""
        result = structured_generator.generate(
            structure_type="box",
            dimensions=(300, 200, 150),
            assembly_method="interlocking"
        )
        
        assert "panels" in result
        assert "joints" in result
        assert "assembly_order" in result
        
        # Should have 6 panels for a box
        assert len(result["panels"]) == 6
        
        # Check panel names
        expected_panels = ["bottom", "top", "front", "back", "left", "right"]
        for panel_name in expected_panels:
            assert panel_name in result["panels"]
    
    def test_generate_frame_structure(self, structured_generator):
        """Test frame structure generation."""
        result = structured_generator.generate(
            structure_type="frame",
            dimensions=(400, 300, 200),
            frame_members=12
        )
        
        assert "frame_members" in result
        assert "connectors" in result
        assert len(result["frame_members"]) == 12
    
    def test_calculate_load_paths(self, structured_generator):
        """Test load path calculation."""
        structured_generator.generate(
            structure_type="box",
            dimensions=(300, 200, 150),
            expected_load=5.0  # kg
        )
        
        load_paths = structured_generator.calculate_load_paths()
        
        assert "primary_paths" in load_paths
        assert "stress_points" in load_paths
        assert "recommended_reinforcement" in load_paths


class TestGeneratorIntegration:
    """Test integration between different generators."""
    
    def test_axis_in_structured_base(self):
        """Test combining axis generator with structured base."""
        # Create structured base
        base_config = GeneratorConfig(material_thickness=6.0)
        base_gen = StructuredGenerator(base_config)
        
        base_result = base_gen.generate(
            structure_type="box",
            dimensions=(300, 200, 100)
        )
        
        # Create axis system
        axis_config = GeneratorConfig(material_thickness=6.0)
        axis_gen = AxisGenerator(axis_config)
        
        axis_result = axis_gen.generate(
            base_width=300,
            base_height=200,
            axis_height=80  # Fits within 100mm box height
        )
        
        # Verify compatibility
        assert axis_result["base_plate"]["width"] <= 300
        assert axis_result["base_plate"]["height"] <= 200
        assert axis_result["axis_shaft"]["height"] <= 100
    
    def test_cavity_with_mounting_points(self):
        """Test body cavity with mechanism mounting."""
        config = GeneratorConfig()
        cavity_gen = BodyCavityGenerator(config)
        
        # Generate cavity with mechanism space
        result = cavity_gen.generate(
            character_outline=[(0, 0), (100, 0), (100, 150), (0, 150)],
            cavity_depth=40,
            mechanism_clearance=20
        )
        
        mounting_points = cavity_gen.calculate_mounting_points()
        
        # Should have mounting points for mechanisms
        mechanism_points = [
            mp for mp in mounting_points 
            if mp.mechanism_type is not None
        ]
        assert len(mechanism_points) > 0


# Concrete implementation for testing abstract base class
class ConcreteGenerator(BaseGenerator):
    """Concrete generator for testing base class."""
    
    def generate(self) -> Dict[str, Any]:
        """Generate test data."""
        return {"test": "data"}
    
    def validate_input(self, **kwargs) -> None:
        """Validate test input."""
        pass
    
    def calculate_mounting_points(self) -> list:
        """Calculate test mounting points."""
        return []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])