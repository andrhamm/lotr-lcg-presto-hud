import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.fake_hardware import FakeHardware
from ui.theme import Palette
from ui.screen_boot import BootScreen
from gamestate import GameState


def _draw(saved):
    hw = FakeHardware()
    pal = Palette(hw.display)
    s = BootScreen(saved)
    s.draw(hw, GameState(), pal)
    return hw, s


def test_saved_game_shows_resume_and_new_only():
    hw, s = _draw({"round": 2, "phase": "Travel", "saved_at": "earlier session"})
    ids = [b.id for b in s.buttons]
    assert ids == [("resume",), ("new",)]


def test_no_save_shows_new_only():
    hw, s = _draw(None)
    assert [b.id for b in s.buttons] == [("new",)]


def test_no_header_round_text():
    hw, s = _draw({"round": 2, "phase": "Travel", "saved_at": "x"})
    texts = [str(c[1]) for c in hw.display.calls if c[0] == "text"]
    assert not any(t.startswith("resume R") for t in texts)
    assert "Resume Game" in texts and "New Game" in texts
