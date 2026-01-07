"""
Animation Module.

Provides centralized animation scheduling and viewport control utilities.

Architecture: Presentation Layer

Real-Time Components:
- RealTimeAnimationEngine: High-level facade for off-thread computation
- AcceleratedAnimationScheduler: Scheduler with integrated compute engine
- ComputeThread/DoubleBuffer: Threading infrastructure
- OpenGLCanvas/GeometryBuffer: GPU rendering (optional)
"""

from .compute_thread import ComputeThread, DoubleBuffer, FrameData
from .opengl_renderer import GeometryBuffer, OpenGLCanvas
from .performance import PerformanceProfiler
from .realtime_engine import EngineConfig, RealTimeAnimationEngine
from .scheduler import AnimationPriority, AnimationSubscription, CentralAnimationScheduler
from .scheduler_accelerated import AcceleratedAnimationScheduler
from .viewport_controller import ViewportConfig, ViewportController

__all__ = [
    # Animation scheduling
    "CentralAnimationScheduler",
    "AcceleratedAnimationScheduler",
    "AnimationPriority",
    "AnimationSubscription",
    # Real-time engine
    "RealTimeAnimationEngine",
    "EngineConfig",
    # Threading infrastructure
    "ComputeThread",
    "DoubleBuffer",
    "FrameData",
    # OpenGL rendering
    "OpenGLCanvas",
    "GeometryBuffer",
    # Performance monitoring
    "PerformanceProfiler",
    # Viewport control
    "ViewportController",
    "ViewportConfig",
]
