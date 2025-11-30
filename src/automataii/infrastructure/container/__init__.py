"""
Dependency Injection Container.

Provides service registration and resolution with lifetime management.

Usage:
    from automataii.infrastructure.container import Container, inject

    container = get_global_container()
    container.register(IService, ConcreteService)
    service = container.resolve(IService)
"""

from automataii.infrastructure.container.container import (
    CircularDependencyError,
    Container,
    Injectable,
    Lifetime,
    Scope,
    ScopeError,
    ServiceDescriptor,
    ServiceNotFoundError,
    get_global_container,
    inject,
    register_transient,
)

__all__ = [
    "Container",
    "Injectable",
    "get_global_container",
    "inject",
    "register_transient",
    "Lifetime",
    "Scope",
    "ServiceDescriptor",
    "ServiceNotFoundError",
    "CircularDependencyError",
    "ScopeError",
]
