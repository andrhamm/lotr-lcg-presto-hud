"""Play screen - guided per-round flow, one view per stage.

resource -> planning -> [quest_sailing] -> quest_commit (per-player willpower) ->
quest_staging (totals with -/+) -> quest_resolution (spreadsheet placement) ->
travel -> encounter -> combat -> refresh (end round). The header navigates.

Mirror of docs/js/screen_play.js - keep the two in lockstep.
"""

import phases
from gamestate import VIEW_ORDER
from viewcopy import (VIEW_LABELS, SETUP_TIP, ACTION_WINDOW_TIPS,
                      PHASE_FRAMEWORK, PHASE_WINDOW, PHASE_CAPTION,
                      COMBAT_FLOW, SHIP_NOTES, STAGING, TRAVEL, OUTCOME,
                      SAILING, QUEST_SETUP, CONFIRM, TOTALS, REFRESH)
from ui.header import draw_header, HEADER_H
from ui.theme import DISPLAY, BODY, LABEL
from ui.widgets import (Button, panel, bevel, text_center, text_left, ribbon,
                        note_panel, phase_block, willpower_staging_meter, wrap_text,
                        truncate_text, draw_heart, draw_flag, disc, arc_runs, token,
                        arrow_left, arrow_right,
                        wx_small)
from ui.modal_counter import CounterModal
from ui.modals import LocationPickModal
from ui import icons

MARGIN = 8
ZONE_TOP = HEADER_H + 6                # top of the players/progress zones
CONTENT_Y = 150                        # zones end ~136; tips start below
CTA_Y = 410
CTA_H = 58
NAV_W = CTA_H          # back / forward are matching squares, CTA_H on a side
NAV_RULE_Y = 400       # 1px rule dividing the content area from the bottom nav
ARROW = 22             # arrow glyph size inside a nav square
NAV_PAD = 8            # clearance between a nav square and the label between them
AW_TICKS = 150         # 3s at the 0.02s main-loop tick



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
        self.action_window = None # view whose window screen is showing, or None

    # -- shared pieces -----------------------------------------------------
    def _players_zone(self, d, pal, game):
        """Flipped 3-row players matrix: P# header / threat token / willpower
        token, one shared tap target over the whole zone (columns are fixed -
        up to MAX_PLAYERS - not width-sized off the live player count).

        The tokens are READ-ONLY. 77f2e11 made each threat token two 24px
        tap-halves (-1 / +1) to skip a modal round-trip, which meant widening
        the columns 32 -> 48px and pushing the progress zone right. That was
        reverted: these are status readouts, and at 24px they were both too
        small to hit reliably and too easy to hit by accident while holding
        the device. Threat is edited in the Players modal, which has room for
        real targets."""
        pcx = [50, 82, 114, 146]
        threat_cy, will_cy = ZONE_TOP + 40, ZONE_TOP + 72
        text_center(d, pal, "P", 18, ZONE_TOP + 2, BODY, pal.muted)
        # player threat helm keeps its red identity (charcoal dropshadow)
        icons.draw(d, icons.THREAT, 8, threat_cy - 9, pal.bevel_d)
        icons.draw(d, icons.THREAT, 7, threat_cy - 10, pal.red)
        icons.draw(d, icons.WILLPOWER, 7, will_cy - 10, pal.gold)
        for i, p in enumerate(game.players):
            cx = pcx[i]
            if i == game.first_player:
                d.set_pen(pal.gold)
                d.rectangle(cx - 12, ZONE_TOP - 2, 24, 19)
                text_center(d, pal, str(i + 1), cx, ZONE_TOP + 1, BODY, pal.bg, shadow=False)
            else:
                text_center(d, pal, str(i + 1), cx, ZONE_TOP + 1, BODY, pal.tan)
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
        and sailing always stay). Back at x=174 / 9 columns now that the
        players zone no longer needs 36px for inline threat taps."""
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
            text_center(d, pal, label, cx, ZONE_TOP + 2, BODY, pal.tan)
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
        # a rules caption (what the ring numeral means), not chrome - BODY.
        # 210px at BODY inside the 258px zone, so it needs no re-layout.
        text_left(d, pal, "quest points remaining", 174, ZONE_TOP + 66, BODY, pal.dim)
        self.buttons.append(Button(("progress_detail",), 174, ZONE_TOP - 2, 298, 90))

    # -- action-window screen ----------------------------------------------
    # A static contextual page shown in front of a step that opens a player
    # action window. No timer and no "Perform Actions" button: those existed
    # only to let a 3s auto-advance be frozen, and there is no auto-advance.
    # The player leaves when they are ready, like every other view.
    AW_Y0 = 146                       # top of the copy band, under the zones
    AW_MAX_BOTTOM = NAV_RULE_Y - 10   # copy must clear the nav rule

    def open_action_window(self, game):
        self.action_window = game.view

    def close_action_window(self):
        self.action_window = None

    def _draw_action_window(self, d, pal, game):
        # "ACTION WINDOW" is the screen's TITLE and belongs in the header,
        # where every other screen puts its title - not floating in the
        # content area competing with the copy.
        y0 = self.AW_Y0
        w = 480 - 2 * MARGIN
        gutter = len(icons.LEADERSHIP) + 14
        usable = w - 16 - 12 - gutter
        lh = 10 * BODY + 6
        band_top, band_bottom = y0, self.AW_MAX_BOTTOM
        max_lines = max(1, (band_bottom - band_top - 16) // lh)
        # Whole paragraphs only - clipping a sentence mid-clause is exactly
        # what the design system forbids.
        lines = []
        for para in ACTION_WINDOW_TIPS.get(game.view, ()):
            wrapped = wrap_text(para, BODY, usable, d.measure_text)
            if len(lines) + len(wrapped) > max_lines:
                continue
            lines.extend(wrapped)
        # centre the panel in the band rather than letting it hug the title
        ph = max(len(lines) * lh + 16, len(icons.LEADERSHIP) + 14)
        ty = band_top + max(0, (band_bottom - band_top - ph) // 2)
        note_panel(d, pal, MARGIN, ty, w, lines, BODY, 0, icons.LEADERSHIP)
        # The window hands off to the NEXT step, so the CTA names it - the same
        # "Next: X" every phase view uses, which the nav bar renders as the
        # NEXT PHASE kicker over the destination.
        self._cta(d, pal, game, "Next: %s" % VIEW_LABELS[game.next_view()],
                  ("aw_close",))

    # Combat substeps, in resolution order. Both halves of the combat phase
    # are a LOOP - the substeps run once per enemy / per attack - and upstream
    # says a player-action window opens after each substep, not once at the
    # end. A prose arrow-chain could carry the order but not the looping, so
    # this draws the sequence and the loop instead.
    COMBAT_FLOW = COMBAT_FLOW      # module constant, kept as a class alias
    FLOW_X = 44            # left gutter holds the loop arrow
    FLOW_ROW = 42

    def _combat_flow(self, d, pal, game, y0):
        caption, note, steps = self.COMBAT_FLOW[game.view]
        n = len(steps)
        rows = [y0 + i * self.FLOW_ROW for i in range(n)]
        # loop arrow: down the gutter from the last row back up to the first
        gx = 20
        d.set_pen(pal.border_gold)
        d.rectangle(gx, rows[0] + 6, 2, rows[-1] - rows[0])       # the spine
        d.rectangle(gx, rows[-1] + 6, self.FLOW_X - gx - 8, 2)     # bottom stub
        d.rectangle(gx, rows[0] + 6, self.FLOW_X - gx - 8, 2)      # top stub
        # arrowhead at the top, pointing into the first step
        ax = self.FLOW_X - 8
        d.triangle(ax, rows[0] + 1, ax, rows[0] + 13, ax + 9, rows[0] + 7)
        # flavour icon, top-right of the flow (kept from the prose version)
        mask, pen = {"combat_enemy": (icons.DEFENSE, pal.green),
                     "combat_player": (icons.ATTACK, pal.tan)}[game.view]
        icons.draw(d, mask, 480 - MARGIN - len(mask), y0 - 2, pen)
        for label, ry in zip(steps, rows):
            tx = self.FLOW_X + 6
            text_left(d, pal, label, tx, ry, BODY, pal.tan)
            # ", then actions" in the action-window purple, inline after each
            # substep - it says what a dot plus a legend had to explain, and
            # it is upstream's own phrasing ("then player actions"). Longest
            # row lands at 450px of 472.
            text_left(d, pal, ", then actions",
                      tx + d.measure_text(label, BODY) + 4, ry, BODY, pal.purple)
        cy = rows[-1] + self.FLOW_ROW - 10
        # wrap rather than trusting the string to fit - the first draft of
        # these notes ran 508px against 464 of screen
        yy = cy
        # Ships note only when the scenario is a Sailing quest - real rules
        # content the prose version carried; dropping it silently would have
        # been a regression (caught by test_combat_enemy_sailing_...).
        ship = {"combat_enemy": "Ships: only a ship can defend a ship-enemy.",
                "combat_player": "Ships: your ships attack only ship-enemies."}
        extra = (ship[game.view],) if game.sailing else ()
        for para in (caption, note) + extra:
            for line in wrap_text(para, BODY, 480 - 2 * MARGIN, d.measure_text):
                text_left(d, pal, line, MARGIN, yy, BODY, pal.dim)
                yy += 24
        return yy + 4

    def _cta(self, d, pal, game, label, id, fill=None, fg=None):
        """The bottom nav bar: a 1px rule, then matching square arrow buttons
        at each edge with the destination label between them.

        The label sits OUTSIDE both buttons so the two arrows stay identically
        sized. It is still part of the forward button's hit area, though - that
        control is tapped every phase, so its target spans label + arrow rather
        than the 58px square alone. Back's target is only its square, so a
        mis-reach for the label can never undo.
        """
        d.set_pen(pal.border)
        d.rectangle(0, NAV_RULE_Y, 480, 1)
        fgp = fg if fg is not None else pal.gold
        cy = CTA_Y + CTA_H // 2
        fwd_x = 480 - MARGIN - NAV_W

        if game.can_undo():
            back = Button(("back",), MARGIN, CTA_Y, NAV_W, CTA_H)
            bevel(d, pal, back.x, back.y, back.w, back.h, pal.btn, t=3)
            arrow_left(d, pal, MARGIN + NAV_W // 2, cy, ARROW, pal.tan)
            self.buttons.append(back)

        bevel(d, pal, fwd_x, CTA_Y, NAV_W, CTA_H,
              fill if fill is not None else pal.btn_ok, t=3)
        arrow_right(d, pal, fwd_x + NAV_W // 2, cy, ARROW, fgp)

        # Label centred in the span between the squares - a fixed frame, so the
        # text does not shift when Back appears.
        lx, rx = MARGIN + NAV_W + NAV_PAD, fwd_x - NAV_PAD
        tcx = (lx + rx) // 2
        # Phase advances read as a kicker over the destination; every other CTA
        # ("End Round", "Flip to Side B ...") is a single centred line.
        if label.startswith("Next: "):
            text_center(d, pal, "NEXT PHASE", tcx, CTA_Y + 10, LABEL, pal.muted)
            text_center(d, pal, label[6:], tcx, CTA_Y + 24, DISPLAY, fgp)
        else:
            text_center(d, pal, label, tcx, CTA_Y + 16, DISPLAY, fgp)
        # one hit area: the label span plus the arrow square
        self.buttons.append(Button(id, lx, CTA_Y, 480 - MARGIN - lx, CTA_H))

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
            text_center(d, pal, label, x + half / 2, y + 6, BODY, pal.muted)
            # scale 4 is the numeral tier above DISPLAY - owned by this widget,
            # never a reading size (ui/theme.py).
            vw = d.measure_text(str(val), 4)
            gx = int(x + half / 2 - (vw + 8 + 28) / 2)
            text_left(d, pal, str(val), gx, y + 32, 4, pen, shadow=shadow)
            icons.draw(d, icon, gx + vw + 8, y + 32, ipen)
            if with_steppers:
                mn = Button((key + "-",), x + 8, y + 30, 52, 44)
                pl = Button((key + "+",), x + half - 60, y + 30, 52, 44)
                for b, s in ((mn, "-"), (pl, "+")):
                    bevel(d, pal, b.x, b.y, b.w, b.h, pal.btn)
                    text_center(d, pal, s, b.x + 26, b.y + 10, DISPLAY, pal.tan)
                    self.buttons.append(b)
                if key == "stg":
                    self.buttons.append(Button(("enc_rem",), x + 64, y, half - 128, 84))
                if key == "wp":
                    self.buttons.append(Button(("wp",), x + 64, y, half - 128, 84))
            elif key in tappable:
                # thin inset dividers + tan ± glyphs (matches the mock - no
                # button chrome). Left/right strips tap ±; centre = big editor
                # (direct total entry for "wp", the staging counter for "stg").
                d.set_pen(pal.border)
                d.rectangle(x + 36, y + 8, 1, 56)
                d.rectangle(x + half - 36, y + 8, 1, 56)
                text_center(d, pal, "-", x + 18, y + 32, DISPLAY, pal.tan)
                text_center(d, pal, "+", x + half - 18, y + 32, DISPLAY, pal.tan)
                self.buttons.append(Button((key + "-",), x, y, 36, 84))
                self.buttons.append(Button((key,), x + 36, y, half - 72, 84))
                self.buttons.append(Button((key + "+",), x + half - 36, y, 36, 84))
                if key == "stg":
                    text_center(d, pal, "+%d reveal estimate" % game.staging_reveal_estimate(),
                                x + half / 2, y + 64, BODY, pal.dim)

    # -- draw --------------------------------------------------------------
    def draw(self, hw, game, pal):
        d = hw.display
        self.buttons = []
        d.set_pen(pal.bg)
        d.clear()
        view = game.view
        if self.action_window:
            # Phase, not a coined position name: it comes straight from
            # phases.py and is accurate for all ten windows. The step id in
            # the round stamp (R1 3.2 vs R1 3.3) is what distinguishes two
            # windows inside the same phase.
            draw_header(d, pal, game, self.buttons, title_pen=pal.purple,
                        title="ACTION WINDOW - %s"
                              % phases.step(game.step)["phase"].upper())
        elif view == "quest_setup":
            draw_header(d, pal, game, self.buttons, title="QUEST SETUP", round_label="R0")
        else:
            draw_header(d, pal, game, self.buttons)

        if self.action_window:
            self._players_zone(d, pal, game)
            self._progress_zone(d, pal, game)
            self._draw_action_window(d, pal, game)
            return
        if view == "setup_game":
            th = note_panel(d, pal, MARGIN, 56, 480 - 2 * MARGIN, SETUP_TIP)
            # This view's two rows are the tallest stack on any play screen and
            # used to run to y=412 - 2px PAST the old CTA at 410, an overlap the
            # layout linter never caught because it compares text, not rects.
            # The nav rule at NAV_RULE_Y makes it visible, so the rows were
            # tightened by 20px total (gap 18->8, rows 48->42 and 38->34) and
            # now end at 392, clearing the rule by 8px. Every target stays
            # >=24px. tests/test_layout.py's rect check now guards it.
            y = 56 + th + 8
            text_left(d, pal, "Stage 1B quest points", MARGIN + 8, y + 13, BODY, pal.tan)
            mn = Button(("qp", -1), 300, y, 52, 42)
            pl = Button(("qp", 1), 412, y, 52, 42)
            for b, s in ((mn, "-"), (pl, "+")):
                bevel(d, pal, b.x, b.y, b.w, b.h, pal.btn)
                text_center(d, pal, s, b.x + 26, b.y + 9, DISPLAY, pal.tan)
                self.buttons.append(b)
            text_center(d, pal, str(game.quest["points"]), 382, y + 9, DISPLAY, pal.gold)
            sy = y + 44
            text_left(d, pal, "Sailing quest", MARGIN + 8, sy + 9, BODY, pal.tan)
            icons.draw(d, icons.WHEEL, 160, sy + 6, pal.gold if game.sailing else pal.dim)
            sb = Button(("sail_toggle",), 300, sy, 164, 34)
            panel(d, pal, sb.x, sb.y, sb.w, sb.h, fill=pal.gold if game.sailing else pal.btn)
            text_center(d, pal, "On" if game.sailing else "Off", sb.x + 82, sb.y + 9, BODY,
                        pal.bg if game.sailing else pal.tan, shadow=False)
            self.buttons.append(sb)
            self._cta(d, pal, game, "Begin Round 1", ("advance",))
        elif view == "quest_setup":
            self._players_zone(d, pal, game)
            self._progress_zone(d, pal, game)
            self._draw_quest_setup(d, pal, game)
        elif view == "resource":
            self._players_zone(d, pal, game)
            self._progress_zone(d, pal, game)
            phase_block(d, pal, MARGIN, CONTENT_Y, 480 - 2 * MARGIN, [
                ("framework", PHASE_FRAMEWORK["resource"]),
            ])
            self._cta(d, pal, game, "Next: %s" % VIEW_LABELS["planning"], ("advance",))
        elif view == "planning":
            self._players_zone(d, pal, game)
            self._progress_zone(d, pal, game)
            phase_block(d, pal, MARGIN, CONTENT_Y, 480 - 2 * MARGIN, [
                ("framework", PHASE_FRAMEWORK["planning"]),
                ("window", PHASE_WINDOW["planning"]),
            ])
            nxt = "quest_sailing" if game.sailing else "quest_commit"
            self._cta(d, pal, game, "Next: %s" % VIEW_LABELS[nxt], ("advance",))
        elif view == "quest_commit":
            self._players_zone(d, pal, game)
            self._progress_zone(d, pal, game)
            bh = phase_block(d, pal, MARGIN, CONTENT_Y, 480 - 2 * MARGIN,
                             [("window", PHASE_WINDOW["quest_commit"])])
            cy = self._draw_confirm_all(d, pal, game, CONTENT_Y + bh + 8)
            self._totals_row(d, pal, game, cy, tappable=("wp", "stg"))
            self._cta(d, pal, game, "Next: %s" % VIEW_LABELS["quest_staging"], ("advance",))
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
            bh = phase_block(d, pal, MARGIN, CONTENT_Y, 480 - 2 * MARGIN, [
                ("framework", PHASE_FRAMEWORK["refresh"]),
                ("window", PHASE_WINDOW["refresh"]),
            ])
            self._refresh_threat_preview(d, pal, game, CONTENT_Y + bh + 8)
            self._cta(d, pal, game, "End Round", ("endround",))
        elif view in self.COMBAT_FLOW:
            # Combat is a loop, so it gets the flow diagram rather than a
            # prose arrow-chain: the chain could carry the order but not the
            # repetition, and the windows sit INSIDE the loop.
            self._players_zone(d, pal, game)
            self._progress_zone(d, pal, game)
            self._combat_flow(d, pal, game, CONTENT_Y + 6)
            nxt = VIEW_ORDER[(VIEW_ORDER.index(view) + 1) % len(VIEW_ORDER)]
            self._cta(d, pal, game, "Next: %s" % VIEW_LABELS[nxt], ("advance",))
        else:
            self._players_zone(d, pal, game)
            ship_notes = SHIP_NOTES
            flavor = {"combat_enemy": (icons.DEFENSE, pal.green),
                      "combat_player": (icons.ATTACK, pal.tan)}.get(view)
            self._progress_zone(d, pal, game)
            sections = []
            if PHASE_FRAMEWORK.get(view):
                fw = PHASE_FRAMEWORK[view]
                if game.sailing and view in ship_notes:
                    fw = [fw, ship_notes[view]]
                sections.append(("framework", fw))
            if PHASE_WINDOW.get(view):
                sections.append(("window", PHASE_WINDOW[view]))
            bh = phase_block(d, pal, MARGIN, CONTENT_Y, 480 - 2 * MARGIN, sections,
                             34 if flavor else 0)
            if flavor:
                icons.draw(d, flavor[0], 480 - MARGIN - 34,
                           CONTENT_Y + (bh - 20) // 2, flavor[1])
            if PHASE_CAPTION.get(view):
                # a rules caption: BODY, wrapped over as many lines as it needs
                # (every one of these is 2 lines, ending by y=316).
                cap_w = 480 - 2 * (MARGIN + 4)
                cy = CONTENT_Y + bh + 10
                for ln in wrap_text(PHASE_CAPTION[view], BODY, cap_w, d.measure_text):
                    text_left(d, pal, ln, MARGIN + 4, cy, BODY, pal.dim)
                    cy += 24
            i = VIEW_ORDER.index(view)
            nxt = VIEW_ORDER[(i + 1) % len(VIEW_ORDER)]
            self._cta(d, pal, game, "Next: %s" % VIEW_LABELS.get(nxt, nxt), ("advance",))

        self._draw_notif(d, pal)

        if self.banner and self.banner[2] == view:
            btext, bkind = self.banner[0], self.banner[1]
            bpen = {"good": pal.green, "bad": pal.red, "mid": pal.amber}[bkind]
            btext = truncate_text(btext, BODY, 480 - 2 * MARGIN, d.measure_text)
            text_center(d, pal, btext, 240, CTA_Y - 26, BODY, bpen)

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
            for ln in wrap_text(s, BODY, usable, d.measure_text):
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
            text_left(d, pal, s, tx0, ty, BODY, getattr(pal, c))
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
                       [SAILING["no_keyword"],
                        SAILING["enable_hint"]])
            eb = Button(("sail_toggle",), MARGIN, CONTENT_Y + 96, 480 - 2 * MARGIN, 52)
            bevel(d, pal, eb.x, eb.y, eb.w, eb.h, pal.btn)
            icons.draw(d, icons.WHEEL, 130, CONTENT_Y + 96 + 14, pal.gold)
            text_center(d, pal, "Enable Sailing", 254, CONTENT_Y + 96 + 16, BODY, pal.tan)
            self.buttons.append(eb)
            self._cta(d, pal, game, "Next: %s" % VIEW_LABELS["quest_commit"], ("advance",))
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
        text_left(d, pal, fp, tx, ly, BODY, pal.muted)
        sx0 = tx + d.measure_text(fp, BODY) + 6
        ribbon(d, pal, sx0, ly - 1, 10, 18)
        sx0 += 10 + 6
        text_left(d, pal, "exhausts characters (ships", sx0, ly, BODY, pal.muted)
        ly += lh
        text_left(d, pal, "count), looks at and discards them.", tx, ly, BODY, pal.muted)
        ly += lh
        icons.draw(d, icons.WHEEL_SM, tx, ly, pal.gold)
        text_left(d, pal, "found: move 1 step on-course.", tx + 22, ly, BODY, pal.muted)
        sb = Button(("sail_modal",), MARGIN, ty0 + th + 10, 480 - 2 * MARGIN, 52)
        bevel(d, pal, sb.x, sb.y, sb.w, sb.h, pal.btn)
        icons.draw(d, icons.WHEEL, 150, sb.y + 14, pal.gold)
        text_center(d, pal, "Log sailing test", 262, sb.y + 16, BODY, pal.tan)
        self.buttons.append(sb)
        self._cta(d, pal, game, "Next: %s" % VIEW_LABELS["quest_commit"], ("advance",))

    def _draw_staging(self, d, pal, game):
        self._players_zone(d, pal, game)
        self._progress_zone(d, pal, game)
        bh = phase_block(d, pal, MARGIN, CONTENT_Y, 480 - 2 * MARGIN, [
            ("framework", STAGING["framework"]),
            ("window", STAGING["window"]),
        ])
        # Gaps are 4, not 8: the framework line grew to two lines when it
        # gained the STAGING["short"] rule, and
        # the totals row has to stay clear of the CTA. Re-laid out rather
        # than shrinking the text - see the design system.
        my = CONTENT_Y + bh + 4
        mh = willpower_staging_meter(d, pal, MARGIN, my, 480 - 2 * MARGIN,
                                     game.willpower, game.staging)
        self._totals_row(d, pal, game, my + mh + 4, with_steppers=True)
        self._cta(d, pal, game, "Next: %s" % VIEW_LABELS["quest_resolution"],
                  ("stage_advance",))

    def _draw_quest_setup(self, d, pal, game):
        """R0 pre-round-1 phase: stage 1A's setup text to resolve, then the
        first flip (1A -> 1B) that begins round 1. Reuses the standard zones
        (Task 8) - mirror of screen_play.js's _drawQuestSetup."""
        card = game.stages[game.stage_idx]["cards"][game.card_idx]
        a_face = next((f for f in card["faces"] if f["side"] == "A"), {})
        stage_label = "STAGE %d%s" % (game.quest["stage_n"], game.quest["side"])
        text_center(d, pal, stage_label, 240, CONTENT_Y, BODY, pal.amber)
        name_y = CONTENT_Y + 22
        card_name = truncate_text(a_face.get("name") or "", DISPLAY, 480 - 2 * MARGIN,
                                  d.measure_text)
        text_center(d, pal, card_name, 240, name_y, DISPLAY, pal.gold)

        # Distinct scroll-style tip: a double gold frame + ribbon banner -
        # UNLIKE the standard note_panel() left-accent-bar style used
        # elsewhere, since this is the one moment that reads as "resolve
        # this printed text now".
        tip_x, tip_w, tip_y = MARGIN, 480 - 2 * MARGIN, name_y + 30
        # ribbon_h is 28, not 22: its caption is BODY (16px tall) plus the 6px
        # inset, and the banner has to hold the text rather than the text
        # shrink to hold the banner.
        ribbon_h, pad_top, line_h, pad_bottom, max_lines = 28, 10, 24, 10, 4
        usable = tip_w - 28
        raw = a_face.get("text")
        body = raw if raw else QUEST_SETUP["none"]
        lines = wrap_text(body, BODY, usable, measure=d.measure_text)
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            lines[max_lines - 1] = truncate_text(lines[max_lines - 1] + " ..", BODY, usable,
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
        text_left(d, pal, QUEST_SETUP["banner"], tip_x + 10, tip_y + 6, BODY, pal.bg,
                  shadow=False)
        ly = tip_y + ribbon_h + pad_top
        for ln in lines:
            text_left(d, pal, ln, tip_x + 14, ly, BODY, pal.tan)
            ly += line_h

        # Read-only card modal (M4-B) - see on_button; null for custom games
        # (no scenario loaded, nothing to show).
        card_btn = Button(("open_card_modal",), MARGIN, 358, 480 - 2 * MARGIN, 44)
        bevel(d, pal, card_btn.x, card_btn.y, card_btn.w, card_btn.h, pal.btn)
        text_center(d, pal, "View quest card", 240, card_btn.y + 14, BODY, pal.tan)
        self.buttons.append(card_btn)

        self._cta(d, pal, game, QUEST_SETUP["flip"] % card["questPoints"], ("flip_to_b",))

    def _draw_confirm_all(self, d, pal, game, y):
        """One-tap 'everyone's commit is reviewed' button for the commit view -
        replaces the old per-player CommitModal round-trip. Caption counts
        confirmed living players; once all are confirmed it reads as done and
        the button goes inert. Returns the y for whatever follows."""
        living = [p for p in game.players if not p.eliminated]
        done = [p for p in living if p.commit_touched]
        all_done = len(done) == len(living) and living
        b = Button(("confirm_all",), MARGIN, y, 480 - 2 * MARGIN, 40)
        bevel(d, pal, b.x, b.y, b.w, b.h, pal.card if all_done else pal.btn)
        label = (CONFIRM["all"] if all_done else
                 CONFIRM["partial"] % (len(done), len(living)))
        text_center(d, pal, label, 240, y + 12, BODY,
                    pal.dim if all_done else pal.tan)
        if not all_done:
            self.buttons.append(b)
        return y + 48

    def _refresh_threat_preview(self, d, pal, game, y):
        """Live REFRESH["preview_caption"] threat per living player, flagged red
        when the projected value crosses the same danger threshold
        _players_zone uses (proj >= elimination - 10). Eliminated players are
        skipped - their threat is capped at their elimination level and does
        not keep rising. Fixed height: 48 (the caption is BODY, so the row
        below it sits 22px down rather than 14px)."""
        text_left(d, pal, "After +1 threat:", MARGIN + 4, y, BODY, pal.dim)
        x = MARGIN + 4
        ly = y + 22
        for i, p in enumerate(game.players):
            if p.eliminated:
                continue
            proj = p.threat + p.threat_per_round
            danger = proj >= p.elimination - 10
            seg = "P%d %d->%d%s" % (i + 1, p.threat, proj, "!" if danger else "")
            text_left(d, pal, seg, x, ly, BODY, pal.red if danger else pal.value)
            x += d.measure_text(seg, BODY) + 16
        return 48

    def _draw_travel(self, d, pal, game):
        loc = game.active_location
        fw = (TRAVEL["blocked"] if loc else
              TRAVEL["open"])
        bh = phase_block(d, pal, MARGIN, CONTENT_Y, 480 - 2 * MARGIN,
                         [("framework", fw), ("window", "Responses.")])
        y = CONTENT_Y + bh + 10
        if loc is None:
            tb = Button(("travel_new",), MARGIN, y, 480 - 2 * MARGIN, 56)
            bevel(d, pal, tb.x, tb.y, tb.w, tb.h, pal.btn)
            text_center(d, pal, TRAVEL["btn_travel"], 240, y + 18, BODY, pal.tan)
            self.buttons.append(tb)
        else:
            cb = Button(("travel_change",), MARGIN, y, 480 - 2 * MARGIN, 48)
            panel(d, pal, cb.x, cb.y, cb.w, cb.h, fill=pal.card)
            text_center(d, pal, TRAVEL["btn_replace"], 240, y + 14, BODY, pal.muted)
            self.buttons.append(cb)
        self._cta(d, pal, game, "Next: %s" % VIEW_LABELS["enc_optional"], ("advance",))

    def _outcome_toast(self, game):
        if game.quest_outcome == "success":
            return ("TRAIL", OUTCOME["toast_success"] % game.quest_outcome_n, "green")
        if game.quest_outcome == "fail":
            return ("THREAT_SM", OUTCOME["toast_fail"] % game.quest_outcome_n, "red")
        return (None, OUTCOME["toast_tie"], "amber")

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
            l1 = "Quest failed. " if fail else OUTCOME["card_tie"]
            text_left(d, pal, l1, tx, ty0 + 8, BODY, pal.muted)
            draw_heart(d, pal, tx + d.measure_text(l1, BODY) + 8, ty0 + 8 + 8, 7, True, pal.red)
            y2 = ty0 + 8 + lh
            if fail:
                a = "Each player's "
                text_left(d, pal, a, tx, y2, BODY, pal.muted)
                ax = tx + d.measure_text(a, BODY)
                icons.draw(d, icons.THREAT_SM, ax, y2 - 1, pal.red)
                text_left(d, pal, "rose by %d." % game.quest_outcome_n,
                          ax + len(icons.THREAT_SM) + 6, y2, BODY, pal.muted)
            else:
                text_left(d, pal, OUTCOME["tie_line2"], tx, y2, BODY,
                          pal.muted)
            self._cta(d, pal, game, "Next: %s" % VIEW_LABELS["travel"], ("advance",))
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

        text_center(d, pal, "Place %d progress" % game.pending_budget, 240, HEADER_H + 6,
                    DISPLAY, pal.gold)

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
            # rules caption -> BODY (334px of the 464 available). hy moves from
            # +50 to +56 to clear the taller line; the table below shifts 6px
            # and still ends 38px clear of the CTA.
            text_center(d, pal, OUTCOME["alloc_caption"], 240, HEADER_H + 32,
                        BODY, pal.dim)
            hy = HEADER_H + 56
        # ALL-CAPS column heads over a dense table - LABEL is right here.
        text_left(d, pal, "TARGET", 20, hy, LABEL, pal.dim)
        text_center(d, pal, "WAS", cx_was, hy, LABEL, pal.dim)
        text_center(d, pal, "PLACE", cx_place, hy, LABEL, pal.dim)
        text_center(d, pal, "GOAL", cx_goal, hy, LABEL, pal.dim)

        y = hy + 12
        for key, idx, label, cur, pts in rows:
            add = alloc["side_quests"][idx] if key == "side" else alloc[key]
            result = cur + add
            done = pts > 0 and result >= pts
            locked = key == "location"
            panel(d, pal, MARGIN, y, rw, 52,
                  fill=pal.card_hi if done else pal.card,
                  border=pal.border_gold if done else pal.border)
            text_left(d, pal, label, 20, y + 16, BODY, pal.gold if done else pal.tan)
            if done:
                draw_flag(d, 20 + d.measure_text(label, BODY) + 8, y + 12, 20, pal.gold)
            text_center(d, pal, str(cur), cx_was, y + 16, BODY, pal.dim)
            if locked:
                text_center(d, pal, str(add), cx_place, y + 10, DISPLAY,
                            pal.gold if add > 0 else pal.dim)
            else:
                mn = Button(("am", key, idx), mn_x, y + 6, btn_w, btn_h)
                pl = Button(("ap", key, idx), pl_x, y + 6, btn_w, btn_h)
                for b, s in ((mn, "-"), (pl, "+")):
                    bevel(d, pal, b.x, b.y, b.w, b.h, pal.btn)
                    text_center(d, pal, s, b.x + btn_w / 2, b.y + 8, DISPLAY, pal.tan)
                    self.buttons.append(b)
                text_center(d, pal, str(add), cx_place, y + 10, DISPLAY,
                            pal.gold if add > 0 else pal.dim)
            text_center(d, pal, str(pts), cx_goal, y + 16, BODY, pal.tan)
            self._bottom_bar(d, pal, MARGIN, rw, y + 52, result / pts if pts > 0 else 0, pal.gold)
            y += 58

        if discard > 0:
            panel(d, pal, MARGIN, y, rw, 44, fill=pal.card)
            text_left(d, pal, OUTCOME["alloc_unplaced"], 20, y + 14, BODY, pal.dim)
            text_center(d, pal, str(discard), cx_goal, y + 8, DISPLAY, pal.red)
            y += 50

        rb = Button(("areset",), MARGIN, y + 2, rw, 38)
        bevel(d, pal, rb.x, rb.y, rb.w, rb.h, pal.btn)
        text_center(d, pal, "Reset", 240, y + 12, BODY, pal.tan)
        self.buttons.append(rb)

        self._cta(d, pal, game, "Next: %s" % VIEW_LABELS["travel"], ("apply_alloc",))

    # -- interaction -------------------------------------------------------
    def on_button(self, btn, game):
        k = btn.id[0]
        if k == "nav":
            return ("goto", btn.id[1])
        if k == "back":
            if not game.undo():
                return None
            # screen-local scratch describes the view we just left
            self.alloc = None
            self.banner = None
            return True
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
        if k == "confirm_all":
            game.confirm_all_commits()
            game.log_event("Confirmed all player commits")
            return True
        if k == "wp":
            def set_wp(v, game=game):
                game.willpower = v
            return ("modal", CounterModal(TOTALS["willpower_modal"], game.willpower,
                                          on_commit=set_wp, icon="willpower"))
        if k == "enc_rem":
            from ui.modals import RemindersModal
            return ("modal", RemindersModal(game))
        if k == "stg":
            def set_stg(v, game=game):
                game.staging = v
            return ("modal", CounterModal(TOTALS["staging_modal"], game.staging,
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
        # Travel opens the location picker, which needs the scenario's
        # gather-list union read out of the catalog first - flash I/O a
        # screen's on_button can't do mid-tap (and a fetch the web twin
        # can't await there at all). Flag it and let main.py's loop build
        # the modal, same pending-flag pattern as pending_side_quest_pick.
        if k in ("travel_new", "travel_change"):
            game.pending_location_pick = {"mode": k[len("travel_"):], "back": "play"}
            return True
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
