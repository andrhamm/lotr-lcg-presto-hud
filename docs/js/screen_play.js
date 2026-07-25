// Port of ui/screen_play.py — the guided round.
import { pal, Button, rect, panel, bevel, textLeft, textCenter, wrapText,
         truncateText, ribbon, notePanel, phaseBlock, willpowerStagingMeter,
         drawHeart, drawFlag, disc, arcRuns, wxSmall, token,
         DISPLAY, BODY, LABEL } from "./ui.js";
import { measureText } from "./metrics.js";
import * as icons from "./icons.js";
import { VIEW_ORDER, VIEW_LABELS, SETUP_TIP } from "./gamestate.js";
import { drawHeader, drawNotifPie, HEADER_H, CounterModal,
         PlayersDetailModal, RemindersModal, LocationPickModal, SideQuestsModal,
         QuestConfigModal, StageCompleteModal, SailingModal,
         QuestingProgressModal, QuestCardModal, ResolutionModal } from "./screens.js";

const MARGIN = 8;
const ZONE_TOP = HEADER_H + 6;            // top of the players/progress zones
const CONTENT_Y = 150;                    // zones end ~136; tips start below
const CTA_Y = 410;
const CTA_H = 58;

// Threat-as-risk framing for Encounter & Combat (M2 Task 6): the app tracks
// each player's live threat but not individual enemy cards or their
// engagement costs, so the risk framing is rules-verified explanatory copy
// tied to the numbers already on screen (players-zone threat tokens), not a
// fabricated cost comparison against data the app doesn't have.
const PHASE_FRAMEWORK = {
  enc_checks: "One check engages one enemy: the highest engagement cost that is <= your threat.",
  combat_shadow: "Deal 1 facedown shadow card to each engaged enemy, in player order - highest engagement cost first.",
  combat_enemy: "Choose an enemy -> exhaust a defender (optional) -> shadow effect -> damage, one at a time.",
  combat_player: "Choose an enemy -> exhaust attackers -> total ATK -> damage, one enemy at a time.",
};
const PHASE_WINDOW = {
  enc_optional: "In player order, each player may engage 1 enemy - engagement cost does not matter here.",
  enc_checks: "Responses.",
  combat_shadow: "Responses.",
  combat_enemy: "Responses at each step.",
  combat_player: "Responses at each step.",
};
const PHASE_CAPTION = {
  enc_optional: "Your threat decides which enemies can engage you next.",
  enc_checks: "In player order, repeating until no enemy in staging can engage anyone.",
  combat_enemy: "In player order; each player resolves all their enemies before the next. Undefended: all damage to one of your heroes.",
  combat_player: "In player order; each player makes all their attacks before the next. 1 attack per engaged enemy, and attacking is optional.",
};

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

  // Flipped 3-row players matrix: P# header / threat token (inline +/-) /
  // willpower token. Columns are fixed - up to MAX_PLAYERS - not width-sized
  // off the live player count. Threat columns are 48px wide (not 32px) so
  // each half - tap left = -1, tap right = +1 - clears the >=24px touch
  // target rule; the shared zone button is still the fallback for the P#
  // and willpower rows, appended last so the specific halves win first
  // (first-match-wins hit order).
  _playersZone(ctx, game) {
    const pcx = [44, 92, 140, 188];
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
      // inline +/- split: thin divider through the token, tap left=-1 right=+1
      rect(ctx, cx, threatCy - 14, 1, 28, pal.border);
      this.buttons.push(new Button(["threat", i, -1], cx - 24, threatCy - 16, 24, 32));
      this.buttons.push(new Button(["threat", i, 1], cx, threatCy - 16, 24, 32));
      const wpFill = game.view === "quest_commit"
        ? (p.commit_touched ? pal.gold : pal.dim) : pal.gold;
      token(ctx, cx, willCy, 14, 2, p.commit, pal.value, 1.0, wpFill, pal.dim);
    });
    this.buttons.push(new Button(["players_detail"], 8, ZONE_TOP - 2, 196, 90));
  }

  // Flipped progress header + one circle row: Q / L / S1..Sn / sailing. Starts
  // at x=210 (was 174) - the players zone above gave up 36px for the inline
  // threat +/- columns, so max_cols drops from 9 to 8; the existing overflow
  // logic (drop the newest side quests) already handles that gracefully.
  _progressZone(ctx, game) {
    rect(ctx, 208, ZONE_TOP, 1, 90, pal.border);
    const cols = [["Q", game.quest.progress, game.quest.points]];
    if (game.active_location) {
      cols.push(["L", game.active_location.progress, game.active_location.points]);
    }
    const sideCols = game.side_quests.map((sq, i) => [`S${i + 1}`, sq.progress, sq.points]);
    const maxCols = Math.floor((472 - 214) / 32);
    const fixed = cols.length + (game.sailing ? 1 : 0);
    const sideBudget = Math.max(0, maxCols - fixed);
    const allCols = cols.concat(sideCols.slice(0, sideBudget));
    allCols.forEach(([label, prog, pts], i) => {
      const cx = 230 + i * 32;
      textCenter(ctx, label, cx, ZONE_TOP + 2, BODY, pal.tan);
      const rem = Math.max(0, pts - prog);
      const frac = pts > 0 ? prog / pts : 0;
      token(ctx, cx, ZONE_TOP + 40, 14, 2, rem, pal.value, frac, pal.gold, pal.dim);
    });
    if (game.sailing) {
      const scx = 230 + allCols.length * 32;
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
    textLeft(ctx, "quest points remaining", 214, ZONE_TOP + 66, BODY, pal.dim);
    this.buttons.push(new Button(["progress_detail"], 214, ZONE_TOP - 2, 258, 90));
  }

  _cta(ctx, label, id, fill = pal.btn_ok, fg = pal.gold) {
    const b = new Button(id, MARGIN, CTA_Y, 480 - 2 * MARGIN, CTA_H);
    bevel(ctx, b.x, b.y, b.w, b.h, fill, false, 3);
    // The primary CTA is DISPLAY - the biggest reading size, for the one
    // control you tap every phase. It only fits because the labels were cut
    // to earn it ("Next Phase:" -> "Next:", and "End round (raise threat,
    // pass token)" -> "End Round"): the longest is now "Next: Combat (Player
    // Attacks)" at 408px against 424px of usable button.
    textCenter(ctx, label, 240, CTA_Y + 16, DISPLAY, fg);
    this.buttons.push(b);
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
    const label = allDone ? "All players confirmed"
                          : `Confirm all commits (${done.length}/${living.length})`;
    textCenter(ctx, label, 240, y + 12, BODY, allDone ? pal.dim : pal.tan);
    if (!allDone) this.buttons.push(b);
    return y + 48;
  }

  // Live "current -> projected" threat per living player, flagged red when the
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
    } else {
      drawHeader(ctx, game, this.buttons);
    }

    if (view === "setup_game") {
      const th = notePanel(ctx, MARGIN, 56, 480 - 2 * MARGIN, SETUP_TIP);
      const y = 56 + th + 18;
      textLeft(ctx, "Stage 1B quest points", MARGIN + 8, y + 16, BODY, pal.tan);
      const mn = new Button(["qp", -1], 300, y, 52, 48);
      const pl = new Button(["qp", 1], 412, y, 52, 48);
      for (const [b, s] of [[mn, "-"], [pl, "+"]]) {
        bevel(ctx, b.x, b.y, b.w, b.h, pal.btn);
        textCenter(ctx, s, b.x + 26, b.y + 12, DISPLAY, pal.tan);
        this.buttons.push(b);
      }
      textCenter(ctx, String(game.quest.points), 382, y + 12, DISPLAY, pal.gold);
      const sy = y + 50;
      textLeft(ctx, "Sailing quest", MARGIN + 8, sy + 11, BODY, pal.tan);
      icons.drawIcon(ctx, icons.WHEEL, 160, sy + 7,
                     game.sailing ? pal.gold : pal.dim);
      const sb = new Button(["sail_toggle"], 300, sy, 164, 38);
      panel(ctx, sb.x, sb.y, sb.w, sb.h, game.sailing ? pal.gold : pal.btn);
      textCenter(ctx, game.sailing ? "On" : "Off", sb.x + 82, sb.y + 12, BODY,
                 game.sailing ? pal.bg : pal.tan, false);
      this.buttons.push(sb);
      this._cta(ctx, "Begin Round 1", ["advance"]);
    } else if (view === "quest_setup") {
      this._playersZone(ctx, game);
      this._progressZone(ctx, game);
      this._drawQuestSetup(ctx, game);
    } else if (view === "resource_planning") {
      this._playersZone(ctx, game);
      this._progressZone(ctx, game);
      phaseBlock(ctx, MARGIN, CONTENT_Y, 480 - 2 * MARGIN, [
        { kind: "framework", text: "1 resource to each of your heroes, then each player draws 1 card - all at once." },
        { kind: "window", text: "In player order, play allies and attachments from hand - the only step that allows it." },
      ]);
      this._cta(ctx, `Next: ${VIEW_LABELS[game.sailing ? "quest_sailing" : "quest_commit"]}`, ["advance"]);
    } else if (view === "quest_commit") {
      this._playersZone(ctx, game);
      this._progressZone(ctx, game);
      const bh = phaseBlock(ctx, MARGIN, CONTENT_Y, 480 - 2 * MARGIN,
        [{ kind: "window", text: "In player order, exhaust characters to commit them and add their willpower." }]);
      const cy = this._drawConfirmAll(ctx, game, CONTENT_Y + bh + 8);
      this._totalsRow(ctx, game, cy, false, ["wp", "stg"]);
      this._cta(ctx, `Next: ${VIEW_LABELS.quest_staging}`, ["advance"]);
    } else if (view === "quest_sailing") {
      this._playersZone(ctx, game);
      this._progressZone(ctx, game);
      if (!game.sailing) {
        notePanel(ctx, MARGIN, CONTENT_Y + 6, 480 - 2 * MARGIN,
                  ["No Sailing keyword on this quest.", "Enable it if the stage says Sailing."]);
        const eb = new Button(["sail_toggle"], MARGIN, CONTENT_Y + 96,
                              480 - 2 * MARGIN, 52);
        bevel(ctx, eb.x, eb.y, eb.w, eb.h, pal.btn);
        icons.drawIcon(ctx, icons.WHEEL, 130, CONTENT_Y + 96 + 14, pal.gold);
        textCenter(ctx, "Enable Sailing", 254, CONTENT_Y + 96 + 16, BODY, pal.tan);
        this.buttons.push(eb);
        this._cta(ctx, `Next: ${VIEW_LABELS.quest_commit}`, ["advance"]);
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
        this._cta(ctx, `Next: ${VIEW_LABELS.quest_commit}`, ["advance"]);
      }
    } else if (view === "quest_staging") {
      this._playersZone(ctx, game);
      this._progressZone(ctx, game);
      const bh = phaseBlock(ctx, MARGIN, CONTENT_Y, 480 - 2 * MARGIN, [
        { kind: "framework", text: "1 card per player, one at a time - resolve each When Revealed before the next." },
        { kind: "window", text: "Responses to the reveal." },
      ]);
      // Gaps are 4, not 8: the framework line grew to two lines when it
      // gained the "one at a time / resolve each When Revealed" rule, and the
      // totals row has to stay clear of the CTA. Re-laid out rather than
      // shrinking the text - see the design system.
      const my = CONTENT_Y + bh + 4;
      const mh = willpowerStagingMeter(ctx, MARGIN, my, 480 - 2 * MARGIN, game.willpower, game.staging);
      this._totalsRow(ctx, game, my + mh + 4, true);
      this._cta(ctx, `Next: ${VIEW_LABELS.quest_resolution}`, ["stage_advance"]);
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
        { kind: "framework", text: "Simultaneously ready all exhausted cards; each player's threat +1. Pass the token clockwise." },
        { kind: "window", text: "Responses." },
      ]);
      this._refreshThreatPreview(ctx, game, CONTENT_Y + bh + 8);
      this._cta(ctx, "End Round", ["endround"]);
    } else {
      this._playersZone(ctx, game);
      const flavor = { combat_enemy: [icons.DEFENSE, pal.green],
                       combat_player: [icons.ATTACK, pal.tan] }[view];
      this._progressZone(ctx, game);
      const shipNotes = {
        combat_enemy: "Ships: only a ship can defend a ship-enemy. Undefended ship attacks must damage a ship you control.",
        combat_player: "Ships: your ships attack only ship-enemies - but any character may attack a ship-enemy.",
      };
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
      const i = VIEW_ORDER.indexOf(view);
      const nxt = VIEW_ORDER[(i + 1) % VIEW_ORDER.length];
      this._cta(ctx, `Next: ${VIEW_LABELS[nxt] ?? nxt}`, ["advance"]);
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
      ? "No setup instructions for this stage." : raw;
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
    textLeft(ctx, "QUEST SETUP - resolve now", tipX + 10, tipY + 6, BODY, pal.bg, false);
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

    this._cta(ctx, `Flip to Side B  ->  ${card.questPoints} qp`, ["flip_to_b"]);
  }

  _drawTravel(ctx, game) {
    const loc = game.active_location;
    const fw = loc
      ? "No travel while a location is active - explore it first."
      : "The group may travel to 1 location - the first player has the final say.";
    const bh = phaseBlock(ctx, MARGIN, CONTENT_Y, 480 - 2 * MARGIN,
      [{ kind: "framework", text: fw }, { kind: "window", text: "Responses." }]);
    const y = CONTENT_Y + bh + 10;
    if (!loc) {
      const tb = new Button(["travel_new"], MARGIN, y, 480 - 2 * MARGIN, 56);
      bevel(ctx, tb.x, tb.y, tb.w, tb.h, pal.btn);
      textCenter(ctx, "Travel to location", 240, y + 18, BODY, pal.tan);
      this.buttons.push(tb);
    } else {
      const cb = new Button(["travel_change"], MARGIN, y, 480 - 2 * MARGIN, 48);
      panel(ctx, cb.x, cb.y, cb.w, cb.h);
      textCenter(ctx, "Replace location (card effect)", 240, y + 14, BODY, pal.muted);
      this.buttons.push(cb);
    }
    this._cta(ctx, `Next: ${VIEW_LABELS.enc_optional}`, ["advance"]);
  }

  _outcomeToast(game) {
    if (game.quest_outcome === "success")
      return ["TRAIL", `Quested successfully! +${game.quest_outcome_n} progress`, "green"];
    if (game.quest_outcome === "fail")
      return ["THREAT_SM", `Quest failed. +${game.quest_outcome_n} threat to all`, "red"];
    return [null, "Quest unsuccessful - a tie, no change", "amber"];
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
      const l1 = fail ? "Quest failed. " : "Quest unsuccessful - a tie. ";
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
        textLeft(ctx, "No progress placed, no threat gained.", tx, y2, BODY, pal.muted);
      }
      this._cta(ctx, `Next: ${VIEW_LABELS.travel}`, ["advance"]);
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
      textCenter(ctx, "Location fills first, then the quest", 240, HEADER_H + 32,
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
      textLeft(ctx, "Unplaced (discarded)", 20, y + 14, BODY, pal.dim);
      textCenter(ctx, String(discard), cxGoal, y + 8, DISPLAY, pal.red);
      y += 50;
    }

    const rb = new Button(["areset"], MARGIN, y + 2, rw, 38);
    bevel(ctx, rb.x, rb.y, rb.w, rb.h, pal.btn);
    textCenter(ctx, "Reset", 240, y + 12, BODY, pal.tan);
    this.buttons.push(rb);

    this._cta(ctx, `Next: ${VIEW_LABELS.travel}`, ["apply_alloc"]);
  }

  onButton(btn, game) {
    const k = btn.id[0];
    if (k === "nav") return ["goto", btn.id[1]];
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
    if (k === "threat") {
      const [, i, delta] = btn.id;
      const before = game.players[i].threat;
      game.adjustThreat(i, delta);
      const after = game.players[i].threat;
      if (after !== before) game.logEvent(`P${i + 1} threat ${before} -> ${after}`);
      return true;
    }
    if (k === "confirm_all") {
      game.confirmAllCommits();
      game.logEvent("Confirmed all player commits");
      return true;
    }
    if (k === "wp") {
      return ["modal", new CounterModal("Questing willpower total", game.willpower,
        v => { game.willpower = v; }, "willpower")];
    }
    if (k === "enc_rem") return ["modal", new RemindersModal(game)];
    if (k === "stg") {
      return ["modal", new CounterModal("Staging area threat", game.staging,
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
      game.enterView("travel");
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
    if (k === "travel_new") return ["modal", new LocationPickModal(game, "new")];
    if (k === "travel_change") return ["modal", new LocationPickModal(game, "change")];
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
