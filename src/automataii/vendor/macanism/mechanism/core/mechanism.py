"""Core Mechanism class for kinematic analysis."""

import numpy as np
from typing import List

from .joint import Joint
from ..analysis.kinematics import KinematicsAnalyzer
from ..analysis.solver import MechanismSolver
from ..analysis.bounds import BoundsCalculator
from ..visualization.plotting import MechanismPlotter
from ..visualization.animation import MechanismAnimator
from ..visualization.scaling import ScalingCalculator
from ..tables import MechanismTables


class Mechanism:
    """Main mechanism class for kinematic analysis."""

    def __init__(
        self,
        vectors=None,
        origin=None,
        loops=None,
        loops_vel=None,
        loops_acc=None,
        pos=None,
        vel=None,
        acc=None,
        guess=None,
        unknown_map=None,
    ):
        """
        Initialize a mechanism for kinematic analysis.

        Parameters
        ----------
        vectors : tuple
            A tuple of Vector objects. The first vector is the input vector.
        origin : Joint
            The joint object to be taken as the origin.
        loops : function
            A function that returns a list/array of loop equations.
        loops_vel : function, optional
            Loop equations for velocity analysis.
        loops_acc : function, optional
            Loop equations for acceleration analysis.
        pos : ndarray or scalar
            Input position data for the driven vector(s).
        vel : ndarray or scalar, optional
            Input velocity data for the driven vector(s).
        acc : ndarray or scalar, optional
            Input acceleration data for the driven vector(s).
        guess : tuple
            Initial guesses for (pos_guess, vel_guess, acc_guess).
        unknown_map : list, optional
            Mapping between unknowns and vector DOFs.
        """
        self.vectors = vectors
        self.origin = origin
        self.loops = loops
        self.loops_vel = loops_vel
        self.loops_acc = loops_acc
        self.pos = pos
        self.vel = vel
        self.acc = acc
        self.guess = guess
        self.unknown_map = unknown_map

        # Validate inputs
        assert self.vectors, "Vector argument not defined."
        assert self.origin, "Origin argument not defined."
        assert self.loops, "Loops argument not defined."
        assert self.pos is not None, "pos argument must be defined."

        # Extract joints from vectors
        joints = set()
        for v in vectors:
            joints.update(v.joints)
        self.joints = list(joints)

        # Extract position, velocity, acceleration objects
        self.positions, self.velocities, self.accelerations = [], [], []
        for v in self.vectors:
            self.positions.append(v.pos)
            self.velocities.append(v.vel)
            self.accelerations.append(v.acc)

        # Create dictionary for vector access
        self.dic = {v: v for v in self.vectors}

        # Determine if input is array
        self.is_array = isinstance(self.pos, np.ndarray) and self.pos.ndim > 0
        
        # Ensure inputs are arrays internally
        if not isinstance(self.pos, np.ndarray):
            self.pos = np.array([self.pos])
        if self.vel is not None and not isinstance(self.vel, np.ndarray):
            self.vel = np.array([self.vel])
        if self.acc is not None and not isinstance(self.acc, np.ndarray):
            self.acc = np.array([self.acc])

        # Initialize arrays if needed
        if self.is_array:
            for v in self.vectors:
                v._zero(self.pos.shape[0])
            for j in self.joints:
                j._zero(self.pos.shape[0])

            # Validate array sizes
            if self.vel is not None:
                assert self.pos.shape[0] == self.vel.shape[0], (
                    "vel input size does not match pos input size."
                )
            if self.acc is not None:
                assert self.pos.shape[0] == self.acc.shape[0], (
                    "acc input size does not match pos input size."
                )

        # Fix origin
        self.origin._fix_position(0, 0, 0)
        self.origin._fix_velocity(0, 0, 0)
        self.origin._fix_acceleration(0, 0, 0)

        # Initialize helper objects
        self._kinematics_analyzer = KinematicsAnalyzer(
            self.origin, self.positions, self.velocities, 
            self.accelerations, self.joints
        )
        self._solver = MechanismSolver(self)
        self._plotter = MechanismPlotter(self)
        self._animator = MechanismAnimator(self)
        self._tables = MechanismTables(
            self.positions, self.velocities, 
            self.accelerations, self.joints
        )

    def calculate(self):
        """Solve for a single point in time."""
        self._solver.calculate()

    def iterate(self):
        """Solve for multiple time steps."""
        self._solver.iterate()

    def plot(self, velocity=False, acceleration=False, scale=0.1, 
             show_joints=True, grid=True, cushion=1):
        """Plot the mechanism in its current state."""
        return self._plotter.plot(
            velocity=velocity,
            acceleration=acceleration,
            scale=scale,
            show_joints=show_joints,
            grid=grid,
            cushion=cushion
        )

    def get_animation(self, velocity=False, acceleration=False, scale=0.1,
                      stamp=None, stamp_loc=(0.05, 0.9), grid=True,
                      cushion=1, show_joints=False, interval=50,
                      key_bindings=True):
        """Create an animation of the mechanism motion."""
        return self._animator.get_animation(
            velocity=velocity,
            acceleration=acceleration,
            scale=scale,
            stamp=stamp,
            stamp_loc=stamp_loc,
            grid=grid,
            cushion=cushion,
            show_joints=show_joints,
            interval=interval,
            key_bindings=key_bindings
        )

    def tables(self, position=False, velocity=False, acceleration=False, to_five=False):
        """Print specified data tables."""
        self._tables.print_tables(
            position=position,
            velocity=velocity,
            acceleration=acceleration,
            to_five=to_five
        )

    def test(self):
        """Check the distances between joints."""
        self._plotter.test_distances()

    def get_bounds(self, for_animation=False):
        """Get the bounding box of the mechanism."""
        return BoundsCalculator.get_bounds(self.joints, for_animation=for_animation)

    def clear_joints(self):
        """Clear joint data between calculations."""
        for joint in self.joints:
            joint._clear()

    @staticmethod
    def exclude(joints: List[Joint]):
        """Exclude joint velocities and accelerations from animations."""
        ScalingCalculator.exclude_joints(joints)

    # Internal methods delegated to kinematics analyzer
    def _fix_position(self):
        """Calculate the x, y, and z components of all vectors."""
        self._kinematics_analyzer.fix_position()

    def _fix_velocity(self):
        """Calculate the x, y, and z velocity components of all vectors."""
        self._kinematics_analyzer.fix_velocity()

    def _fix_acceleration(self):
        """Calculate the x, y, and z acceleration components of all vectors."""
        self._kinematics_analyzer.fix_acceleration()

    def _position_is_fixed(self):
        """Check if all joint positions are fixed."""
        return self._kinematics_analyzer._position_is_fixed()

    def _velocity_is_fixed(self):
        """Check if all joint velocities are fixed."""
        return self._kinematics_analyzer._velocity_is_fixed()

    def _acceleration_is_fixed(self):
        """Check if all joint accelerations are fixed."""
        return self._kinematics_analyzer._acceleration_is_fixed()

    def _find_scale(self, x_min, x_max, y_min, y_max, z_min=0, z_max=0,
                    scale_length=0.1, kind="plot", velocity=False, 
                    acceleration=False):
        """Find scale factor for kinematic vectors."""
        return ScalingCalculator.find_scale(
            self.joints, x_min, x_max, y_min, y_max, z_min, z_max,
            scale_length=scale_length, kind=kind, 
            velocity=velocity, acceleration=acceleration
        )

    def __getitem__(self, item):
        """Access vectors by key."""
        return self.dic[item]