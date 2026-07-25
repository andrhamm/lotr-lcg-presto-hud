// Port of ui/screen_*.py + ui/modals.py + ui/modal_counter.py.
// Structure mirrors the Python: every screen/modal draws into ctx, rebuilds
// .buttons, and handles taps in onButton returning the same protocol values.
import { pal, Button, rect, panel, bevel, textLeft, textCenter, button,
         stepper, wrapText, truncateText, ribbon, notePanel, drawWeather,
         disc, arcRuns, ring, token, wxSmall } from "./ui.js";
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
  textCenter(ctx, "DONE", 440, 12, 2, pal.ok_fg);
}

export function drawHeader(ctx, game, buttons, { highlight = null, title = null,
                                                 close = false, closeLeft = false,
                                                 roundLabel = null } = {}) {
  const roundLbl = roundLabel ?? `R${game.round} ${game.step}`;
  textLeft(ctx, roundLbl, 10, 12, 2,
           (closeLeft || highlight === "log") ? pal.gold : pal.muted);
  const center = title ?? (VIEW_LABELS[game.view] ?? phaseStep(game.step).phase);
  const scale = center.length > 12 ? 2 : 3;
  textCenter(ctx, center, 240, scale === 2 ? 12 : 8, scale, pal.gold);
  if (close) {
    doneButton(ctx);
  } else {
    textLeft(ctx, "Set.", 480 - 10 - measureText("Set.", 2), 12, 2,
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
  textLeft(ctx, roundLbl, 10, 12, 2, pal.muted);
  textCenter(ctx, title, 240, 12, 2, pal.gold);
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
  textCenter(ctx, glyph, cx, Math.round(cy - 8), 2, pen);
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
  textCenter(ctx, "Cancel", no.x + no.w / 2, no.y + 20, 2, pal.no_fg);
  bevel(ctx, ok.x, ok.y, ok.w, ok.h, pal.btn_ok, false, 3);
  textCenter(ctx, saveLabel, ok.x + ok.w / 2, ok.y + 20, 2, pal.ok_fg);
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
      const w = measureText(this.title, 3);
      const ix = Math.floor(240 - w / 2 - 30);
      icons.drawIcon(ctx, icons[maskName], ix, 30, pal[penName]);
      textCenter(ctx, this.title, 240 + 12, 28, 3, pal.gold);
    } else {
      textCenter(ctx, this.title, 240, 28, 3, pal.gold);
    }
    const val = this.state.preview;
    textCenter(ctx, String(val), 240, 90, 9, pal.gold);
    if (this.subtext) textCenter(ctx, this.subtext, 240, 168, 2, pal.muted);
    if (this.state.pending) {
      const dlt = this.state.delta;
      textCenter(ctx, `${this.state.value}  ->  ${val}`, 240, 190, 2, pal.muted);
      textCenter(ctx, `${dlt >= 0 ? "+" : ""}${dlt}`, 240, 216, 3,
                 dlt >= 0 ? pal.green : pal.red);
    }
    const bw = 104, bh = 76, gap = 8;
    const x0 = (480 - (4 * bw + 3 * gap)) / 2;
    CounterModal.STEPS.forEach(([step, label], i) => {
      const b = new Button(["step", step], x0 + i * (bw + gap), 250, bw, bh);
      bevel(ctx, b.x, b.y, b.w, b.h, pal.btn, false, 3);
      textCenter(ctx, label, b.x + bw / 2, b.y + 26, 3, pal.tan);
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
    textCenter(ctx, `P${this.i + 1} settings`, 240, 24, 3, pal.gold);
    icons.drawIcon(ctx, icons.THREAT, 30, 92, pal.red);
    textLeft(ctx, "Starting threat", 58, 96, 2, pal.tan);
    stepper(ctx, this.buttons, ["st", -1], ["st", 1], 260, 82, String(this.st), 190, 56);
    icons.drawIcon(ctx, icons.THREAT, 30, 172, pal.red);
    textLeft(ctx, "Threat / round", 58, 176, 2, pal.tan);
    stepper(ctx, this.buttons, ["tpr", -1], ["tpr", 1], 260, 162, String(this.tpr), 190, 56);
    icons.drawIcon(ctx, icons.THREAT, 30, 252, pal.red);
    textLeft(ctx, "Elimination level", 58, 256, 2, pal.tan);
    stepper(ctx, this.buttons, ["el", -1], ["el", 1], 260, 242, String(this.elim), 190, 56);
    textLeft(ctx, "eliminated when threat reaches this (50 std)", 30, 306, 1, pal.dim);
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
    textCenter(ctx, "Side quests", 240, 22, 3, pal.gold);
    const sq = this.game.side_quests;
    if (!sq.length) textCenter(ctx, "none", 240, 90, 3, pal.dim);
    let y = 70;
    sq.forEach((s, i) => {
      panel(ctx, 24, y, 432, 56);
      textLeft(ctx, `SQ${i + 1}  ${s.progress}/${s.points}`, 36, y + 18, 2, pal.tan);
      const mn = new Button(["pts", i, -1], 250, y + 6, 44, 44);
      const pl = new Button(["pts", i, 1], 302, y + 6, 44, 44);
      const rm = new Button(["rm", i], 400, y + 6, 44, 44);
      button(ctx, this.buttons, mn, "-", 3);
      button(ctx, this.buttons, pl, "+", 3);
      bevel(ctx, rm.x, rm.y, rm.w, rm.h, pal.btn_no);
      textCenter(ctx, "x", rm.x + 22, rm.y + 10, 3, pal.no_fg);
      this.buttons.push(mn, pl, rm);
      y += 62;
    });
    const add = new Button(["add"], 24, Math.min(y, 320), 432, 52);
    bevel(ctx, add.x, add.y, add.w, add.h, pal.btn);
    textCenter(ctx, "+ Add side quest", add.x + 216, add.y + 16, 2, pal.tan);
    this.buttons.push(add);
    const done = new Button(["save"], 24, 404, 432, 64);
    bevel(ctx, done.x, done.y, done.w, done.h, pal.btn_ok, false, 3);
    textCenter(ctx, "Done", done.x + 216, done.y + 20, 2, pal.ok_fg);
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
    textCenter(ctx, title, 240, 30, 3, pal.gold);
    const loc = this.game.active_location;
    if (this.mode === "change" && loc) {
      textCenter(ctx, `current ${loc.progress}/${loc.points} will be discarded`, 240, 80, 2, pal.no_fg);
    }
    textLeft(ctx, "Quest points", 60, 190, 2, pal.tan);
    stepper(ctx, this.buttons, ["pts", -1], ["pts", 1], 250, 174, String(this.pts), 170, 60);
    icons.drawIcon(ctx, icons.THREAT, 60, 262, pal.red);
    textLeft(ctx, "Contribution", 88, 266, 2, pal.tan);
    stepper(ctx, this.buttons, ["ctr", -1], ["ctr", 1], 250, 250, String(this.contrib), 170, 60);
    textLeft(ctx, "subtracted from the staging area on travel", 60, 318, 1, pal.dim);
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
    textCenter(ctx, "Threat", threatX, 46, 1, pal.dim);
    textCenter(ctx, "Willpower", willX, 46, 1, pal.dim);
    game.players.forEach((p, i) => {
      const cy = 66 + i * 56;
      const label = `P${i + 1}`;
      if (i === game.first_player) {
        rect(ctx, labelX - 18, cy - 11, 36, 22, pal.gold);
        textCenter(ctx, label, labelX, cy - 8, 2, pal.bg, false);
      } else {
        textCenter(ctx, label, labelX, cy - 8, 2, pal.tan);
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
    const w = measureText(title, 3);
    const ix = Math.floor(240 - w / 2 - 30);
    icons.drawIcon(ctx, icons[maskName], ix, 30, pal[penName]);
    textCenter(ctx, title, 240 + 12, 28, 3, pal.gold);

    const val = state.preview;
    textCenter(ctx, String(val), 240, 90, 9, pal.gold);
    if (state.pending) {
      const dlt = state.delta;
      textCenter(ctx, `${state.value}  ->  ${val}`, 240, 190, 2, pal.muted);
      textCenter(ctx, `${dlt >= 0 ? "+" : ""}${dlt}`, 240, 216, 3,
                 dlt >= 0 ? pal.green : pal.red);
    }
    const bw = 104, bh = 76, gap = 8;
    const x0 = (480 - (4 * bw + 3 * gap)) / 2;
    [[-5, "-5"], [-1, "-1"], [1, "+1"], [5, "+5"]].forEach(([step, lbl], k) => {
      const b = new Button(["step", step], x0 + k * (bw + gap), 250, bw, bh);
      bevel(ctx, b.x, b.y, b.w, b.h, pal.btn, false, 3);
      textCenter(ctx, lbl, b.x + bw / 2, b.y + 26, 3, pal.tan);
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
      textLeft(ctx, label, 76, y + 12, 2, on ? pal.tan : pal.muted);
      if (key === "archery") {
        const part1 = `Notifies at ${VIEW_LABELS[view]} if staging `;
        const w1 = measureText(part1, 1);
        textLeft(ctx, part1, 76, y + 38, 1, pal.dim);
        icons.drawIcon(ctx, icons.THREAT_SM, 76 + w1 + 2, y + 35, pal.dim);
        textLeft(ctx, "> 0", 76 + w1 + 18, y + 38, 1, pal.dim);
      } else {
        textLeft(ctx, `Notifies at ${VIEW_LABELS[view]}`, 76, y + 38, 1, pal.dim);
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
    textCenter(ctx, `P${this.idx + 1} quests for...`, 240, 28, 3, pal.gold);
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
      textCenter(ctx, label, b.x + bw / 2, b.y + 26, 3, pal.tan);
      this.buttons.push(b);
    });
    const done = new Button(["done"], 24, 360, 200, 92);
    const nxt = new Button(["next"], 256, 360, 200, 92);
    if (this.final) {
      bevel(ctx, done.x, done.y, done.w, done.h, pal.btn_ok, false, 3);
      textCenter(ctx, "Done", done.x + 100, done.y + 32, 3, pal.ok_fg);
      bevel(ctx, nxt.x, nxt.y, nxt.w, nxt.h, pal.card, false, 3);
      textCenter(ctx, "Next", nxt.x + 100, nxt.y + 32, 3, pal.dim);
    } else {
      bevel(ctx, done.x, done.y, done.w, done.h, pal.card, false, 3);
      textCenter(ctx, "Done", done.x + 100, done.y + 32, 3, pal.dim);
      bevel(ctx, nxt.x, nxt.y, nxt.w, nxt.h, pal.btn, false, 3);
      textCenter(ctx, "Next", nxt.x + 100, nxt.y + 32, 3, pal.gold);
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
    const tw = measureText(title, 3);
    const start = Math.floor((480 - (20 + 8 + tw)) / 2);
    icons.drawIcon(ctx, icons.THREAT, start, 22, pal.red);
    textLeft(ctx, title, start + 28, 20, 3, pal.red);
    textCenter(ctx, `threat ${p.threat} reached elimination level ${p.elimination}`,
               240, 62, 2, pal.tan);
    const eb = new Button(["elim"], 24, 110, 432, 64);
    bevel(ctx, eb.x, eb.y, eb.w, eb.h, pal.btn_no, false, 3);
    textCenter(ctx, "Yes - eliminated", 240, eb.y + 22, 2, pal.no_fg);
    this.buttons.push(eb);
    const ab = new Button(["avert"], 24, 190, 432, 64);
    bevel(ctx, ab.x, ab.y, ab.w, ab.h, pal.btn, false, 3);
    textCenter(ctx, "Averted by card effect", 240, ab.y + 12, 2, pal.tan);
    textCenter(ctx, `threat -> ${Math.max(0, p.elimination - 5)}, stays in`,
               240, ab.y + 38, 1, pal.dim);
    this.buttons.push(ab);
    textLeft(ctx, "Elimination level changed?", 24, 286, 2, pal.tan);
    stepper(ctx, this.buttons, ["lvl", -1], ["lvl", 1], 24, 316,
            String(this.newLevel), 300, 56);
    const sb = new Button(["setlvl"], 340, 316, 116, 56);
    bevel(ctx, sb.x, sb.y, sb.w, sb.h, pal.btn_ok, false, 3);
    textCenter(ctx, "Set", sb.x + 58, sb.y + 18, 2, pal.ok_fg);
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
      textCenter(ctx, String(value), cx, Math.round(cy - 8), 2, pal.gold);
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
      textCenter(ctx, "+ Add location", b.x + b.w / 2, b.y + 5, 2, pal.tan);
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
    const nameS = truncateText(it.name, 2, 118);
    textLeft(ctx, nameS, 12, y, 2, questCardTappable ? pal.gold : pal.tan);
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

    textLeft(ctx, "Quest points", 12, 48, 1, pal.muted);
    textCenter(ctx, "Current", 178, 48, 1, pal.dim);
    textCenter(ctx, "Target", 300, 48, 1, pal.dim);

    const items = this._items();
    items.forEach((it, i) => this._row(ctx, it, QuestingProgressModal.ROWS_Y0 + i * QuestingProgressModal.ROW_H));
    const n = items.length;

    const addY = QuestingProgressModal.ROWS_Y0 + n * QuestingProgressModal.ROW_H - 4;
    const add = new Button(["add"], 12, addY, 120, 24);
    bevel(ctx, add.x, add.y, add.w, add.h, pal.btn);
    textCenter(ctx, "+ Side quest", add.x + add.w / 2, add.y + 5, 2, pal.tan);
    this.buttons.push(add);

    if (this.game.sailing) {
      const headingY = QuestingProgressModal.ROWS_Y0 + n * QuestingProgressModal.ROW_H + 34;
      textLeft(ctx, "Heading", 12, headingY, 2, pal.tan);
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
    textLeft(ctx, "THIS GAME - BY ROUND", 12, cy0 - 9, 1, pal.muted);
    const cols = this.game.quest_history.slice(-8);
    if (!cols.length) {
      textCenter(ctx, "No rounds resolved yet", 240, cy0 + 14, 1, pal.dim);
      return;
    }
    const x0 = 52;
    const stride = Math.floor((472 - x0) / cols.length);
    cols.forEach((r, i) =>
      textCenter(ctx, `R${r.round}`, x0 + i * stride + Math.floor(stride / 2), cy0, 1, pal.dim));
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
        textCenter(ctx, s, x0 + i * stride + Math.floor(stride / 2), ry, 2, pen);
      });
      ry += 26;
    }
    const caption = "willpower / staging / result" + (this.game.sailing ? " / heading" : "");
    textCenter(ctx, caption, 240, ry + 4, 1, pal.dim);
  }

  _drawLocPrompt(ctx) {
    const lp = this.locPrompt;
    if (lp.stage === "choose") { this._drawLocChoose(ctx); return; }
    if (lp.stage === "pts") { this._drawLocPts(ctx); return; }
    this._drawLocContrib(ctx);
  }

  _drawLocChoose(ctx) {
    const loc = this.game.active_location;
    textCenter(ctx, "Location removed", 240, 30, 3, pal.gold);
    textCenter(ctx, "What happened to it?", 240, 70, 2, pal.tan);
    textCenter(ctx, `${loc.progress}/${loc.points} progress will be discarded`, 240, 94, 1, pal.dim);
    const opt = (y, id, label, sub) => {
      const b = new Button([id], 24, y, 432, 64);
      bevel(ctx, b.x, b.y, b.w, b.h, pal.btn, false, 3);
      textCenter(ctx, label, 240, y + 14, 3, pal.tan);
      textCenter(ctx, sub, 240, y + 44, 1, pal.dim);
      this.buttons.push(b);
    };
    opt(120, "lp_replaced", "Replaced", "enter the new location's quest points");
    opt(196, "lp_staging", "To staging", "its threat returns to the staging area");
    opt(272, "lp_discard", "Discard", "no replacement");
    const cancel = new Button(["lp_cancel"], 24, 356, 432, 56);
    bevel(ctx, cancel.x, cancel.y, cancel.w, cancel.h, pal.btn_no, false, 3);
    textCenter(ctx, "Cancel", 240, cancel.y + 18, 2, pal.no_fg);
    this.buttons.push(cancel);
  }

  _drawLocPts(ctx) {
    textCenter(ctx, "Replace location", 240, 30, 3, pal.gold);
    textLeft(ctx, "Quest points", 60, 216, 2, pal.tan);
    stepper(ctx, this.buttons, ["lp_pts", -1], ["lp_pts", 1], 250, 200, String(this.locPrompt.pts), 170, 60);
    footer(ctx, this.buttons, "Confirm");
  }

  _drawLocContrib(ctx) {
    textCenter(ctx, "Location to staging", 240, 30, 3, pal.gold);
    icons.drawIcon(ctx, icons.THREAT, 60, 208, pal.red);
    textLeft(ctx, "Contribution", 88, 216, 2, pal.tan);
    stepper(ctx, this.buttons, ["lp_ctr", -1], ["lp_ctr", 1], 250, 200,
            String(this.locPrompt.state.preview), 170, 60);
    textLeft(ctx, "added to the staging area", 60, 270, 1, pal.dim);
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
      textLeft(ctx, label, x0 + 32, cy + (scale === 2 ? 2 : 0), scale, pen);
    };

    textCenter(ctx, "Current heading", 240, 54, 1, pal.dim);
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
    textCenter(ctx, sub, 240, 200, 1, spen);

    const mn = new Button(["d", -1], 34, 128, 64, 60);
    const pl = new Button(["d", 1], 480 - 34 - 64, 128, 64, 60);
    bevel(ctx, mn.x, mn.y, mn.w, mn.h, pal.btn);
    textCenter(ctx, "-", mn.x + 32, mn.y + 14, 4, pal.tan);
    bevel(ctx, pl.x, pl.y, pl.w, pl.h, pal.btn);
    textCenter(ctx, "+", pl.x + 32, pl.y + 14, 4, pal.tan);
    this.buttons.push(mn, pl);

    textCenter(ctx, "Result", 240, 240, 1, pal.dim);
    heading(this._result(), 262, 2);

    const no = new Button(["cancel"], 24, 404, 200, 64);
    const ok = new Button(["apply"], 256, 404, 200, 64);
    bevel(ctx, no.x, no.y, no.w, no.h, pal.btn_no, false, 3);
    textCenter(ctx, "Cancel", no.x + 100, no.y + 20, 2, pal.no_fg);
    bevel(ctx, ok.x, ok.y, ok.w, ok.h, pal.btn_ok, false, 3);
    textCenter(ctx, "Apply", ok.x + 100, ok.y + 20, 2, pal.ok_fg);
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
    textCenter(ctx, `Quest Stage ${this.cleared} cleared!`, 240, 26, 3, pal.gold);
    let y = 74;
    textCenter(ctx, "Set up the next stage", 240, y, 2, pal.tan);
    y += 40;
    textLeft(ctx, "Stage", 30, y + 14, 2, pal.tan);
    stepper(ctx, this.buttons, ["n", -1], ["n", 1], 160, y, String(this.n), 130, 52);
    // side cycles A-H (multi-variant quests go beyond A/B - DragnCards data)
    stepper(ctx, this.buttons, ["side", -1], ["side", 1], 316, y, this.side, 144, 52);
    y += 76;
    textLeft(ctx, "Quest points", 30, y + 14, 2, pal.tan);
    stepper(ctx, this.buttons, ["pts", -1], ["pts", 1], 240, y, String(this.pts), 210, 52);
    y += 90;
    const go = new Button(["go"], 30, y, 420, 60);
    bevel(ctx, go.x, go.y, go.w, go.h, pal.btn_ok, false, 3);
    textCenter(ctx, `Continue to ${this.n}${this.side}`, 240, y + 20, 2, pal.ok_fg);
    this.buttons.push(go);
    y += 74;
    const win = new Button(["win"], 30, y, 420, 60);
    bevel(ctx, win.x, win.y, win.w, win.h, pal.card_hi, false, 3);
    textCenter(ctx, "That was the final stage - Victory!", 240, y + 20, 2, pal.gold);
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
    textCenter(ctx, label, 240, y + Math.floor(h / 2) - 10, 2, ok ? pal.ok_fg : pal.no_fg);
    this.buttons.push(b);
  }

  _drawDone(ctx) {
    textCenter(ctx, "All resolved", 240, 200, 3, pal.gold);
    this._cta(ctx, "Continue", ["close"]);
  }

  _drawReveal(ctx, st) {
    textCenter(ctx, `STAGE ${st.stage_n} REVEALED`, 240, 64, 2, pal.amber);
    const name = truncateText(st.face_a.name || "", 3, 432);
    textCenter(ctx, name, 240, 92, 3, pal.gold);
    const tipX = 24, tipW = 432, tipY = 130;
    const ribbonH = 22, padTop = 10, lineH = 24, padBottom = 10, maxLines = 5;
    const raw = st.face_a.text;
    const body = raw ? raw : "No setup instructions for this stage.";
    const lines = wrapText(body, 2, tipW - 28).slice(0, maxLines);
    const tipH = ribbonH + padTop + lines.length * lineH + padBottom;
    rect(ctx, tipX, tipY, tipW, tipH, pal.border_gold);
    rect(ctx, tipX + 2, tipY + 2, tipW - 4, tipH - 4, pal.bg);
    rect(ctx, tipX + 4, tipY + 4, tipW - 8, tipH - 8, pal.border_gold);
    rect(ctx, tipX + 6, tipY + 6, tipW - 12, tipH - 12, pal.scroll);
    rect(ctx, tipX, tipY, tipW, ribbonH, pal.border_gold);
    textLeft(ctx, "STAGE ADVANCE - resolve now", tipX + 10, tipY + 6, 1, pal.bg, false);
    let ly = tipY + ribbonH + padTop;
    for (const ln of lines) {
      textLeft(ctx, ln, tipX + 14, ly, 2, pal.tan);
      ly += lineH;
    }
    this._cta(ctx, `Flip to Side B  ->  ${st.next_points} qp`, ["do_flip"]);
  }

  _drawLocation(ctx, st) {
    textCenter(ctx, "Location Explored", 240, 90, 3, pal.gold);
    textCenter(ctx, `${st.progress}/${st.points} progress`, 240, 130, 2, pal.tan);
    const excess = st.progress - st.points;
    if (excess) {
      textCenter(ctx, `${excess} excess -> quest card`, 240, 160, 2, pal.amber);
    }
    this._cta(ctx, "Continue", ["resolve_location"]);
  }

  _drawBranch(ctx, st) {
    textCenter(ctx, "Choose a path", 240, 56, 3, pal.gold);
    textCenter(ctx, st.mode !== "random" ? "First player chooses" : "Random", 240, 86, 1, pal.dim);
    let y = 116;
    st.cards.forEach((card, i) => {
      const bFace = card.faces.find(f => f.side === "B") ?? {};
      const b = new Button(["pick_branch", i], 24, y, 432, 64);
      const sel = this.branchPick === i;
      bevel(ctx, b.x, b.y, b.w, b.h, sel ? pal.btn_ok : pal.btn, false, 3);
      textLeft(ctx, bFace.name || "?", b.x + 14, y + 10, 2, sel ? pal.ok_fg : pal.tan);
      const preview = truncateText(bFace.text || "", 1, 400);
      textLeft(ctx, preview, b.x + 14, y + 38, 1, pal.dim);
      this.buttons.push(b);
      y += 74;
    });
    if (st.mode === "random") {
      const r = new Button(["randomize_branch"], 24, y, 432, 40);
      bevel(ctx, r.x, r.y, r.w, r.h, pal.card, false, 2);
      textCenter(ctx, "Randomize for me", 240, y + 10, 2, pal.tan);
      this.buttons.push(r);
    }
  }

  _drawAdvance(ctx, st) {
    textCenter(ctx, `Quest ${st.cleared} cleared`, 240, 90, 3, pal.gold);
    if (st.underfilled) {
      textCenter(ctx, "Progress hasn't reached target - confirm", 240, 130, 1, pal.red);
    }
    this._cta(ctx, `Reveal Stage ${st.next_stage}`, ["do_advance"]);
  }

  _drawVictory(ctx, st) {
    textCenter(ctx, `Quest ${st.cleared} cleared`, 240, 70, 2, pal.tan);
    textCenter(ctx, "That was the final stage!", 240, 110, 3, pal.gold);
    this._cta(ctx, "Declare Victory", ["declare_victory"], 340);
    this._cta(ctx, "Not yet - keep playing", ["continue_without_victory"], 404, 56, false);
  }

  _drawSideQuest(ctx, st) {
    textCenter(ctx, st.name, 240, 90, 3, pal.gold);
    textCenter(ctx, `${st.progress}/${st.points}`, 240, 130, 2, pal.tan);
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
    textCenter(ctx, `Quest  ${this.q.stage_n}${this.q.side}`, 240, 24, 3, pal.gold);
    textLeft(ctx, "Stage number", 30, 84, 2, pal.tan);
    stepper(ctx, this.buttons, ["n", -1], ["n", 1], 300, 70, String(this.q.stage_n), 150, 52);
    textLeft(ctx, "Side", 30, 156, 2, pal.tan);
    stepper(ctx, this.buttons, ["side", -1], ["side", 1], 300, 142, this.q.side, 150, 52);
    textLeft(ctx, "Quest points", 30, 228, 2, pal.tan);
    stepper(ctx, this.buttons, ["pts", -1], ["pts", 1], 300, 214, String(this.q.points), 150, 52);
    textLeft(ctx, "Sailing quest", 30, 296, 2, pal.tan);
    icons.drawIcon(ctx, icons.WHEEL, 176, 292, this.sail ? pal.gold : pal.dim);
    const sb = new Button(["sail"], 300, 284, 150, 48);
    panel(ctx, sb.x, sb.y, sb.w, sb.h, this.sail ? pal.gold : pal.btn);
    textCenter(ctx, this.sail ? "On" : "Off", sb.x + 75, sb.y + 14, 2,
               this.sail ? pal.bg : pal.tan, false);
    this.buttons.push(sb);
    const adv = new Button(["adv"], 30, 344, 420, 48);
    bevel(ctx, adv.x, adv.y, adv.w, adv.h, pal.btn);
    textCenter(ctx, "Advance stage (progress -> 0)", adv.x + 210, adv.y + 14, 2, pal.tan);
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
  static MARGIN = 12;
  // Ceiling, not a floor: the SIDE A/SIDE B blocks must end at or below this
  // y so the Tips button + pager (a fixed 88px: 48px gap + 40px pager tall,
  // themselves 40px tall) still fit above 480 with margin. _lineBudget()
  // uses it to size each block's line cap per render (see below) instead of
  // a flat constant - short text no longer leaves Tips/pager stranded down
  // at a fixed position (they float up to meet the content), and long text
  // gets far more than the old flat 3-line cap when the other side is short.
  static BOTTOM_Y0 = 380;

  // stages/scenario override the game's own: Scenario Options opens this
  // BEFORE the scenario is preloaded into the game, so it passes the picked
  // scenario's stages and index entry directly. Everything below reads these,
  // never the game - the modal was already read-only, this just names its
  // source. Mirrors ui/modals.py.
  constructor(game, tips = null, stages = null, scenario = null) {
    this.game = game;
    this.stages = stages ?? game.stages;
    this.scenario = (stages === null ? game.scenario : scenario) ?? {};
    // Which stage is live. In preview there is no live stage yet, and stage 1
    // is where the game will start, so 0 marks the same card Quest Setup would.
    this.currentIdx = stages === null ? game.stage_idx : 0;
    this.idx = this.stages.length ? this.currentIdx : 0;
    this.card = this.stages.length ? (stages === null ? game.card_idx : 0) : 0;
    this.buttons = [];
    this.tips = tips ?? {};      // loaded tips.json "scenarios" map (M4-B tips)
    this.tipsOpen = false;       // toggled by the Tips/Back button
    this._tipsData = null;       // tipsFor(...) result for the current stage, set by draw()
  }

  // Word-wraps text (or the "no text" placeholder) at the block's usable
  // width with no line cap - the "natural" line count _lineBudget() then
  // allocates space against.
  _wrapBody(text, w) {
    const usable = w - 20;
    const hasText = Boolean(text);
    const body = hasText ? text : "no text";
    return { hasText, lines: wrapText(body, 1, usable), usable };
  }

  // Distributes the pixel budget between y0 (top of the SIDE A block) and
  // BOTTOM_Y0 across the two blocks' natural line counts: each gets its full
  // natural count if both fit, otherwise the longer block is trimmed one
  // line at a time (ties trim A first) until the total fits. Always leaves
  // at least 1 line per block.
  _lineBudget(y0, naturalA, naturalB) {
    const OVERHEAD = 26;   // per block: 18px label row + 8px bottom pad
    const GAP = 12;        // 6px trailing gap after each of the two blocks
    const LH = 16;         // 10*scale(1) + 6, one wrapped text line
    const availablePx = QuestCardModal.BOTTOM_Y0 - y0 - 2 * OVERHEAD - GAP;
    const budgetLines = Math.max(2, Math.floor(availablePx / LH));
    let allowedA = naturalA, allowedB = naturalB;
    while (allowedA + allowedB > budgetLines && (allowedA > 1 || allowedB > 1)) {
      if (allowedA >= allowedB && allowedA > 1) allowedA -= 1;
      else if (allowedB > 1) allowedB -= 1;
      else allowedA -= 1;
    }
    return [allowedA, allowedB];
  }

  // Bordered panel: a small label row + up to maxLines of the pre-wrapped
  // body text (or the "no text" placeholder). Returns height.
  _sideBlock(ctx, x, y, w, label, wrapped, maxLines) {
    let lines = wrapped.lines;
    if (lines.length > maxLines) {
      lines = lines.slice(0, maxLines);
      lines[lines.length - 1] = truncateText(`${lines[lines.length - 1]} ..`, 1, wrapped.usable);
    }
    const lh = 16;
    const h = 18 + lines.length * lh + 8;
    panel(ctx, x, y, w, h, pal.card);
    textLeft(ctx, label, x + 10, y + 6, 1, pal.amber);
    let ty = y + 20;
    const ink = wrapped.hasText ? pal.tan : pal.dim;
    for (const ln of lines) {
      textLeft(ctx, ln, x + 10, ty, 1, ink);
      ty += lh;
    }
    return h;
  }

  // Bordered panel: a "TIPS" label row, up to maxH px of wrapped tip lines
  // (each prefixed "- "), and the attribution name + URL in pal.dim
  // beneath - the tips-view counterpart of _sideBlock, sized against the
  // same BOTTOM_Y0 ceiling so the Tips/Back button and pager land at the
  // same y in either view. Excess content truncates its last visible line
  // with ".." rather than overflowing into the button/pager area,
  // mirroring _sideBlock's own truncate-to-fit. Returns height (<= maxH).
  _tipsPanel(ctx, x, y, w, tipsData, maxH) {
    const usable = w - 20;
    const lh = 16;
    let lines = [];
    for (const t of tipsData.tips) lines.push(...wrapText(`- ${t}`, 1, usable));
    const attribution = tipsData.attribution ?? {};
    const name = attribution.name ?? "";
    const url = attribution.url ?? "";
    const attribLines = [name ? `Source: ${name}` : "", url]
      .filter(Boolean)
      .map(s => truncateText(s, 1, usable));

    const overhead = 18 + 8;   // label row + bottom pad, matches _sideBlock
    const budget = Math.max(1, Math.floor((maxH - overhead - attribLines.length * lh) / lh));
    if (lines.length > budget) {
      lines = lines.slice(0, budget);
      lines[lines.length - 1] = truncateText(`${lines[lines.length - 1]} ..`, 1, usable);
    }

    const h = Math.min(maxH, overhead + (lines.length + attribLines.length) * lh);
    panel(ctx, x, y, w, h, pal.card);
    textLeft(ctx, "TIPS", x + 10, y + 6, 1, pal.amber);
    let ty = y + 20;
    for (const ln of lines) { textLeft(ctx, ln, x + 10, ty, 1, pal.tan); ty += lh; }
    for (const ln of attribLines) { textLeft(ctx, ln, x + 10, ty, 1, pal.dim); ty += lh; }
    return h;
  }

  draw(ctx, game) {
    this.buttons = [];
    rect(ctx, 0, 0, 480, 480, pal.bg);
    modalHeader(ctx, game, "QUEST CARD", this.buttons);
    const M = QuestCardModal.MARGIN, W = 480 - 2 * M;

    if (!this.stages.length) {
      textCenter(ctx, "No quest loaded", 240, 200, 2, pal.dim);
      textCenter(ctx, "Start a scenario to see stage cards.", 240, 226, 1, pal.dim);
      return;
    }

    const n = this.stages.length;
    this.idx = Math.max(0, Math.min(this.idx, n - 1));
    const stage = this.stages[this.idx];
    const cards = stage.cards;
    this.card = Math.max(0, Math.min(this.card, cards.length - 1));
    const card = cards[this.card];
    // Front is side A; the back is whatever non-A side this printing uses.
    // Most cards are A/B, but epic multiplayer variants share one A front with
    // backs C..H (e.g. Mount Gundabad stage 2 has 7 alternatives), so matching
    // "B" literally would blank all but the first.
    const aFace = card.faces.find(f => f.side === "A") ?? card.faces[0] ?? {};
    const bFace = card.faces.find(f => f.side && f.side !== "A") ?? card.faces[1] ?? {};
    const aName = aFace.name ?? "";
    const bName = bFace.name ?? "";

    // -- stage line: number, an A/B legend, and a CURRENT marker so paging
    // away from the game's live stage is obvious --------------------------
    let y = 48;
    textLeft(ctx, `STAGE ${stage.stage}`, M, y, 2, pal.amber);
    const abHint = "A / B";
    textLeft(ctx, abHint, 480 - M - measureText(abHint, 1), y + 4, 1, pal.dim);
    if (this.idx === this.currentIdx) {
      const pw = measureText("CURRENT", 1) + 14;
      const px = 240 - Math.floor(pw / 2);
      rect(ctx, px, y, pw, 18, pal.gold);
      textCenter(ctx, "CURRENT", 240, y + 4, 1, pal.bg, false);
    }
    y += 28;

    // -- card name(s): a shared name shows once; a branch payoff (the
    // B-face name differs, e.g. "A Chosen Path" -> "Beorn's Path") shows
    // both, labelled --------------------------------------------------------
    if (bName && bName !== aName) {
      textLeft(ctx, truncateText(`A: ${aName}`, 2, W), M, y, 2, pal.gold);
      y += 22;
      textLeft(ctx, truncateText(`B: ${bName}`, 2, W), M, y, 2, pal.gold);
      y += 26;
    } else {
      const name = aName || bName || "(unnamed)";
      textCenter(ctx, truncateText(name, 3, W), 240, y, 3, pal.gold);
      y += 32;
    }

    // -- quest points / victory / sailing stat strip -------------------------
    const cx = M + 16;
    textLeft(ctx, "PTS", M, y, 1, pal.dim);
    token(ctx, cx, y + 22, 14, 2, card.questPoints ?? 0, pal.gold, 0, pal.gold, pal.dim);
    let nx = cx + 40;
    if (card.victory !== null && card.victory !== undefined) {
      textLeft(ctx, "VP", nx - 14, y, 1, pal.dim);
      token(ctx, nx, y + 22, 14, 2, card.victory, pal.gold, 0, pal.gold, pal.dim);
      nx += 40;
    }
    if (card.sailing) {
      textLeft(ctx, "SAIL", nx - 16, y, 1, pal.dim);
      disc(ctx, nx, y + 22, 14, pal.well);
      icons.drawIcon(ctx, icons.WHEEL_SM, nx - 8, y + 14, pal.gold);
    }
    y += 46;

    // -- branch: which alternative is displayed only affects the view --------
    if (cards.length > 1) {
      const label = { random: "BRANCH - random",
                      choice: "BRANCH - first player chooses" }[stage.branch] ?? "BRANCH";
      textLeft(ctx, truncateText(label, 2, 480 - 2 * M - 162), M, y + 12, 2, pal.amber);
      const alt = new Button(["alt"], 480 - M - 150, y, 150, 36);
      bevel(ctx, alt.x, alt.y, alt.w, alt.h, pal.btn);
      textCenter(ctx, `Card ${this.card + 1} / ${cards.length}`, alt.x + alt.w / 2, alt.y + 12, 1, pal.tan);
      this.buttons.push(alt);
      y += 44;
    }

    // -- SIDE A/B card text, or (M4-B tips) the tips panel in its place -------
    this._tipsData = tipsFor(this.scenario?.slug, stage.stage, this.tips);
    if (this.tipsOpen && this._tipsData) {
      y += this._tipsPanel(ctx, M, y, W, this._tipsData, QuestCardModal.BOTTOM_Y0 - y) + 6;
    } else {
      this.tipsOpen = false;   // nothing to show (e.g. paged to an untipped stage)
      const wrapA = this._wrapBody(aFace.text, W);
      const wrapB = this._wrapBody(bFace.text, W);
      const [maxA, maxB] = this._lineBudget(y, wrapA.lines.length, wrapB.lines.length);
      y += this._sideBlock(ctx, M, y, W, "SIDE A - setup / story", wrapA, maxA) + 6;
      y += this._sideBlock(ctx, M, y, W, "SIDE B - quest", wrapB, maxB) + 6;
    }

    // -- Tips: enabled (normal palette) only where tips exist for this stage;
    // toggles the tips panel above in place of the SIDE A/B blocks
    // (M4-B tips) --------------------------------------------------------------
    const tips = new Button(["tips"], M, y, 140, 40);
    bevel(ctx, tips.x, tips.y, tips.w, tips.h, pal.btn);
    if (this._tipsData) {
      const n = this._tipsData.tips.length;
      textCenter(ctx, this.tipsOpen ? "Back" : "Tips", tips.x + 70, tips.y + 6, 2, pal.tan);
      const sub = this.tipsOpen ? "to card" : `${n} note${n === 1 ? "" : "s"}`;
      textCenter(ctx, sub, tips.x + 70, tips.y + 26, 1, pal.dim);
    } else {
      textCenter(ctx, "Tips", tips.x + 70, tips.y + 6, 2, pal.dim);
      textCenter(ctx, "none yet", tips.x + 70, tips.y + 26, 1, pal.dim);
    }
    this.buttons.push(tips);

    // -- pager: hidden (not just disabled) at each end ------------------------
    const py = y + 48;
    if (this.idx > 0) {
      const prev = new Button(["prev"], M, py, 110, 40);
      bevel(ctx, prev.x, prev.y, prev.w, prev.h, pal.btn);
      textCenter(ctx, "< Prev", prev.x + 55, prev.y + 12, 2, pal.tan);
      this.buttons.push(prev);
    }
    if (this.idx < n - 1) {
      const nxt = new Button(["next"], 480 - M - 110, py, 110, 40);
      bevel(ctx, nxt.x, nxt.y, nxt.w, nxt.h, pal.btn);
      textCenter(ctx, "Next >", nxt.x + 55, nxt.y + 12, 2, pal.tan);
      this.buttons.push(nxt);
    }
    textCenter(ctx, `stage ${this.idx + 1} of ${n}`, 240, py + 12, 2, pal.muted);
  }

  onButton(btn) {
    const k = btn.id[0];
    if (k === "close") return "close";
    if (k === "tips") {
      if (this._tipsData) { this.tipsOpen = !this.tipsOpen; return "redraw"; }
      return null;
    }
    if (!this.stages.length) return null;
    const n = this.stages.length;
    if (k === "next") {
      if (this.idx < n - 1) { this.idx += 1; this.card = 0; return "redraw"; }
      return null;
    }
    if (k === "prev") {
      if (this.idx > 0) { this.idx -= 1; this.card = 0; return "redraw"; }
      return null;
    }
    if (k === "alt") {
      const cards = this.stages[this.idx].cards;
      if (cards.length > 1) { this.card = (this.card + 1) % cards.length; return "redraw"; }
      return null;
    }
    return null;
  }
}

// Radio-button glyph: ring, filled when selected. Duplicates
// screens_other.js's radioGlyph (this codebase's screen/modal helpers are
// per-file, not cross-imported - screens_other.js already imports from this
// file, so the reverse would cycle) so SideQuestPickModal can "feel like
// the same family" as ChooseScenarioScreen without a new module cycle.
function sqRadio(ctx, cx, cy, on) {
  arcRuns(ctx, cx, cy, 10, 8, 0, 360, on ? pal.gold : pal.dim);
  if (on) disc(ctx, cx, cy, 5, pal.gold);
}

// Picker over the player side-quest catalog (M4-B sidequest, Task 2):
// radio-select list (name / points / sphere), Up/Down pager (mirrors
// ChooseScenarioScreen/PickCycleScreen in screens_other.js - same row
// stride/pager geometry, same radio glyph), plus Add (commits the
// selection) and Manual (today's blank-entry fallback, unchanged shape).
//
// Opened from QuestingProgressModal's "+ Side quest" button via the
// pending_side_quest_pick flag (see main.js's setInterval) - constructed
// with the already-loaded catalog entries (quest_catalog.sideQuests(...)
// shape: {id, name, points, sphere, pack}), never reads the catalog itself.
//
// Empty `entries` (no catalog data) still renders and offers Manual rather
// than throwing - defense in depth. The call site is expected to skip
// opening this modal entirely when loadPlayerSideQuests() comes back empty
// and append directly instead (today's behavior, Global Constraints:
// catalog data is optional at runtime), but nothing here assumes that.
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
      textCenter(ctx, "No side-quest catalog data available.", 240, 140, 2, pal.dim);
      textCenter(ctx, "Use Manual entry below.", 240, 168, 1, pal.dim);
    } else {
      textLeft(ctx, "Pick a side quest, then Add - or enter manually.", 12, 46, 1, pal.dim);
      const pages = this._pages();
      this.page = Math.min(this.page, pages - 1);
      const chunk = this.entries.slice(this.page * PER_PAGE, (this.page + 1) * PER_PAGE);
      let y = LIST_Y0;
      for (const e of chunk) {
        const on = e.id === this.selected;
        if (on) rect(ctx, 8, y, 456, ROW_H, pal.card_hi);
        sqRadio(ctx, 30, y + 22, on);
        const name = truncateText(e.name ?? "", 2, NAME_MAX_W);
        textLeft(ctx, name, 52, y + 13, 2, on ? pal.tan : pal.muted);
        const ptsS = `${e.points ?? 0} pts`;
        const pw = measureText(ptsS, 2);
        textLeft(ctx, ptsS, 456 - pw, y + 4, 2, on ? pal.gold : pal.tan);
        // ASCII hyphen, not an em-dash - matches ui/modals.py's device-safe
        // choice: PicoGraphics' "bitmap8" font only covers standard ASCII.
        const sphereS = e.sphere || "-";
        const sw = measureText(sphereS, 1);
        textLeft(ctx, sphereS, 456 - sw, y + 26, 1, pal.dim);
        rect(ctx, 8, y + ROW_H, 456, 1, pal.border);
        this.buttons.push(new Button(["row", e.id], 8, y, 456, ROW_H));
        y += ROW_STRIDE;
      }
      if (pages > 1) {
        const up = new Button(["older"], 12, 352, 150, 46);
        const dn = new Button(["newer"], 318, 352, 150, 46);
        bevel(ctx, up.x, up.y, up.w, up.h, pal.btn);
        textCenter(ctx, "Up", up.x + 75, up.y + 14, 2, pal.tan);
        bevel(ctx, dn.x, dn.y, dn.w, dn.h, pal.btn);
        textCenter(ctx, "Down", dn.x + 75, dn.y + 14, 2, pal.tan);
        textCenter(ctx, `${this.page + 1}/${pages}`, 240, 366, 2, pal.muted);
        this.buttons.push(up, dn);
      }
    }

    const manual = new Button(["manual"], 24, FOOTER_Y, 200, FOOTER_H);
    bevel(ctx, manual.x, manual.y, manual.w, manual.h, pal.btn, false, 3);
    textCenter(ctx, "Manual", manual.x + manual.w / 2, manual.y + 20, 2, pal.tan);
    this.buttons.push(manual);

    if (this.entries.length) {
      const add = new Button(["add"], 256, FOOTER_Y, 200, FOOTER_H);
      bevel(ctx, add.x, add.y, add.w, add.h, pal.btn_ok, false, 3);
      textCenter(ctx, "Add", add.x + add.w / 2, add.y + 20, 2, pal.ok_fg);
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
