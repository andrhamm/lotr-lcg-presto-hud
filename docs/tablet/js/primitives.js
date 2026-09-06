import { h, raw, cx } from "./dom.js";

// Bevelled = tappable: the HUD's one chrome rule, kept. Every button is a
// real <button> with a data-act; app.js delegates on it.
export function chip({ act, arg = "", label, tone = "gold", height = 44, extraClass = "" }) {
  return h`<button type="button" class="${cx("chip", "chip-" + tone, extraClass)}" style="height:${height}px" data-act="${act}" data-arg="${arg}">${raw(label)}</button>`;
}

export function band({ kind, text, sub = null }) {
  return h`<div class="${cx("band", "band-" + kind)}"><div class="band-text"><p class="body">${text}</p>${sub ? raw(h`<p class="body secondary">${sub}</p>`) : ""}</div></div>`;
}

export function counter({ label, icon, value, act, arg = "" }) {
  return h`<div class="counter"><div class="label">${label}</div><div class="counter-row">
<button type="button" class="step" data-act="${act}-" data-arg="${arg}">&minus;</button>
<div class="counter-value"><span class="num num-64">${value}</span>${raw(icon)}</div>
<button type="button" class="step" data-act="${act}+" data-arg="${arg}">+</button></div></div>`;
}

// `chip` is an already-rendered chip() button (raw html), pushed to the far
// right of the header by CSS (.zone-head .chip) - the milestone-3 rail's one
// tap target per zone, "Edit ›" (design spec, "The left column").
export function zone({ name, icon, edge, ground, body, chip = "" }) {
  return h`<section class="${cx("zone", "zone-" + edge, "ground-" + ground)}"><header class="zone-head">${raw(icon)}<span class="label">${name}</span>${chip ? raw(chip) : ""}</header><div class="zone-body">${raw(body)}</div></section>`;
}

export function cta({ act, arg = "", label, tone = "ok", grow = true }) {
  return h`<button type="button" class="${cx("cta", "cta-" + tone, grow && "grow")}" data-act="${act}" data-arg="${arg}">${raw(label)}</button>`;
}

// The strip's transport (Task 2) and the Game Log's six-control one (Task 3) -
// one home so the two never drift. `on` is canUndo()/canRedo() for the
// undo/redo pair, or a fixed availability check for first/last: when false
// there is nowhere to move.
//
// Two shapes for that off state, and the difference is the surface. On the
// strip the control sits among live play controls, so it drops to an inert,
// unbevelled <span> - nothing for app.js's delegation to catch, exactly like
// .step-off above. On the Game Log the transport IS the screen's instrument:
// each glyph's act is what names it, so `keepAct` keeps the <button> and
// marks it `disabled` instead. A disabled button fires no click event at
// all, so delegation still never sees it - same "not a tap target" property,
// written the way HTML already has a word for.
export function transportButton({ act, glyph, on, title, keepAct = false }) {
  if (on) return h`<button type="button" class="tbtn" data-act="${act}" title="${title}">${glyph}</button>`;
  return keepAct
    ? h`<button type="button" class="tbtn is-off" data-act="${act}" title="${title}" disabled>${glyph}</button>`
    : h`<span class="tbtn is-off" title="${title}">${glyph}</span>`;
}
