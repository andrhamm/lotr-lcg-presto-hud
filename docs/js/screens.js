// Port of ui/screen_*.py + ui/modals.py + ui/modal_counter.py.
// Structure mirrors the Python: every screen/modal draws into ctx, rebuilds
// .buttons, and handles taps in onButton returning the same protocol values.
import { pal, Button, rect, panel, bevel, textLeft, textCenter, button,
         stepper, wrapText, truncateText, ribbon, ribbonH, notePanel, drawWeather,
         disc, arcRuns, ring, token, wxSmall, BAND_PAD, bandLineH,
         DISPLAY, BODY, LABEL , statPill,
         progRowCard, fillBar, glyph, stepperCluster, phaseBlock,
         frontFace, backFace, fitLines,
         ROW_H, ROW_H_COMPACT } from "./ui.js";
import { PROGRESS_PLACEMENT, NO_CARD_TEXT, QUEST_SETUP } from "./viewcopy.js";
import { measureText } from "./metrics.js";
import * as xtargets from "./xtargets.js";
import * as icons from "./icons.js";
import { GameState, VIEW_ORDER, VIEW_LABELS, SETUP_TIP, HEADINGS,
         DEFAULT_START_THREAT, MAX_PLAYERS, viewForStep, fmtMs,
         boardTracking } from "./gamestate.js";
import { PHASES, STEPS, step as phaseStep } from "./phases.js";
import { tipsFor } from "./quest_catalog.js";

export const HEADER_H = 40;
// A subtitle rides under the title, so the bar grows: DISPLAY title at y=8
// (24px tall), LABEL subtitle at y=36, rule at 52, 8px of air top and bottom.
export const SUBTITLE_HEADER_H = 52;
const MARGIN = 8;
const STRIP_Y = HEADER_H + 10;
const CHIP_H = 56;
const PROG_Y = STRIP_Y + CHIP_H + 8;
const CONTENT_Y = PROG_Y + CHIP_H + 8;
const CTA_Y = 410;
const CTA_H = 58;
const GUTTER = MARGIN + 40;

// Upper-right DONE bevel button: the universal "commit and dismiss" affordance
// shared by drawHeader's close case and modalHeader (same geometry, same pens).
// Widens for a longer label the same way drawHeader's round stamp does -
// "RESOLVE" does not fit DONE's 64px. Returns [x, y, w, h] so the caller
// registers a hit-box matching what was drawn; a fixed 64 would have left the
// wider button's left third dead.
//
// `ready` swaps the ink to amber: the Progress screen relabels this RESOLVE
// when something is sitting at its target, and the colour is the same
// at-target signal its value tokens already use.
function doneButton(ctx, label = "DONE", ready = false) {
  const w = Math.max(64, measureText(label, BODY) + 20);
  const x = 472 - w;
  bevel(ctx, x, 4, w, 32, pal.btn_ok);
  textCenter(ctx, label, x + Math.floor(w / 2), 12, BODY,
             ready ? pal.amber : pal.ok_fg);
  return [x, 4, w, 32];
}

export function drawHeader(ctx, game, buttons, { highlight = null, title = null,
                                                 close = false, closeLeft = false,
                                                 roundLabel = null,
                                                 titlePen = null,
                                                 roundId = null,
                                                 subtitle = null } = {}) {
  const roundLbl = roundLabel ?? `R${game.round} ${game.step}`;
  textLeft(ctx, roundLbl, 10, 12, BODY,
           (closeLeft || highlight === "log") ? pal.gold : pal.muted);
  const center = title ?? (VIEW_LABELS[game.view] ?? phaseStep(game.step).phase);
  // Always DISPLAY. The scale used to come from the title's character count,
  // so the same element changed tier as a round advanced. Every title fits at
  // DISPLAY inside the narrowest span a title has (360px), which is what
  // settled it.
  // titlePen lets a screen own its title colour. The action-window screens
  // use pal.purple, the same ink their in-view window sections use, so the
  // header says which KIND of screen this is rather than only its name.
  textCenter(ctx, center, 240, 8, DISPLAY, titlePen ?? pal.gold);
  const h = subtitle ? SUBTITLE_HEADER_H : HEADER_H;
  if (subtitle) textCenter(ctx, subtitle, 240, 36, LABEL, pal.dim);
  if (close) {
    doneButton(ctx);
  } else {
    textLeft(ctx, "Set.", 480 - 10 - measureText("Set.", BODY), 12, BODY,
             highlight === "settings" ? pal.gold : pal.muted);
  }
  rect(ctx, 0, h, 480, 1, pal.border);
  if (close) {
    buttons.push(new Button(["nav", "close"], 408, 4, 64, 32));
    // ...unless the screen put its own control in the round-stamp slot.
    // roundId used to be honoured on the default branch only, so the Game
    // Log's Story/All filter drew a label that nothing could tap. DONE sits at
    // x=408 and the slot at 0..150, so they cannot shadow each other.
    if (roundId) buttons.push(new Button(roundId, 0, 0, 150, h));
  } else if (closeLeft) {
    buttons.push(new Button(["nav", "close"], 0, 0, 150, h));
    buttons.push(new Button(["nav", "settings"], 330, 0, 150, h));
  } else {
    // roundId retargets the round-stamp slot. The label and its tap target are
    // one affordance: a screen that puts "< Menu" there cannot just append its
    // own button over the slot, because the dispatcher takes the first hit and
    // this one is already in the list.
    buttons.push(new Button(roundId ?? ["nav", "log"], 0, 0, 150, h));
    buttons.push(new Button(["nav", "phases"], 150, 0, 180, h));
    buttons.push(new Button(["nav", "settings"], 330, 0, 150, h));
  }
}

// Shared header for full-screen modals: round id upper-left, centred title,
// and a DONE button upper-right that pushes id ["close"] (each modal's
// onButton maps "close" to its own commit-and-dismiss / dismiss semantics).
// `back: [label, id]` puts a way back in the round-stamp slot instead of the
// stamp. A sub-view that drew its own back button elsewhere landed on its own
// content (the History chart is bottom-anchored), and one drawn OVER the stamp
// printed the two on top of each other. Same affordance drawHeader's roundId
// gives the pre-game screens, and for the same reason: the slot and its tap
// target are one thing.
export function modalHeader(ctx, game, title, buttons,
                            { cta = "DONE", ctaReady = false, back = null } = {}) {
  if (back) {
    const [label, bid] = back;
    textLeft(ctx, label, 10, 12, BODY, pal.tan);
    buttons.push(new Button(bid, 0, 0, 150, HEADER_H));
  } else {
    textLeft(ctx, `R${game.round} ${game.step}`, 10, 12, BODY, pal.muted);
  }
  // DISPLAY, like every screen title. This was BODY, so opening a modal from
  // Settings stepped its title DOWN a tier - the spec's "screen and modal
  // titles" is one row of the table, not two.
  textCenter(ctx, title, 240, 8, DISPLAY, pal.gold);
  rect(ctx, 0, HEADER_H, 480, 1, pal.border);
  // cta null suppresses the DONE button entirely. A sheet with nothing to
  // commit and a "< Progress" already in the left slot had two controls doing
  // one job, and both pushed the same ["close"] id.
  if (cta !== null) {
    const [x, y, w, h] = doneButton(ctx, cta, ctaReady);
    buttons.push(new Button(["close"], x, y, w, h));
  }
}

// Circular -/+ (or similar single-glyph) button: btn disc + light affordance
// ring + centred glyph. The drawn circle is small (r~10-11); callers push a
// >=24px Button separately for the actual tap target, centred on (cx, cy).
export function circBtn(ctx, cx, cy, r, glyph, pen = pal.tan) {
  disc(ctx, cx, cy, r, pal.btn);
  arcRuns(ctx, cx, cy, r, r - 2, 0, 360, pal.bevel_l);
  textCenter(ctx, glyph, cx, Math.round(cy - 8), BODY, pen);
}


// ---------------------------------------------------------------- modals
function footer(ctx, buttons, saveLabel = "Save") {
  const no = new Button(["cancel"], 24, 404, 200, 64);
  const ok = new Button(["save"], 256, 404, 200, 64);
  bevel(ctx, no.x, no.y, no.w, no.h, pal.btn_no, false, 3);
  textCenter(ctx, "Cancel", no.x + no.w / 2, no.y + 20, BODY, pal.no_fg);
  bevel(ctx, ok.x, ok.y, ok.w, ok.h, pal.btn_ok, false, 3);
  textCenter(ctx, saveLabel, ok.x + ok.w / 2, ok.y + 20, BODY, pal.ok_fg);
  buttons.push(no, ok);
}

export class CounterState {
  constructor(value, minimum = 0, maximum = 99) {
    Object.assign(this, { value, minimum, maximum, pending: false, _delta: 0 });
  }
  _clamp(v) { return Math.max(this.minimum, Math.min(this.maximum, v)); }
  get delta() { return this._delta; }
  get preview() { return this._clamp(this.value + this._delta); }
  tap(step) { this.pending = true; this._delta += step; }
  zero() { this.pending = true; this._delta = -this.value; }
  confirm() { this.value = this.preview; this._delta = 0; this.pending = false; }
  cancel() { this._delta = 0; this.pending = false; }
}

export class CounterModal {
  static STEPS = [[-5, "-5"], [-1, "-1"], [1, "+1"], [5, "+5"]];
  // icon name -> [mask, pen, ground pen or null]. "threat" and "staging" are
  // the SAME glyph in two inks: red is the player's threat, black is the
  // staging area's (design/stat-system.md's staging/enemy-threat rule). Black
  // needs a ground - pal.bg is (16,12,9) and pal.outline is (0,0,0).
  static ICONS = {
    threat: ["THREAT", "red", null],
    staging: ["THREAT", "outline", "row_stripe"],
    willpower: ["WILLPOWER", "gold", null],
  };
  static ICON_PAD = 4;

  constructor(title, value, onCommit = null, icon = null, subtext = null) {
    this.title = title;
    this.state = new CounterState(value);
    this.onCommit = onCommit;
    this.icon = icon;
    this.subtext = subtext;
    this.buttons = [];
  }

  draw(ctx, game) {
    this.buttons = [];
    rect(ctx, 0, 0, 480, 480, pal.bg);
    if (this.icon && CounterModal.ICONS[this.icon]) {
      const [maskName, penName, ground] = CounterModal.ICONS[this.icon];
      const mask = icons[maskName];
      const w = measureText(this.title, DISPLAY);
      const ix = Math.floor(240 - w / 2 - 30);
      if (ground) {
        // mask is [size, rows] - mask[0] is the size, .length is always 2.
        const p = CounterModal.ICON_PAD, s = mask[0] + 2 * p;
        rect(ctx, ix - p, 30 - p, s, s, pal[ground]);
      }
      icons.drawIcon(ctx, mask, ix, 30, pal[penName]);
      textCenter(ctx, this.title, 240 + 12, 28, DISPLAY, pal.gold);
    } else {
      textCenter(ctx, this.title, 240, 28, DISPLAY, pal.gold);
    }
    const val = this.state.preview;
    textCenter(ctx, String(val), 240, 90, 9, pal.gold);
    if (this.subtext) textCenter(ctx, this.subtext, 240, 168, BODY, pal.muted);
    if (this.state.pending) {
      const dlt = this.state.delta;
      textCenter(ctx, `${this.state.value}  ->  ${val}`, 240, 190, BODY, pal.muted);
      textCenter(ctx, `${dlt >= 0 ? "+" : ""}${dlt}`, 240, 216, DISPLAY,
                 dlt >= 0 ? pal.green : pal.red);
    }
    const bw = 104, bh = 76, gap = 8;
    const x0 = (480 - (4 * bw + 3 * gap)) / 2;
    CounterModal.STEPS.forEach(([step, label], i) => {
      const b = new Button(["step", step], x0 + i * (bw + gap), 250, bw, bh);
      bevel(ctx, b.x, b.y, b.w, b.h, pal.btn, false, 3);
      textCenter(ctx, label, b.x + bw / 2, b.y + 26, DISPLAY, pal.tan);
      this.buttons.push(b);
    });
    const no = new Button(["no"], 24, 360, 200, 92);
    const ok = new Button(["ok"], 256, 360, 200, 92);
    bevel(ctx, no.x, no.y, no.w, no.h, pal.btn_no, false, 3);
    textCenter(ctx, "X", no.x + 100, no.y + 28, 4, pal.no_fg);
    bevel(ctx, ok.x, ok.y, ok.w, ok.h, pal.btn_ok, false, 3);
    textCenter(ctx, "OK", ok.x + 100, ok.y + 28, 4, pal.ok_fg);
    this.buttons.push(no, ok);
  }

  onButton(btn) {
    const k = btn.id[0];
    if (k === "step") { this.state.tap(btn.id[1]); return null; }
    if (k === "ok") {
      this.state.confirm();
      if (this.onCommit) this.onCommit(this.state.value);
      return "close";
    }
    if (k === "no") { this.state.cancel(); return "cancel"; }
    return null;
  }
}

export class PlayerSettingsModal {
  constructor(game, index) {
    this.game = game;
    this.i = index;
    const p = game.players[index];
    this.st = p.starting_threat;
    this.tpr = p.threat_per_round;
    this.elim = p.elimination;
    this.buttons = [];
  }
  draw(ctx) {
    this.buttons = [];
    rect(ctx, 0, 0, 480, 480, pal.bg);
    textCenter(ctx, `P${this.i + 1} settings`, 240, 24, DISPLAY, pal.gold);
    icons.drawIcon(ctx, icons.THREAT, 30, 92, pal.red);
    textLeft(ctx, "Starting threat", 58, 96, BODY, pal.tan);
    stepper(ctx, this.buttons, ["st", -1], ["st", 1], 260, 82, String(this.st), 190, 56);
    icons.drawIcon(ctx, icons.THREAT, 30, 172, pal.red);
    textLeft(ctx, "Threat / round", 58, 176, BODY, pal.tan);
    stepper(ctx, this.buttons, ["tpr", -1], ["tpr", 1], 260, 162, String(this.tpr), 190, 56);
    icons.drawIcon(ctx, icons.THREAT, 30, 252, pal.red);
    textLeft(ctx, "Elimination level", 58, 256, BODY, pal.tan);
    stepper(ctx, this.buttons, ["el", -1], ["el", 1], 260, 242, String(this.elim), 190, 56);
    textLeft(ctx, "eliminated when threat reaches this (50 std)", 30, 306, BODY, pal.dim);
    footer(ctx, this.buttons);
  }
  onButton(btn) {
    const k = btn.id[0];
    if (k === "st") { this.st = Math.max(0, Math.min(60, this.st + btn.id[1])); return null; }
    if (k === "tpr") { this.tpr = Math.max(0, Math.min(9, this.tpr + btn.id[1])); return null; }
    if (k === "el") { this.elim = Math.max(20, Math.min(99, this.elim + btn.id[1])); return null; }
    if (k === "save") {
      const p = this.game.players[this.i];
      p.starting_threat = this.st;
      p.threat_per_round = this.tpr;
      p.elimination = this.elim;
      this.game.adjustThreat(this.i, 0);
      this.game.logEvent(`P${this.i + 1} settings: start ${this.st}, +${this.tpr}/round, elim ${this.elim}`);
      return "close";
    }
    return null;
  }
}

export class SideQuestsModal {
  constructor(game) { this.game = game; this.buttons = []; }
  draw(ctx) {
    this.buttons = [];
    rect(ctx, 0, 0, 480, 480, pal.bg);
    textCenter(ctx, "Side quests", 240, 22, DISPLAY, pal.gold);
    const sq = this.game.side_quests;
    if (!sq.length) textCenter(ctx, "none", 240, 90, DISPLAY, pal.dim);
    let y = 70;
    sq.forEach((s, i) => {
      panel(ctx, 24, y, 432, 56);
      textLeft(ctx, `SQ${i + 1}  ${s.progress}/${s.points}`, 36, y + 18, BODY, pal.tan);
      const mn = new Button(["pts", i, -1], 214, y + 6, 44, 44);
      const pl = new Button(["pts", i, 1], 264, y + 6, 44, 44);
      // Completing a side quest was an unlabelled green pennant icon on the
      // Progress row. That row is a card with one big stepper now, so the
      // action lives here with a name on it - and it is a DIFFERENT outcome
      // from removing one: a completed side quest goes to the victory display,
      // a removed one never happened. This twin had only the remove.
      const dn = new Button(["done", i], 320, y + 6, 60, 44);
      const rm = new Button(["rm", i], 392, y + 6, 52, 44);
      button(ctx, this.buttons, mn, "-", DISPLAY);
      button(ctx, this.buttons, pl, "+", DISPLAY);
      bevel(ctx, dn.x, dn.y, dn.w, dn.h, pal.btn, false, 3);
      textCenter(ctx, "Done", dn.x + Math.floor(dn.w / 2), dn.y + 13, BODY, pal.green);
      panel(ctx, rm.x, rm.y, rm.w, rm.h, pal.btn_no, pal.no_fg);
      textCenter(ctx, "x", rm.x + Math.floor(rm.w / 2), rm.y + 10, DISPLAY, pal.no_fg);
      this.buttons.push(mn, pl, dn, rm);
      y += 62;
    });
    const add = new Button(["add"], 24, Math.min(y, 320), 432, 52);
    bevel(ctx, add.x, add.y, add.w, add.h, pal.btn);
    textCenter(ctx, "+ Add side quest", add.x + 216, add.y + 16, BODY, pal.tan);
    this.buttons.push(add);
    const done = new Button(["save"], 24, 404, 432, 64);
    bevel(ctx, done.x, done.y, done.w, done.h, pal.btn_ok, false, 3);
    textCenter(ctx, "Done", done.x + 216, done.y + 20, BODY, pal.ok_fg);
    this.buttons.push(done);
  }
  onButton(btn) {
    const k = btn.id[0];
    // Live edits, like PlayersDetailModal: Save only closes, so each action
    // logs as it happens rather than on commit.
    if (k === "add") {
      this.game.side_quests.push({ points: 4, progress: 0 });
      this.game.logEvent(`Side quest ${this.game.side_quests.length} added (4 quest points)`);
      return null;
    }
    if (k === "pts") {
      const s = this.game.side_quests[btn.id[1]];
      const was = s.points;
      s.points = Math.max(1, Math.min(30, was + btn.id[2]));
      if (s.points !== was) {
        this.game.logEvent(`Side quest ${btn.id[1] + 1} quest points ${was} -> ${s.points}`);
      }
      return null;
    }
    if (k === "done") {
      this.game.side_quests.splice(btn.id[1], 1);
      this.game.logEvent(`Side quest ${btn.id[1] + 1} completed`);
      return null;
    }
    if (k === "rm") {
      this.game.side_quests.splice(btn.id[1], 1);
      this.game.logEvent(`Side quest ${btn.id[1] + 1} removed`);
      return null;
    }
    if (k === "save") return "close";
    return null;
  }
}

// Travel / "+ Add location": pick the location off the scenario's own cards,
// or enter its numbers by hand.
//
// mode "new"    -> travel when there is no active location
// mode "change" -> replace the current active location (old is discarded)
//
// Two steps, and which one it opens on is decided entirely by the data:
// "list" is a flat, name-sorted radio list of every location the scenario can
// put into play (locationsFor's union across its "sets to gather"), each row
// carrying the printed quest points and threat - picking one fills in BOTH
// numbers this flow used to make a player guess, since a location's threat
// leaves the staging area when you travel to it, which is exactly the
// "contribution" the manual step asks for. "manual" is the original two
// steppers, unchanged: where a scenario with no catalog data lands, and still
// reachable from the list for cards a scenario never gathers.
//
// Flat, not the sphere-first drill SideQuestPickModal uses - a scenario's
// union is 5 locations at the median and 14 at the worst. The encounter set
// is not on the row either: no scenario in the catalog gathers two same-named
// locations from different sets. No row starts selected and Travel only
// appears once one is (hidden, not disabled, like the pager arrows), because
// in "change" mode committing discards the current location's progress.
//
// `back` is where every exit returns you - "play" or "progress" (the Progress
// modal, reopened via pending_progress_detail). Opened through
// game.pending_location_pick (see main.js's loop) because the union is a
// catalog fetch neither a screen's nor a modal's onButton can await mid-tap.
// Mirror of ui/modals.py - keep the two in lockstep.
export class LocationPickModal {
  static PER_PAGE = 6;
  static ROW_H = 44;
  static ROW_STRIDE = 46;
  static LIST_Y0 = 66;
  static NAME_MAX_W = 292;    // 52 -> 344, ahead of the threat block at 352
  static THREAT_X = 352;
  static FOOTER_Y = 404;
  static FOOTER_H = 64;

  constructor(game, mode = "new", entries = null, back = "play", idx = 0) {
    this.game = game;
    this.mode = mode;
    this.entries = entries ?? [];
    this.back = back;
    // Which seat "change" replaces. Only meaningful in change mode; "new"
    // appends and ignores it.
    this.idx = idx;
    this.step = this.entries.length ? "list" : "manual";
    this.selected = null;
    this.page = 0;
    this.pts = 3;
    this.contrib = 2;   // its threat leaves the staging area while active
    // "travel" (the players paid the travel cost) vs "effect" (a card made it
    // active). Only the log and the CTA differ - see _drawManual.
    this.arrival = "travel";
    this.buttons = [];
  }

  _pages() {
    return Math.max(1, Math.ceil(this.entries.length / LocationPickModal.PER_PAGE));
  }

  draw(ctx, game) {
    this.buttons = [];
    rect(ctx, 0, 0, 480, 480, pal.bg);
    if (this.step === "list") this._drawList(ctx, game);
    else this._drawManual(ctx);
  }

  // The seat a "change" would overwrite, or null. In "new" mode nothing is
  // being replaced even when a location IS active - that is the whole point of
  // a second seat - so the caption must not claim a discard.
  //
  // This existed only in the firmware after the active_locations migration:
  // the calls were mirrored here, the method was not, so drawing this modal
  // threw. There is no host test for the web picker, which is why the browser
  // walkthrough is the step that caught it.
  _replacing() {
    if (this.mode !== "change") return null;
    return this.idx < this.game.active_locations.length
      ? this.game.active_locations[this.idx] : null;
  }

  _drawList(ctx, game) {
    const S = LocationPickModal;
    modalHeader(ctx, game, this.mode === "new" ? "Travel" : "Change Location",
                this.buttons);
    const loc = this._replacing();
    let sub, ink;
    if (this.mode === "change" && loc) {
      sub = `Replaces the current location (${loc.progress}/${loc.points} discarded).`;
      ink = pal.no_fg;
    } else {
      sub = "Pick the location - or enter it manually.";
      ink = pal.dim;
    }
    textLeft(ctx, truncateText(sub, BODY, 456), 12, 46, BODY, ink);

    const pages = this._pages();
    this.page = Math.min(this.page, pages - 1);
    const chunk = this.entries.slice(this.page * S.PER_PAGE, (this.page + 1) * S.PER_PAGE);
    let y = S.LIST_Y0;
    for (const e of chunk) {
      const on = e.id === this.selected;
      if (on) rect(ctx, 8, y, 456, S.ROW_H, pal.card_hi);
      pickRadio(ctx, 30, y + 22, on);
      textLeft(ctx, truncateText(e.name ?? "", BODY, S.NAME_MAX_W), 52, y + 13, BODY,
               on ? pal.tan : pal.muted);
      // One pill carrying both numbers instead of a loose icon, a loose number
      // and a separate "N qp": threat (black, on the light segment that makes
      // black possible) then quest points. Right-aligned so the column lines up
      // however long the name is.
      // A card that prints a literal X gets an "X", not a 0. 58 faces in the
      // catalog print X, mostly for threat, and rendering the absent number as
      // 0 made Tangled Grove ("X is the number of locations in the staging
      // area") read as the SAFEST location in the list - the one whose threat
      // scales with the board. locationsFor already hands the picker
      // threatKind/pointsKind; only the pill threw them away. The picker
      // never resolves a live value here - the location is not placed yet,
      // so it shows X rather than inventing a number, even for
      // locations_in_staging now that it is tracker-backed.
      const eThreat = e.threatKind === "x" ? "X" : (e.threat ?? 0);
      const ePoints = e.pointsKind === "x" ? "X" : (e.points ?? 0);
      const pw = statPill(ctx, 0, 0, eThreat, ePoints, { measure: true });
      statPill(ctx, 458 - pw, y + 8, eThreat, ePoints);
      rect(ctx, 8, y + S.ROW_H, 456, 1, pal.border);
      this.buttons.push(new Button(["row", e.id], 8, y, 456, S.ROW_H));
      y += S.ROW_STRIDE;
    }
    this._pager(ctx, pages);

    const manual = new Button(["manual"], 24, S.FOOTER_Y, 200, S.FOOTER_H);
    bevel(ctx, manual.x, manual.y, manual.w, manual.h, pal.btn, false, 3);
    textCenter(ctx, "Manual", manual.x + manual.w / 2, manual.y + 20, BODY, pal.tan);
    this.buttons.push(manual);
    if (this.selected !== null) {
      const go = new Button(["travel"], 256, S.FOOTER_Y, 200, S.FOOTER_H);
      bevel(ctx, go.x, go.y, go.w, go.h, pal.btn_ok, false, 3);
      textCenter(ctx, this.back !== "progress" ? "Travel" : "Add",
                 go.x + go.w / 2, go.y + 20, BODY, pal.ok_fg);
      this.buttons.push(go);
    }
  }

  _pager(ctx, pages) {
    if (pages <= 1) return;
    const up = new Button(["older"], 12, 352, 150, 46);
    const dn = new Button(["newer"], 318, 352, 150, 46);
    bevel(ctx, up.x, up.y, up.w, up.h, pal.btn);
    textCenter(ctx, "Up", up.x + 75, up.y + 14, BODY, pal.tan);
    bevel(ctx, dn.x, dn.y, dn.w, dn.h, pal.btn);
    textCenter(ctx, "Down", dn.x + 75, dn.y + 14, BODY, pal.tan);
    textCenter(ctx, `${this.page + 1}/${pages}`, 240, 366, BODY, pal.muted);
    this.buttons.push(up, dn);
  }

  _drawManual(ctx) {
    // The title follows the arrival choice rather than always claiming a
    // travel: "Manual" used to land on "Travel to new location" even when the
    // player was recording a card effect.
    let title;
    if (this.mode !== "new") title = "Change active location";
    else if (this.arrival === "travel") title = "Travel to new location";
    else title = "New active location";
    textCenter(ctx, title, 240, 16, DISPLAY, pal.gold);
    const loc = this._replacing();
    let y = 58;
    if (this.mode === "change" && loc) {
      textCenter(ctx, `current ${loc.progress}/${loc.points} will be discarded`,
                 240, y, BODY, pal.no_fg);
      y += 26;
    }
    // How it arrived. Travelling is only travelling when the players pay the
    // travel cost; a card effect can make a location active without one, and the
    // once-per-round travel limit does not apply to that. The MECHANICS are the
    // same either way - RR: "the active location acts as a buffer", so its
    // threat leaves the staging total however it got there - but the log is the
    // game's record and it should not claim a travel that never happened.
    textLeft(ctx, "HOW IT ARRIVED", 60, y, LABEL, pal.muted);
    y += 20;
    for (const [key, label] of [["travel", "Travelled here"],
                                ["effect", "A card put it into play"]]) {
      const on = this.arrival === key;
      const b = new Button(["arr", key], 60, y, 360, 40);
      bevel(ctx, b.x, b.y, b.w, b.h, on ? pal.card_hi : pal.btn, 3);
      disc(ctx, b.x + 20, b.y + 20, 9, pal.well);
      if (on) disc(ctx, b.x + 20, b.y + 20, 5, pal.gold);
      arcRuns(ctx, b.x + 20, b.y + 20, 9, 7, 0, 360, on ? pal.gold : pal.dim);
      textLeft(ctx, label, b.x + 40, b.y + 10, BODY, on ? pal.gold : pal.tan);
      this.buttons.push(b);
      y += 44;
    }
    y += 8;
    textLeft(ctx, "Quest points", 60, y + 14, BODY, pal.tan);
    stepper(ctx, this.buttons, ["pts", -1], ["pts", 1], 250, y, String(this.pts), 170, 48);
    y += 54;
    // No icon here: a threat glyph with no value beside it had nowhere legible
    // to sit (black on the ground is invisible, and a plate around an empty icon
    // reads as a bug). The words carry it.
    textLeft(ctx, "Threat contribution", 60, y + 14, BODY, pal.tan);
    stepper(ctx, this.buttons, ["ctr", -1], ["ctr", 1], 250, y, String(this.contrib), 170, 48);
    y += 54;
    textLeft(ctx, "leaves the staging area while it is active", 60, y, BODY, pal.dim);
    y += 26;
    if (this.entries.length) {
      const back = new Button(["back"], 12, y, 200, 40);
      bevel(ctx, back.x, back.y, back.w, back.h, pal.btn);
      textCenter(ctx, "< Locations", back.x + back.w / 2, back.y + 11, BODY, pal.tan);
      this.buttons.push(back);
    }
    footer(ctx, this.buttons, this.arrival === "travel" ? "Travel" : "Place");
  }

  // Every exit returns you where you came from: the Progress modal reopens
  // via the pending flag, the play screen just falls through.
  _leave(result = "close") {
    if (this.back === "progress") this.game.pending_progress_detail = true;
    return result;
  }

  // `entry` is the picker row, or null for the manual stepper. Its threat /
  // *Kind / *Formula keys ride along onto the location record so the Progress
  // screen can put a real threat back into staging, and can show the card's
  // own definition of X rather than a 0.
  _commit(points, contribution, name = null, entry = null) {
    entry = { ...(entry ?? {}), arrival: this.arrival };
    // A MANUAL entry has no catalog row, so nothing filled in `threat` - but
    // `contribution` is that number: the manual stepper's own caption is "its
    // threat leaves the staging area while it is active". Without this,
    // travelling took N out of staging and "Back to staging" put 0 back, which
    // is the asymmetry that action exists to avoid. The catalog path already
    // sets it to the same value, so this is a no-op there.
    if ((entry.threat ?? null) === null && contribution) entry.threat = contribution;
    // "new" APPENDS - that is how a second seat arrives, and the five cards
    // that allow one all phrase it as travelling with one active. "change"
    // replaces the seat it was opened on.
    if (this.mode === "new") {
      this.game.travelTo(points, contribution, name, entry);
    } else {
      this.game.changeLocation(points, contribution, name, this.idx, entry);
    }
  }

  onButton(btn) {
    const k = btn.id[0];
    if (k === "pts") { this.pts = Math.max(1, Math.min(30, this.pts + btn.id[1])); return null; }
    if (k === "ctr") { this.contrib = Math.max(0, Math.min(9, this.contrib + btn.id[1])); return null; }
    if (k === "arr") { this.arrival = btn.id[1]; return "redraw"; }
    if (k === "row") { this.selected = btn.id[1]; return "redraw"; }
    if (k === "older") { this.page = Math.max(0, this.page - 1); return "redraw"; }
    if (k === "newer") { this.page = Math.min(this._pages() - 1, this.page + 1); return "redraw"; }
    if (k === "manual") { this.step = "manual"; return "redraw"; }
    if (k === "back") { this.step = "list"; return "redraw"; }
    if (k === "travel") {
      const e = this.entries.find(x => x.id === this.selected);
      // From the Travel view this IS a travel; from Progress's "+ Add" it is
      // not, and the log should not say otherwise.
      this.arrival = this.back !== "progress" ? "travel" : "effect";
      if (e) this._commit(e.points ?? 0, e.threat ?? 0, e.name, e);
      return this._leave();
    }
    if (k === "save") { this._commit(this.pts, this.contrib); return this._leave(); }
    if (k === "close") return this._leave();
    if (k === "cancel") return this._leave("cancel");
    return null;
  }
}

// Every player's threat + willpower in one inline grid (Task 9) - the
// unified target for the play screen's Players zone and the "Questing for"
// card (replaces the QuestingProgressModal/QuestingForModal stubs there).
// Edits are live: every tap commits immediately to the game + logs (no
// save/cancel step). Tapping a token opens a small inline +-5 pad (nested
// modals aren't supported - the main loop only holds one `modal` at a time)
// that replaces the grid until OK/back, modeled on CounterModal.
export class PlayersDetailModal {
  // Row geometry - mirrors ui/modals.py's PlayersDetailModal. The old row was
  // 56px tall with 24x24 targets (the bare legal minimum for the most-tapped
  // control in the app) while leaving 252px of the screen empty. Proximity
  // does the grouping: each cluster is tight and the columns are far apart,
  // because at the old spacing the gap between clusters equalled the gap
  // inside one and the row read as six loose buttons.
  static ROW_H = 96;
  static ROW_TOP = 124;
  static STEP_DX = 52;
  static STEP_R = 20;
  static HIT = 52;
  static TOKEN_R = 22;

  constructor(game) {
    this.game = game;
    // This constructor used to call game.resyncWillpower(), on the theory that
    // opening the view that shows the per-player numbers made them the truth
    // again. It did not: it overwrote a committed TOTAL with a stale sum.
    // Opening this view mid-quest-phase - which recording a Doomed keyword or
    // Caught in a Web forces - silently zeroed 11 committed willpower, and the
    // quest then resolved against 0. A view that shows numbers must not
    // rewrite them; reconciliation belongs in setCommit, which fires when a
    // player actually edits a breakdown.
    this.buttons = [];
    this.edit = null;   // { i, stat, state: CounterState } while the inline pad is open
  }

  _openEdit(i, stat) {
    const game = this.game;
    const cur = stat === "threat" ? game.players[i].threat : game.players[i].commit;
    // CounterState's default max (99) is a cosmetic pad ceiling, not a game
    // rule - adjustThreat/setCommit have no upper bound. Widen it so opening
    // the pad on an already-high value (e.g. a spammed-past-99 threat) can
    // never silently clamp the preview down on an untouched OK tap.
    this.edit = { i, stat, state: new CounterState(cur, 0, Math.max(9999, cur)) };
  }

  _commitEdit() {
    const { i, stat, state } = this.edit;
    const before = state.value;
    state.confirm();
    const after = state.value;
    if (after !== before) {
      const game = this.game;
      if (stat === "threat") {
        game.adjustThreat(i, after - before);
        game.logEvent(`P${i + 1} threat ${before} -> ${game.players[i].threat}`);
      } else {
        game.setCommit(i, after);
        game.logEvent(`P${i + 1} committed ${after} willpower`);
      }
    }
    this.edit = null;
  }

  _editorRow(ctx, i, key, cx, cy, value, frac, ringFill) {
    const { STEP_DX, STEP_R, HIT, TOKEN_R } = PlayersDetailModal;
    circBtn(ctx, cx - STEP_DX, cy, STEP_R, "-");
    circBtn(ctx, cx + STEP_DX, cy, STEP_R, "+");
    token(ctx, cx, cy, TOKEN_R, 3, value, pal.value, frac, ringFill, pal.dim, DISPLAY);
    const h = HIT / 2;
    this.buttons.push(
      new Button([key, i, -1], cx - STEP_DX - h, cy - h, HIT, HIT),
      new Button([key, i, "edit"], cx - h, cy - h, HIT, HIT),
      new Button([key, i, 1], cx + STEP_DX - h, cy - h, HIT, HIT),
    );
  }

  draw(ctx, game) {
    this.buttons = [];
    rect(ctx, 0, 0, 480, 480, pal.bg);
    if (this.edit) { this._drawEdit(ctx); return; }
    modalHeader(ctx, game, "Players", this.buttons);
    const { ROW_H, ROW_TOP } = PlayersDetailModal;
    const threatX = 160, willX = 360, labelX = 33;
    // Column headers are the same ICONS the play screen uses - the red threat
    // helm and the gold willpower star - not ALL-CAPS LABEL text.
    // 2x scale: at 1x (20px) they read as afterthoughts against 52px controls
    // and DISPLAY numerals. The masks are 1-bit, so scaling is exact.
    icons.drawIcon(ctx, icons.THREAT, threatX - 19, 49, pal.bevel_d, 2);
    icons.drawIcon(ctx, icons.THREAT, threatX - 20, 48, pal.red, 2);
    icons.drawIcon(ctx, icons.WILLPOWER, willX - 20, 48, pal.gold, 2);
    // Hairline between the clusters - proximity alone was not enough to stop
    // the row reading as six loose buttons.
    rect(ctx, 260, 40, 1, ROW_TOP - 40 + game.players.length * ROW_H - 30, pal.border);
    game.players.forEach((p, i) => {
      const cy = ROW_TOP + i * ROW_H;
      const label = `P${i + 1}`;
      // The first-player marker is a ribbon running IN FROM THE LEFT EDGE
      // with the label inside it, so marker and name are one object.
      if (i === game.first_player) {
        ribbonH(ctx, cy - 17, 76, 34);
        textCenter(ctx, label, labelX, cy - 12, DISPLAY, pal.bg, false);
      } else {
        textCenter(ctx, label, labelX, cy - 12, DISPLAY, pal.tan);
      }
      const danger = p.threat >= p.elimination - 10;
      const tfrac = p.elimination > 0 ? p.threat / p.elimination : 0;
      this._editorRow(ctx, i, "t", threatX, cy, p.threat, tfrac, danger ? pal.red : pal.gold);
      this._editorRow(ctx, i, "w", willX, cy, p.commit, 1.0, pal.gold);
    });
  }

  _drawEdit(ctx) {
    const { i, stat, state } = this.edit;
    const isThreat = stat === "threat";
    const title = `P${i + 1} ${isThreat ? "Threat" : "Willpower"}`;
    const [maskName, penName] = isThreat ? ["THREAT", "red"] : ["WILLPOWER", "gold"];
    const w = measureText(title, DISPLAY);
    const ix = Math.floor(240 - w / 2 - 30);
    icons.drawIcon(ctx, icons[maskName], ix, 30, pal[penName]);
    textCenter(ctx, title, 240 + 12, 28, DISPLAY, pal.gold);

    const val = state.preview;
    textCenter(ctx, String(val), 240, 90, 9, pal.gold);
    if (state.pending) {
      const dlt = state.delta;
      textCenter(ctx, `${state.value}  ->  ${val}`, 240, 190, BODY, pal.muted);
      textCenter(ctx, `${dlt >= 0 ? "+" : ""}${dlt}`, 240, 216, DISPLAY,
                 dlt >= 0 ? pal.green : pal.red);
    }
    const bw = 104, bh = 76, gap = 8;
    const x0 = (480 - (4 * bw + 3 * gap)) / 2;
    [[-5, "-5"], [-1, "-1"], [1, "+1"], [5, "+5"]].forEach(([step, lbl], k) => {
      const b = new Button(["step", step], x0 + k * (bw + gap), 250, bw, bh);
      bevel(ctx, b.x, b.y, b.w, b.h, pal.btn, false, 3);
      textCenter(ctx, lbl, b.x + bw / 2, b.y + 26, DISPLAY, pal.tan);
      this.buttons.push(b);
    });
    const no = new Button(["back"], 24, 360, 200, 92);
    const ok = new Button(["ok"], 256, 360, 200, 92);
    bevel(ctx, no.x, no.y, no.w, no.h, pal.btn_no, false, 3);
    textCenter(ctx, "X", no.x + 100, no.y + 28, 4, pal.no_fg);
    bevel(ctx, ok.x, ok.y, ok.w, ok.h, pal.btn_ok, false, 3);
    textCenter(ctx, "OK", ok.x + 100, ok.y + 28, 4, pal.ok_fg);
    this.buttons.push(no, ok);
  }

  onButton(btn) {
    const k = btn.id[0];
    if (this.edit) {
      if (k === "step") { this.edit.state.tap(btn.id[1]); return null; }
      if (k === "ok") { this._commitEdit(); return null; }
      if (k === "back") { this.edit = null; return null; }
      return null;
    }
    if (k === "close") return "close";
    if (k === "t" || k === "w") {
      const [, i, action] = btn.id;
      if (action === "edit") { this._openEdit(i, k === "t" ? "threat" : "willpower"); return null; }
      if (k === "t") {
        const before = this.game.players[i].threat;
        this.game.adjustThreat(i, action);
        const after = this.game.players[i].threat;
        if (after !== before) this.game.logEvent(`P${i + 1} threat ${before} -> ${after}`);
      } else {
        const before = this.game.players[i].commit;
        const next = Math.max(0, before + action);
        if (next !== before) {
          this.game.setCommit(i, next);
          this.game.logEvent(`P${i + 1} committed ${next} willpower`);
        }
      }
      return null;
    }
    return null;
  }
}


export class CommitModal {
  static STEPS = [["zero", "->0"], [-1, "-1"], [1, "+1"], [5, "+5"]];
  constructor(game, start) {
    this.game = game;
    this.order = [];
    for (let k = 0; k < game.players.length; k++) {
      const i = (start + k) % game.players.length;
      if (!game.players[i].eliminated) this.order.push(i);
    }
    if (!this.order.length) this.order = [start];
    this.pos = 0;
    this.state = new CounterState(game.players[this.order[0]].commit);
    this.buttons = [];
  }
  get idx() { return this.order[this.pos]; }
  get final() { return this.pos === this.order.length - 1; }
  _commitCurrent() {
    const v = this.state.pending ? this.state.preview : this.state.value;
    this.state.confirm();
    const before = this.game.players[this.idx].commit;
    this.game.setCommit(this.idx, v);
    if (v !== before) this.game.logEvent(`P${this.idx + 1} committed ${v} willpower`);
  }
  draw(ctx) {
    this.buttons = [];
    rect(ctx, 0, 0, 480, 480, pal.bg);
    textCenter(ctx, `P${this.idx + 1} quests for...`, 240, 28, DISPLAY, pal.gold);
    const val = this.state.preview;
    const VSCALE = 12, ISZ = 84;
    const zoneTop = 58, zoneBottom = 244;
    const vw = measureText(String(val), VSCALE);
    const vx = Math.floor((480 - (vw + 14 + ISZ)) / 2);
    const vy = zoneTop + Math.floor((zoneBottom - zoneTop - ISZ) / 2);
    textLeft(ctx, String(val), vx, vy, VSCALE, pal.gold);
    icons.drawIcon(ctx, icons.WILLPOWER_XL, vx + vw + 14, vy, pal.gold);
    const bw = 104, bh = 76, gap = 8;
    const sx0 = (480 - (4 * bw + 3 * gap)) / 2;
    CommitModal.STEPS.forEach(([step, label], i) => {
      const b = new Button(["step", step], sx0 + i * (bw + gap), 250, bw, bh);
      bevel(ctx, b.x, b.y, b.w, b.h, pal.btn, false, 3);
      textCenter(ctx, label, b.x + bw / 2, b.y + 26, DISPLAY, pal.tan);
      this.buttons.push(b);
    });
    const done = new Button(["done"], 24, 360, 200, 92);
    const nxt = new Button(["next"], 256, 360, 200, 92);
    if (this.final) {
      bevel(ctx, done.x, done.y, done.w, done.h, pal.btn_ok, false, 3);
      textCenter(ctx, "Done", done.x + 100, done.y + 32, DISPLAY, pal.ok_fg);
      bevel(ctx, nxt.x, nxt.y, nxt.w, nxt.h, pal.card, false, 3);
      textCenter(ctx, "Next", nxt.x + 100, nxt.y + 32, DISPLAY, pal.dim);
    } else {
      bevel(ctx, done.x, done.y, done.w, done.h, pal.card, false, 3);
      textCenter(ctx, "Done", done.x + 100, done.y + 32, DISPLAY, pal.dim);
      bevel(ctx, nxt.x, nxt.y, nxt.w, nxt.h, pal.btn, false, 3);
      textCenter(ctx, "Next", nxt.x + 100, nxt.y + 32, DISPLAY, pal.gold);
    }
    this.buttons.push(done, nxt);
  }
  onButton(btn) {
    const k = btn.id[0];
    if (k === "step") {
      if (btn.id[1] === "zero") this.state.zero();
      else this.state.tap(btn.id[1]);
      return null;
    }
    if (k === "next") {
      if (this.final) return null;
      this._commitCurrent();
      this.pos += 1;
      this.state = new CounterState(this.game.players[this.idx].commit);
      return null;
    }
    if (k === "done") { this._commitCurrent(); return "close"; }
    return null;
  }
}

export class EliminationModal {
  constructor(game, index) {
    this.game = game;
    this.i = index;
    this.newLevel = game.players[index].elimination;
    this.buttons = [];
  }
  draw(ctx) {
    this.buttons = [];
    rect(ctx, 0, 0, 480, 480, pal.bg);
    const p = this.game.players[this.i];
    const title = `P${this.i + 1} eliminated?`;
    const tw = measureText(title, DISPLAY);
    const start = Math.floor((480 - (20 + 8 + tw)) / 2);
    icons.drawIcon(ctx, icons.THREAT, start, 22, pal.red);
    textLeft(ctx, title, start + 28, 20, DISPLAY, pal.red);
    textCenter(ctx, `threat ${p.threat} reached elimination level ${p.elimination}`,
               240, 62, BODY, pal.tan);
    const eb = new Button(["elim"], 24, 110, 432, 64);
    bevel(ctx, eb.x, eb.y, eb.w, eb.h, pal.btn_no, false, 3);
    textCenter(ctx, "Yes - eliminated", 240, eb.y + 22, BODY, pal.no_fg);
    this.buttons.push(eb);
    const ab = new Button(["avert"], 24, 190, 432, 64);
    bevel(ctx, ab.x, ab.y, ab.w, ab.h, pal.btn, false, 3);
    textCenter(ctx, "Averted by card effect", 240, ab.y + 12, BODY, pal.tan);
    textCenter(ctx, `threat -> ${Math.max(0, p.elimination - 5)}, stays in`,
               240, ab.y + 38, BODY, pal.dim);
    this.buttons.push(ab);
    textLeft(ctx, "Elimination level changed?", 24, 286, BODY, pal.tan);
    stepper(ctx, this.buttons, ["lvl", -1], ["lvl", 1], 24, 316,
            String(this.newLevel), 300, 56);
    const sb = new Button(["setlvl"], 340, 316, 116, 56);
    bevel(ctx, sb.x, sb.y, sb.w, sb.h, pal.btn_ok, false, 3);
    textCenter(ctx, "Set", sb.x + 58, sb.y + 18, BODY, pal.ok_fg);
    this.buttons.push(sb);
  }
  onButton(btn) {
    const k = btn.id[0];
    const g = this.game;
    const p = g.players[this.i];
    if (k === "elim") {
      g.pending_elim = null;
      g.logEvent(`P${this.i + 1} eliminated (threat ${p.threat} >= level ${p.elimination})`);
      return "close";
    }
    if (k === "avert") { g.avertElimination(this.i); return "close"; }
    if (k === "lvl") {
      this.newLevel = Math.max(20, Math.min(99, this.newLevel + btn.id[1]));
      return null;
    }
    if (k === "setlvl") {
      p.elimination = this.newLevel;
      p.eliminated = p.threat >= p.elimination;
      g.logEvent(`P${this.i + 1} elimination level set to ${this.newLevel}`);
      if (p.eliminated) {
        g.pending_elim = null;
        g.logEvent(`P${this.i + 1} eliminated (threat ${p.threat} >= level ${p.elimination})`);
      } else {
        g.pending_elim = null;
      }
      return "close";
    }
    return null;
  }
}

export class QuestingProgressModal {
  // All questing progress in one place: the active location(s), the main
  // quest, and each side quest, each as one row carrying a "progress / target"
  // stepper over a fill bar and a ">" into its own detail sheet. Port of
  // ui/modals.py's QuestingProgressModal - keep the two in lockstep.
  //
  // A row is a card with a coloured accent down its left edge (green =
  // location, gold = quest/side quest), the entity's glyph and name, its
  // printed quest points as dense metadata, and ONE big stepper cluster. The
  // old row was 38px with two small circular editors and four 24px icon
  // buttons crowded to the right - tiny tap targets, and nothing like the
  // Players screen. The target stepper is gone from the row entirely: editing
  // a target is a detail-sheet job, which is also what labels the actions the
  // icons never named.
  static ROW_H = ROW_H;
  static ROW_H_COMPACT = ROW_H_COMPACT;
  static ROW_GAP = 5;

  constructor(game) {
    this.game = game;
    this.buttons = [];
    this.addPrompt = false;   // "+ Add" asks Location or Side quest
    this.history = false;     // the by-round chart + heading sub-view
    this.page = 0;
    this._snap = this._snapshot();
  }

  _snapshot() {
    const g = this.game;
    return {
      q: { p: g.quest.progress, t: g.quest.points },
      locs: g.active_locations.map(l => ({ p: l.progress, t: l.points })),
      sqLen: g.side_quests.length,
      sq: g.side_quests.map(s => ({ p: s.progress, t: s.points })),
    };
  }

  _items() {
    const g = this.game;
    const items = [{ kind: "q", name: `Quest ${g.questLabel()}`, removable: false,
                     advanceable: g.stages.length > 0 }];
    // Prefer the catalog name (LocationPickModal's list step) when present;
    // manual entries and old saves have no "name" key at all, so this stays
    // "Location" for them - same rule as the side quests below.
    g.active_locations.forEach((loc, i) =>
      items.push({ kind: "l", idx: i, removable: true,
                   name: loc.name || (i === 0 ? "Location" : `Location ${i + 1}`) }));
    g.side_quests.forEach((s, i) =>
      items.push({ kind: "s", idx: i, name: s.name || `Side Quest ${i + 1}`,
                   removable: true }));
    return items;
  }

  _section(ctx, y, label, count = null) {
    textLeft(ctx, label, MARGIN + 2, y, LABEL, pal.muted);
    if (count) {
      const w = measureText(label, LABEL);
      textLeft(ctx, count, MARGIN + 10 + w, y, LABEL, pal.dim);
    }
    return y + 14;
  }

  _row(ctx, it, y, compact = false) {
    const g = this.game;
    const kind = it.kind;
    const cond = kind === "q" && g.quest.mode === "condition";
    // A condition row carries two lines of the card's own sentence AND a
    // count-only stepper, so it needs more than a bar row does.
    const h = cond ? 96
      : (compact ? QuestingProgressModal.ROW_H_COMPACT : QuestingProgressModal.ROW_H);
    let prog, pts, pfx, idx, accent, meta = null;
    if (kind === "q") {
      prog = g.quest.progress; pts = g.quest.points; pfx = "q"; idx = null;
      accent = pal.gold; meta = `STAGE ${g.questLabel()}`;
      // A computed target is NOT a third row treatment. "X is 1 plus the
      // number of players" resolves to a number the moment the count is known,
      // and from there the row is an ordinary pointed stage. What differs is
      // only WHERE the number comes from, which is the sheet's job. Unresolved
      // (a count nobody has supplied yet) leaves the printed 0.
      if (g.quest.mode === "formula") {
        const resolved = this._questTarget();
        if (resolved !== null) pts = resolved;
        meta = resolved !== null ? `X = ${pts}` : "X";
      }
    } else if (kind === "l") {
      idx = it.idx ?? 0;
      const loc = g.active_locations[idx];
      prog = loc.progress; pts = loc.points; pfx = "l";
      accent = pal.green;
      meta = pts ? `${pts} QP` : null;
    } else {
      const sq = g.side_quests[it.idx];
      prog = sq.progress; pts = sq.points; pfx = "s"; idx = it.idx;
      accent = pal.gold;
      meta = pts ? `${pts} QP` : null;
    }
    const atTarget = !!pts && prog >= pts;
    progRowCard(ctx, MARGIN, y, 480 - 2 * MARGIN, h, accent);

    // A stage that advances on a condition has no bar to fill and no target to
    // count toward, so the card's own sentence takes the space instead.
    if (cond) {
      glyph(ctx, kind, MARGIN + 14, y + 5, accent);
      textLeft(ctx, truncateText(it.name, BODY, 236), MARGIN + 40, y + 8, BODY, pal.tan);
      const mw = measureText("NO QUEST POINTS", LABEL);
      textLeft(ctx, "NO QUEST POINTS", 480 - MARGIN - 28 - mw, y + 10, LABEL, pal.dim);
      textLeft(ctx, ">", 480 - MARGIN - 18, y + 6, BODY, pal.gold);
      // No bar and NO STEPPERS: the card's own sentence takes the whole width
      // the controls would have used. A stepper here invited the player to
      // count toward a target the card never printed, which is the thing this
      // whole mode exists to stop.
      let ty = y + 36;
      const bodyW = 480 - 2 * MARGIN - 28;
      const lines = wrapText(g.quest.advance
        || "This stage advances on a condition, not on progress.", BODY, bodyW);
      for (const ln of lines.slice(0, 2)) {
        textLeft(ctx, ln, MARGIN + 14, ty, BODY, pal.dim);
        ty += 22;
      }
      let more = lines.length > 2;
      // 11 stages state BOTH how they are won and how they are lost - Return
      // to Rhosgobel is won if Wilyador is healed and lost otherwise. Showing
      // only the win is showing half the rule.
      if (g.quest.lose && !more) {
        const ll = wrapText(g.quest.lose, BODY, bodyW);
        textLeft(ctx, ll[0], MARGIN + 14, ty, BODY, pal.no_fg);
        ty += 22;
        more = ll.length > 1;
      }
      if (more) {
        // The affordance the Quest Cards modal already uses - the sheet behind
        // the chevron carries the full text.
        textLeft(ctx, "[...] more", MARGIN + 14, ty, BODY, pal.gold);
      }
      this.buttons.push(new Button(["detail", kind, idx], MARGIN, y,
                                   480 - 2 * MARGIN, h));
      return y + h + QuestingProgressModal.ROW_GAP;
    }

    if (compact) {
      const cy = y + Math.floor(h / 2) - 3;
      // Compact rows pack two locations plus the quest onto one page, so the
      // disc shrinks - but the TAP target does not go below the row it sits in.
      const left = stepperCluster(ctx, this.buttons, 480 - MARGIN - 30, cy,
                                  prog, pts, atTarget,
                                  [pfx + "P-", idx], [pfx + "P+", idx],
                                  18, QuestingProgressModal.ROW_H_COMPACT);
      glyph(ctx, kind, MARGIN + 14, cy - 10, accent);
      textLeft(ctx, truncateText(it.name, BODY, left - (MARGIN + 40) - 10),
               MARGIN + 40, cy - 8, BODY, pal.tan);
      fillBar(ctx, MARGIN + 14, y + h - 9, left - (MARGIN + 28), 4,
              prog, pts, accent, atTarget);
      this.buttons.push(new Button(["detail", kind, idx], MARGIN, y,
                                   left - MARGIN - 10, h));
      return y + h + QuestingProgressModal.ROW_GAP;
    }

    glyph(ctx, kind, MARGIN + 14, y + 5, accent);
    textLeft(ctx, truncateText(it.name, BODY, 236), MARGIN + 40, y + 8, BODY, pal.tan);
    if (meta) {
      const mw = measureText(meta, LABEL);
      textLeft(ctx, meta, 480 - MARGIN - 28 - mw, y + 10, LABEL, pal.dim);
    }
    textLeft(ctx, ">", 480 - MARGIN - 18, y + 6, BODY, pal.gold);
    const cy = y + 48;
    const left = stepperCluster(ctx, this.buttons, 480 - MARGIN - 36, cy,
                                prog, pts, atTarget,
                                [pfx + "P-", idx], [pfx + "P+", idx]);
    // Side A carries the story and the setup; the quest points are on side B.
    // A bare 0 / 0 reads as a stage you have failed to fill rather than one you
    // have not turned over yet - and 1A->1B happens before round 1 (rulebook
    // setup step 7). The line takes the bar's row, since a bar with no target
    // has nothing to draw. Said short rather than truncated: the full sentence
    // is 380px against the 248 this row leaves, and the type scale is not
    // negotiable. This is 218.
    const sideA = kind === "q" && g.quest.side === "A" && !pts;
    if (sideA) {
      textLeft(ctx, "Flip to side B to start.", MARGIN + 14, cy - 9, BODY, pal.dim);
    } else {
      fillBar(ctx, MARGIN + 14, cy - 3, left - (MARGIN + 28), 6,
              prog, pts, accent, atTarget);
    }
    // The whole title band opens the detail sheet - the ">" is the hint, not
    // the hit-box. Pushed last so the stepper hit-boxes win any overlap.
    this.buttons.push(new Button(["detail", kind, idx], MARGIN, y,
                                 480 - 2 * MARGIN, 40));
    return y + h + QuestingProgressModal.ROW_GAP;
  }

  _bottomBar(ctx, page, pages) {
    const y = 420;
    for (const [label, x, w, bid] of [["History", 12, 118, ["history"]],
                                      ["+ Add", 138, 96, ["add"]]]) {
      const b = new Button(bid, x, y, w, 46);
      bevel(ctx, b.x, b.y, b.w, b.h, pal.btn);
      textCenter(ctx, label, x + Math.floor(w / 2), y + 14, BODY, pal.tan);
      this.buttons.push(b);
    }
    if (pages > 1) {
      for (const [label, x, bid] of [["Up", 288, ["older"]], ["Down", 382, ["newer"]]]) {
        const b = new Button(bid, x, y, 86, 46);
        bevel(ctx, b.x, b.y, b.w, b.h, pal.btn);
        textCenter(ctx, label, x + 43, y + 14, BODY, pal.tan);
        this.buttons.push(b);
      }
      textCenter(ctx, `${page + 1}/${pages}`, 262, y + 14, BODY, pal.muted);
    }
  }

  draw(ctx, game) {
    this.buttons = [];
    rect(ctx, 0, 0, 480, 480, pal.bg);
    if (this.addPrompt) { this._drawAddPrompt(ctx); return; }
    if (this.history) { this._drawHistory(ctx); return; }
    // DONE becomes RESOLVE when something is sitting at its target. Closing
    // ALREADY runs the resolve flow (main.js checks needsResolution() on
    // close), so a separate "Resolve now" button was a second control doing the
    // first one's job - the label just has to admit what DONE will do.
    const ready = typeof game.needsResolution === "function" && game.needsResolution();
    modalHeader(ctx, game, "Progress", this.buttons,
                { cta: ready ? "RESOLVE" : "DONE", ctaReady: ready });
    // {kind, text} objects, not Python's tuples - this twin's phaseBlock
    // destructures. Passing the tuple shape silently measured an empty band
    // (36px instead of 122), which made this screen fit three rows where the
    // firmware needed compact ones.
    let y = 46 + phaseBlock(ctx, MARGIN, 46, 480 - 2 * MARGIN,
                            [{ kind: "framework", text: PROGRESS_PLACEMENT }]) + 8;

    // Location BEFORE quest: progress fills the location first, and the band
    // directly above says so. Reading order should match the rule.
    const order = { l: 0, q: 1, s: 2 };
    const rows = this._items().sort((a, b) => order[a.kind] - order[b.kind]);
    const avail = 420 - y - 8;

    const fits = (c) => {
      const rh = (c ? QuestingProgressModal.ROW_H_COMPACT
                    : QuestingProgressModal.ROW_H) + QuestingProgressModal.ROW_GAP;
      // Sections are emitted once per GROUP, not per row, so the worst case is
      // one header per distinct kind on the page.
      const per = Math.max(1, Math.floor((avail - 3 * 14) / rh));
      return [per, Math.max(1, Math.ceil(rows.length / per))];
    };

    // Prefer shrinking the rows over paging them: a lone side quest stranded on
    // page 2 is worse than three compact rows on page 1.
    let [perPage, pages] = fits(false);
    let compact = false;
    if (pages > 1) {
      const [perC, pagesC] = fits(true);
      if (pagesC < pages) { compact = true; perPage = perC; pages = pagesC; }
    }

    // The break follows the CHAIN, not the row count. Progress fills the
    // locations and then the quest, and the band at the top of the screen
    // describes exactly that motion - so those rows are one thing and are not
    // split across a page turn. Side quests take what is left, and page 2
    // onward if they have to.
    const chain = rows.filter(it => it.kind === "l" || it.kind === "q");
    const tail = rows.filter(it => it.kind === "s");
    let pagesList;
    if (chain.length && chain.length <= perPage) {
      pagesList = [chain.concat(tail.slice(0, perPage - chain.length))];
      let rest = tail.slice(perPage - chain.length);
      while (rest.length) { pagesList.push(rest.slice(0, perPage)); rest = rest.slice(perPage); }
    } else {
      // The chain alone overflows the page - nothing to protect, so fall back
      // to plain slicing rather than inventing a worse rule.
      pagesList = [];
      for (let i = 0; i < rows.length; i += perPage) pagesList.push(rows.slice(i, i + perPage));
      if (!pagesList.length) pagesList = [[]];
    }
    pages = pagesList.length;
    this.page = Math.min(this.page, pages - 1);
    const shown = pagesList[this.page];

    const nLoc = rows.filter(r => r.kind === "l").length;
    const SECTION = { l: nLoc > 1 ? "ACTIVE LOCATIONS" : "ACTIVE LOCATION",
                      q: "CURRENT QUEST", s: "SIDE QUESTS" };
    let lastKind = null;
    for (const it of shown) {
      if (it.kind !== lastKind) {
        // The count rides beside the header when a section holds more than one,
        // so a paged-off row is still accounted for.
        const n = rows.filter(r => r.kind === it.kind).length;
        y = this._section(ctx, y, SECTION[it.kind], n > 1 ? String(n) : null);
        lastKind = it.kind;
      }
      y = this._row(ctx, it, y, compact);
    }
    if (!game.active_locations.length && this.page === 0) {
      textLeft(ctx, "No active location.", MARGIN + 4, y, BODY, pal.dim);
      y += 24;
    }
    this._bottomBar(ctx, this.page, pages);
  }

  // "+ Location" and "+ Side quest" were two permanent buttons mid-screen for
  // occasional actions. Merged into one "+ Add" that asks which - the same
  // in-modal prompt pattern the removal prompt used to use, because a modal
  // cannot open another.
  _drawAddPrompt(ctx) {
    modalHeader(ctx, this.game, "Add", this.buttons);
    let y = 90;
    for (const [label, bid, note] of [
        ["Location", ["add_loc"], "the one you just travelled to"],
        ["Side quest", ["add_sq"], "a player side quest in play"]]) {
      const b = new Button(bid, 40, y, 400, 62);
      bevel(ctx, b.x, b.y, b.w, b.h, pal.btn, false, 3);
      textLeft(ctx, label, b.x + 20, b.y + 8, BODY, pal.tan);
      textLeft(ctx, note, b.x + 20, b.y + 34, BODY, pal.dim);
      this.buttons.push(b);
      y += 74;
    }
    const c = new Button(["add_cancel"], 40, y + 10, 400, 48);
    panel(ctx, c.x, c.y, c.w, c.h, pal.btn_no, pal.no_fg);
    textCenter(ctx, "Cancel", 240, c.y + 14, BODY, pal.no_fg);
    this.buttons.push(c);
  }

  // The by-round chart and, for a sailing game, the heading radios. Both used
  // to sit permanently below the rows, so an empty chart held 130px hostage
  // every round before the first resolve. They are one tap away now instead.
  _drawHistory(ctx) {
    // The way back takes the round-stamp slot: a button at the bottom landed on
    // the chart's last row and its caption, and one drawn over the stamp
    // printed the two on top of each other.
    modalHeader(ctx, this.game, "History", this.buttons,
                { back: ["< Progress", ["hist_back"]] });
    if (this.game.sailing) {
      const headingY = 60;
      textLeft(ctx, "Heading", 12, headingY, BODY, pal.tan);
      const cy = headingY + 4;
      for (let i = 0; i < 4; i++) {
        const cx = 150 + i * 40;
        disc(ctx, cx, cy, 14, pal.well);
        const active = i === this.game.heading;
        if (active) ring(ctx, cx, cy, 14, 2, 1.0, pal.gold, pal.gold);
        wxSmall(ctx, i, cx, cy, 7, active ? null : pal.dim);
        this.buttons.push(new Button(["hd_set", i], cx - 14, cy - 14, 28, 28));
      }
    }
    // Nothing sits above the chart here, so it starts under the heading row
    // instead of holding its play-screen anchor and leaving 250px of empty
    // screen between the two.
    this._drawChart(ctx, this.game.sailing ? 116 : 76);
  }

  // `cy0` is the block's top. It defaults to the play-screen anchor it has
  // always had; the History sub-view passes its own, since nothing sits above
  // it there.
  _drawChart(ctx, cy0 = 344) {
    rect(ctx, 8, cy0 - 12, 464, 1, pal.border);
    textLeft(ctx, "THIS GAME - BY ROUND", 12, cy0 - 9, LABEL, pal.muted);
    const cols = this.game.quest_history.slice(-8);
    if (!cols.length) {
      textCenter(ctx, "No rounds resolved yet", 240, cy0 + 14, BODY, pal.dim);
      return;
    }
    const x0 = 52;
    const stride = Math.floor((472 - x0) / cols.length);
    cols.forEach((r, i) =>
      textCenter(ctx, `R${r.round}`, x0 + i * stride + Math.floor(stride / 2),
                 cy0, LABEL, pal.dim));
    const hdgPen = [pal.gold, pal.amber, pal.amber, pal.red];
    const resultCell = (r) => {
      const signed = r.outcome === "fail" ? -r.n : r.n;
      return [signed > 0 ? `+${signed}` : String(signed),
              signed > 0 ? pal.green : pal.red];
    };
    const rows = [
      [icons.WILLPOWER, pal.gold, false, r => [String(r.willpower), pal.gold]],
      [icons.THREAT, pal.outline, true, r => [String(r.staging), pal.outline]],
      [icons.TRAIL, pal.green, false, resultCell],
    ];
    if (this.game.sailing) {
      rows.push([icons.WHEEL, pal.gold, false, r => [String(r.heading), hdgPen[r.heading]]]);
    }
    // A gold vertical wherever the stage changed between two columns. It is the
    // one thing that explains a sudden jump in the staging line, and without it
    // the chart shows the rounds but not the shape of the game. Entries written
    // before `stage` existed have none and rule nothing.
    let ry = cy0 + 14;
    const ruleH = 26 * rows.length;
    for (let i = 1; i < cols.length; i++) {
      const a = cols[i - 1].stage, b = cols[i].stage;
      if (a === undefined || b === undefined || a === null || b === null || a === b) continue;
      rect(ctx, x0 + i * stride - 1, ry - 6, 1, ruleH, pal.gold);
    }
    for (const [mask, ipen, stripe, cell] of rows) {
      if (stripe) rect(ctx, 8, ry - 4, 464, 24, pal.row_stripe);
      icons.drawIcon(ctx, mask, 12, ry - 2, ipen);
      cols.forEach((r, i) => {
        const [s, pen] = cell(r);
        textCenter(ctx, s, x0 + i * stride + Math.floor(stride / 2), ry, BODY, pen);
      });
      ry += 26;
    }
    // The key for the icon column above it - chrome for a dense readout,
    // scanned rather than read, so it stays LABEL and goes ALL CAPS to match
    // "THIS GAME - BY ROUND" at the top of the same block.
    const caption = "WILLPOWER / STAGING / RESULT" + (this.game.sailing ? " / HEADING" : "");
    textCenter(ctx, caption, 240, ry + 4, LABEL, pal.dim);
  }

  // Step a value, clamped. `cap` is the row's own target: progress cannot
  // exceed the quest points it is filling.
  //
  // RR p.22: excess progress beyond a stage's quest points is DISCARDED on
  // advance, not carried, and a location explores the moment it is full - so a
  // bar reading 12/3 describes a state the game cannot be in. Location overflow
  // does flow on to the quest card (p.15), but that is the guided resolution
  // flow's job, not something the stepper should let you type in.
  //
  // cap null/0 leaves the 0..99 behaviour, which is what a target-less row
  // wants: a condition stage has no quest points to clamp against.
  // The stage's real target, resolving a formula X. null when the formula
  // needs a count nobody has supplied yet.
  //
  // The ROW and the STEPPER have to agree on this: the row drew the resolved 4
  // while the handler clamped against the printed 0, so the bar read 4/4 at
  // target and a tap still pushed it to 5.
  _questTarget() {
    const g = this.game;
    if (g.quest.mode !== "formula") return g.quest.points;
    return xtargets.resolve(g.quest.x, { count: g.quest.xCount ?? null, ...g.xContext() });
  }

  _clampAdj(cur, d, cap = null) {
    const hi = !cap || cap <= 0 ? 99 : cap;
    return Math.max(0, Math.min(hi, cur + d));
  }

  onButton(btn) {
    const g = this.game;
    const [k, a] = btn.id;
    const up = k.endsWith("+");
    if (k === "qP-" || k === "qP+") {
      // A condition stage has no target to clamp against (mode set by flipToB).
      const cap = g.quest.mode === "condition" ? null : this._questTarget();
      g.quest.progress = this._clampAdj(g.quest.progress, up ? 1 : -1, cap);
      return null;
    }
    if (k === "lP-" || k === "lP+") {
      // The location can have explored itself out from under this button (the
      // auto-explore below clears it), and a stale tap then threw on null.
      const i = a ?? 0;
      if (i >= g.active_locations.length) return null;
      const loc = g.active_locations[i];
      loc.progress = this._clampAdj(loc.progress, up ? 1 : -1, loc.points);
      if (!g.stages.length) {
        // Catalog games defer this to the guided resolution flow (close-time
        // needsResolution() check + ResolutionModal's "location" step) so
        // overflow excess gets credited to the quest card (rulebook p.15) via
        // resolveLocationOverflow() instead of silently discarded. Custom games
        // have no guided flow to defer to, so they keep the immediate
        // auto-explore they have always had.
        g.exploreLocationIfDone();
      }
      return null;
    }
    if (k === "sP-" || k === "sP+") {
      const s = g.side_quests[a];
      s.progress = this._clampAdj(s.progress, up ? 1 : -1, s.points);
      return null;
    }
    if (k === "hd_set") {
      if (a !== g.heading) g.shiftHeading(a - g.heading, "progress view");
      return null;
    }
    if (k === "detail") {
      // The row's ">" opens that entity's own sheet, which is where the target
      // lives now and where the icon-button actions finally get labels. One
      // modal at a time, so close-and-flag like "quest_card".
      const kind = btn.id[1];
      if (kind === "q") {
        // The EDITOR, not the card: this is where quest points and the advance
        // sentence live, and it links on to the card itself.
        g.pending_quest_config = true;
      } else if (kind === "l") {
        g.pending_location_detail = true;
      } else {
        // SideQuestsModal, where Done and Remove live - NOT the add picker.
        // This raised pending_side_quest_pick, so a row's own chevron opened
        // "choose a side quest to add" and there was no way to reach the row's
        // own actions at all.
        g.pending_side_quest_detail = true;
      }
      this._logChanges();
      return "close";
    }
    if (k === "add") {
      // "+ Location" and "+ Side quest" were two permanent buttons for
      // occasional actions; one "+ Add" asks which.
      this.addPrompt = true;
      return "redraw";
    }
    if (k === "add_loc") {
      this.addPrompt = false;
      g.pending_location_pick = { mode: "new", back: "progress" };
      this._logChanges();
      return "close";
    }
    if (k === "add_sq") {
      this.addPrompt = false;
      g.pending_side_quest_pick = true;
      this._logChanges();
      return "close";
    }
    if (k === "add_cancel") { this.addPrompt = false; return "redraw"; }
    if (k === "history") { this.history = true; return "redraw"; }
    if (k === "hist_back") { this.history = false; return "redraw"; }
    if (k === "older" || k === "newer") {
      this.page = Math.max(0, this.page + (k === "older" ? -1 : 1));
      return "redraw";
    }
    if (k === "close") {
      this._logChanges();
      // Any overflow (location, quest or side quest) defers to
      // ResolutionModal: every one of its steps has a real close/dismiss
      // escape hatch, so handing it a state the player did not mean to reach
      // is always recoverable.
      if (g.stages.length) {
        if (g.needsResolution()) g.pending_resolution = "auto";
      } else if (g.quest.points > 0 && g.quest.progress >= g.quest.points) {
        g.pending_resolution = "auto";
      }
      return "close";
    }
    return null;
  }

  _logChanges() {
    const s = this._snap, g = this.game;
    if (g.quest.progress !== s.q.p || g.quest.points !== s.q.t) {
      g.logEvent(`Quest ${g.questLabel()} set ${g.quest.progress}/${g.quest.points} (progress view)`);
    }
    // Only seats that were there when the modal opened AND are still there: one
    // that left is already logged by whatever removed it, and one that arrived
    // was logged by the travel.
    s.locs.forEach((snap, i) => {
      if (i >= g.active_locations.length) return;
      const l = g.active_locations[i];
      if (l.progress === snap.p && l.points === snap.t) return;
      const label = s.locs.length === 1 ? "Active location" : `Active location ${i + 1}`;
      g.logEvent(`${label} set ${l.progress}/${l.points} (progress view)`);
    });
    if (g.side_quests.length === s.sqLen) {
      g.side_quests.forEach((sq, i) => {
        if (sq.progress !== s.sq[i].p || sq.points !== s.sq[i].t) {
          g.logEvent(`Side quest ${i + 1} set ${sq.progress}/${sq.points} (progress view)`);
        }
      });
    }
  }
}
export class SailingModal {
  // Log the result of a Sailing test: +v = wheels found (shift on-course),
  // -v = steps off-course (winds/card effects). Heading index 0 = on-course.
  constructor(game) { this.game = game; this.v = 0; this.buttons = []; }
  _result() { return Math.max(0, Math.min(3, this.game.heading - this.v)); }
  draw(ctx) {
    this.buttons = [];
    rect(ctx, 0, 0, 480, 480, pal.bg);
    modalHeader(ctx, this.game, "Sailing test", this.buttons);

    const heading = (h, cy, scale) => {
      const [term, , facing] = HEADINGS[h];
      const pen = h === 0 ? pal.gold : h === 3 ? pal.red : pal.amber;
      const label = `${facing} - ${term}`;
      const lw = measureText(label, scale);
      const total = 24 + 8 + lw;
      const x0 = Math.floor(240 - total / 2);
      drawWeather(ctx, h, x0 + 12, cy + 10, 12);
      textLeft(ctx, label, x0 + 32, cy + (scale === BODY ? 2 : 0), scale, pen);
    };

    textCenter(ctx, "CURRENT HEADING", 240, 54, LABEL, pal.dim);
    heading(this.game.heading, 74, 2);

    // wheel stepper
    const big = String(Math.abs(this.v));
    const bw = measureText(big, 6);
    const bx = Math.floor(240 - (this.v > 0 ? (bw + 14 + 48) : bw) / 2);
    const bpen = this.v < 0 ? pal.red : this.v > 0 ? pal.gold : pal.muted;
    textLeft(ctx, big, bx, 128, 6, bpen);
    // wheel as a currency symbol, its 48px height matching the scale-6 digit
    if (this.v > 0) icons.drawIcon(ctx, icons.WHEEL, bx + bw + 14, 128, pal.gold, 2);
    let sub, spen;
    if (this.v > 0) { sub = `${this.v} wheel${this.v > 1 ? "s" : ""} found - shift on-course`; spen = pal.green; }
    else if (this.v < 0) { sub = `${-this.v} step${this.v < -1 ? "s" : ""} off-course (card effect)`; spen = pal.red; }
    else { sub = "no wheels found - heading stays"; spen = pal.dim; }
    textCenter(ctx, sub, 240, 200, BODY, spen);

    const mn = new Button(["d", -1], 34, 128, 64, 60);
    const pl = new Button(["d", 1], 480 - 34 - 64, 128, 64, 60);
    bevel(ctx, mn.x, mn.y, mn.w, mn.h, pal.btn);
    textCenter(ctx, "-", mn.x + 32, mn.y + 14, 4, pal.tan);
    bevel(ctx, pl.x, pl.y, pl.w, pl.h, pal.btn);
    textCenter(ctx, "+", pl.x + 32, pl.y + 14, 4, pal.tan);
    this.buttons.push(mn, pl);

    textCenter(ctx, "RESULT", 240, 240, LABEL, pal.dim);
    heading(this._result(), 262, 2);

    const no = new Button(["cancel"], 24, 404, 200, 64);
    const ok = new Button(["apply"], 256, 404, 200, 64);
    bevel(ctx, no.x, no.y, no.w, no.h, pal.btn_no, false, 3);
    textCenter(ctx, "Cancel", no.x + 100, no.y + 20, BODY, pal.no_fg);
    bevel(ctx, ok.x, ok.y, ok.w, ok.h, pal.btn_ok, false, 3);
    textCenter(ctx, "Apply", ok.x + 100, ok.y + 20, BODY, pal.ok_fg);
    this.buttons.push(no, ok);
  }
  onButton(btn) {
    const k = btn.id[0];
    if (k === "d") { this.v = Math.max(-3, Math.min(8, this.v + btn.id[1])); return null; }
    if (k === "apply") {
      if (this.v !== 0) {
        const why = this.v > 0
          ? `${this.v} wheel${this.v > 1 ? "s" : ""} found (sailing test)`
          : "card effect";
        this.game.shiftHeading(-this.v, why);
      }
      return "close";
    }
    // Footer Cancel and the header DONE button both dismiss without
    // applying the pending wheel delta — only Apply commits the shift.
    if (k === "cancel" || k === "close") return "cancel";
    return null;
  }
}

export class ResolutionModal {
  // Two bands of card text sit between the panel top (130) and the CTA (404).
  // Each band costs 42px of chrome (22 ribbon + 10/10 padding) and 24px per
  // line, and they sit 8px apart: (396 - 130 - 8 - 84) / 24 = 7 lines to share.
  // The front takes up to 5 and the back takes the remainder, so a long front
  // cannot squeeze the back out of existence.
  static REVEAL_Y = 130;
  static REVEAL_W = 432;
  static REVEAL_GAP = 8;
  static REVEAL_LINES = 7;
  static REVEAL_FRONT_MAX = 5;

  constructor(game, forceAdvance = false) {
    this.game = game;
    this.buttons = [];
    this.branchPick = null;
    this.forceAdvance = forceAdvance;
    this._skippedSideQuests = [];   // object refs (identity, not value) - see _derive
    this.step = this._derive();
  }

  _questStep() {
    const g = this.game;
    if (g.quest.side === "A") {
      const card = g.stages[g.stage_idx].cards[g.card_idx];
      // BOTH faces. The back is not decoration: 75 of 514 stage cards print
      // their When Revealed on the back and nothing on the front, so reading
      // only the front told the player there was nothing to do on cards that
      // add enemies to staging or gate the stage's defeat.
      return { kind: "reveal", stage_n: g.quest.stage_n,
               face_a: frontFace(card), face_b: backFace(card),
               next_points: card.questPoints };
    }
    const nxtIdx = g.stage_idx + 1;
    if (nxtIdx >= g.stages.length) {
      // The final stage's back face carries the win condition, and often a
      // restriction on it ("cannot be defeated while X is in play"). That
      // sentence is the entire reason the victory prompt offers a "Not yet"
      // button, so it has to travel with the step.
      const final = g.stages[g.stage_idx].cards[g.card_idx];
      return { kind: "victory", cleared: g.questLabel(), face_b: backFace(final) };
    }
    const nxt = g.stages[nxtIdx];
    if (nxt.cards.length > 1 && this.branchPick === null) {
      return { kind: "branch", cards: nxt.cards, mode: nxt.branch ?? "choice" };
    }
    const cardIdx = this.branchPick || 0;
    return { kind: "advance", cleared: g.questLabel(), card_idx: cardIdx,
             next_stage: nxt.stage,
             underfilled: g.quest.points > 0 && g.quest.progress < g.quest.points };
  }

  _derive() {
    const g = this.game;
    if (g.stages.length && g.quest.side === "A") {
      return this._questStep();      // finish an interrupted reveal/flip first
    }
    // First seat that is at its points. The guided flow resolves them one at
    // a time, so the next _derive() picks up the next one.
    for (const loc of g.active_locations) {
      if (loc.points > 0 && loc.progress >= loc.points) {
        return { kind: "location", progress: loc.progress, points: loc.points,
                 name: loc.name || "Active location" };
      }
    }
    if ((g.quest.points > 0 && g.quest.progress >= g.quest.points) || this.forceAdvance) {
      return this._questStep();
    }
    for (let i = 0; i < g.side_quests.length; i++) {
      const s = g.side_quests[i];
      if (this._skippedSideQuests.some(skipped => s === skipped)) continue;
      if (s.points > 0 && s.progress >= s.points) {
        return { kind: "side_quest", idx: i,
                 name: s.name || `Side Quest ${i + 1}`,
                 progress: s.progress, points: s.points };
      }
    }
    return null;
  }

  draw(ctx) {
    this.buttons = [];
    rect(ctx, 0, 0, 480, 480, pal.bg);
    modalHeader(ctx, this.game, "Resolve", this.buttons);
    const st = this.step;
    if (st === null) this._drawDone(ctx);
    else if (st.kind === "reveal") this._drawReveal(ctx, st);
    else if (st.kind === "location") this._drawLocation(ctx, st);
    else if (st.kind === "branch") this._drawBranch(ctx, st);
    else if (st.kind === "advance") this._drawAdvance(ctx, st);
    else if (st.kind === "victory") this._drawVictory(ctx, st);
    else if (st.kind === "side_quest") this._drawSideQuest(ctx, st);
  }

  // -- per-step draw helpers (layout bands per the plan's Layout section) --
  _cta(ctx, label, id, y = 404, h = 56, ok = true) {
    const b = new Button(id, 24, y, 432, h);
    bevel(ctx, b.x, b.y, b.w, b.h, ok ? pal.btn_ok : pal.btn_no, false, 3);
    textCenter(ctx, label, 240, y + Math.floor(h / 2) - 10, BODY, ok ? pal.ok_fg : pal.no_fg);
    this.buttons.push(b);
  }

  _drawDone(ctx) {
    textCenter(ctx, "All resolved", 240, 200, DISPLAY, pal.gold);
    this._cta(ctx, "Continue", ["close"]);
  }

  // One scroll-edged band of card text. Returns [height, wasCut].
  _revealBand(ctx, y, label, text, maxLines) {
    const tipX = 24, tipW = ResolutionModal.REVEAL_W;
    const ribH = 22, padTop = 10, lineH = 24, padBottom = 10;
    const usable = tipW - 28;
    const wrapped = wrapText(text, BODY, usable);
    const [lines, cut] = fitLines(wrapped, maxLines, usable, wrapped.length > maxLines);
    const tipH = ribH + padTop + lines.length * lineH + padBottom;
    rect(ctx, tipX, y, tipW, tipH, pal.border_gold);
    rect(ctx, tipX + 2, y + 2, tipW - 4, tipH - 4, pal.bg);
    rect(ctx, tipX + 4, y + 4, tipW - 8, tipH - 8, pal.border_gold);
    rect(ctx, tipX + 6, y + 6, tipW - 12, tipH - 12, pal.scroll);
    rect(ctx, tipX, y, tipW, ribH, pal.border_gold);
    textLeft(ctx, label, tipX + 10, y + 6, LABEL, pal.bg, false);
    let ly = y + ribH + padTop;
    for (const ln of lines) {
      textLeft(ctx, ln, tipX + 14, ly, BODY, pal.tan);
      ly += lineH;
    }
    return [tipH, cut];
  }

  // Both faces, because the back is where a stage's rules often live.
  //
  // This drew st.face_a.text alone and printed "No setup instructions for this
  // stage." when it was empty. 75 of 514 stage cards in the catalog print their
  // When Revealed on the BACK and nothing on the front, so the panel actively
  // told the player to do nothing on cards that add enemies to staging or gate
  // the stage's defeat. The Oath's stage 2 is one, and its stage 3B carries the
  // win condition. Found in the 2026-07-30 playtest.
  _drawReveal(ctx, st) {
    textCenter(ctx, `STAGE ${st.stage_n} REVEALED`, 240, 64, BODY, pal.amber);
    const faceA = st.face_a, faceB = st.face_b ?? {};
    // Fall back to the back's name: on the 22 cards with no "A" face at all the
    // front lookup used to yield {} and the title rendered empty.
    const name = truncateText(faceA.name || faceB.name || "", DISPLAY, 432);
    textCenter(ctx, name, 240, 92, DISPLAY, pal.gold);

    const aText = faceA.text, bText = faceB.text;
    let y = ResolutionModal.REVEAL_Y, cut = false;
    if (!aText && !bText) {
      const [, c] = this._revealBand(ctx, y, "STAGE ADVANCE - RESOLVE NOW",
                                     QUEST_SETUP.none.replace("%s", st.stage_n),
                                     ResolutionModal.REVEAL_LINES);
      cut = c;
    } else {
      let budget = ResolutionModal.REVEAL_LINES;
      if (aText) {
        const cap = bText ? ResolutionModal.REVEAL_FRONT_MAX : budget;
        const [h, c] = this._revealBand(ctx, y, "STAGE ADVANCE - RESOLVE NOW", aText, cap);
        y += h + ResolutionModal.REVEAL_GAP;
        budget -= (h - 42) / 24;
        cut = cut || c;
      }
      if (bText) {
        // "QUEST SIDE" only distinguishes it FROM the front band. When the back
        // is the only text - the 75-card case - it is what the player has to
        // resolve, so it wears the action label.
        const label = aText ? "QUEST SIDE" : "STAGE ADVANCE - RESOLVE NOW";
        const [, c] = this._revealBand(ctx, y, label, bText, Math.max(2, budget));
        cut = cut || c;
      }
    }
    // Truncated text is a wrong rule, so the cut always comes with a way to
    // read the rest: the whole panel opens the card. Same pending-flag route
    // main.js already uses - a modal cannot open a modal.
    if (cut) {
      this.buttons.push(new Button(["more_card"], 24, ResolutionModal.REVEAL_Y,
                                   ResolutionModal.REVEAL_W,
                                   396 - ResolutionModal.REVEAL_Y));
    }
    this._cta(ctx, `Flip to Side B  ->  ${st.next_points} qp`, ["do_flip"]);
  }

  _drawLocation(ctx, st) {
    textCenter(ctx, "Location Explored", 240, 90, DISPLAY, pal.gold);
    // The card's own name when the player picked it from the catalog, else
    // the generic "Active location" _step() falls back to.
    textCenter(ctx, truncateText(st.name, BODY, 432), 240, 126, BODY, pal.muted);
    textCenter(ctx, `${st.progress}/${st.points} progress`, 240, 152, BODY, pal.tan);
    const excess = st.progress - st.points;
    if (excess) {
      textCenter(ctx, `${excess} excess -> quest card`, 240, 178, BODY, pal.amber);
    }
    this._cta(ctx, "Continue", ["resolve_location"]);
  }

  // Branch rows quote the alternative stages' own printed text, so the
  // preview is card text and gets BODY like every other quote. The rows grow
  // to hold it (they were 64px with a one-line LABEL preview) instead of the
  // type shrinking to fit them: the stride is whatever the space left below
  // the header divides into, capped so a 2-way split does not sprawl, and the
  // preview takes as many BODY lines as the resulting row height allows.
  static BRANCH_Y0 = 116;
  static BRANCH_STRIDE_MAX = 106;
  static BRANCH_LH = 24;

  _drawBranch(ctx, st) {
    const S = ResolutionModal;
    textCenter(ctx, "Choose a path", 240, 56, DISPLAY, pal.gold);
    // ALL CAPS both ways: this slot names how the choice gets made and is
    // read as chrome under the title, not as a sentence.
    textCenter(ctx, st.mode !== "random" ? "FIRST PLAYER CHOOSES" : "RANDOM", 240, 86, LABEL, pal.dim);
    const reserve = st.mode === "random" ? 50 : 0;    // the Randomize button
    const stride = Math.min(S.BRANCH_STRIDE_MAX,
      Math.floor((468 - S.BRANCH_Y0 - reserve) / Math.max(1, st.cards.length)));
    const rowH = Math.max(48, stride - 10);
    const maxLines = Math.max(1, Math.floor((rowH - 34) / S.BRANCH_LH));
    const usable = 432 - 28;
    let y = S.BRANCH_Y0;
    st.cards.forEach((card, i) => {
      const bFace = backFace(card);
      const b = new Button(["pick_branch", i], 24, y, 432, rowH);
      const sel = this.branchPick === i;
      bevel(ctx, b.x, b.y, b.w, b.h, sel ? pal.btn_ok : pal.btn, false, 3);
      textLeft(ctx, bFace.name || "?", b.x + 14, y + 10, BODY, sel ? pal.ok_fg : pal.tan);
      let lines = wrapText(bFace.text || "", BODY, usable);
      if (lines.length > maxLines) {
        lines = lines.slice(0, maxLines);
        lines[lines.length - 1] = truncateText(lines[lines.length - 1] + " ..", BODY, usable);
      }
      let ly = y + 38;
      for (const ln of lines) {
        if (ln) textLeft(ctx, ln, b.x + 14, ly, BODY, pal.dim);
        ly += S.BRANCH_LH;
      }
      this.buttons.push(b);
      y += stride;
    });
    if (st.mode === "random") {
      const r = new Button(["randomize_branch"], 24, y, 432, 40);
      bevel(ctx, r.x, r.y, r.w, r.h, pal.card, false, 2);
      textCenter(ctx, "Randomize for me", 240, y + 10, BODY, pal.tan);
      this.buttons.push(r);
    }
  }

  _drawAdvance(ctx, st) {
    textCenter(ctx, `Quest ${st.cleared} cleared`, 240, 90, DISPLAY, pal.gold);
    if (st.underfilled) {
      textCenter(ctx, "Progress hasn't reached target - confirm", 240, 130, BODY, pal.red);
    }
    this._cta(ctx, `Reveal Stage ${st.next_stage}`, ["do_advance"]);
  }

  // The final stage's own text, so "Not yet" has a stated reason.
  //
  // This screen offered Declare Victory with nothing but "That was the final
  // stage!" above it. The sentence that decides whether the game is actually
  // won - "This stage cannot be defeated while Goblin Troop is in play" - is
  // printed on the stage's BACK face, which nothing on this screen ever read.
  // In the 2026-07-30 playtest the HUD offered victory with Goblin Troop alive
  // in the staging area.
  _drawVictory(ctx, st) {
    textCenter(ctx, `Quest ${st.cleared} cleared`, 240, 70, BODY, pal.tan);
    textCenter(ctx, "That was the final stage!", 240, 110, DISPLAY, pal.gold);
    const bText = (st.face_b ?? {}).text;
    if (bText) {
      const usable = 432 - 28;
      const wrapped = wrapText(bText, BODY, usable);
      // 150 to 330 is 180px = 7 lines at the 24px prose pitch.
      const [lines, cut] = fitLines(wrapped, 7, usable, wrapped.length > 7);
      let ly = 150;
      for (const ln of lines) {
        textLeft(ctx, ln, 38, ly, BODY, pal.muted);
        ly += 24;
      }
      if (cut) this.buttons.push(new Button(["more_card"], 24, 150, 432, ly - 150));
    }
    this._cta(ctx, "Declare Victory", ["declare_victory"], 340);
    this._cta(ctx, "Not yet - keep playing", ["continue_without_victory"], 404, 56, false);
  }

  _drawSideQuest(ctx, st) {
    textCenter(ctx, st.name, 240, 90, DISPLAY, pal.gold);
    textCenter(ctx, `${st.progress}/${st.points}`, 240, 130, BODY, pal.tan);
    this._cta(ctx, "Mark Complete", ["resolve_side_quest"], 340);
    this._cta(ctx, "Leave as-is", ["skip_side_quest"], 404, 56, false);
  }

  onButton(btn) {
    const g = this.game;
    const k = btn.id[0];
    if (k === "do_flip") { g.flipToB(); this.step = this._derive(); return "redraw"; }
    if (k === "resolve_location") {
      g.resolveLocationOverflow();
      this.step = this._derive();
      return "redraw";
    }
    if (k === "pick_branch") { this.branchPick = btn.id[1]; this.step = this._derive(); return "redraw"; }
    if (k === "randomize_branch") {
      this.branchPick = Math.floor(Math.random() * this.step.cards.length);
      this.step = this._derive();
      return "redraw";
    }
    if (k === "do_advance") {
      g.clearAndAdvance(this.step.card_idx);
      this.forceAdvance = false;
      this.branchPick = null;
      this.step = this._derive();
      return "redraw";
    }
    if (k === "declare_victory") { g.setGameOver("victory"); return "close"; }
    if (k === "continue_without_victory") {
      // Must CLOSE, not redraw. _derive() recomputes the same victory step
      // while progress >= points, so redrawing put the identical screen back
      // and the tap read as a no-op - the player pressed it three times in the
      // 2026-07-30 playtest before reaching for DONE.
      g.logEvent("Victory declined - the stage is not defeated yet");
      return "close";
    }
    if (k === "more_card") {
      // A modal cannot open a modal, so hand off through the router's pending
      // flags: main.js checks pending_quest_card BEFORE pending_resolution, so
      // the card opens, and closing it brings this modal straight back with its
      // step re-derived from live state.
      g.pending_quest_card = true;
      g.pending_resolution = this.forceAdvance ? "forced" : true;
      return "close";
    }
    if (k === "resolve_side_quest") {
      const i = this.step.idx;
      g.logEvent(`Side quest ${i + 1} completed (resolution)`);
      g.side_quests.splice(i, 1);
      this.step = this._derive();
      return "redraw";
    }
    if (k === "skip_side_quest") {
      this._skippedSideQuests.push(g.side_quests[this.step.idx]);
      this.step = this._derive();
      return "redraw";
    }
    if (k === "close") return "close";
    return null;
  }
}

// Twin of ui/modals.py LocationConfigModal. Everything about the active
// location the player may need to correct at the table: its progress, its
// quest points (defaulted from the card, still overridable) and its THREAT -
// the staging contribution that "Back to staging" has to add back.
//
// 34 of the catalog's X-printing location faces print X for threat rather
// than quest points, so this is the row the X work actually shows up on.
export class LocationConfigModal {
  constructor(game, idx = 0) {
    this.game = game;
    // WHICH seat this sheet edits. The row's chevron passes its own index;
    // everything else opens the first, which is the only one there is unless
    // one of the five two-location cards is in play.
    this.idx = idx;
    const loc = idx < game.active_locations.length ? game.active_locations[idx] : null;
    this.has = loc !== null && loc !== undefined;
    this.pts = loc ? loc.points : 2;
    this.prog = loc ? loc.progress : 0;
    this.name = loc?.name ?? null;
    this.threat = loc?.threat ?? 0;
    // The coded X: {text, target, mul, add}. `text` is the card's own words,
    // shown as-is; `target` is the xtargets enum the count control will be
    // built from. See xtargets.py.
    this.threatX = loc?.threatX ?? null;
    this.threatFormula = this.threatX?.text ?? null;
    // How the threat row behaves, from the coded X (see xtargets.js):
    //   "auto"   a tracked value answers it - read-only, no stepper
    //   "count"  the player supplies a count the app does arithmetic on -
    //            read-only value PLUS a stepper on the count
    //   "bare"   the count IS the value - one stepper, no second number
    //   null     an ordinary editable number
    this.threatCount = loc?.threatCount ?? null;
    this.threatShape = null;
    if (this.threatX) {
      const t = this.threatX.target;
      const auto = xtargets.autoFor(t);
      // AUTO_ENEMIES/AUTO_STAGING_LOCATIONS are tracker-backed: only skip the
      // stepper when this client actually tracks the board - the same call
      // xtargets.resolve makes via xContext(). The three always-on auto
      // targets (players/stage/highestThreat) never need the guard.
      const trackerBacked = auto === xtargets.AUTO_ENEMIES ||
                            auto === xtargets.AUTO_STAGING_LOCATIONS;
      if (auto && (!trackerBacked || boardTracking())) this.threatShape = "auto";
      else if ((this.threatX.mul ?? 1) === 1 && !this.threatX.add) this.threatShape = "bare";
      else this.threatShape = "count";
      this.threatLabel = xtargets.labelFor(t);
    }
    // An X with no formula has no number to show yet, and 0 would be a claim
    // the card never made. One tap on "+" makes it a real value.
    this.threatBlank = loc?.threatKind === "x" && !this.threat;
    this.buttons = [];
  }

  // `blank` draws an empty value slot instead of a number. A DRAWN rule rather
  // than a typed dash: at this size a dash is indistinguishable from the
  // stepper's own "-", and the device font has 82 glyphs so an em-dash is not
  // guaranteed to be one of them.
  _row(ctx, y, label, value, key, blank = false) {
    textLeft(ctx, label, 30, y + 14, BODY, pal.tan);
    stepper(ctx, this.buttons, [key, -1], [key, 1], 260, y,
            blank ? "" : String(value), 190, 52);
    if (blank) rect(ctx, 340, y + 25, 30, 3, pal.gold);
  }

  // A value the CARD owns: read-only, no stepper. "label = X" states the chain
  // rather than leaving the player to infer it from a note.
  _computed(ctx, y, label, value) {
    textLeft(ctx, label, 30, y + 14, BODY, pal.tan);
    textLeft(ctx, "= X", 36 + measureText(label, BODY), y + 14, BODY, pal.dim);
    textCenter(ctx, value === null ? "-" : String(value), 355, y + 10, DISPLAY, pal.gold);
  }

  _resolved() {
    return xtargets.resolve(this.threatX, { count: this.threatCount, ...this.game.xContext() });
  }

  // The threat row, in whichever shape the card calls for. Returns the y to
  // continue at.
  _threatBlock(ctx, y) {
    const shape = this.threatShape;
    if (shape === "auto" || shape === "count") {
      this._computed(ctx, y, "Threat", this._resolved());
      // +40, not +34: the value is DISPLAY-sized (24px tall drawn at y+10), so
      // a 34 step put the formula's first line inside its descender.
      y += 40;
      for (const ln of wrapText("X = " + (this.threatFormula ?? ""), BODY, 420,
                                measureText).slice(0, 2)) {
        textLeft(ctx, ln, 50, y, BODY, pal.dim);
        y += 22;
      }
      if (shape === "count") {
        // The only thing the player can move. They answer "how many enemies are
        // in play?" by looking at the table; the app applies the arithmetic, so
        // nobody does it in their head, and the count survives to next round.
        this._row(ctx, y + 4, this.threatLabel, this.threatCount ?? 0, "count");
        y += 62;
      } else {
        y += 8;
      }
      return y;
    }
    this._row(ctx, y, "Threat", this.threat, "threat", this.threatBlank);
    return y + 56;
  }

  draw(ctx) {
    this.buttons = [];
    rect(ctx, 0, 0, 480, 480, pal.bg);
    // Back rides in the title bar, not at the bottom: the count shape's threat
    // block pushes the action grid down past y=420, so a pinned bottom button
    // lands on top of "Replaced". Top-left is where the mock puts it anyway,
    // and it matches every other sub-view's way back.
    textLeft(ctx, "< Progress", 10, 12, BODY, pal.tan);
    this.buttons.push(new Button(["close"], 0, 0, 150, 40));
    textCenter(ctx, "Active Location", 240, 12, DISPLAY, pal.gold);
    if (this.name) {
      textCenter(ctx, truncateText(this.name, BODY, 440), 240, 46, BODY, pal.tan);
    }
    this._row(ctx, 76, "Progress", this.prog, "prog");
    this._row(ctx, 136, "Quest points", this.pts, "pts");
    let y = this._threatBlock(ctx, 196);
    if (this.threatFormula && this.threatShape === "bare") {
      for (const ln of wrapText("X = " + this.threatFormula, BODY, 420,
                                measureText).slice(0, 2)) {
        textLeft(ctx, ln, 30, y, BODY, pal.dim);
        y += 22;
      }
    } else if (this.threatBlank && !this.threatX) {
      // Only when the card defines X NOWHERE we can read. With a coded X the
      // formula line above already said where the number comes from.
      textLeft(ctx, "the card prints X and defines it elsewhere", 30, y, BODY, pal.dim);
      y += 22;
    }
    // RR: progress is NOT lost when a location returns to the staging area -
    // Impassable Chasm has to SAY "remove all progress tokens", which it would
    // not need to if returning did it.
    if (this.has && y < 296) {
      textLeft(ctx, "Back to staging keeps its progress.", 30, y, BODY, pal.dim);
      y += 22;
    }
    // The four ways a location leaves, each NAMED - JS had only a vague
    // "Set none (no active location)", which is what "the additional actions
    // are not labeled" was about. "Back to staging" is only honest because the
    // record carries the card's threat: it puts the right number back.
    //
    // Floor only, no ceiling: a ceiling pinned the grid however tall the
    // threat block got, and the count shape ends near 342.
    y = Math.max(y + 6, 288);
    const acts = [["Explored", ["explored"], pal.green],
                  ["Back to staging", ["tostaging"], pal.tan],
                  ["Replaced", ["replaced"], pal.tan],
                  ["Remove", ["none"], pal.no_fg]];
    acts.forEach(([label, bid, pen], i) => {
      const b = new Button(bid, 30 + (i % 2) * 212, y + Math.floor(i / 2) * 50,
                           200, 44);
      if (pen === pal.no_fg) panel(ctx, b.x, b.y, b.w, b.h, pal.btn_no, pal.no_fg);
      else bevel(ctx, b.x, b.y, b.w, b.h, pal.btn, false, 3);
      textCenter(ctx, label, b.x + b.w / 2, b.y + 12, BODY, pen);
      this.buttons.push(b);
    });
    // No Done and no Cancel: there is nothing to commit. Every tap applies
    // immediately, the way PlayersDetailModal already works, so the only
    // control this sheet needs is the way back - drawn in the title bar at the
    // top of this method, which also gives the threat block the 64px the count
    // shape needs.
  }

  // Write the edit through NOW. The sheet has no Save, so every tap lands
  // here. Starts from the EXISTING record rather than replacing it - a
  // wholesale replace dropped the card name, its threat and the *Kind/*X keys
  // the picker had just filled in.
  _apply() {
    const loc = { ...(this._seat() ?? {}) };
    loc.points = this.pts;
    loc.progress = this.prog;
    if (this.threatShape === "auto" || this.threatShape === "count") {
      // Store the COUNT and recompute: storing only the result would go stale
      // the moment the board changes.
      if (this.threatCount !== null) loc.threatCount = this.threatCount;
      loc.threat = this._resolved() ?? 0;
    } else if (this.threat || !this.threatBlank) {
      loc.threat = this.threat;
    }
    if (this.idx < this.game.active_locations.length) {
      this.game.active_locations[this.idx] = loc;
    } else {
      this.game.active_locations.push(loc);
      this.idx = this.game.active_locations.length - 1;
    }
  }

  // The record this sheet edits, or null if the seat is empty.
  _seat() {
    return this.idx < this.game.active_locations.length
      ? this.game.active_locations[this.idx] : null;
  }

  // Take this location out of the row. Returns the record it removed.
  _leave() {
    const loc = this._seat();
    if (loc) this.game.active_locations.splice(this.idx, 1);
    return loc ?? null;
  }

  onButton(btn) {
    const k = btn.id[0];
    if (k === "pts") {
      this.pts = Math.max(1, Math.min(30, this.pts + btn.id[1]));
      this.has = true; this._apply(); return null;
    }
    if (k === "prog") {
      this.prog = Math.max(0, Math.min(99, this.prog + btn.id[1]));
      this.has = true; this._apply(); return null;
    }
    if (k === "count") {
      this.threatCount = Math.max(0, Math.min(60, (this.threatCount ?? 0) + btn.id[1]));
      this.has = true; this._apply(); return null;
    }
    if (k === "threat") {
      this.threat = Math.max(0, Math.min(30, this.threat + btn.id[1]));
      this.threatBlank = false;   // a tap makes it a real value
      this.has = true; this._apply(); return null;
    }
    if (k === "none") {
      if (this._leave()) this.game.logEvent("Active location removed");
      return "close";
    }
    if (k === "explored") {
      if (this._leave()) this.game.logEvent("Active location Explored");
      return "close";
    }
    if (k === "tostaging") {
      // The record carries the card's threat, so staging gets the right number
      // back rather than a guess. RR: progress is NOT lost, so nothing is
      // zeroed here.
      const loc = this._leave() ?? {};
      const back = loc.threat ?? 0;
      this.game.staging += back;
      this.game.logEvent(`Active location to staging (+${back} threat, ${loc.progress ?? 0} progress kept)`);
      return "close";
    }
    if (k === "replaced") {
      this.game.pending_location_pick = { mode: "change", back: "progress" };
      return "close";
    }
    if (k === "close") {
      // One summary line for the whole visit; a log entry per stepper tap
      // would bury the round.
      if (this.has) {
        this.game.logEvent(`Active location set to ${this.prog}/${this.pts} progress, ${this.threat} threat`);
      }
      return "close";
    }
    return null;
  }
}


export class QuestConfigModal {
  constructor(game) {
    this.game = game;
    this.q = { ...game.quest };
    this.sail = game.sailing;
    this.buttons = [];
    // What it looked like on the way in, so close can log ONE summary line
    // instead of one per stepper tap.
    this._was = [this.q.stage_n, this.q.side, this.q.points, this.q.progress].join("/");
  }

  // Write the edit through NOW. The sheet has no Save, so every tap lands
  // here - the same live-edit model PlayersDetailModal and the location sheet
  // use.
  _apply() {
    this.game.quest = { ...this.q };
  }

  draw(ctx) {
    this.buttons = [];
    rect(ctx, 0, 0, 480, 480, pal.bg);
    modalHeader(ctx, this.game, `Quest  ${this.q.stage_n}${this.q.side}`,
                this.buttons, { back: ["< Progress", ["close"]], cta: null });
    textLeft(ctx, "Stage number", 30, 84, BODY, pal.tan);
    stepper(ctx, this.buttons, ["n", -1], ["n", 1], 300, 70, String(this.q.stage_n), 150, 52);
    textLeft(ctx, "Side", 30, 156, BODY, pal.tan);
    stepper(ctx, this.buttons, ["side", -1], ["side", 1], 300, 142, this.q.side, 150, 52);
    // A stage that advances on a condition has no quest points to edit, so the
    // stepper is replaced by the card's own sentence about how the stage ends
    // (distilled from its printed text - see tools/build_advancement.py). 177
    // stage cards are like this; a stepper reading 0 invites the player to
    // "fix" a number the card never printed.
    if (this.q.mode === "condition" && this.q.advance) {
      textLeft(ctx, "Advances", 30, 214, BODY, pal.tan);
      let ty = 236;
      for (const ln of wrapText(this.q.advance, BODY, 420, measureText).slice(0, 2)) {
        textLeft(ctx, ln, 30, ty, BODY, pal.dim);
        ty += 22;
      }
      // 11 stages state BOTH: Return to Rhosgobel is won if Wilyador is healed
      // and lost otherwise. Showing only the win is showing half the rule.
      if (this.q.lose) {
        for (const ln of wrapText(this.q.lose, BODY, 420, measureText).slice(0, 1)) {
          textLeft(ctx, ln, 30, ty, BODY, pal.no_fg);
          ty += 22;
        }
      }
    } else {
      textLeft(ctx, this.q.x ? "Quest points = X" : "Quest points",
               30, 228, BODY, pal.tan);
      stepper(ctx, this.buttons, ["pts", -1], ["pts", 1], 300, 214, String(this.q.points), 150, 52);
    }
    textLeft(ctx, "Sailing quest", 30, 296, BODY, pal.tan);
    icons.drawIcon(ctx, icons.WHEEL, 176, 292, this.sail ? pal.gold : pal.dim);
    const sb = new Button(["sail"], 300, 284, 150, 48);
    panel(ctx, sb.x, sb.y, sb.w, sb.h, this.sail ? pal.gold : pal.btn);
    textCenter(ctx, this.sail ? "On" : "Off", sb.x + 75, sb.y + 14, BODY,
               this.sail ? pal.bg : pal.tan, false);
    this.buttons.push(sb);
    // A catalog game advances through the GUIDED flow, which knows about
    // branch alternatives, victory and the location credit. A custom game has
    // no ResolutionModal to open, so it keeps the manual edit it has always
    // had. Showing both would be two buttons named "advance" that do
    // different things.
    if (this.game.stages.length) {
      // The only way in for a stage with no quest points: ~137 of ~400 stage
      // cards advance on a condition, so there is no target to cross and
      // nothing to trigger the flow on its own.
      const fa = new Button(["force_adv"], 30, 344, 205, 48);
      bevel(ctx, fa.x, fa.y, fa.w, fa.h, pal.btn);
      textCenter(ctx, "Advance anyway", fa.x + Math.floor(fa.w / 2), fa.y + 14, BODY, pal.tan);
      this.buttons.push(fa);
      const vc = new Button(["quest_card"], 245, 344, 205, 48);
      bevel(ctx, vc.x, vc.y, vc.w, vc.h, pal.btn);
      textCenter(ctx, "View quest card", vc.x + Math.floor(vc.w / 2), vc.y + 14, BODY, pal.tan);
      this.buttons.push(vc);
    } else {
      const adv = new Button(["adv"], 30, 344, 420, 48);
      bevel(ctx, adv.x, adv.y, adv.w, adv.h, pal.btn);
      textCenter(ctx, "Advance stage (progress -> 0)", adv.x + 210, adv.y + 14, BODY, pal.tan);
      this.buttons.push(adv);
    }
    // No Done and no Cancel: every tap has already landed on the game. The
    // only control this sheet needs is the way back, in the header above.
  }
  onButton(btn) {
    const k = btn.id[0];
    if (k === "n") {
      this.q.stage_n = Math.max(1, Math.min(9, this.q.stage_n + btn.id[1]));
      this._apply(); return null;
    }
    if (k === "side") {
      const i = (this.q.side.charCodeAt(0) - 65 + btn.id[1] + 8) % 8;   // cycle A-H
      this.q.side = String.fromCharCode(65 + i);
      this._apply(); return null;
    }
    if (k === "pts") {
      this.q.points = Math.max(0, Math.min(30, this.q.points + btn.id[1]));
      this._apply(); return null;
    }
    if (k === "adv") {
      if (this.q.side === "A") this.q.side = "B";
      else { this.q.side = "A"; this.q.stage_n += 1; }
      this.q.progress = 0;
      this._apply(); return null;
    }
    if (k === "force_adv") {
      // One modal at a time, so flag and close - main.js opens ResolutionModal
      // on the next tick, same pattern as quest_card.
      this.game.pending_resolution = "forced";
      return "close";
    }
    if (k === "quest_card") {
      this.game.pending_quest_card = true;
      return "close";
    }
    if (k === "sail") {
      this.sail = !this.sail;
      if (this.sail !== this.game.sailing) {
        this.game.sailing = this.sail;
        this.game.logEvent(this.sail
          ? "Sailing enabled (Dream-chaser) - heading starts On-course"
          : "Sailing disabled");
        if (this.sail) this.game.heading = 0;
      }
      return null;
    }
    if (k === "close") {
      // One summary line for the whole visit - a log entry per stepper tap
      // would bury the round. Sailing logs as it happens, above, because it is
      // a game-wide switch rather than a value edit.
      const now = [this.q.stage_n, this.q.side, this.q.points, this.q.progress].join("/");
      if (now !== this._was) {
        this.game.logEvent(`Quest set to stage ${this.q.stage_n}${this.q.side}, `
                           + `${this.q.progress}/${this.q.points} progress`);
      }
      this._apply();
      return "close";
    }
    return null;
  }
}

// Read-only stage/card reference (M4-B): opens on the game's current stage
// and pages through every stage of the loaded scenario snapshot (game.stages,
// copied at preload - no catalog re-read). Branch stages (multiple
// alternative cards) can be flipped between with the alt control; switching
// only changes what is displayed. Purely presentational - idx/card are the
// modal's own state, never written back to game.
export class QuestCardModal {
  // Read-only card reference (M4-B): one **card side per page**, paged flat
  // across every stage, every alternative and every face of the loaded
  // scenario snapshot (game.stages, copied at preload), or of a `stages` list
  // handed in directly (preview mode, see the constructor).
  //
  // It is a reference, not a game view, so branch structure deliberately does
  // not shape it: a stage's alternatives are simply more pages rather than a
  // toggle, and nothing here reads or writes the branch the game actually
  // took. Purely presentational - page/detail are the modal's own state,
  // never written back to game.
  //
  // Long card text and the stage's tips are both shown truncated inline with
  // a "more" affordance; tapping either opens a full-page detail view of it
  // (scale 1, where every catalogued face fits - the longest is 11 lines).
  // Mirror of ui/modals.py - keep the two in lockstep.
  static MARGIN = 12;
  // Fixed bottom nav, so the reading area above it is the same height on
  // every page (the previous layout let the pager float up under short text,
  // which meant the body started at a different y on every card).
  static NAV_Y = 424;
  static NAV_H = 44;
  static BODY_Y0 = 130;
  static DETAIL_Y0 = 78;
  // One wrapped body line. This was 26, hand-copied from notePanel's old
  // formula, so card text stepped 2px looser than every guidance band.
  static LH = bandLineH(BODY);
  static TIPS_LINES = 2;       // inline peek before "more" takes over
  static TIPS_H = 18 + 2 * 26 + 8;
  static MORE = " [...] more";

  constructor(game, tips = null, stages = null, scenario = null) {
    this.game = game;
    // Preview mode: Scenario Options opens this BEFORE the scenario is
    // preloaded into the game, so it passes the picked scenario's stages and
    // index entry directly. Everything below reads these, never the game.
    this.preview = stages !== null;
    this.stages = stages ?? game.stages;
    this.scenario = (stages === null ? game.scenario : scenario) ?? {};
    this.buttons = [];
    this.tips = tips || {};
    this.detail = null;        // null | "tips" | "text" - full-page views
    this.detailPage = 0;
    this._tipsData = null;
    this.page = this._livePage();
  }

  // -- page model ------------------------------------------------------
  _pages() {
    const out = [];
    (this.stages ?? []).forEach((st, si) => {
      (st.cards ?? []).forEach((card, ci) => {
        (card.faces ?? []).forEach((_, fi) => out.push([si, ci, fi]));
      });
    });
    return out;
  }

  _at(page) {
    const [si, ci, fi] = page;
    const st = this.stages[si];
    const card = st.cards[ci];
    return [st, card, card.faces[fi]];
  }

  _livePage() {
    const pages = this._pages();
    if (!pages.length || this.preview) return 0;
    const want = this.game.quest?.side ?? "A";
    for (let i = 0; i < pages.length; i++) {
      const [si, ci] = pages[i];
      if (si === this.game.stage_idx && ci === this.game.card_idx) {
        if ((this._at(pages[i])[2].side || "A") === want) return i;
      }
    }
    return 0;
  }

  _label(page) {
    const [st, , face] = this._at(page);
    return `Stage ${st.stage}${face.side || ""}`;
  }

  // -- shared bits -----------------------------------------------------
  // The marker has to be made room for, not appended and truncated - doing
  // the latter cuts the marker itself down to "[...." and the affordance
  // disappears.
  // Delegates to ui.js fitLines - the stage-advance panel needs the same
  // measured-marker rule, so there is one implementation of it.
  _fit(lines, maxLines, usable, more) {
    return fitLines(lines, maxLines, usable, more, QuestCardModal.MORE);
  }

  _nav(ctx, pages) {
    const M = QuestCardModal.MARGIN;
    const half = Math.floor((480 - 2 * M - 8) / 2);
    if (this.page > 0) {
      const b = new Button(["prev"], M, QuestCardModal.NAV_Y, half, QuestCardModal.NAV_H);
      bevel(ctx, b.x, b.y, b.w, b.h, pal.btn);
      textCenter(ctx, truncateText("< " + this._label(pages[this.page - 1]), BODY, half - 16),
                 b.x + half / 2, b.y + 14, BODY, pal.tan);
      this.buttons.push(b);
    }
    if (this.page < pages.length - 1) {
      const b = new Button(["next"], M + half + 8, QuestCardModal.NAV_Y, half, QuestCardModal.NAV_H);
      bevel(ctx, b.x, b.y, b.w, b.h, pal.btn);
      textCenter(ctx, truncateText(this._label(pages[this.page + 1]) + " >", BODY, half - 16),
                 b.x + half / 2, b.y + 14, BODY, pal.tan);
      this.buttons.push(b);
    }
  }

  // The full content behind a "more" tap - at BODY, like everything else. It
  // used to render at LABEL so it would fit on one page, which is exactly
  // backwards: this view exists to give the text ROOM. When it does not fit,
  // it pages (see _detailCapacity).
  _detailLines(usable) {
    if (this.detail === "tips") {
      const t = this._tipsData ?? { tips: [] };
      const lines = [];
      for (const tip of t.tips) lines.push(...wrapText("- " + tip, BODY, usable));
      const attribution = t.attribution ?? {};
      for (const extra of [attribution.name ? "Source: " + attribution.name : "",
                           attribution.url || ""]) {
        if (extra) lines.push({ dim: truncateText(extra, LABEL, usable) });
      }
      return lines;
    }
    const [, , face] = this._at(this._pages()[this.page]);
    return wrapText(face.text || NO_CARD_TEXT, BODY, usable);
  }

  // Lines of BODY text one detail page holds.
  _detailCapacity() {
    const S = QuestCardModal;
    return Math.max(1, Math.floor((S.NAV_Y - 12 - S.DETAIL_Y0 - 10) / S.LH));
  }

  _drawDetail(ctx, title) {
    const S = QuestCardModal;
    const M = S.MARGIN, W = 480 - 2 * M, usable = W - 20;
    const lines = this._detailLines(usable);
    const cap = this._detailCapacity();
    const pages = Math.max(1, Math.ceil(lines.length / cap));
    this.detailPage = Math.max(0, Math.min(this.detailPage, pages - 1));
    const chunk = lines.slice(this.detailPage * cap, (this.detailPage + 1) * cap);

    textLeft(ctx, truncateText(title, BODY, W), M, 48, BODY, pal.gold);
    const y = S.DETAIL_Y0;
    panel(ctx, M, y, W, S.NAV_Y - 12 - y, pal.card);
    let ty = y + 10;
    for (const ln of chunk) {
      if (typeof ln === "object") {
        textLeft(ctx, ln.dim, M + 10, ty, LABEL, pal.dim);
        ty += 16;
      } else {
        textLeft(ctx, ln, M + 10, ty, BODY, pal.tan);
        ty += S.LH;
      }
    }

    // Back always; a "More" pager only when the text genuinely needs one.
    const half = Math.floor((480 - 2 * M - 8) / 2);
    const w = pages > 1 ? half : 480 - 2 * M;
    const b = new Button(["back"], M, S.NAV_Y, w, S.NAV_H);
    bevel(ctx, b.x, b.y, b.w, b.h, pal.btn);
    textCenter(ctx, "Back", b.x + Math.floor(w / 2), b.y + 14, BODY, pal.tan);
    this.buttons.push(b);
    if (pages > 1) {
      const nb = new Button(["detail_more"], M + half + 8, S.NAV_Y, half, S.NAV_H);
      bevel(ctx, nb.x, nb.y, nb.w, nb.h, pal.btn);
      textCenter(ctx, `More ${this.detailPage + 1}/${pages} >`,
                 nb.x + Math.floor(half / 2), nb.y + 14, BODY, pal.tan);
      this.buttons.push(nb);
    }
  }

  // -- draw ------------------------------------------------------------
  draw(ctx, game) {
    const S = QuestCardModal;
    this.buttons = [];
    rect(ctx, 0, 0, 480, 480, pal.bg);
    modalHeader(ctx, game, "Quest Cards", this.buttons);
    const M = S.MARGIN, W = 480 - 2 * M;

    const pages = this._pages();
    if (!pages.length) {
      textCenter(ctx, "No quest loaded", 240, 200, BODY, pal.dim);
      textCenter(ctx, "Start a scenario to see stage cards.", 240, 226, BODY, pal.dim);
      return;
    }

    this.page = Math.max(0, Math.min(this.page, pages.length - 1));
    const page = pages[this.page];
    const [stage, card, face] = this._at(page);
    const side = face.side || "A";
    this._tipsData = tipsFor(this.scenario?.slug, stage.stage, this.tips);

    if (this.detail === "tips" && this._tipsData) {
      this._drawDetail(ctx, `Tips - Stage ${stage.stage}`);
      return;
    }
    if (this.detail === "text") {
      this._drawDetail(ctx, this._label(page));
      return;
    }
    this.detail = null;

    // -- identity row: which card side, whether it is the live one, and what
    // it is worth. The quest points sit here (they used to own a whole
    // block-level row) - it is one number, it belongs in a corner.
    let y = 48;
    textLeft(ctx, this._label(page), M, y, BODY, pal.amber);
    const pts = `${card.questPoints ?? 0} pts`;
    textLeft(ctx, pts, 480 - M - measureText(pts, BODY), y, BODY, pal.gold);
    if (this.page === this._livePage()) {
      const pw = measureText("CURRENT", LABEL) + 14;
      rect(ctx, 240 - pw / 2, y + 2, pw, 18, pal.gold);
      textCenter(ctx, "CURRENT", 240, y + 6, LABEL, pal.bg, false);
    }
    y += 26;

    // Victory/sailing are rare, so they cost a row only when present.
    // ALL CAPS: this is a keyword badge sitting beside the card name, read as
    // chrome rather than as a sentence, so the casing carries the demotion
    // instead of the size (design system, LABEL).
    const extra = [];
    if (card.victory !== null && card.victory !== undefined) extra.push(`VICTORY ${card.victory}`);
    if (card.sailing) extra.push("SAILING");
    if (extra.length) {
      const s = extra.join("  ");
      textLeft(ctx, s, 480 - M - measureText(s, LABEL), y, LABEL, pal.dim);
    }

    textLeft(ctx, truncateText(face.name || "(unnamed)", BODY, W), M, y, BODY, pal.gold);
    y += 28;
    // The card's own text usually leads with "Setup:", which IS the heading -
    // printed, at BODY, legible. Repeating it in LABEL chrome above gave the
    // section two headings, the smaller of which read as stray text. Show the
    // label only when the text does not already name the section. The printed
    // text is never edited: rule 4 prefers a card's own words.
    const heading = side === "A" ? "SETUP / STORY" : "QUEST";
    const leads = (face.text || "").trimStart().toLowerCase();
    if (!leads.startsWith(heading.split(" / ")[0].toLowerCase() + ":")) {
      textLeft(ctx, heading, M, y, LABEL, pal.amber);
    }

    // -- body: the card's own text, at the same scale as everywhere else. It
    // gets every pixel between here and whatever sits below (the tips peek,
    // or the nav), and marks its own truncation.
    const hasTips = !!this._tipsData;
    const tipsY = S.NAV_Y - 12 - S.TIPS_H;
    const bodyBottom = hasTips ? tipsY - 8 : S.NAV_Y - 12;
    const by = S.BODY_Y0, usable = W - 20;
    const text = face.text || "";
    let [lines, cut] = this._fit(wrapText(text || NO_CARD_TEXT, BODY, usable),
                                 Math.max(1, Math.floor((bodyBottom - by) / S.LH)),
                                 usable, false);
    panel(ctx, M, by - 8, W, bodyBottom - by + 8, pal.card);
    let ty = by;
    for (const ln of lines) {
      textLeft(ctx, ln, M + 10, ty, BODY, text ? pal.tan : pal.dim);
      ty += S.LH;
    }
    if (cut) this.buttons.push(new Button(["more_text"], M, by - 8, W, bodyBottom - by + 8));

    // -- tips peek: the first lines inline, the rest behind a tap ---------
    if (hasTips) {
      const joined = this._tipsData.tips.join("  ");
      let [tl] = this._fit(wrapText(joined, BODY, usable), S.TIPS_LINES, usable,
                           wrapText(joined, BODY, usable).length > S.TIPS_LINES);
      panel(ctx, M, tipsY, W, S.TIPS_H, pal.card);
      textLeft(ctx, "TIPS", M + 10, tipsY + 6, LABEL, pal.amber);
      let tty = tipsY + 22;
      for (const ln of tl) { textLeft(ctx, ln, M + 10, tty, BODY, pal.tan); tty += S.LH; }
      this.buttons.push(new Button(["tips"], M, tipsY, W, S.TIPS_H));
    }

    this._nav(ctx, pages);
  }

  onButton(btn) {
    const k = btn.id[0];
    if (k === "close") return "close";
    if (k === "back") { this.detail = null; this.detailPage = 0; return "redraw"; }
    if (!this.stages?.length) return null;
    if (k === "tips") {
      if (this._tipsData) { this.detail = "tips"; this.detailPage = 0; return "redraw"; }
      return null;
    }
    if (k === "more_text") { this.detail = "text"; this.detailPage = 0; return "redraw"; }
    if (k === "detail_more") {
      this.detailPage += 1;     // _drawDetail clamps; wrap is handled there
      return "redraw";
    }
    const n = this._pages().length;
    if (k === "next" && this.page < n - 1) { this.page += 1; return "redraw"; }
    if (k === "prev" && this.page > 0) { this.page -= 1; return "redraw"; }
    return null;
  }
}


// Radio-button glyph: ring, filled when selected. Mirror of ui/modals.py's
// _sq_radio - it was called below but never defined here, so the web twin
// threw "sqRadio is not defined" on any non-empty side-quest catalog.
function pickRadio(ctx, cx, cy, on) {
  arcRuns(ctx, cx, cy, 10, 8, 0, 360, on ? pal.gold : pal.dim);
  if (on) disc(ctx, cx, cy, 5, pal.gold);
}

// Two-step picker over the player side-quest catalog: sphere first, then the
// quest, mirroring the Pick Cycle -> Choose Scenario drill. Sphere order
// follows the Rules Reference's "Spheres of Influence" diagram (Leadership,
// Lore, Spirit, Tactics), then Neutral, then anything else; cards whose
// sphere the catalog does not carry are grouped last under NO_SPHERE rather
// than guessed into one. On the way out it sets game.pending_progress_detail
// so the router reopens the Progress modal you came from.
// Mirror of ui/modals.py - keep the two in lockstep.
export class SideQuestPickModal {
  static PER_PAGE = 6;
  static ROW_H = 44;
  static ROW_STRIDE = 46;
  static LIST_Y0 = 66;
  static NAME_MAX_W = 300;
  static FOOTER_Y = 404;
  static FOOTER_H = 64;
  static NO_SPHERE = "No sphere";
  static SPHERE_ORDER = ["Leadership", "Lore", "Spirit", "Tactics", "Neutral"];

  constructor(game, entries) {
    this.game = game;
    this.entries = entries;
    this.sphere = null;          // null = step 1 (pick a sphere)
    this.selected = null;
    this.page = 0;
    this.buttons = [];
  }

  _sphereOf(e) { return e.sphere || SideQuestPickModal.NO_SPHERE; }

  spheres() {
    const S = SideQuestPickModal;
    const counts = new Map();
    for (const e of this.entries) {
      const k = this._sphereOf(e);
      counts.set(k, (counts.get(k) ?? 0) + 1);
    }
    const out = S.SPHERE_ORDER.filter(k => counts.has(k)).map(k => [k, counts.get(k)]);
    const rest = [...counts.keys()]
      .filter(k => !S.SPHERE_ORDER.includes(k) && k !== S.NO_SPHERE).sort();
    for (const k of rest) out.push([k, counts.get(k)]);
    if (counts.has(S.NO_SPHERE)) out.push([S.NO_SPHERE, counts.get(S.NO_SPHERE)]);
    return out;
  }

  inSphere() { return this.entries.filter(e => this._sphereOf(e) === this.sphere); }

  _rows() { return this.sphere === null ? this.spheres() : this.inSphere(); }

  _pages() {
    return Math.max(1, Math.ceil(this._rows().length / SideQuestPickModal.PER_PAGE));
  }

  draw(ctx, game) {
    const S = SideQuestPickModal;
    this.buttons = [];
    rect(ctx, 0, 0, 480, 480, pal.bg);
    modalHeader(ctx, game, "Add Side Quest", this.buttons);

    if (!this.entries.length) {
      textCenter(ctx, "No side-quest catalog data available.", 240, 140, BODY, pal.dim);
      textCenter(ctx, "Use Manual entry below.", 240, 168, BODY, pal.dim);
    } else if (this.sphere === null) {
      this._drawSpheres(ctx);
    } else {
      this._drawQuests(ctx);
    }

    const manual = new Button(["manual"], 24, S.FOOTER_Y, 200, S.FOOTER_H);
    bevel(ctx, manual.x, manual.y, manual.w, manual.h, pal.btn, false, 3);
    textCenter(ctx, "Manual", manual.x + manual.w / 2, manual.y + 20, BODY, pal.tan);
    this.buttons.push(manual);

    if (this.entries.length && this.sphere !== null) {
      const add = new Button(["add"], 256, S.FOOTER_Y, 200, S.FOOTER_H);
      bevel(ctx, add.x, add.y, add.w, add.h, pal.btn_ok, false, 3);
      textCenter(ctx, "Add", add.x + add.w / 2, add.y + 20, BODY, pal.ok_fg);
      this.buttons.push(add);
    }
  }

  _pager(ctx, pages) {
    if (pages <= 1) return;
    const up = new Button(["older"], 12, 352, 150, 46);
    const dn = new Button(["newer"], 318, 352, 150, 46);
    bevel(ctx, up.x, up.y, up.w, up.h, pal.btn);
    textCenter(ctx, "Up", up.x + 75, up.y + 14, BODY, pal.tan);
    bevel(ctx, dn.x, dn.y, dn.w, dn.h, pal.btn);
    textCenter(ctx, "Down", dn.x + 75, dn.y + 14, BODY, pal.tan);
    textCenter(ctx, `${this.page + 1}/${pages}`, 240, 366, BODY, pal.muted);
    this.buttons.push(up, dn);
  }

  _drawSpheres(ctx) {
    const S = SideQuestPickModal;
    textLeft(ctx, "Pick a sphere - or enter manually.", 12, 46, BODY, pal.dim);
    const rows = this.spheres();
    const pages = this._pages();
    this.page = Math.min(this.page, pages - 1);
    const chunk = rows.slice(this.page * S.PER_PAGE, (this.page + 1) * S.PER_PAGE);
    let y = S.LIST_Y0;
    for (const [sphere, count] of chunk) {
      textLeft(ctx, truncateText(sphere, BODY, 320), 20, y + 13, BODY, pal.tan);
      const right = `${count} quest${count === 1 ? "" : "s"}`;
      textLeft(ctx, right, 436 - measureText(right, LABEL), y + 16, LABEL, pal.dim);
      ctx.fillStyle = pal.dim;
      ctx.beginPath();
      ctx.moveTo(450, y + 17); ctx.lineTo(450, y + 27); ctx.lineTo(455, y + 22);
      ctx.closePath(); ctx.fill();
      rect(ctx, 8, y + S.ROW_H, 456, 1, pal.border);
      this.buttons.push(new Button(["sphere", sphere], 8, y, 456, S.ROW_H));
      y += S.ROW_STRIDE;
    }
    this._pager(ctx, pages);
  }

  _drawQuests(ctx) {
    const S = SideQuestPickModal;
    textLeft(ctx, truncateText(`${this.sphere} - pick one, then Add.`, BODY, 456),
             12, 46, BODY, pal.dim);
    const rows = this.inSphere();
    const pages = this._pages();
    this.page = Math.min(this.page, pages - 1);
    const chunk = rows.slice(this.page * S.PER_PAGE, (this.page + 1) * S.PER_PAGE);
    let y = S.LIST_Y0;
    for (const e of chunk) {
      const on = e.id === this.selected;
      if (on) rect(ctx, 8, y, 456, S.ROW_H, pal.card_hi);
      pickRadio(ctx, 30, y + 22, on);
      textLeft(ctx, truncateText(e.name ?? "", BODY, S.NAME_MAX_W), 52, y + 13, BODY,
               on ? pal.tan : pal.muted);
      const pts = `${e.points ?? 0} pts`;
      textLeft(ctx, pts, 456 - measureText(pts, BODY), y + 13, BODY, on ? pal.gold : pal.tan);
      rect(ctx, 8, y + S.ROW_H, 456, 1, pal.border);
      this.buttons.push(new Button(["row", e.id], 8, y, 456, S.ROW_H));
      y += S.ROW_STRIDE;
    }
    this._pager(ctx, pages);
    const back = new Button(["back"], 12, S.FOOTER_Y - 56, 200, 44);
    bevel(ctx, back.x, back.y, back.w, back.h, pal.btn);
    textCenter(ctx, "< Spheres", back.x + back.w / 2, back.y + 14, BODY, pal.tan);
    this.buttons.push(back);
  }

  // Every exit reopens the Progress modal this was launched from.
  _leave() {
    this.game.pending_progress_detail = true;
    return "close";
  }

  onButton(btn) {
    const k = btn.id[0];
    if (k === "close") return this._leave();
    if (k === "sphere") {
      this.sphere = btn.id[1];
      const quests = this.inSphere();
      this.selected = quests.length ? quests[0].id : null;
      this.page = 0;
      return "redraw";
    }
    if (k === "back") { this.sphere = null; this.selected = null; this.page = 0; return "redraw"; }
    if (k === "row") { this.selected = btn.id[1]; return "redraw"; }
    if (k === "older") { this.page = Math.max(0, this.page - 1); return "redraw"; }
    if (k === "newer") { this.page = Math.min(this._pages() - 1, this.page + 1); return "redraw"; }
    if (k === "manual") {
      this.game.side_quests.push({ points: 0, progress: 0 });
      this.game.logEvent("Side quest added manually (progress view)");
      return this._leave();
    }
    if (k === "add") {
      const e = this.entries.find(x => x.id === this.selected);
      if (e) {
        const pts = e.points ?? 0;
        this.game.side_quests.push({ points: pts, progress: 0, name: e.name });
        this.game.logEvent(`Side quest added: ${e.name} (${pts} pts, progress view)`);
      }
      return this._leave();
    }
    return null;
  }
}
