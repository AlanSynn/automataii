"""Joint class for mechanism analysis."""

import json
import numpy as np
from matplotlib.patches import FancyArrowPatch

from mechanism.vectors import Vector, APPEARANCE


class Joint:
    """Represents a joint in a mechanism with position, velocity, and acceleration tracking."""
    
    follow_all = False

    def __init__(
        self,
        name="",
        follow=None,
        style=None,
        exclude=None,
        vel_arrow_kwargs=None,
        acc_arrow_kwargs=None,
        **kwargs,
    ):
        """
        Initialize a Joint object.

        Parameters
        ----------
        name : str
            The name of the joint. Typically, a capital letter.
        follow : bool, optional
            If true, the path of the joint will be drawn in the animation.
        style : str, optional
            A named style located in the appearance json and under the 'joint_path' option.
        exclude : bool, optional
            If true, the velocity and acceleration arrows will not be displayed in plots.
        vel_arrow_kwargs : dict, optional
            kwargs to be passed into the FancyArrowPatch that makes up the velocity arrows.
        acc_arrow_kwargs : dict, optional
            kwargs to be passed into the FancyArrowPatch that makes up the acceleration arrows.
        **kwargs
            Extra arguments that get past to plt.plot(). Useful only if follow is set to true.

        Attributes
        ----------
        x_pos, y_pos, z_pos : float
            The global x, y, and z position of the joint
        x_vel, y_vel, z_vel : float
            The global x, y, and z velocity components of the joint.
        x_acc, y_acc, z_acc : float
            The global x, y, and z acceleration components of the joint.
        x_positions, y_positions, z_positions : ndarray
            Arrays of the x, y, and z positions.
        x_velocities, y_velocities, z_velocities : ndarray
            Arrays of the x, y, and z velocities.
        x_accelerations, y_accelerations, z_accelerations : ndarray
            Arrays of the x, y, and z accelerations.
        vel_mags, vel_thetas, vel_phis : ndarray
            Arrays of velocity magnitudes, xy-plane angles (theta), and z-axis angles (phi).
        acc_mags, acc_thetas, acc_phis : ndarray
            Arrays of acceleration magnitudes, xy-plane angles (theta), and z-axis angles (phi).
        """
        self.name = name
        self.x_pos, self.y_pos, self.z_pos = None, None, None
        self.x_vel, self.y_vel, self.z_vel = None, None, None
        self.x_acc, self.y_acc, self.z_acc = None, None, None

        self.x_positions, self.y_positions, self.z_positions = None, None, None
        self.x_velocities, self.y_velocities, self.z_velocities = None, None, None
        self.x_accelerations, self.y_accelerations, self.z_accelerations = (
            None,
            None,
            None,
        )

        self.vel_mags, self.vel_thetas, self.vel_phis = None, None, None
        self.acc_mags, self.acc_thetas, self.acc_phis = None, None, None

        # These _scaled attributes are for 3D plotting
        self._x_vel_scaled, self._y_vel_scaled, self._z_vel_scaled = (
            None,
            None,
            None,
        )
        self._x_acc_scaled, self._y_acc_scaled, self._z_acc_scaled = (
            None,
            None,
            None,
        )
        self._x_vel_scales, self._y_vel_scales, self._z_vel_scales = (
            None,
            None,
            None,
        )
        self._x_acc_scales, self._y_acc_scales, self._z_acc_scales = (
            None,
            None,
            None,
        )
        self._vel_heads_3d = None  # N x 3 array of 3D head coordinates
        self._acc_heads_3d = None  # N x 3 array of 3D head coordinates

        if follow is None:
            self.follow = self.follow_all
        else:
            self.follow = follow

        with open(APPEARANCE, "r") as f:
            appearance = json.load(f)

        if style:
            self.kwargs = appearance["joint_path"][style]
        elif kwargs:
            self.kwargs = kwargs
        else:
            self.kwargs = appearance["joint_path"]["default"]

        if vel_arrow_kwargs:
            self.vel_arrow_kwargs = vel_arrow_kwargs
        elif exclude:
            self.vel_arrow_kwargs = dict(lw=0, mutation_scale=0)
        else:
            self.vel_arrow_kwargs = appearance["vel_arrow"]

        if acc_arrow_kwargs:
            self.acc_arrow_kwargs = acc_arrow_kwargs
        elif exclude:
            self.acc_arrow_kwargs = dict(lw=0, mutation_scale=0)
        else:
            self.acc_arrow_kwargs = appearance["acc_arrow"]

    def _position_is_fixed(self):
        """Check if the position is globally defined."""
        return (
            False
            if self.x_pos is None or self.y_pos is None or self.z_pos is None
            else True
        )

    def _velocity_is_fixed(self):
        """Check if the velocity is globally defined."""
        return (
            False
            if self.x_vel is None or self.y_vel is None or self.z_vel is None
            else True
        )

    def _acceleration_is_fixed(self):
        """Check if the acceleration is globally defined."""
        return (
            False
            if self.x_acc is None or self.y_acc is None or self.z_acc is None
            else True
        )

    def _fix_position(self, x_pos, y_pos, z_pos):
        """Set the position coordinates."""
        self.x_pos, self.y_pos, self.z_pos = x_pos, y_pos, z_pos

    def _fix_velocity(self, x_vel, y_vel, z_vel):
        """Set the velocity components."""
        self.x_vel, self.y_vel, self.z_vel = x_vel, y_vel, z_vel
        if abs(self.x_vel) < 1e-10:
            self.x_vel = 0
        if abs(self.y_vel) < 1e-10:
            self.y_vel = 0
        if abs(self.z_vel) < 1e-10:
            self.z_vel = 0

    def _fix_acceleration(self, x_acc, y_acc, z_acc):
        """Set the acceleration components."""
        self.x_acc, self.y_acc, self.z_acc = x_acc, y_acc, z_acc
        if abs(self.x_acc) < 1e-10:
            self.x_acc = 0
        if abs(self.y_acc) < 1e-10:
            self.y_acc = 0
        if abs(self.z_acc) < 1e-10:
            self.z_acc = 0

    def _clear(self):
        """Clear the non-iterable instance variables."""
        self.x_pos, self.y_pos, self.z_pos = None, None, None
        self.x_vel, self.y_vel, self.z_vel = None, None, None
        self.x_acc, self.y_acc, self.z_acc = None, None, None

    def _vel_mag(self):
        """Calculate the magnitude and angles of the velocity."""
        return Vector(x=self.x_vel, y=self.y_vel, z=self.z_vel)._get_mag()

    def _acc_mag(self):
        """Calculate the magnitude and angles of the acceleration."""
        return Vector(x=self.x_acc, y=self.y_acc, z=self.z_acc)._get_mag()

    def _zero(self, s):
        """
        Initialize arrays for storing time-series data.

        Parameters
        ----------
        s : int
            The size of the arrays
        """
        self.x_positions, self.y_positions, self.z_positions = (
            np.zeros(s),
            np.zeros(s),
            np.zeros(s),
        )
        self.x_velocities, self.y_velocities, self.z_velocities = (
            np.zeros(s),
            np.zeros(s),
            np.zeros(s),
        )
        self.x_accelerations, self.y_accelerations, self.z_accelerations = (
            np.zeros(s),
            np.zeros(s),
            np.zeros(s),
        )

        self.vel_mags, self.vel_thetas, self.vel_phis = (
            np.zeros(s),
            np.zeros(s),
            np.zeros(s),
        )
        self.acc_mags, self.acc_thetas, self.acc_phis = (
            np.zeros(s),
            np.zeros(s),
            np.zeros(s),
        )

    def _set_position_data(self, i):
        """Store position data at index i."""
        self.x_positions[i] = self.x_pos
        self.y_positions[i] = self.y_pos
        self.z_positions[i] = self.z_pos

    def _set_velocity_data(self, i):
        """Store velocity data at index i."""
        self.x_velocities[i] = self.x_vel
        self.y_velocities[i] = self.y_vel
        self.z_velocities[i] = self.z_vel

        mag, theta, phi = self._vel_mag()
        self.vel_mags[i] = mag
        self.vel_thetas[i] = theta
        self.vel_phis[i] = phi

    def _set_acceleration_data(self, i):
        """Store acceleration data at index i."""
        self.x_accelerations[i] = self.x_acc
        self.y_accelerations[i] = self.y_acc
        self.z_accelerations[i] = self.z_acc

        mag, theta, phi = self._acc_mag()
        self.acc_mags[i] = mag
        self.acc_thetas[i] = theta
        self.acc_phis[i] = phi

    def _scale_kinematics_vector_for_plot(
        self, scale, velocity=False, acceleration=False
    ):
        """Scale a single velocity or acceleration vector for static plotting."""
        if velocity:
            if self.x_vel is None or self.y_vel is None or self.z_vel is None:
                return
            vec = np.array([self.x_vel, self.y_vel, self.z_vel])
            scaled_vec = vec * scale
            self._x_vel_scaled = scaled_vec[0]
            self._y_vel_scaled = scaled_vec[1]
            self._z_vel_scaled = scaled_vec[2]
        elif acceleration:
            if self.x_acc is None or self.y_acc is None or self.z_acc is None:
                return
            vec = np.array([self.x_acc, self.y_acc, self.z_acc])
            scaled_vec = vec * scale
            self._x_acc_scaled = scaled_vec[0]
            self._y_acc_scaled = scaled_vec[1]
            self._z_acc_scaled = scaled_vec[2]

    def _get_kinematics_arrow_head_for_plot(self, velocity=False, acceleration=False):
        """Get the 3D position of the scaled arrow head."""
        Rp_x, Rp_y, Rp_z = (
            self.x_pos,
            self.y_pos,
            self.z_pos if self.z_pos is not None else 0.0,
        )

        if velocity:
            head_x = Rp_x + self._x_vel_scaled
            head_y = Rp_y + self._y_vel_scaled
            head_z = Rp_z + self._z_vel_scaled
            return [head_x, head_y, head_z]
        elif acceleration:
            head_x = Rp_x + self._x_acc_scaled
            head_y = Rp_y + self._y_acc_scaled
            head_z = Rp_z + self._z_acc_scaled
            return [head_x, head_y, head_z]
        return [Rp_x, Rp_y, Rp_z]

    def _scale_kinematics_vectors_for_plot_arrays(
        self, scale, velocity=False, acceleration=False
    ):
        """Scale kinematics vectors for animation plotting."""
        if velocity:
            if (
                self.x_velocities is None
                or self.y_velocities is None
                or self.z_velocities is None
            ):
                return
            vecs = np.stack(
                [self.x_velocities, self.y_velocities, self.z_velocities], axis=-1
            )
            scaled_vecs = vecs * scale
            self._x_vel_scales = scaled_vecs[:, 0]
            self._y_vel_scales = scaled_vecs[:, 1]
            self._z_vel_scales = scaled_vecs[:, 2]

        elif acceleration:
            if (
                self.x_accelerations is None
                or self.y_accelerations is None
                or self.z_accelerations is None
            ):
                return
            vecs = np.stack(
                [self.x_accelerations, self.y_accelerations, self.z_accelerations],
                axis=-1,
            )
            scaled_vecs = vecs * scale
            self._x_acc_scales = scaled_vecs[:, 0]
            self._y_acc_scales = scaled_vecs[:, 1]
            self._z_acc_scales = scaled_vecs[:, 2]

    def _get_kinematics_arrow_heads_for_plot_arrays(
        self, velocity=False, acceleration=False
    ):
        """Calculate 3D head points for velocity/acceleration arrows."""
        if (
            self.x_positions is None
            or self.y_positions is None
            or self.z_positions is None
        ):
            return

        base_points_x = self.x_positions
        base_points_y = self.y_positions
        base_points_z = self.z_positions

        if velocity:
            if (
                self._x_vel_scales is None
                or self._y_vel_scales is None
                or self._z_vel_scales is None
            ):
                return
            self._vel_heads_3d = np.array(
                [
                    base_points_x + self._x_vel_scales,
                    base_points_y + self._y_vel_scales,
                    base_points_z + self._z_vel_scales,
                ]
            ).T

        elif acceleration:
            if (
                self._x_acc_scales is None
                or self._y_acc_scales is None
                or self._z_acc_scales is None
            ):
                return
            self._acc_heads_3d = np.array(
                [
                    base_points_x + self._x_acc_scales,
                    base_points_y + self._y_acc_scales,
                    base_points_z + self._z_acc_scales,
                ]
            ).T

    def __repr__(self):
        return f"Joint(name={self.name})"

    def __str__(self):
        return self.name