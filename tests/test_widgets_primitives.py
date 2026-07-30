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
    # No label rows any more - the bar is the whole vocabulary, so the only
    # text in the block is the phase copy itself.
    texts = [c[1] for c in d.calls if c[0] == "text"]
    assert "FRAMEWORK" not in texts and "YOUR WINDOW" not in texts
    assert "Commit characters." in texts


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


# -- progress-row widgets ---------------------------------------------------
# These were private methods on QuestingProgressModal, which is how the web
# twin came to draw a different row. Pinned here so the shared versions carry
# the contract both twins are written against.

def test_stepper_geometry_is_the_players_screen_geometry():
    # 40px disc inside a 52px tap target - the size the rest of the app uses
    # for a value the player nudges repeatedly.
    assert (W.STEP_R, W.STEP_HIT) == (20, 52)


def test_stepper_plus_goes_dead_at_the_target():
    # RR p.22: excess progress beyond a stage's quest points is DISCARDED on
    # advance, so there is nothing past the target to record. Dead means no
    # button at all, not a button that does nothing.
    d, pal = _d()
    bs = []
    W.stepper_cluster(d, pal, bs, 400, 40, 3, 3, True, ("m",), ("p",))
    assert [b.id for b in bs] == [("m",)]


def test_stepper_minus_goes_dead_at_zero():
    d, pal = _d()
    bs = []
    W.stepper_cluster(d, pal, bs, 400, 40, 0, 3, False, ("m",), ("p",))
    assert [b.id for b in bs] == [("p",)]


def test_stepper_keeps_both_when_the_row_has_no_target():
    # A condition stage has no quest points, so there is no target to be "at".
    d, pal = _d()
    bs = []
    W.stepper_cluster(d, pal, bs, 400, 40, 2, 0, False, ("m",), ("p",))
    assert [b.id for b in bs] == [("m",), ("p",)]


def test_stepper_tap_targets_are_the_full_hit_size():
    d, pal = _d()
    bs = []
    W.stepper_cluster(d, pal, bs, 400, 40, 1, 3, False, ("m",), ("p",))
    for b in bs:
        assert (b.w, b.h) == (W.STEP_HIT, W.STEP_HIT), b.id


def test_stepper_returns_its_own_left_edge():
    # The caller sizes the bar and the row's tap band against this, so it has
    # to be the real edge - a wrong number overlaps the name.
    d, pal = _d()
    bs = []
    left = W.stepper_cluster(d, pal, bs, 400, 40, 1, 3, False, ("m",), ("p",))
    assert left == min(b.x for b in bs) + (W.STEP_HIT // 2) - W.STEP_R


def test_fill_bar_is_amber_at_target_not_the_row_accent():
    d, pal = _d()
    W.fill_bar(d, pal, 10, 10, 100, 6, 3, 3, pal.green, True)
    assert any(c[-1] == pal.amber for c in d.calls)
    assert not any(c[-1] == pal.green for c in d.calls)


def test_fill_bar_uses_the_accent_below_target():
    d, pal = _d()
    W.fill_bar(d, pal, 10, 10, 100, 6, 1, 3, pal.green, False)
    assert any(c[-1] == pal.green for c in d.calls)


def test_fill_bar_never_overflows_its_width():
    # A location can sit over its points until the guided flow resolves it.
    d, pal = _d()
    W.fill_bar(d, pal, 10, 10, 100, 6, 9, 3, pal.green, True)
    for c in d.calls:
        _, x, _y, w, _h, _pen = c
        assert x + w <= 110


def test_fill_bar_with_no_target_draws_only_the_well():
    d, pal = _d()
    W.fill_bar(d, pal, 10, 10, 100, 6, 5, 0, pal.green, False)
    assert [c[-1] for c in d.calls] == [pal.well]


def test_prog_row_card_stripes_the_left_edge_in_the_accent():
    d, pal = _d()
    W.prog_row_card(d, pal, 8, 20, 464, W.ROW_H, pal.green)
    stripe = [c for c in d.calls if c[-1] == pal.green]
    assert stripe, "no accent stripe"
    _, x, y, w, h, _ = stripe[0]
    assert (x, y, w, h) == (8, 20, 4, W.ROW_H)


def test_every_glyph_kind_draws_inside_its_box():
    d, pal = _d()
    for kind in ("l", "q", "s"):
        d.calls.clear()
        W.glyph(d, pal, kind, 100, 100, pal.gold)
        assert d.calls, kind
        for c in d.calls:
            if c[0] != "rect":
                continue
            _, x, y, w, h, _pen = c
            assert 100 <= x and x + w <= 100 + 20, (kind, c)
            assert 100 <= y and y + h <= 100 + 20, (kind, c)
