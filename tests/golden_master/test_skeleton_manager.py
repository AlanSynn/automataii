"""
Golden Master Tests for Skeleton Manager.

These tests capture the expected behavior of skeleton processing
and joint management to ensure refactoring doesn't change behavior.
"""

import pytest


class TestSkeletonManagerGoldenMaster:
    """Golden master tests for skeleton manager."""

    @pytest.fixture
    def skeleton_manager(self, qapp):
        """Create skeleton manager for testing."""
        from automataii.application.managers import SkeletonManager

        return SkeletonManager()

    @pytest.fixture
    def qapp(self):
        """Create QApplication for Qt-based tests."""
        import sys

        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        yield app

    @pytest.fixture
    def sample_ad_skeleton(self):
        """Sample Animated Drawings format skeleton."""
        return {
            "skeleton": [
                {"name": "root", "parent": None, "coordinates": [0, 0]},
                {"name": "hip", "parent": "root", "coordinates": [0, 50]},
                {"name": "left_hip", "parent": "hip", "coordinates": [-20, 50]},
                {"name": "left_knee", "parent": "left_hip", "coordinates": [-20, 100]},
                {"name": "left_ankle", "parent": "left_knee", "coordinates": [-20, 150]},
                {"name": "right_hip", "parent": "hip", "coordinates": [20, 50]},
                {"name": "right_knee", "parent": "right_hip", "coordinates": [20, 100]},
                {"name": "right_ankle", "parent": "right_knee", "coordinates": [20, 150]},
                {"name": "spine", "parent": "hip", "coordinates": [0, 30]},
                {"name": "neck", "parent": "spine", "coordinates": [0, 10]},
                {"name": "head", "parent": "neck", "coordinates": [0, -10]},
                {"name": "left_shoulder", "parent": "neck", "coordinates": [-30, 10]},
                {"name": "left_elbow", "parent": "left_shoulder", "coordinates": [-50, 30]},
                {"name": "left_wrist", "parent": "left_elbow", "coordinates": [-70, 50]},
                {"name": "right_shoulder", "parent": "neck", "coordinates": [30, 10]},
                {"name": "right_elbow", "parent": "right_shoulder", "coordinates": [50, 30]},
                {"name": "right_wrist", "parent": "right_elbow", "coordinates": [70, 50]},
            ]
        }

    def test_skeleton_loading_ad_format(self, golden_master, skeleton_manager, sample_ad_skeleton):
        """Capture skeleton loading from Animated Drawings format."""
        result = skeleton_manager.load_skeleton_from_dict(
            sample_ad_skeleton, source_format="animated_drawings"
        )

        assert result is True

        model = skeleton_manager.standardized_model
        assert model is not None

        # Capture key aspects of the loaded model
        snapshot_data = {
            "joint_count": len(model.joints),
            "root_joint_ids": sorted(model.root_joint_ids),
            "joint_names": sorted([j.name for j in model.joints.values()]),
            "hierarchy_keys": sorted(model.hierarchy.keys()),
            "source_format": model.source_format,
        }

        snapshot = golden_master("skeleton_ad_format")
        snapshot.assert_matches(
            snapshot_data,
            message="Skeleton loading from Animated Drawings format",
        )

    def test_skeleton_joint_positions(self, golden_master, skeleton_manager, sample_ad_skeleton):
        """Capture joint positions after loading."""
        skeleton_manager.load_skeleton_from_dict(
            sample_ad_skeleton, source_format="animated_drawings"
        )

        positions = skeleton_manager.joint_positions

        # Normalize positions for stable comparison
        normalized_positions = {k: (round(v[0], 2), round(v[1], 2)) for k, v in positions.items()}

        snapshot = golden_master("skeleton_joint_positions")
        snapshot.assert_matches(
            {"positions": normalized_positions},
            message="Joint positions after loading",
        )

    def test_skeleton_hierarchy(self, golden_master, skeleton_manager, sample_ad_skeleton):
        """Capture skeleton hierarchy structure."""
        skeleton_manager.load_skeleton_from_dict(
            sample_ad_skeleton, source_format="animated_drawings"
        )

        model = skeleton_manager.standardized_model
        assert model is not None

        # Build hierarchy representation
        hierarchy_data = {}
        for joint_id, children in model.hierarchy.items():
            joint = model.joints.get(joint_id)
            if joint:
                hierarchy_data[joint.name] = sorted(
                    [model.joints[c].name for c in children if c in model.joints]
                )

        snapshot = golden_master("skeleton_hierarchy")
        snapshot.assert_matches(
            hierarchy_data,
            message="Skeleton hierarchy structure",
        )

    def test_skeleton_limb_lengths(self, golden_master, skeleton_manager, sample_ad_skeleton):
        """Capture calculated limb lengths."""
        skeleton_manager.load_skeleton_from_dict(
            sample_ad_skeleton, source_format="animated_drawings"
        )

        model = skeleton_manager.standardized_model
        assert model is not None

        # Get limb lengths, rounded for stability
        limb_lengths = {}
        if model.limb_lengths:
            limb_lengths = {k: round(v, 2) for k, v in model.limb_lengths.items()}

        snapshot = golden_master("skeleton_limb_lengths")
        snapshot.assert_matches(
            {"limb_lengths": limb_lengths},
            message="Calculated limb lengths",
        )

    def test_skeleton_extend_lengths(self, golden_master, skeleton_manager, sample_ad_skeleton):
        """Capture skeleton after extending lengths."""
        skeleton_manager.load_skeleton_from_dict(
            sample_ad_skeleton, source_format="animated_drawings"
        )

        # Get positions before
        positions_before = dict(skeleton_manager.joint_positions)

        # Extend by 10%
        result = skeleton_manager.extend_skeleton_lengths(scale_factor=1.1)
        assert result is True

        # Get positions after
        positions_after = skeleton_manager.joint_positions

        # Calculate displacement for each joint
        displacements = {}
        for joint_id in positions_before:
            if joint_id in positions_after:
                before = positions_before[joint_id]
                after = positions_after[joint_id]
                dx = round(after[0] - before[0], 2)
                dy = round(after[1] - before[1], 2)
                displacements[joint_id] = (dx, dy)

        snapshot = golden_master("skeleton_extend_lengths")
        snapshot.assert_matches(
            {"displacements": displacements, "scale_factor": 1.1},
            message="Joint displacements after extending lengths",
        )

    def test_skeleton_bend_directions(self, golden_master, skeleton_manager, sample_ad_skeleton):
        """Capture bend directions for joints."""
        skeleton_manager.load_skeleton_from_dict(
            sample_ad_skeleton, source_format="animated_drawings"
        )

        bend_directions = skeleton_manager.get_all_joint_bend_directions()

        # Filter to only joints with non-default bend directions
        non_default_bends = {k: v for k, v in bend_directions.items() if v is not None and v != 0.0}

        snapshot = golden_master("skeleton_bend_directions")
        snapshot.assert_matches(
            {"bend_directions": non_default_bends},
            message="Joint bend directions",
        )

    def test_skeleton_serialization_roundtrip(
        self, golden_master, skeleton_manager, sample_ad_skeleton
    ):
        """Capture skeleton data after serialization roundtrip."""
        skeleton_manager.load_skeleton_from_dict(
            sample_ad_skeleton, source_format="animated_drawings"
        )

        # Get serialized data
        data = skeleton_manager.get_current_skeleton_data()
        assert data is not None

        # Create new manager and load serialized data
        from automataii.application.managers import SkeletonManager

        new_manager = SkeletonManager()
        result = new_manager.load_skeleton_from_dict(data, source_format="standard")
        assert result is True

        # Compare key aspects
        original_positions = skeleton_manager.joint_positions
        new_positions = new_manager.joint_positions

        # Verify positions match
        position_matches = {}
        for joint_id in original_positions:
            if joint_id in new_positions:
                orig = original_positions[joint_id]
                new = new_positions[joint_id]
                matches = round(orig[0], 2) == round(new[0], 2) and round(orig[1], 2) == round(
                    new[1], 2
                )
                position_matches[joint_id] = matches

        snapshot = golden_master("skeleton_roundtrip")
        snapshot.assert_matches(
            {
                "all_positions_match": all(position_matches.values()),
                "joint_count_original": len(original_positions),
                "joint_count_roundtrip": len(new_positions),
            },
            message="Skeleton serialization roundtrip",
        )
