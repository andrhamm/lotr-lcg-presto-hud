"""Help: how the HUD works + the conventions legend.

Reached from Settings -> Help. It is NOT shown automatically at boot - the
boot menu is the first thing you see. Mirror of the web classes in
docs/js/screens_other.js - keep the two in lockstep.
"""

from ui.header import draw_header, HEADER_H
from ui.theme import DISPLAY, BODY, LABEL
from ui.widgets import Button, bevel, disc, text_center, text_left, token
from ui import icons

PAGES = 3


def draw_legend_rows(d, pal, y):
    """The conventions legend, shared by first-run page 3 and LegendScreen.
    Each row is a real sample of the thing it explains - drawn with the same
    primitives the live screens use - so the legend cannot drift from the UI.
    Returns the y below the last row."""
    x_icon, x_text = 30, 76

    icons.draw(d, icons.THREAT, x_icon - 10, y - 10, pal.bevel_d)
    icons.draw(d, icons.THREAT, x_icon - 11, y - 11, pal.red)
    text_left(d, pal, "your threat - enemies engage at/below it", x_text, y - 8, BODY, pal.tan)
    y += 34

    icons.draw(d, icons.THREAT, x_icon - 11, y - 11, pal.outline)
    text_left(d, pal, "staging threat - what questing must beat", x_text, y - 8, BODY, pal.tan)
    y += 34

    icons.draw(d, icons.WILLPOWER, x_icon - 11, y - 11, pal.gold)
    text_left(d, pal, "willpower committed to the quest", x_text, y - 8, BODY, pal.tan)
    y += 34

    token(d, pal, x_icon, y, 13, 2, 4, pal.value, 0.55, pal.gold, pal.dim)
    text_left(d, pal, "ring = progress; number = points left", x_text, y - 8, BODY, pal.tan)
    y += 34

    token(d, pal, x_icon, y, 13, 2, 41, pal.value, 0.9, pal.red, pal.dim)
    text_left(d, pal, "red ring = close to elimination", x_text, y - 8, BODY, pal.tan)
    y += 34

    d.set_pen(pal.red)
    d.rectangle(x_icon - 12, y - 10, 4, 20)
    d.set_pen(pal.green)
    d.rectangle(x_icon + 2, y - 10, 4, 20)
    text_left(d, pal, "red = happens anyway; green = your window", x_text, y - 8, BODY, pal.tan)
    return y + 30


class LegendScreen:
    """Standalone conventions legend (Settings -> How to read this HUD)."""

    def __init__(self):
        self.buttons = []

    def draw(self, hw, game, pal):
        d = hw.display
        self.buttons = []
        d.set_pen(pal.bg)
        d.clear()
        draw_header(d, pal, game, self.buttons, title="How to read this HUD",
                    close=True)
        draw_legend_rows(d, pal, HEADER_H + 34)

    def on_button(self, btn, game=None):
        if btn.id[0] in ("close", "nav"):
            return ("goto", "close")
        return None


class FirstRunScreen:
    """Three-page help: what the HUD is, how a round flows, and the legend.
    Opened from Settings -> Help; never shown automatically."""

    def __init__(self):
        self.page = 0
        self.buttons = []

    def _body(self, d, pal):
        y = HEADER_H + 40
        if self.page == 0:
            text_center(d, pal, "A companion, not a rules engine", 240, y, BODY, pal.gold)
            y += 40
            for ln in ["This tracks threat, progress and the",
                       "turn sequence for you.",
                       "",
                       "It never touches your cards - you still",
                       "play the game on the table."]:
                text_center(d, pal, ln, 240, y, BODY, pal.tan)
                y += 26
        elif self.page == 1:
            text_center(d, pal, "One screen per phase", 240, y, BODY, pal.gold)
            y += 40
            for ln in ["Pick a quest, then follow the round.",
                       "",
                       "The big button at the bottom always",
                       "moves you forward.",
                       "",
                       "Tap the stats up top to edit them."]:
                text_center(d, pal, ln, 240, y, BODY, pal.tan)
                y += 26
        else:
            text_center(d, pal, "What the marks mean", 240, y, BODY, pal.gold)
            draw_legend_rows(d, pal, y + 36)

    def draw(self, hw, game, pal):
        d = hw.display
        self.buttons = []
        d.set_pen(pal.bg)
        d.clear()
        draw_header(d, pal, game, self.buttons, title="Help", close=True)
        self._body(d, pal)

        if self.page > 0:
            b = Button(("fr_back",), 12, 412, 140, 52)
            bevel(d, pal, b.x, b.y, b.w, b.h, pal.btn)
            text_center(d, pal, "Back", b.x + 70, b.y + 16, BODY, pal.tan)
            self.buttons.append(b)
        for i in range(PAGES):
            cx = 240 + (i - 1) * 18
            disc(d, cx, 438, 5, pal.gold if i == self.page else pal.dim)
        last = self.page == PAGES - 1
        b = Button(("fr_done",) if last else ("fr_next",), 328, 412, 140, 52)
        bevel(d, pal, b.x, b.y, b.w, b.h, pal.btn_ok)
        text_center(d, pal, "Done" if last else "Next", b.x + 70, b.y + 16, BODY, pal.ok_fg)
        self.buttons.append(b)

    def on_button(self, btn, game=None):
        k = btn.id[0]
        if k == "fr_next":
            self.page = min(PAGES - 1, self.page + 1)
            return "redraw"
        if k == "fr_back":
            self.page = max(0, self.page - 1)
            return "redraw"
        if k in ("fr_done", "close", "nav"):
            self.page = 0          # reopen at the start next time
            return ("goto", "close")   # pops the nav trail -> back to Settings
        return None
