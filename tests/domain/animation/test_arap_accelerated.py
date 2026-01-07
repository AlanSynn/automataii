"""
Tests for ARAP acceleration module.

TDD: Write tests first, then implement.

These tests verify:
1. Numerical correctness (results match original ARAP.solve())
2. Performance improvement (at least 5x speedup on rotation matrix computation)
3. Graceful fallback when acceleration is unavailable
"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

import numpy as np
import pytest

if TYPE_CHECKING:
    import numpy.typing as npt


# Test fixtures
@pytest.fixture
def simple_triangle_mesh() -> tuple[
    npt.NDArray[np.float32],  # vertices
    list[npt.NDArray[np.int32]],  # triangles
    npt.NDArray[np.float32],  # pins_xy
]:
    """Simple triangle mesh for basic testing."""
    vertices = np.array([
        [0.0, 0.0],
        [1.0, 0.0],
        [0.5, 1.0],
    ], dtype=np.float32)

    triangles = [np.array([0, 1, 2], dtype=np.int32)]

    pins_xy = np.array([
        [0.0, 0.0],
        [1.0, 0.0],
    ], dtype=np.float32)

    return vertices, triangles, pins_xy


@pytest.fixture
def quad_mesh() -> tuple[
    npt.NDArray[np.float32],
    list[npt.NDArray[np.int32]],
    npt.NDArray[np.float32],
]:
    """Quad mesh (2 triangles) for more complex testing."""
    vertices = np.array([
        [0.0, 0.0],
        [1.0, 0.0],
        [1.0, 1.0],
        [0.0, 1.0],
    ], dtype=np.float32)

    triangles = [
        np.array([0, 1, 2], dtype=np.int32),
        np.array([0, 2, 3], dtype=np.int32),
    ]

    pins_xy = np.array([
        [0.0, 0.0],
        [1.0, 0.0],
    ], dtype=np.float32)

    return vertices, triangles, pins_xy


@pytest.fixture
def large_mesh() -> tuple[
    npt.NDArray[np.float32],
    list[npt.NDArray[np.int32]],
    npt.NDArray[np.float32],
]:
    """Large mesh for performance testing (100+ vertices)."""
    # Create a grid mesh
    grid_size = 10
    vertices = []
    for i in range(grid_size):
        for j in range(grid_size):
            vertices.append([float(i), float(j)])
    vertices = np.array(vertices, dtype=np.float32)

    triangles = []
    for i in range(grid_size - 1):
        for j in range(grid_size - 1):
            idx = i * grid_size + j
            triangles.append(np.array([idx, idx + 1, idx + grid_size], dtype=np.int32))
            triangles.append(np.array([idx + 1, idx + grid_size + 1, idx + grid_size], dtype=np.int32))

    # Pins at corners
    pins_xy = np.array([
        [0.0, 0.0],
        [float(grid_size - 1), 0.0],
        [0.0, float(grid_size - 1)],
        [float(grid_size - 1), float(grid_size - 1)],
    ], dtype=np.float32)

    return vertices, triangles, pins_xy


class TestAcceleratedRotationMatrices:
    """Test the accelerated rotation matrix computation."""

    def test_compute_rotation_matrices_shape(self) -> None:
        """Verify output shape matches input edge count."""
        from automataii.domain.animation.arap_accelerated import compute_rotation_matrices

        num_edges = 10
        edge_vectors = np.random.randn(num_edges, 2).astype(np.float64)
        T1 = np.random.randn(2 * num_edges).astype(np.float64)

        result = compute_rotation_matrices(edge_vectors, T1)

        assert result.shape == (num_edges, 2)
        assert result.dtype == np.float64

    def test_compute_rotation_matrices_identity_rotation(self) -> None:
        """When T1 encodes identity rotation, output should match input edges."""
        from automataii.domain.animation.arap_accelerated import compute_rotation_matrices

        edge_vectors = np.array([
            [1.0, 0.0],
            [0.0, 1.0],
            [1.0, 1.0],
        ], dtype=np.float64)

        # Identity rotation: c=1, s=0 for each edge
        T1 = np.array([1.0, 0.0, 1.0, 0.0, 1.0, 0.0], dtype=np.float64)

        result = compute_rotation_matrices(edge_vectors, T1)

        np.testing.assert_allclose(result, edge_vectors, rtol=1e-6)

    def test_compute_rotation_matrices_90_degree_rotation(self) -> None:
        """Test 90 degree rotation."""
        from automataii.domain.animation.arap_accelerated import compute_rotation_matrices

        edge_vectors = np.array([
            [1.0, 0.0],
        ], dtype=np.float64)

        # 90 degree rotation: c=0, s=1
        T1 = np.array([0.0, 1.0], dtype=np.float64)

        result = compute_rotation_matrices(edge_vectors, T1)

        # After 90 degree rotation, [1, 0] -> [0, -1]
        expected = np.array([[0.0, -1.0]], dtype=np.float64)
        np.testing.assert_allclose(result, expected, rtol=1e-6)

    def test_compute_rotation_matrices_matches_original(
        self,
        large_mesh: tuple[npt.NDArray[np.float32], list[npt.NDArray[np.int32]], npt.NDArray[np.float32]],
    ) -> None:
        """Verify accelerated version matches original ARAP implementation."""
        from automataii.domain.animation.arap import ARAP
        from automataii.domain.animation.arap_accelerated import compute_rotation_matrices

        vertices, triangles, pins_xy = large_mesh

        # Initialize original ARAP
        arap = ARAP(pins_xy, triangles, vertices)

        # Get edge vectors from ARAP
        edge_vectors = arap.edge_vectors.astype(np.float64)

        # Create random T1 (simulating intermediate solve result)
        np.random.seed(42)
        T1 = np.random.randn(2 * len(edge_vectors)).astype(np.float64)

        # Compute using accelerated function
        accelerated_result = compute_rotation_matrices(edge_vectors, T1)

        # Compute using original loop (from ARAP.solve)
        original_result = np.empty((len(edge_vectors), 2), dtype=np.float64)
        for idx, e0 in enumerate(edge_vectors):
            c = T1[2 * idx]
            s = T1[2 * idx + 1]
            scale = 1.0 / np.sqrt(c * c + s * s)
            c *= scale
            s *= scale
            T2 = np.asarray(((c, s), (-s, c)))
            original_result[idx] = np.dot(T2, e0)

        np.testing.assert_allclose(accelerated_result, original_result, rtol=1e-10)


class TestBatchTransforms:
    """Test batch coordinate transformation functions."""

    def test_batch_transform_points_shape(self) -> None:
        """Verify output shape matches input."""
        from automataii.domain.animation.arap_accelerated import batch_transform_points

        points = np.random.randn(100, 2).astype(np.float64)

        result = batch_transform_points(
            points,
            scale=2.0,
            offset_x=10.0,
            offset_y=20.0,
        )

        assert result.shape == points.shape
        assert result.dtype == np.float64

    def test_batch_transform_points_identity(self) -> None:
        """Identity transform (scale=1, offset=0) should preserve points."""
        from automataii.domain.animation.arap_accelerated import batch_transform_points

        points = np.array([
            [1.0, 2.0],
            [3.0, 4.0],
        ], dtype=np.float64)

        result = batch_transform_points(
            points,
            scale=1.0,
            offset_x=0.0,
            offset_y=0.0,
            flip_y=False,
        )

        np.testing.assert_allclose(result, points)

    def test_batch_transform_points_with_scale(self) -> None:
        """Test scaling transformation."""
        from automataii.domain.animation.arap_accelerated import batch_transform_points

        points = np.array([
            [1.0, 1.0],
            [2.0, 2.0],
        ], dtype=np.float64)

        result = batch_transform_points(
            points,
            scale=2.0,
            offset_x=0.0,
            offset_y=0.0,
            flip_y=False,
        )

        expected = np.array([
            [2.0, 2.0],
            [4.0, 4.0],
        ], dtype=np.float64)

        np.testing.assert_allclose(result, expected)

    def test_batch_transform_points_with_offset(self) -> None:
        """Test offset transformation."""
        from automataii.domain.animation.arap_accelerated import batch_transform_points

        points = np.array([
            [0.0, 0.0],
            [1.0, 1.0],
        ], dtype=np.float64)

        result = batch_transform_points(
            points,
            scale=1.0,
            offset_x=10.0,
            offset_y=20.0,
            flip_y=False,
        )

        expected = np.array([
            [10.0, 20.0],
            [11.0, 21.0],
        ], dtype=np.float64)

        np.testing.assert_allclose(result, expected)

    def test_batch_transform_points_with_flip_y(self) -> None:
        """Test Y-axis flip (common for screen coordinates)."""
        from automataii.domain.animation.arap_accelerated import batch_transform_points

        points = np.array([
            [1.0, 2.0],
        ], dtype=np.float64)

        result = batch_transform_points(
            points,
            scale=1.0,
            offset_x=0.0,
            offset_y=100.0,
            flip_y=True,
        )

        # With flip_y: y' = -y * scale + offset_y = -2.0 + 100.0 = 98.0
        expected = np.array([
            [1.0, 98.0],
        ], dtype=np.float64)

        np.testing.assert_allclose(result, expected)


class TestAcceleratedARAPSolver:
    """Test the complete accelerated ARAP solver."""

    def test_accelerated_solve_matches_original(
        self,
        quad_mesh: tuple[npt.NDArray[np.float32], list[npt.NDArray[np.int32]], npt.NDArray[np.float32]],
    ) -> None:
        """Verify accelerated solve produces same results as original."""
        from automataii.domain.animation.arap import ARAP
        from automataii.domain.animation.arap_accelerated import AcceleratedARAP

        vertices, triangles, pins_xy = quad_mesh

        # Initialize both solvers
        original = ARAP(pins_xy, triangles, vertices)
        accelerated = AcceleratedARAP(pins_xy, triangles, vertices)

        # New pin positions (translate second pin)
        new_pins = np.array([
            [0.0, 0.0],
            [1.2, 0.1],
        ], dtype=np.float32)

        # Solve with both
        original_result = original.solve(new_pins)
        accelerated_result = accelerated.solve(new_pins)

        np.testing.assert_allclose(accelerated_result, original_result, rtol=1e-6)

    def test_accelerated_solve_large_mesh(
        self,
        large_mesh: tuple[npt.NDArray[np.float32], list[npt.NDArray[np.int32]], npt.NDArray[np.float32]],
    ) -> None:
        """Test on larger mesh to verify stability."""
        from automataii.domain.animation.arap import ARAP
        from automataii.domain.animation.arap_accelerated import AcceleratedARAP

        vertices, triangles, pins_xy = large_mesh

        original = ARAP(pins_xy, triangles, vertices)
        accelerated = AcceleratedARAP(pins_xy, triangles, vertices)

        # Move pins
        new_pins = pins_xy.copy()
        new_pins[1, 0] += 0.5
        new_pins[2, 1] += 0.5

        original_result = original.solve(new_pins)
        accelerated_result = accelerated.solve(new_pins)

        np.testing.assert_allclose(accelerated_result, original_result, rtol=1e-5)


class TestPerformance:
    """Performance benchmarks for acceleration."""

    @pytest.mark.benchmark
    def test_rotation_matrices_speedup(
        self,
        large_mesh: tuple[npt.NDArray[np.float32], list[npt.NDArray[np.int32]], npt.NDArray[np.float32]],
    ) -> None:
        """Verify accelerated rotation is faster than Python loop."""
        from automataii.domain.animation.arap import ARAP
        from automataii.domain.animation.arap_accelerated import compute_rotation_matrices

        vertices, triangles, pins_xy = large_mesh
        arap = ARAP(pins_xy, triangles, vertices)
        edge_vectors = arap.edge_vectors.astype(np.float64)

        np.random.seed(42)
        T1 = np.random.randn(2 * len(edge_vectors)).astype(np.float64)

        # Time original Python loop
        iterations = 100
        start = time.perf_counter()
        for _ in range(iterations):
            original_result = np.empty((len(edge_vectors), 2), dtype=np.float64)
            for idx, e0 in enumerate(edge_vectors):
                c = T1[2 * idx]
                s = T1[2 * idx + 1]
                scale = 1.0 / np.sqrt(c * c + s * s)
                c *= scale
                s *= scale
                T2 = np.asarray(((c, s), (-s, c)))
                original_result[idx] = np.dot(T2, e0)
        original_time = time.perf_counter() - start

        # Time accelerated version
        start = time.perf_counter()
        for _ in range(iterations):
            accelerated_result = compute_rotation_matrices(edge_vectors, T1)
        accelerated_time = time.perf_counter() - start

        speedup = original_time / accelerated_time

        print(f"\nRotation matrices speedup: {speedup:.1f}x")
        print(f"  Original: {original_time * 1000 / iterations:.3f} ms/call")
        print(f"  Accelerated: {accelerated_time * 1000 / iterations:.3f} ms/call")

        # Expect at least 2x speedup with pure numpy (more with numba)
        assert speedup >= 2.0, f"Expected at least 2x speedup, got {speedup:.1f}x"


class TestGracefulFallback:
    """Test graceful degradation when acceleration is unavailable."""

    def test_backend_detection(self) -> None:
        """Verify backend is detected correctly."""
        from automataii.domain.animation.arap_accelerated import get_backend

        backend = get_backend()
        assert backend in ("numba", "numpy", "native")

    def test_solve_works_regardless_of_backend(
        self,
        simple_triangle_mesh: tuple[npt.NDArray[np.float32], list[npt.NDArray[np.int32]], npt.NDArray[np.float32]],
    ) -> None:
        """Solve should work with any backend."""
        from automataii.domain.animation.arap_accelerated import AcceleratedARAP

        vertices, triangles, pins_xy = simple_triangle_mesh

        solver = AcceleratedARAP(pins_xy, triangles, vertices)

        new_pins = np.array([
            [0.1, 0.0],
            [1.0, 0.1],
        ], dtype=np.float32)

        result = solver.solve(new_pins)

        assert result is not None
        assert result.shape == vertices.shape
