"""
Test script for mechanism placement optimization.

This script demonstrates the placement optimization algorithms
using the generated dataset.
"""

import json
import time
from pathlib import Path
from typing import Optional
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import Rectangle, Circle, FancyBboxPatch
import numpy as np

from automataii.modules.automata_base.data.mechanism_placement_dataset import (
    PlacementDatasetGenerator, PlacementScenario
)
from automataii.modules.automata_base.utils.placement_optimizer import (
    optimize_placement, PlacementStatus
)


def visualize_placement(scenario: PlacementScenario, solution, 
                       title: str = "Placement Solution", 
                       save_path: Optional[Path] = None):
    """Visualize a placement solution."""
    fig, ax = plt.subplots(figsize=(10, 8))
    
    # Draw base
    base = scenario.base_layout
    ax.set_xlim(0, base.width)
    ax.set_ylim(0, base.height)
    ax.set_aspect('equal')
    
    # Draw mounting zones
    for zone in base.mounting_zones:
        if zone["type"] == "rectangle":
            rect = Rectangle((zone["x"], zone["y"]), 
                           zone["width"], zone["height"],
                           fill=False, edgecolor='green', 
                           linewidth=2, linestyle='--',
                           label='Mounting Zone')
            ax.add_patch(rect)
        elif zone["type"] == "circle":
            circle = Circle((zone["center_x"], zone["center_y"]), 
                          zone["radius"],
                          fill=False, edgecolor='green', 
                          linewidth=2, linestyle='--')
            ax.add_patch(circle)
    
    # Draw obstacles
    for obstacle in base.obstacles:
        if obstacle["type"] == "circle":
            circle = Circle((obstacle["center_x"], obstacle["center_y"]), 
                          obstacle["radius"],
                          fill=True, facecolor='red', alpha=0.3,
                          edgecolor='red', linewidth=2,
                          label='Obstacle')
            ax.add_patch(circle)
    
    # Draw preferred zones
    if base.preferred_zones:
        for zone in base.preferred_zones:
            if zone["type"] == "rectangle":
                rect = Rectangle((zone["x"], zone["y"]), 
                               zone["width"], zone["height"],
                               fill=True, facecolor='yellow', alpha=0.2,
                               edgecolor='orange', linewidth=1,
                               label='Preferred Zone')
                ax.add_patch(rect)
    
    # Draw components
    component_colors = {
        "gear": "blue",
        "linkage": "green",
        "cam": "purple",
        "motor": "red",
        "bearing": "orange",
        "platform": "brown"
    }
    
    for comp_id, placement in solution.placements.items():
        if placement.status != PlacementStatus.PLACED:
            continue
        
        component = next(c for c in scenario.components if c.id == comp_id)
        
        # Determine component type from ID
        comp_type = comp_id.split('_')[0]
        color = component_colors.get(comp_type, "gray")
        
        # Draw component rectangle
        # Create transform for rotation
        transform = plt.matplotlib.transforms.Affine2D().rotate_deg_around(
            placement.position.x, placement.position.y, placement.rotation
        ) + ax.transData
        
        # Draw main body
        rect = FancyBboxPatch(
            (placement.position.x - component.width/2, 
             placement.position.y - component.height/2),
            component.width, component.height,
            boxstyle="round,pad=2",
            facecolor=color, alpha=0.6,
            edgecolor='black', linewidth=2,
            transform=transform
        )
        ax.add_patch(rect)
        
        # Draw clearance circle
        clearance = Circle((placement.position.x, placement.position.y),
                         component.clearance_radius,
                         fill=False, edgecolor=color, 
                         linewidth=1, linestyle=':',
                         alpha=0.5)
        ax.add_patch(clearance)
        
        # Add component label
        ax.text(placement.position.x, placement.position.y, 
               comp_id, ha='center', va='center',
               fontsize=8, weight='bold')
        
        # Draw mounting points
        for mp in component.mounting_points:
            # Transform mounting point by rotation
            angle_rad = np.radians(placement.rotation)
            rot_x = mp.x * np.cos(angle_rad) - mp.y * np.sin(angle_rad)
            rot_y = mp.x * np.sin(angle_rad) + mp.y * np.cos(angle_rad)
            
            mount_x = placement.position.x + rot_x
            mount_y = placement.position.y + rot_y
            
            mount_circle = Circle((mount_x, mount_y), 2,
                                fill=True, facecolor='black')
            ax.add_patch(mount_circle)
    
    # Draw constraints
    for constraint in scenario.constraints:
        if constraint.type == "distance":
            # Draw line between constrained components
            comp_ids = constraint.component_ids
            if all(cid in solution.placements and 
                   solution.placements[cid].status == PlacementStatus.PLACED 
                   for cid in comp_ids[:2]):
                pos1 = solution.placements[comp_ids[0]].position
                pos2 = solution.placements[comp_ids[1]].position
                ax.plot([pos1.x, pos2.x], [pos1.y, pos2.y], 
                       'k--', alpha=0.3, linewidth=1)
                
                # Add distance label
                mid_x = (pos1.x + pos2.x) / 2
                mid_y = (pos1.y + pos2.y) / 2
                dist = np.sqrt((pos1.x - pos2.x)**2 + (pos1.y - pos2.y)**2)
                ax.text(mid_x, mid_y, f"{dist:.1f}mm", 
                       fontsize=7, ha='center',
                       bbox=dict(boxstyle="round,pad=0.3", 
                                facecolor='white', alpha=0.7))
    
    # Add title and info
    ax.set_title(f"{title}\nScore: {solution.total_score:.2f}, "
                f"Valid: {solution.is_valid}", fontsize=14)
    ax.set_xlabel("X (mm)")
    ax.set_ylabel("Y (mm)")
    ax.grid(True, alpha=0.3)
    
    # Add legend
    handles, labels = ax.get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    ax.legend(by_label.values(), by_label.keys(), 
             loc='upper left', bbox_to_anchor=(1.02, 1))
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()
    else:
        plt.show()


def test_placement_algorithms():
    """Test placement optimization algorithms."""
    print("Testing Placement Optimization Algorithms")
    print("=" * 50)
    
    # Load dataset
    dataset_path = Path(__file__).parent / "data" / "placement_dataset.json"
    generator = PlacementDatasetGenerator()
    scenarios = generator.load_dataset(dataset_path)
    
    print(f"\nLoaded {len(scenarios)} scenarios from dataset")
    
    # Create output directory for visualizations
    output_dir = Path("placement_results")
    output_dir.mkdir(exist_ok=True)
    
    # Test on a few scenarios
    test_scenarios = scenarios[:5]  # Test first 5
    
    results = []
    
    for i, scenario in enumerate(test_scenarios):
        print(f"\n--- Scenario {i+1}: {scenario.name} ---")
        print(f"Difficulty: {scenario.difficulty}")
        print(f"Components: {len(scenario.components)}")
        print(f"Constraints: {len(scenario.constraints)}")
        
        # Test greedy algorithm
        print("\nTesting Greedy Algorithm...")
        start_time = time.time()
        greedy_solution = optimize_placement(scenario, algorithm="greedy")
        greedy_time = time.time() - start_time
        
        print(f"  Time: {greedy_time:.3f}s")
        print(f"  Score: {greedy_solution.total_score:.2f}")
        print(f"  Valid: {greedy_solution.is_valid}")
        print(f"  Placed: {greedy_solution.metrics['placed_count']}/{len(scenario.components)}")
        
        # Test simulated annealing
        print("\nTesting Simulated Annealing...")
        start_time = time.time()
        sa_solution = optimize_placement(scenario, algorithm="sa")
        sa_time = time.time() - start_time
        
        print(f"  Time: {sa_time:.3f}s")
        print(f"  Score: {sa_solution.total_score:.2f}")
        print(f"  Valid: {sa_solution.is_valid}")
        print(f"  Placed: {sa_solution.metrics['placed_count']}/{len(scenario.components)}")
        
        # Compare results
        print(f"\nImprovement: {sa_solution.total_score - greedy_solution.total_score:.2f} "
              f"({(sa_solution.total_score/greedy_solution.total_score - 1)*100:.1f}%)")
        
        # Visualize both solutions
        visualize_placement(
            scenario, greedy_solution,
            title=f"Greedy Algorithm - {scenario.name}",
            save_path=output_dir / f"scenario_{i+1}_greedy.png"
        )
        
        visualize_placement(
            scenario, sa_solution,
            title=f"Simulated Annealing - {scenario.name}",
            save_path=output_dir / f"scenario_{i+1}_sa.png"
        )
        
        # Store results
        results.append({
            "scenario": scenario.name,
            "difficulty": scenario.difficulty,
            "num_components": len(scenario.components),
            "greedy_score": greedy_solution.total_score,
            "greedy_time": greedy_time,
            "greedy_valid": greedy_solution.is_valid,
            "sa_score": sa_solution.total_score,
            "sa_time": sa_time,
            "sa_valid": sa_solution.is_valid,
            "improvement": sa_solution.total_score - greedy_solution.total_score
        })
    
    # Summary statistics
    print("\n" + "=" * 50)
    print("SUMMARY STATISTICS")
    print("=" * 50)
    
    avg_greedy_score = np.mean([r["greedy_score"] for r in results])
    avg_sa_score = np.mean([r["sa_score"] for r in results])
    avg_improvement = np.mean([r["improvement"] for r in results])
    
    print(f"\nAverage Scores:")
    print(f"  Greedy: {avg_greedy_score:.2f}")
    print(f"  SA: {avg_sa_score:.2f}")
    print(f"  Improvement: {avg_improvement:.2f} ({(avg_sa_score/avg_greedy_score - 1)*100:.1f}%)")
    
    print(f"\nAverage Times:")
    print(f"  Greedy: {np.mean([r['greedy_time'] for r in results]):.3f}s")
    print(f"  SA: {np.mean([r['sa_time'] for r in results]):.3f}s")
    
    print(f"\nSuccess Rate:")
    greedy_success = sum(1 for r in results if r["greedy_valid"]) / len(results) * 100
    sa_success = sum(1 for r in results if r["sa_valid"]) / len(results) * 100
    print(f"  Greedy: {greedy_success:.1f}%")
    print(f"  SA: {sa_success:.1f}%")
    
    print(f"\nResults saved to: {output_dir.absolute()}")
    
    # Save results to JSON
    results_file = output_dir / "optimization_results.json"
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"Detailed results saved to: {results_file}")


def test_specific_scenario():
    """Test optimization on a specific challenging scenario."""
    print("\nTesting Specific Challenging Scenario")
    print("=" * 50)
    
    # Create a challenging scenario
    generator = PlacementDatasetGenerator(seed=42)
    scenario = generator.generate_scenario(difficulty="hard", component_count=10)
    
    print(f"Generated scenario with {len(scenario.components)} components")
    
    # Optimize
    print("\nOptimizing placement...")
    solution = optimize_placement(scenario, algorithm="sa")
    
    print(f"\nResults:")
    print(f"  Score: {solution.total_score:.2f}")
    print(f"  Valid: {solution.is_valid}")
    print(f"  Metrics:")
    for metric, value in solution.metrics.items():
        print(f"    {metric}: {value:.3f}")
    
    if solution.violations:
        print(f"\nViolations:")
        for v in solution.violations:
            print(f"  - {v}")
    
    # Visualize
    visualize_placement(scenario, solution, 
                       title="Challenging Scenario - SA Optimization")


if __name__ == "__main__":
    # Ensure matplotlib works without display
    import matplotlib
    matplotlib.use('Agg')
    
    test_placement_algorithms()
    # test_specific_scenario()  # Uncomment to test specific scenario