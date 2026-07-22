"""Play screen — guided per-round flow, one view per stage.

resource_planning -> quest_commit (per-player willpower) -> quest_staging
(totals with -/+) -> [resolve] -> quest_resolution (placement) -> travel ->
encounter -> combat -> refresh (end round). The header carries navigation.
"""

from gamestate import VIEW_ORDER
from ui.header import draw_header, HEADER_H, VIEW_LABEL
from ui.widgets import Button, panel, bevel, text_center, text_left, ribbon, note_panel
from ui.modal_counter import CounterModal
from ui.modals import LocationPickModal
from ui import icons

MARGIN = 8
STRIP_Y = HEADER_H + 10
CHIP_H = 56
PROG_Y = STRIP_Y + CHIP_H + 8          # progress row: immediately under threat
CONTENT_Y = PROG_Y + CHIP_H + 8        # everything else starts here
CTA_Y = 410
CTA_H = 58
GUTTER = MARGIN + 40


def draw_notif_pie(d, pal, cx, cy, r, frac, color="amber"):
    """Countdown indicator: full disc that loses a growing pac-man mouth as
    frac drops from 1.0 to 0. Drawn as a triangle fan (device-safe)."""
    import math
    d.set_pen(pal.card_hi)
    d.rectangle(cx - r - 2, cy - r - 2, 2 * r + 4, 2 * r + 4)
    steps = 24
    remaining = max(0, min(steps, int(frac * steps + 0.5)))
    d.set_pen(getattr(pal, color))
    start = -90 + (steps - remaining) * (360 // steps)  # mouth eats clockwise
    for i in range(remaining):
        a0 = math.radians(start + i * (360 / steps))
        a1 = math.radians(start + (i + 1) * (360 / steps))
        d.triangle(cx, cy,
                   cx + int(r * math.cos(a0)), cy + int(r * math.sin(a0)),
                   cx + int(r * math.cos(a1)), cy + int(r * math.sin(a1)))


class ScreenPlay:
    def __init__(self):
        self.buttons = []
        self.banner = None        # (text, kind, view-it-belongs-to)
        self.notif = None         # list of reminder lines, drawn as an overlay
        self.notif_frac = 1.0     # countdown fraction for the pie indicator
        self.notif_pie = None     # (cx, cy, r) of the pie, for partial updates
        self.notif_edge = "amber" # banner/pie color (leadership purple for windows)
        # resolution-view allocation state
        self.alloc = None

    # -- shared pieces -----------------------------------------------------
    def _chip_w(self, game):
        n = len(game.players)
        return (480 - GUTTER - MARGIN - (n - 1) * MARGIN) // n

    def _chips(self, d, pal, game):
        """Player threat chips behind the helm gutter icon. First player gets
        a book-ribbon marker."""
        chip_w = self._chip_w(game)
        icons.draw(d, icons.THREAT, MARGIN + 4, STRIP_Y + 18, pal.red)
        for i, p in enumerate(game.players):
            x = GUTTER + i * (chip_w + MARGIN)
            panel(d, pal, x, STRIP_Y, chip_w, CHIP_H, fill=pal.card)
            text_center(d, pal, "P%d" % (i + 1), x + chip_w / 2, STRIP_Y + 5, 2, pal.tan)
            val = "OUT" if p.eliminated else str(p.threat)
            text_center(d, pal, val, x + chip_w / 2, STRIP_Y + 26, 3,
                        pal.red if p.eliminated else pal.threat_pen(p.threat))
            if i == game.first_player:
                ribbon(d, pal, x + chip_w - 20, STRIP_Y + 1)
            self.buttons.append(Button(("thr", i), x, STRIP_Y, chip_w, CHIP_H))

    def _commit_row(self, d, pal, game, y):
        """Per-player willpower commit cards (sunburst gutter), chip-aligned."""
        chip_w = self._chip_w(game)
        icons.draw(d, icons.WILLPOWER, MARGIN + 4, y + 18, pal.gold)
        for i, p in enumerate(game.players):
            x = GUTTER + i * (chip_w + MARGIN)
            panel(d, pal, x, y, chip_w, 52, fill=pal.card_hi)
            text_center(d, pal, str(p.commit), x + chip_w / 2, y + 14, 3, pal.green)
            self.buttons.append(Button(("commit", i), x, y, chip_w, 52))

    def _progress_row(self, d, pal, game, allow_add=False):
        """Quest/location/side-quest progress cards at PROG_Y — same card
        sizing and column grid as the threat row (shrinks only if more cards
        than players). Trail gutter icon. Tap a SQ card (or +SQ where adding
        is appropriate) to manage side quests."""
        y = PROG_Y
        icons.draw(d, icons.TRAIL, MARGIN + 4, y + 18, pal.gold)
        cards = [("Q%d%s" % (game.quest["stage_n"], game.quest["side"]),
                  "%d/%d" % (game.quest["progress"], game.quest["points"]),
                  pal.gold, ("prog_q",))]
        if game.active_location is not None:
            cards.append(("LOC", "%d/%d" % (game.active_location["progress"],
                                            game.active_location["points"]),
                          pal.gold, ("prog_loc",)))
        for i, sq in enumerate(game.side_quests):
            cards.append(("SQ%d" % (i + 1), "%d/%d" % (sq["progress"], sq["points"]),
                          pal.gold, ("prog_sq", i)))
        if allow_add:
            cards.append(("+SQ", "", pal.dim, ("sq_add",)))
        n = len(cards)
        cw = min(self._chip_w(game),
                 (480 - GUTTER - MARGIN - (n - 1) * MARGIN) // n)
        for i, (label, val, pen, bid) in enumerate(cards):
            x = GUTTER + i * (cw + MARGIN)
            panel(d, pal, x, y, cw, CHIP_H, fill=pal.card)
            if val:
                text_center(d, pal, label, x + cw / 2, y + 5, 2, pal.tan)
                text_center(d, pal, val, x + cw / 2, y + 26, 3, pen)
            else:
                text_center(d, pal, label, x + cw / 2, y + 18, 2, pen)
            if bid:
                self.buttons.append(Button(bid, x, y, cw, CHIP_H))

    def _cta(self, d, pal, label, id, fill=None, fg=None):
        b = Button(id, MARGIN, CTA_Y, 480 - 2 * MARGIN, CTA_H)
        bevel(d, pal, b.x, b.y, b.w, b.h,
              fill if fill is not None else pal.btn_ok, t=3)
        text_center(d, pal, label, 240, CTA_Y + 20, 2, fg if fg is not None else pal.gold)
        self.buttons.append(b)

    def _totals_row(self, d, pal, game, y, with_steppers=False, tappable=()):
        half = (480 - 3 * MARGIN) // 2
        for idx, (label, val, pen, key, icon, ipen, shadow) in enumerate((
                ("Questing for", game.willpower, pal.gold, "wp",
                 icons.WILLPOWER_MD, pal.gold, True),
                ("Staging area", game.staging, pal.outline, "stg",
                 icons.THREAT_MD, pal.outline, False))):
            x = MARGIN + idx * (half + MARGIN)
            panel(d, pal, x, y, half, 84, fill=pal.card)
            text_center(d, pal, label, x + half / 2, y + 6, 2, pal.muted)
            # value + icon as a currency pair, icon matched to digit ink (28px)
            vw = d.measure_text(str(val), 4)
            gx = int(x + half / 2 - (vw + 8 + 28) / 2)
            text_left(d, pal, str(val), gx, y + 32, 4, pen, shadow=shadow)
            icons.draw(d, icon, gx + vw + 8, y + 32, ipen)
            if with_steppers:
                mn = Button((key + "-",), x + 8, y + 30, 52, 44)
                pl = Button((key + "+",), x + half - 60, y + 30, 52, 44)
                for b, s in ((mn, "-"), (pl, "+")):
                    bevel(d, pal, b.x, b.y, b.w, b.h, pal.btn)
                    text_center(d, pal, s, b.x + 26, b.y + 10, 3, pal.tan)
                    self.buttons.append(b)
                if key == "stg":
                    # center tap between the steppers -> encounter reminders
                    self.buttons.append(Button(("enc_rem",), x + 64, y, half - 128, 84))
                if key == "wp":
                    # center tap -> per-player commit adjustments
                    self.buttons.append(Button(("wp",), x + 64, y, half - 128, 84))
            elif key in tappable:
                self.buttons.append(Button((key,), x, y, half, 84))
                if key == "stg":
                    # dim high-end estimate of the upcoming staging reveal
                    text_center(d, pal, "reveal up to +%d" % game.staging_reveal_estimate(),
                                x + half / 2, y + 68, 1, pal.dim)

    # -- draw --------------------------------------------------------------
    def draw(self, hw, game, pal):
        d = hw.display
        self.buttons = []
        d.set_pen(pal.bg)
        d.clear()
        draw_header(d, pal, game, self.buttons)

        view = game.view
        if view == "setup_game":
            from gamestate import SETUP_TIP
            th = note_panel(d, pal, MARGIN, 56, 480 - 2 * MARGIN, SETUP_TIP)
            y = 56 + th + 18
            text_left(d, pal, "Stage 1B quest points", MARGIN + 8, y + 16, 2, pal.tan)
            mn = Button(("qp", -1), 300, y, 52, 48)
            pl = Button(("qp", 1), 412, y, 52, 48)
            for b, s in ((mn, "-"), (pl, "+")):
                bevel(d, pal, b.x, b.y, b.w, b.h, pal.btn)
                text_center(d, pal, s, b.x + 26, b.y + 12, 3, pal.tan)
                self.buttons.append(b)
            text_center(d, pal, str(game.quest["points"]), 382, y + 12, 3, pal.gold)
            text_left(d, pal, "so round 1 starts knowing the goal", MARGIN + 8, y + 58, 1, pal.dim)
            self._cta(d, pal, "Begin Round 1 >", ("advance",))
        elif view == "resource_planning":
            self._chips(d, pal, game)
            self._progress_row(d, pal, game, allow_add=True)
            note_panel(d, pal, MARGIN, CONTENT_Y + 6, 480 - 2 * MARGIN,
                       ["Collect resources.", "Draw cards.",
                        "Play allies and attachments."])
            self._cta(d, pal, "Quest >", ("advance",))
        elif view == "quest_commit":
            self._chips(d, pal, game)
            self._progress_row(d, pal, game)
            self._commit_row(d, pal, game, CONTENT_Y)
            th = note_panel(d, pal, MARGIN, CONTENT_Y + 60, 480 - 2 * MARGIN,
                            "Commit characters to the quest.")
            self.buttons.append(Button(("commit_tip",), MARGIN, CONTENT_Y + 60,
                                       480 - 2 * MARGIN, th))
            self._totals_row(d, pal, game, CONTENT_Y + 108, tappable=("wp", "stg"))
            self._cta(d, pal, "Quest (Staging) >", ("advance",))
        elif view == "quest_staging":
            self._chips(d, pal, game)
            self._progress_row(d, pal, game, allow_add=True)
            note_panel(d, pal, MARGIN, CONTENT_Y + 2, 480 - 2 * MARGIN,
                       "Reveal 1 encounter card per player.")
            self._totals_row(d, pal, game, CONTENT_Y + 52, with_steppers=True)
            if game.quest_resolved:
                self._cta(d, pal, "Travel >", ("advance",))
            else:
                diff = game.willpower - game.staging
                if diff > 0:
                    lbl = "Resolve Quest - success, +%d progress" % diff
                elif diff < 0:
                    lbl = "Resolve Quest - failure, +%d threat all" % (-diff)
                else:
                    lbl = "Resolve Quest - unsuccessful (tie)"
                self._cta(d, pal, lbl, ("resolve",))
        elif view == "quest_resolution":
            self._draw_resolution(d, pal, game)
        elif view == "travel":
            self._chips(d, pal, game)
            self._progress_row(d, pal, game)
            self._draw_travel(d, pal, game)
        elif view == "refresh":
            self._chips(d, pal, game)
            self._progress_row(d, pal, game)
            note_panel(d, pal, MARGIN, CONTENT_Y + 6, 480 - 2 * MARGIN,
                       ["Ready all exhausted cards.",
                        "Threat increases (automatic).",
                        "Pass the first player token."])
            self._cta(d, pal, "End round >", ("endround",))
        else:
            self._chips(d, pal, game)
            notes = {
                "enc_optional": "Each player may engage one enemy in the staging area (optional).",
                "enc_checks": "Engagement checks: enemies engage players whose threat >= their cost.",
                "combat_shadow": "Deal 1 shadow card to each engaged enemy.",
                "combat_enemy": "Enemies attack. Declare defenders, resolve shadow effects, apply damage.",
                "combat_player": "Players attack engaged enemies.",
            }
            flavor = {"combat_enemy": (icons.DEFENSE, pal.green),
                      "combat_player": (icons.ATTACK, pal.tan)}.get(view)
            self._progress_row(d, pal, game)
            h = note_panel(d, pal, MARGIN, CONTENT_Y + 6, 480 - 2 * MARGIN,
                           notes.get(view, ""),
                           reserve_right=34 if flavor else 0)
            if flavor:
                icons.draw(d, flavor[0], 480 - MARGIN - 34,
                           CONTENT_Y + 6 + (h - 20) // 2, flavor[1])
            i = VIEW_ORDER.index(view)
            nxt = VIEW_ORDER[(i + 1) % len(VIEW_ORDER)]
            self._cta(d, pal, "%s >" % VIEW_LABEL.get(nxt, nxt), ("advance",))

        # rulebook turn chart: green = player action window after framework
        # steps. The banner takes priority over the tag (same slot).
        if self.notif:
            from ui.widgets import wrap_text
            entries = []
            for e in self.notif:
                if isinstance(e, tuple):
                    entries.append(e if len(e) == 3 else (e[0], e[1], "amber"))
                else:
                    entries.append((None, e, "amber"))
            has_icon = any(ic for ic, _s, _c in entries)
            edge = entries[0][2]
            self.notif_edge = edge
            tx0 = MARGIN + (48 if has_icon else 14)
            usable = 480 - MARGIN - 48 - tx0  # minus icon column + pie zone
            lines = []
            for _ic, s, c in entries:
                for ln in wrap_text(s, 2, usable, d.measure_text):
                    lines.append((ln, c))
            th = max(14 + 22 * len(lines), 40 if has_icon else 34)
            bevel(d, pal, MARGIN, HEADER_H + 2, 480 - 2 * MARGIN, th, pal.card_hi, t=2)
            d.set_pen(getattr(pal, edge))
            d.rectangle(MARGIN, HEADER_H + 2, 4, th)
            if has_icon:
                first_ic, _s, first_c = [e for e in entries if e[0]][0]
                icons.draw(d, getattr(icons, first_ic), MARGIN + 14,
                           HEADER_H + 2 + (th - 24) // 2, getattr(pal, first_c))
            ty = HEADER_H + 9
            for s, c in lines:
                text_left(d, pal, s, tx0, ty, 2, getattr(pal, c))
                ty += 22
            # pac-man countdown pie, right edge; tap anywhere to dismiss
            cx, cy, r = 480 - MARGIN - 22, HEADER_H + 2 + th // 2, 11
            self.notif_pie = (cx, cy, r)
            draw_notif_pie(d, pal, cx, cy, r, self.notif_frac, edge)
            self.buttons.append(Button(("notif_dismiss",), MARGIN, HEADER_H + 2,
                                       480 - 2 * MARGIN, th))
        else:
            self.notif_pie = None

        if self.banner and self.banner[2] == view:
            btext, bkind = self.banner[0], self.banner[1]
            bpen = {"good": pal.green, "bad": pal.red, "mid": pal.amber}[bkind]
            from ui.widgets import truncate_text
            btext = truncate_text(btext, 1, 480 - 2 * MARGIN, d.measure_text)
            text_center(d, pal, btext, 240, CTA_Y - 26, 1, bpen)

    def _draw_travel(self, d, pal, game):
        loc = game.active_location
        y = CONTENT_Y + 4

        if loc is None:
            y += note_panel(d, pal, MARGIN, y, 480 - 2 * MARGIN,
                            "Players may travel to 1 location. It becomes the active location.") + 10
            tb = Button(("travel_new",), MARGIN, y, 480 - 2 * MARGIN, 56)
            bevel(d, pal, tb.x, tb.y, tb.w, tb.h, pal.btn)
            text_center(d, pal, "Travel to location", 240, y + 18, 2, pal.tan)
            self.buttons.append(tb)
        else:
            y += note_panel(d, pal, MARGIN, y, 480 - 2 * MARGIN,
                            "Travel is only possible while there is no active location (rulebook).") + 10
            cb = Button(("travel_change",), MARGIN, y, 480 - 2 * MARGIN, 48)
            panel(d, pal, cb.x, cb.y, cb.w, cb.h, fill=pal.card)
            text_center(d, pal, "Replace location (card effect)", 240, y + 14, 2, pal.muted)
            self.buttons.append(cb)

        self._cta(d, pal, "Encounter (Opt. Engage) >", ("advance",))

    def _draw_resolution(self, d, pal, game):
        if self.alloc is None:
            a = game.auto_split(game.pending_budget)
            self.alloc = {"location": a["location"], "quest": a["quest"],
                          "side_quests": [0] * len(game.side_quests)}
        alloc = self.alloc
        used = alloc["location"] + alloc["quest"] + sum(alloc["side_quests"])
        remaining = game.pending_budget - used

        text_center(d, pal, "Place %d progress  (remaining %d)" %
                    (game.pending_budget, remaining), 240, HEADER_H + 8, 2, pal.gold)
        text_center(d, pal, "Location fills first; overflow -> quest. Adjust freely.",
                    240, HEADER_H + 34, 1, pal.muted)

        y = HEADER_H + 56
        rows = []
        if game.active_location is not None:
            rows.append(("location", None, "Active Location",
                         game.active_location["progress"], game.active_location["points"]))
        rows.append(("quest", None, "Quest %s" % game.quest_label(),
                     game.quest["progress"], game.quest["points"]))
        for i, sq in enumerate(game.side_quests):
            rows.append(("side", i, "Side quest %d" % (i + 1), sq["progress"], sq["points"]))

        for key, idx, label, cur, pts in rows:
            add = alloc["side_quests"][idx] if key == "side" else alloc[key]
            panel(d, pal, MARGIN, y, 480 - 2 * MARGIN, 56, fill=pal.card)
            text_left(d, pal, label, 22, y + 8, 2, pal.tan)
            text_left(d, pal, "%d + %d / %d" % (cur, add, pts), 22, y + 34, 1, pal.muted)
            mn = Button(("am", key, idx), 300, y + 8, 50, 40)
            pl = Button(("ap", key, idx), 414, y + 8, 50, 40)
            for b, s in ((mn, "-"), (pl, "+")):
                bevel(d, pal, b.x, b.y, b.w, b.h, pal.btn)
                text_center(d, pal, s, b.x + 25, b.y + 8, 3, pal.tan)
                self.buttons.append(b)
            text_center(d, pal, str(cur + add), 382, y + 14, 3, pal.gold)
            y += 62

        ab = Button(("aauto",), MARGIN, y + 4, 230, 44)
        bevel(d, pal, ab.x, ab.y, ab.w, ab.h, pal.btn)
        text_center(d, pal, "Auto loc->quest", ab.x + 115, ab.y + 12, 2, pal.tan)
        self.buttons.append(ab)
        rb = Button(("areset",), 250, y + 4, 110, 44)
        bevel(d, pal, rb.x, rb.y, rb.w, rb.h, pal.btn)
        text_center(d, pal, "Reset", rb.x + 55, rb.y + 12, 2, pal.tan)
        self.buttons.append(rb)

        if remaining > 0:
            # inert until the whole budget is placed
            b = Button(("apply_alloc_disabled",), MARGIN, CTA_Y, 480 - 2 * MARGIN, CTA_H)
            bevel(d, pal, b.x, b.y, b.w, b.h, pal.card, t=3)
            text_center(d, pal, "Place %d more to continue" % remaining,
                        240, CTA_Y + 20, 2, pal.dim)
        else:
            self._cta(d, pal, "Apply placement - Travel >", ("apply_alloc",))

    # -- interaction -------------------------------------------------------
    def on_button(self, btn, game):
        k = btn.id[0]
        if k == "nav":
            return ("goto", btn.id[1])
        if k == "thr":
            i = btn.id[1]

            def commit(v, i=i, game=game):
                before = game.players[i].threat
                game.adjust_threat(i, v - before)
                if game.players[i].threat != before:
                    game.log_event("P%d threat %d -> %d" % (i + 1, before, game.players[i].threat))
            return ("modal", CounterModal("P%d threat" % (i + 1), game.players[i].threat, on_commit=commit, icon="threat"))
        if k == "commit":
            from ui.modals import CommitModal
            return ("modal", CommitModal(game, btn.id[1]))
        if k == "wp":
            from ui.modals import QuestingForModal
            return ("modal", QuestingForModal(game))
        if k == "stg":
            def set_stg(v, game=game):
                game.staging = v
            return ("modal", CounterModal("Staging area threat", game.staging,
                                          on_commit=set_stg, icon="threat"))
        if k == "wp-":
            game.willpower = max(0, game.willpower - 1)
            return True
        if k == "wp+":
            game.willpower += 1
            return True
        if k == "stg-":
            game.staging = max(0, game.staging - 1)
            return True
        if k == "stg+":
            game.staging += 1
            return True
        if k == "resolve":
            res = game.resolve_quest(game.willpower, game.staging)
            if res["outcome"] == "success":
                game.pending_budget = res["budget"]
                game.enter_view("quest_resolution")
                self.alloc = None
            elif res["outcome"] == "fail":
                # stay on staging — show the outcome where it happened
                self.banner = ("Quest failed. +%d threat to all" % res["threat"],
                               "bad", "quest_staging")
            else:
                self.banner = ("Quest unsuccessful - tie, no change", "mid",
                               "quest_staging")
            return True
        if k in ("am", "ap"):
            key, idx = btn.id[1], btn.id[2]
            delta = 1 if k == "ap" else -1
            a = self.alloc
            used = a["location"] + a["quest"] + sum(a["side_quests"])
            if delta > 0 and used >= game.pending_budget:
                return True
            if key == "side":
                a["side_quests"][idx] = max(0, a["side_quests"][idx] + delta)
            else:
                a[key] = max(0, a[key] + delta)
            return True
        if k == "aauto":
            a = game.auto_split(game.pending_budget)
            self.alloc = {"location": a["location"], "quest": a["quest"],
                          "side_quests": [0] * len(game.side_quests)}
            return True
        if k == "areset":
            self.alloc = {"location": 0, "quest": 0,
                          "side_quests": [0] * len(game.side_quests)}
            return True
        if k == "apply_alloc":
            completed = game.place_progress(self.alloc)
            msg = "Placed %d progress" % game.pending_budget
            if completed:
                msg += " (" + ", ".join(completed) + ")"
            game.log_event(msg)
            game.pending_budget = 0
            self.alloc = None
            game.enter_view("travel")
            return True
        if k == "qp":
            game.quest["points"] = max(0, min(30, game.quest["points"] + btn.id[1]))
            return True
        if k == "notif_dismiss":
            self.notif = None
            return True
        if k == "commit_tip":
            from ui.modals import CommitModal
            return ("modal", CommitModal(game, 0))
        if k == "enc_rem":
            from ui.modals import RemindersModal
            return ("modal", RemindersModal(game))
        if k == "sq_add":
            from ui.modals import SideQuestsModal
            return ("modal", SideQuestsModal(game))
        if k == "prog_q":
            def commit(v, game=game):
                b = game.quest["progress"]
                if v != b:
                    game.quest["progress"] = v
                    game.log_event("Quest %s progress %d -> %d (manual)"
                                   % (game.quest_label(), b, v))
            return ("modal", CounterModal("Quest %s progress" % game.quest_label(),
                                          game.quest["progress"], on_commit=commit))
        if k == "prog_loc":
            def commit(v, game=game):
                b = game.active_location["progress"]
                if v != b:
                    game.active_location["progress"] = v
                    game.log_event("Location progress %d -> %d (manual)" % (b, v))
            return ("modal", CounterModal("Location progress",
                                          game.active_location["progress"],
                                          on_commit=commit))
        if k == "prog_sq":
            i = btn.id[1]

            def commit(v, i=i, game=game):
                b = game.side_quests[i]["progress"]
                if v != b:
                    game.side_quests[i]["progress"] = v
                    game.log_event("Side quest %d progress %d -> %d (manual)"
                                   % (i + 1, b, v))
            return ("modal", CounterModal("Side quest %d progress" % (i + 1),
                                          game.side_quests[i]["progress"],
                                          on_commit=commit))
        if k == "travel_new":
            return ("modal", LocationPickModal(game, mode="new"))
        if k == "travel_change":
            return ("modal", LocationPickModal(game, mode="change"))
        if k == "endround":
            game.end_round()
            self.banner = None
            return True
        if k == "advance":
            game.advance_view()
            self.banner = None
            return True
        return None
