# End-to-End Test Scenarios

This document outlines all the test scenarios covered by the E2E test suite for the Automataii application.

## Test Organization

The E2E tests are organized into four main test files:

1. **test_e2e_base_workflow.py** - Complete workflows from start to finish
2. **test_e2e_canvas_operations.py** - Canvas drawing, zooming, and panning
3. **test_e2e_mechanism_integration.py** - Mechanism placement and adaptation
4. **test_e2e_export_functionality.py** - File export and validation

## Detailed Test Scenarios

### 1. Base Workflow Tests (test_e2e_base_workflow.py)

#### test_landing_to_export_workflow
- **Purpose**: Tests the complete happy path from landing page to final export
- **Steps**:
  1. Select example image from landing tab
  2. Process image to extract skeleton
  3. Generate body parts
  4. Switch to editor and draw motion paths
  5. Generate mechanisms
  6. Export blueprint as SVG
- **Verifies**: End-to-end functionality works correctly

#### test_direct_image_load_workflow
- **Purpose**: Tests workflow starting with direct image load
- **Steps**:
  1. Load image directly via file dialog
  2. Process and continue normal workflow
- **Verifies**: Alternative entry points work correctly

#### test_project_save_and_load_workflow
- **Purpose**: Tests project persistence
- **Steps**:
  1. Create project with processed image and parts
  2. Save project to .ata file
  3. Clear state and reload project
- **Verifies**: Project data is correctly saved and restored

#### test_mechanism_recommendation_workflow
- **Purpose**: Tests AI-powered mechanism recommendation
- **Steps**:
  1. Draw motion path for a part
  2. Click recommendation button
  3. Select recommended mechanism type
- **Verifies**: Recommendation system integration works

#### test_error_handling_workflow
- **Purpose**: Tests error handling throughout the application
- **Scenarios**:
  - Processing without loaded image
  - Generating mechanism without motion path
  - Invalid mechanism parameters
- **Verifies**: Proper error messages and disabled states

#### test_multi_part_animation_workflow
- **Purpose**: Tests animating multiple parts simultaneously
- **Steps**:
  1. Create multiple animated parts
  2. Draw unique paths for each
  3. Generate different mechanism types
  4. Run synchronized animation
- **Verifies**: Multiple mechanisms work together correctly

### 2. Canvas Operations Tests (test_e2e_canvas_operations.py)

#### test_freehand_path_drawing
- **Purpose**: Tests drawing motion paths on canvas
- **Features**:
  - Freehand drawing with mouse
  - Path smoothing
  - Complex curved paths
- **Verifies**: Path drawing creates valid motion data

#### test_canvas_zoom_operations
- **Purpose**: Tests zoom functionality
- **Features**:
  - Mouse wheel zoom in/out
  - Zoom to fit
  - Zoom reset (Ctrl+0)
- **Verifies**: View scaling works correctly

#### test_canvas_pan_operations
- **Purpose**: Tests panning the view
- **Features**:
  - Middle mouse button pan
  - Alt+Left mouse pan
- **Verifies**: View translation works correctly

#### test_part_selection_and_movement
- **Purpose**: Tests interactive part manipulation
- **Features**:
  - Click to select parts
  - Drag to move parts
  - Visual selection feedback
- **Verifies**: Part interaction is intuitive

#### test_joint_definition_on_canvas
- **Purpose**: Tests defining skeleton joints
- **Features**:
  - Click to place joints
  - Parent-child relationships
  - Cancel with ESC
- **Verifies**: Joint creation workflow

#### test_grid_snapping
- **Purpose**: Tests grid display and units
- **Features**:
  - Grid visibility
  - Unit switching (cm, inch, px)
  - Grid-based alignment
- **Verifies**: Grid system functionality

#### test_context_menu_operations
- **Purpose**: Tests right-click context menus
- **Features**:
  - Part-specific menus
  - Canvas menus
  - Context-sensitive options
- **Verifies**: Context menu system

#### test_multi_selection_operations
- **Purpose**: Tests selecting multiple items
- **Features**:
  - Rubber band selection
  - Multiple item manipulation
- **Verifies**: Multi-selection works correctly

#### test_undo_redo_canvas_operations
- **Purpose**: Tests undo/redo functionality
- **Features**:
  - Undo with Ctrl+Z
  - Redo with Ctrl+Y
  - Operation history
- **Verifies**: Edit history management

#### test_touch_gesture_support
- **Purpose**: Tests tablet/touch support
- **Features**:
  - Pinch to zoom
  - Touch gestures
- **Verifies**: Touch input infrastructure

#### test_canvas_coordinate_systems
- **Purpose**: Tests coordinate conversions
- **Features**:
  - Scene to view coordinates
  - Zoom-aware conversions
- **Verifies**: Coordinate math is correct

### 3. Mechanism Integration Tests (test_e2e_mechanism_integration.py)

#### test_cam_mechanism_generation_and_placement
- **Purpose**: Tests cam mechanism creation
- **Features**:
  - Cam center selection
  - Profile generation
  - Animation playback
- **Verifies**: Cam mechanisms work correctly

#### test_fourbar_mechanism_with_pivots
- **Purpose**: Tests four-bar linkage creation
- **Features**:
  - Pivot point selection
  - Link generation
  - Kinematic constraints
- **Verifies**: Linkage mechanisms work correctly

#### test_mechanism_editing_mode
- **Purpose**: Tests interactive mechanism editing
- **Features**:
  - Edit mode toggle
  - Anchor dragging
  - Constraint display
- **Verifies**: Mechanisms can be modified

#### test_gear_mechanism_integration
- **Purpose**: Tests gear mechanism creation
- **Features**:
  - Gear generation
  - Meshing verification
  - Opposite rotation
- **Verifies**: Gear systems work correctly

#### test_mechanism_adaptation_to_path
- **Purpose**: Tests mechanism optimization
- **Features**:
  - Path matching
  - Best mechanism selection
  - Adaptation algorithms
- **Verifies**: Mechanisms adapt to paths

#### test_multi_mechanism_synchronization
- **Purpose**: Tests multiple mechanisms together
- **Features**:
  - Multiple part animation
  - Synchronized motion
  - Combined systems
- **Verifies**: Complex automata work

#### test_mechanism_collision_detection
- **Purpose**: Tests collision handling
- **Features**:
  - Overlapping detection
  - Conflict visualization
- **Verifies**: Collision system exists

#### test_mechanism_performance_optimization
- **Purpose**: Tests motion smoothing
- **Features**:
  - Jerky motion handling
  - Profile optimization
  - Smooth output
- **Verifies**: Optimization algorithms work

### 4. Export Functionality Tests (test_e2e_export_functionality.py)

#### test_svg_blueprint_export
- **Purpose**: Tests SVG export for fabrication
- **Features**:
  - Valid SVG structure
  - Mechanism outlines
  - Dimension labels
  - Assembly marks
- **Verifies**: SVG files are valid and complete

#### test_json_project_export
- **Purpose**: Tests JSON data export
- **Features**:
  - Complete project data
  - Character information
  - Mechanism parameters
  - Metadata
- **Verifies**: JSON contains all project data

#### test_stl_3d_export
- **Purpose**: Tests 3D model export
- **Features**:
  - STL file structure
  - 3D geometry
  - Valid format
- **Verifies**: STL files are valid

#### test_dxf_2d_profile_export
- **Purpose**: Tests DXF export for laser cutting
- **Features**:
  - DXF file structure
  - 2D profiles
  - Layer organization
- **Verifies**: DXF files are valid

#### test_animated_gif_export
- **Purpose**: Tests animation export
- **Features**:
  - GIF recording
  - Animation capture
  - File validation
- **Verifies**: Animations can be exported

#### test_batch_export_multiple_formats
- **Purpose**: Tests exporting to multiple formats
- **Features**:
  - Format selection
  - Batch processing
  - Multiple outputs
- **Verifies**: Batch export works

#### test_export_with_custom_settings
- **Purpose**: Tests export customization
- **Features**:
  - Scale factor
  - Unit selection
  - Optional elements
- **Verifies**: Export options work

#### test_export_error_handling
- **Purpose**: Tests export error cases
- **Features**:
  - Permission errors
  - Invalid paths
  - Empty projects
- **Verifies**: Errors handled gracefully

#### test_export_large_project_performance
- **Purpose**: Tests performance with large projects
- **Features**:
  - Many mechanisms
  - Performance timing
  - Memory usage
- **Verifies**: Scales to large projects

## Test Utilities and Fixtures

### TestImageGenerator
- Creates test character images
- Generates skeleton data
- Creates body parts info
- Generates motion paths

### E2ETestBase
- Common test setup/teardown
- Window creation helpers
- UI interaction utilities
- File verification methods

### Mock Services
- MockProcessingService for faster tests
- Mocked dialogs for automation
- File system mocking

## Running the Tests

```bash
# Run all E2E tests
pytest tests/e2e/ -v

# Run specific test file
pytest tests/e2e/test_e2e_base_workflow.py -v

# Run with GUI visible (slower but useful for debugging)
pytest tests/e2e/ -v -s --no-qt-log

# Run specific test
pytest tests/e2e/test_e2e_canvas_operations.py::TestE2ECanvasOperations::test_freehand_path_drawing -v
```

## Best Practices

1. **Test Independence**: Each test should be independent and not rely on others
2. **Cleanup**: Always clean up created files and resources
3. **Mocking**: Mock external dependencies (file dialogs, processing) for speed
4. **Assertions**: Verify actual functionality, not just that code runs
5. **Timeouts**: Use appropriate timeouts for async operations
6. **Visual Verification**: Some tests verify visual elements exist and change

## Future Test Scenarios

1. **Performance Tests**:
   - Large image processing
   - Complex path optimization
   - Memory usage monitoring

2. **Integration Tests**:
   - External tool integration
   - Plugin system testing
   - Network features

3. **Accessibility Tests**:
   - Keyboard navigation
   - Screen reader support
   - High contrast modes

4. **Platform Tests**:
   - Windows-specific features
   - macOS-specific features
   - Linux compatibility