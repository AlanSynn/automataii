"""Data loading and processing for mechanism recommendations."""

import json
from typing import Any, Dict, List
import numpy as np


class MechanismDataLoader:
    """Handles loading and processing of mechanism path data."""
    
    @staticmethod
    def load_generated_paths(filepath: str) -> List[Dict[str, Any]]:
        """Loads mechanism paths from a JSON file and prepares them.
        
        Args:
            filepath: Path to the JSON file containing mechanism data
            
        Returns:
            List of mechanism data dictionaries with numpy arrays
        """
        loaded_paths = []
        try:
            with open(filepath, "r") as f:
                raw_data = json.load(f)

            for item in raw_data:
                path_coords = item.get("path_coordinates")
                if (
                    path_coords
                    and isinstance(path_coords, list)
                    and len(path_coords) > 0
                ):
                    # Ensure coordinates are suitable for numpy array
                    try:
                        item["path_coordinates_np"] = np.array(path_coords, dtype=float)
                        loaded_paths.append(item)
                    except ValueError as e:
                        print(
                            f"Warning: Could not convert path_coordinates to numpy array "
                            f"for item: {item.get('type', 'N/A')}. Error: {e}"
                        )
                else:
                    print(
                        f"Warning: Missing or invalid 'path_coordinates' "
                        f"for item: {item.get('type', 'N/A')}"
                    )

        except FileNotFoundError:
            print(f"Error: Generated paths file not found at {filepath}")
        except json.JSONDecodeError:
            print(f"Error: Could not decode JSON from {filepath}")
        except Exception as e:
            print(f"An unexpected error occurred while loading generated paths: {e}")
        return loaded_paths