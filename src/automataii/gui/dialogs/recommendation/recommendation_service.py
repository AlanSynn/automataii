"""Service for mechanism recommendation logic."""

from typing import Any, Dict, List, Optional
import numpy as np
from PyQt6.QtGui import QPainterPath

from .constants import MECHANISM_TYPE_MAPPING, DEFAULT_NUM_SAMPLES_FOR_PATH
from .path_analysis import (
    qpainterpath_to_numpy_array,
    calculate_hausdorff_distance
)
from .data_loader import MechanismDataLoader


class MechanismRecommendationService:
    """Service class for mechanism recommendation logic."""
    
    def __init__(self, user_motion_path: QPainterPath, 
                 generated_paths_filepath: str,
                 num_samples_user_path: int = DEFAULT_NUM_SAMPLES_FOR_PATH):
        """Initialize the recommendation service.
        
        Args:
            user_motion_path: The user's drawn motion path
            generated_paths_filepath: Path to JSON file with generated mechanisms
            num_samples_user_path: Number of samples to take from user path
        """
        self.user_motion_path = user_motion_path
        self.user_motion_path_np = qpainterpath_to_numpy_array(
            user_motion_path, num_samples_user_path
        )
        
        self.generated_paths_data = MechanismDataLoader.load_generated_paths(
            generated_paths_filepath
        )
    
    def get_best_recommendations(self) -> List[Optional[Dict[str, Any]]]:
        """
        Compares the user's motion path with generated paths using Hausdorff distance
        and returns the top 2-3 matches, ensuring diversity across mechanism types.
        
        Returns:
            List of top mechanism recommendations (may include None for empty slots)
        """
        if self.user_motion_path_np is None or not self.generated_paths_data:
            print("User motion path is not processed or no generated paths loaded.")
            return []

        # Group mechanisms by type
        mechanisms_by_type = self._group_mechanisms_by_type()
        
        # Get the best mechanism of each type
        best_per_type = self._get_best_per_type(mechanisms_by_type)
        
        # Sort all best mechanisms by score
        best_per_type.sort(key=lambda x: x["overall_score"])
        
        # Take top 3, ensuring diversity
        top_recommendations = best_per_type[:3]

        # Fill remaining slots if needed
        top_recommendations = self._fill_remaining_slots(
            top_recommendations, mechanisms_by_type
        )

        # Ensure we have at least 3 slots (can be empty)
        while len(top_recommendations) < 3:
            top_recommendations.append(None)

        return top_recommendations
    
    def _group_mechanisms_by_type(self) -> Dict[str, List[Dict[str, Any]]]:
        """Group mechanisms by their display type.
        
        Returns:
            Dictionary mapping mechanism types to lists of mechanism data
        """
        mechanisms_by_type = {}
        
        for gen_path_data in self.generated_paths_data:
            gen_path_np = gen_path_data.get("path_coordinates_np")
            json_type_str = gen_path_data.get("type")

            if gen_path_np is None or json_type_str is None:
                continue

            distance = calculate_hausdorff_distance(
                self.user_motion_path_np, gen_path_np
            )

            target_mech_type = MECHANISM_TYPE_MAPPING.get(
                json_type_str, json_type_str
            )

            # Prepare data for PreviewContainer
            preview_data = {
                "name": gen_path_data.get("name", json_type_str),
                "type": target_mech_type,
                "original_json_type": json_type_str,
                "overall_score": distance,
                "parameters": gen_path_data.get("parameters"),
                "path_coordinates_np": gen_path_np,
                "path_coordinates": gen_path_data.get("path_coordinates"),
            }
            
            # Group by mechanism type
            if target_mech_type not in mechanisms_by_type:
                mechanisms_by_type[target_mech_type] = []
            mechanisms_by_type[target_mech_type].append(preview_data)
        
        return mechanisms_by_type
    
    def _get_best_per_type(self, mechanisms_by_type: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """Get the best mechanism of each type.
        
        Args:
            mechanisms_by_type: Dictionary of mechanisms grouped by type
            
        Returns:
            List of best mechanisms per type
        """
        best_per_type = []
        for mech_type, mechanisms in mechanisms_by_type.items():
            # Sort mechanisms of this type by score
            mechanisms.sort(key=lambda x: x["overall_score"])
            # Take the best one
            if mechanisms:
                best_per_type.append(mechanisms[0])
        return best_per_type
    
    def _fill_remaining_slots(self, top_recommendations: List[Dict[str, Any]], 
                              mechanisms_by_type: Dict[str, List[Dict[str, Any]]]) -> List[Optional[Dict[str, Any]]]:
        """Fill remaining recommendation slots with next best mechanisms.
        
        Args:
            top_recommendations: Current list of recommendations
            mechanisms_by_type: Dictionary of mechanisms grouped by type
            
        Returns:
            Updated list of recommendations
        """
        if len(top_recommendations) < 3:
            # Collect all mechanisms not already selected
            all_remaining = []
            selected_names = {r["name"] for r in top_recommendations}
            
            for mechanisms in mechanisms_by_type.values():
                for m in mechanisms:
                    if m["name"] not in selected_names:
                        all_remaining.append(m)
            
            # Sort remaining by score and add to recommendations
            all_remaining.sort(key=lambda x: x["overall_score"])
            for m in all_remaining:
                if len(top_recommendations) >= 3:
                    break
                top_recommendations.append(m)
        
        return top_recommendations