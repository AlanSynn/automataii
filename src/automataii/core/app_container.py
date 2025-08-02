"""
Application Dependency Injection Container

Sets up the complete dependency injection container for the Automataii application.
Registers all services and their dependencies.
"""

import logging

from automataii.core.event_bus import EventBus, get_global_event_bus, set_global_event_bus
from automataii.services.di import Container, get_global_container
from automataii.services.motion_path_service import MotionPathService
from automataii.services.project_data_manager import ProjectDataManager
from automataii.services.skeleton_manager import SkeletonManager
from automataii.services.mechanism_manager import MechanismManager
from automataii.services.blueprint_manager import BlueprintExportManager
from automataii.domain.kinematics.kinematics_system import KinematicsSystem
from automataii.core.error_handler import GlobalErrorHandler, set_global_error_handler


logger = logging.getLogger(__name__)


def setup_application_container() -> Container:
    """
    Sets up the complete application dependency injection container.
    
    This function:
    1. Creates and configures the global event bus
    2. Registers all core services with proper lifetimes
    3. Sets up service dependencies
    4. Returns the configured container
    
    Returns:
        Configured Container instance
    """
    logger.info("Setting up application dependency injection container")
    
    # Create container
    container = Container()
    
    # Setup event bus as singleton
    event_bus = EventBus(max_history=2000, thread_pool_size=6)
    set_global_event_bus(event_bus)
    container.register_singleton(EventBus, instance=event_bus)
    
    # Setup global error handler as singleton
    error_handler = GlobalErrorHandler()
    set_global_error_handler(error_handler)
    container.register_singleton(GlobalErrorHandler, instance=error_handler)
    
    # Register core services as singletons
    container.register_singleton(MotionPathService, MotionPathService)
    container.register_singleton(ProjectDataManager, ProjectDataManager)
    container.register_singleton(SkeletonManager, SkeletonManager)
    container.register_singleton(MechanismManager, MechanismManager)
    container.register_singleton(BlueprintExportManager, BlueprintExportManager)
    
    # Register domain services as singletons
    container.register_singleton(KinematicsSystem, KinematicsSystem)
    
    logger.info("Application container setup completed")
    logger.info(f"Registered services: {[desc.name for desc in container.get_registrations()]}")
    
    return container


def initialize_services(container: Container) -> None:
    """
    Initialize all registered services.
    
    This ensures that singleton services are created and properly initialized
    before the application starts processing events.
    
    Args:
        container: The dependency injection container
    """
    logger.info("Initializing application services")
    
    # Initialize services in dependency order
    services_to_initialize = [
        EventBus,
        GlobalErrorHandler,
        MotionPathService,
        ProjectDataManager,
        SkeletonManager,
        MechanismManager,
        BlueprintExportManager,
        KinematicsSystem,
    ]
    
    initialized_services = []
    
    for service_type in services_to_initialize:
        try:
            service = container.resolve(service_type)
            initialized_services.append(service_type.__name__)
            logger.debug(f"Initialized service: {service_type.__name__}")
        except Exception as e:
            logger.error(f"Failed to initialize service {service_type.__name__}: {e}")
            raise
    
    logger.info(f"Successfully initialized services: {initialized_services}")


def shutdown_application_container(container: Container) -> None:
    """
    Shutdown the application container and cleanup resources.
    
    This function:
    1. Shuts down all services gracefully
    2. Clears the container
    3. Shuts down the event bus
    
    Args:
        container: The dependency injection container to shutdown
    """
    logger.info("Shutting down application container")
    
    try:
        # Shutdown services that have cleanup methods
        services_with_cleanup = [
            MotionPathService,
            ProjectDataManager,
            KinematicsSystem,
            GlobalErrorHandler,
        ]
        
        for service_type in services_with_cleanup:
            try:
                service = container.resolve(service_type)
                if hasattr(service, 'shutdown'):
                    service.shutdown()
                    logger.debug(f"Shutdown service: {service_type.__name__}")
            except Exception as e:
                logger.warning(f"Error shutting down service {service_type.__name__}: {e}")
        
        # Shutdown event bus
        event_bus = get_global_event_bus()
        if event_bus:
            event_bus.shutdown()
            logger.debug("Event bus shutdown completed")
        
        # Clear container
        container.clear()
        logger.info("Application container shutdown completed")
        
    except Exception as e:
        logger.error(f"Error during application container shutdown: {e}")
        raise


def get_service(service_type):
    """
    Convenience function to get a service from the global container.
    
    Args:
        service_type: The type of service to resolve
        
    Returns:
        Service instance
    """
    container = get_global_container()
    return container.resolve(service_type)