import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.fake_hardware import FakeHardware
from ui.theme import Palette
from ui.screen_setup import SetupScreen
from gamestate import GameState


def _draw(screen):
    hw = FakeHardware()
    pal = Palette(hw.display)
    screen.draw(hw, GameState(), pal)
    return screen


def test_single_player_has_no_first_player_row_button():
    s = _draw(SetupScreen())
    assert not any(b.id[0] == "fp" for b in s.buttons)
    assert s.first == 0


def test_multi_player_rows_are_tappable_to_move_ribbon():
    s = SetupScreen()
    s.threats = [25, 25, 25]
    _draw(s)
    fp2 = [b for b in s.buttons if b.id == ("fp", 2)][0]
    s.on_button(fp2, None)
    assert s.first == 2


def test_row_controls_win_hit_test_over_row_button():
    s = SetupScreen()
    s.threats = [25, 25]
    _draw(s)
    # the minus stepper of row 0 overlaps the fp row target; first hit wins
    minus = [b for b in s.buttons if b.id == ("st", 0, -1)][0]
    cx, cy = minus.x + 2, minus.y + 2
    hit = [b for b in s.buttons if b.hit(cx, cy)][0]
    assert hit.id == ("st", 0, -1)


def test_removing_first_player_row_resets_ribbon():
    s = SetupScreen()
    s.threats = [25, 25]
    s.first = 1
    _draw(s)
    rm = [b for b in s.buttons if b.id == ("rm", 1)][0]
    s.on_button(rm, None)
    assert s.first == 0


def test_start_returns_threats_and_first():
    s = SetupScreen()
    s.threats = [25, 30]
    s.first = 1
    _draw(s)
    start = [b for b in s.buttons if b.id == ("start",)][0]
    result = s.on_button(start, None)
    assert result == ("start_game", [25, 30], 1)


def test_warning_only_when_save_exists():
    from ui.screen_setup import SetupScreen
    from ui.theme import Palette
    from tests.fake_hardware import FakeHardware
    from gamestate import GameState
    for has_save, expect in ((False, False), (True, True)):
        hw = FakeHardware()
        s = SetupScreen()
        s.has_save = has_save
        s.draw(hw, GameState(), Palette(hw.display))
        texts = [str(c[1]) for c in hw.display.calls if c[0] == "text"]
        shown = any("overwrites" in t for t in texts)
        assert shown is expect
