import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.fake_hardware import FakeHardware
from ui.theme import Palette
from ui.screen_settings import ScreenSettings
from gamestate import GameState


def _draw():
    hw = FakeHardware()
    pal = Palette(hw.display)
    s = ScreenSettings()
    s.draw(hw, GameState(), pal)
    return hw, s


def test_header_shows_settings_title_and_close():
    hw, s = _draw()
    texts = [str(c[1]) for c in hw.display.calls if c[0] == "text"]
    assert "Settings" in texts
    assert "X" in texts
    assert "Set." not in texts


def test_close_is_the_only_nav_target():
    hw, s = _draw()
    navs = [b.id for b in s.buttons if b.id[0] == "nav"]
    assert navs == [("nav", "close")]


def test_close_returns_goto_close():
    hw, s = _draw()
    close = [b for b in s.buttons if b.id == ("nav", "close")][0]
    assert s.on_button(close, GameState()) == ("goto", "close")


def _find(s, id):
    return [b for b in s.buttons if b.id == id][0]


def test_save_quit_returns_action():
    hw, s = _draw()
    assert s.on_button(_find(s, ("save_quit",)), GameState()) == ("save_quit",)


def test_end_game_requires_confirmation():
    hw, s = _draw()
    game = GameState()
    assert s.on_button(_find(s, ("end_game",)), game) is True
    assert s.confirm_end is True
    s.draw(hw, game, __import__("ui.theme", fromlist=["Palette"]).Palette(hw.display))
    assert s.on_button(_find(s, ("end_game2",)), game) == ("end_game",)
