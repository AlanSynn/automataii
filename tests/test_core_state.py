"""
Test state management system
"""
import pytest
from automataii.core import StateStore, Action
from automataii.core.state.base import State, Reducer


class AppState:
    """Test application state"""
    def __init__(self):
        self.counter = 0
        self.user_name = ""
        self.items = []


class CounterReducer(Reducer[AppState]):
    """Test reducer for counter operations"""
    
    @property
    def action_types(self) -> set[str]:
        return {"INCREMENT", "DECREMENT", "SET_NAME", "ADD_ITEM", "RESET"}
    
    def reduce(self, state: State[AppState], action: Action) -> State[AppState]:
        new_data = AppState()
        new_data.counter = state.data.counter
        new_data.user_name = state.data.user_name
        new_data.items = state.data.items.copy()
        
        if action.type == "INCREMENT":
            new_data.counter += 1
        elif action.type == "DECREMENT":
            new_data.counter -= 1
        elif action.type == "SET_NAME":
            new_data.user_name = action.payload.get("name", "")
        elif action.type == "ADD_ITEM":
            new_data.items.append(action.payload.get("item"))
        elif action.type == "RESET":
            new_data.counter = 0
            new_data.user_name = ""
            new_data.items = []
        
        return State(new_data)


class TestStateStore:
    """Test state management store"""
    
    def test_state_store_creation(self):
        """Test state store can be created"""
        reducer = CounterReducer()
        store = StateStore(initial_state=AppState(), reducer=reducer)
        assert store is not None
        assert store.state.data.counter == 0
        
    def test_simple_state_update(self):
        """Test basic state updates"""
        reducer = CounterReducer()
        store = StateStore(initial_state=AppState(), reducer=reducer)
        
        # Test increment
        store.dispatch(Action(type="INCREMENT"))
        assert store.state.data.counter == 1
        
        # Test decrement
        store.dispatch(Action(type="DECREMENT"))
        assert store.state.data.counter == 0
        
    def test_complex_state_update(self):
        """Test complex state updates with payload"""
        reducer = CounterReducer()
        store = StateStore(initial_state=AppState(), reducer=reducer)
        
        # Update name
        store.dispatch(Action(type="SET_NAME", payload={"name": "Test User"}))
        assert store.state.data.user_name == "Test User"
        
        # Add items
        store.dispatch(Action(type="ADD_ITEM", payload={"item": "Item 1"}))
        store.dispatch(Action(type="ADD_ITEM", payload={"item": "Item 2"}))
        
        assert len(store.state.data.items) == 2
        assert "Item 1" in store.state.data.items
        assert "Item 2" in store.state.data.items
        
    def test_state_immutability(self):
        """Test that state updates create new state objects"""
        reducer = CounterReducer()
        store = StateStore(initial_state=AppState(), reducer=reducer)
        
        initial_state = store.state
        
        # Dispatch action
        store.dispatch(Action(type="INCREMENT"))
        
        new_state = store.state
        
        # Should be different objects
        assert initial_state is not new_state
        assert initial_state.data is not new_state.data
        
        # But old state should be unchanged
        assert initial_state.data.counter == 0
        assert new_state.data.counter == 1
        
    def test_multiple_state_updates(self):
        """Test multiple consecutive state updates"""
        reducer = CounterReducer()
        store = StateStore(initial_state=AppState(), reducer=reducer)
        
        # Multiple increments
        for i in range(5):
            store.dispatch(Action(type="INCREMENT"))
            
        assert store.state.data.counter == 5
        
        # Set name and add items
        store.dispatch(Action(type="SET_NAME", payload={"name": "Multi Test"}))
        store.dispatch(Action(type="ADD_ITEM", payload={"item": "First"}))
        store.dispatch(Action(type="ADD_ITEM", payload={"item": "Second"}))
        
        # All changes should be preserved
        assert store.state.data.counter == 5
        assert store.state.data.user_name == "Multi Test"
        assert len(store.state.data.items) == 2
        
    def test_action_validation(self):
        """Test action validation"""
        # Test that action must have type
        with pytest.raises(ValueError):
            Action(type="")
            
    def test_reset_functionality(self):
        """Test state reset functionality"""
        reducer = CounterReducer()
        store = StateStore(initial_state=AppState(), reducer=reducer)
        
        # Make some changes
        store.dispatch(Action(type="INCREMENT"))
        store.dispatch(Action(type="INCREMENT"))
        store.dispatch(Action(type="SET_NAME", payload={"name": "Test"}))
        store.dispatch(Action(type="ADD_ITEM", payload={"item": "Test Item"}))
        
        # Verify changes
        assert store.state.data.counter == 2
        assert store.state.data.user_name == "Test"
        assert len(store.state.data.items) == 1
        
        # Reset
        store.dispatch(Action(type="RESET"))
        
        # Should be back to initial state
        assert store.state.data.counter == 0
        assert store.state.data.user_name == ""
        assert len(store.state.data.items) == 0
        
    def test_unhandled_action(self):
        """Test behavior with unhandled action types"""
        reducer = CounterReducer()
        store = StateStore(initial_state=AppState(), reducer=reducer)
        
        initial_counter = store.state.data.counter
        
        # Dispatch unknown action
        store.dispatch(Action(type="UNKNOWN_ACTION"))
        
        # State should be unchanged
        assert store.state.data.counter == initial_counter