"""
Four-bar linkage mechanism implementation.
Provides complete kinematics simulation and validation.
"""

import logging
from typing import Any

import numpy as np

from ..interfaces.mechanism import MechanismInterface, MechanismParameters, SimulationData


class FourBarMechanism(MechanismInterface):
    """
    Four-bar linkage mechanism.

    Implements Grashof's criteria and full kinematic analysis.
    """

    def __init__(self, parameters: MechanismParameters):
        """Initialize four-bar mechanism."""
        self.parameters = parameters
        self.params = parameters.params

        # Extract link lengths and anchor positions
        self.p1 = np.array(self.params.get('anchor1', [0, 0]))
        self.p2 = np.array(self.params.get('anchor2', [100, 0]))
        self.l1 = np.linalg.norm(self.p2 - self.p1)  # Ground link
        self.l2 = self.params.get('l2', 40)  # Crank
        self.l3 = self.params.get('l3', 60)  # Coupler
        self.l4 = self.params.get('l4', 50)  # Rocker

        # Validate mechanism
        self._validate_grashof()

    def validate_parameters(self) -> tuple[bool, str | None]:
        """Validate mechanism parameters."""
        # Check for positive link lengths
        if any(l <= 0 for l in [self.l2, self.l3, self.l4]):
            return False, "All link lengths must be positive"

        # Check triangle inequality
        links = [self.l1, self.l2, self.l3, self.l4]
        for i in range(4):
            other_links = links[:i] + links[i+1:]
            if links[i] > sum(other_links):
                return False, f"Link {i+1} violates triangle inequality"

        # Check Grashof condition
        is_grashof, grashof_type = self._check_grashof_condition()

        return True, f"Valid {grashof_type} mechanism"

    def simulate(self, num_frames: int = 100) -> SimulationData:
        """Run four-bar simulation."""
        time_steps = np.linspace(0, 2*np.pi, num_frames)

        joint_positions = {
            'anchor1': np.tile(self.p1, (num_frames, 1)),
            'anchor2': np.tile(self.p2, (num_frames, 1)),
            'crank': [],
            'rocker': [],
            'coupler': []
        }

        link_orientations = {
            'crank': [],
            'coupler': [],
            'rocker': []
        }

        output_path = []

        for _i, theta in enumerate(time_steps):
            # Calculate crank position
            p3 = self.p1 + self.l2 * np.array([np.cos(theta), np.sin(theta)])

            # Solve for rocker position using circle-circle intersection
            p4 = self._solve_rocker_position(p3)

            if p4 is not None:
                # Calculate coupler point (midpoint or custom ratio)
                coupler_ratio = self.params.get('coupler_ratio', 0.5)
                p_coupler = p3 * (1 - coupler_ratio) + p4 * coupler_ratio

                joint_positions['crank'].append(p3)
                joint_positions['rocker'].append(p4)
                joint_positions['coupler'].append(p_coupler)

                # Calculate link orientations
                link_orientations['crank'].append(np.arctan2(p3[1] - self.p1[1], p3[0] - self.p1[0]))
                link_orientations['coupler'].append(np.arctan2(p4[1] - p3[1], p4[0] - p3[0]))
                link_orientations['rocker'].append(np.arctan2(p4[1] - self.p2[1], p4[0] - self.p2[0]))

                output_path.append(p_coupler)

        # Convert lists to arrays
        for key in ['crank', 'rocker', 'coupler']:
            if joint_positions[key]:
                joint_positions[key] = np.array(joint_positions[key])
            else:
                joint_positions[key] = np.empty((0, 2))

        for key in link_orientations:
            if link_orientations[key]:
                link_orientations[key] = np.array(link_orientations[key])
            else:
                link_orientations[key] = np.empty(0)

        return SimulationData(
            frames=num_frames,
            time_steps=time_steps,
            joint_positions=joint_positions,
            link_orientations=link_orientations,
            output_path=np.array(output_path) if output_path else None,
            metadata={
                'mechanism_type': 'four_bar',
                'grashof_type': self._check_grashof_condition()[1]
            }
        )

    def update_parameters(self, param_changes: dict[str, Any]) -> None:
        """Update mechanism parameters."""
        self.params.update(param_changes)

        # Update internal state
        if 'anchor1' in param_changes:
            self.p1 = np.array(param_changes['anchor1'])
        if 'anchor2' in param_changes:
            self.p2 = np.array(param_changes['anchor2'])

        self.l1 = np.linalg.norm(self.p2 - self.p1)

        if 'l2' in param_changes:
            self.l2 = param_changes['l2']
        if 'l3' in param_changes:
            self.l3 = param_changes['l3']
        if 'l4' in param_changes:
            self.l4 = param_changes['l4']

        # Re-validate
        self._validate_grashof()

    def get_key_points(self) -> dict[str, tuple[float, float]]:
        """Get key points for visualization."""
        return {
            'anchor1': tuple(self.p1),
            'anchor2': tuple(self.p2),
            'crank_length': self.l2,
            'coupler_length': self.l3,
            'rocker_length': self.l4
        }

    def get_constraints(self) -> dict[str, Any]:
        """Get mechanism constraints."""
        return {
            'min_link_length': 10,
            'max_link_length': 500,
            'grashof_condition': self._check_grashof_condition()[0],
            'workspace_bounds': self._calculate_workspace_bounds()
        }

    def calculate_output_motion(self, input_angle: float) -> dict[str, Any]:
        """Calculate output for given input."""
        # Calculate crank position
        p3 = self.p1 + self.l2 * np.array([np.cos(input_angle), np.sin(input_angle)])

        # Solve for rocker position
        p4 = self._solve_rocker_position(p3)

        if p4 is None:
            return {'valid': False, 'reason': 'No solution at this angle'}

        # Calculate rocker angle
        rocker_angle = np.arctan2(p4[1] - self.p2[1], p4[0] - self.p2[0])

        # Calculate coupler point
        coupler_ratio = self.params.get('coupler_ratio', 0.5)
        p_coupler = p3 * (1 - coupler_ratio) + p4 * coupler_ratio

        return {
            'valid': True,
            'crank_position': p3.tolist(),
            'rocker_position': p4.tolist(),
            'rocker_angle': rocker_angle,
            'coupler_position': p_coupler.tolist(),
            'mechanical_advantage': self._calculate_mechanical_advantage(input_angle)
        }

    @property
    def mechanism_type(self) -> str:
        """Get mechanism type."""
        return "four_bar"

    @property
    def degrees_of_freedom(self) -> int:
        """Get degrees of freedom."""
        return 1  # Single input (crank angle)

    def _solve_rocker_position(self, p3: np.ndarray) -> np.ndarray | None:
        """
        Solve for rocker position using circle-circle intersection.

        Args:
            p3: Crank joint position

        Returns:
            Rocker joint position or None if no solution
        """
        # Distance from p3 to p2
        d = np.linalg.norm(p3 - self.p2)

        # Check if solution exists
        if d > self.l3 + self.l4 or d < abs(self.l3 - self.l4):
            return None

        # Calculate angle for rocker
        a = (d*d + self.l4*self.l4 - self.l3*self.l3) / (2 * d * self.l4)
        a = np.clip(a, -1, 1)

        angle_offset = np.arccos(a)
        base_angle = np.arctan2(p3[1] - self.p2[1], p3[0] - self.p2[0])

        # Choose solution based on assembly mode
        assembly_mode = self.params.get('assembly_mode', 1)  # 1 or -1
        rocker_angle = base_angle + assembly_mode * angle_offset

        p4 = self.p2 + self.l4 * np.array([np.cos(rocker_angle), np.sin(rocker_angle)])

        return p4

    def _check_grashof_condition(self) -> tuple[bool, str]:
        """
        Check Grashof condition and determine mechanism type.

        Returns:
            Tuple of (is_grashof, mechanism_type)
        """
        links = sorted([self.l1, self.l2, self.l3, self.l4])
        s, p, q, l = links

        if s + l <= p + q:
            # Grashof mechanism
            if self.l1 == s:
                return True, "double-crank"
            elif self.l1 == l:
                return True, "double-rocker"
            else:
                return True, "crank-rocker"
        else:
            # Non-Grashof
            return False, "triple-rocker"

    def _validate_grashof(self) -> None:
        """Validate and log Grashof condition."""
        is_grashof, mech_type = self._check_grashof_condition()
        logging.info(f"[4BAR] {mech_type} mechanism (Grashof: {is_grashof})")

    def _calculate_workspace_bounds(self) -> dict[str, float]:
        """Calculate mechanism workspace bounds."""
        # Maximum reach
        max_reach = self.l2 + self.l3

        # Minimum reach (depends on configuration)
        abs(self.l2 - self.l3)

        return {
            'min_x': min(self.p1[0], self.p2[0]) - max_reach,
            'max_x': max(self.p1[0], self.p2[0]) + max_reach,
            'min_y': min(self.p1[1], self.p2[1]) - max_reach,
            'max_y': max(self.p1[1], self.p2[1]) + max_reach
        }

    def _calculate_mechanical_advantage(self, input_angle: float) -> float:
        """Calculate instantaneous mechanical advantage."""
        # Simplified calculation - ratio of output to input angular velocity
        # Would need velocity analysis for accurate calculation
        return self.l2 / self.l4
