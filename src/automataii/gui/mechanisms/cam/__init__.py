"""Cam mechanism module."""

from .mechanism import CamMechanism
from .editor import CamEditor
from .serializer import CamSerializer

# Register with the mechanism registry
from ..registry import mechanism_registry

mechanism_registry.register_mechanism(
    mechanism_type="cam",
    mechanism_class=CamMechanism,
    editor_class=CamEditor,
    serializer_class=CamSerializer,
    metadata={
        'display_name': 'Cam & Follower',
        'description': 'Cam mechanism with customizable profile and follower',
        'icon': 'cam.svg',
        'category': 'cams',
        'complexity': 'medium'
    }
)

__all__ = ['CamMechanism', 'CamEditor', 'CamSerializer']