#!/usr/bin/env python3
"""
Simplified dataset generator for automataii.
Generates mechanism paths using direct mathematical equations.
"""

import json
import numpy as np
import os
from typing import List, Dict, Tuple, Any
from scipy.optimize import fsolve

# Output path for the dataset
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), 'kinematics', 'generated_mechanism_paths.json')


def generate_fourbar_paths() -> List[Dict[str, Any]]:
    """Generate 4-bar linkage paths using direct kinematics."""
    print("Generating 4-bar linkages...")
    mechanisms = []
    
    # Parameter ranges for link lengths [L1, L2, L3, L4]
    link_configs = [
        (10, 40, 50, 60),    # Crank-rocker
        (20, 50, 40, 60),    # Double-crank
        (30, 60, 70, 80),    # Rocker-rocker
        (15, 45, 55, 65),    # Crank-rocker
        (25, 60, 50, 70),    # Double-crank
        (10, 30, 40, 50),    # Crank-rocker
        (20, 60, 70, 80),    # Rocker-rocker
        (15, 50, 60, 70),    # Rocker-rocker
    ]
    
    mech_id = 0
    for L1, L2, L3, L4 in link_configs:
        # Check Grashof condition
        lengths = sorted([L1, L2, L3, L4])
        if lengths[0] + lengths[3] > lengths[1] + lengths[2]:
            continue
        
        # Generate path for coupler midpoint
        theta = np.linspace(0, 2 * np.pi, 360)
        path_coords = []
        
        for t in theta:
            # Position of joint A (crank endpoint)
            Ax = L1 * np.cos(t)
            Ay = L1 * np.sin(t)
            
            # Solve for joint B position using constraint equations
            def constraint_equations(vars):
                Bx, By = vars
                # Distance constraints
                eq1 = (Bx - Ax)**2 + (By - Ay)**2 - L2**2  # Link 2 length
                eq2 = (Bx - L4)**2 + By**2 - L3**2  # Link 3 length
                return [eq1, eq2]
            
            try:
                # Initial guess
                B_guess = [L4/2, L2/2]
                result = fsolve(constraint_equations, B_guess)
                Bx, By = result
                
                # Coupler midpoint
                Px = (Ax + Bx) / 2
                Py = (Ay + By) / 2
                path_coords.append([float(Px), float(Py)])
            except:
                continue
        
        if len(path_coords) > 300:  # Valid path
            mechanisms.append({
                "type": "4-bar Coupler",
                "name": f"4-bar {mech_id}: L=({L1},{L2},{L3},{L4})",
                "parameters": {
                    "L1": L1,
                    "L2": L2,
                    "L3": L3,
                    "L4_ground": L4
                },
                "path_coordinates": path_coords
            })
            mech_id += 1
            print(f"  Generated 4-bar mechanism {mech_id}")
    
    return mechanisms


def generate_crankslider_paths() -> List[Dict[str, Any]]:
    """Generate crank-slider mechanism paths."""
    print("Generating crank-slider mechanisms...")
    mechanisms = []
    
    # Parameter ranges
    configs = [
        (10, 30, 0),    # No offset
        (15, 40, 5),    # Small offset
        (20, 50, -5),   # Negative offset
        (10, 40, 10),   # Large offset
        (25, 60, 0),    # No offset, larger
        (15, 50, -10),  # Large negative offset
        (30, 70, 5),    # Large mechanism
        (20, 60, 15),   # Very large offset
    ]
    
    mech_id = 0
    for crank_len, rod_len, offset in configs:
        if rod_len <= crank_len + abs(offset):
            continue  # Skip invalid configurations
        
        theta = np.linspace(0, 2 * np.pi, 360)
        path_coords = []
        
        for t in theta:
            # Crank endpoint
            Ax = crank_len * np.cos(t)
            Ay = crank_len * np.sin(t)
            
            # Slider position (moves horizontally at y = offset)
            # Using cosine law to find slider x position
            discriminant = rod_len**2 - (Ay - offset)**2
            if discriminant < 0:
                continue
                
            Bx = Ax + np.sqrt(discriminant)
            By = offset
            
            path_coords.append([float(Bx), float(By)])
        
        if len(path_coords) > 300:
            mechanisms.append({
                "type": "3-bar Output",
                "name": f"Crank-Slider {mech_id}: C={crank_len}, R={rod_len}, Off={offset}",
                "parameters": {
                    "crank_length": crank_len,
                    "connecting_rod_length": rod_len,
                    "offset": offset
                },
                "path_coordinates": path_coords
            })
            mech_id += 1
            print(f"  Generated crank-slider mechanism {mech_id}")
    
    return mechanisms


def generate_more_cam_profiles() -> List[Dict[str, Any]]:
    """Generate additional cam profile mechanisms."""
    print("Generating additional cam mechanisms...")
    mechanisms = []
    
    # More varied motion profiles
    motion_profiles = [
        # (rise1, dwell1, fall1, dwell2, rise2, dwell3, fall2)
        (30, 60, 30, 60, 20, 60, 20),   # Double rise-fall
        (40, 90, 40, 90, 0, 0, 0),      # Single rise-fall with long dwells
        (20, 45, 20, 45, 30, 90, 30),   # Asymmetric double
        (50, 120, 50, 60, 0, 0, 0),     # Large rise with dwell
    ]
    
    base_radii = [15, 25, 35]
    
    mech_id = 0
    for profile in motion_profiles:
        rise1, dwell1, fall1, dwell2, rise2, dwell3, fall2 = profile
        
        for base_radius in base_radii:
            theta = np.linspace(0, 2 * np.pi, 360)
            path_coords = []
            
            for t in theta:
                angle_deg = np.rad2deg(t) % 360
                s = 0  # displacement
                
                # Complex cam profile
                if angle_deg < rise1:
                    # First rise
                    s = (rise1/10) * (1 - np.cos(np.pi * angle_deg / rise1)) / 2
                elif angle_deg < rise1 + dwell1:
                    # First dwell
                    s = rise1/10
                elif angle_deg < rise1 + dwell1 + fall1:
                    # First fall
                    fall_angle = angle_deg - rise1 - dwell1
                    s = (rise1/10) * (1 + np.cos(np.pi * fall_angle / fall1)) / 2
                elif angle_deg < rise1 + dwell1 + fall1 + dwell2:
                    # Second dwell at base
                    s = 0
                elif rise2 > 0 and angle_deg < rise1 + dwell1 + fall1 + dwell2 + rise2:
                    # Second rise
                    rise_angle = angle_deg - rise1 - dwell1 - fall1 - dwell2
                    s = (rise2/10) * (1 - np.cos(np.pi * rise_angle / rise2)) / 2
                elif rise2 > 0 and angle_deg < rise1 + dwell1 + fall1 + dwell2 + rise2 + dwell3:
                    # Third dwell
                    s = rise2/10
                elif rise2 > 0:
                    # Second fall
                    fall_angle = angle_deg - rise1 - dwell1 - fall1 - dwell2 - rise2 - dwell3
                    if fall2 > 0 and fall_angle < fall2:
                        s = (rise2/10) * (1 + np.cos(np.pi * fall_angle / fall2)) / 2
                
                # Convert to x, y coordinates
                r = base_radius + s * 5  # Scale displacement
                x = r * np.cos(t)
                y = r * np.sin(t)
                path_coords.append([float(x), float(y)])
            
            mechanisms.append({
                "type": "Cam Profile",
                "name": f"Complex Cam {mech_id}: R={base_radius}",
                "parameters": {
                    "base_radius": base_radius,
                    "profile": "complex",
                    "rise_pattern": profile
                },
                "path_coordinates": path_coords
            })
            mech_id += 1
            print(f"  Generated complex cam mechanism {mech_id}")
    
    return mechanisms


def generate_more_gear_trains() -> List[Dict[str, Any]]:
    """Generate additional gear train mechanisms."""
    print("Generating additional gear mechanisms...")
    mechanisms = []
    
    # More gear configurations
    configs = [
        # (sun_radius, planet_radius, arm_length_ratio, num_lobes)
        (40, 20, 0.8, 2),   # 2-lobe hypocycloid
        (30, 15, 1.2, 2),   # 2-lobe hypocycloid extended
        (45, 15, 0.6, 3),   # 3-lobe hypocycloid
        (20, 20, 0.5, 1),   # Cardioid
        (20, 20, 1.5, 1),   # Extended cardioid
        (36, 12, 0.8, 3),   # 3-lobe hypocycloid
        (40, 10, 1.0, 4),   # 4-lobe hypocycloid
        (50, 25, 0.7, 2),   # Large 2-lobe
    ]
    
    mech_id = 0
    for sun_r, planet_r, arm_ratio, expected_lobes in configs:
        t = np.linspace(0, 2 * np.pi * expected_lobes, 360)
        path_coords = []
        
        for theta in t:
            if sun_r >= planet_r:
                # Hypocycloid
                ratio = (sun_r - planet_r) / planet_r
                x = (sun_r - planet_r) * np.cos(theta) + arm_ratio * planet_r * np.cos(ratio * theta)
                y = (sun_r - planet_r) * np.sin(theta) - arm_ratio * planet_r * np.sin(ratio * theta)
            else:
                # Epicycloid
                ratio = (sun_r + planet_r) / planet_r
                x = (sun_r + planet_r) * np.cos(theta) - arm_ratio * planet_r * np.cos(ratio * theta)
                y = (sun_r + planet_r) * np.sin(theta) - arm_ratio * planet_r * np.sin(ratio * theta)
            
            path_coords.append([float(x), float(y)])
        
        gear_type = "Hypocycloid" if sun_r >= planet_r else "Epicycloid"
        mechanisms.append({
            "type": "Gear Train",
            "name": f"{gear_type} {mech_id}: S={sun_r}, P={planet_r}, {expected_lobes}-lobe",
            "parameters": {
                "sun_radius": sun_r,
                "planet_radius": planet_r,
                "arm_ratio": arm_ratio,
                "gear_type": gear_type,
                "expected_lobes": expected_lobes
            },
            "path_coordinates": path_coords
        })
        mech_id += 1
        print(f"  Generated {gear_type} mechanism {mech_id}")
    
    return mechanisms


def load_existing_mechanisms() -> List[Dict[str, Any]]:
    """Load mechanisms that were already generated."""
    if os.path.exists(OUTPUT_PATH):
        with open(OUTPUT_PATH, 'r') as f:
            return json.load(f)
    return []


def main():
    """Main function to generate all mechanisms and save to JSON."""
    print("Starting simplified mechanism dataset generation...")
    
    # Load existing mechanisms (cam and gear from previous run)
    existing_mechanisms = load_existing_mechanisms()
    print(f"Loaded {len(existing_mechanisms)} existing mechanisms")
    
    # Generate new mechanisms
    new_mechanisms = []
    new_mechanisms.extend(generate_fourbar_paths())
    new_mechanisms.extend(generate_crankslider_paths())
    new_mechanisms.extend(generate_more_cam_profiles())
    new_mechanisms.extend(generate_more_gear_trains())
    
    # Combine all mechanisms
    all_mechanisms = existing_mechanisms + new_mechanisms
    
    print(f"\nTotal mechanisms in dataset: {len(all_mechanisms)}")
    
    # Save to JSON
    with open(OUTPUT_PATH, 'w') as f:
        json.dump(all_mechanisms, f, indent=2)
    
    print(f"Dataset saved to: {OUTPUT_PATH}")
    
    # Update toberemoved.md
    tobedeleted_path = os.path.join(os.path.dirname(__file__), '..', '..', 'toberemoved.md')
    if not os.path.exists(tobedeleted_path):
        with open(tobedeleted_path, 'w') as f:
            f.write("# Files to be removed\n\n")
    
    with open(tobedeleted_path, 'a') as f:
        f.write(f"\n- {os.path.abspath(__file__)} (simplified dataset generator script)\n")


if __name__ == "__main__":
    main()