"""
Skeleton type detection system for classifying character skeletons.
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from automataii.core.models.skeleton import StandardizedSkeletonModel
from automataii.core.models.skeleton_types import (
    SkeletonType, SkeletonClassificationResult, SKELETON_TEMPLATES, SkeletonTemplate
)


class SkeletonTypeDetector:
    """Detects and classifies skeleton types from various inputs."""
    
    def __init__(self):
        self.templates = SKELETON_TEMPLATES
        
    def classify_from_skeleton(
        self, 
        skeleton: StandardizedSkeletonModel,
        confidence_threshold: float = 0.7
    ) -> SkeletonClassificationResult:
        """
        Classify a skeleton based on its structure and features.
        
        Args:
            skeleton: The skeleton to classify
            confidence_threshold: Minimum confidence for classification
            
        Returns:
            Classification result with type and confidence
        """
        features = self._extract_skeleton_features(skeleton)
        scores = {}
        
        # Score against each template
        for skeleton_type, template in self.templates.items():
            score = self._score_skeleton_against_template(features, template)
            scores[skeleton_type] = score
        
        # Find best match
        best_type = max(scores, key=scores.get)
        best_score = scores[best_type]
        
        # Normalize scores to probabilities
        total_score = sum(scores.values())
        if total_score > 0:
            normalized_scores = {k: v/total_score for k, v in scores.items()}
        else:
            normalized_scores = {k: 0.0 for k in scores}
        
        # Create result
        result = SkeletonClassificationResult(
            primary_type=best_type if best_score >= confidence_threshold else SkeletonType.UNKNOWN,
            confidence=normalized_scores[best_type],
            alternative_types={k: v for k, v in normalized_scores.items() if k != best_type},
            detected_features=features,
            recommendation=self._generate_recommendation(best_type, normalized_scores[best_type])
        )
        
        return result
    
    def classify_from_pose_data(
        self,
        pose_keypoints: Dict[str, Tuple[float, float]],
        confidence_threshold: float = 0.7
    ) -> SkeletonClassificationResult:
        """
        Classify skeleton type from pose detection keypoints.
        
        Args:
            pose_keypoints: Dictionary of keypoint names to positions
            confidence_threshold: Minimum confidence for classification
            
        Returns:
            Classification result
        """
        features = self._extract_pose_features(pose_keypoints)
        scores = {}
        
        # Check for humanoid first (most common)
        if self._is_humanoid_pose(pose_keypoints):
            scores[SkeletonType.HUMANOID] = 0.9
            scores[SkeletonType.QUADRUPED] = 0.05
            scores[SkeletonType.BIRD] = 0.03
            scores[SkeletonType.INSECT] = 0.02
        else:
            # Use feature-based classification
            scores = self._classify_by_features(features)
        
        # Find best match
        best_type = max(scores, key=scores.get)
        best_score = scores[best_type]
        
        # Create result
        result = SkeletonClassificationResult(
            primary_type=best_type if best_score >= confidence_threshold else SkeletonType.UNKNOWN,
            confidence=best_score,
            alternative_types={k: v for k, v in scores.items() if k != best_type},
            detected_features=features,
            recommendation=self._generate_recommendation(best_type, best_score)
        )
        
        return result
    
    def classify_from_image_features(
        self,
        contour: np.ndarray,
        bbox: Tuple[int, int, int, int],
        mask: Optional[np.ndarray] = None
    ) -> SkeletonClassificationResult:
        """
        Classify skeleton type from image features.
        
        Args:
            contour: Character contour points
            bbox: Bounding box (x, y, width, height)
            mask: Optional segmentation mask
            
        Returns:
            Classification result
        """
        features = self._extract_image_features(contour, bbox, mask)
        scores = self._classify_by_features(features)
        
        # Find best match
        best_type = max(scores, key=scores.get)
        best_score = scores[best_type]
        
        # Create result
        result = SkeletonClassificationResult(
            primary_type=best_type if best_score >= 0.5 else SkeletonType.UNKNOWN,
            confidence=best_score,
            alternative_types={k: v for k, v in scores.items() if k != best_type},
            detected_features=features,
            recommendation=self._generate_recommendation(best_type, best_score)
        )
        
        return result
    
    def _extract_skeleton_features(self, skeleton: StandardizedSkeletonModel) -> Dict[str, Any]:
        """Extract features from a skeleton for classification."""
        joints = skeleton.joints
        
        # Count joints and bones
        num_joints = len(joints)
        num_bones = sum(len(children) for children in skeleton.hierarchy.values())
        
        # Calculate aspect ratio
        positions = [joint.position for joint in joints.values()]
        if positions:
            x_coords = [p[0] for p in positions]
            y_coords = [p[1] for p in positions]
            width = max(x_coords) - min(x_coords)
            height = max(y_coords) - min(y_coords)
            aspect_ratio = width / height if height > 0 else 1.0
        else:
            aspect_ratio = 1.0
        
        # Check for symmetry
        left_joints = [j for j in joints if "left" in j.lower()]
        right_joints = [j for j in joints if "right" in j.lower()]
        has_bilateral_symmetry = len(left_joints) == len(right_joints) and len(left_joints) > 0
        
        # Count limbs
        limb_counts = {
            "arms": len([j for j in joints if any(word in j.lower() for word in ["arm", "elbow", "wrist", "hand"])]) // 2,
            "legs": len([j for j in joints if any(word in j.lower() for word in ["leg", "knee", "ankle", "foot"])]) // 2,
            "wings": len([j for j in joints if "wing" in j.lower()]) // 2,
        }
        
        # Check for specific features
        has_tail = any("tail" in j.lower() for j in joints)
        has_wings = limb_counts["wings"] > 0
        
        return {
            "num_joints": num_joints,
            "num_bones": num_bones,
            "aspect_ratio": aspect_ratio,
            "has_bilateral_symmetry": has_bilateral_symmetry,
            "limb_counts": limb_counts,
            "has_tail": has_tail,
            "has_wings": has_wings,
            "horizontal_orientation": aspect_ratio > 1.5,
        }
    
    def _extract_pose_features(self, pose_keypoints: Dict[str, Tuple[float, float]]) -> Dict[str, Any]:
        """Extract features from pose keypoints."""
        num_keypoints = len(pose_keypoints)
        
        # Calculate bounding box and aspect ratio
        if pose_keypoints:
            x_coords = [p[0] for p in pose_keypoints.values()]
            y_coords = [p[1] for p in pose_keypoints.values()]
            width = max(x_coords) - min(x_coords)
            height = max(y_coords) - min(y_coords)
            aspect_ratio = width / height if height > 0 else 1.0
        else:
            aspect_ratio = 1.0
        
        # Check for humanoid keypoints
        humanoid_keys = ["nose", "eye", "ear", "shoulder", "elbow", "wrist", "hip", "knee", "ankle"]
        humanoid_count = sum(1 for key in pose_keypoints if any(hk in key.lower() for hk in humanoid_keys))
        
        return {
            "num_keypoints": num_keypoints,
            "aspect_ratio": aspect_ratio,
            "humanoid_keypoint_ratio": humanoid_count / num_keypoints if num_keypoints > 0 else 0,
            "horizontal_orientation": aspect_ratio > 1.5,
        }
    
    def _extract_image_features(
        self, 
        contour: np.ndarray, 
        bbox: Tuple[int, int, int, int],
        mask: Optional[np.ndarray] = None
    ) -> Dict[str, Any]:
        """Extract features from image data."""
        x, y, w, h = bbox
        aspect_ratio = w / h if h > 0 else 1.0
        
        # Calculate contour features
        if len(contour) > 0:
            # Simplify contour to find major segments
            epsilon = 0.02 * cv2.arcLength(contour, True) if contour.shape[0] > 3 else 0
            approx_contour = cv2.approxPolyDP(contour, epsilon, True) if epsilon > 0 else contour
            num_vertices = len(approx_contour)
        else:
            num_vertices = 0
        
        # Analyze mask for body segments
        body_segments = 1  # Default
        if mask is not None:
            # Simple segmentation analysis
            # This could be enhanced with more sophisticated analysis
            pass
        
        return {
            "aspect_ratio": aspect_ratio,
            "num_vertices": num_vertices,
            "horizontal_orientation": aspect_ratio > 1.5,
            "body_segments": body_segments,
        }
    
    def _score_skeleton_against_template(
        self, 
        features: Dict[str, Any], 
        template: SkeletonTemplate
    ) -> float:
        """Score how well skeleton features match a template."""
        score = 0.0
        weights = {
            "joint_count": 0.3,
            "aspect_ratio": 0.2,
            "symmetry": 0.2,
            "limb_count": 0.2,
            "special_features": 0.1,
        }
        
        template_features = template.detection_features
        
        # Joint count similarity
        if "expected_joints" in template_features:
            expected = template_features["expected_joints"]
            actual = features.get("num_joints", 0)
            joint_score = 1.0 - min(abs(expected - actual) / expected, 1.0)
            score += weights["joint_count"] * joint_score
        
        # Aspect ratio similarity
        if "aspect_ratio_range" in template_features:
            min_ar, max_ar = template_features["aspect_ratio_range"]
            actual_ar = features.get("aspect_ratio", 1.0)
            if min_ar <= actual_ar <= max_ar:
                score += weights["aspect_ratio"]
        
        # Symmetry match
        if "symmetry" in template_features:
            if template_features["symmetry"] == "bilateral" and features.get("has_bilateral_symmetry", False):
                score += weights["symmetry"]
        
        # Limb count match
        if "limb_count" in template_features:
            limb_score = 0.0
            limb_types = template_features["limb_count"]
            for limb_type, expected_count in limb_types.items():
                actual_count = features.get("limb_counts", {}).get(limb_type, 0)
                if actual_count == expected_count:
                    limb_score += 1.0 / len(limb_types)
            score += weights["limb_count"] * limb_score
        
        # Special features
        special_score = 0.0
        special_count = 0
        
        if "has_wings" in template_features:
            special_count += 1
            if template_features["has_wings"] == features.get("has_wings", False):
                special_score += 1.0
        
        if "horizontal_orientation" in template_features:
            special_count += 1
            if template_features["horizontal_orientation"] == features.get("horizontal_orientation", False):
                special_score += 1.0
        
        if special_count > 0:
            score += weights["special_features"] * (special_score / special_count)
        
        return score
    
    def _is_humanoid_pose(self, pose_keypoints: Dict[str, Tuple[float, float]]) -> bool:
        """Check if pose keypoints represent a humanoid skeleton."""
        # Common humanoid keypoint patterns
        humanoid_patterns = [
            # COCO format
            ["nose", "neck", "shoulder", "elbow", "wrist", "hip", "knee", "ankle"],
            # OpenPose format
            ["head", "neck", "shoulder", "elbow", "wrist", "hip", "knee", "ankle"],
            # MediaPipe format
            ["nose", "shoulder", "elbow", "wrist", "hip", "knee", "ankle", "eye", "ear"],
        ]
        
        keypoint_names = set(k.lower() for k in pose_keypoints.keys())
        
        # Check against each pattern
        for pattern in humanoid_patterns:
            matches = sum(1 for p in pattern if any(p in kp for kp in keypoint_names))
            if matches >= len(pattern) * 0.6:  # 60% match threshold
                return True
        
        return False
    
    def _classify_by_features(self, features: Dict[str, Any]) -> Dict[SkeletonType, float]:
        """Classify based on extracted features."""
        scores = {}
        
        # Simple heuristic-based classification
        aspect_ratio = features.get("aspect_ratio", 1.0)
        horizontal = features.get("horizontal_orientation", False)
        
        if horizontal and aspect_ratio > 1.5:
            # Likely quadruped, insect, or fish
            scores[SkeletonType.QUADRUPED] = 0.4
            scores[SkeletonType.INSECT] = 0.3
            scores[SkeletonType.FISH] = 0.2
            scores[SkeletonType.HUMANOID] = 0.05
            scores[SkeletonType.BIRD] = 0.05
        else:
            # Likely humanoid or bird
            scores[SkeletonType.HUMANOID] = 0.5
            scores[SkeletonType.BIRD] = 0.3
            scores[SkeletonType.QUADRUPED] = 0.1
            scores[SkeletonType.INSECT] = 0.05
            scores[SkeletonType.FISH] = 0.05
        
        # Adjust based on specific features
        if features.get("has_wings", False):
            scores[SkeletonType.BIRD] += 0.3
            scores[SkeletonType.INSECT] += 0.1
        
        if features.get("humanoid_keypoint_ratio", 0) > 0.7:
            scores[SkeletonType.HUMANOID] += 0.3
        
        # Normalize scores
        total = sum(scores.values())
        if total > 0:
            scores = {k: v/total for k, v in scores.items()}
        
        # Add missing types with zero score
        for skeleton_type in SkeletonType:
            if skeleton_type not in scores:
                scores[skeleton_type] = 0.0
        
        return scores
    
    def _generate_recommendation(self, skeleton_type: SkeletonType, confidence: float) -> str:
        """Generate a recommendation based on classification results."""
        if confidence < 0.5:
            return "Low confidence detection. Consider using custom skeleton builder."
        elif confidence < 0.7:
            return f"Moderate confidence for {skeleton_type.value}. Review and adjust if needed."
        else:
            return f"High confidence {skeleton_type.value} detected. Using {skeleton_type.value} template."


# Import cv2 only if available (for image feature extraction)
try:
    import cv2
except ImportError:
    cv2 = None