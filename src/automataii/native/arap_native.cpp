/**
 * @file arap_native.cpp
 * @brief Native C++ implementation of ARAP acceleration functions.
 *
 * This module provides high-performance implementations of:
 * - compute_rotation_matrices: Vectorized rotation matrix computation
 * - batch_transform_points: Batch coordinate transformation
 *
 * Performance: 10-100x faster than pure Python loops.
 *
 * Build:
 *   mkdir build && cd build
 *   cmake .. -DCMAKE_BUILD_TYPE=Release
 *   make
 *
 * @author Automataii Contributors
 */

#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>
#include <Eigen/Dense>
#include <cmath>

namespace py = pybind11;

/**
 * Compute rotation matrices for ARAP solve step.
 *
 * This replaces the Python loop in ARAP.solve() with optimized C++ code.
 *
 * @param edge_vectors (E, 2) array of original edge vectors
 * @param T1 (2*E,) array of rotation parameters [c0, s0, c1, s1, ...]
 * @return (E, 2) array of rotated edge vectors
 *
 * Time Complexity: O(E)
 */
py::array_t<double> compute_rotation_matrices(
    py::array_t<double, py::array::c_style | py::array::forcecast> edge_vectors,
    py::array_t<double, py::array::c_style | py::array::forcecast> T1
) {
    // Get buffer info
    auto edges_buf = edge_vectors.request();
    auto T1_buf = T1.request();

    if (edges_buf.ndim != 2 || edges_buf.shape[1] != 2) {
        throw std::runtime_error("edge_vectors must have shape (E, 2)");
    }
    if (T1_buf.ndim != 1) {
        throw std::runtime_error("T1 must be 1-dimensional");
    }

    const size_t num_edges = edges_buf.shape[0];
    if (T1_buf.shape[0] != static_cast<ssize_t>(2 * num_edges)) {
        throw std::runtime_error("T1 must have length 2 * num_edges");
    }

    // Get raw pointers
    const double* edges_ptr = static_cast<double*>(edges_buf.ptr);
    const double* T1_ptr = static_cast<double*>(T1_buf.ptr);

    // Allocate output
    auto result = py::array_t<double>({static_cast<ssize_t>(num_edges), static_cast<ssize_t>(2)});
    auto result_buf = result.request();
    double* result_ptr = static_cast<double*>(result_buf.ptr);

    // Process edges in parallel using OpenMP if available
    #pragma omp parallel for if(num_edges > 100)
    for (size_t idx = 0; idx < num_edges; ++idx) {
        // Extract rotation parameters
        double c = T1_ptr[2 * idx];
        double s = T1_ptr[2 * idx + 1];

        // Normalize to unit rotation
        const double inv_scale = 1.0 / std::sqrt(c * c + s * s);
        c *= inv_scale;
        s *= inv_scale;

        // Get edge vector
        const double e0_x = edges_ptr[2 * idx];
        const double e0_y = edges_ptr[2 * idx + 1];

        // Apply rotation matrix [[c, s], [-s, c]]
        result_ptr[2 * idx] = c * e0_x + s * e0_y;
        result_ptr[2 * idx + 1] = -s * e0_x + c * e0_y;
    }

    return result;
}

/**
 * Batch transform points from local to scene coordinates.
 *
 * @param points (N, 2) array of points
 * @param scale Scale factor
 * @param offset_x X offset
 * @param offset_y Y offset
 * @param flip_y Whether to flip Y axis
 * @return (N, 2) array of transformed points
 *
 * Time Complexity: O(N)
 */
py::array_t<double> batch_transform_points(
    py::array_t<double, py::array::c_style | py::array::forcecast> points,
    double scale,
    double offset_x,
    double offset_y,
    bool flip_y = true
) {
    auto points_buf = points.request();

    if (points_buf.ndim != 2 || points_buf.shape[1] != 2) {
        throw std::runtime_error("points must have shape (N, 2)");
    }

    const size_t num_points = points_buf.shape[0];
    const double* points_ptr = static_cast<double*>(points_buf.ptr);

    // Allocate output
    auto result = py::array_t<double>({static_cast<ssize_t>(num_points), static_cast<ssize_t>(2)});
    auto result_buf = result.request();
    double* result_ptr = static_cast<double*>(result_buf.ptr);

    // Transform points
    const double y_sign = flip_y ? -1.0 : 1.0;

    #pragma omp parallel for if(num_points > 1000)
    for (size_t i = 0; i < num_points; ++i) {
        result_ptr[2 * i] = points_ptr[2 * i] * scale + offset_x;
        result_ptr[2 * i + 1] = y_sign * points_ptr[2 * i + 1] * scale + offset_y;
    }

    return result;
}

/**
 * Get version information.
 */
std::string get_version() {
    return "1.0.0";
}

/**
 * Check if OpenMP is available.
 */
bool has_openmp() {
    #ifdef _OPENMP
    return true;
    #else
    return false;
    #endif
}

// Module definition
PYBIND11_MODULE(arap_native, m) {
    m.doc() = R"doc(
        Native C++ acceleration for ARAP deformation.

        This module provides optimized implementations of performance-critical
        ARAP operations using C++ and optionally OpenMP for parallelization.

        Functions:
            compute_rotation_matrices: Compute rotation matrices for ARAP solve
            batch_transform_points: Batch coordinate transformation
            get_version: Get module version
            has_openmp: Check if OpenMP parallelization is available
    )doc";

    m.def("compute_rotation_matrices", &compute_rotation_matrices,
          py::arg("edge_vectors"),
          py::arg("T1"),
          R"doc(
              Compute rotation matrices for ARAP solve step.

              Args:
                  edge_vectors: (E, 2) array of original edge vectors
                  T1: (2*E,) array of rotation parameters

              Returns:
                  (E, 2) array of rotated edge vectors
          )doc");

    m.def("batch_transform_points", &batch_transform_points,
          py::arg("points"),
          py::arg("scale"),
          py::arg("offset_x"),
          py::arg("offset_y"),
          py::arg("flip_y") = true,
          R"doc(
              Batch transform points from local to scene coordinates.

              Args:
                  points: (N, 2) array of points
                  scale: Scale factor
                  offset_x: X offset
                  offset_y: Y offset
                  flip_y: Whether to flip Y axis (default True)

              Returns:
                  (N, 2) array of transformed points
          )doc");

    m.def("get_version", &get_version,
          "Get the module version string.");

    m.def("has_openmp", &has_openmp,
          "Check if OpenMP parallelization is available.");
}
