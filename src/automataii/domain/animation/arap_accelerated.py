"""
Accelerated ARAP (As-Rigid-As-Possible) Deformation.

This module provides accelerated implementations of the ARAP solve step
with graceful fallback:

1. Native (C++ via pybind11) - fastest, if available
2. Numba JIT - fast, if numba is installed
3. NumPy vectorized - baseline, always available

Architecture: Domain Layer (Pure computation, no UI dependencies)

Time Complexity:
- compute_rotation_matrices: O(E) where E = number of edges
- batch_transform_points: O(N) where N = number of points
- AcceleratedARAP.solve: O(V^2) dominated by sparse solve

Author: Automataii Contributors
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Literal

import numpy as np
import scipy.sparse.linalg as spla

if TYPE_CHECKING:
    import numpy.typing as npt

logger = logging.getLogger(__name__)

# Backend detection
_BACKEND: Literal["native", "numba", "numpy"] | None = None


def get_backend() -> Literal["native", "numba", "numpy"]:
    """
    Detect and return the best available backend.

    Returns:
        "native" if pybind11 extension is available
        "numba" if numba is installed
        "numpy" otherwise
    """
    global _BACKEND

    if _BACKEND is not None:
        return _BACKEND

    # Try native extension first
    try:
        from automataii.native import arap_native  # type: ignore[import-not-found]  # noqa: F401

        _BACKEND = "native"
        logger.info("ARAP acceleration: using native (C++) backend")
        return _BACKEND
    except ImportError:
        pass

    # Try numba
    try:
        import numba  # noqa: F401

        _BACKEND = "numba"
        logger.info("ARAP acceleration: using numba backend")
        return _BACKEND
    except ImportError:
        pass

    # Fallback to numpy
    _BACKEND = "numpy"
    logger.info("ARAP acceleration: using numpy backend (consider installing numba for better performance)")
    return _BACKEND


# =============================================================================
# NUMPY IMPLEMENTATIONS (Baseline - Always Available)
# =============================================================================


def _compute_rotation_matrices_numpy(
    edge_vectors: npt.NDArray[np.float64],
    T1: npt.NDArray[np.float64],
) -> npt.NDArray[np.float64]:
    """
    Compute rotation matrices using vectorized NumPy operations.

    This replaces the Python loop in ARAP.solve() with vectorized operations.

    Args:
        edge_vectors: (E, 2) array of edge vectors
        T1: (2*E,) array of rotation parameters [c0, s0, c1, s1, ...]

    Returns:
        (E, 2) array of rotated edge vectors

    Time Complexity: O(E)
    """
    num_edges = len(edge_vectors)

    # Extract c and s components (interleaved in T1)
    c = T1[0::2]  # Even indices: c0, c1, c2, ...
    s = T1[1::2]  # Odd indices: s0, s1, s2, ...

    # Normalize to unit rotation (vectorized)
    scale = 1.0 / np.sqrt(c * c + s * s)
    c = c * scale
    s = s * scale

    # Apply rotation matrix to each edge vector (vectorized)
    # For rotation matrix [[c, s], [-s, c]], the result is:
    # [c*x + s*y, -s*x + c*y]
    result = np.empty((num_edges, 2), dtype=np.float64)
    result[:, 0] = c * edge_vectors[:, 0] + s * edge_vectors[:, 1]
    result[:, 1] = -s * edge_vectors[:, 0] + c * edge_vectors[:, 1]

    return result


def _batch_transform_points_numpy(
    points: npt.NDArray[np.float64],
    scale: float,
    offset_x: float,
    offset_y: float,
    flip_y: bool = True,
) -> npt.NDArray[np.float64]:
    """
    Batch transform points from local to scene coordinates.

    This replaces per-point function calls with vectorized operations.

    Args:
        points: (N, 2) array of points in local coordinates
        scale: Scale factor
        offset_x: X offset after scaling
        offset_y: Y offset after scaling
        flip_y: If True, flip Y axis (common for screen coordinates)

    Returns:
        (N, 2) array of points in scene coordinates

    Time Complexity: O(N)
    """
    result = np.empty_like(points)
    result[:, 0] = points[:, 0] * scale + offset_x

    if flip_y:
        result[:, 1] = -points[:, 1] * scale + offset_y
    else:
        result[:, 1] = points[:, 1] * scale + offset_y

    return result


# =============================================================================
# NUMBA IMPLEMENTATIONS (Optional - Faster if Available)
# =============================================================================


def _get_numba_functions() -> tuple | None:
    """
    Get numba-accelerated functions if available.

    Returns:
        Tuple of (compute_rotation_matrices, batch_transform_points) or None
    """
    try:
        from numba import njit, prange

        @njit(cache=True, fastmath=True, parallel=True)
        def compute_rotation_matrices_numba(
            edge_vectors: npt.NDArray[np.float64],
            T1: npt.NDArray[np.float64],
        ) -> npt.NDArray[np.float64]:
            num_edges = len(edge_vectors)
            result = np.empty((num_edges, 2), dtype=np.float64)

            for idx in prange(num_edges):
                c = T1[2 * idx]
                s = T1[2 * idx + 1]
                scale = 1.0 / np.sqrt(c * c + s * s)
                c = c * scale
                s = s * scale

                e0_x = edge_vectors[idx, 0]
                e0_y = edge_vectors[idx, 1]

                result[idx, 0] = c * e0_x + s * e0_y
                result[idx, 1] = -s * e0_x + c * e0_y

            return result

        @njit(cache=True, fastmath=True, parallel=True)
        def batch_transform_points_numba(
            points: npt.NDArray[np.float64],
            scale: float,
            offset_x: float,
            offset_y: float,
            flip_y: bool,
        ) -> npt.NDArray[np.float64]:
            n = len(points)
            result = np.empty((n, 2), dtype=np.float64)

            for i in prange(n):
                result[i, 0] = points[i, 0] * scale + offset_x
                if flip_y:
                    result[i, 1] = -points[i, 1] * scale + offset_y
                else:
                    result[i, 1] = points[i, 1] * scale + offset_y

            return result

        return (compute_rotation_matrices_numba, batch_transform_points_numba)

    except ImportError:
        return None


# =============================================================================
# PUBLIC API (Auto-selects best backend)
# =============================================================================


def compute_rotation_matrices(
    edge_vectors: npt.NDArray[np.float64],
    T1: npt.NDArray[np.float64],
) -> npt.NDArray[np.float64]:
    """
    Compute rotation matrices for ARAP solve step.

    Automatically uses the best available backend (native > numba > numpy).

    Args:
        edge_vectors: (E, 2) array of original edge vectors
        T1: (2*E,) array of rotation parameters from first solve

    Returns:
        (E, 2) array of rotated edge vectors (b2_top in ARAP.solve)

    Time Complexity: O(E) where E = number of edges
    """
    backend = get_backend()

    if backend == "native":
        from automataii.native import arap_native  # type: ignore[import-not-found]

        return arap_native.compute_rotation_matrices(edge_vectors, T1)

    if backend == "numba":
        numba_funcs = _get_numba_functions()
        if numba_funcs is not None:
            return numba_funcs[0](edge_vectors, T1)

    return _compute_rotation_matrices_numpy(edge_vectors, T1)


def batch_transform_points(
    points: npt.NDArray[np.float64],
    scale: float,
    offset_x: float,
    offset_y: float,
    flip_y: bool = True,
) -> npt.NDArray[np.float64]:
    """
    Batch transform points from local to scene coordinates.

    Automatically uses the best available backend.

    Args:
        points: (N, 2) array of points
        scale: Scale factor
        offset_x: X offset
        offset_y: Y offset
        flip_y: Whether to flip Y axis

    Returns:
        (N, 2) array of transformed points

    Time Complexity: O(N) where N = number of points
    """
    backend = get_backend()

    if backend == "native":
        from automataii.native import arap_native  # type: ignore[import-not-found]

        return arap_native.batch_transform_points(points, scale, offset_x, offset_y, flip_y)

    if backend == "numba":
        numba_funcs = _get_numba_functions()
        if numba_funcs is not None:
            return numba_funcs[1](points, scale, offset_x, offset_y, flip_y)

    return _batch_transform_points_numpy(points, scale, offset_x, offset_y, flip_y)


# =============================================================================
# ACCELERATED ARAP SOLVER
# =============================================================================


class AcceleratedARAP:
    """
    Accelerated ARAP solver with identical API to original ARAP class.

    This is a drop-in replacement that uses accelerated rotation matrix
    computation while delegating sparse solves to scipy.

    Usage:
        solver = AcceleratedARAP(pins_xy, triangles, vertices)
        new_vertices = solver.solve(new_pin_positions)

    Performance:
        - Initialization: Same as original ARAP (one-time cost)
        - Solve: 2-10x faster on the rotation matrix step
    """

    def __init__(
        self,
        pins_xy: npt.NDArray[np.float32],
        triangles: list[npt.NDArray[np.int32]],
        vertices: npt.NDArray[np.float32],
        w: int = 1000,
    ):
        """
        Initialize the accelerated ARAP solver.

        Args:
            pins_xy: (N, 2) initial pin positions
            triangles: List of (3,) arrays with vertex indices
            vertices: (V, 2) vertex positions
            w: Weight for pin constraints (default 1000)
        """
        # Import original ARAP for initialization
        from automataii.domain.animation.arap import ARAP

        # Use original ARAP for matrix setup
        self._original = ARAP(pins_xy, triangles, vertices, w)

        # Cache frequently accessed attributes
        self.edge_vectors = self._original.edge_vectors.astype(np.float64)
        self.w = self._original.w
        self.edge_num = self._original.edge_num
        self.pin_num = self._original.pin_num
        self.pin_mask = self._original.pin_mask

        # Sparse matrices for solve
        self.tA1xA1 = self._original.tA1xA1
        self.tA1 = self._original.tA1
        self.G = self._original.G
        self.tA2xA2 = self._original.tA2xA2
        self.tA2 = self._original.tA2

        logger.debug(f"AcceleratedARAP initialized with {self.edge_num} edges, backend={get_backend()}")

    def solve(self, pins_xy_: npt.NDArray[np.float32]) -> npt.NDArray[np.float64]:
        """
        Solve ARAP with new pin positions.

        Args:
            pins_xy_: (N, 2) new pin positions

        Returns:
            (V, 2) updated vertex positions

        Time Complexity: O(V^2) dominated by sparse linear solve
        """
        # Filter pins by mask
        pins_xy: npt.NDArray[np.float32] = pins_xy_[self.pin_mask]

        assert len(pins_xy) == self.pin_num

        # First solve (same as original)
        b1: npt.NDArray[np.float64] = np.hstack([
            np.zeros([2 * self.edge_num], dtype=np.float64),
            self.w * pins_xy.reshape([-1]),
        ])
        v1: npt.NDArray[np.float64] = spla.spsolve(self.tA1xA1, self.tA1 @ b1.T)

        # Compute rotation matrices (ACCELERATED)
        T1: npt.NDArray[np.float64] = self.G @ v1
        b2_top = compute_rotation_matrices(self.edge_vectors, T1)

        # Second solve (same as original)
        b2 = np.vstack([b2_top, self.w * pins_xy])
        b2x = b2[:, 0]
        b2y = b2[:, 1]

        v2x: npt.NDArray[np.float64] = spla.spsolve(self.tA2xA2, self.tA2 @ b2x)
        v2y: npt.NDArray[np.float64] = spla.spsolve(self.tA2xA2, self.tA2 @ b2y)

        return np.vstack((v2x, v2y)).T
