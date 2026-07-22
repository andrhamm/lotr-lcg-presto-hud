import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.counter import CounterState


def test_starts_idle_at_value():
    c = CounterState(14)
    assert c.value == 14
    assert c.pending is False


def test_tap_enters_pending_without_changing_value():
    c = CounterState(14)
    c.tap(1)
    assert c.pending is True
    assert c.value == 14          # committed value unchanged
    assert c.preview == 15        # preview shows target
    assert c.delta == 1


def test_multiple_taps_accumulate_delta():
    c = CounterState(14)
    c.tap(1)
    c.tap(1)
    c.tap(-1)
    assert c.delta == 1
    assert c.preview == 15


def test_confirm_commits_preview_and_leaves_pending():
    c = CounterState(14)
    c.tap(1)
    c.tap(1)
    c.confirm()
    assert c.value == 16
    assert c.pending is False


def test_cancel_reverts_to_base():
    c = CounterState(14)
    c.tap(5)
    c.cancel()
    assert c.value == 14
    assert c.pending is False


def test_preview_clamps_at_zero():
    c = CounterState(2)
    c.tap(-5)
    assert c.preview == 0
    c.confirm()
    assert c.value == 0


def test_optional_max_clamp():
    c = CounterState(48, maximum=50)
    c.tap(9)
    assert c.preview == 50


def test_set_directly_bypasses_pending():
    c = CounterState(10)
    c.set(20)
    assert c.value == 20
    assert c.pending is False


def test_zero_enters_pending_with_zero_preview():
    c = CounterState(14)
    c.zero()
    assert c.pending is True
    assert c.preview == 0
    assert c.value == 14
    c.confirm()
    assert c.value == 0
