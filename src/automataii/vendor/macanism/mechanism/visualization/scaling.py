"""Scaling utilities for mechanism visualization."""

import numpy as np


class ScalingCalculator:
    """Calculator for scaling kinematic vectors in visualizations."""

    @staticmethod
    def find_scale(
        joints,
        x_min,
        x_max,
        y_min,
        y_max,
        z_min=0,
        z_max=0,
        scale_length=0.1,
        kind="plot",
        velocity=False,
        acceleration=False,
    ):
        """
        Calculate scale factor for velocity/acceleration vectors.

        This method finds the maximum magnitude of velocity/acceleration for all 
        joints, then returns a scale value for scaling the vectors when plotting.

        Parameters
        ----------
        joints : list
            List of Joint objects.
        x_min, x_max, y_min, y_max, z_min, z_max : float
            Bounding box coordinates.
        scale_length : float, optional
            The fraction for which the velocity/acceleration vector is to the
            diagonal length of the bounding box.
        kind : str, optional
            Either "plot" for single frame or "animation" for multiple frames.
        velocity : bool, optional
            Calculate scale for velocity vectors.
        acceleration : bool, optional
            Calculate scale for acceleration vectors.

        Returns
        -------
        float
            Scale factor for vector plotting.
        """
        # Use 3D diagonal for scaling reference
        max_length = np.sqrt(
            (x_max - x_min) ** 2 + (y_max - y_min) ** 2 + (z_max - z_min) ** 2
        )
        if max_length == 0:
            max_length = 1.0  # Avoid division by zero

        max_mag = 1.0  # Default magnitude

        if kind == "plot":
            if velocity:
                joint_mags = [
                    np.sqrt(j.x_vel**2 + j.y_vel**2 + j.z_vel**2)
                    for j in joints
                    if j.x_vel is not None
                ]
                if joint_mags:
                    max_mag = max(joint_mags)
            elif acceleration:
                joint_mags = [
                    np.sqrt(j.x_acc**2 + j.y_acc**2 + j.z_acc**2)
                    for j in joints
                    if j.x_acc is not None
                ]
                if joint_mags:
                    max_mag = max(joint_mags)
            else:
                raise ValueError("Neither velocity or acceleration specified.")
        elif kind == "animation":
            if velocity:
                if any(j.vel_mags is not None for j in joints):
                    max_mag = np.amax(
                        [j.vel_mags for j in joints if j.vel_mags is not None]
                    )
            elif acceleration:
                if any(j.acc_mags is not None for j in joints):
                    max_mag = np.amax(
                        [j.acc_mags for j in joints if j.acc_mags is not None]
                    )
            else:
                raise ValueError("Neither velocity or acceleration specified.")

        if max_mag == 0:
            return 1.0  # No scaling needed if max magnitude is zero
        else:
            return scale_length * max_length / max_mag

    @staticmethod
    def exclude_joints(joints):
        """
        Exclude joint velocities and accelerations from animations.

        Parameters
        ----------
        joints : list
            A list of Joint objects to exclude from the animations.
        """
        for joint in joints:
            joint.vel_arrow_kwargs = dict(lw=0, mutation_scale=0)
            joint.acc_arrow_kwargs = dict(lw=0, mutation_scale=0)