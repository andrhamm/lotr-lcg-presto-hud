// Ports of ui/screen_phases.py, screen_log.py, screen_settings.py,
// screen_boot.py, screen_setup.py + LedModal (virtual LED strip on web).
import { pal, Button, rect, panel, bevel, textLeft, textCenter, button,
         stepper, truncateText, ribbon } from "./ui.js";
import { measureText } from "./metrics.js";
import * as icons from "./icons.js";
import { viewForStep, DEFAULT_START_THREAT, MAX_PLAYERS } from "./gamestate.js";
import { PHASES, STEPS } from "./phases.js";
import { step as phaseStep } from "./phases.js";
import { drawHeader, HEADER_H } from "./screens.js";

export class ScreenPhases {
  constructor() { this.buttons = []; }
  draw(ctx, game) {
    this.buttons = [];
    rect(ctx, 0, 0, 480, 480, pal.bg);
    drawHeader(ctx, game, this.buttons, { title: "Game Phases", close: true });
    const curPhase = phaseStep(game.step).phase;
    let y = HEADER_H + 8;
    for (const ph of PHASES) {
      if (ph.id === "Beginning" || ph.id === "End") continue;
      const isCur = ph.id === curPhase;
      if (!isCur) {
        panel(ctx, 12, y, 456, 30);
        textLeft(ctx, ph.label, 24, y + 8, 2, pal.dim);
        this.buttons.push(new Button(["jump", ph.id], 12, y, 456, 30));
        y += 34;
      } else {
        const steps = STEPS.filter(s => s.phase === ph.id);
        const boxH = 34 + steps.length * 26;
        panel(ctx, 12, y, 456, boxH, pal.card_hi, pal.border_gold);
        textLeft(ctx, ph.label, 24, y + 8, 2, pal.gold);
        let sy = y + 32;
        for (const s of steps) {
          const active = s.id === game.step;
          if (active) rect(ctx, 20, sy - 2, 440, 24, pal.gold);
          const pen = active ? pal.bg : pal.tan;
          if (s.action_window) rect(ctx, 28, sy + 3, 8, 8, active ? pal.bg : pal.purple);
          let label = s.label;
          if (s.id === "6.E" || s.id === "6.P") label += "  (loops: each player)";
          textLeft(ctx, label, 42, sy + 2, 1, pen, !active);
          this.buttons.push(new Button(["step", s.id], 20, sy - 2, 440, 24));
          sy += 26;
        }
        y += boxH + 4;
      }
    }
    rect(ctx, 12, 436, 8, 8, pal.purple);
    textLeft(ctx, "= action window   tap a step to jump", 26, 434, 1, pal.dim);
    textLeft(ctx, "Combat loops in turn order: every enemy attacks, then", 12, 450, 1, pal.dim);
    textLeft(ctx, "every player attacks - first player resolves first.", 12, 464, 1, pal.dim);
  }
  onButton(btn, game) {
    const k = btn.id[0];
    if (k === "nav") return ["goto", btn.id[1]];
    if (k === "jump") {
      const first = STEPS.find(s => s.phase === btn.id[1]);
      if (first) game.step = first.id;
      game.view = viewForStep(game.step);
      return true;
    }
    if (k === "step") {
      game.step = btn.id[1];
      game.view = viewForStep(game.step);
      return true;
    }
    return null;
  }
}

export class ScreenLog {
  constructor() { this.buttons = []; this.page = 0; }
  draw(ctx, game) {
    const PER_PAGE = 13, ROW_H = 26;
    this.buttons = [];
    rect(ctx, 0, 0, 480, 480, pal.bg);
    drawHeader(ctx, game, this.buttons, { title: "Game Log", close: true });
    const entries = [...game.log].reverse();
    const pages = Math.max(1, Math.ceil(entries.length / PER_PAGE));
    this.page = Math.min(this.page, pages - 1);
    const chunk = entries.slice(this.page * PER_PAGE, (this.page + 1) * PER_PAGE);
    let y = HEADER_H + 10;
    if (!chunk.length) textCenter(ctx, "no activity yet", 240, 200, 2, pal.dim);
    for (const e of chunk) {
      textLeft(ctx, `R${e.round}.${e.step}`, 12, y, 1, pal.dim);
      if (e.t !== null && e.t !== undefined) {
        const s = Math.floor(e.t / 1000);
        textLeft(ctx, `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`,
                 76, y, 1, pal.dim);
      }
      textLeft(ctx, truncateText(e.text, 1, 480 - 122 - 12), 122, y, 1, pal.tan);
      y += ROW_H;
    }
    if (pages > 1) {
      const up = new Button(["older"], 12, 420, 150, 46);
      const dn = new Button(["newer"], 318, 420, 150, 46);
      bevel(ctx, up.x, up.y, up.w, up.h, pal.btn);
      textCenter(ctx, "Older", up.x + 75, up.y + 14, 2, pal.tan);
      bevel(ctx, dn.x, dn.y, dn.w, dn.h, pal.btn);
      textCenter(ctx, "Newer", dn.x + 75, dn.y + 14, 2, pal.tan);
      textCenter(ctx, `${this.page + 1}/${pages}`, 240, 434, 2, pal.muted);
      this.buttons.push(up, dn);
    }
  }
  onButton(btn) {
    const k = btn.id[0];
    if (k === "nav") return ["goto", btn.id[1]];
    if (k === "older") { this.page += 1; return true; }
    if (k === "newer") { this.page = Math.max(0, this.page - 1); return true; }
    return null;
  }
}

export class LedModal {
  constructor(prefs, game) { this.prefs = prefs; this.game = game; this.buttons = []; }
  draw(ctx) {
    const SCENES = ["phase", "danger", "torch", "off"];
    const LABELS = { phase: "Phase + danger", danger: "Danger only",
                     torch: "Torchlight", off: "Off" };
    this.buttons = [];
    rect(ctx, 0, 0, 480, 480, pal.bg);
    textCenter(ctx, "LED behavior", 240, 22, 3, pal.gold);
    textLeft(ctx, `Brightness  ${this.prefs.brightness}%`, 24, 70, 2, pal.tan);
    const segW = 42, segH = 52, x0 = 24, y0 = 100;
    const lit = Math.floor(this.prefs.brightness / 10);
    for (let i = 0; i < 10; i++) {
      const x = x0 + i * (segW + 2);
      panel(ctx, x, y0, segW, segH, i < lit ? pal.gold : pal.btn,
            i < lit ? pal.border_gold : pal.border);
      this.buttons.push(new Button(["bri", (i + 1) * 10], x, y0, segW, segH));
    }
    textLeft(ctx, "Scene", 24, 182, 2, pal.tan);
    const half = Math.floor((480 - 3 * 24) / 2);
    SCENES.forEach((key, i) => {
      const x = 24 + (i % 2) * (half + 24);
      const y = 210 + Math.floor(i / 2) * 70;
      const on = this.prefs.scene === key;
      const b = new Button(["scene", key], x, y, half, 58);
      panel(ctx, b.x, b.y, b.w, b.h, on ? pal.card_hi : pal.card,
            on ? pal.border_gold : pal.border);
      textCenter(ctx, LABELS[key], x + half / 2, y + 20, 2, on ? pal.gold : pal.muted);
      this.buttons.push(b);
    });
    const done = new Button(["save"], 24, 396, 432, 62);
    bevel(ctx, done.x, done.y, done.w, done.h, pal.btn_ok, false, 3);
    textCenter(ctx, "Done", 240, done.y + 20, 2, pal.ok_fg);
    this.buttons.push(done);
  }
  onButton(btn) {
    const k = btn.id[0];
    if (k === "bri") { this.prefs.brightness = btn.id[1]; return null; }
    if (k === "scene") { this.prefs.scene = btn.id[1]; return null; }
    if (k === "save") return "close";
    return null;
  }
}

export class ScreenSettings {
  constructor(prefs) {
    this.prefs = prefs;
    this.buttons = [];
    this.confirmEnd = false;
  }
  draw(ctx, game) {
    const TILE = 100;
    this.buttons = [];
    rect(ctx, 0, 0, 480, 480, pal.bg);
    drawHeader(ctx, game, this.buttons, { title: "Settings", close: true });
    let y = HEADER_H + 16;
    textLeft(ctx, "GAME", 16, y, 1, pal.dim);
    y += 18;
    const sq = new Button(["save_quit"], 16, y, 452, 56);
    bevel(ctx, sq.x, sq.y, sq.w, sq.h, pal.btn, false, 3);
    textCenter(ctx, "Save & Quit", 240, y + 18, 2, pal.tan);
    this.buttons.push(sq);
    y += 66;
    let b;
    if (this.confirmEnd) {
      b = new Button(["end_game2"], 16, y, 452, 56);
      bevel(ctx, b.x, b.y, b.w, b.h, pal.btn_no, false, 3);
      textCenter(ctx, "Really end? Save will be deleted", 240, y + 18, 2, pal.no_fg);
    } else {
      b = new Button(["end_game"], 16, y, 452, 56);
      bevel(ctx, b.x, b.y, b.w, b.h, pal.card, false, 3);
      textCenter(ctx, "End Game", 240, y + 18, 2, pal.no_fg);
    }
    this.buttons.push(b);
    y += 76;
    textLeft(ctx, "DEVICE", 16, y, 1, pal.dim);
    y += 18;
    bevel(ctx, 16, y, TILE, TILE, pal.card);
    icons.drawIcon(ctx, icons.LED, 16 + 30, y + 14, pal.gold, 2);
    textCenter(ctx, "LEDs", 16 + TILE / 2, y + TILE - 22, 1, pal.tan);
    this.buttons.push(new Button(["led"], 16, y, TILE, TILE));
    const ax = 16 + TILE + 16;
    bevel(ctx, ax, y, TILE, TILE, pal.card);
    icons.drawIcon(ctx, icons.LORE, ax + 26, y + 16, pal.gold, 2);
    textCenter(ctx, "About", ax + TILE / 2, y + TILE - 22, 1, pal.tan);
    this.buttons.push(new Button(["about"], ax, y, TILE, TILE));
    y += TILE + 24;
    textLeft(ctx, "APPS  (coming soon)", 16, y, 1, pal.dim);
    y += 18;
    let x = 16;
    for (const [icon, label] of [[icons.WIFI, "Network"], [icons.MUSIC, "Tunes"]]) {
      bevel(ctx, x, y, TILE, TILE, pal.card);
      icons.drawIcon(ctx, icon, x + 30, y + 14, pal.dim, 2);
      textCenter(ctx, label, x + TILE / 2, y + TILE - 22, 1, pal.dim);
      x += TILE + 16;
    }
  }
  onButton(btn, game) {
    const k = btn.id[0];
    if (k === "nav") { this.confirmEnd = false; return ["goto", btn.id[1]]; }
    if (k === "led") return ["modal", new LedModal(this.prefs, game)];
    if (k === "about") return ["goto", "about"];
    if (k === "save_quit") { this.confirmEnd = false; return ["save_quit"]; }
    if (k === "end_game") { this.confirmEnd = true; return true; }
    if (k === "end_game2") { this.confirmEnd = false; return ["end_game"]; }
    return null;
  }
}

export class GameOverScreen {
  constructor() { this.buttons = []; }
  draw(ctx, game) {
    this.buttons = [];
    rect(ctx, 0, 0, 480, 480, pal.bg);
    const win = game.game_over?.result === "victory";
    textCenter(ctx, win ? "VICTORY!" : "DEFEAT", 240, 64, 5,
               win ? pal.gold : pal.red);
    textCenter(ctx, win ? "The final quest stage is complete."
                        : "All players have been eliminated.", 240, 132, 2, pal.tan);
    let y = 190;
    const line = (label, val) => {
      textLeft(ctx, label, 120, y, 2, pal.muted);
      textLeft(ctx, String(val), 300, y, 2, pal.gold);
      y += 30;
    };
    line("Rounds", game.game_over?.round ?? game.round);
    if (game.game_over?.duration) line("Duration", game.game_over.duration);
    game.players.forEach((p, i) => {
      line(`P${i + 1} threat`, p.eliminated ? `${p.threat} (out)` : p.threat);
    });
    const fin = new Button(["finish"], 100, 396, 280, 58);
    bevel(ctx, fin.x, fin.y, fin.w, fin.h, pal.btn_ok, false, 3);
    textCenter(ctx, "Finish - clear save", 240, 414, 2, pal.ok_fg);
    this.buttons.push(fin);
    const back = new Button(["back"], 180, 356, 120, 32);
    textCenter(ctx, "back to game", 240, 364, 1, pal.dim);
    this.buttons.push(back);
  }
  onButton(btn, game) {
    if (btn.id[0] === "finish") return ["end_game"];
    if (btn.id[0] === "back") {
      game.game_over = null;
      game.logEvent("Game over dismissed - back to the table");
      return ["goto", "play"];
    }
    return null;
  }
}

export class ScreenAbout {
  constructor() { this.buttons = []; }
  draw(ctx, game) {
    this.buttons = [];
    rect(ctx, 0, 0, 480, 480, pal.bg);
    drawHeader(ctx, game, this.buttons, { title: "About", close: true });
    let y = HEADER_H + 18;
    textCenter(ctx, "LOTR LCG HUD", 240, y, 3, pal.gold);
    y += 42;
    const para = (lines, color) => {
      for (const ln of lines) {
        textCenter(ctx, ln, 240, y, 2, color);
        y += 22;
      }
      y += 12;
    };
    para(["A companion tracker for the table."], pal.tan);
    para(["An unofficial fan project for",
          "The Lord of the Rings: The Card Game.",
          "Not endorsed, supported by, or affiliated",
          "with Fantasy Flight Publishing, Inc."], pal.muted);
    para(["The Lord of the Rings and its characters",
          "are trademarks of Middle-earth Enterprises,",
          "used under license by Fantasy Flight Games."], pal.muted);
    para(["Turn sequence: DragnCards plugin (seastan).",
          "Icons: lotr-lcg-assets (KevBelisle)."], pal.muted);
    const label = "made with <3 by";
    const handle = "@andrhamm";
    const lw = measureText(label, 2), hw = measureText(handle, 2);
    const total = lw + 8 + 20 + 6 + hw;
    let x = 240 - Math.floor(total / 2);
    const by = 402;
    const b = new Button(["repo"], x - 10, by - 12, total + 20, 44);
    bevel(ctx, b.x, b.y, b.w, b.h, pal.card, false, 2);
    textLeft(ctx, label, x, by, 2, pal.tan);
    x += lw + 8;
    icons.drawIcon(ctx, icons.GITHUB, x, by - 2, pal.gold);
    x += 20 + 6;
    textLeft(ctx, handle, x, by, 2, pal.gold);
    this.buttons.push(b);
  }
  onButton(btn) {
    const k = btn.id[0];
    if (k === "nav") return ["goto", btn.id[1]];
    if (k === "repo") return ["open_repo"];
    return null;
  }
}

export class BootScreen {
  constructor(savedMeta, bootImg) {
    this.saved = savedMeta;
    this.bootImg = bootImg;   // HTMLImageElement or null
    this.buttons = [];
  }
  _button(ctx, id, label, sub, y, h, primary) {
    const b = new Button(id, 100, y, 280, h);
    bevel(ctx, b.x, b.y, b.w, b.h, primary ? pal.btn_ok : pal.btn, false, 3);
    const ty = b.y + Math.floor((h - (sub ? 26 : 16)) / 2);
    textCenter(ctx, label, 240, ty, 2, primary ? pal.gold : pal.tan);
    if (sub) textCenter(ctx, sub, 240, ty + 20, 1, pal.muted);
    this.buttons.push(b);
  }
  draw(ctx) {
    this.buttons = [];
    if (this.bootImg && this.bootImg.complete) {
      ctx.imageSmoothingEnabled = false;
      ctx.drawImage(this.bootImg, 0, 0, 480, 480);
    } else {
      rect(ctx, 0, 0, 480, 480, pal.bg);
      textCenter(ctx, "LOTR LCG", 240, 120, 4, pal.gold);
      textCenter(ctx, "THE CARD GAME", 240, 170, 2, pal.tan);
    }
    if (this.saved) {
      const sub = `R${this.saved.round} - ${this.saved.phase} (${this.saved.saved_at})`;
      this._button(ctx, ["resume"], "Resume Game", sub, 344, 58, true);
      this._button(ctx, ["new"], "New Game", null, 410, 48, false);
    } else {
      this._button(ctx, ["new"], "New Game", null, 388, 58, true);
    }
    const dw = measureText("disclaimers", 2);
    const dx = 240 - Math.floor(dw / 2);
    for (const [ox, oy] of [[-1, 0], [1, 0], [0, -1], [0, 1], [1, 1]]) {
      textLeft(ctx, "disclaimers", dx + ox, 462 + oy, 2, pal.tan, false);
    }
    textLeft(ctx, "disclaimers", dx, 462, 2, pal.outline, false);
    this.buttons.push(new Button(["about"], dx - 12, 450, dw + 24, 30));
  }
  onButton(btn) { return ["boot", btn.id[0]]; }
}

export class SetupScreen {
  constructor() {
    this.threats = [DEFAULT_START_THREAT];
    this.first = 0;
    this.hasSave = false;
    this.buttons = [];
  }
  draw(ctx) {
    const ROW_H = 62, ROW_GAP = 10;
    this.buttons = [];
    rect(ctx, 0, 0, 480, 480, pal.bg);
    textCenter(ctx, "New game", 240, 16, 3, pal.gold);
    if (this.threats.length > 1) {
      textLeft(ctx, "tap a row to set the first player", 24, 52, 2, pal.dim);
    }
    this.first = Math.min(this.first, this.threats.length - 1);
    const rowButtons = [];
    let y = 84;
    this.threats.forEach((t, i) => {
      panel(ctx, 16, y, 448, ROW_H);
      textLeft(ctx, `P${i + 1}`, 30, y + 19, 3, pal.tan);
      if (i === this.first) ribbon(ctx, 16 + 448 - 26, y + 1);
      icons.drawIcon(ctx, icons.THREAT, 82, y + 21, pal.red);
      stepper(ctx, this.buttons, ["st", i, -1], ["st", i, 1], 108, y + 7, String(t), 210, 48);
      if (this.threats.length > 1) {
        const rm = new Button(["rm", i], 340, y + 7, 48, 48);
        bevel(ctx, rm.x, rm.y, rm.w, rm.h, pal.btn_no);
        textCenter(ctx, "x", rm.x + 24, rm.y + 12, 3, pal.no_fg);
        this.buttons.push(rm);
        rowButtons.push(new Button(["fp", i], 16, y, 448, ROW_H));
      }
      y += ROW_H + ROW_GAP;
    });
    if (this.threats.length < MAX_PLAYERS) {
      const add = new Button(["add"], 16, y, 448, 50);
      bevel(ctx, add.x, add.y, add.w, add.h, pal.btn);
      textCenter(ctx, "+ Add player", 240, y + 15, 2, pal.tan);
      this.buttons.push(add);
    }
    const sb = new Button(["start"], 60, 388, 360, 62);
    bevel(ctx, sb.x, sb.y, sb.w, sb.h, pal.btn_ok, false, 3);
    textCenter(ctx, "Start", 240, 404, 3, pal.gold);
    this.buttons.push(sb);
    if (this.hasSave) {
      textCenter(ctx, "starting a new game overwrites the saved one", 240, 458, 2, pal.no_fg);
    }
    this.buttons.push(...rowButtons);
  }
  onButton(btn) {
    const k = btn.id[0];
    if (k === "st") {
      const [, i, d] = btn.id;
      this.threats[i] = Math.max(0, Math.min(60, this.threats[i] + d));
      return "redraw";
    }
    if (k === "add") { this.threats.push(DEFAULT_START_THREAT); return "redraw"; }
    if (k === "rm") {
      this.threats.splice(btn.id[1], 1);
      if (this.first >= this.threats.length) this.first = 0;
      return "redraw";
    }
    if (k === "fp") { this.first = btn.id[1]; return "redraw"; }
    if (k === "start") return ["start_game", [...this.threats], this.first];
    return null;
  }
}
