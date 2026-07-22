// Port of ui/screen_*.py + ui/modals.py + ui/modal_counter.py.
// Structure mirrors the Python: every screen/modal draws into ctx, rebuilds
// .buttons, and handles taps in onButton returning the same protocol values.
import { pal, Button, rect, panel, bevel, textLeft, textCenter, button,
         stepper, wrapText, truncateText, ribbon, notePanel, drawWeather } from "./ui.js";
import { measureText } from "./metrics.js";
import * as icons from "./icons.js";
import { GameState, VIEW_ORDER, VIEW_LABELS, SETUP_TIP, REMINDER_DEFS, HEADINGS,
         DEFAULT_START_THREAT, MAX_PLAYERS, viewForStep, fmtMs } from "./gamestate.js";
import { PHASES, STEPS, step as phaseStep } from "./phases.js";

export const HEADER_H = 40;
const MARGIN = 8;
const STRIP_Y = HEADER_H + 10;
const CHIP_H = 56;
const PROG_Y = STRIP_Y + CHIP_H + 8;
const CONTENT_Y = PROG_Y + CHIP_H + 8;
const CTA_Y = 410;
const CTA_H = 58;
const GUTTER = MARGIN + 40;

export function drawHeader(ctx, game, buttons, { highlight = null, title = null,
                                                 close = false, closeLeft = false } = {}) {
  const roundLbl = `R${game.round} ${game.step}`;
  textLeft(ctx, roundLbl, 10, 12, 2,
           (closeLeft || highlight === "log") ? pal.gold : pal.muted);
  const center = title ?? (VIEW_LABELS[game.view] ?? phaseStep(game.step).phase);
  const scale = center.length > 12 ? 2 : 3;
  textCenter(ctx, center, 240, scale === 2 ? 12 : 8, scale, pal.gold);
  if (close) {
    textLeft(ctx, "X", 480 - 16 - measureText("X", 3), 8, 3, pal.no_fg);
  } else {
    textLeft(ctx, "Set.", 480 - 10 - measureText("Set.", 2), 12, 2,
             highlight === "settings" ? pal.gold : pal.muted);
  }
  rect(ctx, 0, HEADER_H, 480, 1, pal.border);
  if (close) {
    buttons.push(new Button(["nav", "close"], 330, 0, 150, HEADER_H));
  } else if (closeLeft) {
    buttons.push(new Button(["nav", "close"], 0, 0, 150, HEADER_H));
    buttons.push(new Button(["nav", "settings"], 330, 0, 150, HEADER_H));
  } else {
    buttons.push(new Button(["nav", "log"], 0, 0, 150, HEADER_H));
    buttons.push(new Button(["nav", "phases"], 150, 0, 180, HEADER_H));
    buttons.push(new Button(["nav", "settings"], 330, 0, 150, HEADER_H));
  }
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

  constructor(title, value, onCommit = null, icon = null) {
    this.title = title;
    this.state = new CounterState(value);
    this.onCommit = onCommit;
    this.icon = icon;
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

export class QuestingForModal {
  constructor(game) {
    this.game = game;
    this.vals = game.players.map(p => p.commit);
    this.buttons = [];
  }
  draw(ctx) {
    this.buttons = [];
    rect(ctx, 0, 0, 480, 480, pal.bg);
    textCenter(ctx, "Questing for...", 240, 22, 3, pal.gold);
    let y = 74;
    this.game.players.forEach((p, i) => {
      if (p.eliminated) return;
      textLeft(ctx, `P${i + 1}`, 30, y + 16, 3, pal.tan);
      const mn = new Button(["wpm", i, -1], 108, y + 4, 52, 48);
      const pl = new Button(["wpm", i, 1], 340, y + 4, 52, 48);
      button(ctx, this.buttons, mn, "-", 3);
      button(ctx, this.buttons, pl, "+", 3);
      this.buttons.push(mn, pl);
      const v = String(this.vals[i]);
      const vw = measureText(v, 3);
      const gx = Math.floor(250 - (vw + 8 + 28) / 2);
      textLeft(ctx, v, gx, y + 16, 3, pal.gold);
      icons.drawIcon(ctx, icons.WILLPOWER_MD, gx + vw + 8, y + 14, pal.gold);
      y += 62;
    });
    const total = this.game.players.reduce(
      (a, p, i) => a + (p.eliminated ? 0 : this.vals[i]), 0);
    textLeft(ctx, "Total", 30, y + 18, 2, pal.muted);
    const tv = String(total);
    const vw = measureText(tv, 3);
    const gx = Math.floor(250 - (vw + 8 + 28) / 2);
    textLeft(ctx, tv, gx, y + 14, 3, pal.gold);
    icons.drawIcon(ctx, icons.WILLPOWER_MD, gx + vw + 8, y + 12, pal.gold);
    footer(ctx, this.buttons);
  }
  onButton(btn) {
    const k = btn.id[0];
    if (k === "wpm") {
      const [_, i, d] = btn.id;
      this.vals[i] = Math.max(0, Math.min(99, this.vals[i] + d));
      return null;
    }
    if (k === "save") {
      this.game.players.forEach((p, i) => {
        if (p.eliminated) return;
        if (this.vals[i] !== p.commit) {
          this.game.setCommit(i, this.vals[i]);
          this.game.logEvent(`P${i + 1} committed ${this.vals[i]} willpower`);
        }
      });
      return "close";
    }
    if (k === "cancel") return "cancel";
    return null;
  }
}

export class RemindersModal {
  constructor(game) { this.game = game; this.buttons = []; }
  draw(ctx) {
    this.buttons = [];
    rect(ctx, 0, 0, 480, 480, pal.bg);
    textLeft(ctx, `R${this.game.round} ${this.game.step}`, 10, 12, 2, pal.muted);
    textCenter(ctx, "Encounter Reminders", 240, 12, 2, pal.gold);
    textLeft(ctx, "X", 480 - 16 - measureText("X", 3), 8, 3, pal.no_fg);
    this.buttons.push(new Button(["close"], 330, 0, 150, 40));
    rect(ctx, 0, 40, 480, 1, pal.border);
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
    const committed = val + this.order.slice(0, this.pos)
      .reduce((a, i) => a + this.game.players[i].commit, 0);
    const remaining = this.order.slice(this.pos + 1)
      .reduce((a, i) => a + this.game.players[i].commit, 0);
    const p1 = `committed ${committed}`, p2 = `uncommitted ${remaining}`;
    const w1 = measureText(p1, 2), w2 = measureText(p2, 2);
    const x0 = Math.floor((480 - (w1 + 24 + w2)) / 2);
    textLeft(ctx, p1, x0, 226, 2, pal.green);
    textLeft(ctx, p2, x0 + w1 + 24, 226, 2, pal.dim);
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
  // All questing progress in one place: main quest, active location and each
  // side quest, with progress + quest-points editable; add/remove side
  // quests; shift the heading. Value edits are logged on close.
  constructor(game) {
    this.game = game;
    this.buttons = [];
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
    const items = [{ kind: "q", name: `Quest ${g.questLabel()}` }];
    if (g.active_location) items.push({ kind: "l", name: "Location", removable: true });
    g.side_quests.forEach((s, i) =>
      items.push({ kind: "s", idx: i, name: `Side Quest ${i + 1}`, sub: s.since || null, removable: true }));
    return items;
  }
  _row(ctx, it, y) {
    const g = this.game;
    let prog, pts, pfx;
    if (it.kind === "q") { prog = g.quest.progress; pts = g.quest.points; pfx = "q"; }
    else if (it.kind === "l") { prog = g.active_location.progress; pts = g.active_location.points; pfx = "l"; }
    else { prog = g.side_quests[it.idx].progress; pts = g.side_quests[it.idx].points; pfx = "s"; }
    panel(ctx, 12, y, 456, 58);
    textLeft(ctx, it.name, 22, y + 8, 2, pal.tan);
    if (it.sub) textLeft(ctx, `since ${it.sub}`, 22, y + 32, 1, pal.dim);
    const idx = it.idx ?? null;
    textLeft(ctx, "current", 166, y + 4, 1, pal.muted);
    stepper(ctx, this.buttons, [pfx + "P-", idx], [pfx + "P+", idx], 164, y + 16, String(prog), 130, 34);
    textLeft(ctx, "points", 304, y + 4, 1, pal.muted);
    stepper(ctx, this.buttons, [pfx + "T-", idx], [pfx + "T+", idx], 300, y + 16, String(pts), 130, 34);
    if (it.removable) {
      const rm = new Button([pfx + "X", idx], 438, y + 15, 28, 28);
      bevel(ctx, rm.x, rm.y, rm.w, rm.h, pal.btn_no);
      textCenter(ctx, "x", rm.x + 14, rm.y + 6, 2, pal.no_fg);
      this.buttons.push(rm);
    }
  }
  draw(ctx) {
    this.buttons = [];
    rect(ctx, 0, 0, 480, 480, pal.bg);
    textLeft(ctx, `R${this.game.round} ${this.game.step}`, 10, 12, 2, pal.muted);
    textCenter(ctx, "Questing Progress", 240, 12, 2, pal.gold);
    textLeft(ctx, "X", 480 - 16 - measureText("X", 3), 8, 3, pal.no_fg);
    this.buttons.push(new Button(["close"], 330, 0, 150, 40));
    rect(ctx, 0, 40, 480, 1, pal.border);
    let y = 48;
    for (const it of this._items()) { this._row(ctx, it, y); y += 62; }
    const add = new Button(["add"], 12, y, 456, 38);
    bevel(ctx, add.x, add.y, add.w, add.h, pal.btn);
    textCenter(ctx, "+ Add side quest", 240, y + 11, 2, pal.tan);
    this.buttons.push(add);
    y += 46;
    if (this.game.sailing) {
      const pen = this.game.heading === 0 ? pal.gold : this.game.heading === 3 ? pal.red : pal.amber;
      panel(ctx, 12, y, 456, 52);
      textLeft(ctx, "Heading", 22, y + 18, 2, pal.tan);
      drawWeather(ctx, this.game.heading, 176, y + 26, 12);
      textLeft(ctx, HEADINGS[this.game.heading][2], 196, y + 18, 2, pen);
      const mn = new Button(["hd", -1], 320, y + 10, 60, 32);
      const pl = new Button(["hd", 1], 388, y + 10, 60, 32);
      button(ctx, this.buttons, mn, "-", 3);
      button(ctx, this.buttons, pl, "+", 3);
      this.buttons.push(mn, pl);
    }
    const done = new Button(["close"], 12, 430, 456, 42);
    bevel(ctx, done.x, done.y, done.w, done.h, pal.btn_ok, false, 3);
    textCenter(ctx, "Done", 240, 442, 2, pal.ok_fg);
    this.buttons.push(done);
  }
  _clampAdj(cur, d) { return Math.max(0, Math.min(99, cur + d)); }
  onButton(btn) {
    const [k, a, b] = btn.id;
    const g = this.game;
    if (k === "qP-" || k === "qP+") { g.quest.progress = this._clampAdj(g.quest.progress, k.endsWith("+") ? 1 : -1); return null; }
    if (k === "qT-" || k === "qT+") { g.quest.points = this._clampAdj(g.quest.points, k.endsWith("+") ? 1 : -1); return null; }
    if (k === "lP-" || k === "lP+") { g.active_location.progress = this._clampAdj(g.active_location.progress, k.endsWith("+") ? 1 : -1); return null; }
    if (k === "lT-" || k === "lT+") { g.active_location.points = this._clampAdj(g.active_location.points, k.endsWith("+") ? 1 : -1); return null; }
    if (k === "lX") { g.active_location = null; g.logEvent("Active location cleared (progress view)"); return null; }
    if (k === "sP-" || k === "sP+") { const s = g.side_quests[a]; s.progress = this._clampAdj(s.progress, k.endsWith("+") ? 1 : -1); return null; }
    if (k === "sT-" || k === "sT+") { const s = g.side_quests[a]; s.points = this._clampAdj(s.points, k.endsWith("+") ? 1 : -1); return null; }
    if (k === "sX") { g.side_quests.splice(a, 1); g.logEvent(`Side quest ${a + 1} removed (progress view)`); return null; }
    if (k === "add") {
      g.side_quests.push({ points: 4, progress: 0, since: `R${g.round} ${g.step}` });
      g.logEvent(`Side quest ${g.side_quests.length} added (progress view)`);
      return null;
    }
    if (k === "hd") { g.shiftHeading(a, "progress view"); return null; }
    if (k === "close") { this._logChanges(); return "close"; }
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
    textLeft(ctx, `R${this.game.round} ${this.game.step}`, 10, 12, 2, pal.muted);
    textCenter(ctx, "Sailing test", 240, 12, 2, pal.gold);
    textLeft(ctx, "X", 480 - 16 - measureText("X", 3), 8, 3, pal.no_fg);
    this.buttons.push(new Button(["cancel"], 330, 0, 150, 40));
    rect(ctx, 0, 40, 480, 1, pal.border);

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
    if (k === "cancel") return "cancel";
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
    textCenter(ctx, `Stage ${this.cleared} cleared!`, 240, 26, 3, pal.gold);
    let y = 70;
    if (this.excess > 0) {
      textCenter(ctx, `${this.excess} excess progress discarded (rulebook)`,
                 240, y, 1, pal.dim);
      y += 20;
    }
    textCenter(ctx, "Set up the next stage", 240, y, 2, pal.tan);
    y += 40;
    textLeft(ctx, "Stage", 30, y + 14, 2, pal.tan);
    stepper(ctx, this.buttons, ["n", -1], ["n", 1], 190, y, String(this.n), 130, 52);
    ["A", "B"].forEach((s, idx) => {
      const b = new Button(["side", s], 336 + idx * 60, y, 52, 52);
      const on = this.side === s;
      panel(ctx, b.x, b.y, b.w, b.h, on ? pal.gold : pal.btn);
      textCenter(ctx, s, b.x + 26, b.y + 16, 3, on ? pal.bg : pal.tan, false);
      this.buttons.push(b);
    });
    y += 76;
    textLeft(ctx, "Quest points", 30, y + 14, 2, pal.tan);
    stepper(ctx, this.buttons, ["pts", -1], ["pts", 1], 240, y, String(this.pts), 210, 52);
    y += 90;
    const go = new Button(["go"], 30, y, 420, 60);
    bevel(ctx, go.x, go.y, go.w, go.h, pal.btn_ok, false, 3);
    textCenter(ctx, `Continue to ${this.n}${this.side} >`, 240, y + 20, 2, pal.ok_fg);
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
    if (k === "side") { this.side = btn.id[1]; return null; }
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
    ["A", "B"].forEach((s, idx) => {
      const b = new Button(["side", s], 300 + idx * 78, 142, 70, 52);
      const on = this.q.side === s;
      panel(ctx, b.x, b.y, b.w, b.h, on ? pal.gold : pal.btn);
      textCenter(ctx, s, b.x + 35, b.y + 16, 3, on ? pal.bg : pal.tan, false);
      this.buttons.push(b);
    });
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
    if (k === "side") { this.q.side = btn.id[1]; return null; }
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
