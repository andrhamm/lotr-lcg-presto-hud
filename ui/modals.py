"""Full-screen config + allocation modals.

Each modal mutates the passed GameState directly on confirm. Protocol:
  draw(hw, game, pal)  -> renders, rebuilds self.buttons
  on_button(btn)       -> "close" (save+dismiss), "cancel" (dismiss), or None
"""

import random

from ui.widgets import (Button, panel, bevel, text_center, text_left, button,
                        stepper, draw_weather, token, circ_btn, disc, arc_runs,
                        ring, wx_small, wrap_text, truncate_text)
from ui.counter import CounterState
from ui import icons
from gamestate import HEADINGS
from quest_catalog import tips_for

CANCEL_Y = 404
BTN_H = 64


def _footer(d, pal, buttons, save_label="Save"):
    no = Button(("cancel",), 24, CANCEL_Y, 200, BTN_H)
    ok = Button(("save",), 256, CANCEL_Y, 200, BTN_H)
    bevel(d, pal, no.x, no.y, no.w, no.h, pal.btn_no, t=3)
    text_center(d, pal, "Cancel", no.x + no.w / 2, no.y + 20, 2, pal.no_fg)
    bevel(d, pal, ok.x, ok.y, ok.w, ok.h, pal.btn_ok, t=3)
    text_center(d, pal, save_label, ok.x + ok.w / 2, ok.y + 20, 2, pal.ok_fg)
    buttons.append(no)
    buttons.append(ok)


class PlayerSettingsModal:
    def __init__(self, game, index):
        self.game = game
        self.i = index
        p = game.players[index]
        self.st = p.starting_threat
        self.tpr = p.threat_per_round
        self.elim = p.elimination
        self.buttons = []

    def draw(self, hw, game, pal):
        d = hw.display
        self.buttons = []
        d.set_pen(pal.bg)
        d.clear()
        text_center(d, pal, "P%d settings" % (self.i + 1), 240, 24, 3, pal.gold)

        icons.draw(d, icons.THREAT, 30, 92, pal.red)
        text_left(d, pal, "Starting threat", 58, 96, 2, pal.tan)
        stepper(d, pal, self.buttons, ("st", -1), ("st", 1), 260, 82, str(self.st), 190, 56)

        icons.draw(d, icons.THREAT, 30, 172, pal.red)
        text_left(d, pal, "Threat / round", 58, 176, 2, pal.tan)
        stepper(d, pal, self.buttons, ("tpr", -1), ("tpr", 1), 260, 162, str(self.tpr), 190, 56)

        icons.draw(d, icons.THREAT, 30, 252, pal.red)
        text_left(d, pal, "Elimination level", 58, 256, 2, pal.tan)
        stepper(d, pal, self.buttons, ("el", -1), ("el", 1), 260, 242, str(self.elim), 190, 56)
        text_left(d, pal, "eliminated when threat reaches this (50 std)", 30, 306, 1, pal.dim)

        _footer(d, pal, self.buttons)

    def on_button(self, btn):
        k = btn.id[0]
        if k == "st":
            self.st = max(0, min(60, self.st + btn.id[1]))
            return None
        if k == "tpr":
            self.tpr = max(0, min(9, self.tpr + btn.id[1]))
            return None
        if k == "el":
            self.elim = max(20, min(99, self.elim + btn.id[1]))
            return None
        if k == "save":
            p = self.game.players[self.i]
            p.starting_threat = self.st
            p.threat_per_round = self.tpr
            p.elimination = self.elim
            # re-evaluate elimination against the new level
            self.game.adjust_threat(self.i, 0)
            self.game.log_event("P%d settings: start %d, +%d/round, elim %d"
                                % (self.i + 1, self.st, self.tpr, self.elim))
            return "close"
        if k == "cancel":
            return "cancel"
        return None


class QuestConfigModal:
    def __init__(self, game):
        self.game = game
        self.q = dict(game.quest)
        self.sail = game.sailing
        self.buttons = []

    def draw(self, hw, game, pal):
        d = hw.display
        self.buttons = []
        d.set_pen(pal.bg)
        d.clear()
        text_center(d, pal, "Quest  %d%s" % (self.q["stage_n"], self.q["side"]),
                    240, 24, 3, pal.gold)

        text_left(d, pal, "Stage number", 30, 84, 2, pal.tan)
        stepper(d, pal, self.buttons, ("n", -1), ("n", 1), 300, 70, str(self.q["stage_n"]), 150, 52)

        # side cycles A-H (multi-variant quests go beyond A/B - DragnCards data)
        text_left(d, pal, "Side", 30, 156, 2, pal.tan)
        stepper(d, pal, self.buttons, ("side", -1), ("side", 1), 300, 142, self.q["side"], 150, 52)

        text_left(d, pal, "Quest points", 30, 228, 2, pal.tan)
        stepper(d, pal, self.buttons, ("pts", -1), ("pts", 1), 300, 214, str(self.q["points"]), 150, 52)

        text_left(d, pal, "Sailing quest", 30, 296, 2, pal.tan)
        icons.draw(d, icons.WHEEL, 176, 292, pal.gold if self.sail else pal.dim)
        sb = Button(("sail",), 300, 284, 150, 48)
        panel(d, pal, sb.x, sb.y, sb.w, sb.h, fill=pal.gold if self.sail else pal.btn)
        text_center(d, pal, "On" if self.sail else "Off", sb.x + 75, sb.y + 14, 2,
                    pal.bg if self.sail else pal.tan, shadow=False)
        self.buttons.append(sb)

        adv = Button(("adv",), 30, 344, 420, 48)
        bevel(d, pal, adv.x, adv.y, adv.w, adv.h, pal.btn)
        text_center(d, pal, "Advance stage (progress -> 0)", adv.x + adv.w / 2, adv.y + 14, 2, pal.tan)
        self.buttons.append(adv)

        _footer(d, pal, self.buttons)

    def on_button(self, btn):
        k = btn.id[0]
        if k == "n":
            self.q["stage_n"] = max(1, min(9, self.q["stage_n"] + btn.id[1]))
            return None
        if k == "side":
            i = (ord(self.q["side"][0]) - 65 + btn.id[1] + 8) % 8   # cycle A-H
            self.q["side"] = chr(65 + i)
            return None
        if k == "pts":
            self.q["points"] = max(0, min(30, self.q["points"] + btn.id[1]))
            return None
        if k == "adv":
            if self.q["side"] == "A":
                self.q["side"] = "B"
            else:
                self.q["side"] = "A"
                self.q["stage_n"] += 1
            self.q["progress"] = 0
            return None
        if k == "sail":
            self.sail = not self.sail
            return None
        if k == "save":
            self.game.quest = self.q
            if self.sail != self.game.sailing:
                self.game.sailing = self.sail
                self.game.log_event(
                    "Sailing enabled (Dream-chaser) - heading starts On-course"
                    if self.sail else "Sailing disabled")
                if self.sail:
                    self.game.heading = 0
            return "close"
        if k == "cancel":
            return "cancel"
        return None


class LocationConfigModal:
    def __init__(self, game):
        self.game = game
        loc = game.active_location
        self.has = loc is not None
        self.pts = loc["points"] if loc else 2
        self.prog = loc["progress"] if loc else 0
        self.buttons = []

    def draw(self, hw, game, pal):
        d = hw.display
        self.buttons = []
        d.set_pen(pal.bg)
        d.clear()
        text_center(d, pal, "Active Location", 240, 24, 3, pal.gold)
        state = "%d / %d" % (self.prog, self.pts) if self.has else "none"
        text_center(d, pal, state, 240, 80, 3, pal.tan if self.has else pal.dim)

        text_left(d, pal, "Quest points", 30, 168, 2, pal.tan)
        stepper(d, pal, self.buttons, ("pts", -1), ("pts", 1), 260, 154, str(self.pts), 190, 56)

        none_b = Button(("none",), 30, 250, 420, 56)
        panel(d, pal, none_b.x, none_b.y, none_b.w, none_b.h, fill=pal.btn_no, border=pal.no_fg)
        text_center(d, pal, "Set none (no active location)", none_b.x + none_b.w / 2,
                    none_b.y + 18, 2, pal.no_fg)
        self.buttons.append(none_b)

        _footer(d, pal, self.buttons)

    def on_button(self, btn):
        k = btn.id[0]
        if k == "pts":
            self.pts = max(1, min(30, self.pts + btn.id[1]))
            self.has = True
            return None
        if k == "none":
            self.game.active_location = None
            return "close"
        if k == "save":
            self.game.active_location = {"points": self.pts, "progress": self.prog}
            return "close"
        if k == "cancel":
            return "cancel"
        return None


class SideQuestsModal:
    def __init__(self, game):
        self.game = game
        self.buttons = []

    def draw(self, hw, game, pal):
        d = hw.display
        self.buttons = []
        d.set_pen(pal.bg)
        d.clear()
        text_center(d, pal, "Side quests", 240, 22, 3, pal.gold)
        sq = self.game.side_quests
        if not sq:
            text_center(d, pal, "none", 240, 90, 3, pal.dim)
        y = 70
        for i, s in enumerate(sq):
            panel(d, pal, 24, y, 432, 56, fill=pal.card)
            text_left(d, pal, "SQ%d  %d/%d" % (i + 1, s["progress"], s["points"]), 36, y + 18, 2, pal.tan)
            mn = Button(("pts", i, -1), 250, y + 6, 44, 44)
            pl = Button(("pts", i, 1), 302, y + 6, 44, 44)
            rm = Button(("rm", i), 400, y + 6, 44, 44)
            button(d, pal, mn, "-", 3)
            button(d, pal, pl, "+", 3)
            panel(d, pal, rm.x, rm.y, rm.w, rm.h, fill=pal.btn_no, border=pal.no_fg)
            text_center(d, pal, "x", rm.x + rm.w / 2, rm.y + 10, 3, pal.no_fg)
            self.buttons.extend([mn, pl, rm])
            y += 62

        add = Button(("add",), 24, min(y, 320), 432, 52)
        panel(d, pal, add.x, add.y, add.w, add.h, fill=pal.btn)
        text_center(d, pal, "+ Add side quest", add.x + add.w / 2, add.y + 16, 2, pal.tan)
        self.buttons.append(add)

        done = Button(("save",), 24, CANCEL_Y, 432, BTN_H)
        panel(d, pal, done.x, done.y, done.w, done.h, fill=pal.btn_ok, border=pal.ok_fg)
        text_center(d, pal, "Done", done.x + done.w / 2, done.y + 20, 2, pal.ok_fg)
        self.buttons.append(done)

    def on_button(self, btn):
        k = btn.id[0]
        if k == "add":
            self.game.side_quests.append({"points": 4, "progress": 0})
            return None
        if k == "pts":
            i = btn.id[1]
            self.game.side_quests[i]["points"] = max(1, min(30, self.game.side_quests[i]["points"] + btn.id[2]))
            return None
        if k == "rm":
            self.game.side_quests.pop(btn.id[1])
            return None
        if k == "save":
            return "close"
        return None


class PlayersDetailModal:
    """Every player's threat + willpower in one inline grid (Task 9) - the
    unified target for the play screen's Players zone and the "Questing for"
    card (replaces the QuestingProgressModal/QuestingForModal stubs there).
    Edits are live: every tap commits immediately to the game + logs (no
    save/cancel step). Tapping a token opens a small inline +-5 pad (nested
    modals aren't supported - the main loop only holds one `modal` at a time)
    that replaces the grid until OK/back, modeled on CounterModal."""

    STEPS = ((-5, "-5"), (-1, "-1"), (1, "+1"), (5, "+5"))

    def __init__(self, game):
        self.game = game
        self.buttons = []
        self.edit = None   # (i, stat, CounterState) while the inline pad is open

    def _open_edit(self, i, stat):
        game = self.game
        cur = game.players[i].threat if stat == "threat" else game.players[i].commit
        if stat == "willpower":
            game.touch_commit(i)
        # CounterState's default max (99) is a cosmetic pad ceiling, not a
        # game rule - adjust_threat/set_commit have no upper bound. Widen it
        # so opening the pad on an already-high value (e.g. a spammed-past-99
        # threat) can never silently clamp the preview down on an untouched
        # OK tap.
        self.edit = (i, stat, CounterState(cur, 0, max(9999, cur)))

    def _commit_edit(self):
        i, stat, state = self.edit
        before = state.value
        state.confirm()
        after = state.value
        if after != before:
            game = self.game
            if stat == "threat":
                game.adjust_threat(i, after - before)
                game.log_event("P%d threat %d -> %d" % (i + 1, before, game.players[i].threat))
            else:
                game.set_commit(i, after)
                game.log_event("P%d committed %d willpower" % (i + 1, after))
        self.edit = None

    def _editor_row(self, d, pal, i, key, cx, cy, value, frac, ring_fill):
        circ_btn(d, pal, cx - 30, cy, 11, "-")
        circ_btn(d, pal, cx + 30, cy, 11, "+")
        token(d, pal, cx, cy, 14, 2, value, pal.value, frac, ring_fill, pal.dim)
        self.buttons.append(Button((key, i, -1), cx - 30 - 12, cy - 12, 24, 24))
        self.buttons.append(Button((key, i, "edit"), cx - 12, cy - 12, 24, 24))
        self.buttons.append(Button((key, i, 1), cx + 30 - 12, cy - 12, 24, 24))

    def draw(self, hw, game, pal):
        d = hw.display
        self.buttons = []
        d.set_pen(pal.bg)
        d.clear()
        if self.edit:
            self._draw_edit(d, pal)
            return
        from ui.header import modal_header
        modal_header(d, pal, game, "Players", self.buttons)
        threat_x, will_x, label_x = 150, 330, 32
        text_center(d, pal, "Threat", threat_x, 46, 1, pal.dim)
        text_center(d, pal, "Willpower", will_x, 46, 1, pal.dim)
        for i, p in enumerate(game.players):
            cy = 66 + i * 56
            label = "P%d" % (i + 1)
            if i == game.first_player:
                d.set_pen(pal.gold)
                d.rectangle(label_x - 18, cy - 11, 36, 22)
                text_center(d, pal, label, label_x, cy - 8, 2, pal.bg, shadow=False)
            else:
                text_center(d, pal, label, label_x, cy - 8, 2, pal.tan)
            danger = p.threat >= p.elimination - 10
            tfrac = p.threat / p.elimination if p.elimination > 0 else 0
            self._editor_row(d, pal, i, "t", threat_x, cy, p.threat, tfrac,
                             pal.red if danger else pal.gold)
            self._editor_row(d, pal, i, "w", will_x, cy, p.commit, 1.0, pal.gold)

    def _draw_edit(self, d, pal):
        i, stat, state = self.edit
        is_threat = stat == "threat"
        title = "P%d %s" % (i + 1, "Threat" if is_threat else "Willpower")
        mask = icons.THREAT if is_threat else icons.WILLPOWER
        pen = pal.red if is_threat else pal.gold
        w = d.measure_text(title, 3)
        ix = int(240 - w / 2 - 30)
        icons.draw(d, mask, ix, 30, pen)
        text_center(d, pal, title, 240 + 12, 28, 3, pal.gold)

        val = state.preview
        text_center(d, pal, str(val), 240, 90, 9, pal.gold)
        if state.pending:
            dlt = state.delta
            text_center(d, pal, "%d  ->  %d" % (state.value, val), 240, 190, 2, pal.muted)
            text_center(d, pal, "%s%d" % ("+" if dlt >= 0 else "", dlt), 240, 216, 3,
                        pal.green if dlt >= 0 else pal.red)

        bw, bh, gap = 104, 76, 8
        x0 = (480 - (4 * bw + 3 * gap)) // 2
        for k, (step, label) in enumerate(self.STEPS):
            b = Button(("step", step), x0 + k * (bw + gap), 250, bw, bh)
            bevel(d, pal, b.x, b.y, b.w, b.h, pal.btn, t=3)
            text_center(d, pal, label, b.x + b.w / 2, b.y + 26, 3, pal.tan)
            self.buttons.append(b)

        no = Button(("back",), 24, 360, 200, 92)
        ok = Button(("ok",), 256, 360, 200, 92)
        bevel(d, pal, no.x, no.y, no.w, no.h, pal.btn_no, t=3)
        text_center(d, pal, "X", no.x + no.w / 2, no.y + 28, 4, pal.no_fg)
        bevel(d, pal, ok.x, ok.y, ok.w, ok.h, pal.btn_ok, t=3)
        text_center(d, pal, "OK", ok.x + ok.w / 2, ok.y + 28, 4, pal.ok_fg)
        self.buttons.append(no)
        self.buttons.append(ok)

    def on_button(self, btn):
        k = btn.id[0]
        if self.edit:
            if k == "step":
                self.edit[2].tap(btn.id[1])
                return None
            if k == "ok":
                self._commit_edit()
                return None
            if k == "back":
                self.edit = None
                return None
            return None
        if k == "close":
            return "close"
        if k in ("t", "w"):
            i, action = btn.id[1], btn.id[2]
            if action == "edit":
                self._open_edit(i, "threat" if k == "t" else "willpower")
                return None
            if k == "t":
                before = self.game.players[i].threat
                self.game.adjust_threat(i, action)
                after = self.game.players[i].threat
                if after != before:
                    self.game.log_event("P%d threat %d -> %d" % (i + 1, before, after))
            else:
                self.game.touch_commit(i)
                before = self.game.players[i].commit
                nxt = max(0, before + action)
                if nxt != before:
                    self.game.set_commit(i, nxt)
                    self.game.log_event("P%d committed %d willpower" % (i + 1, nxt))
            return None
        return None


class RemindersModal:
    """Encounter reminders — modal header (R# left, DONE right). Checkboxes
    enable a timed toast at the start of the matching phase view."""

    def __init__(self, game):
        self.game = game
        self.buttons = []

    def draw(self, hw, game, pal):
        from gamestate import REMINDER_DEFS
        from ui.header import modal_header
        d = hw.display
        self.buttons = []
        d.set_pen(pal.bg)
        d.clear()
        modal_header(d, pal, self.game, "Encounter Reminders", self.buttons)

        y = 56
        for key, label, view, _toast, _icon in REMINDER_DEFS:
            on = self.game.reminders.get(key, False)
            row = Button(("tog", key), 16, y, 448, 62)
            bevel(d, pal, row.x, row.y, row.w, row.h, pal.card_hi if on else pal.card)
            # checkbox well
            d.set_pen(pal.well if hasattr(pal, "well") else pal.bg)
            d.rectangle(30, y + 17, 28, 28)
            if on:
                d.set_pen(pal.ok_fg)
                d.rectangle(36, y + 23, 16, 16)
            text_left(d, pal, label, 76, y + 12, 2, pal.tan if on else pal.muted)
            from ui.header import VIEW_LABEL
            if key == "archery":
                part1 = "Notifies at %s if staging " % VIEW_LABEL.get(view, view)
                w1 = d.measure_text(part1, 1)
                text_left(d, pal, part1, 76, y + 38, 1, pal.dim)
                icons.draw(d, icons.THREAT_SM, 76 + w1 + 2, y + 35, pal.dim)
                text_left(d, pal, "> 0", 76 + w1 + 18, y + 38, 1, pal.dim)
            else:
                text_left(d, pal, "Notifies at %s" % VIEW_LABEL.get(view, view), 76, y + 38, 1, pal.dim)
            self.buttons.append(row)
            y += 70

    def on_button(self, btn):
        k = btn.id[0]
        if k == "tog":
            key = btn.id[1]
            self.game.reminders[key] = not self.game.reminders.get(key, False)
            return None
        if k == "close":
            return "close"
        return None


class CommitModal:
    """Per-player willpower commit, cycling through all living players from
    whichever card was tapped. Next commits and moves on; on the final player
    of the loop Done goes green and Next goes inert. Reset button (->0) zeroes.
    """

    STEPS = [("zero", "->0"), (-1, "-1"), (1, "+1"), (5, "+5")]

    def __init__(self, game, start):
        from ui.counter import CounterState
        self.game = game
        self.order = [i for i in [(start + k) % len(game.players)
                                  for k in range(len(game.players))]
                      if not game.players[i].eliminated]
        if not self.order:
            self.order = [start]
        self.pos = 0
        self.state = CounterState(game.players[self.order[0]].commit)
        self.buttons = []

    @property
    def idx(self):
        return self.order[self.pos]

    @property
    def final(self):
        return self.pos == len(self.order) - 1

    def _commit_current(self):
        v = self.state.preview if self.state.pending else self.state.value
        self.state.confirm()
        before = self.game.players[self.idx].commit
        self.game.set_commit(self.idx, v)
        if v != before:
            self.game.log_event("P%d committed %d willpower" % (self.idx + 1, v))

    def draw(self, hw, game, pal):
        from ui.counter import CounterState
        d = hw.display
        self.buttons = []
        d.set_pen(pal.bg)
        d.clear()

        text_center(d, pal, "P%d quests for..." % (self.idx + 1), 240, 28, 3, pal.gold)

        # big value + official willpower icon as a trailing currency symbol,
        # centered in the zone between the header and the step buttons
        val = self.state.preview
        VSCALE = 12                      # digit ink height = 7 rows x 12 = 84px
        ISZ = 84                         # icon matches the digit ink height
        zone_top, zone_bottom = 58, 244
        vw = d.measure_text(str(val), VSCALE)
        group_w = vw + 14 + ISZ
        vx = (480 - group_w) // 2
        vy = zone_top + (zone_bottom - zone_top - ISZ) // 2
        text_left(d, pal, str(val), vx, vy, VSCALE, pal.gold)
        icons.draw(d, icons.WILLPOWER_XL, vx + vw + 14, vy, pal.gold)

        bw, bh, gap = 104, 76, 8
        total = 4 * bw + 3 * gap
        x0 = (480 - total) // 2
        for i, (step, label) in enumerate(self.STEPS):
            b = Button(("step", step), x0 + i * (bw + gap), 250, bw, bh)
            bevel(d, pal, b.x, b.y, b.w, b.h, pal.btn, t=3)
            text_center(d, pal, label, b.x + bw / 2, b.y + 26, 3, pal.tan)
            self.buttons.append(b)

        done = Button(("done",), 24, 360, 200, 92)
        nxt = Button(("next",), 256, 360, 200, 92)
        if self.final:
            bevel(d, pal, done.x, done.y, done.w, done.h, pal.btn_ok, t=3)
            text_center(d, pal, "Done", done.x + 100, done.y + 32, 3, pal.ok_fg)
            bevel(d, pal, nxt.x, nxt.y, nxt.w, nxt.h, pal.card, t=3)
            text_center(d, pal, "Next", nxt.x + 100, nxt.y + 32, 3, pal.dim)
        else:
            bevel(d, pal, done.x, done.y, done.w, done.h, pal.card, t=3)
            text_center(d, pal, "Done", done.x + 100, done.y + 32, 3, pal.dim)
            bevel(d, pal, nxt.x, nxt.y, nxt.w, nxt.h, pal.btn, t=3)
            text_center(d, pal, "Next", nxt.x + 100, nxt.y + 32, 3, pal.gold)
        self.buttons.append(done)
        self.buttons.append(nxt)

    def on_button(self, btn):
        from ui.counter import CounterState
        k = btn.id[0]
        if k == "step":
            if btn.id[1] == "zero":
                self.state.zero()
            else:
                self.state.tap(btn.id[1])
            return None
        if k == "next":
            if self.final:
                return None  # inert on the last player
            self._commit_current()
            self.pos += 1
            self.state = CounterState(self.game.players[self.idx].commit)
            return None
        if k == "done":
            self._commit_current()
            return "close"
        return None


class LedModal:
    """LED behavior: brightness (segmented slider) + scene choice.
    Mutates the passed prefs dict in place; draw() live-previews on the LEDs.
    """

    SEGMENTS = 10

    def __init__(self, prefs, game):
        self.prefs = prefs
        self.game = game
        self.buttons = []

    def draw(self, hw, game, pal):
        import leds
        d = hw.display
        self.buttons = []
        d.set_pen(pal.bg)
        d.clear()
        text_center(d, pal, "LED behavior", 240, 22, 3, pal.gold)

        # brightness slider (10 tap segments)
        text_left(d, pal, "Brightness  %d%%" % self.prefs["brightness"], 24, 70, 2, pal.tan)
        seg_w, seg_h, x0, y0 = 42, 52, 24, 100
        lit = self.prefs["brightness"] // 10
        for i in range(self.SEGMENTS):
            x = x0 + i * (seg_w + 2)
            on = i < lit
            panel(d, pal, x, y0, seg_w, seg_h,
                  fill=pal.gold if on else pal.btn,
                  border=pal.border_gold if on else pal.border)
            self.buttons.append(Button(("bri", (i + 1) * 10), x, y0, seg_w, seg_h))

        # scenes (2x2 tiles)
        text_left(d, pal, "Scene", 24, 182, 2, pal.tan)
        half = (480 - 3 * 24) // 2
        for i, key in enumerate(leds.SCENES):
            x = 24 + (i % 2) * (half + 24)
            y = 210 + (i // 2) * 70
            on = self.prefs["scene"] == key
            b = Button(("scene", key), x, y, half, 58)
            panel(d, pal, b.x, b.y, b.w, b.h,
                  fill=pal.card_hi if on else pal.card,
                  border=pal.border_gold if on else pal.border)
            text_center(d, pal, leds.SCENE_LABELS[key], x + half / 2, y + 20, 2,
                        pal.gold if on else pal.muted)
            self.buttons.append(b)

        done = Button(("save",), 24, 396, 432, 62)
        panel(d, pal, done.x, done.y, done.w, done.h, fill=pal.btn_ok, border=pal.ok_fg)
        text_center(d, pal, "Done", 240, done.y + 20, 2, pal.ok_fg)
        self.buttons.append(done)

        # live preview
        summary = {"step": self.game.step,
                   "players": [{"threat": p.threat, "eliminated": p.eliminated}
                               for p in self.game.players]}
        leds.apply_scene(hw, self.prefs["scene"], summary,
                         self.prefs["brightness"])

    def on_button(self, btn):
        k = btn.id[0]
        if k == "bri":
            self.prefs["brightness"] = btn.id[1]
            return None
        if k == "scene":
            self.prefs["scene"] = btn.id[1]
            return None
        if k == "save":
            return "close"
        return None


class EliminationModal:
    """A player's threat reached their elimination level. Rulebook: eliminated
    immediately when threat reaches the level (50 std; Dire quests 99, some
    quests lower it). Cards like Favor of the Valar avert it instead: threat
    becomes level - 5 and the player stays in.
    """

    def __init__(self, game, index):
        self.game = game
        self.i = index
        self.new_level = game.players[index].elimination
        self.buttons = []

    def draw(self, hw, game, pal):
        d = hw.display
        self.buttons = []
        d.set_pen(pal.bg)
        d.clear()
        p = self.game.players[self.i]
        title = "P%d eliminated?" % (self.i + 1)
        tw = d.measure_text(title, 3)
        start = (480 - (20 + 8 + tw)) // 2
        icons.draw(d, icons.THREAT, start, 22, pal.red)
        text_left(d, pal, title, start + 28, 20, 3, pal.red)
        text_center(d, pal, "threat %d reached elimination level %d"
                    % (p.threat, p.elimination), 240, 62, 2, pal.tan)

        eb = Button(("elim",), 24, 110, 432, 64)
        panel(d, pal, eb.x, eb.y, eb.w, eb.h, fill=pal.btn_no, border=pal.no_fg)
        text_center(d, pal, "Yes - eliminated", 240, eb.y + 22, 2, pal.no_fg)
        self.buttons.append(eb)

        ab = Button(("avert",), 24, 190, 432, 64)
        panel(d, pal, ab.x, ab.y, ab.w, ab.h, fill=pal.btn)
        text_center(d, pal, "Averted by card effect", 240, ab.y + 12, 2, pal.tan)
        text_center(d, pal, "threat -> %d, stays in" % max(0, p.elimination - 5),
                    240, ab.y + 38, 1, pal.dim)
        self.buttons.append(ab)

        text_left(d, pal, "Elimination level changed?", 24, 286, 2, pal.tan)
        stepper(d, pal, self.buttons, ("lvl", -1), ("lvl", 1), 24, 316,
                str(self.new_level), 300, 56)
        sb = Button(("setlvl",), 340, 316, 116, 56)
        panel(d, pal, sb.x, sb.y, sb.w, sb.h, fill=pal.btn_ok, border=pal.ok_fg)
        text_center(d, pal, "Set", sb.x + 58, sb.y + 18, 2, pal.ok_fg)
        self.buttons.append(sb)

    def on_button(self, btn):
        k = btn.id[0]
        g = self.game
        p = g.players[self.i]
        if k == "elim":
            g.pending_elim = None
            g.log_event("P%d eliminated (threat %d >= level %d)"
                        % (self.i + 1, p.threat, p.elimination))
            return "close"
        if k == "avert":
            g.avert_elimination(self.i)
            return "close"
        if k == "lvl":
            self.new_level = max(20, min(99, self.new_level + btn.id[1]))
            return None
        if k == "setlvl":
            p.elimination = self.new_level
            p.eliminated = p.threat >= p.elimination
            g.pending_elim = self.i if p.eliminated else None
            g.log_event("P%d elimination level set to %d" % (self.i + 1, self.new_level))
            if p.eliminated:
                g.pending_elim = None
                g.log_event("P%d eliminated (threat %d >= level %d)"
                            % (self.i + 1, p.threat, p.elimination))
            return "close"
        return None


class LocationPickModal:
    """Travel: choose the quest points of the location traveled to.

    mode 'new'    -> travel when there is no active location
    mode 'change' -> replace the current active location (old is discarded)
    """

    def __init__(self, game, mode="new"):
        self.game = game
        self.mode = mode
        self.pts = 3
        self.contrib = 2   # its threat leaves the staging area on travel
        self.buttons = []

    def draw(self, hw, game, pal):
        d = hw.display
        self.buttons = []
        d.set_pen(pal.bg)
        d.clear()
        title = "Travel to new location" if self.mode == "new" else "Change active location"
        text_center(d, pal, title, 240, 30, 3, pal.gold)
        loc = self.game.active_location
        if self.mode == "change" and loc:
            text_center(d, pal, "current %d/%d will be discarded"
                        % (loc["progress"], loc["points"]), 240, 80, 2, pal.no_fg)

        text_left(d, pal, "Quest points", 60, 190, 2, pal.tan)
        stepper(d, pal, self.buttons, ("pts", -1), ("pts", 1), 250, 174,
                str(self.pts), 170, 60)
        icons.draw(d, icons.THREAT, 60, 262, pal.red)
        text_left(d, pal, "Contribution", 88, 266, 2, pal.tan)
        stepper(d, pal, self.buttons, ("ctr", -1), ("ctr", 1), 250, 250,
                str(self.contrib), 170, 60)
        text_left(d, pal, "subtracted from the staging area on travel", 60, 318, 1, pal.dim)
        _footer(d, pal, self.buttons, save_label="Travel")

    def on_button(self, btn):
        k = btn.id[0]
        if k == "pts":
            self.pts = max(1, min(30, self.pts + btn.id[1]))
            return None
        if k == "ctr":
            self.contrib = max(0, min(9, self.contrib + btn.id[1]))
            return None
        if k == "save":
            if self.mode == "new" and self.game.active_location is None:
                self.game.travel_to(self.pts, self.contrib)
            else:
                self.game.change_location(self.pts, self.contrib)
            return "close"
        if k == "cancel":
            return "cancel"
        return None


class AllocationModal:
    """Distribute a success budget across location / quest / side quests."""

    def __init__(self, game, budget):
        self.game = game
        self.budget = budget
        self.alloc = {"location": 0, "quest": 0, "side_quests": [0] * len(game.side_quests)}
        self._auto()
        self.buttons = []

    def _auto(self):
        a = self.game.auto_split(self.budget)
        self.alloc = {"location": a["location"], "quest": a["quest"],
                      "side_quests": [0] * len(self.game.side_quests)}

    def _used(self):
        return self.alloc["location"] + self.alloc["quest"] + sum(self.alloc["side_quests"])

    def _remaining(self):
        return self.budget - self._used()

    def draw(self, hw, game, pal):
        d = hw.display
        self.buttons = []
        d.set_pen(pal.bg)
        d.clear()
        text_center(d, pal, "Quested successfully", 240, 16, 3, pal.ok_fg)
        text_center(d, pal, "remaining %d / %d" % (self._remaining(), self.budget),
                    240, 54, 2, pal.gold)

        # reminder
        panel(d, pal, 16, 78, 448, 52, fill=pal.card)
        text_left(d, pal, "Fill Active Location first; overflow -> Quest.", 26, 86, 1, pal.muted)
        text_left(d, pal, "Side quest may take progress instead. Card effects override.", 26, 104, 1, pal.muted)

        y = 142
        self._rows = []
        if self.game.active_location is not None:
            self._rows.append(("location", None, "Active Location",
                               self.game.active_location["progress"], self.game.active_location["points"]))
        self._rows.append(("quest", None, "Quest %s" % self.game.quest_label(),
                           self.game.quest["progress"], self.game.quest["points"]))
        for i, sq in enumerate(self.game.side_quests):
            self._rows.append(("side", i, "Side quest %d" % (i + 1), sq["progress"], sq["points"]))

        for key, idx, label, cur, pts in self._rows:
            add = self.alloc["side_quests"][idx] if key == "side" else self.alloc[key]
            panel(d, pal, 16, y, 448, 50, fill=pal.card)
            text_left(d, pal, label, 26, y + 6, 2, pal.tan)
            text_left(d, pal, "%d + %d / %d" % (cur, add, pts), 26, y + 28, 1, pal.muted)
            mn = Button(("m", key, idx), 300, y + 5, 44, 40)
            pl = Button(("p", key, idx), 410, y + 5, 44, 40)
            button(d, pal, mn, "-", 3)
            button(d, pal, pl, "+", 3)
            text_center(d, pal, str(cur + add), 377, y + 12, 3, pal.gold)
            self.buttons.extend([mn, pl])
            y += 56

        auto = Button(("auto",), 16, 356, 300, 44)
        rst = Button(("reset",), 324, 356, 140, 44)
        panel(d, pal, auto.x, auto.y, auto.w, auto.h, fill=pal.btn)
        text_center(d, pal, "Auto loc->quest", auto.x + auto.w / 2, auto.y + 12, 2, pal.tan)
        panel(d, pal, rst.x, rst.y, rst.w, rst.h, fill=pal.btn)
        text_center(d, pal, "Reset", rst.x + rst.w / 2, rst.y + 12, 2, pal.tan)
        self.buttons.extend([auto, rst])

        _footer(d, pal, self.buttons, save_label="Apply")

    def _add(self, key, idx, delta):
        if delta > 0 and self._remaining() <= 0:
            return
        if key == "side":
            self.alloc["side_quests"][idx] = max(0, self.alloc["side_quests"][idx] + delta)
        else:
            self.alloc[key] = max(0, self.alloc[key] + delta)

    def on_button(self, btn):
        k = btn.id[0]
        if k == "m":
            self._add(btn.id[1], btn.id[2], -1)
            return None
        if k == "p":
            self._add(btn.id[1], btn.id[2], 1)
            return None
        if k == "auto":
            self._auto()
            return None
        if k == "reset":
            self.alloc = {"location": 0, "quest": 0, "side_quests": [0] * len(self.game.side_quests)}
            return None
        if k == "save":
            completed = self.game.place_progress(self.alloc)
            msg = "Quested successfully! +%d progress" % self.budget
            if completed:
                msg += " (" + ", ".join(completed) + ")"
            self.game.log_event(msg)
            return "close"
        if k == "cancel":
            return "cancel"
        return None


class QuestingProgressModal:
    """All questing progress in one place: main quest, active location (or a
    slot to add one) and each side quest, each as Current (live progress
    ring) | Target (dim, no fill) circular editors. Non-main rows add
    complete/remove icon buttons; removing the Location opens an in-modal
    prompt (Replaced / To staging / Discard - a modal cannot open another,
    so this is state on self, not a nested modal). Weather radios replace
    the old heading stepper when sailing. A bottom-anchored chart summarizes
    quest_history by round. Silent progress/points edits are batched into
    one summary log line per field on close."""

    ROWS_Y0 = 62
    ROW_H = 38

    def __init__(self, game):
        self.game = game
        self.buttons = []
        self.loc_prompt = None   # {"stage": "choose"|"pts"|"contrib", ...} or None
        self._snap = self._snapshot()

    def _snapshot(self):
        g = self.game
        return {
            "q": {"p": g.quest["progress"], "t": g.quest["points"]},
            "loc": ({"p": g.active_location["progress"], "t": g.active_location["points"]}
                    if g.active_location else None),
            "sqLen": len(g.side_quests),
            "sq": [{"p": s["progress"], "t": s["points"]} for s in g.side_quests],
        }

    def _items(self):
        g = self.game
        items = [{"kind": "q", "name": "Quest %s" % g.quest_label(), "removable": False,
                  "advanceable": bool(g.stages)}]
        items.append({"kind": "l", "name": "Location", "removable": True}
                     if g.active_location else {"kind": "l_add"})
        for i, s in enumerate(g.side_quests):
            # Prefer the catalog name (SideQuestPickModal, M4-B sidequest
            # Task 2) when present; old saves and manual entries have no
            # "name" key at all, so this stays "Side Quest N" for them.
            label = s.get("name") or "Side Quest %d" % (i + 1)
            items.append({"kind": "s", "idx": i, "name": label, "removable": True})
        return items

    def _val_editor2(self, d, pal, cx, cy, value, frac, progress_ring, id_minus, id_plus):
        """Circular -/+ flanking a value token: Current shows a live progress
        ring (token()); Target is dim-only (well + full dim ring, no fill)."""
        circ_btn(d, pal, cx - 30, cy, 10, "-")
        if progress_ring:
            token(d, pal, cx, cy, 13, 2, value, pal.gold, frac, pal.gold, pal.dim)
        else:
            disc(d, cx, cy, 13, pal.well)
            arc_runs(d, cx, cy, 13, 11, 0, 360, pal.dim)
            text_center(d, pal, str(value), cx, int(cy - 8), 2, pal.gold)
        circ_btn(d, pal, cx + 30, cy, 10, "+")
        self.buttons.append(Button(id_minus, cx - 30 - 12, cy - 12, 24, 24))
        self.buttons.append(Button(id_plus, cx + 30 - 12, cy - 12, 24, 24))

    def _icon_btn(self, d, pal, cx, cy, r, kind, id):
        """Small circular action: 'x' = remove (red X, reuses circ_btn),
        'done' = mark complete (green pennant flag), 'adv' = manually trigger
        the guided resolution flow (gold chevron - conditional/0-point
        stages have no numeric gate to cross, so this is the only way in)."""
        if kind == "x":
            circ_btn(d, pal, cx, cy, r, "X", pal.red)
        elif kind == "adv":
            disc(d, cx, cy, r, pal.btn)
            arc_runs(d, cx, cy, r, r - 2, 0, 360, pal.bevel_l)
            d.set_pen(pal.gold)
            d.triangle(cx - 3, cy - 5, cx - 3, cy + 5, cx + 5, cy)
        else:
            disc(d, cx, cy, r, pal.btn)
            arc_runs(d, cx, cy, r, r - 2, 0, 360, pal.bevel_l)
            d.set_pen(pal.green)
            d.rectangle(cx - 4, cy - 5, 1, 10)
            d.triangle(cx - 3, cy - 5, cx + 4, cy - 3, cx - 3, cy - 1)
        self.buttons.append(Button(id, cx - 12, cy - 12, 24, 24))

    def _row(self, d, pal, it, y):
        g = self.game
        cy = y + 8
        if it["kind"] == "l_add":
            b = Button(("addloc",), 12, y + 7, 140, 24)
            bevel(d, pal, b.x, b.y, b.w, b.h, pal.btn)
            text_center(d, pal, "+ Add location", b.x + b.w / 2, b.y + 5, 2, pal.tan)
            self.buttons.append(b)
            return
        if it["kind"] == "q":
            prog, pts, pfx, idx = g.quest["progress"], g.quest["points"], "q", None
        elif it["kind"] == "l":
            prog, pts, pfx, idx = (g.active_location["progress"], g.active_location["points"],
                                   "l", None)
        else:
            s = g.side_quests[it["idx"]]
            prog, pts, pfx, idx = s["progress"], s["points"], "s", it["idx"]
        # The quest row's title doubles as a tap target opening the read-only
        # QuestCardModal (M4-B, second entry point) - gold ink hints it's
        # interactive, matching this row alone (Location/Side Quest titles
        # stay plain). The button is pushed AFTER the Current/Target editors
        # below so their hit regions win on any overlap; its own bounds
        # (x 12-130) sit left of the Current editor's leftmost hit-box
        # (x=136) by construction, so there should be no real overlap to
        # arbitrate.
        quest_card_tappable = it["kind"] == "q" and bool(g.stages)
        # 118px matches the quest_card tap target's fixed width below (and
        # the room left before the Current editor's leftmost hit-box at
        # x=136) - a real catalog side-quest name (up to ~20 chars) can
        # otherwise run into the Current/Target editors, unlike the old
        # always-short generic labels ("Quest 1A", "Location", "Side Quest 3").
        name_s = truncate_text(it["name"], 2, 118, d.measure_text)
        text_left(d, pal, name_s, 12, y, 2, pal.gold if quest_card_tappable else pal.tan)
        self._val_editor2(d, pal, 178, cy, prog, (prog / pts if pts else 0), True,
                          (pfx + "P-", idx), (pfx + "P+", idx))
        self._val_editor2(d, pal, 300, cy, pts, 0, False,
                          (pfx + "T-", idx), (pfx + "T+", idx))
        if it.get("removable"):
            self._icon_btn(d, pal, 400, cy, 11, "done", (pfx + "done", idx))
            self._icon_btn(d, pal, 436, cy, 11, "x", (pfx + "X", idx))
        if it.get("advanceable"):
            self._icon_btn(d, pal, 400, cy, 11, "adv", ("qAdv",))
        if quest_card_tappable:
            self.buttons.append(Button(("quest_card",), 12, y, 118, self.ROW_H))

    def draw(self, hw, game, pal):
        from ui.header import modal_header
        d = hw.display
        self.buttons = []
        d.set_pen(pal.bg)
        d.clear()
        if self.loc_prompt:
            self._draw_loc_prompt(d, pal)
            return
        modal_header(d, pal, game, "Progress", self.buttons)

        text_left(d, pal, "Quest points", 12, 48, 1, pal.muted)
        text_center(d, pal, "Current", 178, 48, 1, pal.dim)
        text_center(d, pal, "Target", 300, 48, 1, pal.dim)

        items = self._items()
        for i, it in enumerate(items):
            self._row(d, pal, it, self.ROWS_Y0 + i * self.ROW_H)
        n = len(items)

        add_y = self.ROWS_Y0 + n * self.ROW_H - 4
        add = Button(("add",), 12, add_y, 120, 24)
        bevel(d, pal, add.x, add.y, add.w, add.h, pal.btn)
        text_center(d, pal, "+ Side quest", add.x + add.w / 2, add.y + 5, 2, pal.tan)
        self.buttons.append(add)

        if self.game.sailing:
            heading_y = self.ROWS_Y0 + n * self.ROW_H + 34
            text_left(d, pal, "Heading", 12, heading_y, 2, pal.tan)
            cy = heading_y + 4
            for i in range(4):
                cx = 150 + i * 40
                disc(d, cx, cy, 14, pal.well)
                active = i == self.game.heading
                if active:
                    ring(d, cx, cy, 14, 2, 1.0, pal.gold, pal.gold)
                wx_small(d, pal, i, cx, cy, 7, None if active else pal.dim)
                self.buttons.append(Button(("hd_set", i), cx - 14, cy - 14, 28, 28))

        self._draw_chart(d, pal)

    def _draw_chart(self, d, pal):
        """Absolutely positioned near the bottom regardless of how many rows
        are above (quest/location/side-quest count varies) - never moves."""
        cy0 = 344
        d.set_pen(pal.border)
        d.rectangle(8, cy0 - 12, 464, 1)
        text_left(d, pal, "THIS GAME - BY ROUND", 12, cy0 - 9, 1, pal.muted)
        cols = self.game.quest_history[-8:]
        if not cols:
            text_center(d, pal, "No rounds resolved yet", 240, cy0 + 14, 1, pal.dim)
            return
        x0 = 52
        stride = (472 - x0) // len(cols)
        for i, r in enumerate(cols):
            text_center(d, pal, "R%d" % r["round"], x0 + i * stride + stride // 2, cy0, 1, pal.dim)
        hdg_pen = [pal.gold, pal.amber, pal.amber, pal.red]

        def _result_cell(r):
            signed = -r["n"] if r["outcome"] == "fail" else r["n"]
            s = ("+%d" % signed) if signed > 0 else str(signed)
            return s, (pal.green if signed > 0 else pal.red)

        rows = [
            (icons.WILLPOWER, pal.gold, False, lambda r: (str(r["willpower"]), pal.gold)),
            (icons.THREAT, pal.outline, True, lambda r: (str(r["staging"]), pal.outline)),
            (icons.TRAIL, pal.green, False, _result_cell),
        ]
        if self.game.sailing:
            rows.append((icons.WHEEL, pal.gold, False,
                         lambda r: (str(r["heading"]), hdg_pen[r["heading"]])))
        ry = cy0 + 14
        for mask, ipen, stripe, cell in rows:
            if stripe:
                d.set_pen(pal.row_stripe)
                d.rectangle(8, ry - 4, 464, 24)
            icons.draw(d, mask, 12, ry - 2, ipen)
            for i, r in enumerate(cols):
                s, pen = cell(r)
                text_center(d, pal, s, x0 + i * stride + stride // 2, ry, 2, pen)
            ry += 26
        caption = "willpower / staging / result" + (" / heading" if self.game.sailing else "")
        text_center(d, pal, caption, 240, ry + 4, 1, pal.dim)

    def _draw_loc_prompt(self, d, pal):
        lp = self.loc_prompt
        if lp["stage"] == "choose":
            self._draw_loc_choose(d, pal)
        elif lp["stage"] == "pts":
            self._draw_loc_pts(d, pal)
        else:
            self._draw_loc_contrib(d, pal)

    def _draw_loc_choose(self, d, pal):
        loc = self.game.active_location
        text_center(d, pal, "Location removed", 240, 30, 3, pal.gold)
        text_center(d, pal, "What happened to it?", 240, 70, 2, pal.tan)
        text_center(d, pal, "%d/%d progress will be discarded" % (loc["progress"], loc["points"]),
                    240, 94, 1, pal.dim)

        def opt(y, id, label, sub):
            b = Button((id,), 24, y, 432, 64)
            bevel(d, pal, b.x, b.y, b.w, b.h, pal.btn, t=3)
            text_center(d, pal, label, 240, y + 14, 3, pal.tan)
            text_center(d, pal, sub, 240, y + 44, 1, pal.dim)
            self.buttons.append(b)

        opt(120, "lp_replaced", "Replaced", "enter the new location's quest points")
        opt(196, "lp_staging", "To staging", "its threat returns to the staging area")
        opt(272, "lp_discard", "Discard", "no replacement")
        cancel = Button(("lp_cancel",), 24, 356, 432, 56)
        bevel(d, pal, cancel.x, cancel.y, cancel.w, cancel.h, pal.btn_no, t=3)
        text_center(d, pal, "Cancel", 240, cancel.y + 18, 2, pal.no_fg)
        self.buttons.append(cancel)

    def _draw_loc_pts(self, d, pal):
        text_center(d, pal, "Replace location", 240, 30, 3, pal.gold)
        text_left(d, pal, "Quest points", 60, 216, 2, pal.tan)
        stepper(d, pal, self.buttons, ("lp_pts", -1), ("lp_pts", 1), 250, 200,
               str(self.loc_prompt["pts"]), 170, 60)
        _footer(d, pal, self.buttons, save_label="Confirm")

    def _draw_loc_contrib(self, d, pal):
        text_center(d, pal, "Location to staging", 240, 30, 3, pal.gold)
        icons.draw(d, icons.THREAT, 60, 208, pal.red)
        text_left(d, pal, "Contribution", 88, 216, 2, pal.tan)
        stepper(d, pal, self.buttons, ("lp_ctr", -1), ("lp_ctr", 1), 250, 200,
               str(self.loc_prompt["state"].preview), 170, 60)
        text_left(d, pal, "added to the staging area", 60, 270, 1, pal.dim)
        _footer(d, pal, self.buttons, save_label="Confirm")

    def _clamp_adj(self, cur, delta):
        return max(0, min(99, cur + delta))

    def on_button(self, btn):
        g = self.game
        if self.loc_prompt:
            return self._on_loc_prompt_button(btn)
        k = btn.id[0]
        a = btn.id[1] if len(btn.id) > 1 else None
        up = k.endswith("+")
        if k in ("qP-", "qP+"):
            g.quest["progress"] = self._clamp_adj(g.quest["progress"], 1 if up else -1)
            return None
        if k in ("qT-", "qT+"):
            g.quest["points"] = self._clamp_adj(g.quest["points"], 1 if up else -1)
            return None
        if k in ("lP-", "lP+"):
            g.active_location["progress"] = self._clamp_adj(g.active_location["progress"], 1 if up else -1)
            if not g.stages:
                # Catalog games defer this to the guided resolution flow
                # (close-time needs_resolution() check + ResolutionModal's
                # "location" step, B-resolve Task 3) so overflow excess gets
                # credited to the quest card (rulebook p.15) via
                # resolve_location_overflow() instead of silently discarded.
                # Custom games have no guided flow to defer to, so they keep
                # the immediate auto-explore they've always had.
                g.explore_location_if_done()
            return None
        if k in ("lT-", "lT+"):
            g.active_location["points"] = self._clamp_adj(g.active_location["points"], 1 if up else -1)
            return None
        if k == "ldone":
            g.log_event("Active location Explored")
            g.active_location = None
            self._snap = self._snapshot()
            return None
        if k == "lX":
            self.loc_prompt = {"stage": "choose"}
            return None
        if k in ("sP-", "sP+"):
            s = g.side_quests[a]
            s["progress"] = self._clamp_adj(s["progress"], 1 if up else -1)
            return None
        if k in ("sT-", "sT+"):
            s = g.side_quests[a]
            s["points"] = self._clamp_adj(s["points"], 1 if up else -1)
            return None
        if k == "sdone":
            g.log_event("Side quest %d completed" % (a + 1))
            g.side_quests.pop(a)
            self._snap = self._snapshot()
            return None
        if k == "sX":
            g.log_event("Side quest %d removed" % (a + 1))
            g.side_quests.pop(a)
            self._snap = self._snapshot()
            return None
        if k == "add":
            # The router holds one modal at a time (no stacking) - close this
            # one (flushing any pending edits, same as a normal "close") and
            # flag that SideQuestPickModal should open on the next loop pass,
            # same pending-flag pattern as "quest_card" below. The picker
            # needs a catalog read (flash I/O) that a modal's on_button
            # can't do mid-tap without breaking that invariant.
            g.pending_side_quest_pick = True
            self._log_changes()
            return "close"
        if k == "addloc":
            g.active_location = {"points": 3, "progress": 0}
            g.log_event("Active location added (card effect)")
            self._snap = self._snapshot()
            return None
        if k == "hd_set":
            if a != g.heading:
                g.shift_heading(a - g.heading, "progress view")
            return None
        if k == "quest_card":
            # The router holds one modal at a time (no stacking) - close this
            # one (flushing any pending edits, same as a normal "close") and
            # flag that QuestCardModal should open on the next loop pass. See
            # main.py's loop, which checks pending_quest_card once modal is
            # None.
            g.pending_quest_card = True
            self._log_changes()
            return "close"
        if k == "qAdv":
            # Manually trigger the guided resolution flow even though the
            # numeric target hasn't been reached - the only way in for
            # conditional/0-point stages, which have no gate to cross. See
            # main.py's loop, which checks pending_resolution once modal is
            # None (same pending-flag pattern as pending_quest_card above).
            g.pending_resolution = "forced"
            self._log_changes()
            return "close"
        if k == "close":
            self._log_changes()
            # Catalog games: any overflow (location/quest/side-quest) is
            # safe to defer to ResolutionModal, since every one of its
            # steps has a real close/dismiss escape hatch. Custom games
            # have no ResolutionModal - their only fallback is the legacy
            # StageCompleteModal, which has no safe "cancel" (only "go",
            # committing a stage/side/points change, or "win") - so their
            # trigger must stay scoped to the quest itself overflowing
            # (what StageCompleteModal has always been opened for), not
            # needs_resolution()'s broader check. A side-quest-only
            # overflow must not force a custom-game player into that
            # advance-or-victory dilemma.
            if g.stages:
                if g.needs_resolution():
                    g.pending_resolution = "auto"
            elif g.quest["points"] > 0 and g.quest["progress"] >= g.quest["points"]:
                g.pending_resolution = "auto"
            return "close"
        return None

    def _on_loc_prompt_button(self, btn):
        from ui.counter import CounterState
        g = self.game
        k = btn.id[0]
        lp = self.loc_prompt
        if lp["stage"] == "choose":
            if k == "lp_replaced":
                self.loc_prompt = {"stage": "pts", "pts": 3}
                return None
            if k == "lp_staging":
                self.loc_prompt = {"stage": "contrib", "state": CounterState(2, 0, 9)}
                return None
            if k == "lp_discard":
                g.log_event("Active location removed")
                g.active_location = None
                self._snap = self._snapshot()
                self.loc_prompt = None
                return None
            if k == "lp_cancel":
                self.loc_prompt = None
                return None
            return None
        # pts / contrib sub-stages share the generic _footer() ids
        if k == "cancel":
            self.loc_prompt = {"stage": "choose"}
            return None
        if k == "save":
            if lp["stage"] == "pts":
                g.change_location(lp["pts"], 0)
            else:
                lp["state"].confirm()
                v = lp["state"].value
                g.staging += v
                g.active_location = None
                g.log_event("Active location to staging (+%d threat)" % v)
            self._snap = self._snapshot()
            self.loc_prompt = None
            return None
        if k == "lp_pts":
            lp["pts"] = max(1, min(30, lp["pts"] + btn.id[1]))
            return None
        if k == "lp_ctr":
            lp["state"].tap(btn.id[1])
            return None
        return None

    def _log_changes(self):
        s, g = self._snap, self.game
        if g.quest["progress"] != s["q"]["p"] or g.quest["points"] != s["q"]["t"]:
            g.log_event("Quest %s set %d/%d (progress view)"
                        % (g.quest_label(), g.quest["progress"], g.quest["points"]))
        if s["loc"] and g.active_location and (
                g.active_location["progress"] != s["loc"]["p"]
                or g.active_location["points"] != s["loc"]["t"]):
            g.log_event("Active location set %d/%d (progress view)"
                        % (g.active_location["progress"], g.active_location["points"]))
        if len(g.side_quests) == s["sqLen"]:
            for i, sq in enumerate(g.side_quests):
                if sq["progress"] != s["sq"][i]["p"] or sq["points"] != s["sq"][i]["t"]:
                    g.log_event("Side quest %d set %d/%d (progress view)"
                                % (i + 1, sq["progress"], sq["points"]))


class SailingModal:
    """Log the result of a Sailing test: +v = wheels found (shift on-course),
    -v = steps off-course (winds/card effects). Heading index 0 = on-course."""

    def __init__(self, game):
        self.game = game
        self.v = 0
        self.buttons = []

    def _result(self):
        return max(0, min(3, self.game.heading - self.v))

    def _heading(self, d, pal, h, cy, scale):
        term, _icon, facing, _deg = HEADINGS[h]
        pen = pal.gold if h == 0 else (pal.red if h == 3 else pal.amber)
        label = "%s - %s" % (facing, term)
        lw = d.measure_text(label, scale)
        total = 24 + 8 + lw
        x0 = int(240 - total / 2)
        draw_weather(d, pal, h, x0 + 12, cy + 10, 12)
        text_left(d, pal, label, x0 + 32, cy + (2 if scale == 2 else 0), scale, pen)

    def draw(self, hw, game, pal):
        from ui.header import modal_header
        d = hw.display
        self.buttons = []
        d.set_pen(pal.bg)
        d.clear()
        modal_header(d, pal, self.game, "Sailing test", self.buttons)

        text_center(d, pal, "Current heading", 240, 54, 1, pal.dim)
        self._heading(d, pal, self.game.heading, 74, 2)

        big = str(abs(self.v))
        bw = d.measure_text(big, 6)
        bx = int(240 - ((bw + 14 + 48) if self.v > 0 else bw) / 2)
        bpen = pal.red if self.v < 0 else (pal.gold if self.v > 0 else pal.muted)
        text_left(d, pal, big, bx, 128, 6, bpen)
        if self.v > 0:
            icons.draw(d, icons.WHEEL, bx + bw + 14, 128, pal.gold, 2)
        if self.v > 0:
            sub = "%d wheel%s found - shift on-course" % (self.v, "s" if self.v > 1 else "")
            spen = pal.green
        elif self.v < 0:
            sub = "%d step%s off-course (card effect)" % (-self.v, "s" if self.v < -1 else "")
            spen = pal.red
        else:
            sub = "no wheels found - heading stays"
            spen = pal.dim
        text_center(d, pal, sub, 240, 200, 1, spen)

        mn = Button(("d", -1), 34, 128, 64, 60)
        pl = Button(("d", 1), 480 - 34 - 64, 128, 64, 60)
        bevel(d, pal, mn.x, mn.y, mn.w, mn.h, pal.btn)
        text_center(d, pal, "-", mn.x + 32, mn.y + 14, 4, pal.tan)
        bevel(d, pal, pl.x, pl.y, pl.w, pl.h, pal.btn)
        text_center(d, pal, "+", pl.x + 32, pl.y + 14, 4, pal.tan)
        self.buttons.append(mn)
        self.buttons.append(pl)

        text_center(d, pal, "Result", 240, 240, 1, pal.dim)
        self._heading(d, pal, self._result(), 262, 2)

        no = Button(("cancel",), 24, 404, 200, 64)
        ok = Button(("apply",), 256, 404, 200, 64)
        bevel(d, pal, no.x, no.y, no.w, no.h, pal.btn_no, t=3)
        text_center(d, pal, "Cancel", no.x + 100, no.y + 20, 2, pal.no_fg)
        bevel(d, pal, ok.x, ok.y, ok.w, ok.h, pal.btn_ok, t=3)
        text_center(d, pal, "Apply", ok.x + 100, ok.y + 20, 2, pal.ok_fg)
        self.buttons.append(no)
        self.buttons.append(ok)

    def on_button(self, btn):
        k = btn.id[0]
        if k == "d":
            self.v = max(-3, min(8, self.v + btn.id[1]))
            return None
        if k == "apply":
            if self.v != 0:
                if self.v > 0:
                    why = "%d wheel%s found (sailing test)" % (self.v, "s" if self.v > 1 else "")
                else:
                    why = "card effect"
                self.game.shift_heading(-self.v, why)
            return "close"
        # Footer Cancel and the header DONE button both dismiss without
        # applying the pending wheel delta — only Apply commits the shift.
        if k in ("cancel", "close"):
            return "cancel"
        return None


class StageCompleteModal:
    """After a quest stage clears, set up the next stage (number, side A-H,
    quest points) - or declare the final stage a Victory."""

    def __init__(self, game):
        self.game = game
        ps = game.pending_stage or {"cleared": "?", "excess": 0}
        self.cleared = ps["cleared"]
        self.excess = ps["excess"]
        self.n = game.quest["stage_n"]
        self.side = game.quest["side"]
        self.pts = 0
        self.buttons = []

    def draw(self, hw, game, pal):
        d = hw.display
        self.buttons = []
        d.set_pen(pal.bg)
        d.clear()
        text_center(d, pal, "Quest Stage %s cleared!" % self.cleared, 240, 26, 3, pal.gold)
        y = 74
        text_center(d, pal, "Set up the next stage", 240, y, 2, pal.tan)
        y += 40
        text_left(d, pal, "Stage", 30, y + 14, 2, pal.tan)
        stepper(d, pal, self.buttons, ("n", -1), ("n", 1), 160, y, str(self.n), 130, 52)
        stepper(d, pal, self.buttons, ("side", -1), ("side", 1), 316, y, self.side, 144, 52)
        y += 76
        text_left(d, pal, "Quest points", 30, y + 14, 2, pal.tan)
        stepper(d, pal, self.buttons, ("pts", -1), ("pts", 1), 240, y, str(self.pts), 210, 52)
        y += 90
        go = Button(("go",), 30, y, 420, 60)
        bevel(d, pal, go.x, go.y, go.w, go.h, pal.btn_ok, t=3)
        text_center(d, pal, "Continue to %d%s" % (self.n, self.side), 240, y + 20, 2, pal.ok_fg)
        self.buttons.append(go)
        y += 74
        win = Button(("win",), 30, y, 420, 60)
        bevel(d, pal, win.x, win.y, win.w, win.h, pal.card_hi, t=3)
        text_center(d, pal, "That was the final stage - Victory!", 240, y + 20, 2, pal.gold)
        self.buttons.append(win)

    def on_button(self, btn):
        k = btn.id[0]
        if k == "n":
            self.n = max(1, min(9, self.n + btn.id[1]))
            return None
        if k == "side":
            i = (ord(self.side[0]) - 65 + btn.id[1] + 8) % 8   # cycle A-H
            self.side = chr(65 + i)
            return None
        if k == "pts":
            self.pts = max(0, min(30, self.pts + btn.id[1]))
            return None
        if k == "go":
            g = self.game
            g.quest["stage_n"] = self.n
            g.quest["side"] = self.side
            g.quest["points"] = self.pts
            g.pending_stage = None
            g.log_event("Advance to stage %s (needs %d)" % (g.quest_label(), self.pts))
            return "close"
        if k == "win":
            self.game.pending_stage = None
            self.game.set_game_over("victory")
            return "close"
        return None


class ResolutionModal:
    """Guided post-edit/post-success resolution: location -> quest advance
    (branch/reveal/flip) -> side quests, one explicit step at a time,
    re-deriving what's next from live game state after every action. Opened
    only for catalog games (game.stages non-empty) - custom games keep the
    legacy StageCompleteModal. See docs/superpowers/plans/
    2026-07-24-quest-picker-bresolve.md for the full rationale, including
    why at most one stage advance can ever happen per pass."""

    def __init__(self, game, force_advance=False):
        self.game = game
        self.buttons = []
        self.branch_pick = None
        self.force_advance = force_advance
        self._skipped_side_quests = []   # dict refs (identity, not value) - see _derive
        self.step = self._derive()

    def _quest_step(self):
        g = self.game
        if g.quest["side"] == "A":
            card = g.stages[g.stage_idx]["cards"][g.card_idx]
            face_a = next((f for f in card["faces"] if f["side"] == "A"), {})
            return {"kind": "reveal", "stage_n": g.quest["stage_n"], "face_a": face_a,
                    "next_points": card["questPoints"]}
        nxt_idx = g.stage_idx + 1
        if nxt_idx >= len(g.stages):
            return {"kind": "victory", "cleared": g.quest_label()}
        nxt = g.stages[nxt_idx]
        if len(nxt["cards"]) > 1 and self.branch_pick is None:
            return {"kind": "branch", "cards": nxt["cards"], "mode": nxt.get("branch", "choice")}
        card_idx = self.branch_pick or 0
        return {"kind": "advance", "cleared": g.quest_label(), "card_idx": card_idx,
                "next_stage": nxt["stage"],
                "underfilled": g.quest["points"] > 0 and g.quest["progress"] < g.quest["points"]}

    def _derive(self):
        g = self.game
        if g.stages and g.quest["side"] == "A":
            return self._quest_step()      # finish an interrupted reveal/flip first
        loc = g.active_location
        if loc and loc["points"] > 0 and loc["progress"] >= loc["points"]:
            return {"kind": "location", "progress": loc["progress"], "points": loc["points"]}
        if (g.quest["points"] > 0 and g.quest["progress"] >= g.quest["points"]) or self.force_advance:
            return self._quest_step()
        for i, s in enumerate(g.side_quests):
            if any(s is skipped for skipped in self._skipped_side_quests):
                continue
            if s["points"] > 0 and s["progress"] >= s["points"]:
                return {"kind": "side_quest", "idx": i,
                        "name": s.get("name") or "Side Quest %d" % (i + 1),
                        "progress": s["progress"], "points": s["points"]}
        return None

    def draw(self, hw, game, pal):
        from ui.header import modal_header
        d = hw.display
        self.buttons = []
        d.set_pen(pal.bg)
        d.clear()
        modal_header(d, pal, game, "Resolve", self.buttons)
        st = self.step
        if st is None:
            self._draw_done(d, pal)
        elif st["kind"] == "reveal":
            self._draw_reveal(d, pal, st)
        elif st["kind"] == "location":
            self._draw_location(d, pal, st)
        elif st["kind"] == "branch":
            self._draw_branch(d, pal, st)
        elif st["kind"] == "advance":
            self._draw_advance(d, pal, st)
        elif st["kind"] == "victory":
            self._draw_victory(d, pal, st)
        elif st["kind"] == "side_quest":
            self._draw_side_quest(d, pal, st)

    # -- per-step draw helpers (layout bands per the plan's Layout section) --
    def _cta(self, d, pal, label, id_, y=404, h=56, ok=True):
        b = Button(id_, 24, y, 432, h)
        bevel(d, pal, b.x, b.y, b.w, b.h, pal.btn_ok if ok else pal.btn_no, t=3)
        text_center(d, pal, label, 240, y + h // 2 - 10, 2, pal.ok_fg if ok else pal.no_fg)
        self.buttons.append(b)

    def _draw_done(self, d, pal):
        text_center(d, pal, "All resolved", 240, 200, 3, pal.gold)
        self._cta(d, pal, "Continue", ("close",))

    def _draw_reveal(self, d, pal, st):
        text_center(d, pal, "STAGE %d REVEALED" % st["stage_n"], 240, 64, 2, pal.amber)
        name = truncate_text(st["face_a"].get("name") or "", 3, 432, d.measure_text)
        text_center(d, pal, name, 240, 92, 3, pal.gold)
        tip_x, tip_w, tip_y = 24, 432, 130
        ribbon_h, pad_top, line_h, pad_bottom, max_lines = 22, 10, 24, 10, 5
        raw = st["face_a"].get("text")
        body = raw if raw else "No setup instructions for this stage."
        lines = wrap_text(body, 2, tip_w - 28, measure=d.measure_text)[:max_lines]
        tip_h = ribbon_h + pad_top + len(lines) * line_h + pad_bottom
        d.set_pen(pal.border_gold); d.rectangle(tip_x, tip_y, tip_w, tip_h)
        d.set_pen(pal.bg); d.rectangle(tip_x + 2, tip_y + 2, tip_w - 4, tip_h - 4)
        d.set_pen(pal.border_gold); d.rectangle(tip_x + 4, tip_y + 4, tip_w - 8, tip_h - 8)
        d.set_pen(pal.scroll); d.rectangle(tip_x + 6, tip_y + 6, tip_w - 12, tip_h - 12)
        d.set_pen(pal.border_gold); d.rectangle(tip_x, tip_y, tip_w, ribbon_h)
        text_left(d, pal, "STAGE ADVANCE - resolve now", tip_x + 10, tip_y + 6, 1, pal.bg, shadow=False)
        ly = tip_y + ribbon_h + pad_top
        for ln in lines:
            text_left(d, pal, ln, tip_x + 14, ly, 2, pal.tan)
            ly += line_h
        self._cta(d, pal, "Flip to Side B  ->  %d qp" % st["next_points"], ("do_flip",))

    def _draw_location(self, d, pal, st):
        text_center(d, pal, "Location Explored", 240, 90, 3, pal.gold)
        text_center(d, pal, "%d/%d progress" % (st["progress"], st["points"]), 240, 130, 2, pal.tan)
        excess = st["progress"] - st["points"]
        if excess:
            text_center(d, pal, "%d excess -> quest card" % excess, 240, 160, 2, pal.amber)
        self._cta(d, pal, "Continue", ("resolve_location",))

    def _draw_branch(self, d, pal, st):
        text_center(d, pal, "Choose a path", 240, 56, 3, pal.gold)
        text_center(d, pal, "First player chooses" if st["mode"] != "random" else "Random",
                   240, 86, 1, pal.dim)
        y = 116
        for i, card in enumerate(st["cards"]):
            b_face = next((f for f in card["faces"] if f["side"] == "B"), {})
            b = Button(("pick_branch", i), 24, y, 432, 64)
            sel = self.branch_pick == i
            bevel(d, pal, b.x, b.y, b.w, b.h, pal.btn_ok if sel else pal.btn, t=3)
            text_left(d, pal, b_face.get("name") or "?", b.x + 14, y + 10, 2,
                      pal.ok_fg if sel else pal.tan)
            preview = truncate_text(b_face.get("text") or "", 1, 400, d.measure_text)
            text_left(d, pal, preview, b.x + 14, y + 38, 1, pal.dim)
            self.buttons.append(b)
            y += 74
        if st["mode"] == "random":
            r = Button(("randomize_branch",), 24, y, 432, 40)
            bevel(d, pal, r.x, r.y, r.w, r.h, pal.card, t=2)
            text_center(d, pal, "Randomize for me", 240, y + 10, 2, pal.tan)
            self.buttons.append(r)

    def _draw_advance(self, d, pal, st):
        text_center(d, pal, "Quest %s cleared" % st["cleared"], 240, 90, 3, pal.gold)
        if st["underfilled"]:
            text_center(d, pal, "Progress hasn't reached target - confirm", 240, 130, 1, pal.red)
        self._cta(d, pal, "Reveal Stage %d" % st["next_stage"], ("do_advance",))

    def _draw_victory(self, d, pal, st):
        text_center(d, pal, "Quest %s cleared" % st["cleared"], 240, 70, 2, pal.tan)
        text_center(d, pal, "That was the final stage!", 240, 110, 3, pal.gold)
        self._cta(d, pal, "Declare Victory", ("declare_victory",), y=340)
        self._cta(d, pal, "Not yet - keep playing", ("continue_without_victory",), y=404, ok=False)

    def _draw_side_quest(self, d, pal, st):
        text_center(d, pal, st["name"], 240, 90, 3, pal.gold)
        text_center(d, pal, "%d/%d" % (st["progress"], st["points"]), 240, 130, 2, pal.tan)
        self._cta(d, pal, "Mark Complete", ("resolve_side_quest",), y=340)
        self._cta(d, pal, "Leave as-is", ("skip_side_quest",), y=404, ok=False)

    def on_button(self, btn):
        g = self.game
        k = btn.id[0]
        if k == "do_flip":
            g.flip_to_b(); self.step = self._derive(); return "redraw"
        if k == "resolve_location":
            g.resolve_location_overflow(); self.step = self._derive(); return "redraw"
        if k == "pick_branch":
            self.branch_pick = btn.id[1]; self.step = self._derive(); return "redraw"
        if k == "randomize_branch":
            self.branch_pick = random.randrange(len(self.step["cards"]))
            self.step = self._derive(); return "redraw"
        if k == "do_advance":
            g.clear_and_advance(card_idx=self.step["card_idx"])
            self.force_advance = False
            self.branch_pick = None
            self.step = self._derive()
            return "redraw"
        if k == "declare_victory":
            g.set_game_over("victory")
            return "close"
        if k == "continue_without_victory":
            self.step = self._derive(); return "redraw"
        if k == "resolve_side_quest":
            i = self.step["idx"]
            g.log_event("Side quest %d completed (resolution)" % (i + 1))
            g.side_quests.pop(i)
            self.step = self._derive()
            return "redraw"
        if k == "skip_side_quest":
            self._skipped_side_quests.append(g.side_quests[self.step["idx"]])
            self.step = self._derive()
            return "redraw"
        if k == "close":
            return "close"
        return None


class QuestCardModal:
    """Read-only stage/card reference (M4-B): opens on the game's current
    stage and pages through every stage of the loaded scenario snapshot
    (game.stages, copied at preload - no catalog re-read). Branch stages
    (multiple alternative cards) can be flipped between with the alt
    control; switching only changes what is displayed. Purely presentational
    - idx/card are the modal's own state, never written back to game."""

    MARGIN = 12
    # Ceiling, not a floor: the SIDE A/SIDE B blocks must end at or below this
    # y so the Tips button + pager (a fixed 88px: 48px gap + 40px pager tall,
    # themselves 40px tall) still fit above 480 with margin. _line_budget()
    # uses it to size each block's line cap per render (see below) instead of
    # a flat constant - short text no longer leaves Tips/pager stranded down
    # at a fixed position (they float up to meet the content), and long text
    # gets far more than the old flat 3-line cap when the other side is short.
    BOTTOM_Y0 = 380

    def __init__(self, game, tips=None):
        self.game = game
        self.idx = game.stage_idx if game.stages else 0
        self.card = game.card_idx if game.stages else 0
        self.buttons = []
        self.tips = tips or {}          # loaded tips.json "scenarios" map (M4-B tips)
        self.tips_open = False          # toggled by the Tips/Back button
        self._tips_data = None          # tips_for(...) result for the current stage, set by draw()

    def _wrap_body(self, d, text, w):
        """Word-wraps text (or the "no text" placeholder) at the block's
        usable width with no line cap - the "natural" line count
        _line_budget() then allocates space against."""
        usable = w - 20
        has_text = bool(text)
        body = text if has_text else "no text"
        lines = wrap_text(body, 1, usable, d.measure_text)
        return has_text, lines, usable

    def _line_budget(self, y0, natural_a, natural_b):
        """Distributes the pixel budget between y0 (top of the SIDE A block)
        and BOTTOM_Y0 across the two blocks' natural line counts: each gets
        its full natural count if both fit, otherwise the longer block is
        trimmed one line at a time (ties trim A first) until the total fits.
        Always leaves at least 1 line per block."""
        overhead = 26   # per block: 18px label row + 8px bottom pad
        gap = 12         # 6px trailing gap after each of the two blocks
        lh = 16          # 10*scale(1) + 6, one wrapped text line
        available_px = self.BOTTOM_Y0 - y0 - 2 * overhead - gap
        budget_lines = max(2, available_px // lh)
        allowed_a, allowed_b = natural_a, natural_b
        while allowed_a + allowed_b > budget_lines and (allowed_a > 1 or allowed_b > 1):
            if allowed_a >= allowed_b and allowed_a > 1:
                allowed_a -= 1
            elif allowed_b > 1:
                allowed_b -= 1
            else:
                allowed_a -= 1
        return allowed_a, allowed_b

    def _side_block(self, d, pal, x, y, w, label, wrapped, max_lines):
        """Bordered panel: a small label row + up to max_lines of the
        pre-wrapped body text (or the "no text" placeholder). Returns
        height."""
        has_text, lines, usable = wrapped
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            lines[-1] = truncate_text(lines[-1] + " ..", 1, usable, d.measure_text)
        lh = 16
        h = 18 + len(lines) * lh + 8
        panel(d, pal, x, y, w, h, fill=pal.card)
        text_left(d, pal, label, x + 10, y + 6, 1, pal.amber)
        ty = y + 20
        ink = pal.tan if has_text else pal.dim
        for ln in lines:
            text_left(d, pal, ln, x + 10, ty, 1, ink)
            ty += lh
        return h

    def _tips_panel(self, d, pal, x, y, w, tips_data, max_h):
        """Bordered panel: a "TIPS" label row, up to `max_h` px of wrapped
        tip lines (each prefixed "- "), and the attribution name + URL in
        pal.dim beneath - the tips-view counterpart of _side_block, sized
        against the same BOTTOM_Y0 ceiling so the Tips/Back button and
        pager land at the same y in either view. Excess content truncates
        its last visible line with ".." rather than overflowing into the
        button/pager area, mirroring _side_block's own truncate-to-fit.
        Returns height (always <= max_h)."""
        usable = w - 20
        lh = 16
        lines = []
        for t in tips_data["tips"]:
            lines.extend(wrap_text("- " + t, 1, usable, d.measure_text))
        attribution = tips_data.get("attribution") or {}
        name = attribution.get("name") or ""
        url = attribution.get("url") or ""
        attrib_lines = [truncate_text(s, 1, usable, d.measure_text)
                         for s in (("Source: " + name) if name else "", url) if s]

        overhead = 18 + 8   # label row + bottom pad, matches _side_block
        budget = max(1, (max_h - overhead - len(attrib_lines) * lh) // lh)
        if len(lines) > budget:
            lines = lines[:budget]
            lines[-1] = truncate_text(lines[-1] + " ..", 1, usable, d.measure_text)

        h = min(max_h, overhead + (len(lines) + len(attrib_lines)) * lh)
        panel(d, pal, x, y, w, h, fill=pal.card)
        text_left(d, pal, "TIPS", x + 10, y + 6, 1, pal.amber)
        ty = y + 20
        for ln in lines:
            text_left(d, pal, ln, x + 10, ty, 1, pal.tan)
            ty += lh
        for ln in attrib_lines:
            text_left(d, pal, ln, x + 10, ty, 1, pal.dim)
            ty += lh
        return h

    def draw(self, hw, game, pal):
        from ui.header import modal_header
        d = hw.display
        self.buttons = []
        d.set_pen(pal.bg)
        d.clear()
        modal_header(d, pal, game, "QUEST CARD", self.buttons)
        M, W = self.MARGIN, 480 - 2 * self.MARGIN

        if not game.stages:
            text_center(d, pal, "No quest loaded", 240, 200, 2, pal.dim)
            text_center(d, pal, "Start a scenario to see stage cards.", 240, 226, 1, pal.dim)
            return

        n = len(game.stages)
        self.idx = max(0, min(self.idx, n - 1))
        stage = game.stages[self.idx]
        cards = stage["cards"]
        self.card = max(0, min(self.card, len(cards) - 1))
        card = cards[self.card]
        # Front is side A; the back is whatever non-A side this printing uses.
        # Most cards are A/B, but epic multiplayer variants share one A front
        # with backs C..H (e.g. Mount Gundabad stage 2 has 7 alternatives),
        # so matching "B" literally would blank all but the first.
        faces = card["faces"]
        a_face = next((f for f in faces if f["side"] == "A"), faces[0] if faces else {})
        b_face = next((f for f in faces if f["side"] and f["side"] != "A"),
                      faces[1] if len(faces) > 1 else {})
        a_name = a_face.get("name") or ""
        b_name = b_face.get("name") or ""

        # -- stage line: number, an A/B legend, and a CURRENT marker so
        # paging away from the game's live stage is obvious -----------------
        y = 48
        text_left(d, pal, "STAGE %d" % stage["stage"], M, y, 2, pal.amber)
        ab_hint = "A / B"
        text_left(d, pal, ab_hint, 480 - M - d.measure_text(ab_hint, 1), y + 4, 1, pal.dim)
        if self.idx == game.stage_idx:
            pw = d.measure_text("CURRENT", 1) + 14
            px = 240 - pw // 2
            d.set_pen(pal.gold)
            d.rectangle(px, y, pw, 18)
            text_center(d, pal, "CURRENT", 240, y + 4, 1, pal.bg, shadow=False)
        y += 28

        # -- card name(s): a shared name shows once; a branch payoff (the
        # B-face name differs, e.g. "A Chosen Path" -> "Beorn's Path") shows
        # both, labelled -----------------------------------------------------
        if b_name and b_name != a_name:
            text_left(d, pal, truncate_text("A: " + a_name, 2, W, d.measure_text), M, y, 2, pal.gold)
            y += 22
            text_left(d, pal, truncate_text("B: " + b_name, 2, W, d.measure_text), M, y, 2, pal.gold)
            y += 26
        else:
            name = a_name or b_name or "(unnamed)"
            text_center(d, pal, truncate_text(name, 3, W, d.measure_text), 240, y, 3, pal.gold)
            y += 32

        # -- quest points / victory / sailing stat strip ---------------------
        cx = M + 16
        text_left(d, pal, "PTS", M, y, 1, pal.dim)
        token(d, pal, cx, y + 22, 14, 2, card.get("questPoints", 0), pal.gold, 0, pal.gold, pal.dim)
        nx = cx + 40
        if card.get("victory") is not None:
            text_left(d, pal, "VP", nx - 14, y, 1, pal.dim)
            token(d, pal, nx, y + 22, 14, 2, card["victory"], pal.gold, 0, pal.gold, pal.dim)
            nx += 40
        if card.get("sailing"):
            text_left(d, pal, "SAIL", nx - 16, y, 1, pal.dim)
            disc(d, nx, y + 22, 14, pal.well)
            icons.draw(d, icons.WHEEL_SM, nx - 8, y + 14, pal.gold)
        y += 46

        # -- branch: which alternative is displayed only affects the view ----
        if len(cards) > 1:
            label = {"random": "BRANCH - random",
                     "choice": "BRANCH - first player chooses"}.get(stage.get("branch"), "BRANCH")
            text_left(d, pal, truncate_text(label, 2, 480 - 2 * M - 162, d.measure_text),
                      M, y + 12, 2, pal.amber)
            alt = Button(("alt",), 480 - M - 150, y, 150, 36)
            bevel(d, pal, alt.x, alt.y, alt.w, alt.h, pal.btn)
            text_center(d, pal, "Card %d / %d" % (self.card + 1, len(cards)),
                        alt.x + alt.w / 2, alt.y + 12, 1, pal.tan)
            self.buttons.append(alt)
            y += 44

        # -- SIDE A/B card text, or (M4-B tips) the tips panel in its place --
        self._tips_data = tips_for(
            (self.game.scenario or {}).get("slug"), stage["stage"], self.tips)
        if self.tips_open and self._tips_data:
            y += self._tips_panel(d, pal, M, y, W, self._tips_data, self.BOTTOM_Y0 - y) + 6
        else:
            self.tips_open = False   # nothing to show (e.g. paged to an untipped stage)
            wrap_a = self._wrap_body(d, a_face.get("text"), W)
            wrap_b = self._wrap_body(d, b_face.get("text"), W)
            max_a, max_b = self._line_budget(y, len(wrap_a[1]), len(wrap_b[1]))
            y += self._side_block(d, pal, M, y, W, "SIDE A - setup / story", wrap_a, max_a) + 6
            y += self._side_block(d, pal, M, y, W, "SIDE B - quest", wrap_b, max_b) + 6

        # -- Tips: enabled (normal palette) only where tips exist for this
        # stage; toggles the tips panel above in place of the SIDE A/B blocks
        # (M4-B tips) --------------------------------------------------------
        tips = Button(("tips",), M, y, 140, 40)
        bevel(d, pal, tips.x, tips.y, tips.w, tips.h, pal.btn)
        if self._tips_data:
            n = len(self._tips_data["tips"])
            text_center(d, pal, "Back" if self.tips_open else "Tips", tips.x + 70, tips.y + 6, 2, pal.tan)
            sub = "to card" if self.tips_open else ("%d note%s" % (n, "" if n == 1 else "s"))
            text_center(d, pal, sub, tips.x + 70, tips.y + 26, 1, pal.dim)
        else:
            text_center(d, pal, "Tips", tips.x + 70, tips.y + 6, 2, pal.dim)
            text_center(d, pal, "none yet", tips.x + 70, tips.y + 26, 1, pal.dim)
        self.buttons.append(tips)

        # -- pager: hidden (not just disabled) at each end --------------------
        py = y + 48
        if self.idx > 0:
            prev = Button(("prev",), M, py, 110, 40)
            bevel(d, pal, prev.x, prev.y, prev.w, prev.h, pal.btn)
            text_center(d, pal, "< Prev", prev.x + 55, prev.y + 12, 2, pal.tan)
            self.buttons.append(prev)
        if self.idx < n - 1:
            nxt = Button(("next",), 480 - M - 110, py, 110, 40)
            bevel(d, pal, nxt.x, nxt.y, nxt.w, nxt.h, pal.btn)
            text_center(d, pal, "Next >", nxt.x + 55, nxt.y + 12, 2, pal.tan)
            self.buttons.append(nxt)
        text_center(d, pal, "stage %d of %d" % (self.idx + 1, n), 240, py + 12, 2, pal.muted)

    def on_button(self, btn):
        k = btn.id[0]
        if k == "close":
            return "close"
        if k == "tips":
            if self._tips_data:
                self.tips_open = not self.tips_open
                return "redraw"
            return None
        if not self.game.stages:
            return None
        n = len(self.game.stages)
        if k == "next":
            if self.idx < n - 1:
                self.idx += 1
                self.card = 0
                return "redraw"
            return None
        if k == "prev":
            if self.idx > 0:
                self.idx -= 1
                self.card = 0
                return "redraw"
            return None
        if k == "alt":
            cards = self.game.stages[self.idx]["cards"]
            if len(cards) > 1:
                self.card = (self.card + 1) % len(cards)
                return "redraw"
            return None
        return None


def _sq_radio(d, pal, cx, cy, on):
    """Radio-button glyph: ring, filled when selected. Duplicates
    ui/screen_quest.py's _radio (this codebase's screen/modal helpers are
    per-file, not cross-imported - e.g. _footer/footer and circ_btn/circBtn
    already exist independently in this file vs. the web twin) so
    SideQuestPickModal can "feel like the same family" as ChooseScenarioScreen
    without a new cross-module dependency."""
    arc_runs(d, cx, cy, 10, 8, 0, 360, pal.gold if on else pal.dim)
    if on:
        disc(d, cx, cy, 5, pal.gold)


class SideQuestPickModal:
    """Picker over the player side-quest catalog (M4-B sidequest, Task 2):
    radio-select list (name / points / sphere), Up/Down pager (mirrors
    ChooseScenarioScreen/PickCycleScreen in ui/screen_quest.py - same row
    stride/pager geometry, same radio glyph), plus Add (commits the
    selection) and Manual (today's blank-entry fallback, unchanged shape).

    Opened from QuestingProgressModal's "+ Side quest" button via the
    pending_side_quest_pick flag (see main.py's loop) - constructed with the
    already-loaded catalog entries (quest_catalog.side_quests(...) shape:
    {"id","name","points","sphere","pack"}), never reads the catalog itself.

    Empty `entries` (no catalog data) still renders and offers Manual rather
    than raising - defense in depth. The call site is expected to skip
    opening this modal entirely when load_player_side_quests() comes back
    empty and append directly instead (today's behavior, Global Constraints:
    catalog data is optional at runtime), but nothing here assumes that."""

    PER_PAGE = 6
    ROW_H = 44
    ROW_STRIDE = 46
    LIST_Y0 = 66
    NAME_MAX_W = 300
    FOOTER_Y = 404
    FOOTER_H = 64

    def __init__(self, game, entries):
        self.game = game
        self.entries = entries
        self.selected = entries[0]["id"] if entries else None
        self.page = 0
        self.buttons = []

    def _pages(self):
        return max(1, -(-len(self.entries) // self.PER_PAGE))

    def draw(self, hw, game, pal):
        from ui.header import modal_header
        d = hw.display
        self.buttons = []
        d.set_pen(pal.bg)
        d.clear()
        modal_header(d, pal, game, "Add Side Quest", self.buttons)

        if not self.entries:
            text_center(d, pal, "No side-quest catalog data available.", 240, 140, 2, pal.dim)
            text_center(d, pal, "Use Manual entry below.", 240, 168, 1, pal.dim)
        else:
            text_left(d, pal, "Pick a side quest, then Add - or enter manually.",
                      12, 46, 1, pal.dim)
            pages = self._pages()
            self.page = min(self.page, pages - 1)
            chunk = self.entries[self.page * self.PER_PAGE:(self.page + 1) * self.PER_PAGE]
            y = self.LIST_Y0
            for e in chunk:
                on = e["id"] == self.selected
                if on:
                    d.set_pen(pal.card_hi)
                    d.rectangle(8, y, 456, self.ROW_H)
                _sq_radio(d, pal, 30, y + 22, on)
                name = truncate_text(e.get("name") or "", 2, self.NAME_MAX_W, d.measure_text)
                text_left(d, pal, name, 52, y + 13, 2, pal.tan if on else pal.muted)
                pts_s = "%d pts" % (e.get("points") or 0)
                pw = d.measure_text(pts_s, 2)
                text_left(d, pal, pts_s, 456 - pw, y + 4, 2, pal.gold if on else pal.tan)
                # ASCII hyphen, not an em-dash - the device pins PicoGraphics'
                # "bitmap8" font (hardware.py), which only covers the
                # standard-ASCII glyphs verified in tests/fake_hardware.py's
                # BITMAP8_W table; a real dash character risks a blank/tofu
                # glyph on hardware even though it renders fine in this host
                # preview (PIL/Menlo has full Unicode coverage, masking it).
                sphere_s = e.get("sphere") or "-"
                sw = d.measure_text(sphere_s, 1)
                text_left(d, pal, sphere_s, 456 - sw, y + 26, 1, pal.dim)
                d.set_pen(pal.border)
                d.rectangle(8, y + self.ROW_H, 456, 1)
                self.buttons.append(Button(("row", e["id"]), 8, y, 456, self.ROW_H))
                y += self.ROW_STRIDE

            if pages > 1:
                up = Button(("older",), 12, 352, 150, 46)
                dn = Button(("newer",), 318, 352, 150, 46)
                bevel(d, pal, up.x, up.y, up.w, up.h, pal.btn)
                text_center(d, pal, "Up", up.x + 75, up.y + 14, 2, pal.tan)
                bevel(d, pal, dn.x, dn.y, dn.w, dn.h, pal.btn)
                text_center(d, pal, "Down", dn.x + 75, dn.y + 14, 2, pal.tan)
                text_center(d, pal, "%d/%d" % (self.page + 1, pages), 240, 366, 2, pal.muted)
                self.buttons.append(up)
                self.buttons.append(dn)

        manual = Button(("manual",), 24, self.FOOTER_Y, 200, self.FOOTER_H)
        bevel(d, pal, manual.x, manual.y, manual.w, manual.h, pal.btn, t=3)
        text_center(d, pal, "Manual", manual.x + manual.w / 2, manual.y + 20, 2, pal.tan)
        self.buttons.append(manual)

        if self.entries:
            add = Button(("add",), 256, self.FOOTER_Y, 200, self.FOOTER_H)
            bevel(d, pal, add.x, add.y, add.w, add.h, pal.btn_ok, t=3)
            text_center(d, pal, "Add", add.x + add.w / 2, add.y + 20, 2, pal.ok_fg)
            self.buttons.append(add)

    def on_button(self, btn):
        k = btn.id[0]
        if k == "close":
            return "close"
        if k == "row":
            self.selected = btn.id[1]
            return "redraw"
        if k == "older":
            self.page = max(0, self.page - 1)
            return "redraw"
        if k == "newer":
            self.page = min(self._pages() - 1, self.page + 1)
            return "redraw"
        if k == "manual":
            self.game.side_quests.append({"points": 0, "progress": 0})
            self.game.log_event("Side quest added manually (progress view)")
            return "close"
        if k == "add":
            e = next((x for x in self.entries if x["id"] == self.selected), None)
            if e:
                pts = e.get("points") or 0
                self.game.side_quests.append({"points": pts, "progress": 0,
                                              "name": e.get("name")})
                self.game.log_event("Side quest added: %s (%d pts, progress view)"
                                    % (e.get("name"), pts))
            return "close"
        return None
