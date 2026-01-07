"""
Tests for OpenGL rendering backend.

TDD: Write tests first, then implement.

These tests verify:
1. OpenGL context creation
2. Shader compilation
3. Vertex buffer management
4. Batch rendering performance
5. Fallback to software rendering

Note: Some tests require a display and may be skipped in headless CI.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

import numpy as np
import pytest

if TYPE_CHECKING:
    import numpy.typing as npt

# Skip all tests if running in headless environment
pytestmark = pytest.mark.skipif(
    os.environ.get("CI") == "true" or os.environ.get("DISPLAY") is None,
    reason="OpenGL tests require display"
)


# =============================================================================
# GEOMETRY BUFFER TESTS
# =============================================================================


class TestGeometryBuffer:
    """Test the geometry buffer for batched rendering."""

    def test_buffer_creation(self) -> None:
        """Buffer should be creatable with a capacity."""
        from automataii.presentation.qt.animation.opengl_renderer import GeometryBuffer

        buffer = GeometryBuffer(max_vertices=1000, max_indices=3000)
        assert buffer.max_vertices == 1000
        assert buffer.max_indices == 3000

    def test_add_line(self) -> None:
        """Should be able to add lines to the buffer."""
        from automataii.presentation.qt.animation.opengl_renderer import GeometryBuffer

        buffer = GeometryBuffer(max_vertices=100, max_indices=100)

        buffer.add_line(
            start=(0.0, 0.0),
            end=(1.0, 1.0),
            color=(1.0, 0.0, 0.0, 1.0),
            width=2.0,
        )

        assert buffer.vertex_count > 0

    def test_add_circle(self) -> None:
        """Should be able to add circles to the buffer."""
        from automataii.presentation.qt.animation.opengl_renderer import GeometryBuffer

        buffer = GeometryBuffer(max_vertices=200, max_indices=300)

        buffer.add_circle(
            center=(0.0, 0.0),
            radius=10.0,
            color=(0.0, 1.0, 0.0, 1.0),
            segments=32,
        )

        assert buffer.vertex_count > 0

    def test_add_polygon(self) -> None:
        """Should be able to add polygons to the buffer."""
        from automataii.presentation.qt.animation.opengl_renderer import GeometryBuffer

        buffer = GeometryBuffer(max_vertices=100, max_indices=100)

        points = np.array([
            [0.0, 0.0],
            [1.0, 0.0],
            [0.5, 1.0],
        ], dtype=np.float32)

        buffer.add_polygon(
            points=points,
            color=(0.0, 0.0, 1.0, 1.0),
        )

        assert buffer.vertex_count >= 3

    def test_clear_buffer(self) -> None:
        """Clear should reset vertex count."""
        from automataii.presentation.qt.animation.opengl_renderer import GeometryBuffer

        buffer = GeometryBuffer(max_vertices=100, max_indices=100)

        buffer.add_line(
            start=(0.0, 0.0),
            end=(1.0, 1.0),
            color=(1.0, 1.0, 1.0, 1.0),
            width=1.0,
        )

        assert buffer.vertex_count > 0

        buffer.clear()

        assert buffer.vertex_count == 0

    def test_batch_add_lines(self) -> None:
        """Should efficiently add multiple lines."""
        from automataii.presentation.qt.animation.opengl_renderer import GeometryBuffer

        buffer = GeometryBuffer(max_vertices=10000, max_indices=10000)

        # Add 100 lines
        for i in range(100):
            buffer.add_line(
                start=(float(i), 0.0),
                end=(float(i), 100.0),
                color=(1.0, 1.0, 1.0, 1.0),
                width=1.0,
            )

        assert buffer.vertex_count >= 200  # At least 2 vertices per line


# =============================================================================
# SHADER TESTS
# =============================================================================


class TestShaderProgram:
    """Test shader compilation and uniform handling."""

    def test_shader_source_is_valid_glsl(self) -> None:
        """Shader source should be syntactically valid GLSL."""
        from automataii.presentation.qt.animation.opengl_renderer import (
            FRAGMENT_SHADER_SOURCE,
            VERTEX_SHADER_SOURCE,
        )

        # Basic syntax checks
        assert "void main()" in VERTEX_SHADER_SOURCE
        assert "void main()" in FRAGMENT_SHADER_SOURCE
        assert "gl_Position" in VERTEX_SHADER_SOURCE
        assert "gl_FragColor" in FRAGMENT_SHADER_SOURCE or "out vec4" in FRAGMENT_SHADER_SOURCE

    def test_uniform_names_are_defined(self) -> None:
        """Required uniforms should be declared in shaders."""
        from automataii.presentation.qt.animation.opengl_renderer import (
            VERTEX_SHADER_SOURCE,
        )

        # MVP matrix uniform
        assert "u_mvp" in VERTEX_SHADER_SOURCE or "mvp" in VERTEX_SHADER_SOURCE.lower()


# =============================================================================
# OPENGL CANVAS TESTS
# =============================================================================


class TestOpenGLCanvas:
    """Test the OpenGL canvas widget."""

    @pytest.fixture
    def qapp(self):
        """Create QApplication for widget tests."""
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        yield app

    def test_canvas_creation(self, qapp) -> None:
        """Canvas should be creatable as a QWidget."""
        from automataii.presentation.qt.animation.opengl_renderer import OpenGLCanvas

        canvas = OpenGLCanvas()
        assert canvas is not None

    def test_canvas_has_geometry_buffer(self, qapp) -> None:
        """Canvas should have a geometry buffer."""
        from automataii.presentation.qt.animation.opengl_renderer import OpenGLCanvas

        canvas = OpenGLCanvas()
        assert hasattr(canvas, "geometry_buffer")
        assert canvas.geometry_buffer is not None

    def test_canvas_resize(self, qapp) -> None:
        """Canvas should handle resize events."""
        from automataii.presentation.qt.animation.opengl_renderer import OpenGLCanvas

        canvas = OpenGLCanvas()
        canvas.resize(800, 600)

        assert canvas.width() == 800
        assert canvas.height() == 600

    def test_canvas_set_view_transform(self, qapp) -> None:
        """Canvas should accept view transformation."""
        from automataii.presentation.qt.animation.opengl_renderer import OpenGLCanvas

        canvas = OpenGLCanvas()

        # Set pan and zoom
        canvas.set_view_transform(
            pan_x=100.0,
            pan_y=50.0,
            zoom=2.0,
        )

        assert canvas.pan_x == 100.0
        assert canvas.pan_y == 50.0
        assert canvas.zoom == 2.0


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestOpenGLRendererIntegration:
    """Integration tests for OpenGL rendering."""

    @pytest.fixture
    def qapp(self):
        """Create QApplication for widget tests."""
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        yield app

    def test_render_skeleton(self, qapp) -> None:
        """Should render a skeleton with joints and bones."""
        from automataii.presentation.qt.animation.opengl_renderer import OpenGLCanvas

        canvas = OpenGLCanvas()
        buffer = canvas.geometry_buffer

        # Add skeleton joints
        joint_positions = [
            (0.0, 0.0),
            (0.0, 50.0),
            (25.0, 100.0),
            (-25.0, 100.0),
        ]

        for x, y in joint_positions:
            buffer.add_circle(
                center=(x, y),
                radius=5.0,
                color=(1.0, 0.5, 0.0, 1.0),
                segments=16,
            )

        # Add bones
        bone_connections = [(0, 1), (1, 2), (1, 3)]
        for start_idx, end_idx in bone_connections:
            buffer.add_line(
                start=joint_positions[start_idx],
                end=joint_positions[end_idx],
                color=(0.8, 0.8, 0.8, 1.0),
                width=3.0,
            )

        assert buffer.vertex_count > 0

    def test_render_mechanism(self, qapp) -> None:
        """Should render a 4-bar linkage mechanism."""
        from automataii.presentation.qt.animation.opengl_renderer import OpenGLCanvas

        canvas = OpenGLCanvas()
        buffer = canvas.geometry_buffer

        # 4-bar linkage positions
        p1 = (0.0, 0.0)  # Ground pivot 1
        p2 = (100.0, 0.0)  # Ground pivot 2
        p3 = (20.0, 50.0)  # Moving pivot 1
        p4 = (80.0, 60.0)  # Moving pivot 2

        # Add ground pivots (larger circles)
        for p in [p1, p2]:
            buffer.add_circle(center=p, radius=8.0, color=(0.5, 0.5, 0.5, 1.0), segments=24)

        # Add moving pivots
        for p in [p3, p4]:
            buffer.add_circle(center=p, radius=6.0, color=(1.0, 0.0, 0.0, 1.0), segments=24)

        # Add links
        buffer.add_line(start=p1, end=p3, color=(0.2, 0.6, 1.0, 1.0), width=4.0)
        buffer.add_line(start=p2, end=p4, color=(0.2, 0.6, 1.0, 1.0), width=4.0)
        buffer.add_line(start=p3, end=p4, color=(1.0, 0.8, 0.2, 1.0), width=4.0)

        assert buffer.vertex_count > 0


# =============================================================================
# PERFORMANCE TESTS
# =============================================================================


class TestOpenGLPerformance:
    """Performance benchmarks for OpenGL rendering."""

    def test_batch_geometry_performance(self) -> None:
        """Geometry batching should be fast."""
        import time

        from automataii.presentation.qt.animation.opengl_renderer import GeometryBuffer

        buffer = GeometryBuffer(max_vertices=100000, max_indices=300000)

        num_objects = 1000

        start = time.perf_counter()

        for i in range(num_objects):
            buffer.add_circle(
                center=(float(i % 100) * 10, float(i // 100) * 10),
                radius=5.0,
                color=(1.0, 1.0, 1.0, 1.0),
                segments=16,
            )

        elapsed = time.perf_counter() - start

        print(f"\nBatched {num_objects} circles in {elapsed*1000:.2f}ms")
        print(f"  Per object: {elapsed*1000000/num_objects:.2f}us")
        print(f"  Vertex count: {buffer.vertex_count}")

        # Should batch 1000 circles in under 100ms
        assert elapsed < 0.1, f"Batching too slow: {elapsed*1000:.2f}ms"
