"""M5 accessibility gate: every text colour the app actually draws must clear
WCAG 2.1 AA against every background it is drawn on.

Thresholds: 4.5:1 for body text, 3.0:1 for large text. The device draws at a
fixed small size, so body text (4.5) is the bar that matters here.

Before this gate, `pal.dim` failed at EVERY background it was used on
(2.04-2.85 - below even the large-text floor) while being the most-used
secondary colour: captions, hints, disabled states, log metadata. `muted` and
`red` failed the body threshold too. Raising `dim` alone would have collided
with `muted` (they were only ~1.9x apart in luminance), so the whole secondary
ramp moved together and the separation between rungs is asserted below.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.fake_hardware import FakeHardware
from ui.theme import Palette

AA_BODY = 4.5
MIN_RUNG_SEPARATION = 1.25   # adjacent ramp steps must stay tellable apart


def _rgb(pal, name):
    """Palette pens are opaque ints on device and (r,g,b) on the host shim."""
    v = getattr(pal, name)
    return v if isinstance(v, tuple) else ((v >> 16) & 255, (v >> 8) & 255, v & 255)


def _lum(c):
    def f(v):
        v /= 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (f(x) for x in c)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _ratio(a, b):
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _pal():
    hw = FakeHardware()
    return Palette(hw.display)


# Foregrounds the app draws as text, against the surfaces they land on.
FOREGROUNDS = ["gold", "tan", "muted", "dim", "value", "green", "amber", "red", "ok_fg"]
BACKGROUNDS = ["bg", "card", "card_hi", "well", "btn"]


def test_every_text_colour_clears_aa_body_on_every_background():
    pal = _pal()
    failures = []
    for fg in FOREGROUNDS:
        for bg in BACKGROUNDS:
            r = _ratio(_rgb(pal, fg), _rgb(pal, bg))
            if r < AA_BODY:
                failures.append("%s on %s = %.2f" % (fg, bg, r))
    assert not failures, "WCAG AA body-text failures:\n  " + "\n  ".join(failures)


def test_secondary_ramp_stays_visually_distinct():
    """dim < muted < tan must remain tellable apart after the contrast lift -
    otherwise the hierarchy that carries meaning collapses into one flat tone."""
    pal = _pal()
    dim, muted, tan = (_lum(_rgb(pal, n)) for n in ("dim", "muted", "tan"))
    assert dim < muted < tan, "the secondary ramp inverted"
    assert muted / dim >= MIN_RUNG_SEPARATION, "muted is too close to dim"
    assert tan / muted >= MIN_RUNG_SEPARATION, "tan is too close to muted"
