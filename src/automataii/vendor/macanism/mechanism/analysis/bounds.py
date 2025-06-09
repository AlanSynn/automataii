"""Bounds calculation utilities for mechanism visualization."""

import numpy as np


class BoundsCalculator:
    """Calculator for mechanism bounds used in plotting and animation."""

    @staticmethod
    def get_bounds(joints, for_animation=False):
        """
        Calculate the bounding box of the mechanism.

        Parameters
        ----------
        joints : list
            List of Joint objects.
        for_animation : bool, optional
            If True, calculate bounds for all time steps. If False, calculate 
            bounds for current position only.

        Returns
        -------
        tuple
            (min_x, max_x, min_y, max_y, min_z, max_z)
        """
        x_coords, y_coords, z_coords = [], [], []
        
        if for_animation:
            for j in joints:
                if j.x_positions is not None:
                    x_coords.extend(j.x_positions)
                if j.y_positions is not None:
                    y_coords.extend(j.y_positions)
                if j.z_positions is not None:
                    z_coords.extend(j.z_positions)
            
            # Also consider arrow head positions for full animation bounds
            for j in joints:
                if hasattr(j, "_vel_heads_3d") and j._vel_heads_3d is not None:
                    x_coords.extend(j._vel_heads_3d[:, 0])
                    y_coords.extend(j._vel_heads_3d[:, 1])
                    z_coords.extend(j._vel_heads_3d[:, 2])
                if hasattr(j, "_acc_heads_3d") and j._acc_heads_3d is not None:
                    x_coords.extend(j._acc_heads_3d[:, 0])
                    y_coords.extend(j._acc_heads_3d[:, 1])
                    z_coords.extend(j._acc_heads_3d[:, 2])
        else:
            for j in joints:
                if j.x_pos is not None:
                    x_coords.append(j.x_pos)
                if j.y_pos is not None:
                    y_coords.append(j.y_pos)
                if j.z_pos is not None:
                    z_coords.append(j.z_pos)

        # Ensure non-empty lists
        if not x_coords:
            x_coords = [0]
        if not y_coords:
            y_coords = [0]
        if not z_coords:
            z_coords = [0]

        min_x, max_x = min(x_coords), max(x_coords)
        min_y, max_y = min(y_coords), max(y_coords)
        min_z, max_z = min(z_coords), max(z_coords)

        # Ensure origin is included
        min_x = min(min_x, 0)
        max_x = max(max_x, 0)
        min_y = min(min_y, 0)
        max_y = max(max_y, 0)
        min_z = min(min_z, 0)
        max_z = max(max_z, 0)

        return min_x, max_x, min_y, max_y, min_z, max_z