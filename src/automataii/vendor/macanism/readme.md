# Macanism - 2D & 3D Mechanism Analysis Library

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) <!-- Update license if different -->

`macanism` is a Python library designed for the kinematic analysis of planar (2D) and spatial (3D) mechanisms, including linkages, cams, and gears (though 3D cam/gear support is currently basic).

This library allows users to define mechanisms using joints and vectors, specify input motions, and calculate the resulting positions, velocities, and accelerations of all components. It includes visualization tools for plotting and animating mechanism motion.

**Note:** The 3D extension is relatively new (as of v0.2.0) and under active development. While core 3D kinematics are implemented, some features (complex loop functions, advanced plotting, comprehensive testing) are still evolving.

## Features

*   Define mechanisms using `Joint` and `Vector` objects.
*   Support for both 2D (planar) and 3D (spatial) analysis.
*   Calculation of position, velocity, and acceleration using numerical methods (`scipy.optimize.fsolve`).
*   Visualization via `matplotlib` for static plots and animations.
*   Basic structure follows principles of object-oriented design.

## Installation

It is recommended to use a virtual environment.

### Using `uv` (Recommended)

```bash
# Create and activate a virtual environment (optional but recommended)
python -m venv .venv
source .venv/bin/activate # or .venv\Scripts\activate on Windows

# Install using uv
uv pip install macanism

# Or, install directly from a local clone (if you have the source code)
uv pip install .

# To install development dependencies (for running tests, linting):
uv pip install ".[dev]"
```

### Using `pip`

```bash
# Create and activate a virtual environment (optional but recommended)
python -m venv .venv
source .venv/bin/activate # or .venv\Scripts\activate on Windows

# Install using pip
pip install macanism

# Or, install directly from a local clone
pip install .

# To install development dependencies:
pip install ".[dev]"
```

## Basic Usage (2D Example)

```python
import numpy as np
from mechanism import Mechanism, Joint, Vector
import matplotlib.pyplot as plt

# Define joints
j0 = Joint('0')
j1 = Joint('1')
j2 = Joint('2')
j3 = Joint('3')

# Define vectors (links)
v_ground = Vector(joints=(j0, j3), x=2, style='ground')
v1 = Vector(joints=(j0, j1), r=1)       # Input link (r=1, theta driven)
v2 = Vector(joints=(j1, j2), r=2.5)     # Coupler (r=2.5, theta varies)
v3 = Vector(joints=(j3, j2), r=2.5)     # Output link (r=2.5, theta varies)

vectors = [v1, v2, v3, v_ground]

def loops(x, v1_angle):
    # Loop equation: v1 + v2 - v3 - v_ground = 0
    return v1(v1_angle) + v2(x[0]) - v3(x[1]) - v_ground()

# Initial guess [v2 angle, v3 angle]
guess = [np.pi/2, np.pi/2]

# Create mechanism
mech = Mechanism(vectors=vectors, loops=loops, origin=j0, guess=guess)

# Input angles
input_angles = np.linspace(0, 2*np.pi, 100)

# Solve
mech.calculate(input_angles, (v1.pos, 'theta')) # Drive v1 theta

# Animate
player, fig, ax = mech.get_animation()
plt.show()
```

## 3D Usage Example

See `examples/spatial_crank_rocker.py` for an example of setting up and solving a simple spatial mechanism.

Key differences for 3D:

*   Joints are defined with `x, y, z` coordinates.
*   Vectors can be initialized with `r, theta, phi` (magnitude, inclination, azimuth) or `x, y, z` components.
*   Loop functions must return 3 residuals (for x, y, z closure).
*   Guesses will typically involve more unknown angles.
*   Plotting and animation occur in 3D space.

## Running Tests

Ensure you have installed the development dependencies (`uv pip install ".[dev]"` or `pip install ".[dev]"`).

From the root directory of the project:

```bash
pytest
```

## Contributing

Contributions are welcome! Please refer to the contribution guidelines (TODO: Create CONTRIBUTING.md) and the issue tracker on GitHub (TODO: Update URL).

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details (TODO: Create LICENSE file).

## Documentation Structure (Code)

*   `mechanism/`: Main package directory
    *   `mechanism.py`: Core `Mechanism` and `Joint` classes.
    *   `vectors.py`: `VectorBase`, `Vector`, `Position`, `Velocity`, `Acceleration` classes.
    *   `plotting.py`: Plotting helper functions.
    *   `animation.py`: Animation (`Player`) class.
    *   `appearance.json`: Default plotting styles.
*   `examples/`: Example usage scripts.
*   `tests/`: Unit tests.
*   `pyproject.toml`: Project build configuration and dependencies.
*   `README.md`: This file.
*   `CHANGELOG.md`: History of changes.

## Reproducibility

To ensure reproducibility of any experiments or results generated using this library:

*   **Environment:** Use the specified Python version (>=3.9) and install dependencies using the provided `pyproject.toml` (preferably with `uv` or within a locked virtual environment).
*   **Scripts:** Example scripts in the `examples/` directory demonstrate setup and execution.
*   **Parameters:** Mechanism definitions (joint locations, vector lengths/properties), input motions, and solver guesses are explicitly defined within the scripts.
*   **Assumptions:** The core assumption is rigid body kinematics. Solver behavior depends on `scipy.optimize.fsolve`.
