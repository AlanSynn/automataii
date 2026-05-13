from automataii.infrastructure.state import State
from automataii.infrastructure.state.selectors import Selector, memoize


def test_selector_honors_configured_cache_size():
    selector = Selector(lambda state: state.data["value"], max_cache_size=2)

    for value in range(5):
        assert selector(State({"value": value})) == value

    assert len(selector._cache) == 2


def test_memoize_decorator_honors_cache_size():
    calls = {"count": 0}

    @memoize(cache_size=2)
    def select_value(state):
        calls["count"] += 1
        return state.data["value"]

    for value in range(5):
        assert select_value(State({"value": value})) == value

    assert calls["count"] == 5
    assert len(select_value._cache) == 2


def test_selector_cache_reuses_dependency_subset():
    calls = {"count": 0}

    def select_value(state):
        calls["count"] += 1
        return state.data["value"]

    selector = Selector(select_value, dependencies=["value"], max_cache_size=3)

    assert selector(State({"value": 1, "noise": "a"})) == 1
    assert selector(State({"value": 1, "noise": "b"})) == 1

    assert calls["count"] == 1


def test_selector_fallback_hash_uses_dependency_subset():
    calls = {"count": 0}
    circular_value = []
    circular_value.append(circular_value)

    def select_value(state):
        calls["count"] += 1
        return "stable"

    selector = Selector(select_value, dependencies=["value"], max_cache_size=3)

    assert selector(State({"value": circular_value, "noise": "a"})) == "stable"
    assert selector(State({"value": circular_value, "noise": "b"})) == "stable"

    assert calls["count"] == 1
