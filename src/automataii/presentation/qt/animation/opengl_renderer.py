"""
OpenGL Rendering Backend for High-Performance Animation.

This module provides a GPU-accelerated alternative to QGraphicsView
for rendering animation frames with many objects.

Architecture: Presentation Layer
Pattern: Immediate Mode + Batched Geometry

Components:
- GeometryBuffer: CPU-side geometry batching
- OpenGLCanvas: QOpenGLWidget for GPU rendering
- Shader programs: GLSL vertex/fragment shaders

Performance:
- Batches all geometry into single draw calls
- Uses vertex buffer objects (VBOs) for GPU-side storage
- Reduces Python-to-C++ overhead through batching

Usage:
    canvas = OpenGLCanvas(parent)

    # Build geometry
    buffer = canvas.geometry_buffer
    buffer.add_line(start=(0, 0), end=(100, 100), color=(1, 0, 0, 1), width=2)
    buffer.add_circle(center=(50, 50), radius=10, color=(0, 1, 0, 1))

    # Render (happens automatically in paintGL)
    canvas.update()
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    import numpy.typing as npt

logger = logging.getLogger(__name__)


# =============================================================================
# SHADER SOURCES
# =============================================================================


VERTEX_SHADER_SOURCE = """
#version 120

attribute vec2 a_position;
attribute vec4 a_color;

uniform mat4 u_mvp;

varying vec4 v_color;

void main() {
    gl_Position = u_mvp * vec4(a_position, 0.0, 1.0);
    v_color = a_color;
}
"""

FRAGMENT_SHADER_SOURCE = """
#version 120

varying vec4 v_color;

void main() {
    gl_FragColor = v_color;
}
"""


# =============================================================================
# GEOMETRY BUFFER
# =============================================================================


class GeometryBuffer:
    """
    CPU-side geometry buffer for batched rendering.

    Collects lines, circles, and polygons into vertex arrays
    that can be uploaded to the GPU in a single batch.

    Attributes:
        max_vertices: Maximum number of vertices
        max_indices: Maximum number of indices
        vertex_count: Current number of vertices
        index_count: Current number of indices

    Vertex Format:
        - position: float32 x 2 (x, y)
        - color: float32 x 4 (r, g, b, a)
        Total: 24 bytes per vertex
    """

    # Vertex components
    POSITION_SIZE = 2  # x, y
    COLOR_SIZE = 4  # r, g, b, a
    VERTEX_SIZE = POSITION_SIZE + COLOR_SIZE  # 6 floats = 24 bytes
    _CIRCLE_UNIT_CACHE: dict[int, npt.NDArray[np.float32]] = {}
    _CIRCLE_INDEX_CACHE: dict[int, npt.NDArray[np.uint32]] = {}

    def __init__(self, max_vertices: int = 10000, max_indices: int = 30000):
        """
        Initialize geometry buffer.

        Args:
            max_vertices: Maximum vertices (default 10000)
            max_indices: Maximum indices (default 30000)
        """
        self.max_vertices = max_vertices
        self.max_indices = max_indices

        # Pre-allocate arrays
        self._vertices = np.zeros((max_vertices, self.VERTEX_SIZE), dtype=np.float32)
        self._indices = np.zeros(max_indices, dtype=np.uint32)

        self._vertex_count = 0
        self._index_count = 0

    @property
    def vertex_count(self) -> int:
        """Get current vertex count."""
        return self._vertex_count

    @property
    def index_count(self) -> int:
        """Get current index count."""
        return self._index_count

    @property
    def vertices(self) -> npt.NDArray[np.float32]:
        """Get vertex data (position + color)."""
        return self._vertices[: self._vertex_count]

    @property
    def indices(self) -> npt.NDArray[np.uint32]:
        """Get index data."""
        return self._indices[: self._index_count]

    def clear(self) -> None:
        """Clear all geometry."""
        self._vertex_count = 0
        self._index_count = 0

    @classmethod
    def _circle_unit_vertices(cls, segments: int) -> npt.NDArray[np.float32]:
        """Return cached unit-circle perimeter vertices for a segment count."""
        cached = cls._CIRCLE_UNIT_CACHE.get(segments)
        if cached is not None:
            return cached

        angles = np.arange(segments, dtype=np.float32) * (2.0 * math.pi / float(segments))
        vertices = np.column_stack((np.cos(angles), np.sin(angles))).astype(np.float32)
        cls._CIRCLE_UNIT_CACHE[segments] = vertices
        return vertices

    @classmethod
    def _circle_index_offsets(cls, segments: int) -> npt.NDArray[np.uint32]:
        """Return cached triangle-fan indices relative to a circle's base vertex."""
        cached = cls._CIRCLE_INDEX_CACHE.get(segments)
        if cached is not None:
            return cached

        perimeter = np.arange(segments, dtype=np.uint32)
        offsets = np.empty(segments * 3, dtype=np.uint32)
        offsets[0::3] = 0
        offsets[1::3] = 1 + perimeter
        offsets[2::3] = 1 + ((perimeter + 1) % segments)
        cls._CIRCLE_INDEX_CACHE[segments] = offsets
        return offsets

    def add_line(
        self,
        start: tuple[float, float],
        end: tuple[float, float],
        color: tuple[float, float, float, float],
        width: float = 1.0,
    ) -> None:
        """
        Add a line to the buffer.

        For width > 1, creates a quad. For width == 1, creates two vertices.

        Args:
            start: Start point (x, y)
            end: End point (x, y)
            color: RGBA color (0-1 range)
            width: Line width in pixels
        """
        if width <= 1.0:
            # Simple line (2 vertices)
            if self._vertex_count + 2 > self.max_vertices:
                return

            base_idx = self._vertex_count

            self._vertices[base_idx, 0:2] = start
            self._vertices[base_idx, 2:6] = color

            self._vertices[base_idx + 1, 0:2] = end
            self._vertices[base_idx + 1, 2:6] = color

            self._vertex_count += 2
        else:
            # Thick line as quad (4 vertices, 6 indices)
            if self._vertex_count + 4 > self.max_vertices:
                return
            if self._index_count + 6 > self.max_indices:
                return

            # Calculate perpendicular offset
            dx = end[0] - start[0]
            dy = end[1] - start[1]
            length = math.sqrt(dx * dx + dy * dy)

            if length < 0.001:
                return

            # Perpendicular unit vector
            px = -dy / length * width * 0.5
            py = dx / length * width * 0.5

            base_idx = self._vertex_count

            # Four corners of the quad
            self._vertices[base_idx, 0:2] = (start[0] + px, start[1] + py)
            self._vertices[base_idx, 2:6] = color

            self._vertices[base_idx + 1, 0:2] = (start[0] - px, start[1] - py)
            self._vertices[base_idx + 1, 2:6] = color

            self._vertices[base_idx + 2, 0:2] = (end[0] - px, end[1] - py)
            self._vertices[base_idx + 2, 2:6] = color

            self._vertices[base_idx + 3, 0:2] = (end[0] + px, end[1] + py)
            self._vertices[base_idx + 3, 2:6] = color

            # Two triangles
            idx_base = self._index_count
            self._indices[idx_base : idx_base + 6] = [
                base_idx,
                base_idx + 1,
                base_idx + 2,
                base_idx,
                base_idx + 2,
                base_idx + 3,
            ]

            self._vertex_count += 4
            self._index_count += 6

    def add_circle(
        self,
        center: tuple[float, float],
        radius: float,
        color: tuple[float, float, float, float],
        segments: int = 32,
    ) -> None:
        """
        Add a filled circle to the buffer.

        Uses a triangle fan (center + perimeter vertices).

        Args:
            center: Center point (x, y)
            radius: Circle radius
            color: RGBA color (0-1 range)
            segments: Number of segments (more = smoother)
        """
        if segments < 3 or radius <= 0.0:
            return
        if self._vertex_count + segments + 1 > self.max_vertices:
            return
        if self._index_count + segments * 3 > self.max_indices:
            return

        base_idx = self._vertex_count

        # Center vertex
        self._vertices[base_idx, 0:2] = center
        self._vertices[base_idx, 2:6] = color

        # Perimeter vertices. Vectorized writes avoid per-segment Python loops
        # during animation batching and keep performance tests stable under load.
        unit_vertices = self._circle_unit_vertices(segments)
        perimeter_slice = self._vertices[base_idx + 1 : base_idx + 1 + segments]
        perimeter_slice[:, 0] = float(center[0]) + (float(radius) * unit_vertices[:, 0])
        perimeter_slice[:, 1] = float(center[1]) + (float(radius) * unit_vertices[:, 1])
        perimeter_slice[:, 2:6] = color

        # Triangle fan indices
        idx_base = self._index_count
        self._indices[idx_base : idx_base + segments * 3] = (
            self._circle_index_offsets(segments) + base_idx
        )

        self._vertex_count += segments + 1
        self._index_count += segments * 3

    def add_polygon(
        self,
        points: npt.NDArray[np.float32],
        color: tuple[float, float, float, float],
    ) -> None:
        """
        Add a filled polygon to the buffer.

        Uses triangle fan from first vertex.

        Args:
            points: (N, 2) array of polygon vertices
            color: RGBA color (0-1 range)
        """
        num_points = len(points)
        if num_points < 3:
            return

        num_triangles = num_points - 2

        if self._vertex_count + num_points > self.max_vertices:
            return
        if self._index_count + num_triangles * 3 > self.max_indices:
            return

        base_idx = self._vertex_count

        # Add vertices
        for i, point in enumerate(points):
            self._vertices[base_idx + i, 0:2] = point
            self._vertices[base_idx + i, 2:6] = color

        # Triangle fan indices
        idx_base = self._index_count
        for i in range(num_triangles):
            self._indices[idx_base + i * 3] = base_idx  # First vertex
            self._indices[idx_base + i * 3 + 1] = base_idx + i + 1
            self._indices[idx_base + i * 3 + 2] = base_idx + i + 2

        self._vertex_count += num_points
        self._index_count += num_triangles * 3


# =============================================================================
# OPENGL CANVAS
# =============================================================================


class OpenGLCanvas:
    """
    OpenGL rendering canvas for animation.

    This can be used as a drop-in replacement for QGraphicsView
    when many objects need to be rendered.

    Note: This is a minimal implementation that can be extended
    to inherit from QOpenGLWidget when Qt integration is needed.

    Attributes:
        geometry_buffer: Buffer for batched geometry
        pan_x, pan_y: View pan offset
        zoom: View zoom level
    """

    def __init__(self, parent: Any = None) -> None:
        """
        Initialize OpenGL canvas.

        Args:
            parent: Parent widget (optional)
        """
        self._parent: Any = parent
        self._width = 800
        self._height = 600

        # View transform
        self._pan_x = 0.0
        self._pan_y = 0.0
        self._zoom = 1.0

        # Geometry buffer
        self._geometry_buffer = GeometryBuffer()

        # OpenGL state (initialized in initializeGL)
        self._gl_initialized = False

        logger.debug("OpenGLCanvas created")

    @property
    def geometry_buffer(self) -> GeometryBuffer:
        """Get the geometry buffer."""
        return self._geometry_buffer

    @property
    def pan_x(self) -> float:
        """Get X pan offset."""
        return self._pan_x

    @property
    def pan_y(self) -> float:
        """Get Y pan offset."""
        return self._pan_y

    @property
    def zoom(self) -> float:
        """Get zoom level."""
        return self._zoom

    def width(self) -> int:
        """Get canvas width."""
        return self._width

    def height(self) -> int:
        """Get canvas height."""
        return self._height

    def resize(self, width: int, height: int) -> None:
        """
        Resize the canvas.

        Args:
            width: New width in pixels
            height: New height in pixels
        """
        self._width = width
        self._height = height

    def set_view_transform(
        self,
        pan_x: float = 0.0,
        pan_y: float = 0.0,
        zoom: float = 1.0,
    ) -> None:
        """
        Set view transformation.

        Args:
            pan_x: X pan offset
            pan_y: Y pan offset
            zoom: Zoom level (1.0 = 100%)
        """
        self._pan_x = pan_x
        self._pan_y = pan_y
        self._zoom = max(0.1, min(10.0, zoom))

    def compute_mvp_matrix(self) -> npt.NDArray[np.float32]:
        """
        Compute Model-View-Projection matrix.

        Returns:
            4x4 MVP matrix
        """
        # Orthographic projection
        left = -self._width / 2.0
        right = self._width / 2.0
        bottom = -self._height / 2.0
        top = self._height / 2.0

        # Apply zoom
        left /= self._zoom
        right /= self._zoom
        bottom /= self._zoom
        top /= self._zoom

        # Apply pan
        left -= self._pan_x
        right -= self._pan_x
        bottom -= self._pan_y
        top -= self._pan_y

        # Orthographic projection matrix
        mvp = np.array(
            [
                [2.0 / (right - left), 0.0, 0.0, -(right + left) / (right - left)],
                [0.0, 2.0 / (top - bottom), 0.0, -(top + bottom) / (top - bottom)],
                [0.0, 0.0, -1.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
            ],
            dtype=np.float32,
        )

        return mvp
