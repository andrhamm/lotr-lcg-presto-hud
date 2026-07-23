"""Full-screen config + allocation modals.

Each modal mutates the passed GameState directly on confirm. Protocol:
  draw(hw, game, pal)  -> renders, rebuilds self.buttons
  on_button(btn)       -> "close" (save+dismiss), "cancel" (dismiss), or None
"""

from ui.widgets import (Button, panel, bevel, text_center, text_left, button,
                        stepper, draw_weather)
from ui import icons
from gamestate import HEADINGS

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


class QuestingForModal:
    """Per-player willpower commits in one view — player-settings layout with
    willpower coloring and the sunburst as a currency mark. Save applies and
    logs each change; Cancel discards."""

    def __init__(self, game):
        self.game = game
        self.vals = [p.commit for p in game.players]
        self.buttons = []

    def draw(self, hw, game, pal):
        d = hw.display
        self.buttons = []
        d.set_pen(pal.bg)
        d.clear()
        text_center(d, pal, "Questing for...", 240, 22, 3, pal.gold)

        y = 74
        for i, p in enumerate(self.game.players):
            if p.eliminated:
                continue
            text_left(d, pal, "P%d" % (i + 1), 30, y + 16, 3, pal.tan)
            mn = Button(("wpm", i, -1), 108, y + 4, 52, 48)
            pl = Button(("wpm", i, 1), 340, y + 4, 52, 48)
            for b, s in ((mn, "-"), (pl, "+")):
                bevel(d, pal, b.x, b.y, b.w, b.h, pal.btn)
                text_center(d, pal, s, b.x + 26, b.y + 12, 3, pal.tan)
                self.buttons.append(b)
            v = str(self.vals[i])
            vw = d.measure_text(v, 3)
            gx = int(250 - (vw + 8 + 28) / 2)
            text_left(d, pal, v, gx, y + 16, 3, pal.gold)
            icons.draw(d, icons.WILLPOWER_MD, gx + vw + 8, y + 14, pal.gold)
            y += 62

        total = sum(self.vals[i] for i, p in enumerate(self.game.players)
                    if not p.eliminated)
        tv = str(total)
        tw = d.measure_text("Total  " + tv, 3)
        text_left(d, pal, "Total", 30, y + 18, 2, pal.muted)
        vw = d.measure_text(tv, 3)
        gx = int(250 - (vw + 8 + 28) / 2)
        text_left(d, pal, tv, gx, y + 14, 3, pal.gold)
        icons.draw(d, icons.WILLPOWER_MD, gx + vw + 8, y + 12, pal.gold)

        _footer(d, pal, self.buttons)

    def on_button(self, btn):
        k = btn.id[0]
        if k == "wpm":
            i, delta = btn.id[1], btn.id[2]
            self.vals[i] = max(0, min(99, self.vals[i] + delta))
            return None
        if k == "save":
            for i, p in enumerate(self.game.players):
                if p.eliminated:
                    continue
                before = p.commit
                if self.vals[i] != before:
                    self.game.set_commit(i, self.vals[i])
                    self.game.log_event("P%d committed %d willpower"
                                        % (i + 1, self.vals[i]))
            return "close"
        if k == "cancel":
            return "cancel"
        return None


class RemindersModal:
    """Encounter reminders — log-style header (R# left, X right). Checkboxes
    enable a timed toast at the start of the matching phase view."""

    def __init__(self, game):
        self.game = game
        self.buttons = []

    def draw(self, hw, game, pal):
        from gamestate import REMINDER_DEFS
        d = hw.display
        self.buttons = []
        d.set_pen(pal.bg)
        d.clear()
        text_left(d, pal, "R%d %s" % (self.game.round, self.game.step), 10, 12, 2, pal.muted)
        text_center(d, pal, "Encounter Reminders", 240, 12, 2, pal.gold)
        w = d.measure_text("X", 3)
        text_left(d, pal, "X", 480 - 16 - w, 8, 3, pal.no_fg)
        self.buttons.append(Button(("close",), 330, 0, 150, 40))
        d.set_pen(pal.border)
        d.rectangle(0, 40, 480, 1)

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
    """All questing progress in one place: main quest, active location and each
    side quest (progress + quest-points editable), add/remove side quests, and
    the heading shift when sailing. Value edits are logged on close."""

    def __init__(self, game):
        self.game = game
        self.buttons = []
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
        items = [{"kind": "q", "name": "Quest %s" % g.quest_label()}]
        if g.active_location:
            items.append({"kind": "l", "name": "Location", "removable": True})
        for i, s in enumerate(g.side_quests):
            items.append({"kind": "s", "idx": i, "name": "Side Quest %d" % (i + 1),
                          "sub": s.get("since"), "removable": True})
        return items

    def _row(self, d, pal, it, y):
        g = self.game
        if it["kind"] == "q":
            prog, pts, pfx = g.quest["progress"], g.quest["points"], "q"
        elif it["kind"] == "l":
            prog, pts, pfx = g.active_location["progress"], g.active_location["points"], "l"
        else:
            s = g.side_quests[it["idx"]]
            prog, pts, pfx = s["progress"], s["points"], "s"
        panel(d, pal, 12, y, 456, 58)
        text_left(d, pal, it["name"], 22, y + 8, 2, pal.tan)
        if it.get("sub"):
            text_left(d, pal, "since %s" % it["sub"], 22, y + 32, 1, pal.dim)
        idx = it.get("idx")
        text_left(d, pal, "current", 166, y + 2, 1, pal.muted)
        stepper(d, pal, self.buttons, (pfx + "P-", idx), (pfx + "P+", idx), 164, y + 12, str(prog), 130, 42)
        text_left(d, pal, "points", 304, y + 2, 1, pal.muted)
        stepper(d, pal, self.buttons, (pfx + "T-", idx), (pfx + "T+", idx), 300, y + 12, str(pts), 130, 42)
        if it.get("removable"):
            rm = Button((pfx + "X", idx), 436, y + 15, 36, 36)
            bevel(d, pal, rm.x, rm.y, rm.w, rm.h, pal.btn_no)
            text_center(d, pal, "x", rm.x + 18, rm.y + 10, 2, pal.no_fg)
            self.buttons.append(rm)

    def draw(self, hw, game, pal):
        d = hw.display
        self.buttons = []
        d.set_pen(pal.bg)
        d.clear()
        text_left(d, pal, "R%d %s" % (self.game.round, self.game.step), 10, 12, 2, pal.muted)
        text_center(d, pal, "Questing Progress", 240, 12, 2, pal.gold)
        text_left(d, pal, "X", 480 - 16 - d.measure_text("X", 3), 8, 3, pal.no_fg)
        self.buttons.append(Button(("close",), 330, 0, 150, 40))
        d.set_pen(pal.border)
        d.rectangle(0, 40, 480, 1)
        y = 48
        for it in self._items():
            self._row(d, pal, it, y)
            y += 62
        add = Button(("add",), 12, y, 456, 38)
        bevel(d, pal, add.x, add.y, add.w, add.h, pal.btn)
        text_center(d, pal, "+ Add side quest", 240, y + 11, 2, pal.tan)
        self.buttons.append(add)
        y += 46
        if self.game.sailing:
            h = self.game.heading
            pen = pal.gold if h == 0 else (pal.red if h == 3 else pal.amber)
            panel(d, pal, 12, y, 456, 52)
            text_left(d, pal, "Heading", 22, y + 18, 2, pal.tan)
            draw_weather(d, pal, h, 176, y + 26, 12)
            text_left(d, pal, HEADINGS[h][2], 196, y + 18, 2, pen)
            mn = Button(("hd", -1), 320, y + 10, 60, 32)
            pl = Button(("hd", 1), 388, y + 10, 60, 32)
            button(d, pal, mn, "-", 3)
            button(d, pal, pl, "+", 3)
            self.buttons.append(mn)
            self.buttons.append(pl)
        done = Button(("close",), 12, 430, 456, 42)
        bevel(d, pal, done.x, done.y, done.w, done.h, pal.btn_ok, t=3)
        text_center(d, pal, "Done", 240, 442, 2, pal.ok_fg)
        self.buttons.append(done)

    def _clamp_adj(self, cur, delta):
        return max(0, min(99, cur + delta))

    def on_button(self, btn):
        k = btn.id[0]
        a = btn.id[1] if len(btn.id) > 1 else None
        g = self.game
        up = k.endswith("+")
        if k in ("qP-", "qP+"):
            g.quest["progress"] = self._clamp_adj(g.quest["progress"], 1 if up else -1)
            return None
        if k in ("qT-", "qT+"):
            g.quest["points"] = self._clamp_adj(g.quest["points"], 1 if up else -1)
            return None
        if k in ("lP-", "lP+"):
            g.active_location["progress"] = self._clamp_adj(g.active_location["progress"], 1 if up else -1)
            g.explore_location_if_done()
            return None
        if k in ("lT-", "lT+"):
            g.active_location["points"] = self._clamp_adj(g.active_location["points"], 1 if up else -1)
            return None
        if k == "lX":
            g.active_location = None
            g.log_event("Active location cleared (progress view)")
            return None
        if k in ("sP-", "sP+"):
            s = g.side_quests[a]
            s["progress"] = self._clamp_adj(s["progress"], 1 if up else -1)
            return None
        if k in ("sT-", "sT+"):
            s = g.side_quests[a]
            s["points"] = self._clamp_adj(s["points"], 1 if up else -1)
            return None
        if k == "sX":
            g.side_quests.pop(a)
            g.log_event("Side quest %d removed (progress view)" % (a + 1))
            return None
        if k == "add":
            g.side_quests.append({"points": 4, "progress": 0,
                                  "since": "R%d %s" % (g.round, g.step)})
            g.log_event("Side quest %d added (progress view)" % len(g.side_quests))
            return None
        if k == "hd":
            g.shift_heading(a, "progress view")
            return None
        if k == "close":
            self._log_changes()
            return "close"
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
        d = hw.display
        self.buttons = []
        d.set_pen(pal.bg)
        d.clear()
        text_left(d, pal, "R%d %s" % (self.game.round, self.game.step), 10, 12, 2, pal.muted)
        text_center(d, pal, "Sailing test", 240, 12, 2, pal.gold)
        text_left(d, pal, "X", 480 - 16 - d.measure_text("X", 3), 8, 3, pal.no_fg)
        self.buttons.append(Button(("cancel",), 330, 0, 150, 40))
        d.set_pen(pal.border)
        d.rectangle(0, 40, 480, 1)

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
        if k == "cancel":
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
