"""M5 Task 1: first-run guidance + the conventions legend."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.fake_hardware import FakeHardware
from ui.theme import Palette
from ui.screen_firstrun import FirstRunScreen, LegendScreen, PAGES
from gamestate import GameState


def _setup(cls):
    hw = FakeHardware()
    return hw, Palette(hw.display), GameState(), cls()


def _texts(hw):
    return [str(c[1]) for c in hw.display.calls if c[0] == "text"]


def test_every_page_draws_and_paginates_forward():
    hw, pal, game, s = _setup(FirstRunScreen)
    seen = []
    for _ in range(PAGES):
        s.draw(hw, game, pal)
        seen.append(s.page)
        nxt = [b for b in s.buttons if b.id[0] == "fr_next"]
        if nxt:
            s.on_button(nxt[0])
    assert seen == list(range(PAGES))


def test_first_page_has_no_back_and_last_page_offers_done():
    hw, pal, game, s = _setup(FirstRunScreen)
    s.draw(hw, game, pal)
    assert not any(b.id[0] == "fr_back" for b in s.buttons)
    s.page = PAGES - 1
    s.draw(hw, game, pal)
    assert any(b.id[0] == "fr_done" for b in s.buttons)
    assert not any(b.id[0] == "fr_next" for b in s.buttons)


def test_back_clamps_at_the_first_page():
    hw, pal, game, s = _setup(FirstRunScreen)
    s.page = 1
    s.draw(hw, game, pal)
    s.on_button(next(b for b in s.buttons if b.id[0] == "fr_back"))
    assert s.page == 0
    s.on_button(type("B", (), {"id": ("fr_back",)})())
    assert s.page == 0


def test_done_signals_the_router():
    hw, pal, game, s = _setup(FirstRunScreen)
    s.page = PAGES - 1
    s.draw(hw, game, pal)
    assert s.on_button(next(b for b in s.buttons if b.id[0] == "fr_done")) == ("first_run_done",)


def test_legend_screen_explains_the_colour_convention():
    hw, pal, game, s = _setup(LegendScreen)
    s.draw(hw, game, pal)
    joined = " ".join(_texts(hw)).lower()
    assert "your window" in joined and "happens anyway" in joined
    assert "elimination" in joined


def test_every_button_meets_the_touch_target_floor():
    for cls in (FirstRunScreen, LegendScreen):
        hw, pal, game, s = _setup(cls)
        s.draw(hw, game, pal)
        for b in s.buttons:
            assert b.w >= 24 and b.h >= 24, (cls.__name__, b.id)
