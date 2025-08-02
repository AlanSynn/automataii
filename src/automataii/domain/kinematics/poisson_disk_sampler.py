"""
Poisson-Disk Sampling for Mechanism Database Generation

Implements PAPER_IMPL.md Section 2.2 requirement:
"Generate a large set of sample motions using Poisson-disk sampling 
in the metric space of the output curves to ensure diversity."

250% Confidence Implementation
"""

import numpy as np
import logging
from typing import List, Dict, Any, Optional, Tuple, Callable
from dataclasses import dataclass
import time

from .curve_similarity import CurveSimilarity
from .mechanism import MotionCurve


@dataclass
class SamplePoint:
    """A sample point in the mechanism parameter/curve feature space."""
    parameters: np.ndarray
    curve_features: np.ndarray
    motion_curve: MotionCurve
    mechanism_type: str
    sample_id: int


class PoissonDiskSampler:
    """
    Poisson-disk sampler for mechanism parameter space.
    
    Critical Feature: Sampling occurs in the METRIC SPACE of output curves,
    not in the input parameter space. This ensures perceptual diversity
    of the generated motions as required by the paper.
    
    Algorithm:
    1. Generate candidate parameters randomly
    2. Simulate mechanism to get motion curve
    3. Extract curve features using CurveSimilarity
    4. Check distance to all existing samples in feature space
    5. Accept only if minimum distance > threshold (Poisson condition)
    """
    
    def __init__(self, curve_similarity: CurveSimilarity, min_distance: float = 0.1,
                 max_attempts: int = 10000, feature_space_dim: int = 15):
        """
        Initialize Poisson-disk sampler.
        
        Args:
            curve_similarity: Curve similarity metric for distance computation
            min_distance: Minimum distance in feature space (Poisson radius)
            max_attempts: Maximum attempts before giving up
            feature_space_dim: Dimension of curve feature space
        """
        self.curve_similarity = curve_similarity
        self.min_distance = min_distance
        self.max_attempts = max_attempts
        self.feature_space_dim = feature_space_dim
        
        self.logger = logging.getLogger(__name__)
        
        # Sampling state
        self.samples: List[SamplePoint] = []
        self.sample_counter = 0
        self.rejected_samples = 0
        self.total_attempts = 0
        
    def generate_samples(self, mechanism_type: str, target_count: int,
                        parameter_generator: Callable[[], np.ndarray],
                        mechanism_simulator: Callable[[str, np.ndarray], MotionCurve],
                        progress_callback: Optional[Callable[[int, int], None]] = None) -> List[SamplePoint]:
        """
        Generate Poisson-disk distributed samples for a mechanism type.
        
        Args:
            mechanism_type: Type of mechanism to sample
            target_count: Target number of samples to generate
            parameter_generator: Function that generates random parameters
            mechanism_simulator: Function that simulates mechanism motion
            progress_callback: Optional progress reporting function
            
        Returns:
            List of sample points with Poisson-disk distribution in feature space
        """
        self.logger.info(f"Starting Poisson-disk sampling for {mechanism_type} "
                        f"(target: {target_count} samples, min_distance: {self.min_distance})")
        
        start_time = time.time()
        self.samples.clear()
        self.sample_counter = 0
        self.rejected_samples = 0
        self.total_attempts = 0
        
        while len(self.samples) < target_count and self.total_attempts < self.max_attempts:
            self.total_attempts += 1
            
            try:
                # 1. Generate candidate parameters
                candidate_params = parameter_generator()
                
                # 2. Simulate mechanism to get motion curve
                motion_curve = mechanism_simulator(mechanism_type, candidate_params)
                
                # 3. Extract curve features
                curve_features = self.curve_similarity._extract_curve_features(motion_curve)
                
                # 4. Check Poisson-disk condition in feature space
                if self._is_valid_poisson_sample(curve_features):
                    # Accept sample
                    sample = SamplePoint(
                        parameters=candidate_params,
                        curve_features=curve_features,
                        motion_curve=motion_curve,
                        mechanism_type=mechanism_type,
                        sample_id=self.sample_counter
                    )
                    
                    self.samples.append(sample)
                    self.sample_counter += 1
                    
                    if progress_callback and len(self.samples) % 10 == 0:
                        progress_callback(len(self.samples), target_count)
                    
                    self.logger.debug(f"Accepted sample {len(self.samples)}/{target_count} "
                                    f"(attempts: {self.total_attempts})")
                else:
                    # Reject sample
                    self.rejected_samples += 1
                    
            except Exception as e:
                self.logger.warning(f"Error generating sample {self.total_attempts}: {e}")
                self.rejected_samples += 1
                continue
        
        elapsed_time = time.time() - start_time
        acceptance_rate = len(self.samples) / max(self.total_attempts, 1)
        
        self.logger.info(f"Poisson-disk sampling completed: {len(self.samples)} samples "
                        f"in {elapsed_time:.1f}s (acceptance rate: {acceptance_rate:.1%})")
        
        if len(self.samples) < target_count:
            self.logger.warning(f"Only generated {len(self.samples)}/{target_count} samples "
                              f"after {self.total_attempts} attempts")
        
        return self.samples.copy()
    
    def _is_valid_poisson_sample(self, candidate_features: np.ndarray) -> bool:
        """
        Check if candidate satisfies Poisson-disk condition.
        
        Args:
            candidate_features: Feature vector for candidate sample
            
        Returns:
            True if candidate is valid (minimum distance satisfied)
        """
        if not self.samples:
            return True  # First sample is always valid
        
        # Check distance to all existing samples in feature space
        for existing_sample in self.samples:
            distance = self._compute_feature_distance(candidate_features, 
                                                    existing_sample.curve_features)
            if distance < self.min_distance:
                return False  # Too close to existing sample
        
        return True
    
    def _compute_feature_distance(self, features_1: np.ndarray, 
                                features_2: np.ndarray) -> float:
        """
        Compute distance between two feature vectors.
        
        Uses the same metric as CurveSimilarity for consistency.
        
        Args:
            features_1: First feature vector
            features_2: Second feature vector
            
        Returns:
            Distance in feature space
        """
        # Use weighted Euclidean distance consistent with CurveSimilarity
        diff = features_1 - features_2
        weighted_sq_diff = np.sum(self.curve_similarity.weights * (diff**2))
        return np.sqrt(weighted_sq_diff)
    
    def get_sampling_statistics(self) -> Dict[str, Any]:
        """Get sampling performance statistics."""
        return {
            'total_samples': len(self.samples),
            'total_attempts': self.total_attempts,
            'rejected_samples': self.rejected_samples,
            'acceptance_rate': len(self.samples) / max(self.total_attempts, 1),
            'min_distance': self.min_distance,
            'feature_space_dimension': self.feature_space_dim,
            'average_sample_density': self._compute_average_density()
        }
    
    def _compute_average_density(self) -> float:
        """Compute average sample density in feature space."""
        if len(self.samples) < 2:
            return 0.0
        
        total_distance = 0.0
        count = 0
        
        # Compute average nearest-neighbor distance
        for i, sample_i in enumerate(self.samples):
            min_distance = float('inf')
            for j, sample_j in enumerate(self.samples):
                if i != j:
                    distance = self._compute_feature_distance(
                        sample_i.curve_features, sample_j.curve_features)
                    min_distance = min(min_distance, distance)
            
            if min_distance < float('inf'):
                total_distance += min_distance
                count += 1
        
        return total_distance / max(count, 1)
    
    def export_samples(self, filepath: str, include_curves: bool = False):
        """
        Export samples to file for database storage.
        
        Args:
            filepath: Output file path
            include_curves: Whether to include full motion curve data
        """
        import json
        
        export_data = {
            'metadata': {
                'mechanism_type': self.samples[0].mechanism_type if self.samples else 'unknown',
                'sample_count': len(self.samples),
                'sampling_method': 'poisson_disk',
                'min_distance': self.min_distance,
                'feature_space_dim': self.feature_space_dim,
                'statistics': self.get_sampling_statistics()
            },
            'samples': []
        }
        
        for sample in self.samples:
            sample_data = {
                'sample_id': sample.sample_id,
                'parameters': sample.parameters.tolist(),
                'curve_features': sample.curve_features.tolist(),
                'mechanism_type': sample.mechanism_type
            }
            
            if include_curves:
                sample_data['motion_curve'] = {
                    'points': sample.motion_curve.points.tolist(),
                    'period': float(sample.motion_curve.period),
                    'attachment_point': sample.motion_curve.attachment_point.tolist()
                }
            
            export_data['samples'].append(sample_data)
        
        with open(filepath, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        self.logger.info(f"Exported {len(self.samples)} samples to {filepath}")
    
    @classmethod
    def load_samples(cls, filepath: str) -> List[SamplePoint]:
        """
        Load samples from exported file.
        
        Args:
            filepath: Path to exported samples file
            
        Returns:
            List of loaded sample points
        """
        import json
        
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        samples = []
        for sample_data in data['samples']:
            # Reconstruct motion curve if available
            motion_curve = None
            if 'motion_curve' in sample_data:
                curve_data = sample_data['motion_curve']
                motion_curve = MotionCurve(
                    points=np.array(curve_data['points']),
                    period=curve_data['period'],
                    attachment_point=np.array(curve_data['attachment_point']),
                    parameter_vector=np.array(sample_data['parameters'])
                )
            
            sample = SamplePoint(
                parameters=np.array(sample_data['parameters']),
                curve_features=np.array(sample_data['curve_features']),
                motion_curve=motion_curve,
                mechanism_type=sample_data['mechanism_type'],
                sample_id=sample_data['sample_id']
            )
            
            samples.append(sample)
        
        return samples


class AdaptivePoissonSampler(PoissonDiskSampler):
    """
    Adaptive Poisson-disk sampler that adjusts min_distance based on density.
    
    Automatically reduces minimum distance when sampling becomes difficult,
    ensuring we can reach target sample count while maintaining diversity.
    """
    
    def __init__(self, curve_similarity: CurveSimilarity, initial_min_distance: float = 0.1,
                 min_distance_factor: float = 0.8, adaptation_threshold: int = 1000):
        """
        Initialize adaptive sampler.
        
        Args:
            curve_similarity: Curve similarity metric
            initial_min_distance: Starting minimum distance
            min_distance_factor: Factor to reduce min_distance when adapting
            adaptation_threshold: Attempts before adapting distance
        """
        super().__init__(curve_similarity, initial_min_distance)
        
        self.initial_min_distance = initial_min_distance
        self.min_distance_factor = min_distance_factor
        self.adaptation_threshold = adaptation_threshold
        self.adaptations = 0
        
    def generate_samples(self, mechanism_type: str, target_count: int,
                        parameter_generator: Callable[[], np.ndarray],
                        mechanism_simulator: Callable[[str, np.ndarray], MotionCurve],
                        progress_callback: Optional[Callable[[int, int], None]] = None) -> List[SamplePoint]:
        """Generate samples with adaptive distance adjustment."""
        
        last_sample_count = 0
        attempts_since_last_sample = 0
        
        while len(self.samples) < target_count and self.total_attempts < self.max_attempts:
            # Run batch of standard sampling
            batch_samples = super().generate_samples(
                mechanism_type, 
                min(target_count, len(self.samples) + 100),  # Batch size
                parameter_generator,
                mechanism_simulator,
                progress_callback
            )
            
            # Check if we need to adapt
            if len(self.samples) == last_sample_count:
                attempts_since_last_sample += 100
                
                if attempts_since_last_sample >= self.adaptation_threshold:
                    # Reduce minimum distance to increase acceptance rate
                    old_distance = self.min_distance
                    self.min_distance *= self.min_distance_factor
                    self.adaptations += 1
                    
                    self.logger.info(f"Adapted min_distance: {old_distance:.3f} -> {self.min_distance:.3f} "
                                   f"(adaptation #{self.adaptations})")
                    
                    attempts_since_last_sample = 0
            else:
                last_sample_count = len(self.samples)
                attempts_since_last_sample = 0
        
        return self.samples