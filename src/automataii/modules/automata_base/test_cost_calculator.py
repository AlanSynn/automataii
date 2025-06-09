"""
Test script for material cost calculator functionality.

This script demonstrates cost estimation for different base configurations
and materials.
"""

from pathlib import Path
from automataii.modules.automata_base.enums.base_types import (
    BaseType, MaterialType, MountingType
)
from automataii.modules.automata_base.models.base_config import BaseConfiguration
from automataii.modules.automata_base.models.dimensions import (
    Dimensions2D, Dimensions3D, MountingPoint, Point2D, Unit
)
from automataii.modules.automata_base.utils.cost_calculator import (
    CostCalculator, MaterialCost, estimate_project_cost
)


def create_test_configurations():
    """Create various test configurations."""
    configs = []
    
    # Small wooden base
    config1 = BaseConfiguration(
        name="Small Wooden Base",
        base_type=BaseType.FLAT_RECTANGULAR,
        dimensions=Dimensions2D(width=200, height=150, unit=Unit.MM),
        primary_material=MaterialType.WOOD,
        material_thickness=15.0,
        mounting_type=MountingType.SURFACE
    )
    config1.add_mounting_point(MountingPoint(
        position=Point2D(50, 50), hole_diameter=5, thread_type="M5"
    ))
    config1.add_mounting_point(MountingPoint(
        position=Point2D(150, 50), hole_diameter=5, thread_type="M5"
    ))
    configs.append(config1)
    
    # Medium aluminum base
    config2 = BaseConfiguration(
        name="Medium Aluminum Base",
        base_type=BaseType.FLAT_RECTANGULAR,
        dimensions=Dimensions2D(width=300, height=200, unit=Unit.MM),
        primary_material=MaterialType.ALUMINUM,
        material_thickness=5.0,
        mounting_type=MountingType.SURFACE
    )
    for i in range(4):
        x = 50 + (i % 2) * 200
        y = 50 + (i // 2) * 100
        config2.add_mounting_point(MountingPoint(
            position=Point2D(x, y), hole_diameter=6, thread_type="M6"
        ))
    configs.append(config2)
    
    # Large acrylic base
    config3 = BaseConfiguration(
        name="Large Acrylic Display",
        base_type=BaseType.FLAT_CIRCULAR,
        dimensions=Dimensions2D(width=400, height=400, unit=Unit.MM),
        primary_material=MaterialType.ACRYLIC,
        material_thickness=10.0,
        mounting_type=MountingType.SURFACE
    )
    configs.append(config3)
    
    # Wooden box
    config4 = BaseConfiguration(
        name="Wooden Storage Box",
        base_type=BaseType.BOX_OPEN,
        dimensions=Dimensions3D(width=250, height=100, depth=200, unit=Unit.MM),
        primary_material=MaterialType.PLYWOOD,
        material_thickness=12.0,
        mounting_type=MountingType.FREESTANDING
    )
    configs.append(config4)
    
    # 3D printed base
    config5 = BaseConfiguration(
        name="3D Printed Custom Base",
        base_type=BaseType.PEDESTAL,
        dimensions=Dimensions3D(width=150, height=120, depth=150, unit=Unit.MM),
        primary_material=MaterialType.PLASTIC_3D_PRINTED,
        material_thickness=20.0,
        mounting_type=MountingType.FREESTANDING
    )
    configs.append(config5)
    
    return configs


def test_individual_costs():
    """Test cost calculation for individual bases."""
    print("=== Individual Base Cost Estimates ===\n")
    
    calculator = CostCalculator()
    configs = create_test_configurations()
    
    for config in configs:
        print(f"\nCalculating costs for: {config.name}")
        print("-" * 40)
        
        try:
            # Calculate costs
            costs = calculator.calculate_material_cost(config)
            
            # Generate report
            report = calculator.generate_cost_report(config)
            print(report)
            
        except Exception as e:
            print(f"Error: {e}")


def test_custom_pricing():
    """Test with custom material pricing."""
    print("\n\n=== Custom Pricing Test ===\n")
    
    # Define custom prices (e.g., bulk discount)
    custom_prices = {
        MaterialType.ALUMINUM: MaterialCost(
            material=MaterialType.ALUMINUM,
            unit_price=150.0,  # Discounted from 200
            price_unit="USD/sq_m",
            density=2700.0,
            supplier="Local Metal Supply Co.",
            notes="Bulk discount pricing"
        ),
        MaterialType.WOOD: MaterialCost(
            material=MaterialType.WOOD,
            unit_price=40.0,  # Discounted from 50
            price_unit="USD/sq_m",
            density=700.0,
            supplier="Lumber Depot",
            notes="Contractor pricing"
        )
    }
    
    calculator = CostCalculator(custom_prices)
    
    # Test with aluminum base
    config = BaseConfiguration(
        name="Bulk Order Aluminum Base",
        base_type=BaseType.FLAT_RECTANGULAR,
        dimensions=Dimensions2D(width=500, height=300, unit=Unit.MM),
        primary_material=MaterialType.ALUMINUM,
        material_thickness=6.0,
        mounting_type=MountingType.SURFACE
    )
    
    report = calculator.generate_cost_report(config)
    print(report)


def test_project_estimation():
    """Test total project cost estimation."""
    print("\n\n=== Project Cost Estimation ===\n")
    
    configs = create_test_configurations()
    
    # Calculate total project cost
    project_costs = estimate_project_cost(configs)
    
    print(f"Project: Multiple Automata Bases")
    print(f"Number of bases: {project_costs['num_bases']}")
    print(f"\nCost Summary:")
    print(f"  Material costs: ${project_costs['material_cost']:.2f}")
    print(f"  Fastener costs: ${project_costs['fastener_cost']:.2f}")
    print(f"  Finish costs: ${project_costs['finish_cost']:.2f}")
    print(f"  TOTAL PROJECT COST: ${project_costs['total_cost']:.2f}")
    print(f"\nAverage cost per base: ${project_costs['total_cost']/project_costs['num_bases']:.2f}")


def test_price_persistence():
    """Test saving and loading prices."""
    print("\n\n=== Price Persistence Test ===\n")
    
    # Create calculator with custom prices
    calculator = CostCalculator()
    
    # Save current prices
    price_file = Path("material_prices.json")
    calculator.save_prices(price_file)
    print(f"Saved prices to: {price_file}")
    
    # Load and verify
    new_calculator = CostCalculator()
    new_calculator.load_prices(price_file)
    print("Loaded prices successfully")
    
    # Clean up
    price_file.unlink()
    print("Cleaned up price file")


def main():
    """Run all cost calculator tests."""
    print("Material Cost Calculator Tests")
    print("=" * 50)
    
    test_individual_costs()
    test_custom_pricing()
    test_project_estimation()
    test_price_persistence()
    
    print("\n\n✅ All cost calculator tests completed!")


if __name__ == "__main__":
    main()