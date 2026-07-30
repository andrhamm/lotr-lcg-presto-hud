// Port of ui/screen_play.py — the guided round.
import { pal, Button, rect, panel, bevel, textLeft, textCenter, wrapText,
         truncateText, ribbon, notePanel, phaseBlock, willpowerStagingMeter,
         drawHeart, drawFlag, disc, arcRuns, wxSmall, token,
         BAND_PAD, bandLineH, pill, pillWidth,
         PILL_H, PILL_GAP, PILL_ROW_GAP,
         arrowLeft, arrowRight,
         DISPLAY, BODY, LABEL } from "./ui.js";
import { measureText } from "./metrics.js";
import { step as phaseStep } from "./phases.js";
import * as icons from "./icons.js";
import { VIEW_ORDER, isWindowView, phaseViewOf } from "./gamestate.js";
import { VIEW_LABELS, SETUP_TIP, ACTION_WINDOW_TIPS, PHASE_FRAMEWORK, PHASE_WINDOW,
         PHASE_CAPTION, LOOP_FLOW, LOOP_LEGEND, SHIP_FLOW_NOTES,
         STAGING_PENDING, COMBAT_LAST_CHANCE,
         STAGING, TRAVEL,
         OUTCOME, SAILING, QUEST_SETUP, TOTALS,
         REFRESH } from "./viewcopy.js";
import { drawHeader, drawNotifPie, HEADER_H, CounterModal,
         PlayersDetailModal, RemindersModal, LocationPickModal, SideQuestsModal,
         QuestConfigModal, StageCompleteModal, SailingModal,
         QuestingProgressModal, QuestCardModal, ResolutionModal } from "./screens.js";

const MARGIN = 8;
const ZONE_TOP = HEADER_H + 6;            // top of the players/progress zones
const CONTENT_Y = 150;                    // zones end ~136; tips start below
const CTA_Y = 410;
const CTA_H = 58;
const NAV_W = CTA_H;      // back / forward are matching squares, CTA_H a side
const NAV_RULE_Y = 400;
const FLOW_X = 44;        // left gutter holds the loop arrow
const FLOW_LINE = 20;     // one wrapped line inside a rung (16px glyphs)
const FLOW_GAP = 2;
const TICK_W = 14;        // purple window marker, right-aligned
// Top of the copy band - the same line every phase view starts its band
// on; this was 146, off by 4 for no reason.
// the action window's band starts at this.contentY (set by _statZone)
const AW_MAX_BOTTOM = NAV_RULE_Y - 10;  // copy must clear the nav rule   // 1px rule dividing the content area from the nav
const ARROW = 22;         // arrow glyph size inside a nav square
const NAV_PAD = 8;        // clearance between a nav square and the label

// Threat-as-risk framing for Encounter & Combat (M2 Task 6): the app tracks
// each player's live threat but not individual enemy cards or their
// engagement costs, so the risk framing is rules-verified explanatory copy
// tied to the numbers already on screen (players-zone threat tokens), not a
// fabricated cost comparison against data the app doesn't have.
// See ui/screen_play.py - three phases get their action-window guidance here
// rather than on a dedicated screen, because upstream does not describe them
// as a discrete window following the step.

export class ScreenPlay {
  // a 4-player game needs two rows; more than that starts eating the content
  // band the zone exists to hand back
  static MAX_ZONE_ROWS = 2;

  constructor() {
    this.buttons = [];
    this.banner = null;      // [text, kind, view]
    this.notif = null;       // list of [icon, text, color]
    this.notifFrac = 1.0;
    this.notifPie = null;
    this.notifEdge = "amber";
    this.alloc = null;
    this.toast = null;       // [[icon, text, color]] picked up by the main loop
  }

  // The top zone: a flowing row of segmented pills. Sets and returns
  // this.contentY, the line the content band anchors to.
  //
  // Replaces two fixed 90px matrices with pills that take only the room they
  // need, so a small game gets its space back: 1-3 players fit one row and
  // start content 66px higher, 4 players take two rows and gain 33px. The
  // zone reflows when a side quest is added or a location explored - a
  // deliberate accept, since it only happens on an explicit action.
  //
  // The pills are READ-ONLY status, same as the tokens they replace: each is
  // a tap target only so it can open the detail modal that already edits
  // these values.
  _statZone(ctx, game) {
    const pills = [];
    pills.push([["players_detail"],
                [["text", "P", "slate"],
                 ["icon", icons.THREAT, "red"],
                 ["icon", icons.WILLPOWER, "gold"]], null, false, false]);
    game.players.forEach((p, i) => {
      const danger = p.threat >= p.elimination - 10;
      // "?" while the total has been set directly: the stored per-player
      // value is still there, it is just no longer what the total says, and
      // showing it would assert a breakdown that does not add up.
      const wp = game.willpower_detached ? "?" : String(p.commit);
      pills.push([["players_detail"],
                  [["text", String(i + 1), "slate"],
                   ["text", String(p.threat), "red"],
                   ["text", wp, "gold"]],
                  danger ? pal.red : null,
                  i === game.first_player, p.eliminated]);
    });

    const prog = [["Q", game.quest.progress, game.quest.points]];
    // L, then L2 - a bare "L" twice would be two identical pills for two
    // different cards.
    game.active_locations.forEach((loc, i) => {
      prog.push([i === 0 ? "L" : `L${i + 1}`, loc.progress, loc.points]);
    });
    game.side_quests.forEach((sq, i) => prog.push([`S${i + 1}`, sq.progress, sq.points]));
    for (const [label, done, total] of prog) {
      pills.push([["progress_detail"],
                  [["text", label, "slate"],
                   ["text", String(Math.max(0, total - done)), "gold"]],
                  null, false, false]);
    }
    if (game.sailing) {
      const wx = [icons.SUN, icons.CLOUD, icons.RAIN, icons.STORM][game.heading];
      pills.push([["progress_detail"],
                  [["icon", icons.WHEEL_SM, "gold"], ["icon", wx, "tan"]],
                  null, false, false]);
    }

    // Cap the zone at MAX_ZONE_ROWS and drop the NEWEST side quests to fit,
    // exactly the policy the fixed-column zone had. Without it the row flows
    // on forever: ten side quests is four rows, straight through the content
    // band and off the screen.
    const rowsFor = items => {
      let x = MARGIN, rows = 1;
      for (const [, segs] of items) {
        const w = pillWidth(segs);
        if (x > MARGIN && x + w > 480 - MARGIN) { x = MARGIN; rows += 1; }
        x += w + PILL_GAP;
      }
      return rows;
    };
    while (rowsFor(pills) > ScreenPlay.MAX_ZONE_ROWS) {
      let drop = -1;
      for (let i = pills.length - 1; i >= 0; i--) {
        const head = pills[i][1][0];
        if (head[0] === "text" && head[1].startsWith("S")) { drop = i; break; }
      }
      if (drop < 0) break;
      pills.splice(drop, 1);
    }

    let x = MARGIN, y = ZONE_TOP;
    for (const [bid, segs, border, ribbon, dead] of pills) {
      const w = pillWidth(segs);
      if (x > MARGIN && x + w > 480 - MARGIN) { x = MARGIN; y += PILL_H + PILL_ROW_GAP; }
      pill(ctx, x, y, segs, border, ribbon, dead, icons);
      this.buttons.push(new Button(bid, x, y, w, PILL_H));
      x += w + PILL_GAP;
    }
    // The content band anchors here rather than to a constant, which is the
    // whole point of the compaction.
    this.contentY = y + PILL_H + 10;
    return this.contentY;
  }

  // The bottom nav bar: a 1px rule, then matching square arrow buttons at each
  // edge with the destination label between them.
  //
  // The label sits OUTSIDE both buttons so the two arrows stay identically
  // sized. It is still part of the forward button's hit area, though - that
  // control is tapped every phase, so its target spans label + arrow rather
  // than the 58px square alone. Back's target is only its square, so a
  // mis-reach for the label can never undo.
  // Mirror of ui/screen_play.py _loop_flow. Variable height: every rung
  // wraps, so the loop arrow is sized from the result rather than a fixed row
  // pitch. The old fixed-pitch version is why the corrected copy ran off the
  // right edge - the longest rung measured 570px against a 480px screen.
  _loopFlow(ctx, game, y0) {
    const spec = LOOP_FLOW[game.view];
    const full = 480 - 2 * MARGIN;
    let yy = y0;

    // Flavour icon (defence / attack). It used to sit top-right on the intro
    // row, where it reserved 30px of width - once the intro is banded that is
    // the difference between one line and two, and combat_enemy's intro
    // cannot be shortened (both halves carry a cited rule). It moves to the
    // bottom-right beside the closing note, drawn at the end once yy is known.
    const flavour = { combat_enemy: [icons.DEFENSE, pal.green],
                      combat_player: [icons.ATTACK, pal.tan] }[game.view];

    // Framing line, banded like every other phase view's framing copy. These
    // four views used to state it as bare text, so a player who had learned
    // red = happens anyway and green = your window met four screens that
    // simply stopped saying it - Planning, the phase that is nothing BUT your
    // window, among them. The diagram has its own vocabulary (the bracket
    // loops, the purple tick marks a window); this sentence is not part of it.
    yy += phaseBlock(ctx, MARGIN, yy, full, [{ kind: spec.kind, text: spec.intro }]);

    const ticks = spec.rungs.some(r => r[1]);
    const labelW = 480 - FLOW_X - 6 - MARGIN - (ticks ? TICK_W : 0);
    const top = yy;
    for (const [label, opens, sub] of spec.rungs) {
      const lines = wrapText(label, BODY, labelW, measureText);
      lines.forEach((line, k) => {
        textLeft(ctx, line, FLOW_X + 6, yy, BODY, pal.tan);
        if (opens && k === 0) rect(ctx, 480 - MARGIN - 8, yy + 3, 6, 6, pal.purple);
        yy += FLOW_LINE;
      });
      if (sub) {
        for (const line of wrapText(sub, BODY, labelW - 14, measureText)) {
          textLeft(ctx, line, FLOW_X + 20, yy, BODY, pal.dim);
          yy += FLOW_LINE;
        }
      }
      yy += FLOW_GAP;
    }
    const bottom = yy - FLOW_GAP;

    // Both arms are centred on the TEXT they point at, which they were not: a
    // BODY line at y is 16px tall, so its centre is y+8 and a 2px rail centred
    // there starts at y+7. The bottom arm sat in the gap between the last rung
    // and the exit line, pointing at neither. It belongs to the exit line -
    // "Repeat until ..." is the loop's exit and the arm wraps back up from it.
    const exitY = bottom + FLOW_GAP;
    const gx = 20;
    const armTop = top + 7, armBot = exitY + 7;
    rect(ctx, gx, armTop, 2, Math.max(2, armBot - armTop), pal.border_gold);
    rect(ctx, gx, armBot, FLOW_X - gx - 8, 2, pal.border_gold);
    rect(ctx, gx, armTop, FLOW_X - gx - 8, 2, pal.border_gold);
    const ax = FLOW_X - 8;
    ctx.fillStyle = pal.border_gold;
    ctx.beginPath();
    ctx.moveTo(ax, armTop - 5); ctx.lineTo(ax, armTop + 7);
    ctx.lineTo(ax + 9, armTop + 1);
    ctx.closePath(); ctx.fill();

    for (const line of wrapText(spec.exit, BODY, full - 24, measureText)) {
      textLeft(ctx, line, FLOW_X + 6, yy, BODY, pal.dim);
      yy += FLOW_LINE;
    }
    if (ticks) {
      rect(ctx, MARGIN + 2, yy + 3, 6, 6, pal.purple);
      textLeft(ctx, LOOP_LEGEND, MARGIN + 14, yy, BODY, pal.purple);
      yy += FLOW_LINE;
    }

    const notes = [];
    if (spec.note) notes.push(spec.note);
    // Unconditional - see COMBAT_LAST_CHANCE. Nothing between 6.8.3's window
    // and 7.3 lets a player act.
    if (game.view === "combat_player") notes.push(COMBAT_LAST_CHANCE);
    if (game.sailing && SHIP_FLOW_NOTES[game.view]) notes.push(SHIP_FLOW_NOTES[game.view]);
    // The closing note gets a treatment too. It used to be bare dim text under
    // the diagram - "just text in the void" - which left the line a player is
    // most likely to act on as the least marked thing on screen. `note_kind`
    // says which it is: a rule the game applies to you (framework, red) or
    // advice you may act on (tip, gold).
    //
    // A BAR, not a filled band. The two combat views have 8px of headroom and
    // a filled band costs 16-20 more, which would mean cutting a cited rule to
    // make room - and the note is a footnote to the diagram, not a second
    // framing statement, so it earns the lighter weight anyway.
    let lastNoteY = yy;
    const noteTop = yy;
    for (const para of notes) {
      for (const line of wrapText(para, BODY, full - 14, measureText)) {
        textLeft(ctx, line, MARGIN + 14, yy, BODY, pal.dim);
        lastNoteY = yy;
        yy += FLOW_LINE;
      }
    }
    if (notes.length) {
      rect(ctx, MARGIN, noteTop, 4, lastNoteY + 16 - noteTop,
           spec.note_kind === "framework" ? pal.red : pal.border_gold);
    }
    if (flavour) {
      icons.drawIcon(ctx, flavour[0], 480 - MARGIN - flavour[0][0],
                     lastNoteY - 2, flavour[1]);
    }
    return yy + 4;
  }

  // The staging window's conditional line. The comparison itself lives in
  // gamestate.questPreview() - two copies of a rule drift.
  _pendingLine(game) {
    const [outcome, n, room] = game.questPreview();
    const fmt = (t, ...a) => { let i = 0; return t.replace(/%[sd]/g, () => a[i++]); };
    if (outcome === "fail") {
      const doomed = game.players.findIndex(
        p => !p.eliminated && p.threat + n >= p.elimination);
      if (doomed >= 0) {
        return fmt(STAGING_PENDING.fail_elim, game.players[doomed].label, "threat");
      }
      return fmt(STAGING_PENDING.fail, "threat", n);
    }
    if (outcome === "tie") {
      return fmt(STAGING_PENDING.tie, "threat", "willpower", "progress");
    }
    if (room > 0) return fmt(STAGING_PENDING.success_room, "willpower", "progress");
    return fmt(STAGING_PENDING.success_full, "Progress", game.quest.points);
  }

  _drawActionWindow(ctx, game) {
    const y0 = this.contentY, w = 480 - 2 * MARGIN;
    const usable = w - 16 - 12;
    const lh = bandLineH(BODY);
    const bandTop = y0, bandBottom = AW_MAX_BOTTOM;
    const maxLines = Math.max(1, Math.floor((bandBottom - bandTop - 2 * BAND_PAD) / lh));
    // Whole paragraphs only - clipping a sentence mid-clause is exactly what
    // the design system forbids.
    const lines = [];
    const paras = [...(ACTION_WINDOW_TIPS[phaseViewOf(game.view)] ?? [])];
    if (phaseViewOf(game.view) === "quest_staging") paras.push(this._pendingLine(game));
    for (const para of paras) {
      const wrapped = wrapText(para, BODY, usable, measureText);
      if (lines.length + wrapped.length > maxLines) continue;
      lines.push(...wrapped);
    }
    // Top-anchored, like every phase view's band. This used to centre the
    // panel, so its top edge moved with the copy length - 195 on a five-line
    // window, 234 on a two-line one, against a flat 150 on every phase view.
    // GREEN, not the gold hint bar. An action window IS what green means -
    // "your window to act" - so these eight screens wore the one treatment
    // reserved for hints while the phase view before each drew the same idea
    // in green. The leadership medallion goes with it: the bar already says
    // it, which is why the label rows were dropped in the first place.
    // pen=tan: this is guidance, the same as every phase view's band, and
    // notePanel's default `muted` made the action windows read a tier quieter
    // than the screen the player just came from.
    notePanel(ctx, MARGIN, bandTop, w, lines, BODY, 0, false, pal.green, pal.tan);
    // The window hands off to the NEXT step, so the CTA names it - the same
    // "Next: X" every phase view uses.
    this._cta(ctx, game, `Next: ${VIEW_LABELS[game.nextPhaseView()]}`, ["advance"]);
  }

  _cta(ctx, game, label, id, fill = pal.btn_ok, fg = pal.gold) {
    rect(ctx, 0, NAV_RULE_Y, 480, 1, pal.border);
    const cy = CTA_Y + CTA_H / 2;
    const fwdX = 480 - MARGIN - NAV_W;

    // Quest Setup has no undo history - it is the first screen of a game -
    // but it is also the last point where the scenario and difficulty can
    // still be changed. Its Back leaves the game rather than undoing a move.
    const backId = game.view === "quest_setup" ? ["setup_back"] : ["back"];
    if (game.view === "quest_setup" || game.canUndo()) {
      const back = new Button(backId, MARGIN, CTA_Y, NAV_W, CTA_H);
      bevel(ctx, back.x, back.y, back.w, back.h, pal.btn, false, 3);
      arrowLeft(ctx, MARGIN + NAV_W / 2, cy, ARROW, pal.tan);
      this.buttons.push(back);
    }

    bevel(ctx, fwdX, CTA_Y, NAV_W, CTA_H, fill, false, 3);
    arrowRight(ctx, fwdX + NAV_W / 2, cy, ARROW, fg);

    // Label centred in the span between the squares - a fixed frame, so the
    // text does not shift when Back appears.
    const lx = MARGIN + NAV_W + NAV_PAD, rx = fwdX - NAV_PAD;
    const tcx = Math.floor((lx + rx) / 2);
    // Phase advances read as a kicker over the destination; every other CTA
    // ("End Round", "Flip to Side B ...") is a single centred line.
    if (label.startsWith("Next: ")) {
      textCenter(ctx, "NEXT PHASE", tcx, CTA_Y + 10, LABEL, pal.muted);
      textCenter(ctx, label.slice(6), tcx, CTA_Y + 24, DISPLAY, fg);
    } else {
      textCenter(ctx, label, tcx, CTA_Y + 16, DISPLAY, fg);
    }
    // one hit area: the label span plus the arrow square
    this.buttons.push(new Button(id, lx, CTA_Y, 480 - MARGIN - lx, CTA_H));
  }

  // 2px progress bar along a card's bottom edge (threat/elimination,
  // progress/quest-points). Dim track + coloured fill.
  _bottomBar(ctx, x, w, bottomY, frac, color) {
    const by = bottomY - 2;
    rect(ctx, x, by, w, 2, pal.border);
    if (frac > 0) rect(ctx, x, by, Math.max(1, Math.round(w * Math.min(1, frac))), 2, color);
  }

  // One-tap "everyone's commit is reviewed" button for the commit view -
  // replaces the old per-player CommitModal round-trip. Caption counts
  // confirmed living players; once all are confirmed it reads as done and the
  // button goes inert. Returns the y for whatever follows.
  _totalsRow(ctx, game, y, withSteppers = false, tappable = []) {
    const half = Math.floor((480 - 3 * MARGIN) / 2);
    const defs = [
      ["Questing for", game.willpower, pal.value, "wp", icons.WILLPOWER_MD, pal.gold, true],
      ["Staging area", game.staging, pal.outline, "stg", icons.THREAT_MD, pal.outline, false],
    ];
    defs.forEach(([label, val, pen, key, icon, ipen, shadow], idx) => {
      const x = MARGIN + idx * (half + MARGIN);
      panel(ctx, x, y, half, 84);
      textCenter(ctx, label, x + half / 2, y + 6, BODY, pal.muted);
      // scale 4 is the numeral tier above DISPLAY - owned by this widget,
      // never a reading size (docs/js/ui.js).
      const vw = measureText(String(val), 4);
      const gx = Math.floor(x + half / 2 - (vw + 8 + 28) / 2);
      textLeft(ctx, String(val), gx, y + 32, 4, pen, shadow);
      icons.drawIcon(ctx, icon, gx + vw + 8, y + 32, ipen);
      if (withSteppers) {
        const mn = new Button([key + "-"], x + 8, y + 30, 52, 44);
        const pl = new Button([key + "+"], x + half - 60, y + 30, 52, 44);
        for (const [b, s] of [[mn, "-"], [pl, "+"]]) {
          bevel(ctx, b.x, b.y, b.w, b.h, pal.btn);
          textCenter(ctx, s, b.x + 26, b.y + 10, DISPLAY, pal.tan);
          this.buttons.push(b);
        }
        if (key === "stg") this.buttons.push(new Button(["enc_rem"], x + 64, y, half - 128, 84));
        if (key === "wp") this.buttons.push(new Button(["wp"], x + 64, y, half - 128, 84));
      } else if (tappable.includes(key)) {
        // thin inset dividers + tan +/- glyphs (matches the mock — no button
        // chrome). Left/right strips tap +/-; centre = big editor (direct
        // total entry for "wp", the staging counter for "stg").
        rect(ctx, x + 36, y + 8, 1, 56, pal.border);
        rect(ctx, x + half - 36, y + 8, 1, 56, pal.border);
        textCenter(ctx, "-", x + 18, y + 32, DISPLAY, pal.tan);
        textCenter(ctx, "+", x + half - 18, y + 32, DISPLAY, pal.tan);
        this.buttons.push(new Button([key + "-"], x, y, 36, 84));
        this.buttons.push(new Button([key], x + 36, y, half - 72, 84));
        this.buttons.push(new Button([key + "+"], x + half - 36, y, 36, 84));
        if (key === "stg") {
          textCenter(ctx, `+${game.stagingRevealEstimate()} reveal estimate`,
                     x + half / 2, y + 64, BODY, pal.dim);
        }
      }
    });
  }

  draw(ctx, game) {
    this.buttons = [];
    rect(ctx, 0, 0, 480, 480, pal.bg);
    // Views that draw no stat zone (the pre-game screens) keep the old fixed
    // line; _statZone overwrites this with its own bottom edge.
    this.contentY = CONTENT_Y;
    const view = game.view;
    if (view === "quest_setup") {
      // Same spelling as VIEW_LABELS.quest_setup, which is what any CTA
      // pointing at this view would print. They used to disagree.
      drawHeader(ctx, game, this.buttons, { title: "Quest Setup", roundLabel: "R0" });
    } else if (view === "round_end") {
      // The one screen where two round numbers are live at once: the round
      // being closed, and the one its CTA offers.
      drawHeader(ctx, game, this.buttons, { title: `End of Round ${game.round}` });
    } else if (isWindowView(view)) {
      // "Action Window" is the screen's TITLE and belongs in the header,
      // where every other screen puts its title - not floating in the
      // content area competing with the copy.
      drawHeader(ctx, game, this.buttons, {
        title: `Action Window: ${phaseStep(game.step).phase}`,
        titlePen: pal.purple,
      });
    } else {
      drawHeader(ctx, game, this.buttons);
    }

    if (isWindowView(view)) {
      this._statZone(ctx, game);
      this._drawActionWindow(ctx, game);
      return;
    }

    if (view === "setup_game") {
      const th = notePanel(ctx, MARGIN, 56, 480 - 2 * MARGIN, SETUP_TIP);
      // This view's two rows are the tallest stack on any play screen and used
      // to run to y=412 - 2px PAST the old CTA at 410, an overlap the layout
      // linter never caught because it compares text, not rects. The nav rule
      // at NAV_RULE_Y makes it visible, so the rows were tightened by 20px
      // total (gap 18->8, rows 48->42 and 38->34) and now end at 392, clearing
      // the rule by 8px. Every target stays >=24px.
      const y = 56 + th + 8;
      textLeft(ctx, "Stage 1B quest points", MARGIN + 8, y + 13, BODY, pal.tan);
      const mn = new Button(["qp", -1], 300, y, 52, 42);
      const pl = new Button(["qp", 1], 412, y, 52, 42);
      for (const [b, s] of [[mn, "-"], [pl, "+"]]) {
        bevel(ctx, b.x, b.y, b.w, b.h, pal.btn);
        textCenter(ctx, s, b.x + 26, b.y + 9, DISPLAY, pal.tan);
        this.buttons.push(b);
      }
      textCenter(ctx, String(game.quest.points), 382, y + 9, DISPLAY, pal.gold);
      const sy = y + 44;
      textLeft(ctx, "Sailing quest", MARGIN + 8, sy + 9, BODY, pal.tan);
      icons.drawIcon(ctx, icons.WHEEL, 160, sy + 6,
                     game.sailing ? pal.gold : pal.dim);
      const sb = new Button(["sail_toggle"], 300, sy, 164, 34);
      panel(ctx, sb.x, sb.y, sb.w, sb.h, game.sailing ? pal.gold : pal.btn);
      textCenter(ctx, game.sailing ? "On" : "Off", sb.x + 82, sb.y + 9, BODY,
                 game.sailing ? pal.bg : pal.tan, false);
      this.buttons.push(sb);
      this._cta(ctx, game, "Begin Round 1", ["advance"]);
    } else if (view === "quest_setup") {
      this._statZone(ctx, game);
      this._drawQuestSetup(ctx, game);
    } else if (view === "resource") {
      this._statZone(ctx, game);
      phaseBlock(ctx, MARGIN, this.contentY, 480 - 2 * MARGIN, [
        { kind: "framework", text: PHASE_FRAMEWORK["resource"] },
      ]);
      this._cta(ctx, game, `Next: ${VIEW_LABELS["planning"]}`, ["advance"]);
    } else if (view in LOOP_FLOW) {
      // Four views are genuinely loops and share one widget: Planning, the
      // engagement checks, and both combat halves.
      this._statZone(ctx, game);
      this._loopFlow(ctx, game, this.contentY);
      const nxt = (view === "planning" && game.sailing)
        ? "quest_sailing" : game.nextPhaseView();
      this._cta(ctx, game, `Next: ${VIEW_LABELS[nxt]}`, ["advance"]);
    } else if (view === "quest_commit") {
      this._statZone(ctx, game);
      const bh = phaseBlock(ctx, MARGIN, this.contentY, 480 - 2 * MARGIN,
        [{ kind: "window", text: PHASE_WINDOW["quest_commit"] }]);
      this._totalsRow(ctx, game, this.contentY + bh + 8, false, ["wp", "stg"]);
      this._cta(ctx, game, `Next: ${VIEW_LABELS.quest_staging}`, ["advance"]);
    } else if (view === "quest_sailing") {
      this._statZone(ctx, game);
      if (!game.sailing) {
        notePanel(ctx, MARGIN, this.contentY, 480 - 2 * MARGIN,
                  [SAILING.no_keyword, SAILING.enable_hint]);
        const eb = new Button(["sail_toggle"], MARGIN, this.contentY + 96,
                              480 - 2 * MARGIN, 52);
        bevel(ctx, eb.x, eb.y, eb.w, eb.h, pal.btn);
        icons.drawIcon(ctx, icons.WHEEL, 130, this.contentY + 96 + 14, pal.gold);
        textCenter(ctx, "Enable Sailing", 254, this.contentY + 96 + 16, BODY, pal.tan);
        this.buttons.push(eb);
        this._cta(ctx, game, `Next: ${VIEW_LABELS.quest_commit}`, ["advance"]);
      } else {
        // tip (pipe medallion top-left; wheel glyph inline in the sentence)
        const tw = 480 - 2 * MARGIN, ty0 = this.contentY;
        const gutt = 28 + 14, lh = bandLineH(BODY), th = 3 * lh + 2 * BAND_PAD;
        rect(ctx, MARGIN, ty0, tw, th, pal.card_hi);
        rect(ctx, MARGIN, ty0, 4, th, pal.border_gold);
        icons.drawIcon(ctx, icons.PIPE, MARGIN + 10, ty0 + BAND_PAD, pal.gold);
        const tx = MARGIN + 12 + gutt;
        let ly = ty0 + BAND_PAD;
        const fp = `P${game.first_player + 1}`;
        textLeft(ctx, fp, tx, ly, BODY, pal.muted);
        let sx0 = tx + measureText(fp, BODY) + 6;
        ribbon(ctx, sx0, ly - 1, 10, 18);
        sx0 += 10 + 6;
        textLeft(ctx, "exhausts characters (ships", sx0, ly, BODY, pal.muted);
        ly += lh;
        textLeft(ctx, "count), looks at and discards them.", tx, ly, BODY, pal.muted);
        ly += lh;
        icons.drawIcon(ctx, icons.WHEEL_SM, tx, ly, pal.gold);
        textLeft(ctx, "found: move 1 step on-course.", tx + 22, ly, BODY, pal.muted);
        const sb = new Button(["sail_modal"], MARGIN, ty0 + th + 10, 480 - 2 * MARGIN, 52);
        bevel(ctx, sb.x, sb.y, sb.w, sb.h, pal.btn);
        icons.drawIcon(ctx, icons.WHEEL, 150, sb.y + 14, pal.gold);
        textCenter(ctx, "Log sailing test", 262, sb.y + 16, BODY, pal.tan);
        this.buttons.push(sb);
        this._cta(ctx, game, `Next: ${VIEW_LABELS.quest_commit}`, ["advance"]);
      }
    } else if (view === "quest_staging") {
      this._statZone(ctx, game);
      const bh = phaseBlock(ctx, MARGIN, this.contentY, 480 - 2 * MARGIN, [
        { kind: "framework", text: STAGING.framework },
        { kind: "window", text: STAGING.window },
      ]);
      // Gaps are 4, not 8: the framework line grew to two lines when it
      // gained the STAGING.short rule, and the
      // totals row has to stay clear of the CTA. Re-laid out rather than
      // shrinking the text - see the design system.
      const my = this.contentY + bh + 4;
      const mh = willpowerStagingMeter(ctx, MARGIN, my, 480 - 2 * MARGIN, game.willpower, game.staging);
      this._totalsRow(ctx, game, my + mh + 4, true);
      this._cta(ctx, game, `Next: ${VIEW_LABELS.quest_resolution}`, ["stage_advance"]);
    } else if (view === "quest_resolution") {
      this._drawResolution(ctx, game);
    } else if (view === "travel") {
      this._statZone(ctx, game);
      this._drawTravel(ctx, game);
    } else if (view === "refresh") {
      this._statZone(ctx, game);
      const bh = phaseBlock(ctx, MARGIN, this.contentY, 480 - 2 * MARGIN, [
        { kind: "framework", text: PHASE_FRAMEWORK["refresh"] },
        { kind: "window", text: PHASE_WINDOW["refresh"] },
      ]);
      this._cta(ctx, game, `Next: ${VIEW_LABELS[game.nextPhaseView()]}`, ["advance"]);
    } else if (view === "round_end") {
      // 0.1. Not an action window - RR's chart puts the last one after 7.4 -
      // so no purple treatment: this is a resolution checklist.
      this._statZone(ctx, game);
      phaseBlock(ctx, MARGIN, this.contentY, 480 - 2 * MARGIN, [
        { kind: "framework", text: PHASE_FRAMEWORK["round_end"] },
      ]);
      this._cta(ctx, game,
                `Next: ${VIEW_LABELS["resource"]} (Round ${game.round + 1})`,
                ["endround"]);
    } else {
      this._statZone(ctx, game);
      const flavor = { combat_enemy: [icons.DEFENSE, pal.green],
                       combat_player: [icons.ATTACK, pal.tan] }[view];
      const sections = [];
      if (PHASE_FRAMEWORK[view]) {
        const fw = PHASE_FRAMEWORK[view];
        sections.push({ kind: "framework", text: fw });
      }
      if (PHASE_WINDOW[view]) sections.push({ kind: "window", text: PHASE_WINDOW[view] });
      const reserve = flavor ? 34 : 0;
      const bh = phaseBlock(ctx, MARGIN, this.contentY, 480 - 2 * MARGIN, sections, reserve);
      if (flavor) {
        icons.drawIcon(ctx, flavor[0], 480 - MARGIN - 34,
                       this.contentY + Math.floor((bh - 20) / 2), flavor[1]);
      }
      if (PHASE_CAPTION[view]) {
        // a rules caption: BODY, wrapped over as many lines as it needs
        // (every one of these is 2 lines, ending by y=316).
        const capW = 480 - 2 * (MARGIN + 4);
        let cy = this.contentY + bh + 10;
        for (const ln of wrapText(PHASE_CAPTION[view], BODY, capW)) {
          textLeft(ctx, ln, MARGIN + 4, cy, BODY, pal.dim);
          cy += 24;
        }
      }
      // nextPhaseView(), not raw VIEW_ORDER indexing: the very next view is
      // this phase's action window, and a CTA must announce the next PHASE.
      const nxt = game.nextPhaseView();
      this._cta(ctx, game, `Next: ${VIEW_LABELS[nxt] ?? nxt}`, ["advance"]);
    }

    if (this.notif) {
      const entries = this.notif.map(e =>
        Array.isArray(e) ? (e.length === 3 ? e : [e[0], e[1], "amber"]) : [null, e, "amber"]);
      const hasIcon = entries.some(([ic]) => ic);
      const edge = entries[0][2];
      this.notifEdge = edge;
      const tx0 = MARGIN + (hasIcon ? 48 : 14);
      const usable = 480 - MARGIN - 48 - tx0;
      const lines = [];
      for (const [, s, c] of entries) {
        for (const ln of wrapText(s, BODY, usable)) lines.push([ln, c]);
      }
      const th = Math.max(14 + 22 * lines.length, hasIcon ? 40 : 34);
      bevel(ctx, MARGIN, HEADER_H + 2, 480 - 2 * MARGIN, th, pal.card_hi, false, 2);
      rect(ctx, MARGIN, HEADER_H + 2, 4, th, pal[edge]);
      if (hasIcon) {
        const [firstIc, , firstC] = entries.find(([ic]) => ic);
        icons.drawIcon(ctx, icons[firstIc], MARGIN + 14,
                       HEADER_H + 2 + Math.floor((th - 24) / 2), pal[firstC]);
      }
      let ty = HEADER_H + 9;
      for (const [s, c] of lines) {
        textLeft(ctx, s, tx0, ty, BODY, pal[c]);
        ty += 22;
      }
      const cx = 480 - MARGIN - 22, cy = HEADER_H + 2 + Math.floor(th / 2), r = 11;
      this.notifPie = [cx, cy, r];
      drawNotifPie(ctx, cx, cy, r, this.notifFrac, edge);
      this.buttons.push(new Button(["notif_dismiss"], MARGIN, HEADER_H + 2,
                                   480 - 2 * MARGIN, th));
    } else {
      this.notifPie = null;
    }

    if (this.banner && this.banner[2] === view) {
      const [btextRaw, bkind] = this.banner;
      const bpen = { good: pal.green, bad: pal.red, mid: pal.amber }[bkind];
      const btext = truncateText(btextRaw, BODY, 480 - 2 * MARGIN);
      textCenter(ctx, btext, 240, CTA_Y - 26, BODY, bpen);
    }
  }

  // R0 pre-round-1 phase: stage 1A's setup text to resolve, then the first
  // flip (1A -> 1B) that begins round 1. Reuses the standard zones (Task 8).
  _drawQuestSetup(ctx, game) {
    const card = game.stages[game.stage_idx].cards[game.card_idx];
    const aFace = card.faces.find(f => f.side === "A") ?? {};
    // No bespoke title block. A centred amber stage label over a
    // DISPLAY-gold card name was this view's own invention - nothing else
    // in the app presents content that way - and it pushed the actual
    // instruction down the screen.

    // Framework treatment, like every other "this happens anyway" band in the
    // app: say what to DO, and let the card's own text live one tap away
    // behind View quest card. Printing the setup text here made this screen a
    // text dump with a button under it, duplicating a card the player can
    // already open. No stage number or card name in the copy either - the
    // screen shows both 20px above.
    const stageN = `${game.quest.stage_n}${game.quest.side}`;
    const lead = aFace.text
      ? QUEST_SETUP.resolve.replace("%s", stageN).replace("%s", aFace.name || "")
      : QUEST_SETUP.none.replace("%s", stageN);
    phaseBlock(ctx, MARGIN, this.contentY, 480 - 2 * MARGIN, [
      { kind: "framework",
        text: [lead, QUEST_SETUP.then_flip.replace("%s", game.quest.stage_n)] },
    ]);

    // Read-only card modal (M4-B) - see onButton; null for custom games
    // (no scenario loaded, nothing to show).
    const cardBtn = new Button(["open_card_modal"], MARGIN, 358, 480 - 2 * MARGIN, 44);
    bevel(ctx, cardBtn.x, cardBtn.y, cardBtn.w, cardBtn.h, pal.btn);
    textCenter(ctx, QUEST_SETUP.view, 240, cardBtn.y + 14, BODY, pal.tan);
    this.buttons.push(cardBtn);

    this._cta(ctx, game, QUEST_SETUP.begin, ["flip_to_b"]);
  }

  _drawTravel(ctx, game) {
    // "Blocked" is about whether a location is active AT ALL. Rules Reference,
    // "Active Location": "There can only be one active location at a time" and
    // "The players cannot travel if another location card is active." The five
    // cards that seat a second one say so in their own text, and card text
    // beats the rulebook - but the default stays "any", not "exactly one".
    const loc = game.active_locations[0] ?? null;
    const fw = loc
      ? TRAVEL.blocked
      : TRAVEL.open;
    const bh = phaseBlock(ctx, MARGIN, this.contentY, 480 - 2 * MARGIN,
      [{ kind: "framework", text: fw }, { kind: "window", text: "Responses." }]);
    const y = this.contentY + bh + 10;
    if (!loc) {
      const tb = new Button(["travel_new"], MARGIN, y, 480 - 2 * MARGIN, 56);
      bevel(ctx, tb.x, tb.y, tb.w, tb.h, pal.btn);
      textCenter(ctx, TRAVEL.btn_travel, 240, y + 18, BODY, pal.tan);
      this.buttons.push(tb);
    } else {
      const cb = new Button(["travel_change"], MARGIN, y, 480 - 2 * MARGIN, 48);
      panel(ctx, cb.x, cb.y, cb.w, cb.h);
      textCenter(ctx, TRAVEL.btn_replace, 240, y + 14, BODY, pal.muted);
      this.buttons.push(cb);
    }
    this._cta(ctx, game, `Next: ${VIEW_LABELS.enc_optional}`, ["advance"]);
  }

  _outcomeToast(game) {
    if (game.quest_outcome === "success")
      return ["TRAIL", `Quested successfully! +${game.quest_outcome_n} progress`, "green"];
    if (game.quest_outcome === "fail")
      return ["THREAT_SM", `Quest failed. +${game.quest_outcome_n} threat to all`, "red"];
    return [null, OUTCOME.toast_tie, "amber"];
  }

  _drawResolution(ctx, game) {
    if (game.quest_outcome !== "success") {
      // fail / tie: no placement - just report the outcome and move on
      this._statZone(ctx, game);
      const fail = game.quest_outcome === "fail";
      const ty0 = this.contentY, gutt = 28 + 14, tx = MARGIN + 12 + gutt,
            lh = bandLineH(BODY);
      const th = 2 * lh + 2 * BAND_PAD;
      rect(ctx, MARGIN, ty0, 480 - 2 * MARGIN, th, pal.card_hi);
      // RED, not the gold hint bar: this reports what the resolution already
      // did to the table - the quest failed and threat rose - which is exactly
      // "happens whether or not you act". The sailing panel above stays gold,
      // because that one really is a hint about a control.
      rect(ctx, MARGIN, ty0, 4, th, pal.red);
      icons.drawIcon(ctx, icons.PIPE, MARGIN + 10, ty0 + BAND_PAD, pal.gold);
      // line 1: outcome + a broken heart marking the failed quest
      const l1 = fail ? "Quest failed. " : OUTCOME.card_tie;
      textLeft(ctx, l1, tx, ty0 + BAND_PAD, BODY, pal.muted);
      drawHeart(ctx, tx + measureText(l1, BODY) + 8, ty0 + BAND_PAD + 8, 7, true, pal.red);
      // line 2
      const y2 = ty0 + BAND_PAD + lh;
      if (fail) {
        const a = "Each player's ";
        textLeft(ctx, a, tx, y2, BODY, pal.muted);
        const ax = tx + measureText(a, BODY);
        icons.drawIcon(ctx, icons.THREAT_SM, ax, y2 - 1, pal.red);
        textLeft(ctx, `rose by ${game.quest_outcome_n}.`, ax + icons.THREAT_SM[0] + 6, y2,
                 BODY, pal.muted);
      } else {
        textLeft(ctx, OUTCOME.tie_line2, tx, y2, BODY, pal.muted);
      }
      this._cta(ctx, game, `Next: ${VIEW_LABELS.travel}`, ["advance"]);
      return;
    }
    if (this.alloc === null) {
      const a = game.autoSplit(game.pending_budget);
      this.alloc = { locations: game.active_locations.map((_, i) => a.locations[i] ?? 0),
                     quest: a.quest,
                     side_quests: game.side_quests.map((_, i) => a.side_quests[i] ?? 0) };
    }
    const alloc = this.alloc;
    // Rules: progress fills the active location(s) first; only the overflow
    // past their quest points reaches a quest. The quest/side '+' steppers
    // cascade that way, so the location rows need not be locked.
    // Re-fit if the row count changed under us - a location can be explored
    // between opening this screen and re-drawing it, and a stale list would
    // credit progress to a seat that is gone.
    if (alloc.locations.length !== game.active_locations.length) {
      alloc.locations = game.active_locations.map((_, i) => alloc.locations[i] ?? 0);
    }
    const used = alloc.locations.reduce((a, b) => a + b, 0) + alloc.quest
      + alloc.side_quests.reduce((a, b) => a + b, 0);
    const discard = game.pending_budget - used;

    textCenter(ctx, `Place ${game.pending_budget} progress`, 240, HEADER_H + 6, DISPLAY, pal.gold);

    const rows = [];
    game.active_locations.forEach((loc, i) => {
      rows.push(["location", i, i === 0 ? "Location" : `Location ${i + 1}`,
                 loc.progress, loc.points]);
    });
    rows.push(["quest", null, `Quest ${game.questLabel()}`,
               game.quest.progress, game.quest.points]);
    game.side_quests.forEach((sq, i) => {
      rows.push(["side", i, `Side Quest ${i + 1}`, sq.progress, sq.points]);
    });

    const rw = 480 - 2 * MARGIN;
    // spreadsheet columns: TARGET | WAS (before) | PLACE (this round) | GOAL
    const cxWas = 176, cxPlace = 300, cxGoal = 432;
    const mnX = 212, plX = 340, btnW = 44, btnH = 40;

    let hy = HEADER_H + 40;
    if (game.active_locations.length) {
      // rules caption -> BODY (334px of the 464 available). hy moves from +50
      // to +56 to clear the taller line; the table below shifts 6px and still
      // ends 38px clear of the CTA.
      textCenter(ctx, OUTCOME.alloc_caption, 240, HEADER_H + 32,
                 BODY, pal.dim);
      hy = HEADER_H + 56;
    }
    // ALL-CAPS column heads over a dense table - LABEL is right here.
    textLeft(ctx, "TARGET", 20, hy, LABEL, pal.dim);
    textCenter(ctx, "WAS", cxWas, hy, LABEL, pal.dim);
    textCenter(ctx, "PLACE", cxPlace, hy, LABEL, pal.dim);
    textCenter(ctx, "GOAL", cxGoal, hy, LABEL, pal.dim);

    let y = hy + 12;
    for (const [key, idx, label, cur, pts] of rows) {
      const add = key === "side" ? alloc.side_quests[idx]
        : key === "location" ? alloc.locations[idx] : alloc[key];
      const result = cur + add;                                  // was + place
      const done = pts > 0 && result >= pts;
      const locked = key === "location";                         // forced: fills first
      panel(ctx, MARGIN, y, rw, 52, done ? pal.card_hi : pal.card,
            done ? pal.border_gold : pal.border);
      textLeft(ctx, label, 20, y + 16, BODY, done ? pal.gold : pal.tan);
      if (done) drawFlag(ctx, 20 + measureText(label, BODY) + 8, y + 12, 20, pal.gold);
      textCenter(ctx, String(cur), cxWas, y + 16, BODY, pal.dim);  // WAS - read-only base
      if (locked) {
        // display only: the location is filled first via the quest '+' cascade
        textCenter(ctx, String(add), cxPlace, y + 10, DISPLAY, add > 0 ? pal.gold : pal.dim);
      } else {
        const mn = new Button(["am", key, idx], mnX, y + 6, btnW, btnH);
        const pl = new Button(["ap", key, idx], plX, y + 6, btnW, btnH);
        for (const [b, s] of [[mn, "-"], [pl, "+"]]) {
          bevel(ctx, b.x, b.y, b.w, b.h, pal.btn);
          textCenter(ctx, s, b.x + btnW / 2, b.y + 8, DISPLAY, pal.tan);
          this.buttons.push(b);
        }
        textCenter(ctx, String(add), cxPlace, y + 10, DISPLAY, add > 0 ? pal.gold : pal.dim);
      }
      textCenter(ctx, String(pts), cxGoal, y + 16, BODY, pal.tan);  // GOAL - points needed
      // running total bar: (was + place) / goal
      this._bottomBar(ctx, MARGIN, rw, y + 52, pts > 0 ? result / pts : 0, pal.gold);
      y += 58;
    }

    if (discard > 0) {
      panel(ctx, MARGIN, y, rw, 44, pal.card);
      textLeft(ctx, OUTCOME.alloc_unplaced, 20, y + 14, BODY, pal.dim);
      textCenter(ctx, String(discard), cxGoal, y + 8, DISPLAY, pal.red);
      y += 50;
    }

    const rb = new Button(["areset"], MARGIN, y + 2, rw, 38);
    bevel(ctx, rb.x, rb.y, rb.w, rb.h, pal.btn);
    textCenter(ctx, "Reset", 240, y + 12, BODY, pal.tan);
    this.buttons.push(rb);

    this._cta(ctx, game, `Next: ${VIEW_LABELS.travel}`, ["apply_alloc"]);
  }

  onButton(btn, game) {
    const k = btn.id[0];
    if (k === "nav") return ["goto", btn.id[1]];
    if (k === "back") {
      if (!game.undo()) return null;
      // screen-local scratch describes the view we just left
      this.alloc = null;
      this.banner = null;
      return true;
    }
    if (k === "notif_dismiss") { this.notif = null; return true; }
    if (k === "qp") {
      const was = game.quest.points;
      game.quest.points = Math.max(0, Math.min(30, was + btn.id[1]));
      if (game.quest.points !== was) {
        game.logEvent(`Stage ${game.quest.stage_n}${game.quest.side} quest points `
                      + `${was} -> ${game.quest.points}`);
      }
      return true;
    }
    if (k === "setup" ) return null;
    if (k === "open_card_modal") {
      // Custom games have no scenario/stages - nothing to show.
      return game.stages.length ? ["modal", new QuestCardModal(game)] : null;
    }
    if (k === "setup_back") {
      // Back to the difficulty picker for the chosen scenario. Nothing to
      // undo: no move has been made, and preloadScenario re-runs on the way
      // back in.
      return ["goto", "scenario_options"];
    }
    if (k === "flip_to_b") {
      // Mirrors advanceView's setup_game -> round-1 branch (custom-quest
      // path), but for a scenario game: flip 1A -> 1B first, then the same
      // round-1 entry (log, enter view, reset commits, snapshot round).
      const pts = game.flipToB();
      game.logEvent(`Setup complete - round 1 begins (quest ${game.questLabel()} needs ${pts})`);
      game.enterView(VIEW_ORDER[0]);
      game._snapshotRound();
      this.banner = null;
      return true;
    }
    if (k === "players_detail") return ["modal", new PlayersDetailModal(game)];
    if (k === "wp") {
      return ["modal", new CounterModal(TOTALS.willpower_modal, game.willpower,
        v => { game.setWillpower(v); }, "willpower")];
    }
    if (k === "enc_rem") return ["modal", new RemindersModal(game)];
    if (k === "stg") {
      return ["modal", new CounterModal(TOTALS.staging_modal, game.staging,
        v => { game.setStaging(v); }, "threat")];
    }
    if (k === "wp-") { game.setWillpower(game.willpower - 1); return true; }
    if (k === "wp+") { game.setWillpower(game.willpower + 1); return true; }
    if (k === "stg-") { game.setStaging(game.staging - 1); return true; }
    if (k === "stg+") { game.setStaging(game.staging + 1); return true; }
    // Task 10 reworks the modal this opens.
    if (k === "progress_detail") return ["modal", new QuestingProgressModal(game)];
    if (k === "stage_advance") {
      if (!game.quest_resolved) {
        const res = game.resolveQuest(game.willpower, game.staging);
        this.alloc = null;
        if (res.outcome === "success") game.pending_budget = res.budget;
        this.toast = [this._outcomeToast(game)];   // shown as a toast, not a banner
      }
      game.enterView("quest_resolution");
      return true;
    }
    if (k === "am" || k === "ap") {
      const [, key, idx] = btn.id;                 // key: "quest" | "side"
      const a = this.alloc;
      const used = a.locations.reduce((x, y) => x + y, 0) + a.quest
        + a.side_quests.reduce((x, y) => x + y, 0);
      // Room left in each seat, in list order - the '+' cascade fills them in
      // that order before anything reaches the quest.
      const locRoom = game.active_locations.map(l => Math.max(0, l.points - l.progress));
      const qCur = key === "side" ? game.side_quests[idx].progress : game.quest.progress;
      const qPts = key === "side" ? game.side_quests[idx].points : game.quest.points;
      const qRoom = Math.max(0, qPts - qCur);
      const nowQ = key === "side" ? a.side_quests[idx] : a.quest;
      const bumpQ = d => key === "side" ? (a.side_quests[idx] += d) : (a.quest += d);
      if (k === "ap") {                       // + : active locations fill first
        if (used >= game.pending_budget) return true;   // budget spent
        for (let i = 0; i < locRoom.length; i++) {
          if (a.locations[i] < locRoom[i]) { a.locations[i] += 1; return true; }
        }
        if (nowQ < qRoom) bumpQ(1);            // locations full -> the quest itself
        return true;
      }
      // - : pull back the quest first, then unwind the location fill - last
      // seat first, the reverse of the order '+' filled them in.
      if (nowQ > 0) { bumpQ(-1); return true; }
      const overflow = a.quest + a.side_quests.reduce((x, y) => x + y, 0);
      if (overflow === 0) {
        for (let i = a.locations.length - 1; i >= 0; i--) {
          if (a.locations[i] > 0) { a.locations[i] -= 1; break; }
        }
      }
      return true;
    }
    if (k === "areset") {
      // clear every placement; each value falls back to its pre-resolution
      // base, and the budget is re-placed via the '+' cascade
      const a = this.alloc;
      if (a) {
        a.locations = a.locations.map(() => 0);
        a.quest = 0;
        a.side_quests = a.side_quests.map(() => 0);
      }
      return true;
    }
    if (k === "apply_alloc") {
      const used = this.alloc.locations.reduce((x, y) => x + y, 0) + this.alloc.quest
        + this.alloc.side_quests.reduce((x, y) => x + y, 0);
      const discard = game.pending_budget - used;
      const completed = game.placeProgress(this.alloc);
      let msg = `Placed ${used} progress`;
      if (discard > 0) msg += `, discarded ${discard} (over capacity)`;
      if (completed.length) msg += ` (${completed.join(", ")})`;
      game.logEvent(msg);
      game.pending_budget = 0;
      this.alloc = null;
      // Through the resolution window, not past it: allocating progress is
      // the 3.4 step, and 3.4's window follows it like any other.
      game.enterView("aw_quest_resolution");
      if (game.pending_stage) return ["modal", new StageCompleteModal(game)];
      if (game.pending_resolution) {
        // Catalog game: placeProgress() (gamestate.js, B-resolve Task 1)
        // deferred the actual advance mechanics here rather than doing them
        // synchronously - open the guided flow now that the allocation is
        // applied and the view has moved on.
        const forced = game.pending_resolution === "forced";
        game.pending_resolution = false;
        return ["modal", new ResolutionModal(game, forced)];
      }
      return true;
    }
    // Travel opens the location picker, which needs the scenario's
    // gather-list union fetched from the catalog first - which onButton
    // cannot await mid-tap. Flag it and let main.js's loop build the modal,
    // same pending-flag pattern as pending_side_quest_pick.
    if (k === "travel_new" || k === "travel_change") {
      game.pending_location_pick = { mode: k.slice("travel_".length), back: "play" };
      return true;
    }
    if (k === "sail_modal") return ["modal", new SailingModal(game)];
    if (k === "sail_toggle") {
      game.sailing = !game.sailing;
      if (game.sailing) game.heading = 0;
      game.logEvent(game.sailing
        ? "Sailing enabled (Dream-chaser) - heading starts On-course"
        : "Sailing disabled");
      return true;
    }
    if (k === "endround") { game.endRound(); this.banner = null; return true; }
    if (k === "advance") { game.advanceView(); this.banner = null; return true; }
    return null;
  }
}
