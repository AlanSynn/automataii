from abc import ABC, abstractmethod
from typing import Any

# from PyQt6.QtCore import QPointF # Common import, might be needed by subclasses


class BaseMechanism(ABC):
    """
    Abstract base class for mechanism generation.
    Provides a common interface for generating mechanism data.
    """

    def __init__(self, name: str, mechanism_type: str):
        self.name = name
        self.mechanism_type = mechanism_type

    @abstractmethod
    def generate(self, **kwargs) -> dict[str, Any] | None:
        """
        Generates and returns the data dictionary for the specific mechanism.
        All specific mechanism generator classes must implement this method.

        Args:
            **kwargs: Specific parameters required by the subclass for generation.

        Returns:
            A dictionary containing the mechanism data, or None if generation fails.
        """
        pass

    def get_description(self) -> dict[str, str]:
        """
        Returns a basic description of the mechanism instance.
        """
        return {"name": self.name, "type": self.mechanism_type}
