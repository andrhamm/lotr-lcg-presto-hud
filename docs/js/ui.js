// Port of ui/theme.py + ui/widgets.py onto canvas. Text uses the device's
// bitmap8 advance metrics so layout is pixel-identical to the Presto.
import { measureText, BITMAP8_W } from "./metrics.js";
import * as icons from "./icons.js";

export const NOWRAP = 10000; // parity with widgets.py (canvas never auto-wraps)

const rgb = (r, g, b) => `rgb(${r},${g},${b})`;

export const pal = {
  bg: rgb(16, 12, 9), card: rgb(36, 32, 21), card_hi: rgb(48, 44, 29),
  border: rgb(60, 54, 35), border_gold: rgb(150, 118, 48),
  gold: rgb(214, 180, 110), tan: rgb(200, 186, 144), muted: rgb(146, 132, 96),
  dim: rgb(100, 90, 62), green: rgb(136, 168, 92), amber: rgb(214, 164, 70),
  red: rgb(206, 84, 52), btn: rgb(52, 42, 26), btn_ok: rgb(40, 50, 26),
  ok_fg: rgb(158, 196, 104), btn_no: rgb(56, 26, 18), no_fg: rgb(224, 112, 80),
  tab_active: rgb(30, 24, 15), bevel_l: rgb(96, 86, 54), bevel_d: rgb(7, 5, 3),
  purple: rgb(166, 122, 196), outline: rgb(0, 0, 0), well: rgb(24, 20, 12),
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
    drawGlyphs(ctx, s, x + off, y + off, scale, pal.bevel_d);
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
