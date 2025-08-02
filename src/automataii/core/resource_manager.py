"""
Resource management utilities for comprehensive cleanup and lifecycle management.
"""

import gc
import logging
import threading
import weakref
from typing import Any, Dict, List, Optional, Set
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class ResourceManager:
    """
    Centralized resource management system to prevent memory leaks and ensure proper cleanup.
    """
    
    def __init__(self):
        self._resources: Dict[str, weakref.ref] = {}
        self._cleanup_callbacks: Dict[str, List[callable]] = {}
        self._lock = threading.RLock()
        self._shutdown = False
        
    def register_resource(self, resource_id: str, resource: Any, cleanup_callback: callable = None) -> None:
        """
        Register a resource for lifecycle management.
        
        Args:
            resource_id: Unique identifier for the resource
            resource: The resource object to track
            cleanup_callback: Optional callback to run when resource is cleaned up
        """
        with self._lock:
            if self._shutdown:
                return
                
            try:
                # Store weak reference to avoid circular references
                self._resources[resource_id] = weakref.ref(resource, self._resource_finalized)
                
                # Store cleanup callback
                if cleanup_callback:
                    if resource_id not in self._cleanup_callbacks:
                        self._cleanup_callbacks[resource_id] = []
                    self._cleanup_callbacks[resource_id].append(cleanup_callback)
                    
                logger.debug(f"Registered resource: {resource_id}")
                
            except Exception as e:
                logger.error(f"Error registering resource {resource_id}: {e}")
    
    def unregister_resource(self, resource_id: str) -> None:
        """
        Unregister a resource and run cleanup callbacks.
        
        Args:
            resource_id: The resource ID to unregister
        """
        with self._lock:
            if resource_id in self._resources:
                del self._resources[resource_id]
                
            if resource_id in self._cleanup_callbacks:
                for callback in self._cleanup_callbacks[resource_id]:
                    try:
                        callback()
                    except Exception as e:
                        logger.error(f"Error in cleanup callback for {resource_id}: {e}")
                del self._cleanup_callbacks[resource_id]
                
            logger.debug(f"Unregistered resource: {resource_id}")
    
    def get_resource(self, resource_id: str) -> Optional[Any]:
        """
        Get a registered resource by ID.
        
        Args:
            resource_id: The resource ID to retrieve
            
        Returns:
            The resource object if it exists and is still alive, None otherwise
        """
        with self._lock:
            if resource_id in self._resources:
                ref = self._resources[resource_id]
                resource = ref()
                if resource is not None:
                    return resource
                else:
                    # Resource was garbage collected, clean up
                    self.unregister_resource(resource_id)
            return None
    
    def cleanup_all(self) -> None:
        """
        Cleanup all registered resources.
        """
        with self._lock:
            logger.info(f"Cleaning up {len(self._resources)} registered resources")
            
            # Create a copy of resource IDs to avoid modification during iteration
            resource_ids = list(self._resources.keys())
            
            for resource_id in resource_ids:
                try:
                    self.unregister_resource(resource_id)
                except Exception as e:
                    logger.error(f"Error cleaning up resource {resource_id}: {e}")
            
            # Force garbage collection
            gc.collect()
            
            logger.info("Resource cleanup completed")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get resource management statistics.
        
        Returns:
            Dictionary containing resource statistics
        """
        with self._lock:
            alive_resources = 0
            dead_resources = 0
            
            for resource_id, ref in self._resources.items():
                if ref() is not None:
                    alive_resources += 1
                else:
                    dead_resources += 1
            
            return {
                "total_registered": len(self._resources),
                "alive_resources": alive_resources,
                "dead_resources": dead_resources,
                "cleanup_callbacks": len(self._cleanup_callbacks),
                "shutdown": self._shutdown
            }
    
    def shutdown(self) -> None:
        """
        Shutdown the resource manager and cleanup all resources.
        """
        self._shutdown = True
        self.cleanup_all()
        logger.info("Resource manager shutdown completed")
    
    def _resource_finalized(self, ref: weakref.ref) -> None:
        """
        Called when a resource is finalized (garbage collected).
        
        Args:
            ref: The weak reference that was finalized
        """
        with self._lock:
            # Find and remove the finalized resource
            for resource_id, stored_ref in list(self._resources.items()):
                if stored_ref is ref:
                    self.unregister_resource(resource_id)
                    break


class ResourceTracker:
    """
    Context manager and decorator for tracking resource usage.
    """
    
    def __init__(self, resource_manager: ResourceManager, resource_id: str):
        self.resource_manager = resource_manager
        self.resource_id = resource_id
        self._resource = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._resource:
            self.resource_manager.unregister_resource(self.resource_id)
    
    def register(self, resource: Any, cleanup_callback: callable = None) -> None:
        """
        Register a resource within this tracker.
        
        Args:
            resource: The resource to track
            cleanup_callback: Optional cleanup callback
        """
        self._resource = resource
        self.resource_manager.register_resource(self.resource_id, resource, cleanup_callback)


@contextmanager
def managed_resource(resource_manager: ResourceManager, resource_id: str, resource: Any, cleanup_callback: callable = None):
    """
    Context manager for automatic resource management.
    
    Args:
        resource_manager: The resource manager instance
        resource_id: Unique identifier for the resource
        resource: The resource to manage
        cleanup_callback: Optional cleanup callback
    
    Yields:
        The resource object
    """
    try:
        resource_manager.register_resource(resource_id, resource, cleanup_callback)
        yield resource
    finally:
        resource_manager.unregister_resource(resource_id)


def resource_cleanup(resource_manager: ResourceManager, resource_id: str):
    """
    Decorator for automatic resource cleanup.
    
    Args:
        resource_manager: The resource manager instance
        resource_id: Unique identifier for the resource
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            
            # Register the result if it's a resource
            if hasattr(result, '__del__') or hasattr(result, 'cleanup'):
                cleanup_callback = getattr(result, 'cleanup', None)
                resource_manager.register_resource(resource_id, result, cleanup_callback)
            
            return result
        return wrapper
    return decorator


# Global resource manager instance
_global_resource_manager: Optional[ResourceManager] = None


def get_global_resource_manager() -> ResourceManager:
    """
    Get the global resource manager instance.
    
    Returns:
        The global resource manager
    """
    global _global_resource_manager
    if _global_resource_manager is None:
        _global_resource_manager = ResourceManager()
    return _global_resource_manager


def shutdown_global_resource_manager() -> None:
    """
    Shutdown the global resource manager.
    """
    global _global_resource_manager
    if _global_resource_manager:
        _global_resource_manager.shutdown()
        _global_resource_manager = None