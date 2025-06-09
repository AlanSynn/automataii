"""
Hierarchy management module for skeleton parent-child relationships.
"""

from typing import Dict, List, Optional, Set

from .models import StandardizedJointModel, StandardizedSkeletonModel


class HierarchyManager:
    """Manages the hierarchical structure of a skeleton."""

    def __init__(self, skeleton_model: Optional[StandardizedSkeletonModel] = None):
        self._skeleton_model = skeleton_model

    @property
    def skeleton_model(self) -> Optional[StandardizedSkeletonModel]:
        """Get the current skeleton model."""
        return self._skeleton_model

    @skeleton_model.setter
    def skeleton_model(self, model: Optional[StandardizedSkeletonModel]) -> None:
        """Set the skeleton model."""
        self._skeleton_model = model

    @property
    def joint_hierarchy(self) -> Dict[str, List[str]]:
        """Returns the parent_id -> [child_ids] hierarchy from the standardized model."""
        if not self._skeleton_model:
            return {}
        return self._skeleton_model.hierarchy

    @property
    def root_joints(self) -> List[str]:
        """Returns a list of root joint IDs from the standardized model."""
        if not self._skeleton_model:
            return []
        return self._skeleton_model.root_joint_ids

    def rebuild_hierarchy(self) -> None:
        """Rebuild the hierarchy and root joints from joint parent relationships."""
        if not self._skeleton_model:
            return

        # Clear existing hierarchy
        self._skeleton_model.hierarchy.clear()
        self._skeleton_model.root_joint_ids.clear()

        # Rebuild from joint parent_id relationships
        for joint_id, joint in self._skeleton_model.joints.items():
            if joint.parent_id and joint.parent_id in self._skeleton_model.joints:
                self._skeleton_model.hierarchy.setdefault(joint.parent_id, []).append(
                    joint_id
                )
            else:
                # No parent or parent doesn't exist - this is a root
                self._skeleton_model.root_joint_ids.append(joint_id)

    def get_ancestors(self, joint_id: str) -> List[str]:
        """Get all ancestor joint IDs for a given joint (from parent to root)."""
        if not self._skeleton_model or joint_id not in self._skeleton_model.joints:
            return []

        ancestors = []
        current_id = joint_id
        visited = set()  # Prevent infinite loops

        while current_id and current_id not in visited:
            visited.add(current_id)
            joint = self._skeleton_model.joints.get(current_id)
            if joint and joint.parent_id:
                ancestors.append(joint.parent_id)
                current_id = joint.parent_id
            else:
                break

        return ancestors

    def get_descendants(self, joint_id: str) -> List[str]:
        """Get all descendant joint IDs for a given joint (all children recursively)."""
        if not self._skeleton_model:
            return []

        descendants = []
        to_visit = [joint_id]
        visited = set()

        while to_visit:
            current_id = to_visit.pop(0)
            if current_id in visited:
                continue
            visited.add(current_id)

            # Get children of current joint
            children = self._skeleton_model.hierarchy.get(current_id, [])
            for child_id in children:
                if child_id not in visited:
                    descendants.append(child_id)
                    to_visit.append(child_id)

        return descendants

    def get_siblings(self, joint_id: str) -> List[str]:
        """Get all sibling joint IDs (joints with the same parent)."""
        if not self._skeleton_model or joint_id not in self._skeleton_model.joints:
            return []

        joint = self._skeleton_model.joints[joint_id]
        if not joint.parent_id:
            # Root joints are siblings if there are multiple roots
            return [
                root_id
                for root_id in self._skeleton_model.root_joint_ids
                if root_id != joint_id
            ]

        # Get all children of the parent except this joint
        siblings = []
        parent_children = self._skeleton_model.hierarchy.get(joint.parent_id, [])
        for child_id in parent_children:
            if child_id != joint_id:
                siblings.append(child_id)

        return siblings

    def get_subtree(self, joint_id: str) -> Dict[str, List[str]]:
        """Get the entire subtree hierarchy starting from a joint."""
        if not self._skeleton_model:
            return {}

        subtree = {}
        to_visit = [joint_id]

        while to_visit:
            current_id = to_visit.pop(0)
            if current_id in self._skeleton_model.hierarchy:
                children = self._skeleton_model.hierarchy[current_id]
                subtree[current_id] = children.copy()
                to_visit.extend(children)

        return subtree

    def is_ancestor_of(self, ancestor_id: str, descendant_id: str) -> bool:
        """Check if one joint is an ancestor of another."""
        ancestors = self.get_ancestors(descendant_id)
        return ancestor_id in ancestors

    def is_descendant_of(self, descendant_id: str, ancestor_id: str) -> bool:
        """Check if one joint is a descendant of another."""
        descendants = self.get_descendants(ancestor_id)
        return descendant_id in descendants

    def get_chain_to_root(self, joint_id: str) -> List[str]:
        """Get the chain of joint IDs from this joint to the root (inclusive)."""
        if not self._skeleton_model or joint_id not in self._skeleton_model.joints:
            return []

        chain = [joint_id]
        chain.extend(self.get_ancestors(joint_id))
        return chain

    def get_common_ancestor(self, joint_id1: str, joint_id2: str) -> Optional[str]:
        """Find the common ancestor of two joints."""
        if not self._skeleton_model:
            return None

        ancestors1 = set(self.get_chain_to_root(joint_id1))
        ancestors2 = self.get_chain_to_root(joint_id2)

        # Find first common ancestor
        for ancestor in ancestors2:
            if ancestor in ancestors1:
                return ancestor

        return None

    def validate_hierarchy(self) -> List[str]:
        """
        Validate the hierarchy for consistency issues.
        
        Returns:
            List of error messages, empty if hierarchy is valid
        """
        errors = []
        
        if not self._skeleton_model:
            return ["No skeleton model loaded"]

        # Check for orphaned joints (not in hierarchy and not root)
        all_joint_ids = set(self._skeleton_model.joints.keys())
        joints_in_hierarchy = set()
        
        for parent_id, children in self._skeleton_model.hierarchy.items():
            joints_in_hierarchy.add(parent_id)
            joints_in_hierarchy.update(children)
            
        joints_in_hierarchy.update(self._skeleton_model.root_joint_ids)
        
        orphaned = all_joint_ids - joints_in_hierarchy
        if orphaned:
            errors.append(f"Orphaned joints found: {orphaned}")

        # Check for cycles
        for joint_id in all_joint_ids:
            visited = set()
            current = joint_id
            while current:
                if current in visited:
                    errors.append(f"Cycle detected involving joint: {joint_id}")
                    break
                visited.add(current)
                joint = self._skeleton_model.joints.get(current)
                current = joint.parent_id if joint else None

        # Check parent references
        for joint_id, joint in self._skeleton_model.joints.items():
            if joint.parent_id and joint.parent_id not in self._skeleton_model.joints:
                errors.append(
                    f"Joint {joint_id} references non-existent parent: {joint.parent_id}"
                )

        return errors