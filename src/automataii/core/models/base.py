"""Base models and utilities for core data structures."""

from typing import Any, Dict
from pydantic import BaseModel


class BaseDataModel(BaseModel):
    """Base model for all data models with common functionality."""
    
    class Config:
        """Pydantic configuration."""
        arbitrary_types_allowed = True
        use_enum_values = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return self.model_dump()
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BaseDataModel":
        """Create model from dictionary."""
        return cls(**data)