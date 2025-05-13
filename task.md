# Mechanism Generation Refactoring Plan

This file outlines the steps to refactor and enhance the mechanism generation capabilities of the AutomataDesigner application, drawing inspiration from libraries like `macanism` for robust kinematic representations.

## Core Tasks

1.  **Analyze `macanism` Concepts:**
    *   Perform an in-depth review of `macanism/readme.md` and its underlying principles.
    *   Identify key data structures (e.g., `Vector`, `Joint`, `Link`, `Mechanism`, `FourBar`, `Gear`, `GearSet`) and analytical methods (e.g., loop closure equations) that can be adapted for `automataii`.

2.  **Define Core Kinematic Data Models:**
    *   Create new Python data classes/models within `src/automataii/generation/models/` (or `src/automataii/core/models/` if more broadly applicable).
    *   These models should represent:
        *   `KinematicJoint`: Position, type (e.g., revolute fixed, revolute moving, prismatic).
        *   `LinkElement`: Connects two `KinematicJoint`s, has a defined length or geometry.
        *   `GearInfo`: Center position, radius, number of teeth, module, visual path.
    *   These models will provide a more detailed and kinematically accurate representation than the current generic `PartInfo` and `Joint` for the purpose of mechanism definition and analysis.

3.  **Refactor Linkage Generation (`src/automataii/generation/linkage.py`):**
    *   Update `generate_3bar_linkage`:
        *   Define clear input parameters (e.g., fixed pivot(s), link lengths, target coupler point/path characteristics).
        *   Implement logic to calculate joint positions and link configurations.
        *   Return a collection of `LinkElement` and `KinematicJoint` instances.
    *   Update `generate_4bar_linkage`:
        *   Define clear input parameters (e.g., fixed pivots, link lengths, desired coupler curve properties, or synthesis goals like Grashof criteria).
        *   Implement logic to determine the linkage configuration.
        *   Return a collection of `LinkElement` and `KinematicJoint` instances.

4.  **Refactor Gear Generation (`src/automataii/generation/gear.py`):**
    *   Update `generate_gear_pair`:
        *   Define clear input parameters (e.g., desired gear ratio, center distance, module, number of teeth for one gear, pressure angle).
        *   Implement logic to calculate parameters for both gears (radii, actual teeth counts, precise center locations).
        *   Return a list of `GearInfo` instances, including `QPainterPath` representations for their visual profiles (initially simple circles, potentially with involute tooth approximations later).

5.  **Update Dispatch Logic in `MainWindow` (`src/automataii/gui/main_window.py`):**
    *   Modify `_generate_mechanism_auto` to correctly gather necessary inputs (from new UI elements or sensible defaults) for the refactored generation functions.
    *   Ensure it correctly passes these inputs and handles the new return types (collections of `LinkElement`, `KinematicJoint`, `GearInfo`).

6.  **Enhance User Interface in `MainWindow`:**
    *   In `_create_editor_tab` (or a dedicated sub-panel for mechanism parameters):
        *   Add input fields, sliders, or graphical input methods (e.g., clicking on the scene to define pivot points) for users to specify parameters for linkage generation.
        *   Add input fields for gear generation parameters.
    *   Ensure `_update_generate_mechanism_button_state` reflects the input requirements for each mechanism type.

7.  **Update Visualization Methods in `MainWindow`:**
    *   Refine `_visualize_linkage_data` to accurately render linkages based on the `LinkElement` and `KinematicJoint` data (e.g., drawing lines for links, circles for joints).
    *   Refine `_visualize_gear_data` to draw gears based on `GearInfo` (e.g., drawing pitch circles, and eventually more detailed gear shapes).
    *   Ensure these visualizations are added to appropriate layers and can be toggled/cleared.

8.  **Documentation and Rules Update:**
    *   Update `mechanism-generation.mdc` rule to reflect the new, more comprehensive mechanism generation flow and capabilities.
    *   Add documentation for the new data models and generation functions.

## Future Considerations / Advanced Tasks

9.  **Integration with Simulation:**
    *   Develop a pathway to translate the generated `LinkElement`/`KinematicJoint` and `GearInfo` models into a format usable by the existing simulation engine (`update_simulation`) or a new dedicated forward/inverse kinematics solver for mechanisms.
    *   This would allow for animation and analysis of the generated mechanisms.

10. **Advanced Synthesis Algorithms:**
    *   Explore incorporating more advanced mechanism synthesis algorithms (e.g., for path generation with four-bar linkages, or meeting specific motion requirements).

11. **Error Handling and Validation:**
    *   Implement robust input validation for mechanism parameters.
    *   Provide user feedback for invalid configurations (e.g., non-Grashof linkages if relevant, impossible gear parameters).

12. **Unit Tests:**
    *   Develop unit tests for the new generation logic and data models.