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
NUMERAL_ALLOW = {84, 64, 56, 48, 40, 36, 30, 26, 22}   # widget-owned numerals and glyph sizes


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
    for m in re.finditer(
        r"\.(chip|cta|step|scenario-row|step-sm|locpick-row|sqpick-row|rsheet-row|tbtn|tick-btn)(?![\w-])[^{]*\{([^}]*)\}",
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


@pytest.mark.parametrize("selector", ["zone-head", "round-row"])
def test_header_chip_rows_clear_the_44px_floor(selector):
    # rail.js's "Edit ->" chip and strip.js's "Menu ->" chip are 30px header
    # nav chips, not a sheet's own 44px tap target - the spec allows that
    # ONLY inside a row that is itself >= 44px tall (review finding I4), so
    # the row - .zone-head / .round-row - is what has to carry the floor.
    px = _min_height_of(_css(), selector)
    assert px is not None and px >= 44, ".%s has no min-height >= 44px" % selector


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
