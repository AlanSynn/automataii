"""
Material cost calculator for automata bases.

This module provides tools to estimate material costs based on
material type, dimensions, and current market prices.
"""

from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path

from automataii.modules.automata_base.models.base_config import BaseConfiguration
from automataii.modules.automata_base.enums.base_types import MaterialType, BaseType
from automataii.modules.automata_base.models.dimensions import Unit


@dataclass
class MaterialCost:
    """Material cost information."""
    material: MaterialType
    unit_price: float  # Price per unit area/volume
    price_unit: str  # e.g., "USD/sq_ft", "USD/kg"
    density: Optional[float] = None  # kg/m³ for weight-based pricing
    last_updated: Optional[datetime] = None
    supplier: Optional[str] = None
    notes: Optional[str] = None


class CostCalculator:
    """Calculate material costs for automata bases."""
    
    # Default material prices (USD)
    DEFAULT_PRICES = {
        MaterialType.WOOD: MaterialCost(
            material=MaterialType.WOOD,
            unit_price=50.0,
            price_unit="USD/sq_m",
            density=700.0,
            notes="Oak/Maple pricing"
        ),
        MaterialType.PLYWOOD: MaterialCost(
            material=MaterialType.PLYWOOD,
            unit_price=35.0,
            price_unit="USD/sq_m",
            density=680.0,
            notes="Baltic birch plywood"
        ),
        MaterialType.MDF: MaterialCost(
            material=MaterialType.MDF,
            unit_price=25.0,
            price_unit="USD/sq_m",
            density=750.0
        ),
        MaterialType.ACRYLIC: MaterialCost(
            material=MaterialType.ACRYLIC,
            unit_price=120.0,
            price_unit="USD/sq_m",
            density=1190.0,
            notes="Clear cast acrylic"
        ),
        MaterialType.ALUMINUM: MaterialCost(
            material=MaterialType.ALUMINUM,
            unit_price=200.0,
            price_unit="USD/sq_m",
            density=2700.0,
            notes="6061 aluminum sheet"
        ),
        MaterialType.STEEL: MaterialCost(
            material=MaterialType.STEEL,
            unit_price=150.0,
            price_unit="USD/sq_m",
            density=7850.0,
            notes="Mild steel sheet"
        ),
        MaterialType.PLASTIC_3D_PRINTED: MaterialCost(
            material=MaterialType.PLASTIC_3D_PRINTED,
            unit_price=50.0,
            price_unit="USD/kg",
            density=1240.0,
            notes="PLA filament"
        ),
        MaterialType.RESIN_3D_PRINTED: MaterialCost(
            material=MaterialType.RESIN_3D_PRINTED,
            unit_price=80.0,
            price_unit="USD/L",
            density=1300.0,
            notes="Standard UV resin"
        ),
        MaterialType.CARDBOARD: MaterialCost(
            material=MaterialType.CARDBOARD,
            unit_price=5.0,
            price_unit="USD/sq_m",
            density=689.0,
            notes="Corrugated cardboard"
        ),
    }
    
    def __init__(self, custom_prices: Optional[Dict[MaterialType, MaterialCost]] = None):
        """
        Initialize cost calculator.
        
        Args:
            custom_prices: Optional custom material prices
        """
        self.prices = self.DEFAULT_PRICES.copy()
        if custom_prices:
            self.prices.update(custom_prices)
    
    def calculate_material_cost(self, config: BaseConfiguration) -> Dict[str, float]:
        """
        Calculate material cost for a base configuration.
        
        Args:
            config: Base configuration
            
        Returns:
            Dictionary with cost breakdown
        """
        # Get material cost info
        material_info = self.prices.get(config.primary_material)
        if not material_info:
            raise ValueError(f"No pricing data for material: {config.primary_material}")
        
        # Calculate material usage
        material_usage = self._calculate_material_usage(config)
        
        # Calculate base cost
        if "sq_m" in material_info.price_unit:
            # Area-based pricing
            area_m2 = material_usage["area_m2"]
            base_cost = area_m2 * material_info.unit_price
        elif "kg" in material_info.price_unit:
            # Weight-based pricing
            weight_kg = material_usage["weight_kg"]
            base_cost = weight_kg * material_info.unit_price
        elif "L" in material_info.price_unit:
            # Volume-based pricing (for resins)
            volume_m3 = material_usage["volume_m3"]
            volume_L = volume_m3 * 1000  # Convert to liters
            base_cost = volume_L * material_info.unit_price
        else:
            base_cost = 0.0
        
        # Add waste factor (10-20% depending on material)
        waste_factor = self._get_waste_factor(config.primary_material)
        material_cost = base_cost * (1 + waste_factor)
        
        # Calculate additional costs
        fastener_cost = self._calculate_fastener_cost(config)
        finish_cost = self._calculate_finish_cost(config)
        
        # Create breakdown
        return {
            "material_cost": round(material_cost, 2),
            "fastener_cost": round(fastener_cost, 2),
            "finish_cost": round(finish_cost, 2),
            "subtotal": round(material_cost + fastener_cost + finish_cost, 2),
            "waste_factor": waste_factor,
            "material_usage": material_usage,
            "price_per_unit": material_info.unit_price,
            "price_unit": material_info.price_unit,
        }
    
    def _calculate_material_usage(self, config: BaseConfiguration) -> Dict[str, float]:
        """Calculate material usage metrics."""
        # Convert dimensions to mm first, then to meters
        dims_mm = config.dimensions.to_unit(Unit.MM) if config.dimensions.unit != Unit.MM else config.dimensions
        thickness_m = (config.material_thickness or 10.0) / 1000.0  # mm to m
        
        # Convert mm dimensions to meters for calculation
        width_m = dims_mm.width / 1000.0
        height_m = dims_mm.height / 1000.0
        depth_m = dims_mm.depth / 1000.0 if hasattr(dims_mm, 'depth') else None
        
        # Calculate based on base type
        if config.base_type == BaseType.FLAT_RECTANGULAR:
            area_m2 = width_m * height_m
            volume_m3 = area_m2 * thickness_m
            
        elif config.base_type == BaseType.FLAT_CIRCULAR:
            radius = min(width_m, height_m) / 2.0
            area_m2 = 3.14159 * radius * radius
            volume_m3 = area_m2 * thickness_m
            
        elif config.base_type in [BaseType.BOX_ENCLOSED, BaseType.BOX_OPEN]:
            # Calculate surface area for box
            if depth_m is not None:
                # 5 faces for open box, 6 for enclosed
                num_faces = 5 if config.base_type == BaseType.BOX_OPEN else 6
                area_m2 = (2 * width_m * depth_m + 
                          2 * width_m * height_m +
                          2 * depth_m * height_m)
                if config.base_type == BaseType.BOX_OPEN:
                    area_m2 -= width_m * depth_m  # Remove top
            else:
                area_m2 = width_m * height_m
            volume_m3 = area_m2 * thickness_m
            
        elif config.base_type == BaseType.PEDESTAL:
            # Approximate as truncated pyramid
            if depth_m is not None:
                base_area = width_m * depth_m
                top_area = base_area * 0.49  # 70% linear = 49% area
                avg_area = (base_area + top_area) / 2
                lateral_area = 2 * height_m * (width_m + depth_m) * 0.85
                area_m2 = base_area + top_area + lateral_area
            else:
                area_m2 = width_m * height_m * 1.5
            volume_m3 = area_m2 * thickness_m
            
        elif config.base_type == BaseType.WALL_MOUNTED:
            area_m2 = width_m * height_m
            # Add bracket material
            bracket_area = area_m2 * 0.15  # 15% additional for brackets
            area_m2 += bracket_area
            volume_m3 = area_m2 * thickness_m
            
        else:
            # Default fallback
            area_m2 = width_m * height_m
            volume_m3 = area_m2 * thickness_m
        
        # Calculate weight if density available
        material_info = self.prices.get(config.primary_material)
        weight_kg = 0.0
        if material_info and material_info.density:
            weight_kg = volume_m3 * material_info.density
        
        return {
            "area_m2": round(area_m2, 4),
            "volume_m3": round(volume_m3, 6),
            "weight_kg": round(weight_kg, 2),
            "thickness_m": thickness_m
        }
    
    def _get_waste_factor(self, material: MaterialType) -> float:
        """Get waste factor for material type."""
        waste_factors = {
            MaterialType.WOOD: 0.15,  # 15% waste
            MaterialType.PLYWOOD: 0.10,
            MaterialType.MDF: 0.10,
            MaterialType.ACRYLIC: 0.05,  # Less waste with laser cutting
            MaterialType.ALUMINUM: 0.10,
            MaterialType.STEEL: 0.10,
            MaterialType.PLASTIC_3D_PRINTED: 0.05,  # Minimal waste
            MaterialType.RESIN_3D_PRINTED: 0.08,
            MaterialType.CARDBOARD: 0.20,  # Higher waste
        }
        return waste_factors.get(material, 0.10)
    
    def _calculate_fastener_cost(self, config: BaseConfiguration) -> float:
        """Calculate cost of fasteners."""
        if not config.mounting_points:
            return 0.0
        
        # Estimate fastener costs
        fastener_costs = {
            "M3": 0.10,
            "M4": 0.12,
            "M5": 0.15,
            "M6": 0.20,
            "M8": 0.30,
            "M10": 0.50,
        }
        
        total_cost = 0.0
        for mp in config.mounting_points:
            thread = mp.thread_type or "M5"
            # Extract size from thread type (e.g., "M5" -> 0.15)
            for size, cost in fastener_costs.items():
                if size in thread:
                    total_cost += cost
                    break
            else:
                total_cost += 0.20  # Default cost
        
        # Add nuts and washers (double the screw cost)
        return total_cost * 2
    
    def _calculate_finish_cost(self, config: BaseConfiguration) -> float:
        """Calculate cost of finishes/coatings."""
        # Finish costs per square meter
        finish_costs = {
            MaterialType.WOOD: 15.0,  # Stain + polyurethane
            MaterialType.PLYWOOD: 10.0,  # Clear coat
            MaterialType.MDF: 12.0,  # Primer + paint
            MaterialType.ALUMINUM: 5.0,  # Anodizing (optional)
            MaterialType.STEEL: 8.0,  # Powder coating
        }
        
        if config.primary_material not in finish_costs:
            return 0.0
        
        material_usage = self._calculate_material_usage(config)
        area_m2 = material_usage["area_m2"]
        
        return area_m2 * finish_costs.get(config.primary_material, 0)
    
    def generate_cost_report(self, config: BaseConfiguration) -> str:
        """
        Generate a detailed cost report.
        
        Args:
            config: Base configuration
            
        Returns:
            Formatted cost report string
        """
        try:
            costs = self.calculate_material_cost(config)
        except ValueError as e:
            return f"Error calculating costs: {e}"
        
        report = f"Material Cost Estimate - {config.name}\n"
        report += "=" * 50 + "\n\n"
        
        report += f"Base Type: {config.base_type.value.replace('_', ' ').title()}\n"
        report += f"Material: {config.primary_material.value.replace('_', ' ').title()}\n"
        report += f"Dimensions: {self._format_dimensions(config)}\n"
        report += f"Material Thickness: {config.material_thickness} mm\n\n"
        
        report += "Material Usage:\n"
        report += f"  Area: {costs['material_usage']['area_m2']:.3f} m²\n"
        report += f"  Volume: {costs['material_usage']['volume_m3']*1000:.1f} L\n"
        if costs['material_usage']['weight_kg'] > 0:
            report += f"  Weight: {costs['material_usage']['weight_kg']:.2f} kg\n"
        report += f"  Waste Factor: {costs['waste_factor']*100:.0f}%\n\n"
        
        report += "Cost Breakdown:\n"
        report += f"  Material Cost: ${costs['material_cost']:.2f}\n"
        report += f"    ({costs['price_per_unit']} {costs['price_unit']})\n"
        if costs['fastener_cost'] > 0:
            report += f"  Fasteners: ${costs['fastener_cost']:.2f}\n"
        if costs['finish_cost'] > 0:
            report += f"  Finish/Coating: ${costs['finish_cost']:.2f}\n"
        report += f"\n  TOTAL: ${costs['subtotal']:.2f}\n"
        
        report += "\n" + "=" * 50 + "\n"
        report += "Note: Prices are estimates and may vary by supplier and location.\n"
        
        return report
    
    def _format_dimensions(self, config: BaseConfiguration) -> str:
        """Format dimensions as string."""
        dims = config.dimensions
        if hasattr(dims, 'width') and hasattr(dims, 'height'):
            if hasattr(dims, 'depth'):
                return f"{dims.width} × {dims.height} × {dims.depth} {dims.unit.value}"
            else:
                return f"{dims.width} × {dims.height} {dims.unit.value}"
        return "N/A"
    
    def save_prices(self, filepath: Path) -> None:
        """Save current prices to JSON file."""
        data = {}
        for material, cost_info in self.prices.items():
            data[material.value] = {
                "unit_price": cost_info.unit_price,
                "price_unit": cost_info.price_unit,
                "density": cost_info.density,
                "supplier": cost_info.supplier,
                "notes": cost_info.notes,
                "last_updated": datetime.now().isoformat()
            }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    def load_prices(self, filepath: Path) -> None:
        """Load prices from JSON file."""
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        for material_str, cost_data in data.items():
            try:
                material = MaterialType(material_str)
                self.prices[material] = MaterialCost(
                    material=material,
                    unit_price=cost_data["unit_price"],
                    price_unit=cost_data["price_unit"],
                    density=cost_data.get("density"),
                    supplier=cost_data.get("supplier"),
                    notes=cost_data.get("notes"),
                    last_updated=datetime.fromisoformat(cost_data["last_updated"])
                    if "last_updated" in cost_data else None
                )
            except ValueError:
                # Skip unknown materials
                pass


def estimate_project_cost(configs: List[BaseConfiguration],
                         custom_prices: Optional[Dict[MaterialType, MaterialCost]] = None) -> Dict[str, float]:
    """
    Estimate total cost for multiple base configurations.
    
    Args:
        configs: List of base configurations
        custom_prices: Optional custom material prices
        
    Returns:
        Dictionary with total cost breakdown
    """
    calculator = CostCalculator(custom_prices)
    
    total_material = 0.0
    total_fasteners = 0.0
    total_finish = 0.0
    
    for config in configs:
        costs = calculator.calculate_material_cost(config)
        total_material += costs["material_cost"]
        total_fasteners += costs["fastener_cost"]
        total_finish += costs["finish_cost"]
    
    return {
        "material_cost": round(total_material, 2),
        "fastener_cost": round(total_fasteners, 2),
        "finish_cost": round(total_finish, 2),
        "total_cost": round(total_material + total_fasteners + total_finish, 2),
        "num_bases": len(configs)
    }