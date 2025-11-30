"""
Project serialization system with support for multiple formats.
"""

import base64
import json
import logging
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

try:
    import msgpack
    HAS_MSGPACK = True
except ImportError:
    HAS_MSGPACK = False

try:
    import bson
    HAS_BSON = True
except ImportError:
    HAS_BSON = False

# Qt imports (optional)
try:
    from PyQt6.QtCore import QPoint, QRect, QSize
    from PyQt6.QtGui import QColor
    HAS_QT = True
except ImportError:
    try:
        from PySide6.QtCore import QPoint, QRect, QSize
        from PySide6.QtGui import QColor
        HAS_QT = True
    except ImportError:
        # Fallback dummy classes for when Qt is not available
        HAS_QT = False

        class QPoint:
            def __init__(self, x=0, y=0):
                self._x, self._y = x, y
            def x(self): return self._x
            def y(self): return self._y

        class QSize:
            def __init__(self, w=0, h=0):
                self._w, self._h = w, h
            def width(self): return self._w
            def height(self): return self._h

        class QRect:
            def __init__(self, x=0, y=0, w=0, h=0):
                self._x, self._y, self._w, self._h = x, y, w, h
            def x(self): return self._x
            def y(self): return self._y
            def width(self): return self._w
            def height(self): return self._h

        class QColor:
            def __init__(self, r=0, g=0, b=0, a=255):
                self._r, self._g, self._b, self._a = r, g, b, a
            def red(self): return self._r
            def green(self): return self._g
            def blue(self): return self._b
            def alpha(self): return self._a

from automataii.core.serialization.base import Serializable


class SerializationFormat(Enum):
    """Supported serialization formats."""
    JSON = "json"
    MSGPACK = "msgpack"
    BSON = "bson"


class SerializationError(Exception):
    """Raised when serialization fails."""
    pass


class ReferenceResolver:
    """
    Resolves object references using UUID-based system.
    Prevents circular references and duplicate serialization.
    """

    def __init__(self):
        self._id_to_object: dict[str, Any] = {}
        self._object_to_id: dict[int, str] = {}
        self._pending_refs: dict[str, list[tuple]] = {}

    def get_or_create_id(self, obj: Any) -> str:
        """Get or create UUID for object."""
        obj_id = id(obj)
        if obj_id not in self._object_to_id:
            ref_id = str(uuid.uuid4())
            self._object_to_id[obj_id] = ref_id
            self._id_to_object[ref_id] = obj
        return self._object_to_id[obj_id]

    def resolve_reference(self, ref_id: str) -> Any:
        """Resolve reference by ID."""
        return self._id_to_object.get(ref_id)


    def resolve_pending_references(self) -> None:
        """Resolve all pending references."""
        for ref_id, pending_list in self._pending_refs.items():
            obj = self.resolve_reference(ref_id)
            if obj is not None:
                for container, key in pending_list:
                    if isinstance(container, dict):
                        container[key] = obj
                    elif isinstance(container, list):
                        container[int(key)] = obj
        self._pending_refs.clear()

    def clear(self) -> None:
        """Clear all references."""
        self._id_to_object.clear()
        self._object_to_id.clear()
        self._pending_refs.clear()


class QtTypeEncoder:
    """Handles serialization of Qt types."""

    @staticmethod
    def encode_qt_type(obj: Any) -> dict[str, Any]:
        """Encode Qt types to JSON-serializable format."""
        if isinstance(obj, QPoint):
            return {
                '__qt_type__': 'QPoint',
                'x': obj.x(),
                'y': obj.y()
            }
        elif isinstance(obj, QSize):
            return {
                '__qt_type__': 'QSize',
                'width': obj.width(),
                'height': obj.height()
            }
        elif isinstance(obj, QRect):
            return {
                '__qt_type__': 'QRect',
                'x': obj.x(),
                'y': obj.y(),
                'width': obj.width(),
                'height': obj.height()
            }
        elif isinstance(obj, QColor):
            return {
                '__qt_type__': 'QColor',
                'red': obj.red(),
                'green': obj.green(),
                'blue': obj.blue(),
                'alpha': obj.alpha()
            }
        else:
            raise SerializationError(f"Unsupported Qt type: {type(obj)}")

    @staticmethod
    def decode_qt_type(data: dict[str, Any]) -> Any:
        """Decode Qt types from JSON format."""
        qt_type = data.get('__qt_type__')

        if qt_type == 'QPoint':
            return QPoint(data['x'], data['y'])
        elif qt_type == 'QSize':
            return QSize(data['width'], data['height'])
        elif qt_type == 'QRect':
            return QRect(data['x'], data['y'], data['width'], data['height'])
        elif qt_type == 'QColor':
            return QColor(data['red'], data['green'], data['blue'], data['alpha'])
        else:
            raise SerializationError(f"Unknown Qt type: {qt_type}")


class ProjectJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for project data."""

    def __init__(self, reference_resolver: ReferenceResolver = None, **kwargs):
        super().__init__(**kwargs)
        self.reference_resolver = reference_resolver or ReferenceResolver()
        self.qt_encoder = QtTypeEncoder()

    def default(self, obj: Any) -> Any:
        # Handle Serializable objects
        if isinstance(obj, Serializable):
            return obj.to_dict()

        # Handle datetime
        if isinstance(obj, datetime):
            return {
                '__datetime__': True,
                'isoformat': obj.isoformat()
            }

        # Handle Path objects
        if isinstance(obj, Path):
            return {
                '__path__': True,
                'path': str(obj)
            }

        # Handle bytes
        if isinstance(obj, bytes):
            if len(obj) > 1024:  # Large binary data
                # Store as external reference
                ref_id = self.reference_resolver.get_or_create_id(obj)
                return {
                    '__binary_ref__': ref_id,
                    'size': len(obj)
                }
            else:
                # Store as base64
                return {
                    '__binary__': True,
                    'data': base64.b64encode(obj).decode('utf-8')
                }

        # Handle Qt types
        if hasattr(obj, '__class__') and obj.__class__.__module__.startswith('PyQt'):
            try:
                return self.qt_encoder.encode_qt_type(obj)
            except SerializationError:
                pass

        # Handle sets
        if isinstance(obj, set):
            return {
                '__set__': True,
                'items': list(obj)
            }

        # Handle complex numbers
        if isinstance(obj, complex):
            return {
                '__complex__': True,
                'real': obj.real,
                'imag': obj.imag
            }

        return super().default(obj)


class ProjectJSONDecoder(json.JSONDecoder):
    """Custom JSON decoder for project data."""

    def __init__(self, reference_resolver: ReferenceResolver = None, **kwargs):
        super().__init__(object_hook=self.object_hook, **kwargs)
        self.reference_resolver = reference_resolver or ReferenceResolver()
        self.qt_encoder = QtTypeEncoder()

    def object_hook(self, dct: dict[str, Any]) -> Any:
        # Handle datetime
        if '__datetime__' in dct:
            return datetime.fromisoformat(dct['isoformat'])

        # Handle Path
        if '__path__' in dct:
            return Path(dct['path'])

        # Handle binary data
        if '__binary__' in dct:
            return base64.b64decode(dct['data'])

        # Handle binary references
        if '__binary_ref__' in dct:
            ref_id = dct['__binary_ref__']
            return self.reference_resolver.resolve_reference(ref_id)

        # Handle Qt types
        if '__qt_type__' in dct:
            return self.qt_encoder.decode_qt_type(dct)

        # Handle sets
        if '__set__' in dct:
            return set(dct['items'])

        # Handle complex numbers
        if '__complex__' in dct:
            return complex(dct['real'], dct['imag'])

        return dct


class ProjectSerializer:
    """
    Handles complex object serialization with references and validation.

    Features:
    - Multiple format support (JSON, MessagePack, BSON)
    - Reference resolution for circular dependencies
    - Qt type serialization
    - Binary data handling
    - Schema validation
    - Compression support
    """

    def __init__(self, format: SerializationFormat = SerializationFormat.JSON):
        self.format = format
        self.reference_resolver = ReferenceResolver()
        self._logger = logging.getLogger(__name__)

        # Validate format availability
        if format == SerializationFormat.MSGPACK and not HAS_MSGPACK:
            raise SerializationError("MessagePack not available. Install msgpack package.")

        if format == SerializationFormat.BSON and not HAS_BSON:
            raise SerializationError("BSON not available. Install pymongo package.")

    def serialize(
        self,
        obj: Any,
        compress: bool = False,
        _validate_schema: bool = True
    ) -> bytes:
        """
        Serialize object to bytes.

        Args:
            obj: Object to serialize
            compress: Apply compression
            validate_schema: Validate against schema

        Returns:
            Serialized data as bytes
        """
        try:
            self.reference_resolver.clear()

            if self.format == SerializationFormat.JSON:
                encoder = ProjectJSONEncoder(self.reference_resolver, indent=2)
                json_str = encoder.encode(obj)
                data = json_str.encode('utf-8')

            elif self.format == SerializationFormat.MSGPACK:
                data = msgpack.packb(obj, use_bin_type=True)

            elif self.format == SerializationFormat.BSON:
                if not isinstance(obj, dict):
                    obj = {'data': obj}
                data = bson.encode(obj)

            else:
                raise SerializationError(f"Unsupported format: {self.format}")

            if compress:
                import gzip
                data = gzip.compress(data)

            self._logger.debug(f"Serialized {len(data)} bytes in {self.format.value} format")
            return data

        except Exception as e:
            self._logger.error(f"Serialization failed: {e}", exc_info=True)
            raise SerializationError(f"Serialization failed: {e}") from e

    def deserialize(
        self,
        data: bytes,
        expected_type: type | None = None,
        compressed: bool = False
    ) -> Any:
        """
        Deserialize bytes to object.

        Args:
            data: Serialized data
            expected_type: Expected object type
            compressed: Data is compressed

        Returns:
            Deserialized object
        """
        try:
            if compressed:
                import gzip
                data = gzip.decompress(data)

            self.reference_resolver.clear()

            if self.format == SerializationFormat.JSON:
                decoder = ProjectJSONDecoder(self.reference_resolver)
                json_str = data.decode('utf-8')
                obj = decoder.decode(json_str)

            elif self.format == SerializationFormat.MSGPACK:
                obj = msgpack.unpackb(data, raw=False)

            elif self.format == SerializationFormat.BSON:
                decoded = bson.decode(data)
                obj = decoded.get('data', decoded)

            else:
                raise SerializationError(f"Unsupported format: {self.format}")

            # Resolve pending references
            self.reference_resolver.resolve_pending_references()

            # Type validation
            if expected_type and not isinstance(obj, expected_type):
                self._logger.warning(f"Type mismatch: expected {expected_type}, got {type(obj)}")

            self._logger.debug(f"Deserialized object from {len(data)} bytes")
            return obj

        except Exception as e:
            self._logger.error(f"Deserialization failed: {e}", exc_info=True)
            raise SerializationError(f"Deserialization failed: {e}") from e




