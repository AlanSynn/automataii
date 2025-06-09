# Automata Base System GUI Tests

This directory contains comprehensive unit and integration tests for the automata base system GUI components, following the patterns from [Testing PySide GUI Applications](https://ilmanzo.github.io/post/testing_pyside_gui_applications/).

## Test Structure

### Test Files

1. **`gui_test_utils.py`** - Common utilities for GUI testing
   - `QtTestCase` base class for proper Qt setup/teardown
   - `SignalSpy` for monitoring Qt signals
   - Helper functions for simulating user interactions
   - Mock object creators for test data

2. **`test_gui_base_selection.py`** - Tests for BaseSelectionWidget
   - Initial state verification
   - Base type selection (rectangular, cylindrical, custom)
   - Configuration value updates
   - Signal emission testing
   - File selection mocking
   - Value constraints validation

3. **`test_gui_preview.py`** - Tests for BasePreviewWidget  
   - View mode toggling (2D/3D)
   - Zoom and pan controls
   - Mechanism management (add, remove, clear)
   - Mouse interaction handling
   - Coordinate system conversion
   - Rendering verification

4. **`test_gui_integration.py`** - Integration tests
   - Complete workflow testing
   - Widget communication via signals
   - State persistence
   - Performance testing
   - Error handling

## Running Tests

### Run all GUI tests:
```bash
python tests/run_gui_tests.py
```

### Run specific test file:
```bash
python tests/run_gui_tests.py test_gui_base_selection
```

### Run with different verbosity:
```bash
# Quiet mode
python tests/run_gui_tests.py -q

# Verbose mode
python tests/run_gui_tests.py -v
```

### Run individual test class:
```bash
python -m unittest tests.test_gui_base_selection.TestBaseSelectionWidget
```

### Run specific test method:
```bash
python -m unittest tests.test_gui_base_selection.TestBaseSelectionWidget.test_initial_state
```

## Test Patterns Used

### 1. QTest for User Interactions
```python
# Mouse clicks
QTest.mouseClick(widget, Qt.MouseButton.LeftButton, pos=QPoint(x, y))

# Keyboard input
QTest.keyClick(widget, Qt.Key.Key_Return)

# Text input
for char in text:
    QTest.keyClick(widget, char)
```

### 2. SignalSpy for Signal Testing
```python
spy = SignalSpy(widget.some_signal)
# Perform action
assert_signal_emitted(spy, expected_count=1)
assert_last_signal_args(spy, (expected, args))
```

### 3. Proper Setup/Teardown
```python
class TestMyWidget(QtTestCase, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.widget = self.register_widget(MyWidget())
        self.widget.show()
        process_events_for(50)
```

### 4. Mock Objects
```python
@patch('PyQt6.QtWidgets.QFileDialog.getOpenFileName')
def test_file_selection(self, mock_dialog):
    mock_dialog.return_value = ("/path/to/file.stl", "Filter")
    # Test file selection
```

## Key Testing Utilities

### Helper Functions

- `click_widget(widget, pos, button, modifier)` - Simulate mouse clicks
- `drag_widget(widget, start, end)` - Simulate mouse drags
- `type_text(widget, text)` - Type text into widget
- `wait_for_condition(condition, timeout)` - Wait for async operations
- `process_events_for(duration_ms)` - Process Qt events

### Assertion Helpers

- `assert_signal_emitted(spy, count)` - Check signal emission count
- `assert_signal_not_emitted(spy)` - Ensure signal wasn't emitted
- `assert_last_signal_args(spy, args)` - Verify signal arguments

### Mock Data Creators

- `create_mock_config(base_type, **kwargs)` - Create base configurations
- `create_mock_mechanism(id, position)` - Create mechanism data

## Writing New Tests

1. **Inherit from QtTestCase**:
   ```python
   class TestNewWidget(QtTestCase, unittest.TestCase):
   ```

2. **Register widgets for cleanup**:
   ```python
   self.widget = self.register_widget(NewWidget())
   ```

3. **Use SignalSpy for signals**:
   ```python
   spy = SignalSpy(self.widget.data_changed)
   ```

4. **Process events after actions**:
   ```python
   click_widget(button)
   process_events_for(50)  # Give Qt time to process
   ```

5. **Test both positive and negative cases**:
   ```python
   # Test valid input
   self.widget.set_value(100)
   self.assertTrue(self.widget.is_valid())
   
   # Test invalid input
   self.widget.set_value(-1)
   self.assertFalse(self.widget.is_valid())
   ```

## Debugging Tips

1. **Add debug prints in tests**:
   ```python
   print(f"Widget state: {self.widget.get_state()}")
   ```

2. **Increase event processing time**:
   ```python
   process_events_for(200)  # More time for complex operations
   ```

3. **Check widget visibility**:
   ```python
   self.assertTrue(self.widget.isVisible())
   wait_for_widget_visible(self.widget)
   ```

4. **Use verbose mode** to see detailed test output:
   ```bash
   python tests/run_gui_tests.py -v
   ```

## Common Issues and Solutions

1. **"QWidget: Must construct a QApplication before a QWidget"**
   - Ensure you're inheriting from `QtTestCase`
   - Use the `run_gui_tests.py` script

2. **Signal not emitted as expected**
   - Add `process_events_for()` after actions
   - Check signal is connected properly
   - Verify the action triggers the signal

3. **Widget not found**
   - Ensure widget is shown: `widget.show()`
   - Use `get_child_widget()` helper
   - Check widget object names

4. **Flaky tests**
   - Increase wait times
   - Use `wait_for_condition()` instead of fixed delays
   - Ensure proper cleanup in `tearDown()`