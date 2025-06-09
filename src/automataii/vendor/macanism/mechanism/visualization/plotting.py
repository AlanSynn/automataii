"""Static plotting functionality for mechanisms."""

import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import numpy as np

from .scaling import ScalingCalculator
from ..analysis.bounds import BoundsCalculator


class MechanismPlotter:
    """Plotter for static mechanism visualization."""

    def __init__(self, mechanism):
        """
        Initialize the plotter.

        Parameters
        ----------
        mechanism : Mechanism
            The mechanism instance to plot.
        """
        self.mechanism = mechanism
        self.scaling_calculator = ScalingCalculator()
        self.bounds_calculator = BoundsCalculator()

    def plot(
        self,
        velocity=False,
        acceleration=False,
        scale=0.1,
        show_joints=True,
        grid=True,
        cushion=1,
    ):
        """
        Plot the mechanism in its current state.

        Parameters
        ----------
        velocity : bool, optional
            Plot velocity vectors if True.
        acceleration : bool, optional
            Plot acceleration vectors if True.
        scale : float, optional
            Scale factor for velocity/acceleration vectors relative to bounding box.
        show_joints : bool, optional
            Add joint labels to the plot.
        grid : bool, optional
            Add grid to the plot.
        cushion : float, optional
            Cushion around the plot boundaries.

        Returns
        -------
        tuple
            (figure, axes) matplotlib objects.
        """
        fig = plt.figure(figsize=(10, 8))
        ax = fig.add_subplot(111, projection="3d")

        # Plot vectors
        x_coords, y_coords, z_coords = self._plot_vectors(ax)

        # Plot velocity/acceleration arrows
        arrow_coords = self._plot_kinematic_arrows(
            ax, velocity, acceleration, scale
        )
        x_coords.extend(arrow_coords[0])
        y_coords.extend(arrow_coords[1])
        z_coords.extend(arrow_coords[2])

        # Plot joints
        if show_joints:
            joint_coords = self._plot_joints(ax)
            x_coords.extend(joint_coords[0])
            y_coords.extend(joint_coords[1])
            z_coords.extend(joint_coords[2])

        # Set plot bounds
        self._set_plot_bounds(ax, x_coords, y_coords, z_coords, cushion)

        # Configure plot
        ax.set_xlabel("X axis")
        ax.set_ylabel("Y axis")
        ax.set_zlabel("Z axis")

        if grid:
            ax.grid(True)

        return fig, ax

    def _plot_vectors(self, ax):
        """Plot mechanism vectors."""
        x_coords, y_coords, z_coords = [], [], []

        for v_idx, v in enumerate(self.mechanism.vectors):
            if v.show:
                # Check if joints have positions
                if (
                    v.joints[0].x_pos is None
                    or v.joints[1].x_pos is None
                    or v.joints[0].y_pos is None
                    or v.joints[1].y_pos is None
                    or v.joints[0].z_pos is None
                    or v.joints[1].z_pos is None
                ):
                    continue

                x_data = [v.joints[0].x_pos, v.joints[1].x_pos]
                y_data = [v.joints[0].y_pos, v.joints[1].y_pos]
                z_data = [v.joints[0].z_pos, v.joints[1].z_pos]
                
                ax.plot(x_data, y_data, z_data, **v.pos.kwargs)
                
                x_coords.extend(x_data)
                y_coords.extend(y_data)
                z_coords.extend(z_data)

        return x_coords, y_coords, z_coords

    def _plot_kinematic_arrows(self, ax, velocity, acceleration, scale):
        """Plot velocity and/or acceleration arrows."""
        arrow_x, arrow_y, arrow_z = [], [], []

        if velocity and self.mechanism.vel is not None:
            min_bx, max_bx, min_by, max_by, min_bz, max_bz = self.bounds_calculator.get_bounds(
                self.mechanism.joints, for_animation=False
            )
            sf = self.scaling_calculator.find_scale(
                self.mechanism.joints,
                min_bx, max_bx, min_by, max_by, min_bz, max_bz,
                scale_length=scale,
                kind="plot",
                velocity=True,
            )
            arrow_x, arrow_y, arrow_z = self._add_arrows(
                ax, sf, velocity=True, arrow_coords=(arrow_x, arrow_y, arrow_z)
            )

        if acceleration and self.mechanism.acc is not None:
            min_bx, max_bx, min_by, max_by, min_bz, max_bz = self.bounds_calculator.get_bounds(
                self.mechanism.joints, for_animation=False
            )
            sf = self.scaling_calculator.find_scale(
                self.mechanism.joints,
                min_bx, max_bx, min_by, max_by, min_bz, max_bz,
                scale_length=scale,
                kind="plot",
                acceleration=True,
            )
            arrow_x, arrow_y, arrow_z = self._add_arrows(
                ax, sf, acceleration=True, arrow_coords=(arrow_x, arrow_y, arrow_z)
            )

        return arrow_x, arrow_y, arrow_z

    def _add_arrows(self, ax, scale_factor, velocity=False, acceleration=False, 
                    arrow_coords=None):
        """Add velocity or acceleration arrows to the plot."""
        if arrow_coords is None:
            arrow_x, arrow_y, arrow_z = [], [], []
        else:
            arrow_x, arrow_y, arrow_z = arrow_coords

        for j in self.mechanism.joints:
            if j.x_pos is None:
                continue

            j._scale_kinematics_vector_for_plot(scale_factor, 
                                                velocity=velocity, 
                                                acceleration=acceleration)

            if velocity:
                vx, vy, vz = j._x_vel_scaled, j._y_vel_scaled, j._z_vel_scaled
                arrow_kwargs = j.vel_arrow_kwargs
                default_color = "blue"
            else:
                vx, vy, vz = j._x_acc_scaled, j._y_acc_scaled, j._z_acc_scaled
                arrow_kwargs = j.acc_arrow_kwargs
                default_color = "red"

            if not all(val is not None for val in [j.x_pos, j.y_pos, j.z_pos, vx, vy, vz]):
                continue

            ax.quiver(
                j.x_pos, j.y_pos, j.z_pos,
                vx, vy, vz,
                color=arrow_kwargs.get("edgecolor", default_color),
                length=1.0,
                arrow_length_ratio=0.3,
                normalize=False,
            )
            
            arrow_x.extend([j.x_pos, j.x_pos + vx])
            arrow_y.extend([j.y_pos, j.y_pos + vy])
            arrow_z.extend([j.z_pos, j.z_pos + vz])

        return arrow_x, arrow_y, arrow_z

    def _plot_joints(self, ax):
        """Plot joint markers."""
        x_coords, y_coords, z_coords = [], [], []

        for j in self.mechanism.joints:
            if j.x_pos is None:
                continue
            
            ax.plot(
                [j.x_pos], [j.y_pos], [j.z_pos],
                marker=".",
                color=j.kwargs.get("color", "black"),
                markersize=j.kwargs.get("markersize", 5),
            )
            
            x_coords.append(j.x_pos)
            y_coords.append(j.y_pos)
            z_coords.append(j.z_pos)

        return x_coords, y_coords, z_coords

    def _set_plot_bounds(self, ax, x_coords, y_coords, z_coords, cushion):
        """Set the plot boundaries."""
        # Ensure non-empty coordinates
        if not x_coords:
            x_coords = [0]
            y_coords = [0]
            z_coords = [0]

        min_x, max_x = min(x_coords) - cushion, max(x_coords) + cushion
        min_y, max_y = min(y_coords) - cushion, max(y_coords) + cushion
        min_z, max_z = min(z_coords) - cushion, max(z_coords) + cushion

        # Ensure origin is included
        min_x = min(min_x, -cushion if max_x > cushion else -abs(max_x) / 2 if max_x != 0 else -0.1)
        max_x = max(max_x, cushion if min_x < -cushion else abs(min_x) / 2 if min_x != 0 else 0.1)
        min_y = min(min_y, -cushion if max_y > cushion else -abs(max_y) / 2 if max_y != 0 else -0.1)
        max_y = max(max_y, cushion if min_y < -cushion else abs(min_y) / 2 if min_y != 0 else 0.1)
        min_z = min(min_z, -cushion if max_z > cushion else -abs(max_z) / 2 if max_z != 0 else -0.1)
        max_z = max(max_z, cushion if min_z < -cushion else abs(min_z) / 2 if min_z != 0 else 0.1)

        ax.set_xlim(min_x, max_x)
        ax.set_ylim(min_y, max_y)
        ax.set_zlim(min_z, max_z)

        # Set aspect ratio
        x_range = ax.get_xlim()[1] - ax.get_xlim()[0]
        y_range = ax.get_ylim()[1] - ax.get_ylim()[0]
        z_range = ax.get_zlim()[1] - ax.get_zlim()[0]
        ax.set_box_aspect([x_range, y_range, z_range])

    def test_distances(self):
        """Check and print the distances between joints."""
        print("Distances:")
        for v in self.mechanism.vectors:
            j1, j2 = v.joints
            distance = np.sqrt(
                (j1.x_pos - j2.x_pos) ** 2 + 
                (j1.y_pos - j2.y_pos) ** 2 +
                (j1.z_pos - j2.z_pos) ** 2
            )
            print(f"- {j1} to {j2}: {distance}")