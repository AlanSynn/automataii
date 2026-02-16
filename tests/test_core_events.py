"""
Test event bus system
"""
from automataii.infrastructure.events import ApplicationStarted, ComponentActivated, EventBus


class TestEventBus:
    """Test event bus functionality"""

    def test_event_bus_creation(self):
        """Test event bus can be created"""
        bus = EventBus()
        assert bus is not None

    def test_event_subscription_and_publishing(self):
        """Test basic event subscription and publishing"""
        bus = EventBus()
        received_events = []

        def test_handler(event):
            received_events.append(event)

        # Subscribe to events
        bus.subscribe(ApplicationStarted, test_handler)

        # Publish event
        test_event = ApplicationStarted(startup_time=1.5)
        bus.publish(test_event)

        # Check if event was received
        assert len(received_events) == 1
        assert received_events[0].startup_time == 1.5

    def test_multiple_handlers_for_same_event(self):
        """Test multiple handlers can subscribe to same event type"""
        bus = EventBus()
        handler1_called = []
        handler2_called = []

        def handler1(event):
            handler1_called.append(event)

        def handler2(event):
            handler2_called.append(event)

        # Subscribe both handlers
        bus.subscribe(ApplicationStarted, handler1)
        bus.subscribe(ApplicationStarted, handler2)

        # Publish event
        test_event = ApplicationStarted(startup_time=2.0)
        bus.publish(test_event)

        # Both handlers should be called
        assert len(handler1_called) == 1
        assert len(handler2_called) == 1
        assert handler1_called[0].startup_time == 2.0
        assert handler2_called[0].startup_time == 2.0

    def test_event_filtering(self):
        """Test events only go to appropriate handlers"""
        bus = EventBus()
        app_events = []
        component_events = []

        def app_handler(event):
            app_events.append(event)

        def component_handler(event):
            component_events.append(event)

        # Subscribe to different event types
        bus.subscribe(ApplicationStarted, app_handler)
        bus.subscribe(ComponentActivated, component_handler)

        # Publish different events
        app_event = ApplicationStarted(startup_time=1.0)
        component_event = ComponentActivated(component_id="test", component_type="tab")

        bus.publish(app_event)
        bus.publish(component_event)

        # Check correct filtering
        assert len(app_events) == 1
        assert len(component_events) == 1
        assert app_events[0] == app_event
        assert component_events[0] == component_event

    def test_event_unsubscription(self):
        """Test event handler unsubscription"""
        bus = EventBus()
        received_events = []

        def test_handler(event):
            received_events.append(event)

        # Subscribe and publish
        bus.subscribe(ApplicationStarted, test_handler)
        bus.publish(ApplicationStarted(startup_time=1.0))
        assert len(received_events) == 1

        # Unsubscribe and publish again
        bus.unsubscribe(ApplicationStarted, test_handler)
        bus.publish(ApplicationStarted(startup_time=2.0))

        # Should still be 1 (no new events received)
        assert len(received_events) == 1

    def test_event_data_integrity(self):
        """Test that event data is preserved correctly"""
        bus = EventBus()
        received_event = None

        def test_handler(event):
            nonlocal received_event
            received_event = event

        bus.subscribe(ComponentActivated, test_handler)

        original_event = ComponentActivated(
            component_id="test_component",
            component_type="dialog",
            widget_id="widget123",
            action="activate"
        )

        bus.publish(original_event)

        # Verify all data is preserved
        assert received_event is not None
        assert received_event.component_id == "test_component"
        assert received_event.component_type == "dialog"
        assert received_event.widget_id == "widget123"
        assert received_event.action == "activate"
