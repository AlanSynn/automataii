import numpy as np
from typing import List
from automataii.kinematics.mechanism import MotionCurve

class CurveSimilarity:
    """
    Calculates the similarity between motion curves based on feature vectors.
    This class is designed to be extensible, allowing for metric training in the future.
    """

    def __init__(self, weights: np.ndarray = None):
        """
        Initializes the similarity metric.
        Args:
            weights: A numpy array of weights for each feature. If None, default weights are used.
        """
        if weights is None:
            # Default weights - placeholder for a trained metric as per the paper.
            self.weights = np.ones(15)
        else:
            self.weights = weights

    def calculate_distance(self, curve1: MotionCurve, curve2: MotionCurve) -> float:
        """
        Calculates the weighted distance between two motion curves.
        """
        features1 = self._extract_curve_features(curve1)
        features2 = self._extract_curve_features(curve2)

        # Weighted Euclidean distance
        diff = features1 - features2
        weighted_sq_diff = np.sum(self.weights * (diff ** 2))
        return np.sqrt(weighted_sq_diff)

    def _extract_curve_features(self, curve: MotionCurve) -> np.ndarray:
        """Extracts a feature vector for curve similarity matching."""
        points = curve.points
        if points.shape[0] < 3:
            return np.zeros(15)  # Return a zero vector for invalid curves

        # 1. Normalize curve (translation and scale invariant)
        centroid = np.mean(points, axis=0)
        points_centered = points - centroid
        scale = np.max(np.linalg.norm(points_centered, axis=1))
        points_normalized = (
            points_centered / scale if scale > 1e-6 else points_centered
        )

        features = []

        # 2. Curve length
        lengths = np.linalg.norm(np.diff(points_normalized, axis=0), axis=1)
        features.append(np.sum(lengths))

        # 3. Area (using shoelace formula)
        area = 0.5 * np.abs(
            np.dot(points_normalized[:, 0], np.roll(points_normalized[:, 1], 1))
            - np.dot(points_normalized[:, 1], np.roll(points_normalized[:, 0], 1))
        )
        features.append(area)

        # 4. Aspect ratio from PCA
        covariance_matrix = np.cov(points_normalized, rowvar=False)
        eigenvalues, _ = np.linalg.eigh(covariance_matrix)
        aspect_ratio = (
            np.sqrt(eigenvalues[0] / eigenvalues[1]) if eigenvalues[1] > 1e-6 else 0
        )
        features.append(aspect_ratio)

        # 5. Curvature statistics
        curvatures = self._compute_discrete_curvature(points_normalized)
        features.extend(
            [
                np.mean(curvatures),
                np.std(curvatures),
                np.max(np.abs(curvatures)),
            ]
        )

        # 6. Fourier descriptors (first 5 coefficients for simplicity)
        complex_coords = points_normalized[:, 0] + 1j * points_normalized[:, 1]
        fft = np.fft.fft(complex_coords)
        # Use first 5 non-DC components, normalized by the first component
        fft_features = np.abs(fft[1:7]) / (np.abs(fft[1]) if np.abs(fft[1]) > 1e-6 else 1)
        features.extend(fft_features)

        # Pad with zeros if not enough features
        while len(features) < 15:
            features.append(0)

        return np.array(features[:15])

    def _compute_discrete_curvature(self, points: np.ndarray) -> np.ndarray:
        """Computes discrete curvature along the curve."""
        # Using the formula for curvature from vectors
        vec1 = np.diff(points, axis=0)
        vec2 = np.roll(vec1, -1, axis=0)
        # Using cross product for 2D vectors
        cross_product = vec1[:-1, 0] * vec2[:-1, 1] - vec1[:-1, 1] * vec2[:-1, 0]
        dot_product = np.sum(vec1[:-1] * vec2[:-1], axis=1)
        norm_prod = np.linalg.norm(vec1[:-1], axis=1) * np.linalg.norm(vec2[:-1], axis=1)

        # Avoid division by zero
        safe_norm_prod = np.where(norm_prod > 1e-6, norm_prod, 1e-6)

        # Angle between vectors
        cosine_angle = dot_product / safe_norm_prod
        angle = np.arccos(np.clip(cosine_angle, -1.0, 1.0))

        # Curvature is change in angle over arc length
        ds = (np.linalg.norm(vec1[:-1], axis=1) + np.linalg.norm(vec2[:-1], axis=1)) / 2
        safe_ds = np.where(ds > 1e-6, ds, 1e-6)

        curvature = angle / safe_ds
        return np.nan_to_num(curvature)
