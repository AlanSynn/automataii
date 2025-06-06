#!/usr/bin/env python3
"""
Generate a comprehensive synthetic mechanism path dataset.
Since the macanism library has some issues, we'll generate mathematically-defined paths
that represent typical mechanism behaviors.
"""

import json
import numpy as np
import os
from typing import List, Dict, Any, Tuple


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


def generate_fourbar_coupler_curves() -> List[Dict[str, Any]]:
    """Generate various 4-bar linkage coupler curves using parametric equations."""
    mechanisms = []
    t = np.linspace(0, 2 * np.pi, 100)
    
    # Classic coupler curves
    coupler_patterns = [
        # Figure-8 (symmetric)
        {
            "name": "Figure-8 Symmetric",
            "x": lambda t: np.sin(t),
            "y": lambda t: np.sin(2 * t) / 2,
            "params": {"L1": 1.0, "L2": 2.5, "L3": 2.5, "L4": 3.0, "lc_ratio": 0.8, "beta_coupler": 0}
        },
        # Figure-8 (asymmetric)
        {
            "name": "Figure-8 Asymmetric", 
            "x": lambda t: 1.2 * np.sin(t) + 0.3 * np.sin(2 * t),
            "y": lambda t: np.sin(2 * t) / 1.8,
            "params": {"L1": 1.2, "L2": 2.8, "L3": 2.2, "L4": 3.2, "lc_ratio": 0.7, "beta_coupler": 15}
        },
        # Teardrop
        {
            "name": "Teardrop Shape",
            "x": lambda t: 1.5 * np.cos(t),
            "y": lambda t: 2 * np.sin(t) - 0.5 * np.sin(2 * t),
            "params": {"L1": 1.0, "L2": 3.0, "L3": 2.5, "L4": 3.5, "lc_ratio": 1.2, "beta_coupler": -30}
        },
        # Bean/Kidney shape
        {
            "name": "Bean Shape",
            "x": lambda t: (1 + 0.5 * np.cos(3 * t)) * np.cos(t),
            "y": lambda t: (1 + 0.5 * np.cos(3 * t)) * np.sin(t),
            "params": {"L1": 1.5, "L2": 2.5, "L3": 2.0, "L4": 3.0, "lc_ratio": 0.6, "beta_coupler": 45}
        },
        # D-shape
        {
            "name": "D-Shape",
            "x": lambda t: np.where(t < np.pi, 2 * np.cos(t/2), -1.0),
            "y": lambda t: np.where(t < np.pi, 2 * np.sin(t/2), 2 * np.sin(t) - 2),
            "params": {"L1": 2.0, "L2": 1.5, "L3": 1.5, "L4": 3.0, "lc_ratio": 0.5, "beta_coupler": 0}
        },
        # Heart shape
        {
            "name": "Heart Shape",
            "x": lambda t: 16 * np.sin(t)**3,
            "y": lambda t: 13 * np.cos(t) - 5 * np.cos(2*t) - 2 * np.cos(3*t) - np.cos(4*t),
            "params": {"L1": 1.0, "L2": 2.0, "L3": 2.0, "L4": 2.5, "lc_ratio": 1.5, "beta_coupler": 60}
        },
        # Elliptical variations
        {
            "name": "Ellipse Wide",
            "x": lambda t: 3 * np.cos(t),
            "y": lambda t: np.sin(t),
            "params": {"L1": 1.0, "L2": 2.0, "L3": 2.0, "L4": 1.8, "lc_ratio": 0.4, "beta_coupler": 0}
        },
        {
            "name": "Ellipse Tall",
            "x": lambda t: np.cos(t),
            "y": lambda t: 3 * np.sin(t),
            "params": {"L1": 1.2, "L2": 2.2, "L3": 2.2, "L4": 1.5, "lc_ratio": 0.5, "beta_coupler": 0}
        },
        # Lemniscate (infinity symbol)
        {
            "name": "Lemniscate",
            "x": lambda t: np.cos(t) / (1 + np.sin(t)**2),
            "y": lambda t: np.sin(t) * np.cos(t) / (1 + np.sin(t)**2),
            "params": {"L1": 1.0, "L2": 2.5, "L3": 2.5, "L4": 3.0, "lc_ratio": 1.0, "beta_coupler": 0}
        },
        # Cardioid
        {
            "name": "Cardioid",
            "x": lambda t: 2 * (1 - np.cos(t)) * np.cos(t),
            "y": lambda t: 2 * (1 - np.cos(t)) * np.sin(t),
            "params": {"L1": 1.5, "L2": 3.0, "L3": 2.5, "L4": 4.0, "lc_ratio": 0.8, "beta_coupler": -45}
        },
        # Rose curves (different petals)
        {
            "name": "Rose 3-petals",
            "x": lambda t: np.cos(3 * t) * np.cos(t),
            "y": lambda t: np.cos(3 * t) * np.sin(t),
            "params": {"L1": 1.0, "L2": 2.0, "L3": 2.0, "L4": 2.5, "lc_ratio": 1.2, "beta_coupler": 30}
        },
        {
            "name": "Rose 4-petals",
            "x": lambda t: np.cos(2 * t) * np.cos(t),
            "y": lambda t: np.cos(2 * t) * np.sin(t),
            "params": {"L1": 1.2, "L2": 2.5, "L3": 2.5, "L4": 3.0, "lc_ratio": 0.9, "beta_coupler": 0}
        },
        # Straight line approximations
        {
            "name": "Near-Linear Horizontal",
            "x": lambda t: 2 * np.cos(t) + 0.1 * np.sin(2 * t),
            "y": lambda t: 0.1 * np.sin(t),
            "params": {"L1": 1.0, "L2": 4.0, "L3": 4.0, "L4": 1.0, "lc_ratio": 0.5, "beta_coupler": 0}
        },
        {
            "name": "Near-Linear Vertical",
            "x": lambda t: 0.1 * np.sin(t),
            "y": lambda t: 2 * np.cos(t) + 0.1 * np.sin(2 * t),
            "params": {"L1": 1.0, "L2": 4.0, "L3": 4.0, "L4": 1.0, "lc_ratio": 0.5, "beta_coupler": 90}
        },
        # Cusp patterns
        {
            "name": "Single Cusp",
            "x": lambda t: 2 * np.cos(t) + np.cos(2 * t),
            "y": lambda t: 2 * np.sin(t) - np.sin(2 * t),
            "params": {"L1": 1.0, "L2": 1.0, "L3": 1.0, "L4": 3.0, "lc_ratio": 0.5, "beta_coupler": 0}
        },
        {
            "name": "Double Cusp",
            "x": lambda t: np.cos(t) + 0.5 * np.cos(3 * t),
            "y": lambda t: np.sin(t) + 0.5 * np.sin(3 * t),
            "params": {"L1": 1.5, "L2": 2.0, "L3": 1.5, "L4": 3.5, "lc_ratio": 0.7, "beta_coupler": 30}
        }
    ]
    
    for pattern in coupler_patterns:
        try:
            x = pattern["x"](t)
            y = pattern["y"](t)
            path_coords = [[float(x[i]), float(y[i])] for i in range(len(t))]
            
            mechanisms.append({
                "type": "4-bar Coupler",
                "name": f"4-bar {pattern['name']}",
                "parameters": pattern["params"],
                "path_coordinates": normalize_path(path_coords)
            })
        except Exception as e:
            print(f"Failed to generate {pattern['name']}: {e}")
    
    return mechanisms


def generate_crankslider_paths() -> List[Dict[str, Any]]:
    """Generate crank-slider mechanism paths."""
    mechanisms = []
    t = np.linspace(0, 2 * np.pi, 100)
    
    # Various crank-slider configurations
    configs = [
        # Standard inline
        {"name": "Inline Zero Offset", "r": 1.0, "l": 3.0, "offset": 0.0},
        {"name": "Inline Short Rod", "r": 1.5, "l": 2.0, "offset": 0.0},
        {"name": "Inline Long Rod", "r": 1.0, "l": 5.0, "offset": 0.0},
        # Offset configurations
        {"name": "Offset Positive Small", "r": 1.0, "l": 3.0, "offset": 0.5},
        {"name": "Offset Positive Large", "r": 1.0, "l": 3.0, "offset": 1.0},
        {"name": "Offset Negative Small", "r": 1.0, "l": 3.0, "offset": -0.5},
        {"name": "Offset Negative Large", "r": 1.0, "l": 3.0, "offset": -1.0},
        # Quick-return mechanisms
        {"name": "Quick Return 1", "r": 2.0, "l": 3.0, "offset": 1.5},
        {"name": "Quick Return 2", "r": 1.5, "l": 2.5, "offset": 1.0},
        # Different stroke lengths
        {"name": "Short Stroke", "r": 0.5, "l": 4.0, "offset": 0.0},
        {"name": "Medium Stroke", "r": 1.5, "l": 3.0, "offset": 0.0},
        {"name": "Long Stroke", "r": 2.5, "l": 3.0, "offset": 0.0},
    ]
    
    for cfg in configs:
        r = cfg["r"]  # crank radius
        l = cfg["l"]  # connecting rod length
        e = cfg["offset"]  # offset
        
        # Calculate slider position
        x_slider = []
        y_slider = []
        
        for angle in t:
            # Crank position
            x_crank = r * np.cos(angle)
            y_crank = r * np.sin(angle)
            
            # Solve for slider position
            # For offset slider: (x - x_crank)² + (e - y_crank)² = l²
            # Solving for x: x = x_crank ± sqrt(l² - (e - y_crank)²)
            discriminant = l**2 - (e - y_crank)**2
            
            if discriminant >= 0:
                x = x_crank + np.sqrt(discriminant)  # Take the forward solution
                x_slider.append(float(x))
                y_slider.append(float(e))
        
        if len(x_slider) > 10:
            path_coords = [[x_slider[i], y_slider[i]] for i in range(len(x_slider))]
            mechanisms.append({
                "type": "3-bar Output",
                "name": f"Crank-Slider {cfg['name']}",
                "parameters": {
                    "crank_length": r,
                    "rod_length": l,
                    "offset": e
                },
                "path_coordinates": normalize_path(path_coords)
            })
    
    return mechanisms


def generate_cam_profiles() -> List[Dict[str, Any]]:
    """Generate various cam profile shapes."""
    mechanisms = []
    
    # Base parameters
    angles = np.linspace(0, 2 * np.pi, 200)
    
    cam_profiles = [
        # Simple dwell-rise-dwell-fall
        {
            "name": "Simple DRDF",
            "base_radius": 4.0,
            "lift": 2.0,
            "profile": lambda a, rb, h: np.where(
                a < np.pi/2, rb,
                np.where(a < np.pi, rb + h * np.sin((a - np.pi/2) * 2),
                np.where(a < 3*np.pi/2, rb + h,
                rb + h * (1 + np.cos((a - 3*np.pi/2) * 2)) / 2)))
        },
        # Harmonic motion
        {
            "name": "Harmonic Rise-Fall",
            "base_radius": 5.0,
            "lift": 3.0,
            "profile": lambda a, rb, h: rb + h * (1 - np.cos(a)) / 2
        },
        # Cycloidal motion
        {
            "name": "Cycloidal",
            "base_radius": 4.5,
            "lift": 2.5,
            "profile": lambda a, rb, h: rb + h * (a / (2 * np.pi) - np.sin(a) / (2 * np.pi))
        },
        # Modified sine
        {
            "name": "Modified Sine",
            "base_radius": 5.0,
            "lift": 2.0,
            "profile": lambda a, rb, h: rb + h * (np.sin(a)**2)
        },
        # Double dwell
        {
            "name": "Double Dwell",
            "base_radius": 4.0,
            "lift": 3.0,
            "profile": lambda a, rb, h: np.where(
                a < np.pi/3, rb + h * np.sin(3 * a / 2),
                np.where(a < 2*np.pi/3, rb + h,
                np.where(a < np.pi, rb + h * np.cos(3 * (a - 2*np.pi/3) / 2),
                np.where(a < 4*np.pi/3, rb,
                np.where(a < 5*np.pi/3, rb + h/2 * np.sin(3 * (a - 4*np.pi/3) / 2),
                rb + h/2)))))
        },
        # Asymmetric profile
        {
            "name": "Asymmetric Fast Rise",
            "base_radius": 4.5,
            "lift": 2.5,
            "profile": lambda a, rb, h: np.where(
                a < np.pi/4, rb + h * np.sin(2 * a)**2,
                np.where(a < 3*np.pi/2, rb + h,
                rb + h * np.cos((a - 3*np.pi/2) * 4/3)**2))
        },
        # Constant velocity
        {
            "name": "Constant Velocity",
            "base_radius": 5.0,
            "lift": 2.0,
            "profile": lambda a, rb, h: np.where(
                a < np.pi/2, rb + h * a / (np.pi/2),
                np.where(a < np.pi, rb + h,
                np.where(a < 3*np.pi/2, rb + h * (3*np.pi/2 - a) / (np.pi/2),
                rb)))
        },
        # Parabolic motion
        {
            "name": "Parabolic",
            "base_radius": 4.0,
            "lift": 2.5,
            "profile": lambda a, rb, h: rb + h * (4 * a * (2*np.pi - a) / (4 * np.pi**2))
        }
    ]
    
    for cam in cam_profiles:
        rb = cam["base_radius"]
        h = cam["lift"]
        r = cam["profile"](angles, rb, h)
        
        # Convert to Cartesian coordinates
        x = r * np.cos(angles)
        y = r * np.sin(angles)
        
        path_coords = [[float(x[i]), float(y[i])] for i in range(len(angles))]
        
        mechanisms.append({
            "type": "Cam Profile",
            "name": f"Cam {cam['name']}",
            "parameters": {
                "base_radius": rb,
                "lift": h,
                "motion_type": cam["name"].lower().replace(" ", "_")
            },
            "path_coordinates": normalize_path(path_coords)
        })
    
    return mechanisms


def generate_gear_contact_paths() -> List[Dict[str, Any]]:
    """Generate gear contact point paths."""
    mechanisms = []
    t = np.linspace(0, 2 * np.pi, 100)
    
    gear_configs = [
        # Standard gear pairs
        {"name": "1:2 Ratio", "r1": 1.0, "r2": 2.0},
        {"name": "1:3 Ratio", "r1": 1.0, "r2": 3.0},
        {"name": "1:4 Ratio", "r1": 1.0, "r2": 4.0},
        {"name": "2:3 Ratio", "r1": 2.0, "r2": 3.0},
        {"name": "3:5 Ratio", "r1": 3.0, "r2": 5.0},
        # Reverse ratios
        {"name": "2:1 Ratio", "r1": 2.0, "r2": 1.0},
        {"name": "3:1 Ratio", "r1": 3.0, "r2": 1.0},
        {"name": "4:1 Ratio", "r1": 4.0, "r2": 1.0},
    ]
    
    for cfg in gear_configs:
        r1 = cfg["r1"]  # radius of gear 1
        r2 = cfg["r2"]  # radius of gear 2
        center_distance = r1 + r2
        
        # Contact point moves along the line of centers
        # For external gears, contact point traces a straight line
        x_contact = []
        y_contact = []
        
        for angle in t:
            # Simplified model: contact point oscillates along line of centers
            # In reality, it follows the line of action at pressure angle
            contact_ratio = r1 / (r1 + r2)
            x = center_distance * contact_ratio + 0.1 * np.sin(angle * (r2/r1))
            y = 0.1 * np.cos(angle * (r2/r1))
            
            x_contact.append(float(x))
            y_contact.append(float(y))
        
        path_coords = [[x_contact[i], y_contact[i]] for i in range(len(x_contact))]
        
        mechanisms.append({
            "type": "Gear Contact",
            "name": f"Gear {cfg['name']}",
            "parameters": {
                "gear1_radius": r1,
                "gear2_radius": r2,
                "gear_ratio": r2/r1,
                "center_distance": center_distance
            },
            "path_coordinates": normalize_path(path_coords)
        })
    
    return mechanisms


def main():
    """Generate comprehensive synthetic dataset."""
    print("\n=== Comprehensive Mechanism Path Dataset Generator ===\n")
    
    all_mechanisms = []
    
    # Generate all mechanism types
    print("Generating 4-bar coupler curves...")
    fourbar_mechs = generate_fourbar_coupler_curves()
    all_mechanisms.extend(fourbar_mechs)
    print(f"  Generated {len(fourbar_mechs)} 4-bar mechanisms")
    
    print("\nGenerating crank-slider paths...")
    crankslider_mechs = generate_crankslider_paths()
    all_mechanisms.extend(crankslider_mechs)
    print(f"  Generated {len(crankslider_mechs)} crank-slider mechanisms")
    
    print("\nGenerating cam profiles...")
    cam_mechs = generate_cam_profiles()
    all_mechanisms.extend(cam_mechs)
    print(f"  Generated {len(cam_mechs)} cam mechanisms")
    
    print("\nGenerating gear contact paths...")
    gear_mechs = generate_gear_contact_paths()
    all_mechanisms.extend(gear_mechs)
    print(f"  Generated {len(gear_mechs)} gear mechanisms")
    
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
    
    # Merge datasets (avoid duplicates)
    existing_names = {m.get("name", "") for m in existing_data}
    new_mechanisms = [m for m in all_mechanisms if m.get("name", "") not in existing_names]
    
    combined_data = existing_data + new_mechanisms
    
    # Save
    print(f"\nSaving dataset...")
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
    
    print("\n✓ Dataset generation complete!")


if __name__ == "__main__":
    main()