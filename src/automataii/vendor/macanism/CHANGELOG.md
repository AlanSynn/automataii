# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - YYYY-MM-DD (Replace with date)

### Added

*   **3D Kinematics**: Extended core classes (`VectorBase`, `Position`, `Velocity`, `Acceleration`, `Joint`, `Mechanism`) to support 3D spatial coordinates (x, y, z and r, theta, phi).
*   Implemented 3D velocity and acceleration calculations based on spherical coordinate derivatives.
*   Refactored `VectorBase.__init__` to better determine the state (fixed/variable) of 3D vectors and assign appropriate `get` methods for position calculation.
*   Added `Position._phi_varies_get` method for cases where r and theta are fixed, but phi varies.
*   **3D Plotting**: Modified `Mechanism.plot` and `Mechanism.get_animation` to generate 3D visualizations using `matplotlib`'s `Axes3D`.
*   **3D Example**: Added `examples/spatial_crank_rocker.py` demonstrating a simple spatial mechanism setup and solution.
*   **3D Unit Tests**: Created `tests/mechanism/test_vectors_3d.py` with initial tests for 3D vector operations and kinematics (including acceleration for circular motion).
*   **Project Structure**: Added `pyproject.toml` for PEP 621 compliant packaging, `README.md` with updated instructions, and this `CHANGELOG.md`.

### Changed

*   `VectorBase`, `Position`, `Velocity`, `Acceleration` updated for 3D data storage and calculation.
*   `Joint` class updated to store 3D position/velocity/acceleration data and time series.
*   `Mechanism` class updated to handle 3D loop equations (expecting 3 residuals), 3D bounds calculation, 3D plotting, and 3D animation.
*   Internal coordinate handling uses `np.arctan2` and `np.arccos` for robust angle calculations.
*   Renamed some internal `Joint` attributes (e.g., `vel_angles` -> `vel_thetas`) and added `phi` equivalents.
*   Updated plotting helpers in `Joint` for 3D arrow representation (`ax.quiver`).
*   Updated `Mechanism.get_animation` return value to `(player, fig, ax)`.

### Fixed

*   Corrected various errors identified during testing of 2D examples within the 3D framework (e.g., attribute errors, type errors, argument mismatches, guess update logic).
*   Ensured `Position.__init__` uses `super()`.
*   Addressed linter errors in test and example files.

### Removed

*   Placeholders/warnings regarding unimplemented 3D acceleration in `Acceleration.__init__`.

## [0.1.x] - Previous Versions (Assuming based on original 2D library)

*   Initial release focused on 2D planar mechanism analysis (linkages, cams, gears).
*   Features for SVAJ diagrams, cam profile generation, spur gear coordinates.
*   2D plotting and animation capabilities.

*(Note: Details for versions prior to 0.2.0 should be filled in based on the original project's history if available)*