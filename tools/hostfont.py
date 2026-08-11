"""Draw the device's real bitmap glyphs on the host.

`tools/preview.py` used to render text in Menlo and `docs/js/ui.js` in Courier
New. Both are metric-faithful and glyph-substituted, which is how three
retheme attempts were judged against letterforms the device does not have.

The device draws a glyph as a set of filled rectangles, one per run of set
pixels (`bitmap_fonts.cpp::character` plots a `scale`x`scale` rect per pixel;
`ui/icons.py` already does the run-compressed equivalent for icon masks). So
reproducing it exactly on the host needs no font engine at all - just the mask
data from `tools/build_fonts.py` and the same run decoder.

Runs are cached per (font, char) exactly as `icons._runs_for` caches per mask,
and for the same reason: decoding per draw was measured at 147ms for one large
icon before that cache existed.
"""
import json
import os

_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data",
                     "fonts.json")

_FONTS = None
_RUNS = {}

# PicoGraphics' default letter_spacing, applied between glyphs but not after
# the last one (bitmap_fonts.cpp::measure_text).
LETTER_SPACING = 1


def _load():
    global _FONTS
    if _FONTS is None:
        if not os.path.exists(_DATA):
            raise SystemExit(
                "tools/data/fonts.json missing - run python3 tools/build_fonts.py")
        with open(_DATA) as f:
            _FONTS = json.load(f)["fonts"]
    return _FONTS


def available():
    """True when the glyph data is present, so callers can fall back."""
    return os.path.exists(_DATA)


def height(font="font8"):
    return _load()[font]["height"]


def width(ch, font="font8"):
    """A glyph's own width, with the 4px fallback for anything unmapped."""
    g = _load()[font]["glyphs"].get(ch)
    return g["w"] if g else 4


def measure(s, scale=1, font="font8"):
    """Match bitmap_fonts.cpp::measure_text: widths + spacing between."""
    s = str(s)
    if not s:
        return 0
    return (sum(width(c, font) for c in s)
            + (len(s) - 1) * LETTER_SPACING) * scale


def runs(ch, font="font8"):
    """[(row, col, length)] of set pixels, cached per glyph."""
    key = (font, ch)
    cached = _RUNS.get(key)
    if cached is not None:
        return cached
    g = _load()[font]["glyphs"].get(ch)
    out = []
    if g:
        w = g["w"]
        for row, bits in enumerate(g["rows"]):
            col = 0
            while col < w:
                if bits & (1 << (w - 1 - col)):
                    run = col
                    while run < w and bits & (1 << (w - 1 - run)):
                        run += 1
                    out.append((row, col, run - col))
                    col = run
                else:
                    col += 1
    _RUNS[key] = out
    return out


def draw(rect, s, x, y, scale=1, font="font8"):
    """Plot a string via `rect(x, y, w, h)`, advancing exactly as the device.

    `rect` is whatever the caller fills with - a PIL draw shim, a canvas, or
    the device's own rectangle(). That is the point: the host and the device
    run identical geometry.
    """
    cx = x
    for ch in str(s):
        for row, col, length in runs(ch, font):
            rect(cx + col * scale, y + row * scale, length * scale, scale)
        cx += (width(ch, font) + LETTER_SPACING) * scale
    return cx - x - LETTER_SPACING * scale
