#!/usr/bin/env python3
"""
Generate a comprehensive mechanism path dataset for the automataii project.
This script creates various mechanism configurations and samples their paths.
Version 2: Simplified with better error handling
"""

import json
import numpy as np
import sys
import os
from typing import List, Dict, Any, Tuple

# Add the macanism directory to the Python path
macanism_path = os.path.join(os.path.dirname(__file__), 'macanism')
sys.path.insert(0, macanism_path)

print(f"Adding to sys.path: {macanism_path}")

# Import mechanism modules with detailed error handling
try:
    from mechanism import get_joints, Vector, Mechanism
    print("✓ Imported core mechanism modules")
except ImportError as e:
    print(f"✗ Failed to import core modules: {e}")
    sys.exit(1)

try:
    from mechanism.cams import Cam
    print("✓ Imported Cam module")
except ImportError as e:
    print(f"✗ Failed to import Cam module: {e}")
    # Continue without cam generation
    Cam = None

import warnings
warnings.filterwarnings('ignore')


def normalize_path(path_coords: List[Tuple[float, float]], 
                  target_bounds: Tuple[float, float] = (-1.0, 1.0)) -> List[List[float]]:
    """Normalize path coordinates to fit within target bounds."""
    if not path_coords:
        return []
    
    coords_array = np.array(path_coords)
    
    # Find current bounds
    min_vals = coords_array.min(axis=0)
    max_vals = coords_array.max(axis=0)
    ranges = max_vals - min_vals
    
    # Avoid division by zero
    ranges[ranges == 0] = 1
    
    # Normalize to [0, 1] then scale to target bounds
    normalized = (coords_array - min_vals) / ranges
    scaled = normalized * (target_bounds[1] - target_bounds[0]) + target_bounds[0]
    
    return scaled.tolist()


def generate_simple_fourbar() -> List[Dict[str, Any]]:
    """Generate a few simple 4-bar linkage configurations to test."""
    mechanisms = []
    
    # Simple test configuration
    configs = [
        {"L1": 1.0, "L2": 2.0, "L3": 2.5, "L4": 3.0, "lc": 0.5, "beta": 0},
        {"L1": 1.2, "L2": 2.5, "L3": 2.0, "L4": 3.2, "lc": 0.7, "beta": 30},
        {"L1": 1.0, "L2": 3.0, "L3": 2.5, "L4": 3.5, "lc": 1.0, "beta": -45},
    ]
    
    for i, cfg in enumerate(configs):
        print(f"\nTesting 4-bar config {i+1}/{len(configs)}")
        try:
            # Create joints
            O, A, B, C, D = get_joints("O A B C D")
            D.follow = True
            
            # Create vectors
            a = Vector((O, A), r=cfg["L1"])
            b = Vector((O, C), r=cfg["L4"], theta=0, style="ground")
            c = Vector((A, B), r=cfg["L2"])
            d = Vector((C, B), r=cfg["L3"])
            
            # Coupler point
            beta_rad = np.deg2rad(cfg["beta"])
            e = Vector((A, D), r=cfg["L2"] * cfg["lc"])
            f = Vector((O, D), show=False)
            
            print("  ✓ Created vectors")
            
            def loops(x, inp):
                try:
                    # Loop 1: O->A->B->C->O
                    loop1 = a(inp) + c(x[0]) - d(x[1]) - b()
                    # Loop 2: O->A->D->O  
                    loop2 = a(inp) + e(x[0] + beta_rad) - f(x[2], x[3])
                    return np.array([loop1[0], loop1[1], loop2[0], loop2[1]])
                except Exception as e:
                    print(f"    Error in loops: {e}")
                    raise
            
            # Simulate mechanism
            t2 = np.linspace(0, 2 * np.pi, 50)  # Fewer points for testing
            guess = np.array([np.pi/4, 3*np.pi/4, cfg["L2"], np.pi/2])
            
            print("  Creating mechanism...")
            mechanism = Mechanism(
                vectors=(a, b, c, d, e, f),
                origin=O,
                pos=t2,
                guess=(guess,),
                loops=loops
            )
            
            print("  Iterating...")
            mechanism.iterate()
            print("  ✓ Iteration complete")
            
            # Extract path
            path_coords = []
            if "D" in mechanism.joints and "pos" in mechanism.joints["D"]:
                xy_data = mechanism.joints["D"]["pos"]["xy"]
                for i in range(len(xy_data[0])):
                    x = float(xy_data[0][i])
                    y = float(xy_data[1][i])
                    if not (np.isnan(x) or np.isnan(y) or np.isinf(x) or np.isinf(y)):
                        path_coords.append([x, y])
            
            print(f"  ✓ Extracted {len(path_coords)} path points")
            
            if len(path_coords) > 10:
                mechanisms.append({
                    "type": "4-bar Coupler",
                    "name": f"Test 4-bar #{i+1}",
                    "parameters": cfg,
                    "path_coordinates": normalize_path(path_coords)
                })
                print("  ✓ Added to dataset")
            
        except Exception as e:
            print(f"  ✗ Failed: {str(e)[:200]}")
            import traceback
            traceback.print_exc()
    
    return mechanisms


def generate_synthetic_paths() -> List[Dict[str, Any]]:
    """Generate synthetic paths using mathematical functions."""
    mechanisms = []
    
    # Generate some synthetic paths
    t = np.linspace(0, 2 * np.pi, 100)
    
    # Figure-8 path
    x = np.sin(t)
    y = np.sin(2 * t) / 2
    path_coords = [[float(x[i]), float(y[i])] for i in range(len(t))]
    mechanisms.append({
        "type": "4-bar Coupler",
        "name": "Synthetic Figure-8",
        "parameters": {"synthetic": True, "pattern": "figure-8"},
        "path_coordinates": normalize_path(path_coords)
    })
    
    # Elliptical paths with different eccentricities
    for a, b in [(2, 1), (3, 1), (1.5, 1)]:
        x = a * np.cos(t)
        y = b * np.sin(t)
        path_coords = [[float(x[i]), float(y[i])] for i in range(len(t))]
        mechanisms.append({
            "type": "4-bar Coupler",
            "name": f"Synthetic Ellipse a={a} b={b}",
            "parameters": {"synthetic": True, "a": a, "b": b},
            "path_coordinates": normalize_path(path_coords)
        })
    
    # Teardrop shape
    x = 1.5 * np.cos(t) 
    y = 2 * np.sin(t) - np.sin(2 * t) / 2
    path_coords = [[float(x[i]), float(y[i])] for i in range(len(t))]
    mechanisms.append({
        "type": "4-bar Coupler", 
        "name": "Synthetic Teardrop",
        "parameters": {"synthetic": True, "pattern": "teardrop"},
        "path_coordinates": normalize_path(path_coords)
    })
    
    # Linear motion (crank-slider like)
    for offset in [-0.5, 0, 0.5]:
        x = 2 * np.cos(t) + 1
        y = np.full_like(t, offset)
        path_coords = [[float(x[i]), float(y[i])] for i in range(len(t))]
        mechanisms.append({
            "type": "3-bar Output",
            "name": f"Synthetic Linear offset={offset}",
            "parameters": {"synthetic": True, "offset": offset},
            "path_coordinates": normalize_path(path_coords)
        })
    
    # Cam-like profiles
    # Simple rise-dwell-fall
    angles = np.linspace(0, 2 * np.pi, 100)
    r = np.ones_like(angles) * 4
    # Rise
    r[0:25] = 4 + 2 * np.sin(np.linspace(0, np.pi/2, 25))
    # Dwell at top
    r[25:50] = 6
    # Fall
    r[50:75] = 4 + 2 * np.sin(np.linspace(np.pi/2, np.pi, 25))
    # Dwell at bottom
    r[75:] = 4
    
    x = r * np.cos(angles)
    y = r * np.sin(angles)
    path_coords = [[float(x[i]), float(y[i])] for i in range(len(angles))]
    mechanisms.append({
        "type": "Cam Profile",
        "name": "Synthetic Rise-Dwell-Fall Cam",
        "parameters": {"synthetic": True, "base_radius": 4, "lift": 2},
        "path_coordinates": normalize_path(path_coords)
    })
    
    print(f"Generated {len(mechanisms)} synthetic paths")
    return mechanisms


def main():
    """Main function to generate the dataset."""
    print("\n=== Mechanism Path Dataset Generator V2 ===\n")
    
    all_mechanisms = []
    
    # Try to generate real mechanisms
    print("Attempting to generate real 4-bar mechanisms...")
    real_mechanisms = generate_simple_fourbar()
    all_mechanisms.extend(real_mechanisms)
    print(f"Generated {len(real_mechanisms)} real mechanisms")
    
    # Generate synthetic paths as fallback/supplement
    print("\nGenerating synthetic mechanism paths...")
    synthetic_mechanisms = generate_synthetic_paths()
    all_mechanisms.extend(synthetic_mechanisms)
    
    # Output path
    output_path = os.path.join(
        os.path.dirname(__file__),
        "kinematics",
        "generated_mechanism_paths.json"
    )
    
    # Load existing data
    existing_data = []
    if os.path.exists(output_path):
        try:
            with open(output_path, 'r') as f:
                existing_data = json.load(f)
            print(f"\nLoaded {len(existing_data)} existing mechanisms")
        except Exception as e:
            print(f"\nCould not load existing data: {e}")
    
    # Merge datasets
    existing_names = {m.get("name", "") for m in existing_data}
    new_mechanisms = [m for m in all_mechanisms if m.get("name", "") not in existing_names]
    
    combined_data = existing_data + new_mechanisms
    
    # Save
    print(f"\nSaving {len(new_mechanisms)} new mechanisms...")
    with open(output_path, 'w') as f:
        json.dump(combined_data, f, indent=2)
    
    print(f"\n=== Summary ===")
    print(f"Total mechanisms: {len(combined_data)}")
    print(f"New mechanisms added: {len(new_mechanisms)}")
    print(f"Saved to: {output_path}")
    
    # Type distribution
    type_counts = {}
    for mech in combined_data:
        mech_type = mech.get("type", "Unknown")
        type_counts[mech_type] = type_counts.get(mech_type, 0) + 1
    
    print("\nMechanism type distribution:")
    for mech_type, count in sorted(type_counts.items()):
        print(f"  {mech_type}: {count}")


if __name__ == "__main__":
    main()