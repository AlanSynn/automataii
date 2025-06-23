
import numpy as np
from scipy.optimize import fsolve

from automataii.kinematics.mechanism import MechanismType, MotionCurve


# --- Kinematic Solvers ---
def solve_4bar_closure(x: np.ndarray, l1: float, l2: float, l3: float, l4: float, theta2: float) -> tuple[float, float]:
    """Solve the 4-bar linkage closure equations."""
    theta3, theta4 = x
    eq1 = l2 * np.cos(theta2) + l3 * np.cos(theta3) - l4 * np.cos(theta4) - l1
    eq2 = l2 * np.sin(theta2) + l3 * np.sin(theta3) - l4 * np.sin(theta4)
    return (eq1, eq2)


def get_4bar_input_angle_range(l1: float, l2: float, l3: float, l4: float) -> tuple[float, float]:
    """Get the valid input angle range for a 4-bar linkage based on Grashof condition."""
    links = sorted([l1, l2, l3, l4])
    s, p, q, l = links
    # Grashof condition
    if (s + l) > (p + q):
        # It's a triple-rocker, calculate the limited range if possible.
        # This is a simplified check; real triple-rocker analysis is more complex.
        return (np.pi/3, 2*np.pi/3)  # Placeholder range
    # If the shortest link is the driver, it's a crank.
    if l2 == s:
        return (0, 2 * np.pi)
    # If the shortest link is the frame, it's a double-crank (drag-link).
    if l1 == s:
        return (0, 2 * np.pi)
    # Otherwise, it's a rocker-crank, where l2 is not the full crank.
    return (np.pi/4, 3*np.pi/4)  # Placeholder range


class MechanismSimulator:
    """Simulates mechanism motion to generate motion curves."""

    def __init__(self, time_steps: int = 100):
        """
        Initializes the simulator.
        Args:
            time_steps: The number of time steps to simulate for one period.
        """
        self.time_steps = time_steps

    def simulate_mechanism(
        self, mech_type: MechanismType, parameters: np.ndarray
    ) -> MotionCurve:
        """
        Simulates the motion of a given mechanism type for one period.
        Args:
            mech_type: The type of mechanism to simulate.
            parameters: The numpy array of parameters for the mechanism.
        Returns:
            A MotionCurve object representing the generated path.
        """
        t = np.linspace(0, 2 * np.pi, self.time_steps)

        if mech_type == MechanismType.THREE_BAR:
            points = self._simulate_3bar(parameters, t)
        elif mech_type == MechanismType.FOUR_BAR:
            points = self._simulate_4bar(parameters, t)
        elif mech_type == MechanismType.CAM:
            points = self._simulate_cam(parameters, t)
        else:
            raise ValueError(f"Unknown mechanism type: {mech_type}")

        return MotionCurve(
            points=points,
            period=2 * np.pi,
            attachment_point=points[-1],  # Use end effector position as default
            parameter_vector=parameters,
        )

    def _simulate_3bar(self, params: np.ndarray, t: np.ndarray) -> np.ndarray:
        """
        Placeholder simulation for a three-bar linkage.
        Note: This is a simplified geometric approach, not a full physics-based simulation.
        Parameters are expected as [l1, l2, l3, theta0, omega].
        """
        if len(params) < 5:
            raise ValueError("3-bar simulation requires 5 parameters.")
        l1, l2, _, theta0, omega = params[:5]

        points = []
        for ti in t:
            theta1 = theta0 + omega * ti
            j1 = np.array([l1 * np.cos(theta1), l1 * np.sin(theta1)])
            # Simplified end effector calculation (not physically accurate)
            theta2 = theta1 + np.pi / 4
            end_effector = j1 + np.array([l2 * np.cos(theta2), l2 * np.sin(theta2)])
            points.append(end_effector)

        return np.array(points)

    def _simulate_4bar(self, params: np.ndarray, t: np.ndarray) -> np.ndarray:
        """
        Simulates a four-bar linkage using a numerical solver.
        Parameters: [l1, l2, l3, l4, p_x, p_y, theta0, omega]
        l1: ground link, l2: driver, l3: coupler, l4: follower
        (p_x, p_y): coupler point coordinates relative to the coupler link's frame.
        """
        if len(params) < 8:
            raise ValueError("4-bar simulation requires 8 parameters.")
        l1, l2, l3, l4, p_x, p_y, theta0, omega = params

        # Determine the valid angular range for the input crank
        min_angle, max_angle = get_4bar_input_angle_range(l1, l2, l3, l4)

        if max_angle == min_angle:
            return np.array([]) # Unmovable mechanism

        # Create the simulation angles array based on whether it's a crank or rocker
        if (max_angle - min_angle) >= (2 * np.pi * 0.99):  # Crank
            thetas = np.linspace(0, 2 * np.pi, self.time_steps)
        else:  # Rocker
            half_steps = self.time_steps // 2
            forward = np.linspace(min_angle, max_angle, half_steps)
            backward = np.linspace(max_angle, min_angle, self.time_steps - half_steps)
            thetas = np.concatenate([forward, backward])

        points = []
        # Initial guess for the angles [theta3, theta4]
        theta3_guess, theta4_guess = np.pi / 2, np.pi / 2

        for theta2 in thetas * omega + theta0:
            # Solve for theta3 and theta4
            solution, infodict, ier, mesg = fsolve(
                solve_4bar_closure,
                [theta3_guess, theta4_guess],
                args=(l1, l2, l3, l4, theta2),
                full_output=True,
            )

            if ier == 1:  # Solution found
                theta3, theta4 = solution

                # Update guess for next iteration to ensure continuity
                theta3_guess, theta4_guess = theta3, theta4

                # Calculate coupler point position
                x_a = l2 * np.cos(theta2)
                y_a = l2 * np.sin(theta2)
                x_p = x_a + p_x * np.cos(theta3) - p_y * np.sin(theta3)
                y_p = y_a + p_x * np.sin(theta3) + p_y * np.cos(theta3)
                points.append([x_p, y_p])
            else:
                # If solver fails, skip this point
                continue

        return np.array(points)

    def _simulate_cam(self, params: np.ndarray, t: np.ndarray) -> np.ndarray:
        """
        Placeholder simulation for a cam and follower mechanism.
        Parameters are expected as [base_radius, rise, offset].
        """
        if len(params) < 3:
            raise ValueError("Cam simulation requires 3 parameters.")
        base_radius, rise, offset = params[:3]

        # Assuming a simple translating follower along the y-axis
        # The follower displacement is determined by the cam's radius at a given angle.
        # This simulation assumes the parameters define the follower displacement directly,
        # which is what generate_comprehensive_dataset will now provide.

        angle = t
        # The "radius" here is actually the follower displacement.
        # The "rise" parameter scales the motion, and "base_radius" is the initial offset.
        displacement = base_radius + rise * (1 + np.sin(angle)) / 2

        points = np.zeros((len(t), 2))
        points[:, 1] = displacement + offset

        return points
