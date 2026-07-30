"""Full-screen config + allocation modals.

Each modal mutates the passed GameState directly on confirm. Protocol:
  draw(hw, game, pal)  -> renders, rebuilds self.buttons
  on_button(btn)       -> "close" (save+dismiss), "cancel" (dismiss), or None
"""

import random

from ui.widgets import (Button, panel, bevel, text_center, text_left, button,
                        stepper, draw_weather, token, circ_btn, disc, arc_runs,
                        ring, wx_small, wrap_text, truncate_text, ribbon, ribbon_h,
                        stat_pill, phase_block, BAND_PAD, band_line_h,
                        prog_row_card, fill_bar, glyph, stepper_cluster,
                        ROW_H as W_ROW_H, ROW_H_COMPACT as W_ROW_H_COMPACT)
from ui.counter import CounterState
from viewcopy import PROGRESS_PLACEMENT

# Card gutter, matching the play screen's own band inset.
MARGIN = 8
import xtargets
from ui import icons
from gamestate import HEADINGS
from ui.theme import DISPLAY, BODY, LABEL
from quest_catalog import tips_for

CANCEL_Y = 404
BTN_H = 64


def _footer(d, pal, buttons, save_label="Save"):
    no = Button(("cancel",), 24, CANCEL_Y, 200, BTN_H)
    ok = Button(("save",), 256, CANCEL_Y, 200, BTN_H)
    bevel(d, pal, no.x, no.y, no.w, no.h, pal.btn_no, t=3)
    text_center(d, pal, "Cancel", no.x + no.w / 2, no.y + 20, BODY, pal.no_fg)
    bevel(d, pal, ok.x, ok.y, ok.w, ok.h, pal.btn_ok, t=3)
    text_center(d, pal, save_label, ok.x + ok.w / 2, ok.y + 20, BODY, pal.ok_fg)
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
        text_center(d, pal, "P%d settings" % (self.i + 1), 240, 24, DISPLAY, pal.gold)

        icons.draw(d, icons.THREAT, 30, 92, pal.red)
        text_left(d, pal, "Starting threat", 58, 96, BODY, pal.tan)
        stepper(d, pal, self.buttons, ("st", -1), ("st", 1), 260, 82, str(self.st), 190, 56)

        icons.draw(d, icons.THREAT, 30, 172, pal.red)
        text_left(d, pal, "Threat / round", 58, 176, BODY, pal.tan)
        stepper(d, pal, self.buttons, ("tpr", -1), ("tpr", 1), 260, 162, str(self.tpr), 190, 56)

        icons.draw(d, icons.THREAT, 30, 252, pal.red)
        text_left(d, pal, "Elimination level", 58, 256, BODY, pal.tan)
        stepper(d, pal, self.buttons, ("el", -1), ("el", 1), 260, 242, str(self.elim), 190, 56)
        text_left(d, pal, "eliminated when threat reaches this (50 std)", 30, 306, BODY, pal.dim)

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
        # What it looked like on the way in, so close can log ONE summary line
        # instead of one per stepper tap.
        self._was = (self.q["stage_n"], self.q["side"], self.q["points"],
                     self.q["progress"])

    def _apply(self):
        """Write the edit through NOW. The sheet has no Save, so every tap
        lands here - the same live-edit model PlayersDetailModal and the
        location sheet use."""
        self.game.quest = dict(self.q)

    def draw(self, hw, game, pal):
        from ui.header import modal_header
        d = hw.display
        self.buttons = []
        d.set_pen(pal.bg)
        d.clear()
        modal_header(d, pal, game,
                     "Quest  %d%s" % (self.q["stage_n"], self.q["side"]),
                     self.buttons, cta=None,
                     back=("< Progress", ("close",)))

        text_left(d, pal, "Stage number", 30, 84, BODY, pal.tan)
        stepper(d, pal, self.buttons, ("n", -1), ("n", 1), 300, 70, str(self.q["stage_n"]), 150, 52)

        # side cycles A-H (multi-variant quests go beyond A/B - DragnCards data)
        text_left(d, pal, "Side", 30, 156, BODY, pal.tan)
        stepper(d, pal, self.buttons, ("side", -1), ("side", 1), 300, 142, self.q["side"], 150, 52)

        # A stage that advances on a condition has no quest points to edit, so
        # the stepper is replaced by the card's own sentence about how the
        # stage ends (distilled from its printed text - see
        # tools/build_advancement.py). 177 stage cards are like this; a
        # stepper reading 0 invites the player to "fix" a number the card
        # never printed.
        if self.q.get("mode") == "condition" and self.q.get("advance"):
            text_left(d, pal, "Advances", 30, 214, BODY, pal.tan)
            ty = 236
            for ln in wrap_text(self.q["advance"], BODY, 420, d.measure_text)[:2]:
                text_left(d, pal, ln, 30, ty, BODY, pal.dim)
                ty += 22
            # 11 stages state BOTH: Return to Rhosgobel is won if Wilyador is
            # healed and lost otherwise. Showing only the win is showing half
            # the rule, so the loss gets the red pen it deserves.
            if self.q.get("lose"):
                for ln in wrap_text(self.q["lose"], BODY, 420,
                                    d.measure_text)[:1]:
                    text_left(d, pal, ln, 30, ty, BODY, pal.no_fg)
                    ty += 22
        else:
            label = "Quest points"
            if self.q.get("x"):
                label = "Quest points = X"
            text_left(d, pal, label, 30, 228, BODY, pal.tan)
            stepper(d, pal, self.buttons, ("pts", -1), ("pts", 1), 300, 214,
                    str(self.q["points"]), 150, 52)

        text_left(d, pal, "Sailing quest", 30, 296, BODY, pal.tan)
        icons.draw(d, icons.WHEEL, 176, 292, pal.gold if self.sail else pal.dim)
        sb = Button(("sail",), 300, 284, 150, 48)
        panel(d, pal, sb.x, sb.y, sb.w, sb.h, fill=pal.gold if self.sail else pal.btn)
        text_center(d, pal, "On" if self.sail else "Off", sb.x + 75, sb.y + 14, BODY,
                    pal.bg if self.sail else pal.tan, shadow=False)
        self.buttons.append(sb)

        # A catalog game advances through the GUIDED flow, which knows about
        # branch alternatives, victory and the location credit. A custom game
        # has no ResolutionModal to open, so it keeps the manual edit it has
        # always had. Showing both would be two buttons named "advance" that
        # do different things.
        if game.stages:
            # The only way in for a stage with no quest points: ~137 of ~400
            # stage cards advance on a condition, so there is no target to
            # cross and nothing to trigger the flow on its own.
            fa = Button(("force_adv",), 30, 344, 205, 48)
            bevel(d, pal, fa.x, fa.y, fa.w, fa.h, pal.btn)
            text_center(d, pal, "Advance anyway", fa.x + fa.w / 2, fa.y + 14,
                        BODY, pal.tan)
            self.buttons.append(fa)
            vc = Button(("quest_card",), 245, 344, 205, 48)
            bevel(d, pal, vc.x, vc.y, vc.w, vc.h, pal.btn)
            text_center(d, pal, "View quest card", vc.x + vc.w / 2, vc.y + 14,
                        BODY, pal.tan)
            self.buttons.append(vc)
        else:
            adv = Button(("adv",), 30, 344, 420, 48)
            bevel(d, pal, adv.x, adv.y, adv.w, adv.h, pal.btn)
            text_center(d, pal, "Advance stage (progress -> 0)", adv.x + adv.w / 2, adv.y + 14, BODY, pal.tan)
            self.buttons.append(adv)

        # No Done and no Cancel: every tap has already landed on the game.
        # The sheet edits a live copy the way PlayersDetailModal does, so the
        # only control it needs is the way back - and this sheet is reached
        # from the Progress row's chevron, which is where it returns to.

    def on_button(self, btn):
        k = btn.id[0]
        if k == "n":
            self.q["stage_n"] = max(1, min(9, self.q["stage_n"] + btn.id[1]))
            self._apply()
            return None
        if k == "side":
            i = (ord(self.q["side"][0]) - 65 + btn.id[1] + 8) % 8   # cycle A-H
            self.q["side"] = chr(65 + i)
            self._apply()
            return None
        if k == "pts":
            self.q["points"] = max(0, min(30, self.q["points"] + btn.id[1]))
            self._apply()
            return None
        if k == "adv":
            if self.q["side"] == "A":
                self.q["side"] = "B"
            else:
                self.q["side"] = "A"
                self.q["stage_n"] += 1
            self.q["progress"] = 0
            self._apply()
            return None
        if k == "force_adv":
            # One modal at a time, so flag and close - main.py opens
            # ResolutionModal on the next pass, same pattern as quest_card.
            self.game.pending_resolution = "forced"
            return "close"
        if k == "quest_card":
            self.game.pending_quest_card = True
            return "close"
        if k == "sail":
            self.sail = not self.sail
            if self.sail != self.game.sailing:
                self.game.sailing = self.sail
                self.game.log_event(
                    "Sailing enabled (Dream-chaser) - heading starts On-course"
                    if self.sail else "Sailing disabled")
                if self.sail:
                    self.game.heading = 0
            return None
        if k == "close":
            # One summary line for the whole visit - a log entry per stepper
            # tap would bury the round. Sailing logs as it happens, above,
            # because it is a game-wide switch rather than a value edit.
            now = (self.q["stage_n"], self.q["side"], self.q["points"],
                   self.q["progress"])
            if now != self._was:
                self.game.log_event(
                    "Quest set to stage %d%s, %d/%d progress"
                    % (self.q["stage_n"], self.q["side"],
                       self.q["progress"], self.q["points"]))
            self._apply()
            return "close"
        if k == "cancel":
            return "cancel"
        return None


class LocationConfigModal:
    def __init__(self, game, idx=0):
        self.game = game
        # WHICH seat this sheet edits. The row's chevron passes its own index;
        # everything else opens the first, which is the only one there is
        # unless one of the five two-location cards is in play.
        self.idx = idx
        loc = (game.active_locations[idx]
               if idx < len(game.active_locations) else None)
        self.has = loc is not None
        self.pts = loc["points"] if loc else 2
        self.prog = loc["progress"] if loc else 0
        self.name = (loc or {}).get("name")
        self.threat = (loc or {}).get("threat") or 0
        # The coded X: {"text", "target", "mul", "add"}. `text` is the card's
        # own words, shown as-is; `target` is the xtargets enum the count
        # control will be built from. See xtargets.py.
        self.threat_x = (loc or {}).get("threatX")
        self.threat_formula = (self.threat_x or {}).get("text")
        # How the threat row behaves, from the coded X (see xtargets.py):
        #   "auto"   a tracked value answers it - read-only, no stepper
        #   "count"  the player supplies a count the app does arithmetic on -
        #            read-only value PLUS a stepper on the count
        #   "bare"   the count IS the value - one stepper, no second number
        #   None     an ordinary editable number
        self.threat_count = (loc or {}).get("threatCount")
        self.threat_shape = None
        if self.threat_x:
            target = self.threat_x.get("target")
            if xtargets.auto_for(target):
                self.threat_shape = "auto"
            elif (self.threat_x.get("mul", 1) == 1
                  and not self.threat_x.get("add")):
                self.threat_shape = "bare"
            else:
                self.threat_shape = "count"
            self.threat_label = xtargets.label_for(target)
        # An X with no formula has no number to show yet, and 0 would be a
        # claim the card never made. Once the player taps "+" it is a real
        # value like any other.
        self.threat_blank = ((loc or {}).get("threatKind") == "x"
                             and not self.threat)
        self.buttons = []

    def _row(self, d, pal, y, label, value, key, blank=False):
        """One editable stat. `blank` draws an empty value slot instead of a
        number: the card prints X and nothing tells us what X is, and a 0 there
        is a claim the card never made. A DRAWN rule rather than a typed dash -
        at this size a dash is indistinguishable from the stepper's own "-",
        and the device font has 82 glyphs so an em-dash is not guaranteed."""
        text_left(d, pal, label, 30, y + 14, BODY, pal.tan)
        stepper(d, pal, self.buttons, (key, -1), (key, 1), 260, y,
                "" if blank else str(value), 190, 52)
        if blank:
            d.set_pen(pal.gold)
            d.rectangle(340, y + 25, 30, 3)

    def _computed(self, d, pal, y, label, value):
        """A value the CARD owns: read-only, no stepper. `label = X` states the
        chain rather than leaving the player to infer it from a note."""
        text_left(d, pal, label, 30, y + 14, BODY, pal.tan)
        lw = d.measure_text(label, BODY)
        text_left(d, pal, "= X", 36 + lw, y + 14, BODY, pal.dim)
        text_center(d, pal, "-" if value is None else str(value),
                    355, y + 10, DISPLAY, pal.gold)

    def _threat_block(self, d, pal, y):
        """The threat row, in whichever of the four shapes the card calls for.
        Returns the y to continue at."""
        shape = self.threat_shape
        if shape in ("auto", "count"):
            value = self._resolved()
            self._computed(d, pal, y, "Threat", value)
            # +40, not +34: the value is DISPLAY-sized (24px tall drawn at
            # y+10), so a 34 step put the formula's first line inside its
            # descender. The layout linter caught it on the tallest scene.
            y += 40
            for ln in wrap_text("X = " + (self.threat_formula or ""), BODY,
                               420, d.measure_text)[:2]:
                text_left(d, pal, ln, 50, y, BODY, pal.dim)
                y += 22
            if shape == "count":
                # The only thing the player can move. They answer "how many
                # enemies are in play?" by looking at the table; the app applies
                # the arithmetic, so nobody does it in their head, and the count
                # survives to next round when it changes by one.
                self._row(d, pal, y + 4, self.threat_label,
                          self.threat_count or 0, "count")
                y += 62
            else:
                y += 8
            return y
        # bare count, or an ordinary number: one stepper, no second value.
        self._row(d, pal, y, "Threat", self.threat, "threat",
                  blank=self.threat_blank)
        return y + 56

    def draw(self, hw, game, pal):
        d = hw.display
        self.buttons = []
        d.set_pen(pal.bg)
        d.clear()
        # Back rides in the title bar, not at the bottom: the count shape's
        # threat block pushes the action grid down past y=420, so a pinned
        # bottom button lands on top of "Replaced". Top-left is where the mock
        # puts it anyway, and it matches every other sub-view's way back.
        text_left(d, pal, "< Progress", 10, 12, BODY, pal.tan)
        self.buttons.append(Button(("close",), 0, 0, 150, 40))
        text_center(d, pal, "Active Location", 240, 12, DISPLAY, pal.gold)
        if self.name:
            text_center(d, pal, truncate_text(self.name, BODY, 440, d.measure_text),
                        240, 46, BODY, pal.tan)

        self._row(d, pal, 76, "Progress", self.prog, "prog")
        self._row(d, pal, 136, "Quest points", self.pts, "pts")
        # Threat is the location's staging contribution, and it is what "Back
        # to staging" has to add back. 34 of the catalog's X-printing location
        # faces print X HERE rather than on quest points, so this is the row
        # the X work actually shows up on.
        y = self._threat_block(d, pal, 196)
        if self.threat_formula and self.threat_shape == "bare":
            for ln in wrap_text("X = " + self.threat_formula, BODY, 420,
                                d.measure_text)[:2]:
                text_left(d, pal, ln, 30, y, BODY, pal.dim)
                y += 22
        elif self.threat_blank and not self.threat_x:
            # Only when the card defines X NOWHERE we can read. With a coded X
            # the formula line above already said where the number comes from,
            # and this contradicted it.
            text_left(d, pal, "the card prints X and defines it elsewhere",
                      30, y, BODY, pal.dim)
            y += 22

        # Clamped: the threat block is variable-height (a computed value, up to
        # two formula lines and a count stepper), and unclamped it walked into
        # the footer's Cancel/Save at y=404.
        # RR: progress is NOT lost when a location returns to the staging area -
        # Impassable Chasm has to SAY "remove all progress tokens", which it
        # would not need to if returning did it.
        if self.has and y < 296:
            text_left(d, pal, "Back to staging keeps its progress.",
                      30, y, BODY, pal.dim)
            y += 22
        # The four ways a location leaves, each NAMED. These used to be two
        # unlabelled 24px icon circles on the Progress row plus a vague
        # "Set none (no active location)" here, which is what "the additional
        # actions are not labeled, not clear what they do" was about.
        #
        # "Back to staging" is only honest because the record now carries the
        # card's threat: it can put the right number back without asking.
        # Follows y with a FLOOR only. The previous ceiling (min(..., 300))
        # pinned the grid at 300 however tall the threat block got, so in the
        # count shape - computed value, two formula lines and a count stepper,
        # ending near 342 - the actions were drawn straight through the stepper.
        y = max(y + 6, 288)
        acts = (("Explored", ("explored",), pal.green),
                ("Back to staging", ("tostaging",), pal.tan),
                ("Replaced", ("replaced",), pal.tan),
                ("Remove", ("none",), pal.no_fg))
        for i, (label, bid, pen) in enumerate(acts):
            bx = 30 + (i % 2) * 212
            by = y + (i // 2) * 50
            b = Button(bid, bx, by, 200, 44)
            if pen is pal.no_fg:
                panel(d, pal, b.x, b.y, b.w, b.h, fill=pal.btn_no,
                      border=pal.no_fg)
            else:
                bevel(d, pal, b.x, b.y, b.w, b.h, pal.btn, t=3)
            text_center(d, pal, label, b.x + b.w / 2, b.y + 12, BODY, pen)
            self.buttons.append(b)

        # No Done and no Cancel: there is nothing to commit. Every stepper tap
        # applies to the game immediately and logs, the way PlayersDetailModal
        # already works, so the only control this sheet needs is the way back -
        # drawn in the title bar at the top of this method. Two commit
        # affordances on a page with nothing to commit was the design note;
        # removing them also gives the threat block the 64px it needs in the
        # count shape, which no clamp could reclaim.

    def _apply(self):
        """Write the edit through to the game NOW.

        The sheet has no Save, so every tap lands here. Starts from the
        EXISTING record rather than replacing it - a wholesale replace used to
        drop the card name, its threat and the *Kind/*X keys the picker had
        just filled in.
        """
        g = self.game
        loc = dict(self._seat() or {})
        loc["points"] = self.pts
        loc["progress"] = self.prog
        if self.threat_shape in ("auto", "count"):
            # The count is the player's input and the threat is derived, so
            # store the COUNT and recompute - storing only the result would go
            # stale the moment the board changes.
            if self.threat_count is not None:
                loc["threatCount"] = self.threat_count
            loc["threat"] = self._resolved() or 0
        elif self.threat or not self.threat_blank:
            loc["threat"] = self.threat
        if self.idx < len(g.active_locations):
            g.active_locations[self.idx] = loc
        else:
            g.active_locations.append(loc)
            self.idx = len(g.active_locations) - 1

    def _seat(self):
        """The record this sheet edits, or None if the seat is empty."""
        return (self.game.active_locations[self.idx]
                if self.idx < len(self.game.active_locations) else None)

    def _leave(self):
        """Take this location out of the row. Returns the record it removed."""
        loc = self._seat()
        if loc is not None:
            del self.game.active_locations[self.idx]
        return loc

    def _resolved(self):
        g = self.game
        return xtargets.resolve(
            self.threat_x, count=self.threat_count,
            players=len(g.players),
            stage=g.quest.get("stage_n", 1),
            highest_threat=max([p.threat for p in g.players] or [0]))

    def on_button(self, btn):
        k = btn.id[0]
        if k == "pts":
            self.pts = max(1, min(30, self.pts + btn.id[1]))
            self.has = True
            self._apply()
            return None
        if k == "prog":
            self.prog = max(0, min(99, self.prog + btn.id[1]))
            self.has = True
            self._apply()
            return None
        if k == "count":
            self.threat_count = max(0, min(60, (self.threat_count or 0) + btn.id[1]))
            self.has = True
            self._apply()
            return None
        if k == "threat":
            self.threat = max(0, min(30, self.threat + btn.id[1]))
            self.threat_blank = False   # a tap makes it a real value
            self.has = True
            self._apply()
            return None
        if k == "none":
            if self._leave() is not None:
                self.game.log_event("Active location removed")
            return "close"
        if k == "explored":
            if self._leave() is not None:
                self.game.log_event("Active location Explored")
            return "close"
        if k == "tostaging":
            # The record carries the card's threat, so the staging total gets
            # the right number back rather than a guess. RR: progress is NOT
            # lost, so nothing is zeroed here.
            loc = self._leave() or {}
            back = loc.get("threat") or 0
            self.game.staging += back
            self.game.log_event("Active location to staging (+%d threat, "
                                "%d progress kept)"
                                % (back, loc.get("progress") or 0))
            return "close"
        if k == "replaced":
            # A card swapped it: reopen the picker in change mode rather than
            # making the player clear this one and add another.
            self.game.pending_location_pick = {"mode": "change",
                                               "back": "progress",
                                               "idx": self.idx}
            return "close"
        if k == "close":
            # One summary line for the whole visit, the way the Progress modal
            # batches its own edits - a log entry per stepper tap would bury
            # the round.
            if self.has:
                self.game.log_event("Active location set to %d/%d progress, "
                                    "%d threat"
                                    % (self.prog, self.pts, self.threat))
            return "close"
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
        text_center(d, pal, "Side quests", 240, 22, DISPLAY, pal.gold)
        sq = self.game.side_quests
        if not sq:
            text_center(d, pal, "none", 240, 90, DISPLAY, pal.dim)
        y = 70
        for i, s in enumerate(sq):
            panel(d, pal, 24, y, 432, 56, fill=pal.card)
            text_left(d, pal, "SQ%d  %d/%d" % (i + 1, s["progress"], s["points"]), 36, y + 18, BODY, pal.tan)
            mn = Button(("pts", i, -1), 214, y + 6, 44, 44)
            pl = Button(("pts", i, 1), 264, y + 6, 44, 44)
            # Completing a side quest was an unlabelled green pennant icon on
            # the Progress row. That row is a card with one big stepper now, so
            # the action lives here with a name on it - and it is a DIFFERENT
            # outcome from removing one: a completed side quest goes to the
            # victory display, a removed one never happened.
            dn = Button(("done", i), 320, y + 6, 60, 44)
            rm = Button(("rm", i), 392, y + 6, 52, 44)
            button(d, pal, mn, "-", DISPLAY)
            button(d, pal, pl, "+", DISPLAY)
            bevel(d, pal, dn.x, dn.y, dn.w, dn.h, pal.btn, t=3)
            text_center(d, pal, "Done", dn.x + dn.w / 2, dn.y + 13, BODY, pal.green)
            panel(d, pal, rm.x, rm.y, rm.w, rm.h, fill=pal.btn_no, border=pal.no_fg)
            text_center(d, pal, "x", rm.x + rm.w / 2, rm.y + 10, DISPLAY, pal.no_fg)
            self.buttons.extend([mn, pl, dn, rm])
            y += 62

        add = Button(("add",), 24, min(y, 320), 432, 52)
        panel(d, pal, add.x, add.y, add.w, add.h, fill=pal.btn)
        text_center(d, pal, "+ Add side quest", add.x + add.w / 2, add.y + 16, BODY, pal.tan)
        self.buttons.append(add)

        done = Button(("save",), 24, CANCEL_Y, 432, BTN_H)
        panel(d, pal, done.x, done.y, done.w, done.h, fill=pal.btn_ok, border=pal.ok_fg)
        text_center(d, pal, "Done", done.x + done.w / 2, done.y + 20, BODY, pal.ok_fg)
        self.buttons.append(done)

    def on_button(self, btn):
        k = btn.id[0]
        # Live edits, like PlayersDetailModal: Save only closes, so each
        # action logs as it happens rather than on commit.
        if k == "add":
            self.game.side_quests.append({"points": 4, "progress": 0})
            self.game.log_event("Side quest %d added (4 quest points)"
                                % len(self.game.side_quests))
            return None
        if k == "pts":
            i = btn.id[1]
            sq = self.game.side_quests[i]
            was = sq["points"]
            sq["points"] = max(1, min(30, was + btn.id[2]))
            if sq["points"] != was:
                self.game.log_event("Side quest %d quest points %d -> %d"
                                    % (i + 1, was, sq["points"]))
            return None
        if k == "done":
            # Completed, not removed: it goes to the victory display, so the log
            # has to say which of the two happened.
            i = btn.id[1]
            self.game.side_quests.pop(i)
            self.game.log_event("Side quest %d completed" % (i + 1))
            return None
        if k == "rm":
            self.game.side_quests.pop(btn.id[1])
            self.game.log_event("Side quest %d removed" % (btn.id[1] + 1))
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
        # Opening this view is what re-syncs the two sources. The per-player
        # values were never lost while the total was detached - they are just
        # no longer what the total says - so the moment the view that shows
        # them opens, they become the truth again and the pills stop showing
        # "?". See GameState.resync_willpower.
        game.resync_willpower()
        self.buttons = []
        self.edit = None   # (i, stat, CounterState) while the inline pad is open

    def _open_edit(self, i, stat):
        game = self.game
        cur = game.players[i].threat if stat == "threat" else game.players[i].commit
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

    # Row geometry. The old row was 56px tall with 24x24 targets - the bare
    # legal minimum for the most-tapped control in the app - while leaving
    # 252px of the screen empty. There is no reason to be stingy here: this
    # modal shows at most 4 rows on a 480px panel.
    ROW_H = 96            # was 56
    ROW_TOP = 124         # first row centre; 4 rows then fill to y=438
    STEP_DX = 52          # -/+ offset from the token centre
    STEP_R = 20           # drawn button radius (was 11)
    HIT = 52              # tap target, both axes (was 24)
    TOKEN_R = 22          # drawn token radius (was 14)
    # Proximity has to do the grouping work: at STEP_DX 60 the gap BETWEEN
    # the threat and willpower clusters was 8px - identical to the gap
    # inside each cluster - so the row read as six loose buttons instead of
    # two groups of three. Tightening each cluster and pushing the columns
    # apart makes the grouping legible, and a hairline divider seals it (the
    # same one the play screen draws between its two zones).

    def _editor_row(self, d, pal, i, key, cx, cy, value, frac, ring_fill):
        circ_btn(d, pal, cx - self.STEP_DX, cy, self.STEP_R, "-")
        circ_btn(d, pal, cx + self.STEP_DX, cy, self.STEP_R, "+")
        token(d, pal, cx, cy, self.TOKEN_R, 3, value, pal.value, frac,
              ring_fill, pal.dim, vscale=DISPLAY)
        h = self.HIT // 2
        self.buttons.append(Button((key, i, -1), cx - self.STEP_DX - h, cy - h,
                                   self.HIT, self.HIT))
        self.buttons.append(Button((key, i, "edit"), cx - h, cy - h,
                                   self.HIT, self.HIT))
        self.buttons.append(Button((key, i, 1), cx + self.STEP_DX - h, cy - h,
                                   self.HIT, self.HIT))

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
        threat_x, will_x, label_x = 160, 360, 33
        # Column headers are the same ICONS the play screen uses - the red
        # threat helm and the gold willpower star - not ALL-CAPS LABEL text.
        # A player already reads these glyphs on the play screen; repeating
        # them here is what makes this modal recognisably the same data.
        # 2x scale: at 1x (20px) they read as afterthoughts against 52px
        # controls and DISPLAY numerals. The masks are 1-bit, so scaling is
        # exact - no resampling.
        icons.draw(d, icons.THREAT, threat_x - 19, 49, pal.bevel_d, scale=2)
        icons.draw(d, icons.THREAT, threat_x - 20, 48, pal.red, scale=2)
        icons.draw(d, icons.WILLPOWER, will_x - 20, 48, pal.gold, scale=2)
        n = len(game.players)
        d.set_pen(pal.border)
        d.rectangle(260, 40, 1, self.ROW_TOP - 40 + n * self.ROW_H - 30)
        for i, p in enumerate(game.players):
            cy = self.ROW_TOP + i * self.ROW_H
            label = "P%d" % (i + 1)
            # The first-player marker is a ribbon running IN FROM THE LEFT
            # EDGE with the label inside it, so marker and name are one
            # object. A separate glyph beside the label read as two unrelated
            # things floating in the gutter.
            if i == game.first_player:
                ribbon_h(d, pal, cy - 17, 76, 34)
                text_center(d, pal, label, label_x, cy - 12, DISPLAY,
                            pal.bg, shadow=False)
            else:
                text_center(d, pal, label, label_x, cy - 12, DISPLAY, pal.tan)
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
        w = d.measure_text(title, DISPLAY)
        ix = int(240 - w / 2 - 30)
        icons.draw(d, mask, ix, 30, pen)
        text_center(d, pal, title, 240 + 12, 28, DISPLAY, pal.gold)

        val = state.preview
        text_center(d, pal, str(val), 240, 90, 9, pal.gold)
        if state.pending:
            dlt = state.delta
            text_center(d, pal, "%d  ->  %d" % (state.value, val), 240, 190, BODY, pal.muted)
            text_center(d, pal, "%s%d" % ("+" if dlt >= 0 else "", dlt), 240, 216, DISPLAY,
                        pal.green if dlt >= 0 else pal.red)

        bw, bh, gap = 104, 76, 8
        x0 = (480 - (4 * bw + 3 * gap)) // 2
        for k, (step, label) in enumerate(self.STEPS):
            b = Button(("step", step), x0 + k * (bw + gap), 250, bw, bh)
            bevel(d, pal, b.x, b.y, b.w, b.h, pal.btn, t=3)
            text_center(d, pal, label, b.x + b.w / 2, b.y + 26, DISPLAY, pal.tan)
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
            text_left(d, pal, label, 76, y + 12, BODY, pal.tan if on else pal.muted)
            from ui.header import VIEW_LABEL
            # "At <view>", not "Notifies at <view>": at BODY the archery row
            # ("Combat: Shadow Cards" plus the staging condition) runs 22px
            # past the row at the longer wording. Shortening the copy is the
            # fix; shrinking the caption is not (see the design system spec).
            if key == "archery":
                part1 = "At %s if staging " % VIEW_LABEL.get(view, view)
                w1 = d.measure_text(part1, BODY)
                text_left(d, pal, part1, 76, y + 38, BODY, pal.dim)
                icons.draw(d, icons.THREAT_SM, 76 + w1 + 2, y + 38, pal.dim)
                text_left(d, pal, "> 0", 76 + w1 + 18, y + 38, BODY, pal.dim)
            else:
                text_left(d, pal, "At %s" % VIEW_LABEL.get(view, view), 76, y + 38, BODY, pal.dim)
            self.buttons.append(row)
            y += 70

    def on_button(self, btn):
        k = btn.id[0]
        if k == "tog":
            key = btn.id[1]
            on = not self.game.reminders.get(key, False)
            self.game.reminders[key] = on
            from gamestate import REMINDER_DEFS
            label = next((lb for k2, lb, _v, _t, _i in REMINDER_DEFS
                          if k2 == key), key)
            self.game.log_event("Reminder %s: %s" % (label, "on" if on else "off"))
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

        text_center(d, pal, "P%d quests for..." % (self.idx + 1), 240, 28, DISPLAY, pal.gold)

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
            text_center(d, pal, label, b.x + bw / 2, b.y + 26, DISPLAY, pal.tan)
            self.buttons.append(b)

        done = Button(("done",), 24, 360, 200, 92)
        nxt = Button(("next",), 256, 360, 200, 92)
        if self.final:
            bevel(d, pal, done.x, done.y, done.w, done.h, pal.btn_ok, t=3)
            text_center(d, pal, "Done", done.x + 100, done.y + 32, DISPLAY, pal.ok_fg)
            bevel(d, pal, nxt.x, nxt.y, nxt.w, nxt.h, pal.card, t=3)
            text_center(d, pal, "Next", nxt.x + 100, nxt.y + 32, DISPLAY, pal.dim)
        else:
            bevel(d, pal, done.x, done.y, done.w, done.h, pal.card, t=3)
            text_center(d, pal, "Done", done.x + 100, done.y + 32, DISPLAY, pal.dim)
            bevel(d, pal, nxt.x, nxt.y, nxt.w, nxt.h, pal.btn, t=3)
            text_center(d, pal, "Next", nxt.x + 100, nxt.y + 32, DISPLAY, pal.gold)
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
        # Taps mutate prefs in place so the LEDs can live-preview. Cancel has
        # to put back what was there, or "Cancel" would keep every change it
        # previewed on the way.
        self._restore = {"brightness": prefs.get("brightness"),
                         "scene": prefs.get("scene")}
        self.buttons = []

    def draw(self, hw, game, pal):
        import leds
        d = hw.display
        self.buttons = []
        d.set_pen(pal.bg)
        d.clear()
        text_center(d, pal, "LED behavior", 240, 22, DISPLAY, pal.gold)

        # brightness slider (10 tap segments)
        text_left(d, pal, "Brightness  %d%%" % self.prefs["brightness"], 24, 70, BODY, pal.tan)
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
        text_left(d, pal, "Scene", 24, 182, BODY, pal.tan)
        half = (480 - 3 * 24) // 2
        for i, key in enumerate(leds.SCENES):
            x = 24 + (i % 2) * (half + 24)
            y = 210 + (i // 2) * 70
            on = self.prefs["scene"] == key
            b = Button(("scene", key), x, y, half, 58)
            panel(d, pal, b.x, b.y, b.w, b.h,
                  fill=pal.card_hi if on else pal.card,
                  border=pal.border_gold if on else pal.border)
            text_center(d, pal, leds.SCENE_LABELS[key], x + half / 2, y + 20, BODY,
                        pal.gold if on else pal.muted)
            self.buttons.append(b)

        # Cancel alongside Save: this modal writes prefs, and a full-width
        # Save was the only way out - so opening it to look at the options
        # meant committing whatever you had touched on the way.
        cancel = Button(("cancel",), 24, 396, 208, 62)
        bevel(d, pal, cancel.x, cancel.y, cancel.w, cancel.h, pal.btn_no, t=3)
        text_center(d, pal, "Cancel", cancel.x + cancel.w // 2, cancel.y + 20,
                    BODY, pal.no_fg)
        self.buttons.append(cancel)
        done = Button(("save",), 248, 396, 208, 62)
        panel(d, pal, done.x, done.y, done.w, done.h, fill=pal.btn_ok, border=pal.ok_fg)
        text_center(d, pal, "Done", done.x + done.w // 2, done.y + 20, BODY, pal.ok_fg)
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
        if k == "cancel":
            self.prefs.update(self._restore)
            return "cancel"
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
        tw = d.measure_text(title, DISPLAY)
        start = (480 - (20 + 8 + tw)) // 2
        icons.draw(d, icons.THREAT, start, 22, pal.red)
        text_left(d, pal, title, start + 28, 20, DISPLAY, pal.red)
        text_center(d, pal, "threat %d reached elimination level %d"
                    % (p.threat, p.elimination), 240, 62, BODY, pal.tan)

        eb = Button(("elim",), 24, 110, 432, 64)
        panel(d, pal, eb.x, eb.y, eb.w, eb.h, fill=pal.btn_no, border=pal.no_fg)
        text_center(d, pal, "Yes - eliminated", 240, eb.y + 22, BODY, pal.no_fg)
        self.buttons.append(eb)

        ab = Button(("avert",), 24, 190, 432, 64)
        panel(d, pal, ab.x, ab.y, ab.w, ab.h, fill=pal.btn)
        text_center(d, pal, "Averted by card effect", 240, ab.y + 12, BODY, pal.tan)
        text_center(d, pal, "threat -> %d, stays in" % max(0, p.elimination - 5),
                    240, ab.y + 38, BODY, pal.dim)
        self.buttons.append(ab)

        text_left(d, pal, "Elimination level changed?", 24, 286, BODY, pal.tan)
        stepper(d, pal, self.buttons, ("lvl", -1), ("lvl", 1), 24, 316,
                str(self.new_level), 300, 56)
        sb = Button(("setlvl",), 340, 316, 116, 56)
        panel(d, pal, sb.x, sb.y, sb.w, sb.h, fill=pal.btn_ok, border=pal.ok_fg)
        text_center(d, pal, "Set", sb.x + 58, sb.y + 18, BODY, pal.ok_fg)
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
    """Travel / "+ Add location": pick the location off the scenario's own
    cards, or enter its numbers by hand.

    mode 'new'    -> travel when there is no active location
    mode 'change' -> replace the current active location (old is discarded)

    Two steps, and which one it opens on is decided entirely by the data:

    - **list** - a flat, name-sorted radio list of every location the
      scenario can put into play (quest_catalog.locations_for's union across
      its "sets to gather"), each row carrying the printed quest points and
      threat. Picking one fills in BOTH numbers this flow used to make a
      player guess: a location's threat leaves the staging area when you
      travel to it, which is exactly the "contribution" the manual step asks
      for.
    - **manual** - the original two steppers, unchanged. This is where a
      scenario with no catalog data lands, and it stays reachable from the
      list for the cards a scenario never gathers - card effects put
      locations into play from outside the encounter deck, and the enrichment
      that supplies the gather list covers 108 scenarios (the rest fall back
      to their own set; 3 quest scenarios gather no locations at all).

    Flat, not the sphere-first drill SideQuestPickModal uses: a scenario's
    union is 5 locations at the median and 14 at the worst, so a grouping
    step would cost a tap on every travel to save paging on a handful of
    scenarios. The encounter set is not on the row either - no scenario in
    the catalog gathers two same-named locations from different sets, so the
    name alone is unambiguous, and the player is holding the card anyway.

    No row starts selected and Travel only appears once one is (hidden, not
    disabled, like the pager arrows): in 'change' mode committing discards
    the current location's progress, so a stray tap on a preselected first
    row would be destructive.

    `back` is where every exit returns you - "play" (the Travel-phase
    buttons) or "progress" (the Progress modal's "+ Add location", reopened
    via pending_progress_detail). Opened through game.pending_location_pick
    (see main.py's loop) because the union is a catalog read that neither a
    screen's nor a modal's on_button can do mid-tap.

    Empty `entries` (no catalog data) opens straight on the manual step and
    never shows a Locations back button - byte-identical to the pre-catalog
    modal."""

    PER_PAGE = 6
    ROW_H = 44
    ROW_STRIDE = 46
    LIST_Y0 = 66
    NAME_MAX_W = 292      # 52 -> 344, ahead of the threat block at 352
    THREAT_X = 352
    FOOTER_Y = 404
    FOOTER_H = 64

    def __init__(self, game, mode="new", entries=None, back="play", idx=0):
        self.game = game
        self.mode = mode
        self.entries = entries or []
        self.back = back
        # Which seat "change" replaces. Only meaningful in change mode; "new"
        # appends and ignores it.
        self.idx = idx
        self.step = "list" if self.entries else "manual"
        self.selected = None
        self.page = 0
        self.pts = 3
        self.contrib = 2   # its threat leaves the staging area while active
        # "travel" (the players paid the travel cost) vs "effect" (a card made
        # it active). Only the log and the CTA differ - see the draw comment.
        self.arrival = "travel"
        self.buttons = []

    def _replacing(self):
        """The seat a "change" would overwrite, or None. In "new" mode nothing
        is being replaced even when a location IS active - that is the whole
        point of a second seat - so the caption must not claim a discard."""
        if self.mode != "change":
            return None
        return (self.game.active_locations[self.idx]
                if self.idx < len(self.game.active_locations) else None)

    def _pages(self):
        return max(1, -(-len(self.entries) // self.PER_PAGE))

    # -- draw ------------------------------------------------------------
    def draw(self, hw, game, pal):
        d = hw.display
        self.buttons = []
        d.set_pen(pal.bg)
        d.clear()
        if self.step == "list":
            self._draw_list(d, pal)
        else:
            self._draw_manual(d, pal)

    def _draw_list(self, d, pal):
        from ui.header import modal_header
        # "+ Add location" (back == "progress") is not the Travel phase, so the
        # header must not claim one. Reaching this from the Travel view is.
        if self.mode != "new":
            head = "Change Location"
        elif self.back == "progress":
            head = "Add Location"
        else:
            head = "Travel"
        modal_header(d, pal, self.game, head, self.buttons)
        loc = self._replacing()
        if self.mode == "change" and loc:
            sub = "Replaces the current location (%d/%d discarded)." % (
                loc["progress"], loc["points"])
            ink = pal.no_fg
        else:
            sub = "Pick the location - or enter it manually."
            ink = pal.dim
        text_left(d, pal, truncate_text(sub, BODY, 456, d.measure_text), 12, 46, BODY, ink)

        pages = self._pages()
        self.page = min(self.page, pages - 1)
        chunk = self.entries[self.page * self.PER_PAGE:(self.page + 1) * self.PER_PAGE]
        y = self.LIST_Y0
        for e in chunk:
            on = e["id"] == self.selected
            if on:
                d.set_pen(pal.card_hi)
                d.rectangle(8, y, 456, self.ROW_H)
            _pick_radio(d, pal, 30, y + 22, on)
            name = truncate_text(e.get("name") or "", BODY, self.NAME_MAX_W, d.measure_text)
            text_left(d, pal, name, 52, y + 13, BODY, pal.tan if on else pal.muted)
            # Threat, then quest points - the same order the row's two
            # steppers sit in on the manual step is reversed here on purpose:
            # quest points are the number the player acts on, so they take
            # the right edge where every other list in the app puts its
            # headline figure.
            # One pill carrying both numbers instead of a loose icon, a loose
            # number and a separate "N qp": threat (black, on the light segment
            # that makes black possible) then quest points. Right-aligned so the
            # column lines up however long the name is.
            pw = stat_pill(d, pal, 0, 0, e.get("threat") or 0,
                           e.get("points") or 0, measure_only=True)
            stat_pill(d, pal, 458 - pw, y + 8, e.get("threat") or 0,
                      e.get("points") or 0)
            d.set_pen(pal.border)
            d.rectangle(8, y + self.ROW_H, 456, 1)
            self.buttons.append(Button(("row", e["id"]), 8, y, 456, self.ROW_H))
            y += self.ROW_STRIDE
        self._pager(d, pal, pages)

        manual = Button(("manual",), 24, self.FOOTER_Y, 200, self.FOOTER_H)
        bevel(d, pal, manual.x, manual.y, manual.w, manual.h, pal.btn, t=3)
        text_center(d, pal, "Manual", manual.x + manual.w / 2, manual.y + 20, BODY, pal.tan)
        self.buttons.append(manual)
        if self.selected is not None:
            go = Button(("travel",), 256, self.FOOTER_Y, 200, self.FOOTER_H)
            bevel(d, pal, go.x, go.y, go.w, go.h, pal.btn_ok, t=3)
            text_center(d, pal, "Travel" if self.back != "progress" else "Add",
                        go.x + go.w / 2, go.y + 20, BODY, pal.ok_fg)
            self.buttons.append(go)

    def _pager(self, d, pal, pages):
        if pages <= 1:
            return
        up = Button(("older",), 12, 352, 150, 46)
        dn = Button(("newer",), 318, 352, 150, 46)
        bevel(d, pal, up.x, up.y, up.w, up.h, pal.btn)
        text_center(d, pal, "Up", up.x + 75, up.y + 14, BODY, pal.tan)
        bevel(d, pal, dn.x, dn.y, dn.w, dn.h, pal.btn)
        text_center(d, pal, "Down", dn.x + 75, dn.y + 14, BODY, pal.tan)
        text_center(d, pal, "%d/%d" % (self.page + 1, pages), 240, 366, BODY, pal.muted)
        self.buttons.append(up)
        self.buttons.append(dn)

    def _draw_manual(self, d, pal):
        # The title follows the arrival choice rather than always claiming a
        # travel: "Manual" used to land on "Travel to new location" even when the
        # player was recording a card effect.
        if self.mode != "new":
            title = "Change active location"
        elif self.arrival == "travel":
            title = "Travel to new location"
        else:
            title = "New active location"
        text_center(d, pal, title, 240, 16, DISPLAY, pal.gold)
        loc = self._replacing()
        y = 58
        if self.mode == "change" and loc:
            text_center(d, pal, "current %d/%d will be discarded"
                        % (loc["progress"], loc["points"]), 240, y, BODY, pal.no_fg)
            y += 26

        # How it arrived. Travelling is only travelling when the players pay the
        # travel cost; a card effect can make a location active without one, and
        # the once-per-round travel limit does not apply to that. The MECHANICS
        # are the same either way - RR: "the active location acts as a buffer",
        # so its threat leaves the staging total however it got there - but the
        # log is the game's record and it should not claim a travel that never
        # happened.
        text_left(d, pal, "HOW IT ARRIVED", 60, y, LABEL, pal.muted)
        y += 20
        for key, label in (("travel", "Travelled here"),
                           ("effect", "A card put it into play")):
            on = self.arrival == key
            b = Button(("arr", key), 60, y, 360, 40)
            bevel(d, pal, b.x, b.y, b.w, b.h, pal.card_hi if on else pal.btn, t=3)
            disc(d, b.x + 20, b.y + 20, 9, pal.well)
            if on:
                disc(d, b.x + 20, b.y + 20, 5, pal.gold)
            arc_runs(d, b.x + 20, b.y + 20, 9, 7, 0, 360,
                     pal.gold if on else pal.dim)
            text_left(d, pal, label, b.x + 40, b.y + 10, BODY,
                      pal.gold if on else pal.tan)
            self.buttons.append(b)
            y += 44
        y += 8
        text_left(d, pal, "Quest points", 60, y + 14, BODY, pal.tan)
        stepper(d, pal, self.buttons, ("pts", -1), ("pts", 1), 250, y,
                str(self.pts), 170, 48)
        y += 54
        # No icon here: a threat glyph with no value beside it had nowhere legible
        # to sit (black on the ground is invisible, and a plate around an empty
        # icon reads as a bug). The words carry it.
        text_left(d, pal, "Threat contribution", 60, y + 14, BODY, pal.tan)
        stepper(d, pal, self.buttons, ("ctr", -1), ("ctr", 1), 250, y,
                str(self.contrib), 170, 48)
        y += 54
        text_left(d, pal, "leaves the staging area while it is active", 60, y,
                  BODY, pal.dim)
        y += 26
        if self.entries:
            back = Button(("back",), 12, y, 200, 40)
            bevel(d, pal, back.x, back.y, back.w, back.h, pal.btn)
            text_center(d, pal, "< Locations", back.x + back.w / 2, back.y + 11,
                        BODY, pal.tan)
            self.buttons.append(back)
        _footer(d, pal, self.buttons,
                save_label="Travel" if self.arrival == "travel" else "Place")

    # -- input -----------------------------------------------------------
    def _leave(self, result="close"):
        """Every exit returns you where you came from: the Progress modal
        reopens via the pending flag, the play screen just falls through."""
        if self.back == "progress":
            self.game.pending_progress_detail = True
        return result

    def _commit(self, points, contribution, name=None, entry=None):
        """`entry` is the picker row, or None for the manual stepper. Its
        threat / *Kind / *Formula keys ride along onto the location record so
        the Progress screen can put a real threat back into staging, and can
        show the card's own definition of X rather than a 0."""
        entry = dict(entry or {})
        entry["arrival"] = self.arrival
        # "new" APPENDS - that is how a second seat arrives, and the five
        # cards that allow one all phrase it as travelling with one active.
        # "change" replaces the seat it was opened on.
        if self.mode == "new":
            self.game.travel_to(points, contribution, name, entry)
        else:
            self.game.change_location(points, contribution, name,
                                      idx=self.idx, meta=entry)

    def on_button(self, btn):
        k = btn.id[0]
        if k == "pts":
            self.pts = max(1, min(30, self.pts + btn.id[1]))
            return None
        if k == "ctr":
            self.contrib = max(0, min(9, self.contrib + btn.id[1]))
            return None
        if k == "arr":
            self.arrival = btn.id[1]
            return "redraw"
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
            self.step = "manual"
            return "redraw"
        if k == "back":
            self.step = "list"
            return "redraw"
        if k == "travel":
            # From the Travel view this IS a travel; from Progress's "+ Add" it
            # is not, and the log should not say otherwise.
            self.arrival = "travel" if self.back != "progress" else "effect"
            e = next((x for x in self.entries if x["id"] == self.selected), None)
            if e:
                self._commit(e.get("points") or 0, e.get("threat") or 0,
                             e.get("name"), e)
            return self._leave()
        if k == "save":
            self._commit(self.pts, self.contrib)
            return self._leave()
        if k == "close":
            return self._leave()
        if k == "cancel":
            return self._leave("cancel")
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
        self.alloc = {"locations": list(a["locations"]), "quest": a["quest"],
                      "side_quests": [0] * len(self.game.side_quests)}

    def _used(self):
        return (sum(self.alloc["locations"]) + self.alloc["quest"]
                + sum(self.alloc["side_quests"]))

    def _remaining(self):
        return self.budget - self._used()

    def draw(self, hw, game, pal):
        d = hw.display
        self.buttons = []
        d.set_pen(pal.bg)
        d.clear()
        text_center(d, pal, "Quested successfully", 240, 16, DISPLAY, pal.ok_fg)
        text_center(d, pal, "remaining %d / %d" % (self._remaining(), self.budget),
                    240, 54, BODY, pal.gold)

        # reminder - two BODY lines; the second was one long sentence that
        # only fitted at LABEL ("Side quest may take progress instead. Card
        # effects override.", 570px at BODY against 438 of panel), so the copy
        # was shortened rather than the type.
        panel(d, pal, 16, 78, 448, 52, fill=pal.card)
        text_left(d, pal, "Fill Active Location first; overflow -> Quest.", 26, 84, BODY, pal.muted)
        text_left(d, pal, "Side quest may take it. Card effects override.", 26, 106, BODY, pal.muted)

        y = 142
        self._rows = []
        for i, loc in enumerate(self.game.active_locations):
            self._rows.append(("location", i,
                               "Active Location" if i == 0
                               else "Active Location %d" % (i + 1),
                               loc["progress"], loc["points"]))
        self._rows.append(("quest", None, "Quest %s" % self.game.quest_label(),
                           self.game.quest["progress"], self.game.quest["points"]))
        for i, sq in enumerate(self.game.side_quests):
            self._rows.append(("side", i, "Side quest %d" % (i + 1), sq["progress"], sq["points"]))

        for key, idx, label, cur, pts in self._rows:
            add = (self.alloc["side_quests"][idx] if key == "side"
                   else self.alloc["locations"][idx] if key == "location"
                   else self.alloc[key])
            panel(d, pal, 16, y, 448, 50, fill=pal.card)
            text_left(d, pal, label, 26, y + 6, BODY, pal.tan)
            text_left(d, pal, "%d + %d / %d" % (cur, add, pts), 26, y + 28, LABEL, pal.muted)
            mn = Button(("m", key, idx), 300, y + 5, 44, 40)
            pl = Button(("p", key, idx), 410, y + 5, 44, 40)
            button(d, pal, mn, "-", DISPLAY)
            button(d, pal, pl, "+", DISPLAY)
            text_center(d, pal, str(cur + add), 377, y + 12, DISPLAY, pal.gold)
            self.buttons.extend([mn, pl])
            y += 56

        auto = Button(("auto",), 16, 356, 300, 44)
        rst = Button(("reset",), 324, 356, 140, 44)
        panel(d, pal, auto.x, auto.y, auto.w, auto.h, fill=pal.btn)
        text_center(d, pal, "Auto loc->quest", auto.x + auto.w / 2, auto.y + 12, BODY, pal.tan)
        panel(d, pal, rst.x, rst.y, rst.w, rst.h, fill=pal.btn)
        text_center(d, pal, "Reset", rst.x + rst.w / 2, rst.y + 12, BODY, pal.tan)
        self.buttons.extend([auto, rst])

        _footer(d, pal, self.buttons, save_label="Apply")

    def _add(self, key, idx, delta):
        if delta > 0 and self._remaining() <= 0:
            return
        if key == "side":
            self.alloc["side_quests"][idx] = max(0, self.alloc["side_quests"][idx] + delta)
        elif key == "location":
            self.alloc["locations"][idx] = max(0, self.alloc["locations"][idx] + delta)
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
            self.alloc = {"locations": [0] * len(self.game.active_locations),
                          "quest": 0,
                          "side_quests": [0] * len(self.game.side_quests)}
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

    def __init__(self, game):
        self.game = game
        self.buttons = []
        self.add_prompt = False  # "+ Add" asks Location or Side quest
        self.history = False     # the by-round chart + heading sub-view
        self.page = 0
        self._snap = self._snapshot()

    def _snapshot(self):
        g = self.game
        return {
            "q": {"p": g.quest["progress"], "t": g.quest["points"]},
            "locs": [{"p": l["progress"], "t": l["points"]}
                     for l in g.active_locations],
            "sqLen": len(g.side_quests),
            "sq": [{"p": s["progress"], "t": s["points"]} for s in g.side_quests],
        }

    def _items(self):
        g = self.game
        items = [{"kind": "q", "name": "Quest %s" % g.quest_label(), "removable": False,
                  "advanceable": bool(g.stages)}]
        # Prefer the catalog name (LocationPickModal's list step) when
        # present; manual entries and old saves have no "name" key at all, so
        # this stays "Location" for them - same rule as the side quests below.
        for i, loc in enumerate(g.active_locations):
            items.append({"kind": "l", "idx": i, "removable": True,
                          "name": (loc.get("name")
                                   or ("Location" if i == 0
                                       else "Location %d" % (i + 1)))})
        if not g.active_locations:
            items.append({"kind": "l_add"})
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
            text_center(d, pal, str(value), cx, int(cy - 8), BODY, pal.gold)
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

    # -- the mock's row vocabulary -------------------------------------------
    # A row is a card with a coloured accent down its left edge (green =
    # location, gold = quest/side quest), the entity's glyph and name, its
    # printed quest points as dense metadata, a ">" into its own detail sheet,
    # and ONE big stepper cluster reading "progress / target" over a fill bar.
    #
    # The old row was 38px with two small circular editors side by side and
    # four 24px icon buttons crowded to the right - "tap targets are tiny, and
    # very different from the Players screen controls". The target stepper is
    # gone from the row entirely: editing a target is a detail-sheet job, which
    # is also what labels the actions the icons never named.
    # From ui.widgets, so the web twin reads the same two numbers.
    ROW_H = W_ROW_H
    ROW_H_COMPACT = W_ROW_H_COMPACT
    ROW_GAP = 5

    def _section(self, d, pal, y, label, count=None):
        text_left(d, pal, label, MARGIN + 2, y, LABEL, pal.muted)
        if count:
            w = d.measure_text(label, LABEL)
            text_left(d, pal, count, MARGIN + 10 + w, y, LABEL, pal.dim)
        return y + 14

    def _row(self, d, pal, it, y, compact=False):
        g = self.game
        kind = it["kind"]
        cond = kind == "q" and g.quest.get("mode") == "condition"
        # A condition row carries two lines of the card's own sentence AND a
        # count-only stepper, so it needs more than a bar row does.
        h = 96 if cond else (self.ROW_H_COMPACT if compact else self.ROW_H)
        if kind == "q":
            prog, pts, pfx, idx = g.quest["progress"], g.quest["points"], "q", None
            accent, meta = pal.gold, "STAGE %s" % g.quest_label()
        elif kind == "l":
            idx = it.get("idx", 0)
            loc = g.active_locations[idx]
            prog, pts, pfx = loc["progress"], loc["points"], "l"
            accent = pal.green
            meta = "%d QP" % pts if pts else None
        else:
            sq = g.side_quests[it["idx"]]
            prog, pts, pfx, idx = sq["progress"], sq["points"], "s", it["idx"]
            accent = pal.gold
            meta = "%d QP" % pts if pts else None
        at_target = bool(pts) and prog >= pts
        panel(d, pal, MARGIN, y, 480 - 2 * MARGIN, h, fill=pal.card,
              border=pal.border)
        d.set_pen(accent)
        d.rectangle(MARGIN, y, 4, h)
        # A stage that advances on a condition has no bar to fill and no target
        # to count toward, so the card's own sentence takes the space instead.
        if cond:
            glyph(d, pal, kind, MARGIN + 14, y + 5, accent)
            text_left(d, pal, truncate_text(it["name"], BODY, 236,
                                            d.measure_text),
                      MARGIN + 40, y + 8, BODY, pal.tan)
            mw = d.measure_text("NO QUEST POINTS", LABEL)
            text_left(d, pal, "NO QUEST POINTS", 480 - MARGIN - 28 - mw,
                      y + 10, LABEL, pal.dim)
            text_left(d, pal, ">", 480 - MARGIN - 18, y + 6, BODY, pal.gold)
            ty = y + 36
            lines = wrap_text(g.quest.get("advance") or
                              "This stage advances on a condition, not on "
                              "progress.", BODY, 480 - 2 * MARGIN - 56,
                              d.measure_text)
            for ln in lines[:2]:
                text_left(d, pal, ln, MARGIN + 40, ty, BODY, pal.dim)
                ty += 22
            if len(lines) > 2:
                text_left(d, pal, "[...] more", MARGIN + 40, ty, BODY, pal.gold)
            # Still a stepper, just no denominator: a condition stage can carry
            # progress (some place it and discard it, some ignore it), it simply
            # has no target to fill. Dropping the control entirely would have
            # left the player nowhere to count.
            cy = y + h - 26
            for cx, mark, on, bid in ((404, "-", prog > 0, ("qP-", None)),
                                       (452, "+", True, ("qP+", None))):
                disc(d, cx, cy, 18, pal.btn if on else pal.card_hi)
                arc_runs(d, cx, cy, 18, 16, 0, 360,
                         pal.bevel_l if on else pal.border)
                text_center(d, pal, mark, cx, cy - 8, DISPLAY,
                            pal.tan if on else pal.dim)
                if on:
                    self.buttons.append(Button(bid, cx - 18, cy - 18, 36, 36))
            text_left(d, pal, str(prog), 372, cy - 12, DISPLAY, pal.gold)
            self.buttons.append(Button(("detail", kind, idx), MARGIN, y,
                                       340, 34))
            return y + h + self.ROW_GAP
        if compact:
            cy = y + h // 2 - 3
            # Compact rows pack two locations plus the quest onto one page,
            # so the disc shrinks - but the TAP target does not go below the
            # row it sits in.
            left = stepper_cluster(d, pal, self.buttons, 480 - MARGIN - 30, cy,
                                   prog, pts, at_target,
                                   (pfx + "P-", idx), (pfx + "P+", idx),
                                   r=18, hit=self.ROW_H_COMPACT)
            glyph(d, pal, kind, MARGIN + 14, cy - 10, accent)
            text_left(d, pal, truncate_text(it["name"], BODY,
                                            left - (MARGIN + 40) - 10,
                                            d.measure_text),
                      MARGIN + 40, cy - 8, BODY, pal.tan)
            fill_bar(d, pal, MARGIN + 14, y + h - 9,
                           left - (MARGIN + 28), 4, prog, pts, accent, at_target)
            self.buttons.append(Button(("detail", kind, idx), MARGIN, y,
                                       left - MARGIN - 10, h))
            return y + h + self.ROW_GAP
        glyph(d, pal, kind, MARGIN + 14, y + 5, accent)
        text_left(d, pal, truncate_text(it["name"], BODY, 236, d.measure_text),
                  MARGIN + 40, y + 8, BODY, pal.tan)
        if meta:
            mw = d.measure_text(meta, LABEL)
            text_left(d, pal, meta, 480 - MARGIN - 28 - mw, y + 10, LABEL, pal.dim)
        text_left(d, pal, ">", 480 - MARGIN - 18, y + 6, BODY, pal.gold)
        cy = y + 48
        left = stepper_cluster(d, pal, self.buttons, 480 - MARGIN - 36, cy,
                               prog, pts, at_target,
                               (pfx + "P-", idx), (pfx + "P+", idx))
        fill_bar(d, pal, MARGIN + 14, cy - 3, left - (MARGIN + 28), 6,
                       prog, pts, accent, at_target)
        # The whole title band opens the detail sheet - the ">" is the hint, not
        # the hit-box. Pushed last so the stepper hit-boxes win any overlap.
        self.buttons.append(Button(("detail", kind, idx), MARGIN, y,
                                   480 - 2 * MARGIN, 40))
        return y + h + self.ROW_GAP

    def _bottom_bar(self, d, pal, page, pages):
        y = 420
        for label, x, w, bid in (("History", 12, 118, ("history",)),
                                 ("+ Add", 138, 96, ("add",))):
            b = Button(bid, x, y, w, 46)
            bevel(d, pal, b.x, b.y, b.w, b.h, pal.btn)
            text_center(d, pal, label, x + w // 2, y + 14, BODY, pal.tan)
            self.buttons.append(b)
        if pages > 1:
            for label, x, bid in (("Up", 288, ("older",)), ("Down", 382, ("newer",))):
                b = Button(bid, x, y, 86, 46)
                bevel(d, pal, b.x, b.y, b.w, b.h, pal.btn)
                text_center(d, pal, label, x + 43, y + 14, BODY, pal.tan)
                self.buttons.append(b)
            text_center(d, pal, "%d/%d" % (page + 1, pages), 262, y + 14,
                        BODY, pal.muted)

    def draw(self, hw, game, pal):
        from ui.header import modal_header
        d = hw.display
        self.buttons = []
        d.set_pen(pal.bg)
        d.clear()
        if self.add_prompt:
            self._draw_add_prompt(d, pal)
            return
        if self.history:
            self._draw_history(d, pal)
            return
        # DONE becomes RESOLVE when something is sitting at its target. Closing
        # ALREADY runs the resolve flow (main.py checks needs_resolution() on
        # close), so a separate "Resolve now" button was a second control doing
        # the first one's job - the label just has to admit what DONE will do.
        ready = game.needs_resolution() if hasattr(game, "needs_resolution") else False
        modal_header(d, pal, game, "Progress", self.buttons,
                     cta="RESOLVE" if ready else "DONE", cta_ready=ready)
        y = 46 + phase_block(d, pal, MARGIN, 46, 480 - 2 * MARGIN,
                             [("framework", PROGRESS_PLACEMENT)]) + 8

        # Location BEFORE quest: progress fills the location first, and the
        # band directly above says so. Reading order should match the rule.
        items = self._items()
        order = {"l": 0, "l_add": 0, "q": 1, "s": 2}
        rows = sorted((it for it in items if it["kind"] != "l_add"),
                      key=lambda it: order[it["kind"]])
        avail = 420 - y - 8

        def fits(compact):
            rh = (self.ROW_H_COMPACT if compact else self.ROW_H) + self.ROW_GAP
            # Sections are emitted once per GROUP, not per row, so the worst
            # case is one header per distinct kind on the page.
            per = max(1, (avail - 3 * 14) // rh)
            return per, max(1, (len(rows) + per - 1) // per)

        # Prefer shrinking the rows over paging them: a lone side quest stranded
        # on page 2 is worse than three compact rows on page 1.
        per_page, pages = fits(False)
        compact = False
        if pages > 1:
            per_c, pages_c = fits(True)
            if pages_c < pages:
                compact, per_page, pages = True, per_c, pages_c

        # The break follows the CHAIN, not the row count. Progress fills the
        # locations and then the quest, and the band at the top of the screen
        # describes exactly that motion - so those rows are one thing and are
        # not split across a page turn. Side quests take what is left, and page
        # 2 onward if they have to.
        chain = [it for it in rows if it["kind"] in ("l", "q")]
        tail = [it for it in rows if it["kind"] == "s"]
        if chain and len(chain) <= per_page:
            pages_list = [chain + tail[:per_page - len(chain)]]
            rest = tail[per_page - len(chain):]
            while rest:
                pages_list.append(rest[:per_page])
                rest = rest[per_page:]
        else:
            # The chain alone overflows the page - nothing to protect, so fall
            # back to plain slicing rather than inventing a worse rule.
            pages_list = [rows[i:i + per_page]
                          for i in range(0, len(rows), per_page)] or [[]]
        pages = len(pages_list)
        self.page = min(self.page, pages - 1)
        shown = pages_list[self.page]

        n_loc = sum(1 for r in rows if r["kind"] == "l")
        SECTION = {"l": "ACTIVE LOCATIONS" if n_loc > 1 else "ACTIVE LOCATION",
                   "q": "CURRENT QUEST", "s": "SIDE QUESTS"}
        last_kind = None
        for it in shown:
            if it["kind"] != last_kind:
                # The count rides beside the header when a section holds more
                # than one, so a paged-off row is still accounted for.
                n = sum(1 for r in rows if r["kind"] == it["kind"])
                count = str(n) if n > 1 else None
                y = self._section(d, pal, y, SECTION[it["kind"]], count)
                last_kind = it["kind"]
            y = self._row(d, pal, it, y, compact)
        if not game.active_locations and self.page == 0:
            text_left(d, pal, "No active location.", MARGIN + 4, y, BODY, pal.dim)
            y += 24
        self._bottom_bar(d, pal, self.page, pages)
        return

    def _draw_add_prompt(self, d, pal):
        """"+ Location" and "+ Side quest" were two permanent buttons mid-screen
        for occasional actions. Merged into one "+ Add" that asks which - the
        same in-modal prompt pattern the removal prompt used to use, because a
        modal cannot open another."""
        from ui.header import modal_header
        modal_header(d, pal, self.game, "Add", self.buttons)
        y = 90
        for label, bid, note in (
                ("Location", ("add_loc",), "the one you just travelled to"),
                ("Side quest", ("add_sq",), "a player side quest in play")):
            b = Button(bid, 40, y, 400, 62)
            bevel(d, pal, b.x, b.y, b.w, b.h, pal.btn, t=3)
            text_left(d, pal, label, b.x + 20, b.y + 8, BODY, pal.tan)
            text_left(d, pal, note, b.x + 20, b.y + 34, BODY, pal.dim)
            self.buttons.append(b)
            y += 74
        c = Button(("add_cancel",), 40, y + 10, 400, 48)
        panel(d, pal, c.x, c.y, c.w, c.h, fill=pal.btn_no, border=pal.no_fg)
        text_center(d, pal, "Cancel", 240, c.y + 14, BODY, pal.no_fg)
        self.buttons.append(c)

    def _draw_history(self, d, pal):
        """The by-round chart and, for a sailing game, the heading radios.

        Both used to sit permanently below the rows, which is what made "round
        summary section has poor layout when early in the game" true - an empty
        chart held 130px hostage every round before the first resolve. They are
        one tap away now instead, behind the bottom bar's History button.
        """
        from ui.header import modal_header
        # The way back takes the round-stamp slot: a button at the bottom
        # landed on the chart's last row and its caption, and one drawn over
        # the stamp printed the two on top of each other.
        modal_header(d, pal, self.game, "History", self.buttons,
                     back=("< Progress", ("hist_back",)))
        if self.game.sailing:
            heading_y = 60
            text_left(d, pal, "Heading", 12, heading_y, BODY, pal.tan)
            cy = heading_y + 4
            for i in range(4):
                cx = 150 + i * 40
                disc(d, cx, cy, 14, pal.well)
                active = i == self.game.heading
                if active:
                    ring(d, cx, cy, 14, 2, 1.0, pal.gold, pal.gold)
                wx_small(d, pal, i, cx, cy, 7, None if active else pal.dim)
                self.buttons.append(Button(("hd_set", i), cx - 14, cy - 14, 28, 28))

        # Nothing sits above the chart here, so it starts under the heading
        # row instead of holding its play-screen anchor and leaving 250px of
        # empty screen between the two.
        self._draw_chart(d, pal, 116 if self.game.sailing else 76)

    def _draw_chart(self, d, pal, cy0=344):
        """`cy0` is the block's top. It defaults to the play-screen anchor it
        has always had; the History sub-view passes its own, since nothing sits
        above it there."""
        d.set_pen(pal.border)
        d.rectangle(8, cy0 - 12, 464, 1)
        text_left(d, pal, "THIS GAME - BY ROUND", 12, cy0 - 9, LABEL, pal.muted)
        cols = self.game.quest_history[-8:]
        if not cols:
            text_center(d, pal, "No rounds resolved yet", 240, cy0 + 14, BODY, pal.dim)
            return
        x0 = 52
        stride = (472 - x0) // len(cols)
        for i, r in enumerate(cols):
            text_center(d, pal, "R%d" % r["round"], x0 + i * stride + stride // 2, cy0, LABEL, pal.dim)
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
        # A gold vertical wherever the stage changed between two columns. It
        # is the one thing that explains a sudden jump in the staging line, and
        # without it the chart shows the rounds but not the shape of the game.
        # Entries written before `stage` existed return None and rule nothing.
        ry = cy0 + 14
        rule_h = 26 * len(rows)
        for i in range(1, len(cols)):
            a_st, b_st = cols[i - 1].get("stage"), cols[i].get("stage")
            if a_st is None or b_st is None or a_st == b_st:
                continue
            d.set_pen(pal.gold)
            d.rectangle(x0 + i * stride - 1, ry - 6, 1, rule_h)
        for mask, ipen, stripe, cell in rows:
            if stripe:
                d.set_pen(pal.row_stripe)
                d.rectangle(8, ry - 4, 464, 24)
            icons.draw(d, mask, 12, ry - 2, ipen)
            for i, r in enumerate(cols):
                s, pen = cell(r)
                text_center(d, pal, s, x0 + i * stride + stride // 2, ry, BODY, pen)
            ry += 26
        # The key for the icon column above it - chrome for a dense readout,
        # scanned rather than read, so it stays LABEL and goes ALL CAPS to
        # match "THIS GAME - BY ROUND" at the top of the same block.
        caption = "WILLPOWER / STAGING / RESULT" + (" / HEADING" if self.game.sailing else "")
        text_center(d, pal, caption, 240, ry + 4, LABEL, pal.dim)

    def _clamp_adj(self, cur, delta, cap=None):
        """Step a value, clamped. `cap` is the row's own target: progress
        cannot exceed the quest points it is filling.

        RR p.22: excess progress beyond a stage's quest points is DISCARDED on
        advance, not carried, and a location explores the moment it is full -
        so a bar reading 12/3 describes a state the game cannot be in. Location
        overflow does flow on to the quest card (p.15), but that is the guided
        resolution flow's job, not something the stepper should let you type in.

        cap=None leaves the old 0..99 behaviour, which is what a target-less
        row wants: a condition stage has no quest points, so there is nothing
        to clamp against and the player may be counting anything.
        """
        hi = 99 if not cap or cap <= 0 else cap
        return max(0, min(hi, cur + delta))

    def on_button(self, btn):
        g = self.game
        k = btn.id[0]
        a = btn.id[1] if len(btn.id) > 1 else None
        up = k.endswith("+")
        if k in ("qP-", "qP+"):
            # A condition stage has no target to clamp against (mode set by
            # flip_to_b) - leave it free.
            cap = None if g.quest.get("mode") == "condition" else g.quest["points"]
            g.quest["progress"] = self._clamp_adj(g.quest["progress"],
                                                  1 if up else -1, cap)
            return None
        if k in ("qT-", "qT+"):
            g.quest["points"] = self._clamp_adj(g.quest["points"], 1 if up else -1)
            return None
        if k in ("lP-", "lP+"):
            # The location can have explored itself out from under this button
            # (the auto-explore below clears it), and a stale tap on the old
            # hit-box then crashed on a None record.
            i = btn.id[1] if len(btn.id) > 1 else 0
            if i >= len(g.active_locations):
                return None
            loc = g.active_locations[i]
            loc["progress"] = self._clamp_adj(
                loc["progress"], 1 if up else -1, loc["points"])
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
            i = btn.id[1] if len(btn.id) > 1 else 0
            if i >= len(g.active_locations):
                return None
            loc = g.active_locations[i]
            loc["points"] = self._clamp_adj(loc["points"], 1 if up else -1)
            return None
        if k == "ldone":
            i = btn.id[1] if len(btn.id) > 1 else 0
            if i < len(g.active_locations):
                g.log_event("Active location Explored")
                del g.active_locations[i]
            self._snap = self._snapshot()
            return None
        if k in ("sP-", "sP+"):
            s = g.side_quests[a]
            s["progress"] = self._clamp_adj(s["progress"], 1 if up else -1,
                                            s["points"])
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
        if k == "addloc":
            # Was a blind append of a guessed 3 quest points. Now the same
            # picker Travel uses, opened via the pending flag (the router
            # holds one modal at a time) with back="progress" so every exit
            # reopens this modal instead of dropping you on the play screen.
            g.pending_location_pick = {"mode": "new", "back": "progress"}
            self._log_changes()
            return "close"
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
        if k == "detail":
            # The row's ">" opens that entity's own sheet, which is where the
            # target lives now and where the icon-button actions finally get
            # labels. One modal at a time, so close-and-flag like "quest_card".
            kind = btn.id[1]
            if kind == "q":
                # The EDITOR, not the card: this is where quest points and the
                # advance sentence live, and it links on to the card itself.
                g.pending_quest_config = True
            elif kind == "l":
                g.pending_location_detail = True
            else:
                # SideQuestsModal, where Done and Remove live - NOT the add
                # picker. This raised pending_side_quest_pick, so a row's own
                # chevron opened "choose a side quest to add" and there was no
                # way to reach the row's own actions at all.
                g.pending_side_quest_detail = True
            self._log_changes()
            return "close"
        if k == "add":
            # "+ Location" and "+ Side quest" were two permanent buttons for
            # occasional actions; one "+ Add" asks which.
            self.add_prompt = True
            return "redraw"
        if k == "add_loc":
            self.add_prompt = False
            g.pending_location_pick = {"mode": "new", "back": "progress"}
            self._log_changes()
            return "close"
        if k == "add_sq":
            self.add_prompt = False
            g.pending_side_quest_pick = True
            self._log_changes()
            return "close"
        if k == "add_cancel":
            self.add_prompt = False
            return "redraw"
        if k == "history":
            self.history = True
            return "redraw"
        if k == "hist_back":
            self.history = False
            return "redraw"
        if k in ("older", "newer"):
            self.page = max(0, self.page + (-1 if k == "older" else 1))
            return "redraw"
        if k == "loc_detail":
            # Same one-modal-at-a-time dance as "quest_card" above: close, flag,
            # and let the router open LocationConfigModal on the next pass.
            g.pending_location_detail = True
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

    def _log_changes(self):
        s, g = self._snap, self.game
        if g.quest["progress"] != s["q"]["p"] or g.quest["points"] != s["q"]["t"]:
            g.log_event("Quest %s set %d/%d (progress view)"
                        % (g.quest_label(), g.quest["progress"], g.quest["points"]))
        # Only seats that were there when the modal opened AND are still
        # there: one that left is already logged by whatever removed it, and
        # one that arrived was logged by the travel.
        for i, snap in enumerate(s["locs"]):
            if i >= len(g.active_locations):
                continue
            loc = g.active_locations[i]
            if loc["progress"] != snap["p"] or loc["points"] != snap["t"]:
                label = "Active location" if len(s["locs"]) == 1 \
                    else "Active location %d" % (i + 1)
                g.log_event("%s set %d/%d (progress view)"
                            % (label, loc["progress"], loc["points"]))
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
        text_left(d, pal, label, x0 + 32, cy + (2 if scale == BODY else 0), scale, pen)

    def draw(self, hw, game, pal):
        from ui.header import modal_header
        d = hw.display
        self.buttons = []
        d.set_pen(pal.bg)
        d.clear()
        modal_header(d, pal, self.game, "Sailing test", self.buttons)

        text_center(d, pal, "CURRENT HEADING", 240, 54, LABEL, pal.dim)
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
        text_center(d, pal, sub, 240, 200, BODY, spen)

        mn = Button(("d", -1), 34, 128, 64, 60)
        pl = Button(("d", 1), 480 - 34 - 64, 128, 64, 60)
        bevel(d, pal, mn.x, mn.y, mn.w, mn.h, pal.btn)
        text_center(d, pal, "-", mn.x + 32, mn.y + 14, 4, pal.tan)
        bevel(d, pal, pl.x, pl.y, pl.w, pl.h, pal.btn)
        text_center(d, pal, "+", pl.x + 32, pl.y + 14, 4, pal.tan)
        self.buttons.append(mn)
        self.buttons.append(pl)

        text_center(d, pal, "RESULT", 240, 240, LABEL, pal.dim)
        self._heading(d, pal, self._result(), 262, 2)

        no = Button(("cancel",), 24, 404, 200, 64)
        ok = Button(("apply",), 256, 404, 200, 64)
        bevel(d, pal, no.x, no.y, no.w, no.h, pal.btn_no, t=3)
        text_center(d, pal, "Cancel", no.x + 100, no.y + 20, BODY, pal.no_fg)
        bevel(d, pal, ok.x, ok.y, ok.w, ok.h, pal.btn_ok, t=3)
        text_center(d, pal, "Apply", ok.x + 100, ok.y + 20, BODY, pal.ok_fg)
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
        text_center(d, pal, "Quest Stage %s cleared!" % self.cleared, 240, 26, DISPLAY, pal.gold)
        y = 74
        text_center(d, pal, "Set up the next stage", 240, y, BODY, pal.tan)
        y += 40
        text_left(d, pal, "Stage", 30, y + 14, BODY, pal.tan)
        stepper(d, pal, self.buttons, ("n", -1), ("n", 1), 160, y, str(self.n), 130, 52)
        stepper(d, pal, self.buttons, ("side", -1), ("side", 1), 316, y, self.side, 144, 52)
        y += 76
        text_left(d, pal, "Quest points", 30, y + 14, BODY, pal.tan)
        stepper(d, pal, self.buttons, ("pts", -1), ("pts", 1), 240, y, str(self.pts), 210, 52)
        y += 90
        go = Button(("go",), 30, y, 420, 60)
        bevel(d, pal, go.x, go.y, go.w, go.h, pal.btn_ok, t=3)
        text_center(d, pal, "Continue to %d%s" % (self.n, self.side), 240, y + 20, BODY, pal.ok_fg)
        self.buttons.append(go)
        y += 74
        win = Button(("win",), 30, y, 420, 60)
        bevel(d, pal, win.x, win.y, win.w, win.h, pal.card_hi, t=3)
        text_center(d, pal, "That was the final stage - Victory!", 240, y + 20, BODY, pal.gold)
        self.buttons.append(win)
        # A way out. The modal opens off game.pending_stage, so declining has
        # to clear that flag or it reopens on the next draw - and without it
        # a stage marked complete in error was unrecoverable: both other
        # buttons advance the quest.
        y += 66
        no = Button(("not_yet",), 30, y, 420, 44)
        bevel(d, pal, no.x, no.y, no.w, no.h, pal.btn_no, t=3)
        text_center(d, pal, "Not yet - go back", 240, y + 12, BODY, pal.no_fg)
        self.buttons.append(no)

    def on_button(self, btn):
        k = btn.id[0]
        if k == "not_yet":
            self.game.pending_stage = None
            return "cancel"
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
        # First seat that is at its points. The guided flow resolves them one
        # at a time, so the next _derive() picks up the next one.
        for loc in g.active_locations:
            if loc["points"] > 0 and loc["progress"] >= loc["points"]:
                return {"kind": "location", "progress": loc["progress"],
                        "points": loc["points"],
                        "name": loc.get("name") or "Active location"}
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
        text_center(d, pal, label, 240, y + h // 2 - 10, BODY, pal.ok_fg if ok else pal.no_fg)
        self.buttons.append(b)

    def _draw_done(self, d, pal):
        text_center(d, pal, "All resolved", 240, 200, DISPLAY, pal.gold)
        self._cta(d, pal, "Continue", ("close",))

    def _draw_reveal(self, d, pal, st):
        text_center(d, pal, "STAGE %d REVEALED" % st["stage_n"], 240, 64, BODY, pal.amber)
        name = truncate_text(st["face_a"].get("name") or "", DISPLAY, 432, d.measure_text)
        text_center(d, pal, name, 240, 92, DISPLAY, pal.gold)
        tip_x, tip_w, tip_y = 24, 432, 130
        ribbon_h, pad_top, line_h, pad_bottom, max_lines = 22, 10, 24, 10, 5
        raw = st["face_a"].get("text")
        body = raw if raw else "No setup instructions for this stage."
        lines = wrap_text(body, BODY, tip_w - 28, measure=d.measure_text)[:max_lines]
        tip_h = ribbon_h + pad_top + len(lines) * line_h + pad_bottom
        d.set_pen(pal.border_gold); d.rectangle(tip_x, tip_y, tip_w, tip_h)
        d.set_pen(pal.bg); d.rectangle(tip_x + 2, tip_y + 2, tip_w - 4, tip_h - 4)
        d.set_pen(pal.border_gold); d.rectangle(tip_x + 4, tip_y + 4, tip_w - 8, tip_h - 8)
        d.set_pen(pal.scroll); d.rectangle(tip_x + 6, tip_y + 6, tip_w - 12, tip_h - 12)
        d.set_pen(pal.border_gold); d.rectangle(tip_x, tip_y, tip_w, ribbon_h)
        text_left(d, pal, "STAGE ADVANCE - RESOLVE NOW", tip_x + 10, tip_y + 6, LABEL, pal.bg, shadow=False)
        ly = tip_y + ribbon_h + pad_top
        for ln in lines:
            text_left(d, pal, ln, tip_x + 14, ly, BODY, pal.tan)
            ly += line_h
        self._cta(d, pal, "Flip to Side B  ->  %d qp" % st["next_points"], ("do_flip",))

    def _draw_location(self, d, pal, st):
        text_center(d, pal, "Location Explored", 240, 90, DISPLAY, pal.gold)
        # The card's own name when the player picked it from the catalog,
        # else the generic "Active location" _step() falls back to.
        text_center(d, pal, truncate_text(st["name"], BODY, 432, d.measure_text),
                    240, 126, BODY, pal.muted)
        text_center(d, pal, "%d/%d progress" % (st["progress"], st["points"]), 240, 152, BODY, pal.tan)
        excess = st["progress"] - st["points"]
        if excess:
            text_center(d, pal, "%d excess -> quest card" % excess, 240, 178, BODY, pal.amber)
        self._cta(d, pal, "Continue", ("resolve_location",))

    # Branch rows quote the alternative stages' own printed text, so the
    # preview is card text and gets BODY like every other quote. The rows grow
    # to hold it (they were 64px with a one-line LABEL preview) instead of the
    # type shrinking to fit them: the stride is whatever the space left below
    # the header divides into, capped so a 2-way split does not sprawl, and
    # the preview takes as many BODY lines as the resulting row height allows.
    BRANCH_Y0 = 116
    BRANCH_STRIDE_MAX = 106
    BRANCH_LH = 24

    def _draw_branch(self, d, pal, st):
        text_center(d, pal, "Choose a path", 240, 56, DISPLAY, pal.gold)
        # ALL CAPS both ways: this slot names how the choice gets made and is
        # read as chrome under the title, not as a sentence.
        text_center(d, pal, "FIRST PLAYER CHOOSES" if st["mode"] != "random" else "RANDOM",
                    240, 86, LABEL, pal.dim)
        cards = st["cards"]
        reserve = 50 if st["mode"] == "random" else 0    # the Randomize button
        stride = min(self.BRANCH_STRIDE_MAX,
                     (468 - self.BRANCH_Y0 - reserve) // max(1, len(cards)))
        row_h = max(48, stride - 10)
        max_lines = max(1, (row_h - 34) // self.BRANCH_LH)
        usable = 432 - 28
        y = self.BRANCH_Y0
        for i, card in enumerate(cards):
            b_face = next((f for f in card["faces"] if f["side"] == "B"), {})
            b = Button(("pick_branch", i), 24, y, 432, row_h)
            sel = self.branch_pick == i
            bevel(d, pal, b.x, b.y, b.w, b.h, pal.btn_ok if sel else pal.btn, t=3)
            text_left(d, pal, b_face.get("name") or "?", b.x + 14, y + 10, BODY,
                      pal.ok_fg if sel else pal.tan)
            lines = wrap_text(b_face.get("text") or "", BODY, usable, d.measure_text)
            if len(lines) > max_lines:
                lines = lines[:max_lines]
                lines[-1] = truncate_text(lines[-1] + " ..", BODY, usable, d.measure_text)
            ly = y + 38
            for ln in lines:
                if ln:
                    text_left(d, pal, ln, b.x + 14, ly, BODY, pal.dim)
                ly += self.BRANCH_LH
            self.buttons.append(b)
            y += stride
        if st["mode"] == "random":
            r = Button(("randomize_branch",), 24, y, 432, 40)
            bevel(d, pal, r.x, r.y, r.w, r.h, pal.card, t=2)
            text_center(d, pal, "Randomize for me", 240, y + 10, BODY, pal.tan)
            self.buttons.append(r)

    def _draw_advance(self, d, pal, st):
        text_center(d, pal, "Quest %s cleared" % st["cleared"], 240, 90, DISPLAY, pal.gold)
        if st["underfilled"]:
            text_center(d, pal, "Progress hasn't reached target - confirm", 240, 130, BODY, pal.red)
        self._cta(d, pal, "Reveal Stage %d" % st["next_stage"], ("do_advance",))

    def _draw_victory(self, d, pal, st):
        text_center(d, pal, "Quest %s cleared" % st["cleared"], 240, 70, BODY, pal.tan)
        text_center(d, pal, "That was the final stage!", 240, 110, DISPLAY, pal.gold)
        self._cta(d, pal, "Declare Victory", ("declare_victory",), y=340)
        self._cta(d, pal, "Not yet - keep playing", ("continue_without_victory",), y=404, ok=False)

    def _draw_side_quest(self, d, pal, st):
        text_center(d, pal, st["name"], 240, 90, DISPLAY, pal.gold)
        text_center(d, pal, "%d/%d" % (st["progress"], st["points"]), 240, 130, BODY, pal.tan)
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
    """Read-only card reference (M4-B): one **card side per page**, paged flat
    across every stage, every alternative and every face of the loaded
    scenario snapshot (game.stages, copied at preload - no catalog re-read),
    or of a `stages` list handed in directly (preview mode, see __init__).

    It is a reference, not a game view, so branch structure deliberately does
    not shape it: a stage's alternatives are simply more pages rather than a
    toggle, and nothing here reads or writes the branch the game actually
    took. Purely presentational - page/detail are the modal's own state,
    never written back to game.

    Long card text and the stage's tips are both shown truncated inline with
    a "more" affordance; tapping either opens a full-page detail view of it
    (scale 1, where every catalogued face fits - the longest is 11 lines)."""

    MARGIN = 12
    # Fixed bottom nav, so the reading area above it is the same height on
    # every page (the previous layout let the pager float up under short text,
    # which meant the body started at a different y on every card).
    NAV_Y = 424
    NAV_H = 44
    BODY_Y0 = 130
    DETAIL_Y0 = 78
    # One wrapped body line. This was 26, hand-copied from note_panel's old
    # formula, so card text stepped 2px looser than every guidance band on
    # the play screen for no stated reason.
    LH = band_line_h(BODY)
    TIPS_LINES = 2          # inline peek before "more" takes over
    TIPS_H = 18 + TIPS_LINES * LH + 8

    def __init__(self, game, tips=None, stages=None, scenario=None):
        self.game = game
        # Preview mode: Scenario Options opens this BEFORE the scenario is
        # preloaded into the game, so it passes the picked scenario's stages
        # and index entry directly. Everything below reads these, never the
        # game - the modal was already read-only, this just names its source.
        self.preview = stages is not None
        self.stages = game.stages if stages is None else stages
        self.scenario = (game.scenario or {}) if scenario is None else (scenario or {})
        self.buttons = []
        self.tips = tips or {}          # loaded tips.json "scenarios" map (M4-B tips)
        self.detail = None              # None | "tips" | "text" - full-page views
        self.detail_page = 0
        self._tips_data = None          # tips_for(...) for the current stage, set by draw()
        self.page = self._live_page()

    # -- page model ------------------------------------------------------
    def _pages(self):
        """(stage_idx, card_idx, face_idx) for every face, in catalog order."""
        out = []
        for si, st in enumerate(self.stages or []):
            for ci, card in enumerate(st.get("cards") or []):
                for fi in range(len(card.get("faces") or [])):
                    out.append((si, ci, fi))
        return out

    def _at(self, page):
        si, ci, fi = page
        st = self.stages[si]
        card = st["cards"][ci]
        return st, card, card["faces"][fi]

    def _live_page(self):
        """Index of the page the game is actually on. In preview there is no
        live side yet and stage 1A is where play begins, so page 0."""
        pages = self._pages()
        if not pages or self.preview:
            return 0
        want = (self.game.quest or {}).get("side", "A")
        for i, p in enumerate(pages):
            si, ci, _ = p
            if si == self.game.stage_idx and ci == self.game.card_idx:
                if (self._at(p)[2].get("side") or "A") == want:
                    return i
        return 0

    def _label(self, page):
        st, _, face = self._at(page)
        return "Stage %d%s" % (st["stage"], face.get("side") or "")

    # -- shared bits -----------------------------------------------------
    def _body_text(self, face):
        return face.get("text") or ""

    MORE = " [...] more"

    def _fit(self, d, lines, max_lines, usable, more):
        """Trims to max_lines, marking the cut with "[...] more" so a
        truncated card never looks like the whole card. The marker has to be
        made room for, not appended and truncated - doing the latter cuts the
        marker itself down to "[...." and the affordance disappears."""
        if len(lines) <= max_lines and not more:
            return lines, False
        keep = lines[:max_lines] or [""]
        mw = d.measure_text(self.MORE, BODY)
        last = keep[-1]
        while last and d.measure_text(last, BODY) + mw > usable:
            last = last.rsplit(" ", 1)[0] if " " in last else last[:-1]
        keep[-1] = last + self.MORE
        return keep, True

    def _nav(self, d, pal, pages):
        """Prev/Next, equal width, pinned to the bottom and labelled with the
        page they lead to. Hidden (not just disabled) at each end."""
        M = self.MARGIN
        half = (480 - 2 * M - 8) // 2
        if self.page > 0:
            b = Button(("prev",), M, self.NAV_Y, half, self.NAV_H)
            bevel(d, pal, b.x, b.y, b.w, b.h, pal.btn)
            text_center(d, pal, truncate_text("< " + self._label(pages[self.page - 1]),
                                              BODY, half - 16, d.measure_text),
                        b.x + half // 2, b.y + 14, BODY, pal.tan)
            self.buttons.append(b)
        if self.page < len(pages) - 1:
            b = Button(("next",), M + half + 8, self.NAV_Y, half, self.NAV_H)
            bevel(d, pal, b.x, b.y, b.w, b.h, pal.btn)
            text_center(d, pal, truncate_text(self._label(pages[self.page + 1]) + " >",
                                              BODY, half - 16, d.measure_text),
                        b.x + half // 2, b.y + 14, BODY, pal.tan)
            self.buttons.append(b)

    def _detail_lines(self, d, usable):
        """The full content behind a "more" tap - at BODY, like everything
        else. It used to render at LABEL so it would fit on one page, which
        is exactly backwards: this view exists to give the text ROOM. When it
        does not fit, it pages (see _detail_capacity)."""
        if self.detail == "tips":
            t = self._tips_data or {"tips": []}
            lines = []
            for tip in t["tips"]:
                lines.extend(wrap_text("- " + tip, BODY, usable, d.measure_text))
            attribution = t.get("attribution") or {}
            for extra in (("Source: " + attribution["name"]) if attribution.get("name") else "",
                          attribution.get("url") or ""):
                if extra:
                    lines.append(("ATTRIB", truncate_text(extra, LABEL, usable, d.measure_text)))
            return lines
        _, _, face = self._at(self._pages()[self.page])
        return wrap_text(self._body_text(face) or "no text", BODY, usable, d.measure_text)

    def _detail_capacity(self):
        """Lines of BODY text one detail page holds."""
        return max(1, (self.NAV_Y - 12 - self.DETAIL_Y0 - 10) // self.LH)

    def _draw_detail(self, d, pal, title):
        M, W = self.MARGIN, 480 - 2 * self.MARGIN
        usable = W - 20
        lines = self._detail_lines(d, usable)
        cap = self._detail_capacity()
        pages = max(1, (len(lines) + cap - 1) // cap)
        self.detail_page = max(0, min(self.detail_page, pages - 1))
        chunk = lines[self.detail_page * cap:(self.detail_page + 1) * cap]

        text_left(d, pal, truncate_text(title, BODY, W, d.measure_text), M, 48, BODY, pal.gold)
        y = self.DETAIL_Y0
        panel(d, pal, M, y, W, self.NAV_Y - 12 - y, fill=pal.card)
        ty = y + 10
        for ln in chunk:
            if isinstance(ln, tuple):
                text_left(d, pal, ln[1], M + 10, ty, LABEL, pal.dim)
                ty += 16
            else:
                text_left(d, pal, ln, M + 10, ty, BODY, pal.tan)
                ty += self.LH

        # Back always; a "More" pager only when the text genuinely needs one.
        half = (480 - 2 * M - 8) // 2
        w = half if pages > 1 else 480 - 2 * M
        b = Button(("back",), M, self.NAV_Y, w, self.NAV_H)
        bevel(d, pal, b.x, b.y, b.w, b.h, pal.btn)
        text_center(d, pal, "Back", b.x + w // 2, b.y + 14, BODY, pal.tan)
        self.buttons.append(b)
        if pages > 1:
            nb = Button(("detail_more",), M + half + 8, self.NAV_Y, half, self.NAV_H)
            bevel(d, pal, nb.x, nb.y, nb.w, nb.h, pal.btn)
            text_center(d, pal, "More %d/%d >" % (self.detail_page + 1, pages),
                        nb.x + half // 2, nb.y + 14, BODY, pal.tan)
            self.buttons.append(nb)

    # -- draw ------------------------------------------------------------
    def draw(self, hw, game, pal):
        from ui.header import modal_header
        d = hw.display
        self.buttons = []
        d.set_pen(pal.bg)
        d.clear()
        modal_header(d, pal, game, "Quest Cards", self.buttons)
        M, W = self.MARGIN, 480 - 2 * self.MARGIN

        pages = self._pages()
        if not pages:
            text_center(d, pal, "No quest loaded", 240, 200, BODY, pal.dim)
            text_center(d, pal, "Start a scenario to see stage cards.", 240, 226, BODY, pal.dim)
            return

        self.page = max(0, min(self.page, len(pages) - 1))
        page = pages[self.page]
        stage, card, face = self._at(page)
        side = face.get("side") or "A"
        self._tips_data = tips_for(self.scenario.get("slug"), stage["stage"], self.tips)

        if self.detail == "tips" and self._tips_data:
            self._draw_detail(d, pal, "Tips - Stage %d" % stage["stage"])
            return
        if self.detail == "text":
            self._draw_detail(d, pal, self._label(page))
            return
        self.detail = None

        # -- identity row: which card side, whether it is the live one, and
        # what it is worth. The quest points sit here (they used to own a
        # whole block-level row) - it is one number, it belongs in a corner.
        y = 48
        text_left(d, pal, self._label(page), M, y, BODY, pal.amber)
        pts = "%d pts" % card.get("questPoints", 0)
        text_left(d, pal, pts, 480 - M - d.measure_text(pts, BODY), y, BODY, pal.gold)
        if self.page == self._live_page():
            pw = d.measure_text("CURRENT", LABEL) + 14
            d.set_pen(pal.gold)
            d.rectangle(240 - pw // 2, y + 2, pw, 18)
            text_center(d, pal, "CURRENT", 240, y + 6, LABEL, pal.bg, shadow=False)
        y += 26

        # Victory/sailing are rare, so they cost a row only when present.
        # ALL CAPS: this is a keyword badge sitting beside the card name, read
        # as chrome rather than as a sentence, so the casing carries the
        # demotion instead of the size (design system, LABEL).
        extra = []
        if card.get("victory") is not None:
            extra.append("VICTORY %d" % card["victory"])
        if card.get("sailing"):
            extra.append("SAILING")
        if extra:
            s = "  ".join(extra)
            text_left(d, pal, s, 480 - M - d.measure_text(s, LABEL), y, LABEL, pal.dim)

        text_left(d, pal, truncate_text(face.get("name") or "(unnamed)", BODY, W, d.measure_text),
                  M, y, BODY, pal.gold)
        y += 28
        # The card's own text usually leads with "Setup:", which IS the
        # heading - printed, at BODY, and legible. Repeating it in LABEL
        # chrome above gave the section two headings, the smaller of which
        # read as stray text. Show the label only when the text does not
        # already name the section. The printed text is never edited: rule 4
        # prefers a card's own words, and this is a card's own words.
        heading = "SETUP / STORY" if side == "A" else "QUEST"
        body_leads = (self._body_text(face) or "").lstrip().lower()
        if not body_leads.startswith(heading.split(" / ")[0].lower() + ":"):
            text_left(d, pal, heading, M, y, LABEL, pal.amber)

        # -- body: the card's own text, at the same scale as everywhere else.
        # It gets every pixel between here and whatever sits below (the tips
        # peek, or the nav), and marks its own truncation.
        has_tips = bool(self._tips_data)
        tips_y = self.NAV_Y - 12 - self.TIPS_H
        body_bottom = (tips_y - 8) if has_tips else (self.NAV_Y - 12)
        by = self.BODY_Y0
        usable = W - 20
        text = self._body_text(face)
        lines = wrap_text(text or "no text", BODY, usable, d.measure_text)
        lines, cut = self._fit(d, lines, max(1, (body_bottom - by) // self.LH), usable, False)
        panel(d, pal, M, by - 8, W, body_bottom - by + 8, fill=pal.card)
        ty = by
        for ln in lines:
            text_left(d, pal, ln, M + 10, ty, BODY, pal.tan if text else pal.dim)
            ty += self.LH
        if cut:
            self.buttons.append(Button(("more_text",), M, by - 8, W, body_bottom - by + 8))

        # -- tips peek: the first lines inline, the rest behind a tap -------
        if has_tips:
            joined = "  ".join(self._tips_data["tips"])
            tl = wrap_text(joined, BODY, usable, d.measure_text)
            tl, _ = self._fit(d, tl, self.TIPS_LINES, usable, len(tl) > self.TIPS_LINES)
            panel(d, pal, M, tips_y, W, self.TIPS_H, fill=pal.card)
            text_left(d, pal, "TIPS", M + 10, tips_y + 6, LABEL, pal.amber)
            ty = tips_y + 22
            for ln in tl:
                text_left(d, pal, ln, M + 10, ty, BODY, pal.tan)
                ty += self.LH
            self.buttons.append(Button(("tips",), M, tips_y, W, self.TIPS_H))

        self._nav(d, pal, pages)

    def on_button(self, btn):
        k = btn.id[0]
        if k == "close":
            return "close"
        if k == "back":
            self.detail = None
            self.detail_page = 0
            return "redraw"
        if not self.stages:
            return None
        if k == "tips":
            if self._tips_data:
                self.detail = "tips"
                self.detail_page = 0
                return "redraw"
            return None
        if k == "more_text":
            self.detail = "text"
            self.detail_page = 0
            return "redraw"
        if k == "detail_more":
            self.detail_page += 1     # _draw_detail clamps; wrap is handled there
            return "redraw"
        n = len(self._pages())
        if k == "next" and self.page < n - 1:
            self.page += 1
            return "redraw"
        if k == "prev" and self.page > 0:
            self.page -= 1
            return "redraw"
        return None



def _pick_radio(d, pal, cx, cy, on):
    """Radio-button glyph: ring, filled when selected. Duplicates
    ui/screen_quest.py's _radio (this codebase's screen/modal helpers are
    per-file, not cross-imported - e.g. _footer/footer and circ_btn/circBtn
    already exist independently in this file vs. the web twin) so the pickers
    in this file can "feel like the same family" as ChooseScenarioScreen
    without a new cross-module dependency. Shared by SideQuestPickModal and
    LocationPickModal."""
    arc_runs(d, cx, cy, 10, 8, 0, 360, pal.gold if on else pal.dim)
    if on:
        disc(d, cx, cy, 5, pal.gold)


class SideQuestPickModal:
    """Two-step picker over the player side-quest catalog: **sphere first,
    then the quest**, mirroring the Pick Cycle -> Choose Scenario drill in
    ui/screen_quest.py (same row stride, pager geometry and radio glyph).

    Step 1 lists each sphere present in the catalog with its quest count and
    a chevron; step 2 is the radio list for that sphere, with a "< Spheres"
    back button, Add (commits) and Manual (blank-entry fallback). Manual is
    reachable from both steps.

    Sphere order follows the Rules Reference's own "Spheres of Influence"
    diagram (Leadership, Lore, Spirit, Tactics), then Neutral, then anything
    else. Cards whose sphere the catalog does not carry are grouped last
    under NO_SPHERE rather than guessed into one: the four campaign side
    quests from the Angmar Awakened Campaign Expansion have no sphere in the
    card DB (that pack reuses the column for Boon/Burden), and inventing a
    sphere for them would be a rules claim we cannot source.

    Opened from QuestingProgressModal's "+ Side quest" button via the
    pending_side_quest_pick flag (see main.py's loop) - constructed with the
    already-loaded catalog entries (quest_catalog.side_quests(...) shape:
    {"id","name","points","sphere","pack"}), never reads the catalog itself.
    On the way out it sets game.pending_progress_detail so the router reopens
    the Progress modal you came from.

    Empty `entries` (no catalog data) still renders and offers Manual rather
    than raising - defense in depth."""

    PER_PAGE = 6
    ROW_H = 44
    ROW_STRIDE = 46
    LIST_Y0 = 66
    NAME_MAX_W = 300
    FOOTER_Y = 404
    FOOTER_H = 64
    NO_SPHERE = "No sphere"
    SPHERE_ORDER = ("Leadership", "Lore", "Spirit", "Tactics", "Neutral")

    def __init__(self, game, entries):
        self.game = game
        self.entries = entries
        self.sphere = None          # None = step 1 (pick a sphere)
        self.selected = None
        self.page = 0
        self.buttons = []

    # -- grouping --------------------------------------------------------
    def _sphere_of(self, e):
        return e.get("sphere") or self.NO_SPHERE

    def spheres(self):
        """[(sphere, count), ...] in the rulebook's order, unknown last."""
        counts = {}
        for e in self.entries:
            k = self._sphere_of(e)
            counts[k] = counts.get(k, 0) + 1
        out = [(s, counts[s]) for s in self.SPHERE_ORDER if s in counts]
        rest = sorted(k for k in counts
                      if k not in self.SPHERE_ORDER and k != self.NO_SPHERE)
        out += [(k, counts[k]) for k in rest]
        if self.NO_SPHERE in counts:
            out.append((self.NO_SPHERE, counts[self.NO_SPHERE]))
        return out

    def in_sphere(self):
        return [e for e in self.entries if self._sphere_of(e) == self.sphere]

    def _rows(self):
        return self.spheres() if self.sphere is None else self.in_sphere()

    def _pages(self):
        return max(1, -(-len(self._rows()) // self.PER_PAGE))

    # -- draw ------------------------------------------------------------
    def draw(self, hw, game, pal):
        from ui.header import modal_header
        d = hw.display
        self.buttons = []
        d.set_pen(pal.bg)
        d.clear()
        modal_header(d, pal, game, "Add Side Quest", self.buttons)

        if not self.entries:
            text_center(d, pal, "No side-quest catalog data available.", 240, 140, BODY, pal.dim)
            text_center(d, pal, "Use Manual entry below.", 240, 168, BODY, pal.dim)
        elif self.sphere is None:
            self._draw_spheres(d, pal)
        else:
            self._draw_quests(d, pal)

        manual = Button(("manual",), 24, self.FOOTER_Y, 200, self.FOOTER_H)
        bevel(d, pal, manual.x, manual.y, manual.w, manual.h, pal.btn, t=3)
        text_center(d, pal, "Manual", manual.x + manual.w / 2, manual.y + 20, BODY, pal.tan)
        self.buttons.append(manual)

        if self.entries and self.sphere is not None:
            add = Button(("add",), 256, self.FOOTER_Y, 200, self.FOOTER_H)
            bevel(d, pal, add.x, add.y, add.w, add.h, pal.btn_ok, t=3)
            text_center(d, pal, "Add", add.x + add.w / 2, add.y + 20, BODY, pal.ok_fg)
            self.buttons.append(add)

    def _pager(self, d, pal, pages):
        if pages <= 1:
            return
        up = Button(("older",), 12, 352, 150, 46)
        dn = Button(("newer",), 318, 352, 150, 46)
        bevel(d, pal, up.x, up.y, up.w, up.h, pal.btn)
        text_center(d, pal, "Up", up.x + 75, up.y + 14, BODY, pal.tan)
        bevel(d, pal, dn.x, dn.y, dn.w, dn.h, pal.btn)
        text_center(d, pal, "Down", dn.x + 75, dn.y + 14, BODY, pal.tan)
        text_center(d, pal, "%d/%d" % (self.page + 1, pages), 240, 366, BODY, pal.muted)
        self.buttons.append(up)
        self.buttons.append(dn)

    def _draw_spheres(self, d, pal):
        text_left(d, pal, "Pick a sphere - or enter manually.", 12, 46, BODY, pal.dim)
        rows = self.spheres()
        pages = self._pages()
        self.page = min(self.page, pages - 1)
        chunk = rows[self.page * self.PER_PAGE:(self.page + 1) * self.PER_PAGE]
        y = self.LIST_Y0
        for sphere, count in chunk:
            text_left(d, pal, truncate_text(sphere, BODY, 320, d.measure_text),
                      20, y + 13, BODY, pal.tan)
            right = "%d quest%s" % (count, "" if count == 1 else "s")
            rw = d.measure_text(right, LABEL)
            text_left(d, pal, right, 436 - rw, y + 16, LABEL, pal.dim)
            d.set_pen(pal.dim)
            d.triangle(450, y + 17, 450, y + 27, 455, y + 22)
            d.set_pen(pal.border)
            d.rectangle(8, y + self.ROW_H, 456, 1)
            self.buttons.append(Button(("sphere", sphere), 8, y, 456, self.ROW_H))
            y += self.ROW_STRIDE
        self._pager(d, pal, pages)

    def _draw_quests(self, d, pal):
        text_left(d, pal, truncate_text("%s - pick one, then Add." % self.sphere,
                                        BODY, 456, d.measure_text),
                  12, 46, BODY, pal.dim)
        rows = self.in_sphere()
        pages = self._pages()
        self.page = min(self.page, pages - 1)
        chunk = rows[self.page * self.PER_PAGE:(self.page + 1) * self.PER_PAGE]
        y = self.LIST_Y0
        for e in chunk:
            on = e["id"] == self.selected
            if on:
                d.set_pen(pal.card_hi)
                d.rectangle(8, y, 456, self.ROW_H)
            _pick_radio(d, pal, 30, y + 22, on)
            name = truncate_text(e.get("name") or "", BODY, self.NAME_MAX_W, d.measure_text)
            text_left(d, pal, name, 52, y + 13, BODY, pal.tan if on else pal.muted)
            pts_s = "%d pts" % (e.get("points") or 0)
            pw = d.measure_text(pts_s, BODY)
            text_left(d, pal, pts_s, 456 - pw, y + 13, BODY, pal.gold if on else pal.tan)
            d.set_pen(pal.border)
            d.rectangle(8, y + self.ROW_H, 456, 1)
            self.buttons.append(Button(("row", e["id"]), 8, y, 456, self.ROW_H))
            y += self.ROW_STRIDE
        self._pager(d, pal, pages)
        back = Button(("back",), 12, self.FOOTER_Y - 56, 200, 44)
        bevel(d, pal, back.x, back.y, back.w, back.h, pal.btn)
        text_center(d, pal, "< Spheres", back.x + back.w / 2, back.y + 14, BODY, pal.tan)
        self.buttons.append(back)

    # -- input -----------------------------------------------------------
    def _leave(self):
        """Every exit reopens the Progress modal this was launched from."""
        self.game.pending_progress_detail = True
        return "close"

    def on_button(self, btn):
        k = btn.id[0]
        if k == "close":
            return self._leave()
        if k == "sphere":
            self.sphere = btn.id[1]
            quests = self.in_sphere()
            self.selected = quests[0]["id"] if quests else None
            self.page = 0
            return "redraw"
        if k == "back":
            self.sphere = None
            self.selected = None
            self.page = 0
            return "redraw"
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
            return self._leave()
        if k == "add":
            e = next((x for x in self.entries if x["id"] == self.selected), None)
            if e:
                pts = e.get("points") or 0
                self.game.side_quests.append({"points": pts, "progress": 0,
                                              "name": e.get("name")})
                self.game.log_event("Side quest added: %s (%d pts, progress view)"
                                    % (e.get("name"), pts))
            return self._leave()
        return None
