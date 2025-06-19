#!/usr/bin/env python3
"""
Visualize the generated mechanism dataset.
"""

import json
import matplotlib.pyplot as plt
import numpy as np
import os
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QListWidget, QGraphicsView, QGraphicsScene
from PyQt6.QtGui import QPainter, QPen, QColor, QPainterPath
from PyQt6.QtCore import Qt, QPointF
from automataii.utils.paths import resolve_path

class MechanismVisualizer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mechanism Path Visualizer")

        # Load the dataset
        dataset_path = resolve_path("automataii/kinematics/generated_mechanism_paths.json")
        try:
            with open(dataset_path, 'r') as f:
                self.dataset = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Error loading dataset: {e}")
            return

        print(f"Loaded {len(self.dataset)} mechanisms")

        # Count by type
        self.type_counts = {}
        for mech in self.dataset:
            mech_type = mech['type']
            self.type_counts[mech_type] = self.type_counts.get(mech_type, 0) + 1

        print("\nMechanism counts by type:")
        for mech_type, count in self.type_counts.items():
            print(f"  {mech_type}: {count}")

        # Plot a sample from each type
        self.fig, self.axes = plt.subplots(2, 2, figsize=(12, 12))
        self.axes = self.axes.flatten()

        self.type_samples = {}
        for mech in self.dataset:
            if mech['type'] not in self.type_samples:
                self.type_samples[mech['type']] = mech

        self.update_sample_plots()

    def update_sample_plots(self):
        for i, (mech_type, mech) in enumerate(self.type_samples.items()):
            if i >= 4:
                break

            ax = self.axes[i]
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
        self.stats = {
            "total_mechanisms": len(self.dataset),
            "type_counts": self.type_counts,
            "sample_names": [mech['name'] for mech in self.dataset[:10]]
        }

        with open('dataset_stats.json', 'w') as f:
            json.dump(self.stats, f, indent=2)

        print("Dataset statistics saved to dataset_stats.json")

if __name__ == "__main__":
    app = QApplication([])
    window = MechanismVisualizer()
    window.show()
    app.exec()