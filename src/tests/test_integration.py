"""
Test suite for integration components.

Tests the MechanismAdapter and ExportManager for integrating
mechanisms with automata bases.
"""

import pytest
import json
import tempfile
from pathlib import Path
from typing import List, Dict, Any
import numpy as np

from automataii.integration import MechanismAdapter, ExportManager
from automataii.generation import LinkageMechanism, CamMechanism, GearMechanism
from automataii.modules.automata_base import (
    BaseConfiguration, BaseType, MaterialType, 
    Dimensions2D, Dimensions3D, Unit
)


class TestMechanismAdapter:
    """Test MechanismAdapter functionality."""
    
    @pytest.fixture
    def adapter(self):
        """Create MechanismAdapter instance."""
        return MechanismAdapter()
    
    @pytest.fixture
    def sample_mechanisms(self):
        """Create sample mechanisms for testing."""
        linkage = LinkageMechanism(
            id="test_linkage",
            name="Test Linkage",
            crank_length=40,
            coupler_length=60,
            follower_length=50,
            ground_length=80,
            crank_pivot=(0, 0),
            ground_pivot=(80, 0)
        )
        
        cam = CamMechanism(
            id="test_cam",
            name="Test Cam",
            cam_radius=30,
            follower_type="roller",
            center_position=(100, 100)
        )
        
        gear = GearMechanism(
            id="test_gear",
            name="Test Gear",
            driver_teeth=20,
            driven_teeth=40,
            module=2.0,
            center_distance=60
        )
        
        return [linkage, cam, gear]
    
    def test_add_single_mechanism(self, adapter, sample_mechanisms):
        """Test adding a single mechanism."""
        mechanism = sample_mechanisms[0]
        placement = adapter.add_mechanism(mechanism, "rectangular")
        
        assert placement.mechanism_id == "test_linkage"
        assert placement.base_position is not None
        assert placement.rotation == (0, 0, 0)
        assert placement.scale == 1.0
        assert len(placement.connection_points) > 0
    
    def test_add_multiple_mechanisms(self, adapter, sample_mechanisms):
        """Test adding multiple mechanisms."""
        placements = []
        for mechanism in sample_mechanisms:
            placement = adapter.add_mechanism(mechanism, "rectangular")
            placements.append(placement)
        
        assert len(adapter.placements) == 3
        
        # Check each mechanism has unique placement
        positions = [p.base_position for p in placements]
        assert len(set(map(tuple, positions))) == len(positions)
    
    def test_connection_point_identification(self, adapter):
        """Test identification of connection points."""
        linkage = LinkageMechanism(
            id="linkage_1",
            crank_pivot=(10, 20),
            ground_pivot=(90, 20)
        )
        
        placement = adapter.add_mechanism(linkage, "rectangular")
        
        # Should have motor and support connections
        motor_points = [
            cp for cp in placement.connection_points 
            if cp.type == "motor"
        ]
        support_points = [
            cp for cp in placement.connection_points 
            if cp.type == "support"
        ]
        
        assert len(motor_points) >= 1
        assert len(support_points) >= 1
        
        # Check motor point is at crank pivot
        motor_point = motor_points[0]
        assert motor_point.position[0] == 10
        assert motor_point.position[1] == 20
    
    def test_clearance_checking(self, adapter):
        """Test mechanism clearance validation."""
        # Add first mechanism
        mech1 = LinkageMechanism(id="mech1", crank_pivot=(0, 0))
        adapter.add_mechanism(mech1, "rectangular")
        
        # Add second mechanism very close
        mech2 = LinkageMechanism(id="mech2", crank_pivot=(2, 2))
        adapter.add_mechanism(mech2, "rectangular")
        
        # Force close placement
        adapter.placements["mech2"].base_position = (2, 2, 0)
        
        # Check clearance
        has_clearance = adapter.check_clearance("mech2", ["mech1"])
        assert not has_clearance  # Should fail due to proximity
    
    def test_update_placement(self, adapter, sample_mechanisms):
        """Test updating mechanism placement."""
        mechanism = sample_mechanisms[0]
        placement = adapter.add_mechanism(mechanism, "rectangular")
        
        # Update position
        new_position = (50, 50, 25)
        adapter.update_placement(
            mechanism.id,
            position=new_position,
            rotation=(0, 45, 0),
            scale=1.5
        )
        
        updated = adapter.placements[mechanism.id]
        assert updated.base_position == new_position
        assert updated.rotation == (0, 45, 0)
        assert updated.scale == 1.5
    
    def test_connection_mappings(self, adapter):
        """Test getting connection mappings for manufacturing."""
        linkage = LinkageMechanism(
            id="linkage_1",
            crank_pivot=(20, 30),
            ground_pivot=(100, 30)
        )
        
        placement = adapter.add_mechanism(linkage, "rectangular")
        placement.base_position = (10, 10, 50)
        
        mappings = adapter.get_connection_mappings("linkage_1")
        
        assert "motor_connections" in mappings
        assert "support_connections" in mappings
        assert "output_connections" in mappings
        
        # Check world position transformation
        motor_conn = mappings["motor_connections"][0]
        world_pos = motor_conn["world_position"]
        
        # Local (20, 30, 0) + base (10, 10, 50) = world (30, 40, 50)
        assert world_pos == (30, 40, 50)


class TestExportManager:
    """Test ExportManager functionality."""
    
    @pytest.fixture
    def export_manager(self):
        """Create ExportManager instance."""
        return ExportManager()
    
    @pytest.fixture
    def sample_base(self):
        """Create sample base configuration."""
        base = BaseConfiguration(
            name="Test Base",
            base_type=BaseType.BOX_ENCLOSED,
            dimensions=Dimensions3D(300, 200, 150, Unit.MM),
            primary_material=MaterialType.WOOD,
            material_thickness=6.0
        )
        return base
    
    @pytest.fixture
    def sample_assembly(self, sample_base, sample_mechanisms):
        """Create complete assembly for testing."""
        adapter = MechanismAdapter()
        
        for mechanism in sample_mechanisms:
            adapter.add_mechanism(mechanism, sample_base.base_type.value)
        
        return {
            "base": sample_base,
            "mechanisms": sample_mechanisms,
            "adapter": adapter
        }
    
    def test_export_to_json(self, export_manager, sample_assembly):
        """Test JSON export."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            export_path = Path(f.name)
        
        try:
            export_manager.export_assembly(
                assembly=sample_assembly,
                format="json",
                output_path=export_path
            )
            
            # Verify file exists and contains data
            assert export_path.exists()
            
            with open(export_path) as f:
                data = json.load(f)
            
            assert "base" in data
            assert "mechanisms" in data
            assert "placements" in data
            assert data["base"]["name"] == "Test Base"
            assert len(data["mechanisms"]) == 3
            
        finally:
            export_path.unlink()
    
    def test_export_to_svg(self, export_manager, sample_base):
        """Test SVG export."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.svg', delete=False) as f:
            export_path = Path(f.name)
        
        try:
            export_manager.export_base(
                base=sample_base,
                format="svg",
                output_path=export_path,
                show_dimensions=True
            )
            
            assert export_path.exists()
            
            # Check SVG content
            content = export_path.read_text()
            assert "<svg" in content
            assert 'width=' in content
            assert 'height=' in content
            
        finally:
            export_path.unlink()
    
    def test_export_manufacturing_package(self, export_manager, sample_assembly):
        """Test complete manufacturing package export."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            
            export_manager.export_manufacturing_package(
                assembly=sample_assembly,
                output_dir=output_dir,
                formats=["svg", "json", "bom"]
            )
            
            # Check all expected files exist
            assert (output_dir / "base.svg").exists()
            assert (output_dir / "assembly_info.json").exists()
            assert (output_dir / "bill_of_materials.csv").exists()
            assert (output_dir / "assembly_instructions.txt").exists()
    
    def test_export_with_options(self, export_manager, sample_base):
        """Test export with various options."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.svg', delete=False) as f:
            export_path = Path(f.name)
        
        try:
            # Export with custom scale and options
            export_manager.export_base(
                base=sample_base,
                format="svg",
                output_path=export_path,
                scale=2.0,
                show_mounting_points=True,
                show_dimensions=True,
                show_labels=True
            )
            
            content = export_path.read_text()
            
            # Should contain mounting point circles
            assert "<circle" in content
            
            # Should contain dimension text
            assert "<text" in content
            
        finally:
            export_path.unlink()
    
    def test_batch_export(self, export_manager):
        """Test exporting multiple bases in batch."""
        bases = []
        for i in range(3):
            base = BaseConfiguration(
                name=f"Base {i+1}",
                base_type=BaseType.FLAT_RECTANGULAR,
                dimensions=Dimensions2D(200 + i*50, 150 + i*30, Unit.MM),
                primary_material=MaterialType.MDF
            )
            bases.append(base)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            
            export_manager.batch_export_bases(
                bases=bases,
                output_dir=output_dir,
                format="svg"
            )
            
            # Check all files created
            for i, base in enumerate(bases):
                filename = f"base_{i+1}.svg"
                assert (output_dir / filename).exists()


class TestIntegrationWorkflow:
    """Test complete integration workflows."""
    
    def test_simple_automata_workflow(self):
        """Test creating a simple automata from start to finish."""
        # 1. Create base
        base = BaseConfiguration(
            name="Simple Automata Base",
            base_type=BaseType.FLAT_RECTANGULAR,
            dimensions=Dimensions2D(250, 200, Unit.MM),
            primary_material=MaterialType.WOOD,
            material_thickness=10.0
        )
        
        # 2. Create mechanism
        linkage = LinkageMechanism(
            id="main_linkage",
            name="Main Motion",
            crank_length=40,
            coupler_length=80,
            follower_length=60,
            ground_length=100
        )
        
        # 3. Adapt mechanism to base
        adapter = MechanismAdapter()
        placement = adapter.add_mechanism(linkage, base.base_type.value)
        
        # 4. Export
        export_manager = ExportManager()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "automata.json"
            
            assembly_data = {
                "base": base.__dict__,
                "mechanisms": [linkage.__dict__],
                "placements": {linkage.id: placement.__dict__}
            }
            
            with open(output_file, 'w') as f:
                json.dump(assembly_data, f, default=str)
            
            assert output_file.exists()
            
            # Verify assembly data
            with open(output_file) as f:
                loaded = json.load(f)
            
            assert loaded["base"]["name"] == "Simple Automata Base"
            assert len(loaded["mechanisms"]) == 1
            assert loaded["mechanisms"][0]["id"] == "main_linkage"
    
    def test_complex_multi_mechanism_workflow(self):
        """Test creating complex automata with multiple mechanisms."""
        # Create elaborate base
        base = BaseConfiguration(
            name="Complex Display Base",
            base_type=BaseType.BOX_ENCLOSED,
            dimensions=Dimensions3D(400, 300, 200, Unit.MM),
            primary_material=MaterialType.WOOD,
            secondary_materials=[MaterialType.ACRYLIC],
            material_thickness=12.0
        )
        
        # Create multiple interconnected mechanisms
        mechanisms = [
            LinkageMechanism(
                id="primary_motion",
                crank_length=50,
                coupler_length=100
            ),
            CamMechanism(
                id="secondary_motion",
                cam_radius=40,
                follower_type="flat"
            ),
            GearMechanism(
                id="speed_control",
                driver_teeth=15,
                driven_teeth=45,
                module=2.0
            )
        ]
        
        # Adapt all mechanisms
        adapter = MechanismAdapter()
        placements = []
        
        for mechanism in mechanisms:
            placement = adapter.add_mechanism(mechanism, base.base_type.value)
            placements.append(placement)
        
        # Verify no collisions
        for i, mech in enumerate(mechanisms):
            other_ids = [m.id for j, m in enumerate(mechanisms) if j != i]
            has_clearance = adapter.check_clearance(mech.id, other_ids)
            assert has_clearance or len(mechanisms) == 1
        
        # Export complete package
        export_manager = ExportManager()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            
            assembly = {
                "base": base,
                "mechanisms": mechanisms,
                "adapter": adapter
            }
            
            export_manager.export_manufacturing_package(
                assembly=assembly,
                output_dir=output_dir
            )
            
            # Verify all components exported
            assert (output_dir / "base.svg").exists()
            assert (output_dir / "assembly_info.json").exists()
            
            # Check assembly has all mechanisms
            with open(output_dir / "assembly_info.json") as f:
                info = json.load(f)
            
            assert len(info["mechanisms"]) == 3
            assert all(m["id"] in ["primary_motion", "secondary_motion", "speed_control"] 
                      for m in info["mechanisms"])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])