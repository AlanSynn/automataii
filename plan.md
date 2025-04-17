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

### Phase 3: Simplified Cam Mechanism Generation & Visualization

- [ ] **Goal:** Implement the initial, simplified cam mechanism generation based on a selected part's motion path, using the torso center as the fixed cam center. Visualize the generated cam.
- [ ] **Deliverables:**
    - [ ] `generate_cam_profile` function in `src/automataii/generation/cam.py` implementing path sampling, polar coordinate conversion, and `QPainterPath` generation for the cam shape.
    - [ ] UI Integration:
        - [ ] Replace individual cam buttons with a single "Generate Mechanism" button.
        - [ ] Button enabled only when a part with a motion path is selected.
        - [ ] Button action triggers automatic generation using the 'torso' part's center as the cam center.
    - [ ] Mechanism Visualization:
        - [ ] Display the generated cam profile(s) in the editor scene, positioned correctly relative to the torso center.
        - [ ] Display the target motion path for the follower.
        - [ ] Display placeholder visuals for potential linkage connections (e.g., the random 4-bar hints).
    - [ ] Layer Management:
        - [ ] Introduce mechanism layer controls (checkboxes) to toggle visibility of generated cams, path hints, etc.
        - [ ] Implement `_add_mechanism_visual`, `_clear_mechanism_visuals`, `_toggle_layer_visibility`.

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
        - [ ] Connect the "Generate Blueprint (SVG)" button to trigger the generation and file save dialog.
    - [ ] File Saving: Prompt user for SVG save location.

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
    - [ ] Include generated mechanism components (cam profiles, linkage dimensions) in the blueprint.
    - [ ] Add assembly indicators (e.g., joint locations, part connections).
    - [ ] Explore different layout strategies for clarity.
    - [ ] Investigate PDF export options.
    - [ ] Add options for scale markers, material thickness notations, etc.

### Phase 7: Refinement & Testing

- [ ] **Goal:** Improve usability, fix bugs, optimize performance, and gather user feedback across all implemented features.
- [ ] **Potential Tasks:**
    - [ ] UI/UX refinements based on user feedback.
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