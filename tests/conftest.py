"""Shared fixtures. Board tracking is module state in gamestate; a test
that flips it must not leak into the next one."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def _reset_client_switches():
    import gamestate
    yield
    gamestate.set_board_tracking(False)
