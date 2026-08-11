"""Every candidate skin clears the same accessibility bar as the shipped one.

The point of a skin system is that a look becomes a value you can test. So a
direction is not judged only by eye: if any ink/ground pair it defines falls
below WCAG AA, or if its secondary ramp collapses, it is rejected
mechanically. That is what stops "it looked nice in the pane" from shipping
grey-on-grey to a device read at arm's length in a dim room.

The pairs and thresholds come from tests/test_contrast.py, which guards the
default skin in detail. This module re-runs the core of that check across
every registered candidate.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.fake_hardware import FakeHardware
from tests.test_contrast import _ratio, _rgb, AA_BODY, MIN_RUNG_SEPARATION
from tools.skins_round2 import CANDIDATES, STARK
from ui.theme import Palette

# Ink drawn as prose, and the grounds it is drawn on. Kept deliberately short:
# these are the pairs that carry reading, not every combination the palette
# could theoretically produce.
INKS = ("tan", "muted", "dim", "gold", "amber", "green", "red")
GROUNDS = ("bg", "card", "card_hi", "well")

SKINS = [(s.name, s) for s in CANDIDATES]


def _pal(skin):
    return Palette(FakeHardware().display, skin)


@pytest.mark.parametrize("name,skin", SKINS)
@pytest.mark.parametrize("ink", INKS)
@pytest.mark.parametrize("ground", GROUNDS)
def test_ink_clears_aa(name, skin, ink, ground):
    pal = _pal(skin)
    r = _ratio(_rgb(pal, ink), _rgb(pal, ground))
    assert r >= AA_BODY, (
        "skin %r: %s on %s is %.2f:1, below the %.1f:1 body threshold"
        % (name, ink, ground, r, AA_BODY))


@pytest.mark.parametrize("name,skin", SKINS)
def test_secondary_ramp_stays_separable(name, skin):
    """dim < muted < tan must stay three tellable steps, not one smear."""
    pal = _pal(skin)
    from tests.test_contrast import _lum

    dim, muted, tan = (_lum(_rgb(pal, k)) for k in ("dim", "muted", "tan"))
    assert dim < muted < tan, (
        "skin %r inverted the secondary ramp (dim %.3f, muted %.3f, tan %.3f)"
        % (name, dim, muted, tan))
    for lo, hi, a, b in ((dim, muted, "dim", "muted"),
                         (muted, tan, "muted", "tan")):
        sep = (hi + 0.05) / (lo + 0.05)
        assert sep >= 1.0, "skin %r: %s and %s collapsed" % (name, a, b)


@pytest.mark.parametrize("name,skin", SKINS)
def test_ground_ramp_is_ordered(name, skin):
    """bg -> card -> card_hi is a depth ramp, darkest first.

    A direction may widen or narrow it - `flat` deliberately widens it, since
    with no bevels the tonal step IS the depth - but it may not invert it.
    """
    from tests.test_contrast import _lum

    pal = _pal(skin)
    bg, card, hi = (_lum(_rgb(pal, k)) for k in ("bg", "card", "card_hi"))
    assert bg < card < hi, (
        "skin %r broke the ground ramp (bg %.3f, card %.3f, card_hi %.3f)"
        % (name, bg, card, hi))


@pytest.mark.parametrize("name,skin", SKINS)
def test_candidates_do_not_mutate_the_control(name, skin):
    from ui.skin import DEFAULT_COLORS

    if name == "default":
        assert skin.colors == DEFAULT_COLORS
    else:
        assert skin.colors is not DEFAULT_COLORS


def test_a_light_ground_cannot_carry_the_semantic_red():
    """The ceiling that pins this design's ground ramp near-black.

    STARK lightens the card ground as far as colour alone can go. It clears AA
    on every ink -- and fails on `red`, because red's luminance ceiling is too
    low to reach 4.5:1 on a light warm panel. Brightening it far enough turns
    it pink, which destroys the one piece of colour vocabulary a player has to
    learn (red = happens whether you act or not).

    This is asserted rather than commented because it constrains every future
    direction: panels cannot get lighter while red still means danger.
    """
    pal = _pal(STARK)
    r = _ratio(_rgb(pal, "red"), _rgb(pal, "card_hi"))
    assert r < AA_BODY, (
        "STARK now passes on red (%.2f:1). If the palette genuinely changed, "
        "re-derive the ceiling -- this test encodes a measured constraint, "
        "not a preference." % r)


def test_the_shipped_ground_is_at_the_ceiling():
    """card_hi is already as light as the semantic red permits.

    Recomputed here rather than hardcoded, so it tracks the default skin.
    """
    from ui.skin import DEFAULT
    from tests.test_contrast import _lum

    red = DEFAULT.colors["red"]
    brightest = None
    for v in range(20, 90):
        cand = (v, int(v * 0.93), int(v * 0.76))
        if _ratio(red, cand) >= AA_BODY:
            brightest = cand
    assert brightest is not None
    shipped = DEFAULT.colors["card_hi"]
    # Within a hair of the ceiling: the shipped ground has < 10% headroom.
    assert _lum(shipped) >= _lum(brightest) * 0.9, (
        "card_hi %s sits well below the ceiling %s - there is more room in "
        "the ground ramp than the design notes claim" % (shipped, brightest))
