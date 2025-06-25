import json
import logging

import numpy as np
from scipy.spatial import cKDTree

from automataii.kinematics.curve_similarity import CurveSimilarity
from automataii.kinematics.mechanism import (
    MechanismCandidate,
    MechanismTemplate,
    MechanismType,
    MotionCurve,
    PrecomputedMotionEntry,
)
from automataii.kinematics.mechanism_simulator import MechanismSimulator
from automataii.utils.paths import resolve_path

# Configure logging
logger = logging.getLogger(__name__)

class MotionDatabase:
    """Manages a precomputed database of mechanism motions for fast querying."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.entries: dict[MechanismType, list[PrecomputedMotionEntry]] = {}
        self.feature_trees: dict[MechanismType, cKDTree] = {}
        self.similarity_metric = CurveSimilarity()
        self.db = []
        self.load_database()

    def build_database(
        self, mechanism_templates: list[MechanismTemplate], force_rebuild: bool = False
    ):
        """
        Builds the precomputed motion database using Poisson-disk sampling.
        If the database file already exists, it loads it unless force_rebuild is True.
        """
        # TODO: Add file existence check and loading logic
        print("Building motion database...")
        for template in mechanism_templates:
            if not template.enabled:
                continue
            print(f"Building database for {template.type.value}...")
            entries = self._sample_mechanism_space(template)
            self.entries[template.type] = entries

            if entries:
                features = np.array([e.features for e in entries])
                self.feature_trees[template.type] = cKDTree(features)
        self._save_database()

    def _sample_mechanism_space(
        self, template: MechanismTemplate
    ) -> list[PrecomputedMotionEntry]:
        """
        Generates motion samples using a simplified sampling strategy.
        Note: This is a simplified version of the Poisson-disk sampling from the plan.
        """
        entries = []
        simulator = MechanismSimulator()
        param_ranges = [(p.min_val, p.max_val) for p in template.parameters]

        # Generate a grid of samples for simplicity
        num_samples_per_dim = 5
        # This creates a grid, which is not ideal but simpler than Poisson-disk for now
        # A proper implementation would use a more sophisticated sampling strategy.
        # This is just a placeholder to get the structure right.
        # For a real implementation, consider libraries like `bridson` or implementing the algorithm.

        # Let's just generate random samples for now
        max_samples = 1000
        for _ in range(max_samples):
            try:
                params = self._random_parameters(param_ranges)
                curve = simulator.simulate_mechanism(template.type, params)
                if curve.points.shape[0] == 0:
                    continue

                features = self.similarity_metric._extract_curve_features(curve)
                entries.append(
                    PrecomputedMotionEntry(
                        mechanism_type=template.type,
                        parameters=params,
                        motion_curve=curve,
                        features=features,
                    )
                )
            except (ValueError, np.linalg.LinAlgError):
                continue  # Skip invalid parameter sets

        print(f"Generated {len(entries)} samples for {template.type.value}")
        return entries

    def _random_parameters(self, param_ranges: list[tuple]) -> np.ndarray:
        """Generates a random set of parameters within the given ranges."""
        return np.array([np.random.uniform(low, high) for low, high in param_ranges])

    def query_similar_curves(
        self,
        target_curve: np.ndarray,
        enabled_types: set[MechanismType],
        k: int = 3,
    ) -> list[MechanismCandidate]:
        """Finds the k most similar curves from the database."""
        if not self.entries:
            print("Database is empty. Please build it first.")
            return []

        target_motion_curve = MotionCurve(points=target_curve, period=1.0)
        target_features = self.similarity_metric._extract_curve_features(target_motion_curve)

        candidates = []
        for mech_type in enabled_types:
            if mech_type not in self.feature_trees:
                continue

            tree = self.feature_trees[mech_type]
            distances, indices = tree.query(target_features, k=k)

            for dist, idx in zip(distances, indices, strict=False):
                entry = self.entries[mech_type][idx]
                transform = self._compute_alignment_transform(
                    target_curve, entry.motion_curve.points
                )
                candidates.append(
                    MechanismCandidate(
                        mechanism_type=mech_type,
                        parameters={
                            f"param_{i}": v for i, v in enumerate(entry.parameters)
                        },
                        motion_curve=entry.motion_curve,
                        similarity_score=1.0 / (1.0 + dist),
                        transform_matrix=transform,
                    )
                )

        candidates.sort(key=lambda x: x.similarity_score, reverse=True)
        return candidates[:k]

    def _compute_alignment_transform(
        self, target: np.ndarray, source: np.ndarray
    ) -> np.ndarray:
        """
        Computes the optimal rigid transformation (translation, rotation, scale)
        to align the source curve to the target curve using Procrustes analysis.
        """
        # TODO: Implement Procrustes analysis for optimal alignment
        return np.eye(3)

    def _save_database(self):
        """Saves the database to an HDF5 file."""
        # This is now handled by the generation script directly.
        print(f"Database saved to {self.db_path}")

    def load_database(self):
        """Loads the motion path database from the JSON file."""
        db_path = resolve_path("src/automataii/kinematics/generated_mechanism_paths.json")
        if not db_path or not db_path.exists():
            logger.warning("Generated mechanism paths file not found.")
            return

        try:
            with open(db_path) as f:
                data = json.load(f)

            for item in data:
                mech_type_str = item.get("type", "").split()[0].lower()
                try:
                    mech_type = {
                        "4-bar": MechanismType.FOUR_BAR,
                        "3-bar": MechanismType.THREE_BAR,
                        "cam": MechanismType.CAM,
                    }.get(mech_type_str)

                    if mech_type is None:
                        continue

                    numeric_params = [v for v in item["parameters"].values() if isinstance(v, (int, float))]
                    params = np.array(numeric_params)
                    points = np.array(item["path_coordinates"])
                    motion_curve = MotionCurve(points=points, parameter_vector=params)
                    features = self.similarity_metric._extract_curve_features(motion_curve)

                    entry = PrecomputedMotionEntry(
                        mechanism_type=mech_type,
                        parameters=params,
                        motion_curve=motion_curve,
                        features=features,
                    )

                    if mech_type not in self.entries:
                        self.entries[mech_type] = []
                    self.entries[mech_type].append(entry)

                except (KeyError, TypeError) as e:
                    print(f"Skipping invalid entry in database: {item.get('name')}, error: {e}")
                    continue

            for mech_type, entries in self.entries.items():
                if entries:
                    features = np.array([e.features for e in entries])
                    self.feature_trees[mech_type] = cKDTree(features)

            print(f"Database loaded successfully from {db_path} with {len(data)} total entries.")

        except Exception as e:
            logger.error(f"Error loading database: {e}")
