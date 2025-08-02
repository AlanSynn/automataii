"""
Performance and memory validation tests.
"""
import time
import gc
import pytest
from automataii.core.decorators import EventHandlerMixin, event_handler
from automataii.core import get_global_event_bus, set_global_event_bus, EventBus, ApplicationStarted


class TestPerformanceValidation:
    """Test performance and memory characteristics."""
    
    def test_event_system_performance(self):
        """Test that event system performs well under load."""
        test_bus = EventBus()
        original_bus = get_global_event_bus()
        set_global_event_bus(test_bus)
        
        try:
            events_received = []
            
            class TestComponent(EventHandlerMixin):
                def __init__(self, component_id):
                    self.component_id = component_id
                    super().__init__()
                
                @event_handler(ApplicationStarted)
                def handle_event(self, event):
                    events_received.append(self.component_id)
            
            # Create multiple components
            components = []
            for i in range(100):
                component = TestComponent(f"component_{i}")
                components.append(component)
            
            # Measure event publishing performance
            start_time = time.time()
            for i in range(50):
                test_bus.publish(ApplicationStarted(startup_time=float(i)))
            end_time = time.time()
            
            publish_time = end_time - start_time
            
            # Should handle 50 events to 100 components (5000 handler calls) quickly
            assert publish_time < 5.0, f"Event publishing took {publish_time:.2f}s - too slow"
            assert len(events_received) == 5000  # 50 events * 100 components
            
            print(f"✅ Event system performance: {publish_time:.3f}s for 5000 handler calls")
            
        finally:
            set_global_event_bus(original_bus)
    
    def test_memory_usage_stability(self):
        """Test memory usage doesn't grow excessively."""
        import psutil
        import os
        
        # Get current process
        process = psutil.Process(os.getpid())
        
        # Get initial memory usage
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        test_bus = EventBus()
        original_bus = get_global_event_bus()
        set_global_event_bus(test_bus)
        
        try:
            # Create and destroy components multiple times
            for cycle in range(10):
                components = []
                
                class TestComponent(EventHandlerMixin):
                    def __init__(self, component_id):
                        self.component_id = component_id
                        self.data = list(range(100))  # Some data
                        super().__init__()
                    
                    @event_handler(ApplicationStarted)
                    def handle_event(self, event):
                        pass
                
                # Create components
                for i in range(20):
                    component = TestComponent(f"cycle_{cycle}_component_{i}")
                    components.append(component)
                
                # Publish some events
                for i in range(5):
                    test_bus.publish(ApplicationStarted(startup_time=float(i)))
                
                # Cleanup
                for component in components:
                    component.unsubscribe_all_events()
                
                # Clear references
                components.clear()
                gc.collect()
            
            # Get final memory usage
            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_growth = final_memory - initial_memory
            
            print(f"Initial memory: {initial_memory:.1f} MB")
            print(f"Final memory: {final_memory:.1f} MB")
            print(f"Memory growth: {memory_growth:.1f} MB")
            
            # Memory should not grow excessively
            assert memory_growth < 100, f"Memory growth too large: {memory_growth:.1f} MB"
            
            print("✅ Memory usage stability test passed")
            
        finally:
            set_global_event_bus(original_bus)
    
    def test_event_handler_creation_performance(self):
        """Test that event handler creation doesn't have performance regressions."""
        test_bus = EventBus()
        original_bus = get_global_event_bus()
        set_global_event_bus(test_bus)
        
        try:
            class TestComponent(EventHandlerMixin):
                def __init__(self, component_id):
                    self.component_id = component_id
                    super().__init__()
                
                @event_handler(ApplicationStarted)
                def handle_event(self, event):
                    pass
            
            # Measure component creation time
            start_time = time.time()
            components = []
            for i in range(200):
                component = TestComponent(f"component_{i}")
                components.append(component)
            end_time = time.time()
            
            creation_time = end_time - start_time
            
            # Should create 200 components quickly
            assert creation_time < 2.0, f"Component creation took {creation_time:.2f}s - too slow"
            
            print(f"✅ Component creation performance: {creation_time:.3f}s for 200 components")
            
        finally:
            set_global_event_bus(original_bus)
    
    def test_cleanup_performance(self):
        """Test that cleanup operations are efficient."""
        test_bus = EventBus()
        original_bus = get_global_event_bus()
        set_global_event_bus(test_bus)
        
        try:
            class TestComponent(EventHandlerMixin):
                def __init__(self, component_id):
                    self.component_id = component_id
                    super().__init__()
                
                @event_handler(ApplicationStarted)
                def handle_event(self, event):
                    pass
            
            # Create many components
            components = []
            for i in range(100):
                component = TestComponent(f"component_{i}")
                components.append(component)
            
            # Measure cleanup time
            start_time = time.time()
            for component in components:
                component.unsubscribe_all_events()
            end_time = time.time()
            
            cleanup_time = end_time - start_time
            
            # Should cleanup 100 components quickly
            assert cleanup_time < 1.0, f"Cleanup took {cleanup_time:.2f}s - too slow"
            
            print(f"✅ Cleanup performance: {cleanup_time:.3f}s for 100 components")
            
        finally:
            set_global_event_bus(original_bus)