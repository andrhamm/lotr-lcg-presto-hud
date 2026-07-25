"""Help screen (Settings -> Help) + the conventions legend."""
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


def test_done_closes_back_to_settings():
    """Help is opened from Settings, never at boot - Done returns there.

    A bare ("close",) is the *modal* idiom; the screen router only understands
    ("goto", "close") - returning the modal form left Done a dead button.
    """
    hw, pal, game, s = _setup(FirstRunScreen)
    s.page = PAGES - 1
    s.draw(hw, game, pal)
    assert s.on_button(next(b for b in s.buttons if b.id[0] == "fr_done")) == ("goto", "close")
    assert s.page == 0          # reopens at the start next time


def test_header_close_also_exits():
    hw, pal, game, s = _setup(FirstRunScreen)
    s.draw(hw, game, pal)
    close = [b for b in s.buttons if b.id[0] in ("close", "nav")]
    assert close, "help header must offer a way out"
    assert s.on_button(close[0]) == ("goto", "close")


def test_both_twins_keep_help_on_the_nav_trail():
    """("goto","close") pops the nav trail, so the router must have *pushed*
    the caller when it opened Help - otherwise Done lands on the play screen
    instead of Settings. The push list is inline in each twin's router."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for rel, marker in (("main.py", 'target in ("settings"'),
                        ("docs/js/main.js", '].includes(target)')):
        with open(os.path.join(root, rel)) as f:
            src = f.read()
        i = src.index(marker)
        window = src[i - 200:i + 200]
        for key in ("firstrun", "legend"):
            assert '"%s"' % key in window, "%s: %s missing from the nav trail" % (rel, key)


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
