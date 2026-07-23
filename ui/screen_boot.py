"""Boot screen: full-bleed pixelated box art + two buttons — Resume Game
(when a save exists) and New Game. No header, no extra chrome.
Falls back to a plain layout when the art/decoder is unavailable (host tests).
"""

from ui.widgets import Button, panel, bevel, text_center, text_left


class BootScreen:
    def __init__(self, saved_meta):
        # saved_meta: None or {"round": int, "phase": str, "saved_at": str}
        self.saved = saved_meta
        self.buttons = []

    def _draw_art(self, hw):
        try:
            import pngdec
            png = pngdec.PNG(hw.display)
            png.open_file("boot_bg.png")
            png.decode(0, 0)
            return True
        except Exception:
            return False

    def _button(self, d, pal, id, label, sub, y, h, primary):
        b = Button(id, 100, y, 280, h)
        bevel(d, pal, b.x, b.y, b.w, b.h,
              pal.btn_ok if primary else pal.btn, t=3)
        ty = b.y + (h - (26 if sub else 16)) // 2
        text_center(d, pal, label, 240, ty, 2, pal.gold if primary else pal.tan)
        if sub:
            text_center(d, pal, sub, 240, ty + 20, 1, pal.muted)
        self.buttons.append(b)

    def draw(self, hw, game, pal):
        d = hw.display
        self.buttons = []
        art = self._draw_art(hw)
        if not art:
            d.set_pen(pal.bg)
            d.clear()
            text_center(d, pal, "LOTR LCG", 240, 120, 4, pal.gold)
            text_center(d, pal, "THE CARD GAME", 240, 170, 2, pal.tan)

        if self.saved:
            sub = "R%d - %s (%s)" % (self.saved["round"], self.saved["phase"],
                                     self.saved["saved_at"])
            self._button(d, pal, ("resume",), "Resume Game", sub, 336, 58, True)
            self._button(d, pal, ("new",), "New Game", None, 402, 48, False)
        else:
            self._button(d, pal, ("new",), "New Game", None, 388, 58, True)

        # bottom "disclaimers" link -> About (dropshadow for legibility over art)
        dw = d.measure_text("disclaimers", 2)
        dx = 240 - dw // 2
        for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1), (1, 1)):
            text_left(d, pal, "disclaimers", dx + ox, 462 + oy, 2, pal.tan, shadow=False)
        text_left(d, pal, "disclaimers", dx, 462, 2, pal.outline, shadow=False)
        self.buttons.append(Button(("about",), dx - 12, 450, dw + 24, 30))

    def on_button(self, btn, game):
        return ("boot", btn.id[0])  # handled by main
