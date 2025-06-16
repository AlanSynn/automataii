"""
Test dependency injection container
"""
import pytest
from automataii.core import Container, Injectable


class TestService(Injectable):
    def __init__(self):
        self.name = "TestService"
        
    def get_info(self):
        return f"Service: {self.name}"


class TestServiceWithDependency(Injectable):
    def __init__(self, dependency: TestService):
        self.dependency = dependency
        self.name = "TestServiceWithDependency"
        
    def get_info(self):
        return f"Service: {self.name}, Dependency: {self.dependency.get_info()}"


class TestContainer:
    """Test dependency injection container"""
    
    def test_container_creation(self):
        """Test container can be created"""
        container = Container()
        assert container is not None
        
    def test_singleton_registration_and_resolution(self):
        """Test singleton service registration and resolution"""
        container = Container()
        
        # Register service
        container.register_singleton(TestService, implementation=TestService)
        
        # Resolve service
        service1 = container.resolve(TestService)
        service2 = container.resolve(TestService)
        
        # Should be same instance
        assert service1 is service2
        assert service1.get_info() == "Service: TestService"
        
    def test_transient_registration_and_resolution(self):
        """Test transient service registration and resolution"""
        container = Container()
        
        # Register service as transient
        container.register_transient(TestService, implementation=TestService)
        
        # Resolve service
        service1 = container.resolve(TestService)
        service2 = container.resolve(TestService)
        
        # Should be different instances
        assert service1 is not service2
        assert service1.get_info() == service2.get_info()
        
    def test_dependency_injection(self):
        """Test automatic dependency injection"""
        container = Container()
        
        # Register dependencies
        container.register_singleton(TestService, implementation=TestService)
        container.register_singleton(TestServiceWithDependency, implementation=TestServiceWithDependency)
        
        # Resolve service with dependency
        service = container.resolve(TestServiceWithDependency)
        
        assert service is not None
        assert "TestServiceWithDependency" in service.get_info()
        assert "TestService" in service.get_info()
        
    def test_factory_registration(self):
        """Test factory-based service registration"""
        container = Container()
        
        def create_test_service():
            service = TestService()
            service.name = "FactoryCreatedService"
            return service
        
        container.register_singleton(TestService, factory=create_test_service)
        
        service = container.resolve(TestService)
        assert service.get_info() == "Service: FactoryCreatedService"
        
    def test_instance_registration(self):
        """Test instance-based service registration"""
        container = Container()
        
        instance = TestService()
        instance.name = "PreCreatedInstance"
        
        container.register_singleton(TestService, instance=instance)
        
        service = container.resolve(TestService)
        assert service is instance
        assert service.get_info() == "Service: PreCreatedInstance"
        
    def test_resolution_error_for_unregistered_service(self):
        """Test error when resolving unregistered service"""
        container = Container()
        
        with pytest.raises(Exception):  # Should raise some form of resolution error
            container.resolve(TestService)