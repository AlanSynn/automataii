# Automata II - Mechanism & Blueprint Generation: Implementation Plan

## 1. Introduction

This document outlines the phased implementation plan for adding automated mechanism generation (initially cam-based, with potential for linkages) and blueprint generation capabilities to the Automata II Designer application. The goal is to streamline the process of converting character motion paths into functional mechanical designs suitable for fabrication.

## 2. Development Phases

### Phase 1: Foundational Setup

- [x] **Goal:** Establish the core application structure for loading, visualizing, and manipulating character parts.
- [x] **Deliverables:**
    - [x] Loading character parts from `parts_info.json` (SVG/Image).
    - [x] Displaying parts in an interactive `QGraphicsScene`.
    - [x] Manual part transformation (translation, rotation, scaling).
    - [x] Manual Z-depth adjustment.
    - [x] Manual joint definition between parts.
    - [x] Basic project saving/loading.
    - [x] Initial UI structure (Tabs for Character, Mechanism Design, Options).
    - [x] Theme support (Light/Dark).

### Phase 2: Motion Path Definition & Basic Simulation

- [x] **Goal:** Enable users to define desired motion paths for character parts and simulate basic kinematic motion.
- [x] **Deliverables:**
    - [x] Motion path drawing tools (Freehand, Bézier) with loop options (Open/Closed).
    - [x] Association of motion paths with specific `CharacterPartItem` instances.
    - [x] Visualization of motion paths in the editor view.
    - [x] Implementation of kinematic chain building (`build_kinematic_chains`).
    - [x] Implementation of Inverse Kinematics (IK) solver (`solve_ik_ccd`).
    - [x] Simulation controls (Play, Stop, Reset) driving IK based on motion paths.
    - [x] Saving/Loading motion paths with project data.

### Phase 3: Mechanism Generation & Visualization

- [x] **Goal:** Implement generation and visualization for various mechanism types (Cam, Linkages, Gears) based on a selected part's motion path.
- [x] **Completed/In-Progress (Foundational Work):**
    - [x] **UI Refactor:**
        - [x] Renamed "Cam Mechanism" group box to "Mechanism Design".
        - [x] Added `QComboBox` (`self.mechanism_type_combo`) for selecting "Cam", "3-Bar Linkage", "4-Bar Linkage", "Cam & Gears".
        - [x] Renamed "Generate Cam Profile" button to "Generate Mechanism" (`self.generate_mechanism_btn`).
        - [x] Button state (`_update_generate_mechanism_button_state`) updated for different mechanism types (initial support).
    - [x] **Core Logic Dispatch:**
        - [x] `_generate_mechanism_auto` in `main_window.py` modified to dispatch to different generation functions based on selected mechanism type.
        - [x] Cam generation logic moved into this dispatcher.
    - [x] **Placeholder Modules:**
        - [x] `src/automataii/generation/linkage.py` created with `generate_3bar_linkage` and `generate_4bar_linkage` placeholder functions.
        - [x] `src/automataii/generation/gear.py` created with `generate_gear_pair` placeholder function.
    - [x] **Basic Visualization Framework:**
        - [x] Placeholder visualization methods (`_visualize_linkage_data`, `_visualize_gear_data`) in `main_window.py`.
        - [x] Display the generated cam profile(s) in the editor scene.
        - [x] Display the target motion path for the follower.
    - [x] **Layer Management:**
        - [x] Mechanism layer controls (checkboxes) to toggle visibility of generated cams, path hints, etc.
        - [x] Implemented `_add_mechanism_visual`, `_clear_mechanism_visuals`, `_toggle_layer_visibility`.
- [ ] **Next Steps (Implementation Details):**
    - [ ] **Cam Mechanism (`src/automataii/generation/cam.py`):**
        - [ ] Refine `generate_cam_profile` (already largely functional).
        - [ ] Ensure accurate cam center determination (currently torso-based, allow user specification later).
    - [ ] **3-Bar Linkage (`src/automataii/generation/linkage.py`):**
        - [ ] Implement `generate_3bar_linkage`.
            - [ ] **Inputs:** Target motion path (`QPainterPath`), fixed pivot point(s) (e.g., from torso or user-defined), potential link length constraints.
            - [ ] **Algorithm:** Research and implement a suitable synthesis method (e.g., path point matching, geometric construction for common types like crank-rocker driving a coupler).
            - [ ] **Output:** Dictionary containing link lengths, pivot positions, and potentially motion data.
        - [ ] Enhance `_visualize_linkage_data` to draw the 3-bar linkage accurately.
    - [ ] **4-Bar Linkage (`src/automataii/generation/linkage.py`):**
        - [ ] Implement `generate_4bar_linkage`.
            - [ ] **Inputs:** Target motion path (`QPainterPath`), fixed pivot points (e.g., from torso or user-defined), potential link length constraints.
            - [ ] **Algorithm:** Research and implement a suitable synthesis method (e.g., Freudenstein's equation, optimization-based approaches for path generation).
            - [ ] **Output:** Dictionary containing link lengths, pivot positions, and potentially motion data.
        - [ ] Enhance `_visualize_linkage_data` to draw the 4-bar linkage accurately.
    - [ ] **Cam & Gears (`src/automataii/generation/gear.py`):**
        - [ ] Implement `generate_gear_pair` for a simple driving gear and a cam-shaped gear or a gear driving a cam follower.
            - [ ] **Inputs:** Target motion path (for the cam/follower element), driving gear center, gear ratio, desired module/number of teeth.
            - [ ] **Algorithm:**
                - Calculate gear pitch diameters.
                - Generate basic gear tooth profiles (e.g., involute, or simplified for visualization).
                - Combine with cam profile generation logic if one element is a cam.
            - [ ] **Output:** Gear parameters (pitch diameters, teeth counts, profiles as `QPainterPath`), cam profile if applicable.
        - [ ] Enhance `_visualize_gear_data` to draw gears and their interaction.
    - [ ] **Mechanism Simulation:**
        - [ ] Integrate generated mechanisms into the existing simulation loop (`update_simulation`).
        - [ ] Allow driving the mechanism (e.g., rotating a crank link at a constant speed).

### Phase 4: Basic Blueprint Generation (SVG)

- [ ] **Goal:** Implement the functionality to export the current state of all character parts into a basic SVG blueprint suitable for laser cutting or reference.
- [ ] **Deliverables:**
    - [ ] `generate_blueprint_svg` function in `src/automataii/generation/blueprint.py`.
        - [ ] Input: List of `CharacterPartItem` instances.
        - [ ] Functionality:
            - [ ] Extract the `QPainterPath` or outline for each part.
            - [ ] Arrange part outlines efficiently on an SVG canvas (simple grid or basic packing).
            - [ ] Include part names as labels near each outline.
            - [ ] Optionally include simple bounding box dimensions.
        - [ ] Output: String containing the SVG content.
    - [ ] UI Integration:
        - [x] Connect the "Generate Blueprint (SVG)" button to trigger the generation and file save dialog.
    - [x] File Saving: Prompt user for SVG save location.

### Phase 5: Linkage Mechanism Exploration

- [ ] **Goal:** Investigate and potentially implement algorithms for generating linkage-based mechanisms (e.g., 4-bar linkages) that approximate a given motion path.
- [ ] **Potential Tasks:**
    - [ ] Research mechanism synthesis algorithms (e.g., geometric constraint solving, optimization-based methods, path matching).
    - [ ] Adapt/integrate concepts from the `Mechanical_Characters` project (mechanism database, path similarity metrics).
    - [ ] Develop path analysis tools (identifying key features, curvature, desired precision).
    - [ ] Implement a linkage solver/simulator to verify generated mechanisms.
    - [ ] Develop UI for specifying linkage constraints or selecting from generated options.
    - [ ] Integrate linkage visualization into the mechanism layers.

### Phase 6: Advanced Blueprinting

- [ ] **Goal:** Enhance the blueprint generation to include more details useful for fabrication and assembly.
- [ ] **Potential Tasks:**
    - [ ] Include generated mechanism components (cam profiles, linkage dimensions, gear profiles) in the blueprint.
    - [ ] Add assembly indicators (e.g., joint locations, part connections).
    - [ ] Explore different layout strategies for clarity.
    - [ ] Investigate PDF export options.
    - [ ] Add options for scale markers, material thickness notations, etc.

### Phase 7: Refinement & Testing

- [x] **Goal:** Improve usability, fix bugs, optimize performance, and gather user feedback across all implemented features.
- [ ] **Completed/In-Progress:**
    - [x] **Image Processing View Enhancements (`src/automataii/gui/image_view.py`):**
        - [x] Corrected skeleton alignment with the loaded image and bounding box, parenting joints to the `image_item` for robust transformations.
        - [x] Implemented a `debug_mode` to display image/bounding box/scene information.
        - [x] Added debug bounding box visualization (`self.debug_bb_item`).
        - [x] Integrated debug mode toggle into the "Options" tab.
    - [x] **UI/UX Improvements:**
        - [x] Set canvas background colors for `ImageProcessingView` and `EditorView` to gray for better contrast.
    - [x] **Data Model Enhancements:**
        - [x] Added original image dimensions to `bounding_box.yaml`.
        - [x] Added bounding box origin to `char_cfg.yaml`.
- [ ] **Potential Tasks:**
    - [ ] UI/UX refinements based on user feedback for mechanism generation.
    - [ ] Performance profiling and optimization (especially simulation and generation).
    - [ ] Robust error handling and reporting.
    - [ ] Code cleanup and documentation improvements.
    - [ ] Cross-platform testing (if applicable).
    - [ ] Creation of example projects and tutorials.

### Phase X: Enhanced IK Simulation and Visual Joint Anchors

## Goals:
1.  Refine IK simulation to produce more "robotic" limb movements, where parts maintain their orientation relative to their parent in the kinematic chain, rooted at the torso (or main fixed part).
2.  Add clear visual anchors for all active joints in the editor scene, which update during simulation.

## Detailed Steps:

### Part 1: Improve IK Behavior

1.  **Review `build_kinematic_chains` (in `main_window.py`):**
    *   [ ] Ensure that the `torso` (if fixed) is consistently treated as the ultimate root of kinematic chains.
    *   [ ] If `torso` is not fixed or not present, verify logic for selecting the fixed base of a chain.
    *   [ ] Chains should be ordered from the root to the end-effector.

2.  **Modify `update_simulation` (in `main_window.py`):**
    *   [X] **Crucial Fix:** Remove the loop that iterates `for item in chain:` *after* `solve_ik_ccd` and calls `item.setRotation(initial_rot)`. This loop overrides the IK's calculated orientations and is the primary cause of parts "spinning independently" instead of maintaining hierarchical orientation.
    *   [ ] Verify that `solve_ik_ccd` (in `ik_solver.py`) correctly uses parent-child relationships and joint locations to calculate rotations. The standard CCD algorithm should inherently handle hierarchical rotations.
    *   [ ] The `initial_part_rotations` dictionary might still be useful if we want to reset the *entire character* to a specific pose, but it should not be used to override individual part rotations *during* each step of an active IK solve.

3.  **Verify `Joint` and `CharacterPartItem` data (in `core/models.py` and `gui/part_item.py`):**
    *   [ ] Ensure `Joint.parent_pos` and `Joint.child_pos` accurately represent the local pivot points on the respective parts. These are critical for the IK solver.
    *   [ ] Confirm `CharacterPartItem.parent_joint` and `CharacterPartItem.child_joints` correctly establish the hierarchy.

### Part 2: Visual Joint Anchors

1.  **Data Structure for Visual Anchors:**
    *   [X] In `AutomataDesigner.__init__`, add `self.joint_visual_markers: List[QGraphicsItem] = []` (using `QGraphicsEllipseItem` for now).

2.  **Create Anchors when Joints are Made:**
    *   [X] Modify `_create_and_add_joint` (in `main_window.py`):
        *   After a `Joint` object is created:
            *   Create a `QGraphicsEllipseItem` (e.g., 5px radius, distinct color like blue or green).
            *   Set its initial position: `marker.setPos(parent_item.mapToScene(joint.parent_pos))`.
            *   Add it to `self.editor_scene` and `self.joint_visual_markers`.
            *   Set an appropriate Z-value so it's visible.
    *   [ ] Handle anchor creation when joints are loaded from a project file (extend `load_parts` or a dedicated joint loading function).

3.  **Update Anchor Positions During Simulation:**
    *   [X] In `update_simulation` (in `main_window.py`), *after* the IK loop:
        *   Add a new loop: `for i, joint in enumerate(self.joints):`
            *   Ensure `i` is a valid index for `self.joint_visual_markers`.
            *   `parent_item = joint.parent_item`
            *   `marker = self.joint_visual_markers[i]`
            *   `scene_joint_pos = parent_item.mapToScene(joint.parent_pos)`
            *   `marker.setPos(scene_joint_pos)`

4.  **Manage Anchor Visibility:**
    *   [X] **Initial Visibility:** Anchors should be made visible when created.
    *   [X] **Toggling:** Connect visibility to the "Show Skeleton" button (`self.show_skeleton_btn`):
        *   In `_show_skeleton_and_joints`, iterate through `self.joint_visual_markers` and set their visibility according to the button's `checked` state.
    *   [X] **Clearing:** In `_clear_editor_state`, iterate through `self.joint_visual_markers`, remove them from the scene, and clear the list. This should also be called by `_show_skeleton_and_joints` when `checked` is `False` if the markers are solely tied to skeleton visibility.
    *   [ ] Ensure joint markers are also cleared/recreated appropriately during `load_parts` if joints are redefined.

### Part 3: (Optional Refinement) Torso as Explicit IK Root

1.  **Identify Root in `build_kinematic_chains`:**
    *   [ ] Prioritize finding a `CharacterPartItem` named "torso" that `is_fixed`.
    *   [ ] If found, all kinematic chains relevant for full-body IK (like arm or leg movements) should trace back to this torso.

## Testing Plan:
*   Load a character with multiple parts (e.g., torso, upper arm, lower arm, hand).
*   Define joints connecting them, with the torso fixed.
*   Define a motion path for the hand.
*   Run the simulation.
    *   Verify: Limbs move cohesively. Parts should not revert to a global "initial rotation."
    *   Verify: Visual joint anchors appear at each joint location and move with the joints.
    *   Verify: Toggling "Show Skeleton" also toggles the visibility of these joint anchors.
    *   Verify: Resetting simulation correctly resets part positions.

## 3. Dependencies & Tools

*   Python 3.x
*   PyQt6
*   PyYAML
*   NumPy (potentially for advanced geometry/kinematics)
*   OpenCV-Python (for image processing)
*   (Future) Libraries for geometry processing, SVG manipulation, PDF generation.

## 4. Tracking

*   Progress will be tracked via commit history and potentially an issue tracker.
*   This document (`plan.md`) and `llm.txt` will serve as living documents, updated as phases are completed or requirements change.