import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests.fake_hardware import FakeDisplay
from ui.theme import Palette
from ui import widgets as W


def _d():
    d = FakeDisplay()
    return d, Palette(d)


def test_disc_stays_in_bounds_and_draws():
    d, pal = _d()
    W.disc(d, 40, 40, 15, pal.gold)
    assert d.calls, "disc drew nothing"
    for c in d.calls:
        assert c[0] == "rect"
        _, x, y, w, h, _pen = c
        assert 0 <= x and 0 <= y and x + w <= 480 and y + h <= 480


def test_ring_full_then_partial_uses_both_pens():
    d, pal = _d()
    W.ring(d, 40, 40, 15, 2, 0.5, pal.gold, pal.dim)
    pens = {c[5] for c in d.calls if c[0] == "rect"}
    assert pal.dim in pens and pal.gold in pens


def test_token_draws_value_text_centered():
    d, pal = _d()
    W.token(d, pal, 40, 40, 14, 2, 42, pal.gold, 0.5, pal.gold, pal.dim)
    texts = [c for c in d.calls if c[0] == "text" and str(c[1]) == "42"]
    assert texts, "token value not drawn"


def test_wx_small_sun_and_storm_differ():
    d, pal = _d()
    W.wx_small(d, pal, 0, 40, 40, 6)
    sun = len(d.calls)
    d2, _ = _d()
    W.wx_small(d2, pal, 3, 40, 40, 6)
    assert sun != len(d2.calls)
