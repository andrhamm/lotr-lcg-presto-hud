import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.fake_hardware import FakeHardware
from ui.theme import Palette
from ui.screen_phases import ScreenPhases
from gamestate import GameState


def _draw(step="3.3"):
    hw = FakeHardware()
    pal = Palette(hw.display)
    g = GameState()
    g.step = step
    s = ScreenPhases()
    s.draw(hw, g, pal)
    return hw, s, g


def test_header_title_and_x_close():
    hw, s, g = _draw()
    texts = [str(c[1]) for c in hw.display.calls if c[0] == "text"]
    assert "Game Phases" in texts and "X" in texts
    navs = [b.id for b in s.buttons if b.id[0] == "nav"]
    assert navs == [("nav", "close")]


def test_action_window_markers_and_combat_loop_note():
    hw, s, g = _draw("6.2")   # combat expanded
    texts = [str(c[1]) for c in hw.display.calls if c[0] == "text"]
    assert any("(loops: each player)" in t for t in texts)
    assert any("Combat loops in turn order" in t for t in texts)
    # purple window markers drawn as 8x8 rects
    purple = Palette(FakeHardware().display).purple
    assert any(c[0] == "rect" and c[3] == 8 and c[4] == 8 and c[5] == purple
               for c in hw.display.calls)


def test_step_jump_still_works():
    hw, s, g = _draw("6.2")
    step_btn = [b for b in s.buttons if b.id == ("step", "6.P")][0]
    s.on_button(step_btn, g)
    assert g.step == "6.P"
    assert g.view == "combat_player"
