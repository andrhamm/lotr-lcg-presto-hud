"""The delta engine in isolation — pure functions, no GameState.

Ported at parity from DragnCards (seastan/DragnCards @ a79716f9)
backend/lib/dragncards_game/ui/game_ui.ex. These tests pin the reference
semantics that are easy to lose in a port: the [old, new] leaf shape, the
":removed" sentinel, one apply function for both directions, and — the
load-bearing one — that lists are atomic because recursion is guarded on both
sides being maps.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gamestate import get_delta, apply_delta, apply_delta_list, REMOVED


def test_equal_maps_produce_no_delta():
    assert get_delta({"a": 1}, {"a": 1}) is None


def test_primitive_change_is_old_new_pair():
    assert get_delta({"a": 1}, {"a": 2}) == {"a": [1, 2]}


def test_unchanged_keys_are_omitted():
    assert get_delta({"a": 1, "b": 2}, {"a": 1, "b": 3}) == {"b": [2, 3]}


def test_added_key_uses_removed_sentinel_on_the_left():
    assert get_delta({}, {"a": 5}) == {"a": [REMOVED, 5]}


def test_removed_key_uses_removed_sentinel_on_the_right():
    assert get_delta({"a": 5}, {}) == {"a": [5, REMOVED]}


def test_nested_maps_recurse():
    assert get_delta({"p": {"x": 1, "y": 2}}, {"p": {"x": 1, "y": 9}}) == {"p": {"y": [2, 9]}}


def test_lists_are_atomic_not_recursed():
    """Parity with map_diff: the recursive clause is guarded on both values
    being maps, so a list is a primitive and changes wholesale. This is why
    GameState.snapshot() keys its collections."""
    assert get_delta({"xs": [1, 2, 3]}, {"xs": [1, 2, 4]}) == {"xs": [[1, 2, 3], [1, 2, 4]]}


def test_map_replaced_by_non_map_is_primitive():
    assert get_delta({"a": {"x": 1}}, {"a": None}) == {"a": [{"x": 1}, None]}


def test_apply_delta_undo_takes_index_zero():
    state = {"a": 2}
    apply_delta(state, {"a": [1, 2]}, "undo")
    assert state == {"a": 1}


def test_apply_delta_redo_takes_index_one():
    state = {"a": 1}
    apply_delta(state, {"a": [1, 2]}, "redo")
    assert state == {"a": 2}


def test_apply_delta_undo_of_an_add_deletes_the_key():
    state = {"a": 5}
    apply_delta(state, {"a": [REMOVED, 5]}, "undo")
    assert state == {}


def test_apply_delta_redo_of_a_removal_deletes_the_key():
    state = {"a": 5}
    apply_delta(state, {"a": [5, REMOVED]}, "redo")
    assert state == {}


def test_apply_delta_recurses_into_nested_maps():
    state = {"p": {"x": 1, "y": 9}}
    apply_delta(state, {"p": {"y": [2, 9]}}, "undo")
    assert state == {"p": {"x": 1, "y": 2}}


def test_apply_delta_ignores_delta_metadata():
    state = {"a": 2}
    apply_delta(state, {"a": [1, 2], "_delta_metadata": {"unix_ms": 1}}, "undo")
    assert state == {"a": 1}


def test_apply_delta_guard_returns_state_when_delta_is_not_a_map():
    state = {"a": 1}
    assert apply_delta(state, None, "undo") is state
    assert state == {"a": 1}


def test_round_trip_undo_then_redo_is_identity():
    import copy
    old = {"p": {"0": {"threat": 31}}, "view": "quest_staging", "n": 0}
    new = {"p": {"0": {"threat": 33}}, "view": "travel", "n": 2}
    d = get_delta(old, new)
    state = copy.deepcopy(new)
    apply_delta(state, d, "undo")
    assert state == old
    apply_delta(state, d, "redo")
    assert state == new


def test_apply_delta_list_walks_in_order():
    state = {"a": 3}
    apply_delta_list(state, [{"a": [2, 3]}, {"a": [1, 2]}], "undo")
    assert state == {"a": 1}
