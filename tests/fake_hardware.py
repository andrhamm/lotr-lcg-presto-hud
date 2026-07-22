"""Host-side stand-in for hardware.Hardware and the PicoGraphics display.

Records draw calls and lets tests simulate taps, so screen layout / hit-testing
logic can be exercised under CPython without a device.

measure_text implements the REAL bitmap8 metric, captured from the device:
per-glyph widths plus 1px inter-character spacing, all scaled linearly
(verified: measure("AB",1)=9=4+4+1; measure(s,2)=2*measure(s,1)).
"""

# Glyph widths at scale 1, probed on the Presto (PicoGraphics bitmap8).
BITMAP8_W = {
    'a': 4, 'b': 4, 'c': 4, 'd': 4, 'e': 4, 'f': 4, 'g': 4, 'h': 4, 'i': 3,
    'j': 4, 'k': 4, 'l': 3, 'm': 5, 'n': 4, 'o': 4, 'p': 4, 'q': 4, 'r': 4,
    's': 4, 't': 4, 'u': 4, 'v': 4, 'w': 5, 'x': 4, 'y': 4, 'z': 4,
    'A': 4, 'B': 4, 'C': 4, 'D': 4, 'E': 4, 'F': 4, 'G': 4, 'H': 4, 'I': 3,
    'J': 4, 'K': 4, 'L': 4, 'M': 5, 'N': 4, 'O': 4, 'P': 4, 'Q': 4, 'R': 4,
    'S': 4, 'T': 5, 'U': 4, 'V': 4, 'W': 5, 'X': 4, 'Y': 4, 'Z': 4,
    '0': 4, '1': 3, '2': 4, '3': 4, '4': 4, '5': 4, '6': 4, '7': 4, '8': 4,
    '9': 4, ' ': 3, '.': 2, ',': 2, ':': 1, ';': 2, '!': 1, '?': 4, '(': 3,
    ')': 3, '+': 3, '-': 3, '/': 4, '*': 3, '<': 3, '>': 3, '=': 3, '%': 4,
    '&': 4, "'": 1, '"': 3,
}


def measure_bitmap8(s, scale=1):
    s = str(s)
    if not s:
        return 0
    w = sum(BITMAP8_W.get(c, 4) for c in s) + (len(s) - 1)
    return w * scale


class FakeDisplay:
    def __init__(self, w=480, h=480):
        self.w = w
        self.h = h
        self._pen = 0
        self.calls = []

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

    def text(self, s, x, y, wrap=0, scale=1):
        # wrap is recorded because the REAL PicoGraphics wraps words at the
        # wrap width (wrap=0 stacks every word vertically!) — lint checks it.
        self.calls.append(("text", s, x, y, scale, self._pen, wrap))

    def measure_text(self, s, scale=1):
        return measure_bitmap8(s, scale)

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
