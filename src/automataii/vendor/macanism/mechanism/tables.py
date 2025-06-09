"""Table generation for mechanism data display."""

import numpy as np
from mechanism.dataframe import Data


class MechanismTables:
    """Generator for mechanism data tables."""

    def __init__(self, positions, velocities, accelerations, joints):
        """
        Initialize the table generator.

        Parameters
        ----------
        positions : list
            List of position vectors.
        velocities : list
            List of velocity vectors.
        accelerations : list
            List of acceleration vectors.
        joints : list
            List of joints.
        """
        self.positions = positions
        self.velocities = velocities
        self.accelerations = accelerations
        self.joints = joints

    def print_tables(self, position=False, velocity=False, acceleration=False, to_five=False):
        """
        Print specified data tables.

        Parameters
        ----------
        position : bool, optional
            Print position data if True.
        velocity : bool, optional
            Print velocity data if True.
        acceleration : bool, optional
            Print acceleration data if True.
        to_five : bool, optional
            Print all data to five decimal places if True.
        """
        if position:
            self._print_position_table(to_five)
        if velocity:
            self._print_velocity_table(to_five)
        if acceleration:
            self._print_acceleration_table(to_five)

    def _print_position_table(self, to_five):
        """Print position data table."""
        print("POSITION")
        print("--------\n")
        
        if not to_five:
            mechanism_data = [
                [v, v.r, np.rad2deg(v.theta), v.x, v.y] for v in self.positions
            ]
            joint_data = [
                [j, j.x_pos, j.y_pos]
                for j in sorted(self.joints, key=lambda x: x.name)
            ]
        else:
            mechanism_data = [
                [
                    v,
                    f"{v.r:.5f}",
                    f"{np.rad2deg(v.theta):.5f}",
                    f"{v.x:.5f}",
                    f"{v.y:.5f}",
                ]
                for v in self.positions
            ]
            joint_data = [
                [j, f"{j.x_pos:.5f}", f"{j.y_pos:.5f}"]
                for j in sorted(self.joints, key=lambda x: x.name)
            ]
        
        Data(mechanism_data, headers=["Vector", "R", "Theta", "x", "y"]).print(
            table=True
        )
        print("")
        Data(joint_data, headers=["Joint", "x", "y"]).print(table=True)
        print("")

    def _print_velocity_table(self, to_five):
        """Print velocity data table."""
        print("VELOCITY")
        print("--------\n")
        
        if not to_five:
            mechanism_data = [
                [v, v._get_mag()[0], np.rad2deg(v._get_mag()[1]), v.x, v.y]
                for v in self.velocities
            ]
            omega_slip_data = [[v, v.omega, v.r_dot] for v in self.velocities]
            joint_data = [
                [j, j._vel_mag()[0], np.rad2deg(j._vel_mag()[1]), j.x_vel, j.y_vel]
                for j in sorted(self.joints, key=lambda x: x.name)
            ]
        else:
            mechanism_data = [
                [
                    v,
                    f"{v._get_mag()[0]:.5f}",
                    f"{np.rad2deg(v._get_mag()[1]):.5f}",
                    f"{v.x:.5f}",
                    f"{v.y:.5f}",
                ]
                for v in self.velocities
            ]
            omega_slip_data = [
                [v, f"{v.omega:.5f}", f"{v.r_dot:.5f}"] for v in self.velocities
            ]
            joint_data = [
                [
                    j,
                    f"{j._vel_mag()[0]:.5f}",
                    f"{np.rad2deg(j._vel_mag()[1]):.5f}",
                    f"{j.x_vel:.5f}",
                    f"{j.y_vel:.5f}",
                ]
                for j in sorted(self.joints, key=lambda x: x.name)
            ]

        Data(mechanism_data, headers=["Vector", "Mag", "Angle", "x", "y"]).print(
            table=True
        )
        print("")
        Data(omega_slip_data, headers=["Vector", "Omega", "R_dot"]).print(
            table=True
        )
        print("")
        Data(joint_data, headers=["Joint", "Mag", "Angle", "x", "y"]).print(
            table=True
        )
        print("")

    def _print_acceleration_table(self, to_five):
        """Print acceleration data table."""
        print("ACCELERATION")
        print("------------\n")
        
        if not to_five:
            mechanism_data = [
                [v, v._get_mag()[0], np.rad2deg(v._get_mag()[1]), v.x, v.y]
                for v in self.accelerations
            ]
            alpha_slip_data = [[v, v.alpha, v.r_ddot] for v in self.accelerations]
            joint_data = [
                [j, j._acc_mag()[0], np.rad2deg(j._acc_mag()[1]), j.x_acc, j.y_acc]
                for j in sorted(self.joints, key=lambda x: x.name)
            ]
        else:
            mechanism_data = [
                [
                    v,
                    f"{v._get_mag()[0]:.5f}",
                    f"{np.rad2deg(v._get_mag()[1]):.5f}",
                    f"{v.x:.5f}",
                    f"{v.y:.5f}",
                ]
                for v in self.accelerations
            ]
            alpha_slip_data = [
                [v, f"{v.alpha:.5f}", f"{v.r_ddot:.5f}"] for v in self.accelerations
            ]
            joint_data = [
                [
                    j,
                    f"{j._acc_mag()[0]:.5f}",
                    f"{np.rad2deg(j._acc_mag()[1]):.5f}",
                    f"{j.x_acc:.5f}",
                    f"{j.y_acc:.5f}",
                ]
                for j in sorted(self.joints, key=lambda x: x.name)
            ]

        Data(mechanism_data, headers=["Vector", "Mag", "Angle", "x", "y"]).print(
            table=True
        )
        print("")
        Data(alpha_slip_data, headers=["Vector", "Alpha", "R_ddot"]).print(
            table=True
        )
        print("")
        Data(joint_data, headers=["Joint", "Mag", "Angle", "x", "y"]).print(
            table=True
        )