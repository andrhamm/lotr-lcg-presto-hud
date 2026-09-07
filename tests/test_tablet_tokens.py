"""The tablet's type, target and contrast gate - the spec's Testing table row
"Every chip >= 44 px, every stat value >= 26 px, contrast AA on the tablet
tokens". The HUD's equivalents (test_typography.py, test_contrast.py) read
Python draw sites; the tablet's live in one stylesheet, so this reads that."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSS = os.path.join(ROOT, "docs", "tablet", "style.css")
SCALE = {34, 26, 20, 18, 13}            # DISPLAY, small numerals, BODY, secondary, LABEL
# Widget-owned numerals and glyph sizes, plus the one WORDMARK: the design
# system reserves everything above DISPLAY for "numerals and wordmarks",
# chosen by the widget that owns them and never at a call site. 52 is the
# landing screen's title (home.js/.home-wordmark), which is a wordmark in
# exactly that sense - it is the app's name on an otherwise empty screen,
# not a heading in a document. A sentence may never use it.
NUMERAL_ALLOW = {84, 64, 56, 52, 48, 40, 36, 30, 26, 22}


def _strip_comments(css):
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _css():
    return _strip_comments(open(CSS).read())


def _font_sizes_of(css):
    css = _strip_comments(css)
    out = []
    for m in re.finditer(r"font(?:-size)?\s*:\s*([^;{}]+)[;}]", css):
        for px in re.findall(r"(\d+(?:\.\d+)?)px", m.group(1)):
            out.append(float(px))
    return out


def _font_sizes():
    return _font_sizes_of(_css())


def test_no_text_smaller_than_label():
    small = sorted({s for s in _font_sizes() if s < 13})
    assert not small, "font sizes below LABEL (13px): %s" % small


def test_every_font_size_is_on_the_scale_or_a_numeral():
    off = sorted({s for s in _font_sizes() if s not in SCALE | NUMERAL_ALLOW})
    assert not off, "font sizes off the scale: %s (add to the scale or justify in NUMERAL_ALLOW)" % off


def _button_heights_of(css):
    css = _strip_comments(css)
    out = []
    # locpick-row/sqpick-row/rsheet-row (review finding I4) join the same
    # gate as chip/cta/step: they are min-height:56px today, and this is
    # regression cover so a future rewrite can't quietly drop below 44.
    # log-line is the Game Log's row (milestone 4): a rewindable row is a
    # <button>, so it carries the same floor. cycle-row (milestone 6, Task 2)
    # drill-row (M7) is the scenario chooser's drill-in list - cycles and
    # the quests inside one, the same row either way.
    # pill-name-btn (milestone 6, Task 3) is the rail's stage-pill name, now
    # the way into the read-only Scenario overview - it sits inside the
    # 324px rail, which is exactly where a tap target gets quietly shrunk.
    for m in re.finditer(
        r"\.(chip|cta|step|drill-row|drill-current|step-sm|locpick-row|sqpick-row|rsheet-row|tbtn|tick-btn|log-line|pill-name-btn)(?![\w-])[^{]*\{([^}]*)\}",
        css,
    ):
        hm = re.search(r"(?:min-)?height\s*:\s*(\d+)px", m.group(2))
        if hm:
            out.append((m.group(1), int(hm.group(1))))
    return out


def test_buttons_are_at_least_44px():
    # every rule that sets a height on a button-ish class must be >= 44
    for cls, px in _button_heights_of(_css()):
        assert px >= 44, "%s is %spx tall" % (cls, px)


def _min_height_of(css, selector):
    css = _strip_comments(css)
    m = re.search(r"\." + re.escape(selector) + r"(?![\w-])[^{]*\{([^}]*)\}", css)
    assert m, "no rule found for .%s" % selector
    hm = re.search(r"min-height\s*:\s*(\d+)px", m.group(1))
    return int(hm.group(1)) if hm else None


@pytest.mark.parametrize("selector", ["zone-head", "strip-tools"])
def test_header_chip_rows_clear_the_44px_floor(selector):
    # rail.js's "Edit ->" chip is a 30px header nav chip, not a sheet's own
    # 44px tap target - the spec allows that ONLY inside a row that is itself
    # >= 44px tall (review finding I4), so the ROW is what carries the floor.
    # The strip's Menu chip moved out of .round-row (which is gone with the
    # transport) into .strip-tools at the strip's right end.
    px = _min_height_of(_css(), selector)
    assert px is not None and px >= 44, ".%s has no min-height >= 44px" % selector


def _z_index_of(css, selector):
    css = _strip_comments(css)
    m = re.search(r"\." + re.escape(selector) + r"(?![\w-])[^{]*\{([^}]*)\}", css)
    assert m, "no rule found for .%s" % selector
    zm = re.search(r"z-index\s*:\s*(\d+)", m.group(1))
    return int(zm.group(1)) if zm else None


def test_the_busiest_phase_segment_fits_all_of_its_ticks():
    """The Quest phase has three framework steps and three action windows -
    six ticks in one segment, the most any phase carries. They have to FIT.

    A `flex-wrap: wrap` let the row spill onto a second line, which overflowed
    the strip's content box and clipped the phase NAME off the busiest
    segment; switching to nowrap moved the loss to the other end and cut the
    last action window in half instead. So the sizes are chosen against that
    worst case rather than against a comfortable one, and this asserts the
    arithmetic rather than trusting it.

    Segment width at 1366: (1366 - the rail and the strip's own padding) split
    eight ways, ~116px of content."""
    css = _css()

    def px(selector, prop):
        m = re.search(r"\." + re.escape(selector) + r"(?![\w-])[^{]*\{([^}]*)\}",
                      _strip_comments(css))
        assert m, "no rule for .%s" % selector
        v = re.search(prop + r"\s*:\s*(\d+)px", m.group(1))
        return int(v.group(1)) if v else None

    square = px("tick-framework", "width")
    circle = px("tick-window", "width")
    gap = px("tick-row", "gap")
    assert square and circle and gap is not None
    # Three squares, three circles, five gaps between them.
    needed = 3 * square + 3 * circle + 5 * gap
    assert needed <= 116, (
        "Quest's six ticks need %spx and the segment gives ~116" % needed)
    # And the row must not silently hide the overflow if that ever stops
    # being true - a clipped tick is an action window the player cannot see.
    row = re.search(r"\.tick-row(?![\w-])[^{]*\{([^}]*)\}", _strip_comments(css)).group(1)
    assert "overflow: hidden" not in row


def test_the_primary_action_cannot_be_scrolled_off_the_screen():
    """.pane scrolls, and .cta-row is a direct child of it - so before this,
    any view whose content ran taller than the pane pushed the primary action
    below the fold. Questing: Staging overflowed by 2px at 1366x1024, and by
    more on a device once the safe-area inset shortens the pane, which is how
    it ended up half off-screen there.

    margin-top: auto puts it at the bottom when the content is SHORT. Sticky
    is what keeps it there when the content is LONG, and the ground is what
    stops the content showing through it on the way past. All three are
    required; this asserts all three rather than trusting that the next person
    to touch this rule knows why they are there."""
    css = _strip_comments(_css())
    m = re.search(r"\.pane\s*>\s*\.cta-row(?![\w-])[^{]*\{([^}]*)\}", css)
    assert m, ".pane > .cta-row has no rule pinning it"
    rule = m.group(1)
    assert "position: sticky" in rule, "the CTA row must be sticky, or it scrolls away"
    assert re.search(r"bottom:\s*0", rule), "sticky with no bottom offset does nothing"
    assert "background:" in rule, "content would show through it as it scrolls past"
    base = re.search(r"^\.cta-row(?![\w-])[^{]*\{([^}]*)\}", css, re.M)
    assert base and "margin-top: auto" in base.group(1), (
        "it still has to sit at the bottom when the content is short")


def test_the_modal_scrim_covers_everything_the_app_draws():
    """A modal that things show through is not a modal. The rail's pinned rows
    are what did it: `position: sticky` with a z-index makes each one its own
    stacking context, so a scrim with no z-index at all painted UNDER the
    chosen cycle, the chosen scenario and their headers.

    So the scrim has to outrank every z-index the app assigns - the pins and
    the corner reload. The ?debug=1 readout is the one deliberate exception:
    it is a measuring instrument, and it has to be able to report on a modal
    too."""
    css = _css()
    scrim = _z_index_of(css, "scrim")
    assert scrim is not None, "the scrim needs an explicit z-index"
    for selector in ("setup-list > .label", "app-reload"):
        # (the first is matched by its own leading class below)
        pass
    ranked = {}
    for m in re.finditer(r"([^{}]*)\{([^}]*z-index\s*:\s*(\d+)[^}]*)\}", _strip_comments(css)):
        sel, z = m.group(1).strip(), int(m.group(3))
        ranked[sel] = z
    below = {s: z for s, z in ranked.items()
             if z >= scrim and "scrim" not in s and "debug-overlay" not in s}
    assert not below, "these paint at or above the modal scrim: %s" % below
    # And it really is above the two that mattered.
    assert scrim > _z_index_of(css, "app-reload")


def test_font_regex_does_not_cross_braces():
    assert _font_sizes_of(".a { font-size: 13px } .b { width: 7px }") == [13.0]


def test_button_regex_ignores_comments():
    css = "/* like .chip */ .other { height: 20px } .chip { height: 44px }"
    assert _button_heights_of(css) == [("chip", 44)]


def _contrast(fg, bg):
    def lum(rgb):
        r, g, b = [c / 255 for c in rgb]
        f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)
    l1, l2 = sorted([lum(fg), lum(bg)], reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


def _pal():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not installed")
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(ROOT, "docs", "js")
        for f in os.listdir(src):
            if f.endswith(".js"):
                shutil.copy(os.path.join(src, f), os.path.join(tmp, f))
        with open(os.path.join(tmp, "package.json"), "w") as f:
            f.write('{"type":"module"}')
        probe = os.path.join(tmp, "probe.mjs")
        with open(probe, "w") as f:
            f.write('import { pal } from "./ui.js"; console.log(JSON.stringify(pal));')
        r = subprocess.run([node, probe], cwd=tmp, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        raw = json.loads(r.stdout)
    rgb = lambda s: tuple(int(x) for x in re.findall(r"\d+", s))
    return {k: rgb(v) for k, v in raw.items() if isinstance(v, str) and v.startswith("rgb")}


@pytest.mark.parametrize("ink,ground", [
    ("tan", "bg"), ("tan", "card"), ("tan", "card_hi"), ("tan", "well"),
    ("gold", "bg"), ("gold", "card"), ("gold", "card_hi"), ("gold", "well"),
    ("muted", "card"), ("dim", "card"), ("dim", "well"),
    ("ok_fg", "btn_ok"), ("amber", "card"), ("red", "card"), ("green", "card"),
])
def test_tablet_ink_on_ground_clears_aa(ink, ground):
    pal = _pal()
    ratio = _contrast(pal[ink], pal[ground])
    assert ratio >= 4.5, "%s on %s is %.2f:1" % (ink, ground, ratio)
