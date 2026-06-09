"""
Dependency Injection Container.

Provides service registration and resolution with lifetime management.
"""

import inspect
import logging
import threading
from collections.abc import Callable
from enum import Enum
from typing import (
    Any,
    Generic,
    Optional,
    TypeVar,
    get_type_hints,
)
from weakref import WeakKeyDictionary

T = TypeVar("T")


class Lifetime(Enum):
    """Service lifetime modes."""

    SINGLETON = "singleton"  # One instance for entire application
    TRANSIENT = "transient"  # New instance every time
    SCOPED = "scoped"  # One instance per scope


class Injectable:
    """
    Base class for injectable services.
    Provides automatic dependency resolution.

    Note: This is a marker class, not an abstract base class.
    Subclasses are automatically marked as injectable.
    """

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Mark class as injectable
        cls._injectable = True


class ServiceDescriptor(Generic[T]):
    """Describes how to create and manage a service."""

    def __init__(
        self,
        service_type: type[T],
        implementation: type[T] | None = None,
        factory: Callable[..., T] | None = None,
        instance: T | None = None,
        lifetime: Lifetime = Lifetime.TRANSIENT,
        name: str | None = None,
    ):
        self.service_type = service_type
        self.implementation = implementation or service_type
        self.factory = factory
        self.instance = instance
        self.lifetime = lifetime
        self.name = name or service_type.__name__

        # Validation
        if not any([implementation, factory, instance]):
            raise ValueError("Must provide implementation, factory, or instance")

        if lifetime == Lifetime.SINGLETON and instance:
            # Pre-created singleton
            pass
        elif not (implementation or factory):
            raise ValueError("Must provide implementation or factory for non-instance services")


class Scope:
    """Represents a dependency injection scope."""

    def __init__(self, name: str = "default"):
        self.name = name
        self._instances: dict[str, Any] = {}
        self._lock = threading.RLock()

    def get_instance(self, key: str) -> Any | None:
        """Get instance from this scope."""
        with self._lock:
            return self._instances.get(key)

    def set_instance(self, key: str, instance: Any) -> None:
        """Set instance in this scope."""
        with self._lock:
            self._instances[key] = instance

    def clear(self) -> None:
        """Clear all instances in this scope."""
        with self._lock:
            self._instances.clear()

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc_val, _exc_tb):
        self.clear()


class Container:
    """
    Dependency injection container with hierarchical scoping.

    Features:
    - Automatic constructor injection
    - Multiple lifetime management
    - Hierarchical scoping
    - Circular dependency detection
    - Generic type support
    """

    def __init__(self, parent: Optional["Container"] = None):
        self.parent = parent
        self._services: dict[str, ServiceDescriptor] = {}
        self._singletons: dict[str, Any] = {}
        self._scopes: dict[str, Scope] = {}
        self._current_scope: Scope | None = None
        self._lock = threading.RLock()
        self._logger = logging.getLogger(__name__)
        self._resolving: set[str] = set()  # Circular dependency detection

        # Weak reference cache for performance
        self._resolution_cache: WeakKeyDictionary = WeakKeyDictionary()

    def register_singleton(
        self,
        service_type: type[T],
        implementation: type[T] | None = None,
        factory: Callable[..., T] | None = None,
        instance: T | None = None,
    ) -> "Container":
        """Register a singleton service."""
        return self._register(service_type, implementation, factory, instance, Lifetime.SINGLETON)

    def register_transient(
        self,
        service_type: type[T],
        implementation: type[T] | None = None,
        factory: Callable[..., T] | None = None,
    ) -> "Container":
        """Register a transient service."""
        return self._register(service_type, implementation, factory, None, Lifetime.TRANSIENT)

    def _register(
        self,
        service_type: type[T],
        implementation: type[T] | None,
        factory: Callable[..., T] | None,
        instance: T | None,
        lifetime: Lifetime,
    ) -> "Container":
        """Internal registration method."""
        descriptor = ServiceDescriptor(
            service_type=service_type,
            implementation=implementation,
            factory=factory,
            instance=instance,
            lifetime=lifetime,
        )

        with self._lock:
            key = self._get_service_key(service_type)
            self._services[key] = descriptor

            # If singleton instance provided, store it
            if lifetime == Lifetime.SINGLETON and instance:
                self._singletons[key] = instance

        self._logger.debug(f"Registered {lifetime.value} service: {service_type.__name__}")
        return self

    def resolve(self, service_type: type[T]) -> T:
        """
        Resolve a service instance.

        Args:
            service_type: Type of service to resolve

        Returns:
            Service instance

        Raises:
            ServiceNotFoundError: If service is not registered
            CircularDependencyError: If circular dependency detected
        """
        key = self._get_service_key(service_type)

        # Check circular dependency
        if key in self._resolving:
            raise CircularDependencyError(
                f"Circular dependency detected for {service_type.__name__}"
            )

        try:
            self._resolving.add(key)
            return self._resolve_internal(service_type, key)
        finally:
            self._resolving.discard(key)

    def _resolve_internal(self, service_type: type[T], key: str) -> T:
        """Internal resolution logic."""
        # Try current container
        descriptor = self._services.get(key)

        # Try parent container
        if not descriptor and self.parent:
            return self.parent.resolve(service_type)

        if not descriptor:
            raise ServiceNotFoundError(f"Service not found: {service_type.__name__}")

        # Handle different lifetimes
        if descriptor.lifetime == Lifetime.SINGLETON:
            return self._resolve_singleton(descriptor, key)
        elif descriptor.lifetime == Lifetime.SCOPED:
            return self._resolve_scoped(descriptor, key)
        else:  # TRANSIENT
            return self._create_instance(descriptor)

    def _resolve_singleton(self, descriptor: ServiceDescriptor, key: str) -> Any:
        """Resolve singleton instance."""
        with self._lock:
            # Check if already created
            if key in self._singletons:
                return self._singletons[key]

            # Create new singleton
            instance = self._create_instance(descriptor)
            self._singletons[key] = instance
            return instance

    def _resolve_scoped(self, descriptor: ServiceDescriptor, key: str) -> Any:
        """Resolve scoped instance."""
        if not self._current_scope:
            raise ScopeError("No active scope for scoped service")

        # Check if already created in current scope
        instance = self._current_scope.get_instance(key)
        if instance:
            return instance

        # Create new scoped instance
        instance = self._create_instance(descriptor)
        self._current_scope.set_instance(key, instance)
        return instance

    def _create_instance(self, descriptor: ServiceDescriptor) -> Any:
        """Create new service instance."""
        if descriptor.instance:
            return descriptor.instance

        if descriptor.factory:
            # Use factory with dependency injection
            return self._call_with_injection(descriptor.factory)

        # Use constructor with dependency injection
        return self._call_with_injection(descriptor.implementation)

    def _call_with_injection(self, callable_obj: Callable) -> Any:
        """Call function/constructor with automatic dependency injection."""
        # Get type hints for parameters
        type_hints = get_type_hints(callable_obj)
        sig = inspect.signature(callable_obj)

        kwargs = {}

        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue

            # Get parameter type
            param_type = type_hints.get(param_name, param.annotation)

            if param_type and param_type != inspect.Parameter.empty:
                try:
                    # Resolve dependency
                    kwargs[param_name] = self.resolve(param_type)
                except ServiceNotFoundError:
                    # Check if parameter has default value
                    if param.default != inspect.Parameter.empty:
                        kwargs[param_name] = param.default
                    else:
                        # Try to create if it's an Injectable
                        if inspect.isclass(param_type) and issubclass(param_type, Injectable):
                            kwargs[param_name] = self._auto_resolve(param_type)
                        else:
                            raise

        return callable_obj(**kwargs)

    def _auto_resolve(self, service_type: type[T]) -> T:
        """Automatically resolve Injectable types."""
        # Register as transient and resolve
        self.register_transient(service_type)
        return self.resolve(service_type)

    def _get_service_key(self, service_type: type) -> str:
        """Get unique key for service type."""
        if hasattr(service_type, "__name__"):
            return service_type.__name__
        else:
            return str(service_type)

    def clear(self) -> None:
        """Clear all registrations and instances."""
        with self._lock:
            self._services.clear()
            self._singletons.clear()
            self._scopes.clear()
            self._current_scope = None
            self._resolution_cache.clear()


# Exceptions
class ServiceNotFoundError(Exception):
    """Raised when a service cannot be found."""

    pass


class CircularDependencyError(Exception):
    """Raised when a circular dependency is detected."""

    pass


class ScopeError(Exception):
    """Raised when scope-related operations fail."""

    pass


# Global container instance
_global_container: Container | None = None


def get_global_container() -> Container:
    """Get the global dependency container."""
    global _global_container
    if _global_container is None:
        _global_container = Container()
    return _global_container


# Convenience functions
def inject(service_type: type[T]) -> T:
    """Inject a service from the global container."""
    return get_global_container().resolve(service_type)


def register_transient(service_type: type[T], implementation: type[T] = None) -> None:
    """Register a transient in the global container."""
    get_global_container().register_transient(service_type, implementation)
