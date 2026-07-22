import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.fake_hardware import FakeHardware
from ui.theme import Palette
from ui.screen_log import ScreenLog
from gamestate import GameState


def _draw():
    hw = FakeHardware()
    pal = Palette(hw.display)
    s = ScreenLog()
    s.draw(hw, GameState(), pal)
    return hw, s


def test_header_shows_game_log_title():
    hw, s = _draw()
    texts = [str(c[1]) for c in hw.display.calls if c[0] == "text"]
    assert "Game Log" in texts


def test_x_is_the_only_nav_and_round_is_not_a_link():
    hw, s = _draw()
    navs = [b.id for b in s.buttons if b.id[0] == "nav"]
    assert navs == [("nav", "close")]      # X only — R# and Set. are not links
    close = [b for b in s.buttons if b.id == ("nav", "close")][0]
    assert close.x == 330                  # upper-right, like Settings


def test_close_returns_goto_close():
    hw, s = _draw()
    close = [b for b in s.buttons if b.id == ("nav", "close")][0]
    assert s.on_button(close, GameState()) == ("goto", "close")
