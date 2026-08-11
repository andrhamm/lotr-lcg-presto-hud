"""BITMAP8_W must keep matching the upstream font data it was generated from.

The table was hand-probed for a long time and every layout gate measures
through it, so a silent drift between it and the device's real font is a lint
suite passing on wrong numbers. It now comes from tools/data/fonts.json
(compiled by tools/build_fonts.py from the pinned upstream headers); this is
the test that keeps the two in step.
"""
import json
import os

import pytest

from tests.fake_hardware import BITMAP8_W, measure_bitmap8

FONTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "tools", "data", "fonts.json")

pytestmark = pytest.mark.skipif(
    not os.path.exists(FONTS),
    reason="tools/data/fonts.json absent - run tools/build_fonts.py")


def _glyphs(font="font8"):
    with open(FONTS) as f:
        return json.load(f)["fonts"][font]["glyphs"]


def test_every_printable_ascii_is_covered():
    """No character may fall through to the 4px fallback.

    The fallback is what hid `|` measuring 4 where it is 1 and `#` measuring
    4 where it is 5 - the latter being the direction that overflows.
    """
    missing = [chr(c) for c in range(32, 127) if chr(c) not in BITMAP8_W]
    assert not missing, "unmeasured glyphs fall back to 4px: %r" % missing


def test_widths_match_upstream():
    glyphs = _glyphs()
    wrong = {ch: (w, glyphs[ch]["w"])
             for ch, w in sorted(BITMAP8_W.items())
             if ch in glyphs and glyphs[ch]["w"] != w}
    assert not wrong, "table disagrees with upstream (probed, actual): %r" % wrong


def test_no_invented_glyphs():
    glyphs = _glyphs()
    extra = sorted(set(BITMAP8_W) - set(glyphs))
    assert not extra, "table measures characters the font lacks: %r" % extra


def test_measure_matches_picographics_rule():
    """widths summed, plus one pixel between glyphs but not after the last.

    Mirrors bitmap_fonts.cpp::measure_text, which subtracts the trailing
    letter_spacing.
    """
    assert measure_bitmap8("AB", 1) == 4 + 1 + 4
    assert measure_bitmap8("A", 1) == 4
    assert measure_bitmap8("", 1) == 0
    # scale multiplies the whole measurement, spacing included
    assert measure_bitmap8("AB", 2) == 2 * measure_bitmap8("AB", 1)


def test_the_truncation_marker_is_measured_correctly():
    """The design system requires the [...] marker be measured, not appended.

    Its brackets were two of the characters missing from the table, so the
    marker used to reserve 4px more than it needs.
    """
    from ui.widgets import MORE_MARKER

    glyphs = _glyphs()
    expected = (sum(glyphs[c]["w"] for c in MORE_MARKER)
                + len(MORE_MARKER) - 1)
    assert measure_bitmap8(MORE_MARKER, 1) == expected
