"""About / disclaimers screen, reachable from the boot screen's 'disclaimers'
link. Mirror of the web ScreenAbout (docs/js/screens_other.js)."""

from ui.header import draw_header, HEADER_H
from ui.widgets import Button, bevel, text_center, text_left
from ui import icons


class ScreenAbout:
    def __init__(self):
        self.buttons = []

    def draw(self, hw, game, pal):
        d = hw.display
        self.buttons = []
        d.set_pen(pal.bg)
        d.clear()
        draw_header(d, pal, game, self.buttons, title="About", close=True)
        y = [HEADER_H + 18]
        text_center(d, pal, "LOTR LCG HUD", 240, y[0], 3, pal.gold)
        y[0] += 42

        def para(lines, color):
            for ln in lines:
                text_center(d, pal, ln, 240, y[0], 2, color)
                y[0] += 22
            y[0] += 12

        para(["A companion tracker for the table."], pal.tan)
        para(["An unofficial fan project for",
              "The Lord of the Rings: The Card Game.",
              "Not endorsed, supported by, or affiliated",
              "with Fantasy Flight Publishing, Inc."], pal.muted)
        para(["The Lord of the Rings, its characters and",
              "game iconography are trademarks of",
              "Middle-earth Enterprises, used under",
              "license by Fantasy Flight Games."], pal.muted)

        label, handle = "made with <3 by", "@andrhamm"
        lw = d.measure_text(label, 2)
        hw_ = d.measure_text(handle, 2)
        total = lw + 8 + 20 + 6 + hw_
        x = 240 - total // 2
        by = 402
        b = Button(("repo",), x - 10, by - 12, total + 20, 44)
        bevel(d, pal, b.x, b.y, b.w, b.h, pal.card, t=2)
        text_left(d, pal, label, x, by, 2, pal.tan)
        x += lw + 8
        icons.draw(d, icons.GITHUB, x, by - 2, pal.gold)
        x += 20 + 6
        text_left(d, pal, handle, x, by, 2, pal.gold)
        self.buttons.append(b)

    def on_button(self, btn, game):
        k = btn.id[0]
        if k == "nav":
            return ("goto", btn.id[1])
        if k == "repo":
            return ("open_repo",)
        return None
