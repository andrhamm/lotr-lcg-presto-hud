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
NUMERAL_ALLOW = {84, 64, 56, 48, 40, 36, 30, 26, 24, 22}   # widget-owned numerals and glyph sizes


def _css():
    with open(CSS) as f:
        return f.read()


def _font_sizes():
    css = _css()
    out = []
    for m in re.finditer(r"font(?:-size)?\s*:\s*([^;]+);", css):
        for px in re.findall(r"(\d+(?:\.\d+)?)px", m.group(1)):
            out.append(float(px))
    return out


def test_no_text_smaller_than_label():
    small = sorted({s for s in _font_sizes() if s < 13})
    assert not small, "font sizes below LABEL (13px): %s" % small


def test_every_font_size_is_on_the_scale_or_a_numeral():
    off = sorted({s for s in _font_sizes() if s not in SCALE | NUMERAL_ALLOW})
    assert not off, "font sizes off the scale: %s (add to the scale or justify in NUMERAL_ALLOW)" % off


def test_buttons_are_at_least_44px():
    css = _css()
    # every rule that sets a height on a button-ish class must be >= 44
    for m in re.finditer(r"\.(chip|cta|step|scenario-row|step-sm)[^{]*\{([^}]*)\}", css):
        body = m.group(2)
        hm = re.search(r"(?:min-)?height\s*:\s*(\d+)px", body)
        if hm:
            assert int(hm.group(1)) >= 44, "%s is %spx tall" % (m.group(1), hm.group(1))


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
