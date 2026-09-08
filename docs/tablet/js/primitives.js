import { h, raw, cx } from "./dom.js";
import { CHROME } from "./copy.js";
import { glyph } from "./glyphs.js";

// The app's own reload.
//
// Not a debugging convenience: added to the Home Screen (the manifest's
// display: standalone) or in Fullscreen, this app has no browser chrome at
// all, so there is otherwise NO way to reload it - and a reload is the one
// recovery a player has when a render goes wrong, since the game itself is
// durable in storage and comes back exactly as it was.
//
// It says what it does. A bare circular-arrow glyph in the corner is
// ambiguous with "undo" and with "restart the game", and a title attribute
// does not help: there is no hover on a tablet. Quiet, not hidden - it reads
// as part of the frame rather than as a control anyone needs.
//
// `inline` seats it in the strip's own tool cluster beside Menu instead of
// floating over the corner. On the play screen the corner is already spoken
// for, and two controls a few pixels apart, one of them floating, is not a
// cluster - it is a collision.
export function reloadButton({ inline = false } = {}) {
  return h`<button type="button" class="${cx("app-reload", inline && "app-reload-inline")}" data-act="reload_app" aria-label="${CHROME.refresh}">${raw(glyph("reload", 20))}<span class="label">${CHROME.reload}</span></button>`;
}

// Bevelled = tappable: the HUD's one chrome rule, kept. Every button is a
// real <button> with a data-act; app.js delegates on it.
export function chip({ act, arg = "", label, tone = "gold", height = 44, extraClass = "" }) {
  return h`<button type="button" class="${cx("chip", "chip-" + tone, extraClass)}" style="height:${height}px" data-act="${act}" data-arg="${arg}">${raw(label)}</button>`;
}

// `section` (Task 3, milestone 5) is a Rules Reference section id
// (rules_map.js's sectionsFor()) - when given, the band grows a trailing
// "Rules §n ›" row that opens the Rules sheet (sheet_rules.js) on that
// section. quest_setup/quest_sailing's bands never pass one (rules_map.js's
// own comment on why), so they stay chip-less exactly as before.
// An action-window band SAYS SO. It is the one thing in the round a player
// may choose to do - "An action ability may only be triggered during an action
// window" (Rules Reference, Action Windows) - so it gets a heading naming
// itself rather than being a differently-coloured paragraph among paragraphs.
// A framework band needs no heading: it is what happens anyway, and every
// other band on the screen is one.
export function band({ kind, text, sub = null, section = null }) {
  // The rules reference is a CORNER LABEL, not a button. It was a full chip
  // sitting under the text - a 44px bevelled control, the same weight as the
  // things a player actually taps to change the game, for what is a citation.
  // The whole band is the tap target instead, so the reference names itself
  // where a citation belongs (top right, on the heading's own line) and the
  // thing you reach for is the section you are reading.
  const cite = section
    ? raw(h`<span class="label band-cite">§${section}</span>`) : "";
  const head = kind === "window"
    ? raw(h`<div class="label band-kind">${CHROME.actionWindow}</div>`) : "";
  const body = h`<div class="band-head">${head}${cite}</div><p class="body">${text}</p>${sub ? raw(h`<p class="body secondary">${sub}</p>`) : ""}`;
  const cls = cx("band", "band-" + kind, section && "band-cited");
  // No section, no citation, nothing to open - it stays an inert block rather
  // than a control that does nothing.
  if (!section) return h`<div class="${cls}"><div class="band-text">${raw(body)}</div></div>`;
  return h`<button type="button" class="${cls}" data-act="open_rules" data-arg="${section}"><div class="band-text">${raw(body)}</div></button>`;
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
// ONE off state, on both surfaces: an inert, unbevelled <span> carrying no
// data-act - nothing for app.js's delegation to catch, exactly like .step-off
// above, and the same shape the log screen's own Rewind CTA uses when no row
// is selected. A `disabled` <button> that kept its act was tried on the log
// screen and dropped in the milestone-4 fix wave: it is a second way to say
// the same thing, and the bevel is the client's one signal for "tappable".
export function transportButton({ act, glyph, on, title }) {
  // `glyph` is markup now (glyphs.js's inline SVG), not a character, so it is
  // interpolated raw. It used to be a literal "\u23EE"/"\u25C0" and friends,
  // which iOS renders as full-colour emoji.
  if (on) return h`<button type="button" class="tbtn" data-act="${act}" title="${title}">${raw(glyph)}</button>`;
  return h`<span class="tbtn is-off" title="${title}">${raw(glyph)}</span>`;
}
