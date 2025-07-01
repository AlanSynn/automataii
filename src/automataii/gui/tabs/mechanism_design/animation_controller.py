# mechanism_design/animation_controller.py

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

class MechanismAnimationController(QObject):
    """
    (Controller) QTimer와 애니메이션 로직을 전담합니다.
    """
    tick = pyqtSignal(float)
    reset_animation = pyqtSignal()

    def __init__(self, state_manager, parent=None):
        super().__init__(parent)
        self.state = state_manager
        self.timer = QTimer(self)
        self.timer.setInterval(16) # ~60 FPS
        self.timer.timeout.connect(self._on_tick)
        self.animation_time = 0.0
        self.animation_speed = 1.0 # radians per second

    def _on_tick(self):
        self.animation_time += self.animation_speed * (self.timer.interval() / 1000.0)
        self.tick.emit(self.animation_time)

    def start(self):
        if not self.timer.isActive():
            self.timer.start()

    def stop(self):
        if self.timer.isActive():
            self.timer.stop()

    def reset(self):
        self.stop()
        self.animation_time = 0.0
        self.reset_animation.emit()
        self.tick.emit(0.0)
