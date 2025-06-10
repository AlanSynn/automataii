import numpy as np
from automataii.kinematics.mechanism import MechanismType, MotionCurve


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
        Simulates a four-bar linkage using Freudenstein's equation.
        Parameters: [l1, l2, l3, l4, p_x, p_y, theta0, omega]
        l1: ground link, l2: driver, l3: coupler, l4: follower
        (p_x, p_y): coupler point coordinates relative to the coupler link's frame.
        """
        if len(params) < 8:
            raise ValueError("4-bar simulation requires 8 parameters.")
        l1, l2, l3, l4, p_x, p_y, theta0, omega = params

        points = []
        for theta2 in t * omega + theta0:
            # Freudenstein's equation for theta4
            k1 = l1 / l2
            k2 = l1 / l4
            k3 = (l1**2 + l2**2 - l3**2 + l4**2) / (2 * l2 * l4)

            a = k3 - k1 * np.cos(theta2) - np.cos(theta2)
            b = -2 * np.sin(theta2)
            c = k3 - (k1 + 1) * np.cos(theta2)

            # Solve for theta4
            discriminant = b**2 - 4 * a * c
            if discriminant < 0:
                continue  # No real solution, invalid configuration

            # Two possible solutions for theta4, choose one consistently
            tan_theta4_half_1 = (-b + np.sqrt(discriminant)) / (2 * a)
            theta4 = 2 * np.arctan(tan_theta4_half_1)

            # Calculate theta3
            x_a = l2 * np.cos(theta2)
            y_a = l2 * np.sin(theta2)
            x_b = l1 + l4 * np.cos(theta4)
            y_b = l4 * np.sin(theta4)

            delta_x = x_b - x_a
            delta_y = y_b - y_a
            theta3 = np.arctan2(delta_y, delta_x)

            # Calculate coupler point position
            x_p = x_a + p_x * np.cos(theta3) - p_y * np.sin(theta3)
            y_p = y_a + p_x * np.sin(theta3) + p_y * np.cos(theta3)

            points.append([x_p, y_p])

        return np.array(points)

    def _simulate_cam(self, params: np.ndarray, t: np.ndarray) -> np.ndarray:
        """
        Placeholder simulation for a cam and follower mechanism.
        Parameters are expected as [base_radius, rise, offset].
        """
        if len(params) < 3:
            raise ValueError("Cam simulation requires 3 parameters.")
        base_radius, rise, offset = params[:3]

        angle = t
        radius = base_radius + rise * (1 + np.sin(angle)) / 2

        # Assuming a simple translating follower along the y-axis
        points = np.zeros((len(t), 2))
        points[:, 1] = radius + offset

        return points
