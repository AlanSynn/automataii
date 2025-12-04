#!/usr/bin/env python3
"""
Regenerate cam mechanism data in generated_mechanism_paths.json with proper motion paths.

The cam-follower mechanism consists of:
- Cam: A rotating profile that converts rotational motion to linear motion
- Follower: A component that rides on the cam and moves up/down
- Rod: Connects the follower to whatever it's actuating

For a pear-cam profile:
- Rise segment: Follower moves from min to max height (sinusoidal motion)
- High dwell: Follower stays at max height
- Fall segment: Follower moves from max to min height
- Low dwell: Follower stays at min height
"""

import json
import math
from pathlib import Path

import numpy as np


def build_pear_cam_profile(
    base_radius: float,
    eccentricity: float,
    rise_deg: float = 90.0,
    high_dwell_deg: float = 60.0,
    dwell_low_deg: float = 180.0,
    align_max_to_deg: float = 90.0,
    num_samples: int = 90,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Build pear-cam profile and follower path.

    Returns:
        Tuple of (cam_profile_points, follower_path_points)
    """
    rise = np.deg2rad(rise_deg)
    dwell_high = np.deg2rad(high_dwell_deg)
    dwell_low = np.deg2rad(dwell_low_deg)
    total = 2 * np.pi
    fall = max(0.0, total - (rise + dwell_high + dwell_low))

    # Phase reference: ensure max radius at align_max_to_deg
    theta0 = np.deg2rad(align_max_to_deg)
    seg1_end = theta0 + rise
    seg2_end = seg1_end + dwell_high
    seg3_end = seg2_end + fall

    thetas = np.linspace(0, 2 * np.pi, num_samples, endpoint=False)
    s = np.zeros_like(thetas)  # Normalized lift 0-1

    for i, t in enumerate(thetas):
        rel = (t - theta0) % (2 * np.pi) + theta0
        if rel < seg1_end:  # rise 0->1
            u = (rel - theta0) / rise if rise > 0 else 1.0
            s[i] = 0.5 * (1 - np.cos(np.pi * u))
        elif rel < seg2_end:  # high dwell at 1
            s[i] = 1.0
        elif rel < seg3_end:  # fall 1->0
            u = (rel - seg2_end) / fall if fall > 0 else 1.0
            s[i] = 0.5 * (1 + np.cos(np.pi * u))
        else:  # low dwell at 0
            s[i] = 0.0

    # Cam profile in local coordinates
    r = base_radius + eccentricity * s
    cam_profile = np.stack([r * np.cos(thetas), r * np.sin(thetas)], axis=1)

    # Follower path: vertical motion based on cam profile
    # Follower rides on top of cam at y = max(cam profile at that rotation)
    follower_y = base_radius + eccentricity * s  # Follower Y position
    follower_path = np.stack([np.zeros_like(follower_y), follower_y], axis=1)

    return cam_profile, follower_path


def generate_cam_mechanisms() -> list[dict]:
    """Generate cam mechanism entries with proper motion data."""

    cam_variants = [
        {
            "name": "Symmetric Cam (Medium Lift)",
            "base_radius": 40.0,
            "eccentricity": 20.0,
            "rise_deg": 90.0,
            "high_dwell_deg": 60.0,
            "low_dwell_deg": 120.0,
            "follower_rod_length": 60.0,
        },
        {
            "name": "Quick Return Cam",
            "base_radius": 35.0,
            "eccentricity": 25.0,
            "rise_deg": 120.0,
            "high_dwell_deg": 30.0,
            "low_dwell_deg": 180.0,
            "follower_rod_length": 50.0,
        },
        {
            "name": "High Lift Cam",
            "base_radius": 30.0,
            "eccentricity": 35.0,
            "rise_deg": 90.0,
            "high_dwell_deg": 90.0,
            "low_dwell_deg": 90.0,
            "follower_rod_length": 70.0,
        },
        {
            "name": "Dwell Cam (Long Pause)",
            "base_radius": 45.0,
            "eccentricity": 15.0,
            "rise_deg": 60.0,
            "high_dwell_deg": 120.0,
            "low_dwell_deg": 120.0,
            "follower_rod_length": 55.0,
        },
    ]

    mechanisms = []

    for variant in cam_variants:
        cam_profile, follower_path = build_pear_cam_profile(
            base_radius=variant["base_radius"],
            eccentricity=variant["eccentricity"],
            rise_deg=variant["rise_deg"],
            high_dwell_deg=variant["high_dwell_deg"],
            dwell_low_deg=variant["low_dwell_deg"],
            num_samples=90,
        )

        # Normalize path_coordinates to [-1, 1] range for matching
        path_min = np.min(follower_path, axis=0)
        path_max = np.max(follower_path, axis=0)
        path_range = path_max - path_min
        path_range[path_range < 1e-6] = 1.0  # Prevent division by zero
        path_normalized = 2.0 * (follower_path - path_min) / path_range - 1.0

        # For X coordinate (which is 0), keep it at 0
        path_normalized[:, 0] = 0.0

        mechanism = {
            "type": "Cam-Follower",
            "name": variant["name"],
            "parameters": {
                "base_radius": variant["base_radius"],
                "eccentricity": variant["eccentricity"],
                "rise_deg": variant["rise_deg"],
                "high_dwell_deg": variant["high_dwell_deg"],
                "low_dwell_deg": variant["low_dwell_deg"],
                "follower_rod_length": variant["follower_rod_length"],
            },
            "path_coordinates": path_normalized.tolist(),
            "key_points": {
                "cam_center": [0.0, 0.0],
                "follower_min": [0.0, float(variant["base_radius"])],
                "follower_max": [0.0, float(variant["base_radius"] + variant["eccentricity"])],
            },
            "full_simulation_data": {
                "follower_path": follower_path.tolist(),
                "cam_profile": cam_profile.tolist(),
                "cam_data": {
                    "cam_centers": [[0.0, 0.0]] * 90,
                    "follower_y_positions": (variant["base_radius"] + variant["eccentricity"] *
                        np.array([0.5 * (1 - np.cos(np.pi * i / 45)) if i < 45 else
                                  1.0 if i < 60 else
                                  0.5 * (1 + np.cos(np.pi * (i - 60) / 15)) if i < 75 else 0.0
                                  for i in range(90)])).tolist(),
                },
            },
        }
        mechanisms.append(mechanism)

    return mechanisms


def update_json_file():
    """Update the generated_mechanism_paths.json with proper cam data."""
    json_path = Path(__file__).parent.parent / "resources" / "data" / "generated_mechanism_paths.json"

    if not json_path.exists():
        print(f"Error: {json_path} not found")
        return

    print(f"Loading {json_path}...")
    with open(json_path, "r") as f:
        data = json.load(f)

    # Remove old cam entries
    original_count = len(data)
    data = [m for m in data if m.get("type") != "Cam-Follower"]
    removed_count = original_count - len(data)
    print(f"Removed {removed_count} old Cam-Follower entries")

    # Add new cam entries
    new_cams = generate_cam_mechanisms()
    data.extend(new_cams)
    print(f"Added {len(new_cams)} new Cam-Follower entries")

    # Save updated file
    print(f"Saving to {json_path}...")
    with open(json_path, "w") as f:
        json.dump(data, f, indent=2)

    print("Done!")

    # Print summary of new cams
    print("\nNew cam mechanisms:")
    for cam in new_cams:
        params = cam["parameters"]
        print(f"  - {cam['name']}: base_radius={params['base_radius']}, "
              f"eccentricity={params['eccentricity']}, "
              f"rod_length={params['follower_rod_length']}")


if __name__ == "__main__":
    update_json_file()
