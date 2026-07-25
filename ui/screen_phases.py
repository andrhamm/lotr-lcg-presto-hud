"""Phases screen — vertical turn-sequence flowchart. The current phase expands
to its numbered steps; lightning mark = action window. Tap a step to jump.
Reached by tapping the phase name in the header; Back returns to Play.
"""

import phases
from ui.header import draw_header, HEADER_H
from ui.theme import DISPLAY, BODY, LABEL
from ui.widgets import Button, panel, text_center, text_left, wrap_text


class ScreenPhases:
    # Step rows are two columns: the rulebook step number ("3.2", "6.7-6.10")
    # is tabular chrome and keeps LABEL, the description beside it is prose and
    # reads at BODY. STEP_ROW_H is 24 (was 26 with LABEL text) so the taller
    # rows still clear the pinned footnotes - the worst case is a 5-step phase
    # (Quest, Combat), which now bottoms out at 410 against FOOT_Y 416.
    STEP_ROW_H = 24
    FOOT_Y = 416

    # Same claim as before, reflowed to two lines at BODY. Wording matches
    # README.md's own summary of the combat loop ("every enemy attacks, then
    # every player attacks, in turn order"); "in turn order" already names the
    # first player, who defines it.
    COMBAT_NOTE = ("Combat loops in turn order: every enemy attacks, "
                   "then every player attacks.")

    def __init__(self):
        self.buttons = []

    def draw(self, hw, game, pal):
        d = hw.display
        self.buttons = []
        d.set_pen(pal.bg)
        d.clear()
        draw_header(d, pal, game, self.buttons, title="Game Phases", close=True)

        cur_phase = phases.step(game.step)["phase"]
        y = HEADER_H + 8
        for ph in phases.PHASES:
            if ph["id"] in ("Beginning", "End"):
                continue
            is_cur = ph["id"] == cur_phase
            if not is_cur:
                panel(d, pal, 12, y, 456, 30, fill=pal.card)
                text_left(d, pal, ph["label"], 24, y + 8, BODY, pal.dim)
                self.buttons.append(Button(("jump", ph["id"]), 12, y, 456, 30))
                y += 34
            else:
                steps = [s for s in phases.STEPS if s["phase"] == ph["id"]]
                box_h = 34 + len(steps) * self.STEP_ROW_H
                panel(d, pal, 12, y, 456, box_h, fill=pal.card_hi, border=pal.border_gold)
                text_left(d, pal, ph["label"], 24, y + 8, BODY, pal.gold)
                sy = y + 32
                for s in steps:
                    active = s["id"] == game.step
                    if active:
                        d.set_pen(pal.gold)
                        d.rectangle(20, sy - 2, 440, self.STEP_ROW_H)
                    pen = pal.bg if active else pal.tan
                    if s["action_window"]:
                        # purple marker = a player action window opens here
                        d.set_pen(pal.bg if active else pal.purple)
                        d.rectangle(28, sy + 6, 8, 8)
                    num, _, desc = s["label"].partition(" ")
                    if s["id"] in ("6.E", "6.P"):
                        desc += "  (loops: each player)"
                    text_left(d, pal, num, 42, sy + 6, LABEL, pen)
                    text_left(d, pal, desc, 82, sy + 2, BODY, pen)
                    self.buttons.append(
                        Button(("step", s["id"]), 20, sy - 2, 440, self.STEP_ROW_H))
                    sy += self.STEP_ROW_H
                y += box_h + 4

        d.set_pen(pal.purple)
        d.rectangle(12, self.FOOT_Y + 4, 8, 8)
        text_left(d, pal, "= action window   tap a step to jump", 26, self.FOOT_Y,
                  BODY, pal.dim)
        fy = self.FOOT_Y + 22
        for ln in wrap_text(self.COMBAT_NOTE, BODY, 456, d.measure_text):
            text_left(d, pal, ln, 12, fy, BODY, pal.dim)
            fy += 21

    def on_button(self, btn, game):
        from gamestate import view_for_step
        k = btn.id[0]
        if k == "nav":
            return ("goto", btn.id[1])
        if k == "jump":
            # jump to the first step of that phase
            for s in phases.STEPS:
                if s["phase"] == btn.id[1]:
                    game.step = s["id"]
                    break
            game.view = view_for_step(game.step)
            return True
        if k == "step":
            game.step = btn.id[1]
            game.view = view_for_step(game.step)
            return True
        return None
