"""Animation functionality for mechanisms."""

import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import numpy as np

from mechanism._player import Player
from .scaling import ScalingCalculator
from ..analysis.bounds import BoundsCalculator


class MechanismAnimator:
    """Animator for mechanism motion visualization."""

    def __init__(self, mechanism):
        """
        Initialize the animator.

        Parameters
        ----------
        mechanism : Mechanism
            The mechanism instance to animate.
        """
        self.mechanism = mechanism
        self.scaling_calculator = ScalingCalculator()
        self.bounds_calculator = BoundsCalculator()

    def get_animation(
        self,
        velocity=False,
        acceleration=False,
        scale=0.1,
        stamp=None,
        stamp_loc=(0.05, 0.9),
        grid=True,
        cushion=1,
        show_joints=False,
        interval=50,
        key_bindings=True,
    ):
        """
        Create an animation of the mechanism motion.

        Parameters
        ----------
        velocity : bool, optional
            Plot velocity vectors if True.
        acceleration : bool, optional
            Plot acceleration vectors if True.
        scale : float, optional
            Scale factor for velocity/acceleration vectors.
        stamp : str, optional
            Text stamp prefix for displaying input values.
        stamp_loc : tuple, optional
            Position of the stamp in axes transform units.
        grid : bool, optional
            Add grid to the plot.
        cushion : float, optional
            Cushion around the plot boundaries.
        show_joints : bool, optional
            Show joint markers if True.
        interval : int, optional
            Delay in milliseconds between frames.
        key_bindings : bool, optional
            Enable keyboard controls for animation.

        Returns
        -------
        tuple
            (player, figure, axes) objects.
        """
        assert self.mechanism.is_array, (
            "Input must be an array to get animation. "
            "Call calculate() and plot() instead."
        )

        fig = plt.figure(figsize=(10, 8))
        ax = fig.add_subplot(111, projection="3d")

        # Prepare scaling for kinematic arrows
        if velocity or acceleration:
            self._prepare_arrow_scaling(velocity, acceleration, scale)

        # Set up plot bounds
        min_x, max_x, min_y, max_y, min_z, max_z = self.bounds_calculator.get_bounds(
            self.mechanism.joints, for_animation=True
        )
        ax.set_xlim(min_x - cushion, max_x + cushion)
        ax.set_ylim(min_y - cushion, max_y + cushion)
        ax.set_zlim(min_z - cushion, max_z + cushion)

        # Configure axes
        ax.set_xlabel("X axis")
        ax.set_ylabel("Y axis")
        ax.set_zlabel("Z axis")

        # Set aspect ratio
        x_range = ax.get_xlim()[1] - ax.get_xlim()[0]
        y_range = ax.get_ylim()[1] - ax.get_ylim()[0]
        z_range = ax.get_zlim()[1] - ax.get_zlim()[0]
        ax.set_box_aspect([
            x_range if x_range > 0 else 1,
            y_range if y_range > 0 else 1,
            z_range if z_range > 0 else 1,
        ])

        if grid:
            ax.grid(True)

        # Create plot elements
        lines = self._create_vector_lines(ax)
        joint_plots = self._create_joint_plots(ax, show_joints)
        text_artists = self._create_text_artists(ax, stamp, stamp_loc)

        # Store dynamic artists (arrows that need to be redrawn each frame)
        dynamic_artists = []

        # Define animation functions
        def init():
            return lines + joint_plots + text_artists + dynamic_artists

        def animate(i):
            # Clear dynamic artists
            for artist_collection in dynamic_artists:
                for artist in artist_collection:
                    artist.remove()
            dynamic_artists.clear()

            # Update vector lines
            self._update_vector_lines(lines, i)

            # Update joint positions
            if show_joints:
                self._update_joint_plots(joint_plots, i)

            # Add velocity arrows
            if velocity:
                vel_arrows = self._add_velocity_arrows(ax, i)
                dynamic_artists.append(vel_arrows)

            # Add acceleration arrows
            if acceleration:
                acc_arrows = self._add_acceleration_arrows(ax, i)
                dynamic_artists.append(acc_arrows)

            # Update stamp text
            if stamp is not None:
                self._update_stamp(text_artists[0], stamp, i)

            return lines + joint_plots + text_artists + sum(dynamic_artists, [])

        # Create player
        num_frames = self.mechanism.pos.shape[0]
        player = Player(
            fig=fig,
            func=animate,
            frames=num_frames,
            interval=interval,
            key_bindings=key_bindings,
            init_func=init,
        )

        return player, fig, ax

    def _prepare_arrow_scaling(self, velocity, acceleration, scale):
        """Prepare scaling factors for kinematic arrows."""
        temp_min_x, temp_max_x, temp_min_y, temp_max_y, _, _ = (
            self.bounds_calculator.get_bounds(
                self.mechanism.joints, for_animation=True
            )
        )
        
        if velocity:
            sf_vel = self.scaling_calculator.find_scale(
                self.mechanism.joints,
                temp_min_x, temp_max_x, temp_min_y, temp_max_y,
                scale_length=scale,
                kind="animation",
                velocity=True,
            )
            for j in self.mechanism.joints:
                j._scale_kinematics_vectors_for_plot_arrays(sf_vel, velocity=True)
                j._get_kinematics_arrow_heads_for_plot_arrays(velocity=True)

        if acceleration:
            sf_acc = self.scaling_calculator.find_scale(
                self.mechanism.joints,
                temp_min_x, temp_max_x, temp_min_y, temp_max_y,
                scale_length=scale,
                kind="animation",
                acceleration=True,
            )
            for j in self.mechanism.joints:
                j._scale_kinematics_vectors_for_plot_arrays(sf_acc, acceleration=True)
                j._get_kinematics_arrow_heads_for_plot_arrays(acceleration=True)

    def _create_vector_lines(self, ax):
        """Create line objects for mechanism vectors."""
        return [
            ax.plot([], [], [], **v.pos.kwargs)[0]
            for v in self.mechanism.vectors
            if v.pos.show
        ]

    def _create_joint_plots(self, ax, show_joints):
        """Create plot objects for joints."""
        joint_plots = []
        if show_joints:
            for j in self.mechanism.joints:
                color = j.kwargs.get("color", "black")
                msize = j.kwargs.get("markersize", 5)
                if j.x_positions is not None and len(j.x_positions) > 0:
                    plot = ax.plot(
                        [j.x_positions[0]],
                        [j.y_positions[0]],
                        [j.z_positions[0]],
                        marker=".",
                        color=color,
                        markersize=msize,
                    )[0]
                else:
                    plot = ax.plot(
                        [], [], [],
                        marker=".",
                        color=color,
                        markersize=msize,
                    )[0]
                joint_plots.append(plot)
        return joint_plots

    def _create_text_artists(self, ax, stamp, stamp_loc):
        """Create text artists for stamps."""
        text_artists = []
        if stamp is not None:
            time_text = ax.text(
                stamp_loc[0], stamp_loc[1], 0.0,
                "",
                transform=ax.transAxes,
                fontsize="large",
            )
            text_artists.append(time_text)
        return text_artists

    def _update_vector_lines(self, lines, i):
        """Update vector line positions for frame i."""
        for line, v in zip(lines, [vec for vec in self.mechanism.vectors if vec.pos.show]):
            if v.joints[0].x_positions is None:
                continue
            line.set_data_3d(
                [v.joints[0].x_positions[i], v.joints[1].x_positions[i]],
                [v.joints[0].y_positions[i], v.joints[1].y_positions[i]],
                [v.joints[0].z_positions[i], v.joints[1].z_positions[i]],
            )

    def _update_joint_plots(self, joint_plots, i):
        """Update joint positions for frame i."""
        for jp, joint_data in zip(joint_plots, self.mechanism.joints):
            if joint_data.x_positions is None:
                continue
            jp.set_data_3d(
                [joint_data.x_positions[i]],
                [joint_data.y_positions[i]],
                [joint_data.z_positions[i]],
            )

    def _add_velocity_arrows(self, ax, i):
        """Add velocity arrows for frame i."""
        current_vel_arrows = []
        for j in self.mechanism.joints:
            if (
                j.x_positions is None
                or not hasattr(j, "_vel_heads_3d")
                or j._vel_heads_3d is None
            ):
                continue
            
            start_point = np.array([j.x_positions[i], j.y_positions[i], j.z_positions[i]])
            end_point = j._vel_heads_3d[i]
            
            if start_point is None or end_point is None:
                continue
            
            vec_components = end_point - start_point
            if np.linalg.norm(vec_components) > 1e-9:
                q = ax.quiver(
                    start_point[0], start_point[1], start_point[2],
                    vec_components[0], vec_components[1], vec_components[2],
                    color=j.vel_arrow_kwargs.get("edgecolor", "blue"),
                    length=1.0,
                    arrow_length_ratio=0.3,
                    normalize=False,
                )
                current_vel_arrows.append(q)
        
        return current_vel_arrows

    def _add_acceleration_arrows(self, ax, i):
        """Add acceleration arrows for frame i."""
        current_acc_arrows = []
        for j in self.mechanism.joints:
            if (
                j.x_positions is None
                or not hasattr(j, "_acc_heads_3d")
                or j._acc_heads_3d is None
            ):
                continue
            
            start_point = np.array([j.x_positions[i], j.y_positions[i], j.z_positions[i]])
            end_point = j._acc_heads_3d[i]
            
            if start_point is None or end_point is None:
                continue
            
            vec_components = end_point - start_point
            if np.linalg.norm(vec_components) > 1e-9:
                q = ax.quiver(
                    start_point[0], start_point[1], start_point[2],
                    vec_components[0], vec_components[1], vec_components[2],
                    color=j.acc_arrow_kwargs.get("edgecolor", "red"),
                    length=1.0,
                    arrow_length_ratio=0.3,
                    normalize=False,
                )
                current_acc_arrows.append(q)
        
        return current_acc_arrows

    def _update_stamp(self, text_artist, stamp, i):
        """Update stamp text for frame i."""
        if self.mechanism.pos.ndim > 1:
            current_stamp_val = self.mechanism.pos[i, 0]  # First column if multi-DOF
        else:
            current_stamp_val = self.mechanism.pos[i]
        text_artist.set_text(f"{stamp}{current_stamp_val:.3f}")