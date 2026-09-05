"""Shared fixtures. Board tracking and the window policy are both module
state in gamestate; a test that flips either must not leak into the next
one."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def _reset_client_switches():
    import gamestate
    yield
    gamestate.set_board_tracking(False)
    gamestate.set_window_policy(gamestate.WINDOW_POLICY_VIEWS)
