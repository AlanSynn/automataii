#!/usr/bin/env python3
"""
Visualize the generated mechanism dataset.
"""

import json
import matplotlib.pyplot as plt
import numpy as np
import os

# Load the dataset
dataset_path = os.path.join(os.path.dirname(__file__), 'kinematics', 'generated_mechanism_paths.json')

with open(dataset_path, 'r') as f:
    mechanisms = json.load(f)

print(f"Loaded {len(mechanisms)} mechanisms")

# Count by type
type_counts = {}
for mech in mechanisms:
    mech_type = mech['type']
    type_counts[mech_type] = type_counts.get(mech_type, 0) + 1

print("\nMechanism counts by type:")
for mech_type, count in type_counts.items():
    print(f"  {mech_type}: {count}")

# Plot a sample from each type
fig, axes = plt.subplots(2, 2, figsize=(12, 12))
axes = axes.flatten()

type_samples = {}
for mech in mechanisms:
    if mech['type'] not in type_samples:
        type_samples[mech['type']] = mech

for i, (mech_type, mech) in enumerate(type_samples.items()):
    if i >= 4:
        break
    
    ax = axes[i]
    coords = mech['path_coordinates']
    x_coords = [c[0] for c in coords]
    y_coords = [c[1] for c in coords]
    
    ax.plot(x_coords, y_coords, 'b-', linewidth=2)
    ax.plot(x_coords[0], y_coords[0], 'go', markersize=8, label='Start')
    ax.plot(x_coords[-1], y_coords[-1], 'ro', markersize=8, label='End')
    
    ax.set_title(f"{mech['name']}")
    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.grid(True, alpha=0.3)
    ax.axis('equal')
    ax.legend()

plt.tight_layout()
plt.savefig('mechanism_samples.png', dpi=150)
print(f"\nSample plots saved to mechanism_samples.png")

# Also save dataset statistics
stats = {
    "total_mechanisms": len(mechanisms),
    "type_counts": type_counts,
    "sample_names": [mech['name'] for mech in mechanisms[:10]]
}

with open('dataset_stats.json', 'w') as f:
    json.dump(stats, f, indent=2)

print("Dataset statistics saved to dataset_stats.json")