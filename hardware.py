"""Thin wrapper over the Presto board — the ONLY module that imports `presto`.

Confirmed against firmware MicroPython 1.26.0 / Presto full_res:
  - Presto(full_res=True) -> 480x480, display is a PicoGraphics instance
  - presto.touch_poll(); presto.touch_a has .x .y .touched
  - presto.set_led_rgb(i, r, g, b), presto.auto_ambient_leds(False)
  - presto.update(), presto.partial_update(x, y, w, h)
Host tests use tests/fake_hardware.py instead of this module.
"""

from presto import Presto

WIDTH = 480
HEIGHT = 480


class Hardware:
    def __init__(self):
        self.presto = Presto(full_res=True)
        self.display = self.presto.display
        # Pin the font: all host-side metrics (lint, previews) model bitmap8.
        self.display.set_font("bitmap8")
        self.presto.auto_ambient_leds(False)
        self.tx = 0
        self.ty = 0
        self.touched = False
        # tap = press-then-release; these hold the just-released location
        self.clicked = False
        self.click_x = 0
        self.click_y = 0
        self._press_x = 0
        self._press_y = 0

    def poll(self):
        """Update touch state. Sets self.clicked True for one poll on release."""
        self.presto.touch_poll()
        t = self.presto.touch_a
        now = bool(t.touched)
        self.clicked = False
        if now and not self.touched:            # rising edge — press
            self._press_x, self._press_y = t.x, t.y
        elif not now and self.touched:          # falling edge — release => tap
            self.clicked = True
            self.click_x, self.click_y = self._press_x, self._press_y
        if now:
            self.tx, self.ty = t.x, t.y
        self.touched = now

    def set_led(self, i, color):
        self.presto.set_led_rgb(i, color[0], color[1], color[2])

    def set_all_leds(self, color):
        for i in range(7):
            self.set_led(i, color)

    def update(self):
        self.presto.update()

    def partial_update(self, x, y, w, h):
        self.presto.partial_update(x, y, w, h)
