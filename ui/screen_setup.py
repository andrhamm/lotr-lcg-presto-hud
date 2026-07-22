"""New-game setup: add up to 4 players (own starting threat, default 25).
First player is chosen inline — the ribbon marks the row; tapping a row
(outside its buttons) moves it. Single player: P1 is first, not changeable.
Warning about losing the previous game sits below Start.
"""

from gamestate import DEFAULT_START_THREAT, MAX_PLAYERS
from ui.widgets import Button, panel, text_center, text_left, stepper, ribbon
from ui import icons

ROW_H = 62
ROW_GAP = 10


class SetupScreen:
    def __init__(self):
        self.threats = [DEFAULT_START_THREAT]
        self.first = 0
        self.has_save = False  # set by main before entering; gates the warning
        self.buttons = []

    def draw(self, hw, game, pal):
        d = hw.display
        self.buttons = []
        d.set_pen(pal.bg)
        d.clear()
        text_center(d, pal, "New game", 240, 16, 3, pal.gold)
        if len(self.threats) > 1:
            text_left(d, pal, "tap a row to set the first player", 24, 52, 2, pal.dim)

        self.first = min(self.first, len(self.threats) - 1)
        row_buttons = []
        y = 84
        for i, t in enumerate(self.threats):
            panel(d, pal, 16, y, 448, ROW_H, fill=pal.card)
            text_left(d, pal, "P%d" % (i + 1), 30, y + 19, 3, pal.tan)
            if i == self.first:
                ribbon(d, pal, 16 + 448 - 26, y + 1)
            icons.draw(d, icons.THREAT, 82, y + 21, pal.red)
            stepper(d, pal, self.buttons, ("st", i, -1), ("st", i, 1),
                    108, y + 7, str(t), 210, 48)
            if len(self.threats) > 1:
                rm = Button(("rm", i), 340, y + 7, 48, 48)
                panel(d, pal, rm.x, rm.y, rm.w, rm.h, fill=pal.btn_no, border=pal.no_fg)
                text_center(d, pal, "x", rm.x + 24, rm.y + 12, 3, pal.no_fg)
                self.buttons.append(rm)
                # row tap target added after controls so controls win hit-testing
                row_buttons.append(Button(("fp", i), 16, y, 448, ROW_H))
            y += ROW_H + ROW_GAP

        if len(self.threats) < MAX_PLAYERS:
            add = Button(("add",), 16, y, 448, 50)
            panel(d, pal, add.x, add.y, add.w, add.h, fill=pal.btn)
            text_center(d, pal, "+ Add player", 240, y + 15, 2, pal.tan)
            self.buttons.append(add)

        sb = Button(("start",), 60, 388, 360, 62)
        panel(d, pal, sb.x, sb.y, sb.w, sb.h, fill=pal.btn_ok, border=pal.border_gold)
        text_center(d, pal, "Start", 240, 404, 3, pal.gold)
        self.buttons.append(sb)
        if self.has_save:
            text_center(d, pal, "starting a new game overwrites the saved one",
                        240, 458, 2, pal.no_fg)

        self.buttons.extend(row_buttons)

    def on_button(self, btn, game):
        k = btn.id[0]
        if k == "st":
            i, delta = btn.id[1], btn.id[2]
            self.threats[i] = max(0, min(60, self.threats[i] + delta))
            return "redraw"
        if k == "add":
            self.threats.append(DEFAULT_START_THREAT)
            return "redraw"
        if k == "rm":
            self.threats.pop(btn.id[1])
            if self.first >= len(self.threats):
                self.first = 0
            return "redraw"
        if k == "fp":
            self.first = btn.id[1]
            return "redraw"
        if k == "start":
            return ("start_game", list(self.threats), self.first)
        return None
