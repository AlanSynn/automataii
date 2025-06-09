"""
Test script for PDF generation functionality.

This script demonstrates how to generate assembly instruction PDFs
for different base types.
"""

from pathlib import Path
from automataii.modules.automata_base.enums.base_types import (
    BaseType, MaterialType, MountingType, AssemblyMethod
)
from automataii.modules.automata_base.models.base_config import BaseConfiguration
from automataii.modules.automata_base.models.dimensions import (
    Dimensions2D, Dimensions3D, MountingPoint, Point2D, Unit
)
from automataii.modules.automata_base.utils.pdf_generator import (
    PDFGenerator, generate_assembly_pdf
)


def create_sample_bases():
    """Create sample base configurations for testing."""
    bases = []
    
    # Wooden box base
    config1 = BaseConfiguration(
        name="Wooden Music Box Base",
        base_type=BaseType.BOX_OPEN,
        dimensions=Dimensions3D(width=300, height=100, depth=200, unit=Unit.MM),
        primary_material=MaterialType.WOOD,
        material_thickness=12.0,
        mounting_type=MountingType.FREESTANDING,
        assembly_method=AssemblyMethod.GLUE
    )
    
    # Add mounting points for mechanism
    config1.add_mounting_point(MountingPoint(
        position=Point2D(150, 100),
        hole_diameter=8,
        thread_type="M8"
    ))
    config1.add_mounting_point(MountingPoint(
        position=Point2D(75, 50),
        hole_diameter=5,
        thread_type="M5"
    ))
    config1.add_mounting_point(MountingPoint(
        position=Point2D(225, 50),
        hole_diameter=5,
        thread_type="M5"
    ))
    
    bases.append(("wooden_box", config1))
    
    # Aluminum wall mount
    config2 = BaseConfiguration(
        name="Wall-Mounted Kinetic Display",
        base_type=BaseType.WALL_MOUNTED,
        dimensions=Dimensions2D(width=400, height=300, unit=Unit.MM),
        primary_material=MaterialType.ALUMINUM,
        material_thickness=5.0,
        mounting_type=MountingType.WALL,
        assembly_method=AssemblyMethod.SCREWS
    )
    
    # Add wall mounting holes
    config2.add_mounting_point(MountingPoint(
        position=Point2D(50, 250),
        hole_diameter=8,
        countersink=True,
        countersink_diameter=16,
        thread_type="M8"
    ))
    config2.add_mounting_point(MountingPoint(
        position=Point2D(350, 250),
        hole_diameter=8,
        countersink=True,
        countersink_diameter=16,
        thread_type="M8"
    ))
    config2.add_mounting_point(MountingPoint(
        position=Point2D(50, 50),
        hole_diameter=8,
        countersink=True,
        countersink_diameter=16,
        thread_type="M8"
    ))
    config2.add_mounting_point(MountingPoint(
        position=Point2D(350, 50),
        hole_diameter=8,
        countersink=True,
        countersink_diameter=16,
        thread_type="M8"
    ))
    
    # Add mechanism mounting points
    config2.add_mounting_point(MountingPoint(
        position=Point2D(200, 150),
        hole_diameter=10,
        thread_type="M10"
    ))
    
    bases.append(("wall_mount", config2))
    
    # Acrylic display pedestal
    config3 = BaseConfiguration(
        name="Acrylic Display Pedestal",
        base_type=BaseType.PEDESTAL,
        dimensions=Dimensions3D(width=150, height=200, depth=150, unit=Unit.MM),
        primary_material=MaterialType.ACRYLIC,
        material_thickness=10.0,
        mounting_type=MountingType.FREESTANDING,
        assembly_method=AssemblyMethod.INTERLOCKING
    )
    
    bases.append(("pedestal", config3))
    
    return bases


def main():
    """Test PDF generation functionality."""
    output_dir = Path("pdf_output")
    output_dir.mkdir(exist_ok=True)
    
    bases = create_sample_bases()
    
    print("Generating assembly instruction PDFs...\n")
    
    for name, config in bases:
        print(f"Generating PDF for {config.name}...")
        
        # Generate using PDFGenerator class
        pdf_path = output_dir / f"{name}_instructions.pdf"
        generator = PDFGenerator(config)
        result_path = generator.generate(pdf_path)
        
        if result_path.suffix == '.txt':
            print(f"  ⚠️  Generated text file (ReportLab not installed): {result_path}")
        else:
            print(f"  ✅ Generated PDF: {result_path}")
        
        # Also test convenience function
        pdf_path2 = output_dir / f"{name}_instructions_v2.pdf"
        result_path2 = generate_assembly_pdf(config, pdf_path2)
        
        if result_path2.suffix == '.pdf':
            print(f"  ✅ Also generated via convenience function: {result_path2}")
    
    print(f"\n✅ PDF generation test completed!")
    print(f"Files saved to: {output_dir.absolute()}")
    
    # Check if ReportLab is available
    try:
        import reportlab
        print("\n✓ ReportLab is installed - full PDF generation available")
    except ImportError:
        print("\n⚠️  ReportLab not installed - generated text files instead")
        print("   Install with: pip install reportlab")


if __name__ == "__main__":
    main()