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


def test_phase_block_framework_and_window_use_correct_accents():
    d, pal = _d()
    h = W.phase_block(d, pal, 8, 100, 300,
                       [("framework", "Reveal 1 card per player."),
                        ("window", "Responses.")])
    accents = [c[5] for c in d.calls if c[0] == "rect" and c[1] == 8 and c[3] == 4]
    assert accents == [pal.red, pal.green]
    assert h > 0


def test_phase_block_omits_framework_section_when_absent():
    d, pal = _d()
    W.phase_block(d, pal, 8, 100, 300, [("window", "Commit characters.")])
    accents = [c[5] for c in d.calls if c[0] == "rect" and c[1] == 8 and c[3] == 4]
    assert accents == [pal.green]
    texts = [c[1] for c in d.calls if c[0] == "text"]
    assert "FRAMEWORK" not in texts and "YOUR WINDOW" in texts


def test_phase_block_reserve_right_produces_more_wrapped_lines():
    d, pal = _d()
    h_wide = W.phase_block(d, pal, 8, 100, 300, [("window", "x" * 80)])
    d2, pal2 = _d()
    h_narrow = W.phase_block(d2, pal2, 8, 100, 300, [("window", "x" * 80)], 34)
    assert h_narrow > h_wide   # less usable width, same unbroken text -> more lines


def test_phase_block_multi_paragraph_section_wraps_each_paragraph():
    d, pal = _d()
    W.phase_block(d, pal, 8, 100, 300,
                   [("framework", ["First sentence.", "Second sentence."])])
    texts = [str(c[1]) for c in d.calls if c[0] == "text"]
    assert any("First" in t for t in texts) and any("Second" in t for t in texts)


def test_willpower_staging_meter_fills_proportionally_and_has_fixed_height():
    d, pal = _d()
    h = W.willpower_staging_meter(d, pal, 8, 100, 300, 11, 7)
    assert h == 64
    fills = [c for c in d.calls if c[0] == "rect" and c[4] == 10
             and c[5] in (pal.gold, pal.outline)]
    assert len(fills) == 2
    gold_w = next(c[3] for c in fills if c[5] == pal.gold)
    outline_w = next(c[3] for c in fills if c[5] == pal.outline)
    assert gold_w > outline_w        # willpower (11) ahead of staging (7)


def test_willpower_staging_meter_tied_shows_dim_message():
    d, pal = _d()
    W.willpower_staging_meter(d, pal, 8, 100, 300, 5, 5)
    texts = [str(c[1]) for c in d.calls if c[0] == "text"]
    assert any("Tied" in t for t in texts)


def test_willpower_staging_meter_losing_shows_threat_gain_sentence():
    d, pal = _d()
    W.willpower_staging_meter(d, pal, 8, 100, 300, 4, 9)
    texts = [str(c[1]) for c in d.calls if c[0] == "text"]
    assert any("Each player will gain 5" in t for t in texts)
