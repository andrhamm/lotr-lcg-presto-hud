"""Phases screen — vertical turn-sequence flowchart. The current phase expands
to its numbered steps; lightning mark = action window. Tap a step to jump.
Reached by tapping the phase name in the header; Back returns to Play.
"""

import phases
from ui.header import draw_header, HEADER_H
from ui.widgets import Button, panel, text_center, text_left


class ScreenPhases:
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
                text_left(d, pal, ph["label"], 24, y + 8, 2, pal.dim)
                self.buttons.append(Button(("jump", ph["id"]), 12, y, 456, 30))
                y += 34
            else:
                steps = [s for s in phases.STEPS if s["phase"] == ph["id"]]
                box_h = 34 + len(steps) * 26
                panel(d, pal, 12, y, 456, box_h, fill=pal.card_hi, border=pal.border_gold)
                text_left(d, pal, ph["label"], 24, y + 8, 2, pal.gold)
                sy = y + 32
                for s in steps:
                    active = s["id"] == game.step
                    if active:
                        d.set_pen(pal.gold)
                        d.rectangle(20, sy - 2, 440, 24)
                    pen = pal.bg if active else pal.tan
                    if s["action_window"]:
                        # purple marker = a player action window opens here
                        d.set_pen(pal.bg if active else pal.purple)
                        d.rectangle(28, sy + 3, 8, 8)
                    label = s["label"]
                    if s["id"] in ("6.E", "6.P"):
                        label += "  (loops: each player)"
                    text_left(d, pal, label, 42, sy + 2, 1, pen)
                    self.buttons.append(Button(("step", s["id"]), 20, sy - 2, 440, 24))
                    sy += 26
                y += box_h + 4

        d.set_pen(pal.purple)
        d.rectangle(12, 436, 8, 8)
        text_left(d, pal, "= action window   tap a step to jump", 26, 434, 1, pal.dim)
        text_left(d, pal, "Combat loops in turn order: every enemy attacks, then", 12, 450, 1, pal.dim)
        text_left(d, pal, "every player attacks - first player resolves first.", 12, 464, 1, pal.dim)

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
