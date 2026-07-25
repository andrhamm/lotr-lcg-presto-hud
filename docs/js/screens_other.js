// Ports of ui/screen_phases.py, screen_log.py, screen_settings.py,
// screen_boot.py, screen_setup.py, screen_quest.py + LedModal (virtual LED
// strip on web).
import { pal, Button, rect, panel, bevel, textLeft, textCenter, button,
         stepper, truncateText, wrapText, ribbon, disc, arcRuns, notePanel, token } from "./ui.js";
import { measureText } from "./metrics.js";
import * as icons from "./icons.js";
import { viewForStep, DEFAULT_START_THREAT, MAX_PLAYERS } from "./gamestate.js";
import { PHASES, STEPS } from "./phases.js";
import { step as phaseStep } from "./phases.js";
import { drawHeader, HEADER_H, QuestCardModal } from "./screens.js";
import { iconFor, slugify } from "./quest_catalog.js";

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
    const hx = ax + TILE + 16;
    bevel(ctx, hx, y, TILE, TILE, pal.card);
    icons.drawIcon(ctx, icons.PIPE, hx + 26, y + 16, pal.gold, 2);
    textCenter(ctx, "Help", hx + TILE / 2, y + TILE - 22, 1, pal.tan);
    this.buttons.push(new Button(["help"], hx, y, TILE, TILE));
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
    if (k === "help") { this.confirmEnd = false; return ["goto", "firstrun"]; }
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
    const back = new Button(["back"], 150, 358, 180, 34);
    bevel(ctx, back.x, back.y, back.w, back.h, pal.card, false, 2);
    textCenter(ctx, "back to game", 240, back.y + 9, 2, pal.tan);
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
    para(["The Lord of the Rings, its characters and",
          "game iconography are trademarks of",
          "Middle-earth Enterprises, used under",
          "license by Fantasy Flight Games."], pal.muted);
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
      this._button(ctx, ["resume"], "Resume Game", sub, 336, 58, true);
      this._button(ctx, ["new"], "New Game", null, 402, 48, false);
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

// ---------------------------------------------------------------- quest picker (M4-B Tasks 4-6)
// Pre-game scenario picker: Scenario Source (source gate) -> Pick Cycle
// (drill into one cycle) -> Choose Scenario (radio + submit). Firmware twin:
// ui/screen_quest.py. Routing (Task 9) constructs PickCycleScreen(source,
// cycles) from quest_catalog.cyclesFor(index, source) and
// ChooseScenarioScreen(source, cycle, scenarios) from one group's
// .scenarios (quest_catalog.groupByCycle).

// Right-pointing row-disclosure triangle (list rows drill further in).
function chevronRight(ctx, cx, cy, pen) {
  ctx.fillStyle = pen;
  ctx.beginPath();
  ctx.moveTo(cx, cy - 5);
  ctx.lineTo(cx, cy + 5);
  ctx.lineTo(cx + 5, cy);
  ctx.closePath();
  ctx.fill();
}

// Radio-button glyph: ring, filled when selected (mirrors mock_quest.py's radio()).
function radioGlyph(ctx, cx, cy, on) {
  arcRuns(ctx, cx, cy, 10, 8, 0, 360, on ? pal.gold : pal.dim);
  if (on) disc(ctx, cx, cy, 5, pal.gold);
}

// Downward-pointing disclosure triangle (dropdown "tap to open" affordance;
// mirrors mock_quest.py's chevron(..., down=True)).
function chevronDown(ctx, cx, cy, pen) {
  ctx.fillStyle = pen;
  ctx.beginPath();
  ctx.moveTo(cx - 5, cy - 2);
  ctx.lineTo(cx + 5, cy - 2);
  ctx.lineTo(cx, cy + 4);
  ctx.closePath();
  ctx.fill();
}

// Bordered well for a scenario/set icon (M4-B icons, Task 3). When `mask`
// is a real rasterized icon (tools/build_icons.py's 24x24 masks, matched
// via quest_catalog.iconFor) it's drawn centred in the well with
// icons.drawIcon() - the same primitive the stat icons already use, since
// it derives its size from the mask itself rather than hardcoding one; the
// flat [int,...] array icons.json/iconFor deal in is wrapped as the
// [size, rows] pair drawIcon expects (icons.js's own hardcoded constants,
// e.g. icons.THREAT, are already shaped that way - only the dynamically
// loaded catalog masks need the wrap). With no match (mask is null -
// unmatched set, or icons.json unavailable) this keeps today's placeholder
// triangle glyph, exactly as before. Mirrors mock_quest.py's icon_slot().
function iconSlot(ctx, x, y, s, glyphPen = null, mask = null) {
  panel(ctx, x, y, s, s, pal.iconslot);
  if (mask) {
    const msize = mask.length;
    const off = Math.max(0, Math.floor((s - msize) / 2));
    icons.drawIcon(ctx, [msize, mask], x + off, y + off, glyphPen ?? pal.gold, 1);
  } else {
    ctx.fillStyle = glyphPen ?? pal.dim;
    ctx.beginPath();
    ctx.moveTo(x + s / 2, y + 5);
    ctx.lineTo(x + 5, y + s - 5);
    ctx.lineTo(x + s - 5, y + s - 5);
    ctx.closePath();
    ctx.fill();
  }
}

export class ScenarioSourceScreen {
  // Source gate: Official (FFG) vs Community (ALeP) scenarios. Stateless -
  // two big bevel buttons, no tip.
  constructor() { this.buttons = []; }
  draw(ctx, game) {
    this.buttons = [];
    rect(ctx, 0, 0, 480, 480, pal.bg);
    drawHeader(ctx, game, this.buttons, { title: "SCENARIO SOURCE", roundLabel: "R0" });

    const off = new Button(["choose_scenario", "official"], 24, 96, 432, 120);
    bevel(ctx, off.x, off.y, off.w, off.h, pal.btn);
    textCenter(ctx, "Official Scenarios", 240, 128, 3, pal.gold);
    textCenter(ctx, "Fantasy Flight Games content", 240, 168, 2, pal.muted);
    this.buttons.push(off);

    const com = new Button(["choose_scenario", "alep"], 24, 244, 432, 120);
    bevel(ctx, com.x, com.y, com.w, com.h, pal.btn);
    textCenter(ctx, "Community Scenarios", 240, 276, 3, pal.gold);
    textCenter(ctx, "Community created content", 240, 316, 2, pal.muted);
    this.buttons.push(com);
  }
  onButton(btn) {
    const k = btn.id[0];
    if (k === "nav") return ["goto", btn.id[1]];
    if (k === "choose_scenario") return btn.id;
    return null;
  }
}

export class PickCycleScreen {
  // Cycle list for one source ("official"/"alep"): name / release date or
  // quest count / chevron, Log-style pager, plus a pinned "Custom" row that
  // bypasses the catalog entirely. Empty (no cycles for this source, e.g.
  // Community pre-ALeP) renders a graceful placeholder instead of a blank
  // list.
  static PER_PAGE = 7;
  static ROW_H = 44;
  static ROW_STRIDE = 45;
  static LIST_Y0 = 50;
  static CUSTOM_Y = 370;
  static CUSTOM_H = 38;

  constructor(source, cycles) {
    this.source = source;
    this.cycles = cycles;   // [{cycle, date, count}, ...] (quest_catalog.cyclesFor)
    this.page = 0;
    this.buttons = [];
  }
  _pages() { return Math.max(1, Math.ceil(this.cycles.length / PickCycleScreen.PER_PAGE)); }
  draw(ctx, game) {
    const { PER_PAGE, ROW_H, ROW_STRIDE, LIST_Y0, CUSTOM_Y, CUSTOM_H } = PickCycleScreen;
    this.buttons = [];
    rect(ctx, 0, 0, 480, 480, pal.bg);
    rect(ctx, 0, 0, 480, 40, pal.card);
    rect(ctx, 0, 40, 480, 1, pal.border);
    textLeft(ctx, "< Source", 12, 12, 2, pal.muted);
    textCenter(ctx, "CHOOSE CYCLE", 250, 12, 2, pal.gold);
    this.buttons.push(new Button(["back"], 0, 0, 150, 40));

    const pages = this._pages();
    this.page = Math.min(this.page, pages - 1);
    const chunk = this.cycles.slice(this.page * PER_PAGE, (this.page + 1) * PER_PAGE);

    if (!this.cycles.length) {
      const msg = this.source === "alep" ? "No community scenarios yet" : "No official scenarios yet";
      textCenter(ctx, msg, 240, 200, 2, pal.dim);
    } else {
      let y = LIST_Y0;
      for (const { cycle, date, count } of chunk) {
        const name = truncateText(cycle, 2, 320);
        textLeft(ctx, name, 20, y + 13, 2, pal.tan);
        const right = date ?? `${count} quest${count === 1 ? "" : "s"}`;
        const rw = measureText(right, 1);
        textLeft(ctx, right, 440 - rw, y + 16, 1, pal.dim);
        chevronRight(ctx, 452, y + 22, pal.dim);
        rect(ctx, 8, y + ROW_H, 456, 1, pal.border);
        this.buttons.push(new Button(["cycle", cycle], 8, y, 456, ROW_H));
        y += ROW_STRIDE;
      }
    }

    const custom = new Button(["custom"], 8, CUSTOM_Y, 464, CUSTOM_H);
    bevel(ctx, custom.x, custom.y, custom.w, custom.h, pal.btn);
    textCenter(ctx, "Custom / uncatalogued quest", 240, CUSTOM_Y + 12, 2, pal.tan);
    this.buttons.push(custom);

    rect(ctx, 0, 410, 480, 1, pal.border);
    if (pages > 1) {
      const up = new Button(["older"], 12, 420, 150, 46);
      const dn = new Button(["newer"], 318, 420, 150, 46);
      bevel(ctx, up.x, up.y, up.w, up.h, pal.btn);
      textCenter(ctx, "Up", up.x + 75, up.y + 14, 2, pal.tan);
      bevel(ctx, dn.x, dn.y, dn.w, dn.h, pal.btn);
      textCenter(ctx, "Down", dn.x + 75, dn.y + 14, 2, pal.tan);
      textCenter(ctx, `${this.page + 1}/${pages}`, 240, 434, 2, pal.muted);
      this.buttons.push(up, dn);
    }
  }
  onButton(btn) {
    const k = btn.id[0];
    if (k === "back") return ["goto", "scenario_source"];
    if (k === "cycle") return ["choose_scenario_list", this.source, btn.id[1]];
    if (k === "custom") return ["start_custom"];
    if (k === "older") { this.page = Math.max(0, this.page - 1); return "redraw"; }
    if (k === "newer") { this.page = Math.min(this._pages() - 1, this.page + 1); return "redraw"; }
    return null;
  }
}

export class ChooseScenarioScreen {
  // Radio-select scenario list for one cycle: circle + name (no chevron, no
  // stage count - Task 6), one selection, Submit CTA, Log-style pager.
  static PER_PAGE = 6;
  static ROW_STRIDE = 46;
  static LIST_Y0 = 66;

  constructor(source, cycle, scenarios) {
    this.source = source;
    this.cycle = cycle;
    this.scenarios = scenarios;   // [{slug, name, ...}, ...] (one group_by_cycle group)
    this.selected = scenarios[0]?.slug ?? null;
    this.page = 0;
    this.buttons = [];
  }
  _pages() { return Math.max(1, Math.ceil(this.scenarios.length / ChooseScenarioScreen.PER_PAGE)); }
  draw(ctx, game) {
    const { PER_PAGE, ROW_STRIDE, LIST_Y0 } = ChooseScenarioScreen;
    this.buttons = [];
    rect(ctx, 0, 0, 480, 480, pal.bg);
    rect(ctx, 0, 0, 480, 52, pal.card);
    rect(ctx, 0, 52, 480, 1, pal.border);
    textLeft(ctx, "< Cycles", 12, 8, 2, pal.muted);
    textCenter(ctx, "Choose Scenario", 250, 6, 2, pal.gold);
    textCenter(ctx, truncateText(`Cycle: ${this.cycle}`, 1, 440), 250, 30, 1, pal.dim);
    this.buttons.push(new Button(["back"], 0, 0, 150, 52));

    const pages = this._pages();
    this.page = Math.min(this.page, pages - 1);
    const chunk = this.scenarios.slice(this.page * PER_PAGE, (this.page + 1) * PER_PAGE);

    let y = LIST_Y0;
    for (const scn of chunk) {
      const on = scn.slug === this.selected;
      if (on) rect(ctx, 8, y, 456, 44, pal.card_hi);
      radioGlyph(ctx, 30, y + 22, on);
      const name = truncateText(scn.name, 2, 400);
      textLeft(ctx, name, 52, y + 13, 2, on ? pal.tan : pal.muted);
      rect(ctx, 8, y + 44, 456, 1, pal.border);
      this.buttons.push(new Button(["scn", scn.slug], 8, y, 456, 44));
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

    const submit = new Button(["submit"], 130, 414, 220, 52);
    bevel(ctx, submit.x, submit.y, submit.w, submit.h, pal.btn_ok, false, 3);
    textCenter(ctx, "Submit", 240, 432, 3, pal.ok_fg);
    this.buttons.push(submit);
  }
  onButton(btn) {
    const k = btn.id[0];
    if (k === "back") return ["goto_pick_cycle", this.source];
    if (k === "scn") { this.selected = btn.id[1]; return "redraw"; }
    if (k === "older") { this.page = Math.max(0, this.page - 1); return "redraw"; }
    if (k === "newer") { this.page = Math.min(this._pages() - 1, this.page + 1); return "redraw"; }
    if (k === "submit") return this.selected ? ["scenario_chosen", this.selected] : null;
    return null;
  }
}

export class ScenarioOptionsScreen {
  // Scenario Options (Task 7): the chosen scenario (tap to reopen the
  // chooser) + a "sets to gather" list + Difficulty/Mode dropdowns (each
  // opens an OptionListModal) + a conditional contextual tip + a "Begin
  // Setup" CTA. Mirrors mock_quest.py's frame_options().
  //
  // Constructed with `scenario` (the catalog index entry: slug/name/pack/
  // cycle/source/...), `data` (the loaded per-scenario JSON - routing
  // stashes this here after loadScenario(slug) so "begin_setup" can hand
  // its stages to preloadScenario without re-fetching), and `icons` (M4-B
  // icons, Task 3: the loaded docs/data/icons.json "icons" map, or {} - the
  // router loads it once alongside the catalog index and passes it
  // through, same as `data`; a miss/failure just means every iconSlot()
  // falls back to its placeholder triangle, never a crash).
  // Easy and Standard always apply: Easy is a general rule (drop every
  // encounter card whose set icon carries the gold difficulty ring), not a
  // per-scenario card. Anything else - Hard, Epic Multiplayer - only exists as
  // a printed Mode card on the handful of scenarios that ship one, so it is
  // offered only when this scenario's catalog entry lists it. Of 349 scenarios
  // exactly one prints a Hard Mode card and three print Epic Multiplayer.
  // Nightmare is a rung on this ladder, not a second dropdown: no scenario
  // ships both a printed Mode card and a Nightmare deck, so splitting them
  // bought exactly one combination (Easy + Nightmare) and forced the tip
  // panel to shrink its text whenever both showed. It is per-scenario too -
  // only 68 of 349 have a Nightmare deck (`hasNightmare`).
  static BASE_DIFFICULTY_OPTIONS = ["Easy", "Standard"];
  static GATHER_Y0 = 116;
  static GATHER_ROW_H = 30;
  static MAX_GATHER_ROWS = 4;
  // The Difficulty row: dropdown + "Quest card" button, together spanning the
  // 16..464 content width. 124 leaves 14px either side of the label at scale 2
  // (96px), and the dropdown still clears its widest value, "Epic Multiplayer"
  // (150px), inside its 26px of chrome.
  static CARD_BTN_W = 124;
  static CARD_BTN_X = 480 - 16 - 124;
  static DD_W = 480 - 16 - 124 - 8 - 16;
  static CTA_Y = 410;
  static CTA_H = 54;

  // Only Easy and Nightmare get authored copy, because only those two are
  // general rules. A scenario-specific mode (Hard, Epic Multiplayer) shows that
  // card's own printed setup text instead - the real rules, not a paraphrase.
  // Both wordings follow FFG's own, not a paraphrase (CLAUDE.md Iron rule #4):
  // Easy is TWO steps - Learn to Play p.28 / Easy Mode Rules (2013) p.1: add
  // one resource to each hero's pool, AND remove any card with a gold border
  // around its encounter set icon (FFG's "difficulty" indicator). Nightmare is
  // a swap, per the printed Nightmare Setup card: remove the listed cards, then
  // "shuffle the encounter cards in this Nightmare Deck into the remainder".
  // Kept to at most 3 lines at scale 2 so the tip fits unclipped even with 4
  // sets-to-gather rows. There is a test for that.
  static TIP_TEXT = {
    Easy: "Easy: add 1 resource to each hero at setup, and remove every encounter card with a gold-bordered set icon.",
    Nightmare: "Nightmare: a separately sold deck - remove the cards its setup card lists, then shuffle it into the rest.",
  };

  constructor(scenario, data, icons = {}, difficulty = "Standard") {
    this.scenario = scenario;
    this.data = data || {};
    this.icons = icons ?? {};
    this.difficulty = difficulty;
    this.buttons = [];
  }

  // -- data shaping ---------------------------------------------------
  _gatherSets() {
    // B-data: the real multi-set gather list, merged into the per-scenario
    // JSON by build_card_data.py from Hall of Beorn's sets-to-gather
    // enrichment (tools/build_hob_enrichment.py) - see docs/superpowers/
    // plans/2026-07-24-catalog-enrichment.md. Falls back to the scenario's
    // own set alone when enrichment wasn't merged for this scenario (an API
    // miss/skip at build time, no enrichment.json at all, or a pre-B-data
    // catalog build) - never a crash, never an empty list.
    const sets = this.data.includedSets
      ?? [this.data.name ?? this.scenario.name ?? "Unknown scenario"];
    return sets.filter(Boolean);
  }

  _gatherRows() {
    // [[label, isMore], ...], at most MAX_GATHER_ROWS entries - a "+N more"
    // row (isMore=true, no icon slot) replaces the tail when the
    // scenario's real gather list runs long.
    const { MAX_GATHER_ROWS } = ScenarioOptionsScreen;
    const sets = this._gatherSets();
    if (sets.length <= MAX_GATHER_ROWS) return sets.map(s => [s, false]);
    const shown = sets.slice(0, MAX_GATHER_ROWS - 1);
    return [...shown.map(s => [s, false]), [`+${sets.length - shown.length} more`, true]];
  }

  _scenarioModes() {
    return (this.scenario.modes ?? [])
      .map(n => n.replace(" Mode", "").replace(" Game", "").trim())
      .filter(l => l && !["standard", "normal"].includes(l.toLowerCase()));
  }

  difficultyOptions() {
    const extra = this._scenarioModes().filter(m => m.toLowerCase() !== "easy");
    const opts = [...ScenarioOptionsScreen.BASE_DIFFICULTY_OPTIONS, ...extra];
    if (this.scenario.hasNightmare) opts.push("Nightmare");
    return opts;
  }

  _modeCardText(label) {
    for (const card of this.data.modes ?? []) {
      const name = (card.name ?? "").replace(" Mode", "").replace(" Game", "").trim();
      if (name === label) {
        for (const face of card.faces ?? []) if (face.text) return face.text;
      }
    }
    return null;
  }

  // At most one message - the tip always renders at the same size, so it must
  // never have to fit two (see the scale note in draw()).
  _tipMessages() {
    const { TIP_TEXT } = ScenarioOptionsScreen;
    if (TIP_TEXT[this.difficulty]) return [TIP_TEXT[this.difficulty]];
    if (this.difficulty === "Standard") return [];
    return [this._modeCardText(this.difficulty)
            ?? `${this.difficulty}: follow this quest's ${this.difficulty} Mode card.`];
  }

  // -- draw -------------------------------------------------------------
  draw(ctx, game) {
    const { GATHER_Y0, GATHER_ROW_H, CTA_Y, CTA_H } = ScenarioOptionsScreen;
    this.buttons = [];
    rect(ctx, 0, 0, 480, 480, pal.bg);
    drawHeader(ctx, game, this.buttons, { title: "SCENARIO OPTIONS", roundLabel: "R0" });

    const name = this.scenario.name ?? this.data.name ?? "Unknown scenario";
    const pack = this.scenario.pack ?? this.data.pack ?? "";

    const scenarioMask = iconFor(this.scenario.slug, this.icons);
    iconSlot(ctx, 16, 50, 40, pal.gold, scenarioMask);
    textLeft(ctx, truncateText(name, 2, 480 - 66 - 14), 66, 54, 2, pal.gold);
    textLeft(ctx, truncateText(`${pack} - tap to change`, 1, 480 - 66 - 14), 66, 76, 1, pal.dim);
    this.buttons.push(new Button(["retitle"], 8, 46, 464, 50));

    textLeft(ctx, "SETS TO GATHER", 16, 100, 1, pal.muted);
    let gy = GATHER_Y0;
    for (const [label, isMore] of this._gatherRows()) {
      if (isMore) {
        textLeft(ctx, label, 48, gy + 5, 2, pal.muted);
      } else {
        // Slot is 26 (not the mask's exact 24) so panel()'s 1px border ring
        // stays visible around the icon, same look as an unmatched
        // placeholder - see the Task 3 report.
        const rowMask = iconFor(slugify(label), this.icons);
        iconSlot(ctx, 16, gy, 26, null, rowMask);
        textLeft(ctx, truncateText(label, 2, 480 - 48 - 14), 48, gy + 5, 2, pal.tan);
      }
      gy += GATHER_ROW_H;
    }

    // Dropdown y is derived from the actual gather-row count (not a fixed
    // offset) so 1-4 rows can never collide with the form below; with the
    // 3-row fixture this reproduces mock_quest.py's y=212 exactly
    // (116 + 3*30 + 6).
    const ddY = gy + 6;
    const S = ScenarioOptionsScreen;
    this._dropdown(ctx, 16, ddY, S.DD_W, "Difficulty", this.difficulty, ["dd", "difficulty"]);
    // Same read-only card reference the Quest Setup view and the progress
    // detail row open - reachable here so you can read the stages before
    // committing to the scenario. Sits on the dropdown's row (its box starts
    // 14px below the label), not under it.
    const cb = new Button(["open_card_modal"], S.CARD_BTN_X, ddY + 14, S.CARD_BTN_W, 34);
    bevel(ctx, cb.x, cb.y, cb.w, cb.h, pal.btn);
    textCenter(ctx, "Quest card", cb.x + cb.w / 2, cb.y + 9, 2, pal.tan);
    this.buttons.push(cb);

    let msgs = this._tipMessages();
    if (msgs.length) {
      // Always the mock's scale (2). The tip used to shrink to scale 1
      // whenever two messages showed at once, which read as a bug - the same
      // panel rendering at two different sizes. There is only ever one
      // message now (see _tipMessages), and the authored copy is kept short
      // enough to wrap to 2 lines at this scale.
      const scale = 2;
      const ty = ddY + 62;
      // A scenario-specific mode card's own printed setup text can run several
      // hundred characters. Clip it above the CTA rather than letting it run
      // through - the full text is on the physical card in front of the player.
      // Mirrors notePanel's own geometry (ui.js): lh = 10*scale+6, and the
      // usable width subtracts the panel padding and the pipe-icon gutter.
      const gutter = icons.PIPE[0] + 14;
      const usable = 448 - 16 - 12 - gutter;
      const lh = 10 * scale + 6;
      const maxLines = Math.max(1, Math.floor((CTA_Y - 10 - ty - 16) / lh));
      let lines = [];
      for (const m of msgs) lines = lines.concat(wrapText(m, scale, usable));
      const shown = lines.length <= maxLines
        ? msgs : [lines.slice(0, maxLines).join(" ").trimEnd() + " ..."];
      notePanel(ctx, 16, ty, 448, shown, scale);
    }

    const begin = new Button(["begin"], 16, CTA_Y, 448, CTA_H);
    bevel(ctx, begin.x, begin.y, begin.w, begin.h, pal.btn_ok, false, 3);
    textCenter(ctx, "Begin Setup", 240, CTA_Y + 18, 3, pal.ok_fg);
    this.buttons.push(begin);
  }

  _dropdown(ctx, x, y, w, label, value, id) {
    textLeft(ctx, label, x, y, 1, pal.muted);
    const yy = y + 14;
    panel(ctx, x, yy, w, 34, pal.well);
    textLeft(ctx, value, x + 10, yy + 9, 2, pal.tan);
    chevronDown(ctx, x + w - 16, yy + 17, pal.dim);
    this.buttons.push(new Button(id, x, yy, w, 34));
  }

  onButton(btn, game) {
    const k = btn.id[0];
    if (k === "nav") return ["goto", btn.id[1]];
    if (k === "retitle") return ["choose_scenario_list", this.scenario.source, this.scenario.cycle];
    if (k === "dd") {
      return ["modal", new OptionListModal(this, "difficulty", "Difficulty", this.difficultyOptions())];
    }
    if (k === "open_card_modal") {
      const stages = this.data?.quest?.stages ?? [];
      if (!stages.length) return null;   // nothing loaded, nothing to show
      return ["modal", new QuestCardModal(game, null, stages, this.scenario)];
    }
    if (k === "begin") return ["begin_setup", this.difficulty];
    return null;
  }
}

export class OptionListModal {
  // Tiny radio-list picker for a Scenario Options dropdown (Difficulty or
  // Mode): reuses the radio glyph from ChooseScenarioScreen. Tapping a row
  // sets the value directly on the host ScenarioOptionsScreen and closes;
  // Done closes without changing the current selection. Mirrors the
  // full-screen modal protocol used throughout screens_other.js/main.js:
  // draw(ctx) / onButton(btn) -> "close"|null.
  static ROWS_Y0 = 110;
  static ROW_H = 64;
  static ROW_STRIDE = 74;
  static DONE_Y = 404;
  static DONE_H = 56;

  constructor(host, attr, title, options) {
    this.host = host;
    this.attr = attr;
    this.title = title;
    this.options = options;
    this.buttons = [];
  }

  draw(ctx) {
    const { ROWS_Y0, ROW_H, ROW_STRIDE, DONE_Y, DONE_H } = OptionListModal;
    this.buttons = [];
    rect(ctx, 0, 0, 480, 480, pal.bg);
    textCenter(ctx, `Choose ${this.title}`, 240, 30, 3, pal.gold);

    const current = this.host[this.attr];
    let y = ROWS_Y0;
    for (const opt of this.options) {
      const on = opt === current;
      if (on) rect(ctx, 24, y, 432, ROW_H, pal.card_hi);
      radioGlyph(ctx, 50, y + ROW_H / 2, on);
      textLeft(ctx, opt, 80, y + ROW_H / 2 - 12, 3, on ? pal.tan : pal.muted);
      rect(ctx, 24, y + ROW_H, 432, 1, pal.border);
      this.buttons.push(new Button(["opt", opt], 24, y, 432, ROW_H));
      y += ROW_STRIDE;
    }

    const done = new Button(["done"], 24, DONE_Y, 432, DONE_H);
    bevel(ctx, done.x, done.y, done.w, done.h, pal.btn_ok, false, 3);
    textCenter(ctx, "Done", 240, DONE_Y + 18, 2, pal.ok_fg);
    this.buttons.push(done);
  }

  onButton(btn) {
    const k = btn.id[0];
    if (k === "opt") { this.host[this.attr] = btn.id[1]; return "close"; }
    if (k === "done") return "close";
    return null;
  }
}

// --- M5 onboarding: first-run intro + HUD conventions legend ----------------
// Mirror of ui/screen_firstrun.py - keep the two in lockstep. Each legend row
// draws the actual primitive it explains, so the legend cannot drift from the UI.
export const FIRSTRUN_PAGES = 3;

export function drawLegendRows(ctx, y) {
  const xIcon = 30, xText = 76;
  icons.drawIcon(ctx, icons.THREAT, xIcon - 10, y - 10, pal.bevel_d);
  icons.drawIcon(ctx, icons.THREAT, xIcon - 11, y - 11, pal.red);
  textLeft(ctx, "your threat - enemies engage at/below it", xText, y - 8, 2, pal.tan);
  y += 34;
  icons.drawIcon(ctx, icons.THREAT, xIcon - 11, y - 11, pal.outline);
  textLeft(ctx, "staging threat - what questing must beat", xText, y - 8, 2, pal.tan);
  y += 34;
  icons.drawIcon(ctx, icons.WILLPOWER, xIcon - 11, y - 11, pal.gold);
  textLeft(ctx, "willpower committed to the quest", xText, y - 8, 2, pal.tan);
  y += 34;
  token(ctx, xIcon, y, 13, 2, 4, pal.value, 0.55, pal.gold, pal.dim);
  textLeft(ctx, "ring = progress; number = points left", xText, y - 8, 2, pal.tan);
  y += 34;
  token(ctx, xIcon, y, 13, 2, 41, pal.value, 0.9, pal.red, pal.dim);
  textLeft(ctx, "red ring = close to elimination", xText, y - 8, 2, pal.tan);
  y += 34;
  rect(ctx, xIcon - 12, y - 10, 4, 20, pal.red);
  rect(ctx, xIcon + 2, y - 10, 4, 20, pal.green);
  textLeft(ctx, "red = happens anyway; green = your window", xText, y - 8, 2, pal.tan);
  return y + 30;
}

export class LegendScreen {
  constructor() { this.buttons = []; }
  draw(ctx, game) {
    this.buttons = [];
    rect(ctx, 0, 0, 480, 480, pal.bg);
    drawHeader(ctx, game, this.buttons, { title: "How to read this HUD", close: true });
    drawLegendRows(ctx, HEADER_H + 34);
  }
  onButton(btn) {
    if (btn.id[0] === "close" || btn.id[0] === "nav") return ["goto", "close"];
    return null;
  }
}

export class FirstRunScreen {
  constructor() { this.page = 0; this.buttons = []; }
  _body(ctx) {
    let y = HEADER_H + 40;
    const para = (title, lines) => {
      textCenter(ctx, title, 240, y, 2, pal.gold);
      y += 40;
      for (const ln of lines) { textCenter(ctx, ln, 240, y, 2, pal.tan); y += 26; }
    };
    if (this.page === 0) {
      para("A companion, not a rules engine",
["This tracks threat, progress and the",
         "turn sequence for you.", "",
         "It never touches your cards - you still",
         "play the game on the table."]);
    } else if (this.page === 1) {
      para("One screen per phase", ["Pick a quest, then follow the round.", "",
         "The big button at the bottom always",
         "moves you forward.", "",
         "Tap the stats up top to edit them."]);
    } else {
      textCenter(ctx, "What the marks mean", 240, y, 2, pal.gold);
      drawLegendRows(ctx, y + 36);
    }
  }
  draw(ctx, game) {
    this.buttons = [];
    rect(ctx, 0, 0, 480, 480, pal.bg);
    drawHeader(ctx, game, this.buttons, { title: "Help", close: true });
    this._body(ctx);
    if (this.page > 0) {
      const b = new Button(["fr_back"], 12, 412, 140, 52);
      bevel(ctx, b.x, b.y, b.w, b.h, pal.btn);
      textCenter(ctx, "Back", b.x + 70, b.y + 16, 2, pal.tan);
      this.buttons.push(b);
    }
    for (let i = 0; i < FIRSTRUN_PAGES; i++) {
      disc(ctx, 240 + (i - 1) * 18, 438, 5, i === this.page ? pal.gold : pal.dim);
    }
    const last = this.page === FIRSTRUN_PAGES - 1;
    const b = new Button([last ? "fr_done" : "fr_next"], 328, 412, 140, 52);
    bevel(ctx, b.x, b.y, b.w, b.h, pal.btn_ok);
    textCenter(ctx, last ? "Done" : "Next", b.x + 70, b.y + 16, 2, pal.ok_fg);
    this.buttons.push(b);
  }
  onButton(btn) {
    const k = btn.id[0];
    if (k === "fr_next") { this.page = Math.min(FIRSTRUN_PAGES - 1, this.page + 1); return "redraw"; }
    if (k === "fr_back") { this.page = Math.max(0, this.page - 1); return "redraw"; }
    // "goto close" pops the nav trail -> back to Settings (a bare ["close"] is
    // the modal idiom; screens must use goto).
    if (k === "fr_done" || k === "close" || k === "nav") { this.page = 0; return ["goto", "close"]; }
    return null;
  }
}
