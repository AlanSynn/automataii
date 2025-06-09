# GUI Testing Framework for Automata Base Module

This directory contains comprehensive GUI tests for the automata base designer interface.

## Test Structure

The GUI testing framework is organized into the following test files:

1. **test_gui_base_selection_widget.py**
   - Tests for base type selection functionality
   - Tests for specification selection
   - Tests for icon generation
   - Signal emission tests

2. **test_gui_base_preview_widget.py**
   - Tests for base configuration preview
   - Zoom functionality tests
   - Display toggle tests
   - Drawing method tests for different base types
   - Export functionality tests

3. **test_gui_material_selection_widget.py**
   - Material selection tests
   - Thickness range validation
   - Cost calculation tests
   - Material properties display tests

4. **test_gui_dimension_input_widget.py**
   - Dimension input tests for 2D and 3D
   - Unit conversion tests
   - Aspect ratio maintenance tests
   - Common size selection tests

5. **test_gui_base_designer_dialog.py**
   - Main dialog integration tests
   - Export functionality tests (SVG, DXF, STL, STEP, PDF)
   - Validation tests
   - Complete workflow tests

6. **test_gui_integration.py**
   - Cross-component integration tests
   - Complete workflow tests
   - Signal connection tests
   - Error handling tests

## Running Tests

### Run All GUI Tests
```bash
python run_gui_tests.py
```

### Run Specific Test File
```bash
python run_gui_tests.py base_selection_widget
```

### Run with Coverage
```bash
python run_gui_tests.py --coverage
```

### List Available Tests
```bash
python run_gui_tests.py --list
```

### Using pytest Directly
```bash
# Run all GUI tests
pytest -v -k gui

# Run specific test file
pytest test_gui_base_selection_widget.py -v

# Run with coverage
pytest --cov=automataii.modules.automata_base.gui --cov-report=html
```

## Test Features

### Mocking Strategy
All tests use comprehensive Qt mocking to avoid requiring PyQt5/PyQt6 installation during testing:
- Mock Qt widgets, layouts, and dialogs
- Mock signals and slots
- Mock file dialogs and message boxes

### Test Categories

1. **Unit Tests**: Test individual widget functionality
2. **Integration Tests**: Test interactions between widgets
3. **Edge Case Tests**: Test boundary conditions and error handling
4. **Workflow Tests**: Test complete user workflows

### Coverage Areas

- Widget initialization and setup
- User interaction handling
- Signal emission and connection
- Data validation
- Export functionality
- Error handling and recovery
- State management
- Cross-widget communication

## Writing New Tests

When adding new GUI components, follow this pattern:

1. Create a mock_qt_modules() function to mock Qt dependencies
2. Create test classes for:
   - Basic functionality (Test<WidgetName>)
   - Integration scenarios (Test<WidgetName>Integration)
   - Edge cases (Test<WidgetName>EdgeCases)
3. Use fixtures for common setup
4. Test both success and failure paths
5. Verify signal emissions
6. Test data flow between components

## Example Test Structure

```python
def mock_qt_modules():
    """Mock Qt modules before importing."""
    # Mock PyQt6/PyQt5 modules
    
mock_qt_modules()

class TestMyWidget:
    @pytest.fixture
    def widget(self):
        return MyWidget()
    
    def test_initialization(self, widget):
        # Test initial state
        
    def test_user_interaction(self, widget):
        # Test user actions
        
    def test_signals(self, widget):
        # Test signal emission
```

## Continuous Integration

These tests are designed to run in CI environments without GUI dependencies:
- No actual Qt windows are created
- All interactions are simulated through mocks
- Tests run headlessly

## Debugging Tests

To debug failing tests:

1. Run with pytest verbose mode: `pytest -vv test_file.py`
2. Use pytest's `-s` flag to see print statements
3. Check mock call assertions carefully
4. Verify signal connections and emissions

## Future Improvements

- Add visual regression tests using screenshot comparison
- Add performance benchmarks for rendering
- Add accessibility testing
- Add internationalization tests