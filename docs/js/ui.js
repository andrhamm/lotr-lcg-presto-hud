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

export const pal = {
  bg: rgb(16, 12, 9), card: rgb(36, 32, 21), card_hi: rgb(48, 44, 29),
  border: rgb(60, 54, 35), border_gold: rgb(150, 118, 48),
  gold: rgb(214, 180, 110), tan: rgb(200, 186, 144), muted: rgb(180, 162, 118),
  dim: rgb(162, 146, 100), green: rgb(136, 168, 92), amber: rgb(214, 164, 70),
  red: rgb(247, 101, 62), btn: rgb(52, 42, 26), btn_ok: rgb(40, 50, 26),
  ok_fg: rgb(158, 196, 104), btn_no: rgb(56, 26, 18), no_fg: rgb(224, 112, 80),
  tab_active: rgb(30, 24, 15), bevel_l: rgb(96, 86, 54), bevel_d: rgb(7, 5, 3),
  shadow: rgb(34, 30, 24),
  purple: rgb(166, 122, 196), outline: rgb(0, 0, 0), well: rgb(24, 20, 12),
  value: rgb(214, 180, 110), brown: rgb(104, 70, 34),
  row_stripe: rgb(66, 60, 42),
  // placeholder fill for undrawn scenario/set icons (Scenario Options - real
  // icons land in a later sub-project)
  iconslot: rgb(44, 40, 28),
  // parchment fill for the Quest Setup scroll-style tip (deliberately
  // distinct from the standard note-panel card_hi background)
  scroll: rgb(30, 26, 17),
  threatPen(t) { return t >= 35 ? this.red : t >= 20 ? this.amber : this.green; },
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

export function notePanel(ctx, x, y, w, text, scale = 2, reserveRight = 0, icon) {
  const mask = icon === undefined ? icons.PIPE : icon;
  const isz = mask ? mask[0] : 0;
  const gutter = mask !== false && mask ? isz + 14 : 0;
  const paras = Array.isArray(text) ? text : [text];
  const usable = w - 16 - 12 - gutter - reserveRight;
  const lines = [];
  for (const p of paras) lines.push(...wrapText(p, scale, usable));
  const lh = 10 * scale + 6;
  const h = Math.max(lines.length * lh + 16, gutter ? isz + 14 : 0);
  rect(ctx, x, y, w, h, pal.card_hi);
  rect(ctx, x, y, 4, h, pal.border_gold);
  if (gutter) icons.drawIcon(ctx, mask, x + 10, y + 8, pal.gold);   // top-left, not centered
  let ty = y + 8;
  for (const s of lines) {
    textLeft(ctx, s, x + 12 + gutter, ty, scale, pal.muted);
    ty += lh;
  }
  return h;
}

const PHASE_CAPTIONS = { framework: "FRAMEWORK", window: "YOUR WINDOW" };

// Framework(red)/window(green) phase-guidance panel - the semantic
// sibling of notePanel(). `sections` is an ordered list of
// {kind, text} ("framework"|"window"; text is a string or paragraph
// array). A phase with no mandatory framework step just omits that
// entry - nothing is drawn for it. Returns the panel height.
export function phaseBlock(ctx, x, y, w, sections, reserveRight = 0) {
  const usable = w - 16 - 12 - reserveRight;
  const laid = sections.map(({ kind, text }) => {
    const body = Array.isArray(text) ? text.join(" ") : text;
    const lines = wrapText(body, 2, usable);
    return { kind, lines, h: 14 + lines.length * 24 };
  });
  const h = 8 + laid.reduce((s, sec) => s + sec.h, 0);
  rect(ctx, x, y, w, h, pal.card_hi);
  let ty = y + 4;
  for (const sec of laid) {
    const accent = sec.kind === "framework" ? pal.red : pal.green;
    rect(ctx, x, ty, 4, sec.h, accent);
    textLeft(ctx, PHASE_CAPTIONS[sec.kind], x + 12, ty + 2, 1, accent);
    let ly = ty + 16;
    for (const s of sec.lines) { textLeft(ctx, s, x + 12, ly, 2, pal.muted); ly += 24; }
    ty += sec.h;
  }
  return h;
}

// Live head-to-head bar: willpower (gold, left) vs staging threat (dark
// pal.outline, right - never red, per design/stat-system.md). The
// "willpower vs staging, live" stat from design/design-review.md's
// Quest-Staging row. Reuses the existing outcome-sentence wording
// verbatim. Fixed height: 64.
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
