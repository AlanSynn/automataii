"""
Pydantic validation schemas for JSON data.

This module provides type-safe validation for JSON data loaded from
files or external sources, preventing invalid data from corrupting
application state.
"""

from automataii.infrastructure.validation.schemas import (
    MechanismCatalogSchema,
    MechanismCategorySchema,
    MechanismEntrySchema,
    MechanismParameterSchema,
    ValidationError,
    validate_mechanism_catalog,
)

__all__ = [
    "MechanismParameterSchema",
    "MechanismEntrySchema",
    "MechanismCategorySchema",
    "MechanismCatalogSchema",
    "validate_mechanism_catalog",
    "ValidationError",
]
