"""Host-side stand-in for hardware.Hardware and the PicoGraphics display.

Records draw calls and lets tests simulate taps, so screen layout / hit-testing
logic can be exercised under CPython without a device.

measure_text implements the REAL bitmap8 metric, captured from the device:
per-glyph widths plus 1px inter-character spacing, all scaled linearly
(verified: measure("AB",1)=9=4+4+1; measure(s,2)=2*measure(s,1)).
"""

# Glyph widths at scale 1 for PicoGraphics bitmap8, for ALL 95 printable
# ASCII characters.
#
# This table was originally probed by hand on the device and covered 82 of
# them. Every probed value turned out to be correct -- but the 13 it omitted
# fell through to a 4px fallback, so `|` measured 4 where it is 1, `[` and `]`
# measured 4 where they are 2, and `#` measured 4 where it is 5. Only `#`
# errs in the dangerous direction (measuring narrower than reality, which is
# how text overflows a linter that passed), and `#` is never drawn. The rest
# over-reserved, which is why nothing visibly broke.
#
# It is now GENERATED from the upstream font data rather than probed --
# tools/build_fonts.py compiles libraries/bitmap_fonts/font8_data.hpp into
# tools/data/fonts.json, and tests/test_font_metrics.py asserts this table
# still matches it. Do not hand-edit; regenerate.
BITMAP8_W = {
    ' ': 3, '!': 1, '"': 3, '#': 5, '$': 4, '%': 4, '&': 4, "'": 1, '(': 3,
    ')': 3, '*': 3, '+': 3, ',': 2, '-': 3, '.': 2, '/': 4, '0': 4, '1': 3,
    '2': 4, '3': 4, '4': 4, '5': 4, '6': 4, '7': 4, '8': 4, '9': 4, ':': 1,
    ';': 2, '<': 3, '=': 3, '>': 3, '?': 4, '@': 4, 'A': 4, 'B': 4, 'C': 4,
    'D': 4, 'E': 4, 'F': 4, 'G': 4, 'H': 4, 'I': 3, 'J': 4, 'K': 4, 'L': 4,
    'M': 5, 'N': 4, 'O': 4, 'P': 4, 'Q': 4, 'R': 4, 'S': 4, 'T': 5, 'U': 4,
    'V': 4, 'W': 5, 'X': 4, 'Y': 4, 'Z': 4, '[': 2, '\\': 4, ']': 2,
    '^': 3, '_': 3, '`': 4, 'a': 4, 'b': 4, 'c': 4, 'd': 4, 'e': 4, 'f': 4,
    'g': 4, 'h': 4, 'i': 3, 'j': 4, 'k': 4, 'l': 3, 'm': 5, 'n': 4, 'o': 4,
    'p': 4, 'q': 4, 'r': 4, 's': 4, 't': 4, 'u': 4, 'v': 4, 'w': 5, 'x': 4,
    'y': 4, 'z': 4, '{': 3, '|': 1, '}': 3, '~': 4,
}


def measure_bitmap8(s, scale=1):
    s = str(s)
    if not s:
        return 0
    w = sum(BITMAP8_W.get(c, 4) for c in s) + (len(s) - 1)
    return w * scale


# -- type binding ----------------------------------------------------------
# A binding maps each type-scale tier to a concrete (font, scale). The app
# asks for LABEL/BODY/DISPLAY (1/2/3); which font renders them, and at what
# multiplier, is a visual decision that belongs to a skin.
#
# It exists because the alternatives are not drop-in replacements. font8 is
# 8px tall, so 1/2/3 gives an 8/16/24px ladder. font14_outline is 14px tall
# at scale 1 and has NO smaller size, so it cannot supply a LABEL tier that
# reads as smaller than its own BODY -- a font14 direction is necessarily a
# HYBRID that falls back to font8 for chrome. Discovering that is the whole
# point of measuring a font rather than looking at a picture of one.
#
# Scales outside the tiers (4-9, the numerals and wordmarks) always render in
# the binding's display font at the requested multiplier.
BITMAP8_BINDING = {1: ("font8", 1), 2: ("font8", 2), 3: ("font8", 3)}

_binding = BITMAP8_BINDING


def set_type_binding(binding=None):
    """Install a tier -> (font, scale) map for newly built displays.

    Module-level on purpose: the 118 scene builders each construct their own
    FakeHardware internally, so a probe has no other seam to reach them
    through. Always restore the default when done.
    """
    global _binding
    _binding = binding or BITMAP8_BINDING
    return _binding


def current_binding():
    return _binding


class FakeDisplay:
    def __init__(self, w=480, h=480, binding=None):
        self.w = w
        self.h = h
        self._pen = 0
        self.calls = []
        self.binding = binding or current_binding()

    def get_bounds(self):
        return (self.w, self.h)

    def create_pen(self, r, g, b):
        return (r, g, b)

    def set_pen(self, pen):
        self._pen = pen

    def clear(self):
        self.calls.append(("clear", self._pen))

    def rectangle(self, x, y, w, h):
        self.calls.append(("rect", x, y, w, h, self._pen))

    def triangle(self, x1, y1, x2, y2, x3, y3):
        self.calls.append(("tri", x1, y1, x2, y2, x3, y3, self._pen))

    def _resolve(self, scale):
        """Tier -> (font, effective scale). Untiered sizes keep their number."""
        return self.binding.get(scale, (self.binding[3][0], scale))

    def text(self, s, x, y, wrap=0, scale=1):
        # wrap is recorded because the REAL PicoGraphics wraps words at the
        # wrap width (wrap=0 stacks every word vertically!) — lint checks it.
        # The font and effective scale are appended so a previewer can draw
        # the right glyphs; every existing consumer indexes positionally and
        # is unaffected.
        font, eff = self._resolve(scale)
        self.calls.append(("text", s, x, y, eff, self._pen, wrap, font))

    def measure_text(self, s, scale=1):
        font, eff = self._resolve(scale)
        if font == "font8":
            return measure_bitmap8(s, eff)
        from tools import hostfont
        return hostfont.measure(s, eff, font)

    def set_font(self, name):
        self.calls.append(("font", name))


class FakeHardware:
    WIDTH = 480
    HEIGHT = 480

    def __init__(self):
        self.display = FakeDisplay()
        self.tx = 0
        self.ty = 0
        self.touched = False
        self.clicked = False
        self.click_x = 0
        self.click_y = 0
        self.leds = [(0, 0, 0)] * 7

    def queue_tap(self, x, y):
        self.click_x, self.click_y = x, y
        self.clicked = True

    def poll(self):
        pass

    def set_led(self, i, color):
        self.leds[i] = color

    def set_all_leds(self, color):
        self.leds = [color] * 7

    def update(self):
        pass

    def partial_update(self, x, y, w, h):
        pass
