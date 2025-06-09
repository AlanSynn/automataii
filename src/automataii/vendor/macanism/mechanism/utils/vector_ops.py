"""Vector operation utilities for mechanism analysis."""


def get_sum(v1, v2):
    """
    Return the sum of two vectors when properly connected.
    
    This function returns the sum of two vectors. It will reverse the vector(s) 
    in such a way that it only sums the two when the head of v1 is attached to 
    the tail of v2.

    Parameters
    ----------
    v1 : Vector
        The vector that is attached to the origin (the tail does not have to be 
        the origin of the mechanism).
    v2 : Vector
        A vector that has a common joint with v1.

    Returns
    -------
    Vector or None
        A Vector object sum of v1 and v2. If there are no common joints between 
        the two, then it returns None.
    """
    j1, j2 = v1.joints
    j3, j4 = v2.joints

    if j2 == j3:
        return v1 + v2
    elif j1 == j3:
        return v1._reverse() + v2
    elif j1 == j4:
        return v1._reverse() + v2._reverse()
    elif j2 == j4:
        return v1 + v2._reverse()
    return None