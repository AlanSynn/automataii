"""Four-bar linkage mechanism module."""

# Register with the mechanism registry
from ..registry import mechanism_registry
from .editor import FourBarEditor
from .mechanism import FourBarMechanism
from .serializer import FourBarSerializer

mechanism_registry.register_mechanism(
    mechanism_type="four_bar",
    mechanism_class=FourBarMechanism,
    editor_class=FourBarEditor,
    serializer_class=FourBarSerializer,
    metadata={
        'display_name': '4-Bar Linkage',
        'description': 'Four-bar linkage mechanism with customizable link lengths',
        'icon': 'four_bar.svg',
        'category': 'linkages',
        'complexity': 'medium'
    }
)

__all__ = ['FourBarMechanism', 'FourBarEditor', 'FourBarSerializer']
