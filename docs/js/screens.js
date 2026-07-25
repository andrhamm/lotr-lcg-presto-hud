// Port of ui/screen_*.py + ui/modals.py + ui/modal_counter.py.
// Structure mirrors the Python: every screen/modal draws into ctx, rebuilds
// .buttons, and handles taps in onButton returning the same protocol values.
import { pal, Button, rect, panel, bevel, textLeft, textCenter, button,
         stepper, wrapText, truncateText, ribbon, notePanel, drawWeather,
         disc, arcRuns, ring, token, wxSmall,
         DISPLAY, BODY, LABEL } from "./ui.js";
import { measureText } from "./metrics.js";
import * as icons from "./icons.js";
import { GameState, VIEW_ORDER, VIEW_LABELS, SETUP_TIP, REMINDER_DEFS, HEADINGS,
         DEFAULT_START_THREAT, MAX_PLAYERS, viewForStep, fmtMs } from "./gamestate.js";
import { PHASES, STEPS, step as phaseStep } from "./phases.js";
import { tipsFor } from "./quest_catalog.js";

export const HEADER_H = 40;
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
function doneButton(ctx) {
  bevel(ctx, 408, 4, 64, 32, pal.btn_ok);
  textCenter(ctx, "DONE", 440, 12, BODY, pal.ok_fg);
}

export function drawHeader(ctx, game, buttons, { highlight = null, title = null,
                                                 close = false, closeLeft = false,
                                                 roundLabel = null } = {}) {
  const roundLbl = roundLabel ?? `R${game.round} ${game.step}`;
  textLeft(ctx, roundLbl, 10, 12, BODY,
           (closeLeft || highlight === "log") ? pal.gold : pal.muted);
  const center = title ?? (VIEW_LABELS[game.view] ?? phaseStep(game.step).phase);
  const scale = center.length > 12 ? BODY : DISPLAY;
  textCenter(ctx, center, 240, scale === BODY ? 12 : 8, scale, pal.gold);
  if (close) {
    doneButton(ctx);
  } else {
    textLeft(ctx, "Set.", 480 - 10 - measureText("Set.", BODY), 12, BODY,
             highlight === "settings" ? pal.gold : pal.muted);
  }
  rect(ctx, 0, HEADER_H, 480, 1, pal.border);
  if (close) {
    buttons.push(new Button(["nav", "close"], 408, 4, 64, 32));
  } else if (closeLeft) {
    buttons.push(new Button(["nav", "close"], 0, 0, 150, HEADER_H));
    buttons.push(new Button(["nav", "settings"], 330, 0, 150, HEADER_H));
  } else {
    buttons.push(new Button(["nav", "log"], 0, 0, 150, HEADER_H));
    buttons.push(new Button(["nav", "phases"], 150, 0, 180, HEADER_H));
    buttons.push(new Button(["nav", "settings"], 330, 0, 150, HEADER_H));
  }
}

// Shared header for full-screen modals: round id upper-left, centred title,
// and a DONE button upper-right that pushes id ["close"] (each modal's
// onButton maps "close" to its own commit-and-dismiss / dismiss semantics).
export function modalHeader(ctx, game, title, buttons) {
  const roundLbl = `R${game.round} ${game.step}`;
  textLeft(ctx, roundLbl, 10, 12, BODY, pal.muted);
  textCenter(ctx, title, 240, 12, BODY, pal.gold);
  rect(ctx, 0, HEADER_H, 480, 1, pal.border);
  doneButton(ctx);
  buttons.push(new Button(["close"], 408, 4, 64, 32));
}

// Circular -/+ (or similar single-glyph) button: btn disc + light affordance
// ring + centred glyph. The drawn circle is small (r~10-11); callers push a
// >=24px Button separately for the actual tap target, centred on (cx, cy).
export function circBtn(ctx, cx, cy, r, glyph, pen = pal.tan) {
  disc(ctx, cx, cy, r, pal.btn);
  arcRuns(ctx, cx, cy, r, r - 2, 0, 360, pal.bevel_l);
  textCenter(ctx, glyph, cx, Math.round(cy - 8), BODY, pen);
}

export function drawNotifPie(ctx, cx, cy, r, frac, color = "amber") {
  rect(ctx, cx - r - 2, cy - r - 2, 2 * r + 4, 2 * r + 4, pal.card_hi);
  const steps = 24;
  const remaining = Math.max(0, Math.min(steps, Math.round(frac * steps)));
  ctx.fillStyle = pal[color];
  const start = -90 + (steps - remaining) * (360 / steps);
  for (let i = 0; i < remaining; i++) {
    const a0 = (start + i * (360 / steps)) * Math.PI / 180;
    const a1 = (start + (i + 1) * (360 / steps)) * Math.PI / 180;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(cx + r * Math.cos(a0), cy + r * Math.sin(a0));
    ctx.lineTo(cx + r * Math.cos(a1), cy + r * Math.sin(a1));
    ctx.closePath();
    ctx.fill();
  }
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
  static ICONS = { threat: ["THREAT", "red"], willpower: ["WILLPOWER", "gold"] };

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
      const [maskName, penName] = CounterModal.ICONS[this.icon];
      const w = measureText(this.title, DISPLAY);
      const ix = Math.floor(240 - w / 2 - 30);
      icons.drawIcon(ctx, icons[maskName], ix, 30, pal[penName]);
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
    if (k === "cancel") return "cancel";
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
      const mn = new Button(["pts", i, -1], 250, y + 6, 44, 44);
      const pl = new Button(["pts", i, 1], 302, y + 6, 44, 44);
      const rm = new Button(["rm", i], 400, y + 6, 44, 44);
      button(ctx, this.buttons, mn, "-", DISPLAY);
      button(ctx, this.buttons, pl, "+", DISPLAY);
      bevel(ctx, rm.x, rm.y, rm.w, rm.h, pal.btn_no);
      textCenter(ctx, "x", rm.x + 22, rm.y + 10, DISPLAY, pal.no_fg);
      this.buttons.push(mn, pl, rm);
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
    if (k === "add") { this.game.side_quests.push({ points: 4, progress: 0 }); return null; }
    if (k === "pts") {
      const s = this.game.side_quests[btn.id[1]];
      s.points = Math.max(1, Math.min(30, s.points + btn.id[2]));
      return null;
    }
    if (k === "rm") { this.game.side_quests.splice(btn.id[1], 1); return null; }
    if (k === "save") return "close";
    return null;
  }
}

export class LocationPickModal {
  constructor(game, mode = "new") {
    this.game = game;
    this.mode = mode;
    this.pts = 3;
    this.contrib = 2;
    this.buttons = [];
  }
  draw(ctx) {
    this.buttons = [];
    rect(ctx, 0, 0, 480, 480, pal.bg);
    const title = this.mode === "new" ? "Travel to new location" : "Change active location";
    textCenter(ctx, title, 240, 30, DISPLAY, pal.gold);
    const loc = this.game.active_location;
    if (this.mode === "change" && loc) {
      textCenter(ctx, `current ${loc.progress}/${loc.points} will be discarded`, 240, 80, BODY, pal.no_fg);
    }
    textLeft(ctx, "Quest points", 60, 190, BODY, pal.tan);
    stepper(ctx, this.buttons, ["pts", -1], ["pts", 1], 250, 174, String(this.pts), 170, 60);
    icons.drawIcon(ctx, icons.THREAT, 60, 262, pal.red);
    textLeft(ctx, "Contribution", 88, 266, BODY, pal.tan);
    stepper(ctx, this.buttons, ["ctr", -1], ["ctr", 1], 250, 250, String(this.contrib), 170, 60);
    textLeft(ctx, "subtracted from the staging area on travel", 60, 318, BODY, pal.dim);
    footer(ctx, this.buttons, "Travel");
  }
  onButton(btn) {
    const k = btn.id[0];
    if (k === "pts") { this.pts = Math.max(1, Math.min(30, this.pts + btn.id[1])); return null; }
    if (k === "ctr") { this.contrib = Math.max(0, Math.min(9, this.contrib + btn.id[1])); return null; }
    if (k === "save") {
      if (this.mode === "new" && !this.game.active_location) {
        this.game.travelTo(this.pts, this.contrib);
      } else {
        this.game.changeLocation(this.pts, this.contrib);
      }
      return "close";
    }
    if (k === "cancel") return "cancel";
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
  constructor(game) {
    this.game = game;
    this.buttons = [];
    this.edit = null;   // { i, stat, state: CounterState } while the inline pad is open
  }

  _openEdit(i, stat) {
    const game = this.game;
    const cur = stat === "threat" ? game.players[i].threat : game.players[i].commit;
    if (stat === "willpower") game.touchCommit(i);
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
    circBtn(ctx, cx - 30, cy, 11, "-");
    circBtn(ctx, cx + 30, cy, 11, "+");
    token(ctx, cx, cy, 14, 2, value, pal.value, frac, ringFill, pal.dim);
    this.buttons.push(
      new Button([key, i, -1], cx - 30 - 12, cy - 12, 24, 24),
      new Button([key, i, "edit"], cx - 12, cy - 12, 24, 24),
      new Button([key, i, 1], cx + 30 - 12, cy - 12, 24, 24),
    );
  }

  draw(ctx, game) {
    this.buttons = [];
    rect(ctx, 0, 0, 480, 480, pal.bg);
    if (this.edit) { this._drawEdit(ctx); return; }
    modalHeader(ctx, game, "Players", this.buttons);
    const threatX = 150, willX = 330, labelX = 32;
    textCenter(ctx, "THREAT", threatX, 46, LABEL, pal.dim);
    textCenter(ctx, "WILLPOWER", willX, 46, LABEL, pal.dim);
    game.players.forEach((p, i) => {
      const cy = 66 + i * 56;
      const label = `P${i + 1}`;
      if (i === game.first_player) {
        rect(ctx, labelX - 18, cy - 11, 36, 22, pal.gold);
        textCenter(ctx, label, labelX, cy - 8, BODY, pal.bg, false);
      } else {
        textCenter(ctx, label, labelX, cy - 8, BODY, pal.tan);
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
        this.game.touchCommit(i);
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

export class RemindersModal {
  constructor(game) { this.game = game; this.buttons = []; }
  draw(ctx) {
    this.buttons = [];
    rect(ctx, 0, 0, 480, 480, pal.bg);
    modalHeader(ctx, this.game, "Encounter Reminders", this.buttons);
    let y = 56;
    for (const [key, label, view] of REMINDER_DEFS) {
      const on = this.game.reminders[key];
      const row = new Button(["tog", key], 16, y, 448, 62);
      bevel(ctx, row.x, row.y, row.w, row.h, on ? pal.card_hi : pal.card);
      rect(ctx, 30, y + 17, 28, 28, pal.well);
      if (on) rect(ctx, 36, y + 23, 16, 16, pal.ok_fg);
      textLeft(ctx, label, 76, y + 12, BODY, on ? pal.tan : pal.muted);
      // "At <view>", not "Notifies at <view>": at BODY the archery row
      // ("Combat (Shadow Cards)" plus the staging condition) runs 22px past
      // the row at the longer wording. Shortening the copy is the fix;
      // shrinking the caption is not (see the design system spec).
      if (key === "archery") {
        const part1 = `At ${VIEW_LABELS[view]} if staging `;
        const w1 = measureText(part1, BODY);
        textLeft(ctx, part1, 76, y + 38, BODY, pal.dim);
        icons.drawIcon(ctx, icons.THREAT_SM, 76 + w1 + 2, y + 38, pal.dim);
        textLeft(ctx, "> 0", 76 + w1 + 18, y + 38, BODY, pal.dim);
      } else {
        textLeft(ctx, `At ${VIEW_LABELS[view]}`, 76, y + 38, BODY, pal.dim);
      }
      this.buttons.push(row);
      y += 70;
    }
  }
  onButton(btn) {
    const k = btn.id[0];
    if (k === "tog") {
      this.game.reminders[btn.id[1]] = !this.game.reminders[btn.id[1]];
      return null;
    }
    if (k === "close") return "close";
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
  // All questing progress in one place: main quest, active location (or a
  // slot to add one) and each side quest, each as Current (live progress
  // ring) | Target (dim, no fill) circular editors. Non-main rows add
  // complete/remove icon buttons; removing the Location opens an in-modal
  // prompt (Replaced / To staging / Discard - a modal cannot open another,
  // so this is state on `this`, not a nested modal). Weather radios replace
  // the old heading stepper when sailing. A bottom-anchored chart summarizes
  // quest_history by round. Silent progress/points edits are batched into
  // one summary log line per field on close.
  static ROWS_Y0 = 62;
  static ROW_H = 38;

  constructor(game) {
    this.game = game;
    this.buttons = [];
    this.locPrompt = null;   // { stage: "choose"|"pts"|"contrib", ... } or null
    this._snap = this._snapshot();
  }

  _snapshot() {
    const g = this.game;
    return {
      q: { p: g.quest.progress, t: g.quest.points },
      loc: g.active_location ? { p: g.active_location.progress, t: g.active_location.points } : null,
      sqLen: g.side_quests.length,
      sq: g.side_quests.map(s => ({ p: s.progress, t: s.points })),
    };
  }

  _items() {
    const g = this.game;
    const items = [{ kind: "q", name: `Quest ${g.questLabel()}`, removable: false,
      advanceable: g.stages.length > 0 }];
    items.push(g.active_location
      ? { kind: "l", name: "Location", removable: true }
      : { kind: "l_add" });
    // Prefer the catalog name (SideQuestPickModal, M4-B sidequest Task 2)
    // when present; old saves and manual entries have no "name" key at
    // all, so this stays "Side Quest N" for them.
    g.side_quests.forEach((s, i) =>
      items.push({ kind: "s", idx: i, name: s.name || `Side Quest ${i + 1}`, removable: true }));
    return items;
  }

  // Circular -/+ flanking a value token: Current shows a live progress ring
  // (token()); Target is dim-only (well + full dim ring, no fill) so the two
  // columns read at a glance without a progress bar implying a "target".
  _valEditor2(ctx, cx, cy, value, frac, progressRing, idMinus, idPlus) {
    circBtn(ctx, cx - 30, cy, 10, "-");
    if (progressRing) {
      token(ctx, cx, cy, 13, 2, value, pal.gold, frac, pal.gold, pal.dim);
    } else {
      disc(ctx, cx, cy, 13, pal.well);
      arcRuns(ctx, cx, cy, 13, 11, 0, 360, pal.dim);
      textCenter(ctx, String(value), cx, Math.round(cy - 8), BODY, pal.gold);
    }
    circBtn(ctx, cx + 30, cy, 10, "+");
    this.buttons.push(
      new Button(idMinus, cx - 30 - 12, cy - 12, 24, 24),
      new Button(idPlus, cx + 30 - 12, cy - 12, 24, 24),
    );
  }

  // Small circular action: "x" = remove (red X, reuses circBtn), "done" =
  // mark complete (green pennant flag - a target reached its max), "adv" =
  // manually trigger the guided resolution flow (gold chevron -
  // conditional/0-point stages have no numeric gate to cross, so this is
  // the only way in).
  _iconBtn(ctx, cx, cy, r, kind, id) {
    if (kind === "x") {
      circBtn(ctx, cx, cy, r, "X", pal.red);
    } else if (kind === "adv") {
      disc(ctx, cx, cy, r, pal.btn);
      arcRuns(ctx, cx, cy, r, r - 2, 0, 360, pal.bevel_l);
      ctx.fillStyle = pal.gold;
      ctx.beginPath();
      ctx.moveTo(cx - 3, cy - 5);
      ctx.lineTo(cx - 3, cy + 5);
      ctx.lineTo(cx + 5, cy);
      ctx.closePath();
      ctx.fill();
    } else {
      disc(ctx, cx, cy, r, pal.btn);
      arcRuns(ctx, cx, cy, r, r - 2, 0, 360, pal.bevel_l);
      rect(ctx, cx - 4, cy - 5, 1, 10, pal.green);
      ctx.fillStyle = pal.green;
      ctx.beginPath();
      ctx.moveTo(cx - 3, cy - 5);
      ctx.lineTo(cx + 4, cy - 3);
      ctx.lineTo(cx - 3, cy - 1);
      ctx.closePath();
      ctx.fill();
    }
    this.buttons.push(new Button(id, cx - 12, cy - 12, 24, 24));
  }

  _row(ctx, it, y) {
    const g = this.game;
    const cy = y + 8;
    if (it.kind === "l_add") {
      const b = new Button(["addloc"], 12, y + 7, 140, 24);
      bevel(ctx, b.x, b.y, b.w, b.h, pal.btn);
      textCenter(ctx, "+ Add location", b.x + b.w / 2, b.y + 5, BODY, pal.tan);
      this.buttons.push(b);
      return;
    }
    let prog, pts, pfx, idx;
    if (it.kind === "q") { prog = g.quest.progress; pts = g.quest.points; pfx = "q"; idx = null; }
    else if (it.kind === "l") { prog = g.active_location.progress; pts = g.active_location.points; pfx = "l"; idx = null; }
    else { const s = g.side_quests[it.idx]; prog = s.progress; pts = s.points; pfx = "s"; idx = it.idx; }
    // The quest row's title doubles as a tap target opening the read-only
    // QuestCardModal (M4-B, second entry point) - gold ink hints it's
    // interactive, matching this row alone (Location/Side Quest titles stay
    // plain). Pushed AFTER the Current/Target editors below so their hit
    // regions win on any overlap; the button's own bounds (x 12-130) sit
    // left of the Current editor's leftmost hit-box (x=136) by construction,
    // so there should be no real overlap to arbitrate.
    const questCardTappable = it.kind === "q" && g.stages.length > 0;
    // 118px matches the quest_card tap target's fixed width below (and the
    // room left before the Current editor's leftmost hit-box at x=136) - a
    // real catalog side-quest name (up to ~20 chars) can otherwise run into
    // the Current/Target editors, unlike the old always-short generic
    // labels ("Quest 1A", "Location", "Side Quest 3").
    const nameS = truncateText(it.name, BODY, 118);
    textLeft(ctx, nameS, 12, y, BODY, questCardTappable ? pal.gold : pal.tan);
    this._valEditor2(ctx, 178, cy, prog, pts ? prog / pts : 0, true, [pfx + "P-", idx], [pfx + "P+", idx]);
    this._valEditor2(ctx, 300, cy, pts, 0, false, [pfx + "T-", idx], [pfx + "T+", idx]);
    if (it.removable) {
      this._iconBtn(ctx, 400, cy, 11, "done", [pfx + "done", idx]);
      this._iconBtn(ctx, 436, cy, 11, "x", [pfx + "X", idx]);
    }
    if (it.advanceable) {
      this._iconBtn(ctx, 400, cy, 11, "adv", ["qAdv"]);
    }
    if (questCardTappable) {
      this.buttons.push(new Button(["quest_card"], 12, y, 118, QuestingProgressModal.ROW_H));
    }
  }

  draw(ctx) {
    this.buttons = [];
    rect(ctx, 0, 0, 480, 480, pal.bg);
    if (this.locPrompt) { this._drawLocPrompt(ctx); return; }
    modalHeader(ctx, this.game, "Progress", this.buttons);

    textLeft(ctx, "QUEST POINTS", 12, 48, LABEL, pal.muted);
    textCenter(ctx, "CURRENT", 178, 48, LABEL, pal.dim);
    textCenter(ctx, "TARGET", 300, 48, LABEL, pal.dim);

    const items = this._items();
    items.forEach((it, i) => this._row(ctx, it, QuestingProgressModal.ROWS_Y0 + i * QuestingProgressModal.ROW_H));
    const n = items.length;

    const addY = QuestingProgressModal.ROWS_Y0 + n * QuestingProgressModal.ROW_H - 4;
    const add = new Button(["add"], 12, addY, 120, 24);
    bevel(ctx, add.x, add.y, add.w, add.h, pal.btn);
    textCenter(ctx, "+ Side quest", add.x + add.w / 2, add.y + 5, BODY, pal.tan);
    this.buttons.push(add);

    if (this.game.sailing) {
      const headingY = QuestingProgressModal.ROWS_Y0 + n * QuestingProgressModal.ROW_H + 34;
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

    this._drawChart(ctx);
  }

  // Absolutely positioned near the bottom regardless of how many rows are
  // above (quest/location/side-quest count varies) - it never moves.
  _drawChart(ctx) {
    const cy0 = 344;
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
      textCenter(ctx, `R${r.round}`, x0 + i * stride + Math.floor(stride / 2), cy0, LABEL, pal.dim));
    const HDG_PEN = [pal.gold, pal.amber, pal.amber, pal.red];
    const rows = [
      [icons.WILLPOWER, pal.gold, false, r => [String(r.willpower), pal.gold]],
      [icons.THREAT, pal.outline, true, r => [String(r.staging), pal.outline]],
      [icons.TRAIL, pal.green, false, r => {
        const signed = r.outcome === "fail" ? -r.n : r.n;
        return [signed > 0 ? `+${signed}` : String(signed), signed > 0 ? pal.green : pal.red];
      }],
    ];
    if (this.game.sailing) {
      rows.push([icons.WHEEL, pal.gold, false, r => [String(r.heading), HDG_PEN[r.heading]]]);
    }
    let ry = cy0 + 14;
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

  _drawLocPrompt(ctx) {
    const lp = this.locPrompt;
    if (lp.stage === "choose") { this._drawLocChoose(ctx); return; }
    if (lp.stage === "pts") { this._drawLocPts(ctx); return; }
    this._drawLocContrib(ctx);
  }

  _drawLocChoose(ctx) {
    const loc = this.game.active_location;
    textCenter(ctx, "Location removed", 240, 30, DISPLAY, pal.gold);
    textCenter(ctx, "What happened to it?", 240, 70, BODY, pal.tan);
    textCenter(ctx, `${loc.progress}/${loc.points} progress will be discarded`, 240, 94, BODY, pal.dim);
    const opt = (y, id, label, sub) => {
      const b = new Button([id], 24, y, 432, 64);
      bevel(ctx, b.x, b.y, b.w, b.h, pal.btn, false, 3);
      textCenter(ctx, label, 240, y + 12, DISPLAY, pal.tan);
      textCenter(ctx, sub, 240, y + 42, BODY, pal.dim);
      this.buttons.push(b);
    };
    opt(120, "lp_replaced", "Replaced", "enter the new location's quest points");
    opt(196, "lp_staging", "To staging", "its threat returns to the staging area");
    opt(272, "lp_discard", "Discard", "no replacement");
    const cancel = new Button(["lp_cancel"], 24, 356, 432, 56);
    bevel(ctx, cancel.x, cancel.y, cancel.w, cancel.h, pal.btn_no, false, 3);
    textCenter(ctx, "Cancel", 240, cancel.y + 18, BODY, pal.no_fg);
    this.buttons.push(cancel);
  }

  _drawLocPts(ctx) {
    textCenter(ctx, "Replace location", 240, 30, DISPLAY, pal.gold);
    textLeft(ctx, "Quest points", 60, 216, BODY, pal.tan);
    stepper(ctx, this.buttons, ["lp_pts", -1], ["lp_pts", 1], 250, 200, String(this.locPrompt.pts), 170, 60);
    footer(ctx, this.buttons, "Confirm");
  }

  _drawLocContrib(ctx) {
    textCenter(ctx, "Location to staging", 240, 30, DISPLAY, pal.gold);
    icons.drawIcon(ctx, icons.THREAT, 60, 208, pal.red);
    textLeft(ctx, "Contribution", 88, 216, BODY, pal.tan);
    stepper(ctx, this.buttons, ["lp_ctr", -1], ["lp_ctr", 1], 250, 200,
            String(this.locPrompt.state.preview), 170, 60);
    textLeft(ctx, "added to the staging area", 60, 270, BODY, pal.dim);
    footer(ctx, this.buttons, "Confirm");
  }

  _clampAdj(cur, d) { return Math.max(0, Math.min(99, cur + d)); }

  onButton(btn) {
    const g = this.game;
    if (this.locPrompt) return this._onLocPromptButton(btn);
    const [k, a] = btn.id;
    if (k === "qP-" || k === "qP+") { g.quest.progress = this._clampAdj(g.quest.progress, k.endsWith("+") ? 1 : -1); return null; }
    if (k === "qT-" || k === "qT+") { g.quest.points = this._clampAdj(g.quest.points, k.endsWith("+") ? 1 : -1); return null; }
    if (k === "lP-" || k === "lP+") {
      g.active_location.progress = this._clampAdj(g.active_location.progress, k.endsWith("+") ? 1 : -1);
      // Catalog games defer this to the guided resolution flow (close-time
      // needsResolution() check + ResolutionModal's "location" step,
      // B-resolve Task 3) so overflow excess gets credited to the quest
      // card (rulebook p.15) via resolveLocationOverflow() instead of
      // silently discarded. Custom games have no guided flow to defer to,
      // so they keep the immediate auto-explore they've always had.
      if (!g.stages.length) g.exploreLocationIfDone();
      return null;
    }
    if (k === "lT-" || k === "lT+") { g.active_location.points = this._clampAdj(g.active_location.points, k.endsWith("+") ? 1 : -1); return null; }
    if (k === "ldone") {
      g.logEvent("Active location Explored");
      g.active_location = null;
      this._snap = this._snapshot();
      return null;
    }
    if (k === "lX") { this.locPrompt = { stage: "choose" }; return null; }
    if (k === "sP-" || k === "sP+") { const s = g.side_quests[a]; s.progress = this._clampAdj(s.progress, k.endsWith("+") ? 1 : -1); return null; }
    if (k === "sT-" || k === "sT+") { const s = g.side_quests[a]; s.points = this._clampAdj(s.points, k.endsWith("+") ? 1 : -1); return null; }
    if (k === "sdone") {
      g.logEvent(`Side quest ${a + 1} completed`);
      g.side_quests.splice(a, 1);
      this._snap = this._snapshot();
      return null;
    }
    if (k === "sX") {
      g.logEvent(`Side quest ${a + 1} removed`);
      g.side_quests.splice(a, 1);
      this._snap = this._snapshot();
      return null;
    }
    if (k === "add") {
      // The router holds one modal at a time (no stacking) - close this one
      // (flushing any pending edits, same as a normal "close") and flag
      // that SideQuestPickModal should open on the next tick, same
      // pending-flag pattern as "quest_card" below. The picker needs a
      // catalog fetch that onButton can't await mid-tap without breaking
      // that invariant.
      g.pending_side_quest_pick = true;
      this._logChanges();
      return "close";
    }
    if (k === "addloc") {
      g.active_location = { points: 3, progress: 0 };
      g.logEvent("Active location added (card effect)");
      this._snap = this._snapshot();
      return null;
    }
    if (k === "hd_set") {
      if (a !== g.heading) g.shiftHeading(a - g.heading, "progress view");
      return null;
    }
    if (k === "quest_card") {
      // The router holds one modal at a time (no stacking) - close this one
      // (flushing any pending edits, same as a normal "close") and flag that
      // QuestCardModal should open on the next tick. See main.js's
      // setInterval, which checks pending_quest_card once modal is null.
      g.pending_quest_card = true;
      this._logChanges();
      return "close";
    }
    if (k === "qAdv") {
      // Manually trigger the guided resolution flow even though the
      // numeric target hasn't been reached - the only way in for
      // conditional/0-point stages, which have no gate to cross. See
      // main.js's setInterval, which checks pending_resolution once modal
      // is null (same pending-flag pattern as pending_quest_card above).
      g.pending_resolution = "forced";
      this._logChanges();
      return "close";
    }
    if (k === "close") {
      this._logChanges();
      // Catalog games: any overflow (location/quest/side-quest) is safe to
      // defer to ResolutionModal, since every one of its steps has a real
      // close/dismiss escape hatch. Custom games have no ResolutionModal -
      // their only fallback is the legacy StageCompleteModal, which has no
      // safe "cancel" (only "go", committing a stage/side/points change, or
      // "win") - so their trigger must stay scoped to the quest itself
      // overflowing (what StageCompleteModal has always been opened for),
      // not needsResolution()'s broader check. A side-quest-only overflow
      // must not force a custom-game player into that advance-or-victory
      // dilemma.
      if (g.stages.length) {
        if (g.needsResolution()) g.pending_resolution = "auto";
      } else if (g.quest.points > 0 && g.quest.progress >= g.quest.points) {
        g.pending_resolution = "auto";
      }
      return "close";
    }
    return null;
  }

  _onLocPromptButton(btn) {
    const g = this.game;
    const k = btn.id[0];
    const lp = this.locPrompt;
    if (lp.stage === "choose") {
      if (k === "lp_replaced") { this.locPrompt = { stage: "pts", pts: 3 }; return null; }
      if (k === "lp_staging") { this.locPrompt = { stage: "contrib", state: new CounterState(2, 0, 9) }; return null; }
      if (k === "lp_discard") {
        g.logEvent("Active location removed");
        g.active_location = null;
        this._snap = this._snapshot();
        this.locPrompt = null;
        return null;
      }
      if (k === "lp_cancel") { this.locPrompt = null; return null; }
      return null;
    }
    // pts / contrib sub-stages share the generic footer() ids
    if (k === "cancel") { this.locPrompt = { stage: "choose" }; return null; }
    if (k === "save") {
      if (lp.stage === "pts") {
        g.changeLocation(lp.pts, 0);
      } else {
        lp.state.confirm();
        const v = lp.state.value;
        g.staging += v;
        g.active_location = null;
        g.logEvent(`Active location to staging (+${v} threat)`);
      }
      this._snap = this._snapshot();
      this.locPrompt = null;
      return null;
    }
    if (k === "lp_pts") { lp.pts = Math.max(1, Math.min(30, lp.pts + btn.id[1])); return null; }
    if (k === "lp_ctr") { lp.state.tap(btn.id[1]); return null; }
    return null;
  }

  _logChanges() {
    const s = this._snap, g = this.game;
    if (g.quest.progress !== s.q.p || g.quest.points !== s.q.t)
      g.logEvent(`Quest ${g.questLabel()} set ${g.quest.progress}/${g.quest.points} (progress view)`);
    if (s.loc && g.active_location &&
        (g.active_location.progress !== s.loc.p || g.active_location.points !== s.loc.t))
      g.logEvent(`Active location set ${g.active_location.progress}/${g.active_location.points} (progress view)`);
    if (g.side_quests.length === s.sqLen) {
      g.side_quests.forEach((sq, i) => {
        if (sq.progress !== s.sq[i].p || sq.points !== s.sq[i].t)
          g.logEvent(`Side quest ${i + 1} set ${sq.progress}/${sq.points} (progress view)`);
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

export class StageCompleteModal {
  constructor(game) {
    this.game = game;
    const ps = game.pending_stage ?? { cleared: "?", excess: 0 };
    this.cleared = ps.cleared;
    this.excess = ps.excess;
    this.n = game.quest.stage_n;
    this.side = game.quest.side;
    this.pts = 0;
    this.buttons = [];
  }
  draw(ctx) {
    this.buttons = [];
    rect(ctx, 0, 0, 480, 480, pal.bg);
    textCenter(ctx, `Quest Stage ${this.cleared} cleared!`, 240, 26, DISPLAY, pal.gold);
    let y = 74;
    textCenter(ctx, "Set up the next stage", 240, y, BODY, pal.tan);
    y += 40;
    textLeft(ctx, "Stage", 30, y + 14, BODY, pal.tan);
    stepper(ctx, this.buttons, ["n", -1], ["n", 1], 160, y, String(this.n), 130, 52);
    // side cycles A-H (multi-variant quests go beyond A/B - DragnCards data)
    stepper(ctx, this.buttons, ["side", -1], ["side", 1], 316, y, this.side, 144, 52);
    y += 76;
    textLeft(ctx, "Quest points", 30, y + 14, BODY, pal.tan);
    stepper(ctx, this.buttons, ["pts", -1], ["pts", 1], 240, y, String(this.pts), 210, 52);
    y += 90;
    const go = new Button(["go"], 30, y, 420, 60);
    bevel(ctx, go.x, go.y, go.w, go.h, pal.btn_ok, false, 3);
    textCenter(ctx, `Continue to ${this.n}${this.side}`, 240, y + 20, BODY, pal.ok_fg);
    this.buttons.push(go);
    y += 74;
    const win = new Button(["win"], 30, y, 420, 60);
    bevel(ctx, win.x, win.y, win.w, win.h, pal.card_hi, false, 3);
    textCenter(ctx, "That was the final stage - Victory!", 240, y + 20, BODY, pal.gold);
    this.buttons.push(win);
  }
  onButton(btn) {
    const k = btn.id[0];
    if (k === "n") { this.n = Math.max(1, Math.min(9, this.n + btn.id[1])); return null; }
    if (k === "side") {
      const i = (this.side.charCodeAt(0) - 65 + btn.id[1] + 8) % 8;   // cycle A-H
      this.side = String.fromCharCode(65 + i);
      return null;
    }
    if (k === "pts") { this.pts = Math.max(0, Math.min(30, this.pts + btn.id[1])); return null; }
    if (k === "go") {
      const g = this.game;
      g.quest.stage_n = this.n;
      g.quest.side = this.side;
      g.quest.points = this.pts;
      g.pending_stage = null;
      g.logEvent(`Advance to stage ${g.questLabel()} (needs ${this.pts})`);
      return "close";
    }
    if (k === "win") {
      this.game.pending_stage = null;
      this.game.setGameOver("victory");
      return "close";
    }
    return null;
  }
}

// Guided post-edit/post-success resolution: location -> quest advance
// (branch/reveal/flip) -> side quests, one explicit step at a time,
// re-deriving what's next from live game state after every action. Opened
// only for catalog games (game.stages non-empty) - custom games keep the
// legacy StageCompleteModal. See docs/superpowers/plans/
// 2026-07-24-quest-picker-bresolve.md for the full rationale, including why
// at most one stage advance can ever happen per pass.
export class ResolutionModal {
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
      const faceA = card.faces.find(f => f.side === "A") ?? {};
      return { kind: "reveal", stage_n: g.quest.stage_n, face_a: faceA,
               next_points: card.questPoints };
    }
    const nxtIdx = g.stage_idx + 1;
    if (nxtIdx >= g.stages.length) {
      return { kind: "victory", cleared: g.questLabel() };
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
    const loc = g.active_location;
    if (loc && loc.points > 0 && loc.progress >= loc.points) {
      return { kind: "location", progress: loc.progress, points: loc.points };
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

  _drawReveal(ctx, st) {
    textCenter(ctx, `STAGE ${st.stage_n} REVEALED`, 240, 64, BODY, pal.amber);
    const name = truncateText(st.face_a.name || "", DISPLAY, 432);
    textCenter(ctx, name, 240, 92, DISPLAY, pal.gold);
    const tipX = 24, tipW = 432, tipY = 130;
    const ribbonH = 22, padTop = 10, lineH = 24, padBottom = 10, maxLines = 5;
    const raw = st.face_a.text;
    const body = raw ? raw : "No setup instructions for this stage.";
    const lines = wrapText(body, BODY, tipW - 28).slice(0, maxLines);
    const tipH = ribbonH + padTop + lines.length * lineH + padBottom;
    rect(ctx, tipX, tipY, tipW, tipH, pal.border_gold);
    rect(ctx, tipX + 2, tipY + 2, tipW - 4, tipH - 4, pal.bg);
    rect(ctx, tipX + 4, tipY + 4, tipW - 8, tipH - 8, pal.border_gold);
    rect(ctx, tipX + 6, tipY + 6, tipW - 12, tipH - 12, pal.scroll);
    rect(ctx, tipX, tipY, tipW, ribbonH, pal.border_gold);
    textLeft(ctx, "STAGE ADVANCE - RESOLVE NOW", tipX + 10, tipY + 6, LABEL, pal.bg, false);
    let ly = tipY + ribbonH + padTop;
    for (const ln of lines) {
      textLeft(ctx, ln, tipX + 14, ly, BODY, pal.tan);
      ly += lineH;
    }
    this._cta(ctx, `Flip to Side B  ->  ${st.next_points} qp`, ["do_flip"]);
  }

  _drawLocation(ctx, st) {
    textCenter(ctx, "Location Explored", 240, 90, DISPLAY, pal.gold);
    textCenter(ctx, `${st.progress}/${st.points} progress`, 240, 130, BODY, pal.tan);
    const excess = st.progress - st.points;
    if (excess) {
      textCenter(ctx, `${excess} excess -> quest card`, 240, 160, BODY, pal.amber);
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
      const bFace = card.faces.find(f => f.side === "B") ?? {};
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

  _drawVictory(ctx, st) {
    textCenter(ctx, `Quest ${st.cleared} cleared`, 240, 70, BODY, pal.tan);
    textCenter(ctx, "That was the final stage!", 240, 110, DISPLAY, pal.gold);
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
    if (k === "continue_without_victory") { this.step = this._derive(); return "redraw"; }
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

export class QuestConfigModal {
  constructor(game) {
    this.game = game;
    this.q = { ...game.quest };
    this.sail = game.sailing;
    this.buttons = [];
  }
  draw(ctx) {
    this.buttons = [];
    rect(ctx, 0, 0, 480, 480, pal.bg);
    textCenter(ctx, `Quest  ${this.q.stage_n}${this.q.side}`, 240, 24, DISPLAY, pal.gold);
    textLeft(ctx, "Stage number", 30, 84, BODY, pal.tan);
    stepper(ctx, this.buttons, ["n", -1], ["n", 1], 300, 70, String(this.q.stage_n), 150, 52);
    textLeft(ctx, "Side", 30, 156, BODY, pal.tan);
    stepper(ctx, this.buttons, ["side", -1], ["side", 1], 300, 142, this.q.side, 150, 52);
    textLeft(ctx, "Quest points", 30, 228, BODY, pal.tan);
    stepper(ctx, this.buttons, ["pts", -1], ["pts", 1], 300, 214, String(this.q.points), 150, 52);
    textLeft(ctx, "Sailing quest", 30, 296, BODY, pal.tan);
    icons.drawIcon(ctx, icons.WHEEL, 176, 292, this.sail ? pal.gold : pal.dim);
    const sb = new Button(["sail"], 300, 284, 150, 48);
    panel(ctx, sb.x, sb.y, sb.w, sb.h, this.sail ? pal.gold : pal.btn);
    textCenter(ctx, this.sail ? "On" : "Off", sb.x + 75, sb.y + 14, BODY,
               this.sail ? pal.bg : pal.tan, false);
    this.buttons.push(sb);
    const adv = new Button(["adv"], 30, 344, 420, 48);
    bevel(ctx, adv.x, adv.y, adv.w, adv.h, pal.btn);
    textCenter(ctx, "Advance stage (progress -> 0)", adv.x + 210, adv.y + 14, BODY, pal.tan);
    this.buttons.push(adv);
    footer(ctx, this.buttons);
  }
  onButton(btn) {
    const k = btn.id[0];
    if (k === "n") { this.q.stage_n = Math.max(1, Math.min(9, this.q.stage_n + btn.id[1])); return null; }
    if (k === "side") {
      const i = (this.q.side.charCodeAt(0) - 65 + btn.id[1] + 8) % 8;   // cycle A-H
      this.q.side = String.fromCharCode(65 + i);
      return null;
    }
    if (k === "pts") { this.q.points = Math.max(0, Math.min(30, this.q.points + btn.id[1])); return null; }
    if (k === "adv") {
      if (this.q.side === "A") this.q.side = "B";
      else { this.q.side = "A"; this.q.stage_n += 1; }
      this.q.progress = 0;
      return null;
    }
    if (k === "sail") { this.sail = !this.sail; return null; }
    if (k === "save") {
      this.game.quest = this.q;
      if (this.sail !== this.game.sailing) {
        this.game.sailing = this.sail;
        this.game.logEvent(this.sail
          ? "Sailing enabled (Dream-chaser) - heading starts On-course"
          : "Sailing disabled");
        if (this.sail) this.game.heading = 0;
      }
      return "close";
    }
    if (k === "cancel") return "cancel";
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
  static LH = 26;              // 10*scale(2)+6 - one wrapped body line
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
  _fit(lines, maxLines, usable, more) {
    if (lines.length <= maxLines && !more) return [lines, false];
    const keep = lines.slice(0, maxLines);
    if (!keep.length) keep.push("");
    const mw = measureText(QuestCardModal.MORE, BODY);
    let last = keep[keep.length - 1];
    while (last && measureText(last, BODY) + mw > usable) {
      last = last.includes(" ") ? last.slice(0, last.lastIndexOf(" ")) : last.slice(0, -1);
    }
    keep[keep.length - 1] = last + QuestCardModal.MORE;
    return [keep, true];
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
    return wrapText(face.text || "no text", BODY, usable);
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
    modalHeader(ctx, game, "QUEST CARDS", this.buttons);
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
    textLeft(ctx, side === "A" ? "SETUP / STORY" : "QUEST", M, y, LABEL, pal.amber);

    // -- body: the card's own text, at the same scale as everywhere else. It
    // gets every pixel between here and whatever sits below (the tips peek,
    // or the nav), and marks its own truncation.
    const hasTips = !!this._tipsData;
    const tipsY = S.NAV_Y - 12 - S.TIPS_H;
    const bodyBottom = hasTips ? tipsY - 8 : S.NAV_Y - 12;
    const by = S.BODY_Y0, usable = W - 20;
    const text = face.text || "";
    let [lines, cut] = this._fit(wrapText(text || "no text", BODY, usable),
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
function sqRadio(ctx, cx, cy, on) {
  arcRuns(ctx, cx, cy, 10, 8, 0, 360, on ? pal.gold : pal.dim);
  if (on) disc(ctx, cx, cy, 5, pal.gold);
}

export class SideQuestPickModal {
  static PER_PAGE = 6;
  static ROW_H = 44;
  static ROW_STRIDE = 46;
  static LIST_Y0 = 66;
  static NAME_MAX_W = 300;
  static FOOTER_Y = 404;
  static FOOTER_H = 64;

  constructor(game, entries) {
    this.game = game;
    this.entries = entries;
    this.selected = entries.length ? entries[0].id : null;
    this.page = 0;
    this.buttons = [];
  }

  _pages() { return Math.max(1, Math.ceil(this.entries.length / SideQuestPickModal.PER_PAGE)); }

  draw(ctx) {
    const { PER_PAGE, ROW_H, ROW_STRIDE, LIST_Y0, NAME_MAX_W, FOOTER_Y, FOOTER_H } = SideQuestPickModal;
    this.buttons = [];
    rect(ctx, 0, 0, 480, 480, pal.bg);
    modalHeader(ctx, this.game, "Add Side Quest", this.buttons);

    if (!this.entries.length) {
      textCenter(ctx, "No side-quest catalog data available.", 240, 140, BODY, pal.dim);
      textCenter(ctx, "Use Manual entry below.", 240, 168, BODY, pal.dim);
    } else {
      textLeft(ctx, "Pick a side quest, then Add - or enter manually.", 12, 46, BODY, pal.dim);
      const pages = this._pages();
      this.page = Math.min(this.page, pages - 1);
      const chunk = this.entries.slice(this.page * PER_PAGE, (this.page + 1) * PER_PAGE);
      let y = LIST_Y0;
      for (const e of chunk) {
        const on = e.id === this.selected;
        if (on) rect(ctx, 8, y, 456, ROW_H, pal.card_hi);
        sqRadio(ctx, 30, y + 22, on);
        const name = truncateText(e.name ?? "", BODY, NAME_MAX_W);
        textLeft(ctx, name, 52, y + 13, BODY, on ? pal.tan : pal.muted);
        const ptsS = `${e.points ?? 0} pts`;
        const pw = measureText(ptsS, BODY);
        textLeft(ctx, ptsS, 456 - pw, y + 4, BODY, on ? pal.gold : pal.tan);
        // ASCII hyphen, not an em-dash - matches ui/modals.py's device-safe
        // choice: PicoGraphics' "bitmap8" font only covers standard ASCII.
        const sphereS = e.sphere || "-";
        const sw = measureText(sphereS, BODY);
        textLeft(ctx, sphereS, 456 - sw, y + 26, BODY, pal.dim);
        rect(ctx, 8, y + ROW_H, 456, 1, pal.border);
        this.buttons.push(new Button(["row", e.id], 8, y, 456, ROW_H));
        y += ROW_STRIDE;
      }
      if (pages > 1) {
        const up = new Button(["older"], 12, 352, 150, 46);
        const dn = new Button(["newer"], 318, 352, 150, 46);
        bevel(ctx, up.x, up.y, up.w, up.h, pal.btn);
        textCenter(ctx, "Up", up.x + 75, up.y + 14, BODY, pal.tan);
        bevel(ctx, dn.x, dn.y, dn.w, dn.h, pal.btn);
        textCenter(ctx, "Down", dn.x + 75, dn.y + 14, BODY, pal.tan);
        textCenter(ctx, `${this.page + 1}/${pages}`, 240, 366, BODY, pal.muted);
        this.buttons.push(up, dn);
      }
    }

    const manual = new Button(["manual"], 24, FOOTER_Y, 200, FOOTER_H);
    bevel(ctx, manual.x, manual.y, manual.w, manual.h, pal.btn, false, 3);
    textCenter(ctx, "Manual", manual.x + manual.w / 2, manual.y + 20, BODY, pal.tan);
    this.buttons.push(manual);

    if (this.entries.length) {
      const add = new Button(["add"], 256, FOOTER_Y, 200, FOOTER_H);
      bevel(ctx, add.x, add.y, add.w, add.h, pal.btn_ok, false, 3);
      textCenter(ctx, "Add", add.x + add.w / 2, add.y + 20, BODY, pal.ok_fg);
      this.buttons.push(add);
    }
  }

  onButton(btn) {
    const k = btn.id[0];
    if (k === "close") return "close";
    if (k === "row") { this.selected = btn.id[1]; return "redraw"; }
    if (k === "older") { this.page = Math.max(0, this.page - 1); return "redraw"; }
    if (k === "newer") { this.page = Math.min(this._pages() - 1, this.page + 1); return "redraw"; }
    if (k === "manual") {
      this.game.side_quests.push({ points: 0, progress: 0 });
      this.game.logEvent("Side quest added manually (progress view)");
      return "close";
    }
    if (k === "add") {
      const e = this.entries.find(x => x.id === this.selected);
      if (e) {
        const pts = e.points ?? 0;
        this.game.side_quests.push({ points: pts, progress: 0, name: e.name });
        this.game.logEvent(`Side quest added: ${e.name} (${pts} pts, progress view)`);
      }
      return "close";
    }
    return null;
  }
}
