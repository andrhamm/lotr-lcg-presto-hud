// Port of ui/screen_play.py — the guided round.
import { pal, Button, rect, panel, bevel, textLeft, textCenter, wrapText,
         truncateText, ribbon, notePanel } from "./ui.js";
import { measureText } from "./metrics.js";
import * as icons from "./icons.js";
import { VIEW_ORDER, VIEW_LABELS, SETUP_TIP } from "./gamestate.js";
import { drawHeader, drawNotifPie, HEADER_H, CounterModal, CommitModal,
         QuestingForModal, RemindersModal, LocationPickModal, SideQuestsModal,
         QuestConfigModal } from "./screens.js";

const MARGIN = 8;
const STRIP_Y = HEADER_H + 10;
const CHIP_H = 56;
const PROG_Y = STRIP_Y + CHIP_H + 8;
const CONTENT_Y = PROG_Y + CHIP_H + 8;
const CTA_Y = 410;
const CTA_H = 58;
const GUTTER = MARGIN + 40;

export class ScreenPlay {
  constructor() {
    this.buttons = [];
    this.banner = null;      // [text, kind, view]
    this.notif = null;       // list of [icon, text, color]
    this.notifFrac = 1.0;
    this.notifPie = null;
    this.notifEdge = "amber";
    this.alloc = null;
  }

  _chipW(game) {
    const n = game.players.length;
    return Math.floor((480 - GUTTER - MARGIN - (n - 1) * MARGIN) / n);
  }

  _chips(ctx, game) {
    const chipW = this._chipW(game);
    icons.drawIcon(ctx, icons.THREAT, MARGIN + 4, STRIP_Y + 18, pal.red);
    game.players.forEach((p, i) => {
      const x = GUTTER + i * (chipW + MARGIN);
      panel(ctx, x, STRIP_Y, chipW, CHIP_H);
      textCenter(ctx, `P${i + 1}`, x + chipW / 2, STRIP_Y + 5, 2, pal.tan);
      const val = p.eliminated ? "OUT" : String(p.threat);
      textCenter(ctx, val, x + chipW / 2, STRIP_Y + 26, 3,
                 p.eliminated ? pal.red : pal.threatPen(p.threat));
      if (i === game.first_player) ribbon(ctx, x + chipW - 20, STRIP_Y + 1);
      this.buttons.push(new Button(["thr", i], x, STRIP_Y, chipW, CHIP_H));
    });
  }

  _commitRow(ctx, game, y) {
    const chipW = this._chipW(game);
    icons.drawIcon(ctx, icons.WILLPOWER, MARGIN + 4, y + 18, pal.gold);
    game.players.forEach((p, i) => {
      const x = GUTTER + i * (chipW + MARGIN);
      panel(ctx, x, y, chipW, 52, pal.card_hi);
      textCenter(ctx, String(p.commit), x + chipW / 2, y + 14, 3, pal.green);
      this.buttons.push(new Button(["commit", i], x, y, chipW, 52));
    });
  }

  _progressRow(ctx, game, allowAdd = false) {
    const y = PROG_Y;
    icons.drawIcon(ctx, icons.TRAIL, MARGIN + 4, y + 18, pal.gold);
    const cards = [[`Q${game.quest.stage_n}${game.quest.side}`,
                    `${game.quest.progress}/${game.quest.points}`, pal.gold, ["prog_q"]]];
    if (game.active_location) {
      cards.push(["LOC", `${game.active_location.progress}/${game.active_location.points}`,
                  pal.gold, ["prog_loc"]]);
    }
    game.side_quests.forEach((sq, i) => {
      cards.push([`SQ${i + 1}`, `${sq.progress}/${sq.points}`, pal.gold, ["prog_sq", i]]);
    });
    if (allowAdd) cards.push(["+SQ", "", pal.dim, ["sq_add"]]);
    const n = cards.length;
    const cw = Math.min(this._chipW(game),
                        Math.floor((480 - GUTTER - MARGIN - (n - 1) * MARGIN) / n));
    cards.forEach(([label, val, pen, bid], i) => {
      const x = GUTTER + i * (cw + MARGIN);
      panel(ctx, x, y, cw, CHIP_H);
      if (val) {
        textCenter(ctx, label, x + cw / 2, y + 5, 2, pal.tan);
        textCenter(ctx, val, x + cw / 2, y + 26, 3, pen);
      } else {
        textCenter(ctx, label, x + cw / 2, y + 18, 2, pen);
      }
      if (bid) this.buttons.push(new Button(bid, x, y, cw, CHIP_H));
    });
  }

  _cta(ctx, label, id, fill = pal.btn_ok, fg = pal.gold) {
    const b = new Button(id, MARGIN, CTA_Y, 480 - 2 * MARGIN, CTA_H);
    bevel(ctx, b.x, b.y, b.w, b.h, fill, false, 3);
    textCenter(ctx, label, 240, CTA_Y + 20, 2, fg);
    this.buttons.push(b);
  }

  _totalsRow(ctx, game, y, withSteppers = false, tappable = []) {
    const half = Math.floor((480 - 3 * MARGIN) / 2);
    const defs = [
      ["Questing for", game.willpower, pal.gold, "wp", icons.WILLPOWER_MD, pal.gold, true],
      ["Staging area", game.staging, pal.outline, "stg", icons.THREAT_MD, pal.outline, false],
    ];
    defs.forEach(([label, val, pen, key, icon, ipen, shadow], idx) => {
      const x = MARGIN + idx * (half + MARGIN);
      panel(ctx, x, y, half, 84);
      textCenter(ctx, label, x + half / 2, y + 6, 2, pal.muted);
      const vw = measureText(String(val), 4);
      const gx = Math.floor(x + half / 2 - (vw + 8 + 28) / 2);
      textLeft(ctx, String(val), gx, y + 32, 4, pen, shadow);
      icons.drawIcon(ctx, icon, gx + vw + 8, y + 32, ipen);
      if (withSteppers) {
        const mn = new Button([key + "-"], x + 8, y + 30, 52, 44);
        const pl = new Button([key + "+"], x + half - 60, y + 30, 52, 44);
        for (const [b, s] of [[mn, "-"], [pl, "+"]]) {
          bevel(ctx, b.x, b.y, b.w, b.h, pal.btn);
          textCenter(ctx, s, b.x + 26, b.y + 10, 3, pal.tan);
          this.buttons.push(b);
        }
        if (key === "stg") this.buttons.push(new Button(["enc_rem"], x + 64, y, half - 128, 84));
        if (key === "wp") this.buttons.push(new Button(["wp"], x + 64, y, half - 128, 84));
      } else if (tappable.includes(key)) {
        this.buttons.push(new Button([key], x, y, half, 84));
        if (key === "stg") {
          textCenter(ctx, `reveal up to +${game.stagingRevealEstimate()}`,
                     x + half / 2, y + 68, 1, pal.dim);
        }
      }
    });
  }

  draw(ctx, game) {
    this.buttons = [];
    rect(ctx, 0, 0, 480, 480, pal.bg);
    drawHeader(ctx, game, this.buttons);
    const view = game.view;

    if (view === "setup_game") {
      const th = notePanel(ctx, MARGIN, 56, 480 - 2 * MARGIN, SETUP_TIP);
      const y = 56 + th + 18;
      textLeft(ctx, "Stage 1B quest points", MARGIN + 8, y + 16, 2, pal.tan);
      const mn = new Button(["qp", -1], 300, y, 52, 48);
      const pl = new Button(["qp", 1], 412, y, 52, 48);
      for (const [b, s] of [[mn, "-"], [pl, "+"]]) {
        bevel(ctx, b.x, b.y, b.w, b.h, pal.btn);
        textCenter(ctx, s, b.x + 26, b.y + 12, 3, pal.tan);
        this.buttons.push(b);
      }
      textCenter(ctx, String(game.quest.points), 382, y + 12, 3, pal.gold);
      textLeft(ctx, "so round 1 starts knowing the goal", MARGIN + 8, y + 58, 1, pal.dim);
      this._cta(ctx, "Begin Round 1 >", ["advance"]);
    } else if (view === "resource_planning") {
      this._chips(ctx, game);
      this._progressRow(ctx, game, true);
      notePanel(ctx, MARGIN, CONTENT_Y + 6, 480 - 2 * MARGIN,
                ["Collect resources.", "Draw cards.", "Play allies and attachments."]);
      this._cta(ctx, "Quest >", ["advance"]);
    } else if (view === "quest_commit") {
      this._chips(ctx, game);
      this._progressRow(ctx, game);
      this._commitRow(ctx, game, CONTENT_Y);
      const th = notePanel(ctx, MARGIN, CONTENT_Y + 60, 480 - 2 * MARGIN,
                           "Commit characters to the quest.");
      this.buttons.push(new Button(["commit_tip"], MARGIN, CONTENT_Y + 60,
                                   480 - 2 * MARGIN, th));
      this._totalsRow(ctx, game, CONTENT_Y + 108, false, ["wp", "stg"]);
      this._cta(ctx, "Quest (Staging) >", ["advance"]);
    } else if (view === "quest_staging") {
      this._chips(ctx, game);
      this._progressRow(ctx, game, true);
      notePanel(ctx, MARGIN, CONTENT_Y + 2, 480 - 2 * MARGIN,
                "Reveal 1 encounter card per player.");
      this._totalsRow(ctx, game, CONTENT_Y + 52, true);
      if (game.quest_resolved) {
        this._cta(ctx, "Travel >", ["advance"]);
      } else {
        const diff = game.willpower - game.staging;
        const lbl = diff > 0 ? `Resolve Quest - success, +${diff} progress`
          : diff < 0 ? `Resolve Quest - failure, +${-diff} threat all`
          : "Resolve Quest - unsuccessful (tie)";
        this._cta(ctx, lbl, ["resolve"]);
      }
    } else if (view === "quest_resolution") {
      this._drawResolution(ctx, game);
    } else if (view === "travel") {
      this._chips(ctx, game);
      this._progressRow(ctx, game);
      this._drawTravel(ctx, game);
    } else if (view === "refresh") {
      this._chips(ctx, game);
      this._progressRow(ctx, game);
      notePanel(ctx, MARGIN, CONTENT_Y + 6, 480 - 2 * MARGIN,
                ["Ready all exhausted cards.", "Threat increases (automatic).",
                 "Pass the first player token."]);
      this._cta(ctx, "End round >", ["endround"]);
    } else {
      this._chips(ctx, game);
      const notes = {
        enc_optional: "Each player may engage one enemy in the staging area (optional).",
        enc_checks: "Engagement checks: enemies engage players whose threat >= their cost.",
        combat_shadow: "Deal 1 shadow card to each engaged enemy.",
        combat_enemy: "Enemies attack. Declare defenders, resolve shadow effects, apply damage.",
        combat_player: "Players attack engaged enemies.",
      };
      const flavor = { combat_enemy: [icons.DEFENSE, pal.green],
                       combat_player: [icons.ATTACK, pal.tan] }[view];
      this._progressRow(ctx, game);
      const h = notePanel(ctx, MARGIN, CONTENT_Y + 6, 480 - 2 * MARGIN,
                          notes[view] ?? "", 2, flavor ? 34 : 0);
      if (flavor) {
        icons.drawIcon(ctx, flavor[0], 480 - MARGIN - 34,
                       CONTENT_Y + 6 + Math.floor((h - 20) / 2), flavor[1]);
      }
      const i = VIEW_ORDER.indexOf(view);
      const nxt = VIEW_ORDER[(i + 1) % VIEW_ORDER.length];
      this._cta(ctx, `${VIEW_LABELS[nxt] ?? nxt} >`, ["advance"]);
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
        for (const ln of wrapText(s, 2, usable)) lines.push([ln, c]);
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
        textLeft(ctx, s, tx0, ty, 2, pal[c]);
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
      const btext = truncateText(btextRaw, 1, 480 - 2 * MARGIN);
      textCenter(ctx, btext, 240, CTA_Y - 26, 1, bpen);
    }
  }

  _drawTravel(ctx, game) {
    const loc = game.active_location;
    let y = CONTENT_Y + 4;
    if (!loc) {
      y += notePanel(ctx, MARGIN, y, 480 - 2 * MARGIN,
        "Players may travel to 1 location. It becomes the active location.") + 10;
      const tb = new Button(["travel_new"], MARGIN, y, 480 - 2 * MARGIN, 56);
      bevel(ctx, tb.x, tb.y, tb.w, tb.h, pal.btn);
      textCenter(ctx, "Travel to location", 240, y + 18, 2, pal.tan);
      this.buttons.push(tb);
    } else {
      y += notePanel(ctx, MARGIN, y, 480 - 2 * MARGIN,
        "Travel is only possible while there is no active location (rulebook).") + 10;
      const cb = new Button(["travel_change"], MARGIN, y, 480 - 2 * MARGIN, 48);
      panel(ctx, cb.x, cb.y, cb.w, cb.h);
      textCenter(ctx, "Replace location (card effect)", 240, y + 14, 2, pal.muted);
      this.buttons.push(cb);
    }
    this._cta(ctx, "Encounter (Opt. Engage) >", ["advance"]);
  }

  _drawResolution(ctx, game) {
    if (this.alloc === null) {
      const a = game.autoSplit(game.pending_budget);
      this.alloc = { location: a.location, quest: a.quest,
                     side_quests: game.side_quests.map(() => 0) };
    }
    const alloc = this.alloc;
    const used = alloc.location + alloc.quest + alloc.side_quests.reduce((a, b) => a + b, 0);
    const remaining = game.pending_budget - used;

    textCenter(ctx, `Place ${game.pending_budget} progress  (remaining ${remaining})`,
               240, HEADER_H + 8, 2, pal.gold);
    textCenter(ctx, "Location fills first; overflow -> quest. Adjust freely.",
               240, HEADER_H + 34, 1, pal.muted);

    let y = HEADER_H + 56;
    const rows = [];
    if (game.active_location) {
      rows.push(["location", null, "Active Location",
                 game.active_location.progress, game.active_location.points]);
    }
    rows.push(["quest", null, `Quest ${game.questLabel()}`,
               game.quest.progress, game.quest.points]);
    game.side_quests.forEach((sq, i) => {
      rows.push(["side", i, `Side quest ${i + 1}`, sq.progress, sq.points]);
    });

    for (const [key, idx, label, cur, pts] of rows) {
      const add = key === "side" ? alloc.side_quests[idx] : alloc[key];
      panel(ctx, MARGIN, y, 480 - 2 * MARGIN, 56);
      textLeft(ctx, label, 22, y + 8, 2, pal.tan);
      textLeft(ctx, `${cur} + ${add} / ${pts}`, 22, y + 34, 1, pal.muted);
      const mn = new Button(["am", key, idx], 300, y + 8, 50, 40);
      const pl = new Button(["ap", key, idx], 414, y + 8, 50, 40);
      for (const [b, s] of [[mn, "-"], [pl, "+"]]) {
        bevel(ctx, b.x, b.y, b.w, b.h, pal.btn);
        textCenter(ctx, s, b.x + 25, b.y + 8, 3, pal.tan);
        this.buttons.push(b);
      }
      textCenter(ctx, String(cur + add), 382, y + 14, 3, pal.gold);
      y += 62;
    }

    const ab = new Button(["aauto"], MARGIN, y + 4, 230, 44);
    bevel(ctx, ab.x, ab.y, ab.w, ab.h, pal.btn);
    textCenter(ctx, "Auto loc->quest", ab.x + 115, ab.y + 12, 2, pal.tan);
    this.buttons.push(ab);
    const rb = new Button(["areset"], 250, y + 4, 110, 44);
    bevel(ctx, rb.x, rb.y, rb.w, rb.h, pal.btn);
    textCenter(ctx, "Reset", rb.x + 55, rb.y + 12, 2, pal.tan);
    this.buttons.push(rb);

    if (remaining > 0) {
      const b = new Button(["apply_alloc_disabled"], MARGIN, CTA_Y, 480 - 2 * MARGIN, CTA_H);
      bevel(ctx, b.x, b.y, b.w, b.h, pal.card, false, 3);
      textCenter(ctx, `Place ${remaining} more to continue`, 240, CTA_Y + 20, 2, pal.dim);
    } else {
      this._cta(ctx, "Apply placement - Travel >", ["apply_alloc"]);
    }
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
    if (k === "thr") {
      const i = btn.id[1];
      return ["modal", new CounterModal(`P${i + 1} threat`, game.players[i].threat,
        v => {
          const before = game.players[i].threat;
          game.adjustThreat(i, v - before);
          if (game.players[i].threat !== before) {
            game.logEvent(`P${i + 1} threat ${before} -> ${game.players[i].threat}`);
          }
        }, "threat")];
    }
    if (k === "commit") return ["modal", new CommitModal(game, btn.id[1])];
    if (k === "commit_tip") return ["modal", new CommitModal(game, 0)];
    if (k === "wp") return ["modal", new QuestingForModal(game)];
    if (k === "enc_rem") return ["modal", new RemindersModal(game)];
    if (k === "stg") {
      return ["modal", new CounterModal("Staging area threat", game.staging,
        v => { game.staging = v; }, "threat")];
    }
    if (k === "wp-") { game.willpower = Math.max(0, game.willpower - 1); return true; }
    if (k === "wp+") { game.willpower += 1; return true; }
    if (k === "stg-") { game.staging = Math.max(0, game.staging - 1); return true; }
    if (k === "stg+") { game.staging += 1; return true; }
    if (k === "prog_q") {
      return ["modal", new CounterModal(`Quest ${game.questLabel()} progress`,
        game.quest.progress, v => {
          const b = game.quest.progress;
          if (v !== b) {
            game.quest.progress = v;
            game.logEvent(`Quest ${game.questLabel()} progress ${b} -> ${v} (manual)`);
          }
        })];
    }
    if (k === "prog_loc") {
      return ["modal", new CounterModal("Location progress",
        game.active_location.progress, v => {
          const b = game.active_location.progress;
          if (v !== b) {
            game.active_location.progress = v;
            game.logEvent(`Location progress ${b} -> ${v} (manual)`);
          }
        })];
    }
    if (k === "prog_sq") {
      const i = btn.id[1];
      return ["modal", new CounterModal(`Side quest ${i + 1} progress`,
        game.side_quests[i].progress, v => {
          const b = game.side_quests[i].progress;
          if (v !== b) {
            game.side_quests[i].progress = v;
            game.logEvent(`Side quest ${i + 1} progress ${b} -> ${v} (manual)`);
          }
        })];
    }
    if (k === "sq_add") return ["modal", new SideQuestsModal(game)];
    if (k === "resolve") {
      const res = game.resolveQuest(game.willpower, game.staging);
      if (res.outcome === "success") {
        game.pending_budget = res.budget;
        game.enterView("quest_resolution");
        this.alloc = null;
      } else if (res.outcome === "fail") {
        this.banner = [`Quest failed. +${res.threat} threat to all`, "bad", "quest_staging"];
      } else {
        this.banner = ["Quest unsuccessful - tie, no change", "mid", "quest_staging"];
      }
      return true;
    }
    if (k === "am" || k === "ap") {
      const [, key, idx] = btn.id;
      const delta = k === "ap" ? 1 : -1;
      const a = this.alloc;
      const used = a.location + a.quest + a.side_quests.reduce((x, y) => x + y, 0);
      if (delta > 0 && used >= game.pending_budget) return true;
      if (key === "side") a.side_quests[idx] = Math.max(0, a.side_quests[idx] + delta);
      else a[key] = Math.max(0, a[key] + delta);
      return true;
    }
    if (k === "aauto") {
      const a = game.autoSplit(game.pending_budget);
      this.alloc = { location: a.location, quest: a.quest,
                     side_quests: game.side_quests.map(() => 0) };
      return true;
    }
    if (k === "areset") {
      this.alloc = { location: 0, quest: 0,
                     side_quests: game.side_quests.map(() => 0) };
      return true;
    }
    if (k === "apply_alloc") {
      const completed = game.placeProgress(this.alloc);
      let msg = `Placed ${game.pending_budget} progress`;
      if (completed.length) msg += ` (${completed.join(", ")})`;
      game.logEvent(msg);
      game.pending_budget = 0;
      this.alloc = null;
      game.enterView("travel");
      return true;
    }
    if (k === "travel_new") return ["modal", new LocationPickModal(game, "new")];
    if (k === "travel_change") return ["modal", new LocationPickModal(game, "change")];
    if (k === "endround") { game.endRound(); this.banner = null; return true; }
    if (k === "advance") { game.advanceView(); this.banner = null; return true; }
    return null;
  }
}
