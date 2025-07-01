# src/automataii/kinematics/ik_animator.py
from PyQt6.QtCore import QObject, QTimer, pyqtSignal, QElapsedTimer

class IKAnimator(QObject):
    """
    Manages the timing and animation loop for the IK system.
    Emits a 'tick' with the current animation progress.
    """
    tick = pyqtSignal(float)  # Emits the animation progress (0.0 to 1.0)
    animation_started = pyqtSignal()
    animation_stopped = pyqtSignal()
    animation_reset = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.timer = QTimer(self)
        self.timer.setInterval(30)  # ~33 FPS
        self.timer.timeout.connect(self._on_tick)
        
        self.duration = 3000  # ms
        self.progress = 0.0
        self.elapsed_timer = QElapsedTimer()

    def set_duration(self, duration_ms: int):
        """Sets the total duration for one loop of the animation."""
        if duration_ms > 0:
            self.duration = duration_ms

    def start(self):
        """Starts the animation."""
        if not self.timer.isActive():
            self.elapsed_timer.start()
            self.timer.start()
            self.animation_started.emit()

    def stop(self):
        """Stops the animation."""
        if self.timer.isActive():
            self.timer.stop()
            self.animation_stopped.emit()

    def reset(self):
        """Resets the animation to the beginning."""
        self.stop()
        self.progress = 0.0
        self.tick.emit(0.0)
        self.animation_reset.emit()

    def _on_tick(self):
        """Called on every timer tick to update the animation progress."""
        if self.duration <= 0:
            self.progress = 0.0
        else:
            elapsed = self.elapsed_timer.elapsed()
            self.progress = (elapsed % self.duration) / float(self.duration)
        
        self.tick.emit(self.progress)