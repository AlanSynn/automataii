"""Kinematics analysis for mechanism position, velocity, and acceleration."""

from ..utils.vector_ops import get_sum


class KinematicsAnalyzer:
    """Analyzer for fixing position, velocity, and acceleration of mechanism."""

    def __init__(self, origin, positions, velocities, accelerations, joints):
        """
        Initialize the kinematics analyzer.

        Parameters
        ----------
        origin : Joint
            The origin joint of the mechanism.
        positions : list
            List of position vectors.
        velocities : list
            List of velocity vectors.
        accelerations : list
            List of acceleration vectors.
        joints : list
            List of all joints in the mechanism.
        """
        self.origin = origin
        self.positions = positions
        self.velocities = velocities
        self.accelerations = accelerations
        self.joints = joints

    def fix_position(self):
        """Calculate the x, y, and z components of all vectors."""
        origin = self.origin
        origin._fix_position(0, 0, 0)

        attached_to_origin = []
        vectors = self.positions[:]

        # Find vectors directly attached to origin
        for v in vectors:
            if v.joints[0] == origin:
                v._fix_global_position()
                attached_to_origin.append(v)
            elif v.joints[1] == origin:
                v_rev = v._reverse()
                v_rev._fix_global_position()
                attached_to_origin.append(v)

        for v in attached_to_origin:
            vectors.remove(v)

        # Iteratively fix remaining vectors
        counter = 0
        while not self._position_is_fixed():
            for v in vectors:
                if self._position_is_fixed():
                    break
                for r in attached_to_origin:
                    sum_ = get_sum(r, v)
                    if sum_:
                        attached_to_origin.append(sum_)
                        sum_._fix_global_position()
                        break
            counter += 1
            if counter > 10:
                raise Exception(
                    "Not all position vectors are able to be fixed to origin. "
                    "Are all joints linked?"
                )

    def fix_velocity(self):
        """Calculate the x, y, and z velocity components of all vectors."""
        origin = self.origin
        origin._fix_velocity(0, 0, 0)

        attached_to_origin = []
        vectors = self.velocities[:]

        # Find vectors directly attached to origin
        for v in vectors:
            if v.joints[0] == origin:
                v._fix_global_velocity()
                attached_to_origin.append(v)
            elif v.joints[1] == origin:
                v_rev = v._reverse()
                v_rev._fix_global_velocity()
                attached_to_origin.append(v)

        for v in attached_to_origin:
            vectors.remove(v)

        # Iteratively fix remaining vectors
        counter = 0
        while not self._velocity_is_fixed():
            for v in vectors:
                if self._velocity_is_fixed():
                    break
                for r in attached_to_origin:
                    sum_ = get_sum(r, v)
                    if sum_:
                        attached_to_origin.append(sum_)
                        sum_._fix_global_velocity()
                        break
            counter += 1
            if counter > 10:
                raise Exception(
                    "Not all velocity vectors are able to be fixed to origin. "
                    "Are all joints linked?"
                )

    def fix_acceleration(self):
        """Calculate the x, y, and z acceleration components of all vectors."""
        origin = self.origin
        origin._fix_acceleration(0, 0, 0)

        attached_to_origin = []
        vectors = self.accelerations[:]

        # Find vectors directly attached to origin
        for v in vectors:
            if v.joints[0] == origin:
                v._fix_global_acceleration()
                attached_to_origin.append(v)
            elif v.joints[1] == origin:
                v_rev = v._reverse()
                v_rev._fix_global_acceleration()
                attached_to_origin.append(v)

        for v in attached_to_origin:
            vectors.remove(v)

        # Iteratively fix remaining vectors
        counter = 0
        while not self._acceleration_is_fixed():
            for v in vectors:
                if self._acceleration_is_fixed():
                    break
                for r in attached_to_origin:
                    sum_ = get_sum(r, v)
                    if sum_:
                        attached_to_origin.append(sum_)
                        sum_._fix_global_acceleration()
                        break
            counter += 1
            if counter > 10:
                raise Exception(
                    "Not all acceleration vectors are able to be fixed to origin. "
                    "Are all joints linked?"
                )

    def _position_is_fixed(self):
        """Check if all joint positions are fixed."""
        for joint in self.joints:
            if not joint._position_is_fixed():
                return False
        return True

    def _velocity_is_fixed(self):
        """Check if all joint velocities are fixed."""
        for joint in self.joints:
            if not joint._velocity_is_fixed():
                return False
        return True

    def _acceleration_is_fixed(self):
        """Check if all joint accelerations are fixed."""
        for joint in self.joints:
            if not joint._acceleration_is_fixed():
                return False
        return True