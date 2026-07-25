"""Play screen - guided per-round flow, one view per stage.

resource_planning -> [quest_sailing] -> quest_commit (per-player willpower) ->
quest_staging (totals with -/+) -> quest_resolution (spreadsheet placement) ->
travel -> encounter -> combat -> refresh (end round). The header navigates.

Mirror of docs/js/screen_play.js - keep the two in lockstep.
"""

from gamestate import VIEW_ORDER, VIEW_LABELS, SETUP_TIP
from ui.header import draw_header, HEADER_H
from ui.widgets import (Button, panel, bevel, text_center, text_left, ribbon,
                        note_panel, phase_block, wrap_text, truncate_text, draw_heart,
                        draw_flag, disc, arc_runs, token, wx_small)
from ui.modal_counter import CounterModal
from ui.modals import LocationPickModal
from ui import icons

MARGIN = 8
ZONE_TOP = HEADER_H + 6                # top of the players/progress zones
CONTENT_Y = 150                        # zones end ~136; tips start below
CTA_Y = 410
CTA_H = 58


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
        self.alloc = None         # resolution-view allocation state
        self.toast = None         # [(icon, text, color)] picked up by the main loop

    # -- shared pieces -----------------------------------------------------
    def _players_zone(self, d, pal, game):
        """Flipped 3-row players matrix: P# header / threat token / willpower
        token, one shared tap target over the whole zone (columns are fixed -
        up to MAX_PLAYERS - not width-sized off the live player count like the
        old chips)."""
        pcx = [50, 82, 114, 146]
        threat_cy, will_cy = ZONE_TOP + 40, ZONE_TOP + 72
        text_center(d, pal, "P", 18, ZONE_TOP + 2, 2, pal.muted)
        # player threat helm keeps its red identity (charcoal dropshadow)
        icons.draw(d, icons.THREAT, 8, threat_cy - 9, pal.bevel_d)
        icons.draw(d, icons.THREAT, 7, threat_cy - 10, pal.red)
        icons.draw(d, icons.WILLPOWER, 7, will_cy - 10, pal.gold)
        for i, p in enumerate(game.players):
            cx = pcx[i]
            if i == game.first_player:
                d.set_pen(pal.gold)
                d.rectangle(cx - 12, ZONE_TOP - 2, 24, 19)
                text_center(d, pal, str(i + 1), cx, ZONE_TOP + 1, 2, pal.bg, shadow=False)
            else:
                text_center(d, pal, str(i + 1), cx, ZONE_TOP + 1, 2, pal.tan)
            danger = p.threat >= p.elimination - 10
            tfrac = p.threat / p.elimination if p.elimination > 0 else 0
            token(d, pal, cx, threat_cy, 14, 2,
                  "OUT" if p.eliminated else str(p.threat),
                  pal.red if p.eliminated else pal.value, tfrac,
                  pal.red if danger else pal.gold, pal.dim)
            if game.view == "quest_commit":
                wp_fill = pal.gold if p.commit_touched else pal.dim
            else:
                wp_fill = pal.gold
            token(d, pal, cx, will_cy, 14, 2, p.commit, pal.value, 1.0, wp_fill, pal.dim)
        self.buttons.append(Button(("players_detail",), 8, ZONE_TOP - 2, 156, 90))

    def _progress_zone(self, d, pal, game):
        """Flipped progress header + one circle row: Q / L / S1..Sn / sailing,
        one shared tap target over the whole zone. Columns are capped to what
        fits; overflow drops the newest side quests (Q, L, the oldest sides,
        and sailing always stay)."""
        d.set_pen(pal.border)
        d.rectangle(168, ZONE_TOP, 1, 90)
        cols = [("Q", game.quest["progress"], game.quest["points"])]
        if game.active_location is not None:
            cols.append(("L", game.active_location["progress"], game.active_location["points"]))
        side_cols = [("S%d" % (i + 1), sq["progress"], sq["points"])
                     for i, sq in enumerate(game.side_quests)]
        max_cols = (472 - 174) // 32
        fixed = len(cols) + (1 if game.sailing else 0)
        side_budget = max(0, max_cols - fixed)
        all_cols = cols + side_cols[:side_budget]
        for i, (label, prog, pts) in enumerate(all_cols):
            cx = 190 + i * 32
            text_center(d, pal, label, cx, ZONE_TOP + 2, 2, pal.tan)
            rem = max(0, pts - prog)
            frac = prog / pts if pts > 0 else 0
            token(d, pal, cx, ZONE_TOP + 40, 14, 2, rem, pal.value, frac, pal.gold, pal.dim)
        if game.sailing:
            scx = 190 + len(all_cols) * 32
            icons.draw(d, icons.WHEEL_SM, scx - 8, ZONE_TOP, pal.gold)
            disc(d, scx, ZONE_TOP + 40, 14, pal.well)
            for rank, (a0, a1) in enumerate([(272, 360), (0, 88), (92, 178), (182, 268)]):
                arc_runs(d, scx, ZONE_TOP + 40, 14, 11, a0, a1,
                         pal.dim if rank < game.heading else pal.gold)
            wx_small(d, pal, game.heading, scx, ZONE_TOP + 40, 6)
        text_left(d, pal, "quest points remaining", 174, ZONE_TOP + 66, 1, pal.dim)
        self.buttons.append(Button(("progress_detail",), 174, ZONE_TOP - 2, 298, 90))

    def _cta(self, d, pal, label, id, fill=None, fg=None):
        b = Button(id, MARGIN, CTA_Y, 480 - 2 * MARGIN, CTA_H)
        bevel(d, pal, b.x, b.y, b.w, b.h,
              fill if fill is not None else pal.btn_ok, t=3)
        text_center(d, pal, label, 240, CTA_Y + 20, 2, fg if fg is not None else pal.gold)
        self.buttons.append(b)

    def _bottom_bar(self, d, pal, x, w, bottom_y, frac, color):
        """2px progress bar along a card's bottom edge. Dim track + fill."""
        by = bottom_y - 2
        d.set_pen(pal.border)
        d.rectangle(x, by, w, 2)
        if frac > 0:
            d.set_pen(color)
            d.rectangle(x, by, max(1, int(round(w * min(1, frac)))), 2)

    def _totals_row(self, d, pal, game, y, with_steppers=False, tappable=()):
        half = (480 - 3 * MARGIN) // 2
        for idx, (label, val, pen, key, icon, ipen, shadow) in enumerate((
                ("Questing for", game.willpower, pal.value, "wp",
                 icons.WILLPOWER_MD, pal.gold, True),
                ("Staging area", game.staging, pal.outline, "stg",
                 icons.THREAT_MD, pal.outline, False))):
            x = MARGIN + idx * (half + MARGIN)
            panel(d, pal, x, y, half, 84, fill=pal.card)
            text_center(d, pal, label, x + half / 2, y + 6, 2, pal.muted)
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
                    self.buttons.append(Button(("enc_rem",), x + 64, y, half - 128, 84))
                if key == "wp":
                    self.buttons.append(Button(("wp",), x + 64, y, half - 128, 84))
            elif key in tappable:
                if key == "stg":
                    # thin inset dividers + tan ± glyphs (matches the mock — no
                    # button chrome). Left/right strips tap ±; centre = big editor.
                    d.set_pen(pal.border)
                    d.rectangle(x + 36, y + 8, 1, 56)
                    d.rectangle(x + half - 36, y + 8, 1, 56)
                    text_center(d, pal, "-", x + 18, y + 32, 3, pal.tan)
                    text_center(d, pal, "+", x + half - 18, y + 32, 3, pal.tan)
                    self.buttons.append(Button(("stg-",), x, y, 36, 84))
                    self.buttons.append(Button(("stg",), x + 36, y, half - 72, 84))
                    self.buttons.append(Button(("stg+",), x + half - 36, y, 36, 84))
                    text_center(d, pal, "+%d reveal estimate" % game.staging_reveal_estimate(),
                                x + half / 2, y + 64, 2, pal.dim)
                else:
                    self.buttons.append(Button((key,), x, y, half, 84))

    # -- draw --------------------------------------------------------------
    def draw(self, hw, game, pal):
        d = hw.display
        self.buttons = []
        d.set_pen(pal.bg)
        d.clear()
        view = game.view
        if view == "quest_setup":
            draw_header(d, pal, game, self.buttons, title="QUEST SETUP", round_label="R0")
        else:
            draw_header(d, pal, game, self.buttons)

        if view == "setup_game":
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
            sy = y + 50
            text_left(d, pal, "Sailing quest", MARGIN + 8, sy + 11, 2, pal.tan)
            icons.draw(d, icons.WHEEL, 160, sy + 7, pal.gold if game.sailing else pal.dim)
            sb = Button(("sail_toggle",), 300, sy, 164, 38)
            panel(d, pal, sb.x, sb.y, sb.w, sb.h, fill=pal.gold if game.sailing else pal.btn)
            text_center(d, pal, "On" if game.sailing else "Off", sb.x + 82, sb.y + 12, 2,
                        pal.bg if game.sailing else pal.tan, shadow=False)
            self.buttons.append(sb)
            self._cta(d, pal, "Begin Round 1", ("advance",))
        elif view == "quest_setup":
            self._players_zone(d, pal, game)
            self._progress_zone(d, pal, game)
            self._draw_quest_setup(d, pal, game)
        elif view == "resource_planning":
            self._players_zone(d, pal, game)
            self._progress_zone(d, pal, game)
            phase_block(d, pal, MARGIN, CONTENT_Y, 480 - 2 * MARGIN, [
                ("framework", "Collect resources. Draw cards."),
                ("window", "Play allies and attachments - your only window for permanents this round."),
            ])
            nxt = "quest_sailing" if game.sailing else "quest_commit"
            self._cta(d, pal, "Next Phase: %s" % VIEW_LABELS[nxt], ("advance",))
        elif view == "quest_commit":
            self._players_zone(d, pal, game)
            self._progress_zone(d, pal, game)
            # willpower now lives in the players matrix; note/totals start at CONTENT_Y
            ty = CONTENT_Y
            th = note_panel(d, pal, MARGIN, ty, 480 - 2 * MARGIN,
                            "Commit characters to the quest.")
            self.buttons.append(Button(("commit_tip",), MARGIN, ty, 480 - 2 * MARGIN, th))
            self._totals_row(d, pal, game, ty + 48, tappable=("wp", "stg"))
            self._cta(d, pal, "Next Phase: %s" % VIEW_LABELS["quest_staging"], ("advance",))
        elif view == "quest_sailing":
            self._draw_sailing(d, pal, game)
        elif view == "quest_staging":
            self._draw_staging(d, pal, game)
        elif view == "quest_resolution":
            self._draw_resolution(d, pal, game)
        elif view == "travel":
            self._players_zone(d, pal, game)
            self._progress_zone(d, pal, game)
            self._draw_travel(d, pal, game)
        elif view == "refresh":
            self._players_zone(d, pal, game)
            self._progress_zone(d, pal, game)
            note_panel(d, pal, MARGIN, CONTENT_Y + 6, 480 - 2 * MARGIN,
                       ["Ready all exhausted cards.",
                        "Threat increases (automatic).",
                        "Pass the first player token."])
            self._cta(d, pal, "End round (raise threat, pass token)", ("endround",))
        else:
            self._players_zone(d, pal, game)
            notes = {
                "enc_optional": "Each player may engage one enemy in the staging area (optional).",
                "enc_checks": "Engagement checks: enemies engage players whose threat >= their cost.",
                "combat_shadow": "Deal 1 shadow card to each engaged enemy.",
                "combat_enemy": "Enemies attack. Declare defenders, resolve shadow effects, apply damage.",
                "combat_player": "Players attack engaged enemies.",
            }
            ship_notes = {
                "combat_enemy": "Ships: only a ship can defend a ship-enemy. Undefended ship attacks must damage a ship you control.",
                "combat_player": "Ships: your ships attack only ship-enemies - but any character may attack a ship-enemy.",
            }
            flavor = {"combat_enemy": (icons.DEFENSE, pal.green),
                      "combat_player": (icons.ATTACK, pal.tan)}.get(view)
            self._progress_zone(d, pal, game)
            note_text = notes.get(view, "")
            if game.sailing and view in ship_notes:
                note_text = [note_text, ship_notes[view]]
            h = note_panel(d, pal, MARGIN, CONTENT_Y + 6, 480 - 2 * MARGIN,
                           note_text, reserve_right=34 if flavor else 0)
            if flavor:
                icons.draw(d, flavor[0], 480 - MARGIN - 34,
                           CONTENT_Y + 6 + (h - 20) // 2, flavor[1])
            i = VIEW_ORDER.index(view)
            nxt = VIEW_ORDER[(i + 1) % len(VIEW_ORDER)]
            self._cta(d, pal, "Next Phase: %s" % VIEW_LABELS.get(nxt, nxt), ("advance",))

        self._draw_notif(d, pal)

        if self.banner and self.banner[2] == view:
            btext, bkind = self.banner[0], self.banner[1]
            bpen = {"good": pal.green, "bad": pal.red, "mid": pal.amber}[bkind]
            btext = truncate_text(btext, 1, 480 - 2 * MARGIN, d.measure_text)
            text_center(d, pal, btext, 240, CTA_Y - 26, 1, bpen)

    def _draw_notif(self, d, pal):
        if not self.notif:
            self.notif_pie = None
            return
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
        usable = 480 - MARGIN - 48 - tx0
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
        cx, cy, r = 480 - MARGIN - 22, HEADER_H + 2 + th // 2, 11
        self.notif_pie = (cx, cy, r)
        draw_notif_pie(d, pal, cx, cy, r, self.notif_frac, edge)
        self.buttons.append(Button(("notif_dismiss",), MARGIN, HEADER_H + 2,
                                   480 - 2 * MARGIN, th))

    def _draw_sailing(self, d, pal, game):
        self._players_zone(d, pal, game)
        self._progress_zone(d, pal, game)
        if not game.sailing:
            note_panel(d, pal, MARGIN, CONTENT_Y + 6, 480 - 2 * MARGIN,
                       ["No Sailing keyword on this quest.",
                        "Enable it if the stage says Sailing."])
            eb = Button(("sail_toggle",), MARGIN, CONTENT_Y + 96, 480 - 2 * MARGIN, 52)
            bevel(d, pal, eb.x, eb.y, eb.w, eb.h, pal.btn)
            icons.draw(d, icons.WHEEL, 130, CONTENT_Y + 96 + 14, pal.gold)
            text_center(d, pal, "Enable Sailing", 254, CONTENT_Y + 96 + 16, 2, pal.tan)
            self.buttons.append(eb)
            self._cta(d, pal, "Next Phase: %s" % VIEW_LABELS["quest_commit"], ("advance",))
            return
        # tip: pipe medallion top-left; wheel glyph inline in the sentence
        tw, ty0 = 480 - 2 * MARGIN, CONTENT_Y + 6
        gutt, lh = 28 + 14, 26
        th = 3 * lh + 16
        d.set_pen(pal.card_hi)
        d.rectangle(MARGIN, ty0, tw, th)
        d.set_pen(pal.border_gold)
        d.rectangle(MARGIN, ty0, 4, th)
        icons.draw(d, icons.PIPE, MARGIN + 10, ty0 + 8, pal.gold)
        tx = MARGIN + 12 + gutt
        ly = ty0 + 8
        fp = "P%d" % (game.first_player + 1)
        text_left(d, pal, fp, tx, ly, 2, pal.muted)
        sx0 = tx + d.measure_text(fp, 2) + 6
        ribbon(d, pal, sx0, ly - 1, 10, 18)
        sx0 += 10 + 6
        text_left(d, pal, "exhausts characters (ships", sx0, ly, 2, pal.muted)
        ly += lh
        text_left(d, pal, "count), looks at that many cards.", tx, ly, 2, pal.muted)
        ly += lh
        icons.draw(d, icons.WHEEL_SM, tx, ly, pal.gold)
        text_left(d, pal, "found: move 1 step on-course.", tx + 22, ly, 2, pal.muted)
        sb = Button(("sail_modal",), MARGIN, ty0 + th + 10, 480 - 2 * MARGIN, 52)
        bevel(d, pal, sb.x, sb.y, sb.w, sb.h, pal.btn)
        icons.draw(d, icons.WHEEL, 150, sb.y + 14, pal.gold)
        text_center(d, pal, "Log sailing test", 262, sb.y + 16, 2, pal.tan)
        self.buttons.append(sb)
        self._cta(d, pal, "Next Phase: %s" % VIEW_LABELS["quest_commit"], ("advance",))

    def _draw_staging(self, d, pal, game):
        self._players_zone(d, pal, game)
        self._progress_zone(d, pal, game)
        tw, gutt, lh = 480 - 2 * MARGIN, 28 + 14, 26
        tx, usable = MARGIN + 12 + gutt, tw - 12 - gutt
        lines = wrap_text(
            "Reveal 1 encounter card per player and adjust staging area threat accordingly.",
            2, usable, d.measure_text)
        ty0 = CONTENT_Y + 2
        th = (len(lines) + 1) * lh + 16
        d.set_pen(pal.card_hi)
        d.rectangle(MARGIN, ty0, tw, th)
        d.set_pen(pal.border_gold)
        d.rectangle(MARGIN, ty0, 4, th)
        icons.draw(d, icons.PIPE, MARGIN + 10, ty0 + 8, pal.gold)
        ly = ty0 + 8
        for ln in lines:
            text_left(d, pal, ln, tx, ly, 2, pal.muted)
            ly += lh
        diff = game.willpower - game.staging
        if diff != 0:
            pre = "%s will gain %d " % ("You" if diff > 0 else "Each player", abs(diff))
            text_left(d, pal, pre, tx, ly, 2, pal.muted)
            px = tx + d.measure_text(pre, 2)
            ic = icons.TRAIL if diff > 0 else icons.THREAT_SM
            icons.draw(d, ic, px, ly - 1, pal.gold if diff > 0 else pal.red)
            text_left(d, pal, "at resolution.", px + len(ic) + 6, ly, 2, pal.muted)
        else:
            text_left(d, pal, "No change at resolution (tie).", tx, ly, 2, pal.muted)
        self._totals_row(d, pal, game, ty0 + th + 8, with_steppers=True)
        self._cta(d, pal, "Next Phase: %s" % VIEW_LABELS["quest_resolution"],
                  ("stage_advance",))

    def _draw_quest_setup(self, d, pal, game):
        """R0 pre-round-1 phase: stage 1A's setup text to resolve, then the
        first flip (1A -> 1B) that begins round 1. Reuses the standard zones
        (Task 8) - mirror of screen_play.js's _drawQuestSetup."""
        card = game.stages[game.stage_idx]["cards"][game.card_idx]
        a_face = next((f for f in card["faces"] if f["side"] == "A"), {})
        stage_label = "STAGE %d%s" % (game.quest["stage_n"], game.quest["side"])
        text_center(d, pal, stage_label, 240, CONTENT_Y, 2, pal.amber)
        name_y = CONTENT_Y + 22
        card_name = truncate_text(a_face.get("name") or "", 3, 480 - 2 * MARGIN, d.measure_text)
        text_center(d, pal, card_name, 240, name_y, 3, pal.gold)

        # Distinct scroll-style tip: a double gold frame + ribbon banner -
        # UNLIKE the standard note_panel() left-accent-bar style used
        # elsewhere, since this is the one moment that reads as "resolve
        # this printed text now".
        tip_x, tip_w, tip_y = MARGIN, 480 - 2 * MARGIN, name_y + 30
        ribbon_h, pad_top, line_h, pad_bottom, max_lines = 22, 10, 24, 10, 4
        usable = tip_w - 28
        raw = a_face.get("text")
        body = raw if raw else "No setup instructions for this stage."
        lines = wrap_text(body, 2, usable, measure=d.measure_text)
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            lines[max_lines - 1] = truncate_text(lines[max_lines - 1] + " ..", 2, usable,
                                                 d.measure_text)
        tip_h = ribbon_h + pad_top + len(lines) * line_h + pad_bottom
        d.set_pen(pal.border_gold)
        d.rectangle(tip_x, tip_y, tip_w, tip_h)
        d.set_pen(pal.bg)
        d.rectangle(tip_x + 2, tip_y + 2, tip_w - 4, tip_h - 4)
        d.set_pen(pal.border_gold)
        d.rectangle(tip_x + 4, tip_y + 4, tip_w - 8, tip_h - 8)
        d.set_pen(pal.scroll)
        d.rectangle(tip_x + 6, tip_y + 6, tip_w - 12, tip_h - 12)
        d.set_pen(pal.border_gold)
        d.rectangle(tip_x, tip_y, tip_w, ribbon_h)
        text_left(d, pal, "QUEST SETUP - resolve now", tip_x + 10, tip_y + 6, 1, pal.bg,
                  shadow=False)
        ly = tip_y + ribbon_h + pad_top
        for ln in lines:
            text_left(d, pal, ln, tip_x + 14, ly, 2, pal.tan)
            ly += line_h

        # Read-only card modal (M4-B) - see on_button; null for custom games
        # (no scenario loaded, nothing to show).
        card_btn = Button(("open_card_modal",), MARGIN, 358, 480 - 2 * MARGIN, 44)
        bevel(d, pal, card_btn.x, card_btn.y, card_btn.w, card_btn.h, pal.btn)
        text_center(d, pal, "View quest card", 240, card_btn.y + 14, 2, pal.tan)
        self.buttons.append(card_btn)

        self._cta(d, pal, "Flip to Side B  ->  %d qp" % card["questPoints"], ("flip_to_b",))

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
        self._cta(d, pal, "Next Phase: %s" % VIEW_LABELS["enc_optional"], ("advance",))

    def _outcome_toast(self, game):
        if game.quest_outcome == "success":
            return ("TRAIL", "Quested successfully! +%d progress" % game.quest_outcome_n, "green")
        if game.quest_outcome == "fail":
            return ("THREAT_SM", "Quest failed. +%d threat to all" % game.quest_outcome_n, "red")
        return (None, "Quest unsuccessful - a tie, no change", "amber")

    def _draw_resolution(self, d, pal, game):
        if game.quest_outcome != "success":
            # fail / tie: no placement - just report the outcome and move on
            self._players_zone(d, pal, game)
            self._progress_zone(d, pal, game)
            fail = game.quest_outcome == "fail"
            ty0, gutt, lh = CONTENT_Y + 6, 28 + 14, 26
            tx = MARGIN + 12 + gutt
            th = 2 * lh + 16
            d.set_pen(pal.card_hi)
            d.rectangle(MARGIN, ty0, 480 - 2 * MARGIN, th)
            d.set_pen(pal.border_gold)
            d.rectangle(MARGIN, ty0, 4, th)
            icons.draw(d, icons.PIPE, MARGIN + 10, ty0 + 8, pal.gold)
            l1 = "Quest failed. " if fail else "Quest unsuccessful - a tie. "
            text_left(d, pal, l1, tx, ty0 + 8, 2, pal.muted)
            draw_heart(d, pal, tx + d.measure_text(l1, 2) + 8, ty0 + 8 + 8, 7, True, pal.red)
            y2 = ty0 + 8 + lh
            if fail:
                a = "Each player's "
                text_left(d, pal, a, tx, y2, 2, pal.muted)
                ax = tx + d.measure_text(a, 2)
                icons.draw(d, icons.THREAT_SM, ax, y2 - 1, pal.red)
                text_left(d, pal, "rose by %d." % game.quest_outcome_n,
                          ax + len(icons.THREAT_SM) + 6, y2, 2, pal.muted)
            else:
                text_left(d, pal, "No progress placed, no threat gained.", tx, y2, 2, pal.muted)
            self._cta(d, pal, "Next Phase: %s" % VIEW_LABELS["travel"], ("advance",))
            return

        if self.alloc is None:
            a = game.auto_split(game.pending_budget)
            self.alloc = {"location": a["location"], "quest": a["quest"],
                          "side_quests": [a["side_quests"][i] if i < len(a["side_quests"]) else 0
                                          for i in range(len(game.side_quests))]}
        alloc = self.alloc
        # Rules: progress fills the active location first; only the overflow past
        # its quest points reaches a quest. The quest/side '+' steppers cascade
        # that way (they fill the location first), so location need not be locked.
        if game.active_location is None:
            alloc["location"] = 0
        used = alloc["location"] + alloc["quest"] + sum(alloc["side_quests"])
        discard = game.pending_budget - used

        text_center(d, pal, "Place %d progress" % game.pending_budget, 240, HEADER_H + 6, 3, pal.gold)

        rows = []
        if game.active_location is not None:
            rows.append(("location", None, "Location",
                         game.active_location["progress"], game.active_location["points"]))
        rows.append(("quest", None, "Quest %s" % game.quest_label(),
                     game.quest["progress"], game.quest["points"]))
        for i, sq in enumerate(game.side_quests):
            rows.append(("side", i, "Side Quest %d" % (i + 1), sq["progress"], sq["points"]))

        rw = 480 - 2 * MARGIN
        cx_was, cx_place, cx_goal = 176, 300, 432
        mn_x, pl_x, btn_w, btn_h = 212, 340, 44, 40

        hy = HEADER_H + 40
        if game.active_location is not None:
            text_center(d, pal, "Location fills first, then the quest", 240, HEADER_H + 32, 1, pal.dim)
            hy = HEADER_H + 50
        text_left(d, pal, "TARGET", 20, hy, 1, pal.dim)
        text_center(d, pal, "WAS", cx_was, hy, 1, pal.dim)
        text_center(d, pal, "PLACE", cx_place, hy, 1, pal.dim)
        text_center(d, pal, "GOAL", cx_goal, hy, 1, pal.dim)

        y = hy + 12
        for key, idx, label, cur, pts in rows:
            add = alloc["side_quests"][idx] if key == "side" else alloc[key]
            result = cur + add
            done = pts > 0 and result >= pts
            locked = key == "location"
            panel(d, pal, MARGIN, y, rw, 52,
                  fill=pal.card_hi if done else pal.card,
                  border=pal.border_gold if done else pal.border)
            text_left(d, pal, label, 20, y + 16, 2, pal.gold if done else pal.tan)
            if done:
                draw_flag(d, 20 + d.measure_text(label, 2) + 8, y + 12, 20, pal.gold)
            text_center(d, pal, str(cur), cx_was, y + 16, 2, pal.dim)
            if locked:
                text_center(d, pal, str(add), cx_place, y + 10, 3, pal.gold if add > 0 else pal.dim)
            else:
                mn = Button(("am", key, idx), mn_x, y + 6, btn_w, btn_h)
                pl = Button(("ap", key, idx), pl_x, y + 6, btn_w, btn_h)
                for b, s in ((mn, "-"), (pl, "+")):
                    bevel(d, pal, b.x, b.y, b.w, b.h, pal.btn)
                    text_center(d, pal, s, b.x + btn_w / 2, b.y + 8, 3, pal.tan)
                    self.buttons.append(b)
                text_center(d, pal, str(add), cx_place, y + 10, 3, pal.gold if add > 0 else pal.dim)
            text_center(d, pal, str(pts), cx_goal, y + 16, 2, pal.tan)
            self._bottom_bar(d, pal, MARGIN, rw, y + 52, result / pts if pts > 0 else 0, pal.gold)
            y += 58

        if discard > 0:
            panel(d, pal, MARGIN, y, rw, 44, fill=pal.card)
            text_left(d, pal, "Unplaced (discarded)", 20, y + 14, 2, pal.dim)
            text_center(d, pal, str(discard), cx_goal, y + 8, 3, pal.red)
            y += 50

        rb = Button(("areset",), MARGIN, y + 2, rw, 38)
        bevel(d, pal, rb.x, rb.y, rb.w, rb.h, pal.btn)
        text_center(d, pal, "Reset", 240, y + 12, 2, pal.tan)
        self.buttons.append(rb)

        self._cta(d, pal, "Next Phase: %s" % VIEW_LABELS["travel"], ("apply_alloc",))

    # -- interaction -------------------------------------------------------
    def on_button(self, btn, game):
        k = btn.id[0]
        if k == "nav":
            return ("goto", btn.id[1])
        if k == "notif_dismiss":
            self.notif = None
            return True
        if k == "qp":
            game.quest["points"] = max(0, min(30, game.quest["points"] + btn.id[1]))
            return True
        if k == "open_card_modal":
            if not game.stages:
                return None    # custom game: no scenario, nothing to show
            from ui.modals import QuestCardModal
            return ("modal", QuestCardModal(game))
        if k == "flip_to_b":
            # Mirrors advance_view's setup_game -> round-1 branch (custom-quest
            # path), but for a scenario game: flip 1A -> 1B first, then the
            # same round-1 entry (log, enter view, reset commits, snapshot).
            pts = game.flip_to_b()
            game.log_event("Setup complete - round 1 begins (quest %s needs %d)"
                           % (game.quest_label(), pts))
            game.enter_view(VIEW_ORDER[0])
            for p in game.players:
                p.commit_touched = False
            game._snapshot_round()
            self.banner = None
            return True
        if k == "players_detail":
            from ui.modals import PlayersDetailModal
            return ("modal", PlayersDetailModal(game))
        if k == "commit_tip":
            from ui.modals import CommitModal
            return ("modal", CommitModal(game, 0))
        if k == "wp":
            from ui.modals import PlayersDetailModal
            return ("modal", PlayersDetailModal(game))
        if k == "enc_rem":
            from ui.modals import RemindersModal
            return ("modal", RemindersModal(game))
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
        if k == "progress_detail":
            # Task 10 reworks the modal this opens.
            from ui.modals import QuestingProgressModal
            return ("modal", QuestingProgressModal(game))
        if k == "stage_advance":
            if not game.quest_resolved:
                res = game.resolve_quest(game.willpower, game.staging)
                self.alloc = None
                if res["outcome"] == "success":
                    game.pending_budget = res["budget"]
                self.toast = [self._outcome_toast(game)]
            game.enter_view("quest_resolution")
            return True
        if k in ("am", "ap"):
            key, idx = btn.id[1], btn.id[2]
            a = self.alloc
            used = a["location"] + a["quest"] + sum(a["side_quests"])
            loc_room = (max(0, game.active_location["points"] - game.active_location["progress"])
                        if game.active_location else 0)
            if key == "side":
                q_cur = game.side_quests[idx]["progress"]
                q_pts = game.side_quests[idx]["points"]
                now_q = a["side_quests"][idx]
            else:
                q_cur, q_pts, now_q = game.quest["progress"], game.quest["points"], a["quest"]
            q_room = max(0, q_pts - q_cur)

            def bump_q(delta):
                if key == "side":
                    a["side_quests"][idx] += delta
                else:
                    a["quest"] += delta

            if k == "ap":                              # + : active location fills first
                if used >= game.pending_budget:
                    return True
                if a["location"] < loc_room:
                    a["location"] += 1
                    return True
                if now_q < q_room:
                    bump_q(1)
                return True
            # - : pull back the quest first, then unwind the location fill
            if now_q > 0:
                bump_q(-1)
                return True
            overflow = a["quest"] + sum(a["side_quests"])
            if overflow == 0 and a["location"] > 0:
                a["location"] -= 1
            return True
        if k == "areset":
            a = self.alloc
            if a:
                a["location"] = 0
                a["quest"] = 0
                a["side_quests"] = [0] * len(a["side_quests"])
            return True
        if k == "apply_alloc":
            used = self.alloc["location"] + self.alloc["quest"] + sum(self.alloc["side_quests"])
            discard = game.pending_budget - used
            completed = game.place_progress(self.alloc)
            msg = "Placed %d progress" % used
            if discard > 0:
                msg += ", discarded %d (over capacity)" % discard
            if completed:
                msg += " (" + ", ".join(completed) + ")"
            game.log_event(msg)
            game.pending_budget = 0
            self.alloc = None
            game.enter_view("travel")
            if game.pending_stage:
                from ui.modals import StageCompleteModal
                return ("modal", StageCompleteModal(game))
            if game.pending_resolution:
                # Catalog game: place_progress() (gamestate.py, B-resolve
                # Task 1) deferred the actual advance mechanics here rather
                # than doing them synchronously - open the guided flow now
                # that the allocation is applied and the view has moved on.
                forced = game.pending_resolution == "forced"
                game.pending_resolution = False
                from ui.modals import ResolutionModal
                return ("modal", ResolutionModal(game, force_advance=forced))
            return True
        if k == "travel_new":
            return ("modal", LocationPickModal(game, mode="new"))
        if k == "travel_change":
            return ("modal", LocationPickModal(game, mode="change"))
        if k == "sail_modal":
            from ui.modals import SailingModal
            return ("modal", SailingModal(game))
        if k == "sail_toggle":
            game.sailing = not game.sailing
            if game.sailing:
                game.heading = 0
            game.log_event("Sailing enabled (Dream-chaser) - heading starts On-course"
                           if game.sailing else "Sailing disabled")
            return True
        if k == "endround":
            game.end_round()
            self.banner = None
            return True
        if k == "advance":
            game.advance_view()
            self.banner = None
            return True
        return None
