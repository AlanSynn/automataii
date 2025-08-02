"""
Test for the decorator closure fix (B023 issue).
"""
import pytest
from automataii.core import EventBus, ApplicationStarted, ComponentActivated, get_global_event_bus, set_global_event_bus
from automataii.core.decorators import EventHandlerMixin, event_handler


class TestDecoratorClosureFix:
    """Test that the decorator closure issue is fixed."""
    
    def test_event_handler_closure_fix(self):
        """
        Test that event handlers correctly bind to instance methods
        and don't have closure issues when multiple instances exist.
        
        This tests the fix for the B023 linting error:
        "Function definition does not bind loop variable"
        """
        # Create a new event bus for this test
        bus = EventBus()
        set_global_event_bus(bus)
        
        try:
            class TestListener(EventHandlerMixin):
                def __init__(self, listener_id: int):
                    self.listener_id = listener_id
                    self.events_received = []
                    super().__init__()
                
                @event_handler(ApplicationStarted)
                def handle_app_started(self, event: ApplicationStarted):
                    self.events_received.append((self.listener_id, event.startup_time))
            
            # Create multiple instances
            listener1 = TestListener(1)
            listener2 = TestListener(2)
            listener3 = TestListener(3)
            
            # Publish an event
            bus.publish(ApplicationStarted(startup_time=10.0))
            
            # Each listener should have received the event with its own ID
            assert len(listener1.events_received) == 1
            assert len(listener2.events_received) == 1
            assert len(listener3.events_received) == 1
            
            # Check that each listener recorded its own ID correctly
            assert listener1.events_received[0] == (1, 10.0)
            assert listener2.events_received[0] == (2, 10.0)
            assert listener3.events_received[0] == (3, 10.0)
            
            # Publish another event
            bus.publish(ApplicationStarted(startup_time=20.0))
            
            # Each listener should have received both events
            assert len(listener1.events_received) == 2
            assert len(listener2.events_received) == 2
            assert len(listener3.events_received) == 2
            
            # Check the second event
            assert listener1.events_received[1] == (1, 20.0)
            assert listener2.events_received[1] == (2, 20.0)
            assert listener3.events_received[1] == (3, 20.0)
            
        finally:
            # Clean up
            set_global_event_bus(None)
    
    def test_event_handler_cleanup_on_deletion(self):
        """Test that event handlers are properly cleaned up when objects are deleted."""
        bus = EventBus()
        set_global_event_bus(bus)
        
        try:
            events_received = []
            
            class TestListener(EventHandlerMixin):
                def __init__(self, listener_id: int):
                    self.listener_id = listener_id
                    super().__init__()
                
                @event_handler(ApplicationStarted)
                def handle_event(self, event: ApplicationStarted):
                    events_received.append(self.listener_id)
            
            # Create a listener
            listener = TestListener(1)
            
            # Publish an event - should be received
            bus.publish(ApplicationStarted(startup_time=1.0))
            assert len(events_received) == 1
            assert events_received[0] == 1
            
            # Delete the listener
            del listener
            
            # Publish another event - should not be received
            bus.publish(ApplicationStarted(startup_time=2.0))
            assert len(events_received) == 1  # Still only 1 event
            
        finally:
            set_global_event_bus(None)
    
    def test_multiple_event_handlers_same_class(self):
        """Test multiple event handlers in the same class work correctly."""
        bus = EventBus()
        set_global_event_bus(bus)
        
        try:
            class MultiEventListener(EventHandlerMixin):
                def __init__(self):
                    self.app_started_count = 0
                    self.component_activated_count = 0
                    super().__init__()
                
                @event_handler(ApplicationStarted)
                def handle_app_started(self, event: ApplicationStarted):
                    self.app_started_count += 1
                
                @event_handler(ComponentActivated)
                def handle_component_activated(self, event: ComponentActivated):
                    self.component_activated_count += 1
            
            listener = MultiEventListener()
            
            # Publish different events
            bus.publish(ApplicationStarted(startup_time=1.0))
            bus.publish(ComponentActivated(component_id="test"))
            bus.publish(ApplicationStarted(startup_time=2.0))
            
            assert listener.app_started_count == 2
            assert listener.component_activated_count == 1
            
        finally:
            set_global_event_bus(None)