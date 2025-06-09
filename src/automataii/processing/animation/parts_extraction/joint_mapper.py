"""Joint mapping utilities for different skeleton formats."""

from typing import Dict, Tuple, List, Any, Optional
from .models import JointInfo


class JointMapper:
    """Handles conversion between different skeleton data formats."""
    
    @staticmethod
    def create_joint_map(skeleton_data: Any) -> Dict[str, Tuple[int, int]]:
        """Create joint map from various skeleton data formats.
        
        Args:
            skeleton_data: Skeleton data in various formats
            
        Returns:
            Dictionary mapping joint names to (x, y) positions
        """
        joint_map = {}
        
        if isinstance(skeleton_data, dict):
            joint_map = JointMapper._process_dict_format(skeleton_data)
        elif isinstance(skeleton_data, list):
            joint_map = JointMapper._process_list_format(skeleton_data)
            
        return joint_map
    
    @staticmethod
    def _process_dict_format(skeleton_data: Dict[str, Any]) -> Dict[str, Tuple[int, int]]:
        """Process dictionary format skeleton data."""
        joint_map = {}
        
        # New format with 'joints' key
        if "joints" in skeleton_data:
            joints = skeleton_data["joints"]
            if isinstance(joints, dict):
                # joints is a dict of joint_id -> joint_data
                for joint_id, joint_data in joints.items():
                    if isinstance(joint_data, dict) and "position" in joint_data:
                        pos = joint_data["position"]
                        if len(pos) >= 2:
                            # Extract joint name from id
                            joint_name = "_".join(joint_id.split("_")[:-1])
                            if not joint_name:
                                joint_name = joint_id.split("_")[0]
                            joint_map[joint_name] = (int(pos[0]), int(pos[1]))
            elif isinstance(joints, list):
                # joints is a list
                for joint in joints:
                    if "name" in joint and "position" in joint:
                        joint_map[joint["name"]] = tuple(joint["position"])
                        
        # Also check 'joint_map' key
        elif "joint_map" in skeleton_data:
            joint_map_data = skeleton_data["joint_map"]
            if isinstance(joint_map_data, dict):
                for joint_name, pos in joint_map_data.items():
                    if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                        joint_map[joint_name] = (int(pos[0]), int(pos[1]))
                        
        return joint_map
    
    @staticmethod
    def _process_list_format(skeleton_data: List[Any]) -> Dict[str, Tuple[int, int]]:
        """Process list format skeleton data."""
        joint_map = {}
        
        for joint in skeleton_data:
            if "name" in joint and "loc" in joint:
                joint_map[joint["name"]] = tuple(joint["loc"])
                
        return joint_map
    
    @staticmethod
    def find_joint_by_prefix(joint_map: Dict[str, Tuple[int, int]], 
                           prefix: str) -> Optional[str]:
        """Find joint name in map by prefix.
        
        Args:
            joint_map: Dictionary of joint names to positions
            prefix: Prefix to search for
            
        Returns:
            Full joint name if found, None otherwise
        """
        # Try exact match first
        if prefix in joint_map:
            return prefix
            
        # Try to find by prefix
        for joint_name in joint_map:
            if joint_name.startswith(prefix):
                return joint_name
                
        return None
    
    @staticmethod
    def map_joints_for_part(part_joints: List[str], 
                           joint_map: Dict[str, Tuple[int, int]]) -> List[str]:
        """Map part joints to actual joint names in the joint map.
        
        Args:
            part_joints: List of joint names from part definition
            joint_map: Dictionary of actual joint names to positions
            
        Returns:
            List of mapped joint names that exist in joint_map
        """
        mapped_joints = []
        
        for joint in part_joints:
            mapped_joint = JointMapper.find_joint_by_prefix(joint_map, joint)
            if mapped_joint:
                mapped_joints.append(mapped_joint)
                
        return mapped_joints
    
    @staticmethod
    def extract_joints_from_config(char_cfg: Dict[str, Any]) -> List[JointInfo]:
        """Extract joint information from character configuration.
        
        Args:
            char_cfg: Character configuration data
            
        Returns:
            List of JointInfo objects
        """
        joints = []
        
        # Get skeleton data with fallbacks
        skeleton_data = char_cfg.get("skeleton", [])
        if not skeleton_data and "joints" in char_cfg:
            skeleton_data = char_cfg
            
        if isinstance(skeleton_data, dict) and "joints" in skeleton_data:
            joints_data = skeleton_data["joints"]
            if isinstance(joints_data, dict):
                for joint_id, joint_info in joints_data.items():
                    if isinstance(joint_info, dict):
                        # Extract joint name from id
                        joint_name = "_".join(joint_id.split("_")[:-1])
                        if not joint_name:
                            joint_name = joint_id.split("_")[0]
                            
                        pos = joint_info.get("position", [0.0, 0.0])
                        if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                            pos = (float(pos[0]), float(pos[1]))
                        else:
                            pos = (0.0, 0.0)
                            
                        parent = joint_info.get("parent")
                        
                        joints.append(JointInfo(
                            name=joint_name,
                            position=pos,
                            parent=parent
                        ))
        elif isinstance(skeleton_data, list):
            # Old format
            raw_joint_map = {
                j_data.get("name"): j_data
                for j_data in skeleton_data
                if isinstance(j_data, dict)
            }
            
            for joint_data in skeleton_data:
                if not isinstance(joint_data, dict):
                    continue
                    
                joint_name = joint_data.get("name")
                if not joint_name:
                    continue
                    
                loc = joint_data.get("loc", [0.0, 0.0])
                if not (isinstance(loc, list) and len(loc) == 2):
                    loc = [0.0, 0.0]
                    
                parent_name = joint_data.get("parent")
                
                joints.append(JointInfo(
                    name=joint_name,
                    position=(float(loc[0]), float(loc[1])),
                    parent=parent_name if parent_name in raw_joint_map else None
                ))
                
        return joints