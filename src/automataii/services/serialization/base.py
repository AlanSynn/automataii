"""
Base serialization classes and interfaces.
"""

import json
from abc import ABC
from datetime import datetime
from typing import Any, TypeVar

T = TypeVar("T", bound="Serializable")


class Serializable(ABC):
    """
    Base class for objects that can be serialized to/from dictionaries.

    Provides automatic serialization of dataclass fields and
    template methods for custom serialization logic.
    """

    def to_dict(self) -> dict[str, Any]:
        """
        Convert object to dictionary representation.

        Returns:
            Dictionary representation of object
        """
        result = {}

        # Get all fields if this is a dataclass
        if hasattr(self, "__dataclass_fields__"):
            import dataclasses

            for field in dataclasses.fields(self):
                value = getattr(self, field.name)
                result[field.name] = self._serialize_value(value)
        else:
            # Fallback to all non-private attributes
            for key, value in self.__dict__.items():
                if not key.startswith("_"):
                    result[key] = self._serialize_value(value)

        # Allow subclasses to customize
        return self.customize_serialization(result)

    @classmethod
    def from_dict(cls: type[T], data: dict[str, Any]) -> T:
        """
        Create object from dictionary representation.

        Args:
            data: Dictionary representation

        Returns:
            Deserialized object instance
        """
        # Allow subclasses to preprocess
        processed_data = cls.customize_deserialization(data)

        # Create instance
        if hasattr(cls, "__dataclass_fields__"):
            # Handle dataclass
            import dataclasses

            field_names = {f.name for f in dataclasses.fields(cls)}
            filtered_data = {
                k: cls._deserialize_value(v, cls._get_field_type(k))
                for k, v in processed_data.items()
                if k in field_names
            }
            return cls(**filtered_data)
        else:
            # Create empty instance and set attributes
            instance = cls.__new__(cls)
            for key, value in processed_data.items():
                if not key.startswith("_"):
                    setattr(instance, key, cls._deserialize_value(value))
            return instance

    def _serialize_value(self, value: Any) -> Any:
        """Serialize a single value."""
        if isinstance(value, Serializable):
            return value.to_dict()
        elif isinstance(value, datetime):
            return {"__datetime__": True, "isoformat": value.isoformat()}
        elif isinstance(value, (list, tuple)):
            return [self._serialize_value(item) for item in value]
        elif isinstance(value, dict):
            return {k: self._serialize_value(v) for k, v in value.items()}
        else:
            return value

    @classmethod
    def _deserialize_value(cls, value: Any, expected_type: type | None = None) -> Any:
        """Deserialize a single value."""
        if isinstance(value, dict):
            # Handle special types
            if "__datetime__" in value:
                return datetime.fromisoformat(value["isoformat"])
            elif expected_type and issubclass(expected_type, Serializable):
                return expected_type.from_dict(value)
            else:
                return {k: cls._deserialize_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [cls._deserialize_value(item) for item in value]
        else:
            return value

    @classmethod
    def _get_field_type(cls, field_name: str) -> type | None:
        """Get type hint for field."""
        if hasattr(cls, "__dataclass_fields__"):
            import dataclasses

            fields = dataclasses.fields(cls)
            for field in fields:
                if field.name == field_name:
                    return field.type
        return None

    def customize_serialization(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Customize serialization output.

        Args:
            data: Default serialized data

        Returns:
            Customized serialized data
        """
        return data

    @classmethod
    def customize_deserialization(cls, data: dict[str, Any]) -> dict[str, Any]:
        """
        Customize deserialization input.

        Args:
            data: Raw deserialized data

        Returns:
            Processed deserialized data
        """
        return data

    def to_json(self, indent: int | None = None) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, default=str)

    @classmethod
    def from_json(cls: type[T], json_str: str) -> T:
        """Create from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)

    def __eq__(self, other) -> bool:
        """Check equality based on serialized representation."""
        if not isinstance(other, self.__class__):
            return False
        return self.to_dict() == other.to_dict()

    def __repr__(self) -> str:
        """String representation."""
        class_name = self.__class__.__name__
        if hasattr(self, "__dataclass_fields__"):
            import dataclasses

            fields = ", ".join(
                f"{field.name}={getattr(self, field.name)!r}" for field in dataclasses.fields(self)
            )
            return f"{class_name}({fields})"
        else:
            attrs = ", ".join(
                f"{k}={v!r}" for k, v in self.__dict__.items() if not k.startswith("_")
            )
            return f"{class_name}({attrs})"


class SerializationMixin:
    """
    Mixin class that adds serialization capabilities to existing classes.

    Use this when you can't inherit from Serializable directly.
    """

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result = {}
        for key, value in self.__dict__.items():
            if not key.startswith("_"):
                result[key] = self._serialize_value(value)
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]):
        """Create from dictionary."""
        instance = cls.__new__(cls)
        for key, value in data.items():
            if not key.startswith("_"):
                setattr(instance, key, cls._deserialize_value(value))
        return instance

    def _serialize_value(self, value: Any) -> Any:
        """Serialize a value."""
        if hasattr(value, "to_dict"):
            return value.to_dict()
        elif isinstance(value, datetime):
            return {"__datetime__": True, "isoformat": value.isoformat()}
        elif isinstance(value, (list, tuple)):
            return [self._serialize_value(item) for item in value]
        elif isinstance(value, dict):
            return {k: self._serialize_value(v) for k, v in value.items()}
        else:
            return value

    @classmethod
    def _deserialize_value(cls, value: Any) -> Any:
        """Deserialize a value."""
        if isinstance(value, dict):
            if "__datetime__" in value:
                return datetime.fromisoformat(value["isoformat"])
            else:
                return {k: cls._deserialize_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [cls._deserialize_value(item) for item in value]
        else:
            return value
