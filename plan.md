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