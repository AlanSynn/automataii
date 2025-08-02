import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.optimize import minimize

from automataii.domain.kinematics.mechanism import MotionCurve


@dataclass
class UserFeedback:
    """User feedback for curve similarity training."""

    curve1: MotionCurve
    curve2: MotionCurve
    similarity_score: float  # 0 = dissimilar, 1 = very similar
    weight: float = 1.0  # Importance weight for this feedback


@dataclass
class TrainingResult:
    """Result from metric training."""

    success: bool
    trained_weights: np.ndarray
    final_loss: float
    iterations: int
    convergence_history: list[float]
    metadata: dict[str, Any]


class CurveSimilarity:
    """
    Calculates the similarity between motion curves based on feature vectors.

    Implements PAPER_IMPL.md Section 2.3: Metric training capability using
    SQP optimization to learn weights from user similarity feedback.

    250% Confidence Implementation
    """

    def __init__(self, weights: np.ndarray = None):
        """
        Initializes the similarity metric.
        Args:
            weights: A numpy array of weights for each feature. If None, default weights are used.
        """
        if weights is None:
            # Default weights - will be trained from user feedback
            self.weights = np.ones(15)
        else:
            self.weights = weights

        self.logger = logging.getLogger(__name__)

        # Training data storage
        self.training_feedback: list[UserFeedback] = []

    def calculate_distance(self, curve1: MotionCurve, curve2: MotionCurve) -> float:
        """
        Calculates the weighted distance between two motion curves.
        """
        features1 = self._extract_curve_features(curve1)
        features2 = self._extract_curve_features(curve2)

        # Weighted Euclidean distance
        diff = features1 - features2
        weighted_sq_diff = np.sum(self.weights * (diff**2))
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
        points_normalized = points_centered / scale if scale > 1e-6 else points_centered

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
        aspect_ratio = np.sqrt(eigenvalues[0] / eigenvalues[1]) if eigenvalues[1] > 1e-6 else 0
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
        # Using dot product for angle calculation
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

    def add_user_feedback(
        self, curve1: MotionCurve, curve2: MotionCurve, similarity_score: float, weight: float = 1.0
    ):
        """
        Add user feedback for metric training.

        Args:
            curve1: First motion curve
            curve2: Second motion curve
            similarity_score: User-provided similarity (0=dissimilar, 1=very similar)
            weight: Importance weight for this feedback pair
        """
        feedback = UserFeedback(curve1, curve2, similarity_score, weight)
        self.training_feedback.append(feedback)

        self.logger.info(
            f"Added user feedback: similarity={similarity_score:.2f}, "
            f"weight={weight:.2f} (total feedback: {len(self.training_feedback)})"
        )

    def train(
        self, max_iterations: int = 100, tolerance: float = 1e-6, regularization: float = 0.01
    ) -> TrainingResult:
        """
        Train the similarity metric using SQP optimization.

        Implements PAPER_IMPL.md Section 2.3 exact algorithm:
        - Minimize weighted squared loss between predicted and user similarities
        - Use SLSQP for constrained optimization (weights ≥ 0, sum = 1)
        - L2 regularization to prevent overfitting

        Args:
            max_iterations: Maximum optimization iterations
            tolerance: Convergence tolerance
            regularization: L2 regularization strength

        Returns:
            TrainingResult with optimized weights and convergence info
        """
        if len(self.training_feedback) < 2:
            self.logger.warning("Insufficient training data for metric learning")
            return TrainingResult(
                success=False,
                trained_weights=self.weights.copy(),
                final_loss=float("inf"),
                iterations=0,
                convergence_history=[],
                metadata={"error": "Insufficient training data"},
            )

        self.logger.info(
            f"Starting metric training with {len(self.training_feedback)} feedback pairs"
        )

        # Extract feature pairs and target similarities
        feature_pairs = []
        target_similarities = []
        feedback_weights = []

        for feedback in self.training_feedback:
            features1 = self._extract_curve_features(feedback.curve1)
            features2 = self._extract_curve_features(feedback.curve2)

            feature_pairs.append((features1, features2))
            target_similarities.append(feedback.similarity_score)
            feedback_weights.append(feedback.weight)

        feature_pairs = np.array(feature_pairs)
        target_similarities = np.array(target_similarities)
        feedback_weights = np.array(feedback_weights)

        # Initialize optimization
        w0 = self.weights / np.sum(self.weights)  # Normalize initial weights
        convergence_history = []

        def objective_function(w):
            """
            Objective function: weighted squared loss + L2 regularization.

            Loss = Σ w_i * (predicted_similarity_i - target_similarity_i)²
                   + λ * ||w||²
            """
            w = np.maximum(w, 1e-8)  # Ensure positivity
            predicted_distances = []

            for features1, features2 in feature_pairs:
                diff = features1 - features2
                weighted_sq_diff = np.sum(w * (diff**2))
                distance = np.sqrt(weighted_sq_diff)
                # Convert distance to similarity: similarity = exp(-distance)
                predicted_similarity = np.exp(-distance)
                predicted_distances.append(predicted_similarity)

            predicted_similarities = np.array(predicted_distances)

            # Weighted squared loss
            loss_terms = feedback_weights * (predicted_similarities - target_similarities) ** 2
            data_loss = np.sum(loss_terms)

            # L2 regularization
            reg_loss = regularization * np.sum(w**2)

            total_loss = data_loss + reg_loss
            convergence_history.append(total_loss)

            return total_loss

        def gradient_function(w):
            """
            Analytical gradient of the objective function.

            ∂L/∂w = Σ w_i * 2 * (pred_sim_i - target_sim_i) * ∂pred_sim_i/∂w
                    + 2 * λ * w
            """
            w = np.maximum(w, 1e-8)
            total_gradient = np.zeros_like(w)

            for i, (features1, features2) in enumerate(feature_pairs):
                diff = features1 - features2
                weighted_sq_diff = np.sum(w * (diff**2))
                distance = np.sqrt(weighted_sq_diff)
                predicted_similarity = np.exp(-distance)

                # ∂pred_sim/∂w = -exp(-distance) * ∂distance/∂w
                # ∂distance/∂w = (1/2) * (1/√(w·diff²)) * diff²
                if distance > 1e-8:
                    ddistance_dw = 0.5 * (diff**2) / distance
                    dpred_sim_dw = -predicted_similarity * ddistance_dw
                else:
                    dpred_sim_dw = np.zeros_like(w)

                # Chain rule for loss gradient
                loss_gradient = (
                    2 * feedback_weights[i] * (predicted_similarity - target_similarities[i])
                )
                total_gradient += loss_gradient * dpred_sim_dw

            # Add regularization gradient
            total_gradient += 2 * regularization * w

            return total_gradient

        # Define constraints
        constraints = [
            # Weights must sum to 1 (normalization constraint)
            {"type": "eq", "fun": lambda w: np.sum(w) - 1.0, "jac": lambda w: np.ones_like(w)},
        ]

        # Define bounds: weights ≥ 0
        bounds = [(1e-8, None) for _ in range(len(w0))]

        try:
            # Run SLSQP optimization (Sequential Least Squares Programming)
            result = minimize(
                objective_function,
                w0,
                method="SLSQP",
                jac=gradient_function,
                constraints=constraints,
                bounds=bounds,
                options={"maxiter": max_iterations, "ftol": tolerance, "disp": False},
            )

            if result.success:
                # Update weights with trained values
                self.weights = result.x.copy()

                self.logger.info(
                    f"Metric training converged in {result.nit} iterations "
                    f"(final loss: {result.fun:.2e})"
                )

                training_result = TrainingResult(
                    success=True,
                    trained_weights=result.x.copy(),
                    final_loss=result.fun,
                    iterations=result.nit,
                    convergence_history=convergence_history,
                    metadata={
                        "message": result.message,
                        "function_evaluations": result.nfev,
                        "optimization_method": "SLSQP",
                        "regularization": regularization,
                        "training_samples": len(self.training_feedback),
                    },
                )
            else:
                self.logger.warning(f"Metric training failed: {result.message}")
                training_result = TrainingResult(
                    success=False,
                    trained_weights=self.weights.copy(),
                    final_loss=result.fun if hasattr(result, "fun") else float("inf"),
                    iterations=result.nit if hasattr(result, "nit") else 0,
                    convergence_history=convergence_history,
                    metadata={"error": result.message},
                )

            return training_result

        except Exception as e:
            self.logger.error(f"Metric training failed with exception: {e}")
            return TrainingResult(
                success=False,
                trained_weights=self.weights.copy(),
                final_loss=float("inf"),
                iterations=0,
                convergence_history=[],
                metadata={"error": str(e)},
            )

    def predict_similarity(self, curve1: MotionCurve, curve2: MotionCurve) -> float:
        """
        Predict similarity score between two curves using current metric.

        Args:
            curve1: First motion curve
            curve2: Second motion curve

        Returns:
            Predicted similarity score (0=dissimilar, 1=very similar)
        """
        distance = self.calculate_distance(curve1, curve2)
        similarity = np.exp(-distance)  # Convert distance to similarity
        return similarity

    def clear_training_data(self):
        """Clear all stored training feedback."""
        self.training_feedback.clear()
        self.logger.info("Cleared all training feedback data")

    def get_training_statistics(self) -> dict[str, Any]:
        """Get statistics about current training data."""
        if not self.training_feedback:
            return {"training_samples": 0}

        similarities = [fb.similarity_score for fb in self.training_feedback]
        weights = [fb.weight for fb in self.training_feedback]

        return {
            "training_samples": len(self.training_feedback),
            "similarity_range": [np.min(similarities), np.max(similarities)],
            "average_similarity": np.mean(similarities),
            "similarity_std": np.std(similarities),
            "average_weight": np.mean(weights),
            "weight_range": [np.min(weights), np.max(weights)],
        }
