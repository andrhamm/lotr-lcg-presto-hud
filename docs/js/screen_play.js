// Port of ui/screen_play.py — the guided round.
import { pal, Button, rect, panel, bevel, textLeft, textCenter, wrapText,
         truncateText, ribbon, notePanel, phaseBlock, willpowerStagingMeter,
         drawHeart, drawFlag, disc, arcRuns, wxSmall, token,
         arrowLeft, arrowRight,
         DISPLAY, BODY, LABEL } from "./ui.js";
import { measureText } from "./metrics.js";
import { step as phaseStep } from "./phases.js";
import * as icons from "./icons.js";
import { VIEW_ORDER, isWindowView, phaseViewOf } from "./gamestate.js";
import { VIEW_LABELS, SETUP_TIP, ACTION_WINDOW_TIPS, PHASE_FRAMEWORK, PHASE_WINDOW,
         PHASE_CAPTION, COMBAT_FLOW, SHIP_NOTES, STAGING, TRAVEL,
         OUTCOME, SAILING, QUEST_SETUP, CONFIRM, TOTALS,
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
const AW_Y0 = 146;                      // top of the copy band, under the zones
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

  // Flipped 3-row players matrix: P# header / threat token / willpower token,
  // one shared tap target over the whole zone (columns are fixed - up to
  // MAX_PLAYERS - not width-sized off the live player count).
  //
  // The tokens are READ-ONLY. 77f2e11 made each threat token two 24px
  // tap-halves (-1 / +1) to skip a modal round-trip, which meant widening the
  // columns 32 -> 48px and pushing the progress zone right. That was reverted:
  // these are status readouts, and at 24px they were both too small to hit
  // reliably and too easy to hit by accident. Threat is edited in the Players
  // modal, which has room for real targets.
  _playersZone(ctx, game) {
    const pcx = [50, 82, 114, 146];
    const threatCy = ZONE_TOP + 40, willCy = ZONE_TOP + 72;
    textCenter(ctx, "P", 18, ZONE_TOP + 2, BODY, pal.muted);
    // player threat helm keeps its red identity (charcoal dropshadow)
    icons.drawIcon(ctx, icons.THREAT, 8, threatCy - 9, pal.bevel_d);
    icons.drawIcon(ctx, icons.THREAT, 7, threatCy - 10, pal.red);
    icons.drawIcon(ctx, icons.WILLPOWER, 7, willCy - 10, pal.gold);
    game.players.forEach((p, i) => {
      const cx = pcx[i];
      if (i === game.first_player) {
        rect(ctx, cx - 12, ZONE_TOP - 2, 24, 19, pal.gold);
        textCenter(ctx, String(i + 1), cx, ZONE_TOP + 1, BODY, pal.bg, false);
      } else {
        textCenter(ctx, String(i + 1), cx, ZONE_TOP + 1, BODY, pal.tan);
      }
      const danger = p.threat >= p.elimination - 10;
      const tfrac = p.elimination > 0 ? p.threat / p.elimination : 0;
      token(ctx, cx, threatCy, 14, 2, p.eliminated ? "OUT" : String(p.threat),
            p.eliminated ? pal.red : pal.value, tfrac,
            danger ? pal.red : pal.gold, pal.dim);
      const wpFill = game.view === "quest_commit"
        ? (p.commit_touched ? pal.gold : pal.dim) : pal.gold;
      token(ctx, cx, willCy, 14, 2, p.commit, pal.value, 1.0, wpFill, pal.dim);
    });
    this.buttons.push(new Button(["players_detail"], 8, ZONE_TOP - 2, 156, 90));
  }

  // Flipped progress header + one circle row: Q / L / S1..Sn / sailing, one
  // shared tap target over the whole zone. Columns are capped to what fits;
  // overflow drops the newest side quests. Back at x=174 / 9 columns now that
  // the players zone no longer needs 36px for inline threat taps.
  _progressZone(ctx, game) {
    rect(ctx, 168, ZONE_TOP, 1, 90, pal.border);
    const cols = [["Q", game.quest.progress, game.quest.points]];
    if (game.active_location) {
      cols.push(["L", game.active_location.progress, game.active_location.points]);
    }
    const sideCols = game.side_quests.map((sq, i) => [`S${i + 1}`, sq.progress, sq.points]);
    const maxCols = Math.floor((472 - 174) / 32);
    const fixed = cols.length + (game.sailing ? 1 : 0);
    const sideBudget = Math.max(0, maxCols - fixed);
    const allCols = cols.concat(sideCols.slice(0, sideBudget));
    allCols.forEach(([label, prog, pts], i) => {
      const cx = 190 + i * 32;
      textCenter(ctx, label, cx, ZONE_TOP + 2, BODY, pal.tan);
      const rem = Math.max(0, pts - prog);
      const frac = pts > 0 ? prog / pts : 0;
      token(ctx, cx, ZONE_TOP + 40, 14, 2, rem, pal.value, frac, pal.gold, pal.dim);
    });
    if (game.sailing) {
      const scx = 190 + allCols.length * 32;
      icons.drawIcon(ctx, icons.WHEEL_SM, scx - 8, ZONE_TOP, pal.gold);
      disc(ctx, scx, ZONE_TOP + 40, 14, pal.well);
      [[272, 360], [0, 88], [92, 178], [182, 268]].forEach(([a0, a1], rank) => {
        arcRuns(ctx, scx, ZONE_TOP + 40, 14, 11, a0, a1,
                rank < game.heading ? pal.dim : pal.gold);
      });
      wxSmall(ctx, game.heading, scx, ZONE_TOP + 40, 6);
    }
    // a rules caption (what the ring numeral means), not chrome - BODY.
    // 210px at BODY inside the 258px zone, so it needs no re-layout.
    textLeft(ctx, "quest points remaining", 174, ZONE_TOP + 66, BODY, pal.dim);
    this.buttons.push(new Button(["progress_detail"], 174, ZONE_TOP - 2, 298, 90));
  }

  // The bottom nav bar: a 1px rule, then matching square arrow buttons at each
  // edge with the destination label between them.
  //
  // The label sits OUTSIDE both buttons so the two arrows stay identically
  // sized. It is still part of the forward button's hit area, though - that
  // control is tapped every phase, so its target spans label + arrow rather
  // than the 58px square alone. Back's target is only its square, so a
  // mis-reach for the label can never undo.
  _drawActionWindow(ctx, game) {
    const y0 = AW_Y0, w = 480 - 2 * MARGIN;
    const gutter = icons.LEADERSHIP[0] + 14;
    const usable = w - 16 - 12 - gutter;
    const lh = 10 * BODY + 6;
    const bandTop = y0, bandBottom = AW_MAX_BOTTOM;
    const maxLines = Math.max(1, Math.floor((bandBottom - bandTop - 16) / lh));
    // Whole paragraphs only - clipping a sentence mid-clause is exactly what
    // the design system forbids.
    const lines = [];
    for (const para of (ACTION_WINDOW_TIPS[phaseViewOf(game.view)] ?? [])) {
      const wrapped = wrapText(para, BODY, usable, measureText);
      if (lines.length + wrapped.length > maxLines) continue;
      lines.push(...wrapped);
    }
    const ph = Math.max(lines.length * lh + 16, icons.LEADERSHIP[0] + 14);
    const ty = bandTop + Math.max(0, Math.floor((bandBottom - bandTop - ph) / 2));
    notePanel(ctx, MARGIN, ty, w, lines, BODY, 0, icons.LEADERSHIP);
    // The window hands off to the NEXT step, so the CTA names it - the same
    // "Next: X" every phase view uses.
    this._cta(ctx, game, `Next: ${VIEW_LABELS[game.nextPhaseView()]}`, ["advance"]);
  }

  _cta(ctx, game, label, id, fill = pal.btn_ok, fg = pal.gold) {
    rect(ctx, 0, NAV_RULE_Y, 480, 1, pal.border);
    const cy = CTA_Y + CTA_H / 2;
    const fwdX = 480 - MARGIN - NAV_W;

    if (game.canUndo()) {
      const back = new Button(["back"], MARGIN, CTA_Y, NAV_W, CTA_H);
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
  _drawConfirmAll(ctx, game, y) {
    const living = game.players.filter(p => !p.eliminated);
    const done = living.filter(p => p.commit_touched);
    const allDone = living.length > 0 && done.length === living.length;
    const b = new Button(["confirm_all"], MARGIN, y, 480 - 2 * MARGIN, 40);
    bevel(ctx, b.x, b.y, b.w, b.h, allDone ? pal.card : pal.btn);
    const label = allDone ? CONFIRM.all
                          : `Confirm all commits (${done.length}/${living.length})`;
    textCenter(ctx, label, 240, y + 12, BODY, allDone ? pal.dim : pal.tan);
    if (!allDone) this.buttons.push(b);
    return y + 48;
  }

  // Live REFRESH.preview_caption threat per living player, flagged red when the
  // projected value crosses the same danger threshold _playersZone uses
  // (proj >= elimination - 10). Eliminated players are skipped: their threat is
  // capped at their elimination level and does not keep rising. Height: 48
  // (the caption is BODY, so the row below it sits 22px down, not 14px).
  _refreshThreatPreview(ctx, game, y) {
    textLeft(ctx, "After +1 threat:", MARGIN + 4, y, BODY, pal.dim);
    let x = MARGIN + 4;
    const ly = y + 22;
    game.players.forEach((p, i) => {
      if (p.eliminated) return;
      const proj = p.threat + p.threat_per_round;
      const danger = proj >= p.elimination - 10;
      const seg = `P${i + 1} ${p.threat}->${proj}${danger ? "!" : ""}`;
      textLeft(ctx, seg, x, ly, BODY, danger ? pal.red : pal.value);
      x += measureText(seg, BODY) + 16;
    });
    return 48;
  }

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
    const view = game.view;
    if (view === "quest_setup") {
      drawHeader(ctx, game, this.buttons, { title: "QUEST SETUP", roundLabel: "R0" });
    } else if (isWindowView(view)) {
      // "ACTION WINDOW" is the screen's TITLE and belongs in the header,
      // where every other screen puts its title - not floating in the
      // content area competing with the copy.
      drawHeader(ctx, game, this.buttons, {
        title: `ACTION WINDOW - ${phaseStep(game.step).phase.toUpperCase()}`,
        titlePen: pal.purple,
      });
    } else {
      drawHeader(ctx, game, this.buttons);
    }

    if (isWindowView(view)) {
      this._playersZone(ctx, game);
      this._progressZone(ctx, game);
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
      this._playersZone(ctx, game);
      this._progressZone(ctx, game);
      this._drawQuestSetup(ctx, game);
    } else if (view === "resource") {
      this._playersZone(ctx, game);
      this._progressZone(ctx, game);
      phaseBlock(ctx, MARGIN, CONTENT_Y, 480 - 2 * MARGIN, [
        { kind: "framework", text: PHASE_FRAMEWORK["resource"] },
      ]);
      this._cta(ctx, game, `Next: ${VIEW_LABELS["planning"]}`, ["advance"]);
    } else if (view === "planning") {
      this._playersZone(ctx, game);
      this._progressZone(ctx, game);
      phaseBlock(ctx, MARGIN, CONTENT_Y, 480 - 2 * MARGIN, [
        { kind: "framework", text: PHASE_FRAMEWORK["planning"] },
        { kind: "window", text: PHASE_WINDOW["planning"] },
      ]);
      const nxt = game.sailing ? "quest_sailing" : "quest_commit";
      this._cta(ctx, game, `Next: ${VIEW_LABELS[nxt]}`, ["advance"]);
    } else if (view === "quest_commit") {
      this._playersZone(ctx, game);
      this._progressZone(ctx, game);
      const bh = phaseBlock(ctx, MARGIN, CONTENT_Y, 480 - 2 * MARGIN,
        [{ kind: "window", text: PHASE_WINDOW["quest_commit"] }]);
      const cy = this._drawConfirmAll(ctx, game, CONTENT_Y + bh + 8);
      this._totalsRow(ctx, game, cy, false, ["wp", "stg"]);
      this._cta(ctx, game, `Next: ${VIEW_LABELS.quest_staging}`, ["advance"]);
    } else if (view === "quest_sailing") {
      this._playersZone(ctx, game);
      this._progressZone(ctx, game);
      if (!game.sailing) {
        notePanel(ctx, MARGIN, CONTENT_Y + 6, 480 - 2 * MARGIN,
                  [SAILING.no_keyword, SAILING.enable_hint]);
        const eb = new Button(["sail_toggle"], MARGIN, CONTENT_Y + 96,
                              480 - 2 * MARGIN, 52);
        bevel(ctx, eb.x, eb.y, eb.w, eb.h, pal.btn);
        icons.drawIcon(ctx, icons.WHEEL, 130, CONTENT_Y + 96 + 14, pal.gold);
        textCenter(ctx, "Enable Sailing", 254, CONTENT_Y + 96 + 16, BODY, pal.tan);
        this.buttons.push(eb);
        this._cta(ctx, game, `Next: ${VIEW_LABELS.quest_commit}`, ["advance"]);
      } else {
        // tip (pipe medallion top-left; wheel glyph inline in the sentence)
        const tw = 480 - 2 * MARGIN, ty0 = CONTENT_Y + 6;
        const gutt = 28 + 14, lh = 26, th = 3 * lh + 16;
        rect(ctx, MARGIN, ty0, tw, th, pal.card_hi);
        rect(ctx, MARGIN, ty0, 4, th, pal.border_gold);
        icons.drawIcon(ctx, icons.PIPE, MARGIN + 10, ty0 + 8, pal.gold);
        const tx = MARGIN + 12 + gutt;
        let ly = ty0 + 8;
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
      this._playersZone(ctx, game);
      this._progressZone(ctx, game);
      const bh = phaseBlock(ctx, MARGIN, CONTENT_Y, 480 - 2 * MARGIN, [
        { kind: "framework", text: STAGING.framework },
        { kind: "window", text: STAGING.window },
      ]);
      // Gaps are 4, not 8: the framework line grew to two lines when it
      // gained the STAGING.short rule, and the
      // totals row has to stay clear of the CTA. Re-laid out rather than
      // shrinking the text - see the design system.
      const my = CONTENT_Y + bh + 4;
      const mh = willpowerStagingMeter(ctx, MARGIN, my, 480 - 2 * MARGIN, game.willpower, game.staging);
      this._totalsRow(ctx, game, my + mh + 4, true);
      this._cta(ctx, game, `Next: ${VIEW_LABELS.quest_resolution}`, ["stage_advance"]);
    } else if (view === "quest_resolution") {
      this._drawResolution(ctx, game);
    } else if (view === "travel") {
      this._playersZone(ctx, game);
      this._progressZone(ctx, game);
      this._drawTravel(ctx, game);
    } else if (view === "refresh") {
      this._playersZone(ctx, game);
      this._progressZone(ctx, game);
      const bh = phaseBlock(ctx, MARGIN, CONTENT_Y, 480 - 2 * MARGIN, [
        { kind: "framework", text: PHASE_FRAMEWORK["refresh"] },
        { kind: "window", text: PHASE_WINDOW["refresh"] },
      ]);
      this._refreshThreatPreview(ctx, game, CONTENT_Y + bh + 8);
      this._cta(ctx, game, "End Round", ["endround"]);
    } else {
      this._playersZone(ctx, game);
      const flavor = { combat_enemy: [icons.DEFENSE, pal.green],
                       combat_player: [icons.ATTACK, pal.tan] }[view];
      this._progressZone(ctx, game);
      const shipNotes = SHIP_NOTES;
      const sections = [];
      if (PHASE_FRAMEWORK[view]) {
        const fw = game.sailing && shipNotes[view]
          ? [PHASE_FRAMEWORK[view], shipNotes[view]] : PHASE_FRAMEWORK[view];
        sections.push({ kind: "framework", text: fw });
      }
      if (PHASE_WINDOW[view]) sections.push({ kind: "window", text: PHASE_WINDOW[view] });
      const reserve = flavor ? 34 : 0;
      const bh = phaseBlock(ctx, MARGIN, CONTENT_Y, 480 - 2 * MARGIN, sections, reserve);
      if (flavor) {
        icons.drawIcon(ctx, flavor[0], 480 - MARGIN - 34,
                       CONTENT_Y + Math.floor((bh - 20) / 2), flavor[1]);
      }
      if (PHASE_CAPTION[view]) {
        // a rules caption: BODY, wrapped over as many lines as it needs
        // (every one of these is 2 lines, ending by y=316).
        const capW = 480 - 2 * (MARGIN + 4);
        let cy = CONTENT_Y + bh + 10;
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
    const stageLabel = `STAGE ${game.quest.stage_n}${game.quest.side}`;
    textCenter(ctx, stageLabel, 240, CONTENT_Y, BODY, pal.amber);
    const nameY = CONTENT_Y + 22;
    const cardName = truncateText(aFace.name ?? "", DISPLAY, 480 - 2 * MARGIN);
    textCenter(ctx, cardName, 240, nameY, DISPLAY, pal.gold);

    // Distinct scroll-style tip: a double gold frame + ribbon banner - UNLIKE
    // the standard notePanel() left-accent-bar style used elsewhere, since
    // this is the one moment that reads as "resolve this printed text now".
    const tipX = MARGIN, tipW = 480 - 2 * MARGIN, tipY = nameY + 30;
    // ribbonH is 28, not 22: its caption is BODY (16px tall) plus the 6px
    // inset, and the banner has to hold the text rather than the text shrink
    // to hold the banner.
    const ribbonH = 28, padTop = 10, lineH = 24, padBottom = 10, maxLines = 4;
    const usable = tipW - 28;
    const raw = aFace.text;
    const body = (raw === null || raw === undefined || raw === "")
      ? QUEST_SETUP.none : raw;
    let lines = wrapText(body, BODY, usable);
    if (lines.length > maxLines) {
      lines = lines.slice(0, maxLines);
      lines[maxLines - 1] = truncateText(`${lines[maxLines - 1]} ..`, BODY, usable);
    }
    const tipH = ribbonH + padTop + lines.length * lineH + padBottom;
    rect(ctx, tipX, tipY, tipW, tipH, pal.border_gold);
    rect(ctx, tipX + 2, tipY + 2, tipW - 4, tipH - 4, pal.bg);
    rect(ctx, tipX + 4, tipY + 4, tipW - 8, tipH - 8, pal.border_gold);
    rect(ctx, tipX + 6, tipY + 6, tipW - 12, tipH - 12, pal.scroll);
    rect(ctx, tipX, tipY, tipW, ribbonH, pal.border_gold);
    textLeft(ctx, QUEST_SETUP.banner, tipX + 10, tipY + 6, BODY, pal.bg, false);
    let ly = tipY + ribbonH + padTop;
    for (const ln of lines) {
      textLeft(ctx, ln, tipX + 14, ly, BODY, pal.tan);
      ly += lineH;
    }

    // Read-only card modal (M4-B) - see onButton; null for custom games
    // (no scenario loaded, nothing to show).
    const cardBtn = new Button(["open_card_modal"], MARGIN, 358, 480 - 2 * MARGIN, 44);
    bevel(ctx, cardBtn.x, cardBtn.y, cardBtn.w, cardBtn.h, pal.btn);
    textCenter(ctx, "View quest card", 240, cardBtn.y + 14, BODY, pal.tan);
    this.buttons.push(cardBtn);

    this._cta(ctx, game, `Flip to Side B  ->  ${card.questPoints} qp`, ["flip_to_b"]);
  }

  _drawTravel(ctx, game) {
    const loc = game.active_location;
    const fw = loc
      ? TRAVEL.blocked
      : TRAVEL.open;
    const bh = phaseBlock(ctx, MARGIN, CONTENT_Y, 480 - 2 * MARGIN,
      [{ kind: "framework", text: fw }, { kind: "window", text: "Responses." }]);
    const y = CONTENT_Y + bh + 10;
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
      this._playersZone(ctx, game);
      this._progressZone(ctx, game);
      const fail = game.quest_outcome === "fail";
      const ty0 = CONTENT_Y + 6, gutt = 28 + 14, tx = MARGIN + 12 + gutt, lh = 26;
      const th = 2 * lh + 16;
      rect(ctx, MARGIN, ty0, 480 - 2 * MARGIN, th, pal.card_hi);
      rect(ctx, MARGIN, ty0, 4, th, pal.border_gold);
      icons.drawIcon(ctx, icons.PIPE, MARGIN + 10, ty0 + 8, pal.gold);
      // line 1: outcome + a broken heart marking the failed quest
      const l1 = fail ? "Quest failed. " : OUTCOME.card_tie;
      textLeft(ctx, l1, tx, ty0 + 8, BODY, pal.muted);
      drawHeart(ctx, tx + measureText(l1, BODY) + 8, ty0 + 8 + 8, 7, true, pal.red);
      // line 2
      const y2 = ty0 + 8 + lh;
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
      this.alloc = { location: a.location, quest: a.quest,
                     side_quests: game.side_quests.map((_, i) => a.side_quests[i] ?? 0) };
    }
    const alloc = this.alloc;
    // Rules: progress fills the active location first; only the overflow past
    // its quest points reaches a quest. The quest/side '+' steppers cascade
    // that way (they fill the location first), so location need not be locked.
    if (!game.active_location) alloc.location = 0;
    const used = alloc.location + alloc.quest + alloc.side_quests.reduce((a, b) => a + b, 0);
    const discard = game.pending_budget - used;

    textCenter(ctx, `Place ${game.pending_budget} progress`, 240, HEADER_H + 6, DISPLAY, pal.gold);

    const rows = [];
    if (game.active_location) {
      rows.push(["location", null, "Location",
                 game.active_location.progress, game.active_location.points]);
    }
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
    if (game.active_location) {
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
      const add = key === "side" ? alloc.side_quests[idx] : alloc[key];
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
      game.quest.points = Math.max(0, Math.min(30, game.quest.points + btn.id[1]));
      return true;
    }
    if (k === "setup" ) return null;
    if (k === "open_card_modal") {
      // Custom games have no scenario/stages - nothing to show.
      return game.stages.length ? ["modal", new QuestCardModal(game)] : null;
    }
    if (k === "flip_to_b") {
      // Mirrors advanceView's setup_game -> round-1 branch (custom-quest
      // path), but for a scenario game: flip 1A -> 1B first, then the same
      // round-1 entry (log, enter view, reset commits, snapshot round).
      const pts = game.flipToB();
      game.logEvent(`Setup complete - round 1 begins (quest ${game.questLabel()} needs ${pts})`);
      game.enterView(VIEW_ORDER[0]);
      game.players.forEach(p => { p.commit_touched = false; });
      game._snapshotRound();
      this.banner = null;
      return true;
    }
    if (k === "players_detail") return ["modal", new PlayersDetailModal(game)];
    if (k === "confirm_all") {
      game.confirmAllCommits();
      game.logEvent("Confirmed all player commits");
      return true;
    }
    if (k === "wp") {
      return ["modal", new CounterModal(TOTALS.willpower_modal, game.willpower,
        v => { game.willpower = v; }, "willpower")];
    }
    if (k === "enc_rem") return ["modal", new RemindersModal(game)];
    if (k === "stg") {
      return ["modal", new CounterModal(TOTALS.staging_modal, game.staging,
        v => { game.staging = v; }, "threat")];
    }
    if (k === "wp-") { game.willpower = Math.max(0, game.willpower - 1); return true; }
    if (k === "wp+") { game.willpower += 1; return true; }
    if (k === "stg-") { game.staging = Math.max(0, game.staging - 1); return true; }
    if (k === "stg+") { game.staging += 1; return true; }
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
      const used = a.location + a.quest + a.side_quests.reduce((x, y) => x + y, 0);
      const locRoom = game.active_location
        ? Math.max(0, game.active_location.points - game.active_location.progress) : 0;
      const qCur = key === "side" ? game.side_quests[idx].progress : game.quest.progress;
      const qPts = key === "side" ? game.side_quests[idx].points : game.quest.points;
      const qRoom = Math.max(0, qPts - qCur);
      const nowQ = key === "side" ? a.side_quests[idx] : a.quest;
      const bumpQ = d => key === "side" ? (a.side_quests[idx] += d) : (a.quest += d);
      if (k === "ap") {                            // + : active location fills first
        if (used >= game.pending_budget) return true;   // budget spent
        if (a.location < locRoom) { a.location += 1; return true; }
        if (nowQ < qRoom) bumpQ(1);               // location full -> the quest itself
        return true;
      }
      // - : pull back the quest first, then unwind the location fill
      if (nowQ > 0) { bumpQ(-1); return true; }
      const overflow = a.quest + a.side_quests.reduce((x, y) => x + y, 0);
      if (overflow === 0 && a.location > 0) a.location -= 1;
      return true;
    }
    if (k === "areset") {
      // clear every placement; each value falls back to its pre-resolution
      // base, and the budget is re-placed via the '+' cascade
      const a = this.alloc;
      if (a) {
        a.location = 0;
        a.quest = 0;
        a.side_quests = a.side_quests.map(() => 0);
      }
      return true;
    }
    if (k === "apply_alloc") {
      const used = this.alloc.location + this.alloc.quest
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
