"""Common utilities for GUI testing following PySide/PyQt testing patterns."""

import sys
import time
from unittest.mock import MagicMock, patch
from typing import Optional, Any, Callable, List, Tuple

from PyQt6.QtCore import Qt, QTimer, QPoint, QPointF, QEventLoop
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtTest import QTest


class QtTestCase:
    """Base class for Qt test cases with common utilities."""
    
    @classmethod
    def setUpClass(cls):
        """Ensure QApplication exists for all tests."""
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()
    
    def setUp(self):
        """Set up test case."""
        self.widgets_to_cleanup = []
        
    def tearDown(self):
        """Clean up widgets after test."""
        for widget in self.widgets_to_cleanup:
            if widget and not widget.isHidden():
                widget.close()
            if widget:
                widget.deleteLater()
        
        # Process events to ensure cleanup
        QApplication.processEvents()
        
    def register_widget(self, widget: QWidget) -> QWidget:
        """Register widget for cleanup."""
        self.widgets_to_cleanup.append(widget)
        return widget


class SignalSpy:
    """Helper class to spy on Qt signals."""
    
    def __init__(self, signal):
        self.signal = signal
        self.emissions = []
        self.signal.connect(self._record_emission)
        
    def _record_emission(self, *args):
        """Record signal emission with arguments."""
        self.emissions.append(args)
        
    def wait(self, timeout: int = 1000) -> bool:
        """Wait for signal emission with timeout."""
        loop = QEventLoop()
        timer = QTimer()
        timer.timeout.connect(loop.quit)
        self.signal.connect(loop.quit)
        timer.start(timeout)
        loop.exec()
        timer.stop()
        return len(self.emissions) > 0
        
    def count(self) -> int:
        """Get number of emissions."""
        return len(self.emissions)
        
    def last_emission(self) -> Tuple[Any, ...]:
        """Get arguments from last emission."""
        if self.emissions:
            return self.emissions[-1]
        return ()
        
    def clear(self):
        """Clear recorded emissions."""
        self.emissions.clear()


def click_widget(widget: QWidget, pos: Optional[QPoint] = None, 
                button: Qt.MouseButton = Qt.MouseButton.LeftButton,
                modifier: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier):
    """Simulate mouse click on widget."""
    if pos is None:
        pos = widget.rect().center()
    
    QTest.mouseClick(widget, button, modifier, pos)
    QApplication.processEvents()


def double_click_widget(widget: QWidget, pos: Optional[QPoint] = None,
                       button: Qt.MouseButton = Qt.MouseButton.LeftButton,
                       modifier: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier):
    """Simulate mouse double click on widget."""
    if pos is None:
        pos = widget.rect().center()
    
    QTest.mouseDClick(widget, button, modifier, pos)
    QApplication.processEvents()


def drag_widget(widget: QWidget, start: QPoint, end: QPoint,
               button: Qt.MouseButton = Qt.MouseButton.LeftButton,
               modifier: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier):
    """Simulate mouse drag on widget."""
    QTest.mousePress(widget, button, modifier, start)
    QApplication.processEvents()
    
    # Simulate intermediate positions for smooth drag
    steps = 5
    for i in range(1, steps + 1):
        t = i / steps
        x = int(start.x() + (end.x() - start.x()) * t)
        y = int(start.y() + (end.y() - start.y()) * t)
        QTest.mouseMove(widget, QPoint(x, y))
        QApplication.processEvents()
    
    QTest.mouseRelease(widget, button, modifier, end)
    QApplication.processEvents()


def type_text(widget: QWidget, text: str):
    """Type text into widget."""
    widget.setFocus()
    QApplication.processEvents()
    
    for char in text:
        QTest.keyClick(widget, char)
        QApplication.processEvents()


def press_key(widget: QWidget, key: Qt.Key,
             modifier: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier):
    """Press a key on widget."""
    QTest.keyPress(widget, key, modifier)
    QApplication.processEvents()


def wait_for_condition(condition: Callable[[], bool], 
                      timeout: int = 5000, 
                      interval: int = 100) -> bool:
    """Wait for a condition to become true."""
    elapsed = 0
    while elapsed < timeout:
        if condition():
            return True
        QTest.qWait(interval)
        elapsed += interval
    return False


def wait_for_widget_enabled(widget: QWidget, timeout: int = 5000) -> bool:
    """Wait for widget to become enabled."""
    return wait_for_condition(lambda: widget.isEnabled(), timeout)


def wait_for_widget_visible(widget: QWidget, timeout: int = 5000) -> bool:
    """Wait for widget to become visible."""
    return wait_for_condition(lambda: widget.isVisible(), timeout)


def get_child_widgets(parent: QWidget, widget_type: type) -> List[QWidget]:
    """Get all child widgets of specific type."""
    return parent.findChildren(widget_type)


def get_child_widget(parent: QWidget, widget_type: type, 
                    name: Optional[str] = None) -> Optional[QWidget]:
    """Get first child widget of specific type."""
    if name:
        children = parent.findChildren(widget_type, name)
    else:
        children = parent.findChildren(widget_type)
    
    return children[0] if children else None


def process_events_for(duration_ms: int = 100):
    """Process events for specified duration."""
    QTest.qWait(duration_ms)


class MockSignal:
    """Mock Qt signal for testing."""
    
    def __init__(self):
        self.callbacks = []
        self.emissions = []
        
    def connect(self, callback):
        """Connect callback to signal."""
        self.callbacks.append(callback)
        
    def disconnect(self, callback=None):
        """Disconnect callback from signal."""
        if callback and callback in self.callbacks:
            self.callbacks.remove(callback)
        elif callback is None:
            self.callbacks.clear()
            
    def emit(self, *args):
        """Emit signal with arguments."""
        self.emissions.append(args)
        for callback in self.callbacks:
            callback(*args)


def create_mock_config(base_type: str = 'rectangular', **kwargs) -> dict:
    """Create mock base configuration."""
    config = {
        'type': base_type,
        'material': 'Wood - Plywood',
        'thickness': 6.0
    }
    
    if base_type == 'rectangular':
        config.update({
            'width': kwargs.get('width', 200),
            'depth': kwargs.get('depth', 150),
            'height': kwargs.get('height', 50)
        })
    elif base_type == 'cylindrical':
        config.update({
            'radius': kwargs.get('radius', 100),
            'height': kwargs.get('height', 60)
        })
    elif base_type == 'custom':
        config.update({
            'file': kwargs.get('file', 'test.stl')
        })
    
    return config


def create_mock_mechanism(mech_id: str = 'test_mech', 
                         position: Tuple[float, float, float] = (0, 0, 0)) -> dict:
    """Create mock mechanism placement info."""
    return {
        'position': position,
        'connection_points': [
            {'position': (10, 0, 0), 'type': 'motor'},
            {'position': (-10, 0, 0), 'type': 'support'},
            {'position': (0, 10, 0), 'type': 'output'}
        ]
    }


def assert_signal_emitted(spy: SignalSpy, expected_count: int = 1,
                         message: Optional[str] = None):
    """Assert signal was emitted expected number of times."""
    actual_count = spy.count()
    if message is None:
        message = f"Expected signal to be emitted {expected_count} times, but got {actual_count}"
    assert actual_count == expected_count, message


def assert_signal_not_emitted(spy: SignalSpy, message: Optional[str] = None):
    """Assert signal was not emitted."""
    if message is None:
        message = f"Expected signal not to be emitted, but it was emitted {spy.count()} times"
    assert spy.count() == 0, message


def assert_last_signal_args(spy: SignalSpy, expected_args: Tuple[Any, ...],
                           message: Optional[str] = None):
    """Assert last signal emission had expected arguments."""
    if spy.count() == 0:
        raise AssertionError("Signal was not emitted")
    
    actual_args = spy.last_emission()
    if message is None:
        message = f"Expected signal args {expected_args}, but got {actual_args}"
    assert actual_args == expected_args, message