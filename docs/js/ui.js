// Port of ui/theme.py + ui/widgets.py onto canvas. Text uses the device's
// bitmap8 advance metrics so layout is pixel-identical to the Presto.
import { measureText, BITMAP8_W } from "./metrics.js";
import * as icons from "./icons.js";

export const NOWRAP = 10000; // parity with widgets.py (canvas never auto-wraps)

// -- type scale (mirror of ui/theme.py) --------------------------------
// The device font is a bitmap8, so "size" is an integer multiplier and there
// are only three of them. Use the NAMES, not the numbers: a bare `1` at a
// draw site is how prose keeps ending up unreadably small.
//
//   BODY is the default. If a player READS it as a sentence - card text,
//   tips, rules captions, empty states, option names - it is BODY. "It did
//   not fit" is not a reason to drop to LABEL; page it, truncate it with a
//   "more" affordance, or give it less to say.
// See docs/superpowers/specs/2026-07-25-design-system.md.
export const DISPLAY = 3;   // screen + modal titles, the primary CTA
export const BODY = 2;      // DEFAULT: anything read as a sentence or a name
export const LABEL = 1;     // ALL-CAPS section labels + dense metadata ONLY

const rgb = (r, g, b) => `rgb(${r},${g},${b})`;

// Source RGB for the pens something needs to SHADE, plus the one new pen.
// Anything wanting "the same colour, turned down" has to start from the
// numbers; see pal.shaded().
export const RGB = {
  bg: [16, 12, 9], card: [36, 32, 21], well: [24, 20, 12],
  border: [60, 54, 35], gold: [214, 180, 110], red: [247, 101, 62],
  tan: [200, 186, 144], slate: [124, 138, 152],
};
export const DIM_FACTOR = 0.55;   // an eliminated stat pill

export const pal = {
  bg: rgb(...RGB.bg), card: rgb(...RGB.card), card_hi: rgb(48, 44, 29),
  border: rgb(...RGB.border), border_gold: rgb(150, 118, 48),
  gold: rgb(...RGB.gold), tan: rgb(...RGB.tan), muted: rgb(180, 162, 118),
  dim: rgb(162, 146, 100), green: rgb(136, 168, 92), amber: rgb(214, 164, 70),
  red: rgb(...RGB.red), btn: rgb(52, 42, 26), btn_ok: rgb(40, 50, 26),
  ok_fg: rgb(158, 196, 104), btn_no: rgb(56, 26, 18), no_fg: rgb(224, 112, 80),
  tab_active: rgb(30, 24, 15), bevel_l: rgb(96, 86, 54), bevel_d: rgb(7, 5, 3),
  shadow: rgb(34, 30, 24),
  purple: rgb(166, 122, 196), outline: rgb(0, 0, 0), well: rgb(...RGB.well),
  // The one deliberately COOL entry, reserved for labels that NAME a value
  // rather than being one (the stat pills' header segments). Every other
  // ink is the same warm hue at a different lightness, so a label beside a
  // gold stat value could only differ from it by brightness.
  slate: rgb(...RGB.slate),
  value: rgb(214, 180, 110), brown: rgb(104, 70, 34),
  row_stripe: rgb(66, 60, 42),
  // placeholder fill for undrawn scenario/set icons (Scenario Options - real
  // icons land in a later sub-project)
  iconslot: rgb(44, 40, 28),
  // parchment fill for the Quest Setup scroll-style tip (deliberately
  // distinct from the standard note-panel card_hi background)
  scroll: rgb(30, 26, 17),
  threatPen(t) { return t >= 35 ? this.red : t >= 20 ? this.amber : this.green; },
  // A pen's own colour at `f` brightness. Eliminated stat pills shade every
  // colour they use through here, which is what makes them read as the same
  // object turned off rather than a different object in one flat grey.
  shaded(name, f = DIM_FACTOR) {
    const [r, g, b] = RGB[name];
    return rgb(Math.floor(r * f), Math.floor(g * f), Math.floor(b * f));
  },
};

export class Button {
  constructor(id, x, y, w, h, data = null) {
    Object.assign(this, { id, x, y, w, h, data });
  }
  hit(px, py) {
    return this.x <= px && px < this.x + this.w &&
           this.y <= py && py < this.y + this.h;
  }
}

export function rect(ctx, x, y, w, h, c) {
  ctx.fillStyle = c;
  ctx.fillRect(x, y, w, h);
}

export function panel(ctx, x, y, w, h, fill = pal.card, border = pal.border) {
  rect(ctx, x, y, w, h, border);
  rect(ctx, x + 1, y + 1, w - 2, h - 2, fill);
}

export function bevel(ctx, x, y, w, h, fill, pressed = false, t = 2) {
  const [lo, hi] = pressed ? [pal.bevel_l, pal.bevel_d] : [pal.bevel_d, pal.bevel_l];
  rect(ctx, x, y, w, h, fill);
  rect(ctx, x, y, w, t, hi);
  rect(ctx, x, y, t, h, hi);
  rect(ctx, x, y + h - t, w, t, lo);
  rect(ctx, x + w - t, y, t, h, lo);
}

// bitmap8-metric text: per-glyph advance from the device table; a chunky
// monospace face approximates the glyph shapes.
function drawGlyphs(ctx, s, x, y, scale, color) {
  ctx.fillStyle = color;
  ctx.font = `bold ${8 * scale}px "Courier New", monospace`;
  ctx.textBaseline = "top";
  let cx = x;
  for (const ch of String(s)) {
    ctx.fillText(ch, cx, y, (BITMAP8_W[ch] ?? 4) * scale + scale);
    cx += ((BITMAP8_W[ch] ?? 4) + 1) * scale;
  }
}

export function textLeft(ctx, s, x, y, scale, color, shadow = true) {
  if (shadow) {
    const off = scale === 1 ? 1 : 2;
    drawGlyphs(ctx, s, x + off, y + off, scale, pal.shadow);
  }
  drawGlyphs(ctx, s, x, y, scale, color);
}

export function textCenter(ctx, s, cx, y, scale, color, shadow = true) {
  textLeft(ctx, s, Math.floor(cx - measureText(s, scale) / 2), y, scale, color, shadow);
}

// Solid triangular arrows for the bottom nav bar. The device draws these with
// d.triangle - the same primitive draw_notif_pie already uses - so no new icon
// mask is needed and the two twins stay pixel-faithful. size is the full
// width and height.
function arrowTri(ctx, cx, cy, size, color, left) {
  const h = Math.floor(size / 2);
  const tip = left ? cx - h : cx + h;
  const base = left ? cx + h : cx - h;
  ctx.beginPath();
  ctx.moveTo(tip, cy);
  ctx.lineTo(base, cy - h);
  ctx.lineTo(base, cy + h);
  ctx.closePath();
  ctx.fillStyle = color;
  ctx.fill();
}

export function arrowLeft(ctx, cx, cy, size, color, shadow = true) {
  if (shadow) arrowTri(ctx, cx + 2, cy + 2, size, pal.shadow, true);
  arrowTri(ctx, cx, cy, size, color, true);
}

export function arrowRight(ctx, cx, cy, size, color, shadow = true) {
  if (shadow) arrowTri(ctx, cx + 2, cy + 2, size, pal.shadow, false);
  arrowTri(ctx, cx, cy, size, color, false);
}

// First-player ribbon running in from the LEFT SCREEN EDGE, with a V-notch
// bitten out of its right end - the horizontal banner reading of the same
// marker `ribbon` hangs vertically. The label sits INSIDE it.
export function ribbonH(ctx, y, w, h, notch = 10, fill = pal.gold) {
  rect(ctx, 0, y, w, h, fill);
  ctx.beginPath();
  ctx.moveTo(w, y);
  ctx.lineTo(w, y + h);
  ctx.lineTo(w - notch, y + Math.floor(h / 2));
  ctx.closePath();
  ctx.fillStyle = pal.bg;
  ctx.fill();
}

export function button(ctx, buttons, btn, label, scale = 2, fill = pal.btn, fg = pal.tan) {
  bevel(ctx, btn.x, btn.y, btn.w, btn.h, fill);
  textCenter(ctx, label, btn.x + btn.w / 2, Math.floor(btn.y + (btn.h - 8 * scale) / 2), scale, fg);
}

export function stepper(ctx, buttons, idMinus, idPlus, x, y, valueStr, w = 200, h = 56) {
  const bw = h;
  const minus = new Button(idMinus, x, y, bw, h);
  const plus = new Button(idPlus, x + w - bw, y, bw, h);
  button(ctx, buttons, minus, "-", 3);
  button(ctx, buttons, plus, "+", 3);
  textCenter(ctx, valueStr, x + w / 2, Math.floor(y + (h - 24) / 2), 3, pal.gold);
  buttons.push(minus, plus);
}

export function wrapText(s, scale, maxW) {
  if (measureText(s, scale) <= maxW) return [String(s)];
  const lines = [];
  let cur = "";
  for (let word of String(s).split(" ")) {
    const cand = cur ? cur + " " + word : word;
    if (measureText(cand, scale) <= maxW) { cur = cand; continue; }
    if (cur) { lines.push(cur); cur = ""; }
    while (measureText(word, scale) > maxW) {
      let i = word.length;
      while (i > 1 && measureText(word.slice(0, i), scale) > maxW) i--;
      lines.push(word.slice(0, i));
      word = word.slice(i);
    }
    cur = word;
  }
  if (cur || !lines.length) lines.push(cur);
  return lines;
}

// A card's front face, by POSITION - never by side letter.
//
// Quest stage cards are not all ("A","B"). Measured over the 514 stage cards in
// docs/data: 16 are ("C","D"), 5 are ("E","F"), 1 is ("G","H") and 4 are
// ("A","A"), with 6 more running ("A","C") through ("A","H"). Looking the front
// up as `side === "A"` therefore returned {} for 22 cards outright, so the
// stage-advance panel drew an empty title AND claimed the stage had no setup
// instructions - on cards that print plenty. faces[0] is the front on every
// card in the catalog. Found in the 2026-07-30 playtest of The Oath.
export function frontFace(card) {
  const faces = card?.faces ?? [];
  return faces.length ? faces[0] : {};
}

// A card's back face, by position. Same reason as frontFace: the branch preview
// looked its alternatives up as `side === "B"` and drew "?" for every card
// whose faces are lettered anything else.
export function backFace(card) {
  const faces = card?.faces ?? [];
  return faces.length > 1 ? faces[1] : {};
}

export const MORE_MARKER = " [...] more";

// Trim lines to maxLines, marking the cut with "[...] more" so a truncated
// block never looks like the whole thing.
//
// The marker has to be made room for, not appended and truncated - appending
// then truncating cuts the marker itself down to "[...." and the affordance
// silently disappears. Was a private method on QuestCardModal until the
// stage-advance panel needed the same rule; one implementation, not two.
export function fitLines(lines, maxLines, usable, more, marker = MORE_MARKER) {
  if (lines.length <= maxLines && !more) return [lines, false];
  const keep = lines.slice(0, maxLines);
  if (!keep.length) keep.push("");
  const mw = measureText(marker, BODY);
  let last = keep[keep.length - 1];
  while (last && measureText(last, BODY) + mw > usable) {
    last = last.includes(" ") ? last.slice(0, last.lastIndexOf(" ")) : last.slice(0, -1);
  }
  keep[keep.length - 1] = last + marker;
  return [keep, true];
}

export function truncateText(s, scale, maxW) {
  if (measureText(s, scale) <= maxW) return String(s);
  s = String(s);
  while (s && measureText(s + "..", scale) > maxW) s = s.slice(0, -1);
  return s + "..";
}

export function ribbon(ctx, x, y, w = 12, h = 22) {
  rect(ctx, x, y, w, h, pal.gold);
  ctx.fillStyle = pal.card;
  ctx.beginPath();
  ctx.moveTo(x, y + h);
  ctx.lineTo(x + w, y + h);
  ctx.lineTo(x + w / 2, y + h - 7);
  ctx.closePath();
  ctx.fill();
}

// Guidance-band metrics, shared by notePanel and phaseBlock.
//
// These were two sets of numbers for one visual element: phaseBlock padded 6
// and stepped 24, notePanel padded 8 and stepped 26, and two hand-rolled
// copies of notePanel in screen_play inlined its 8/26 again. The same band on
// two adjacent views had different leading.
export const BAND_PAD = 6;
// Line pitch inside a guidance band. 24px at BODY, which is what every phase
// view already used.
export function bandLineH(scale = BODY) { return 10 * scale + 4; }

// `accent` overrides the left bar's colour, because the BAR is the vocabulary
// - red happens anyway, green is your window, gold is a hint - and it belongs
// to the meaning of the content, not to the widget that draws it.
// `pen` overrides the ink. The default `muted` suits a hint; guidance copy is
// body text and reads `tan`, the same as phaseBlock's.
export function notePanel(ctx, x, y, w, text, scale = 2, reserveRight = 0, icon,
                          accent, pen) {
  const mask = icon === undefined ? icons.PIPE : icon;
  const isz = mask ? mask[0] : 0;
  const gutter = mask !== false && mask ? isz + 14 : 0;
  const paras = Array.isArray(text) ? text : [text];
  const usable = w - 16 - 12 - gutter - reserveRight;
  const lines = [];
  for (const p of paras) lines.push(...wrapText(p, scale, usable));
  const lh = bandLineH(scale);
  const h = Math.max(lines.length * lh + 2 * BAND_PAD, gutter ? isz + 14 : 0);
  rect(ctx, x, y, w, h, pal.card_hi);
  rect(ctx, x, y, 4, h, accent ?? pal.border_gold);
  if (gutter) icons.drawIcon(ctx, mask, x + 10, y + BAND_PAD, pal.gold);  // top-left, not centered
  let ty = y + BAND_PAD;
  for (const s of lines) {
    // x + 14, matching phaseBlock. These sat 2px apart for no reason.
    textLeft(ctx, s, x + 14 + gutter, ty, scale, pen ?? pal.muted);
    ty += lh;
  }
  return h;
}

// Phase-guidance panel - the semantic sibling of notePanel(). One box; each
// section is a run of BODY lines with a coloured bar down its left edge.
// The bar is the whole vocabulary: red = happens whether or not you act,
// green = your window to act. The FRAMEWORK / YOUR WINDOW label rows were
// dropped - the colour already says it, and they cost ~20px per screen.
// Settings -> Help teaches the pairing. Returns the panel height.
export function phaseBlock(ctx, x, y, w, sections, reserveRight = 0) {
  const usable = w - 14 - 12 - reserveRight;
  const laid = sections.map(({ kind, text }) => {
    const body = Array.isArray(text) ? text.join(" ") : text;
    const lines = wrapText(body, BODY, usable);
    return { kind, lines, h: lines.length * bandLineH() };
  });
  const h = 2 * BAND_PAD + laid.reduce((s, sec) => s + sec.h, 0)
          + BAND_PAD * (laid.length - 1);
  rect(ctx, x, y, w, h, pal.card_hi);
  // The bars TILE the left edge: together they cover the box's full height,
  // and the seam between them is where framework ends and window begins. They
  // used to span only their own text run, so they floated with 6px of
  // background above and below - a different element from notePanel's
  // full-height bar, on screens a player sees one after the other.
  let ty = y + BAND_PAD;
  laid.forEach((sec, i) => {
    const barTop = i === 0 ? y : ty - Math.floor(BAND_PAD / 2);
    const barBot = i === laid.length - 1
      ? y + h : ty + sec.h + BAND_PAD - Math.floor(BAND_PAD / 2);
    // The accent bar alone says which kind this is - no label row. Red =
    // happens whether or not you act; green = your window to act. That
    // pairing is taught in Settings -> Help, and dropping the words buys back
    // ~20px on every phase screen, which is the space that used to get taken
    // out of the type.
    rect(ctx, x, barTop, 4, barBot - barTop,
         sec.kind === "framework" ? pal.red : pal.green);
    let ly = ty;
    for (const s of sec.lines) { textLeft(ctx, s, x + 14, ly, BODY, pal.tan); ly += bandLineH(); }
    ty += sec.h + BAND_PAD;
  });
  return h;
}

// Live head-to-head bar: willpower (gold, left) vs staging threat (dark
// pal.outline, right - never red, per design/stat-system.md). The
// "willpower vs staging, live" stat from design/design-review.md's
// Quest-Staging row. Reuses the existing outcome-sentence wording
// verbatim. Fixed height: 64.
// Two-segment capsule: [threat icon + value | points + label].
//
// The horizontal sibling of token(), the main screen's circular stat widget -
// same idea (a value on its own ground) laid out for a list row.
//
// The LEFT segment carries a light fill so the threat can be BLACK, which
// design/stat-system.md requires (staging threat is never red; red is the
// player's own track). That is the only reason the fill exists: the screen
// ground is (16,12,9) and black on it is invisible. A bare 1px "shadow" did
// nothing for a 16px glyph, and a plain light box behind the icon read as an
// artefact rather than a widget - hence a real two-part pill.
//
// The RIGHT segment stays on the card ground with the points in gold, so the two
// numbers never read as the same kind of thing: one is threat the location adds
// to staging, the other is what it takes to explore.
//
// NOTE: JS icon masks are [size, rows], so the width is mask[0]. `.length` is 2
// and using it silently collapsed an earlier version of this widget.
export function statPill(ctx, x, y, threat, points,
                          { h = 24, label = "QP", measure = false } = {}) {
  const iw = icons.THREAT_SM[0];
  const ts = String(threat ?? 0);
  const ps = String(points ?? 0);
  const wa = 6 + iw + 4 + measureText(ts, BODY) + 6;
  const wb = 6 + measureText(ps, BODY) + 4 + measureText(label, LABEL) + 6;
  const w = wa + wb;
  // Callers that right-align the pill need its width BEFORE they can place it.
  // Measuring by drawing off-screen puts rects outside the panel and stacks
  // every row's numbers at one point.
  if (measure) return w;
  rect(ctx, x, y, w, h, pal.card_hi);
  rect(ctx, x, y, wa, h, pal.dim);
  // chamfer: bite one pixel out of each corner so it reads as a capsule
  for (const cx of [x, x + w - 1]) {
    rect(ctx, cx, y, 1, 1, pal.bg);
    rect(ctx, cx, y + h - 1, 1, 1, pal.bg);
  }
  rect(ctx, x + wa, y + 2, 1, h - 4, pal.bg);
  icons.drawIcon(ctx, icons.THREAT_SM, x + 6, y + Math.floor((h - iw) / 2), pal.outline);
  textLeft(ctx, ts, x + 6 + iw + 4, y + Math.floor((h - 16) / 2) + 2, BODY,
           pal.outline, false);
  const px = x + wa + 6;
  textLeft(ctx, ps, px, y + Math.floor((h - 16) / 2) + 2, BODY, pal.gold);
  // LABEL is the smaller tier, so it needs MORE top offset than the BODY number
  // to share a baseline with it, not less.
  textLeft(ctx, label, px + measureText(ps, BODY) + 4,
           y + Math.floor((h - 16) / 2) + 8, LABEL, pal.muted);
  return w;
}

export function willpowerStagingMeter(ctx, x, y, w, willpower, staging) {
  icons.drawIcon(ctx, icons.WILLPOWER, x, y, pal.gold);
  icons.drawIcon(ctx, icons.THREAT, x + w - icons.THREAT[0], y, pal.outline);
  const bx = x + 26, bw = w - 52, barY = y + 5, barH = 10;
  rect(ctx, bx, barY, bw, barH, pal.well);
  const total = willpower + staging;
  const leftW = total > 0 ? Math.round(bw * willpower / total) : Math.round(bw / 2);
  if (leftW > 0) rect(ctx, bx, barY, leftW, barH, pal.gold);
  if (bw - leftW > 0) rect(ctx, bx + leftW, barY, bw - leftW, barH, pal.outline);
  rect(ctx, x + Math.round(w / 2) - 1, barY - 3, 2, barH + 6, pal.dim);
  const ly = barY + barH + 14;
  const diff = willpower - staging;
  if (diff !== 0) {
    const pre = `${diff > 0 ? "You" : "Each player"} will gain ${Math.abs(diff)} `;
    const preW = measureText(pre, 2);
    const ic = diff > 0 ? icons.TRAIL : icons.THREAT_SM;
    const tail = "at resolution.";
    const totalW = preW + ic[0] + 6 + measureText(tail, 2);
    const lx = x + Math.round((w - totalW) / 2);
    textLeft(ctx, pre, lx, ly, 2, pal.muted);
    icons.drawIcon(ctx, ic, lx + preW, ly - 1, diff > 0 ? pal.gold : pal.red);
    textLeft(ctx, tail, lx + preW + ic[0] + 6, ly, 2, pal.muted);
  } else {
    textCenter(ctx, "Tied - no change at resolution.", x + w / 2, ly, 2, pal.dim);
  }
  return 64;
}

// Small heart glyph (quest-outcome marker). `broken` splits it with a
// jagged notch. Canvas primitives, so it ports to PicoGraphics.
export function drawHeart(ctx, cx, cy, r, broken, color) {
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.moveTo(cx, cy + r);
  ctx.bezierCurveTo(cx - r * 1.5, cy - r * 0.4, cx - r * 0.6, cy - r * 1.2, cx, cy - r * 0.35);
  ctx.bezierCurveTo(cx + r * 0.6, cy - r * 1.2, cx + r * 1.5, cy - r * 0.4, cx, cy + r);
  ctx.closePath();
  ctx.fill();
  if (broken) {
    ctx.strokeStyle = pal.bg;
    ctx.lineWidth = Math.max(1.5, r * 0.28);
    ctx.beginPath();
    ctx.moveTo(cx, cy - r * 0.5);
    ctx.lineTo(cx - r * 0.32, cy - r * 0.05);
    ctx.lineTo(cx + r * 0.24, cy + r * 0.28);
    ctx.lineTo(cx - r * 0.1, cy + r * 0.72);
    ctx.stroke();
  }
}

// Small pennant flag (a target reached its max). Canvas primitives.
export function drawFlag(ctx, x, y, h, color) {
  ctx.fillStyle = color;
  ctx.fillRect(x, y, Math.max(2, h * 0.14), h);            // pole
  ctx.beginPath();                                          // pennant
  ctx.moveTo(x + h * 0.14, y);
  ctx.lineTo(x + h * 0.95, y + h * 0.18);
  ctx.lineTo(x + h * 0.14, y + h * 0.4);
  ctx.closePath();
  ctx.fill();
}

// Circle/arc drawing primitives — the device has no circle/arc primitive, so
// discs and rings are emitted as per-scanline fillRect runs (angle 0deg=top,
// clockwise), the same pipeline every rect/tri call here already uses. This
// is what makes token()/ring() port device-faithfully to PicoGraphics.
export function disc(ctx, cx, cy, rad, pen) {
  ctx.fillStyle = pen;
  for (let py = Math.floor(cy - rad); py <= Math.ceil(cy + rad); py++) {
    const h2 = rad * rad - (py - cy) ** 2;
    if (h2 < 0) continue;
    const hx = Math.floor(Math.sqrt(h2));
    ctx.fillRect(Math.floor(cx - hx), py, 2 * hx + 1, 1);
  }
}

export function arcRuns(ctx, cx, cy, R, r, a0, a1, pen) {
  // Ring/arc band between radii r..R and angles a0..a1 (0deg=top, cw).
  ctx.fillStyle = pen;
  for (let py = Math.floor(cy - R); py <= Math.ceil(cy + R); py++) {
    let run = false, x0 = 0;
    for (let px = Math.floor(cx - R); px <= Math.ceil(cx + R) + 1; px++) {
      const dx = px - cx, dy = py - cy;
      const dd = Math.hypot(dx, dy);
      let on = r <= dd && dd <= R;
      if (on && a1 !== null) {
        const ang = ((Math.atan2(dx, -dy) * 180 / Math.PI) % 360 + 360) % 360;
        on = a0 <= ang && ang <= a1;
      }
      if (on && !run) { run = true; x0 = px; }
      else if (!on && run) { ctx.fillRect(x0, py, px - x0, 1); run = false; }
    }
  }
}

export function ring(ctx, cx, cy, R, w, frac, fill, track) {
  // Thin ring of width w at radius R: full track pen + a frac-of-360 fill
  // arc clockwise from the top (0deg).
  arcRuns(ctx, cx, cy, R, R - w, 0, 360, track);
  if (frac > 0) arcRuns(ctx, cx, cy, R, R - w, 0, frac * 360, fill);
}

export function token(ctx, cx, cy, R, w, value, vpen, frac, fill, track, vscale = 2) {
  // Circular stat widget: inset well disc + progress ring + centred value.
  disc(ctx, cx, cy, R, pal.well);
  ring(ctx, cx, cy, R, w, frac, fill, track);
  if (value !== null && value !== undefined)
    textCenter(ctx, String(value), cx, Math.floor(cy - 4 * vscale), vscale, vpen);
}

export function wxSmall(ctx, idx, cx, cy, r, pen = null) {
  // Tiny weather glyph from rect/tri/disc (the 24px icon masks are too big
  // for the small heading tokens). idx 0 sun / 1 cloud / 2 rain / 3 storm.
  // `pen` forces one colour (e.g. dim for an inactive radio); null = natural.
  if (idx === 0) {
    disc(ctx, cx, cy, r, pen !== null ? pen : pal.amber);
    disc(ctx, cx - 1, cy - 1, Math.max(1, Math.floor(r / 2)), pen !== null ? pen : pal.gold);
    ctx.fillStyle = pen !== null ? pen : pal.amber;
    for (const [dx, dy] of [[0, -r - 3], [0, r + 1], [-r - 3, 0], [r + 1, 0]]) {
      ctx.fillRect(cx + dx, cy + dy, 2, 2);
    }
    return;
  }
  const cloud = pen !== null ? pen : pal.muted;
  disc(ctx, cx - 3, cy, r - 1, cloud);
  disc(ctx, cx + 3, cy - 1, r - 2, cloud);
  disc(ctx, cx, cy - 2, r - 1, cloud);
  ctx.fillStyle = cloud;
  ctx.fillRect(cx - 6, cy, 12, r - 1);
  if (idx === 2) {
    ctx.fillStyle = pen !== null ? pen : pal.dim;
    for (const k of [-3, 1, 5]) {
      ctx.fillRect(cx + k, cy + r - 1, 1, 3);
    }
  } else if (idx === 3) {
    ctx.fillStyle = pen !== null ? pen : pal.gold;
    ctx.beginPath();
    ctx.moveTo(cx, cy + r - 2);
    ctx.lineTo(cx - 3, cy + r + 3);
    ctx.lineTo(cx + 2, cy + r);
    ctx.closePath();
    ctx.fill();
  }
}

// Detailed, coloured weather glyph for the heading facings (canvas
// primitives, so it ports to PicoGraphics' circle/line/poly). idx: 0 sun,
// 1 cloud, 2 rain, 3 storm. Drawn centred on (cx, cy) at radius r.
export function drawWeather(ctx, idx, cx, cy, r) {
  const puff = (fill) => {
    ctx.fillStyle = fill;
    ctx.beginPath();
    ctx.arc(cx - r * 0.5, cy + r * 0.15, r * 0.42, 0, Math.PI * 2);
    ctx.arc(cx - r * 0.05, cy - r * 0.28, r * 0.5, 0, Math.PI * 2);
    ctx.arc(cx + r * 0.55, cy + r * 0.05, r * 0.42, 0, Math.PI * 2);
    ctx.rect(cx - r * 0.92, cy + r * 0.05, r * 1.55, r * 0.46);
    ctx.fill();
  };
  ctx.lineCap = "round";
  if (idx === 0) {                              // sun
    ctx.strokeStyle = "#e2952a";
    ctx.lineWidth = Math.max(2, r * 0.14);
    for (let k = 0; k < 8; k++) {
      const a = k * Math.PI / 4;
      ctx.beginPath();
      ctx.moveTo(cx + Math.cos(a) * r * 0.72, cy + Math.sin(a) * r * 0.72);
      ctx.lineTo(cx + Math.cos(a) * r * 1.05, cy + Math.sin(a) * r * 1.05);
      ctx.stroke();
    }
    ctx.fillStyle = "#f2c247";
    ctx.beginPath(); ctx.arc(cx, cy, r * 0.62, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = "#ffe293";
    ctx.beginPath(); ctx.arc(cx - r * 0.18, cy - r * 0.18, r * 0.26, 0, Math.PI * 2); ctx.fill();
  } else if (idx === 1) {                        // cloud
    puff("#b9bcc6");
    ctx.fillStyle = "#e2e5ed";
    ctx.beginPath(); ctx.arc(cx - r * 0.05, cy - r * 0.3, r * 0.34, 0, Math.PI * 2); ctx.fill();
  } else if (idx === 2) {                        // rain
    puff("#a7abb6");
    ctx.strokeStyle = "#5fa8e6";
    ctx.lineWidth = Math.max(2, r * 0.13);
    for (let k = -1; k <= 1; k++) {
      const sx = cx + k * r * 0.42 + r * 0.1;
      ctx.beginPath(); ctx.moveTo(sx, cy + r * 0.55); ctx.lineTo(sx - r * 0.16, cy + r * 0.98); ctx.stroke();
    }
  } else {                                       // storm
    puff("#8f939e");
    ctx.fillStyle = "#f7d21c";
    ctx.beginPath();
    ctx.moveTo(cx + r * 0.12, cy + r * 0.3);
    ctx.lineTo(cx - r * 0.28, cy + r * 0.74);
    ctx.lineTo(cx - r * 0.02, cy + r * 0.74);
    ctx.lineTo(cx - r * 0.22, cy + r * 1.08);
    ctx.lineTo(cx + r * 0.32, cy + r * 0.56);
    ctx.lineTo(cx + r * 0.05, cy + r * 0.56);
    ctx.closePath(); ctx.fill();
  }
}


// --------------------------------------------------------------------------
// Stat pills - mirror of ui/widgets.py
// --------------------------------------------------------------------------
//
// Segment 0 is the pill's HEADER ("P", a player number, "Q"/"L"/"S1"): its own
// darker ground, a slate label, and a notched right edge, so it reads as a
// label FOR the segments after it rather than a peer of them. Segments are
// FIXED width so the wrap is predictable instead of shifting as numbers change.
//
// Two shapes, one geometry, inverted: a plain header pushes its notch OUT to a
// point; the FIRST PLAYER's header takes the notch IN - the same V bitten out
// of the right end that ribbonH uses - and fills gold with its number knocked
// out. Subtractive and rare, against additive and universal.
export const PILL_H = 28;
export const PILL_CAP = 3;
export const PILL_NOTCH = 6;
export const PILL_GAP = 6;
export const PILL_ROW_GAP = 5;
export const PILL_HEAD_W = 28;   // widest header is "S2" at 18px
export const PILL_VAL_W = 30;    // widest value slot is the 24px weather glyph

function pillShape(ctx, x, y, w, h, pen) {
  const c = PILL_CAP;
  rect(ctx, x + c, y, w - 2 * c, h, pen);
  rect(ctx, x, y + c, c, h - 2 * c, pen);
  rect(ctx, x + w - c, y + c, c, h - 2 * c, pen);
  rect(ctx, x + 1, y + 1, c - 1, c - 1, pen);
  rect(ctx, x + w - c, y + 1, c - 1, c - 1, pen);
  rect(ctx, x + 1, y + h - c, c - 1, c - 1, pen);
  rect(ctx, x + w - c, y + h - c, c - 1, c - 1, pen);
}

// A diagonal strike, stepped out of 1px rects - the device has no line
// primitive, and a triangle this thin renders as a wedge.
function pillSlash(ctx, x, y, w, h, pen, t = 3) {
  for (let i = 0; i < Math.max(1, w); i++) {
    const py = y + h - 1 - Math.floor(i * (h - 1) / Math.max(1, w - 1));
    rect(ctx, x + i, Math.max(y, py - Math.floor(t / 2)), 1, t, pen);
  }
}

export function pillWidth(segs) {
  return PILL_HEAD_W + PILL_NOTCH + (segs.length - 1) * PILL_VAL_W
       + (segs.length - 2);
}

function pillSeg(ctx, seg, cx, sw, y, pen, icons) {
  if (seg[0] === "icon") {
    const mask = seg[1];
    icons.drawIcon(ctx, mask, cx + Math.floor((sw - mask[0]) / 2),
                   y + Math.floor((PILL_H - mask[0]) / 2), pen);
  } else {
    const tw = measureText(seg[1], BODY);
    textLeft(ctx, seg[1], cx + Math.floor((sw - tw) / 2),
             y + Math.floor((PILL_H - 8 * BODY) / 2), BODY, pen, false);
  }
}

export function pill(ctx, x, y, segs, border, ribbon, dead, icons) {
  const ink = name => (dead ? pal.shaded(name) : pal[name]);
  const w = pillWidth(segs);
  // The border is never shaded - it is the pill's own outline - and a dead
  // pill drops the red elimination warning back to the standard border: that
  // warning is about a threat ABOUT to end the player, and once they are out
  // the slash is the statement.
  const edge = dead ? ink("border") : (border ?? pal.border);
  pillShape(ctx, x, y, w, PILL_H, edge);
  pillShape(ctx, x + 1, y + 1, w - 2, PILL_H - 2, ink("card"));

  const hw = PILL_HEAD_W;
  const headBg = ribbon ? ink("gold") : ink("well");
  if (ribbon) {
    // the ribbon takes the bite
    rect(ctx, x + 1, y + 1, hw + PILL_NOTCH - 1, PILL_H - 2, headBg);
    ctx.fillStyle = ink("card");
    ctx.beginPath();
    ctx.moveTo(x + hw + PILL_NOTCH, y + 1);
    ctx.lineTo(x + hw + PILL_NOTCH, y + PILL_H - 1);
    ctx.lineTo(x + hw, y + PILL_H / 2);
    ctx.closePath();
    ctx.fill();
  } else {
    // a plain header inverts it, to a point
    rect(ctx, x + 1, y + 1, hw - 1, PILL_H - 2, headBg);
    ctx.fillStyle = headBg;
    ctx.beginPath();
    ctx.moveTo(x + hw, y + 1);
    ctx.lineTo(x + hw, y + PILL_H - 1);
    ctx.lineTo(x + hw + PILL_NOTCH, y + PILL_H / 2);
    ctx.closePath();
    ctx.fill();
  }

  pillSeg(ctx, segs[0], x + 1, hw, y, ink(ribbon ? "bg" : "slate"), icons);
  let cx = x + hw + PILL_NOTCH;
  segs.slice(1).forEach((seg, i) => {
    if (i > 0) { rect(ctx, cx, y + 1, 1, PILL_H - 2, ink("border")); cx += 1; }
    pillSeg(ctx, seg, cx, PILL_VAL_W, y, ink(seg[2]), icons);
    cx += PILL_VAL_W;
  });

  // the one thing NOT shaded - it is the mark that says why
  if (dead) pillSlash(ctx, x + 5, y + 6, w - 10, PILL_H - 12, pal.red);
  return w;
}


// -- progress rows ---------------------------------------------------------
// Mirrors ui/widgets.py's row widgets. These lived as private methods on the
// Python QuestingProgressModal, where this twin could not reach them - which
// is exactly how the two drew different rows. Anything a row needs is here, in
// both twins, or it is not a row widget.

// PlayersDetailModal's geometry, deliberately: a 40px disc inside a 52px tap
// target is the size the rest of the app already uses for a value the player
// nudges repeatedly.
export const STEP_R = 20;      // drawn radius
export const STEP_HIT = 52;    // tap target, both axes

// Row heights. The compact one is for a page carrying more than one location.
export const ROW_H = 76;
export const ROW_H_COMPACT = 54;

// The row's card: a panel with a 4px accent stripe down its left edge. Green
// for a location, gold for the quest and side quests - the stripe is what
// makes the sections scannable without reading their headers.
export function progRowCard(ctx, x, y, w, h, accent) {
  panel(ctx, x, y, w, h, pal.card, pal.border);
  ctx.fillStyle = accent;
  ctx.fillRect(x, y, 4, h);
}

// Well plus fill. AMBER at target, not the row's accent: at-target is the one
// state the player has to notice, and it is the same amber the value token
// uses for it.
export function fillBar(ctx, x, y, w, h, prog, pts, accent, atTarget) {
  if (w <= 0) return;
  ctx.fillStyle = pal.well;
  ctx.fillRect(x, y, w, h);
  const fw = Math.floor(w * Math.min(1, pts ? prog / pts : 0));
  if (fw > 0) {
    ctx.fillStyle = atTarget ? pal.amber : accent;
    ctx.fillRect(x, y, fw, h);
  }
}

// Entity mark: "l" a signpost, "q" a quest card, anything else a side quest
// card. Drawn rather than an icon mask so it inherits the row's accent pen.
export function glyph(ctx, kind, x, y, pen) {
  ctx.fillStyle = pen;
  if (kind === "l") {
    ctx.fillRect(x + 7, y + 2, 2, 16);
    ctx.fillRect(x, y + 4, 11, 6);
    ctx.beginPath();
    ctx.moveTo(x + 11, y + 4);
    ctx.lineTo(x + 11, y + 10);
    ctx.lineTo(x + 16, y + 7);
    ctx.closePath();
    ctx.fill();
    ctx.fillRect(x + 4, y + 17, 8, 2);
  } else if (kind === "q") {
    ctx.fillRect(x + 1, y + 1, 14, 18);
    ctx.fillStyle = pal.card;
    ctx.fillRect(x + 3, y + 3, 10, 14);
    ctx.fillStyle = pen;
    for (const dy of [6, 9]) ctx.fillRect(x + 5, y + dy, 6, 1);
    ctx.fillRect(x + 5, y + 12, 4, 1);
  } else {
    ctx.fillRect(x, y + 3, 18, 14);
    ctx.fillStyle = pal.card;
    ctx.fillRect(x + 2, y + 5, 14, 10);
    ctx.fillStyle = pen;
    ctx.fillRect(x + 4, y + 8, 8, 1);
    ctx.fillRect(x + 4, y + 11, 5, 1);
  }
}

// "progress / target" between one big - and one big +.
//
// The value carries its own denominator, so the row needs no second editor for
// the target. Both discs go dead at their limit and stop registering a button:
// - at 0, and + at the target, because RR p.22 discards excess on advance, so
// there is nothing past it to record.
//
// Returns the cluster's left edge, so the caller can size the bar and the
// row's tap band against whatever this took.
export function stepperCluster(ctx, buttons, cxPlus, cy, prog, pts, atTarget,
                               idMinus, idPlus, r = STEP_R, hit = STEP_HIT) {
  const val = `${prog} / ${pts}`;
  const vw = measureText(val, DISPLAY);
  const cxMinus = cxPlus - (vw + 2 * r + 26);
  const vx = cxMinus + r + 13;
  const h = Math.floor(hit / 2);
  for (const [cx, mark, on, bid] of [[cxMinus, "-", prog > 0, idMinus],
                                     [cxPlus, "+", !atTarget, idPlus]]) {
    disc(ctx, cx, cy, r, on ? pal.btn : pal.card_hi);
    arcRuns(ctx, cx, cy, r, r - 2, 0, 360, on ? pal.bevel_l : pal.border);
    textCenter(ctx, mark, cx, cy - 8, DISPLAY, on ? pal.tan : pal.dim);
    if (on) buttons.push(new Button(bid, cx - h, cy - h, hit, hit));
  }
  textLeft(ctx, val, vx, cy - 12, DISPLAY, atTarget ? pal.amber : pal.gold);
  return cxMinus - r;
}
