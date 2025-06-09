import numpy as np
import json
import os

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
APPEARANCE = os.path.join(THIS_DIR, "appearance.json")


class VectorBase:
    def __init__(
        self,
        joints=None,
        r=None,
        theta=None,
        phi=None,
        x=None,
        y=None,
        z=None,
        show=True,
        style=None,
        **kwargs,
    ):
        """
        :param joints: tup; A tuple of Joint objects. The first Joint is the tail, and the second is the head.
        :param r: int, float; The length of the vector.
        :param theta: int, float; The angle of the vector in radians from the positive x-axis in the xy-plane (azimuthal angle). Counterclockwise is positive.
        :param phi: int, float; The angle of the vector in radians from the positive z-axis (polar angle or inclination). 0 <= phi <= pi.
        :param x: int, float; The value of the x component of the vector.
        :param y: int, float; The value of the y component of the vector.
        :param z: int, float; The value of the z component of the vector.
        :param show: bool; If True, then the vector will be present in plots and animations.
        :param style: str; Applies a certain style passed to plt.plot().
            Options:
                ground - a dashed black line for grounded link
                dotted - a black dotted line
        :param kwargs: Extra arguments that are passed to plt.plot(). If not specified, the line will be maroon with a
            marker style = 'o'

        Instance Variables
        ------------------
        rs: An ndarray of r values.
        thetas: An ndarray of theta values.
        phis: An ndarray of phi values.
        r_dots: An ndarray of r_dot values (r_dot is the rate of change of the length of the vector length with respect
            to time).
        omegas: An ndarray of omega values (omega is the rate of change of the angle of the vector with respect to
            time).
        r_ddots: An ndarray of r_ddot values (r_ddot is the rate of change of the rate of change of the vector length
            with respect to time).
        alphas: An ndarray of alpha values (alpha is the rate of change of the rate of change of the angle of the vector
            with respect to time).
        get: A function that returns the x and y component of the vector. The arguments for this function depends on
            what is specified at the initialization of the object. For instance, if r is set to a certain value, the get
            function will require an angle input.
        """
        self.joints, self.show = joints, show

        with open(APPEARANCE, "r") as f:
            appearance = json.load(f)

        if style:
            self.kwargs = appearance["mechanism_plot"][style]
        elif kwargs:
            self.kwargs = kwargs
        else:
            self.kwargs = appearance["mechanism_plot"]["default"]

        # Coordinate initialization
        if x is not None and y is not None and z is not None:
            self.x, self.y, self.z = float(x), float(y), float(z)
            _r, _theta, _phi = self._calculate_spherical_from_cartesian(
                self.x, self.y, self.z
            )
            self.r, self.theta, self.phi = _r, _theta, _phi
        elif r is not None and theta is not None and phi is not None:
            self.r, self.theta, self.phi = float(r), float(theta), float(phi)
            self.x, self.y, self.z = self._calculate_cartesian_from_spherical(
                self.r, self.theta, self.phi
            )
        elif (
            r is not None and theta is not None and phi is None
        ):  # Assume 2D vector in XY plane
            self.r, self.theta, self.phi = float(r), float(theta), np.pi / 2
            self.x, self.y, self.z = self._calculate_cartesian_from_spherical(
                self.r, self.theta, self.phi
            )
            if (
                z is not None and z != 0
            ):  # If z is provided for a 2D init, warn or adjust? For now, override z.
                # print("Warning: z component provided for a 2D-style initialization (r, theta). Z will be 0.")
                pass  # self.z is already set from _calculate_cartesian_from_spherical with phi=pi/2
        elif (
            x is not None and y is not None and z is None
        ):  # Assume 2D vector in XY plane
            self.x, self.y, self.z = float(x), float(y), 0.0
            _r, _theta, _phi = self._calculate_spherical_from_cartesian(
                self.x, self.y, self.z
            )
            self.r, self.theta, self.phi = _r, _theta, _phi
        else:
            # Default to zero vector if insufficient information, or handle as per existing logic for partial r/theta
            self.x, self.y, self.z = (
                (float(x) if x is not None else 0.0),
                (float(y) if y is not None else 0.0),
                (float(z) if z is not None else 0.0),
            )
            if (
                x is None
                and y is None
                and z is None
                and r is None
                and theta is None
                and phi is None
            ):
                self.x, self.y, self.z = 0.0, 0.0, 0.0  # Ensure it's a zero vector

            _r, _theta, _phi = self._calculate_spherical_from_cartesian(
                self.x, self.y, self.z
            )
            # Only assign r, theta, phi if they weren't primary inputs leading to this path
            if r is None:
                self.r = _r
            else:
                self.r = float(r)  # Keep provided r if x,y,z were partial
            if theta is None:
                self.theta = _theta
            else:
                self.theta = float(theta)
            if phi is None:
                self.phi = _phi
            else:
                self.phi = float(phi)

        # Store initial r, theta, phi if they were provided as primary inputs for fixed vector case
        self._initial_r = r
        self._initial_theta = theta
        self._initial_phi = phi
        self._initial_x = x
        self._initial_y = y
        self._initial_z = z

        self.rs, self.thetas, self.phis = None, None, None  # ADDED self.phis
        self.zs = None  # ADDED self.zs for direct z storage over time if needed
        self.r_dots, self.omegas, self.phi_dots = (
            None,
            None,
            None,
        )  # ADDED self.phi_dots (omega is for xy-plane: theta_dot)
        self.r_ddots, self.alphas, self.phi_ddots = (
            None,
            None,
            None,
        )  # ADDED self.phi_ddots (alpha is for xy-plane: theta_ddot)

        # Determine state and assign get method
        # Fully fixed cases first
        if (
            self._initial_x is not None
            and self._initial_y is not None
            and self._initial_z is not None
        ):  # Fixed in 3D Cartesian
            self.r_dot, self.omega, self.phi_dot = 0, 0, 0
            self.r_ddot, self.alpha, self.phi_ddot = 0, 0, 0
            self.get = self._neither  # 0 args
        elif (
            self._initial_r is not None
            and self._initial_theta is not None
            and self._initial_phi is not None
        ):  # Fixed in 3D Spherical
            self.r_dot, self.omega, self.phi_dot = 0, 0, 0
            self.r_ddot, self.alpha, self.phi_ddot = 0, 0, 0
            self.get = self._neither  # 0 args
        # Handle fixed 2D polar explicitly *before* variable phi case
        elif (
            self._initial_r is not None
            and self._initial_theta is not None
            and phi is None
        ):  # phi is the original argument passed to __init__
            # This catches Vector(r=..., theta=...) where phi was omitted.
            self.r_dot, self.omega, self.phi_dot = 0, 0, 0
            self.r_ddot, self.alpha, self.phi_ddot = 0, 0, 0
            if self.phi is None or not np.isclose(self.phi, np.pi / 2):
                self.phi = np.pi / 2  # Enforce XY plane assumption for this case
                self.x, self.y, self.z = self._calculate_cartesian_from_spherical(
                    self.r, self.theta, self.phi
                )
            self.get = self._neither  # 0 args, as it's fully determined 2D

        # 3D cases with one or more variables
        elif (
            self._initial_r is None
            and self._initial_theta is None
            and self._initial_phi is None
        ):  # All r, theta, phi are variable
            self.r_dot, self.omega, self.phi_dot = None, None, None
            self.r_ddot, self.alpha, self.phi_ddot = None, None, None
            self.get = self._both_spherical  # Expects 3 args (r, theta, phi)
        elif (
            self._initial_r is not None
            and self._initial_theta is None
            and self._initial_phi is None
        ):  # r-fixed, theta and phi are variable inputs
            self.r_dot, self.r_ddot = 0, 0
            self.omega, self.alpha = None, None  # theta varies
            self.phi_dot, self.phi_ddot = None, None  # phi varies
            # Ensure phi is not assumed pi/2 by default if it's meant to be a variable for _tangent_spherical
            # If self.phi was defaulted to pi/2 earlier due to r, theta given and phi being None,
            # it might need to be "unfixed" here if this path is chosen.
            # However, this path is for _initial_phi is None, so self.phi might already be what it needs to be (e.g. from x,y,z or a default)
            # The key is that _tangent_spherical will receive and set theta and phi.
            self.get = self._tangent_spherical  # Expects 2 args (theta, phi)
        elif (
            self._initial_r is None
            and self._initial_theta is not None
            and self._initial_phi is not None
        ):  # r varies, theta & phi fixed
            self.omega, self.alpha = 0, 0  # theta_dot, theta_ddot fixed
            self.phi_dot, self.phi_ddot = 0, 0  # phi_dot, phi_ddot fixed
            self.r_dot, self.r_ddot = None, None
            self.get = self._slip_spherical  # Expects 1 arg (r)
        elif (
            self._initial_r is not None
            and self._initial_theta is not None
            and self._initial_phi is None
        ):  # r & theta fixed, phi varies
            # This case implies r & theta were given, and phi was explicitly passed as None (or defaulted and wasn't caught by fixed 2D case)
            self.r_dot, self.r_ddot = 0, 0
            self.omega, self.alpha = 0, 0  # theta is fixed
            self.phi_dot, self.phi_ddot = None, None  # phi is variable
            pos_instance = self
            if hasattr(self, "pos") and isinstance(self.pos, Position):
                pos_instance = self.pos
            elif not isinstance(self, Position):
                pass
            self.get = lambda phi_angle_val: pos_instance._phi_varies_get(phi_angle_val)

        # Fallback to 2D interpretations for other partial inputs
        elif (
            self._initial_r is not None and self._initial_theta is None
        ):  # Handles case: r-fixed, theta varies (phi implicitly pi/2 and fixed)
            self.r_dot, self.r_ddot = 0, 0
            self.omega, self.alpha = None, None  # theta varies
            self.phi_dot, self.phi_ddot = 0, 0  # phi implicitly fixed
            if self.phi is None or not np.isclose(self.phi, np.pi / 2):
                self.phi = np.pi / 2
                self.x, self.y, self.z = self._calculate_cartesian_from_spherical(
                    self.r, self.theta, self.phi
                )
            self.get = self._tangent  # 1 arg (theta)
        elif (
            self._initial_r is None and self._initial_theta is not None
        ):  # Handles case: theta-fixed, r varies (phi implicitly pi/2 and fixed)
            self.r_dot, self.r_ddot = None, None  # r varies
            self.omega, self.alpha = 0, 0  # theta fixed
            self.phi_dot, self.phi_ddot = 0, 0  # phi implicitly fixed
            if self.phi is None or not np.isclose(self.phi, np.pi / 2):
                self.phi = np.pi / 2
                self.x, self.y, self.z = self._calculate_cartesian_from_spherical(
                    self.r, self.theta, self.phi
                )
            self.get = self._slip  # 1 arg (r)
        elif (
            self._initial_r is None and self._initial_theta is None
        ):  # Handles case: r, theta vary (phi implicitly pi/2 and fixed)
            self.r_dot, self.omega = None, None
            self.r_ddot, self.alpha = None, None
            self.phi_dot, self.phi_ddot = 0, 0
            if self.phi is None or not np.isclose(self.phi, np.pi / 2):
                self.phi = np.pi / 2
                self.x, self.y, self.z = self._calculate_cartesian_from_spherical(
                    self.r, self.theta, self.phi
                )
            self.get = self._both  # 2 args (r, theta)
        else:  # Default catch-all if no specific pattern matched
            self.r_dot, self.omega, self.phi_dot = None, None, None
            self.r_ddot, self.alpha, self.phi_ddot = None, None, None
            self.get = self._both_spherical  # Safest general fallback for 3D

    def _calculate_cartesian_from_spherical(self, r, theta, phi):
        x = r * np.sin(phi) * np.cos(theta)
        y = r * np.sin(phi) * np.sin(theta)
        z = r * np.cos(phi)
        return float(x), float(y), float(z)

    def _calculate_spherical_from_cartesian(self, x, y, z):
        r = np.sqrt(x**2 + y**2 + z**2)
        if r == 0:
            theta = 0.0
            phi = 0.0  # Or undefined, conventionally 0
        else:
            theta = np.arctan2(y, x)
            phi = np.arccos(z / r)  # 0 <= phi <= pi
        return float(r), float(theta), float(phi)

    def _neither(self):
        pass

    def _both_spherical(self, _, __, ___):
        pass

    def _slip_spherical(self, _):
        pass

    def _tangent_spherical(self, _, __):
        pass

    def _fix_global_position(self):
        """
        Fixes the position of the head joint by making its position the x and y components of the current instance.
        """
        self.joints[1]._fix_position(self.x, self.y, self.z)

    def _fix_global_velocity(self):
        """
        Fixes the velocity of the head joint by making its velocity the x and y components of the current instance.
        """
        self.joints[1]._fix_velocity(self.x, self.y, self.z)

    def _fix_global_acceleration(self):
        """
        Fixes the acceleration of the head joint by making its acceleration the x and y components of the current
        instance.
        """
        self.joints[1]._fix_acceleration(self.x, self.y, self.z)

    def _reverse(self):
        """
        :return: A VectorBase object that is reversed. The joints get reversed as well as the x and y components.
        """
        return VectorBase(
            joints=(self.joints[1], self.joints[0]),
            x=-self.x,
            y=-self.y,
            z=-self.z,
            style=self.kwargs.get("style"),
        )

    def _get_mag(self):
        """
        :return: A tuple consisting of the magnitude of the current instance and the angles (theta_xy, phi_z).
        """
        r, theta, phi = self._calculate_spherical_from_cartesian(self.x, self.y, self.z)
        return r, theta, phi

    def __add__(self, other):
        if not isinstance(other, VectorBase):
            return NotImplemented

        new_x = self.x + other.x
        new_y = self.y + other.y
        other_z = other.z if hasattr(other, "z") and other.z is not None else 0.0
        new_z = self.z + other_z

        new_joints = (
            (self.joints[0], other.joints[1])
            if self.joints
            and other.joints
            and len(self.joints) > 0
            and len(other.joints) > 1
            else None
        )

        return VectorBase(
            joints=new_joints, x=new_x, y=new_y, z=new_z, style=self.kwargs.get("style")
        )


class Vector:
    def __init__(
        self,
        joints=None,
        r=None,
        theta=None,
        phi=None,
        x=None,
        y=None,
        z=None,
        show=True,
        style=None,
        **kwargs,
    ):
        """
        See the VectorBase class for details regarding the parameters. The purpose of this class is to group Position,
        Velocity, and Acceleration objects.

        Instance Variables
        ------------------
        pos: Position object which is a subclass of VectorBase. Does not include the r_dot, omega, r_ddot, and alpha
            attributes.
        vel: Velocity object which is a subclass of VectorBase. Does not include the r_ddot and alpha attributes.
        acc: Acceleration object which is a subclass of VectorBase.
        """
        self.pos = Position(
            joints=joints,
            r=r,
            theta=theta,
            phi=phi,
            x=x,
            y=y,
            z=z,
            show=show,
            style=style,
            **kwargs,
        )
        self.vel = Velocity(
            joints=joints,
            r=r,
            theta=theta,
            phi=phi,
            x=x,
            y=y,
            z=z,
            show=show,
            style=style,
            **kwargs,
        )
        self.acc = Acceleration(
            joints=joints,
            r=r,
            theta=theta,
            phi=phi,
            x=x,
            y=y,
            z=z,
            show=show,
            style=style,
            **kwargs,
        )

        self.get = self.pos.get
        self.joints = joints

    @property
    def show(self) -> bool:
        return self.pos.show

    @show.setter
    def show(self, value: bool):
        self.pos.show = value
        self.vel.show = value
        self.acc.show = value

    def _update_velocity(self):
        """
        Updates the velocity object to include the length, r, and the angle ,theta.
        And for 3D, also phi, and positional data for velocity calculation.
        """
        self.vel.r = self.pos.r
        self.vel.theta = self.pos.theta
        self.vel.phi = self.pos.phi  # ADDED for 3D

        # Pass current position to velocity object for its calculations
        self.vel.pos_r = self.pos.r
        self.vel.pos_theta = self.pos.theta
        self.vel.pos_phi = self.pos.phi

    def _update_acceleration(self):
        """
        Updates the acceleration object to include r, theta, r_dot, and omega.
        And for 3D, also phi, phi_dot, and positional/velocity data for acceleration calculation.
        """
        # Positional context for acceleration calculation
        self.acc.pos_r = self.pos.r
        self.acc.pos_theta = self.pos.theta
        self.acc.pos_phi = self.pos.phi

        # Velocity context for acceleration calculation
        # (These are r_dot, theta_dot, phi_dot of the vector itself)
        self.acc.vel_r_dot = self.vel.r_dot
        self.acc.vel_omega = self.vel.omega  # This is theta_dot
        self.acc.vel_phi_dot = self.vel.phi_dot

        # Set r, theta, phi of the acceleration vector itself (if it means magnitude/direction of acceleration)
        # Or, it could inherit from the point of application (position).
        # For now, let's assume acc's r,theta,phi refer to the position, consistent with vel.
        self.acc.r = (
            self.pos.r
        )  # Or self.vel.r if acc vector's "r" means something else
        self.acc.theta = self.pos.theta
        self.acc.phi = self.pos.phi

    def _zero(self, s):
        """
        Zeros all the ndarray attributes at a certain size, s.

        :param s: int; The size of the data
        """
        self.pos.rs = np.zeros(s)
        self.pos.thetas = np.zeros(s)
        if hasattr(self.pos, "phis"):
            self.pos.phis = np.zeros(s)  # ADDED for 3D

        self.vel.rs = self.pos.rs
        self.vel.thetas = self.pos.thetas
        if hasattr(self.vel, "phis"):
            self.vel.phis = self.pos.phis  # ADDED for 3D

        self.vel.r_dots = np.zeros(s)
        self.vel.omegas = np.zeros(s)
        if hasattr(self.vel, "phi_dots"):
            self.vel.phi_dots = np.zeros(s)  # ADDED for 3D

        self.acc.rs = self.vel.rs  # Should be pos.rs
        self.acc.thetas = self.vel.thetas  # Should be pos.thetas
        if hasattr(self.acc, "phis"):
            self.acc.phis = self.vel.phis  # Should be pos.phis

        self.acc.r_dots = self.vel.r_dots
        self.acc.omegas = self.vel.omegas
        if hasattr(self.acc, "phi_dots"):
            self.acc.phi_dots = self.vel.phi_dots  # ADDED for 3D

        self.acc.r_ddots = np.zeros(s)
        self.acc.alphas = np.zeros(s)
        if hasattr(self.acc, "phi_ddots"):
            self.acc.phi_ddots = np.zeros(s)  # ADDED for 3D

    def _set_position_data(self, i):
        """
        Sets position data at index, i.

        :param i: Index
        """
        self.pos.rs[i] = self.pos.r
        self.pos.thetas[i] = self.pos.theta
        if hasattr(self.pos, "phis") and self.pos.phis is not None:
            self.pos.phis[i] = self.pos.phi  # ADDED for 3D

    def _set_velocity_data(self, i):
        """
        Sets velocity data at index, i.

        :param i: Index
        """
        self.vel.r_dots[i] = self.vel.r_dot
        self.vel.omegas[i] = self.vel.omega
        if hasattr(self.vel, "phi_dots") and self.vel.phi_dots is not None:
            self.vel.phi_dots[i] = self.vel.phi_dot  # ADDED for 3D

    def _set_acceleration_data(self, i):
        """
        Sets acceleration data at index, i.

        :param i: Index
        """
        self.acc.r_ddots[i] = self.acc.r_ddot
        self.acc.alphas[i] = self.acc.alpha
        if hasattr(self.acc, "phi_ddots") and self.acc.phi_ddots is not None:
            self.acc.phi_ddots[i] = self.acc.phi_ddot  # ADDED for 3D

    def __call__(self, *args):
        return self.get(*args)

    def __repr__(self):
        return f"{self.joints[0]}{self.joints[1]}"


class Position(VectorBase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)  # Use super() for proper MRO
        # Remove derivative properties not relevant to Position
        for attr_name in [
            "r_dot",
            "omega",
            "phi_dot",
            "r_ddot",
            "alpha",
            "phi_ddot",
            "r_dots",
            "omegas",
            "phi_dots",
            "r_ddots",
            "alphas",
            "phi_ddots",
        ]:
            if hasattr(self, attr_name):
                delattr(self, attr_name)

    def _phi_varies_get(self, phi_angle):
        # Assumes self.r and self.theta (inclination) are fixed and stored from __init__.
        # phi_angle is the new azimuthal angle.
        self.phi = float(phi_angle)
        self.x, self.y, self.z = self._calculate_cartesian_from_spherical(
            self.r, self.theta, self.phi
        )
        return np.array([self.x, self.y, self.z])

    def _both_spherical(
        self, r, theta, phi
    ):  # All r, theta, phi are inputs defining the position
        self.r, self.theta, self.phi = float(r), float(theta), float(phi)
        self.x, self.y, self.z = self._calculate_cartesian_from_spherical(
            self.r, self.theta, self.phi
        )
        return np.array([self.x, self.y, self.z])

    def _neither(
        self,
    ):  # Position is fixed, x,y,z (and r,theta,phi) already set in __init__
        # Ensure x,y,z are consistent if r,theta,phi were primary for fixed vector
        # This should be handled by VectorBase.__init__
        return np.array([self.x, self.y, self.z])

    def _tangent_spherical(self, theta, phi):  # r is fixed, theta, phi are inputs
        # self.r is already set and fixed
        self.theta, self.phi = float(theta), float(phi)
        self.x, self.y, self.z = self._calculate_cartesian_from_spherical(
            self.r, self.theta, self.phi
        )
        return np.array([self.x, self.y, self.z])

    def _slip_spherical(self, r):  # theta, phi are fixed, r is input
        # self.theta, self.phi are already set and fixed
        self.r = float(r)
        self.x, self.y, self.z = self._calculate_cartesian_from_spherical(
            self.r, self.theta, self.phi
        )
        return np.array([self.x, self.y, self.z])

    # --- Keep 2D versions or adapt them ---
    def _both(self, r, theta):  # Original _both, for 2D (r, theta vary)
        # Calculates x,y,z assuming phi=pi/2
        self.r, self.theta, self.phi = float(r), float(theta), np.pi / 2
        self.x, self.y, self.z = self._calculate_cartesian_from_spherical(
            self.r, self.theta, self.phi
        )
        return np.array([self.x, self.y, self.z])

    def _tangent(self, theta):  # Original _tangent, for 2D (theta varies, r fixed)
        # Calculates x,y,z assuming phi=pi/2 and self.r is fixed
        self.theta, self.phi = float(theta), np.pi / 2
        self.x, self.y, self.z = self._calculate_cartesian_from_spherical(
            self.r, self.theta, self.phi
        )
        return np.array([self.x, self.y, self.z])

    def _slip(self, r):  # Original _slip, for 2D (r varies, theta fixed)
        # Calculates x,y,z assuming phi=pi/2 and self.theta is fixed
        self.r, self.phi = float(r), np.pi / 2
        self.x, self.y, self.z = self._calculate_cartesian_from_spherical(
            self.r, self.theta, self.phi
        )
        return np.array([self.x, self.y, self.z])

    def __repr__(self):
        return f"Position(joints={self.joints}, r={self.r}, theta={self.theta})"

    def __str__(self):
        return f"R_{self.joints[0]}{self.joints[1]}"


class Velocity(VectorBase):
    def __init__(self, **kwargs):
        VectorBase.__init__(self, **kwargs)
        # Remove higher-order derivative properties not relevant to Velocity
        for attr_name in [
            "r_ddot",
            "alpha",
            "phi_ddot",
            "r_ddots",
            "alphas",
            "phi_ddots",
        ]:
            if hasattr(self, attr_name):
                delattr(self, attr_name)

        # Velocity components (vx, vy, vz) are stored in self.x, self.y, self.z
        # Positional r, theta, phi (of the point where velocity is measured) are needed for calculations.
        # These should be set by an update mechanism (e.g., Vector._update_velocity)
        self.pos_r: float | None = None
        self.pos_theta: float | None = None
        self.pos_phi: float | None = None

    def _neither(
        self,
    ):  # Velocity is fixed (all derivatives r_dot, omega, phi_dot are zero)
        # vx, vy, vz (self.x, self.y, self.z) are set if __init__ received fixed velocity components.
        # Or, if __init__ set r_dot=0, omega=0, phi_dot=0, then x,y,z should be 0.
        # This implies that if a vector has fixed r, theta, phi (Position._neither), its velocity is (0,0,0).
        # If the velocity itself is a fixed non-zero vector, x,y,z are its components.
        return np.array([self.x, self.y, self.z])

    def _both_spherical(self, r_dot, theta_dot, phi_dot):  # All velocity inputs vary
        # These are direct inputs for r_dot, omega (theta_dot), phi_dot
        self.r_dot, self.omega, self.phi_dot = (
            float(r_dot),
            float(theta_dot),
            float(phi_dot),
        )

        # Components of velocity in spherical coordinates (radial, azimuthal, polar)
        # Requires pos_r, pos_theta, pos_phi from the corresponding Position vector
        if self.pos_r is None or self.pos_theta is None or self.pos_phi is None:
            # This should not happen if _update_velocity was called
            # Defaulting to origin for calculation, or raise error
            pr, pt, pp = 0.0, 0.0, np.pi / 2  # Or some other handling
            print(
                "Warning: Position data not available in Velocity vector for component calculation."
            )
        else:
            pr, pt, pp = self.pos_r, self.pos_theta, self.pos_phi

        # Velocity components (vx, vy, vz) derived from d/dt(x), d/dt(y), d/dt(z)
        # where x = pr*sin(pp)*cos(pt), y = pr*sin(pp)*sin(pt), z = pr*cos(pp)
        vx = (
            self.r_dot * np.sin(pp) * np.cos(pt)  # r_dot term for x
            + pr * self.phi_dot * np.cos(pp) * np.cos(pt)  # phi_dot term for x
            - pr * self.omega * np.sin(pp) * np.sin(pt)
        )  # theta_dot (omega) term for x
        vy = (
            self.r_dot * np.sin(pp) * np.sin(pt)  # r_dot term for y
            + pr * self.phi_dot * np.cos(pp) * np.sin(pt)  # phi_dot term for y
            + pr * self.omega * np.sin(pp) * np.cos(pt)
        )  # theta_dot (omega) term for y
        vz = self.r_dot * np.cos(pp) - pr * self.phi_dot * np.sin(  # r_dot term for z
            pp
        )  # phi_dot term for z (no theta_dot term)

        self.x, self.y, self.z = vx, vy, vz
        return np.array([self.x, self.y, self.z])

    def _tangent_spherical(self, theta_dot, phi_dot):  # r_dot is zero
        return self._both_spherical(0.0, theta_dot, phi_dot)

    def _slip_spherical(self, r_dot):  # theta_dot, phi_dot are zero
        return self._both_spherical(r_dot, 0.0, 0.0)

    # --- Adapt 2D versions ---
    def _both(self, r_dot, omega):  # Original: r_dot, omega (theta_dot for 2D)
        # Assume motion in XY plane, so phi_dot = 0, and pos_phi = pi/2
        if self.pos_phi is None or not np.isclose(self.pos_phi, np.pi / 2):
            # print("Warning: 2D velocity method called for a non-XY-plane vector or missing pos_phi")
            # To proceed, we'd assume pos_phi = pi/2 for this 2D context.
            # This state should ideally be set by _update_velocity correctly.
            pass
        return self._both_spherical(r_dot, omega, 0.0)  # phi_dot is 0

    def _tangent(self, omega):  # Original: omega (theta_dot for 2D), r_dot=0
        return self._both_spherical(0.0, omega, 0.0)

    def _slip(self, r_dot):  # Original: r_dot, omega=0
        return self._both_spherical(r_dot, 0.0, 0.0)

    def __repr__(self):
        return f"Velocity(joints={self.joints}, r_dot={self.r_dot}, omega={self.omega})"

    def __str__(self):
        return f"V_{self.joints[0]}{self.joints[1]}"


class Acceleration(VectorBase):
    def __init__(self, **kwargs):
        VectorBase.__init__(self, **kwargs)
        # All derivative properties are relevant to Acceleration at the VectorBase level
        # (r_ddot, alpha, phi_ddot)

        # Acceleration components (ax, ay, az) are stored in self.x, self.y, self.z
        # Positional and velocity data (r, theta, phi, r_dot, theta_dot, phi_dot) are needed.
        # These should be set by an update mechanism (e.g., Vector._update_acceleration)
        self.pos_r: float | None = None
        self.pos_theta: float | None = None
        self.pos_phi: float | None = None
        self.vel_r_dot: float | None = None
        self.vel_omega: float | None = None  # This is theta_dot
        self.vel_phi_dot: float | None = None

    def _neither(self):  # Acceleration is fixed
        return np.array([self.x, self.y, self.z])

    def _both_spherical(
        self, r_ddot, theta_ddot, phi_ddot
    ):  # All acceleration inputs vary
        self.r_ddot, self.alpha, self.phi_ddot = (
            float(r_ddot),
            float(theta_ddot),
            float(phi_ddot),
        )  # alpha is theta_ddot

        if None in [
            self.pos_r,
            self.pos_theta,
            self.pos_phi,
            self.vel_r_dot,
            self.vel_omega,
            self.vel_phi_dot,
        ]:
            # print("Warning: Position/Velocity data not available in Acceleration vector for component calculation.")
            # Defaulting to zero acceleration if essential data is missing.
            # This state should ideally be prevented by prior calls to _update_acceleration.
            self.x, self.y, self.z = 0.0, 0.0, 0.0
        else:
            pr = self.pos_r  # Radial distance r
            pt = (
                self.pos_theta
            )  # Azimuthal angle (theta in code, phi in standard physics)
            pp = self.pos_phi  # Polar angle (phi in code, theta in standard physics)

            vrd = self.vel_r_dot  # r_dot
            vthd = (
                self.vel_omega
            )  # theta_dot in code (azimuthal velocity, phi_dot in standard)
            vphd = (
                self.vel_phi_dot
            )  # phi_dot in code (polar velocity, theta_dot in standard)

            r_ddot_val = self.r_ddot
            # self.alpha is theta_ddot in code (azimuthal acceleration, phi_ddot in standard)
            # self.phi_ddot is phi_ddot in code (polar acceleration, theta_ddot in standard)
            theta_ddot_val = (
                self.alpha
            )  # Azimuthal angular acceleration (standard phi_ddot)
            phi_ddot_val = (
                self.phi_ddot
            )  # Polar angular acceleration (standard theta_ddot)

            # Spherical acceleration components (using standard physics notation mapping)
            # Standard polar angle = pp (self.pos_phi)
            # Standard azimuthal angle = pt (self.pos_theta)

            # Radial component of acceleration (a_r)
            a_radial = r_ddot_val - pr * vphd**2 - pr * vthd**2 * np.sin(pp) ** 2

            # Polar component of acceleration (a_theta in standard notation)
            # This is the component along the direction of increasing standard polar angle (pp)
            a_polar_std = (
                pr * phi_ddot_val
                + 2 * vrd * vphd
                - pr * vthd**2 * np.sin(pp) * np.cos(pp)
            )

            # Azimuthal component of acceleration (a_phi in standard notation)
            # This is the component along the direction of increasing standard azimuthal angle (pt)
            a_azimuthal_std = (
                pr * theta_ddot_val * np.sin(pp)
                + 2 * vrd * vthd * np.sin(pp)
                + 2 * pr * vphd * vthd * np.cos(pp)
            )

            # Cartesian components of acceleration
            # Transformation uses:
            # Standard polar angle (theta_std) = pp
            # Standard azimuthal angle (phi_std) = pt
            sin_pp_val = np.sin(pp)  # sin(polar_std)
            cos_pp_val = np.cos(pp)  # cos(polar_std)
            sin_pt_val = np.sin(pt)  # sin(azimuthal_std)
            cos_pt_val = np.cos(pt)  # cos(azimuthal_std)

            # ax = a_r*sin(theta_std)cos(phi_std) + a_theta_std*cos(theta_std)cos(phi_std) - a_phi_std*sin(phi_std)
            self.x = (
                a_radial * sin_pp_val * cos_pt_val
                + a_polar_std * cos_pp_val * cos_pt_val
                - a_azimuthal_std * sin_pt_val
            )

            # ay = a_r*sin(theta_std)sin(phi_std) + a_theta_std*cos(theta_std)sin(phi_std) + a_phi_std*cos(phi_std)
            self.y = (
                a_radial * sin_pp_val * sin_pt_val
                + a_polar_std * cos_pp_val * sin_pt_val
                + a_azimuthal_std * cos_pt_val
            )

            # az = a_r*cos(theta_std) - a_theta_std*sin(theta_std)
            self.z = a_radial * cos_pp_val - a_polar_std * sin_pp_val

        return np.array([self.x, self.y, self.z])

    def _tangent_spherical(self, theta_ddot, phi_ddot):  # r_ddot is zero
        return self._both_spherical(0.0, theta_ddot, phi_ddot)

    def _slip_spherical(self, r_ddot):  # theta_ddot, phi_ddot are zero
        return self._both_spherical(r_ddot, 0.0, 0.0)

    # --- Adapt 2D versions ---
    def _both(self, r_ddot, alpha):  # Original: r_ddot, alpha (theta_ddot for 2D)
        return self._both_spherical(r_ddot, alpha, 0.0)

    def _tangent(self, alpha):  # Original: alpha (theta_ddot for 2D), r_ddot=0
        return self._both_spherical(0.0, alpha, 0.0)

    def _slip(self, r_ddot):  # Original: r_ddot, alpha=0
        return self._both_spherical(r_ddot, 0.0, 0.0)

    def __repr__(self):
        return f"Acceleration(joints={self.joints}, r_ddot={self.r_ddot}, alpha={self.alpha})"

    def __str__(self):
        return f"A_{self.joints[0]}{self.joints[1]}"
