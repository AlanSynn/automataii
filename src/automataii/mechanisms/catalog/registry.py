"""
Mechanism Registry - Central mechanism type discovery and instantiation

The registry provides a single source of truth for available mechanism types.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from automataii.mechanisms.core.protocols import Mechanism

logger = logging.getLogger(__name__)


class MechanismNotFoundError(Exception):
    pass


class MechanismRegistry:
    _instance: MechanismRegistry | None = None
    _mechanisms: dict[str, type[Mechanism]]

    def __init__(self) -> None:
        self._mechanisms = {}

    @classmethod
    def get_instance(cls) -> MechanismRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, mechanism_type: str, mechanism_class: type[Mechanism]) -> None:
        if mechanism_type in self._mechanisms:
            logger.warning(f"Mechanism type '{mechanism_type}' already registered, overwriting")
        self._mechanisms[mechanism_type] = mechanism_class
        logger.debug(f"Registered mechanism type: {mechanism_type}")

    def get(self, mechanism_type: str) -> Mechanism:
        if mechanism_type not in self._mechanisms:
            raise MechanismNotFoundError(
                f"Mechanism type '{mechanism_type}' not found. "
                f"Available types: {list(self._mechanisms.keys())}"
            )
        mechanism_class = self._mechanisms[mechanism_type]
        return mechanism_class()

    def list_types(self) -> list[str]:
        return list(self._mechanisms.keys())

    def is_registered(self, mechanism_type: str) -> bool:
        return mechanism_type in self._mechanisms


def get_mechanism(mechanism_type: str) -> Mechanism:
    return MechanismRegistry.get_instance().get(mechanism_type)


def list_mechanism_types() -> list[str]:
    return MechanismRegistry.get_instance().list_types()
