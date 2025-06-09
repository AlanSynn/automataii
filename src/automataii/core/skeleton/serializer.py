"""
Skeleton serialization module for saving and loading skeleton data.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from pydantic import ValidationError

from .models import StandardizedSkeletonModel


class SkeletonSerializer:
    """Handles serialization and deserialization of skeleton data."""

    @staticmethod
    def to_dict(skeleton_model: StandardizedSkeletonModel) -> Dict[str, Any]:
        """
        Convert a StandardizedSkeletonModel to a dictionary.

        Args:
            skeleton_model: The skeleton model to convert

        Returns:
            Dictionary representation of the skeleton
        """
        if not skeleton_model:
            return {}
        return skeleton_model.model_dump()

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> Optional[StandardizedSkeletonModel]:
        """
        Create a StandardizedSkeletonModel from a dictionary.

        Args:
            data: Dictionary containing skeleton data

        Returns:
            StandardizedSkeletonModel instance or None if validation fails
        """
        try:
            return StandardizedSkeletonModel.model_validate(data)
        except ValidationError as e:
            logging.error(f"Failed to validate skeleton data: {e}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error creating skeleton from dict: {e}")
            return None

    @staticmethod
    def to_json(skeleton_model: StandardizedSkeletonModel, indent: int = 2) -> str:
        """
        Convert a StandardizedSkeletonModel to JSON string.

        Args:
            skeleton_model: The skeleton model to convert
            indent: JSON indentation level

        Returns:
            JSON string representation of the skeleton
        """
        if not skeleton_model:
            return "{}"
        return skeleton_model.model_dump_json(indent=indent)

    @staticmethod
    def from_json(json_string: str) -> Optional[StandardizedSkeletonModel]:
        """
        Create a StandardizedSkeletonModel from a JSON string.

        Args:
            json_string: JSON string containing skeleton data

        Returns:
            StandardizedSkeletonModel instance or None if parsing/validation fails
        """
        try:
            data = json.loads(json_string)
            return SkeletonSerializer.from_dict(data)
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse JSON: {e}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error creating skeleton from JSON: {e}")
            return None

    @staticmethod
    def save_to_file(
        skeleton_model: StandardizedSkeletonModel,
        file_path: Path,
        indent: int = 2
    ) -> bool:
        """
        Save a StandardizedSkeletonModel to a JSON file.

        Args:
            skeleton_model: The skeleton model to save
            file_path: Path to the output file
            indent: JSON indentation level

        Returns:
            True if successful, False otherwise
        """
        try:
            file_path = Path(file_path)
            file_path.parent.mkdir(parents=True, exist_ok=True)

            json_content = skeleton_model.model_dump_json(indent=indent)
            file_path.write_text(json_content, encoding='utf-8')

            logging.info(f"Skeleton saved to {file_path}")
            return True
        except Exception as e:
            logging.error(f"Failed to save skeleton to file: {e}")
            return False

    @staticmethod
    def load_from_file(file_path: Path) -> Optional[StandardizedSkeletonModel]:
        """
        Load a StandardizedSkeletonModel from a JSON file.

        Args:
            file_path: Path to the input file

        Returns:
            StandardizedSkeletonModel instance or None if loading fails
        """
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                logging.error(f"File not found: {file_path}")
                return None

            json_content = file_path.read_text(encoding='utf-8')
            return SkeletonSerializer.from_json(json_content)
        except Exception as e:
            logging.error(f"Failed to load skeleton from file: {e}")
            return None

    @staticmethod
    def export_simplified(skeleton_model: StandardizedSkeletonModel) -> Dict[str, Any]:
        """
        Export a simplified version of the skeleton for visualization or external use.

        Args:
            skeleton_model: The skeleton model to export

        Returns:
            Simplified dictionary with just essential data
        """
        if not skeleton_model:
            return {}

        simplified = {
            "joints": [],
            "connections": [],
            "metadata": {
                "source_format": skeleton_model.source_format,
                "joint_count": len(skeleton_model.joints),
                "root_count": len(skeleton_model.root_joint_ids),
            }
        }

        # Export joints in a simplified format
        for joint_id, joint in skeleton_model.joints.items():
            simplified["joints"].append({
                "id": joint_id,
                "name": joint.name,
                "x": joint.position[0],
                "y": joint.position[1],
                "locked": joint.is_locked,
            })

        # Export connections (parent-child relationships)
        for parent_id, children in skeleton_model.hierarchy.items():
            for child_id in children:
                simplified["connections"].append({
                    "from": parent_id,
                    "to": child_id,
                })

        return simplified

    @staticmethod
    def validate_data(data: Dict[str, Any]) -> List[str]:
        """
        Validate skeleton data without creating a model.

        Args:
            data: Dictionary to validate

        Returns:
            List of validation error messages, empty if valid
        """
        try:
            StandardizedSkeletonModel.model_validate(data)
            return []
        except ValidationError as e:
            return [str(err) for err in e.errors()]
        except Exception as e:
            return [f"Unexpected validation error: {str(e)}"]