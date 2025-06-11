# Mechanism Design Tab Implementation Plan (Python)

## Overview
Python-based implementation for a mechanism design tab that recommends mechanical assemblies (3-bar, 4-bar, cam) to animate character parts using precomputed motion databases.

## Core Architecture

### 1. Data Structures and Models

```python
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple, Set
import numpy as np
from enum import Enum

class MechanismType(Enum):
    THREE_BAR = "3bar"
    FOUR_BAR = "4bar"
    CAM = "cam"
    PARAMETRIC = "parametric"

@dataclass
class MechanismParameter:
    name: str
    value: float
    min_val: float
    max_val: float
    step: float

@dataclass
class MotionCurve:
    points: np.ndarray  # Nx2 array of 2D points
    period: float
    attachment_point: np.ndarray  # 2D point
    parameter_vector: np.ndarray  # Parameters that generated this curve

@dataclass
class MechanismTemplate:
    type: MechanismType
    parameters: List[MechanismParameter]
    enabled: bool = True

@dataclass
class PrecomputedMotionEntry:
    mechanism_type: MechanismType
    parameters: np.ndarray
    motion_curve: MotionCurve
    features: np.ndarray  # Feature vector for similarity matching

@dataclass
class MechanismCandidate:
    mechanism_type: MechanismType
    parameters: Dict[str, float]
    motion_curve: MotionCurve
    similarity_score: float
    transform_matrix: np.ndarray  # Alignment transformation
```

### 2. Precomputed Motion Database

```python
import h5py
import pickle
from scipy.spatial import cKDTree

class MotionDatabase:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.entries: Dict[MechanismType, List[PrecomputedMotionEntry]] = {}
        self.feature_trees: Dict[MechanismType, cKDTree] = {}

    def build_database(self, mechanism_types: List[MechanismTemplate]):
        """Build precomputed motion database using Poisson-disk sampling"""

        for mechanism in mechanism_types:
            print(f"Building database for {mechanism.type.value}")
            entries = self._sample_mechanism_space(mechanism)
            self.entries[mechanism.type] = entries

            # Build KD-tree for fast similarity search
            features = np.array([e.features for e in entries])
            self.feature_trees[mechanism.type] = cKDTree(features)

        self._save_database()

    def _sample_mechanism_space(self, mechanism: MechanismTemplate) -> List[PrecomputedMotionEntry]:
        """Poisson-disk sampling in parameter space"""

        entries = []
        min_curve_distance = 0.1  # Minimum distance between curves in feature space

        # Initial random sample
        param_ranges = [(p.min_val, p.max_val) for p in mechanism.parameters]
        initial_params = self._random_parameters(param_ranges)

        simulator = MechanismSimulator()
        curve = simulator.simulate_mechanism(mechanism.type, initial_params)
        features = self._extract_curve_features(curve)

        entries.append(PrecomputedMotionEntry(
            mechanism_type=mechanism.type,
            parameters=initial_params,
            motion_curve=curve,
            features=features
        ))

        # Poisson-disk sampling
        max_attempts = 10000
        attempts = 0

        while attempts < max_attempts and len(entries) < 3000:  # Max 3000 samples per type
            # Generate candidate around existing samples
            base_idx = np.random.randint(0, len(entries))
            base_params = entries[base_idx].parameters

            # Perturb parameters
            candidate_params = self._perturb_parameters(base_params, param_ranges)

            # Simulate and extract features
            try:
                curve = simulator.simulate_mechanism(mechanism.type, candidate_params)
                features = self._extract_curve_features(curve)

                # Check minimum distance to existing samples
                distances = [np.linalg.norm(features - e.features) for e in entries]

                if min(distances) > min_curve_distance:
                    entries.append(PrecomputedMotionEntry(
                        mechanism_type=mechanism.type,
                        parameters=candidate_params,
                        motion_curve=curve,
                        features=features
                    ))
                    print(f"Added sample {len(entries)} for {mechanism.type.value}")

            except Exception as e:
                # Skip invalid configurations
                pass

            attempts += 1

        return entries

    def _extract_curve_features(self, curve: MotionCurve) -> np.ndarray:
        """Extract features for curve similarity matching"""

        points = curve.points

        # Normalize curve (translation and scale invariant)
        centroid = np.mean(points, axis=0)
        points_centered = points - centroid
        scale = np.max(np.linalg.norm(points_centered, axis=1))
        points_normalized = points_centered / scale if scale > 0 else points_centered

        # Feature extraction
        features = []

        # 1. Curve length
        lengths = np.linalg.norm(np.diff(points_normalized, axis=0), axis=1)
        features.append(np.sum(lengths))

        # 2. Area (using shoelace formula)
        area = 0.5 * np.abs(np.sum(
            points_normalized[:-1, 0] * points_normalized[1:, 1] -
            points_normalized[1:, 0] * points_normalized[:-1, 1]
        ))
        features.append(area)

        # 3. Aspect ratio
        pca = np.linalg.svd(points_normalized.T @ points_normalized)[1]
        aspect_ratio = np.sqrt(pca[1] / pca[0]) if pca[0] > 0 else 0
        features.append(aspect_ratio)

        # 4. Curvature statistics
        if len(points) > 2:
            curvatures = self._compute_discrete_curvature(points_normalized)
            features.extend([
                np.mean(curvatures),
                np.std(curvatures),
                np.max(np.abs(curvatures))
            ])
        else:
            features.extend([0, 0, 0])

        # 5. Fourier descriptors (first 10 coefficients)
        fft = np.fft.fft(points_normalized[:, 0] + 1j * points_normalized[:, 1])
        features.extend(np.abs(fft[1:11]))

        return np.array(features)

    def query_similar_curves(self, target_curve: np.ndarray,
                           enabled_types: Set[MechanismType],
                           k: int = 3) -> List[MechanismCandidate]:
        """Find k most similar curves from enabled mechanism types"""

        # Extract features from target curve
        target_features = self._extract_curve_features(
            MotionCurve(points=target_curve, period=1.0,
                       attachment_point=np.array([0, 0]),
                       parameter_vector=np.array([]))
        )

        candidates = []

        for mech_type in enabled_types:
            if mech_type not in self.feature_trees:
                continue

            # Find k nearest neighbors
            distances, indices = self.feature_trees[mech_type].query(
                target_features, k=min(k*2, len(self.entries[mech_type]))
            )

            for dist, idx in zip(distances, indices):
                entry = self.entries[mech_type][idx]

                # Compute alignment transformation
                transform = self._compute_alignment_transform(
                    target_curve, entry.motion_curve.points
                )

                candidates.append(MechanismCandidate(
                    mechanism_type=mech_type,
                    parameters={f"param_{i}": v for i, v in enumerate(entry.parameters)},
                    motion_curve=entry.motion_curve,
                    similarity_score=1.0 / (1.0 + dist),  # Convert distance to similarity
                    transform_matrix=transform
                ))

        # Sort by similarity and return top k
        candidates.sort(key=lambda x: x.similarity_score, reverse=True)
        return candidates[:k]

    def _compute_alignment_transform(self, target: np.ndarray, source: np.ndarray) -> np.ndarray:
        """Compute optimal rigid transformation to align source to target"""

        # TODO: Implement Procrustes analysis for optimal alignment
        # For now, return identity
        return np.eye(3)
```

### 3. Mechanism Simulation

```python
class MechanismSimulator:
    def __init__(self):
        self.time_steps = 100  # Number of time steps per period

    def simulate_mechanism(self, mech_type: MechanismType,
                         parameters: np.ndarray) -> MotionCurve:
        """Simulate mechanism motion for one period"""

        t = np.linspace(0, 2*np.pi, self.time_steps)

        if mech_type == MechanismType.THREE_BAR:
            points = self._simulate_3bar(parameters, t)
        elif mech_type == MechanismType.FOUR_BAR:
            points = self._simulate_4bar(parameters, t)
        elif mech_type == MechanismType.CAM:
            points = self._simulate_cam(parameters, t)
        else:
            raise ValueError(f"Unknown mechanism type: {mech_type}")

        return MotionCurve(
            points=points,
            period=2*np.pi,
            attachment_point=points[-1],  # End effector position
            parameter_vector=parameters
        )

    def _simulate_3bar(self, params: np.ndarray, t: np.ndarray) -> np.ndarray:
        """Three-bar linkage simulation"""

        # Parameters: [l1, l2, l3, theta0, omega]
        l1, l2, l3, theta0, omega = params[:5]

        # TODO: Implement proper constraint-based simulation
        # Current: Simple geometric approach

        points = []
        for ti in t:
            theta1 = theta0 + omega * ti

            # Joint positions
            j1 = np.array([l1 * np.cos(theta1), l1 * np.sin(theta1)])

            # Solve for end effector (simplified)
            # In reality, need to solve constraint equations
            theta2 = theta1 + np.pi/4  # Placeholder
            end_effector = j1 + np.array([l2 * np.cos(theta2), l2 * np.sin(theta2)])

            points.append(end_effector)

        return np.array(points)

    def _simulate_4bar(self, params: np.ndarray, t: np.ndarray) -> np.ndarray:
        """Four-bar linkage simulation"""

        # Parameters: [l1, l2, l3, l4, theta0, omega]
        l1, l2, l3, l4, theta0, omega = params[:6]

        # TODO: Implement Freudenstein equation solver
        # Current: Simplified version

        points = []
        for ti in t:
            theta1 = theta0 + omega * ti

            # Compute coupler curve point
            # This requires solving the loop closure equations
            # Placeholder implementation
            x = (l1 + l2) * np.cos(theta1) + l3 * np.cos(theta1 + np.pi/3)
            y = (l1 + l2) * np.sin(theta1) + l3 * np.sin(theta1 + np.pi/3)

            points.append([x, y])

        return np.array(points)
```

### 4. Mechanism Design Tab UI

```python
import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

class MechanismDesignTab:
    def __init__(self, parent_frame, editor_path: np.ndarray):
        self.parent = parent_frame
        self.editor_path = editor_path  # Path from editor tab
        self.selected_mechanism = None
        self.candidates = []

        # Initialize database
        self.motion_db = MotionDatabase("motion_database.h5")

        # Create UI
        self._create_ui()

    def _create_ui(self):
        # Main layout
        self.main_frame = ttk.Frame(self.parent)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Left panel - Mechanism toggles and controls
        self.control_panel = ttk.Frame(self.main_frame, width=200)
        self.control_panel.pack(side=tk.LEFT, fill=tk.Y)

        # Mechanism type toggles
        self.mechanism_toggles = {}
        ttk.Label(self.control_panel, text="Mechanism Types").pack()

        for mech_type in MechanismType:
            var = tk.BooleanVar(value=True)
            chk = ttk.Checkbutton(
                self.control_panel,
                text=mech_type.value,
                variable=var
            )
            chk.pack()
            self.mechanism_toggles[mech_type] = var

        # Recommend button
        ttk.Button(
            self.control_panel,
            text="Get Recommendations",
            command=self._get_recommendations
        ).pack(pady=10)

        # Center panel - Visualization
        self.viz_frame = ttk.Frame(self.main_frame)
        self.viz_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Matplotlib figure for visualization
        self.fig, (self.ax_path, self.ax_mechanism) = plt.subplots(1, 2, figsize=(10, 5))
        self.canvas = FigureCanvasTkAgg(self.fig, self.viz_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Right panel - Candidates and parameters
        self.right_panel = ttk.Frame(self.main_frame, width=300)
        self.right_panel.pack(side=tk.RIGHT, fill=tk.Y)

        # Candidate list
        ttk.Label(self.right_panel, text="Candidates").pack()
        self.candidate_frame = ttk.Frame(self.right_panel)
        self.candidate_frame.pack(fill=tk.BOTH, expand=True)

        # Parameter adjustment
        ttk.Label(self.right_panel, text="Parameters").pack()
        self.param_frame = ttk.Frame(self.right_panel)
        self.param_frame.pack(fill=tk.BOTH)

    def _get_recommendations(self):
        """Get mechanism recommendations based on editor path"""

        # Get enabled types
        enabled_types = {
            mech_type for mech_type, var in self.mechanism_toggles.items()
            if var.get()
        }

        # Query database
        self.candidates = self.motion_db.query_similar_curves(
            self.editor_path,
            enabled_types,
            k=3
        )

        # Display candidates
        self._display_candidates()

    def _display_candidates(self):
        """Display candidate mechanisms"""

        # Clear previous candidates
        for widget in self.candidate_frame.winfo_children():
            widget.destroy()

        # Create candidate buttons
        for i, candidate in enumerate(self.candidates):
            frame = ttk.Frame(self.candidate_frame)
            frame.pack(fill=tk.X, pady=5)

            btn = ttk.Button(
                frame,
                text=f"{candidate.mechanism_type.value} (Score: {candidate.similarity_score:.3f})",
                command=lambda c=candidate: self._select_candidate(c)
            )
            btn.pack(fill=tk.X)

        # Update visualization
        self._update_visualization()

    def _select_candidate(self, candidate: MechanismCandidate):
        """Select a candidate mechanism"""

        self.selected_mechanism = candidate
        self._create_parameter_controls(candidate)
        self._update_mechanism_view(candidate)

    def _create_parameter_controls(self, candidate: MechanismCandidate):
        """Create parameter adjustment sliders"""

        # Clear previous controls
        for widget in self.param_frame.winfo_children():
            widget.destroy()

        # TODO: Implement automatic parameter optimization
        # Current: Manual sliders

        self.param_vars = {}
        for param_name, value in candidate.parameters.items():
            frame = ttk.Frame(self.param_frame)
            frame.pack(fill=tk.X, pady=2)

            ttk.Label(frame, text=param_name).pack(side=tk.LEFT)

            var = tk.DoubleVar(value=value)
            self.param_vars[param_name] = var

            scale = ttk.Scale(
                frame,
                from_=value * 0.5,
                to=value * 1.5,
                variable=var,
                command=lambda v, pn=param_name: self._on_parameter_change(pn, float(v))
            )
            scale.pack(side=tk.RIGHT, fill=tk.X, expand=True)

    def _on_parameter_change(self, param_name: str, value: float):
        """Handle parameter change"""

        if not self.selected_mechanism:
            return

        # Update parameters
        self.selected_mechanism.parameters[param_name] = value

        # Re-simulate mechanism
        params = np.array(list(self.selected_mechanism.parameters.values()))
        simulator = MechanismSimulator()
        new_curve = simulator.simulate_mechanism(
            self.selected_mechanism.mechanism_type,
            params
        )

        self.selected_mechanism.motion_curve = new_curve
        self._update_mechanism_view(self.selected_mechanism)
```

### 5. Part Attachment System

```python
@dataclass
class MechanismAttachment:
    mechanism: MechanismCandidate
    part_id: str
    attachment_point_local: np.ndarray  # In mechanism space
    part_offset: np.ndarray  # In part space

class AttachmentManager:
    def __init__(self):
        self.attachments: List[MechanismAttachment] = []
        self.animation_time = 0.0

    def attach_part_to_mechanism(self, part_id: str,
                                mechanism: MechanismCandidate,
                                attachment_point: Optional[np.ndarray] = None):
        """Attach a part to a mechanism"""

        if attachment_point is None:
            # Use default attachment point (end effector)
            attachment_point = mechanism.motion_curve.attachment_point

        attachment = MechanismAttachment(
            mechanism=mechanism,
            part_id=part_id,
            attachment_point_local=attachment_point,
            part_offset=np.array([0, 0])  # Can be adjusted
        )

        self.attachments.append(attachment)

    def update_animation(self, dt: float):
        """Update all attached parts"""

        self.animation_time += dt

        for attachment in self.attachments:
            # Get current position on motion curve
            curve_points = attachment.mechanism.motion_curve.points
            period = attachment.mechanism.motion_curve.period

            # Normalized time in period
            t_norm = (self.animation_time % period) / period
            idx = int(t_norm * len(curve_points))

            # Get position (with interpolation)
            if idx < len(curve_points) - 1:
                alpha = (t_norm * len(curve_points)) - idx
                pos = (1 - alpha) * curve_points[idx] + alpha * curve_points[idx + 1]
            else:
                pos = curve_points[-1]

            # Apply transformation
            transformed_pos = self._apply_transform(
                pos,
                attachment.mechanism.transform_matrix
            )

            # Update part position
            self._update_part_position(attachment.part_id, transformed_pos + attachment.part_offset)
```

### 6. Integration Manager

```python
class MechanismTabIntegration:
    def __init__(self, editor_tab, mechanism_tab):
        self.editor_tab = editor_tab
        self.mechanism_tab = mechanism_tab

    def transfer_path_to_mechanism_tab(self, path: np.ndarray, part_id: str):
        """Transfer path from editor to mechanism design tab"""

        # Create new mechanism tab with the path
        self.mechanism_tab.set_target_path(path)
        self.mechanism_tab.set_target_part(part_id)

        # Get recommendations automatically
        self.mechanism_tab._get_recommendations()

    def apply_mechanism_to_part(self, mechanism: MechanismCandidate, part_id: str):
        """Apply selected mechanism to part"""

        # Remove IK animation from editor
        self.editor_tab.clear_part_animation(part_id)

        # Create mechanism attachment
        attachment_manager = AttachmentManager()
        attachment_manager.attach_part_to_mechanism(part_id, mechanism)

        # Update part animation type
        self.editor_tab.set_part_animation_type(part_id, 'mechanism')
        self.editor_tab.set_mechanism_reference(part_id, mechanism)
```

## Implementation Phases

### Phase 1: Database Construction (Week 1-2)
```python
# Build precomputed motion database
if __name__ == "__main__":
    # Define mechanism templates
    mechanisms = [
        MechanismTemplate(
            type=MechanismType.THREE_BAR,
            parameters=[
                MechanismParameter("link1_length", 1.0, 0.5, 2.0, 0.1),
                MechanismParameter("link2_length", 1.0, 0.5, 2.0, 0.1),
                MechanismParameter("link3_length", 1.0, 0.5, 2.0, 0.1),
                MechanismParameter("initial_phase", 0.0, 0.0, 2*np.pi, 0.1),
                MechanismParameter("angular_velocity", 1.0, 0.5, 2.0, 0.1)
            ]
        ),
        # Add other mechanism types...
    ]

    # Build database
    db = MotionDatabase("motion_database.h5")
    db.build_database(mechanisms)
```

### Phase 2: Basic UI and Visualization (Week 3)
- Implement mechanism design tab UI
- Candidate display system
- Path and mechanism visualization

### Phase 3: Similarity Search (Week 4)
- Feature extraction implementation
- KD-tree based search
- Alignment transformation

### Phase 4: Manual Parameter Adjustment (Week 5)
- Parameter slider UI
- Real-time mechanism re-simulation
- Visual feedback

### Phase 5: Part Attachment (Week 6)
- Attachment point selection
- Animation update system
- Coordinate transformations

## TODOs

```python
# TODO: Real-time parameter exploration
# - Replace precomputed database with real-time sampling
# - GPU acceleration for parallel simulation
# - Adaptive sampling based on user interaction

# TODO: Constraint-based physics simulation
# - Implement Newton-Raphson solver for mechanisms
# - Handle kinematic loops properly
# - Support for more complex assemblies

# TODO: Automatic parameter optimization
# - Gradient computation via automatic differentiation
# - BFGS or L-BFGS optimization
# - Multi-objective optimization for complex paths
# - Integration with PyTorch/JAX for autodiff
```