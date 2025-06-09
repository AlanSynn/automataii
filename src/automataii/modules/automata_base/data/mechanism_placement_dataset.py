"""
Generate dataset for mechanism placement optimization.

This module creates synthetic mechanism placement scenarios with various
constraints and optimal solutions for training/testing placement algorithms.
"""

import json
import random
import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime

from automataii.modules.automata_base.enums.base_types import BaseType
from automataii.modules.automata_base.models.dimensions import Point2D


@dataclass
class MechanismComponent:
    """Represents a single mechanism component to be placed."""
    id: str
    width: float  # mm
    height: float  # mm
    weight: float  # grams
    center_of_mass: Point2D  # relative to component origin
    mounting_points: List[Point2D]  # relative positions
    clearance_radius: float  # minimum clearance needed
    rotation_allowed: bool = True
    rotation_step: float = 90.0  # degrees
    priority: int = 1  # Higher priority placed first
    constraints: Optional[Dict[str, any]] = None


@dataclass
class PlacementConstraint:
    """Constraints for component placement."""
    type: str  # "distance", "alignment", "zone", "orientation"
    component_ids: List[str]
    parameters: Dict[str, any]


@dataclass
class BaseLayout:
    """Base configuration for placement."""
    base_type: BaseType
    width: float  # mm
    height: float  # mm
    mounting_zones: List[Dict[str, any]]  # Available mounting areas
    obstacles: List[Dict[str, any]]  # Areas to avoid
    preferred_zones: Optional[List[Dict[str, any]]] = None


@dataclass
class PlacementScenario:
    """A complete placement scenario."""
    id: str
    name: str
    base_layout: BaseLayout
    components: List[MechanismComponent]
    constraints: List[PlacementConstraint]
    optimal_solution: Optional[Dict[str, any]] = None
    difficulty: str = "medium"  # easy, medium, hard
    tags: Optional[List[str]] = None


class PlacementDatasetGenerator:
    """Generates datasets for mechanism placement optimization."""
    
    def __init__(self, seed: Optional[int] = None):
        """Initialize generator with optional seed for reproducibility."""
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)
    
    def generate_component(self, component_type: str, size_class: str = "medium") -> MechanismComponent:
        """Generate a mechanism component based on type."""
        # Size multipliers
        size_factors = {
            "small": 0.7,
            "medium": 1.0,
            "large": 1.3
        }
        factor = size_factors.get(size_class, 1.0)
        
        # Component templates
        templates = {
            "gear": {
                "width": 40 * factor,
                "height": 40 * factor,
                "weight": 50 * factor,
                "clearance_radius": 25 * factor,
                "mounting_points": [(0, 0)],  # Center mount
                "rotation_allowed": True
            },
            "linkage": {
                "width": 80 * factor,
                "height": 20 * factor,
                "weight": 30 * factor,
                "clearance_radius": 10 * factor,
                "mounting_points": [(-30 * factor, 0), (30 * factor, 0)],  # End mounts
                "rotation_allowed": True
            },
            "cam": {
                "width": 50 * factor,
                "height": 50 * factor,
                "weight": 60 * factor,
                "clearance_radius": 30 * factor,
                "mounting_points": [(0, 0)],  # Center mount
                "rotation_allowed": True
            },
            "motor": {
                "width": 60 * factor,
                "height": 40 * factor,
                "weight": 200 * factor,
                "clearance_radius": 5 * factor,
                "mounting_points": [(-20 * factor, -15 * factor), (20 * factor, -15 * factor),
                                   (-20 * factor, 15 * factor), (20 * factor, 15 * factor)],
                "rotation_allowed": True,
                "rotation_step": 90.0
            },
            "bearing": {
                "width": 30 * factor,
                "height": 30 * factor,
                "weight": 40 * factor,
                "clearance_radius": 18 * factor,
                "mounting_points": [(0, 0)],
                "rotation_allowed": False
            },
            "platform": {
                "width": 100 * factor,
                "height": 80 * factor,
                "weight": 150 * factor,
                "clearance_radius": 5 * factor,
                "mounting_points": [(-40 * factor, -30 * factor), (40 * factor, -30 * factor),
                                   (-40 * factor, 30 * factor), (40 * factor, 30 * factor)],
                "rotation_allowed": True,
                "rotation_step": 90.0
            }
        }
        
        template = templates.get(component_type, templates["gear"])
        
        # Add some randomness
        width = template["width"] * random.uniform(0.9, 1.1)
        height = template["height"] * random.uniform(0.9, 1.1)
        weight = template["weight"] * random.uniform(0.8, 1.2)
        
        # Center of mass (with slight offset)
        com_x = random.uniform(-width * 0.1, width * 0.1)
        com_y = random.uniform(-height * 0.1, height * 0.1)
        
        # Convert mounting points to Point2D
        mounting_points = [Point2D(x, y) for x, y in template["mounting_points"]]
        
        return MechanismComponent(
            id=f"{component_type}_{random.randint(1000, 9999)}",
            width=width,
            height=height,
            weight=weight,
            center_of_mass=Point2D(com_x, com_y),
            mounting_points=mounting_points,
            clearance_radius=template["clearance_radius"],
            rotation_allowed=template["rotation_allowed"],
            rotation_step=template.get("rotation_step", 90.0),
            priority=random.randint(1, 5)
        )
    
    def generate_base_layout(self, base_type: BaseType, size: str = "medium") -> BaseLayout:
        """Generate a base layout configuration."""
        # Base sizes
        sizes = {
            "small": (200, 150),
            "medium": (300, 200),
            "large": (400, 300),
            "xlarge": (500, 400)
        }
        
        width, height = sizes.get(size, (300, 200))
        
        # Define mounting zones based on base type
        if base_type == BaseType.FLAT_RECTANGULAR:
            # Full area minus margins
            margin = 20
            mounting_zones = [{
                "type": "rectangle",
                "x": margin,
                "y": margin,
                "width": width - 2 * margin,
                "height": height - 2 * margin
            }]
            obstacles = []
            
        elif base_type == BaseType.FLAT_CIRCULAR:
            # Circular mounting area
            radius = min(width, height) / 2 - 20
            mounting_zones = [{
                "type": "circle",
                "center_x": width / 2,
                "center_y": height / 2,
                "radius": radius
            }]
            obstacles = []
            
        elif base_type == BaseType.BOX_OPEN:
            # Interior area with wall thickness
            wall = 10
            mounting_zones = [{
                "type": "rectangle",
                "x": wall,
                "y": wall,
                "width": width - 2 * wall,
                "height": height - 2 * wall
            }]
            obstacles = []
            
        else:
            # Default rectangular
            mounting_zones = [{
                "type": "rectangle",
                "x": 10,
                "y": 10,
                "width": width - 20,
                "height": height - 20
            }]
            obstacles = []
        
        # Add some random obstacles
        if random.random() > 0.5:
            num_obstacles = random.randint(1, 3)
            for _ in range(num_obstacles):
                obs_x = random.uniform(50, width - 50)
                obs_y = random.uniform(50, height - 50)
                obs_size = random.uniform(20, 40)
                obstacles.append({
                    "type": "circle",
                    "center_x": obs_x,
                    "center_y": obs_y,
                    "radius": obs_size / 2
                })
        
        # Add preferred zones (e.g., for heavy components)
        preferred_zones = []
        if random.random() > 0.6:
            # Center zone for stability
            preferred_zones.append({
                "type": "rectangle",
                "x": width * 0.3,
                "y": height * 0.3,
                "width": width * 0.4,
                "height": height * 0.4,
                "weight": 2.0  # Preference weight
            })
        
        return BaseLayout(
            base_type=base_type,
            width=width,
            height=height,
            mounting_zones=mounting_zones,
            obstacles=obstacles,
            preferred_zones=preferred_zones if preferred_zones else None
        )
    
    def generate_constraints(self, components: List[MechanismComponent]) -> List[PlacementConstraint]:
        """Generate placement constraints between components."""
        constraints = []
        
        # Add some distance constraints
        if len(components) >= 2:
            # Minimum distance between gears
            gear_ids = [c.id for c in components if "gear" in c.id]
            if len(gear_ids) >= 2:
                constraints.append(PlacementConstraint(
                    type="distance",
                    component_ids=gear_ids[:2],
                    parameters={
                        "min_distance": 5.0,
                        "max_distance": 100.0
                    }
                ))
            
            # Alignment constraint for linkages
            linkage_ids = [c.id for c in components if "linkage" in c.id]
            if len(linkage_ids) >= 2:
                constraints.append(PlacementConstraint(
                    type="alignment",
                    component_ids=linkage_ids[:2],
                    parameters={
                        "axis": "horizontal",
                        "tolerance": 10.0
                    }
                ))
            
            # Motor should be in lower half (zone constraint)
            motor_ids = [c.id for c in components if "motor" in c.id]
            if motor_ids:
                constraints.append(PlacementConstraint(
                    type="zone",
                    component_ids=[motor_ids[0]],
                    parameters={
                        "zone": "lower_half",
                        "margin": 10.0
                    }
                ))
        
        return constraints
    
    def generate_scenario(self, difficulty: str = "medium", 
                         component_count: Optional[int] = None) -> PlacementScenario:
        """Generate a complete placement scenario."""
        # Determine component count based on difficulty
        if component_count is None:
            count_ranges = {
                "easy": (2, 4),
                "medium": (4, 7),
                "hard": (7, 12)
            }
            min_count, max_count = count_ranges.get(difficulty, (4, 7))
            component_count = random.randint(min_count, max_count)
        
        # Generate base layout
        base_sizes = {
            "easy": "large",
            "medium": "medium",
            "hard": "medium"
        }
        base_size = base_sizes.get(difficulty, "medium")
        base_type = random.choice([BaseType.FLAT_RECTANGULAR, BaseType.FLAT_CIRCULAR, BaseType.BOX_OPEN])
        base_layout = self.generate_base_layout(base_type, base_size)
        
        # Generate components
        component_types = ["gear", "linkage", "cam", "motor", "bearing", "platform"]
        components = []
        
        for i in range(component_count):
            comp_type = random.choice(component_types)
            size_class = random.choice(["small", "medium", "large"])
            component = self.generate_component(comp_type, size_class)
            component.priority = component_count - i  # Earlier components have higher priority
            components.append(component)
        
        # Generate constraints
        constraints = self.generate_constraints(components)
        
        # Create scenario
        scenario_id = f"scenario_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{random.randint(1000, 9999)}"
        
        tags = [difficulty, base_type.value]
        if len(components) > 6:
            tags.append("complex")
        if any("motor" in c.id for c in components):
            tags.append("motorized")
        
        return PlacementScenario(
            id=scenario_id,
            name=f"{difficulty.title()} {base_type.value} placement",
            base_layout=base_layout,
            components=components,
            constraints=constraints,
            difficulty=difficulty,
            tags=tags
        )
    
    def generate_dataset(self, num_scenarios: int, 
                        output_path: Optional[Path] = None) -> List[PlacementScenario]:
        """Generate a complete dataset of placement scenarios."""
        scenarios = []
        
        # Generate scenarios with different difficulties
        difficulty_distribution = {
            "easy": int(num_scenarios * 0.3),
            "medium": int(num_scenarios * 0.5),
            "hard": int(num_scenarios * 0.2)
        }
        
        for difficulty, count in difficulty_distribution.items():
            for _ in range(count):
                scenario = self.generate_scenario(difficulty)
                scenarios.append(scenario)
        
        # Save to file if path provided
        if output_path:
            self.save_dataset(scenarios, output_path)
        
        return scenarios
    
    def save_dataset(self, scenarios: List[PlacementScenario], output_path: Path):
        """Save dataset to JSON file."""
        data = {
            "metadata": {
                "version": "1.0",
                "created": datetime.now().isoformat(),
                "num_scenarios": len(scenarios),
                "difficulties": {
                    "easy": sum(1 for s in scenarios if s.difficulty == "easy"),
                    "medium": sum(1 for s in scenarios if s.difficulty == "medium"),
                    "hard": sum(1 for s in scenarios if s.difficulty == "hard")
                }
            },
            "scenarios": []
        }
        
        # Convert scenarios to dict format
        for scenario in scenarios:
            scenario_dict = {
                "id": scenario.id,
                "name": scenario.name,
                "difficulty": scenario.difficulty,
                "tags": scenario.tags,
                "base_layout": {
                    "base_type": scenario.base_layout.base_type.value,
                    "width": scenario.base_layout.width,
                    "height": scenario.base_layout.height,
                    "mounting_zones": scenario.base_layout.mounting_zones,
                    "obstacles": scenario.base_layout.obstacles,
                    "preferred_zones": scenario.base_layout.preferred_zones
                },
                "components": [
                    {
                        "id": c.id,
                        "width": c.width,
                        "height": c.height,
                        "weight": c.weight,
                        "center_of_mass": {"x": c.center_of_mass.x, "y": c.center_of_mass.y},
                        "mounting_points": [{"x": p.x, "y": p.y} for p in c.mounting_points],
                        "clearance_radius": c.clearance_radius,
                        "rotation_allowed": c.rotation_allowed,
                        "rotation_step": c.rotation_step,
                        "priority": c.priority,
                        "constraints": c.constraints
                    }
                    for c in scenario.components
                ],
                "constraints": [
                    {
                        "type": c.type,
                        "component_ids": c.component_ids,
                        "parameters": c.parameters
                    }
                    for c in scenario.constraints
                ],
                "optimal_solution": scenario.optimal_solution
            }
            data["scenarios"].append(scenario_dict)
        
        # Save to file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"Dataset saved to: {output_path}")
        print(f"Total scenarios: {len(scenarios)}")
    
    def load_dataset(self, input_path: Path) -> List[PlacementScenario]:
        """Load dataset from JSON file."""
        with open(input_path, 'r') as f:
            data = json.load(f)
        
        scenarios = []
        for scenario_data in data["scenarios"]:
            # Reconstruct components
            components = []
            for comp_data in scenario_data["components"]:
                component = MechanismComponent(
                    id=comp_data["id"],
                    width=comp_data["width"],
                    height=comp_data["height"],
                    weight=comp_data["weight"],
                    center_of_mass=Point2D(comp_data["center_of_mass"]["x"], 
                                          comp_data["center_of_mass"]["y"]),
                    mounting_points=[Point2D(p["x"], p["y"]) for p in comp_data["mounting_points"]],
                    clearance_radius=comp_data["clearance_radius"],
                    rotation_allowed=comp_data["rotation_allowed"],
                    rotation_step=comp_data["rotation_step"],
                    priority=comp_data["priority"],
                    constraints=comp_data.get("constraints")
                )
                components.append(component)
            
            # Reconstruct constraints
            constraints = []
            for const_data in scenario_data["constraints"]:
                constraint = PlacementConstraint(
                    type=const_data["type"],
                    component_ids=const_data["component_ids"],
                    parameters=const_data["parameters"]
                )
                constraints.append(constraint)
            
            # Reconstruct base layout
            base_layout = BaseLayout(
                base_type=BaseType(scenario_data["base_layout"]["base_type"]),
                width=scenario_data["base_layout"]["width"],
                height=scenario_data["base_layout"]["height"],
                mounting_zones=scenario_data["base_layout"]["mounting_zones"],
                obstacles=scenario_data["base_layout"]["obstacles"],
                preferred_zones=scenario_data["base_layout"].get("preferred_zones")
            )
            
            # Create scenario
            scenario = PlacementScenario(
                id=scenario_data["id"],
                name=scenario_data["name"],
                base_layout=base_layout,
                components=components,
                constraints=constraints,
                optimal_solution=scenario_data.get("optimal_solution"),
                difficulty=scenario_data["difficulty"],
                tags=scenario_data.get("tags")
            )
            scenarios.append(scenario)
        
        return scenarios


def generate_placement_dataset(num_scenarios: int = 100, 
                              output_file: str = "placement_dataset.json",
                              seed: Optional[int] = 42) -> Path:
    """
    Generate a dataset for mechanism placement optimization.
    
    Args:
        num_scenarios: Number of scenarios to generate
        output_file: Output filename
        seed: Random seed for reproducibility
    
    Returns:
        Path to the generated dataset file
    """
    generator = PlacementDatasetGenerator(seed=seed)
    output_path = Path(__file__).parent / output_file
    
    scenarios = generator.generate_dataset(num_scenarios, output_path)
    
    return output_path


if __name__ == "__main__":
    # Generate a sample dataset
    dataset_path = generate_placement_dataset(num_scenarios=50)
    print(f"\nDataset generated at: {dataset_path}")