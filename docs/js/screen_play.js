// Port of ui/screen_play.py — the guided round.
import { pal, Button, rect, panel, bevel, textLeft, textCenter, wrapText,
         truncateText, ribbon, notePanel, drawWeather, drawHeart, drawFlag } from "./ui.js";
import { measureText } from "./metrics.js";
import * as icons from "./icons.js";
import { VIEW_ORDER, VIEW_LABELS, SETUP_TIP, HEADINGS } from "./gamestate.js";
import { drawHeader, drawNotifPie, HEADER_H, CounterModal, CommitModal,
         QuestingForModal, RemindersModal, LocationPickModal, SideQuestsModal,
         QuestConfigModal, StageCompleteModal, SailingModal,
         QuestingProgressModal } from "./screens.js";

const MARGIN = 8;
const STRIP_Y = HEADER_H + 10;
const CHIP_H = 56;
const PROG_Y = STRIP_Y + CHIP_H + 8;
const PROG_H = 72;                        // progress row is taller (heading card)
const CONTENT_Y = PROG_Y + PROG_H + 8;
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
    this.toast = null;       // [[icon, text, color]] picked up by the main loop
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
      const tfrac = p.eliminated ? 1 : (p.elimination > 0 ? p.threat / p.elimination : 0);
      this._bottomBar(ctx, x, chipW, STRIP_Y + CHIP_H, tfrac,
                      p.eliminated ? pal.red : pal.threatPen(p.threat));
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

  _progressRow(ctx, game, allowAdd = false, showHeading = false) {
    const y = PROG_Y;
    icons.drawIcon(ctx, icons.TRAIL, MARGIN + 4, y + 24, pal.gold);   // taps -> progress view
    this.buttons.push(new Button(["prog_view"], 0, y, GUTTER, PROG_H));
    const frac = (prog, pts) => (pts > 0 ? prog / pts : 0);
    const cards = [[`Q${game.quest.stage_n}${game.quest.side}`,
                    `${game.quest.progress}/${game.quest.points}`, pal.gold, ["prog_view"],
                    frac(game.quest.progress, game.quest.points)]];
    if (game.active_location) {
      cards.push(["LOC", `${game.active_location.progress}/${game.active_location.points}`,
                  pal.gold, ["prog_view"],
                  frac(game.active_location.progress, game.active_location.points)]);
    }
    game.side_quests.forEach((sq, i) => {
      cards.push([`SQ${i + 1}`, `${sq.progress}/${sq.points}`, pal.gold, ["prog_view"],
                  frac(sq.progress, sq.points)]);
    });
    const heading = showHeading && game.sailing;
    const n = cards.length + (heading ? 1 : 0);
    const cw = Math.min(this._chipW(game),
                        Math.floor((480 - GUTTER - MARGIN - (n - 1) * MARGIN) / n));
    cards.forEach(([label, val, pen, bid, cfrac], i) => {
      const x = GUTTER + i * (cw + MARGIN);
      panel(ctx, x, y, cw, PROG_H);
      if (val) {
        textCenter(ctx, label, x + cw / 2, y + 8, 2, pal.tan);
        textCenter(ctx, val, x + cw / 2, y + 34, 3, pen);
      } else {
        textCenter(ctx, label, x + cw / 2, y + 26, 2, pen);
      }
      // quest card carries the last resolution's heart (whole/broken), like
      // the first-player ribbon but on the main quest
      if (i === 0 && game.quest_outcome) {
        const ok = game.quest_outcome === "success";
        drawHeart(ctx, x + cw - 15, y + 15, 7, !ok, ok ? pal.green : pal.red);
      }
      if (val) this._bottomBar(ctx, x, cw, y + PROG_H, cfrac ?? 0, pal.gold);
      if (bid) this.buttons.push(new Button(bid, x, y, cw, PROG_H));
    });
    if (heading) this._headingProgressCard(ctx, game, GUTTER + cards.length * (cw + MARGIN), y, cw);
  }

  _headingPen(h) { return h === 0 ? pal.gold : h === 3 ? pal.red : pal.amber; }

  // The heading is just another progress card: HEADING label, the current
  // weather glyph next to its facing name, and "off-course" beneath (nothing
  // extra when on-course / sunny). Tap to log a sailing test.
  _headingProgressCard(ctx, game, x, y, cw) {
    const pen = this._headingPen(game.heading);
    panel(ctx, x, y, cw, PROG_H);
    textCenter(ctx, "HEADING", x + cw / 2, y + 8, 2, pal.tan);
    const name = HEADINGS[game.heading][2];
    const nw = measureText(name, 2);
    const gx = x + Math.floor((cw - (24 + 4 + nw)) / 2);
    drawWeather(ctx, game.heading, gx + 12, y + 38, 12);
    textLeft(ctx, name, gx + 28, y + 32, 2, pen);
    if (game.heading !== 0) {
      const s = measureText("off-course", 2) <= cw - 6 ? 2 : 1;   // readable when it fits
      textCenter(ctx, "off-course", x + cw / 2, y + (s === 2 ? 54 : 56), s, pal.muted);
    }
    this.buttons.push(new Button(["sail_modal"], x, y, cw, PROG_H));
  }

  _cta(ctx, label, id, fill = pal.btn_ok, fg = pal.gold) {
    const b = new Button(id, MARGIN, CTA_Y, 480 - 2 * MARGIN, CTA_H);
    bevel(ctx, b.x, b.y, b.w, b.h, fill, false, 3);
    textCenter(ctx, label, 240, CTA_Y + 20, 2, fg);
    this.buttons.push(b);
  }

  // 2px progress bar along a card's bottom edge (threat/elimination,
  // progress/quest-points). Dim track + coloured fill.
  _bottomBar(ctx, x, w, bottomY, frac, color) {
    const by = bottomY - 2;
    rect(ctx, x, by, w, 2, pal.border);
    if (frac > 0) rect(ctx, x, by, Math.max(1, Math.round(w * Math.min(1, frac))), 2, color);
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
                     x + half / 2, y + 64, 2, pal.dim);
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
      const sy = y + 50;
      textLeft(ctx, "Sailing quest", MARGIN + 8, sy + 11, 2, pal.tan);
      icons.drawIcon(ctx, icons.WHEEL, 160, sy + 7,
                     game.sailing ? pal.gold : pal.dim);
      const sb = new Button(["sail_toggle"], 300, sy, 164, 38);
      panel(ctx, sb.x, sb.y, sb.w, sb.h, game.sailing ? pal.gold : pal.btn);
      textCenter(ctx, game.sailing ? "On" : "Off", sb.x + 82, sb.y + 12, 2,
                 game.sailing ? pal.bg : pal.tan, false);
      this.buttons.push(sb);
      this._cta(ctx, "Begin Round 1", ["advance"]);
    } else if (view === "resource_planning") {
      this._chips(ctx, game);
      this._progressRow(ctx, game, true);
      notePanel(ctx, MARGIN, CONTENT_Y + 6, 480 - 2 * MARGIN,
                ["Collect resources.", "Draw cards.", "Play allies and attachments."]);
      this._cta(ctx, `Next Phase: ${VIEW_LABELS[game.sailing ? "quest_sailing" : "quest_commit"]}`, ["advance"]);
    } else if (view === "quest_commit") {
      this._chips(ctx, game);
      this._progressRow(ctx, game, false, true);
      // per-player willpower row is redundant with a single player
      let ty = CONTENT_Y;
      if (game.players.length > 1) { this._commitRow(ctx, game, CONTENT_Y); ty += 60; }
      const th = notePanel(ctx, MARGIN, ty, 480 - 2 * MARGIN, "Commit characters to the quest.");
      this.buttons.push(new Button(["commit_tip"], MARGIN, ty, 480 - 2 * MARGIN, th));
      this._totalsRow(ctx, game, ty + 48, false, ["wp", "stg"]);
      this._cta(ctx, `Next Phase: ${VIEW_LABELS.quest_staging}`, ["advance"]);
    } else if (view === "quest_sailing") {
      this._chips(ctx, game);
      this._progressRow(ctx, game, true, true);
      if (!game.sailing) {
        notePanel(ctx, MARGIN, CONTENT_Y + 6, 480 - 2 * MARGIN,
                  ["No Sailing keyword on this quest.", "Enable it if the stage says Sailing."]);
        const eb = new Button(["sail_toggle"], MARGIN, CONTENT_Y + 96,
                              480 - 2 * MARGIN, 52);
        bevel(ctx, eb.x, eb.y, eb.w, eb.h, pal.btn);
        icons.drawIcon(ctx, icons.WHEEL, 130, CONTENT_Y + 96 + 14, pal.gold);
        textCenter(ctx, "Enable Sailing", 254, CONTENT_Y + 96 + 16, 2, pal.tan);
        this.buttons.push(eb);
        this._cta(ctx, `Next Phase: ${VIEW_LABELS.quest_commit}`, ["advance"]);
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
        textLeft(ctx, fp, tx, ly, 2, pal.muted);
        let sx0 = tx + measureText(fp, 2) + 6;
        ribbon(ctx, sx0, ly - 1, 10, 18);
        sx0 += 10 + 6;
        textLeft(ctx, "exhausts N characters (ships", sx0, ly, 2, pal.muted);
        ly += lh;
        textLeft(ctx, "count), looks at and discards N cards.", tx, ly, 2, pal.muted);
        ly += lh;
        icons.drawIcon(ctx, icons.WHEEL_SM, tx, ly, pal.gold);
        textLeft(ctx, "found = steps on-course.", tx + 22, ly, 2, pal.muted);
        this._cta(ctx, `Next Phase: ${VIEW_LABELS.quest_commit}`, ["advance"]);
      }
    } else if (view === "quest_staging") {
      this._chips(ctx, game);
      this._progressRow(ctx, game, true, true);
      // tip: reveal reminder, then a live preview of the resolution outcome
      const tw = 480 - 2 * MARGIN, gutt = 28 + 14, lh = 26;
      const tx = MARGIN + 12 + gutt, usable = tw - 12 - gutt;
      const lines = wrapText(
        "Reveal 1 encounter card per player and adjust staging area threat accordingly.",
        2, usable);
      const ty0 = CONTENT_Y + 2, th = (lines.length + 1) * lh + 16;
      rect(ctx, MARGIN, ty0, tw, th, pal.card_hi);
      rect(ctx, MARGIN, ty0, 4, th, pal.border_gold);
      icons.drawIcon(ctx, icons.PIPE, MARGIN + 10, ty0 + 8, pal.gold);
      let ly = ty0 + 8;
      for (const ln of lines) { textLeft(ctx, ln, tx, ly, 2, pal.muted); ly += lh; }
      const diff = game.willpower - game.staging;
      if (diff !== 0) {
        // success places shared progress ("You"); a fail raises each player's threat
        const pre = `${diff > 0 ? "You" : "Each player"} will gain ${Math.abs(diff)} `;
        textLeft(ctx, pre, tx, ly, 2, pal.muted);
        const px = tx + measureText(pre, 2);
        const ic = diff > 0 ? icons.TRAIL : icons.THREAT_SM;
        icons.drawIcon(ctx, ic, px, ly - 1, diff > 0 ? pal.gold : pal.red);
        textLeft(ctx, "at resolution.", px + ic[0] + 6, ly, 2, pal.muted);
      } else {
        textLeft(ctx, "No change at resolution (tie).", tx, ly, 2, pal.muted);
      }
      this._totalsRow(ctx, game, ty0 + th + 8, true);
      this._cta(ctx, `Next Phase: ${VIEW_LABELS.quest_resolution}`, ["stage_advance"]);
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
      this._cta(ctx, "End round (raise threat, pass token)", ["endround"]);
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
      const shipNotes = {
        combat_enemy: "Ships: only a ship can defend a ship-enemy. Undefended ship attacks must damage a ship you control.",
        combat_player: "Ships: your ships attack only ship-enemies - but any character may attack a ship-enemy.",
      };
      let noteText = notes[view] ?? "";
      if (game.sailing && shipNotes[view]) noteText = [noteText, shipNotes[view]];
      const reserve = flavor ? 34 : 0;
      const h = notePanel(ctx, MARGIN, CONTENT_Y + 6, 480 - 2 * MARGIN,
                          noteText, 2, reserve);
      if (flavor) {
        icons.drawIcon(ctx, flavor[0], 480 - MARGIN - 34,
                       CONTENT_Y + 6 + Math.floor((h - 20) / 2), flavor[1]);
      }
      const i = VIEW_ORDER.indexOf(view);
      const nxt = VIEW_ORDER[(i + 1) % VIEW_ORDER.length];
      this._cta(ctx, `Next Phase: ${VIEW_LABELS[nxt] ?? nxt}`, ["advance"]);
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
    this._cta(ctx, `Next Phase: ${VIEW_LABELS.enc_optional}`, ["advance"]);
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
      this._chips(ctx, game);
      this._progressRow(ctx, game);
      const fail = game.quest_outcome === "fail";
      const ty0 = CONTENT_Y + 6, gutt = 28 + 14, tx = MARGIN + 12 + gutt, lh = 26;
      const th = 2 * lh + 16;
      rect(ctx, MARGIN, ty0, 480 - 2 * MARGIN, th, pal.card_hi);
      rect(ctx, MARGIN, ty0, 4, th, pal.border_gold);
      icons.drawIcon(ctx, icons.PIPE, MARGIN + 10, ty0 + 8, pal.gold);
      // line 1: outcome + a broken heart marking the failed quest
      const l1 = fail ? "Quest failed. " : "Quest unsuccessful - a tie. ";
      textLeft(ctx, l1, tx, ty0 + 8, 2, pal.muted);
      drawHeart(ctx, tx + measureText(l1, 2) + 8, ty0 + 8 + 8, 7, true, pal.red);
      // line 2
      const y2 = ty0 + 8 + lh;
      if (fail) {
        const a = "Each player's ";
        textLeft(ctx, a, tx, y2, 2, pal.muted);
        const ax = tx + measureText(a, 2);
        icons.drawIcon(ctx, icons.THREAT_SM, ax, y2 - 1, pal.red);
        textLeft(ctx, `rose by ${game.quest_outcome_n}.`, ax + icons.THREAT_SM[0] + 6, y2, 2, pal.muted);
      } else {
        textLeft(ctx, "No progress placed, no threat gained.", tx, y2, 2, pal.muted);
      }
      this._cta(ctx, `Next Phase: ${VIEW_LABELS.travel}`, ["advance"]);
      return;
    }
    if (this.alloc === null) {
      const a = game.autoSplit(game.pending_budget);
      this.alloc = { location: a.location, quest: a.quest,
                     side_quests: game.side_quests.map((_, i) => a.side_quests[i] ?? 0) };
    }
    const alloc = this.alloc;
    // Rules: progress fills the active location first; only the overflow
    // beyond its quest points reaches the quest. The location's share is
    // therefore forced (never hand-editable) - the quest/side steppers split
    // whatever spills over.
    if (game.active_location) {
      const locroom = Math.max(0, game.active_location.points - game.active_location.progress);
      alloc.location = Math.min(game.pending_budget, locroom);
    } else {
      alloc.location = 0;
    }
    const used = alloc.location + alloc.quest + alloc.side_quests.reduce((a, b) => a + b, 0);
    const discard = game.pending_budget - used;

    textCenter(ctx, `Place ${game.pending_budget} progress`, 240, HEADER_H + 6, 3, pal.gold);

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
      textCenter(ctx, "Location fills first, then the quest", 240, HEADER_H + 32, 1, pal.dim);
      hy = HEADER_H + 50;
    }
    textLeft(ctx, "TARGET", 20, hy, 1, pal.dim);
    textCenter(ctx, "WAS", cxWas, hy, 1, pal.dim);
    textCenter(ctx, "PLACE", cxPlace, hy, 1, pal.dim);
    textCenter(ctx, "GOAL", cxGoal, hy, 1, pal.dim);

    let y = hy + 12;
    for (const [key, idx, label, cur, pts] of rows) {
      const add = key === "side" ? alloc.side_quests[idx] : alloc[key];
      const result = cur + add;                                  // was + place
      const done = pts > 0 && result >= pts;
      const locked = key === "location";                         // forced: fills first
      panel(ctx, MARGIN, y, rw, 52, done ? pal.card_hi : pal.card,
            done ? pal.border_gold : pal.border);
      textLeft(ctx, label, 20, y + 16, 2, done ? pal.gold : pal.tan);
      if (done) drawFlag(ctx, 20 + measureText(label, 2) + 8, y + 12, 20, pal.gold);
      textCenter(ctx, String(cur), cxWas, y + 16, 2, pal.dim);   // WAS - read-only base
      if (locked) {
        // no steppers: the location's share is dictated by the rules
        textCenter(ctx, String(add), cxPlace, y + 10, 3, add > 0 ? pal.gold : pal.dim);
        textCenter(ctx, "auto", cxPlace, y + 38, 1, pal.dim);
      } else {
        const mn = new Button(["am", key, idx], mnX, y + 6, btnW, btnH);
        const pl = new Button(["ap", key, idx], plX, y + 6, btnW, btnH);
        for (const [b, s] of [[mn, "-"], [pl, "+"]]) {
          bevel(ctx, b.x, b.y, b.w, b.h, pal.btn);
          textCenter(ctx, s, b.x + btnW / 2, b.y + 8, 3, pal.tan);
          this.buttons.push(b);
        }
        textCenter(ctx, String(add), cxPlace, y + 10, 3, add > 0 ? pal.gold : pal.dim);
      }
      textCenter(ctx, String(pts), cxGoal, y + 16, 2, pal.tan);  // GOAL - points needed
      // running total bar: (was + place) / goal
      this._bottomBar(ctx, MARGIN, rw, y + 52, pts > 0 ? result / pts : 0, pal.gold);
      y += 58;
    }

    if (discard > 0) {
      panel(ctx, MARGIN, y, rw, 44, pal.card);
      textLeft(ctx, "Unplaced (discarded)", 20, y + 14, 2, pal.dim);
      textCenter(ctx, String(discard), cxGoal, y + 8, 3, pal.red);
      y += 50;
    }

    const rb = new Button(["areset"], MARGIN, y + 2, rw, 38);
    bevel(ctx, rb.x, rb.y, rb.w, rb.h, pal.btn);
    textCenter(ctx, "Reset", 240, y + 12, 2, pal.tan);
    this.buttons.push(rb);

    this._cta(ctx, `Next Phase: ${VIEW_LABELS.travel}`, ["apply_alloc"]);
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
        }, "threat", `Elimination at ${game.players[i].elimination}`)];
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
    if (k === "prog_view") return ["modal", new QuestingProgressModal(game)];
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
      const [, key, idx] = btn.id;
      const delta = k === "ap" ? 1 : -1;
      const a = this.alloc;
      const cur = key === "side" ? game.side_quests[idx].progress
        : key === "location" ? game.active_location.progress : game.quest.progress;
      const pts = key === "side" ? game.side_quests[idx].points
        : key === "location" ? game.active_location.points : game.quest.points;
      const room = Math.max(0, pts - cur);                       // can't exceed quest points
      const used = a.location + a.quest + a.side_quests.reduce((x, y) => x + y, 0);
      if (delta > 0 && used >= game.pending_budget) return true;
      const set = v => key === "side" ? (a.side_quests[idx] = v) : (a[key] = v);
      const now = key === "side" ? a.side_quests[idx] : a[key];
      set(Math.max(0, Math.min(room, now + delta)));
      return true;
    }
    if (k === "areset") {
      // clear the editable PLACE cells (quest + side); the active location's
      // share is forced by the rules and re-filled on the next draw
      const a = this.alloc;
      if (a) {
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
