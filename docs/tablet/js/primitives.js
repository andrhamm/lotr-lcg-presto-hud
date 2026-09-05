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
