"""Factory functions for creating mechanism components."""

from ..core.joint import Joint


def get_joints(names):
    """
    Create a list of Joint objects from a space-separated string of names.

    Parameters
    ----------
    names : str
        A string with the joint names separated by spaces.

    Returns
    -------
    list
        A list of Joint objects.
    """
    return [Joint(ch) for ch in names.split()]