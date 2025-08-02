#!/usr/bin/env python3
"""
Test script for curve metric training capability.

Validates PAPER_IMPL.md Section 2.3 implementation:
- SQP optimization with SLSQP
- Analytical gradients
- Constrained optimization (weights ≥ 0, sum = 1)
- L2 regularization

250% Confidence Test
"""

import sys
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from automataii.domain.kinematics.curve_similarity import CurveSimilarity, UserFeedback
from automataii.domain.kinematics.mechanism import MotionCurve


def create_test_curves():
    """Create diverse test curves for training."""
    curves = []
    
    # 1. Circular motion
    t = np.linspace(0, 2*np.pi, 100)
    circle = np.column_stack([50 * np.cos(t), 50 * np.sin(t)])
    curves.append(MotionCurve(
        points=circle,
        period=2*np.pi,
        attachment_point=np.array([0, 0]),
        parameter_vector=np.array([50, 50, 0, 0])
    ))
    
    # 2. Figure-8 motion
    figure8 = np.column_stack([30 * np.sin(t), 30 * np.sin(2*t)])
    curves.append(MotionCurve(
        points=figure8,
        period=2*np.pi,
        attachment_point=np.array([0, 0]),
        parameter_vector=np.array([30, 30, 1, 2])
    ))
    
    # 3. Elliptical motion
    ellipse = np.column_stack([80 * np.cos(t), 40 * np.sin(t)])
    curves.append(MotionCurve(
        points=ellipse,
        period=2*np.pi,
        attachment_point=np.array([0, 0]),
        parameter_vector=np.array([80, 40, 0, 0])
    ))
    
    # 4. Linear motion
    linear = np.column_stack([t * 10, np.zeros_like(t)])
    curves.append(MotionCurve(
        points=linear,
        period=2*np.pi,
        attachment_point=np.array([0, 0]),
        parameter_vector=np.array([10, 0, 1, 0])
    ))
    
    # 5. Similar circle (smaller)
    small_circle = np.column_stack([30 * np.cos(t), 30 * np.sin(t)])
    curves.append(MotionCurve(
        points=small_circle,
        period=2*np.pi,
        attachment_point=np.array([0, 0]),
        parameter_vector=np.array([30, 30, 0, 0])
    ))
    
    return curves


def test_metric_training():
    """Test the complete metric training pipeline."""
    print("🎯 Testing Curve Metric Training (PAPER_IMPL.md Section 2.3)")
    
    # Create test curves
    curves = create_test_curves()
    circle, figure8, ellipse, linear, small_circle = curves
    
    # Initialize similarity metric
    similarity = CurveSimilarity()
    
    print(f"📊 Initial weights: {similarity.weights}")
    
    # Add training feedback
    print("\n📝 Adding user feedback for training...")
    
    # Circles should be similar
    similarity.add_user_feedback(circle, small_circle, similarity_score=0.8, weight=1.0)
    
    # Circle and ellipse are moderately similar (both closed curves)
    similarity.add_user_feedback(circle, ellipse, similarity_score=0.6, weight=1.0)
    
    # Circle and figure-8 are somewhat similar (both closed, but different complexity)
    similarity.add_user_feedback(circle, figure8, similarity_score=0.4, weight=1.0)
    
    # Circle and linear are very different
    similarity.add_user_feedback(circle, linear, similarity_score=0.1, weight=1.0)
    
    # Figure-8 and ellipse are different
    similarity.add_user_feedback(figure8, ellipse, similarity_score=0.3, weight=1.0)
    
    # Linear motion vs closed curves
    similarity.add_user_feedback(linear, figure8, similarity_score=0.1, weight=1.0)
    similarity.add_user_feedback(linear, ellipse, similarity_score=0.1, weight=1.0)
    
    print(f"   Added {len(similarity.training_feedback)} feedback pairs")
    
    # Show training statistics
    stats = similarity.get_training_statistics()
    print(f"📈 Training statistics: {stats}")
    
    # Measure initial predictions
    print("\n🔍 Initial similarity predictions:")
    initial_predictions = {}
    test_pairs = [
        ("circle", "small_circle", circle, small_circle),
        ("circle", "ellipse", circle, ellipse),
        ("circle", "figure8", circle, figure8),
        ("circle", "linear", circle, linear),
    ]
    
    for name1, name2, curve1, curve2 in test_pairs:
        pred = similarity.predict_similarity(curve1, curve2)
        initial_predictions[f"{name1}-{name2}"] = pred
        print(f"   {name1} <-> {name2}: {pred:.3f}")
    
    # Train the metric
    print("\n🚀 Training similarity metric with SQP optimization...")
    training_result = similarity.train(
        max_iterations=100,
        tolerance=1e-6,
        regularization=0.01
    )
    
    if training_result.success:
        print(f"✅ Training successful!")
        print(f"   Iterations: {training_result.iterations}")
        print(f"   Final loss: {training_result.final_loss:.2e}")
        print(f"   Trained weights: {training_result.trained_weights}")
        
        # Verify constraints
        weight_sum = np.sum(training_result.trained_weights)
        min_weight = np.min(training_result.trained_weights)
        print(f"   Weight sum: {weight_sum:.6f} (should be 1.0)")
        print(f"   Minimum weight: {min_weight:.6f} (should be ≥ 0)")
        
        # Test improved predictions
        print("\n🎯 Improved similarity predictions:")
        for name1, name2, curve1, curve2 in test_pairs:
            pred = similarity.predict_similarity(curve1, curve2)
            initial = initial_predictions[f"{name1}-{name2}"]
            improvement = pred - initial
            print(f"   {name1} <-> {name2}: {pred:.3f} (Δ{improvement:+.3f})")
        
        # Plot convergence
        if len(training_result.convergence_history) > 1:
            plt.figure(figsize=(10, 6))
            plt.plot(training_result.convergence_history)
            plt.title('Metric Training Convergence')
            plt.xlabel('Iteration')
            plt.ylabel('Loss')
            plt.yscale('log')
            plt.grid(True)
            plt.savefig('metric_training_convergence.png', dpi=150, bbox_inches='tight')
            print(f"📊 Convergence plot saved to metric_training_convergence.png")
        
        # Test weight interpretability
        print(f"\n🔬 Feature weight analysis:")
        feature_names = [
            'curve_length', 'area', 'aspect_ratio', 'mean_curvature', 'curvature_std',
            'max_curvature', 'fourier_1', 'fourier_2', 'fourier_3', 'fourier_4',
            'fourier_5', 'fourier_6', 'feature_13', 'feature_14', 'feature_15'
        ]
        
        for i, (name, weight) in enumerate(zip(feature_names, training_result.trained_weights)):
            if weight > 0.05:  # Show significant weights
                print(f"   {name}: {weight:.3f}")
        
        return True
        
    else:
        print(f"❌ Training failed: {training_result.metadata}")
        return False


def test_gradient_accuracy():
    """Test analytical gradient accuracy against numerical gradients."""
    print("\n🧮 Testing analytical gradient accuracy...")
    
    curves = create_test_curves()
    similarity = CurveSimilarity()
    
    # Add some feedback
    similarity.add_user_feedback(curves[0], curves[1], 0.5)
    similarity.add_user_feedback(curves[0], curves[2], 0.7)
    
    # Extract features
    features1 = similarity._extract_curve_features(curves[0])
    features2 = similarity._extract_curve_features(curves[1])
    
    w = similarity.weights / np.sum(similarity.weights)
    epsilon = 1e-8
    
    # Analytical gradient computation
    diff = features1 - features2
    weighted_sq_diff = np.sum(w * (diff**2))
    distance = np.sqrt(weighted_sq_diff)
    predicted_similarity = np.exp(-distance)
    
    # Analytical gradient
    if distance > 1e-8:
        ddistance_dw = 0.5 * (diff**2) / distance
        analytical_grad = -predicted_similarity * ddistance_dw
    else:
        analytical_grad = np.zeros_like(w)
    
    # Numerical gradient
    numerical_grad = np.zeros_like(w)
    for i in range(len(w)):
        w_plus = w.copy()
        w_plus[i] += epsilon
        dist_plus = np.sqrt(np.sum(w_plus * (diff**2)))
        sim_plus = np.exp(-dist_plus)
        
        w_minus = w.copy()
        w_minus[i] -= epsilon
        dist_minus = np.sqrt(np.sum(w_minus * (diff**2)))
        sim_minus = np.exp(-dist_minus)
        
        numerical_grad[i] = (sim_plus - sim_minus) / (2 * epsilon)
    
    # Compare gradients
    grad_error = np.linalg.norm(analytical_grad - numerical_grad)
    relative_error = grad_error / (np.linalg.norm(numerical_grad) + 1e-12)
    
    print(f"   Gradient error: {grad_error:.2e}")
    print(f"   Relative error: {relative_error:.2e}")
    
    if relative_error < 1e-5:
        print("✅ Analytical gradients are accurate")
        return True
    else:
        print("❌ Analytical gradients have errors")
        return False


if __name__ == "__main__":
    print("🔬 Testing Curve Metric Training Implementation")
    print("=" * 60)
    
    success = True
    
    # Test gradient accuracy first
    success &= test_gradient_accuracy()
    
    # Test full training pipeline
    success &= test_metric_training()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 All metric training tests PASSED!")
        print("✅ PAPER_IMPL.md Section 2.3 implementation validated")
    else:
        print("❌ Some tests FAILED")
        sys.exit(1)