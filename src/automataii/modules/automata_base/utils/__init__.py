"""Utility functions for automata base system."""

from automataii.modules.automata_base.utils.validators import validate_base_configuration
from automataii.modules.automata_base.utils.converters import base_to_svg, base_to_dxf
from automataii.modules.automata_base.utils.stl_exporter import (
    STLExporter,
    create_stl_from_config,
    Triangle
)
from automataii.modules.automata_base.utils.step_exporter import (
    STEPExporter,
    create_step_from_config
)
from automataii.modules.automata_base.utils.pdf_generator import (
    PDFGenerator,
    generate_assembly_pdf
)
from automataii.modules.automata_base.utils.cost_calculator import (
    CostCalculator,
    MaterialCost,
    estimate_project_cost
)
from automataii.modules.automata_base.utils.placement_optimizer import (
    PlacementOptimizer,
    GreedyPlacementOptimizer,
    SimulatedAnnealingOptimizer,
    optimize_placement,
    PlacementSolution,
    ComponentPlacement,
    PlacementStatus
)

__all__ = [
    "validate_base_configuration",
    "base_to_svg",
    "base_to_dxf",
    "STLExporter",
    "create_stl_from_config",
    "Triangle",
    "STEPExporter",
    "create_step_from_config",
    "PDFGenerator",
    "generate_assembly_pdf",
    "CostCalculator",
    "MaterialCost",
    "estimate_project_cost",
    "PlacementOptimizer",
    "GreedyPlacementOptimizer",
    "SimulatedAnnealingOptimizer",
    "optimize_placement",
    "PlacementSolution",
    "ComponentPlacement",
    "PlacementStatus",
]